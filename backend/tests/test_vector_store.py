"""
Tests for vector_store.py - Vector store integration functionality.

These tests help diagnose potential ChromaDB and vector store issues that could
cause NetworkError in the RAG chatbot.
"""

import pytest
import tempfile
import shutil
import os
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any

# Import the classes we're testing
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vector_store import VectorStore, SearchResults
from models import Course, Lesson, CourseChunk


class TestSearchResults:
    """Test cases for SearchResults dataclass"""
    
    def test_search_results_creation(self):
        """Test SearchResults creation and properties"""
        results = SearchResults(
            documents=["doc1", "doc2"],
            metadata=[{"key": "value1"}, {"key": "value2"}],
            distances=[0.1, 0.2]
        )
        
        assert len(results.documents) == 2
        assert len(results.metadata) == 2
        assert len(results.distances) == 2
        assert results.error is None
        assert not results.is_empty()
    
    def test_search_results_empty(self):
        """Test empty SearchResults"""
        results = SearchResults(documents=[], metadata=[], distances=[])
        assert results.is_empty()
    
    def test_search_results_from_chroma(self):
        """Test creating SearchResults from ChromaDB format"""
        chroma_results = {
            'documents': [["doc1", "doc2"]],
            'metadatas': [[{"key": "value1"}, {"key": "value2"}]],
            'distances': [[0.1, 0.2]]
        }
        
        results = SearchResults.from_chroma(chroma_results)
        
        assert len(results.documents) == 2
        assert results.documents[0] == "doc1"
        assert results.metadata[0]["key"] == "value1"
        assert results.distances[0] == 0.1
    
    def test_search_results_from_empty_chroma(self):
        """Test creating SearchResults from empty ChromaDB results"""
        chroma_results = {
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }
        
        results = SearchResults.from_chroma(chroma_results)
        
        assert results.is_empty()
        assert len(results.documents) == 0
    
    def test_search_results_with_error(self):
        """Test SearchResults with error message"""
        results = SearchResults.empty("Test error message")
        
        assert results.is_empty()
        assert results.error == "Test error message"


