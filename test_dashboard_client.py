#!/usr/bin/env python3
"""
Test script for the Polaris Validator Dashboard Client
This script demonstrates how to use the dashboard client to send validator data
"""

import asyncio
import time
import random
import argparse
from neurons.utils.dashboard_client import DashboardClient

async def simulate_validator_cycle(dashboard: DashboardClient):
    """Simulate a validator processing cycle"""
    
    # Simulate miner processing cycle
    dashboard.log_cycle_start("process_miners")
    
    # Simulate processing multiple miners
    miners_to_process = random.randint(50, 100)
    dashboard.update_miner_counts(active=miners_to_process)
    
    processed_count = 0
    verified_count = 0
    rejected_count = 0
    
    for i in range(miners_to_process):
        miner_uid = random.randint(0, 255)
        
        # Simulate SSH attempt
        ssh_success = random.random() > 0.1  # 90% success rate
        dashboard.log_ssh_attempt(miner_uid, ssh_success, 
                                 None if ssh_success else "Connection timeout")
        
        if ssh_success:
            # Simulate compute score calculation
            score = random.uniform(30, 150)
            status = "processed" if score >= 50 else "below_threshold"
            dashboard.log_miner_processed(miner_uid, score, status)
            
            if score >= 50:
                processed_count += 1
                
                # Simulate reward distribution
                reward = random.uniform(0.001, 0.1)
                dashboard.log_reward_distribution(miner_uid, reward)
        
        # Small delay to simulate processing time
        await asyncio.sleep(0.01)
    
    # Update final counts
    dashboard.update_miner_counts(processed=processed_count)
    
    # Simulate weight update
    if processed_count > 0:
        total_score = processed_count * random.uniform(50, 150)
        dashboard.log_weight_update(processed_count, total_score)
    
    # End cycle
    cycle_duration = random.uniform(30, 120)
    dashboard.log_cycle_end("process_miners", cycle_duration, processed_count)

async def simulate_verification_cycle(dashboard: DashboardClient):
    """Simulate a miner verification cycle"""
    
    dashboard.log_cycle_start("verify_miners")
    
    # Simulate verification of unverified miners
    miners_to_verify = random.randint(5, 20)
    verified_count = 0
    rejected_count = 0
    
    for i in range(miners_to_verify):
        miner_uid = random.randint(0, 255)
        
        # Simulate verification process
        verification_success = random.random() > 0.3  # 70% success rate
        
        if verification_success:
            score = random.uniform(50, 100)
            dashboard.log_miner_verification(miner_uid, True, score)
            verified_count += 1
        else:
            error_reasons = [
                "SSH connection failed",
                "Invalid compute score",
                "UID mismatch",
                "Miner not unique"
            ]
            error = random.choice(error_reasons)
            dashboard.log_miner_verification(miner_uid, False, error=error)
            rejected_count += 1
        
        await asyncio.sleep(0.05)
    
    dashboard.update_miner_counts(verified=verified_count, rejected=rejected_count)
    
    cycle_duration = random.uniform(10, 60)
    dashboard.log_cycle_end("verify_miners", cycle_duration, miners_to_verify)

async def simulate_validator_operations(dashboard: DashboardClient, duration: int):
    """Simulate validator operations for a specified duration"""
    
    print(f"Starting validator simulation for {duration} seconds...")
    start_time = time.time()
    cycle_count = 0
    
    while time.time() - start_time < duration:
        cycle_count += 1
        
        # Update block info
        current_block = 2847392 + cycle_count * 10
        last_weight_block = current_block - random.randint(50, 200)
        dashboard.update_block_info(current_block, last_weight_block)
        
        # Alternate between processing and verification cycles
        if cycle_count % 3 == 0:
            await simulate_verification_cycle(dashboard)
            await asyncio.sleep(random.uniform(5, 15))
        else:
            await simulate_validator_cycle(dashboard)
            await asyncio.sleep(random.uniform(10, 30))
        
        # Occasionally log errors
        if random.random() < 0.1:
            error_modules = [
                "validator.blockchain",
                "validator.ssh",
                "validator.compute_score",
                "validator.weights"
            ]
            module = random.choice(error_modules)
            error_msg = f"Simulated error in {module}"
            dashboard.log_error(module, error_msg)
    
    print(f"Simulation completed after {cycle_count} cycles")

