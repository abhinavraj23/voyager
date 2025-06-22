from pydantic import BaseModel, Field
from typing import List, Dict
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
    start_date: date = Field(..., alias='startDate')
    end_date: date = Field(..., alias='endDate')
    currency: str

class CalendarResponse(BaseModel):
    dates: Dict[date, DateAvailability]
    metadata: CalendarMetadata 