import httpx
from fastapi import HTTPException
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class WeatherService:
    """Service for fetching weather data from OpenWeatherMap"""
    
    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self):
        self.api_key = settings.weather_api_key
        if not self.api_key:
            raise ValueError("WEATHER_API_KEY is not set in the environment")

    async def get_current_weather(self, lat: float, lon: float) -> dict:
        """Fetch current weather for a given latitude and longitude"""
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric"  # Use Celsius
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                weather_data = response.json()
                
                # Extract relevant information
                main_weather = weather_data.get("weather", [{}])[0].get("main", "Unknown")
                temperature = weather_data.get("main", {}).get("temp", "N/A")
                
                return {
                    "condition": main_weather, # e.g., "Rain", "Clouds", "Clear"
                    "temperature_celsius": temperature
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching weather data: {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail="Failed to fetch weather data")
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching weather data: {e}")
            raise HTTPException(status_code=500, detail="An internal error occurred with the weather service") 