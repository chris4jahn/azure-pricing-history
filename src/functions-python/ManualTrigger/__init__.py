"""
HTTP-triggered wrapper to manually execute PriceSnapshot function
"""
import azure.functions as func
import logging
import sys
import os
from datetime import datetime, timezone
import importlib.util

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger to manually run price snapshot collection
    
    Returns:
        HTTP response with execution status
    """
    logging.info("ManualTrigger HTTP function invoked")
    
    try:
        # Get the base directory (where all functions are)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        functions_base = os.path.dirname(current_dir)
        
        # Add shared directory to Python path - it's at the same level as function dirs
        shared_dir = os.path.join(functions_base, 'shared')
        if os.path.exists(shared_dir) and shared_dir not in sys.path:
            sys.path.insert(0, shared_dir)
            logging.info(f"Added shared directory to path: {shared_dir}")
        
        # Import PriceSnapshot main function
        snapshot_path = os.path.join(functions_base, 'PriceSnapshot', '__init__.py')
        logging.info(f"Loading PriceSnapshot from: {snapshot_path}")
        
        spec = importlib.util.spec_from_file_location("PriceSnapshot", snapshot_path)
        pricesnapshot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pricesnapshot)
        
        # Create a mock timer request object for manual trigger
        class MockTimer:
            past_due = False
        
        logging.info("Executing PriceSnapshot.main()...")
        
        # Execute the main function
        pricesnapshot.main(MockTimer())
        
        return func.HttpResponse(
            f"Success! PriceSnapshot executed at {datetime.now(timezone.utc).isoformat()}",
            status_code=200
        )
        
    except Exception as e:
        error_msg = f"PriceSnapshot failed: {str(e)}"
        logging.error(error_msg, exc_info=True)
        
        return func.HttpResponse(
            f"Error: {error_msg}",
            status_code=500
        )
