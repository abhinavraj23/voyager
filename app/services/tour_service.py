from typing import List, Dict, Optional, Any
import logging
from clickhouse_driver import Client

logger = logging.getLogger(__name__)

class TourService:
    """Service class for tour-related operations"""
    
    def __init__(self, client: Client):
        self.client = client
    
    def get_tours(
        self, 
        skip: int = 0, 
        limit: int = 100,
        category: Optional[str] = None,
        tour_type: Optional[str] = None,
        price_range: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get tours with optional filtering"""
        try:
            query = "SELECT * FROM tour_info WHERE 1=1"
            params = []
            
            if category:
                query += " AND category_name = %s"
                params.append(category)
            
            if tour_type:
                query += " AND tour_type = %s"
                params.append(tour_type)
            
            if price_range:
                query += " AND pricing_range_usd = %s"
                params.append(price_range)
            
            query += f" ORDER BY id LIMIT {limit} OFFSET {skip}"
            
            result = self.client.execute(query, params, with_column_types=True)
            columns = [col[0] for col in result[1]]
            tours = [dict(zip(columns, row)) for row in result[0]]
            
            return tours
        except Exception as e:
            logger.error(f"Error getting tours: {e}")
            raise
    
    def get_tour_by_id(self, tour_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific tour by ID"""
        try:
            query = "SELECT * FROM tour_info WHERE id = %s"
            result = self.client.execute(query, [tour_id], with_column_types=True)
            
            if not result[0]:
                return None
            
            columns = [col[0] for col in result[1]]
            tour = dict(zip(columns, result[0][0]))
            
            return tour
        except Exception as e:
            logger.error(f"Error getting tour {tour_id}: {e}")
            raise
    
    def create_tour(self, tour_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new tour"""
        try:
            # Check if tour already exists
            existing_tour = self.get_tour_by_id(tour_data['id'])
            if existing_tour:
                raise ValueError(f"Tour with ID {tour_data['id']} already exists")
            
            # Insert the tour
            self.client.execute(
                "INSERT INTO tour_info VALUES",
                [tour_data]
            )
            
            return self.get_tour_by_id(tour_data['id'])
        except Exception as e:
            logger.error(f"Error creating tour: {e}")
            raise
    
    def update_tour(self, tour_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing tour"""
        try:
            # Build update query dynamically
            set_clauses = []
            params = []
            
            for key, value in update_data.items():
                if value is not None:
                    set_clauses.append(f"{key} = %s")
                    params.append(value)
            
            if not set_clauses:
                return self.get_tour_by_id(tour_id)
            
            query = f"ALTER TABLE tour_info UPDATE {', '.join(set_clauses)} WHERE id = %s"
            params.append(tour_id)
            
            self.client.execute(query, params)
            
            return self.get_tour_by_id(tour_id)
        except Exception as e:
            logger.error(f"Error updating tour {tour_id}: {e}")
            raise
    
    def delete_tour(self, tour_id: int) -> None:
        """Delete a tour"""
        try:
            query = "ALTER TABLE tour_info DELETE WHERE id = %s"
            self.client.execute(query, [tour_id])
        except Exception as e:
            logger.error(f"Error deleting tour {tour_id}: {e}")
            raise
    
    def search_tours(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search tours by name or description"""
        try:
            search_query = """
                SELECT * FROM tour_info 
                WHERE name ILIKE %s OR category_name ILIKE %s OR subcategory_name ILIKE %s
                ORDER BY id 
                LIMIT %s
            """
            search_pattern = f"%{query}%"
            params = [search_pattern, search_pattern, search_pattern, limit]
            
            result = self.client.execute(search_query, params, with_column_types=True)
            columns = [col[0] for col in result[1]]
            tours = [dict(zip(columns, row)) for row in result[0]]
            
            return tours
        except Exception as e:
            logger.error(f"Error searching tours: {e}")
            raise
    
    def get_tour_count(self) -> int:
        """Get total number of tours"""
        try:
            result = self.client.execute("SELECT COUNT(*) FROM tour_info")
            return result[0][0]
        except Exception as e:
            logger.error(f"Error getting tour count: {e}")
            raise 