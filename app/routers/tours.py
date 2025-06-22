from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
import logging

from app.repository.database import get_clickhouse_client
from app.models.tour import TourResponse, TourCreate, TourUpdate
from app.services.tour_service import TourService

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/tours", response_model=List[TourResponse])
async def get_tours(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    category: Optional[str] = Query(None, description="Filter by category"),
    tour_type: Optional[str] = Query(None, description="Filter by tour type"),
    price_range: Optional[str] = Query(None, description="Filter by price range")
):
    """Get all tours with optional filtering"""
    try:
        client = get_clickhouse_client()
        tour_service = TourService(client)
        
        tours = tour_service.get_tours(
            skip=skip,
            limit=limit,
            category=category,
            tour_type=tour_type,
            price_range=price_range
        )
        
        return tours
    except Exception as e:
        logger.error(f"Error fetching tours: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch tours")

@router.get("/tours/{tour_id}", response_model=TourResponse)
async def get_tour(tour_id: int):
    """Get a specific tour by ID"""
    try:
        client = get_clickhouse_client()
        tour_service = TourService(client)
        
        tour = tour_service.get_tour_by_id(tour_id)
        if not tour:
            raise HTTPException(status_code=404, detail="Tour not found")
        
        return tour
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tour {tour_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch tour")

@router.post("/tours", response_model=TourResponse, status_code=201)
async def create_tour(tour: TourCreate):
    """Create a new tour"""
    try:
        client = get_clickhouse_client()
        tour_service = TourService(client)
        
        created_tour = tour_service.create_tour(tour.dict())
        return created_tour
    except Exception as e:
        logger.error(f"Error creating tour: {e}")
        raise HTTPException(status_code=500, detail="Failed to create tour")

@router.put("/tours/{tour_id}", response_model=TourResponse)
async def update_tour(tour_id: int, tour_update: TourUpdate):
    """Update an existing tour"""
    try:
        client = get_clickhouse_client()
        tour_service = TourService(client)
        
        # Check if tour exists
        existing_tour = tour_service.get_tour_by_id(tour_id)
        if not existing_tour:
            raise HTTPException(status_code=404, detail="Tour not found")
        
        updated_tour = tour_service.update_tour(tour_id, tour_update.dict(exclude_unset=True))
        return updated_tour
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tour {tour_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update tour")

@router.delete("/tours/{tour_id}", status_code=204)
async def delete_tour(tour_id: int):
    """Delete a tour"""
    try:
        client = get_clickhouse_client()
        tour_service = TourService(client)
        
        # Check if tour exists
        existing_tour = tour_service.get_tour_by_id(tour_id)
        if not existing_tour:
            raise HTTPException(status_code=404, detail="Tour not found")
        
        tour_service.delete_tour(tour_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tour {tour_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete tour")

@router.get("/tours/search")
async def search_tours(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Number of results to return")
):
    """Search tours by name or description"""
    try:
        client = get_clickhouse_client()
        tour_service = TourService(client)
        
        results = tour_service.search_tours(q, limit)
        return {"results": results, "query": q, "total": len(results)}
    except Exception as e:
        logger.error(f"Error searching tours: {e}")
        raise HTTPException(status_code=500, detail="Failed to search tours") 