"""
HTTP-triggered wrapper to manually execute PriceSnapshot function
"""
import azure.functions as func
import logging
import sys
import os

# Add parent directory to path to import PriceSnapshot
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PriceSnapshot import (
    PricingConfig,
    process_all_currencies,
    cleanup_hung_snapshots,
    sql_connection,
    DatabaseService
)
from datetime import datetime, timezone


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger to manually run price snapshot collection
    
    Returns:
        HTTP response with execution status
    """
    logging.info("ManualTrigger HTTP function invoked")
    
    config = None
    snapshot_id = None
    
    try:
        # Load and validate configuration
        config = PricingConfig.from_environment()
        config.validate()
        
        # Generate snapshot ID (YYYYMM format)
        snapshot_id = datetime.now(timezone.utc).strftime("%Y%m")
        
        # Clean up any stuck snapshots from previous runs
        with sql_connection(config.sql_server_fqdn, config.sql_database_name) as conn:
            cleanup_hung_snapshots(conn)
        
        logging.info("=" * 50)
        logging.info(f"STARTING PRICE SNAPSHOT (MANUAL): {snapshot_id}")
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
        
        return func.HttpResponse(
            f"Success! {completion_msg}\nResults:\n" + "\n".join(results),
            status_code=200
        )
        
    except Exception as e:
        error_msg = f"PriceSnapshot failed: {str(e)}"
        logging.error(error_msg, exc_info=True)
        
        # Mark snapshot as failed if we have enough context
        if config and snapshot_id:
            try:
                with sql_connection(config.sql_server_fqdn, config.sql_database_name) as conn:
                    db_service = DatabaseService(conn)
                    db_service.mark_snapshot_failed(snapshot_id)
            except Exception as cleanup_error:
                logging.error(f"Failed to mark snapshot as failed: {cleanup_error}")
        
        return func.HttpResponse(
            f"Error: {error_msg}",
            status_code=500
        )
