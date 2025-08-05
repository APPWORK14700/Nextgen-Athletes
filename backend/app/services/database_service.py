from typing import Optional, List, Dict, Any, TypeVar, Generic
from firebase_admin import firestore
from firebase_admin.firestore import FieldFilter
import logging
from datetime import datetime
import json
import asyncio

from ..firebaseConfig import get_firestore_client
# Simple service-level exceptions
class ValidationError(Exception):
    """Validation error for service layer"""
    pass

class ResourceNotFoundError(Exception):
    """Resource not found error for service layer"""
    pass

class DatabaseError(Exception):
    """Database error for service layer"""
    pass

class ConnectionError(Exception):
    """Connection error for service layer"""
    pass

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DatabaseService:
    """Base database service for Firestore operations"""
    
    def __init__(self, collection_name: str):
        if not collection_name or not collection_name.strip():
            raise ValidationError("Collection name is required")
        
        self.collection_name = collection_name.strip()
        self.db = get_firestore_client()
        self.collection = self.db.collection(self.collection_name)
        self.max_batch_size = 500  # Firestore batch limit
        self.max_query_limit = 1000  # Reasonable query limit
    
    async def create(self, data: Dict[str, Any], doc_id: Optional[str] = None) -> str:
        """Create a new document"""
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
            
            # Add timestamps
            data['created_at'] = firestore.SERVER_TIMESTAMP
            data['updated_at'] = firestore.SERVER_TIMESTAMP
            
            if doc_id:
                doc_ref = self.collection.document(doc_id)
                doc_ref.set(data)
                return doc_id
            else:
                result = self.collection.add(data)
                return result[1].id
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating document in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to create document: {str(e)}")
    
    async def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        try:
            # Input validation
            if not doc_id:
                raise ValidationError("Document ID is required")
            if not isinstance(doc_id, str):
                raise ValidationError("Document ID must be a string")
            
            doc_id = doc_id.strip()
            
            doc = self.collection.document(doc_id).get()
            
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            return None
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting document {doc_id} from {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to get document: {str(e)}")
    
    async def update(self, doc_id: str, data: Dict[str, Any]) -> bool:
        """Update document by ID"""
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
            
            # Add updated timestamp
            data['updated_at'] = firestore.SERVER_TIMESTAMP
            
            doc_ref = self.collection.document(doc_id)
            doc_ref.update(data)
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error updating document {doc_id} in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to update document: {str(e)}")
    
    async def delete(self, doc_id: str) -> bool:
        """Delete document by ID"""
        try:
            # Input validation
            if not doc_id:
                raise ValidationError("Document ID is required")
            if not isinstance(doc_id, str):
                raise ValidationError("Document ID must be a string")
            
            doc_id = doc_id.strip()
            
            self.collection.document(doc_id).delete()
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error deleting document {doc_id} from {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to delete document: {str(e)}")
    
    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List all documents with pagination"""
        try:
            # Input validation
            if limit < 1 or limit > self.max_query_limit:
                raise ValidationError(f"Limit must be between 1 and {self.max_query_limit}")
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            query = self.collection.limit(limit).offset(offset)
            docs = query.stream()
            
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
        """Query documents with filters"""
        try:
            # Input validation
            if not isinstance(filters, list):
                raise ValidationError("Filters must be a list")
            if limit < 1 or limit > self.max_query_limit:
                raise ValidationError(f"Limit must be between 1 and {self.max_query_limit}")
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            query = self.collection
            
            # Apply filters
            for filter_condition in filters:
                query = query.where(filter=filter_condition)
            
            # Apply pagination
            query = query.limit(limit).offset(offset)
            docs = query.stream()
            
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
        """Count documents with optional filters"""
        try:
            # Input validation
            if filters is not None and not isinstance(filters, list):
                raise ValidationError("Filters must be a list or None")
            
            query = self.collection
            
            if filters:
                for filter_condition in filters:
                    query = query.where(filter=filter_condition)
            
            # Use a reasonable limit for counting
            docs = query.limit(self.max_query_limit).stream()
            return len(list(docs))
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error counting documents in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to count documents: {str(e)}")
    
    async def exists(self, doc_id: str) -> bool:
        """Check if document exists"""
        try:
            # Input validation
            if not doc_id:
                raise ValidationError("Document ID is required")
            if not isinstance(doc_id, str):
                raise ValidationError("Document ID must be a string")
            
            doc_id = doc_id.strip()
            
            doc = self.collection.document(doc_id).get()
            return doc.exists
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error checking existence of document {doc_id} in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to check document existence: {str(e)}")
    
    async def batch_create(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Create multiple documents in a batch"""
        try:
            # Input validation
            if not documents:
                raise ValidationError("Documents list is required")
            if not isinstance(documents, list):
                raise ValidationError("Documents must be a list")
            if len(documents) > self.max_batch_size:
                raise ValidationError(f"Batch size cannot exceed {self.max_batch_size}")
            
            # Validate each document
            for i, data in enumerate(documents):
                if not isinstance(data, dict):
                    raise ValidationError(f"Document {i} must be a dictionary")
                if not data:
                    raise ValidationError(f"Document {i} cannot be empty")
            
            batch = self.db.batch()
            doc_ids = []
            
            for data in documents:
                # Add timestamps
                data['created_at'] = firestore.SERVER_TIMESTAMP
                data['updated_at'] = firestore.SERVER_TIMESTAMP
                
                doc_ref = self.collection.document()
                batch.set(doc_ref, data)
                doc_ids.append(doc_ref.id)
            
            batch.commit()
            return doc_ids
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error batch creating documents in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to batch create documents: {str(e)}")
    
    async def batch_update(self, updates: List[tuple]) -> bool:
        """Update multiple documents in a batch"""
        try:
            # Input validation
            if not updates:
                raise ValidationError("Updates list is required")
            if not isinstance(updates, list):
                raise ValidationError("Updates must be a list")
            if len(updates) > self.max_batch_size:
                raise ValidationError(f"Batch size cannot exceed {self.max_batch_size}")
            
            # Validate each update
            for i, update in enumerate(updates):
                if not isinstance(update, tuple) or len(update) != 2:
                    raise ValidationError(f"Update {i} must be a tuple of (doc_id, data)")
                doc_id, data = update
                if not isinstance(doc_id, str) or not doc_id.strip():
                    raise ValidationError(f"Document ID in update {i} must be a non-empty string")
                if not isinstance(data, dict):
                    raise ValidationError(f"Data in update {i} must be a dictionary")
            
            batch = self.db.batch()
            
            for doc_id, data in updates:
                # Add updated timestamp
                data['updated_at'] = firestore.SERVER_TIMESTAMP
                
                doc_ref = self.collection.document(doc_id.strip())
                batch.update(doc_ref, data)
            
            batch.commit()
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error batch updating documents in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to batch update documents: {str(e)}")
    
    async def batch_delete(self, doc_ids: List[str]) -> bool:
        """Delete multiple documents in a batch"""
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
            
            batch = self.db.batch()
            
            for doc_id in doc_ids:
                doc_ref = self.collection.document(doc_id.strip())
                batch.delete(doc_ref)
            
            batch.commit()
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error batch deleting documents in {self.collection_name}: {e}")
            raise DatabaseError(f"Failed to batch delete documents: {str(e)}")
    
    async def search(self, field: str, value: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Search documents by field value (case-insensitive)"""
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
            
            query = self.collection.where(filter=FieldFilter(field, ">=", value.lower()))
            docs = query.limit(limit).stream()
            
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
        """Get first document by field value"""
        try:
            # Input validation
            if not field:
                raise ValidationError("Field name is required")
            if not isinstance(field, str):
                raise ValidationError("Field name must be a string")
            if value is None:
                raise ValidationError("Field value is required")
            
            field = field.strip()
            
            query = self.collection.where(filter=FieldFilter(field, "==", value)).limit(1)
            docs = query.stream()
            
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
        """Get documents by field values (in clause)"""
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
            
            query = self.collection.where(filter=FieldFilter(field, "in", values))
            docs = query.stream()
            
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
        """Get paginated results with metadata"""
        try:
            # Input validation
            if filters is not None and not isinstance(filters, list):
                raise ValidationError("Filters must be a list or None")
            if limit < 1 or limit > self.max_query_limit:
                raise ValidationError(f"Limit must be between 1 and {self.max_query_limit}")
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            # Get total count
            total_count = await self.count(filters)
            
            # Get results
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