class TestVectorStore:
    """Test cases for VectorStore class"""
    
    def setup_method(self):
        """Setup for each test method"""
        # Create temporary directory for test ChromaDB
        self.temp_dir = tempfile.mkdtemp()
        self.test_chroma_path = os.path.join(self.temp_dir, "test_chroma")
        
        # We'll mock ChromaDB to avoid actual database operations in most tests
        self.mock_client = Mock()
        self.mock_collection = Mock()
        self.mock_client.get_or_create_collection.return_value = self.mock_collection
        
    def teardown_method(self):
        """Cleanup after each test method"""
        # Clean up temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_vector_store_initialization(self, mock_embedding_func, mock_client_class):
        """Test VectorStore initialization"""
        mock_client_class.return_value = self.mock_client
        
        vector_store = VectorStore(
            chroma_path=self.test_chroma_path,
            embedding_model="test-model",
            max_results=10
        )
        
        assert vector_store.max_results == 10
        assert vector_store.client == self.mock_client
        
        # Should create two collections
        assert self.mock_client.get_or_create_collection.call_count == 2
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_add_course_metadata(self, mock_embedding_func, mock_client_class):
        """Test adding course metadata"""
        mock_client_class.return_value = self.mock_client
        
        vector_store = VectorStore(self.test_chroma_path, "test-model")
        
        course = Course(
            title="Test Course",
            course_link="https://example.com",
            instructor="Test Instructor",
            lessons=[
                Lesson(lesson_number=1, title="Lesson 1", lesson_link="https://example.com/lesson1"),
                Lesson(lesson_number=2, title="Lesson 2", lesson_link="https://example.com/lesson2")
            ]
        )
        
        vector_store.add_course_metadata(course)
        
        # Should call add on course catalog collection
        vector_store.course_catalog.add.assert_called_once()
        
        # Verify the call arguments
        call_args = vector_store.course_catalog.add.call_args
        assert call_args[1]['documents'] == ["Test Course"]
        assert call_args[1]['ids'] == ["Test Course"]
        
        metadata = call_args[1]['metadatas'][0]
        assert metadata['title'] == "Test Course"
        assert metadata['instructor'] == "Test Instructor"
        assert metadata['course_link'] == "https://example.com"
        assert metadata['lesson_count'] == 2
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_add_course_content(self, mock_embedding_func, mock_client_class):
        """Test adding course content chunks"""
        mock_client_class.return_value = self.mock_client
        
        vector_store = VectorStore(self.test_chroma_path, "test-model")
        
        chunks = [
            CourseChunk(
                content="This is chunk 1",
                course_title="Test Course",
                lesson_number=1,
                chunk_index=0
            ),
            CourseChunk(
                content="This is chunk 2", 
                course_title="Test Course",
                lesson_number=1,
                chunk_index=1
            )
        ]
        
        vector_store.add_course_content(chunks)
        
        # Should call add on course content collection
        vector_store.course_content.add.assert_called_once()
        
        call_args = vector_store.course_content.add.call_args
        assert len(call_args[1]['documents']) == 2
        assert call_args[1]['documents'][0] == "This is chunk 1"
        assert call_args[1]['documents'][1] == "This is chunk 2"
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_search_success(self, mock_embedding_func, mock_client_class):
        """Test successful search operation"""
        mock_client_class.return_value = self.mock_client
        
        # Setup mock search results
        self.mock_collection.query.return_value = {
            'documents': [["Found content about Python"]],
            'metadatas': [[{"course_title": "Python Course", "lesson_number": 1}]],
            'distances': [[0.1]]
        }
        
        vector_store = VectorStore(self.test_chroma_path, "test-model")
        vector_store.course_content = self.mock_collection
        
        results = vector_store.search("Python programming")
        
        assert not results.is_empty()
        assert len(results.documents) == 1
        assert "Found content about Python" in results.documents[0]
        assert results.metadata[0]["course_title"] == "Python Course"
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_search_with_course_filter(self, mock_embedding_func, mock_client_class):
        """Test search with course name filter"""
        mock_client_class.return_value = self.mock_client
        
        # Mock course resolution
        def mock_resolve_course_name(course_name):
            if course_name == "Python":
                return "Python Programming Course"
            return None
        
        vector_store = VectorStore(self.test_chroma_path, "test-model")
        vector_store.course_content = self.mock_collection
        vector_store._resolve_course_name = mock_resolve_course_name
        
        # Setup mock search results
        self.mock_collection.query.return_value = {
            'documents': [["Python content"]],
            'metadatas': [[{"course_title": "Python Programming Course"}]],
            'distances': [[0.1]]
        }
        
        results = vector_store.search("variables", course_name="Python")
        
        assert not results.is_empty()
        
        # Verify query was called with filter
        call_args = self.mock_collection.query.call_args
        assert call_args[1]['where'] == {"course_title": "Python Programming Course"}
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_search_course_not_found(self, mock_embedding_func, mock_client_class):
        """Test search when course name cannot be resolved"""
        mock_client_class.return_value = self.mock_client
        
        def mock_resolve_course_name(course_name):
            return None  # Course not found
        
        vector_store = VectorStore(self.test_chroma_path, "test-model")
        vector_store._resolve_course_name = mock_resolve_course_name
        
        results = vector_store.search("test query", course_name="NonexistentCourse")
        
        assert results.is_empty()
        assert "No course found matching 'NonexistentCourse'" in results.error
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_search_database_error(self, mock_embedding_func, mock_client_class):
        """Test search when database operation fails"""
        mock_client_class.return_value = self.mock_client
        
        # Setup mock to raise exception
        self.mock_collection.query.side_effect = Exception("Database connection failed")
        
        vector_store = VectorStore(self.test_chroma_path, "test-model")
        vector_store.course_content = self.mock_collection
        
        results = vector_store.search("test query")
        
        assert results.is_empty()
        assert "Search error: Database connection failed" in results.error
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_resolve_course_name(self, mock_embedding_func, mock_client_class):
        """Test course name resolution"""
        mock_client_class.return_value = self.mock_client
        
        # Setup mock catalog results
        mock_catalog = Mock()
        mock_catalog.query.return_value = {
            'documents': [["Python Programming"]],
            'metadatas': [[{"title": "Python Programming Course"}]]
        }
        
        vector_store = VectorStore(self.test_chroma_path, "test-model")
        vector_store.course_catalog = mock_catalog
        
        resolved = vector_store._resolve_course_name("Python")
        
        assert resolved == "Python Programming Course"
        
        # Verify catalog was queried correctly
        mock_catalog.query.assert_called_with(query_texts=["Python"], n_results=1)
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_build_filter_combinations(self, mock_embedding_func, mock_client_class):
        """Test filter building for different combinations"""
        mock_client_class.return_value = self.mock_client
        
        vector_store = VectorStore(self.test_chroma_path, "test-model")
        
        # No filters
        filter_dict = vector_store._build_filter(None, None)
        assert filter_dict is None
        
        # Course only
        filter_dict = vector_store._build_filter("Test Course", None)
        assert filter_dict == {"course_title": "Test Course"}
        
        # Lesson only
        filter_dict = vector_store._build_filter(None, 5)
        assert filter_dict == {"lesson_number": 5}
        
        # Both filters
        filter_dict = vector_store._build_filter("Test Course", 5)
        expected = {"$and": [{"course_title": "Test Course"}, {"lesson_number": 5}]}
        assert filter_dict == expected
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_get_existing_course_titles(self, mock_embedding_func, mock_client_class):
        """Test getting existing course titles"""
        mock_client_class.return_value = self.mock_client
        
        mock_catalog = Mock()
        mock_catalog.get.return_value = {
            'ids': ['Course 1', 'Course 2', 'Course 3']
        }
        
        vector_store = VectorStore(self.test_chroma_path, "test-model")
        vector_store.course_catalog = mock_catalog
        
        titles = vector_store.get_existing_course_titles()
        
        assert len(titles) == 3
        assert 'Course 1' in titles
        assert 'Course 2' in titles
        assert 'Course 3' in titles
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_get_course_count(self, mock_embedding_func, mock_client_class):
        """Test getting course count"""
        mock_client_class.return_value = self.mock_client
        
        mock_catalog = Mock()
        mock_catalog.get.return_value = {
            'ids': ['Course 1', 'Course 2']
        }
        
        vector_store = VectorStore(self.test_chroma_path, "test-model")
        vector_store.course_catalog = mock_catalog
        
        count = vector_store.get_course_count()
        assert count == 2
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_clear_all_data(self, mock_embedding_func, mock_client_class):
        """Test clearing all data"""
        mock_client_class.return_value = self.mock_client
        
        vector_store = VectorStore(self.test_chroma_path, "test-model")
        
        vector_store.clear_all_data()
        
        # Should delete and recreate collections
        assert self.mock_client.delete_collection.call_count == 2
        # get_or_create_collection called during init (2) + after clear (2) = 4
        assert self.mock_client.get_or_create_collection.call_count == 4


