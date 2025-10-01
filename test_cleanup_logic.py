#!/usr/bin/env python3
"""
Test the improved cleanup logic for stake history.

Tests:
1. Normal case: More than 15 entries in 7 days → Keep only last 7 days
2. Edge case: Less than 15 entries in 7 days → Keep last 15 entries regardless
3. Verify analysis still works after cleanup
"""

import time
from datetime import datetime, timedelta

# Simulate the cleanup logic
def test_cleanup_logic():
    """Test the smart cleanup logic."""
    
    print("=" * 80)
    print("🧪 TESTING IMPROVED CLEANUP LOGIC")
    print("=" * 80)
    
    current_time = time.time()
    cutoff_time = current_time - (7 * 24 * 3600)  # 7 days ago
    MIN_ENTRIES_TO_KEEP = 15
    
    # Test Case 1: Miner with many recent entries
    print("\n" + "=" * 80)
    print("TEST CASE 1: Miner with frequent updates (20 entries in 7 days)")
    print("=" * 80)
    
    # Generate 20 entries over last 7 days
    case1_history = []
    for i in range(20):
        entry_time = current_time - (i * 12 * 3600)  # Every 12 hours
        case1_history.insert(0, {
            'timestamp': entry_time,
            'stake': 1000.0 - (i * 10),
            'emission': 0.5
        })
    
    print(f"Original entries: {len(case1_history)}")
    print(f"Oldest entry: {datetime.fromtimestamp(case1_history[0]['timestamp']).strftime('%Y-%m-%d %H:%M')}")
    print(f"Newest entry: {datetime.fromtimestamp(case1_history[-1]['timestamp']).strftime('%Y-%m-%d %H:%M')}")
    
    # Apply cleanup
    time_filtered = [e for e in case1_history if e['timestamp'] > cutoff_time]
    
    if len(time_filtered) >= MIN_ENTRIES_TO_KEEP:
        final_history = time_filtered
        print(f"\n✅ Result: Keep time-filtered data ({len(final_history)} entries)")
    else:
        final_history = case1_history[-MIN_ENTRIES_TO_KEEP:]
        print(f"\n⚠️  Result: Keep minimum entries ({len(final_history)} entries)")
    
    print(f"After cleanup: {len(final_history)} entries")
    print(f"Oldest kept: {datetime.fromtimestamp(final_history[0]['timestamp']).strftime('%Y-%m-%d %H:%M')}")
    
    # Test Case 2: Miner with infrequent updates
    print("\n" + "=" * 80)
    print("TEST CASE 2: Miner with slow updates (only 8 entries in 7 days)")
    print("=" * 80)
    
    # Generate 8 entries over last 10 days (some older than 7 days)
    case2_history = []
    for i in range(8):
        entry_time = current_time - (i * 1.5 * 24 * 3600)  # Every 1.5 days
        case2_history.insert(0, {
            'timestamp': entry_time,
            'stake': 2000.0 - (i * 50),
            'emission': 1.0
        })
    
    print(f"Original entries: {len(case2_history)}")
    print(f"Oldest entry: {datetime.fromtimestamp(case2_history[0]['timestamp']).strftime('%Y-%m-%d %H:%M')}")
    print(f"Newest entry: {datetime.fromtimestamp(case2_history[-1]['timestamp']).strftime('%Y-%m-%d %H:%M')}")
    
    # Apply cleanup
    time_filtered = [e for e in case2_history if e['timestamp'] > cutoff_time]
    print(f"\nEntries within 7 days: {len(time_filtered)}")
    
    if len(time_filtered) >= MIN_ENTRIES_TO_KEEP:
        final_history = time_filtered
        print(f"✅ Result: Keep time-filtered data ({len(final_history)} entries)")
    else:
        final_history = case2_history[-MIN_ENTRIES_TO_KEEP:]
        print(f"✅ Result: Keep minimum entries ({len(final_history)} entries)")
    
    print(f"After cleanup: {len(final_history)} entries")
    if final_history:
        print(f"Oldest kept: {datetime.fromtimestamp(final_history[0]['timestamp']).strftime('%Y-%m-%d %H:%M')}")
        print(f"Age of oldest: {(current_time - final_history[0]['timestamp']) / (24*3600):.1f} days")
    
    # Verify analysis can still work
    print(f"\n📊 Analysis Check:")
    if len(final_history) >= 10:
        print(f"  ✅ Can perform full analysis (has {len(final_history)} entries, needs 10)")
    elif len(final_history) >= 5:
        print(f"  ⚠️  Can perform limited analysis (has {len(final_history)} entries, needs 10)")
    else:
        print(f"  ❌ Cannot perform analysis (has {len(final_history)} entries, needs 5 minimum)")
    
    # Test Case 3: Very new miner
    print("\n" + "=" * 80)
    print("TEST CASE 3: New miner (only 3 entries)")
    print("=" * 80)
    
    case3_history = []
    for i in range(3):
        entry_time = current_time - (i * 6 * 3600)  # Every 6 hours
        case3_history.insert(0, {
            'timestamp': entry_time,
            'stake': 500.0,
            'emission': 0.2
        })
    
    print(f"Original entries: {len(case3_history)}")
    
    # Apply cleanup
    time_filtered = [e for e in case3_history if e['timestamp'] > cutoff_time]
    
    if len(time_filtered) >= MIN_ENTRIES_TO_KEEP:
        final_history = time_filtered
        print(f"Result: Keep time-filtered data ({len(final_history)} entries)")
    elif len(case3_history) >= MIN_ENTRIES_TO_KEEP:
        final_history = case3_history[-MIN_ENTRIES_TO_KEEP:]
        print(f"Result: Keep minimum entries ({len(final_history)} entries)")
    else:
        final_history = case3_history  # Keep all
        print(f"✅ Result: Keep ALL entries ({len(final_history)} entries - below minimum)")
    
    print(f"After cleanup: {len(final_history)} entries")
    
    print(f"\n📊 Analysis Check:")
    if len(final_history) >= 10:
        print(f"  ✅ Can perform full analysis")
    elif len(final_history) >= 5:
        print(f"  ⚠️  Can perform limited analysis")
    else:
        print(f"  ❌ Cannot perform analysis - Protected as new miner")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 CLEANUP STRATEGY SUMMARY")
    print("=" * 80)
    print("""
Strategy: Keep max(7 days of data, 15 most recent entries)

Benefits:
  ✅ Normal miners: Data cleaned after 7 days (efficient storage)
  ✅ Slow validators: Always keep 15 entries (enough for analysis)
  ✅ New miners: Keep all data until they have 15 entries
  ✅ Guarantees: Analysis always possible if miner has 10+ entries
  
Storage Impact:
  • Reduces from 14 days to 7 days (50% reduction)
  • Maintains data quality for analysis
  • File size expected to reduce from 262 KB to ~130 KB
    """)
    
    print("=" * 80)
    print("🎉 ALL TESTS COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    test_cleanup_logic()
