#!/usr/bin/env python3
"""
Polaris Validator Dashboard Client Example
==========================================

This script demonstrates how to connect your Polaris validator to the 
real-time log streaming dashboard server.

Features:
- Real-time log streaming
- Automatic reconnection
- Metrics reporting
- Error handling
- Multiple integration patterns

Usage:
    python validator_client_example.py

Requirements:
    pip install requests psutil
"""

import requests
import json
import time
import threading
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional
import queue
import signal

# Import the dashboard client
from neurons.utils.dashboard_client import DashboardClient

def example_basic_usage():
    """Example 1: Basic synchronous usage"""
    print("\n🔹 Example 1: Basic Synchronous Usage")
    print("-" * 50)
    
    # Initialize client
    client = DashboardClient("validator_example_1")
    
    # Test connection
    if not client.test_connection():
        print("❌ Cannot connect to server. Make sure it's running on port 3001")
        return
    
    # Send some logs
    client.log_info("utils.validator_utils:process_miners", "Processing 256 miners in current cycle")
    client.log_warning("utils.compute_score:parse_cpu_specs", "Error parsing CPU specs for miner abc123")
    client.log_error("utils.uptimedata:save_payment_log", "Failed to save payment log: disk full")
    
    # Send metrics
    client.send_validator_metrics(
        uptime=98.5,
        memory_usage=85.2,
        cpu_usage=45.8,
        active_miners=256,
        ssh_success_rate=100.0,
        current_block=5655713
    )
    
    print("✅ Basic example completed")


def example_async_usage():
    """Example 2: Asynchronous usage with background threads"""
    print("\n🔹 Example 2: Asynchronous Usage")
    print("-" * 50)
    
    # Initialize client
    client = DashboardClient("validator_example_2")
    
    # Test connection
    if not client.test_connection():
        print("❌ Cannot connect to server. Make sure it's running on port 3001")
        return
    
    # Start async mode
    client.start_async_mode()
    
    try:
        # Simulate validator operations
        for i in range(10):
            # Log some operations
            client.log_info("utils.validator_utils:process_miners", f"Processing batch {i+1}/10")
            
            if i % 3 == 0:
                client.log_warning("utils.api_utils:get_miner_details", f"Slow response for miner batch {i+1}")
            
            # Send metrics every 5 iterations
            if i % 5 == 0:
                client.send_validator_metrics(
                    uptime=98.0 + (i * 0.1),
                    memory_usage=80.0 + (i * 2),
                    cpu_usage=40.0 + (i * 3),
                    active_miners=250 + i,
                    ssh_success_rate=99.0 + (i * 0.1)
                )
            
            time.sleep(0.5)  # Simulate work
        
        print("✅ Async example completed")
        
    finally:
        # Always stop async mode
        client.stop_async_mode()
        client.print_stats()


def example_raw_log_streaming():
    """Example 3: Stream raw log lines"""
    print("\n🔹 Example 3: Raw Log Streaming")
    print("-" * 50)
    
    # Create sample raw log lines
    sample_logs = [
        "2025-05-28 11:43:56.452 | INFO     | utils.api_utils:get_miner_details:366 - Looking up miner abc123",
        "2025-05-28 11:43:56.453 | INFO     | utils.api_utils:get_miner_details:374 - Found miner abc123 in cache",
        "2025-05-28 11:43:56.454 | WARNING  | utils.compute_score:parse_cpu_specs:123 - Error parsing CPU specs",
        "2025-05-28 11:43:56.455 | ERROR    | utils.uptimedata:save_payment_log:89 - Error saving payment log",
        "2025-05-28 11:43:56.456 | INFO     | utils.validator_utils:update_weights:78 - Weight update completed"
    ]
    
    # Initialize client
    client = DashboardClient("validator_example_3")
    
    # Test connection
    if not client.test_connection():
        print("❌ Cannot connect to server. Make sure it's running on port 3001")
        return
    
    # Stream raw logs
    print(f"📁 Streaming raw logs")
    
    for line_num, line in enumerate(sample_logs, 1):
        success = client.send_raw_log(line)
        if success:
            print(f"✅ Line {line_num}: {line[:80]}...")
        else:
            print(f"❌ Line {line_num}: Failed to send")
        
        time.sleep(0.2)  # Small delay between lines
    
    print("✅ Raw log streaming completed")
    client.print_stats()


