from clickhouse_driver import Client
from app.config import settings
import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Global client instance
_clickhouse_client: Optional[Client] = None

def get_clickhouse_client() -> Client:
    """Get ClickHouse client instance"""
    global _clickhouse_client
    
    if _clickhouse_client is None:
        _clickhouse_client = create_clickhouse_client()
    
    return _clickhouse_client

def create_clickhouse_client() -> Client:
    """Create a new ClickHouse client"""
    try:
        is_secure = settings.clickhouse_secure
        client = Client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port if not is_secure else 9440,
            user=settings.clickhouse_user,
            password=settings.clickhouse_password,
            database=settings.clickhouse_db,
            secure=is_secure,
            settings={
                'max_execution_time': 30,
                'max_block_size': 10000,
                'max_threads': 4
            }
        )
        
        # Test connection
        client.execute("SELECT 1")
        logger.info("ClickHouse connection established successfully")
        
        return client
        
    except Exception as e:
        logger.error(f"Failed to connect to ClickHouse: {e}")
        raise

@contextmanager
def get_clickhouse_connection():
    """Context manager for ClickHouse connections"""
    client = get_clickhouse_client()
    try:
        yield client
    except Exception as e:
        logger.error(f"ClickHouse operation failed: {e}")
        raise

def close_clickhouse_connection():
    """Close ClickHouse connection"""
    global _clickhouse_client
    if _clickhouse_client:
        _clickhouse_client.disconnect()
        _clickhouse_client = None
        logger.info("ClickHouse connection closed") 