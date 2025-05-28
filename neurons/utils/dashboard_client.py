#!/usr/bin/env python3
"""
Polaris Validator Dashboard Client
=================================

This client connects your Polaris validator to the real-time log streaming 
dashboard server, sending both raw logs and metrics data.

Features:
- Real-time log streaming
- Automatic log interception from loguru
- Automatic reconnection
- Metrics reporting
- Error handling
- Multiple integration patterns
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
import psutil
from dataclasses import dataclass, asdict

# Suppress urllib3 debug logs to keep terminal clean
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("requests.packages.urllib3").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

# Also disable urllib3 warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Comprehensive HTTP logging suppression at module level
def _suppress_all_http_logging():
    """Aggressively suppress all HTTP library debug logging"""
    http_loggers = [
        'urllib3.connectionpool',
        'urllib3.poolmanager', 
        'urllib3.util.retry',
        'urllib3',
        'requests.packages.urllib3.connectionpool',
        'requests.packages.urllib3',
        'requests',
        'requests.adapters',
        'requests.sessions'
    ]
    
    for logger_name in http_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        logger.propagate = False
        # Remove any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
    
    # Add filter to root logger to block urllib3 debug messages
    class HTTPDebugFilter(logging.Filter):
        def filter(self, record):
            # Block all urllib3 and requests debug/info messages
            if record.levelno <= logging.INFO and any(name in record.name for name in ['urllib3', 'requests']):
                return False
            return True
    
    # Add filter to root logger
    root_logger = logging.getLogger()
    # Remove any existing HTTPDebugFilter to avoid duplicates
    for filter_obj in root_logger.filters[:]:
        if isinstance(filter_obj, type(HTTPDebugFilter())):
            root_logger.removeFilter(filter_obj)
    root_logger.addFilter(HTTPDebugFilter())

# Apply suppression immediately when module is imported
_suppress_all_http_logging()

@dataclass
class ValidatorMetrics:
    """Data class for validator metrics"""
    uptime: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    disk_usage: float = 0.0
    active_miners: int = 0
    processed_miners: int = 0
    verified_miners: int = 0
    rejected_miners: int = 0
    weight_updates: int = 0
    successful_verifications: int = 0
    failed_verifications: int = 0
    total_rewards: float = 0.0
    network_latency: float = 0.0
    cache_hit_rate: float = 0.0
    response_time: float = 0.0
    ssh_success_rate: float = 0.0
    current_block: int = 0
    last_weight_update_block: int = 0
    blocks_since_last_update: int = 0

class DashboardClient:
    """
    Client for connecting to the Polaris Validator Dashboard server
    """
    
    def __init__(self, validator_id: str = None, server_url: str = "http://localhost:3001", 
                 validator_name: str = None, hotkey: str = None, send_interval: int = 5,
                 sse_logs: bool = False, log_buffer_size: int = 50, auto_intercept_logs: bool = True):
        """
        Initialize the dashboard client
        
        Args:
            validator_id: Unique identifier for your validator (e.g., "validator_2b10255f")
            server_url: URL of the dashboard server
            validator_name: Human-readable name for the validator (optional)
            hotkey: Validator hotkey address (optional)
            send_interval: Interval in seconds for sending metrics (default: 5)
            sse_logs: Whether to use Server-Sent Events for logs (legacy, ignored)
            log_buffer_size: Size of log buffer (legacy, ignored)
            auto_intercept_logs: Whether to automatically intercept all loguru logs (default: True)
        """
        # Handle legacy parameter order (server_url, validator_id, ...)
        if validator_id and validator_id.startswith('http'):
            # Old order: server_url, validator_id, validator_name, ...
            server_url, validator_id = validator_id, server_url
        
        self.validator_id = validator_id or "unknown_validator"
        self.validator_name = validator_name or f"Validator {self.validator_id}"
        self.hotkey = hotkey or "unknown_hotkey"
        self.server_url = server_url.rstrip('/')
        self.log_url = f"{self.server_url}/api/validator-logs/{self.validator_id}"
        self.metrics_url = f"{self.server_url}/api/validator-metrics/{self.validator_id}"
        self.status_url = f"{self.server_url}/api/status"
        
        # Connection settings
        self.timeout = 5
        self.max_retries = 3
        self.retry_delay = 2
        self.send_interval = send_interval
        
        # Queue for async log sending
        self.log_queue = queue.Queue(maxsize=1000)
        self.metrics_queue = queue.Queue(maxsize=100)
        
        # Threading control
        self.running = False
        self.log_thread = None
        self.metrics_thread = None
        
        # Metrics data
        self.metrics = ValidatorMetrics()
        self.start_time = time.time()
        
        # Statistics
        self.stats = {
            'logs_sent': 0,
            'logs_failed': 0,
            'metrics_sent': 0,
            'metrics_failed': 0,
            'connection_errors': 0,
            'last_successful_send': None,
            'total_miners_processed': 0,
            'total_verifications': 0,
            'total_weight_updates': 0,
            'total_rewards_distributed': 0.0,
            'ssh_attempts': 0,
            'ssh_successes': 0,
            'cycle_count': 0
        }
        
        # Setup logging (silent)
        self.logger = logging.getLogger(f'DashboardClient[{self.validator_id}]')
        self.logger.setLevel(logging.WARNING)  # Only show warnings and errors
        
        # Log interception setup
        self.log_interceptor = None
        self.loguru_handler_id = None
        self.auto_intercept_logs = auto_intercept_logs
        
    def test_connection(self) -> bool:
        """
        Test connection to the dashboard server
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            response = requests.get(self.status_url, timeout=self.timeout)
            response.raise_for_status()
            
            status_data = response.json()
            print(f"✅ Connected to dashboard server")
            print(f"   Server status: {status_data.get('status', 'unknown')}")
            print(f"   Connected clients: {status_data.get('connected_clients', 0)}")
            print(f"   Active validators: {status_data.get('validators_count', 0)}")
            
            return True
            
        except requests.RequestException as e:
            print(f"❌ Failed to connect to dashboard server: {e}")
            return False
    
    def send_log_sync(self, log_line: str) -> bool:
        """
        Send a log line synchronously
        
        Args:
            log_line: Raw log line to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.log_url,
                    data=log_line,
                    headers={'Content-Type': 'text/plain'},
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                self.stats['logs_sent'] += 1
                self.stats['last_successful_send'] = datetime.now()
                
                return True
                
            except requests.RequestException as e:
                self.stats['connection_errors'] += 1
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    self.stats['logs_failed'] += 1
                    
        return False
    
    def send_log_async(self, log_line: str) -> bool:
        """
        Send a log line asynchronously (queued)
        
        Args:
            log_line: Raw log line to send
            
        Returns:
            bool: True if queued successfully, False if queue is full
        """
        try:
            self.log_queue.put_nowait(log_line)
            return True
        except queue.Full:
            return False
    
    def send_metrics_sync(self, metrics: Dict[str, Any]) -> bool:
        """
        Send metrics synchronously
        
        Args:
            metrics: Dictionary of metrics to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.metrics_url,
                    json=metrics,
                    headers={'Content-Type': 'application/json'},
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                self.stats['metrics_sent'] += 1
                self.stats['last_successful_send'] = datetime.now()
                
                return True
                
            except requests.RequestException as e:
                self.stats['connection_errors'] += 1
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    self.stats['metrics_failed'] += 1
                    
        return False
    
    def send_metrics_async(self, metrics: Dict[str, Any]) -> bool:
        """
        Send metrics asynchronously (queued)
        
        Args:
            metrics: Dictionary of metrics to send
            
        Returns:
            bool: True if queued successfully, False if queue is full
        """
        try:
            self.metrics_queue.put_nowait(metrics)
            return True
        except queue.Full:
            return False
    
    def _log_worker(self):
        """Worker thread for sending logs asynchronously"""
        while self.running:
            try:
                # Get log line with timeout
                log_line = self.log_queue.get(timeout=1.0)
                
                # Send the log line
                self.send_log_sync(log_line)
                
                # Mark task as done
                self.log_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                pass  # Silent error handling
        
    def _metrics_worker(self):
        """Worker thread for sending metrics asynchronously"""
        while self.running:
            try:
                # Get metrics with timeout
                metrics = self.metrics_queue.get(timeout=1.0)
                
                # Send the metrics
                self.send_metrics_sync(metrics)
                
                # Mark task as done
                self.metrics_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                pass  # Silent error handling
    
    def start_async_mode(self):
        """Start asynchronous mode with background threads"""
        if self.running:
            return
        
        self.running = True
        
        # Start log interception
        self.start_log_interception()
        
        # Start worker threads
        self.log_thread = threading.Thread(target=self._log_worker, daemon=True)
        self.metrics_thread = threading.Thread(target=self._metrics_worker, daemon=True)
        
        self.log_thread.start()
        self.metrics_thread.start()
    
    def stop_async_mode(self):
        """Stop asynchronous mode and wait for queues to empty"""
        if not self.running:
            return
        
        # Stop log interception first
        self.stop_log_interception()
        
        # Stop accepting new items
        self.running = False
        
        # Wait for queues to empty
        try:
            self.log_queue.join()
            self.metrics_queue.join()
        except:
            pass
        
        # Wait for threads to finish
        if self.log_thread and self.log_thread.is_alive():
            self.log_thread.join(timeout=5)
        if self.metrics_thread and self.metrics_thread.is_alive():
            self.metrics_thread.join(timeout=5)
    
    def log_info(self, module: str, message: str) -> bool:
        """Log an INFO message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"{timestamp} | INFO     | {module} - {message}"
        
        if self.running:
            return self.send_log_async(log_line)
        else:
            return self.send_log_sync(log_line)
    
    def log_warning(self, module: str, message: str) -> bool:
        """Log a WARNING message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"{timestamp} | WARNING  | {module} - {message}"
        
        if self.running:
            return self.send_log_async(log_line)
        else:
            return self.send_log_sync(log_line)
    
    def log_error(self, module: str, message: str) -> bool:
        """Log an ERROR message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"{timestamp} | ERROR    | {module} - {message}"
        
        if self.running:
            return self.send_log_async(log_line)
        else:
            return self.send_log_sync(log_line)
    
    def log_debug(self, module: str, message: str) -> bool:
        """Log a DEBUG message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"{timestamp} | DEBUG    | {module} - {message}"
        
        if self.running:
            return self.send_log_async(log_line)
        else:
            return self.send_log_sync(log_line)
    
    def send_raw_log(self, log_line: str) -> bool:
        """
        Send a raw log line as it appears in the terminal
        
        Args:
            log_line: Raw log line to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self.running:
            return self.send_log_async(log_line)
        else:
            return self.send_log_sync(log_line)
    
    def get_system_metrics(self) -> Dict[str, float]:
        """Get current system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            return {
                'cpu_usage': cpu_percent,
                'memory_usage': memory_percent,
                'disk_usage': disk_percent
            }
        except:
            return {
                'cpu_usage': 0.0,
                'memory_usage': 0.0,
                'disk_usage': 0.0
            }
    
    def calculate_uptime(self) -> float:
        """Calculate uptime percentage"""
        uptime_seconds = time.time() - self.start_time
        # Assume 100% uptime for now, could be enhanced with actual monitoring
        return min(100.0, (uptime_seconds / 3600) * 100)  # Convert to percentage
    
    def calculate_ssh_success_rate(self) -> float:
        """Calculate SSH success rate"""
        if self.stats['ssh_attempts'] == 0:
            return 100.0
        return (self.stats['ssh_successes'] / self.stats['ssh_attempts']) * 100
    
    def update_metrics(self, **kwargs):
        """Update metrics values"""
        for key, value in kwargs.items():
            if hasattr(self.metrics, key):
                setattr(self.metrics, key, value)
    
    def send_validator_metrics(self, **kwargs):
        """
        Send validator-specific metrics
        
        Common metrics:
        - uptime: Validator uptime percentage
        - memory_usage: Memory usage percentage
        - cpu_usage: CPU usage percentage
        - disk_usage: Disk usage percentage
        - active_miners: Number of active miners
        - ssh_success_rate: SSH connection success rate
        - current_block: Current blockchain block
        - network_latency: Network latency in ms
        """
        # Get system metrics
        system_metrics = self.get_system_metrics()
        
        # Update internal metrics
        self.update_metrics(**kwargs)
        self.update_metrics(**system_metrics)
        self.update_metrics(
            uptime=self.calculate_uptime(),
            ssh_success_rate=self.calculate_ssh_success_rate()
        )
        
        # Create metrics payload
        metrics = {
            'timestamp': datetime.now().isoformat(),
            **asdict(self.metrics),
            **kwargs  # Override with any provided values
        }
        
        if self.running:
            self.send_metrics_async(metrics)
        else:
            self.send_metrics_sync(metrics)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            **self.stats,
            'queue_sizes': {
                'logs': self.log_queue.qsize(),
                'metrics': self.metrics_queue.qsize()
            },
            'async_mode': self.running
        }
    
    def print_stats(self):
        """Print client statistics"""
        stats = self.get_stats()
        
        print(f"\n📊 Dashboard Client Statistics for {self.validator_id}")
        print("=" * 60)
        print(f"Logs sent:           {stats['logs_sent']}")
        print(f"Logs failed:         {stats['logs_failed']}")
        print(f"Metrics sent:        {stats['metrics_sent']}")
        print(f"Metrics failed:      {stats['metrics_failed']}")
        print(f"Connection errors:   {stats['connection_errors']}")
        print(f"Last successful:     {stats['last_successful_send']}")
        print(f"Async mode:          {stats['async_mode']}")
        print(f"Log queue size:      {stats['queue_sizes']['logs']}")
        print(f"Metrics queue size:  {stats['queue_sizes']['metrics']}")
        print("=" * 60)

    # Convenience methods for validator events
    
    def log_miner_processed(self, miner_uid: int, score: float, status: str):
        """Log when a miner is processed"""
        self.log_info(
            "utils.validator_utils:process_miners",
            f"Miner {miner_uid} processed: score={score:.2f}, status={status}"
        )
        self.stats['total_miners_processed'] += 1
        self.update_metrics(processed_miners=self.stats['total_miners_processed'])

    def log_miner_verification(self, miner_uid: int, success: bool, score: float = None, error: str = None):
        """Log miner verification result"""
        message = f"Miner {miner_uid} verification {'succeeded' if success else 'failed'}"
        if score is not None:
            message += f" with score {score:.2f}"
        if error:
            message += f": {error}"
        
        if success:
            self.log_info("utils.validator_utils:verify_miners", message)
        else:
            self.log_warning("utils.validator_utils:verify_miners", message)
        
        self.stats['total_verifications'] += 1
        if success:
            self.update_metrics(successful_verifications=self.stats['total_verifications'])
        else:
            self.update_metrics(failed_verifications=self.stats['total_verifications'])

    def log_ssh_attempt(self, miner_uid: int, success: bool, error: str = None):
        """Log SSH attempt"""
        self.stats['ssh_attempts'] += 1
        if success:
            self.stats['ssh_successes'] += 1
        
        message = f"SSH to miner {miner_uid} {'succeeded' if success else 'failed'}"
        if error:
            message += f": {error}"
        
        if success:
            self.log_info("utils.api_utils:ssh_connection", message)
        else:
            self.log_warning("utils.api_utils:ssh_connection", message)

    def log_weight_update(self, miners_count: int, total_score: float):
        """Log weight update"""
        self.log_info(
            "utils.validator_utils:update_weights",
            f"Updated weights for {miners_count} miners, total score: {total_score:.2f}"
        )
        self.stats['total_weight_updates'] += 1
        self.update_metrics(weight_updates=self.stats['total_weight_updates'])

    def log_reward_distribution(self, miner_uid: int, reward: float):
        """Log reward distribution"""
        self.log_info(
            "utils.validator_utils:distribute_rewards",
            f"Distributed {reward:.6f} tokens to miner {miner_uid}"
        )
        self.stats['total_rewards_distributed'] += reward
        self.update_metrics(total_rewards=self.stats['total_rewards_distributed'])

    def log_cycle_start(self, cycle_type: str):
        """Log start of validator cycle"""
        self.log_info(
            f"utils.validator_utils:{cycle_type}",
            f"Starting {cycle_type} cycle"
        )
        if cycle_type == "process_miners":
            self.stats['cycle_count'] += 1

    def log_cycle_end(self, cycle_type: str, duration: float, miners_processed: int = 0):
        """Log end of validator cycle"""
        self.log_info(
            f"utils.validator_utils:{cycle_type}",
            f"Completed {cycle_type} cycle in {duration:.2f}s, processed {miners_processed} miners"
        )

    def update_block_info(self, current_block: int, last_weight_update_block: int = None):
        """Update block information"""
        self.update_metrics(current_block=current_block)
        if last_weight_update_block is not None:
            self.update_metrics(
                last_weight_update_block=last_weight_update_block,
                blocks_since_last_update=current_block - last_weight_update_block
            )

    def update_miner_counts(self, active: int = None, processed: int = None, 
                           verified: int = None, rejected: int = None):
        """Update miner counts"""
        updates = {}
        if active is not None:
            updates["active_miners"] = active
        if processed is not None:
            updates["processed_miners"] = processed
        if verified is not None:
            updates["verified_miners"] = verified
        if rejected is not None:
            updates["rejected_miners"] = rejected
        
        if updates:
            self.update_metrics(**updates)

    # Legacy compatibility methods
    def start(self):
        """Start the dashboard client (legacy compatibility)"""
        self.start_async_mode()

    def stop(self):
        """Stop the dashboard client (legacy compatibility)"""
        self.stop_async_mode()

    def send_plain_log_message(self, log_message: str):
        """Send a plain log message (legacy compatibility)"""
        self.send_raw_log(log_message)

    def add_log(self, level: str, module: str, message: str, **kwargs):
        """Add a log entry (legacy compatibility)"""
        if level.upper() == "INFO":
            self.log_info(module, message)
        elif level.upper() == "WARNING":
            self.log_warning(module, message)
        elif level.upper() == "ERROR":
            self.log_error(module, message)
        elif level.upper() == "DEBUG":
            self.log_debug(module, message)

    def start_log_interception(self):
        """Start intercepting loguru logs and sending them to dashboard"""
        if not self.auto_intercept_logs or self.log_interceptor:
            return
        
        try:
            # Try to import loguru
            from loguru import logger as loguru_logger
            
            # Create log interceptor
            self.log_interceptor = LogInterceptor(self)
            
            # Add handler to loguru to intercept all logs
            self.loguru_handler_id = loguru_logger.add(
                self.log_interceptor.write,
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
                level="DEBUG",
                colorize=False,
                backtrace=False,
                diagnose=False
            )
            
        except ImportError:
            # loguru not available, skip interception
            pass
        except Exception:
            # Silently handle any other errors
            pass
    
    def stop_log_interception(self):
        """Stop intercepting loguru logs"""
        if self.loguru_handler_id is not None:
            try:
                from loguru import logger as loguru_logger
                loguru_logger.remove(self.loguru_handler_id)
                self.loguru_handler_id = None
            except Exception:
                pass
        
        if self.log_interceptor:
            self.log_interceptor.disable()
            self.log_interceptor = None

    def enable_log_interception(self):
        """Enable automatic log interception"""
        self.auto_intercept_logs = True
        if self.running and not self.log_interceptor:
            self.start_log_interception()
    
    def disable_log_interception(self):
        """Disable automatic log interception"""
        self.auto_intercept_logs = False
        self.stop_log_interception()

class LogInterceptor:
    """Intercepts loguru logs and forwards them to dashboard client"""
    
    def __init__(self, dashboard_client):
        self.dashboard_client = dashboard_client
        self.enabled = True
    
    def write(self, message):
        """Called by loguru for each log message"""
        if self.enabled and self.dashboard_client and message.strip():
            # Send the raw log message to dashboard
            try:
                self.dashboard_client.send_raw_log(message.strip())
            except Exception:
                # Silently ignore errors to prevent log loops
                pass
    
    def enable(self):
        """Enable log interception"""
        self.enabled = True
    
    def disable(self):
        """Disable log interception"""
        self.enabled = False 