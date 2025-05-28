# Polaris Validator Dashboard Client

The dashboard client has been updated to provide a simplified, robust interface for sending real-time logs and metrics to the dashboard server.

## Key Features

- **Automatic Log Interception**: Automatically captures ALL loguru logs from your validator
- **Raw Log Streaming**: Send log lines exactly as they appear in the terminal
- **Structured Logging**: Use convenient methods for different log levels (INFO, WARNING, ERROR, DEBUG)
- **Metrics Reporting**: Send validator metrics including system stats, miner counts, and performance data
- **Asynchronous Operation**: Background threads for non-blocking operation
- **Automatic Reconnection**: Built-in retry logic with exponential backoff
- **Silent Operation**: No terminal clutter, operates quietly in the background

## Automatic Log Interception

🎯 **NEW FEATURE**: The dashboard client now automatically intercepts ALL logs from your validator!

When you start the dashboard client, it automatically captures every `logger.info()`, `logger.warning()`, `logger.error()`, and `logger.debug()` call from loguru and sends them to the dashboard server. This means **you don't need to manually add dashboard logging calls** - all your existing logs are automatically forwarded.

### How it works:
```python
from loguru import logger
from neurons.utils.dashboard_client import DashboardClient

# Initialize dashboard client
dashboard = DashboardClient("validator_123")
dashboard.start()  # Automatic log interception starts here

# All these logs are automatically sent to dashboard
logger.info("Validator started successfully")
logger.warning("High memory usage detected")
logger.error("Failed to connect to miner")
logger.debug("Processing verification batch")

# No manual dashboard calls needed!
```

### Control log interception:
```python
# Disable automatic interception
dashboard.disable_log_interception()
logger.info("This log will NOT be sent to dashboard")

# Re-enable automatic interception
dashboard.enable_log_interception()
logger.info("This log WILL be sent to dashboard")

# Or initialize with interception disabled
dashboard = DashboardClient("validator_123", auto_intercept_logs=False)
```

## API Endpoints

The client sends data to these server endpoints:

- **Logs**: `POST /api/validator-logs/{validator_id}` (Content-Type: text/plain)
- **Metrics**: `POST /api/validator-metrics/{validator_id}` (Content-Type: application/json)
- **Status**: `GET /api/status` (for connection testing)

## Basic Usage

```python
from neurons.utils.dashboard_client import DashboardClient

# Initialize client
client = DashboardClient("validator_2b10255f")

# Test connection
if client.test_connection():
    print("Connected to dashboard server")

# Send raw logs (as they appear in terminal)
client.send_raw_log("2025-05-28 11:43:56.452 | INFO | utils.api_utils:get_miner_details:366 - Looking up miner abc123")

# Send structured logs
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
```

## Asynchronous Mode

For high-throughput scenarios, use asynchronous mode:

```python
# Start async mode
client.start_async_mode()

try:
    # All log and metric calls are now queued and sent in background
    for i in range(1000):
        client.log_info("validator", f"Processing batch {i}")
        client.send_validator_metrics(active_miners=256 + i)
        
finally:
    # Always stop async mode to ensure all data is sent
    client.stop_async_mode()
```

## Validator Event Methods

Convenient methods for common validator events:

```python
# Miner processing
client.log_miner_processed(miner_uid=123, score=85.5, status="verified")
client.log_miner_verification(miner_uid=123, success=True, score=85.5)
client.log_ssh_attempt(miner_uid=123, success=True)

# Weight updates
client.log_weight_update(miners_count=256, total_score=21845.67)

# Reward distribution
client.log_reward_distribution(miner_uid=123, reward=0.000123)

# Cycle tracking
client.log_cycle_start("process_miners")
client.log_cycle_end("process_miners", duration=45.2, miners_processed=256)

# Update metrics
client.update_block_info(current_block=5655713, last_weight_update_block=5655700)
client.update_miner_counts(active=256, processed=256, verified=250, rejected=6)
```

## Integration with Python Logging

You can integrate with existing Python loggers:

```python
import logging
from datetime import datetime

class DashboardLogHandler(logging.Handler):
    def __init__(self, dashboard_client):
        super().__init__()
        self.client = dashboard_client
    
    def emit(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = record.levelname
        module = f"{record.module}:{record.funcName}:{record.lineno}"
        message = record.getMessage()
        
        log_line = f"{timestamp} | {level:<8} | {module} - {message}"
        self.client.send_raw_log(log_line)

# Setup
logger = logging.getLogger('validator_operations')
logger.addHandler(DashboardLogHandler(client))

# Use regular Python logging - automatically goes to dashboard
logger.info("Validator started successfully")
logger.warning("High memory usage detected")
```

## Configuration

```python
client = DashboardClient(
    validator_id="validator_2b10255f",    # Unique validator identifier
    server_url="http://localhost:3001"    # Dashboard server URL
)

# Connection settings (can be modified after initialization)
client.timeout = 5          # Request timeout in seconds
client.max_retries = 3      # Number of retry attempts
client.retry_delay = 2      # Delay between retries
```

## Statistics and Monitoring

```python
# Get current statistics
stats = client.get_stats()
print(f"Logs sent: {stats['logs_sent']}")
print(f"Metrics sent: {stats['metrics_sent']}")
print(f"Connection errors: {stats['connection_errors']}")

# Print formatted statistics
client.print_stats()
```

## Error Handling

The client handles errors gracefully:

- **Connection failures**: Automatic retry with exponential backoff
- **Queue overflow**: Drops oldest items when queues are full
- **Silent operation**: No terminal output for errors (check stats for monitoring)
- **Thread safety**: All operations are thread-safe

## Legacy Compatibility

The client maintains compatibility with the previous API:

```python
# Legacy methods still work
client.start()  # Same as start_async_mode()
client.stop()   # Same as stop_async_mode()
client.send_plain_log_message(log_line)  # Same as send_raw_log()
client.add_log("INFO", "module", "message")  # Same as log_info()
```

## Example Script

Run the complete example script to see all features:

```bash
python validator_client_example.py
```

This demonstrates:
- Basic synchronous usage
- Asynchronous usage
- Raw log streaming
- Logger integration
- Validator event methods

## Requirements

```bash
pip install requests psutil
```

The client automatically collects system metrics (CPU, memory, disk usage) using `psutil`. 