"""
Shared Azure SQL Database Authentication Module
Provides Managed Identity authentication for Azure Functions and Web Apps
"""
import os
import struct
import logging
from dataclasses import dataclass
from typing import Optional
from contextlib import contextmanager
import pyodbc
from azure.identity import DefaultAzureCredential, AzureCliCredential, ChainedTokenCredential
from azure.core.exceptions import ClientAuthenticationError


logger = logging.getLogger(__name__)


# Constants
SQL_COPT_SS_ACCESS_TOKEN = 1256  # pyodbc constant for access token authentication
SQL_DATABASE_SCOPE = "https://database.windows.net/.default"
DEFAULT_ODBC_DRIVER = "ODBC Driver 18 for SQL Server"
DEFAULT_CONNECTION_TIMEOUT = 30
DEFAULT_SQL_PORT = 1433


@dataclass(frozen=True)
class SqlDatabaseConfig:
    """Configuration for Azure SQL Database connection"""
    server_fqdn: str
    database_name: str
    driver: str = DEFAULT_ODBC_DRIVER
    connection_timeout: int = DEFAULT_CONNECTION_TIMEOUT
    port: int = DEFAULT_SQL_PORT
    
    @classmethod
    def from_environment(cls) -> 'SqlDatabaseConfig':
        """Create configuration from environment variables"""
        server_fqdn = os.environ.get("SQL_SERVER_FQDN")
        database_name = os.environ.get("SQL_DATABASE_NAME")
        
        if not server_fqdn:
            raise ValueError("SQL_SERVER_FQDN environment variable is required")
        if not database_name:
            raise ValueError("SQL_DATABASE_NAME environment variable is required")
        
        return cls(
            server_fqdn=server_fqdn,
            database_name=database_name,
            driver=os.environ.get("SQL_DRIVER", DEFAULT_ODBC_DRIVER),
            connection_timeout=int(os.environ.get("SQL_CONNECTION_TIMEOUT", DEFAULT_CONNECTION_TIMEOUT))
        )


class AzureSqlAuthenticator:
    """
    Handles authentication to Azure SQL Database using Managed Identity
    Supports both Azure-hosted (Managed Identity) and local development (Azure CLI)
    """
    
    def __init__(self, config: Optional[SqlDatabaseConfig] = None):
        """
        Initialize the authenticator
        
        Args:
            config: SQL Database configuration. If None, reads from environment variables.
        """
        self.config = config or SqlDatabaseConfig.from_environment()
        
        # Initialize credential chain (Managed Identity first, then Azure CLI for local dev)
        self._credential = ChainedTokenCredential(
            DefaultAzureCredential(),
            AzureCliCredential()
        )
        
        logger.info(f"Initialized authenticator for {self.config.server_fqdn}/{self.config.database_name}")
    
    def get_access_token(self) -> bytes:
        """
        Get Azure SQL Database access token and encode it for pyodbc
        
        Returns:
            Token struct in the format required by pyodbc SQL_COPT_SS_ACCESS_TOKEN
            
        Raises:
            ClientAuthenticationError: If authentication fails
            ValueError: If token encoding fails
        """
        try:
            # Get access token for Azure SQL Database
            token = self._credential.get_token(SQL_DATABASE_SCOPE)
            
            if not token or not token.token:
                raise ValueError("Received empty token from credential provider")
            
            # Encode token as UTF-16-LE bytes (required by SQL Server)
            token_bytes = token.token.encode("UTF-16-LE")
            
            # Pack into struct format expected by pyodbc
            # Format: <I (unsigned int for length) + variable length string
            token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
            
            logger.debug("Successfully acquired and encoded access token")
            return token_struct
            
        except ClientAuthenticationError:
            logger.error("Failed to acquire access token - check Managed Identity configuration")
            raise
        except (ValueError, struct.error) as e:
            logger.error(f"Token encoding failed: {e}")
            raise ValueError(f"Failed to encode authentication token: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error acquiring token: {e}")
            raise
    
    def get_connection(self) -> pyodbc.Connection:
        """
        Create and return a connection to Azure SQL Database using Managed Identity
        
        Returns:
            pyodbc.Connection object
            
        Raises:
            pyodbc.Error: If database connection fails
            ClientAuthenticationError: If authentication fails
        """
        try:
            # Get encoded access token
            token_struct = self.get_access_token()
            
            # Build connection string (no username/password)
            connection_string = (
                f"Driver={{{self.config.driver}}};"
                f"Server=tcp:{self.config.server_fqdn},{self.config.port};"
                f"Database={self.config.database_name};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout={self.config.connection_timeout};"
            )
            
            logger.info(f"Connecting to SQL Server: {self.config.server_fqdn}")
            
            # Connect with access token
            conn = pyodbc.connect(
                connection_string,
                attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct}
            )
            
            logger.info(f"Successfully connected to database: {self.config.database_name}")
            return conn
            
        except pyodbc.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            raise
    
    @contextmanager
    def connection(self):
        """
        Context manager for database connection lifecycle
        
        Usage:
            with authenticator.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
        """
        conn = None
        try:
            conn = self.get_connection()
            yield conn
            conn.commit()
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def test_connection(self) -> bool:
        """
        Test the database connection
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                cursor.close()
                
                if result and result.test == 1:
                    logger.info("Database connection test successful")
                    return True
                else:
                    logger.warning("Database connection test returned unexpected result")
                    return False
                
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False


# Convenience functions for backward compatibility
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
    if server_fqdn or database_name:
        config = SqlDatabaseConfig(
            server_fqdn=server_fqdn or os.environ["SQL_SERVER_FQDN"],
            database_name=database_name or os.environ["SQL_DATABASE_NAME"]
        )
        authenticator = AzureSqlAuthenticator(config)
    else:
        authenticator = AzureSqlAuthenticator()
    
    return authenticator.get_connection()


@contextmanager
def sql_connection(
    server_fqdn: Optional[str] = None,
    database_name: Optional[str] = None
):
    """
    Context manager for SQL Database connection using Managed Identity
    
    Usage:
        with sql_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
    
    Args:
        server_fqdn: SQL Server FQDN (optional, reads from env if not provided)
        database_name: Database name (optional, reads from env if not provided)
    
    Yields:
        pyodbc.Connection object
    """
    if server_fqdn or database_name:
        config = SqlDatabaseConfig(
            server_fqdn=server_fqdn or os.environ["SQL_SERVER_FQDN"],
            database_name=database_name or os.environ["SQL_DATABASE_NAME"]
        )
        authenticator = AzureSqlAuthenticator(config)
    else:
        authenticator = AzureSqlAuthenticator()
    
    with authenticator.connection() as conn:
        yield conn
