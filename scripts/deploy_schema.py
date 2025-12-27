#!/usr/bin/env python3
"""
Deploy SQL schema to Azure SQL Database using Managed Identity
"""
import sys
from azure.identity import DefaultAzureCredential
import pyodbc

SQL_SERVER_FQDN = "sql-pricing-dev-gwc.database.windows.net"
SQL_DATABASE_NAME = "sqldb-pricing-dev"

def get_sql_connection():
    """Create SQL connection using Managed Identity/Azure AD"""
    print("Acquiring Azure AD token...")
    credential = DefaultAzureCredential()
    token = credential.get_token("https://database.windows.net/.default")
    
    # Convert token to bytes for pyodbc
    token_bytes = token.token.encode("utf-16-le")
    token_struct = bytes([0x01]) + len(token_bytes).to_bytes(2, byteorder='little') + token_bytes
    
    connection_string = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server=tcp:{SQL_SERVER_FQDN},1433;"
        f"Database={SQL_DATABASE_NAME};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30;"
    )
    
    print(f"Connecting to {SQL_SERVER_FQDN}...")
    conn = pyodbc.connect(
        connection_string,
        attrs_before={1256: token_struct}  # SQL_COPT_SS_ACCESS_TOKEN
    )
    print("Connected successfully!")
    return conn

def execute_sql_file(conn, file_path):
    """Execute SQL file with GO statement handling"""
    print(f"\nExecuting {file_path}...")
    
    with open(file_path, 'r') as f:
        sql_content = f.read()
    
    # Split by GO statements
    batches = [batch.strip() for batch in sql_content.split('\nGO\n') if batch.strip()]
    
    cursor = conn.cursor()
    
    for i, batch in enumerate(batches, 1):
        # Skip empty batches and comments-only batches
        if not batch or all(line.strip().startswith('--') for line in batch.split('\n') if line.strip()):
            continue
            
        try:
            print(f"  Executing batch {i}/{len(batches)}...")
            cursor.execute(batch)
            conn.commit()
            print(f"  ✓ Batch {i} completed")
        except Exception as e:
            print(f"  ✗ Error in batch {i}: {str(e)}")
            conn.rollback()
            raise
    
    cursor.close()
    print(f"✓ {file_path} completed successfully\n")

def main():
    try:
        # Connect to database
        conn = get_sql_connection()
        
        # Deploy schema
        execute_sql_file(conn, 'src/shared/sql/schema.sql')
        
        # Deploy views
        execute_sql_file(conn, 'src/shared/sql/views.sql')
        
        # Grant permissions to Function App
        print("Granting permissions to Function App managed identity...")
        cursor = conn.cursor()
        
        function_app_name = "func-pricing-dev-gwc"
        
        # Check if user exists
        check_sql = f"SELECT COUNT(*) FROM sys.database_principals WHERE name = '{function_app_name}'"
        cursor.execute(check_sql)
        exists = cursor.fetchone()[0]
        
        if not exists:
            print(f"  Creating user [{function_app_name}]...")
            cursor.execute(f"CREATE USER [{function_app_name}] FROM EXTERNAL PROVIDER")
            conn.commit()
        else:
            print(f"  User [{function_app_name}] already exists")
        
        print(f"  Adding to db_datareader role...")
        cursor.execute(f"ALTER ROLE db_datareader ADD MEMBER [{function_app_name}]")
        conn.commit()
        
        print(f"  Adding to db_datawriter role...")
        cursor.execute(f"ALTER ROLE db_datawriter ADD MEMBER [{function_app_name}]")
        conn.commit()
        
        cursor.close()
        print("✓ Permissions granted successfully\n")
        
        conn.close()
        
        print("=" * 60)
        print("DATABASE DEPLOYMENT COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Deployment failed: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
