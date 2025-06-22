from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Any
from datetime import date

class DateAvailability(BaseModel):
    primary_pax: str = Field(..., alias='primaryPax')
    listing_price: float = Field(..., alias='listingPrice')
    retail_price: float = Field(..., alias='retailPrice')
    extra_charges: float = Field(..., alias='extraCharges')
    is_pricing_inclusive_of_extra_charges: bool = Field(..., alias='isPricingInclusiveOfExtraCharges')
    available_tour_ids: List[int] = Field(..., alias='availableTourIds')
    discount_available: bool = Field(..., alias='discountAvailable')

class CalendarMetadata(BaseModel):
    start_date: Optional[date] = Field(None, alias='startDate')
    end_date: Optional[date] = Field(None, alias='endDate')
    currency: str

    @field_validator('start_date', 'end_date', mode='before')
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Optional[Any]:
        if isinstance(v, str) and v.strip() == '':
            return None
        return v

class CalendarResponse(BaseModel):
    dates: Dict[date, DateAvailability]
    metadata: CalendarMetadata 