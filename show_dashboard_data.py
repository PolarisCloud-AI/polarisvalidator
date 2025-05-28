#!/usr/bin/env python3
"""
Simple script to show what data the dashboard client would send
This is useful for debugging and understanding the data format
"""

import argparse
from neurons.utils.dashboard_client import DashboardClient

def main():
    parser = argparse.ArgumentParser(description="Show Dashboard Data")
    parser.add_argument("--validator-id", default="sample_validator",
                       help="Validator ID")
    parser.add_argument("--validator-name", default="Sample Polaris Validator",
                       help="Validator name")
    parser.add_argument("--hotkey", default="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
                       help="Validator hotkey")
    parser.add_argument("--full-json", action="store_true",
                       help="Show full JSON payload")
    parser.add_argument("--save-file", type=str,
                       help="Save data to specified file")
    
    args = parser.parse_args()
    
    # Create dashboard client (don't start it)
    dashboard = DashboardClient(
        server_url="http://localhost:3001",  # Doesn't matter for this demo
        validator_id=args.validator_id,
        validator_name=args.validator_name,
        hotkey=args.hotkey,
        send_interval=5,
        sse_logs=True,       # Stream logs via SSE
        log_buffer_size=50   # Keep 50 recent logs for display
    )
    
    # Add some sample data to make it more interesting
    dashboard.update_miner_counts(active=85, processed=78, verified=12, rejected=3)
    dashboard.update_block_info(2847392, 2847300)
    dashboard.update_stats(
        total_miners_processed=1250,
        total_verifications=89,
        total_weight_updates=15,
        total_rewards_distributed=12345.67,
        ssh_attempts=1340,
        ssh_successes=1267
    )
    
    # Add some sample logs
    dashboard.log_miner_processed(42, 87.5, "processed")
    dashboard.log_miner_verification(23, True, 92.3)
    dashboard.log_ssh_attempt(15, True)
    dashboard.log_weight_update(78, 8750.25)
    dashboard.log_error("validator.ssh", "Connection timeout to miner 99", 99)
    
    print("🔍 Dashboard Data Preview")
    print("=" * 80)
    print("This shows the data that would be sent to the dashboard server")
    print("=" * 80)
    
    # Show the data summary
    dashboard.log_current_data(include_full_payload=args.full_json)
    
    # Save to file if requested
    if args.save_file:
        filename = dashboard.save_data_to_file(args.save_file)
        if filename:
            print(f"\n💾 Data saved to: {filename}")
            print("You can inspect this file to see the exact JSON structure")

if __name__ == "__main__":
    main() 