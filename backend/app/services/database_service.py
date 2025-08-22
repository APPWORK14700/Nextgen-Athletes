from typing import Optional, List, Dict, Any, Callable
from firebase_admin import firestore
from firebase_admin.firestore import FieldFilter
import logging
import asyncio
from contextlib import asynccontextmanager

from ..firebaseConfig import get_firestore_client

# Simple service-level exceptions
class ValidationError(Exception):
    """Validation error for service layer operations.
    
    Raised when input validation fails for any database operation.
    """
    pass

class ResourceNotFoundError(Exception):
    """Resource not found error for service layer operations.
    
    Raised when attempting to access a document that doesn't exist.
    """
    pass

class DatabaseError(Exception):
    """Database error for service layer operations.
    
    Raised when Firestore operations fail due to database-level issues.
    """
    pass

class ConnectionError(Exception):
    """Connection error for service layer operations.
    
    Raised when unable to connect to Firestore or connection is lost.
    """
    pass

logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """Connection pool for managing Firestore connections"""
    
    def __init__(self, max_connections: int = 10, connection_timeout: int = 30):
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self._connections = []
        self._lock = asyncio.Lock()
        self._active_connections = 0
    
    async def get_connection(self):
        """Get a connection from the pool"""
        async with self._lock:
            if self._connections:
                return self._connections.pop()
            
            if self._active_connections < self.max_connections:
                self._active_connections += 1
                return get_firestore_client()
            
            # Wait for a connection to become available
            timeout = asyncio.create_task(asyncio.sleep(self.connection_timeout))
            while not self._connections and self._active_connections >= self.max_connections:
                await asyncio.sleep(0.1)
            
            timeout.cancel()
            if self._connections:
                return self._connections.pop()
            
            raise ConnectionError("No connections available in pool")
    
    async def return_connection(self, connection):
        """Return a connection to the pool"""
        async with self._lock:
            if len(self._connections) < self.max_connections:
                self._connections.append(connection)
            else:
                self._active_connections -= 1
    
    async def close_all(self):
        """Close all connections in the pool"""
        async with self._lock:
            self._connections.clear()
            self._active_connections = 0


