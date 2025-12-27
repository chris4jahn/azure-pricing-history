"""
Shared Azure SQL Database Authentication Module
Provides Managed Identity authentication for Azure Functions and Web Apps
"""
import os
import struct
import logging
from typing import Optional
import pyodbc
from azure.identity import DefaultAzureCredential, AzureCliCredential, ChainedTokenCredential
from azure.core.exceptions import ClientAuthenticationError


logger = logging.getLogger(__name__)


class AzureSqlAuthenticator:
    """
    Handles authentication to Azure SQL Database using Managed Identity
    Supports both Azure-hosted (Managed Identity) and local development (Azure CLI)
    """
    
    def __init__(
        self,
        server_fqdn: Optional[str] = None,
        database_name: Optional[str] = None,
        driver: str = "ODBC Driver 18 for SQL Server",
        connection_timeout: int = 30
    ):
        """
        Initialize the authenticator
        
        Args:
            server_fqdn: SQL Server FQDN (e.g., 'server.database.windows.net')
            database_name: Database name
            driver: ODBC driver name
            connection_timeout: Connection timeout in seconds
        """
        self.server_fqdn = server_fqdn or os.environ.get("SQL_SERVER_FQDN")
        self.database_name = database_name or os.environ.get("SQL_DATABASE_NAME")
        self.driver = driver
        self.connection_timeout = connection_timeout
        
        if not self.server_fqdn:
            raise ValueError("SQL_SERVER_FQDN must be provided or set in environment")
        if not self.database_name:
            raise ValueError("SQL_DATABASE_NAME must be provided or set in environment")
        
        # Initialize credential chain (Managed Identity first, then Azure CLI for local dev)
        self._credential = ChainedTokenCredential(
            DefaultAzureCredential(),
            AzureCliCredential()
        )
        
        logger.info(f"Initialized authenticator for {self.server_fqdn}/{self.database_name}")
    
    def get_access_token(self) -> bytes:
        """
        Get Azure SQL Database access token and encode it for pyodbc
        
        Returns:
            Token struct in the format required by pyodbc SQL_COPT_SS_ACCESS_TOKEN
        """
        try:
            # Get access token for Azure SQL Database
            token = self._credential.get_token("https://database.windows.net/.default")
            
            # Encode token as UTF-16-LE bytes (required by SQL Server)
            token_bytes = token.token.encode("UTF-16-LE")
            
            # Pack into struct format expected by pyodbc
            # Format: <I (unsigned int for length) + variable length string
            token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
            
            logger.debug("Successfully acquired and encoded access token")
            return token_struct
            
        except ClientAuthenticationError as e:
            logger.error(f"Failed to acquire access token: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error acquiring token: {e}")
            raise
    
    def get_connection(self) -> pyodbc.Connection:
        """
        Create and return a connection to Azure SQL Database using Managed Identity
        
        Returns:
            pyodbc.Connection object
        """
        try:
            # Get encoded access token
            token_struct = self.get_access_token()
            
            # Build connection string (no username/password)
            connection_string = (
                f"Driver={{{self.driver}}};"
                f"Server=tcp:{self.server_fqdn},1433;"
                f"Database={self.database_name};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout={self.connection_timeout};"
            )
            
            logger.info(f"Connecting to SQL Server: {self.server_fqdn}")
            
            # Connect with access token (SQL_COPT_SS_ACCESS_TOKEN = 1256)
            conn = pyodbc.connect(
                connection_string,
                attrs_before={1256: token_struct}
            )
            
            logger.info(f"Successfully connected to database: {self.database_name}")
            return conn
            
        except pyodbc.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test the database connection
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result and result.test == 1:
                logger.info("Database connection test successful")
                return True
            else:
                logger.warning("Database connection test returned unexpected result")
                return False
                
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False


def get_sql_connection(
    server_fqdn: Optional[str] = None,
    database_name: Optional[str] = None
) -> pyodbc.Connection:
    """
    Convenience function to get a SQL Database connection using Managed Identity
    
    Args:
        server_fqdn: SQL Server FQDN (optional, reads from env if not provided)
        database_name: Database name (optional, reads from env if not provided)
    
    Returns:
        pyodbc.Connection object
    """
    authenticator = AzureSqlAuthenticator(server_fqdn, database_name)
    return authenticator.get_connection()
