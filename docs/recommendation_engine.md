# Voyager Recommendation Engine: A Deep Dive

The Voyager recommendation engine is a sophisticated system designed to provide users with intelligent, context-aware tour recommendations. It's built on a modern, high-performance tech stack and employs a multi-layered strategy to deliver relevant and personalized suggestions. This document provides a detailed look into its architecture and logic.

---

## 1. System Architecture

The engine is built around a few core components:

-   **FastAPI**: A high-performance Python web framework used to build the API. It provides automatic data validation, interactive documentation, and excellent asynchronous support.
-   **ClickHouse**: A columnar database that is optimized for real-time analytics and fast queries. It stores all tour data and is the backbone of our recommendation logic.
-   **Pydantic**: Used for data validation and settings management, ensuring that all data flowing into and out of the application is well-structured and type-safe.
-   **OpenAI GPT**: Leveraged to generate personalized, human-like reasons for each recommendation, enhancing the user experience.

---

## 2. The Smart Recommendation Workflow

The core of the engine is the **Smart Recommendation API**, which follows a sophisticated workflow to generate its suggestions. When a request is received, it goes through the following key phases:

### Phase 1: Context Derivation

The first step is to understand the user's current context. The `_derive_context` method gathers and processes real-time information:

-   **Time of Day**: The user's local time is used to determine whether it's morning, afternoon, evening, or night.
-   **Season**: The current month is used to determine the season (e.g., Summer, Winter), which can influence tour suitability.
-   **Weather (Optional)**: If latitude and longitude are provided, the engine queries an external weather service to get the current conditions (e.g., "Rain", "Clear"). This is crucial for recommending weather-appropriate activities.

### Phase 2: Candidate Selection (`_get_candidate_tours`)

Once the context is established, the engine searches for a pool of suitable "candidate" tours. This is where the multi-layered fallback strategy comes into play, ensuring that the user always gets a recommendation.

-   **Attempt 1: The Ideal Scenario (20km Radius)**
    The engine first runs a highly specific query that combines all available filters:
    -   **Geo-location**: Filters for tours within a 20km radius of the user's location.
    -   **Weather**: If it's raining, it prioritizes `indoor` tours; otherwise, it looks for `outdoor` or `both`.
    -   **Time of Day**: Matches the user's current time of day.
    -   **User Preferences**: Incorporates any explicit preferences for tour type, category, or price range.
    -   **Feedback**: Excludes any tours the user has previously disliked.

-   **Attempt 2: The Broader Search (100km Radius)**
    If the first attempt yields no results, the engine automatically broadens its search. It runs a second query with the same filters as before, but increases the **search radius to 100km**. This is particularly useful in less dense areas where the closest tours might be further away.

-   **Attempt 3: The Final Fallback (Just Geolocation)**
    If both previous attempts fail, the engine executes a final, much broader query. It **discards all filters except for geo-location**, returning any tours available within a 20km radius. This ensures that the user is always presented with nearby options, even if they don't perfectly match every other criterion.

### Phase 3: Ranking & Scoring (`_rank_and_select_tours`)

After a list of candidate tours is generated, the next step is to rank them to find the best possible matches. The engine uses a scoring system that assigns points based on several factors:

-   **Distance (Highest Priority)**: If the user's location is known, the tours are primarily sorted by distance in ascending order, ensuring that the closest options are always ranked first.
-   **User Feedback**: Tours in categories that the user has previously liked receive a significant score boost.
-   **Inventory Availability (Temporarily Disabled)**: The engine is designed to check real-time tour availability and boost tours that have open slots in the next two days. This feature is currently disabled but can be re-enabled.

The final ranking is determined by a combination of these scores, with distance being the most influential factor.

### Phase 4: Personalized Explanations

The final step is to generate a personalized reason for each of the top-ranked recommendations. The engine sends the user's context and the details of each tour to the **OpenAI GPT API** and asks it to generate a short, friendly explanation.

This results in recommendations like: *"Since it's a sunny afternoon, this highly-rated outdoor tour is a perfect match and it's just a short distance from you!"*

This final touch makes the recommendations feel more personal and helpful, significantly improving the user experience. 