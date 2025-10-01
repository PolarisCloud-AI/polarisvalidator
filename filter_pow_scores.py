#!/usr/bin/env python3
"""
Script to filter miners with POW scores > 1 and save them to a text file.
"""

import json
import sys
import os

# Add the neurons directory to Python path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'neurons'))

from utils.api_utils import _get_cached_miners_data

def filter_miners_by_pow_score():
    """Filter miners with POW scores > 1 and return formatted data."""
    
    try:
        # Get cached miners data
        miners_data = _get_cached_miners_data()
        
        if not miners_data:
            print("No miners data available")
            return []
        
        filtered_miners = []
        total_resources_with_pow = 0
        
        for i, miner in enumerate(miners_data):
            try:
                miner_id = miner.get('miner_id', 'Unknown')
                miner_uid = miner.get('bittensor_details', {}).get('miner_uid', 'Unknown')
                resources = miner.get('resource_details', [])
                
                print(f"Processing miner {i}: {miner_id} with {len(resources)} resources")
                
                for j, resource in enumerate(resources):
                    try:
                        if resource is None:
                            print(f"  Resource {j}: None - skipping")
                            continue
                            
                        if not isinstance(resource, dict):
                            print(f"  Resource {j}: non-dict type {type(resource)} - skipping")
                            continue
                            
                        monitoring_status = resource.get('monitoring_status', {})
                        pow_data = monitoring_status.get('pow', {})
                        
                        # Check if POW score exists and is > 1
                        if 'total' in pow_data and pow_data['total'] is not None:
                            total_resources_with_pow += 1
                            pow_score = pow_data['total']
                            
                            if pow_score > 1.0:
                                filtered_miners.append({
                                    'miner_id': miner_id,
                                    'miner_uid': miner_uid,
                                    'resource_id': resource.get('id', 'Unknown'),
                                    'pow_score': pow_score,
                                    'status': pow_data.get('status', 'Unknown'),
                                    'qualified': pow_data.get('qualified', False),
                                    'validation_status': resource.get('validation_status', 'Unknown'),
                                    'tier': pow_data.get('tier', 'Unknown'),
                                    'cpu_score': pow_data.get('cpu', 0),
                                    'gpu_score': pow_data.get('gpu', 0)
                                })
                    except Exception as e:
                        print(f"  Error processing resource {j}: {e}")
                        continue
                        
            except Exception as e:
                print(f"Error processing miner {i}: {e}")
                continue
        
        print(f"Total resources with POW data: {total_resources_with_pow}")
        print(f"Resources with POW > 1.0: {len(filtered_miners)}")
        
        return filtered_miners
        
    except Exception as e:
        print(f"Error getting miners data: {e}")
        return []

def save_to_text_file(miners_data, filename="miners_pow_gt_1.txt"):
    """Save filtered miners data to a text file."""
    
    try:
        with open(filename, 'w') as f:
            f.write("MINERS WITH POW SCORES > 1.0\n")
            f.write("=" * 50 + "\n\n")
            
            if not miners_data:
                f.write("No miners found with POW scores > 1.0\n")
                f.write("\nThis means all current resources have POW scores within acceptable limits.\n")
                return
            
            # Sort by POW score (highest first)
            miners_data.sort(key=lambda x: x['pow_score'], reverse=True)
            
            for miner in miners_data:
                f.write(f"UID: {miner['miner_uid']}\n")
                f.write(f"Miner ID: {miner['miner_id']}\n")
                f.write(f"Resource ID: {miner['resource_id']}\n")
                f.write(f"POW Score: {miner['pow_score']:.4f}\n")
                f.write(f"CPU Score: {miner['cpu_score']:.4f}\n")
                f.write(f"GPU Score: {miner['gpu_score']:.4f}\n")
                f.write(f"Status: {miner['status']}\n")
                f.write(f"Tier: {miner['tier']}\n")
                f.write(f"Qualified: {miner['qualified']}\n")
                f.write(f"Validation Status: {miner['validation_status']}\n")
                f.write("-" * 30 + "\n\n")
            
            f.write(f"\nTotal resources with POW > 1.0: {len(miners_data)}\n")
        
        print(f"Data saved to {filename}")
        return filename
        
    except Exception as e:
        print(f"Error saving to file: {e}")
        return None

def main():
    """Main function to execute the filtering and saving."""
    
    print("Filtering miners with POW scores > 1.0...")
    
    # Filter miners
    filtered_miners = filter_miners_by_pow_score()
    
    if not filtered_miners:
        print("No miners found with POW scores > 1.0")
        print("All current resources have POW scores within acceptable limits.")
        
        # Still save a report showing no violations found
        filename = save_to_text_file(filtered_miners)
        if filename:
            print(f"\nReport saved to: {filename}")
        return
    
    print(f"Found {len(filtered_miners)} resources with POW scores > 1.0")
    
    # Save to text file
    filename = save_to_text_file(filtered_miners)
    
    if filename:
        print(f"\nResults saved to: {filename}")
        
        # Also print summary to console
        print("\nSUMMARY:")
        print("=" * 50)
        for miner in filtered_miners:
            print(f"UID: {miner['miner_uid']} | Resource: {miner['resource_id']} | POW: {miner['pow_score']:.4f}")

if __name__ == "__main__":
    main()
