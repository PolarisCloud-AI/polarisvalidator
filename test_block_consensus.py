#!/usr/bin/env python3
"""
Test Block-Based Consensus Mechanism for Penalty Detection

This test verifies that multiple validators analyzing the same blocks
will reach the same penalty decisions, creating natural consensus.
"""

import sys
sys.path.insert(0, '/Users/user/Documents/Jarvis/polarisvalidator/neurons')

from utils.alpha_overselling_detector import AlphaOverSellingDetector
import time

def simulate_validator(name, run_schedule, shared_blockchain_data):
    """
    Simulate a validator that runs at different times but sees same blockchain.
    
    Args:
        name: Validator name
        run_schedule: List of blocks when this validator runs
        shared_blockchain_data: The "blockchain" (same for all validators)
    """
    print(f"\n{'='*80}")
    print(f"🔷 VALIDATOR {name}")
    print(f"{'='*80}")
    print(f"Run schedule: {run_schedule}")
    
    detector = AlphaOverSellingDetector(netuid=49, network="finney")
    
    # Simulate validator running at different blocks
    for run_block in run_schedule:
        # Get blockchain state at this block
        metagraph_at_block = shared_blockchain_data[run_block]
        
        # Manually build history from snapshots up to this block
        for block, state in shared_blockchain_data.items():
            if block <= run_block:
                # Check if should snapshot at this block
                if detector._should_take_snapshot(block) or block == run_block:
                    for uid, stake_data in state.items():
                        if uid not in detector.stake_history:
                            detector.stake_history[uid] = []
                        
                        # Check if already have this block
                        if detector.stake_history[uid]:
                            if detector.stake_history[uid][-1]['block'] >= block:
                                continue
                        
                        detector.stake_history[uid].append({
                            'timestamp': time.time(),
                            'block': block,
                            'stake': stake_data['stake'],
                            'emission': stake_data['emission'],
                            'trust': 1.0
                        })
        
        # Analyze at this block
        print(f"\n  Analysis at block {run_block}:")
        
        for uid in [100, 200]:
            # Detect violations
            stake_analysis = detector._detect_stake_decrement(uid, run_block)
            
            if stake_analysis:
                is_new = detector._is_new_miner(uid, run_block)
                print(f"    UID {uid}:")
                print(f"      Snapshots used: {stake_analysis['data_points']}")
                print(f"      Block range: {stake_analysis['initial_block']} to {stake_analysis['final_block']}")
                print(f"      Blocks analyzed: {stake_analysis['blocks_analyzed']}")
                print(f"      Stake change: {stake_analysis['stake_change_percent']:.1f}%")
                print(f"      Is new miner: {is_new}")
                print(f"      Overselling detected: {stake_analysis['is_overselling']}")
    
    return detector

