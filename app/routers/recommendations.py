from fastapi import APIRouter, HTTPException, Query, Body
from typing import List
import logging

from app.repository.database import get_clickhouse_client
from app.models.recommendation import (
    RecommendationRequest, 
    RecommendationResponse,
    SimilarTourRequest,
    PopularToursRequest,
    SmartRecommendationRequest,
    SmartRecommendationResponse
)
from app.services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/recommendations/smart", response_model=SmartRecommendationResponse)
async def get_smart_recommendations(request: SmartRecommendationRequest = Body(...)):
    """
    Get smart, context-aware tour recommendations based on geo-location,
    time, weather, and personal preferences.
    """
    try:
        client = get_clickhouse_client()
        service = RecommendationService(client)
        result = await service.get_smart_recommendations(request)
        return result
    except Exception as e:
        logger.error(f"Error getting smart recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate smart recommendations.")

@router.post("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(request: RecommendationRequest):
    """Get personalized tour recommendations"""
    try:
        client = get_clickhouse_client()
        recommendation_service = RecommendationService(client)
        
        recommendations = recommendation_service.get_recommendations(request)
        return recommendations
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recommendations")

@router.post("/recommendations/similar")
async def get_similar_tours(request: SimilarTourRequest):
    """Get similar tours based on a given tour"""
    try:
        client = get_clickhouse_client()
        recommendation_service = RecommendationService(client)
        
        similar_tours = recommendation_service.get_similar_tours(request.tour_id, request.limit)
        return {
            "similar_tours": similar_tours,
            "base_tour_id": request.tour_id,
            "total": len(similar_tours)
        }
    except Exception as e:
        logger.error(f"Error getting similar tours: {e}")
        raise HTTPException(status_code=500, detail="Failed to get similar tours")

@router.post("/recommendations/popular")
async def get_popular_tours(request: PopularToursRequest):
    """Get popular tours in a specific area or category"""
    try:
        client = get_clickhouse_client()
        recommendation_service = RecommendationService(client)
        
        popular_tours = recommendation_service.get_popular_tours(request)
        return {
            "popular_tours": popular_tours,
            "total": len(popular_tours),
            "filters": {
                "category": request.category,
                "location": {
                    "lat": request.location_lat,
                    "long": request.location_long
                } if request.location_lat and request.location_long else None,
                "radius_km": request.radius_km
            }
        }
    except Exception as e:
        logger.error(f"Error getting popular tours: {e}")
        raise HTTPException(status_code=500, detail="Failed to get popular tours")

@router.get("/recommendations/nearby")
async def get_nearby_tours(
    lat: float = Query(..., description="Latitude"),
    long: float = Query(..., description="Longitude"),
    radius_km: float = Query(10.0, description="Search radius in kilometers"),
    limit: int = Query(10, description="Number of tours to return")
):
    """Get tours near a specific location"""
    try:
        client = get_clickhouse_client()
        recommendation_service = RecommendationService(client)
        
        nearby_tours = recommendation_service.get_nearby_tours(lat, long, radius_km, limit)
        return {
            "nearby_tours": nearby_tours,
            "location": {"lat": lat, "long": long},
            "radius_km": radius_km,
            "total": len(nearby_tours)
        }
    except Exception as e:
        logger.error(f"Error getting nearby tours: {e}")
        raise HTTPException(status_code=500, detail="Failed to get nearby tours")

@router.get("/recommendations/categories")
async def get_categories():
    """Get all available tour categories"""
    try:
        client = get_clickhouse_client()
        recommendation_service = RecommendationService(client)
        
        categories = recommendation_service.get_categories()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail="Failed to get categories")

@router.get("/recommendations/stats")
async def get_recommendation_stats():
    """Get statistics about tours and recommendations"""
    try:
        client = get_clickhouse_client()
        recommendation_service = RecommendationService(client)
        
        stats = recommendation_service.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

@router.get("/recommendations/random")
def get_random_recommendation():
    """
    Get a single random tour recommendation.
    """
    client = get_clickhouse_client()
    service = RecommendationService(client=client)
    tour = service.get_random_tour()
    if not tour:
        raise HTTPException(status_code=404, detail="No tours found.")
    return tour 