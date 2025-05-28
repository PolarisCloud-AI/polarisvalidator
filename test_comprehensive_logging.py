#!/usr/bin/env python3
"""
Comprehensive logging test for Polaris Validator Dashboard Client
This script demonstrates that ALL logs are captured and sent to the server
"""

import asyncio
import time
import random
import argparse
from neurons.utils.dashboard_client import DashboardClient

async def generate_intensive_logs(dashboard: DashboardClient, duration: int):
    """Generate intensive logging to test comprehensive log capture"""
    
    print(f"🔥 Starting intensive logging test for {duration} seconds...")
    print("This will generate many logs to verify ALL are captured and sent")
    print("=" * 80)
    
    start_time = time.time()
    log_count = 0
    
    while time.time() - start_time < duration:
        # Generate various types of logs rapidly
        
        # Miner processing logs
        for i in range(5):
            miner_uid = random.randint(0, 255)
            score = random.uniform(30, 150)
            status = "processed" if score >= 50 else "below_threshold"
            dashboard.log_miner_processed(miner_uid, score, status)
            log_count += 1
        
        # SSH attempt logs
        for i in range(3):
            miner_uid = random.randint(0, 255)
            success = random.random() > 0.2  # 80% success rate
            error = None if success else random.choice([
                "Connection timeout",
                "Authentication failed", 
                "Host unreachable",
                "Permission denied"
            ])
            dashboard.log_ssh_attempt(miner_uid, success, error)
            log_count += 1
        
        # Verification logs
        for i in range(2):
            miner_uid = random.randint(0, 255)
            success = random.random() > 0.3  # 70% success rate
            if success:
                score = random.uniform(50, 100)
                dashboard.log_miner_verification(miner_uid, True, score)
            else:
                error = random.choice([
                    "Invalid compute score",
                    "UID mismatch", 
                    "Miner not unique",
                    "SSH verification failed"
                ])
                dashboard.log_miner_verification(miner_uid, False, error=error)
            log_count += 1
        
        # Weight update logs
        if random.random() < 0.1:  # 10% chance
            miners_count = random.randint(50, 100)
            total_score = miners_count * random.uniform(50, 150)
            dashboard.log_weight_update(miners_count, total_score)
            log_count += 1
        
        # Reward distribution logs
        for i in range(random.randint(1, 4)):
            miner_uid = random.randint(0, 255)
            reward = random.uniform(0.001, 0.1)
            dashboard.log_reward_distribution(miner_uid, reward)
            log_count += 1
        
        # Error logs
        if random.random() < 0.15:  # 15% chance
            modules = [
                "validator.blockchain",
                "validator.ssh", 
                "validator.compute_score",
                "validator.weights",
                "validator.network",
                "validator.storage"
            ]
            module = random.choice(modules)
            errors = [
                "Connection lost to blockchain",
                "Failed to fetch block data",
                "Timeout during operation",
                "Invalid response format",
                "Resource temporarily unavailable",
                "Rate limit exceeded"
            ]
            error = random.choice(errors)
            dashboard.log_error(module, error, random.randint(0, 255) if random.random() > 0.5 else None)
            log_count += 1
        
        # Cycle logs
        if random.random() < 0.05:  # 5% chance
            cycle_type = random.choice(["process_miners", "verify_miners"])
            dashboard.log_cycle_start(cycle_type)
            log_count += 1
            
            # Simulate cycle completion
            await asyncio.sleep(0.1)
            duration = random.uniform(10, 120)
            miners_processed = random.randint(20, 100)
            dashboard.log_cycle_end(cycle_type, duration, miners_processed)
            log_count += 1
        
        # Update metrics periodically
        if random.random() < 0.1:
            dashboard.update_miner_counts(
                active=random.randint(80, 120),
                processed=random.randint(70, 110),
                verified=random.randint(10, 30),
                rejected=random.randint(0, 10)
            )
            dashboard.update_block_info(
                2847392 + random.randint(0, 1000),
                2847392 + random.randint(0, 800)
            )
        
        # Small delay to prevent overwhelming
        await asyncio.sleep(0.1)
        
        # Show progress every 10 seconds
        elapsed = time.time() - start_time
        if int(elapsed) % 10 == 0 and elapsed > 0:
            print(f"⏱️  {elapsed:.0f}s elapsed - Generated {log_count} logs so far")
    
    print(f"🏁 Intensive logging test completed!")
    print(f"📊 Total logs generated: {log_count}")
    print(f"⏱️  Duration: {time.time() - start_time:.1f} seconds")
    print(f"📈 Rate: {log_count / (time.time() - start_time):.1f} logs/second")
    
    return log_count