class TestVectorStoreIntegration:
    """Integration tests with real ChromaDB (in temporary locations)"""
    
    def setup_method(self):
        """Setup for integration tests"""
        # Create temporary directory for real ChromaDB testing
        self.temp_dir = tempfile.mkdtemp()
        self.test_chroma_path = os.path.join(self.temp_dir, "test_chroma")
    
    def teardown_method(self):
        """Cleanup after integration tests"""
        # Clean up temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @pytest.mark.slow
    def test_real_chromadb_initialization(self):
        """Test initialization with real ChromaDB (slow test)"""
        try:
            vector_store = VectorStore(
                chroma_path=self.test_chroma_path,
                embedding_model="all-MiniLM-L6-v2",
                max_results=5
            )
            
            # Should initialize without errors
            assert vector_store.client is not None
            assert vector_store.course_catalog is not None
            assert vector_store.course_content is not None
            
        except ImportError:
            pytest.skip("ChromaDB or sentence-transformers not available")
        except Exception as e:
            pytest.fail(f"Real ChromaDB initialization failed: {e}")
    
    @pytest.mark.slow
    def test_real_add_and_search_flow(self):
        """Test real add and search flow (slow test)"""
        try:
            vector_store = VectorStore(
                chroma_path=self.test_chroma_path,
                embedding_model="all-MiniLM-L6-v2",
                max_results=5
            )
            
            # Add test course
            course = Course(
                title="Test Integration Course",
                lessons=[Lesson(lesson_number=1, title="Introduction")]
            )
            vector_store.add_course_metadata(course)
            
            # Add test content
            chunks = [
                CourseChunk(
                    content="Python is a programming language used for data science",
                    course_title="Test Integration Course",
                    lesson_number=1,
                    chunk_index=0
                )
            ]
            vector_store.add_course_content(chunks)
            
            # Search for content
            results = vector_store.search("Python programming")
            
            # Should find the content we added
            assert not results.is_empty()
            assert len(results.documents) > 0
            
        except ImportError:
            pytest.skip("ChromaDB or sentence-transformers not available")
        except Exception as e:
            pytest.fail(f"Real ChromaDB integration test failed: {e}")


class TestVectorStoreErrorHandling:
    """Test error handling in various scenarios"""
    
    def setup_method(self):
        """Setup for error handling tests"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_chroma_path = os.path.join(self.temp_dir, "test_chroma")
    
    def teardown_method(self):
        """Cleanup after error handling tests"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @patch('vector_store.chromadb.PersistentClient')
    def test_chromadb_connection_failure(self, mock_client_class):
        """Test handling of ChromaDB connection failure"""
        # Mock client initialization failure
        mock_client_class.side_effect = Exception("ChromaDB connection failed")
        
        with pytest.raises(Exception) as excinfo:
            VectorStore(self.test_chroma_path, "test-model")
        
        assert "ChromaDB connection failed" in str(excinfo.value)
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_embedding_model_failure(self, mock_embedding_func, mock_client_class):
        """Test handling of embedding model failure"""
        # Mock embedding function failure
        mock_embedding_func.side_effect = Exception("Embedding model not found")
        mock_client_class.return_value = Mock()
        
        with pytest.raises(Exception) as excinfo:
            VectorStore(self.test_chroma_path, "invalid-model")
        
        assert "Embedding model not found" in str(excinfo.value)
    
    @patch('vector_store.chromadb.PersistentClient')
    @patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction')
    def test_permission_error_handling(self, mock_embedding_func, mock_client_class):
        """Test handling of permission errors"""
        # Mock client to raise permission error
        mock_client = Mock()
        mock_client.get_or_create_collection.side_effect = PermissionError("Access denied")
        mock_client_class.return_value = mock_client
        
        with pytest.raises(PermissionError) as excinfo:
            VectorStore("/root/restricted_path", "test-model")
        
        assert "Access denied" in str(excinfo.value)


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])