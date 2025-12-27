#!/usr/bin/env python3
"""Quick script to check specific record in database."""

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
        
        # Check total count
        cursor.execute("SELECT COUNT(*) FROM dbo.AzureRetailPrices")
        count = cursor.fetchone()[0]
        print(f"Total records: {count}")
        
        # Check for the specific record mentioned in error
        cursor.execute("""
            SELECT meterId, effectiveStartDate, currencyCode, retailPrice, meterName, serviceName
            FROM dbo.AzureRetailPrices
            WHERE meterId = '000009d0-057f-5f2b-b7e9-9e26add324a8'
              AND currencyCode = 'USD'
        """)
        row = cursor.fetchone()
        if row:
            print(f"\nFound the 'duplicate' record:")
            print(f"  meterId: {row[0]}")
            print(f"  effectiveStartDate: {row[1]}")
            print(f"  currencyCode: {row[2]}")
            print(f"  retailPrice: {row[3]}")
            print(f"  meterName: {row[4]}")
            print(f"  serviceName: {row[5]}")
        else:
            print("\nThe 'duplicate' record doesn't exist in the table")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
