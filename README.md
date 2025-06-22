# Tour Recommendation Service

This is a FastAPI-based service for providing tour recommendations. It uses a ClickHouse database for storing tour information and provides several endpoints for different types of recommendations.

## Smart Recommendation API

The Smart Recommendation API is designed to provide intelligent, context-aware tour recommendations. It leverages a variety of factors including the user's location, local time, weather conditions, and personal preferences to deliver a ranked list of relevant tours.

### Endpoints

#### 1. GET `/api/v1/recommendations/smart`

This endpoint provides a simple, RESTful way to get smart recommendations using query parameters. It's ideal for straightforward requests and for scenarios where you need a shareable URL.

**Query Parameters:**

| Parameter        | Type                 | Description                                                                                          | Required |
| ---------------- | -------------------- | ---------------------------------------------------------------------------------------------------- | -------- |
| `lat`            | `float`              | The user's latitude. If provided, `lon` must also be given.                                          | No       |
| `lon`            | `float`              | The user's longitude. If provided, `lat` must also be given.                                         | No       |
| `tour_type`      | `string`             | The preferred tour type. Valid options: `indoor`, `outdoor`, `both`.                                 | No       |
| `category`       | `string`             | The preferred tour category (e.g., "Adventure", "Historical").                                       | No       |
| `price_range`    | `string`             | The preferred price range. Valid options: `0-50 USD`, `50-100 USD`, `100-200 USD`, `200-500 USD`, `500+ USD`. | No       |
| `liked_tours`    | `array[integer]`     | A list of tour IDs the user has previously liked.                                                    | No       |
| `disliked_tours` | `array[integer]`     | A list of tour IDs the user has previously disliked.                                                 | No       |
| `limit`          | `integer`            | The maximum number of recommendations to return. Default is `10`.                                    | No       |

**Example Request (`curl`):**

```bash
curl -G "http://localhost:8000/api/v1/recommendations/smart" \
  --data-urlencode "lat=40.7128" \
  --data-urlencode "lon=-74.0060" \
  --data-urlencode "tour_type=outdoor" \
  --data-urlencode "limit=5"
```

---

#### 2. POST `/api/v1/recommendations/smart`

This endpoint offers a more structured way to get recommendations by sending a JSON object in the request body. It's best suited for more complex requests or when you prefer to encapsulate parameters in a single object.

**Request Body (`SmartRecommendationRequest`):**

| Field            | Type                 | Description                                                                                      | Required |
| ---------------- | -------------------- | ------------------------------------------------------------------------------------------------ | -------- |
| `lat`            | `float`              | The user's latitude.                                                                             | No       |
| `lon`            | `float`              | The user's longitude.                                                                            | No       |
| `local_datetime` | `string`             | The user's local date and time in ISO format (e.g., "2024-05-22T14:30:00"). Defaults to now.      | No       |
| `preferences`    | `UserPreferences`    | An object containing the user's explicit preferences.                                            | No       |
| `feedback`       | `TourFeedback`       | An object containing the user's past feedback on tours.                                          | No       |
| `limit`          | `integer`            | The maximum number of recommendations to return. Default is `10`.                                | Yes      |

**`UserPreferences` Object:**

| Field         | Type     | Description                                                         |
| ------------- | -------- | ------------------------------------------------------------------- |
| `tour_type`   | `string` | The preferred tour type (`indoor`, `outdoor`, `both`).              |
| `category`    | `string` | The preferred tour category.                                        |
| `price_range` | `string` | The preferred price range.                                          |

**`TourFeedback` Object:**

| Field            | Type           | Description                                       |
| ---------------- | -------------- | ------------------------------------------------- |
| `liked_tours`    | `array[integer]` | A list of tour IDs the user has liked.          |
| `disliked_tours` | `array[integer]` | A list of tour IDs the user has disliked.       |

**Example Request (`curl`):**

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/recommendations/smart' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "lat": 40.7128,
  "lon": -74.0060,
  "preferences": {
    "tour_type": "outdoor",
    "category": "Adventure"
  },
  "limit": 5
}'
```

---

### Response (for both endpoints)

Both endpoints return a `SmartRecommendationResponse` object, which contains a list of recommended tours and the context that was used to generate them.

**`SmartRecommendationResponse` Object:**

| Field             | Type                    | Description                                                              |
| ----------------- | ----------------------- | ------------------------------------------------------------------------ |
| `recommendations` | `array[RecommendedTour]`| A list of recommended tours, each with a personalized reason.            |
| `context`         | `object`                | The context used for the recommendation (e.g., weather, time of day).    |

**`RecommendedTour` Object:**

This object includes all the fields of a standard `Tour` object, with one additional field:

| Field                 | Type     | Description                                             |
| --------------------- | -------- | ------------------------------------------------------- |
| `recommendation_reason`| `string` | A personalized explanation for why the tour is recommended. | 