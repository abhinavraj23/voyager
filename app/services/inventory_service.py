import httpx
from datetime import date, timedelta
from typing import List, Optional, Dict, Set
import logging
from app.models.inventory import CalendarResponse

logger = logging.getLogger(__name__)

class InventoryService:
    def __init__(self):
        self.base_url = "https://api.headout.com/api/v7"
        self.headers = {
            'accept': '*/*',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        }
        # In a real app, you would use a proper cache like Redis
        self._cache = {}

    async def get_tour_group_availability(self, tour_group_id: int, currency: str = "USD") -> Optional[CalendarResponse]:
        """
        Fetches availability for a tour group from the Headout API.
        """
        cache_key = f"{tour_group_id}:{currency}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        url = f"{self.base_url}/tour-groups/{tour_group_id}/calendar/"
        params = {"currency": currency}
        
        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"Fetching inventory for tour group {tour_group_id} from {url} with currency {currency}")
                response = await client.get(url, params=params, headers=self.headers)
                response.raise_for_status()
                
                response_model = CalendarResponse(**response.json())
                self._cache[cache_key] = response_model
                
                logger.info(f"Successfully fetched inventory for tour group {tour_group_id}. Found availability for {len(response_model.dates)} dates.")
                return response_model

            except httpx.RequestError as e:
                logger.error(f"Request error while fetching inventory for tour group {tour_group_id}: {e}")
                return None
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP status error fetching inventory for tour group {tour_group_id}: {e.response.status_code} - {e.response.text}")
                return None
            except Exception as e:
                logger.error(f"Error parsing inventory data for tour group {tour_group_id}: {e}")
                return None

    async def get_available_tour_groups(self, tour_group_ids: List[int], days: int = 2) -> Set[int]:
        """
        Checks availability for multiple tour groups for the next `days` and returns a set of tour group IDs that have at least one tour available.
        """
        available_tour_group_ids: Set[int] = set()
        dates_to_check = [date.today() + timedelta(days=i) for i in range(days)]

        for group_id in tour_group_ids:
            calendar = await self.get_tour_group_availability(group_id)
            if calendar:
                for check_date in dates_to_check:
                    # The dates from the API are already date objects thanks to Pydantic
                    if check_date in calendar.dates:
                        availability = calendar.dates[check_date]
                        if availability.available_tour_ids:
                            available_tour_group_ids.add(group_id)
                            break  # Found availability, no need to check other dates for this group
        
        return available_tour_group_ids 