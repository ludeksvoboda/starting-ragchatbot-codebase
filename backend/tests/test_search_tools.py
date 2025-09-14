"""
Tests for search_tools.py - CourseSearchTool and CourseOutlineTool functionality.

These tests help diagnose potential issues in the search tool execution that could
cause NetworkError in the RAG chatbot.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any, Optional
import json

# Import the classes we're testing
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from vector_store import SearchResults


class MockVectorStore:
    """Mock VectorStore for testing without real ChromaDB"""
    
    def __init__(self):
        self.should_fail = False
        self.empty_results = False
        self.course_resolution_fails = False
        self.course_data = {}
        self.search_results = []
        
    def search(self, query: str, course_name: Optional[str] = None, 
               lesson_number: Optional[int] = None) -> SearchResults:
        """Mock search method"""
        if self.should_fail:
            return SearchResults.empty("Mock search error")
            
        if self.empty_results:
            return SearchResults(documents=[], metadata=[], distances=[])
            
        # Return mock search results
        return SearchResults(
            documents=self.search_results,
            metadata=[{
                'course_title': 'Test Course',
                'lesson_number': 1,
                'chunk_index': 0
            }] * len(self.search_results),
            distances=[0.1] * len(self.search_results)
        )
    
    def _resolve_course_name(self, course_name: str) -> Optional[str]:
        """Mock course name resolution"""
        if self.course_resolution_fails:
            return None
        return "Resolved Course Title"
    
    def get_lesson_link(self, course_title: str, lesson_number: int) -> Optional[str]:
        """Mock lesson link retrieval"""
        return f"https://example.com/{course_title}/lesson/{lesson_number}"
        
    @property 
    def course_catalog(self):
        """Mock course catalog property"""
        mock_catalog = Mock()
        mock_catalog.get.return_value = {
            'metadatas': [self.course_data] if self.course_data else None
        }
        return mock_catalog


class TestCourseSearchTool:
    """Test cases for CourseSearchTool"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.mock_vector_store = MockVectorStore()
        self.search_tool = CourseSearchTool(self.mock_vector_store)
    
    def test_get_tool_definition(self):
        """Test that tool definition is properly formatted"""
        definition = self.search_tool.get_tool_definition()
        
        assert definition["name"] == "search_course_content"
        assert "input_schema" in definition
        assert "query" in definition["input_schema"]["properties"]
        assert ["query"] == definition["input_schema"]["required"]
    
    def test_execute_successful_search(self):
        """Test successful search with results"""
        # Setup mock to return results
        self.mock_vector_store.search_results = ["Test content about Python programming"]
        
        result = self.search_tool.execute("Python programming")
        
        assert "[Test Course - Lesson 1]" in result
        assert "Test content about Python programming" in result
        assert len(self.search_tool.last_sources) == 1
        assert self.search_tool.last_sources[0]["text"] == "Test Course - Lesson 1"
    
    def test_execute_empty_results(self):
        """Test search with no results"""
        # Setup mock to return empty results
        self.mock_vector_store.empty_results = True
        
        result = self.search_tool.execute("nonexistent topic")
        
        assert "No relevant content found" in result
        assert len(self.search_tool.last_sources) == 0
    
    def test_execute_with_course_filter(self):
        """Test search with course name filter"""
        self.mock_vector_store.search_results = ["Filtered content"]
        
        result = self.search_tool.execute("programming", course_name="Python Course")
        
        assert "Filtered content" in result
        # Verify the mock was called with course filter
        # Note: In a real implementation, you'd want to verify the search method was called correctly
    
    def test_execute_with_lesson_filter(self):
        """Test search with lesson number filter"""
        self.mock_vector_store.search_results = ["Lesson-specific content"]
        
        result = self.search_tool.execute("variables", lesson_number=2)
        
        assert "Lesson-specific content" in result
    
    def test_execute_search_error(self):
        """Test search tool behavior when vector store fails"""
        # Setup mock to fail
        self.mock_vector_store.should_fail = True
        
        result = self.search_tool.execute("test query")
        
        assert "Mock search error" in result
    
    def test_execute_with_sources_tracking(self):
        """Test that sources are properly tracked"""
        self.mock_vector_store.search_results = ["Content 1", "Content 2"]
        
        # First search
        result1 = self.search_tool.execute("query 1")
        assert len(self.search_tool.last_sources) == 2
        
        # Second search should reset sources
        self.mock_vector_store.search_results = ["Content 3"]
        result2 = self.search_tool.execute("query 2")
        assert len(self.search_tool.last_sources) == 1
    
    def test_format_results_with_links(self):
        """Test result formatting includes lesson links when available"""
        # Create search results with metadata
        results = SearchResults(
            documents=["Test content"],
            metadata=[{
                'course_title': 'Python Basics',
                'lesson_number': 3,
                'chunk_index': 0
            }],
            distances=[0.1]
        )
        
        formatted = self.search_tool._format_results(results)
        
        assert "[Python Basics - Lesson 3]" in formatted
        assert "Test content" in formatted
        
        # Check that source includes link
        assert len(self.search_tool.last_sources) == 1
        source = self.search_tool.last_sources[0]
        assert source["text"] == "Python Basics - Lesson 3"
        assert "link" in source


