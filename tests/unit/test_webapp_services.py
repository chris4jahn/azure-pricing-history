"""
Unit tests for web app services
"""
from unittest.mock import Mock, MagicMock, patch
import pytest

# Import module under test
from app import WebAppConfig, DatabaseQueryService, DEFAULT_CURRENCY


@pytest.mark.unit
class TestWebAppConfig:
    """Test WebAppConfig dataclass"""
    
    def test_create_config_with_defaults(self):
        """Test creating config with default currency"""
        from azure_sql_auth import SqlDatabaseConfig
        
        sql_config = SqlDatabaseConfig(
            server_fqdn="test.server.net",
            database_name="testdb"
        )
        config = WebAppConfig(sql_config=sql_config)
        
        assert config.sql_config == sql_config
        assert config.default_currency == DEFAULT_CURRENCY
    
    def test_create_config_with_custom_currency(self):
        """Test creating config with custom currency"""
        from azure_sql_auth import SqlDatabaseConfig
        
        sql_config = SqlDatabaseConfig(
            server_fqdn="test.server.net",
            database_name="testdb"
        )
        config = WebAppConfig(sql_config=sql_config, default_currency="EUR")
        
        assert config.default_currency == "EUR"
    
    def test_from_environment(self):
        """Test creating config from environment"""
        with patch('os.environ', {
            "SQL_SERVER_FQDN": "env.server.net",
            "SQL_DATABASE_NAME": "envdb",
            "DEFAULT_CURRENCY": "GBP"
        }):
            with patch('azure_sql_auth.SqlDatabaseConfig.from_environment') as mock_from_env:
                mock_sql_config = Mock()
                mock_from_env.return_value = mock_sql_config
                
                config = WebAppConfig.from_environment()
                
                assert config.sql_config == mock_sql_config


