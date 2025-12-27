"""
Unit tests for Azure Function pricing services
"""
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timezone
import pytest

# Add function path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "functions-python" / "PriceSnapshot"))

from __init__ import (
    PricingConfig,
    APIClient,
    DatabaseService,
    PricingService,
    DEFAULT_BATCH_SIZE,
    RUN_STATUS_SUCCEEDED,
    RUN_STATUS_FAILED,
)


@pytest.mark.unit
class TestPricingConfig:
    """Test PricingConfig dataclass"""
    
    def test_create_config_with_all_params(self):
        """Test creating config with all parameters"""
        config = PricingConfig(
            api_base_url="https://api.test.com",
            api_version="2023-01-01",
            currencies=["USD", "EUR"],
            batch_size=90,
            max_retries=5,
            request_timeout=120,
            sql_server_fqdn="test.database.windows.net",
            sql_database_name="testdb"
        )
        
        assert config.api_base_url == "https://api.test.com"
        assert config.currencies == ["USD", "EUR"]
        assert config.batch_size == 90
    
    def test_from_environment_with_defaults(self):
        """Test creating config from environment with defaults"""
        with patch.dict('os.environ', {
            "SQL_SERVER_FQDN": "env.server.net",
            "SQL_DATABASE_NAME": "envdb"
        }, clear=True):
            config = PricingConfig.from_environment()
            
            assert config.sql_server_fqdn == "env.server.net"
            assert config.sql_database_name == "envdb"
            assert config.batch_size == DEFAULT_BATCH_SIZE
            assert config.currencies == ["USD", "EUR"]
    
    def test_from_environment_with_custom_values(self):
        """Test creating config with custom environment values"""
        with patch.dict('os.environ', {
            "SQL_SERVER_FQDN": "test.server.net",
            "SQL_DATABASE_NAME": "testdb",
            "CURRENCIES": "USD,EUR,GBP",
            "BATCH_SIZE": "50",
            "MAX_RETRIES": "3"
        }):
            config = PricingConfig.from_environment()
            
            assert config.currencies == ["USD", "EUR", "GBP"]
            assert config.batch_size == 50
            assert config.max_retries == 3
    
    def test_validate_success(self):
        """Test validation with valid config"""
        config = PricingConfig(
            api_base_url="https://api.test.com",
            api_version="2023-01-01",
            currencies=["USD"],
            batch_size=90,
            max_retries=5,
            request_timeout=120,
            sql_server_fqdn="test.server.net",
            sql_database_name="testdb"
        )
        
        config.validate()  # Should not raise
    
    def test_validate_batch_size_too_small(self):
        """Test validation fails with batch size too small"""
        config = PricingConfig(
            api_base_url="https://api.test.com",
            api_version="2023-01-01",
            currencies=["USD"],
            batch_size=0,
            max_retries=5,
            request_timeout=120,
            sql_server_fqdn="test.server.net",
            sql_database_name="testdb"
        )
        
        with pytest.raises(ValueError, match="BATCH_SIZE must be between 1 and 95"):
            config.validate()
    
    def test_validate_batch_size_exceeds_sql_limit(self):
        """Test validation fails when batch size exceeds SQL parameter limit"""
        config = PricingConfig(
            api_base_url="https://api.test.com",
            api_version="2023-01-01",
            currencies=["USD"],
            batch_size=100,  # 100 * 22 = 2200 > 2100 limit
            max_retries=5,
            request_timeout=120,
            sql_server_fqdn="test.server.net",
            sql_database_name="testdb"
        )
        
        with pytest.raises(ValueError, match="would exceed SQL Server 2100 parameter limit"):
            config.validate()
    
    def test_validate_empty_currencies(self):
        """Test validation fails with empty currencies"""
        config = PricingConfig(
            api_base_url="https://api.test.com",
            api_version="2023-01-01",
            currencies=[],
            batch_size=90,
            max_retries=5,
            request_timeout=120,
            sql_server_fqdn="test.server.net",
            sql_database_name="testdb"
        )
        
        with pytest.raises(ValueError, match="At least one currency must be configured"):
            config.validate()


