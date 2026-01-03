"""
Unit tests for azure_sql_auth module
"""
import os
import struct
from unittest.mock import Mock, MagicMock, patch, call
import pytest
from azure.core.exceptions import ClientAuthenticationError

# Import module under test
from azure_sql_auth import (
    SqlDatabaseConfig,
    AzureSqlAuthenticator,
    get_sql_connection,
    sql_connection,
    SQL_COPT_SS_ACCESS_TOKEN,
    SQL_DATABASE_SCOPE,
)


@pytest.mark.unit
class TestSqlDatabaseConfig:
    """Test SqlDatabaseConfig dataclass"""
    
    def test_create_config_with_required_params(self):
        """Test creating config with required parameters"""
        config = SqlDatabaseConfig(
            server_fqdn="test.database.windows.net",
            database_name="testdb"
        )
        
        assert config.server_fqdn == "test.database.windows.net"
        assert config.database_name == "testdb"
        assert config.driver == "ODBC Driver 18 for SQL Server"
        assert config.connection_timeout == 30
        assert config.port == 1433
    
    def test_config_is_frozen(self):
        """Test that config is immutable"""
        config = SqlDatabaseConfig(
            server_fqdn="test.database.windows.net",
            database_name="testdb"
        )
        
        with pytest.raises(AttributeError):
            config.server_fqdn = "new.server.net"
    
    def test_from_environment_success(self):
        """Test creating config from environment variables"""
        with patch.dict(os.environ, {
            "SQL_SERVER_FQDN": "env.database.windows.net",
            "SQL_DATABASE_NAME": "envdb",
            "SQL_DRIVER": "Custom Driver",
            "SQL_CONNECTION_TIMEOUT": "60"
        }):
            config = SqlDatabaseConfig.from_environment()
            
            assert config.server_fqdn == "env.database.windows.net"
            assert config.database_name == "envdb"
            assert config.driver == "Custom Driver"
            assert config.connection_timeout == 60
    
    def test_from_environment_missing_server(self):
        """Test error when SQL_SERVER_FQDN is missing"""
        with patch.dict(os.environ, {"SQL_DATABASE_NAME": "testdb"}, clear=True):
            with pytest.raises(ValueError, match="SQL_SERVER_FQDN environment variable is required"):
                SqlDatabaseConfig.from_environment()
    
    def test_from_environment_missing_database(self):
        """Test error when SQL_DATABASE_NAME is missing"""
        with patch.dict(os.environ, {"SQL_SERVER_FQDN": "test.server.net"}, clear=True):
            with pytest.raises(ValueError, match="SQL_DATABASE_NAME environment variable is required"):
                SqlDatabaseConfig.from_environment()


