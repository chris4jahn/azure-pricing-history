"""
Azure Pricing History - PriceSnapshot Timer Function
Runs quarterly to fetch and persist Azure Retail Prices API data
"""
import os
import sys
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
import time

import azure.functions as func
import pyodbc
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Local import for Azure Functions
from .azure_sql_auth import AzureSqlAuthenticator, get_sql_connection

__all__ = ['AzureSqlAuthenticator', 'get_sql_connection']

# Constants
API_BASE_URL = "https://prices.azure.com/api/retail/prices"
DEFAULT_API_VERSION = "2023-01-01-preview"
DEFAULT_CURRENCIES = "USD,EUR"
DEFAULT_BATCH_SIZE = 90  # 90 items * 22 params = 1980 params (under 2100 SQL Server limit)
DEFAULT_MAX_RETRIES = 5
DEFAULT_REQUEST_TIMEOUT = 120
MAX_BACKOFF_SECONDS = 60
PARAMS_PER_ITEM = 22
RUN_STATUS_RUNNING = "RUNNING"
RUN_STATUS_SUCCEEDED = "SUCCEEDED"
RUN_STATUS_FAILED = "FAILED"
MAX_EXECUTION_TIME_HOURS = 2  # Maximum time before considering a run as hung


@dataclass(frozen=True)
class PricingConfig:
    """Configuration for Azure Pricing API integration"""
    api_base_url: str
    api_version: str
    currencies: List[str]
    batch_size: int
    max_retries: int
    request_timeout: int
    sql_server_fqdn: str
    sql_database_name: str
    
    @classmethod
    def from_environment(cls) -> 'PricingConfig':
        """Create configuration from environment variables"""
        currencies_str = os.environ.get("CURRENCIES", DEFAULT_CURRENCIES)
        currencies = [c.strip() for c in currencies_str.split(",")]
        
        return cls(
            api_base_url=API_BASE_URL,
            api_version=os.environ.get("API_VERSION", DEFAULT_API_VERSION),
            currencies=currencies,
            batch_size=int(os.environ.get("BATCH_SIZE", str(DEFAULT_BATCH_SIZE))),
            max_retries=int(os.environ.get("MAX_RETRIES", str(DEFAULT_MAX_RETRIES))),
            request_timeout=int(os.environ.get("REQUEST_TIMEOUT", str(DEFAULT_REQUEST_TIMEOUT))),
            sql_server_fqdn=os.environ["SQL_SERVER_FQDN"],
            sql_database_name=os.environ["SQL_DATABASE_NAME"]
        )
    
    def validate(self) -> None:
        """Validate configuration values"""
        if self.batch_size < 1 or self.batch_size > 95:
            raise ValueError(f"BATCH_SIZE must be between 1 and 95, got {self.batch_size}")
        
        max_params = self.batch_size * PARAMS_PER_ITEM
        if max_params >= 2100:
            raise ValueError(f"BATCH_SIZE {self.batch_size} would exceed SQL Server 2100 parameter limit")
        
        if not self.currencies:
            raise ValueError("At least one currency must be configured")


