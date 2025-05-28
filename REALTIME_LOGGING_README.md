# SSE Log Streaming for Polaris Validator Dashboard

## Overview

The Polaris Validator Dashboard Client now uses **Server-Sent Events (SSE)** to stream plain logs in real-time directly to the dashboard, providing immediate visibility into validator operations without memory accumulation.

## Key Features

### 📡 SSE Log Streaming
- **Server-Sent Events** - Streams plain logs directly via SSE protocol
- **Immediate transmission** - Logs are streamed as soon as they're generated
- **Plain log format** - Raw log data without complex JSON wrapping
- **Persistent connection** - Maintains SSE connection for continuous streaming

### 🚀 Performance Optimized
- **Non-blocking operation** - Validator continues running while logs are streamed
- **Memory efficient** - Only keeps a small buffer of recent logs for display
- **Queue overflow protection** - Prevents memory issues with queue size limits
- **Auto-reconnection** - Automatically reconnects SSE on connection loss

### 🔄 Dual Transmission System
- **SSE log stream** - Plain log entries streamed immediately via `/api/validator-logs/stream`
- **Metrics payload** - System metrics and recent logs sent periodically via `/api/validator-data`
- **Separate protocols** - SSE for logs, HTTP POST for metrics

## Architecture

### SSE Log Flow
```
Validator Event → add_log() → Queue → SSE Thread → Stream → Dashboard
                     ↓
                Recent Logs Buffer (for display)
```

### Dual Threading System
1. **Metrics Thread** - Sends system metrics every 5 seconds (configurable)
2. **SSE Thread** - Continuously streams logs via Server-Sent Events

## Configuration

### Dashboard Client Initialization
```python
dashboard = DashboardClient(
    server_url="http://localhost:3001",
    validator_id="validator_1",
    validator_name="Polaris Validator",
    hotkey="your_hotkey_here",
    send_interval=5,           # Metrics transmission interval
    sse_logs=True,             # Enable SSE log streaming
    log_buffer_size=50         # Recent logs buffer size for display
)
```

### Configuration Options

#### SSE Streaming Mode (Recommended)
```python
sse_logs=True,           # Stream logs via SSE
log_buffer_size=50       # Keep 50 recent logs for display
```
- **Use case**: Production validators, real-time monitoring
- **Memory**: Constant low usage
- **Performance**: Optimal validator performance
- **Visibility**: Complete real-time log streaming

#### Metrics Only Mode
```python
sse_logs=False,          # Disable SSE streaming
log_buffer_size=100      # Keep more logs for batch sending
```
- **Use case**: Testing, debugging, limited connectivity
- **Memory**: Slightly higher usage
- **Performance**: Good
- **Visibility**: Delayed log visibility via metrics payload

## Data Transmission

### SSE Log Stream: `/api/validator-logs/stream`
```json
{
  "validator_id": "validator_1",
  "validator_name": "Polaris Validator",
  "level": "INFO",
  "module": "validator.process_miners",
  "message": "Miner 42 processed: score=87.50, status=processed",
  "timestamp": "2024-01-15T10:30:45.123Z",
  "miner_uid": 42,
  "score": 87.5
}
```

### Metrics Endpoint: `/api/validator-data`
```json
{
  "validator_id": "validator_1",
  "validator_name": "Polaris Validator",
  "metrics": { ... },
  "recent_logs": [
    // Last 10 logs for display
  ],
  "log_info": {
    "sse_logs_enabled": true,
    "sse_connection_status": "connected",
    "recent_logs_count": 10,
    "log_buffer_size": 50,
    "logs_queue_size": 0
  },
  "statistics": {
    "total_logs_generated": 1250,
    "logs_streamed_sse": 1248
  }
}
```

## SSE Connection Management

### Connection Establishment
- **Headers**: Includes validator identification
- **Persistent**: Maintains long-lived connection
- **Auto-retry**: Reconnects on connection loss
- **Timeout**: 30-second connection timeout

### Connection Monitoring
- **Status tracking**: Connected/disconnected/error states
- **Queue monitoring**: Tracks pending logs in queue
- **Reconnection logic**: Automatic retry with backoff
- **Error handling**: Graceful degradation on failures

## Performance Benefits

### Memory Usage
- **Constant memory footprint** - No log accumulation
- **Small buffer size** - Only recent logs kept for display
- **Queue overflow protection** - Prevents memory spikes
- **Automatic cleanup** - Logs are streamed and discarded immediately