@pytest.mark.unit
class TestAPIClient:
    """Test APIClient class"""
    
    @pytest.fixture
    def mock_config(self):
        """Fixture for test configuration"""
        return PricingConfig(
            api_base_url="https://prices.azure.com/api/retail/prices",
            api_version="2023-01-01-preview",
            currencies=["USD"],
            batch_size=90,
            max_retries=3,
            request_timeout=120,
            sql_server_fqdn="test.server.net",
            sql_database_name="testdb"
        )
    
    @pytest.fixture
    def api_client(self, mock_config):
        """Fixture for APIClient instance"""
        return APIClient(mock_config)
    
    def test_initialization(self, mock_config):
        """Test API client initialization"""
        client = APIClient(mock_config)
        
        assert client.config == mock_config
        assert client.session is not None
    
    def test_build_api_url_initial(self, api_client):
        """Test building initial API URL"""
        url = api_client.build_api_url("USD")
        
        assert "https://prices.azure.com/api/retail/prices" in url
        assert "api-version=2023-01-01-preview" in url
        assert "currencyCode=USD" in url
    
    def test_build_api_url_with_next_page(self, api_client):
        """Test building API URL with next page link"""
        next_page = "https://prices.azure.com/api/retail/prices?$skip=100"
        url = api_client.build_api_url("USD", next_page)
        
        assert url == next_page
    
    def test_fetch_page_success(self, api_client):
        """Test successful page fetch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"Items": [], "NextPageLink": None}
        
        api_client.session.get = Mock(return_value=mock_response)
        
        data = api_client.fetch_page("https://test.com/api")
        
        assert data == {"Items": [], "NextPageLink": None}
        api_client.session.get.assert_called_once_with("https://test.com/api", timeout=120)
    
    def test_fetch_page_rate_limited_then_success(self, api_client):
        """Test handling of rate limiting (429) then success"""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"Items": []}
        
        api_client.session.get = Mock(side_effect=[mock_response_429, mock_response_200])
        
        with patch('time.sleep') as mock_sleep:
            data = api_client.fetch_page("https://test.com/api")
            
            assert data == {"Items": []}
            assert api_client.session.get.call_count == 2
            mock_sleep.assert_called_once()
    
    def test_fetch_page_all_retries_exhausted(self, api_client):
        """Test failure when all retries are exhausted"""
        import requests
        
        api_client.session.get = Mock(
            side_effect=requests.exceptions.RequestException("Network error")
        )
        
        with patch('time.sleep'):
            with pytest.raises(Exception, match="Failed to fetch"):
                api_client.fetch_page("https://test.com/api")


@pytest.mark.unit
class TestDatabaseService:
    """Test DatabaseService class"""
    
    @pytest.fixture
    def mock_conn(self):
        """Fixture for mock database connection"""
        return Mock()
    
    @pytest.fixture
    def db_service(self, mock_conn):
        """Fixture for DatabaseService instance"""
        return DatabaseService(mock_conn)
    
    def test_create_snapshot_run(self, db_service, mock_conn):
        """Test creating snapshot run"""
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        started = datetime.now(timezone.utc)
        db_service.create_snapshot_run("202312", "USD", started)
        
        mock_conn.cursor.assert_called_once()
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
    
    def test_update_snapshot_status(self, db_service, mock_conn):
        """Test updating snapshot status"""
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        db_service.update_snapshot_status("202312", "USD", RUN_STATUS_SUCCEEDED, 1000)
        
        mock_cursor.execute.assert_called_once()
        # Verify status and item count in call
        call_args = mock_cursor.execute.call_args[0]
        assert RUN_STATUS_SUCCEEDED in call_args
        assert 1000 in call_args
    
    def test_deduplicate_batch(self):
        """Test batch deduplication"""
        items = [
            {"meterId": "1", "effectiveStartDate": "2023-01-01"},
            {"meterId": "2", "effectiveStartDate": "2023-01-01"},
            {"meterId": "1", "effectiveStartDate": "2023-01-01"},  # Duplicate
        ]
        
        unique, dup_count = DatabaseService._deduplicate_batch(items, "USD")
        
        assert len(unique) == 2
        assert dup_count == 1
    
    def test_extract_item_params(self):
        """Test extracting item parameters"""
        item = {
            "meterId": "meter123",
            "effectiveStartDate": "2023-01-01",
            "retailPrice": 0.5,
            "unitPrice": 0.5,
            "unitOfMeasure": "1 Hour",
            "armRegionName": "eastus",
            "location": "US East",
            "productId": "prod123",
            "productName": "Virtual Machine",
            "skuId": "sku123",
            "skuName": "Standard_D2s_v3",
            "serviceId": "svc123",
            "serviceName": "Virtual Machines",
            "serviceFamily": "Compute",
            "meterName": "D2s v3",
            "armSkuName": "Standard_D2s_v3",
            "reservationTerm": None,
            "type": "Consumption",
            "isPrimaryMeterRegion": True,
            "tierMinimumUnits": 0,
            "availabilityId": None
        }
        
        params = DatabaseService._extract_item_params(item, "USD")
        
        assert len(params) == 22
        assert params[0] == "meter123"
        assert params[2] == "USD"
        assert params[19] == 1  # isPrimaryMeterRegion converted to 1
    
    def test_build_merge_statement(self):
        """Test building MERGE SQL statement"""
        sql = DatabaseService._build_merge_statement(2)
        
        assert "MERGE INTO dbo.AzureRetailPrices" in sql
        assert sql.count("(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)") == 2
        assert "WHEN MATCHED THEN" in sql
        assert "WHEN NOT MATCHED THEN" in sql
    
    def test_upsert_prices_batch_empty(self, db_service, mock_conn):
        """Test upserting empty batch"""
        result = db_service.upsert_prices_batch("202312", "USD", [], 90)
        
        assert result == 0
        mock_conn.cursor.assert_not_called()
    
    def test_upsert_prices_batch_success(self, db_service, mock_conn):
        """Test successful batch upsert"""
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        items = [
            {"meterId": "1", "effectiveStartDate": "2023-01-01", "retailPrice": 0.5}
        ]
        
        result = db_service.upsert_prices_batch("202312", "USD", items, 90)
        
        assert result == 1
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()


@pytest.mark.unit
class TestPricingService:
    """Test PricingService class"""
    
    @pytest.fixture
    def mock_config(self):
        """Fixture for test configuration"""
        return PricingConfig(
            api_base_url="https://prices.azure.com/api/retail/prices",
            api_version="2023-01-01-preview",
            currencies=["USD"],
            batch_size=90,
            max_retries=3,
            request_timeout=120,
            sql_server_fqdn="test.server.net",
            sql_database_name="testdb"
        )
    
    @pytest.fixture
    def mock_conn(self):
        """Fixture for mock database connection"""
        return Mock()
    
    @pytest.fixture
    def pricing_service(self, mock_config, mock_conn):
        """Fixture for PricingService instance"""
        return PricingService(mock_config, mock_conn)
    
    def test_initialization(self, mock_config, mock_conn):
        """Test pricing service initialization"""
        service = PricingService(mock_config, mock_conn)
        
        assert service.config == mock_config
        assert isinstance(service.api_client, APIClient)
        assert isinstance(service.db_service, DatabaseService)
    
    def test_process_currency_success(self, pricing_service):
        """Test successful currency processing"""
        # Mock API responses
        api_data_page1 = {
            "Items": [{"meterId": "1", "effectiveStartDate": "2023-01-01"}],
            "NextPageLink": "https://api.test.com/page2"
        }
        api_data_page2 = {
            "Items": [{"meterId": "2", "effectiveStartDate": "2023-01-01"}],
            "NextPageLink": None
        }
        
        pricing_service.api_client.fetch_page = Mock(side_effect=[api_data_page1, api_data_page2])
        pricing_service.api_client.build_api_url = Mock(return_value="https://api.test.com/page1")
        pricing_service.db_service.create_snapshot_run = Mock()
        pricing_service.db_service.upsert_prices_batch = Mock(side_effect=[1, 1])
        pricing_service.db_service.update_snapshot_status = Mock()
        
        total = pricing_service.process_currency("202312", "USD")
        
        assert total == 2
        assert pricing_service.api_client.fetch_page.call_count == 2
        assert pricing_service.db_service.upsert_prices_batch.call_count == 2
        pricing_service.db_service.update_snapshot_status.assert_called_once_with(
            "202312", "USD", RUN_STATUS_SUCCEEDED, 2
        )
    
    def test_process_currency_api_error(self, pricing_service):
        """Test handling API error during processing"""
        pricing_service.api_client.build_api_url = Mock(return_value="https://api.test.com")
        pricing_service.api_client.fetch_page = Mock(side_effect=Exception("API Error"))
        pricing_service.db_service.create_snapshot_run = Mock()
        
        with pytest.raises(Exception, match="API Error"):
            pricing_service.process_currency("202312", "USD")
