from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from .tour import TourType, TimeOfDay, Season, GroupType, PricingRange, TourResponse

class RecommendationRequest(BaseModel):
    """Recommendation request model"""
    user_location_lat: Optional[float] = Field(None, description="User's latitude")
    user_location_long: Optional[float] = Field(None, description="User's longitude")
    max_distance_km: Optional[float] = Field(100.0, description="Maximum distance in kilometers")
    preferred_tour_type: Optional[TourType] = Field(None, description="Preferred tour type")
    preferred_time_of_day: Optional[List[TimeOfDay]] = Field(None, description="Preferred times of day")
    preferred_season: Optional[List[Season]] = Field(None, description="Preferred seasons")
    group_type: Optional[GroupType] = Field(None, description="Group type")
    max_price_range: Optional[PricingRange] = Field(None, description="Maximum price range")
    category_preference: Optional[str] = Field(None, description="Preferred category")
    limit: Optional[int] = Field(10, description="Number of recommendations to return")

class UserPreferences(BaseModel):
    """User's explicit preferences"""
    category: Optional[str] = None
    subcategory: Optional[str] = None
    price_range: Optional[PricingRange] = None
    tour_type: Optional[TourType] = None

class UserFeedback(BaseModel):
    """User's implicit feedback on tours"""
    liked_tours: Optional[List[int]] = Field(None, description="List of liked tour IDs")
    disliked_tours: Optional[List[int]] = Field(None, description="List of disliked tour IDs")

class TourFeedback(BaseModel):
    liked_tours: Optional[List[int]] = Field(None, description="List of tour IDs the user has liked.")
    disliked_tours: Optional[List[int]] = Field(None, description="List of tour IDs the user has disliked.")

class SmartRecommendationRequest(BaseModel):
    """Model for the smart recommendation endpoint"""
    lat: Optional[float] = Field(None, description="User's latitude.", example=40.7128)
    lon: Optional[float] = Field(None, description="User's longitude.", example=-74.0060)
    local_datetime: datetime = Field(default_factory=datetime.now, description="User's local date and time.")
    preferences: Optional[UserPreferences] = Field(None, description="User's explicit preferences.")
    feedback: Optional[TourFeedback] = Field(None, description="User's past feedback on tours.")
    limit: int = Field(10, gt=0, le=50, description="Number of recommendations to return.")

class RecommendedTour(TourResponse):
    """A recommended tour with an explanation"""
    recommendation_reason: str = Field(..., description="Explanation for why this tour is recommended.")

class SmartRecommendationResponse(BaseModel):
    """Response for the smart recommendation endpoint"""
    recommendations: List[RecommendedTour] = Field(..., description="List of recommended tours with explanations")
    context: dict = Field(..., description="Context used for generating recommendations (weather, time, etc.)")

class RecommendationResponse(BaseModel):
    """Recommendation response model"""
    recommendations: List[dict] = Field(..., description="List of recommended tours")
    total_count: int = Field(..., description="Total number of recommendations found")
    filters_applied: dict = Field(..., description="Filters that were applied")
    metadata: dict = Field(..., description="Additional metadata")

class SimilarTourRequest(BaseModel):
    """Similar tour request model"""
    tour_id: int = Field(..., description="Tour ID to find similar tours for")
    limit: Optional[int] = Field(5, description="Number of similar tours to return")

class PopularToursRequest(BaseModel):
    """Popular tours request model"""
    category: Optional[str] = Field(None, description="Filter by category")
    location_lat: Optional[float] = Field(None, description="Location latitude")
    location_long: Optional[float] = Field(None, description="Location longitude")
    radius_km: Optional[float] = Field(50.0, description="Search radius in kilometers")
    limit: Optional[int] = Field(10, description="Number of popular tours to return") 