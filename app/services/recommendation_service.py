from typing import List, Dict, Optional, Any
import logging
import math
from datetime import datetime
from clickhouse_driver import Client
import openai
from app.config import settings
from app.models.recommendation import RecommendationRequest, PopularToursRequest, SmartRecommendationRequest, RecommendedTour
from app.services.weather_service import WeatherService
from app.utils.cache import cached
# from app.services.inventory_service import InventoryService

logger = logging.getLogger(__name__)

@cached(ttl=1800, key_prefix="openai_recommendation_reason")
async def _generate_recommendation_reason_cached(tour: dict, request_data: dict, context: dict, openai_api_key: str) -> str:
    """Cached function for generating recommendation reasons"""
    if not openai_api_key:
        return "Recommended based on your preferences and current context."

    openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
    
    user_context_parts = []
    if request_data.get('lat') is not None and request_data.get('lon') is not None:
        user_context_parts.append(f"- Location: Near latitude {request_data['lat']}, longitude {request_data['lon']}")
    
    user_context_parts.append(f"- Time: It's currently {context['time_of_day']} on {request_data['local_datetime']}.")

    if context.get('weather'):
        user_context_parts.append(f"- Weather: The weather is {context['weather']['condition']} at {context['weather']['temperature_celsius']}°C.")

    if request_data.get('preferences'):
        user_context_parts.append(f"- Preferences: {request_data['preferences']}.")

    user_context_str = "\n".join(user_context_parts)

    prompt = f"""
    Generate a very short, compelling reason (maximum 2 lines, ideally 1-2 sentences) why this tour is recommended for the user.

    User's Context:
    {user_context_str}

    Tour Details:
    - Name: {tour['name']}
    - Category: {tour['category_name']}
    - Type: {tour['tour_type']}
    - Price Range: {tour['pricing_range_usd']}
    - Summary: Best for {', '.join(tour['group_type_suitability'])} during {', '.join(tour['time_of_day_trip_type'])}.

    Requirements:
    - Keep it to maximum 2 lines
    - Be concise and direct
    - Focus on the most relevant factor (weather, location, time, or preferences)
    - Make it personal and engaging

    Example: "Perfect for this sunny afternoon! This outdoor tour is just minutes away and matches your preferences."
    """
    
    try:
        chat_completion = await openai_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4.1-mini",
            temperature=0.7,
            max_tokens=80,
        )
        reason = chat_completion.choices[0].message.content.strip()
        return reason
    except Exception as e:
        logger.error(f"Error generating recommendation reason from OpenAI: {e}")
        return "This tour is a great fit based on your location and preferences."