### Validator Performance
- **Non-blocking logging** - Validator operations never wait for log transmission
- **Background processing** - Separate threads handle all network communication
- **Fast streaming** - SSE provides efficient real-time transmission
- **No I/O blocking** - Validator cycles continue uninterrupted

### Network Efficiency
- **Persistent connection** - No connection overhead per log
- **Plain log format** - Minimal data overhead
- **Parallel streams** - Metrics and logs sent independently
- **Optimized protocol** - SSE designed for real-time streaming

## Monitoring and Statistics

### SSE Metrics
Monitor these key indicators:
- `total_logs_generated` - Total logs created since startup
- `logs_streamed_sse` - Logs successfully streamed via SSE
- `sse_connection_status` - Current SSE connection state
- `logs_queue_size` - Current queue size (should be near 0)

### Performance Indicators
- **SSE connection** should remain "connected"
- **Queue size** should remain low (< 10)
- **Streaming rate** should match generation rate
- **Memory usage** should remain constant

## Testing

### SSE Streaming Test Script
```bash
# Test SSE log streaming performance
python test_comprehensive_logging.py --duration 60 --send-interval 2

# Monitor SSE connection and queue performance
python test_comprehensive_logging.py --duration 30 --show-final-data
```

### Verification Points
- ✅ Logs streamed immediately via SSE
- ✅ SSE connection remains stable
- ✅ Queue size remains low
- ✅ No memory accumulation
- ✅ Validator performance unaffected

## Production Usage

### Validator Integration
```python
# Automatic SSE log streaming in validator
self.dashboard = DashboardClient(
    server_url=dashboard_url,
    validator_id=f"validator_{self.instance_id}",
    validator_name=f"Polaris Validator {self.instance_id}",
    hotkey=self.wallet.hotkey.ss58_address,
    send_interval=5,
    sse_logs=True,           # SSE streaming
    log_buffer_size=50       # Small buffer for display
)
```

### Best Practices
- **Keep buffer size small** (50-100 logs) for memory efficiency
- **Monitor SSE connection** to ensure streaming performance
- **Use appropriate timeouts** for network reliability
- **Enable SSE mode** for production validators

## Troubleshooting

### SSE Connection Issues
```python
# Check SSE status
print(f"SSE Status: {dashboard.stats['sse_connection_status']}")
print(f"Queue size: {dashboard.stats['logs_queue_size']}")
print(f"Logs streamed: {dashboard.stats['logs_streamed_sse']}")
```

### Network Issues
- SSE uses persistent connections with auto-reconnect
- Failed streams are dropped to prevent queue buildup
- Metrics continue to be sent even if SSE fails
- Connection status is monitored and reported

### Memory Monitoring
```python
# Monitor memory usage
print(f"Buffer size: {len(dashboard.recent_logs)}")
print(f"Max buffer: {dashboard.log_buffer_size}")
```

## Dependencies

### Required Packages
```bash
pip install -r dashboard_requirements.txt
```

Contents of `dashboard_requirements.txt`:
```
requests>=2.25.0
psutil>=5.8.0
loguru>=0.6.0
sseclient-py>=1.7.0
```

## Migration from HTTP POST Logging

### Old Approach (HTTP POST per log)
```python
# OLD: HTTP POST for each log
realtime_logs=True,      # HTTP POST transmission
log_buffer_size=50       # Small display buffer
```

### New Approach (SSE Streaming)
```python
# NEW: Stream logs via SSE
sse_logs=True,           # SSE streaming
log_buffer_size=50       # Small display buffer
```

### Benefits of Migration
- **Better performance** - Persistent connection vs per-request overhead
- **Real-time streaming** - Designed for continuous data flow
- **Lower latency** - No HTTP request/response cycle per log
- **Better scalability** - Handles high log volumes efficiently

## Summary

The SSE log streaming system provides:

✅ **Real-time log streaming** - Plain logs via Server-Sent Events  
✅ **Constant memory usage** - No accumulation over time  
✅ **Optimal performance** - Non-blocking validator operation  
✅ **Complete visibility** - All logs streamed immediately  
✅ **Production ready** - Designed for long-running validators  
✅ **Network efficient** - Persistent SSE connections  

Your validator now streams all logs in real-time via SSE while maintaining minimal memory footprint and optimal performance. 