def test_block_consensus():
    """Test that different validators reach consensus using block-based analysis."""
    
    print("="*80)
    print("🧪 TESTING BLOCK-BASED CONSENSUS MECHANISM")
    print("="*80)
    
    # Simulate blockchain history (same for ALL validators)
    # Block: {uid: {stake, emission}}
    shared_blockchain = {
        1000: {100: {'stake': 10000, 'emission': 1.0}, 200: {'stake': 5000, 'emission': 0.5}},
        1720: {100: {'stake': 10000, 'emission': 1.0}, 200: {'stake': 5000, 'emission': 0.5}},
        2440: {100: {'stake': 9500, 'emission': 1.0}, 200: {'stake': 5000, 'emission': 0.5}},
        3160: {100: {'stake': 9000, 'emission': 1.0}, 200: {'stake': 4800, 'emission': 0.5}},
        3880: {100: {'stake': 8500, 'emission': 1.0}, 200: {'stake': 4600, 'emission': 0.5}},
        4600: {100: {'stake': 8000, 'emission': 1.0}, 200: {'stake': 4400, 'emission': 0.5}},
        5320: {100: {'stake': 7500, 'emission': 1.0}, 200: {'stake': 4200, 'emission': 0.5}},
        6040: {100: {'stake': 7000, 'emission': 1.0}, 200: {'stake': 4000, 'emission': 0.5}},
        6760: {100: {'stake': 6500, 'emission': 1.0}, 200: {'stake': 3800, 'emission': 0.5}},
        7480: {100: {'stake': 6000, 'emission': 1.0}, 200: {'stake': 3600, 'emission': 0.5}},
        8200: {100: {'stake': 5500, 'emission': 1.0}, 200: {'stake': 3400, 'emission': 0.5}},  # Current
    }
    
    print("\n📊 BLOCKCHAIN STATE (Same for all validators):")
    print(f"  UID 100: 10,000 → 5,500 TAO (45% drop over {8200-1000} blocks)")
    print(f"  UID 200: 5,000 → 3,400 TAO (32% drop over {8200-1000} blocks)")
    
    # Validator A: Runs frequently (every major block)
    validator_a = simulate_validator(
        "A (Frequent Runs)",
        run_schedule=[1000, 1720, 2440, 3160, 3880, 4600, 5320, 6040, 6760, 7480, 8200],
        shared_blockchain_data=shared_blockchain
    )
    
    # Validator B: Runs infrequently (only at start and end)
    validator_b = simulate_validator(
        "B (Infrequent Runs)",
        run_schedule=[1000, 8200],
        shared_blockchain_data=shared_blockchain
    )
    
    # Validator C: Missed early blocks, joins late
    validator_c = simulate_validator(
        "C (Late Starter)",
        run_schedule=[5320, 6040, 6760, 7480, 8200],
        shared_blockchain_data=shared_blockchain
    )
    
    # Now all validators analyze at block 8200
    print("\n" + "="*80)
    print("🎯 CONSENSUS CHECK AT BLOCK 8200")
    print("="*80)
    
    analysis_block = 8200
    
    results = {}
    for name, detector in [("Validator A", validator_a), 
                           ("Validator B", validator_b),
                           ("Validator C", validator_c)]:
        uid_100_analysis = detector._detect_stake_decrement(100, analysis_block)
        uid_200_analysis = detector._detect_stake_decrement(200, analysis_block)
        
        results[name] = {
            100: uid_100_analysis['is_overselling'] if uid_100_analysis else None,
            200: uid_200_analysis['is_overselling'] if uid_200_analysis else None
        }
        
        print(f"\n{name}:")
        if uid_100_analysis:
            print(f"  UID 100: Overselling={uid_100_analysis['is_overselling']}, "
                  f"Change={uid_100_analysis['stake_change_percent']:.1f}%, "
                  f"Blocks={uid_100_analysis['blocks_analyzed']}")
        if uid_200_analysis:
            print(f"  UID 200: Overselling={uid_200_analysis['is_overselling']}, "
                  f"Change={uid_200_analysis['stake_change_percent']:.1f}%, "
                  f"Blocks={uid_200_analysis['blocks_analyzed']}")
    
    # Verify consensus
    print("\n" + "="*80)
    print("✅ CONSENSUS VERIFICATION")
    print("="*80)
    
    # Check if all validators agree on UID 100
    uid_100_decisions = [r[100] for r in results.values() if r[100] is not None]
    uid_100_consensus = all(d == uid_100_decisions[0] for d in uid_100_decisions) if uid_100_decisions else False
    
    # Check if all validators agree on UID 200
    uid_200_decisions = [r[200] for r in results.values() if r[200] is not None]
    uid_200_consensus = all(d == uid_200_decisions[0] for d in uid_200_decisions) if uid_200_decisions else False
    
    print(f"\nUID 100 Consensus: {'✅ YES' if uid_100_consensus else '❌ NO'}")
    print(f"  Decisions: {uid_100_decisions}")
    
    print(f"\nUID 200 Consensus: {'✅ YES' if uid_200_consensus else '❌ NO'}")
    print(f"  Decisions: {uid_200_decisions}")
    
    if uid_100_consensus and uid_200_consensus:
        print("\n🎉 CONSENSUS ACHIEVED!")
        print("   All validators analyzing block 8200 reached the same conclusions!")
    else:
        print("\n⚠️  CONSENSUS FAILED - Validators disagree")
    
    print("\n" + "="*80)
    print("💡 KEY INSIGHT")
    print("="*80)
    print("""
Block-based consensus works because:
1. All validators see the SAME metagraph at block X
2. Snapshots taken at SAME block intervals (720, 1440, 2160, etc.)
3. Analysis uses SAME block ranges (e.g., blocks 1000-8200)
4. Same input data → Same analysis → Same penalties

Even though validators run at different times:
- Validator A runs every block
- Validator B runs only twice
- Validator C joins late

They ALL analyze blocks 1000-8200 and reach SAME conclusion!
""")

if __name__ == "__main__":
    test_block_consensus()