class RecommendationService:
    """Service class for recommendation-related operations"""
    
    def __init__(self, client: Client):
        self.client = client
        self.weather_service = WeatherService()
        # self.inventory_service = InventoryService()
        self.openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
    
    def get_recommendations(self, request: RecommendationRequest) -> Dict[str, Any]:
        """Get personalized tour recommendations"""
        try:
            query = "SELECT * FROM tour_info WHERE 1=1"
            params = []
            filters_applied = {}
            
            # Apply location-based filtering if coordinates provided
            if request.user_location_lat and request.user_location_long:
                # Calculate distance using Haversine formula
                distance_query = self._build_distance_query(
                    request.user_location_lat, 
                    request.user_location_long, 
                    request.max_distance_km
                )
                query += f" AND {distance_query}"
                filters_applied["location"] = {
                    "lat": request.user_location_lat,
                    "long": request.user_location_long,
                    "max_distance_km": request.max_distance_km
                }
            
            # Apply tour type filter
            if request.preferred_tour_type:
                query += " AND tour_type = %s"
                params.append(request.preferred_tour_type)
                filters_applied["tour_type"] = request.preferred_tour_type
            
            # Apply time of day filter
            if request.preferred_time_of_day:
                time_conditions = []
                for time in request.preferred_time_of_day:
                    time_conditions.append("has(time_of_day_trip_type, %s)")
                    params.append(time)
                query += f" AND ({' OR '.join(time_conditions)})"
                filters_applied["time_of_day"] = request.preferred_time_of_day
            
            # Apply season filter
            if request.preferred_season:
                season_conditions = []
                for season in request.preferred_season:
                    season_conditions.append("has(season, %s)")
                    params.append(season)
                query += f" AND ({' OR '.join(season_conditions)})"
                filters_applied["season"] = request.preferred_season
            
            # Apply group type filter
            if request.group_type:
                query += " AND has(group_type_suitability, %s)"
                params.append(request.group_type)
                filters_applied["group_type"] = request.group_type
            
            # Apply price range filter
            if request.max_price_range:
                query += " AND pricing_range_usd <= %s"
                params.append(request.max_price_range)
                filters_applied["max_price"] = request.max_price_range
            
            # Apply category filter
            if request.category_preference:
                query += " AND category_name = %s"
                params.append(request.category_preference)
                filters_applied["category"] = request.category_preference
            
            # Add ordering and limit
            query += " ORDER BY id LIMIT %s"
            params.append(request.limit)
            
            result = self.client.execute(query, params, with_column_types=True)
            columns = [col[0] for col in result[1]]
            recommendations = [dict(zip(columns, row)) for row in result[0]]
            
            return {
                "recommendations": recommendations,
                "total_count": len(recommendations),
                "filters_applied": filters_applied,
                "metadata": {
                    "request_id": f"rec_{hash(str(request.dict()))}",
                    "algorithm": "filter_based"
                }
            }
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            raise
    
    def get_similar_tours(self, tour_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Get similar tours based on a given tour"""
        try:
            # First, get the base tour
            base_tour_query = "SELECT * FROM tour_info WHERE id = %s"
            base_tour_result = self.client.execute(base_tour_query, [tour_id], with_column_types=True)
            
            if not base_tour_result[0]:
                return []
            
            columns = [col[0] for col in base_tour_result[1]]
            base_tour = dict(zip(columns, base_tour_result[0][0]))
            
            # Build similarity query
            query = """
                SELECT *, 
                       (CASE WHEN category_name = %s THEN 3 ELSE 0 END +
                        CASE WHEN subcategory_name = %s THEN 2 ELSE 0 END +
                        CASE WHEN tour_type = %s THEN 2 ELSE 0 END +
                        CASE WHEN pricing_range_usd = %s THEN 1 ELSE 0 END) as similarity_score
                FROM tour_info 
                WHERE id != %s
                ORDER BY similarity_score DESC, id
                LIMIT %s
            """
            
            params = [
                base_tour['category_name'],
                base_tour['subcategory_name'],
                base_tour['tour_type'],
                base_tour['pricing_range_usd'],
                tour_id,
                limit
            ]
            
            result = self.client.execute(query, params, with_column_types=True)
            columns = [col[0] for col in result[1]]
            similar_tours = [dict(zip(columns, row)) for row in result[0]]
            
            return similar_tours
        except Exception as e:
            logger.error(f"Error getting similar tours: {e}")
            raise
    
    def get_popular_tours(self, request: PopularToursRequest) -> List[Dict[str, Any]]:
        """Get popular tours in a specific area or category"""
        try:
            query = "SELECT * FROM tour_info WHERE 1=1"
            params = []
            
            # Apply category filter
            if request.category:
                query += " AND category_name = %s"
                params.append(request.category)
            
            # Apply location filter
            if request.location_lat and request.location_long:
                distance_query = self._build_distance_query(
                    request.location_lat,
                    request.location_long,
                    request.radius_km
                )
                query += f" AND {distance_query}"
            
            # Add ordering and limit
            query += " ORDER BY id LIMIT %s"
            params.append(request.limit)
            
            result = self.client.execute(query, params, with_column_types=True)
            columns = [col[0] for col in result[1]]
            popular_tours = [dict(zip(columns, row)) for row in result[0]]
            
            return popular_tours
        except Exception as e:
            logger.error(f"Error getting popular tours: {e}")
            raise
    
    def get_nearby_tours(self, lat: float, long: float, radius_km: float, limit: int) -> List[Dict[str, Any]]:
        """Get tours near a specific location"""
        try:
            distance_query = self._build_distance_query(lat, long, radius_km)
            query = f"SELECT * FROM tour_info WHERE {distance_query} ORDER BY id LIMIT %s"
            
            result = self.client.execute(query, [limit], with_column_types=True)
            columns = [col[0] for col in result[1]]
            nearby_tours = [dict(zip(columns, row)) for row in result[0]]
            
            return nearby_tours
        except Exception as e:
            logger.error(f"Error getting nearby tours: {e}")
            raise
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all available tour categories with counts"""
        try:
            query = """
                SELECT category_name, COUNT(*) as tour_count
                FROM tour_info 
                GROUP BY category_name 
                ORDER BY tour_count DESC
            """
            
            result = self.client.execute(query)
            categories = [{"category": row[0], "count": row[1]} for row in result]
            
            return categories
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about tours and recommendations"""
        try:
            stats = {}
            
            # Total tours
            total_result = self.client.execute("SELECT COUNT(*) FROM tour_info")
            stats["total_tours"] = total_result[0][0]
            
            # Tours by type
            type_result = self.client.execute("SELECT tour_type, COUNT(*) FROM tour_info GROUP BY tour_type")
            stats["tours_by_type"] = {row[0]: row[1] for row in type_result}
            
            # Tours by price range
            price_result = self.client.execute("SELECT pricing_range_usd, COUNT(*) FROM tour_info GROUP BY pricing_range_usd")
            stats["tours_by_price"] = {row[0]: row[1] for row in price_result}
            
            # Categories
            category_result = self.client.execute("SELECT category_name, COUNT(*) FROM tour_info GROUP BY category_name")
            stats["tours_by_category"] = {row[0]: row[1] for row in category_result}
            
            return stats
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            raise

    def get_random_tour(self) -> Optional[Dict[str, Any]]:
        """Get a single random tour from the database."""
        try:
            query = "SELECT * FROM tour_info ORDER BY rand() LIMIT 1"
            result = self.client.execute(query, with_column_types=True)
            
            if not result[0]:
                return None
            
            columns = [col[0] for col in result[1]]
            random_tour = dict(zip(columns, result[0][0]))
            
            return random_tour
        except Exception as e:
            logger.error(f"Error getting random tour: {e}")
            raise

    def _build_distance_query(self, lat: float, long: float, max_distance_km: float) -> str:
        """Build distance calculation query using ClickHouse's native geoDistance function."""
        max_distance_meters = max_distance_km * 1000
        # geoDistance(lon, lat, table_lon, table_lat) returns distance in meters.
        return f"geoDistance({long}, {lat}, long, lat) <= {max_distance_meters}"

    async def get_smart_recommendations(self, request: SmartRecommendationRequest) -> Dict[str, Any]:
        """
        Generates smart, context-aware tour recommendations using a layered filtering approach.
        """
        # 1. Derive real-time context (weather, time, season)
        context = await self._derive_context(request)
        
        # 2. Apply filters sequentially to find candidate tours
        candidate_ids = self._get_candidate_tours(request, context)
        print(f"Candidate IDs: {candidate_ids}")

        if not candidate_ids:
            return {
                "recommendations": [],
                "context": context
            }

        # 3. Rank the candidates and select the best ones
        # Pass weather context to the request for use in scoring
        if context.get('weather'):
            request._weather_context = context['weather']
        
        final_tours = await self._rank_and_select_tours(candidate_ids, request)

        # 4. Generate personalized explanations for the final recommendations
        recommendations_with_reasons = []
        for tour in final_tours:
            reason = await self._generate_recommendation_reason(tour, request, context)
            recommended_tour = RecommendedTour(**tour, recommendation_reason=reason)
            recommendations_with_reasons.append(recommended_tour)
            
        return {
            "recommendations": recommendations_with_reasons,
            "context": context
        }

    def _get_candidate_tours(self, request: SmartRecommendationRequest, context: dict) -> List[int]:
        """
        Applies a hierarchical set of filters to find relevant tours using a
        multi-layered fallback strategy.
        """
        base_query = "SELECT id FROM tour_info WHERE 1=1"
        
        # --- Query 1: Strict search with all filters and 20km radius ---
        logger.info("Attempt 1: Strict search with all filters and 10km radius.")
        conditions_1 = []
        params_1: Dict[str, Any] = {}

        if request.lat is not None and request.lon is not None:
            conditions_1.append(f"({self._build_distance_query(request.lat, request.lon, 10)})")
        
        if context.get('weather'):
            weather_filter = self._get_weather_filter(context['weather']['condition'])
            if weather_filter:
                conditions_1.append(weather_filter)
        
        conditions_1.append("has(time_of_day_trip_type, %(time_of_day)s)")
        params_1['time_of_day'] = context['time_of_day']
        
        prefs_filter = self._get_preferences_filter(request.preferences)
        if prefs_filter:
            conditions_1.append(f"({prefs_filter})")
            params_1.update(self._get_preferences_params(request.preferences))
            
        feedback_filter = self._get_feedback_filter(request.feedback)
        if feedback_filter:
            conditions_1.append(feedback_filter)
            params_1.update(self._get_feedback_params(request.feedback))

        try:
            query_1 = f"{base_query} AND {' AND '.join(conditions_1)}"
            logger.info(f"Executing query 1: {query_1} with params: {params_1}")
            result_1 = self.client.execute(query_1, params_1)
            if result_1:
                logger.info(f"Success on attempt 1. Found {len(result_1)} tours.")
                return [row[0] for row in result_1]
        except Exception as e:
            logger.error(f"Error on attempt 1: {e}", exc_info=True)

        # --- Query 2: Fallback with 100km radius and other filters ---
        logger.info("Attempt 2: Fallback with 30km radius.")
        if request.lat is not None and request.lon is not None:
            conditions_2 = []
            params_2: Dict[str, Any] = {}

            conditions_2.append(f"({self._build_distance_query(request.lat, request.lon, 30)})")
            
            if context.get('weather'):
                weather_filter = self._get_weather_filter(context['weather']['condition'])
                if weather_filter:
                    conditions_2.append(weather_filter)
            
            conditions_2.append("has(time_of_day_trip_type, %(time_of_day)s)")
            params_2['time_of_day'] = context['time_of_day']

            if prefs_filter:
                conditions_2.append(f"({prefs_filter})")
                params_2.update(self._get_preferences_params(request.preferences))

            if feedback_filter:
                conditions_2.append(feedback_filter)
                params_2.update(self._get_feedback_params(request.feedback))

            try:
                query_2 = f"{base_query} AND {' AND '.join(conditions_2)}"
                logger.info(f"Executing query 2: {query_2} with params: {params_2}")
                result_2 = self.client.execute(query_2, params_2)
                if result_2:
                    logger.info(f"Success on attempt 2. Found {len(result_2)} tours.")
                    return [row[0] for row in result_2]
            except Exception as e:
                logger.error(f"Error on attempt 2: {e}", exc_info=True)

        # --- Query 3: Final fallback with just 20km radius ---
        logger.info("Attempt 3: Final fallback with 20km radius only.")
        if request.lat is not None and request.lon is not None:
            try:
                query_3 = f"{base_query} AND ({self._build_distance_query(request.lat, request.lon, 10)})"
                logger.info(f"Executing query 3: {query_3}")
                result_3 = self.client.execute(query_3)
                if result_3:
                    logger.info(f"Success on attempt 3. Found {len(result_3)} tours.")
                    return [row[0] for row in result_3]
            except Exception as e:
                logger.error(f"Error on attempt 3: {e}", exc_info=True)
        
        logger.info("All attempts failed. No tours found.")
        return []

    async def _rank_and_select_tours(self, tour_ids: List[int], request: SmartRecommendationRequest) -> List[Dict]:
        """
        Ranks and selects tours based on multiple factors including preferences,
        weather, location, and user feedback.
        """
        if not tour_ids:
            return []

        # Build a query to fetch the full details for the candidate tours
        query = """
            SELECT *, 
                   geoDistance(%(lon)s, %(lat)s, long, lat) as distance_meters
            FROM tour_info 
            WHERE id IN %(tour_ids)s
        """
        
        params: Dict[str, Any] = {
            'tour_ids': tuple(tour_ids),
            'lat': request.lat or 0,
            'lon': request.lon or 0
        }

        logger.info(f"Executing ranking query for {len(tour_ids)} tours")
        result = self.client.execute(query, params, with_column_types=True)
        columns = [col[0] for col in result[1]]
        tours = [dict(zip(columns, row)) for row in result[0]]

        # Rank tours based on multiple factors
        ranked_tours = []
        for tour in tours:
            score = self._calculate_tour_score(tour, request)
            ranked_tours.append((tour, score))
        
        # Sort by score (highest first) and take top results
        ranked_tours.sort(key=lambda x: x[1], reverse=True)
        selected_tours = [tour for tour, score in ranked_tours[:request.limit]]
        
        logger.info(f"Ranked {len(tours)} tours, selected top {len(selected_tours)}")
        return selected_tours

    def _calculate_tour_score(self, tour: Dict, request: SmartRecommendationRequest) -> float:
        """
        Calculate a comprehensive score for a tour based on multiple factors.
        Returns a score between 0 and 100.
        """
        score = 0.0
        
        # 1. Location/Distance Score (0-25 points)
        if request.lat is not None and request.lon is not None and 'distance_meters' in tour:
            distance_km = tour['distance_meters'] / 1000
            if distance_km <= 5:
                score += 25  # Very close
            elif distance_km <= 10:
                score += 20  # Close
            elif distance_km <= 20:
                score += 15  # Moderate distance
            elif distance_km <= 50:
                score += 10  # Far but acceptable
            else:
                score += 5   # Very far
        
        # 2. Preference Matching Score (0-30 points)
        if request.preferences:
            # Tour type preference
            if request.preferences.tour_type and tour['tour_type'] == request.preferences.tour_type.value:
                score += 10
            
            # Category preference
            if request.preferences.category and tour['category_name'] == request.preferences.category:
                score += 10
            
            # Price range preference
            if request.preferences.price_range and tour['pricing_range_usd'] == request.preferences.price_range.value:
                score += 10
        
        # 3. Weather Compatibility Score (0-15 points)
        # Get weather context from the request context (will be passed from get_smart_recommendations)
        weather_score = self._get_weather_compatibility_score(tour, request)
        score += weather_score
        
        # 4. Time of Day Compatibility Score (0-15 points)
        time_score = self._get_time_compatibility_score(tour, request)
        score += time_score
        
        # 5. User Feedback Score (0-15 points)
        feedback_score = self._get_feedback_score(tour, request)
        score += feedback_score
        
        # 6. Popularity/Quality Indicators (bonus points)
        # Add bonus for tours with good indicators (this could be expanded)
        if tour.get('rating', 0) > 4.0:
            score += 5
        
        return min(score, 100.0)  # Cap at 100

    def _get_weather_compatibility_score(self, tour: Dict, request: SmartRecommendationRequest) -> float:
        """Calculate weather compatibility score (0-15 points)"""
        tour_type = tour.get('tour_type', '')
        
        # Try to get weather from the request context
        # This would be populated by the _derive_context method
        weather_condition = None
        if hasattr(request, '_weather_context'):
            weather_condition = request._weather_context.get('condition')
        
        # If no weather data, use default scoring
        if not weather_condition:
            if tour_type == 'indoor':
                return 10  # Good for any weather
            elif tour_type == 'outdoor':
                return 8   # Good for good weather
            elif tour_type == 'both':
                return 12  # Flexible for any weather
            return 5
        
        # Score based on actual weather condition
        if weather_condition == "Rain":
            if tour_type == 'indoor':
                return 15  # Perfect for rainy weather
            elif tour_type == 'both':
                return 12  # Good option
            else:
                return 5   # Not ideal for rain
        elif weather_condition in ["Clear", "Clouds"]:
            if tour_type == 'outdoor':
                return 15  # Perfect for good weather
            elif tour_type == 'both':
                return 12  # Good option
            else:
                return 8   # Indoor is fine but not optimal
        else:
            # For other weather conditions, use balanced scoring
            if tour_type == 'both':
                return 12  # Most flexible
            elif tour_type == 'indoor':
                return 10  # Safe choice
            else:
                return 8   # Outdoor might be affected

    def _get_time_compatibility_score(self, tour: Dict, request: SmartRecommendationRequest) -> float:
        """Calculate time of day compatibility score (0-15 points)"""
        # Derive time of day from request
        hour = request.local_datetime.hour
        if 5 <= hour < 12:
            current_time = "morning"
        elif 12 <= hour < 17:
            current_time = "afternoon"
        elif 17 <= hour < 21:
            current_time = "evening"
        else:
            current_time = "night"
        
        # Check if tour is suitable for current time
        time_of_day_types = tour.get('time_of_day_trip_type', [])
        if current_time in time_of_day_types:
            return 15
        elif any(time_type in time_of_day_types for time_type in ['morning', 'afternoon', 'evening', 'night']):
            return 10
        else:
            return 5

    def _get_feedback_score(self, tour: Dict, request: SmartRecommendationRequest) -> float:
        """Calculate score based on user feedback (0-15 points)"""
        score = 0
        
        if request.feedback:
            tour_id = tour.get('id')
            
            # Penalty for disliked tours
            if request.feedback.disliked_tours and tour_id in request.feedback.disliked_tours:
                return -50  # Heavy penalty for disliked tours
            
            # Bonus for similar tours to liked ones
            if request.feedback.liked_tours:
                # Check if this tour is similar to liked tours
                liked_tour_categories = set()
                liked_tour_types = set()
                
                # This would ideally query the database for liked tour details
                # For now, we'll use a simplified approach
                if tour.get('category_name') in liked_tour_categories:
                    score += 10
                if tour.get('tour_type') in liked_tour_types:
                    score += 5
        
        return score

    def _get_weather_filter(self, weather_condition: str) -> Optional[str]:
        if weather_condition == "Rain":
            return "tour_type = 'indoor'"
        elif weather_condition in ["Clear", "Clouds"]:
            return "tour_type IN ('outdoor', 'both')"
        return None

    def _get_preferences_filter(self, prefs) -> Optional[str]:
        if not prefs: return None
        clauses = []
        if prefs.tour_type: clauses.append("tour_type = %(tour_type)s")
        if prefs.category: clauses.append("category_name = %(category)s")
        if prefs.price_range: clauses.append("pricing_range_usd = %(price_range)s")
        return " AND ".join(clauses) if clauses else None

    def _get_preferences_params(self, prefs) -> dict:
        if not prefs: return {}
        params = {}
        if prefs.tour_type: params['tour_type'] = prefs.tour_type.value
        if prefs.category: params['category'] = prefs.category
        if prefs.price_range: params['price_range'] = prefs.price_range.value
        return params

    def _get_feedback_filter(self, feedback) -> Optional[str]:
        if feedback and feedback.disliked_tours:
            return "id NOT IN %(disliked_tours)s"
        return None

    def _get_feedback_params(self, feedback) -> dict:
        if feedback and feedback.disliked_tours:
            return {'disliked_tours': tuple(feedback.disliked_tours)}
        return {}

    async def _derive_context(self, request: SmartRecommendationRequest) -> dict:
        """Fetches weather and derives time-based context."""
        context = {}

        # Get weather if location is provided
        if request.lat is not None and request.lon is not None:
            context['weather'] = await self.weather_service.get_current_weather(request.lat, request.lon)
        
        # Derive time of day
        hour = request.local_datetime.hour
        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "night"
            
        # Derive season
        month = request.local_datetime.month
        # This is a simplified logic for Northern Hemisphere. Can be improved.
        if month in [12, 1, 2]:
            season = "Winter"
        elif month in [3, 4, 5]:
            season = "Spring" # Assuming not a distinct filter, maps to general
        elif month in [6, 7, 8]:
            season = "Summer"
        else:
            season = "Autumn" # Assuming not a distinct filter

        
        context["time_of_day"] = time_of_day
        context["season"] = season
        
        return context

    def _build_smart_query(self, request: SmartRecommendationRequest, context: dict) -> (str, list):
        """Builds the dynamic ClickHouse query based on all factors."""
        query_parts = ["SELECT * FROM tour_info WHERE 1=1"]
        params = []
        
        # Geo-distance filter (initial radius)
        if request.lat is not None and request.lon is not None:
            query_parts.append(f"AND ({self._build_distance_query(request.lat, request.lon, 20)})")
        
        # Weather-based filter
        if context.get('weather'):
            weather_condition = context['weather']['condition']
            if weather_condition == "Rain":
                query_parts.append("AND tour_type = 'indoor'")
            elif weather_condition in ["Clear", "Clouds"]:
                query_parts.append("AND tour_type IN ('outdoor', 'both')")

        # Time of day filter
        query_parts.append("AND has(time_of_day_trip_type, %s)")
        params.append(context['time_of_day'])
        
        # Explicit preferences
        if request.preferences:
            if request.preferences.tour_type:
                query_parts.append("AND tour_type = %s")
                params.append(request.preferences.tour_type.value)
            if request.preferences.category:
                query_parts.append("AND category_name = %s")
                params.append(request.preferences.category)
            if request.preferences.price_range:
                query_parts.append("AND pricing_range_usd = %s")
                params.append(request.preferences.price_range.value)
        
        # Disliked tours
        if request.feedback and request.feedback.disliked_tours:
            query_parts.append("AND id NOT IN (%s)")
            params.append(request.feedback.disliked_tours)
            
        # Scoring for liked tours (if provided)
        # This is a simplified scoring model. A more advanced one could be used.
        order_by_clause = "ORDER BY "
        if request.feedback and request.feedback.liked_tours:
            liked_tours_str = ', '.join(map(str, request.feedback.liked_tours))
            order_by_clause += f"(multiIf(id IN ({liked_tours_str}), 10, category_name IN (SELECT category_name FROM tour_info WHERE id IN ({liked_tours_str})), 5, 0)) DESC, "
        
        order_by_clause += "id" # Fallback sort
        
        query_parts.append(order_by_clause)
        query_parts.append("LIMIT %s")
        params.append(request.limit)
        
        final_query = " ".join(query_parts)
        logger.info(f"Executing smart query: {final_query} with params: {params}")
        
        return final_query, params

    async def _generate_recommendation_reason(self, tour: dict, request: SmartRecommendationRequest, context: dict) -> str:
        """Uses GPT to generate a personalized reason for the recommendation."""
        # Convert request to serializable dict for caching
        request_data = {
            'lat': request.lat,
            'lon': request.lon,
            'local_datetime': request.local_datetime.strftime('%A, %Y-%m-%d %H:%M:%S'),
            'preferences': request.preferences.dict() if request.preferences else None
        }
        
        # Use the cached function
        return await _generate_recommendation_reason_cached(
            tour, 
            request_data, 
            context, 
            settings.openai_api_key or ""
        ) 