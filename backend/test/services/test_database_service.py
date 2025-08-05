import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from firebase_admin.firestore import FieldFilter

from app.services.database_service import DatabaseService
# Import the exceptions from the service file
from app.services.database_service import ValidationError, ResourceNotFoundError, DatabaseError, ConnectionError


class TestDatabaseService:
    """Test cases for DatabaseService"""
    
    @pytest.fixture
    def database_service(self):
        service = DatabaseService.__new__(DatabaseService)
        service.collection_name = "test_collection"
        service.db = MagicMock()
        service.collection = MagicMock()
        service.max_batch_size = 500
        service.max_query_limit = 1000
        return service
    
    @pytest.fixture
    def mock_document_data(self):
        return {
            "id": "doc123",
            "name": "Test Document",
            "value": 123,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z"
        }
    
    @pytest.fixture
    def mock_documents_list(self):
        return [
            {"name": "Document 1", "value": 1},
            {"name": "Document 2", "value": 2},
            {"name": "Document 3", "value": 3}
        ]
    
    # Test initialization
    @pytest.mark.asyncio
    async def test_init_success(self):
        """Test successful DatabaseService initialization"""
        with patch('app.services.database_service.get_firestore_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_collection = AsyncMock()
            mock_client.collection.return_value = mock_collection
            
            service = DatabaseService("test_collection")
            
            assert service.collection_name == "test_collection"
            assert service.max_batch_size == 500
            assert service.max_query_limit == 1000
    
    @pytest.mark.asyncio
    async def test_init_missing_collection_name(self):
        """Test initialization with missing collection name"""
        with pytest.raises(ValidationError, match="Collection name is required"):
            DatabaseService("")
    
    @pytest.mark.asyncio
    async def test_init_invalid_collection_name(self):
        """Test initialization with invalid collection name"""
        with pytest.raises(ValidationError, match="Collection name is required"):
            DatabaseService("   ")
    
    # Test create method
    @pytest.mark.asyncio
    async def test_create_success(self, database_service, mock_document_data):
        """Test successful document creation"""
        mock_doc = MagicMock()
        mock_doc.id = "doc123"
        database_service.collection.add = MagicMock(return_value=(None, mock_doc))
        
        result = await database_service.create({"name": "Test", "value": 123})
        
        assert result == "doc123"
        database_service.collection.add.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_with_doc_id(self, database_service):
        """Test document creation with specific ID"""
        mock_doc_ref = MagicMock()
        database_service.collection.document = MagicMock(return_value=mock_doc_ref)
        
        result = await database_service.create({"name": "Test"}, "custom_id")
        
        assert result == "custom_id"
        mock_doc_ref.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_missing_data(self, database_service):
        """Test document creation with missing data"""
        with pytest.raises(ValidationError, match="Data is required"):
            await database_service.create(None)
    
    @pytest.mark.asyncio
    async def test_create_empty_data(self, database_service):
        """Test document creation with empty data"""
        with pytest.raises(ValidationError, match="Data is required"):
            await database_service.create({})
    
    @pytest.mark.asyncio
    async def test_create_invalid_data_type(self, database_service):
        """Test document creation with invalid data type"""
        with pytest.raises(ValidationError, match="Data must be a dictionary"):
            await database_service.create("invalid_data")
    
    @pytest.mark.asyncio
    async def test_create_invalid_doc_id(self, database_service):
        """Test document creation with invalid document ID"""
        with pytest.raises(ValidationError, match="Document ID must be a non-empty string"):
            await database_service.create({"name": "Test"}, "")
    
    # Test get_by_id method
    @pytest.mark.asyncio
    async def test_get_by_id_success(self, database_service, mock_document_data):
        """Test successful document retrieval by ID"""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = mock_document_data
        mock_doc.id = "doc123"
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get = MagicMock(return_value=mock_doc)
        database_service.collection.document = MagicMock(return_value=mock_doc_ref)
        
        result = await database_service.get_by_id("doc123")
        
        assert result == mock_document_data
        assert result["id"] == "doc123"
    
    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, database_service):
        """Test document retrieval when document doesn't exist"""
        mock_doc = MagicMock()
        mock_doc.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get = MagicMock(return_value=mock_doc)
        database_service.collection.document = MagicMock(return_value=mock_doc_ref)
        
        result = await database_service.get_by_id("doc123")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_by_id_missing_id(self, database_service):
        """Test document retrieval with missing ID"""
        with pytest.raises(ValidationError, match="Document ID is required"):
            await database_service.get_by_id("")
    
    @pytest.mark.asyncio
    async def test_get_by_id_invalid_type(self, database_service):
        """Test document retrieval with invalid ID type"""
        with pytest.raises(ValidationError, match="Document ID must be a string"):
            await database_service.get_by_id(123)
    
    # Test update method
    @pytest.mark.asyncio
    async def test_update_success(self, database_service):
        """Test successful document update"""
        mock_doc_ref = MagicMock()
        database_service.collection.document = MagicMock(return_value=mock_doc_ref)
        
        result = await database_service.update("doc123", {"name": "Updated"})
        
        assert result is True
        mock_doc_ref.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_missing_doc_id(self, database_service):
        """Test document update with missing ID"""
        with pytest.raises(ValidationError, match="Document ID is required"):
            await database_service.update("", {"name": "Updated"})
    
    @pytest.mark.asyncio
    async def test_update_missing_data(self, database_service):
        """Test document update with missing data"""
        with pytest.raises(ValidationError, match="Update data is required"):
            await database_service.update("doc123", None)
    
    @pytest.mark.asyncio
    async def test_update_invalid_data_type(self, database_service):
        """Test document update with invalid data type"""
        with pytest.raises(ValidationError, match="Update data must be a dictionary"):
            await database_service.update("doc123", "invalid_data")
    
    # Test delete method
    @pytest.mark.asyncio
    async def test_delete_success(self, database_service):
        """Test successful document deletion"""
        mock_doc_ref = MagicMock()
        database_service.collection.document = MagicMock(return_value=mock_doc_ref)
        
        result = await database_service.delete("doc123")
        
        assert result is True
        mock_doc_ref.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_missing_doc_id(self, database_service):
        """Test document deletion with missing ID"""
        with pytest.raises(ValidationError, match="Document ID is required"):
            await database_service.delete("")
    
    # Test list_all method
    @pytest.mark.asyncio
    async def test_list_all_success(self, database_service, mock_document_data):
        """Test successful document listing"""
        mock_docs = [
            MagicMock(to_dict=lambda: mock_document_data, id="doc1"),
            MagicMock(to_dict=lambda: mock_document_data, id="doc2")
        ]
        
        mock_query = MagicMock()
        mock_query.stream = MagicMock(return_value=mock_docs)
        database_service.collection.limit.return_value.offset.return_value = mock_query
        
        result = await database_service.list_all(10, 0)
        
        assert len(result) == 2
        assert all("id" in doc for doc in result)
    
    @pytest.mark.asyncio
    async def test_list_all_invalid_limit(self, database_service):
        """Test document listing with invalid limit"""
        with pytest.raises(ValidationError, match="Limit must be between 1 and 1000"):
            await database_service.list_all(0, 0)
    
    @pytest.mark.asyncio
    async def test_list_all_invalid_offset(self, database_service):
        """Test document listing with invalid offset"""
        with pytest.raises(ValidationError, match="Offset must be non-negative"):
            await database_service.list_all(10, -1)
    
    # Test query method
    @pytest.mark.asyncio
    async def test_query_success(self, database_service, mock_document_data):
        """Test successful document querying"""
        filters = [FieldFilter("name", "==", "test")]
        mock_docs = [
            MagicMock(to_dict=lambda: mock_document_data, id="doc1"),
            MagicMock(to_dict=lambda: mock_document_data, id="doc2")
        ]
        
        mock_query = MagicMock()
        mock_query.stream = MagicMock(return_value=mock_docs)
        database_service.collection.where.return_value.limit.return_value.offset.return_value = mock_query
        
        result = await database_service.query(filters, 10, 0)
        
        assert len(result) == 2
        assert all("id" in doc for doc in result)
    
    @pytest.mark.asyncio
    async def test_query_invalid_filters(self, database_service):
        """Test document querying with invalid filters"""
        with pytest.raises(ValidationError, match="Filters must be a list"):
            await database_service.query("invalid_filters", 10, 0)
    
    # Test count method
    @pytest.mark.asyncio
    async def test_count_success(self, database_service):
        """Test successful document counting"""
        mock_docs = [MagicMock() for _ in range(25)]
        mock_query = MagicMock()
        mock_query.stream = MagicMock(return_value=mock_docs)
        database_service.collection.limit.return_value = mock_query
        
        result = await database_service.count()
        
        assert result == 25
    
    @pytest.mark.asyncio
    async def test_count_with_filters(self, database_service):
        """Test document counting with filters"""
        filters = [FieldFilter("name", "==", "test")]
        mock_docs = [MagicMock() for _ in range(10)]
        mock_query = MagicMock()
        mock_query.stream = MagicMock(return_value=mock_docs)
        database_service.collection.where.return_value.limit.return_value = mock_query
        
        result = await database_service.count(filters)
        
        assert result == 10
    
    @pytest.mark.asyncio
    async def test_count_invalid_filters(self, database_service):
        """Test document counting with invalid filters"""
        with pytest.raises(ValidationError, match="Filters must be a list or None"):
            await database_service.count("invalid_filters")
    
    # Test exists method
    @pytest.mark.asyncio
    async def test_exists_success(self, database_service):
        """Test successful existence check"""
        mock_doc = MagicMock()
        mock_doc.exists = True
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get = MagicMock(return_value=mock_doc)
        database_service.collection.document = MagicMock(return_value=mock_doc_ref)
        
        result = await database_service.exists("doc123")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_exists_not_found(self, database_service):
        """Test existence check when document doesn't exist"""
        mock_doc = MagicMock()
        mock_doc.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get = MagicMock(return_value=mock_doc)
        database_service.collection.document = MagicMock(return_value=mock_doc_ref)
        
        result = await database_service.exists("doc123")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_exists_missing_id(self, database_service):
        """Test existence check with missing ID"""
        with pytest.raises(ValidationError, match="Document ID is required"):
            await database_service.exists("")
    
    # Test batch_create method
    @pytest.mark.asyncio
    async def test_batch_create_success(self, database_service):
        """Test successful batch document creation"""
        documents = [{"name": "Doc1"}, {"name": "Doc2"}]
        mock_batch = AsyncMock()
        database_service.db.batch.return_value = mock_batch
        
        result = await database_service.batch_create(documents)
        
        assert len(result) == 2
        mock_batch.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_batch_create_missing_documents(self, database_service):
        """Test batch creation with missing documents"""
        with pytest.raises(ValidationError, match="Documents list is required"):
            await database_service.batch_create(None)
    
    @pytest.mark.asyncio
    async def test_batch_create_invalid_type(self, database_service):
        """Test batch creation with invalid documents type"""
        with pytest.raises(ValidationError, match="Documents must be a list"):
            await database_service.batch_create("invalid_documents")
    
    @pytest.mark.asyncio
    async def test_batch_create_too_many_documents(self, database_service):
        """Test batch creation with too many documents"""
        documents = [{"name": f"Doc{i}"} for i in range(501)]
        with pytest.raises(ValidationError, match="Batch size cannot exceed 500"):
            await database_service.batch_create(documents)
    
    # Test batch_update method
    @pytest.mark.asyncio
    async def test_batch_update_success(self, database_service):
        """Test successful batch document update"""
        updates = [("doc1", {"name": "Updated1"}), ("doc2", {"name": "Updated2"})]
        mock_batch = AsyncMock()
        database_service.db.batch.return_value = mock_batch
        
        result = await database_service.batch_update(updates)
        
        assert result is True
        mock_batch.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_batch_update_missing_updates(self, database_service):
        """Test batch update with missing updates"""
        with pytest.raises(ValidationError, match="Updates list is required"):
            await database_service.batch_update(None)
    
    @pytest.mark.asyncio
    async def test_batch_update_invalid_format(self, database_service):
        """Test batch update with invalid update format"""
        updates = [("doc1", "invalid_data")]
        with pytest.raises(ValidationError, match="Data in update 0 must be a dictionary"):
            await database_service.batch_update(updates)
    
    # Test batch_delete method
    @pytest.mark.asyncio
    async def test_batch_delete_success(self, database_service):
        """Test successful batch document deletion"""
        doc_ids = ["doc1", "doc2", "doc3"]
        mock_batch = AsyncMock()
        database_service.db.batch.return_value = mock_batch
        
        result = await database_service.batch_delete(doc_ids)
        
        assert result is True
        mock_batch.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_batch_delete_missing_ids(self, database_service):
        """Test batch delete with missing IDs"""
        with pytest.raises(ValidationError, match="Document IDs list is required"):
            await database_service.batch_delete(None)
    
    @pytest.mark.asyncio
    async def test_batch_delete_invalid_id(self, database_service):
        """Test batch delete with invalid ID"""
        doc_ids = ["doc1", "", "doc3"]
        with pytest.raises(ValidationError, match="Document ID 1 must be a non-empty string"):
            await database_service.batch_delete(doc_ids)
    
    # Test search method
    @pytest.mark.asyncio
    async def test_search_success(self, database_service):
        """Test successful document search"""
        mock_docs = [
            MagicMock(to_dict=lambda: {"name": "Football highlights", "id": "doc1"}, id="doc1"),
            MagicMock(to_dict=lambda: {"name": "Basketball skills", "id": "doc2"}, id="doc2")
        ]
        mock_query = MagicMock()
        mock_query.stream = MagicMock(return_value=mock_docs)
        database_service.collection.where.return_value.limit.return_value = mock_query
        
        result = await database_service.search("name", "football", 10)
        
        assert len(result) >= 1
        assert any("football" in doc["name"].lower() for doc in result)
    
    @pytest.mark.asyncio
    async def test_search_missing_field(self, database_service):
        """Test search with missing field"""
        with pytest.raises(ValidationError, match="Field name is required"):
            await database_service.search("", "value", 10)
    
    @pytest.mark.asyncio
    async def test_search_missing_value(self, database_service):
        """Test search with missing value"""
        with pytest.raises(ValidationError, match="Search value is required"):
            await database_service.search("field", "", 10)
    
    # Test get_by_field method
    @pytest.mark.asyncio
    async def test_get_by_field_success(self, database_service, mock_document_data):
        """Test successful document retrieval by field"""
        mock_doc = MagicMock(to_dict=lambda: mock_document_data, id="doc123")
        mock_query = MagicMock()
        mock_query.stream = MagicMock(return_value=[mock_doc])
        database_service.collection.where.return_value.limit.return_value = mock_query
        
        result = await database_service.get_by_field("name", "test")
        
        assert result == mock_document_data
        assert result["id"] == "doc123"
    
    @pytest.mark.asyncio
    async def test_get_by_field_not_found(self, database_service):
        """Test document retrieval by field when not found"""
        mock_query = MagicMock()
        mock_query.stream = MagicMock(return_value=[])
        database_service.collection.where.return_value.limit.return_value = mock_query
        
        result = await database_service.get_by_field("name", "nonexistent")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_by_field_missing_field(self, database_service):
        """Test document retrieval by field with missing field"""
        with pytest.raises(ValidationError, match="Field name is required"):
            await database_service.get_by_field("", "value")
    
    # Test get_by_field_list method
    @pytest.mark.asyncio
    async def test_get_by_field_list_success(self, database_service, mock_document_data):
        """Test successful document retrieval by field list"""
        mock_docs = [
            MagicMock(to_dict=lambda: mock_document_data, id="doc1"),
            MagicMock(to_dict=lambda: mock_document_data, id="doc2")
        ]
        mock_query = MagicMock()
        mock_query.stream = MagicMock(return_value=mock_docs)
        database_service.collection.where.return_value = mock_query
        
        result = await database_service.get_by_field_list("name", ["test1", "test2"])
        
        assert len(result) == 2
        assert all("id" in doc for doc in result)
    
    @pytest.mark.asyncio
    async def test_get_by_field_list_too_many_values(self, database_service):
        """Test document retrieval by field list with too many values"""
        values = [f"value{i}" for i in range(11)]
        with pytest.raises(ValidationError, match="Values list cannot exceed 10 items"):
            await database_service.get_by_field_list("name", values)
    
    # Test get_paginated_results method
    @pytest.mark.asyncio
    async def test_get_paginated_results_success(self, database_service, mock_document_data):
        """Test successful paginated results retrieval"""
        mock_docs = [
            MagicMock(to_dict=lambda: mock_document_data, id="doc1"),
            MagicMock(to_dict=lambda: mock_document_data, id="doc2")
        ]
        mock_query = MagicMock()
        mock_query.stream = MagicMock(return_value=mock_docs)
        database_service.collection.where.return_value.limit.return_value.offset.return_value = mock_query
        
        # Mock count method
        database_service.count = AsyncMock(return_value=50)
        
        result = await database_service.get_paginated_results(limit=20, offset=0)
        
        assert "results" in result
        assert "total_count" in result
        assert "has_next" in result
        assert "has_previous" in result
        assert result["total_count"] == 50
        assert result["has_next"] is True
        assert result["has_previous"] is False
    
    # Test error handling
    @pytest.mark.asyncio
    async def test_database_error_handling(self, database_service):
        """Test database error handling"""
        database_service.collection.add = MagicMock(side_effect=Exception("Database error"))
        
        with pytest.raises(DatabaseError, match="Failed to create document"):
            await database_service.create({"name": "Test"})
    
    @pytest.mark.asyncio
    async def test_validation_error_propagation(self, database_service):
        """Test that validation errors are properly propagated"""
        with pytest.raises(ValidationError, match="Document ID is required"):
            await database_service.get_by_id("")
    
    # Test performance optimizations
    @pytest.mark.asyncio
    async def test_async_implementation(self, database_service):
        """Test that methods are properly async"""
        # This test verifies that the methods work correctly
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"id": "doc123", "name": "test"}
        mock_doc.id = "doc123"
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get = MagicMock(return_value=mock_doc)
        database_service.collection.document = MagicMock(return_value=mock_doc_ref)
        
        # Should not raise any synchronous blocking errors
        result = await database_service.get_by_id("doc123")
        
        # Verify that the method was called and returns expected result
        database_service.collection.document.assert_called_once()
        assert result["id"] == "doc123" 