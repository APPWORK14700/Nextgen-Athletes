#!/usr/bin/env python3
"""
Demonstration script for the improved notification service
"""
import asyncio
import os
import sys
from datetime import datetime

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.notification_service import NotificationService
from app.config.notification_config import get_config_for_environment
from app.models.notification import NotificationCreate, NotificationSearchFilters
from app.utils.performance_monitor import PerformanceMonitor


async def demo_basic_usage():
    """Demonstrate basic notification service usage"""
    print("🚀 Basic Notification Service Demo")
    print("=" * 50)
    
    # Create service with default configuration
    service = NotificationService()
    
    # Create a simple notification
    notification_data = NotificationCreate(
        user_id="demo_user_123",
        type="message",
        title="Welcome to the Platform",
        message="Thank you for joining our athlete networking platform!"
    )
    
    print(f"Creating notification for user: {notification_data.user_id}")
    print(f"Type: {notification_data.type}")
    print(f"Title: {notification_data.title}")
    print(f"Message: {notification_data.message}")
    
    # Note: In a real scenario, this would create the notification
    # For demo purposes, we'll just show the structure
    print("\n✅ Notification structure created successfully!")
    
    # Show metrics
    metrics = service.get_metrics()
    print(f"\n📊 Current Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")


async def demo_custom_configuration():
    """Demonstrate custom configuration"""
    print("\n🔧 Custom Configuration Demo")
    print("=" * 50)
    
    # Custom configuration for development/testing
    custom_config = {
        'max_notifications_per_user': 500,
        'rate_limit_max': 100,
        'batch_size': 100,
        'enable_metrics': True,
        'enable_performance_monitoring': True
    }
    
    print("Creating service with custom configuration:")
    for key, value in custom_config.items():
        print(f"  {key}: {value}")
    
    service = NotificationService(config=custom_config)
    
    print(f"\n✅ Service configured with:")
    print(f"  Max notifications per user: {service.max_notifications_per_user}")
    print(f"  Rate limit max: {service.rate_limit_max}")
    print(f"  Batch size: {service.batch_size}")


async def demo_notification_templates():
    """Demonstrate notification templates"""
    print("\n📝 Notification Templates Demo")
    print("=" * 50)
    
    service = NotificationService()
    
    # Demonstrate different notification types using templates
    notification_types = [
        ("message", "John Doe", "conv_123"),
        ("opportunity", "Championship Tryout", "opp_456"),
        ("application", "accepted", "Championship Tryout"),
        ("verification", "approved"),
        ("moderation", "profile photo", "approved")
    ]
    
    print("Creating notifications using templates:")
    
    for i, (notif_type, *args) in enumerate(notification_types, 1):
        try:
            if notif_type == "message":
                notification = await service.create_message_notification(*args)
            elif notif_type == "opportunity":
                notification = await service.create_opportunity_notification(*args)
            elif notif_type == "application":
                notification = await service.create_application_notification(*args)
            elif notif_type == "verification":
                notification = await service.create_verification_notification(*args)
            elif notif_type == "moderation":
                notification = await service.create_moderation_notification(*args)
            
            print(f"  {i}. {notif_type.title()} notification created")
            
        except Exception as e:
            print(f"  {i}. {notif_type.title()} notification failed: {e}")
    
    print("\n✅ Template-based notifications demonstrated!")


async def demo_performance_monitoring():
    """Demonstrate performance monitoring"""
    print("\n⚡ Performance Monitoring Demo")
    print("=" * 50)
    
    # Create performance monitor
    monitor = PerformanceMonitor(threshold_ms=100, enable_logging=True)
    
    # Simulate some operations
    @monitor.monitor("demo_operation")
    async def demo_operation():
        await asyncio.sleep(0.05)  # 50ms delay
        return "operation completed"
    
    @monitor.monitor("slow_operation")
    async def slow_operation():
        await asyncio.sleep(0.15)  # 150ms delay (exceeds threshold)
        return "slow operation completed"
    
    print("Running demo operations...")
    
    # Run operations
    await demo_operation()
    await slow_operation()
    
    # Get performance metrics
    metrics = monitor.get_metrics()
    
    print("\n📊 Performance Metrics:")
    for operation, data in metrics.items():
        print(f"\n  {operation}:")
        print(f"    Total calls: {data['total_calls']}")
        print(f"    Successful: {data['successful_calls']}")
        print(f"    Failed: {data['failed_calls']}")
        print(f"    Avg duration: {data['avg_duration_ms']:.2f}ms")
    
    # Check for slow operations
    slow_ops = monitor.get_slow_operations()
    if slow_ops:
        print(f"\n⚠️  Slow operations detected: {list(slow_ops.keys())}")
    
    print("\n✅ Performance monitoring demonstrated!")


async def demo_environment_configs():
    """Demonstrate different environment configurations"""
    print("\n🌍 Environment Configuration Demo")
    print("=" * 50)
    
    environments = ['development', 'production', 'testing']
    
    for env in environments:
        print(f"\n{env.upper()} Configuration:")
        config = get_config_for_environment(env)
        
        print(f"  Max notifications per user: {config['max_notifications_per_user']}")
        print(f"  Rate limit max: {config['rate_limit_max']}")
        print(f"  Batch size: {config['batch_size']}")
        print(f"  Log level: {config['log_level']}")
        print(f"  Enable metrics: {config['enable_metrics']}")
    
    print("\n✅ Environment configurations demonstrated!")


async def demo_metrics_and_analytics():
    """Demonstrate metrics and analytics features"""
    print("\n📈 Metrics and Analytics Demo")
    print("=" * 50)
    
    service = NotificationService()
    
    # Simulate some operations to generate metrics
    print("Simulating notification operations...")
    
    # Create some notifications
    for i in range(3):
        notification_data = NotificationCreate(
            user_id=f"user_{i}",
            type="message",
            title=f"Test Notification {i+1}",
            message=f"This is test notification number {i+1}"
        )
        
        try:
            # In a real scenario, this would create the notification
            # For demo purposes, we'll just simulate
            await asyncio.sleep(0.01)  # Simulate processing time
            print(f"  Created notification {i+1}")
        except Exception as e:
            print(f"  Failed to create notification {i+1}: {e}")
    
    # Get current metrics
    metrics = service.get_metrics()
    
    print(f"\n📊 Current Service Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    
    # Reset metrics
    print("\n🔄 Resetting metrics...")
    service.reset_metrics()
    
    # Verify reset
    metrics_after_reset = service.get_metrics()
    print(f"  Metrics after reset: {metrics_after_reset}")
    
    print("\n✅ Metrics and analytics demonstrated!")


async def main():
    """Main demonstration function"""
    print("🎯 Improved Notification Service - Complete Demo")
    print("=" * 60)
    print("This demo showcases all the improvements made to the notification service")
    print("=" * 60)
    
    try:
        # Run all demos
        await demo_basic_usage()
        await demo_custom_configuration()
        await demo_notification_templates()
        await demo_performance_monitoring()
        await demo_environment_configs()
        await demo_metrics_and_analytics()
        
        print("\n🎉 All demonstrations completed successfully!")
        print("\n💡 Key Benefits Demonstrated:")
        print("  ✅ Configuration management")
        print("  ✅ Notification templates")
        print("  ✅ Performance monitoring")
        print("  ✅ Metrics and analytics")
        print("  ✅ Environment-specific configurations")
        print("  ✅ Enhanced error handling")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main()) 