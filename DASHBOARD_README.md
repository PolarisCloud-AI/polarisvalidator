# Polaris Validator Dashboard Client

This document describes the dashboard client integration for the Polaris Validator, which collects real-time data from validator cycles and sends it to a dashboard server for monitoring.

## Overview

The dashboard client automatically collects and transmits:
- **Validator Metrics**: CPU, memory, disk usage, uptime, SSH success rates
- **Miner Processing Data**: Scores, verification results, reward distributions
- **Real-time Logs**: Detailed logs from validator cycles with timestamps
- **Network Information**: Block heights, weight updates, subnet status
- **Statistics**: Cumulative counts and performance metrics

## Architecture

```
Validator Process → Dashboard Client → HTTP POST → Dashboard Server → SSE → Web Dashboard
```

The system uses:
- **HTTP POST** requests to send data from validator to server
- **Server-Sent Events (SSE)** to stream data from server to web dashboard
- **Background threading** for non-blocking data transmission

## Files

### Core Components
- `neurons/utils/dashboard_client.py` - Main dashboard client implementation
- `neurons/validator.py` - Validator with integrated dashboard logging
- `neurons/utils/validator_utils.py` - Validator utilities with dashboard hooks

### Testing
- `test_dashboard_client.py` - Standalone test script for dashboard client

## Integration

The dashboard client is automatically integrated into the validator:

### 1. Initialization
```python
# In PolarisNode.__init__()
self.dashboard = DashboardClient(
    server_url=dashboard_url,
    validator_id=f"validator_{self.instance_id}",
    validator_name=f"Polaris Validator {self.instance_id}",
    hotkey=self.wallet.hotkey.ss58_address,
    send_interval=5
)
self.dashboard.start()
```

### 2. Automatic Logging
The validator automatically logs:
- Miner processing cycles
- SSH connection attempts
- Verification results
- Weight updates
- Reward distributions
- Errors and warnings

### 3. Real-time Metrics
System metrics are collected automatically:
- CPU and memory usage
- Disk usage
- Network latency
- Validator uptime
- SSH success rates

## Configuration

### Environment Variables
```bash
# Dashboard server URL (default: http://localhost:3001)
export DASHBOARD_URL="http://your-dashboard-server:3001"
```

### Validator Configuration
```python
# In validator config
config.dashboard_url = "http://localhost:3001"  # Dashboard server URL
```

## Data Format

The dashboard client sends data in this format:

```json
{
  "validator_id": "validator_abc123",
  "validator_name": "Polaris Validator abc123",
  "metrics": {
    "uptime": 99.5,
    "memory_usage": 45.2,
    "cpu_usage": 23.1,
    "disk_usage": 67.8,
    "ssh_success_rate": 94.5,
    "active_miners": 85,
    "processed_miners": 78,
    "verified_miners": 12,
    "rejected_miners": 3,
    "weight_updates": 15,
    "total_rewards": 1234.56,
    "current_block": 2847392,
    "last_weight_update_block": 2847300,
    "blocks_since_last_update": 92
  },
  "logs": [
    {
      "level": "INFO",
      "module": "validator.process_miners",
      "message": "Miner 42 processed: score=87.5, status=processed",
      "timestamp": "2024-01-15T10:30:45.123Z",
      "miner_uid": 42,
      "score": 87.5
    }
  ],
  "status": "active",
  "network_info": {
    "netuid": 49,
    "block_height": 2847392,
    "hotkey": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
  },
  "statistics": {
    "total_miners_processed": 1250,
    "total_verifications": 89,
    "total_weight_updates": 15,
    "total_rewards_distributed": 12345.67,
    "ssh_attempts": 1340,
    "ssh_successes": 1267,
    "cycle_count": 45
  },
  "timestamp": "2024-01-15T10:30:45.123Z",
  "version": "1.0.0"
}
```

## Testing

### 1. Test Dashboard Client Standalone
```bash
# Run test simulation
python test_dashboard_client.py --duration 60

# With custom settings
python test_dashboard_client.py \
  --server-url http://localhost:3001 \
  --validator-id test_validator_1 \
  --duration 300 \
  --send-interval 3
```

### 2. Test with Real Validator
```bash
# Run validator with dashboard enabled
python neurons/validator.py --dashboard-url http://localhost:3001
```

## Dashboard Server Setup

The dashboard client expects a server with these endpoints:

### POST /api/validator-data
Receives validator data and broadcasts to connected clients.

**Request:**
```json
{
  "validator_id": "validator_1",
  "metrics": { ... },
  "logs": [ ... ],
  // ... other fields
}
```

**Response:**
```json
{
  "status": "success",
  "clients_notified": 3,
  "timestamp": "2024-01-15T10:30:45.123Z"
}
```

### GET /api/status
Returns server status information.

**Response:**
```json
{
  "status": "running",
  "connected_clients": 3,
  "uptime": 3600,
  "version": "1.0.0"
}
```

### GET /events
Server-Sent Events endpoint for real-time data streaming to web dashboard.

## Monitoring

### Key Metrics to Monitor
- **SSH Success Rate**: Should be >90%
- **Miner Processing Rate**: Miners processed per cycle
- **Weight Update Frequency**: Should match subnet tempo
- **Error Rates**: Monitor for recurring errors
- **System Resources**: CPU, memory, disk usage

### Log Levels
- **INFO**: Normal operations, successful processing
- **WARNING**: Non-critical issues, degraded performance
- **ERROR**: Critical errors, failed operations

### Status Indicators
- **active**: Normal operation
- **degraded**: Performance issues (SSH <80%, high resource usage)
- **error**: Critical failures

## Troubleshooting

### Dashboard Client Not Sending Data
1. Check dashboard server URL configuration
2. Verify network connectivity to dashboard server
3. Check validator logs for dashboard client errors
4. Ensure `psutil` dependency is installed

### High Resource Usage
1. Increase `send_interval` to reduce transmission frequency
2. Reduce `max_logs` to limit memory usage
3. Monitor system resources during peak operations

### Missing Data in Dashboard
1. Verify validator is calling dashboard logging methods
2. Check for network issues between validator and server
3. Ensure dashboard server is processing POST requests correctly

## Dependencies

Required Python packages:
```
requests>=2.25.0
psutil>=5.8.0
loguru>=0.6.0
```

## Security Considerations

1. **HTTPS**: Use HTTPS for dashboard server in production
2. **Authentication**: Consider adding API keys for dashboard endpoints
3. **Rate Limiting**: Implement rate limiting on dashboard server
4. **Data Sanitization**: Validate all incoming data on server side

## Performance

### Recommended Settings
- **send_interval**: 5-10 seconds for production
- **max_logs**: 100-200 entries
- **Network timeout**: 10 seconds

### Scaling Considerations
- For multiple validators, consider batching data
- Use load balancing for dashboard server
- Monitor server resource usage with many validators

## Future Enhancements

Potential improvements:
- WebSocket support for bidirectional communication
- Data compression for large payloads
- Local data persistence for offline periods
- Advanced alerting and notification systems
- Historical data analysis and trends 