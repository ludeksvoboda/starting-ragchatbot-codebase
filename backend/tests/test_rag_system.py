"""
Tests for rag_system.py - RAG system query processing functionality.

These tests help diagnose how the RAG system handles content-query related 
questions and identify potential NetworkError sources.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any, Optional, Tuple
import os
import tempfile

# Import the classes we're testing
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_system import RAGSystem
from models import Course, Lesson, CourseChunk
from config import Config


class MockConfig:
    """Mock configuration for testing"""
    
    def __init__(self):
        self.CHUNK_SIZE = 800
        self.CHUNK_OVERLAP = 100
        self.CHROMA_PATH = "./test_chroma_db"
        self.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        self.MAX_RESULTS = 5
        self.ANTHROPIC_API_KEY = "fake-api-key"
        self.ANTHROPIC_MODEL = "claude-sonnet-4"
        self.MAX_HISTORY = 2


class MockDocumentProcessor:
    """Mock document processor for testing"""
    
    def __init__(self, chunk_size, chunk_overlap):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.should_fail = False
        
    def process_course_document(self, file_path: str) -> Tuple[Course, List[CourseChunk]]:
        """Mock document processing"""
        if self.should_fail:
            raise Exception("Mock document processing error")
            
        # Create mock course
        course = Course(
            title="Test Course",
            course_link="https://example.com/course",
            instructor="Test Instructor",
            lessons=[
                Lesson(lesson_number=1, title="Introduction", lesson_link="https://example.com/lesson1"),
                Lesson(lesson_number=2, title="Basics", lesson_link="https://example.com/lesson2")
            ]
        )
        
        # Create mock chunks
        chunks = [
            CourseChunk(
                content="This is the introduction to the course content",
                course_title="Test Course",
                lesson_number=1,
                chunk_index=0
            ),
            CourseChunk(
                content="This covers the basic concepts of the subject",
                course_title="Test Course",
                lesson_number=2,
                chunk_index=1
            )
        ]
        
        return course, chunks


class MockVectorStore:
    """Mock vector store for testing"""
    
    def __init__(self, chroma_path, embedding_model, max_results):
        self.chroma_path = chroma_path
        self.embedding_model = embedding_model
        self.max_results = max_results
        self.courses = {}
        self.chunks = []
        self.should_fail_search = False
        
    def add_course_metadata(self, course: Course):
        """Mock adding course metadata"""
        self.courses[course.title] = course
        
    def add_course_content(self, chunks: List[CourseChunk]):
        """Mock adding course content"""
        self.chunks.extend(chunks)
        
    def get_existing_course_titles(self) -> List[str]:
        """Mock getting existing course titles"""
        return list(self.courses.keys())
        
    def get_course_count(self) -> int:
        """Mock getting course count"""
        return len(self.courses)
        
    def clear_all_data(self):
        """Mock clearing all data"""
        self.courses = {}
        self.chunks = []


class MockAIGenerator:
    """Mock AI generator for testing"""
    
    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model
        self.should_fail = False
        self.response_text = "This is a mock AI response"
        self.should_use_tools = False
        self.last_query = None
        self.last_tools = None
        
    def generate_response(self, query: str, conversation_history=None, 
                         tools=None, tool_manager=None) -> str:
        """Mock response generation"""
        self.last_query = query
        self.last_tools = tools
        
        if self.should_fail:
            raise Exception("Mock AI generation error")
            
        if self.should_use_tools and tool_manager:
            # Simulate tool usage
            tool_result = tool_manager.execute_tool("search_course_content", query=query)
            return f"Based on search results: {tool_result}"
            
        return self.response_text


class MockSessionManager:
    """Mock session manager for testing"""
    
    def __init__(self, max_history):
        self.max_history = max_history
        self.sessions = {}
        
    def create_session(self) -> str:
        """Mock session creation"""
        session_id = f"session_{len(self.sessions)}"
        self.sessions[session_id] = []
        return session_id
        
    def get_conversation_history(self, session_id: str) -> Optional[str]:
        """Mock getting conversation history"""
        if session_id in self.sessions:
            return "\n".join(self.sessions[session_id])
        return None
        
    def add_exchange(self, session_id: str, query: str, response: str):
        """Mock adding conversation exchange"""
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append(f"User: {query}")
        self.sessions[session_id].append(f"Assistant: {response}")


class MockToolManager:
    """Mock tool manager for testing"""
    
    def __init__(self):
        self.tools_executed = []
        self.last_sources = []
        
    def get_tool_definitions(self):
        """Mock tool definitions"""
        return [
            {
                "name": "search_course_content",
                "description": "Search course materials"
            }
        ]
        
    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Mock tool execution"""
        self.tools_executed.append({"name": tool_name, "args": kwargs})
        return "Mock search result content"
        
    def get_last_sources(self) -> List[str]:
        """Mock getting last sources"""
        return self.last_sources
        
    def reset_sources(self):
        """Mock resetting sources"""
        self.last_sources = []


