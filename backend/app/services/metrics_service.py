"""
Metrics service for monitoring performance and collecting operational data
"""
import time
import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types of metrics that can be collected"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

@dataclass
class MetricValue:
    """Represents a single metric value with timestamp"""
    value: Union[int, float]
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)

@dataclass
class Metric:
    """Represents a metric with its configuration and values"""
    name: str
    type: MetricType
    description: str
    unit: str = ""
    values: deque = field(default_factory=lambda: deque(maxlen=1000))  # Keep last 1000 values
    labels: Dict[str, str] = field(default_factory=dict)

class MetricsService:
    """Service for collecting and managing application metrics"""
    
    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
        self._lock = asyncio.Lock()
        self._start_time = datetime.now()
        
        # Initialize default metrics
        self._init_default_metrics()
    
    def _init_default_metrics(self):
        """Initialize default system metrics"""
        self.register_metric("system_uptime", MetricType.GAUGE, "System uptime in seconds", "seconds")
        self.register_metric("total_requests", MetricType.COUNTER, "Total number of requests", "requests")
        self.register_metric("active_connections", MetricType.GAUGE, "Number of active connections", "connections")
        self.register_metric("error_rate", MetricType.GAUGE, "Error rate percentage", "percentage")
        self.register_metric("response_time", MetricType.HISTOGRAM, "Response time distribution", "milliseconds")
        self.register_metric("cache_hit_rate", MetricType.GAUGE, "Cache hit rate percentage", "percentage")
        self.register_metric("database_connections", MetricType.GAUGE, "Number of database connections", "connections")
        self.register_metric("memory_usage", MetricType.GAUGE, "Memory usage in bytes", "bytes")
        self.register_metric("cpu_usage", MetricType.GAUGE, "CPU usage percentage", "percentage")
    
    def register_metric(self, name: str, metric_type: MetricType, description: str, 
                       unit: str = "", labels: Optional[Dict[str, str]] = None) -> None:
        """
        Register a new metric
        
        Args:
            name: Metric name
            metric_type: Type of metric
            description: Description of what the metric measures
            unit: Unit of measurement
            labels: Optional labels for the metric
        """
        if name in self._metrics:
            logger.warning(f"Metric {name} already registered, overwriting")
        
        self._metrics[name] = Metric(
            name=name,
            type=metric_type,
            description=description,
            unit=unit,
            labels=labels or {}
        )
        logger.info(f"Registered metric: {name} ({metric_type.value})")
    
    def increment(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Increment a counter metric
        
        Args:
            name: Metric name
            value: Value to increment by (default: 1)
            labels: Optional labels for this measurement
        """
        if name not in self._metrics:
            logger.warning(f"Metric {name} not registered, auto-registering as counter")
            self.register_metric(name, MetricType.COUNTER, f"Auto-registered counter: {name}")
        
        metric = self._metrics[name]
        if metric.type != MetricType.COUNTER:
            logger.warning(f"Cannot increment non-counter metric {name} (type: {metric.type.value})")
            return
        
        metric.values.append(MetricValue(
            value=value,
            timestamp=datetime.now(),
            labels=labels or {}
        ))
    
    def set_gauge(self, name: str, value: Union[int, float], 
                  labels: Optional[Dict[str, str]] = None) -> None:
        """
        Set a gauge metric value
        
        Args:
            name: Metric name
            value: Current value
            labels: Optional labels for this measurement
        """
        if name not in self._metrics:
            logger.warning(f"Metric {name} not registered, auto-registering as gauge")
            self.register_metric(name, MetricType.GAUGE, f"Auto-registered gauge: {name}")
        
        metric = self._metrics[name]
        if metric.type != MetricType.GAUGE:
            logger.warning(f"Cannot set gauge value for non-gauge metric {name} (type: {metric.type.value})")
            return
        
        metric.values.append(MetricValue(
            value=value,
            timestamp=datetime.now(),
            labels=labels or {}
        ))
    
    def record_timing(self, name: str, duration_ms: float, 
                     labels: Optional[Dict[str, str]] = None) -> None:
        """
        Record a timing measurement
        
        Args:
            name: Metric name
            duration_ms: Duration in milliseconds
            labels: Optional labels for this measurement
        """
        if name not in self._metrics:
            logger.warning(f"Metric {name} not registered, auto-registering as histogram")
            self.register_metric(name, MetricType.HISTOGRAM, f"Auto-registered histogram: {name}", "milliseconds")
        
        metric = self._metrics[name]
        if metric.type not in [MetricType.HISTOGRAM, MetricType.TIMER]:
            logger.warning(f"Cannot record timing for non-timing metric {name} (type: {metric.type.value})")
            return
        
        metric.values.append(MetricValue(
            value=duration_ms,
            timestamp=datetime.now(),
            labels=labels or {}
        ))
    
    def record_histogram(self, name: str, value: Union[int, float], 
                        labels: Optional[Dict[str, str]] = None) -> None:
        """
        Record a histogram value
        
        Args:
            name: Metric name
            value: Value to record
            labels: Optional labels for this measurement
        """
        if name not in self._metrics:
            logger.warning(f"Metric {name} not registered, auto-registering as histogram")
            self.register_metric(name, MetricType.HISTOGRAM, f"Auto-registered histogram: {name}")
        
        metric = self._metrics[name]
        if metric.type != MetricType.HISTOGRAM:
            logger.warning(f"Cannot record histogram value for non-histogram metric {name} (type: {metric.type.value})")
            return
        
        metric.values.append(MetricValue(
            value=value,
            timestamp=datetime.now(),
            labels=labels or {}
        ))
    
    def get_metric(self, name: str) -> Optional[Metric]:
        """Get a specific metric by name"""
        return self._metrics.get(name)
    
    def get_all_metrics(self) -> Dict[str, Metric]:
        """Get all registered metrics"""
        return self._metrics.copy()
    
    def get_metric_summary(self, name: str, window_minutes: int = 60) -> Optional[Dict[str, Any]]:
        """
        Get a summary of a metric over a time window
        
        Args:
            name: Metric name
            window_minutes: Time window in minutes
            
        Returns:
            Dictionary containing metric summary or None if metric not found
        """
        if name not in self._metrics:
            return None
        
        metric = self._metrics[name]
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        
        # Filter values within the time window
        recent_values = [
            mv for mv in metric.values 
            if mv.timestamp >= cutoff_time
        ]
        
        if not recent_values:
            return {
                "name": name,
                "type": metric.type.value,
                "description": metric.description,
                "unit": metric.unit,
                "window_minutes": window_minutes,
                "count": 0,
                "values": []
            }
        
        values = [mv.value for mv in recent_values]
        
        summary = {
            "name": name,
            "type": metric.type.value,
            "description": metric.description,
            "unit": metric.unit,
            "window_minutes": window_minutes,
            "count": len(recent_values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": recent_values[-1].value,
            "latest_timestamp": recent_values[-1].timestamp.isoformat()
        }
        
        # Add type-specific calculations
        if metric.type == MetricType.HISTOGRAM:
            sorted_values = sorted(values)
            summary["median"] = sorted_values[len(sorted_values) // 2]
            summary["p95"] = sorted_values[int(len(sorted_values) * 0.95)]
            summary["p99"] = sorted_values[int(len(sorted_values) * 0.99)]
        
        return summary
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        uptime = (datetime.now() - self._start_time).total_seconds()
        
        # Update system metrics
        self.set_gauge("system_uptime", uptime)
        
        # Get all system metric summaries
        system_metrics = {}
        for name in ["system_uptime", "total_requests", "active_connections", 
                    "error_rate", "response_time", "cache_hit_rate"]:
            if name in self._metrics:
                system_metrics[name] = self.get_metric_summary(name, window_minutes=1)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": uptime,
            "metrics": system_metrics
        }
    
    def reset_metric(self, name: str) -> None:
        """Reset a specific metric"""
        if name in self._metrics:
            self._metrics[name].values.clear()
            logger.info(f"Reset metric: {name}")
    
    def reset_all_metrics(self) -> None:
        """Reset all metrics"""
        for metric in self._metrics.values():
            metric.values.clear()
        logger.info("Reset all metrics")
    
    def cleanup_old_metrics(self, max_age_hours: int = 24) -> int:
        """
        Clean up old metric values
        
        Args:
            max_age_hours: Maximum age of metric values to keep
            
        Returns:
            Number of cleaned values
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cleaned_count = 0
        
        for metric in self._metrics.values():
            original_count = len(metric.values)
            # Remove old values
            metric.values = deque(
                [mv for mv in metric.values if mv.timestamp >= cutoff_time],
                maxlen=metric.values.maxlen
            )
            cleaned_count += original_count - len(metric.values)
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old metric values")
        
        return cleaned_count
    
    def export_metrics(self, format_type: str = "json") -> Union[str, Dict[str, Any]]:
        """
        Export metrics in various formats
        
        Args:
            format_type: Export format ("json", "prometheus", "text")
            
        Returns:
            Exported metrics in the specified format
        """
        if format_type == "json":
            return self._export_json()
        elif format_type == "prometheus":
            return self._export_prometheus()
        elif format_type == "text":
            return self._export_text()
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    def _export_json(self) -> Dict[str, Any]:
        """Export metrics as JSON"""
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {}
        }
        
        for name, metric in self._metrics.items():
            export_data["metrics"][name] = {
                "type": metric.type.value,
                "description": metric.description,
                "unit": metric.unit,
                "labels": metric.labels,
                "summary": self.get_metric_summary(name, window_minutes=60)
            }
        
        return export_data
    
    def _export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        
        for name, metric in self._metrics.items():
            # Add metric help
            lines.append(f"# HELP {name} {metric.description}")
            lines.append(f"# TYPE {name} {metric.type.value}")
            
            # Add metric values
            if metric.values:
                latest = metric.values[-1]
                labels_str = ""
                if latest.labels:
                    label_pairs = [f'{k}="{v}"' for k, v in latest.labels.items()]
                    labels_str = "{" + ",".join(label_pairs) + "}"
                
                lines.append(f"{name}{labels_str} {latest.value}")
        
        return "\n".join(lines)
    
    def _export_text(self) -> str:
        """Export metrics as human-readable text"""
        lines = ["Metrics Report", "=" * 50, ""]
        
        for name, metric in self._metrics.items():
            lines.append(f"Metric: {name}")
            lines.append(f"  Type: {metric.type.value}")
            lines.append(f"  Description: {metric.description}")
            lines.append(f"  Unit: {metric.unit}")
            
            if metric.values:
                summary = self.get_metric_summary(name, window_minutes=60)
                lines.append(f"  Current Value: {summary['latest']}")
                lines.append(f"  Last Updated: {summary['latest_timestamp']}")
                lines.append(f"  Count (1h): {summary['count']}")
                if 'avg' in summary:
                    lines.append(f"  Average (1h): {summary['avg']:.2f}")
            else:
                lines.append("  No data available")
            
            lines.append("")
        
        return "\n".join(lines)

# Global metrics service instance
metrics_service = MetricsService()

# Convenience functions
def increment_metric(name: str, value: int = 1, labels: Optional[Dict[str, str]] = None) -> None:
    """Convenience function to increment a metric"""
    metrics_service.increment(name, value, labels)

def set_gauge_metric(name: str, value: Union[int, float], labels: Optional[Dict[str, str]] = None) -> None:
    """Convenience function to set a gauge metric"""
    metrics_service.set_gauge(name, value, labels)

def record_timing_metric(name: str, duration_ms: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Convenience function to record a timing metric"""
    metrics_service.record_timing(name, duration_ms, labels)

def record_histogram_metric(name: str, value: Union[int, float], labels: Optional[Dict[str, str]] = None) -> None:
    """Convenience function to record a histogram metric"""
    metrics_service.record_histogram(name, value, labels) 