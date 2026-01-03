
import unittest
from unittest.mock import patch, MagicMock
import PriceSnapshot.__init__ as price_snapshot

class TestPricingConfig(unittest.TestCase):
    def test_validate_valid_config(self):
        config = price_snapshot.PricingConfig(
            api_base_url="https://test/",
            api_version="2023-01-01-preview",
            currencies=["USD"],
            batch_size=90,
            max_retries=3,
            request_timeout=10,
            sql_server_fqdn="test.database.windows.net",
            sql_database_name="testdb"
        )
        config.validate()  # Should not raise

    def test_validate_invalid_batch_size(self):
        config = price_snapshot.PricingConfig(
            api_base_url="https://test/",
            api_version="2023-01-01-preview",
            currencies=["USD"],
            batch_size=200,
            max_retries=3,
            request_timeout=10,
            sql_server_fqdn="test.database.windows.net",
            sql_database_name="testdb"
        )
        with self.assertRaises(ValueError):
            config.validate()

    def test_validate_empty_currencies(self):
        config = price_snapshot.PricingConfig(
            api_base_url="https://test/",
            api_version="2023-01-01-preview",
            currencies=[],
            batch_size=10,
            max_retries=3,
            request_timeout=10,
            sql_server_fqdn="test.database.windows.net",
            sql_database_name="testdb"
        )
        with self.assertRaises(ValueError):
            config.validate()

class TestAPIClient(unittest.TestCase):
    @patch('PriceSnapshot.__init__.requests.Session')
    def test_build_api_url_contains_currency_and_version(self, mock_session):
        config = MagicMock()
        config.api_base_url = "https://test/"
        config.api_version = "2023-01-01-preview"
        client = price_snapshot.APIClient(config)
        url = client.build_api_url("USD")
        self.assertIn("currencyCode=USD", url)
        self.assertIn("api-version=2023-01-01-preview", url)

if __name__ == "__main__":
    unittest.main()
