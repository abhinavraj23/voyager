from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any
from enum import Enum

class TourType(str, Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    BOTH = "both"

class TimeOfDay(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"

class Season(str, Enum):
    SUMMER = "Summer"
    WINTER = "Winter"
    CHRISTMAS = "Christmas"
    RAINY = "Rainy"

class GroupType(str, Enum):
    SOLO = "solo"
    FAMILY = "family"
    COUPLES = "couples"

class PricingRange(str, Enum):
    LOW = "0-50 USD"
    MEDIUM = "50-100 USD"
    HIGH = "100-200 USD"
    VERY_HIGH = "200-500 USD"
    PREMIUM = "500+ USD"

class TourBase(BaseModel):
    """Base tour model"""
    id: int = Field(..., description="Tour ID")
    name: str = Field(..., description="Tour name")
    lat: float = Field(..., description="Latitude")
    long: float = Field(..., description="Longitude")
    pricing_range_usd: PricingRange = Field(..., description="Price range in USD")
    category_name: str = Field(..., description="Primary category")
    subcategory_name: str = Field(..., description="Primary sub-category")
    time_of_day_trip_type: List[TimeOfDay] = Field(..., description="Suitable times of day")
    tour_type: TourType = Field(..., description="Type of tour")
    season: List[Season] = Field(..., description="Best seasons to visit")
    group_type_suitability: List[GroupType] = Field(..., description="Suitable group types")

    @field_validator('pricing_range_usd', mode='before')
    @classmethod
    def normalize_pricing_range(cls, v: Any) -> Optional[Any]:
        if isinstance(v, str):
            return v.replace(' - ', '-')
        return v

    @field_validator('group_type_suitability', 'season', 'time_of_day_trip_type', mode='before')
    @classmethod
    def clean_string_list_field(cls, v: Any) -> Any:
        if isinstance(v, list):
            # This handles cases like ["'solo'", 'family']
            return [s.strip().strip("'\"") for s in v if isinstance(s, str)]
        return v

class TourResponse(TourBase):
    """Tour response model"""
    pass

class TourCreate(TourBase):
    """Tour creation model"""
    pass

class TourUpdate(BaseModel):
    """Tour update model"""
    name: Optional[str] = None
    lat: Optional[float] = None
    long: Optional[float] = None
    pricing_range_usd: Optional[PricingRange] = None
    category_name: Optional[str] = None
    subcategory_name: Optional[str] = None
    time_of_day_trip_type: Optional[List[TimeOfDay]] = None
    tour_type: Optional[TourType] = None
    season: Optional[List[Season]] = None
    group_type_suitability: Optional[List[GroupType]] = None 