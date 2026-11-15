"""Synthetic data generator for AutoAnalyst test and demo datasets.

Generates reproducible e-commerce datasets without external network requests.
"""

import csv
import datetime
import os
import random

SAMPLE_CATEGORIES = {
    "Electronics": ["Smartphone", "Wireless Headphones", "Laptop Pro", "Smartwatch", "4K Monitor"],
    "Apparel": ["Running Shoes", "Denim Jacket", "Cotton T-Shirt", "Wool Sweater", "Backpack"],
    "Home & Kitchen": ["Espresso Maker", "Air Fryer", "Blender 3000", "Cookware Set", "Chef Knife"],
    "Beauty": ["Hydrating Serum", "Moisturizer SPF50", "Face Cleanser", "Shampoo Bar", "Lip Balm"],
    "Sports": ["Yoga Mat", "Dumbbells 15lb", "Resistance Bands", "Water Bottle", "Tennis Racket"],
}

SEGMENTS = ["Consumer", "Corporate", "Small Business"]
REGIONS = ["North", "South", "East", "West"]


def generate_records(num_rows: int = 500) -> list:
    random.seed(42)  # Deterministic seed for reproducible testing
    start_date = datetime.date(2026, 1, 1)
    records = []

    for idx in range(1, num_rows + 1):
        category = random.choice(list(SAMPLE_CATEGORIES.keys()))
        product = random.choice(SAMPLE_CATEGORIES[category])
        days_offset = random.randint(0, 300)
        order_date = start_date + datetime.timedelta(days=days_offset)
        quantity = random.randint(1, 8)
        unit_price = round(random.uniform(15.0, 450.0), 2)
        sales = round(quantity * unit_price, 2)
        discount = round(random.choice([0.0, 0.05, 0.1, 0.15, 0.2]), 2)
        profit = round(sales * (1.0 - discount) * random.uniform(0.15, 0.45), 2)
        segment = random.choice(SEGMENTS)
        region = random.choice(REGIONS)

        records.append({
            "order_id": f"ORD-{20260000 + idx}",
            "order_date": order_date.isoformat(),
            "category": category,
            "product_name": product,
            "sales": sales,
            "quantity": quantity,
            "discount": discount,
            "profit": profit,
            "customer_segment": segment,
            "region": region,
        })

    return records


def save_csv(records: list, output_path: str):
    fieldnames = list(records[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main():
    target_dir = os.path.dirname(os.path.abspath(__file__))
    records = generate_records(500)

    csv_path = os.path.join(target_dir, "ecommerce_sales.csv")
    save_csv(records, csv_path)
    print(f"Generated synthetic CSV dataset at: {csv_path} ({len(records)} rows)")

    # Also generate Parquet if pyarrow/pandas is available
    parquet_path = os.path.join(target_dir, "ecommerce_sales.parquet")
    try:
        import pandas as pd
        df = pd.DataFrame(records)
        df.to_parquet(parquet_path, index=False)
        print(f"Generated synthetic Parquet dataset at: {parquet_path}")
    except Exception as e:
        print(f"Note: Parquet export skipped (optional in host environment): {e}")


if __name__ == "__main__":
    main()
