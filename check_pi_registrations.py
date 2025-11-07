#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

print("=== Available Tables ===\n")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    print(f"  - {table[0]}")

print("\n=== Checking Pi Registrations ===\n")

# Try different possible table names
for table_name in ['auto_registered_pis', 'registered_pis', 'pi_registrations', 'devices']:
    try:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cursor.fetchone():
            print(f"Found table: {table_name}\n")
            cursor.execute(f"""
                SELECT * FROM {table_name}
                WHERE device_id LIKE '%ce39%' OR device_id LIKE '%3ef9%' 
                OR pi_id LIKE '%ce39%' OR pi_id LIKE '%3ef9%'
            """)
            results = cursor.fetchall()
            
            # Get column names
            col_names = [description[0] for description in cursor.description]
            print(f"Columns: {col_names}\n")
            
            for row in results:
                for i, col in enumerate(col_names):
                    print(f"  {col}: {row[i]}")
                print()
            break
    except Exception as e:
        continue

conn.close()