def main(myTimer: func.TimerRequest) -> None:
    """Timer trigger function to fetch and store Azure pricing data"""
    utc_timestamp = datetime.now(timezone.utc).isoformat()

    # Log function invocation immediately
    logging.info(f"=" * 80)
    logging.info(f"FUNCTION INVOKED AT {utc_timestamp}")
    logging.info(f"Timer parameter type: {type(myTimer)}")
    logging.info(f"=" * 80)

    # Diagnostics: try to write to diagnostics table
    try:
        config_diag = PricingConfig.from_environment()
        with get_sql_connection(config_diag.sql_server_fqdn, config_diag.sql_database_name) as conn_diag:
            cursor_diag = conn_diag.cursor()
            cursor_diag.execute(
                "INSERT INTO dbo.FunctionDiagnostics (functionName, message) VALUES (?, ?)",
                "PriceSnapshot", f"Function started at {utc_timestamp}"
            )
            conn_diag.commit()
            cursor_diag.close()
    except Exception as diag_exc:
        logging.error(f"Diagnostics DB write failed: {diag_exc}")

    # Handle both timer and manual triggers
    if myTimer and hasattr(myTimer, 'past_due') and myTimer.past_due:
        logging.warning(f"Timer is past due! Current time: {utc_timestamp}")

    trigger_type = "manual" if not myTimer or not hasattr(myTimer, 'past_due') else "timer"
    logging.info(f"PriceSnapshot {trigger_type} trigger started at {utc_timestamp}")

    config = None
    snapshot_id = None
    
    try:
        # Load and validate configuration
        config = PricingConfig.from_environment()
        config.validate()
        
        # Generate snapshot ID (YYYYMM format)
        snapshot_id = datetime.now(timezone.utc).strftime("%Y%m")
        
        # Clean up any stuck snapshots from previous runs
        with get_sql_connection(config.sql_server_fqdn, config.sql_database_name) as conn:
            cleanup_hung_snapshots(conn)
        
        logging.info("=" * 50)
        logging.info(f"STARTING PRICE SNAPSHOT: {snapshot_id}")
        logging.info(f"Configuration: {len(config.currencies)} currencies, batch size {config.batch_size}")
        logging.info("=" * 50)
        
        # Process all currencies
        results = process_all_currencies(config, snapshot_id)
        
        # Log completion summary
        completion_msg = f"PriceSnapshot completed at {datetime.now(timezone.utc).isoformat()}"
        logging.info("=" * 50)
        logging.info(completion_msg)
        logging.info("Results: " + ", ".join(results))
        logging.info("=" * 50)
        
    except Exception as e:
        error_msg = f"PriceSnapshot failed: {str(e)}"
        logging.error(error_msg, exc_info=True)
        
        # Mark snapshot as failed if we have enough context
        if config and snapshot_id:
            try:
                with get_sql_connection(config.sql_server_fqdn, config.sql_database_name) as conn:
                    db_service = DatabaseService(conn)
                    # Update all running snapshots for this ID to FAILED
                    db_service.mark_snapshot_failed(snapshot_id)
            except Exception as cleanup_error:
                logging.error(f"Failed to mark snapshot as failed: {cleanup_error}")
        
        raise


def cleanup_hung_snapshots(conn: pyodbc.Connection) -> None:
    """
    Clean up snapshots that have been running for too long
    
    Args:
        conn: Database connection
    """
    try:
        cursor = conn.cursor()
        
        # Update snapshots running for more than MAX_EXECUTION_TIME_HOURS hours
        cursor.execute(f"""
            UPDATE dbo.PriceSnapshotRuns
            SET status = ?,
                finishedUtc = GETUTCDATE()
            WHERE status = ?
                AND DATEDIFF(HOUR, startedUtc, GETUTCDATE()) > ?
        """, RUN_STATUS_FAILED, RUN_STATUS_RUNNING, MAX_EXECUTION_TIME_HOURS)
        
        rows_updated = cursor.rowcount
        if rows_updated > 0:
            logging.warning(f"Cleaned up {rows_updated} hung snapshot(s) - marked as FAILED (timeout)")
        
        conn.commit()
        
    except Exception as e:
        logging.error(f"Failed to cleanup hung snapshots: {e}")
        # Don't raise - this is cleanup, main execution should continue


def process_all_currencies(config: PricingConfig, snapshot_id: str) -> List[str]:
    """
    Process pricing data for all configured currencies
    
    Args:
        config: Pricing configuration
        snapshot_id: Snapshot identifier (YYYYMM format)
    
    Returns:
        List of result summaries for each currency
        
    Raises:
        Exception: If any currency processing fails
    """
    results = []
    
    with get_sql_connection(config.sql_server_fqdn, config.sql_database_name) as conn:
        for currency in config.currencies:
            currency = currency.strip()
            logging.info(f"Starting ingestion for currency: {currency}")
            
            try:
                service = PricingService(config, conn)
                item_count = service.process_currency(snapshot_id, currency)
                
                results.append(f"{currency}: {item_count} items")
                logging.info(f"Successfully completed ingestion for {currency}: {item_count} items")
                
            except Exception as e:
                error_msg = f"Failed to process currency {currency}: {str(e)}"
                logging.error(error_msg, exc_info=True)
                
                db_service = DatabaseService(conn)
                db_service.update_snapshot_status(snapshot_id, currency, RUN_STATUS_FAILED, 0)
                
                results.append(f"{currency}: FAILED - {str(e)}")
                raise
    
    return results