def main():
    parser = argparse.ArgumentParser(description="Test Polaris Dashboard Client")
    parser.add_argument("--server-url", default="http://localhost:3001",
                       help="Dashboard server URL")
    parser.add_argument("--validator-id", default="test_validator",
                       help="Validator ID for testing")
    parser.add_argument("--validator-name", default="Test Polaris Validator",
                       help="Validator name for testing")
    parser.add_argument("--hotkey", default="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
                       help="Test hotkey")
    parser.add_argument("--duration", type=int, default=300,
                       help="Simulation duration in seconds")
    parser.add_argument("--send-interval", type=int, default=3,
                       help="Dashboard update interval in seconds")
    parser.add_argument("--log-data", action="store_true",
                       help="Log detailed data summary every 30 seconds")
    parser.add_argument("--save-data", action="store_true",
                       help="Save data payload to file at the end")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging (shows full JSON payloads)")
    
    args = parser.parse_args()
    
    # Set logging level based on debug flag
    if args.debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
        print("🐛 Debug logging enabled - full JSON payloads will be shown")
    
    # Create dashboard client
    dashboard = DashboardClient(
        server_url=args.server_url,
        validator_id=args.validator_id,
        validator_name=args.validator_name,
        hotkey=args.hotkey,
        send_interval=args.send_interval,
        sse_logs=True,       # Stream logs via SSE
        log_buffer_size=100  # Keep 100 recent logs for display
    )
    
    try:
        # Start dashboard client
        dashboard.start()
        print(f"Dashboard client started, sending data to {args.server_url}")
        
        # Show initial data summary if requested
        if args.log_data:
            print("\n" + "="*80)
            print("📊 INITIAL DATA SUMMARY")
            print("="*80)
            dashboard.log_current_data(include_full_payload=args.debug)
            print("="*80 + "\n")
        
        # Run simulation with periodic data logging
        if args.log_data:
            asyncio.run(simulate_validator_operations_with_logging(dashboard, args.duration))
        else:
            asyncio.run(simulate_validator_operations(dashboard, args.duration))
        
        # Save data to file if requested
        if args.save_data:
            filename = dashboard.save_data_to_file()
            if filename:
                print(f"\n💾 Final data payload saved to: {filename}")
        
        # Show final data summary
        if args.log_data:
            print("\n" + "="*80)
            print("📊 FINAL DATA SUMMARY")
            print("="*80)
            dashboard.log_current_data(include_full_payload=args.debug)
            print("="*80)
        
    except KeyboardInterrupt:
        print("\nSimulation interrupted by user")
    except Exception as e:
        print(f"Error during simulation: {e}")
    finally:
        # Stop dashboard client
        dashboard.stop()
        print("Dashboard client stopped")

async def simulate_validator_operations_with_logging(dashboard: DashboardClient, duration: int):
    """Simulate validator operations with periodic data logging"""
    
    print(f"Starting validator simulation for {duration} seconds with data logging...")
    start_time = time.time()
    cycle_count = 0
    last_log_time = start_time
    
    while time.time() - start_time < duration:
        cycle_count += 1
        
        # Update block info
        current_block = 2847392 + cycle_count * 10
        last_weight_block = current_block - random.randint(50, 200)
        dashboard.update_block_info(current_block, last_weight_block)
        
        # Alternate between processing and verification cycles
        if cycle_count % 3 == 0:
            await simulate_verification_cycle(dashboard)
            await asyncio.sleep(random.uniform(5, 15))
        else:
            await simulate_validator_cycle(dashboard)
            await asyncio.sleep(random.uniform(10, 30))
        
        # Log detailed data summary every 30 seconds
        current_time = time.time()
        if current_time - last_log_time >= 30:
            print("\n" + "="*80)
            print(f"📊 DATA SUMMARY - Cycle {cycle_count} ({current_time - start_time:.0f}s elapsed)")
            print("="*80)
            dashboard.log_current_data()
            print("="*80 + "\n")
            last_log_time = current_time
        
        # Occasionally log errors
        if random.random() < 0.1:
            error_modules = [
                "validator.blockchain",
                "validator.ssh",
                "validator.compute_score",
                "validator.weights"
            ]
            module = random.choice(error_modules)
            error_msg = f"Simulated error in {module}"
            dashboard.log_error(module, error_msg)
    
    print(f"Simulation completed after {cycle_count} cycles")

if __name__ == "__main__":
    main() 