class TestRAGSystem:
    """Test cases for RAGSystem"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.config = MockConfig()
        
        # Create RAGSystem with mocked components
        self.rag_system = RAGSystem(self.config)
        
        # Replace real components with mocks
        self.rag_system.document_processor = MockDocumentProcessor(
            self.config.CHUNK_SIZE, 
            self.config.CHUNK_OVERLAP
        )
        self.rag_system.vector_store = MockVectorStore(
            self.config.CHROMA_PATH,
            self.config.EMBEDDING_MODEL, 
            self.config.MAX_RESULTS
        )
        self.rag_system.ai_generator = MockAIGenerator(
            self.config.ANTHROPIC_API_KEY,
            self.config.ANTHROPIC_MODEL
        )
        self.rag_system.session_manager = MockSessionManager(
            self.config.MAX_HISTORY
        )
        self.rag_system.tool_manager = MockToolManager()
    
    def test_initialization(self):
        """Test RAGSystem initialization"""
        assert self.rag_system.config == self.config
        assert hasattr(self.rag_system, 'document_processor')
        assert hasattr(self.rag_system, 'vector_store')
        assert hasattr(self.rag_system, 'ai_generator')
        assert hasattr(self.rag_system, 'session_manager')
        assert hasattr(self.rag_system, 'tool_manager')
    
    def test_add_course_document_success(self):
        """Test successfully adding a course document"""
        with tempfile.NamedTemporaryFile(suffix='.txt') as temp_file:
            temp_file.write(b"Test course content")
            temp_file.flush()
            
            course, chunk_count = self.rag_system.add_course_document(temp_file.name)
            
            assert course is not None
            assert course.title == "Test Course"
            assert chunk_count == 2
            
            # Verify course was added to vector store
            assert "Test Course" in self.rag_system.vector_store.courses
    
    def test_add_course_document_failure(self):
        """Test handling of document processing failure"""
        self.rag_system.document_processor.should_fail = True
        
        course, chunk_count = self.rag_system.add_course_document("fake_file.txt")
        
        assert course is None
        assert chunk_count == 0
    
    def test_add_course_folder_success(self):
        """Test adding course documents from a folder"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_files = ['course1.txt', 'course2.pdf', 'course3.docx', 'ignored.jpg']
            for filename in test_files:
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, 'w') as f:
                    f.write("Test content")
            
            courses, chunks = self.rag_system.add_course_folder(temp_dir)
            
            # Should process 3 valid course files
            assert courses == 3
            assert chunks == 6  # 2 chunks per course
    
    def test_add_course_folder_nonexistent(self):
        """Test adding from nonexistent folder"""
        courses, chunks = self.rag_system.add_course_folder("/nonexistent/path")
        
        assert courses == 0
        assert chunks == 0
    
    def test_query_simple(self):
        """Test simple query processing"""
        response, sources = self.rag_system.query("What is Python?")
        
        assert response == "This is a mock AI response"
        assert isinstance(sources, list)
        
        # Verify AI generator was called correctly
        assert "What is Python?" in self.rag_system.ai_generator.last_query
        assert self.rag_system.ai_generator.last_tools is not None
    
    def test_query_with_session(self):
        """Test query processing with session management"""
        session_id = "test_session"
        self.rag_system.session_manager.sessions[session_id] = ["Previous context"]
        
        response, sources = self.rag_system.query(
            "Follow up question", 
            session_id=session_id
        )
        
        assert response == "This is a mock AI response"
        
        # Verify session was updated
        assert len(self.rag_system.session_manager.sessions[session_id]) > 1
    
    def test_query_with_tool_usage(self):
        """Test query that triggers tool usage"""
        self.rag_system.ai_generator.should_use_tools = True
        
        response, sources = self.rag_system.query("Search for course content")
        
        assert "Based on search results:" in response
        assert "Mock search result content" in response
        
        # Verify tool was executed
        assert len(self.rag_system.tool_manager.tools_executed) == 1
        assert self.rag_system.tool_manager.tools_executed[0]["name"] == "search_course_content"
    
    def test_query_ai_generator_failure(self):
        """Test query handling when AI generator fails"""
        self.rag_system.ai_generator.should_fail = True
        
        with pytest.raises(Exception) as excinfo:
            self.rag_system.query("test query")
        
        assert "Mock AI generation error" in str(excinfo.value)
    
    def test_get_course_analytics(self):
        """Test course analytics functionality"""
        # Add some test courses
        test_courses = ["Course 1", "Course 2", "Course 3"]
        for title in test_courses:
            course = Course(title=title)
            self.rag_system.vector_store.add_course_metadata(course)
        
        analytics = self.rag_system.get_course_analytics()
        
        assert analytics["total_courses"] == 3
        assert set(analytics["course_titles"]) == set(test_courses)
    
    def test_source_tracking(self):
        """Test that sources are properly tracked and reset"""
        # Setup mock sources
        self.rag_system.tool_manager.last_sources = [
            {"text": "Course 1 - Lesson 1", "link": "https://example.com"}
        ]
        
        response, sources = self.rag_system.query("test query")
        
        # Sources should be returned
        assert len(sources) == 1
        assert sources[0]["text"] == "Course 1 - Lesson 1"
        
        # Sources should be reset after retrieval  
        # Note: This tests the reset_sources functionality
        assert len(self.rag_system.tool_manager.last_sources) == 0


