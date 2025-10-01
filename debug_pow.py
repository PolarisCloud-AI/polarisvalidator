#!/usr/bin/env python3
"""
Debug script to examine POW data structure
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'neurons'))

from utils.api_utils import _get_cached_miners_data

def main():
    data = _get_cached_miners_data()
    print(f"Total miners: {len(data)}")
    
    count_total = 0
    count_gt_1 = 0
    
    for i, miner in enumerate(data):
        miner_id = miner.get('miner_id', 'Unknown')
        miner_uid = miner.get('bittensor_details', {}).get('miner_uid', 'Unknown')
        resources = miner.get('resource_details', [])
        
        print(f"Miner {i}: {miner_id} has {len(resources)} resources")
        
        for j, resource in enumerate(resources):
            if resource is None:
                print(f"  Resource {j}: None - skipping")
                continue
                
            if not isinstance(resource, dict):
                print(f"  Resource {j}: non-dict type {type(resource)} - skipping")
                continue
                
            pow_data = resource.get('monitoring_status', {}).get('pow', {})
            if 'total' in pow_data and pow_data['total'] is not None:
                count_total += 1
                pow_score = pow_data['total']
                
                if pow_score > 1.0:
                    count_gt_1 += 1
                    print(f"    UID: {miner_uid} | Miner: {miner_id} | Resource: {resource.get('id', 'Unknown')} | POW: {pow_score:.4f}")
            
            if i >= 2 and j >= 2:  # Only check first few miners and resources
                break
        if i >= 2:
            break
    
    print(f"\nTotal resources with POW data: {count_total}")
    print(f"Resources with POW > 1.0: {count_gt_1}")

if __name__ == "__main__":
    main()
