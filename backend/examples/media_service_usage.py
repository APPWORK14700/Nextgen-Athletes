"""
Example usage of refactored media services
"""
import asyncio
import os
from datetime import datetime

# Set environment variables for configuration
os.environ['MAX_UPLOADS_PER_HOUR'] = '30'
os.environ['AI_ANALYSIS_MAX_RETRIES'] = '3'
os.environ['ENABLE_CONCURRENT_UPLOADS'] = 'true'

from app.services.media_service_refactored import MediaService
from app.models.media import MediaCreate, MediaUpdate


async def example_media_operations():
    """Example of using the refactored media service"""
    
    # Initialize the media service
    media_service = MediaService()
    
    print("=== Media Service Example ===\n")
    
    # 1. Upload single media
    print("1. Uploading single media...")
    try:
        media_data = MediaCreate(
            type="video",
            description="Amazing soccer goal from midfield"
        )
        
        uploaded_media = await media_service.upload_media(
            athlete_id="athlete_123",
            media_data=media_data,
            file_url="https://example.com/soccer_goal.mp4",
            thumbnail_url="https://example.com/thumbnail.jpg"
        )
        
        print(f"✅ Media uploaded successfully!")
        print(f"   ID: {uploaded_media.id}")
        print(f"   Type: {uploaded_media.type}")
        print(f"   Status: {uploaded_media.moderation_status}")
        print(f"   AI Analysis: {uploaded_media.ai_analysis.status}")
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
    
    print()
    
    # 2. Bulk upload media
    print("2. Bulk uploading media...")
    try:
        media_list = [
            {
                "metadata": {
                    "type": "image",
                    "description": "Training session photo"
                },
                "file_url": "https://example.com/training1.jpg"
            },
            {
                "metadata": {
                    "type": "reel",
                    "description": "Skills compilation"
                },
                "file_url": "https://example.com/skills.mp4"
            }
        ]
        
        bulk_result = await media_service.bulk_upload_media(
            athlete_id="athlete_123",
            media_list=media_list
        )
        
        print(f"✅ Bulk upload completed!")
        print(f"   Successfully uploaded: {bulk_result.uploaded_count}")
        print(f"   Failed: {bulk_result.failed_count}")
        print(f"   Media IDs: {bulk_result.media_ids}")
        
        if bulk_result.errors:
            print(f"   Errors: {bulk_result.errors}")
        
    except Exception as e:
        print(f"❌ Bulk upload failed: {e}")
    
    print()
    
    # 3. Query athlete media
    print("3. Querying athlete media...")
    try:
        athlete_media = await media_service.get_athlete_media(
            athlete_id="athlete_123",
            limit=10,
            offset=0
        )
        
        print(f"✅ Found {athlete_media.total_count} media items")
        for media in athlete_media.media[:3]:  # Show first 3
            print(f"   - {media.type}: {media.description or 'No description'}")
        
    except Exception as e:
        print(f"❌ Query failed: {e}")
    
    print()
    
    # 4. Search media
    print("4. Searching media...")
    try:
        search_results = await media_service.search_media(
            query="soccer",
            media_type="video",
            limit=5
        )
        
        print(f"✅ Search completed!")
        print(f"   Found {len(search_results.media)} results")
        for result in search_results.media[:2]:  # Show first 2
            print(f"   - {result.type}: {result.description or 'No description'}")
        
    except Exception as e:
        print(f"❌ Search failed: {e}")
    
    print()
    
    # 5. Get recommendations
    print("5. Getting recommendations...")
    try:
        recommended_reels = await media_service.get_recommended_reels(
            scout_id="scout_456",
            limit=5
        )
        
        print(f"✅ Recommendations retrieved!")
        print(f"   Found {len(recommended_reels)} recommended reels")
        for reel in recommended_reels[:2]:  # Show first 2
            print(f"   - {reel.description or 'No description'}")
        
    except Exception as e:
        print(f"❌ Recommendations failed: {e}")
    
    print()
    
    # 6. Get service status
    print("6. Service status...")
    try:
        status = media_service.get_service_status()
        print(f"✅ Service status:")
        print(f"   Upload Service: {status['upload_service']}")
        print(f"   Query Service: {status['query_service']}")
        print(f"   AI Analysis Agent: {status['analysis_agent']}")
        print(f"   Recommendation Agent: {status['recommendation_agent']}")
        print(f"   Background Tasks: {status['background_tasks']}")
        print(f"   Max Uploads/Hour: {status['config']['max_uploads_per_hour']}")
        
    except Exception as e:
        print(f"❌ Status check failed: {e}")
    
    print()
    
    # 7. Rate limit information
    print("7. Rate limit information...")
    try:
        rate_limit_info = await media_service.get_upload_rate_limit_info("athlete_123")
        print(f"✅ Rate limit info:")
        print(f"   Current uploads: {rate_limit_info.current_uploads}")
        print(f"   Max uploads: {rate_limit_info.max_uploads}")
        print(f"   Time window: {rate_limit_info.time_window_hours} hours")
        print(f"   Reset time: {rate_limit_info.reset_time}")
        
    except Exception as e:
        print(f"❌ Rate limit check failed: {e}")
    
    print("\n=== Example completed ===")


async def example_ai_analysis_operations():
    """Example of AI analysis operations"""
    
    media_service = MediaService()
    
    print("\n=== AI Analysis Example ===\n")
    
    # 1. Retry AI analysis
    print("1. Retrying AI analysis...")
    try:
        success = await media_service.retry_ai_analysis(
            media_id="media_123",
            athlete_id="athlete_123"
        )
        
        if success:
            print("✅ AI analysis retry initiated")
        else:
            print("❌ AI analysis retry failed")
        
    except AuthorizationError:
        print("❌ Not authorized to retry analysis")
    except Exception as e:
        print(f"❌ Retry failed: {e}")
    
    print()
    
    # 2. Get AI analysis status
    print("2. Getting AI analysis status...")
    try:
        status = await media_service.get_ai_analysis_status("media_123")
        if status:
            print(f"✅ AI Analysis Status: {status.get('status', 'unknown')}")
            print(f"   Rating: {status.get('rating', 'N/A')}")
            print(f"   Confidence: {status.get('confidence_score', 'N/A')}")
        else:
            print("❌ Could not retrieve AI analysis status")
        
    except Exception as e:
        print(f"❌ Status check failed: {e}")
    
    print("\n=== AI Analysis Example completed ===")


async def example_cleanup():
    """Example of cleanup operations"""
    
    media_service = MediaService()
    
    print("\n=== Cleanup Example ===\n")
    
    # Cleanup background tasks
    print("1. Cleaning up background tasks...")
    try:
        await media_service.cleanup_background_tasks()
        print("✅ Background tasks cleaned up")
        
        task_count = media_service.get_background_task_count()
        print(f"   Active background tasks: {task_count}")
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
    
    print("\n=== Cleanup Example completed ===")


async def main():
    """Main example function"""
    
    print("🚀 Starting Media Service Examples...\n")
    
    # Run examples
    await example_media_operations()
    await example_ai_analysis_operations()
    await example_cleanup()
    
    print("\n🎉 All examples completed!")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main()) 