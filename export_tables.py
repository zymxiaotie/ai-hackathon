# export_tables.py
from modules.db_connection import get_postgres_connection
import csv
import os

# Create output directory
output_dir = "exported_tables"
os.makedirs(output_dir, exist_ok=True)

with get_postgres_connection() as conn:
    cur = conn.cursor()
    
    # Get all table names
    cur.execute("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
        ORDER BY tablename
    """)
    tables = [row['tablename'] for row in cur.fetchall()]
    
    print(f"Found {len(tables)} tables. Exporting...\n")
    
    for table in tables:
        print(f"Exporting {table}...", end=" ")
        
        # Get all data from table
        cur.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()
        
        if rows:
            # Get column names
            columns = [desc[0] for desc in cur.description]
            
            # Write to CSV
            csv_path = os.path.join(output_dir, f"{table}.csv")
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
            
            print(f"✅ {len(rows)} rows")
        else:
            print("⚠️  Empty table")
    
    print(f"\n✅ All tables exported to '{output_dir}/' directory")