#!/usr/bin/env python3
"""Quick script to check if pricing data exists in the database."""

import struct
import pyodbc
from azure.identity import DefaultAzureCredential

# Database connection details
server = "sql-pricing-dev-gwc.database.windows.net"
database = "sqldb-pricing-dev"

def get_db_connection():
    """Get database connection using managed identity."""
    credential = DefaultAzureCredential()
    token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("UTF-16-LE")
    token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
    
    connection_string = f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};DATABASE={database};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30"
    
    conn = pyodbc.connect(connection_string, attrs_before={1256: token_struct})
    return conn

def main():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check record count
        cursor.execute("SELECT COUNT(*) FROM dbo.AzureRetailPrices")
        count = cursor.fetchone()[0]
        print(f"Total pricing records: {count}")
        
        # Check snapshot runs
        cursor.execute("SELECT TOP 1 snapshotId, currencyCode, startedUtc, finishedUtc, status, itemCount FROM dbo.PriceSnapshotRuns ORDER BY startedUtc DESC")
        row = cursor.fetchone()
        if row:
            print(f"\nLatest snapshot run:")
            print(f"  ID: {row[0]}")
            print(f"  Currency: {row[1]}")
            print(f"  Started: {row[2]}")
            print(f"  Finished: {row[3]}")
            print(f"  Status: {row[4]}")
            print(f"  Items: {row[5]}")
        else:
            print("\nNo snapshot runs found")
        
        # Check some sample data
        if count > 0:
            cursor.execute("SELECT TOP 5 currencyCode, serviceName, meterName, retailPrice FROM dbo.AzureRetailPrices ORDER BY lastSeenUtc DESC")
            print(f"\nSample records:")
            for row in cursor.fetchall():
                print(f"  {row[0]} | {row[1]} | {row[2]} | ${row[3]}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
