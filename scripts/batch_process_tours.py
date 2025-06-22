import time
import json
import os
import csv
from tqdm import tqdm
from clickhouse_driver import Client
from process_tour_data import process_tour_data

def batch_process_tours(ids_filepath):
    """
    Process multiple tours from a file, save to CSV, and bulk insert to ClickHouse.
    
    Args:
        ids_filepath: Path to a text file with tour group IDs (one per line).
    """
    try:
        with open(ids_filepath, 'r') as f:
            tour_ids = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: The file '{ids_filepath}' was not found.")
        return

    if not tour_ids:
        print(f"No tour IDs found in '{ids_filepath}'.")
        return

    print(f"Starting data extraction for {len(tour_ids)} tours from '{ids_filepath}'...")
    print("="*60)
    
    processing_start_time = time.time()
    successful_tours = 0
    failed_tours = 0
    total_cost = 0
    total_tokens = 0
    
    results = []
    successful_data = []
    
    for tour_id in tqdm(tour_ids, desc="Extracting Tour Data", leave=False):
        result = process_tour_data(tour_id, verbose=False, skip_db_insert=True)
        results.append(result)
        
        if result and result.get("success"):
            successful_tours += 1
            total_cost += result.get('cost', 0)
            total_tokens += result.get('tokens', 0)
            successful_data.append(result['data'])
            log_message = (
                f"✅ SUCCESS: Tour {result.get('tour_id')} | "
                f"Cost: ${result.get('cost', 0):.6f}"
            )
            tqdm.write(log_message)
        else:
            failed_tours += 1
            error_message = result.get('error', 'Unknown error')
            tqdm.write(f"❌ FAILED: Tour {tour_id} | Error: {error_message}")
            
    processing_time = time.time() - processing_start_time
    
    # Save to CSV and bulk insert
    csv_filepath = 'scripts/tours_to_upload.csv'
    bulk_insert_time = 0

    if successful_data:
        print(f"\nSaving {len(successful_data)} records to '{csv_filepath}'...")
        try:
            with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
                headers = successful_data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                writer.writerows(successful_data)
            print(f"✅ Successfully saved data to CSV.")
        except Exception as e:
            print(f"❌ Failed to save data to CSV: {e}")

        # Bulk insert to ClickHouse from memory
        print(f"\nStarting bulk insert of {len(successful_data)} records to ClickHouse...")
        bulk_insert_start = time.time()
        try:
            is_secure = True
            ch_client = Client(
                host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
                port=os.getenv('CLICKHOUSE_PORT', 9440 if is_secure else 9000),
                user=os.getenv('CLICKHOUSE_USER', 'default'),
                password=os.getenv('CLICKHOUSE_PASSWORD', ''),
                database=os.getenv('CLICKHOUSE_DB'),
                secure=True
            )
            ch_client.execute('INSERT INTO tour_info VALUES', successful_data)
            bulk_insert_time = time.time() - bulk_insert_start
            print(f"✅ Bulk insert completed in {bulk_insert_time:.2f} seconds.")
        except Exception as e:
            print(f"❌ Bulk insert failed: {e}")
            bulk_insert_time = 0
    else:
        print("\nNo successful tours to process for database insertion.")

    total_time = time.time() - processing_start_time
    
    # Print final summary
    print("\n" + "="*60)
    print("BATCH PROCESSING SUMMARY")
    print("="*60)
    print(f"Total tours attempted: {len(tour_ids)}")
    print(f"  - Successful: {successful_tours}")
    print(f"  - Failed:     {failed_tours}")
    
    print(f"\nExecution Time:")
    print(f"  - Data extraction: {processing_time:.2f} seconds")
    print(f"  - Bulk DB insert:  {bulk_insert_time:.2f} seconds")
    print(f"  - Total time:      {total_time:.2f} seconds")

    if successful_tours > 0:
      print(f"  - Average time per tour (extraction): {processing_time/successful_tours:.2f} seconds")
    
    print(f"\nTotal OpenAI Cost: ${total_cost:.4f}")
    if successful_tours > 0:
      print(f"  - Average cost per tour: ${total_cost/successful_tours:.4f}")

    summary_data = {
        "total_tours": len(tour_ids),
        "successful": successful_tours,
        "failed": failed_tours,
        "total_time_seconds": total_time,
        "processing_time_seconds": processing_time,
        "db_insert_time_seconds": bulk_insert_time,
        "total_cost_usd": total_cost,
        "results": results
    }
    
    results_filepath = 'scripts/batch_processing_results.json'
    with open(results_filepath, 'w') as f:
        json.dump(summary_data, f, indent=2, default=str)
    print(f"\nSummary saved to '{results_filepath}'")

    return summary_data

if __name__ == "__main__":
    ids_filepath = 'scripts/tour_ids.txt'
    batch_process_tours(ids_filepath) 