@pytest.mark.unit
class TestAzureSqlAuthenticator:
    """Test AzureSqlAuthenticator class"""
    
    @pytest.fixture
    def mock_config(self):
        """Fixture for test configuration"""
        return SqlDatabaseConfig(
            server_fqdn="test.database.windows.net",
            database_name="testdb",
            connection_timeout=30
        )
    
    @pytest.fixture
    def authenticator(self, mock_config):
        """Fixture for authenticator instance"""
        with patch('azure_sql_auth.ChainedTokenCredential'):
            return AzureSqlAuthenticator(mock_config)
    
    def test_initialization(self, mock_config):
        """Test authenticator initialization"""
        with patch('azure_sql_auth.ChainedTokenCredential') as mock_cred:
            auth = AzureSqlAuthenticator(mock_config)
            
            assert auth.config == mock_config
            mock_cred.assert_called_once()
    
    def test_initialization_with_defaults(self):
        """Test initialization without config uses environment"""
        with patch('azure_sql_auth.ChainedTokenCredential'):
            with patch('azure_sql_auth.SqlDatabaseConfig.from_environment') as mock_from_env:
                mock_config = SqlDatabaseConfig(
                    server_fqdn="env.server.net",
                    database_name="envdb"
                )
                mock_from_env.return_value = mock_config
                
                auth = AzureSqlAuthenticator()
                
                mock_from_env.assert_called_once()
                assert auth.config == mock_config
    
    def test_get_access_token_success(self, authenticator):
        """Test successful token acquisition"""
        mock_token = Mock()
        mock_token.token = "test-token-12345"
        authenticator._credential.get_token = Mock(return_value=mock_token)
        
        token_struct = authenticator.get_access_token()
        
        # Verify token was acquired with correct scope
        authenticator._credential.get_token.assert_called_once_with(SQL_DATABASE_SCOPE)
        
        # Verify token was properly encoded
        assert isinstance(token_struct, bytes)
        token_bytes = "test-token-12345".encode("UTF-16-LE")
        expected = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
        assert token_struct == expected
    
    def test_get_access_token_empty_token(self, authenticator):
        """Test error when token is empty"""
        mock_token = Mock()
        mock_token.token = None
        authenticator._credential.get_token = Mock(return_value=mock_token)
        
        with pytest.raises(ValueError, match="Received empty token"):
            authenticator.get_access_token()
    
    def test_get_access_token_auth_error(self, authenticator):
        """Test handling of authentication error"""
        authenticator._credential.get_token = Mock(
            side_effect=ClientAuthenticationError("Auth failed")
        )
        
        with pytest.raises(ClientAuthenticationError):
            authenticator.get_access_token()
    
    def test_get_connection_success(self, authenticator):
        """Test successful database connection"""
        mock_conn = Mock()
        mock_token_struct = b"token_data"
        
        with patch.object(authenticator, 'get_access_token', return_value=mock_token_struct):
            with patch('azure_sql_auth.pyodbc.connect', return_value=mock_conn) as mock_connect:
                conn = authenticator.get_connection()
                
                assert conn == mock_conn
                
                # Verify connection string
                call_args = mock_connect.call_args
                conn_string = call_args[0][0]
                assert "Driver={ODBC Driver 18 for SQL Server}" in conn_string
                assert "Server=tcp:test.database.windows.net,1433" in conn_string
                assert "Database=testdb" in conn_string
                assert "Encrypt=yes" in conn_string
                
                # Verify access token was passed
                assert call_args[1]['attrs_before'] == {SQL_COPT_SS_ACCESS_TOKEN: mock_token_struct}
    
    def test_get_connection_pyodbc_error(self, authenticator):
        """Test handling of pyodbc connection error"""
        with patch.object(authenticator, 'get_access_token', return_value=b"token"):
            with patch('azure_sql_auth.pyodbc.connect', side_effect=Exception("Connection failed")):
                with pytest.raises(Exception, match="Connection failed"):
                    authenticator.get_connection()
    
    def test_connection_context_manager_success(self, authenticator):
        """Test connection context manager with successful operation"""
        mock_conn = Mock()
        
        with patch.object(authenticator, 'get_connection', return_value=mock_conn):
            with authenticator.connection() as conn:
                assert conn == mock_conn
            
            # Verify commit was called
            mock_conn.commit.assert_called_once()
            mock_conn.close.assert_called_once()
    
    def test_connection_context_manager_with_error(self, authenticator):
        """Test connection context manager with error"""
        mock_conn = Mock()
        
        with patch.object(authenticator, 'get_connection', return_value=mock_conn):
            with pytest.raises(ValueError):
                with authenticator.connection() as conn:
                    raise ValueError("Test error")
            
            # Verify rollback was called, not commit
            mock_conn.rollback.assert_called_once()
            mock_conn.commit.assert_not_called()
            mock_conn.close.assert_called_once()
    
    def test_test_connection_success(self, authenticator):
        """Test successful connection test"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_result = Mock()
        mock_result.test = 1
        mock_cursor.fetchone.return_value = mock_result
        mock_conn.cursor.return_value = mock_cursor
        authenticator.get_connection = Mock(return_value=mock_conn)
        result = authenticator.test_connection()
        assert result is True
            result = authenticator.test_connection()
            
            assert result is True
            mock_cursor.execute.assert_called_once_with("SELECT 1 as test")
    
    def test_test_connection_failure(self, authenticator):
        """Test failed connection test"""
        with patch.object(authenticator, 'connection', side_effect=Exception("Connection failed")):
            result = authenticator.test_connection()
            
            assert result is False


@pytest.mark.unit
class TestConvenienceFunctions:
    """Test module-level convenience functions"""
    
    def test_get_sql_connection_with_params(self):
        """Test get_sql_connection with explicit parameters"""
        mock_conn = Mock()
        
        with patch('azure_sql_auth.AzureSqlAuthenticator') as mock_auth_class:
            mock_auth = Mock()
            mock_auth.get_connection.return_value = mock_conn
            mock_auth_class.return_value = mock_auth
            
            conn = get_sql_connection("server.net", "dbname")
            
            assert conn == mock_conn
            mock_auth.get_connection.assert_called_once()
    
    def test_get_sql_connection_from_environment(self):
        """Test get_sql_connection without parameters"""
        mock_conn = Mock()
        
        with patch('azure_sql_auth.AzureSqlAuthenticator') as mock_auth_class:
            mock_auth = Mock()
            mock_auth.get_connection.return_value = mock_conn
            mock_auth_class.return_value = mock_auth
            
            conn = get_sql_connection()
            
            assert conn == mock_conn
            mock_auth_class.assert_called_once_with()
    
    def test_sql_connection_context_manager(self):
        """Test sql_connection context manager"""
        mock_conn = Mock()
        with patch('azure_sql_auth.AzureSqlAuthenticator') as mock_auth_class:
            mock_auth = Mock()
            mock_auth.get_connection.return_value = mock_conn
            mock_auth_class.return_value = mock_auth
            with sql_connection() as conn:
                assert conn == mock_conn
            mock_auth.connection.__exit__.assert_called_once()