def example_integration_with_existing_logger():
    """Example 4: Integration with existing Python logger"""
    print("\n🔹 Example 4: Integration with Existing Logger")
    print("-" * 50)
    
    # Custom log handler that sends to dashboard
    class DashboardLogHandler(logging.Handler):
        def __init__(self, dashboard_client):
            super().__init__()
            self.client = dashboard_client
        
        def emit(self, record):
            # Format the log record
            timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            level = record.levelname
            module = f"{record.module}:{record.funcName}:{record.lineno}"
            message = record.getMessage()
            
            # Create log line in expected format
            log_line = f"{timestamp} | {level:<8} | {module} - {message}"
            
            # Send to dashboard
            self.client.send_raw_log(log_line)
    
    # Initialize client
    client = DashboardClient("validator_example_4")
    
    # Test connection
    if not client.test_connection():
        print("❌ Cannot connect to server. Make sure it's running on port 3001")
        return
    
    # Start async mode
    client.start_async_mode()
    
    try:
        # Setup Python logger with dashboard handler
        logger = logging.getLogger('validator_operations')
        logger.setLevel(logging.DEBUG)
        
        # Add dashboard handler
        dashboard_handler = DashboardLogHandler(client)
        logger.addHandler(dashboard_handler)
        
        # Use regular Python logging - it will automatically go to dashboard
        logger.info("Validator started successfully")
        logger.info("Loading miner data from cache")
        logger.warning("High memory usage detected: 85%")
        logger.error("Failed to connect to miner abc123")
        logger.debug("Processing miner verification batch")
        
        print("✅ Logger integration example completed")
        
    finally:
        client.stop_async_mode()
        client.print_stats()


def example_validator_events():
    """Example 5: Using validator-specific event methods"""
    print("\n🔹 Example 5: Validator Event Methods")
    print("-" * 50)
    
    # Initialize client
    client = DashboardClient("validator_example_5")
    
    # Test connection
    if not client.test_connection():
        print("❌ Cannot connect to server. Make sure it's running on port 3001")
        return
    
    # Start async mode
    client.start_async_mode()
    
    try:
        # Simulate a validator cycle
        client.log_cycle_start("process_miners")
        
        # Process some miners
        for miner_id in [123, 456, 789, 101112]:
            client.log_miner_processed(miner_id, 85.5, "verified")
            client.log_ssh_attempt(miner_id, True)
            client.log_miner_verification(miner_id, True, 85.5)
            time.sleep(0.1)
        
        # Update counts and metrics
        client.update_miner_counts(active=256, processed=4, verified=4, rejected=0)
        client.update_block_info(5655713, 5655700)
        
        # Weight update
        client.log_weight_update(256, 21845.67)
        
        # Reward distribution
        client.log_reward_distribution(123, 0.000123)
        
        # End cycle
        client.log_cycle_end("process_miners", 45.2, 4)
        
        print("✅ Validator events example completed")
        
    finally:
        client.stop_async_mode()
        client.print_stats()


def main():
    """Main function demonstrating all examples"""
    print("🚀 Polaris Validator Dashboard Client Examples")
    print("=" * 60)
    print("Make sure the dashboard server is running:")
    print("  npm run server")
    print("=" * 60)
    
    # Setup signal handler for graceful shutdown
    def signal_handler(signum, frame):
        print("\n\n🛑 Received interrupt signal, shutting down...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Run all examples
        example_basic_usage()
        time.sleep(2)
        
        example_async_usage()
        time.sleep(2)
        
        example_raw_log_streaming()
        time.sleep(2)
        
        example_integration_with_existing_logger()
        time.sleep(2)
        
        example_validator_events()
        
        print("\n🎉 All examples completed successfully!")
        print("\n📋 Next Steps:")
        print("1. Open the dashboard at http://localhost:5173")
        print("2. Check the Live Validator Logs section")
        print("3. You should see logs from all examples")
        print("4. Integrate the DashboardClient into your validator code")
        
    except KeyboardInterrupt:
        print("\n\n🛑 Examples interrupted by user")
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 