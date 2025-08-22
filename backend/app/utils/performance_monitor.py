"""
Performance monitoring utilities for the notification service
"""
import time
import functools
import logging
from typing import Callable, Any, Dict, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Performance monitoring utility for tracking method execution times"""
    
    def __init__(self, threshold_ms: int = 1000, enable_logging: bool = True):
        self.threshold_ms = threshold_ms
        self.enable_logging = enable_logging
        self.metrics: Dict[str, Dict[str, Any]] = {}
    
    def monitor(self, operation_name: Optional[str] = None, log_slow_operations: bool = True):
        """
        Decorator to monitor method performance
        
        Args:
            operation_name: Custom name for the operation (defaults to method name)
            log_slow_operations: Whether to log operations that exceed threshold
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self._measure_performance(
                    func, operation_name or func.__name__, 
                    log_slow_operations, *args, **kwargs
                )
            
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return self._measure_performance(
                    func, operation_name or func.__name__, 
                    log_slow_operations, *args, **kwargs
                )
            
            # Return appropriate wrapper based on function type
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    async def _measure_performance(self, func: Callable, operation_name: str, 
                                 log_slow_operations: bool, *args, **kwargs):
        """Measure performance of a function execution"""
        start_time = time.time()
        start_datetime = datetime.now()
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Record metrics
            self._record_metric(operation_name, duration_ms, start_datetime, success=True)
            
            # Log slow operations
            if log_slow_operations and duration_ms > self.threshold_ms:
                logger.warning(
                    f"Slow operation detected: {operation_name} took {duration_ms:.2f}ms "
                    f"(threshold: {self.threshold_ms}ms)"
                )
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Record failed operation metrics
            self._record_metric(operation_name, duration_ms, start_datetime, success=False, error=str(e))
            
            # Log failed operations
            if self.enable_logging:
                logger.error(
                    f"Operation failed: {operation_name} failed after {duration_ms:.2f}ms with error: {e}"
                )
            
            raise
    
    def _record_metric(self, operation_name: str, duration_ms: float, 
                       timestamp: datetime, success: bool, error: Optional[str] = None):
        """Record performance metric"""
        if operation_name not in self.metrics:
            self.metrics[operation_name] = {
                'total_calls': 0,
                'successful_calls': 0,
                'failed_calls': 0,
                'total_duration_ms': 0.0,
                'min_duration_ms': float('inf'),
                'max_duration_ms': 0.0,
                'avg_duration_ms': 0.0,
                'last_call': None,
                'errors': []
            }
        
        metric = self.metrics[operation_name]
        metric['total_calls'] += 1
        metric['total_duration_ms'] += duration_ms
        metric['min_duration_ms'] = min(metric['min_duration_ms'], duration_ms)
        metric['max_duration_ms'] = max(metric['max_duration_ms'], duration_ms)
        metric['avg_duration_ms'] = metric['total_duration_ms'] / metric['total_calls']
        metric['last_call'] = timestamp
        
        if success:
            metric['successful_calls'] += 1
        else:
            metric['failed_calls'] += 1
            if error:
                metric['errors'].append({
                    'timestamp': timestamp.isoformat(),
                    'error': error,
                    'duration_ms': duration_ms
                })
                # Keep only last 10 errors to prevent memory issues
                if len(metric['errors']) > 10:
                    metric['errors'] = metric['errors'][-10:]
    
    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get all performance metrics"""
        return self.metrics.copy()
    
    def get_operation_metrics(self, operation_name: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific operation"""
        return self.metrics.get(operation_name)
    
    def reset_metrics(self):
        """Reset all performance metrics"""
        self.metrics = {}
    
    def get_slow_operations(self, threshold_ms: Optional[int] = None) -> Dict[str, Dict[str, Any]]:
        """Get operations that exceed the threshold"""
        threshold = threshold_ms or self.threshold_ms
        slow_ops = {}
        
        for op_name, metrics in self.metrics.items():
            if metrics['avg_duration_ms'] > threshold:
                slow_ops[op_name] = metrics
        
        return slow_ops
    
    def generate_report(self) -> str:
        """Generate a human-readable performance report"""
        if not self.metrics:
            return "No performance metrics available"
        
        report_lines = ["Performance Report", "=" * 50, ""]
        
        for op_name, metrics in self.metrics.items():
            report_lines.extend([
                f"Operation: {op_name}",
                f"  Total Calls: {metrics['total_calls']}",
                f"  Successful: {metrics['successful_calls']}",
                f"  Failed: {metrics['failed_calls']}",
                f"  Duration (ms):",
                f"    Min: {metrics['min_duration_ms']:.2f}",
                f"    Max: {metrics['max_duration_ms']:.2f}",
                f"    Avg: {metrics['avg_duration_ms']:.2f}",
                f"  Last Call: {metrics['last_call']}",
                ""
            ])
        
        return "\n".join(report_lines)

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

# Convenience decorator
def monitor_performance(operation_name: Optional[str] = None, 
                       threshold_ms: Optional[int] = None,
                       log_slow_operations: bool = True):
    """
    Convenience decorator for performance monitoring
    
    Usage:
        @monitor_performance("create_notification")
        async def create_notification(self, data):
            # method implementation
    """
    def decorator(func: Callable) -> Callable:
        monitor = PerformanceMonitor(
            threshold_ms=threshold_ms or 1000,
            enable_logging=True
        )
        return monitor.monitor(operation_name, log_slow_operations)(func)
    
    return decorator 