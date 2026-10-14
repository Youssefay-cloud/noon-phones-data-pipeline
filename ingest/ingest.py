"""Clean the scraped Noon phones CSV and load it into PostgreSQL in one go."""
import re

import click
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# Types of the CLEAN table (after parsing). Change a type here to change it in the database.
DTYPES = {
    "brand": "string",
    "phone": "string",
    "price": "float64",
    "old_price": "float64",
    "rating": "float64",
    "rating_count": "Int64",
    "best_seller_rank": "Int64",
    "category": "string",
    "vendor": "string",
    "delivery": "string",
    "ram_gb": "float64",
    "storage_gb": "float64",
    "battery_mah": "Int64",
    "screen_in": "float64",
    "link": "string",
    "img": "string",
}

UNIT_TO_GB = {"TB": 1024, "GB": 1, "MB": 1 / 1024}
SIZE = re.compile(r"(\d+(?:\.\d+)?)\s*(TB|GB|MB)\b", re.I)


def parse_memory(title):
    """Pull (ram_gb, storage_gb) out of a product title.

    "8GB RAM 256GB"        -> (8, 256)
    "16GB(8+8)RAM 256GB"   -> (8, 256)   physical RAM, the other 8 GB is virtual
    "4GB 64GB 4G"          -> (4, 64)    no 'RAM' word: first number is RAM
    "iPhone 15 128GB"      -> (None, 128)
    "8MB RAM 16MB 2G"      -> (0.008, 0.016)
    """
    sizes = [(m.start(), float(m.group(1)) * UNIT_TO_GB[m.group(2).upper()])
             for m in SIZE.finditer(title)]

    ram = None
    ram_pos = None
    virtual = re.search(r"(\d+)\s*GB\s*\((\d+)\+\d+\)\s*RAM", title, re.I)
    plain = re.search(r"(\d+(?:\.\d+)?)\s*(GB|MB)\s*RAM", title, re.I)
    if virtual:
        ram, ram_pos = float(virtual.group(2)), virtual.start()
    elif plain:
        ram = float(plain.group(1)) * UNIT_TO_GB[plain.group(2).upper()]
        ram_pos = plain.start()

    if ram is not None:                       # storage = the first other size in the title
        rest = [gb for pos, gb in sizes if pos != ram_pos]
        return ram, (rest[0] if rest else None)
    if len(sizes) >= 2:                       # "4GB 64GB": RAM first, storage second
        return sizes[0][1], sizes[1][1]
    if len(sizes) == 1 and sizes[0][1] >= 1:  # "iPhone 15 128GB": only storage is given
        return None, sizes[0][1]
    return None, None


def clean(df):
    df = df.drop_duplicates(subset="link").reset_index(drop=True)   # the same listing scraped twice

    out = pd.DataFrame()
    out["brand"] = df["phone"].str.split().str[0].str.title()       # NOKIA / Nokia -> Nokia
    out["phone"] = df["phone"]

    # "22,500" -> 22500.0
    out["price"] = pd.to_numeric(df["price"].str.replace(",", "", regex=False), errors="coerce")
    # "EGP\n 20999.00" -> 20999.0 ; "no discount" -> missing
    out["old_price"] = pd.to_numeric(df["before_discount"].str.extract(r"([\d.]+)")[0], errors="coerce")

    # "1768 Ratings" -> 1768 ; "No rating" -> 0
    out["rating_count"] = pd.to_numeric(df["rating_nums"].str.extract(r"(\d+)")[0], errors="coerce").fillna(0)
    out["rating"] = df["rating"].where(out["rating_count"] > 0)     # a rating with 0 reviews is not real

    # "Best Seller #8\nin\nSmartphones" -> rank 8, category Smartphones
    out["best_seller_rank"] = pd.to_numeric(df["ranking"].str.extract(r"#(\d+)")[0], errors="coerce")
    out["category"] = df["ranking"].str.extract(r"\nin\n(.+)$")[0]

    out["vendor"] = df["selling_vendor"].str.removeprefix("Sold by ")
    # "Get it Tomorrow\nOrder in 2h 55m" -> "Tomorrow" (the countdown is scrape-time noise)
    out["delivery"] = df["delivery"].str.split("\n").str[0].str.removeprefix("Get it ")

    mem = df["phone"].apply(parse_memory)
    out["ram_gb"] = [m[0] for m in mem]
    out["storage_gb"] = [m[1] for m in mem]

    # only half of the scraped rows have a specs block ("no specification" otherwise)
    out["battery_mah"] = pd.to_numeric(df["specific"].str.extract(r"Battery Size (\d+) mAh")[0], errors="coerce")
    out["screen_in"] = pd.to_numeric(df["specific"].str.extract(r"Screen Size ([\d.]+)")[0], errors="coerce")

    out["link"] = df["link"]
    out["img"] = df["img"].replace("No image", pd.NA)
    return out


@click.command()
@click.option("--pg-user", default="change_me", envvar="POSTGRES_USER", help="PostgreSQL user")
@click.option("--pg-pass", default="change_me", envvar="POSTGRES_PASSWORD", help="PostgreSQL password")
@click.option("--pg-host", default="localhost", envvar="POSTGRES_HOST", help="PostgreSQL host")
@click.option("--pg-port", default=5432, type=int, help="PostgreSQL port")
@click.option("--pg-db", default="noon", envvar="POSTGRES_DB", help="PostgreSQL database name")
@click.option("--target-table", default="noon_phones", help="Target table name")
@click.option("--csv-path", default="/data/NoonScraping3.csv", help="Path to the scraped CSV")
def run(pg_user, pg_pass, pg_host, pg_port, pg_db, target_table, csv_path):
    """Load the scraped Noon CSV into PostgreSQL in one go."""
    engine = create_engine(URL.create("postgresql+psycopg", pg_user, pg_pass, pg_host, pg_port, pg_db))

    raw = pd.read_csv(csv_path)
    df = clean(raw).astype(DTYPES)
    df.index = range(1, len(df) + 1)          # index starts at 1

    df.to_sql(name=target_table, con=engine, if_exists="replace", index=True, index_label="id")
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {target_table} ADD PRIMARY KEY (id)"))
    print(f"Loaded {len(df)} rows into {target_table} ({len(raw) - len(df)} duplicate row(s) removed)")


if __name__ == "__main__":
    run()