class TestCourseOutlineTool:
    """Test cases for CourseOutlineTool"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.mock_vector_store = MockVectorStore()
        self.outline_tool = CourseOutlineTool(self.mock_vector_store)
    
    def test_get_tool_definition(self):
        """Test that tool definition is properly formatted"""
        definition = self.outline_tool.get_tool_definition()
        
        assert definition["name"] == "get_course_outline"
        assert "input_schema" in definition
        assert "course_name" in definition["input_schema"]["properties"]
        assert ["course_name"] == definition["input_schema"]["required"]
    
    def test_execute_successful_outline(self):
        """Test successful course outline retrieval"""
        # Setup mock course data
        lessons_data = [
            {"lesson_number": 1, "lesson_title": "Introduction", "lesson_link": "https://example.com/lesson1"},
            {"lesson_number": 2, "lesson_title": "Basics", "lesson_link": "https://example.com/lesson2"}
        ]
        
        self.mock_vector_store.course_data = {
            "course_link": "https://example.com/course",
            "lessons_json": json.dumps(lessons_data)
        }
        
        result = self.outline_tool.execute("Test Course")
        
        assert "**Resolved Course Title**" in result
        assert "Course Link: https://example.com/course" in result
        assert "1. Introduction" in result
        assert "2. Basics" in result
        assert "Lessons (2 total)" in result
    
    def test_execute_course_not_found(self):
        """Test outline tool when course resolution fails"""
        self.mock_vector_store.course_resolution_fails = True
        
        result = self.outline_tool.execute("Nonexistent Course")
        
        assert "No course found matching" in result
        assert "Nonexistent Course" in result
    
    def test_execute_no_metadata(self):
        """Test outline tool when course metadata is missing"""
        # Setup mock to return no metadata
        self.mock_vector_store.course_data = {}
        
        result = self.outline_tool.execute("Test Course")
        
        assert "Course metadata not found" in result
    
    def test_execute_no_lessons(self):
        """Test outline tool when course has no lesson information"""
        self.mock_vector_store.course_data = {
            "course_link": "https://example.com/course"
            # No lessons_json
        }
        
        result = self.outline_tool.execute("Test Course")
        
        assert "No lesson information available" in result
    
    def test_execute_json_parse_error(self):
        """Test outline tool handles malformed JSON"""
        self.mock_vector_store.course_data = {
            "lessons_json": "invalid json"
        }
        
        result = self.outline_tool.execute("Test Course")
        
        assert "Error retrieving course outline" in result


class TestToolManager:
    """Test cases for ToolManager"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.tool_manager = ToolManager()
        self.mock_vector_store = MockVectorStore()
    
    def test_register_tool(self):
        """Test tool registration"""
        search_tool = CourseSearchTool(self.mock_vector_store)
        self.tool_manager.register_tool(search_tool)
        
        assert "search_course_content" in self.tool_manager.tools
        
        definitions = self.tool_manager.get_tool_definitions()
        assert len(definitions) == 1
        assert definitions[0]["name"] == "search_course_content"
    
    def test_execute_tool(self):
        """Test tool execution through manager"""
        search_tool = CourseSearchTool(self.mock_vector_store)
        self.tool_manager.register_tool(search_tool)
        
        self.mock_vector_store.search_results = ["Test result"]
        
        result = self.tool_manager.execute_tool("search_course_content", query="test")
        
        assert "Test result" in result
    
    def test_execute_nonexistent_tool(self):
        """Test execution of tool that doesn't exist"""
        result = self.tool_manager.execute_tool("nonexistent_tool", query="test")
        
        assert "Tool 'nonexistent_tool' not found" in result
    
    def test_get_last_sources(self):
        """Test source tracking across tools"""
        search_tool = CourseSearchTool(self.mock_vector_store)
        self.tool_manager.register_tool(search_tool)
        
        self.mock_vector_store.search_results = ["Test content"]
        
        # Execute search to generate sources
        self.tool_manager.execute_tool("search_course_content", query="test")
        
        sources = self.tool_manager.get_last_sources()
        assert len(sources) == 1
        assert sources[0]["text"] == "Test Course - Lesson 1"
    
    def test_reset_sources(self):
        """Test source reset functionality"""
        search_tool = CourseSearchTool(self.mock_vector_store)
        self.tool_manager.register_tool(search_tool)
        
        self.mock_vector_store.search_results = ["Test content"]
        
        # Execute search and verify sources exist
        self.tool_manager.execute_tool("search_course_content", query="test")
        assert len(self.tool_manager.get_last_sources()) == 1
        
        # Reset sources and verify they're cleared
        self.tool_manager.reset_sources()
        assert len(self.tool_manager.get_last_sources()) == 0


class TestIntegration:
    """Integration tests combining multiple components"""
    
    def test_multiple_tools_registered(self):
        """Test multiple tools working together"""
        mock_vector_store = MockVectorStore()
        tool_manager = ToolManager()
        
        search_tool = CourseSearchTool(mock_vector_store)
        outline_tool = CourseOutlineTool(mock_vector_store)
        
        tool_manager.register_tool(search_tool)
        tool_manager.register_tool(outline_tool)
        
        definitions = tool_manager.get_tool_definitions()
        assert len(definitions) == 2
        
        tool_names = [defn["name"] for defn in definitions]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names
    
    def test_error_handling_chain(self):
        """Test error propagation through the tool chain"""
        mock_vector_store = MockVectorStore()
        mock_vector_store.should_fail = True
        
        search_tool = CourseSearchTool(mock_vector_store)
        result = search_tool.execute("test query")
        
        # Should contain error message, not crash
        assert "error" in result.lower()
        assert search_tool.last_sources == []


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])