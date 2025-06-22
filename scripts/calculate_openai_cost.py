import json
import tiktoken
import requests
from flatten_json import flatten

def count_tokens(text):
    """Count tokens using tiktoken for GPT-4o"""
    try:
        encoding = tiktoken.encoding_for_model("gpt-4o")
        return len(encoding.encode(text))
    except:
        # Fallback: rough estimation (1 token ≈ 4 characters for English text)
        return len(text) // 4

def estimate_openai_cost(tour_group_id, num_tours=1):
    """
    Estimate the cost of running the OpenAI API for processing tour data
    
    Args:
        tour_group_id: The tour group ID to process
        num_tours: Number of tours to process (for batch estimation)
    """
    
    # Current OpenAI GPT-4o pricing (as of 2024)
    # Input: $5.00 per 1M tokens
    # Output: $15.00 per 1M tokens
    INPUT_COST_PER_1M_TOKENS = 0.40  # USD
    OUTPUT_COST_PER_1M_TOKENS = 1.60  # USD
    
    try:
        # 1. Fetch sample tour data to estimate token usage
        print(f"Fetching sample data for tour group {tour_group_id}...")
        url = f'https://api-ho.headout.com/api/v6/tour-groups/{tour_group_id}/?&language=en&&currency=USD'
        headers = {
            'accept': '*/*',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'cache-control': 'no-cache',
            'origin': 'https://www.headout.com',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'x-forwarded-country-code': 'IN',
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # 2. Flatten the JSON response
        flattened_data = flatten(data)
        
        # 3. Create the extraction prompt (same as in the original script)
        extraction_prompt = f"""
        Based on the following flattened JSON data for a tour group and your general knowledge,
        please extract the required information. If a piece of information is not available
        in the JSON, use your knowledge about the tour (e.g., "Burj Khalifa") to infer the answer.

        JSON Data:
        {json.dumps(flattened_data, indent=2)}

        Please extract the following fields and return the response as a valid JSON object.
        Do not include any text outside of the JSON response.

        - "lat": Latitude of the start location.
        - "long": Longitude of the start location.
        - "id": The ID of the tour.
        - "name": The name of the tour.
        - "time_of_day_trip_type": An array of suitable times of day. Options: ["morning", "afternoon", "evening", "night"].
        - "tour_type": The type of tour. Options: ["indoor", "outdoor", "both"].
        - "season": Best season(s) to visit. Options: ["Summer", "Winter", "Christmas", "Rainy"].
        - "group_type_suitability": An array of suitable group types. Options: ["solo", "family", "couples"].
        - "pricing_range_usd": A string representing the price range in USD (e.g., "0 - 50 USD" , "50 - 100 USD", "100 - 200 USD", "200 - 500 USD", "500+ USD").
        - "category_name": The primary category of the tour.
        - "subcategory_name": The primary sub-category of the tour.

        Example JSON output format:
        {{
            "lat": 25.1972,
            "long": 55.2744,
            "id": 1866,
            "name": "Burj Khalifa 'At the Top' Tickets: Level 124 & 125",
            "time_of_day_trip_type": ["afternoon", "evening"],
            "tour_type": "indoor",
            "season": ["Summer", "Winter"],
            "group_type_suitability": ["solo", "family", "couples"],
            "pricing_range_usd": "50-100 USD",
            "category_name": "Attractions",
            "subcategory_name": "Observation Decks"
        }}
        """
        
        # 4. Count tokens for input (prompt)
        input_tokens = count_tokens(extraction_prompt)
        
        # 5. Estimate output tokens (typical JSON response)
        estimated_output_json = {
            "lat": 25.1972,
            "long": 55.2744,
            "id": 1866,
            "name": "Burj Khalifa 'At the Top' Tickets: Level 124 & 125",
            "time_of_day_trip_type": ["afternoon", "evening"],
            "tour_type": "indoor",
            "season": ["Summer", "Winter"],
            "group_type_suitability": ["solo", "family", "couples"],
            "pricing_range_usd": "50-100 USD",
            "category_name": "Attractions",
            "subcategory_name": "Observation Decks"
        }
        output_tokens = count_tokens(json.dumps(estimated_output_json, indent=2))
        
        # 6. Calculate costs
        input_cost = (input_tokens / 1_000_000) * INPUT_COST_PER_1M_TOKENS
        output_cost = (output_tokens / 1_000_000) * OUTPUT_COST_PER_1M_TOKENS
        total_cost_per_tour = input_cost + output_cost
        
        # 7. Calculate total cost for all tours
        total_cost = total_cost_per_tour * num_tours
        
        # 8. Print detailed breakdown
        print("\n" + "="*60)
        print("OpenAI API Cost Estimation")
        print("="*60)
        print(f"Model: GPT-4o")
        print(f"Number of tours to process: {num_tours}")
        print(f"\nToken Usage per tour:")
        print(f"  Input tokens: {input_tokens:,}")
        print(f"  Output tokens: {output_tokens:,}")
        print(f"  Total tokens: {input_tokens + output_tokens:,}")
        
        print(f"\nCost per tour:")
        print(f"  Input cost: ${input_cost:.6f}")
        print(f"  Output cost: ${output_cost:.6f}")
        print(f"  Total cost per tour: ${total_cost_per_tour:.6f}")
        
        print(f"\nTotal cost for {num_tours} tour(s): ${total_cost:.6f}")
        
        # 9. Provide cost estimates for different batch sizes
        print(f"\n" + "="*60)
        print("Cost Estimates for Different Batch Sizes")
        print("="*60)
        
        batch_sizes = [1, 10, 100, 1000, 10000]
        for batch_size in batch_sizes:
            batch_cost = total_cost_per_tour * batch_size
            print(f"  {batch_size:,} tours: ${batch_cost:.4f}")
        
        # 10. Monthly cost estimate (assuming 30 days)
        daily_cost = total_cost_per_tour * num_tours
        monthly_cost = daily_cost * 30
        print(f"\nMonthly cost (30 days): ${monthly_cost:.4f}")
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_per_tour": total_cost_per_tour,
            "total_cost": total_cost,
            "monthly_cost": monthly_cost
        }
        
    except Exception as e:
        print(f"Error calculating costs: {e}")
        return None

if __name__ == "__main__":
    # Calculate cost for the current tour (ID: 1866)
    tour_group_id = 1866
    
    # You can change this to estimate costs for different numbers of tours
    num_tours = 1
    
    result = estimate_openai_cost(tour_group_id, num_tours)
    
    if result:
        print(f"\n" + "="*60)
        print("Summary")
        print("="*60)
        print(f"Processing {num_tours} tour(s) will cost approximately ${result['total_cost']:.6f}")
        print(f"Each tour costs approximately ${result['cost_per_tour']:.6f}") 