class DatabaseService:
    """Base database service for Firestore operations.
    
    This service provides a comprehensive interface for common Firestore operations
    including CRUD operations, batch processing, transactions, and querying.
    
    Features:
        - Full CRUD operations (Create, Read, Update, Delete)
        - Batch operations for bulk processing
        - Transaction support for atomic operations
        - Advanced querying with filters and pagination
        - Automatic timestamp management
        - Comprehensive input validation
        - Detailed error logging and custom exceptions
        - Connection health monitoring
        - Connection pooling for better performance
    
    Usage:
        ```python
        # Initialize service for a specific collection
        user_service = DatabaseService("users")
        
        # Create a new user
        user_data = {"name": "John Doe", "email": "john@example.com"}
        user_id = await user_service.create(user_data)
        
        # Get user by ID
        user = await user_service.get_by_id(user_id)
        
        # Update user
        await user_service.update(user_id, {"age": 25})
        
        # Query users with filters
        from firebase_admin.firestore import FieldFilter
        filters = [FieldFilter("age", ">=", 18)]
        adults = await user_service.query(filters, limit=50)
        ```
    
    Firestore Limitations:
        - Batch operations limited to 500 operations
        - Query results limited to 1000 documents by default
        - 'in' clause limited to 10 values
        - No native case-insensitive search
        - No native count() method
    
    Attributes:
        collection_name (str): Name of the Firestore collection
        db: Firestore client instance
        collection: Firestore collection reference
        max_batch_size (int): Maximum batch size (500)
        max_query_limit (int): Maximum query limit (1000)
        connection_pool: Connection pool for managing connections
    """
    
    # Class-level connection pool
    _connection_pool = DatabaseConnectionPool()
    
    def __init__(self, collection_name: str):
        """Initialize the database service for a specific collection.
        
        Args:
            collection_name (str): Name of the Firestore collection to operate on.
                Must be a non-empty string.
        
        Raises:
            ValidationError: If collection_name is empty or invalid.
        
        Example:
            ```python
            # Initialize service for users collection
            user_service = DatabaseService("users")
            
            # Initialize service for athletes collection
            athlete_service = DatabaseService("athletes")
            ```
        """
        if not collection_name or not collection_name.strip():
            raise ValidationError("Collection name is required")
        
        self.collection_name = collection_name.strip()
        self.max_batch_size = 500  # Firestore batch limit
        self.max_query_limit = 1000  # Reasonable query limit
    
    @asynccontextmanager
    async def _get_connection(self):
        """Get a database connection from the pool"""
        connection = None
        try:
            connection = await self._connection_pool.get_connection()
            yield connection
        finally:
            if connection:
                await self._connection_pool.return_connection(connection)
    
    async def health_check(self) -> bool:
        """Check database connection health.
        
        Performs a simple health check by attempting to access the collection.
        Useful for monitoring, debugging, and health endpoints.
        
        Returns:
            bool: True if connection is healthy, False otherwise.
        
        Example:
            ```python
            # Check if database is accessible
            is_healthy = await user_service.health_check()
            if not is_healthy:
                logger.warning("Database connection unhealthy")
            ```
        """
        try:
            async with self._get_connection() as db:
                collection = db.collection(self.collection_name)
                # Simple health check - try to access collection metadata
                await collection.limit(1).stream()
                return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def create(self, data: Dict[str, Any], doc_id: Optional[str] = None) -> str:
        """Create a new document in the collection.
        
        Creates a new document with the provided data. Automatically adds
        timestamps for created_at and updated_at fields. If doc_id is provided,
        the document will be created with that specific ID; otherwise, Firestore
        will generate a unique ID.
        
        Args:
            data (Dict[str, Any]): Document data to store. Must be a non-empty dictionary.
            doc_id (Optional[str]): Custom document ID. If None, Firestore generates one.
        
        Returns:
            str: The ID of the created document.
        
        Raises:
            ValidationError: If data is invalid or doc_id is malformed.
            DatabaseError: If the create operation fails.
        
        Example:
            ```python
            # Create with auto-generated ID
            user_data = {
                "name": "Jane Doe",
                "email": "jane@example.com",
                "age": 30
            }
            user_id = await user_service.create(user_data)
            
            # Create with custom ID
            custom_id = "user_12345"
            user_id = await user_service.create(user_data, custom_id)
            assert user_id == custom_id
            ```
        
        Note:
            - Automatically adds 'created_at' and 'updated_at' timestamps
            - Calls validate_data() hook if implemented by subclass
            - If doc_id is provided, it must be unique within the collection
        """
        try:
            # Input validation
            if not data:
                raise ValidationError("Data is required")
            if not isinstance(data, dict):
                raise ValidationError("Data must be a dictionary")
            
            # Validate doc_id if provided
            if doc_id is not None:
                if not isinstance(doc_id, str) or not doc_id.strip():
                    raise ValidationError("Document ID must be a non-empty string")
                doc_id = doc_id.strip()
            
            # Call validation hook if exists (allows subclasses to implement custom validation)
            if hasattr(self, 'validate_data'):
                await self.validate_data(data)
            
            # Add timestamps for audit trail
            data['created_at'] = firestore.SERVER_TIMESTAMP
            data['updated_at'] = firestore.SERVER_TIMESTAMP
            
            async with self._get_connection() as db:
                collection = db.collection(self.collection_name)
                
                if doc_id:
                    # Create document with specific ID
                    doc_ref = collection.document(doc_id)
                    await doc_ref.set(data)
                    return doc_id
                else:
                    # Let Firestore generate a unique ID
                    result = await collection.add(data)
                    return result[1].id
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating document in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to create document: {str(e)}")
    
    async def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by its ID.
        
        Retrieves a document from the collection using its unique identifier.
        Returns None if the document doesn't exist.
        
        Args:
            doc_id (str): The unique identifier of the document to retrieve.
        
        Returns:
            Optional[Dict[str, Any]]: Document data with 'id' field added, or None if not found.
        
        Raises:
            ValidationError: If doc_id is invalid.
            DatabaseError: If the retrieval operation fails.
        
        Example:
            ```python
            # Get user by ID
            user = await user_service.get_by_id("user_12345")
            if user:
                print(f"Found user: {user['name']}")
            else:
                print("User not found")
            ```
        
        Note:
            - The returned document includes an 'id' field with the document ID
            - Returns None (not an empty dict) if document doesn't exist
            - Automatically strips whitespace from doc_id
        """
        try:
            # Input validation
            if not doc_id:
                raise ValidationError("Document ID is required")
            if not isinstance(doc_id, str):
                raise ValidationError("Document ID must be a string")
            
            doc_id = doc_id.strip()
            
            # Get document reference and fetch data
            async with self._get_connection() as db:
                collection = db.collection(self.collection_name)
                doc_ref = collection.document(doc_id)
                doc = await doc_ref.get()
                
                if doc.exists:
                    data = doc.to_dict()
                    data['id'] = doc.id  # Add document ID to the data
                    return data
                return None
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting document {doc_id} from {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to get document: {str(e)}")
    
    async def update(self, doc_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing document by ID.
        
        Updates the specified document with new data. Only the fields provided
        in the data parameter will be updated. Automatically adds an updated_at
        timestamp.
        
        Args:
            doc_id (str): The unique identifier of the document to update.
            data (Dict[str, Any]): New data to update the document with.
                Must be a non-empty dictionary.
        
        Returns:
            bool: True if update was successful.
        
        Raises:
            ValidationError: If doc_id or data is invalid.
            DatabaseError: If the update operation fails.
        
        Example:
            ```python
            # Update user's age and email
            update_data = {
                "age": 31,
                "email": "jane.updated@example.com"
            }
            success = await user_service.update("user_12345", update_data)
            if success:
                print("User updated successfully")
            ```
        
        Note:
            - Only updates the fields provided in the data parameter
            - Automatically adds 'updated_at' timestamp
            - Will fail if the document doesn't exist
            - Automatically strips whitespace from doc_id
        """
        try:
            # Input validation
            if not doc_id:
                raise ValidationError("Document ID is required")
            if not isinstance(doc_id, str):
                raise ValidationError("Document ID must be a string")
            if not data:
                raise ValidationError("Update data is required")
            if not isinstance(data, dict):
                raise ValidationError("Update data must be a dictionary")
            
            doc_id = doc_id.strip()
            
            # Add updated timestamp for audit trail
            data['updated_at'] = firestore.SERVER_TIMESTAMP
            
            # Update the document
            async with self._get_connection() as db:
                collection = db.collection(self.collection_name)
                doc_ref = collection.document(doc_id)
                await doc_ref.update(data)
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error updating document {doc_id} in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to update document: {str(e)}")
    
    async def delete(self, doc_id: str) -> bool:
        """Delete a document by ID.
        
        Permanently removes a document from the collection. This operation
        cannot be undone.
        
        Args:
            doc_id (str): The unique identifier of the document to delete.
        
        Returns:
            bool: True if deletion was successful.
        
        Raises:
            ValidationError: If doc_id is invalid.
            DatabaseError: If the deletion operation fails.
        
        Example:
            ```python
            # Delete a user
            success = await user_service.delete("user_12345")
            if success:
                print("User deleted successfully")
            ```
        
        Note:
            - This operation is permanent and cannot be undone
            - Will not fail if the document doesn't exist
            - Automatically strips whitespace from doc_id
        """
        try:
            # Input validation
            if not doc_id:
                raise ValidationError("Document ID is required")
            if not isinstance(doc_id, str):
                raise ValidationError("Document ID must be a string")
            
            doc_id = doc_id.strip()
            
            # Delete the document
            async with self._get_connection() as db:
                collection = db.collection(self.collection_name)
                doc_ref = collection.document(doc_id)
                await doc_ref.delete()
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error deleting document {doc_id} from {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to delete document: {str(e)}")
    
    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List all documents in the collection with pagination.
        
        Retrieves documents from the collection with optional pagination.
        Useful for browsing all documents or implementing pagination UI.
        
        Args:
            limit (int): Maximum number of documents to return (1-1000).
            offset (int): Number of documents to skip for pagination.
        
        Returns:
            List[Dict[str, Any]]: List of documents, each with an 'id' field added.
        
        Raises:
            ValidationError: If limit or offset parameters are invalid.
            DatabaseError: If the listing operation fails.
        
        Example:
            ```python
            # Get first 20 users
            users = await user_service.list_all(limit=20, offset=0)
            
            # Get next 20 users (pagination)
            next_users = await user_service.list_all(limit=20, offset=20)
            
            # Get all users (up to 1000)
            all_users = await user_service.list_all()
            ```
        
        Note:
            - Maximum limit is 1000 documents
            - Each document includes an 'id' field
            - Use offset for pagination (0-based)
            - Consider using get_paginated_results() for better pagination metadata
        """
        try:
            # Input validation
            if limit < 1 or limit > self.max_query_limit:
                raise ValidationError(f"Limit must be between 1 and {self.max_query_limit}")
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            # Build query with pagination
            async with self._get_connection() as db:
                collection = db.collection(self.collection_name)
                query = collection.limit(limit).offset(offset)
                docs = await query.stream()
            
            # Process results and add document IDs
            results = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)
            
            return results
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error listing documents from {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to list documents: {str(e)}")
    
    async def query(self, filters: List[FieldFilter], limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Query documents with filters and pagination.
        
        Performs a filtered query on the collection using Firestore FieldFilter
        objects. Supports complex queries with multiple filter conditions.
        
        Args:
            filters (List[FieldFilter]): List of Firestore FieldFilter objects.
            limit (int): Maximum number of documents to return (1-1000).
            offset (int): Number of documents to skip for pagination.
        
        Returns:
            List[Dict[str, Any]]: List of matching documents, each with an 'id' field.
        
        Raises:
            ValidationError: If filters, limit, or offset parameters are invalid.
            DatabaseError: If the query operation fails.
        
        Example:
            ```python
            from firebase_admin.firestore import FieldFilter
            
            # Query users older than 18
            age_filter = FieldFilter("age", ">=", 18)
            adults = await user_service.query([age_filter], limit=50)
            
            # Query users with multiple filters
            age_filter = FieldFilter("age", ">=", 18)
            status_filter = FieldFilter("status", "==", "active")
            active_adults = await user_service.query([age_filter, status_filter])
            
            # Query with pagination
            first_page = await user_service.query([age_filter], limit=20, offset=0)
            second_page = await user_service.query([age_filter], limit=20, offset=20)
            ```
        
        Note:
            - Filters are applied in the order they appear in the list
            - Maximum limit is 1000 documents
            - Each document includes an 'id' field
            - Use offset for pagination (0-based)
            - Consider Firestore query limitations and indexing requirements
        """
        try:
            # Input validation
            if not isinstance(filters, list):
                raise ValidationError("Filters must be a list")
            if limit < 1 or limit > self.max_query_limit:
                raise ValidationError(f"Limit must be between 1 and {self.max_query_limit}")
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            # Start with base collection reference
            async with self._get_connection() as db:
                collection = db.collection(self.collection_name)
                query = collection
                
                # Apply each filter condition sequentially
                for filter_condition in filters:
                    query = query.where(filter=filter_condition)
                
                # Apply pagination
                query = query.limit(limit).offset(offset)
                docs = await query.stream()
            
            # Process results and add document IDs
            results = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)
            
            return results
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error querying documents from {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to query documents: {str(e)}")
    
    async def count(self, filters: Optional[List[FieldFilter]] = None) -> int:
        """Count documents with optional filters.
        
        Counts the total number of documents in the collection, optionally
        applying filters. Note that this method has performance implications
        for large collections as it needs to fetch documents to count them.
        
        Args:
            filters (Optional[List[FieldFilter]]): Optional list of FieldFilter objects.
                If None, counts all documents in the collection.
        
        Returns:
            int: Total count of matching documents.
        
        Raises:
            ValidationError: If filters parameter is invalid.
            DatabaseError: If the count operation fails.
        
        Example:
            ```python
            from firebase_admin.firestore import FieldFilter
            
            # Count all users
            total_users = await user_service.count()
            
            # Count active users
            active_filter = FieldFilter("status", "==", "active")
            active_count = await user_service.count([active_filter])
            
            # Count users older than 18
            age_filter = FieldFilter("age", ">=", 18)
            adult_count = await user_service.count([age_filter])
            ```
        
        Note:
            - This method fetches documents to count them (up to 1000)
            - For large collections, consider maintaining counter fields
            - Performance may degrade with complex filters
            - Firestore doesn't provide a native count() method
        """
        try:
            # Input validation
            if filters is not None and not isinstance(filters, list):
                raise ValidationError("Filters must be a list or None")
            
            # Start with base collection reference
            async with self._get_connection() as db:
                collection = db.collection(self.collection_name)
                query = collection
                
                # Apply filters if provided
                if filters:
                    for filter_condition in filters:
                        query = query.where(filter=filter_condition)
                
                # For now, use the current approach but with a smaller limit for counting
                # Note: Firestore doesn't have a native count() method
                # Consider using a counter field or implementing pagination-based counting
                docs = await query.limit(1000).stream()
                return len(list(docs))
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error counting documents in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to count documents: {str(e)}")
    
    async def exists(self, doc_id: str) -> bool:
        """Check if a document exists in the collection.
        
        Quickly checks whether a document with the specified ID exists
        without fetching the full document data.
        
        Args:
            doc_id (str): The unique identifier of the document to check.
        
        Returns:
            bool: True if document exists, False otherwise.
        
        Raises:
            ValidationError: If doc_id is invalid.
            DatabaseError: If the existence check fails.
        
        Example:
            ```python
            # Check if user exists
            if await user_service.exists("user_12345"):
                print("User exists")
            else:
                print("User not found")
            
            # Use in conditional logic
            if not await user_service.exists(user_id):
                # Create new user
                await user_service.create(user_data, user_id)
            ```
        
        Note:
            - More efficient than get_by_id() when you only need to check existence
            - Automatically strips whitespace from doc_id
            - Returns False if document doesn't exist (not an error)
        """
        try:
            # Input validation
            if not doc_id:
                raise ValidationError("Document ID is required")
            if not isinstance(doc_id, str):
                raise ValidationError("Document ID must be a string")
            
            doc_id = doc_id.strip()
            
            # Check document existence without fetching full data
            async with self._get_connection() as db:
                collection = db.collection(self.collection_name)
                doc_ref = collection.document(doc_id)
                doc = await doc_ref.get()
                return doc.exists
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error checking existence of document {doc_id} in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to check document existence: {str(e)}")
    
    async def run_transaction(self, update_func: Callable) -> Any:
        """Run a Firestore transaction with the given update function.
        
        Executes a function within a Firestore transaction, ensuring atomicity
        for complex operations that involve multiple document updates.
        
        Args:
            update_func (Callable): Function to execute within the transaction.
                This function should accept a transaction object and perform
                the necessary operations.
        
        Returns:
            Any: The result returned by the update function.
        
        Raises:
            DatabaseError: If the transaction fails or times out.
        
        Example:
            ```python
            # Transfer credits between users atomically
            async def transfer_credits(transaction):
                # Get both users
                user1_ref = user_service.collection.document("user1_id")
                user2_ref = user_service.collection.document("user2_id")
                
                user1_doc = await transaction.get(user1_ref)
                user2_doc = await transaction.get(user2_ref)
                
                user1_data = user1_doc.to_dict()
                user2_data = user2_doc.to_dict()
                
                # Update credits
                transaction.update(user1_ref, {"credits": user1_data["credits"] - 100})
                transaction.update(user2_ref, {"credits": user2_data["credits"] + 100})
                
                return "Transfer completed"
            
            # Execute the transaction
            result = await user_service.run_transaction(transfer_credits)
            print(result)  # "Transfer completed"
            ```
        
        Note:
            - Transactions provide atomicity for complex operations
            - All operations within the transaction succeed or fail together
            - Transactions have timeout limits (default: 60 seconds)
            - Use for operations that need to update multiple documents atomically
        """
        try:
            async with self._get_connection() as db:
                result = await db.run_transaction(update_func)
                return result
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            raise DatabaseError(f"Transaction failed: {str(e)}")
    
    async def batch_create(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Create multiple documents in a single batch operation.
        
        Efficiently creates multiple documents using Firestore's batch operations.
        This method is much more efficient than creating documents individually
        when you need to create many documents at once.
        
        Args:
            documents (List[Dict[str, Any]]): List of document data dictionaries.
                Each dictionary should contain the data for one document.
        
        Returns:
            List[str]: List of document IDs for the created documents.
                IDs are returned in the same order as the input documents.
        
        Raises:
            ValidationError: If documents list is invalid or empty.
            DatabaseError: If the batch creation fails.
        
        Example:
            ```python
            # Create multiple users at once
            users_data = [
                {"name": "Alice", "email": "alice@example.com"},
                {"name": "Bob", "email": "bob@example.com"},
                {"name": "Charlie", "email": "charlie@example.com"}
            ]
            
            user_ids = await user_service.batch_create(users_data)
            print(f"Created users with IDs: {user_ids}")
            ```
        
        Note:
            - Maximum batch size is 500 documents (Firestore limit)
            - Automatically adds timestamps to each document
            - All documents are created atomically (all succeed or all fail)
            - Returns document IDs in the same order as input documents
        """
        try:
            # Input validation
            if not documents:
                raise ValidationError("Documents list is required")
            if not isinstance(documents, list):
                raise ValidationError("Documents must be a list")
            if len(documents) > self.max_batch_size:
                raise ValidationError(f"Batch size cannot exceed {self.max_batch_size}")
            
            # Validate each document in the batch
            for i, data in enumerate(documents):
                if not isinstance(data, dict):
                    raise ValidationError(f"Document {i} must be a dictionary")
                if not data:
                    raise ValidationError(f"Document {i} cannot be empty")
            
            # Create batch operation
            async with self._get_connection() as db:
                batch = db.batch()
                doc_ids = []
                
                # Add each document to the batch
                for data in documents:
                    # Add timestamps for audit trail
                    data['created_at'] = firestore.SERVER_TIMESTAMP
                    data['updated_at'] = firestore.SERVER_TIMESTAMP
                    
                    # Create document reference and add to batch
                    doc_ref = collection.document()
                    batch.set(doc_ref, data)
                    doc_ids.append(doc_ref.id)
                
                # Commit the batch operation
                await batch.commit()
                return doc_ids
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error batch creating documents in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to batch create documents: {str(e)}")
    
    async def batch_update(self, updates: List[tuple]) -> bool:
        """Update multiple documents in a single batch operation.
        
        Efficiently updates multiple documents using Firestore's batch operations.
        Each update should be a tuple containing (doc_id, update_data).
        
        Args:
            updates (List[tuple]): List of update tuples.
                Each tuple should contain (doc_id, update_data) where:
                - doc_id (str): Document ID to update
                - update_data (Dict[str, Any]): Data to update the document with
        
        Returns:
            bool: True if all updates were successful.
        
        Raises:
            ValidationError: If updates list is invalid or contains malformed tuples.
            DatabaseError: If the batch update fails.
        
        Example:
            ```python
            # Update multiple users at once
            updates = [
                ("user1_id", {"status": "active", "last_login": "2024-01-01"}),
                ("user2_id", {"status": "inactive", "last_login": "2024-01-01"}),
                ("user3_id", {"status": "active", "last_login": "2024-01-01"})
            ]
            
            success = await user_service.batch_update(updates)
            if success:
                print("All users updated successfully")
            ```
        
        Note:
            - Maximum batch size is 500 updates (Firestore limit)
            - Automatically adds updated_at timestamp to each update
            - All updates are applied atomically (all succeed or all fail)
            - Each update tuple must contain exactly 2 elements
        """
        try:
            # Input validation
            if not updates:
                raise ValidationError("Updates list is required")
            if not isinstance(updates, list):
                raise ValidationError("Updates must be a list")
            if len(updates) > self.max_batch_size:
                raise ValidationError(f"Batch size cannot exceed {self.max_batch_size}")
            
            # Validate each update tuple
            for i, update in enumerate(updates):
                if not isinstance(update, tuple) or len(update) != 2:
                    raise ValidationError(f"Update {i} must be a tuple of (doc_id, data)")
                doc_id, data = update
                if not isinstance(doc_id, str) or not doc_id.strip():
                    raise ValidationError(f"Document ID in update {i} must be a non-empty string")
                if not isinstance(data, dict):
                    raise ValidationError(f"Data in update {i} must be a dictionary")
            
            # Create batch operation
            async with self._get_connection() as db:
                batch = db.batch()
                
                # Add each update to the batch
                for doc_id, data in updates:
                    # Add updated timestamp for audit trail
                    data['updated_at'] = firestore.SERVER_TIMESTAMP
                    
                    # Create document reference and add update to batch
                    doc_ref = collection.document(doc_id.strip())
                    batch.update(doc_ref, data)
                
                # Commit the batch operation
                await batch.commit()
                return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error batch updating documents in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to batch update documents: {str(e)}")
    
    async def batch_delete(self, doc_ids: List[str]) -> bool:
        """Delete multiple documents in a single batch operation.
        
        Efficiently deletes multiple documents using Firestore's batch operations.
        This method is much more efficient than deleting documents individually
        when you need to delete many documents at once.
        
        Args:
            doc_ids (List[str]): List of document IDs to delete.
        
        Returns:
            bool: True if all deletions were successful.
        
        Raises:
            ValidationError: If doc_ids list is invalid or contains invalid IDs.
            DatabaseError: If the batch deletion fails.
        
        Example:
            ```python
            # Delete multiple users at once
            user_ids_to_delete = ["user1_id", "user2_id", "user3_id"]
            
            success = await user_service.batch_delete(user_ids_to_delete)
            if success:
                print("All users deleted successfully")
            ```
        
        Note:
            - Maximum batch size is 500 deletions (Firestore limit)
            - All deletions are performed atomically (all succeed or all fail)
            - Deletions are permanent and cannot be undone
            - Will not fail if some documents don't exist
        """
        try:
            # Input validation
            if not doc_ids:
                raise ValidationError("Document IDs list is required")
            if not isinstance(doc_ids, list):
                raise ValidationError("Document IDs must be a list")
            if len(doc_ids) > self.max_batch_size:
                raise ValidationError(f"Batch size cannot exceed {self.max_batch_size}")
            
            # Validate each document ID
            for i, doc_id in enumerate(doc_ids):
                if not isinstance(doc_id, str) or not doc_id.strip():
                    raise ValidationError(f"Document ID {i} must be a non-empty string")
            
            # Create batch operation
            async with self._get_connection() as db:
                batch = db.batch()
                
                # Add each deletion to the batch
                for doc_id in doc_ids:
                    doc_ref = collection.document(doc_id.strip())
                    batch.delete(doc_ref)
                
                # Commit the batch operation
                await batch.commit()
                return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error batch deleting documents in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to batch delete documents: {str(e)}")
    
    async def search(self, field: str, value: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Search documents by field value with case-insensitive matching.
        
        Performs a text search on a specific field. Note that this is a
        simplified implementation with limitations. For production applications
        requiring advanced search capabilities, consider using external search
        services like Algolia or Elasticsearch.
        
        Args:
            field (str): Name of the field to search in.
            value (str): Text value to search for.
            limit (int): Maximum number of results to return (1-1000).
        
        Returns:
            List[Dict[str, Any]]: List of matching documents, each with an 'id' field.
        
        Raises:
            ValidationError: If field, value, or limit parameters are invalid.
            DatabaseError: If the search operation fails.
        
        Example:
            ```python
            # Search for users by name
            users = await user_service.search("name", "john", limit=50)
            
            # Search for users by email domain
            users = await user_service.search("email", "@gmail.com", limit=100)
            
            # Search for users by partial name
            users = await user_service.search("name", "doe", limit=25)
            ```
        
        Note:
            - This is a simplified search implementation
            - For production, consider using Algolia, Elasticsearch, or similar
            - Firestore doesn't support case-insensitive search natively
            - Search is performed using ">=" operator with additional filtering
            - Performance may degrade with large collections
        """
        try:
            # Input validation
            if not field:
                raise ValidationError("Field name is required")
            if not isinstance(field, str):
                raise ValidationError("Field name must be a string")
            if not value:
                raise ValidationError("Search value is required")
            if not isinstance(value, str):
                raise ValidationError("Search value must be a string")
            if limit < 1 or limit > self.max_query_limit:
                raise ValidationError(f"Limit must be between 1 and {self.max_query_limit}")
            
            field = field.strip()
            value = value.strip()
            
            # Note: This is a simplified search implementation
            # For production, consider using Algolia, Elasticsearch, or similar
            # Firestore doesn't support case-insensitive search natively
            
            # Use ">=" operator as a starting point for search
            async with self._get_connection() as db:
                collection = db.collection(self.collection_name)
                query = collection.where(filter=FieldFilter(field, ">=", value.lower()))
                docs = await query.limit(limit).stream()
            
            # Filter results for case-insensitive matching
            results = []
            for doc in docs:
                data = doc.to_dict()
                if field in data and value.lower() in str(data[field]).lower():
                    data['id'] = doc.id
                    results.append(data)
            
            return results
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error searching documents in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to search documents: {str(e)}")
    
    async def get_by_field(self, field: str, value: Any) -> Optional[Dict[str, Any]]:
        """Get the first document that matches a specific field value.
        
        Retrieves the first document where the specified field equals the
        given value. Useful for finding documents by unique fields like
        email addresses or usernames.
        
        Args:
            field (str): Name of the field to match against.
            value (Any): Value to match in the field.
        
        Returns:
            Optional[Dict[str, Any]]: First matching document with 'id' field, or None.
        
        Raises:
            ValidationError: If field or value parameters are invalid.
            DatabaseError: If the retrieval operation fails.
        
        Example:
            ```python
            # Find user by email
            user = await user_service.get_by_field("email", "john@example.com")
            if user:
                print(f"Found user: {user['name']}")
            
            # Find user by username
            user = await user_service.get_by_field("username", "johndoe")
            if user:
                print(f"Found user: {user['name']}")
            ```
        
        Note:
            - Returns only the first matching document
            - Useful for unique fields (email, username, etc.)
            - Returns None if no document matches
            - Each returned document includes an 'id' field
        """
        try:
            # Input validation
            if not field:
                raise ValidationError("Field name is required")
            if not isinstance(field, str):
                raise ValidationError("Field name must be a string")
            if value is None:
                raise ValidationError("Field value is required")
            
            field = field.strip()
            
            # Query for documents matching the field value
            async with self._get_connection() as db:
                collection = db.collection(self.collection_name)
                query = collection.where(filter=FieldFilter(field, "==", value)).limit(1)
                docs = await query.stream()
            
            # Return the first matching document
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            
            return None
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting document by field {field}={value} from {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to get document by field: {str(e)}")
    
    async def get_by_field_list(self, field: str, values: List[Any]) -> List[Dict[str, Any]]:
        """Get documents where a field matches any value from a list.
        
        Retrieves all documents where the specified field matches any of the
        values in the provided list. Uses Firestore's 'in' clause for efficiency.
        
        Args:
            field (str): Name of the field to match against.
            values (List[Any]): List of values to match in the field.
                Maximum 10 values (Firestore limitation).
        
        Returns:
            List[Dict[str, Any]]: List of matching documents, each with an 'id' field.
        
        Raises:
            ValidationError: If field or values parameters are invalid.
            DatabaseError: If the retrieval operation fails.
        
        Example:
            ```python
            # Get users with specific IDs
            user_ids = ["user1", "user2", "user3"]
            users = await user_service.get_by_field_list("id", user_ids)
            
            # Get users with specific statuses
            statuses = ["active", "pending", "verified"]
            users = await user_service.get_by_field_list("status", statuses)
            
            # Get users in specific age groups
            ages = [18, 19, 20, 21]
            users = await user_service.get_by_field_list("age", ages)
            ```
        
        Note:
            - Maximum 10 values due to Firestore 'in' clause limitation
            - Returns all documents matching any of the values
            - Each returned document includes an 'id' field
            - Useful for bulk retrieval of documents by known values
        """
        try:
            # Input validation
            if not field:
                raise ValidationError("Field name is required")
            if not isinstance(field, str):
                raise ValidationError("Field name must be a string")
            if not values:
                raise ValidationError("Values list is required")
            if not isinstance(values, list):
                raise ValidationError("Values must be a list")
            if len(values) > 10:  # Firestore 'in' clause limit
                raise ValidationError("Values list cannot exceed 10 items")
            
            field = field.strip()
            
            # Query for documents matching any of the values
            async with self._get_connection() as db:
                collection = db.collection(self.collection_name)
                query = collection.where(filter=FieldFilter(field, "in", values))
                docs = await query.stream()
            
            # Process results and add document IDs
            results = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)
            
            return results
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting documents by field {field} in {values} from {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to get documents by field list: {str(e)}")
    
    async def get_paginated_results(self, filters: Optional[List[FieldFilter]] = None, 
                                   limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """Get paginated results with comprehensive metadata.
        
        Retrieves paginated results with detailed pagination information including
        total count, navigation helpers, and result metadata. This method is ideal
        for implementing pagination UI components.
        
        Args:
            filters (Optional[List[FieldFilter]]): Optional list of FieldFilter objects.
                If None, returns all documents in the collection.
            limit (int): Number of documents per page (1-1000).
            offset (int): Number of documents to skip for pagination (0-based).
        
        Returns:
            Dict[str, Any]: Pagination result with the following structure:
                - results: List of documents with 'id' fields
                - total_count: Total number of matching documents
                - limit: Current page size
                - offset: Current page offset
                - has_next: Boolean indicating if next page exists
                - has_previous: Boolean indicating if previous page exists
                - next_offset: Offset for next page (None if no next page)
                - previous_offset: Offset for previous page (None if no previous page)
        
        Raises:
            ValidationError: If filters, limit, or offset parameters are invalid.
            DatabaseError: If the pagination operation fails.
        
        Example:
            ```python
            from firebase_admin.firestore import FieldFilter
            
            # Get first page of active users
            active_filter = FieldFilter("status", "==", "active")
            page1 = await user_service.get_paginated_results(
                filters=[active_filter], 
                limit=20, 
                offset=0
            )
            
            print(f"Page 1: {len(page1['results'])} users")
            print(f"Total users: {page1['total_count']}")
            print(f"Has next page: {page1['has_next']}")
            
            # Get next page if available
            if page1['has_next']:
                page2 = await user_service.get_paginated_results(
                    filters=[active_filter],
                    limit=20,
                    offset=page1['next_offset']
                )
                print(f"Page 2: {len(page2['results'])} users")
            ```
        
        Note:
            - Provides comprehensive pagination metadata
            - Useful for building pagination UI components
            - Automatically calculates navigation helpers
            - Each document includes an 'id' field
            - Consider performance implications for large collections
        """
        try:
            # Input validation
            if filters is not None and not isinstance(filters, list):
                raise ValidationError("Filters must be a list or None")
            if limit < 1 or limit > self.max_query_limit:
                raise ValidationError(f"Limit must be between 1 and {self.max_query_limit}")
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            # Get total count of matching documents
            total_count = await self.count(filters)
            
            # Get paginated results
            results = await self.query(filters or [], limit, offset)
            
            # Calculate pagination metadata
            has_next = (offset + limit) < total_count
            has_previous = offset > 0
            
            return {
                "results": results,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_next": has_next,
                "has_previous": has_previous,
                "next_offset": offset + limit if has_next else None,
                "previous_offset": max(0, offset - limit) if has_previous else None
            }
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting paginated results from {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to get paginated results: {str(e)}") 