@pytest.mark.unit
class TestDatabaseQueryService:
    """Test DatabaseQueryService class"""
    
    @pytest.fixture
    def mock_conn(self):
        """Fixture for mock database connection"""
        return Mock()
    
    @pytest.fixture
    def query_service(self, mock_conn):
        """Fixture for DatabaseQueryService instance"""
        return DatabaseQueryService(mock_conn)
    
    def test_initialization(self, mock_conn):
        """Test query service initialization"""
        service = DatabaseQueryService(mock_conn)
        
        assert service.conn == mock_conn
    
    def test_get_summary_stats(self, query_service, mock_conn):
        """Test getting summary statistics"""
        mock_cursor = Mock()
        
        # Mock first query (overall stats)
        mock_row1 = Mock()
        mock_row1.totalMeters = 1000
        mock_row1.totalServices = 50
        mock_row1.totalRegions = 30
        mock_row1.totalCurrencies = 2
        mock_row1.lastUpdate = None
        
        # Mock second query (snapshot stats)
        mock_row2 = Mock()
        mock_row2.totalSnapshots = 10
        mock_row2.successfulSnapshots = 9
        mock_row2.lastSnapshotDate = None
        
        mock_cursor.fetchone.side_effect = [mock_row1, mock_row2]
        mock_conn.cursor.return_value = mock_cursor
        
        summary = query_service.get_summary_stats()
        
        assert summary['totalMeters'] == 1000
        assert summary['totalServices'] == 50
        assert summary['totalSnapshots'] == 10
        assert summary['successfulSnapshots'] == 9
        assert mock_cursor.execute.call_count == 2
        mock_cursor.close.assert_called_once()
    
    def test_get_top_services(self, query_service, mock_conn):
        """Test getting top services"""
        mock_cursor = Mock()
        
        mock_row1 = Mock()
        mock_row1.serviceName = "Virtual Machines"
        mock_row1.meterCount = 500
        mock_row1.avgPrice = 1.5
        mock_row1.minPrice = 0.1
        mock_row1.maxPrice = 10.0
        
        mock_row2 = Mock()
        mock_row2.serviceName = "Storage"
        mock_row2.meterCount = 300
        mock_row2.avgPrice = 0.5
        mock_row2.minPrice = 0.01
        mock_row2.maxPrice = 2.0
        
        mock_cursor.fetchall.return_value = [mock_row1, mock_row2]
        mock_conn.cursor.return_value = mock_cursor
        
        services = query_service.get_top_services(15, "USD")
        
        assert len(services) == 2
        assert services[0]['name'] == "Virtual Machines"
        assert services[0]['meterCount'] == 500
        assert services[1]['name'] == "Storage"
        mock_cursor.execute.assert_called_once()
    
    def test_get_region_pricing(self, query_service, mock_conn):
        """Test getting region pricing"""
        mock_cursor = Mock()
        
        mock_row = Mock()
        mock_row.armRegionName = "eastus"
        mock_row.meterCount = 200
        mock_row.avgPrice = 1.2
        
        mock_cursor.fetchall.return_value = [mock_row]
        mock_conn.cursor.return_value = mock_cursor
        
        regions = query_service.get_region_pricing("USD")
        
        assert len(regions) == 1
        assert regions[0]['region'] == "eastus"
        assert regions[0]['meterCount'] == 200
    
    def test_get_region_pricing_with_service_filter(self, query_service, mock_conn):
        """Test getting region pricing filtered by service"""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        
        query_service.get_region_pricing("USD", "Virtual Machines")
        
        # Verify service filter was added to query
        call_args = mock_cursor.execute.call_args[0]
        assert "Virtual Machines" in call_args
    
    def test_get_price_trends_for_meter(self, query_service, mock_conn):
        """Test getting price trends for specific meter"""
        mock_cursor = Mock()
        
        mock_row = Mock()
        mock_row.effectiveStartDate = Mock()
        mock_row.effectiveStartDate.isoformat.return_value = "2023-01-01"
        mock_row.retailPrice = 1.5
        mock_row.productName = "VM Product"
        
        mock_cursor.fetchall.return_value = [mock_row]
        mock_conn.cursor.return_value = mock_cursor
        
        trends = query_service.get_price_trends("USD", meter_id="meter123")
        
        assert len(trends) == 1
        assert trends[0]['date'] == "2023-01-01"
        assert trends[0]['price'] == 1.5
        assert trends[0]['productName'] == "VM Product"
    
    def test_get_price_trends_for_service(self, query_service, mock_conn):
        """Test getting price trends for service"""
        mock_cursor = Mock()
        
        mock_row = Mock()
        mock_row.effectiveStartDate = Mock()
        mock_row.effectiveStartDate.isoformat.return_value = "2023-01-01"
        mock_row.retailPrice = 2.0
        mock_row.productName = "Virtual Machines"
        
        mock_cursor.fetchall.return_value = [mock_row]
        mock_conn.cursor.return_value = mock_cursor
        
        trends = query_service.get_price_trends("USD", service="Storage")
        
        assert len(trends) == 1
        assert trends[0]['price'] == 2.0
    
    def test_get_snapshot_history(self, query_service, mock_conn):
        """Test getting snapshot history"""
        mock_cursor = Mock()
        
        mock_row = Mock()
        mock_row.snapshotId = "202312"
        mock_row.currencyCode = "USD"
        mock_row.startedUtc = Mock()
        mock_row.startedUtc.isoformat.return_value = "2023-12-01T00:00:00"
        mock_row.finishedUtc = Mock()
        mock_row.finishedUtc.isoformat.return_value = "2023-12-01T01:00:00"
        mock_row.status = "SUCCEEDED"
        mock_row.itemCount = 50000
        mock_row.durationSeconds = 3600
        mock_row.itemsPerSecond = 13.9
        
        mock_cursor.fetchall.return_value = [mock_row]
        mock_conn.cursor.return_value = mock_cursor
        
        snapshots = query_service.get_snapshot_history(20)
        
        assert len(snapshots) == 1
        assert snapshots[0]['snapshotId'] == "202312"
        assert snapshots[0]['status'] == "SUCCEEDED"
        assert snapshots[0]['itemCount'] == 50000
    
    def test_search_prices(self, query_service, mock_conn):
        """Test searching prices"""
        mock_cursor = Mock()
        
        mock_row = Mock()
        mock_row.meterId = "meter123"
        mock_row.productName = "Virtual Machine"
        mock_row.skuName = "Standard_D2s_v3"
        mock_row.serviceName = "Virtual Machines"
        mock_row.meterName = "D2s v3"
        mock_row.armRegionName = "eastus"
        mock_row.retailPrice = 1.5
        mock_row.unitOfMeasure = "1 Hour"
        mock_row.effectiveStartDate = Mock()
        mock_row.effectiveStartDate.isoformat.return_value = "2023-01-01"
        
        mock_cursor.fetchall.return_value = [mock_row]
        mock_conn.cursor.return_value = mock_cursor
        
        results = query_service.search_prices("virtual machine", "USD", 50)
        
        assert len(results) == 1
        assert results[0]['meterId'] == "meter123"
        assert results[0]['productName'] == "Virtual Machine"
        assert results[0]['price'] == 1.5
        
        # Verify search pattern was applied
        call_args = mock_cursor.execute.call_args[0]
        assert "%virtual machine%" in call_args
    
    def test_search_prices_with_null_price(self, query_service, mock_conn):
        """Test searching prices with null price value"""
        mock_cursor = Mock()
        
        mock_row = Mock()
        mock_row.meterId = "meter123"
        mock_row.productName = "Test"
        mock_row.skuName = "Test SKU"
        mock_row.serviceName = "Test Service"
        mock_row.meterName = "Test Meter"
        mock_row.armRegionName = "eastus"
        mock_row.retailPrice = None  # Null price
        mock_row.unitOfMeasure = "1 Hour"
        mock_row.effectiveStartDate = Mock()
        mock_row.effectiveStartDate.isoformat.return_value = "2023-01-01"
        
        mock_cursor.fetchall.return_value = [mock_row]
        mock_conn.cursor.return_value = mock_cursor
        
        results = query_service.search_prices("test", "USD", 50)
        
        assert results[0]['price'] == 0  # Should convert None to 0