class APIClient:
    """
    Handles HTTP requests to Azure Pricing API with retry logic
    """
    
    def __init__(self, config: PricingConfig):
        self.config = config
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry logic for 429 and transient errors"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=2,  # Exponential backoff: 2, 4, 8, 16, 32 seconds
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session
    
    def fetch_page(self, url: str) -> Dict[str, Any]:
        """
        Fetch pricing data page with exponential backoff on rate limiting
        
        Args:
            url: API endpoint URL
            
        Returns:
            Parsed JSON response
            
        Raises:
            requests.exceptions.RequestException: If request fails after all retries
        """
        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.config.request_timeout)
                
                if response.status_code == 429:
                    # Rate limited - exponential backoff
                    wait_time = min(2 ** attempt, MAX_BACKOFF_SECONDS)
                    logging.warning(
                        f"Rate limited (429). Waiting {wait_time}s before retry {attempt}/{self.config.max_retries}"
                    )
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt == self.config.max_retries:
                    logging.error(f"Failed after {self.config.max_retries} attempts: {str(e)}")
                    raise
                
                wait_time = min(2 ** attempt, MAX_BACKOFF_SECONDS)
                logging.warning(
                    f"Request failed (attempt {attempt}/{self.config.max_retries}): {str(e)}. "
                    f"Retrying in {wait_time}s"
                )
                time.sleep(wait_time)
        
        raise Exception(f"Failed to fetch {url} after {self.config.max_retries} attempts")
    
    def build_api_url(self, currency: str, next_page_link: Optional[str] = None) -> str:
        """
        Build API URL for currency pricing data
        
        Args:
            currency: Currency code (e.g., 'USD', 'EUR')
            next_page_link: Next page URL from previous response (if any)
            
        Returns:
            API endpoint URL
        """
        if next_page_link:
            return next_page_link
        
        return f"{self.config.api_base_url}?api-version={self.config.api_version}&currencyCode={currency}"