class TestRAGSystemIntegration:
    """Integration tests for RAGSystem with more realistic scenarios"""
    
    def setup_method(self):
        """Setup for integration tests"""
        self.config = MockConfig()
        self.rag_system = RAGSystem(self.config)
        
        # Use partially real components
        self.rag_system.document_processor = MockDocumentProcessor(
            self.config.CHUNK_SIZE, 
            self.config.CHUNK_OVERLAP
        )
        self.rag_system.vector_store = MockVectorStore(
            self.config.CHROMA_PATH,
            self.config.EMBEDDING_MODEL, 
            self.config.MAX_RESULTS
        )
        self.rag_system.ai_generator = MockAIGenerator(
            self.config.ANTHROPIC_API_KEY,
            self.config.ANTHROPIC_MODEL
        )
        self.rag_system.session_manager = MockSessionManager(
            self.config.MAX_HISTORY
        )
        
        # Use real tool manager with mock vector store
        from search_tools import ToolManager, CourseSearchTool, CourseOutlineTool
        
        self.rag_system.tool_manager = ToolManager()
        self.rag_system.search_tool = CourseSearchTool(self.rag_system.vector_store)
        self.rag_system.outline_tool = CourseOutlineTool(self.rag_system.vector_store)
        self.rag_system.tool_manager.register_tool(self.rag_system.search_tool)
        self.rag_system.tool_manager.register_tool(self.rag_system.outline_tool)
    
    def test_full_workflow_with_real_tools(self):
        """Test full workflow with real tool manager and search tools"""
        # Add test course data
        course = Course(
            title="Python Programming",
            lessons=[Lesson(lesson_number=1, title="Introduction")]
        )
        self.rag_system.vector_store.add_course_metadata(course)
        
        chunks = [
            CourseChunk(
                content="Python is a high-level programming language",
                course_title="Python Programming",
                lesson_number=1,
                chunk_index=0
            )
        ]
        self.rag_system.vector_store.add_course_content(chunks)
        
        # Configure AI to use tools
        self.rag_system.ai_generator.should_use_tools = True
        
        response, sources = self.rag_system.query("What is Python?")
        
        assert "Based on search results:" in response
        # Should have real tool definitions
        tools = self.rag_system.tool_manager.get_tool_definitions()
        assert len(tools) == 2  # search and outline tools
    
    def test_error_propagation(self):
        """Test how errors propagate through the system"""
        # Test with vector store that fails
        original_search = self.rag_system.vector_store.search
        
        def failing_search(*args, **kwargs):
            raise Exception("Vector store connection failed")
            
        # This tests error handling in the tool layer
        self.rag_system.search_tool.store.search = failing_search
        
        # Should not crash the whole system
        response, sources = self.rag_system.query("test query")
        
        # Response should still be generated (either error message or fallback)
        assert response is not None
        assert len(response) > 0
    
    def test_conversation_context_handling(self):
        """Test conversation context across multiple queries"""
        session_id = "test_conversation"
        
        # First query
        response1, _ = self.rag_system.query("What is machine learning?", session_id)
        
        # Second query with context
        response2, _ = self.rag_system.query("How does it work?", session_id)
        
        # Should have maintained session context
        history = self.rag_system.session_manager.get_conversation_history(session_id)
        assert history is not None
        assert "What is machine learning?" in history
        assert "How does it work?" in history
    
    def test_empty_knowledge_base(self):
        """Test system behavior with empty knowledge base"""
        # Don't add any courses
        
        response, sources = self.rag_system.query("What courses are available?")
        
        # Should handle gracefully
        assert response is not None
        assert len(sources) == 0
        
        # Analytics should show empty state
        analytics = self.rag_system.get_course_analytics()
        assert analytics["total_courses"] == 0
        assert len(analytics["course_titles"]) == 0


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])