"""
Search Service for Athletes Networking App

This service handles search history management and advanced search functionality.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.services.database_service import DatabaseService
from app.api.exceptions import ResourceNotFoundError, ValidationError, DatabaseError

# Configure logging
logger = logging.getLogger(__name__)


class SearchService:
    """Service for managing search functionality and history"""
    
    def __init__(self):
        # Initialize database service with collection name
        self.db = DatabaseService("search_history")
        
        # Configuration
        self.max_searches_per_user = 100
        self.default_suggestion_limit = 5
    
    async def save_search(
        self,
        user_id: str,
        search_type: str,
        query: str,
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Save a search to user's search history
        
        Args:
            user_id: ID of the user performing the search
            search_type: Type of search (athletes, opportunities, etc.)
            query: Search query string
            filters: Applied filters
            
        Returns:
            Created search history record
        """
        try:
            logger.info(f"Saving search for user: {user_id}, type: {search_type}")
            
            # Validate search type
            valid_types = ["athletes", "scouts", "opportunities"]
            if search_type not in valid_types:
                raise ValidationError(f"Invalid search type. Must be one of: {', '.join(valid_types)}")
            
            # Sanitize query
            query = query.strip() if query else ""
            if not query:
                raise ValidationError("Search query cannot be empty")
            
            search_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "search_type": search_type,
                "query": query,
                "filters": filters,
                "created_at": datetime.now().isoformat()
            }
            
            # Create the search record
            doc_id = await self.db.create(search_data, search_data["id"])
            result = await self.db.get_by_id(doc_id)
            
            # Clean up old searches to maintain performance
            await self._cleanup_old_searches(user_id)
            
            logger.info(f"Successfully saved search: {result['id']}")
            return result
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error saving search: {str(e)}")
            raise DatabaseError(f"Failed to save search: {str(e)}")
    
    async def get_user_search_history(
        self,
        user_id: str,
        search_type: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get search history for a user
        
        Args:
            user_id: ID of the user
            search_type: Optional filter by search type
            page: Page number for pagination
            limit: Number of results per page
            
        Returns:
            Paginated search history
        """
        try:
            logger.info(f"Getting search history for user: {user_id}, page: {page}")
            
            # Build query filters
            from firebase_admin.firestore import FieldFilter
            filters = [FieldFilter("user_id", "==", user_id)]
            
            if search_type:
                # Validate search type
                valid_types = ["athletes", "scouts", "opportunities"]
                if search_type not in valid_types:
                    raise ValidationError(f"Invalid search type. Must be one of: {', '.join(valid_types)}")
                filters.append(FieldFilter("search_type", "==", search_type))
            
            # Calculate offset
            offset = (page - 1) * limit
            
            # Get paginated results
            searches = await self.db.query(filters, limit=limit, offset=offset)
            
            # Get total count
            total = await self.db.count(filters)
            
            result = {
                "searches": searches,
                "total": total,
                "page": page,
                "limit": limit,
                "has_next": (page * limit) < total,
                "has_previous": page > 1
            }
            
            logger.info(f"Retrieved {len(searches)} search history items")
            return result
            
        except ValidationError:
            raise  # Re-raise validation errors as-is
        except Exception as e:
            logger.error(f"Error getting search history for user {user_id}: {str(e)}")
            raise DatabaseError(f"Failed to get search history: {str(e)}")
    
    async def delete_search_history_item(
        self,
        search_id: str,
        user_id: str
    ) -> None:
        """
        Delete a specific search history item
        
        Args:
            search_id: ID of the search to delete
            user_id: ID of the user (for authorization)
        """
        try:
            logger.info(f"Deleting search history item: {search_id}")
            
            # Verify search exists and belongs to user
            search = await self.db.get_by_id(search_id)
            if not search:
                raise ResourceNotFoundError("Search history item not found", search_id)
            
            if search["user_id"] != user_id:
                raise ValidationError("You can only delete your own search history")
            
            await self.db.delete(search_id)
            
            logger.info(f"Successfully deleted search history item: {search_id}")
            
        except (ResourceNotFoundError, ValidationError):
            raise  # Re-raise these errors as-is
        except Exception as e:
            logger.error(f"Error deleting search history item {search_id}: {str(e)}")
            raise DatabaseError(f"Failed to delete search history item: {str(e)}")
    
    async def clear_user_search_history(self, user_id: str) -> None:
        """
        Clear all search history for a user
        
        Args:
            user_id: ID of the user
        """
        try:
            logger.info(f"Clearing search history for user: {user_id}")
            
            # Get all user's searches
            from firebase_admin.firestore import FieldFilter
            searches = await self.db.query([FieldFilter("user_id", "==", user_id)])
            
            # Delete all searches in batch
            if searches:
                search_ids = [search["id"] for search in searches]
                await self.db.batch_delete(search_ids)
            
            logger.info(f"Successfully cleared {len(searches)} search history items")
            
        except Exception as e:
            logger.error(f"Error clearing search history for user {user_id}: {str(e)}")
            raise DatabaseError(f"Failed to clear search history: {str(e)}")
    
    async def get_popular_searches(
        self,
        search_type: Optional[str] = None,
        days: int = 30,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get popular search terms from the last N days
        
        Args:
            search_type: Optional filter by search type
            days: Number of days to look back
            limit: Maximum number of results
            
        Returns:
            List of popular search terms with counts
        """
        try:
            logger.info(f"Getting popular searches, days: {days}, limit: {limit}")
            
            # Calculate date threshold
            threshold_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Build filters
            from firebase_admin.firestore import FieldFilter
            filters = [FieldFilter("created_at", ">=", threshold_date)]
            
            if search_type:
                valid_types = ["athletes", "scouts", "opportunities"]
                if search_type not in valid_types:
                    raise ValidationError(f"Invalid search type. Must be one of: {', '.join(valid_types)}")
                filters.append(FieldFilter("search_type", "==", search_type))
            
            searches = await self.db.query(filters)
            
            # Count search terms
            term_counts = {}
            for search in searches:
                query = search.get("query", "").strip().lower()
                if query:  # Only count non-empty queries
                    term_counts[query] = term_counts.get(query, 0) + 1
            
            # Sort by count and return top results
            popular = [
                {"term": term, "count": count}
                for term, count in sorted(term_counts.items(), key=lambda x: x[1], reverse=True)
            ]
            
            result = popular[:limit]
            logger.info(f"Found {len(result)} popular search terms")
            return result
            
        except ValidationError:
            raise  # Re-raise validation errors as-is
        except Exception as e:
            logger.error(f"Error getting popular searches: {str(e)}")
            raise DatabaseError(f"Failed to get popular searches: {str(e)}")
    
    async def get_search_suggestions(
        self,
        user_id: str,
        search_type: str,
        partial_query: str,
        limit: int = 5
    ) -> List[str]:
        """
        Get search suggestions based on user's search history and popular searches
        
        Args:
            user_id: ID of the user
            search_type: Type of search
            partial_query: Partial query to match against
            limit: Maximum number of suggestions
            
        Returns:
            List of suggested search terms
        """
        try:
            logger.info(f"Getting search suggestions for user: {user_id}, type: {search_type}")
            
            # Validate search type
            valid_types = ["athletes", "scouts", "opportunities"]
            if search_type not in valid_types:
                raise ValidationError(f"Invalid search type. Must be one of: {', '.join(valid_types)}")
            
            suggestions = set()
            
            # Get user's recent searches that match the partial query
            from firebase_admin.firestore import FieldFilter
            user_searches = await self.db.query([
                FieldFilter("user_id", "==", user_id),
                FieldFilter("search_type", "==", search_type)
            ], limit=50)
            
            for search in user_searches:
                query = search.get("query", "").strip()
                if query and partial_query.lower() in query.lower():
                    suggestions.add(query)
                    if len(suggestions) >= limit:
                        break
            
            # If we need more suggestions, get from popular searches
            if len(suggestions) < limit:
                popular = await self.get_popular_searches(search_type, days=7, limit=20)
                for item in popular:
                    term = item["term"]
                    if partial_query.lower() in term.lower():
                        suggestions.add(term)
                        if len(suggestions) >= limit:
                            break
            
            result = list(suggestions)[:limit]
            logger.info(f"Generated {len(result)} search suggestions")
            return result
            
        except ValidationError:
            raise  # Re-raise validation errors as-is
        except Exception as e:
            logger.error(f"Error getting search suggestions: {str(e)}")
            raise DatabaseError(f"Failed to get search suggestions: {str(e)}")
    
    async def _cleanup_old_searches(self, user_id: str) -> None:
        """
        Clean up old searches to keep only the most recent N per user
        
        Args:
            user_id: ID of the user
        """
        try:
            # Get all user's searches ordered by creation date (oldest first)
            from firebase_admin.firestore import FieldFilter
            searches = await self.db.query([FieldFilter("user_id", "==", user_id)], limit=1000)
            
            # Delete oldest searches if more than max allowed
            if len(searches) >= self.max_searches_per_user:
                searches_to_delete = searches[:-self.max_searches_per_user]  # Keep the most recent
                if searches_to_delete:
                    search_ids = [search["id"] for search in searches_to_delete]
                    await self.db.batch_delete(search_ids)
                    logger.info(f"Cleaned up {len(search_ids)} old search records for user {user_id}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old searches for user {user_id}: {str(e)}")
            # Don't raise here as this is a background cleanup operation
    
    async def get_search_analytics(self, user_id: str) -> Dict[str, Any]:
        """
        Get search analytics for a user
        
        Args:
            user_id: ID of the user
            
        Returns:
            Search analytics data
        """
        try:
            logger.info(f"Getting search analytics for user: {user_id}")
            
            # Get all user's searches with pagination to avoid memory issues
            from firebase_admin.firestore import FieldFilter
            searches = await self.db.query([FieldFilter("user_id", "==", user_id)], limit=1000)
            
            if not searches:
                return {
                    "total_searches": 0,
                    "searches_by_type": {},
                    "most_common_terms": [],
                    "search_frequency": {},
                    "recent_searches": []
                }
            
            # Analyze search patterns
            searches_by_type = {}
            term_counts = {}
            search_frequency = {}
            recent_searches = []
            
            for search in searches:
                search_type = search.get("search_type", "unknown")
                searches_by_type[search_type] = searches_by_type.get(search_type, 0) + 1
                
                query = search.get("query", "").strip().lower()
                if query:
                    term_counts[query] = term_counts.get(query, 0) + 1
                
                # Count searches by date
                date = search.get("created_at", "")[:10]  # Extract date part
                search_frequency[date] = search_frequency.get(date, 0) + 1
                
                # Get recent searches (last 10)
                if len(recent_searches) < 10:
                    recent_searches.append({
                        "query": search.get("query", ""),
                        "search_type": search_type,
                        "created_at": search.get("created_at", "")
                    })
            
            # Get most common terms
            most_common_terms = [
                {"term": term, "count": count}
                for term, count in sorted(term_counts.items(), key=lambda x: x[1], reverse=True)
            ][:10]
            
            result = {
                "total_searches": len(searches),
                "searches_by_type": searches_by_type,
                "most_common_terms": most_common_terms,
                "search_frequency": search_frequency,
                "recent_searches": recent_searches
            }
            
            logger.info(f"Generated analytics for {len(searches)} searches")
            return result
            
        except Exception as e:
            logger.error(f"Error getting search analytics for user {user_id}: {str(e)}")
            raise DatabaseError(f"Failed to get search analytics: {str(e)}")
    
    async def get_search_trends(
        self,
        search_type: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get search trends and insights
        
        Args:
            search_type: Optional filter by search type
            days: Number of days to analyze
            
        Returns:
            Search trends data
        """
        try:
            logger.info(f"Getting search trends, days: {days}")
            
            # Calculate date threshold
            threshold_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Build filters
            from firebase_admin.firestore import FieldFilter
            filters = [FieldFilter("created_at", ">=", threshold_date)]
            
            if search_type:
                valid_types = ["athletes", "scouts", "opportunities"]
                if search_type not in valid_types:
                    raise ValidationError(f"Invalid search type. Must be one of: {', '.join(valid_types)}")
                filters.append(FieldFilter("search_type", "==", search_type))
            
            searches = await self.db.query(filters, limit=1000)
            
            # Analyze trends
            daily_counts = {}
            search_type_counts = {}
            top_queries = {}
            
            for search in searches:
                # Daily counts
                date = search.get("created_at", "")[:10]
                daily_counts[date] = daily_counts.get(date, 0) + 1
                
                # Search type counts
                search_type = search.get("search_type", "unknown")
                search_type_counts[search_type] = search_type_counts.get(search_type, 0) + 1
                
                # Top queries
                query = search.get("query", "").strip().lower()
                if query:
                    top_queries[query] = top_queries.get(query, 0) + 1
            
            # Sort and limit results
            top_queries_sorted = [
                {"query": query, "count": count}
                for query, count in sorted(top_queries.items(), key=lambda x: x[1], reverse=True)
            ][:20]
            
            result = {
                "total_searches": len(searches),
                "daily_counts": daily_counts,
                "search_type_distribution": search_type_counts,
                "top_queries": top_queries_sorted,
                "average_daily_searches": len(searches) / days if days > 0 else 0
            }
            
            logger.info(f"Generated trends for {len(searches)} searches")
            return result
            
        except ValidationError:
            raise  # Re-raise validation errors as-is
        except Exception as e:
            logger.error(f"Error getting search trends: {str(e)}")
            raise DatabaseError(f"Failed to get search trends: {str(e)}") 