class DatabaseService:
    """
    Handles database operations for pricing snapshots
    """
    
    def __init__(self, conn: pyodbc.Connection):
        self.conn = conn
    
    def create_snapshot_run(self, snapshot_id: str, currency: str, started_utc: datetime) -> None:
        """
        Create or update a snapshot run record
        
        Args:
            snapshot_id: Snapshot identifier (YYYYMM format)
            currency: Currency code
            started_utc: Start timestamp
        """
        cursor = self.conn.cursor()
        
        sql = """
        IF NOT EXISTS (SELECT 1 FROM dbo.PriceSnapshotRuns WHERE snapshotId = ? AND currencyCode = ?)
        BEGIN
            INSERT INTO dbo.PriceSnapshotRuns (snapshotId, currencyCode, startedUtc, status)
            VALUES (?, ?, ?, ?)
        END
        ELSE
        BEGIN
            UPDATE dbo.PriceSnapshotRuns
            SET startedUtc = ?, status = ?, finishedUtc = NULL, itemCount = NULL
            WHERE snapshotId = ? AND currencyCode = ?
        END
        """
        
        cursor.execute(
            sql,
            snapshot_id, currency,
            snapshot_id, currency, started_utc, RUN_STATUS_RUNNING,
            started_utc, RUN_STATUS_RUNNING, snapshot_id, currency
        )
        self.conn.commit()
        cursor.close()
        
        logging.info(f"Created/updated snapshot run: {snapshot_id}_{currency}")
    
    def update_snapshot_status(
        self,
        snapshot_id: str,
        currency: str,
        status: str,
        item_count: int
    ) -> None:
        """
        Update snapshot run status
        
        Args:
            snapshot_id: Snapshot identifier
            currency: Currency code
            status: Run status (SUCCEEDED, FAILED)
            item_count: Number of items processed
        """
        cursor = self.conn.cursor()
        
        sql = """
        UPDATE dbo.PriceSnapshotRuns
        SET finishedUtc = SYSUTCDATETIME(), status = ?, itemCount = ?
        WHERE snapshotId = ? AND currencyCode = ?
        """
        
        cursor.execute(sql, status, item_count, snapshot_id, currency)
        self.conn.commit()
        cursor.close()
        
        logging.info(f"Updated snapshot {snapshot_id}_{currency} to {status} with {item_count} items")
    
    def mark_snapshot_failed(self, snapshot_id: str, currency: str = None) -> None:
        """
        Mark snapshot as failed (for all currencies or specific currency)
        
        Args:
            snapshot_id: Snapshot identifier
            currency: Optional currency code (if None, marks all currencies for snapshot)
        """
        cursor = self.conn.cursor()
        
        if currency:
            sql = """
            UPDATE dbo.PriceSnapshotRuns
            SET finishedUtc = SYSUTCDATETIME(), status = ?
            WHERE snapshotId = ? AND currencyCode = ? AND status = ?
            """
            cursor.execute(sql, RUN_STATUS_FAILED, snapshot_id, currency, RUN_STATUS_RUNNING)
        else:
            sql = """
            UPDATE dbo.PriceSnapshotRuns
            SET finishedUtc = SYSUTCDATETIME(), status = ?
            WHERE snapshotId = ? AND status = ?
            """
            cursor.execute(sql, RUN_STATUS_FAILED, snapshot_id, RUN_STATUS_RUNNING)
        
        self.conn.commit()
        cursor.close()
        
        logging.warning(f"Marked snapshot {snapshot_id} as FAILED")
    
    def upsert_prices_batch(self, snapshot_id: str, currency: str, items: List[Dict[str, Any]], batch_size: int) -> int:
        """
        Upsert pricing items in batches using MERGE statement
        
        Args:
            snapshot_id: Snapshot identifier
            currency: Currency code
            items: List of pricing items from API
            batch_size: Number of items per batch
            
        Returns:
            Number of items processed
        """
        if not items:
            return 0
        
        cursor = self.conn.cursor()
        processed_count = 0
        
        logging.info(f"Upsert batch: Processing {len(items)} items with batch_size={batch_size}")
        
        # Process items in batches
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            # Deduplicate batch by primary key
            unique_batch, duplicates = self._deduplicate_batch(batch, currency)
            
            if duplicates > 0:
                logging.warning(
                    f"Removed {duplicates} duplicate items from batch "
                    f"(original: {len(batch)}, unique: {len(unique_batch)})"
                )
            
            if not unique_batch:
                logging.info("Batch is empty after deduplication, skipping")
                continue
            
            logging.info(f"Processing sub-batch: {len(unique_batch)} items (items {i} to {i+len(unique_batch)-1})")
            
            # Build MERGE statement and prepare parameters
            merge_sql = self._build_merge_statement(len(unique_batch))
            params = []
            for item in unique_batch:
                params.extend(self._extract_item_params(item, currency))
            
            logging.info(f"Built MERGE statement for {len(unique_batch)} items with {len(params)} parameters")
            
            try:
                cursor.execute(merge_sql, *params)
                self.conn.commit()
                processed_count += len(unique_batch)
                
            except Exception as e:
                logging.error(f"Failed to upsert batch: {str(e)}", exc_info=True)
                self.conn.rollback()
                raise
        
        cursor.close()
        return processed_count
    
    @staticmethod
    def _deduplicate_batch(batch: List[Dict[str, Any]], currency: str) -> Tuple[List[Dict[str, Any]], int]:
        """
        Remove duplicate items from batch based on primary key
        
        Args:
            batch: List of pricing items
            currency: Currency code
            
        Returns:
            Tuple of (unique items list, duplicate count)
        """
        seen_keys = set()
        unique_batch = []
        duplicates = 0
        
        for item in batch:
            key = (item.get('meterId'), item.get('effectiveStartDate'), currency)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_batch.append(item)
            else:
                duplicates += 1
        
        return unique_batch, duplicates
    
    @staticmethod
    def _build_merge_statement(batch_size: int) -> str:
        """
        Build parameterized MERGE statement for batch upsert
        
        Args:
            batch_size: Number of items in batch
            
        Returns:
            SQL MERGE statement
        """
        # Build VALUES clause with placeholders
        value_rows = ["(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)" for _ in range(batch_size)]
        values_clause = ",\n".join(value_rows)
        
        return f"""
        MERGE INTO dbo.AzureRetailPrices AS target
        USING (
            VALUES
            {values_clause}
        ) AS source (
            meterId, effectiveStartDate, currencyCode, retailPrice, unitPrice, unitOfMeasure,
            armRegionName, location, productId, productName, skuId, skuName,
            serviceId, serviceName, serviceFamily, meterName, armSkuName,
            reservationTerm, type, isPrimaryMeterRegion, tierMinimumUnits, availabilityId
        )
        ON target.meterId = source.meterId
           AND target.effectiveStartDate = source.effectiveStartDate
           AND target.currencyCode = source.currencyCode
        WHEN MATCHED THEN
            UPDATE SET
                retailPrice = source.retailPrice,
                unitPrice = source.unitPrice,
                unitOfMeasure = source.unitOfMeasure,
                armRegionName = source.armRegionName,
                location = source.location,
                productId = source.productId,
                productName = source.productName,
                skuId = source.skuId,
                skuName = source.skuName,
                serviceId = source.serviceId,
                serviceName = source.serviceName,
                serviceFamily = source.serviceFamily,
                meterName = source.meterName,
                armSkuName = source.armSkuName,
                reservationTerm = source.reservationTerm,
                type = source.type,
                isPrimaryMeterRegion = source.isPrimaryMeterRegion,
                tierMinimumUnits = source.tierMinimumUnits,
                availabilityId = source.availabilityId,
                lastSeenUtc = SYSUTCDATETIME()
        WHEN NOT MATCHED THEN
            INSERT (
                meterId, effectiveStartDate, currencyCode, retailPrice, unitPrice, unitOfMeasure,
                armRegionName, location, productId, productName, skuId, skuName,
                serviceId, serviceName, serviceFamily, meterName, armSkuName,
                reservationTerm, type, isPrimaryMeterRegion, tierMinimumUnits, availabilityId,
                lastSeenUtc
            )
            VALUES (
                source.meterId, source.effectiveStartDate, source.currencyCode,
                source.retailPrice, source.unitPrice, source.unitOfMeasure,
                source.armRegionName, source.location, source.productId, source.productName,
                source.skuId, source.skuName, source.serviceId, source.serviceName,
                source.serviceFamily, source.meterName, source.armSkuName,
                source.reservationTerm, source.type, source.isPrimaryMeterRegion,
                source.tierMinimumUnits, source.availabilityId, SYSUTCDATETIME()
            );
        """
    
    @staticmethod
    def _extract_item_params(item: Dict[str, Any], currency: str) -> List[Any]:
        """
        Extract parameters from API item for SQL statement
        
        Args:
            item: Pricing item from API
            currency: Currency code
            
        Returns:
            List of parameter values
        """
        return [
            item.get("meterId"),
            item.get("effectiveStartDate"),
            currency,
            item.get("retailPrice"),
            item.get("unitPrice"),
            item.get("unitOfMeasure"),
            item.get("armRegionName"),
            item.get("location"),
            item.get("productId"),
            item.get("productName"),
            item.get("skuId"),
            item.get("skuName"),
            item.get("serviceId"),
            item.get("serviceName"),
            item.get("serviceFamily"),
            item.get("meterName"),
            item.get("armSkuName"),
            item.get("reservationTerm"),
            item.get("type"),
            1 if item.get("isPrimaryMeterRegion") else 0,
            item.get("tierMinimumUnits"),
            item.get("availabilityId")
        ]


