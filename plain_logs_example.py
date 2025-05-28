#!/usr/bin/env python3
"""
Example: How to integrate plain logs into your validator

This shows how to send actual log messages as they appear in your terminal
to the dashboard server as plain text.
"""

from neurons.utils.dashboard_client import DashboardClient
import time

def example_validator_with_plain_logs():
    """Example of how to use plain logs in your validator"""
    
    # Initialize dashboard client with plain logs enabled
    dashboard = DashboardClient(
        server_url="http://localhost:3001",
        validator_id="validator_example",
        validator_name="Example Validator",
        hotkey="your_hotkey_here",
        send_interval=5,
        sse_logs=False,  # Disable SSE since we're using plain logs
        send_plain_logs=True,  # Enable plain logs
        log_buffer_size=50
    )
    
    # Start the dashboard client
    dashboard.start()
    
    try:
        # Example validator loop
        while True:
            # Your existing validator code here...
            
            # When you want to send a plain log message to the dashboard:
            # Method 1: Send any log message directly
            dashboard.send_plain_log_message(
                "2025-05-28 11:43:56.452 | INFO | utils.api_utils:get_miner_details:366 - Looking up miner ABC123 in cache"
            )
            
            # Method 2: Capture and send actual loguru output
            # You can capture the formatted log message and send it
            log_message = "2025-05-28 11:43:56.453 | WARNING | validator.ssh:attempt:123 - SSH to miner 231 failed"
            dashboard.send_plain_log_message(log_message)
            
            # Method 3: Send any string that represents a log
            dashboard.send_plain_log_message(f"Processing miners at {time.strftime('%H:%M:%S')}")
            
            # Your validator continues...
            time.sleep(10)  # Example delay
            
    except KeyboardInterrupt:
        print("Stopping validator...")
    finally:
        # Stop the dashboard client
        dashboard.stop()

if __name__ == "__main__":
    print("📝 Plain Logs Integration Example")
    print("=" * 50)
    print("This example shows how to send plain log messages to your dashboard.")
    print("The logs will appear exactly as you send them, preserving the original format.")
    print("")
    print("To integrate into your validator:")
    print("1. Add dashboard client initialization")
    print("2. Call dashboard.send_plain_log_message(log_text) whenever you want to send a log")
    print("3. The log will be sent to your dashboard server immediately")
    print("")
    print("Press Ctrl+C to stop the example")
    print("=" * 50)
    
    example_validator_with_plain_logs() 