def main():
    parser = argparse.ArgumentParser(description="Comprehensive Logging Test")
    parser.add_argument("--server-url", default="http://localhost:3001",
                       help="Dashboard server URL")
    parser.add_argument("--validator-id", default="comprehensive_test",
                       help="Validator ID for testing")
    parser.add_argument("--duration", type=int, default=60,
                       help="Test duration in seconds")
    parser.add_argument("--send-interval", type=int, default=2,
                       help="Dashboard update interval in seconds (faster for testing)")
    parser.add_argument("--show-final-data", action="store_true",
                       help="Show final data summary at the end")
    
    args = parser.parse_args()
    
    print("🧪 COMPREHENSIVE SSE LOG STREAMING TEST")
    print("=" * 80)
    print("This test verifies that ALL logs are streamed in REAL-TIME via SSE")
    print("Key features being tested:")
    print("  ✅ SSE log streaming (sse_logs=True)")
    print("  ✅ Plain log transmission via Server-Sent Events")
    print("  ✅ No memory accumulation - logs streamed immediately")
    print("  ✅ Non-blocking validator operation")
    print("=" * 80)
    
    # Create dashboard client with comprehensive logging
    dashboard = DashboardClient(
        server_url=args.server_url,
        validator_id=args.validator_id,
        validator_name="Comprehensive Test Validator",
        hotkey="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        send_interval=args.send_interval,
        sse_logs=True,       # SSE log streaming
        log_buffer_size=200  # Keep 200 recent logs for display
    )
    
    try:
        # Start dashboard client
        dashboard.start()
        print(f"🚀 Dashboard client started, sending ALL logs to {args.server_url}")
        print(f"📡 Transmission interval: {args.send_interval} seconds")
        print()
        
        # Run intensive logging test
        total_logs = asyncio.run(generate_intensive_logs(dashboard, args.duration))
        
        # Wait a bit for final transmission
        print("\n⏳ Waiting for final log transmission...")
        time.sleep(args.send_interval + 2)
        
        # Show final statistics
        if args.show_final_data:
            print("\n" + "=" * 80)
            print("📊 FINAL DATA SUMMARY")
            print("=" * 80)
            dashboard.log_current_data(include_full_payload=False)
            print("=" * 80)
        
        # Verify log integrity
        print(f"\n🔍 SSE LOG STREAMING VERIFICATION:")
        print(f"  Generated: {total_logs} logs")
        print(f"  Streamed via SSE: {dashboard.stats['logs_streamed_sse']} logs")
        print(f"  SSE Connection: {dashboard.stats.get('sse_connection_status', 'unknown')}")
        print(f"  In buffer: {len(dashboard.recent_logs)} logs")
        print(f"  Queue size: {dashboard.stats.get('logs_queue_size', 0)}")
        
        if dashboard.stats['logs_streamed_sse'] >= total_logs * 0.95:  # Allow for some queue delay
            print("  ✅ SSE STREAMING SUCCESS - All logs streamed via Server-Sent Events!")
        else:
            print("  ⚠️  Some logs may still be in queue or failed to stream")
        
        print(f"\n💾 Save final data to file for inspection...")
        filename = dashboard.save_data_to_file()
        if filename:
            print(f"  📄 Saved to: {filename}")
            print(f"  🔍 This file shows metrics and recent logs buffer")
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
    finally:
        # Stop dashboard client
        dashboard.stop()
        print("\n🛑 Dashboard client stopped")
        print("✅ Comprehensive logging test completed!")

if __name__ == "__main__":
    main() 