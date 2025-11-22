import os
import json
import pandas as pd
from pathlib import Path

def infer_schema_from_csv(file_path):
    """
    Read a CSV file and infer its schema (column names and simplified types).
    Returns a dict: {column_name: simplified_type}
    """
    try:
        # Read only first few rows to speed up inference
        df_sample = pd.read_csv(file_path, nrows=1000)
        df = pd.read_csv(file_path, dtype=str)  # fallback to string if needed
    except Exception as e:
        print(f"⚠️ Warning: Could not read {file_path}. Skipping. Error: {e}")
        return {}

    # Use pandas' type inference on full data (but avoid memory issues)
    try:
        df_full = pd.read_csv(file_path, low_memory=False)
    except Exception as e:
        print(f"⚠️ Warning: Full read failed for {file_path}. Using sample. Error: {e}")
        df_full = df_sample

    schema = {}
    for col in df_full.columns:
        series = df_full[col].dropna()

        if series.empty:
            schema[col] = "string"  # default if all null
            continue

        # Try to infer type
        try:
            # Temporarily coerce to numeric to test
            numeric_series = pd.to_numeric(series, errors='coerce')
            if not numeric_series.isna().all():
                if (numeric_series % 1 == 0).all():
                    schema[col] = "integer"
                else:
                    schema[col] = "float"
                continue
        except Exception:
            pass

        # Try boolean
        unique_vals = set(series.astype(str).str.lower())
        if unique_vals <= {'true', 'false', '1', '0', 'yes', 'no'}:
            schema[col] = "boolean"
            continue

        # Try datetime
        try:
            pd.to_datetime(series, errors='raise')
            schema[col] = "datetime"
            continue
        except (ValueError, TypeError):
            pass

        # Default to string
        schema[col] = "string"

    return schema

def main():
    folder_path = "exported_tables"
    output_file = "schemas.json"

    if not os.path.exists(folder_path):
        print(f"❌ Error: Folder '{folder_path}' does not exist.")
        return

    all_schemas = {}

    for file in Path(folder_path).glob("*.csv"):
        table_name = file.stem  # filename without .csv
        print(f"📄 Processing: {file.name}")
        schema = infer_schema_from_csv(file)
        all_schemas[table_name] = schema

    # Save to JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_schemas, f, indent=2)

    print(f"✅ Schemas saved to '{output_file}'")
    print(f"📊 Total tables processed: {len(all_schemas)}")

if __name__ == "__main__":
    main()