class PricingService:
    """
    Orchestrates pricing data ingestion for a currency
    """
    
    def __init__(self, config: PricingConfig, conn: pyodbc.Connection):
        self.config = config
        self.api_client = APIClient(config)
        self.db_service = DatabaseService(conn)
    
    def process_currency(self, snapshot_id: str, currency: str) -> int:
        """
        Process pricing data for a specific currency
        
        Args:
            snapshot_id: Snapshot identifier (YYYYMM format)
            currency: Currency code (e.g., 'USD', 'EUR')
            
        Returns:
            Total number of items processed
        """
        started_utc = datetime.now(timezone.utc)
        
        # Create snapshot run record
        self.db_service.create_snapshot_run(snapshot_id, currency, started_utc)
        
        # Fetch and process all pages
        total_items = 0
        page_index = 0
        next_page_link = self.api_client.build_api_url(currency)
        
        while next_page_link:
            page_index += 1
            logging.info(f"Fetching page {page_index} for {currency}")
            
            try:
                # Fetch page with retry logic
                data = self.api_client.fetch_page(next_page_link)
                
                items = data.get("Items", [])
                logging.info(f"Page {page_index}: Retrieved {len(items)} items")
                
                # Process items in batches
                if items:
                    items_processed = self.db_service.upsert_prices_batch(
                        snapshot_id, currency, items, self.config.batch_size
                    )
                    total_items += items_processed
                    logging.info(f"Processed {items_processed} items. Total: {total_items}")
                
                # Get next page link
                next_page_link = data.get("NextPageLink")
                
            except Exception as e:
                logging.error(f"Error processing page {page_index}: {str(e)}", exc_info=True)
                raise
        
        # Update snapshot run as succeeded
        finished_utc = datetime.now(timezone.utc)
        self.db_service.update_snapshot_status(snapshot_id, currency, RUN_STATUS_SUCCEEDED, total_items)
        
        duration_seconds = (finished_utc - started_utc).total_seconds()
        logging.info(f"Completed {currency}: {total_items} items in {duration_seconds:.2f} seconds")
        
        return total_items
