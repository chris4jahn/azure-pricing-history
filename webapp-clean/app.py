"""
Azure Pricing History - Web Visualization App
Flask application to visualize pricing data from Azure SQL Database
"""

import os
import sys
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from flask import Flask, render_template, jsonify, request
import pyodbc

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))
from azure_sql_auth import AzureSqlAuthenticator, SqlDatabaseConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


# Constants
DEFAULT_LIMIT_SERVICES = 15
DEFAULT_LIMIT_SEARCH = 50
DEFAULT_LIMIT_SNAPSHOTS = 20
DEFAULT_CURRENCY = "USD"


@dataclass(frozen=True)
class WebAppConfig:
    """Configuration for web application"""
    sql_config: SqlDatabaseConfig
    default_currency: str = DEFAULT_CURRENCY
    
    @classmethod
    def from_environment(cls) -> 'WebAppConfig':
        """Create configuration from environment variables"""
        return cls(
            sql_config=SqlDatabaseConfig.from_environment(),
            default_currency=os.environ.get('DEFAULT_CURRENCY', DEFAULT_CURRENCY)
        )


# Initialize configuration and authenticator
config = WebAppConfig.from_environment()
authenticator = AzureSqlAuthenticator(config.sql_config)

class DatabaseQueryService:
    """Service for executing database queries"""
    
    def __init__(self, conn: pyodbc.Connection):
        self.conn = conn
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get overall summary statistics"""
        cursor = self.conn.cursor()
        
        # Get overall statistics
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT meterId) as totalMeters,
                COUNT(DISTINCT serviceName) as totalServices,
                COUNT(DISTINCT armRegionName) as totalRegions,
                COUNT(DISTINCT currencyCode) as totalCurrencies,
                MAX(lastSeenUtc) as lastUpdate
            FROM dbo.AzureRetailPrices
        """)
        
        row = cursor.fetchone()
        summary = {
            'totalMeters': row.totalMeters,
            'totalServices': row.totalServices,
            'totalRegions': row.totalRegions,
            'totalCurrencies': row.totalCurrencies,
            'lastUpdate': row.lastUpdate.isoformat() if row.lastUpdate else None
        }
        
        # Get snapshot statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as totalSnapshots,
                SUM(CASE WHEN status = 'SUCCEEDED' THEN 1 ELSE 0 END) as successfulSnapshots,
                MAX(startedUtc) as lastSnapshotDate
            FROM dbo.PriceSnapshotRuns
        """)
        
        row = cursor.fetchone()
        summary['totalSnapshots'] = row.totalSnapshots
        summary['successfulSnapshots'] = row.successfulSnapshots
        summary['lastSnapshotDate'] = row.lastSnapshotDate.isoformat() if row.lastSnapshotDate else None
        
        cursor.close()
        return summary
    
    def get_top_services(self, limit: int, currency: str) -> List[Dict[str, Any]]:
        """Get top services by meter count"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT TOP (?) 
                serviceName,
                COUNT(DISTINCT meterId) as meterCount,
                AVG(retailPrice) as avgPrice,
                MIN(retailPrice) as minPrice,
                MAX(retailPrice) as maxPrice
            FROM dbo.v_CurrentRetailPrices
            WHERE currencyCode = ?
                AND retailPrice > 0
                AND serviceName IS NOT NULL
            GROUP BY serviceName
            ORDER BY meterCount DESC
        """, limit, currency)
        
        services = []
        for row in cursor.fetchall():
            services.append({
                'name': row.serviceName,
                'meterCount': row.meterCount,
                'avgPrice': float(row.avgPrice) if row.avgPrice else 0,
                'minPrice': float(row.minPrice) if row.minPrice else 0,
                'maxPrice': float(row.maxPrice) if row.maxPrice else 0
            })
        
        cursor.close()
        return services
    
    def get_region_pricing(self, currency: str, service: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pricing data by region"""
        cursor = self.conn.cursor()
        
        query = """
            SELECT 
                armRegionName,
                COUNT(DISTINCT meterId) as meterCount,
                AVG(retailPrice) as avgPrice
            FROM dbo.v_CurrentRetailPrices
            WHERE currencyCode = ?
                AND retailPrice > 0
                AND armRegionName IS NOT NULL
        """
        params = [currency]
        
        if service:
            query += " AND serviceName = ?"
            params.append(service)
        
        query += """
            GROUP BY armRegionName
            ORDER BY meterCount DESC
        """
        
        cursor.execute(query, *params)
        
        regions = []
        for row in cursor.fetchall():
            regions.append({
                'region': row.armRegionName,
                'meterCount': row.meterCount,
                'avgPrice': float(row.avgPrice) if row.avgPrice else 0
            })
        
        cursor.close()
        return regions
    
    def get_price_trends(
        self,
        currency: str,
        meter_id: Optional[str] = None,
        service: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get price trends over time"""
        cursor = self.conn.cursor()
        
        if meter_id:
            # Specific meter trend
            cursor.execute("""
                SELECT 
                    effectiveStartDate,
                    retailPrice,
                    productName,
                    skuName,
                    meterName
                FROM dbo.v_PriceHistory
                WHERE meterId = ?
                    AND currencyCode = ?
                ORDER BY effectiveStartDate DESC
            """, meter_id, currency)
            
            trends = []
            for row in cursor.fetchall():
                trends.append({
                    'date': row.effectiveStartDate.isoformat(),
                    'price': float(row.retailPrice) if row.retailPrice else 0,
                    'productName': row.productName
                })
        else:
            # Average service trend
            service_name = service or 'Virtual Machines'
            cursor.execute("""
                SELECT 
                    effectiveStartDate,
                    AVG(retailPrice) as retailPrice,
                    serviceName as productName,
                    COUNT(DISTINCT meterId) as meterCount
                FROM dbo.AzureRetailPrices
                WHERE serviceName = ?
                    AND currencyCode = ?
                    AND retailPrice > 0
                GROUP BY effectiveStartDate, serviceName
                ORDER BY effectiveStartDate DESC
            """, service_name, currency)
            
            trends = []
            for row in cursor.fetchall():
                trends.append({
                    'date': row.effectiveStartDate.isoformat(),
                    'price': float(row.retailPrice) if row.retailPrice else 0,
                    'productName': row.productName
                })
        
        cursor.close()
        return trends
    
    def get_snapshot_history(self, limit: int) -> List[Dict[str, Any]]:
        """Get snapshot run history"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT TOP (?)
                snapshotId,
                currencyCode,
                startedUtc,
                finishedUtc,
                status,
                itemCount,
                durationSeconds,
                itemsPerSecond
            FROM dbo.v_SnapshotRunSummary
            ORDER BY startedUtc DESC
        """, limit)
        
        snapshots = []
        for row in cursor.fetchall():
            snapshots.append({
                'snapshotId': row.snapshotId,
                'currency': row.currencyCode,
                'startedUtc': row.startedUtc.isoformat(),
                'finishedUtc': row.finishedUtc.isoformat() if row.finishedUtc else None,
                'status': row.status,
                'itemCount': row.itemCount,
                'durationSeconds': row.durationSeconds,
                'itemsPerSecond': float(row.itemsPerSecond) if row.itemsPerSecond else 0
            })
        
        cursor.close()
        return snapshots
    
    def search_prices(self, query: str, currency: str, limit: int) -> List[Dict[str, Any]]:
        """Search pricing data"""
        cursor = self.conn.cursor()
        
        search_term = f'%{query}%'
        cursor.execute("""
            SELECT TOP (?)
                meterId,
                productName,
                skuName,
                serviceName,
                meterName,
                armRegionName,
                retailPrice,
                unitOfMeasure,
                effectiveStartDate
            FROM dbo.v_CurrentRetailPrices
            WHERE currencyCode = ?
                AND (
                    productName LIKE ? 
                    OR skuName LIKE ?
                    OR serviceName LIKE ?
                    OR meterName LIKE ?
                )
            ORDER BY retailPrice DESC
        """, limit, currency, search_term, search_term, search_term, search_term)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'meterId': row.meterId,
                'productName': row.productName,
                'skuName': row.skuName,
                'serviceName': row.serviceName,
                'meterName': row.meterName,
                'region': row.armRegionName,
                'price': float(row.retailPrice) if row.retailPrice else 0,
                'unit': row.unitOfMeasure,
                'effectiveDate': row.effectiveStartDate.isoformat()
            })
        
        cursor.close()
        return results
    
    def get_hierarchical_pricing(self, currency: str) -> List[Dict[str, Any]]:
        """Get pricing data organized by service family (category) and SKU"""
        cursor = self.conn.cursor()
        
        # Get categories with SKU families
        cursor.execute("""
            SELECT 
                COALESCE(serviceFamily, 'Other') as category,
                COALESCE(skuName, 'Unknown') as skuFamily,
                COUNT(DISTINCT meterId) as meterCount,
                AVG(retailPrice) as avgPrice,
                MIN(retailPrice) as minPrice,
                MAX(retailPrice) as maxPrice
            FROM dbo.v_CurrentRetailPrices
            WHERE currencyCode = ?
                AND retailPrice > 0
            GROUP BY serviceFamily, skuName
            ORDER BY category, skuFamily
        """, currency)
        
        # Organize into hierarchical structure
        categories = {}
        for row in cursor.fetchall():
            category = row.category
            if category not in categories:
                categories[category] = {
                    'name': category,
                    'skuFamilies': [],
                    'totalMeters': 0,
                    'avgPrice': 0
                }
            
            categories[category]['skuFamilies'].append({
                'name': row.skuFamily,
                'meterCount': row.meterCount,
                'avgPrice': float(row.avgPrice) if row.avgPrice else 0,
                'minPrice': float(row.minPrice) if row.minPrice else 0,
                'maxPrice': float(row.maxPrice) if row.maxPrice else 0
            })
            categories[category]['totalMeters'] += row.meterCount
        
        # Calculate average prices for categories
        for category in categories.values():
            if category['skuFamilies']:
                category['avgPrice'] = sum(s['avgPrice'] for s in category['skuFamilies']) / len(category['skuFamilies'])
        
        cursor.close()
        return list(categories.values())
    
    def get_sku_meters(self, currency: str, sku_family: str) -> List[Dict[str, Any]]:
        """Get all meters for a specific SKU family"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                meterId,
                meterName,
                productName,
                serviceName,
                armRegionName,
                retailPrice,
                unitOfMeasure
            FROM dbo.v_CurrentRetailPrices
            WHERE currencyCode = ?
                AND skuName = ?
                AND retailPrice > 0
            ORDER BY retailPrice DESC
        """, currency, sku_family)
        
        meters = []
        for row in cursor.fetchall():
            meters.append({
                'meterId': row.meterId,
                'meterName': row.meterName,
                'productName': row.productName,
                'serviceName': row.serviceName,
                'region': row.armRegionName,
                'price': float(row.retailPrice) if row.retailPrice else 0,
                'unit': row.unitOfMeasure
            })
        
        cursor.close()
        return meters
    
    def get_meter_price_history(self, meter_id: str, currency: str) -> List[Dict[str, Any]]:
        """Get price history for a specific meter across quarters"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                effectiveStartDate,
                retailPrice,
                armRegionName,
                unitOfMeasure
            FROM dbo.AzureRetailPrices
            WHERE meterId = ?
                AND currencyCode = ?
                AND retailPrice > 0
            ORDER BY effectiveStartDate ASC
        """, meter_id, currency)
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'date': row.effectiveStartDate.isoformat(),
                'price': float(row.retailPrice) if row.retailPrice else 0,
                'region': row.armRegionName,
                'unit': row.unitOfMeasure
            })
        
        cursor.close()
        return history
    
    def get_cheapest_region_for_sku(self, sku_family: str, currency: str) -> Dict[str, Any]:
        """Find the region with the cheapest average price for a SKU family"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT TOP 1
                armRegionName,
                AVG(retailPrice) as avgPrice,
                COUNT(DISTINCT meterId) as meterCount
            FROM dbo.v_CurrentRetailPrices
            WHERE currencyCode = ?
                AND skuName = ?
                AND retailPrice > 0
                AND armRegionName IS NOT NULL
            GROUP BY armRegionName
            ORDER BY avgPrice ASC
        """, currency, sku_family)
        
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return {
                'region': row.armRegionName,
                'avgPrice': float(row.avgPrice),
                'meterCount': row.meterCount
            }
        return {}


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


@app.route('/api/summary')
def get_summary():
    """Get summary statistics"""
    try:
        with authenticator.connection() as conn:
            service = DatabaseQueryService(conn)
            summary = service.get_summary_stats()
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Error getting summary: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/services')
def get_services():
    """Get top services by meter count"""
    try:
        limit = request.args.get('limit', DEFAULT_LIMIT_SERVICES, type=int)
        currency = request.args.get('currency', config.default_currency)
        
        with authenticator.connection() as conn:
            service = DatabaseQueryService(conn)
            services = service.get_top_services(limit, currency)
        return jsonify(services)
    except Exception as e:
        logger.error(f"Error getting services: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/regions')
def get_regions():
    """Get pricing by region"""
    try:
        currency = request.args.get('currency', config.default_currency)
        service = request.args.get('service', None)
        
        with authenticator.connection() as conn:
            query_service = DatabaseQueryService(conn)
            regions = query_service.get_region_pricing(currency, service)
        return jsonify(regions)
    except Exception as e:
        logger.error(f"Error getting regions: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/price-trends')
def get_price_trends():
    """Get price trends over time for a specific meter or service"""
    try:
        meter_id = request.args.get('meterId', None)
        service = request.args.get('service', 'Virtual Machines')
        currency = request.args.get('currency', config.default_currency)
        
        with authenticator.connection() as conn:
            query_service = DatabaseQueryService(conn)
            trends = query_service.get_price_trends(currency, meter_id, service)
        return jsonify(trends)
    except Exception as e:
        logger.error(f"Error getting price trends: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/snapshots')
def get_snapshots():
    """Get snapshot run history"""
    try:
        with authenticator.connection() as conn:
            service = DatabaseQueryService(conn)
            snapshots = service.get_snapshot_history(DEFAULT_LIMIT_SNAPSHOTS)
        return jsonify(snapshots)
    except Exception as e:
        logger.error(f"Error getting snapshots: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/search')
def search_prices():
    """Search pricing data"""
    try:
        query = request.args.get('q', '')
        currency = request.args.get('currency', config.default_currency)
        limit = request.args.get('limit', DEFAULT_LIMIT_SEARCH, type=int)
        
        if not query:
            return jsonify([])
        
        with authenticator.connection() as conn:
            service = DatabaseQueryService(conn)
            results = service.search_prices(query, currency, limit)
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error searching prices: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/hierarchical')
def get_hierarchical():
    """Get hierarchical pricing data organized by category and SKU family"""
    try:
        currency = request.args.get('currency', config.default_currency)
        
        with authenticator.connection() as conn:
            service = DatabaseQueryService(conn)
            data = service.get_hierarchical_pricing(currency)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting hierarchical data: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/sku-meters/<sku_family>')
def get_sku_meters_route(sku_family):
    """Get all meters for a specific SKU family"""
    try:
        currency = request.args.get('currency', config.default_currency)
        
        with authenticator.connection() as conn:
            service = DatabaseQueryService(conn)
            meters = service.get_sku_meters(currency, sku_family)
        return jsonify(meters)
    except Exception as e:
        logger.error(f"Error getting SKU meters: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/meter-history/<meter_id>')
def get_meter_history(meter_id):
    """Get price history for a specific meter"""
    try:
        currency = request.args.get('currency', config.default_currency)
        
        with authenticator.connection() as conn:
            service = DatabaseQueryService(conn)
            history = service.get_meter_price_history(meter_id, currency)
        return jsonify(history)
    except Exception as e:
        logger.error(f"Error getting meter history: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/cheapest-region/<sku_family>')
def get_cheapest_region(sku_family):
    """Get the cheapest region for a SKU family"""
    try:
        currency = request.args.get('currency', config.default_currency)
        
        with authenticator.connection() as conn:
            service = DatabaseQueryService(conn)
            result = service.get_cheapest_region_for_sku(sku_family, currency)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting cheapest region: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # For local development
    app.run(debug=True, host='0.0.0.0', port=5000)
