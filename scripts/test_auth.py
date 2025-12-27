#!/usr/bin/env python3
"""Test the shared authentication module"""

import sys
import os

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'shared'))

from azure_sql_auth import AzureSqlAuthenticator

def main():
    """Test the authentication and connection"""
    print("Testing Azure SQL Authentication with Managed Identity")
    print("=" * 60)
    
    # Initialize authenticator
    server = os.environ.get("SQL_SERVER_FQDN", "sql-pricing-dev-gwc.database.windows.net")
    database = os.environ.get("SQL_DATABASE_NAME", "sqldb-pricing-dev")
    
    print(f"Server: {server}")
    print(f"Database: {database}")
    print()
    
    try:
        authenticator = AzureSqlAuthenticator(server, database)
        print("✓ Authenticator initialized")
        
        # Test connection
        print("\nTesting database connection...")
        if authenticator.test_connection():
            print("✓ Connection test PASSED")
            
            # Get a connection and query data
            print("\nQuerying database...")
            conn = authenticator.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as record_count FROM dbo.AzureRetailPrices")
            row = cursor.fetchone()
            print(f"✓ Total pricing records: {row.record_count:,}")
            
            cursor.execute("SELECT TOP 1 snapshotId, currencyCode, status, itemCount FROM dbo.PriceSnapshotRuns ORDER BY startedUtc DESC")
            row = cursor.fetchone()
            if row:
                item_count = row.itemCount if row.itemCount else 0
                print(f"✓ Latest snapshot: {row.snapshotId} ({row.currencyCode}) - {row.status} - {item_count:,} items")
            
            cursor.close()
            conn.close()
            
            print("\n" + "=" * 60)
            print("✓ All authentication tests PASSED")
            return True
        else:
            print("✗ Connection test FAILED")
            return False
            
    except Exception as e:
        print(f"\n✗ Authentication test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
