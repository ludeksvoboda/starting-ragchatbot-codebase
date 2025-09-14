"""
Tests for app.py - FastAPI endpoints functionality.

These tests help diagnose potential NetworkError issues in the API layer
that could be causing the RAG chatbot to fail.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any
import json

# Import the FastAPI app and dependencies
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from rag_system import RAGSystem


class MockRAGSystem:
    """Mock RAG system for API testing"""
    
    def __init__(self):
        self.should_fail = False
        self.should_timeout = False
        self.query_response = "Test response"
        self.query_sources = []
        self.session_id = "test_session_123"
        self.analytics_data = {
            "total_courses": 3,
            "course_titles": ["Course 1", "Course 2", "Course 3"]
        }
        self.queries_received = []
        
        # Mock session manager
        self.session_manager = Mock()
        self.session_manager.create_session.return_value = self.session_id
        self.session_manager.clear_session.return_value = None
    
    def query(self, query_text: str, session_id: str = None) -> tuple:
        """Mock query method"""
        self.queries_received.append({
            "query": query_text,
            "session_id": session_id
        })
        
        if self.should_fail:
            raise Exception("Mock RAG system error")
            
        if self.should_timeout:
            import time
            time.sleep(10)  # Simulate timeout
            
        return self.query_response, self.query_sources
    
    def get_course_analytics(self) -> Dict[str, Any]:
        """Mock analytics method"""
        if self.should_fail:
            raise Exception("Mock analytics error")
            
        return self.analytics_data


class TestAPIEndpoints:
    """Test cases for FastAPI endpoints"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.mock_rag_system = MockRAGSystem()
        
        # Replace the global rag_system with our mock
        with patch('app.rag_system', self.mock_rag_system):
            self.client = TestClient(app)
    
    @patch('app.rag_system')
    def test_query_endpoint_success(self, mock_rag):
        """Test successful query to /api/query endpoint"""
        mock_rag.query.return_value = ("Test response", [{"text": "Source 1", "link": "http://example.com"}])
        mock_rag.session_manager.create_session.return_value = "session_123"
        
        response = self.client.post(
            "/api/query",
            json={
                "query": "What is Python?",
                "session_id": None
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["answer"] == "Test response"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"] == "Source 1"
        assert data["sources"][0]["link"] == "http://example.com"
        assert data["session_id"] == "session_123"
    
    @patch('app.rag_system')
    def test_query_endpoint_with_existing_session(self, mock_rag):
        """Test query with existing session ID"""
        mock_rag.query.return_value = ("Follow-up response", [])
        
        response = self.client.post(
            "/api/query",
            json={
                "query": "Follow up question",
                "session_id": "existing_session"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["answer"] == "Follow-up response"
        assert data["session_id"] == "existing_session"
        
        # Verify RAG system was called with the session
        mock_rag.query.assert_called_with("Follow up question", "existing_session")
    
    @patch('app.rag_system')
    def test_query_endpoint_rag_system_error(self, mock_rag):
        """Test query endpoint when RAG system fails"""
        mock_rag.query.side_effect = Exception("Internal RAG error")
        
        response = self.client.post(
            "/api/query",
            json={
                "query": "Test query"
            }
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "Internal RAG error" in data["detail"]
    
    @patch('app.rag_system')
    def test_query_endpoint_anthropic_credit_error(self, mock_rag):
        """Test query endpoint with Anthropic credit error"""
        mock_rag.query.side_effect = Exception("credit balance is too low")
        
        response = self.client.post(
            "/api/query",
            json={
                "query": "Test query"
            }
        )
        
        assert response.status_code == 402
        data = response.json()
        assert "credit balance too low" in data["detail"]
    
    @patch('app.rag_system')
    def test_query_endpoint_invalid_request_error(self, mock_rag):
        """Test query endpoint with invalid request error"""
        mock_rag.query.side_effect = Exception("invalid_request_error: bad parameters")
        
        response = self.client.post(
            "/api/query",
            json={
                "query": "Test query"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "API request error" in data["detail"]
    
    def test_query_endpoint_missing_query(self):
        """Test query endpoint with missing query parameter"""
        response = self.client.post(
            "/api/query",
            json={
                "session_id": "test"
                # Missing "query"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_query_endpoint_empty_query(self):
        """Test query endpoint with empty query"""
        with patch('app.rag_system') as mock_rag:
            mock_rag.query.return_value = ("Empty query response", [])
            mock_rag.session_manager.create_session.return_value = "session_123"
            
            response = self.client.post(
                "/api/query",
                json={
                    "query": "",
                    "session_id": None
                }
            )
            
            assert response.status_code == 200
            # Should still process empty query
    
    @patch('app.rag_system')
    def test_courses_endpoint_success(self, mock_rag):
        """Test successful request to /api/courses endpoint"""
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 5,
            "course_titles": ["Course A", "Course B", "Course C", "Course D", "Course E"]
        }
        
        response = self.client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_courses"] == 5
        assert len(data["course_titles"]) == 5
        assert "Course A" in data["course_titles"]
    
    @patch('app.rag_system')
    def test_courses_endpoint_error(self, mock_rag):
        """Test courses endpoint when analytics fails"""
        mock_rag.get_course_analytics.side_effect = Exception("Analytics error")
        
        response = self.client.get("/api/courses")
        
        assert response.status_code == 500
        data = response.json()
        assert "Analytics error" in data["detail"]
    
    @patch('app.rag_system')
    def test_courses_endpoint_anthropic_error(self, mock_rag):
        """Test courses endpoint with Anthropic API error"""
        mock_rag.get_course_analytics.side_effect = Exception("credit balance is too low")
        
        response = self.client.get("/api/courses")
        
        assert response.status_code == 402
        data = response.json()
        assert "credit balance too low" in data["detail"]
    
    @patch('app.rag_system')
    def test_clear_session_endpoint_success(self, mock_rag):
        """Test successful session clearing"""
        response = self.client.post(
            "/api/clear-session",
            json={
                "session_id": "test_session"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert "cleared successfully" in data["message"]
        
        # Verify session manager was called
        mock_rag.session_manager.clear_session.assert_called_with("test_session")
    
    @patch('app.rag_system')
    def test_clear_session_endpoint_error(self, mock_rag):
        """Test session clearing when it fails"""
        mock_rag.session_manager.clear_session.side_effect = Exception("Session error")
        
        response = self.client.post(
            "/api/clear-session",
            json={
                "session_id": "test_session"
            }
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "Session error" in data["detail"]
    
    def test_clear_session_endpoint_missing_session_id(self):
        """Test clear session endpoint with missing session_id"""
        response = self.client.post(
            "/api/clear-session",
            json={}  # Missing session_id
        )
        
        assert response.status_code == 422  # Validation error


class TestCORSAndMiddleware:
    """Test CORS and middleware functionality"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.client = TestClient(app)
    
    def test_cors_headers(self):
        """Test CORS headers are properly set"""
        with patch('app.rag_system') as mock_rag:
            mock_rag.query.return_value = ("Test", [])
            mock_rag.session_manager.create_session.return_value = "session_123"
            
            response = self.client.post(
                "/api/query",
                json={"query": "test"},
                headers={"Origin": "http://localhost:3000"}
            )
            
            assert response.status_code == 200
            # Should have CORS headers for development
            assert "access-control-allow-origin" in response.headers
    
    def test_options_request(self):
        """Test preflight OPTIONS request"""
        response = self.client.options(
            "/api/query",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        # Should handle preflight request
        assert response.status_code in [200, 204]


class TestResponseFormats:
    """Test response format compliance"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.client = TestClient(app)
    
    @patch('app.rag_system')
    def test_query_response_format(self, mock_rag):
        """Test that query response matches expected schema"""
        mock_rag.query.return_value = ("Test answer", [
            {"text": "Source 1", "link": "http://example.com"},
            {"text": "Source 2"}  # No link
        ])
        mock_rag.session_manager.create_session.return_value = "session_123"
        
        response = self.client.post(
            "/api/query",
            json={"query": "Test query"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        
        # Check data types
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)
        
        # Check source format
        assert len(data["sources"]) == 2
        assert data["sources"][0]["text"] == "Source 1"
        assert data["sources"][0]["link"] == "http://example.com"
        assert data["sources"][1]["text"] == "Source 2"
        assert "link" not in data["sources"][1] or data["sources"][1]["link"] is None
    
    @patch('app.rag_system')
    def test_courses_response_format(self, mock_rag):
        """Test that courses response matches expected schema"""
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 3,
            "course_titles": ["Course 1", "Course 2", "Course 3"]
        }
        
        response = self.client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "total_courses" in data
        assert "course_titles" in data
        
        # Check data types
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)
        
        # Check values
        assert data["total_courses"] == 3
        assert len(data["course_titles"]) == 3


class TestStaticFileServing:
    """Test static file serving for frontend"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.client = TestClient(app)
    
    def test_root_path_accessibility(self):
        """Test that root path is accessible (for static files)"""
        # This tests that the static file mount doesn't crash
        # The actual file serving depends on the frontend directory existing
        try:
            response = self.client.get("/")
            # Should either serve a file or return 404, but not crash
            assert response.status_code in [200, 404]
        except Exception as e:
            # If static directory doesn't exist, that's expected in tests
            assert "does not exist" in str(e) or "No such file" in str(e)


class TestErrorScenarios:
    """Test various error scenarios that could cause NetworkError"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.client = TestClient(app)
    
    @patch('app.rag_system')
    def test_large_query(self, mock_rag):
        """Test handling of very large queries"""
        mock_rag.query.return_value = ("Large query response", [])
        mock_rag.session_manager.create_session.return_value = "session_123"
        
        # Create a very large query
        large_query = "What is Python? " * 1000
        
        response = self.client.post(
            "/api/query",
            json={"query": large_query}
        )
        
        # Should handle large queries without crashing
        assert response.status_code in [200, 413, 422]  # Success, payload too large, or validation error
    
    @patch('app.rag_system')
    def test_unicode_query(self, mock_rag):
        """Test handling of unicode characters in queries"""
        mock_rag.query.return_value = ("Unicode response", [])
        mock_rag.session_manager.create_session.return_value = "session_123"
        
        response = self.client.post(
            "/api/query",
            json={"query": "What is Python? 中文 émojis 🐍"}
        )
        
        assert response.status_code == 200
        # Should handle unicode without issues
    
    @patch('app.rag_system')
    def test_malformed_json(self, mock_rag):
        """Test handling of malformed JSON requests"""
        response = self.client.post(
            "/api/query",
            data="malformed json",
            headers={"content-type": "application/json"}
        )
        
        assert response.status_code == 422  # Should return validation error
    
    @patch('app.rag_system')
    def test_timeout_simulation(self, mock_rag):
        """Test behavior with simulated timeout"""
        # Mock a slow response
        def slow_query(*args, **kwargs):
            import time
            time.sleep(0.1)  # Short delay for testing
            return ("Delayed response", [])
            
        mock_rag.query.side_effect = slow_query
        mock_rag.session_manager.create_session.return_value = "session_123"
        
        response = self.client.post(
            "/api/query",
            json={"query": "Slow query"}
        )
        
        # Should complete successfully even with delay
        assert response.status_code == 200


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])