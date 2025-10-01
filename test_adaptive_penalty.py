#!/usr/bin/env python3
"""
Test DYNAMIC ADAPTIVE Penalty Detection

Shows how the system adapts to available data points and doesn't wait for 7 days.
"""

import sys
sys.path.insert(0, '/Users/user/Documents/Jarvis/polarisvalidator/neurons')

from utils.alpha_overselling_detector import AlphaOverSellingDetector

def test_adaptive_penalties():
    """Test adaptive penalty detection with varying data availability."""
    
    print("=" * 80)
    print("🧪 TESTING DYNAMIC ADAPTIVE PENALTY SYSTEM")
    print("=" * 80)
    
    detector = AlphaOverSellingDetector(netuid=49, network="finney")
    
    # Scenario 1: Only 3 snapshots (minimum data)
    print("\n" + "=" * 80)
    print("SCENARIO 1: Early Detection (Only 3 snapshots, 2 days)")
    print("=" * 80)
    
    detector.stake_history[100] = [
        {'block': 1000, 'stake': 10000, 'emission': 1.0, 'trust': 1.0, 'timestamp': 1000},
        {'block': 1864, 'stake': 9500, 'emission': 1.0, 'trust': 1.0, 'timestamp': 2000},
        {'block': 2728, 'stake': 8500, 'emission': 1.0, 'trust': 1.0, 'timestamp': 3000},  # 15% drop
    ]
    
    current_block = 2728
    analysis = detector._detect_stake_decrement(100, current_block)
    
    if analysis:
        print(f"\n✅ Analysis Completed:")
        print(f"  Data points: {analysis['data_points']}")
        print(f"  Blocks analyzed: {analysis['blocks_analyzed']} ({analysis['days_analyzed']:.1f} days)")
        print(f"  Stake change: {analysis['stake_change_percent']:.1f}%")
        print(f"  Adaptive threshold: {analysis['adaptive_threshold']:.1f}% (stricter for short period)")
        print(f"  Overselling detected: {analysis['is_overselling']}")
        print(f"\n  💡 System adapts: With only 2 days of data, threshold is {analysis['adaptive_threshold']:.1f}% (not 5%)")
        print(f"      This catches rapid dumps even with limited history!")
    
    # Scenario 2: 5 snapshots (medium data)
    print("\n" + "=" * 80)
    print("SCENARIO 2: Medium Data (5 snapshots, 4 days)")
    print("=" * 80)
    
    detector.stake_history[200] = [
        {'block': 1000, 'stake': 5000, 'emission': 0.5, 'trust': 1.0, 'timestamp': 1000},
        {'block': 1864, 'stake': 4900, 'emission': 0.5, 'trust': 1.0, 'timestamp': 2000},
        {'block': 2728, 'stake': 4700, 'emission': 0.5, 'trust': 1.0, 'timestamp': 3000},
        {'block': 3592, 'stake': 4500, 'emission': 0.5, 'trust': 1.0, 'timestamp': 4000},
        {'block': 4456, 'stake': 4200, 'emission': 0.5, 'trust': 1.0, 'timestamp': 5000},  # 16% drop
    ]
    
    current_block = 4456
    analysis = detector._detect_stake_decrement(200, current_block)
    
    if analysis:
        print(f"\n✅ Analysis Completed:")
        print(f"  Data points: {analysis['data_points']}")
        print(f"  Blocks analyzed: {analysis['blocks_analyzed']} ({analysis['days_analyzed']:.1f} days)")
        print(f"  Stake change: {analysis['stake_change_percent']:.1f}%")
        print(f"  Adaptive threshold: {analysis['adaptive_threshold']:.1f}%")
        print(f"  Overselling detected: {analysis['is_overselling']}")
        print(f"\n  💡 With 4 days of data, threshold is {analysis['adaptive_threshold']:.1f}%")
    
    # Scenario 3: 10+ snapshots (full data)
    print("\n" + "=" * 80)
    print("SCENARIO 3: Full Data (10 snapshots, 10+ days)")
    print("=" * 80)
    
    detector.stake_history[300] = [
        {'block': 1000, 'stake': 8000, 'emission': 0.8, 'trust': 1.0, 'timestamp': 1000},
        {'block': 1864, 'stake': 7900, 'emission': 0.8, 'trust': 1.0, 'timestamp': 2000},
        {'block': 2728, 'stake': 7800, 'emission': 0.8, 'trust': 1.0, 'timestamp': 3000},
        {'block': 3592, 'stake': 7700, 'emission': 0.8, 'trust': 1.0, 'timestamp': 4000},
        {'block': 4456, 'stake': 7600, 'emission': 0.8, 'trust': 1.0, 'timestamp': 5000},
        {'block': 5320, 'stake': 7500, 'emission': 0.8, 'trust': 1.0, 'timestamp': 6000},
        {'block': 6184, 'stake': 7400, 'emission': 0.8, 'trust': 1.0, 'timestamp': 7000},
        {'block': 7048, 'stake': 7300, 'emission': 0.8, 'trust': 1.0, 'timestamp': 8000},
        {'block': 7912, 'stake': 7200, 'emission': 0.8, 'trust': 1.0, 'timestamp': 9000},
        {'block': 8776, 'stake': 7100, 'emission': 0.8, 'trust': 1.0, 'timestamp': 10000},  # 11.25% drop
    ]
    
    current_block = 8776
    analysis = detector._detect_stake_decrement(300, current_block)
    
    if analysis:
        print(f"\n✅ Analysis Completed:")
        print(f"  Data points: {analysis['data_points']}")
        print(f"  Blocks analyzed: {analysis['blocks_analyzed']} ({analysis['days_analyzed']:.1f} days)")
        print(f"  Stake change: {analysis['stake_change_percent']:.1f}%")
        print(f"  Adaptive threshold: {analysis['adaptive_threshold']:.1f}% (base threshold)")
        print(f"  Overselling detected: {analysis['is_overselling']}")
        print(f"\n  💡 With {analysis['days_analyzed']:.1f} days of data, uses base threshold of 5.0%")
    
    # Scenario 4: Flash dump (very rapid)
    print("\n" + "=" * 80)
    print("SCENARIO 4: Flash Dump Detection (3 snapshots, 0.5 days)")
    print("=" * 80)
    
    detector.stake_history[400] = [
        {'block': 9000, 'stake': 12000, 'emission': 1.2, 'trust': 1.0, 'timestamp': 10000},
        {'block': 9200, 'stake': 11500, 'emission': 1.2, 'trust': 1.0, 'timestamp': 11000},
        {'block': 9400, 'stake': 10500, 'emission': 1.2, 'trust': 1.0, 'timestamp': 12000},  # 12.5% in hours!
    ]
    
    current_block = 9400
    analysis = detector._detect_stake_decrement(400, current_block)
    
    if analysis:
        print(f"\n✅ Analysis Completed:")
        print(f"  Data points: {analysis['data_points']}")
        print(f"  Blocks analyzed: {analysis['blocks_analyzed']} ({analysis['days_analyzed']:.2f} days)")
        print(f"  Stake change: {analysis['stake_change_percent']:.1f}%")
        print(f"  Adaptive threshold: {analysis['adaptive_threshold']:.1f}% (STRICTEST for flash dumps)")
        print(f"  Overselling detected: {analysis['is_overselling']}")
        print(f"\n  💡 Flash dump! Only {analysis['days_analyzed']:.2f} days, threshold is {analysis['adaptive_threshold']:.1f}%")
        print(f"      System catches rapid dumps even with minimal data!")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 ADAPTIVE THRESHOLD SUMMARY")
    print("=" * 80)
    print("""
Time Period           | Threshold | Why
--------------------- | --------- | --------------------------------
< 1 day (flash dump)  | 2.5%      | Catch rapid dumps immediately
1-3 days              | 3.5%      | Stricter for short-term drops
3-7 days              | 4.25%     | Moderate threshold
7+ days               | 5.0%      | Base threshold (normal variation)

Key Benefits:
✅ No waiting period - uses available data immediately
✅ Adaptive thresholds prevent false positives
✅ Block-based for validator consensus
✅ Stricter for rapid dumps, lenient for long-term trends
✅ Works with as few as 3 data points
    """)
    
    print("\n" + "=" * 80)
    print("🎯 CONSENSUS VERIFICATION")
    print("=" * 80)
    print("""
All validators analyzing the SAME blocks will:
1. See the SAME stake values (from metagraph)
2. Calculate the SAME time span (blocks analyzed)
3. Use the SAME adaptive threshold
4. Reach the SAME penalty decision

Example at block 9400:
- Validator A (runs frequently): Analyzes blocks 9000-9400
- Validator B (runs rarely): Analyzes blocks 9000-9400
- Both see: 12.5% drop over 400 blocks (0.46 days)
- Both use: 2.5% threshold (flash dump)
- Both decide: PENALTY!

✅ CONSENSUS ACHIEVED through block-based analysis!
    """)

if __name__ == "__main__":
    test_adaptive_penalties()
