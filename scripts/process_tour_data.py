import os
import json
import requests
import openai
from flatten_json import flatten
import dotenv
from clickhouse_driver import Client
import time
import tiktoken

# Load environment variables from .env file
dotenv.load_dotenv()

def count_tokens(text):
    """Count tokens using tiktoken for GPT-4o"""
    try:
        encoding = tiktoken.encoding_for_model("gpt-4o")
        return len(encoding.encode(text))
    except:
        # Fallback: rough estimation (1 token ≈ 4 characters for English text)
        return len(text) // 4

def calculate_cost(input_tokens, output_tokens):
    """Calculate OpenAI API cost based on token usage"""
    # Current OpenAI GPT-4o pricing (as of 2024)
    INPUT_COST_PER_1M_TOKENS = 0.40  # USD
    OUTPUT_COST_PER_1M_TOKENS = 1.60  # USD
    
    input_cost = (input_tokens / 1_000_000) * INPUT_COST_PER_1M_TOKENS
    output_cost = (output_tokens / 1_000_000) * OUTPUT_COST_PER_1M_TOKENS
    total_cost = input_cost + output_cost
    
    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens
    }

def process_tour_data(tour_group_id, verbose=True, skip_db_insert=False):
    """
    Fetches tour data, flattens it, uses GPT to extract key information,
    and inserts the result into a ClickHouse database.
    """
    start_time = time.time()
    
    try:
        # 1. Fetch Tour Details
        if verbose:
            print("--- Fetching tour details from the API... ---")
        fetch_start = time.time()
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
        fetch_time = time.time() - fetch_start
        if verbose:
            print(f"API fetch completed in {fetch_time:.2f} seconds")

        # 2. Flatten the JSON response
        flatten_start = time.time()
        flattened_data = flatten(data)
        flatten_time = time.time() - flatten_start
        if verbose:
            print(f"Data flattening completed in {flatten_time:.2f} seconds")

        # 3. Use OpenAI to extract information
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY environment variable not set.")
            return

        client = openai.OpenAI(api_key=api_key)

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

        # Calculate input tokens before making the API call
        input_tokens = count_tokens(extraction_prompt)
        if verbose:
            print(f"Input tokens: {input_tokens:,}")

        if verbose:
            print("--- Sending request to OpenAI for data extraction... ---")
        openai_start = time.time()
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": extraction_prompt,
                }
            ],
            model="gpt-4o",
            response_format={"type": "json_object"},
        )

        response_content = chat_completion.choices[0].message.content
        extracted_info = json.loads(response_content)
        openai_time = time.time() - openai_start
        
        # Get output tokens from the response
        output_tokens = chat_completion.usage.completion_tokens
        
        # Calculate costs
        cost_info = calculate_cost(input_tokens, output_tokens)
        
        if verbose:
            print(f"OpenAI processing completed in {openai_time:.2f} seconds")
            print(f"Output tokens: {output_tokens:,}")
        
            print("\n--- Extracted Information ---")
            print(json.dumps(extracted_info, indent=4))

        db_time = 0
        if not skip_db_insert:
            # 4. Insert data into ClickHouse
            if verbose:
                print("\n--- Connecting to ClickHouse and inserting data... ---")
            db_start = time.time()
            
            is_secure = True

            ch_client = Client(
                host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
                port=os.getenv('CLICKHOUSE_PORT', 9440 if is_secure else 9000),
                user=os.getenv('CLICKHOUSE_USER', 'default'),
                password=os.getenv('CLICKHOUSE_PASSWORD', ''),
                database=os.getenv('CLICKHOUSE_DB'),
                secure=True
            )

            # Note: Assumes 'tour_info' table already exists with the correct schema.
            ch_client.execute('INSERT INTO tour_info VALUES', [extracted_info])
            
            db_time = time.time() - db_start
            if verbose:
                print(f"Database insertion completed in {db_time:.2f} seconds")
        
        # Calculate total execution time
        total_time = time.time() - start_time
        
        if verbose:
            print(f"\n--- Successfully inserted data for tour ID {extracted_info['id']} into ClickHouse ---")
        
            # Print detailed cost and timing breakdown
            print("\n" + "="*60)
            print("EXECUTION SUMMARY")
            print("="*60)
            print(f"Total execution time: {total_time:.2f} seconds")
            print(f"\nTiming Breakdown:")
            print(f"  API fetch: {fetch_time:.2f}s")
            print(f"  Data flattening: {flatten_time:.2f}s")
            print(f"  OpenAI processing: {openai_time:.2f}s")
            print(f"  Database insertion: {db_time:.2f}s")
            
            print(f"\nToken Usage:")
            print(f"  Input tokens: {input_tokens:,}")
            print(f"  Output tokens: {output_tokens:,}")
            print(f"  Total tokens: {cost_info['total_tokens']:,}")
            
            print(f"\nCost Breakdown:")
            print(f"  Input cost: ${cost_info['input_cost']:.6f}")
            print(f"  Output cost: ${cost_info['output_cost']:.6f}")
            print(f"  Total cost: ${cost_info['total_cost']:.6f}")
            
            # Estimate costs for different batch sizes
            print(f"\n" + "="*60)
            print("BATCH PROCESSING ESTIMATES")
            print("="*60)
            batch_sizes = [10, 100, 1000, 10000]
            for batch_size in batch_sizes:
                batch_cost = cost_info['total_cost'] * batch_size
                batch_time = total_time * batch_size
                print(f"  {batch_size:,} tours: ${batch_cost:.4f} | ~{batch_time/60:.1f} minutes")
        
        return {
            "success": True,
            "tour_id": extracted_info['id'],
            "execution_time": total_time,
            "cost": cost_info['total_cost'],
            "tokens": cost_info['total_tokens'],
            "data": extracted_info
        }

    except requests.exceptions.RequestException as e:
        print(f"An error occurred during the API request: {e}")
        return {"success": False, "error": str(e)}
    except openai.APIError as e:
        print(f"An OpenAI API error occurred: {e}")
        return {"success": False, "error": str(e)}
    except json.JSONDecodeError:
        print("Error: Failed to decode JSON from the API response.")
        return {"success": False, "error": "JSON decode error"}
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    tour_group_id = 21719
    result = process_tour_data(tour_group_id)
    
    if result and result.get("success"):
        print(f"\n" + "="*60)
        print("FINAL SUMMARY")
        print("="*60)
        print(f"✅ Successfully processed tour {result['tour_id']}")
        print(f"⏱️  Total time: {result['execution_time']:.2f} seconds")
        print(f"💰 Total cost: ${result['cost']:.6f}")
        print(f"🔤 Total tokens: {result['tokens']:,}")
    else:
        print(f"\n❌ Processing failed: {result.get('error', 'Unknown error')}") 