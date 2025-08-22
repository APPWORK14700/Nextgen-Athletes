"""
Search Service for Athletes Networking App

This service handles search history management and advanced search functionality.
"""

import uuid
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.services.database_service import DatabaseService
from app.api.exceptions import ResourceNotFoundError, ValidationError, DatabaseError
from app.utils.athlete_utils import AthleteUtils

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
        
        # Search validation patterns
        self.allowed_search_types = ["athletes", "scouts", "opportunities"]
        self.max_query_length = 500
        self.max_filters_count = 20
        self.max_filter_value_length = 100
        
        # Blocked search patterns (prevent malicious queries)
        self.blocked_patterns = [
            r'javascript:', r'vbscript:', r'data:', r'file:', r'ftp:',
            r'<script', r'</script>', r'on\w+\s*=', r'expression\s*\(',
            r'url\s*\(', r'import\s+', r'@import', r'<iframe', r'</iframe>',
            r'\.\.', r'\.\.\.', r'\.\.\.\.',  # Directory traversal
            r'--', r'/\*', r'\*/',  # SQL injection patterns
            r'<', r'>', r'"', r"'", r'&',  # HTML/XML injection
        ]
    
    def _sanitize_search_query(self, query: str) -> str:
        """Sanitize search query to prevent injection attacks
        
        Args:
            query: Raw search query
            
        Returns:
            Sanitized search query
            
        Raises:
            ValidationError: If query contains malicious content
        """
        if not query or not isinstance(query, str):
            raise ValidationError("Search query is required and must be a string")
        
        # Remove null bytes and control characters
        sanitized = query.replace('\x00', '').replace('\r', '').replace('\n', ' ')
        
        # Check for blocked patterns
        for pattern in self.blocked_patterns:
            if re.search(pattern, sanitized, re.IGNORECASE):
                logger.warning(f"Blocked search pattern detected: {pattern}")
                raise ValidationError("Search query contains invalid characters")
        
        # Limit length
        if len(sanitized) > self.max_query_length:
            raise ValidationError(f"Search query too long. Maximum length is {self.max_query_length} characters")
        
        # Remove leading/trailing whitespace
        sanitized = sanitized.strip()
        
        if not sanitized:
            raise ValidationError("Search query cannot be empty after sanitization")
        
        return sanitized
    
    def _sanitize_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize search filters to prevent injection attacks
        
        Args:
            filters: Raw search filters
            
        Returns:
            Sanitized search filters
            
        Raises:
            ValidationError: If filters contain malicious content
        """
        if not filters:
            return {}
        
        if not isinstance(filters, dict):
            raise ValidationError("Filters must be a dictionary")
        
        if len(filters) > self.max_filters_count:
            raise ValidationError(f"Too many filters. Maximum allowed is {self.max_filters_count}")
        
        sanitized_filters = {}
        
        for key, value in filters.items():
            # Sanitize filter key
            if not isinstance(key, str):
                raise ValidationError("Filter keys must be strings")
            
            sanitized_key = AthleteUtils.sanitize_string(key, max_length=50)
            if not sanitized_key:
                continue
            
            # Sanitize filter value
            if isinstance(value, str):
                sanitized_value = AthleteUtils.sanitize_string(value, max_length=self.max_filter_value_length)
                if len(sanitized_value) > self.max_filter_value_length:
                    raise ValidationError(f"Filter value too long. Maximum length is {self.max_filter_value_length} characters")
            elif isinstance(value, (int, float, bool)):
                sanitized_value = value
            elif isinstance(value, list):
                # Sanitize list values
                sanitized_value = []
                for item in value:
                    if isinstance(item, str):
                        sanitized_item = AthleteUtils.sanitize_string(item, max_length=self.max_filter_value_length)
                        sanitized_value.append(sanitized_item)
                    else:
                        sanitized_value.append(item)
            else:
                raise ValidationError(f"Unsupported filter value type: {type(value)}")
            
            sanitized_filters[sanitized_key] = sanitized_value
        
        return sanitized_filters
    
    def _validate_search_type(self, search_type: str) -> str:
        """Validate search type against allowed values
        
        Args:
            search_type: Search type to validate
            
        Returns:
            Validated search type
            
        Raises:
            ValidationError: If search type is invalid
        """
        if not search_type or not isinstance(search_type, str):
            raise ValidationError("Search type is required and must be a string")
        
        sanitized_type = search_type.strip().lower()
        
        if sanitized_type not in self.allowed_search_types:
            raise ValidationError(f"Invalid search type. Must be one of: {', '.join(self.allowed_search_types)}")
        
        return sanitized_type
    
    async def save_search(
        self,
        user_id: str,
        search_type: str,
        query: str,
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Save a search to user's search history with comprehensive validation
        
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
            
            # Validate and sanitize user_id
            if not user_id or not isinstance(user_id, str):
                raise ValidationError("User ID is required and must be a string")
            
            user_id = user_id.strip()
            if not user_id:
                raise ValidationError("User ID cannot be empty")
            
            # Validate and sanitize search type
            validated_search_type = self._validate_search_type(search_type)
            
            # Sanitize search query
            sanitized_query = self._sanitize_search_query(query)
            
            # Sanitize filters
            sanitized_filters = self._sanitize_filters(filters)
            
            # Create search data with sanitized inputs
            search_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "search_type": validated_search_type,
                "query": sanitized_query,
                "filters": sanitized_filters,
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
        Get search history for a user with validation
        
        Args:
            user_id: ID of the user
            search_type: Optional filter by search type
            page: Page number for pagination
            limit: Number of results per page
            
        Returns:
            Search history with pagination
        """
        try:
            # Validate user_id
            if not user_id or not isinstance(user_id, str):
                raise ValidationError("User ID is required and must be a string")
            
            user_id = user_id.strip()
            if not user_id:
                raise ValidationError("User ID cannot be empty")
            
            # Validate pagination parameters
            if not isinstance(page, int) or page < 1:
                raise ValidationError("Page must be a positive integer")
            
            if not isinstance(limit, int) or limit < 1 or limit > 100:
                raise ValidationError("Limit must be between 1 and 100")
            
            # Validate search_type if provided
            validated_search_type = None
            if search_type:
                validated_search_type = self._validate_search_type(search_type)
            
            # Build query filters
            filters = [("user_id", "==", user_id)]
            if validated_search_type:
                filters.append(("search_type", "==", validated_search_type))
            
            # Get search history with pagination
            offset = (page - 1) * limit
            searches = await self.db.query(filters, limit, offset)
            
            # Get total count for pagination
            total_count = await self.db.count(filters)
            
            # Calculate pagination metadata
            total_pages = (total_count + limit - 1) // limit
            has_next = page < total_pages
            has_previous = page > 1
            
            return {
                "searches": searches,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": has_next,
                    "has_previous": has_previous,
                    "next_page": page + 1 if has_next else None,
                    "previous_page": page - 1 if has_previous else None
                }
            }
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting search history for user {user_id}: {str(e)}")
            raise DatabaseError(f"Failed to get search history: {str(e)}")
    
    async def get_search_suggestions(
        self,
        user_id: str,
        search_type: Optional[str] = None,
        limit: int = None
    ) -> List[str]:
        """
        Get search suggestions based on user's search history
        
        Args:
            user_id: ID of the user
            search_type: Optional filter by search type
            limit: Maximum number of suggestions
            
        Returns:
            List of search suggestions
        """
        try:
            # Validate user_id
            if not user_id or not isinstance(user_id, str):
                raise ValidationError("User ID is required and must be a string")
            
            user_id = user_id.strip()
            if not user_id:
                raise ValidationError("User ID cannot be empty")
            
            # Set default limit
            if limit is None:
                limit = self.default_suggestion_limit
            
            if not isinstance(limit, int) or limit < 1 or limit > 50:
                raise ValidationError("Limit must be between 1 and 50")
            
            # Validate search_type if provided
            validated_search_type = None
            if search_type:
                validated_search_type = self._validate_search_type(search_type)
            
            # Build query filters
            filters = [("user_id", "==", user_id)]
            if validated_search_type:
                filters.append(("search_type", "==", validated_search_type))
            
            # Get recent searches
            recent_searches = await self.db.query(filters, limit * 2, 0)
            
            # Extract unique queries and count frequency
            query_counts = {}
            for search in recent_searches:
                query = search.get('query', '')
                if query:
                    query_counts[query] = query_counts.get(query, 0) + 1
            
            # Sort by frequency and recency, return top suggestions
            sorted_queries = sorted(query_counts.items(), key=lambda x: x[1], reverse=True)
            suggestions = [query for query, _ in sorted_queries[:limit]]
            
            return suggestions
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting search suggestions for user {user_id}: {str(e)}")
            raise DatabaseError(f"Failed to get search suggestions: {str(e)}")
    
    async def delete_search_history(
        self,
        user_id: str,
        search_ids: Optional[List[str]] = None
    ) -> bool:
        """
        Delete search history for a user
        
        Args:
            user_id: ID of the user
            search_ids: Optional list of specific search IDs to delete
            
        Returns:
            True if deletion was successful
        """
        try:
            # Validate user_id
            if not user_id or not isinstance(user_id, str):
                raise ValidationError("User ID is required and must be a string")
            
            user_id = user_id.strip()
            if not user_id:
                raise ValidationError("User ID cannot be empty")
            
            if search_ids:
                # Validate search_ids
                if not isinstance(search_ids, list):
                    raise ValidationError("Search IDs must be a list")
                
                if len(search_ids) > 100:
                    raise ValidationError("Cannot delete more than 100 searches at once")
                
                # Validate each search ID
                for search_id in search_ids:
                    if not isinstance(search_id, str) or not search_id.strip():
                        raise ValidationError("Invalid search ID in list")
                
                # Delete specific searches
                await self.db.batch_delete(search_ids)
            else:
                # Delete all search history for user
                filters = [("user_id", "==", user_id)]
                user_searches = await self.db.query(filters, 1000, 0)
                
                if user_searches:
                    search_ids_to_delete = [search['id'] for search in user_searches]
                    await self.db.batch_delete(search_ids_to_delete)
            
            logger.info(f"Successfully deleted search history for user {user_id}")
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error deleting search history for user {user_id}: {str(e)}")
            raise DatabaseError(f"Failed to delete search history: {str(e)}")
    

    
    async def get_popular_searches(
        self,
        search_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get popular searches across all users
        
        Args:
            search_type: Optional filter by search type
            limit: Maximum number of results
            
        Returns:
            List of popular searches with counts
        """
        try:
            # Validate limit
            if not isinstance(limit, int) or limit < 1 or limit > 100:
                raise ValidationError("Limit must be between 1 and 100")
            
            # Validate search_type if provided
            validated_search_type = None
            if search_type:
                validated_search_type = self._validate_search_type(search_type)
            
            # Build query filters
            filters = []
            if validated_search_type:
                filters.append(("search_type", "==", validated_search_type))
            
            # Get recent searches
            recent_searches = await self.db.query(filters, limit * 3, 0)
            
            # Count query frequency
            query_counts = {}
            for search in recent_searches:
                query = search.get('query', '')
                if query:
                    query_counts[query] = query_counts.get(query, 0) + 1
            
            # Sort by frequency and return top results
            sorted_queries = sorted(query_counts.items(), key=lambda x: x[1], reverse=True)
            popular_searches = [
                {"query": query, "count": count} 
                for query, count in sorted_queries[:limit]
            ]
            
            return popular_searches
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting popular searches: {str(e)}")
            raise DatabaseError(f"Failed to get popular searches: {str(e)}") 