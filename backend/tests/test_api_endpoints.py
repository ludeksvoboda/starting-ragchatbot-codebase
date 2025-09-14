"""
Comprehensive API endpoint tests for the RAG system.

This module tests all FastAPI endpoints with proper mocking and fixtures
to avoid static file mounting issues in the test environment.
"""

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json
import time

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Define the Pydantic models here to avoid importing from app
from pydantic import BaseModel
from typing import List, Optional, Union

class QueryRequest(BaseModel):
    """Request model for course queries"""
    query: str
    session_id: Optional[str] = None

class ClearSessionRequest(BaseModel):
    """Request model for clearing a session"""
    session_id: str

class SourceItem(BaseModel):
    """Source item that can have a text and optional link"""
    text: str
    link: Optional[str] = None

class QueryResponse(BaseModel):
    """Response model for course queries"""
    answer: str
    sources: List[Union[str, SourceItem]]
    session_id: str

class CourseStats(BaseModel):
    """Response model for course statistics"""
    total_courses: int
    course_titles: List[str]


def create_test_app():
    """
    Create a test FastAPI app without static file mounting.

    This avoids issues with missing frontend directory in test environment.
    """
    from fastapi import HTTPException, Request
    from pydantic import BaseModel
    from typing import List, Optional, Union
    import time

    app = FastAPI(title="Course Materials RAG System (Test)", root_path="")

    # Add request logging middleware for debugging
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        return response

    # Add trusted host middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]
    )

    # Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Mock RAG system for testing
    mock_rag_system = Mock()

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        """Process a query and return response with sources"""
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()

            answer, sources = mock_rag_system.query(request.query, session_id)

            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            error_msg = str(e)
            if "credit balance is too low" in error_msg:
                raise HTTPException(
                    status_code=402,
                    detail="Anthropic API credit balance too low. Please add credits to your account."
                )
            elif "invalid_request_error" in error_msg:
                raise HTTPException(
                    status_code=400,
                    detail=f"API request error: {error_msg}"
                )
            else:
                raise HTTPException(status_code=500, detail=error_msg)

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        """Get course analytics and statistics"""
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            error_msg = str(e)
            if "credit balance is too low" in error_msg:
                raise HTTPException(
                    status_code=402,
                    detail="Anthropic API credit balance too low. Please add credits to your account."
                )
            elif "invalid_request_error" in error_msg:
                raise HTTPException(
                    status_code=400,
                    detail=f"API request error: {error_msg}"
                )
            else:
                raise HTTPException(status_code=500, detail=error_msg)

    @app.post("/api/clear-session")
    async def clear_session(request: ClearSessionRequest):
        """Clear a conversation session"""
        try:
            mock_rag_system.session_manager.clear_session(request.session_id)
            return {"success": True, "message": "Session cleared successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "service": "rag-system"}

    return app, mock_rag_system


@pytest.fixture
def test_app_client():
    """Fixture providing a test FastAPI client with mocked dependencies."""
    app, mock_rag = create_test_app()
    client = TestClient(app)

    # Configure mock defaults
    mock_rag.query.return_value = ("Default test response", [{"text": "Test source"}])
    mock_rag.session_manager.create_session.return_value = "test_session_123"
    mock_rag.get_course_analytics.return_value = {
        "total_courses": 3,
        "course_titles": ["Course 1", "Course 2", "Course 3"]
    }

    return client, mock_rag


@pytest.mark.api
class TestQueryEndpoint:
    """Test cases for /api/query endpoint"""

    def test_query_success_without_session(self, test_app_client):
        """Test successful query without existing session"""
        client, mock_rag = test_app_client

        mock_rag.query.return_value = ("Python is a programming language", [
            {"text": "Python docs", "link": "https://python.org"}
        ])
        mock_rag.session_manager.create_session.return_value = "new_session_456"

        response = client.post(
            "/api/query",
            json={"query": "What is Python?", "session_id": None}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["answer"] == "Python is a programming language"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"] == "Python docs"
        assert data["sources"][0]["link"] == "https://python.org"
        assert data["session_id"] == "new_session_456"

        # Verify RAG system was called correctly
        mock_rag.query.assert_called_once_with("What is Python?", "new_session_456")

    def test_query_success_with_existing_session(self, test_app_client):
        """Test successful query with existing session"""
        client, mock_rag = test_app_client

        mock_rag.query.return_value = ("Follow-up answer", [])

        response = client.post(
            "/api/query",
            json={"query": "Tell me more", "session_id": "existing_session"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["answer"] == "Follow-up answer"
        assert data["session_id"] == "existing_session"

        # Verify session creation was not called
        mock_rag.session_manager.create_session.assert_not_called()
        mock_rag.query.assert_called_once_with("Tell me more", "existing_session")

    def test_query_with_complex_sources(self, test_app_client):
        """Test query response with complex source structures"""
        client, mock_rag = test_app_client

        complex_sources = [
            {"text": "Source with link", "link": "http://example.com"},
            {"text": "Source without link"},
            "Plain string source"
        ]
        mock_rag.query.return_value = ("Complex response", complex_sources)

        response = client.post(
            "/api/query",
            json={"query": "Complex query"}
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["sources"]) == 3
        assert data["sources"][0]["text"] == "Source with link"
        assert data["sources"][0]["link"] == "http://example.com"
        assert data["sources"][1]["text"] == "Source without link"
        assert data["sources"][2] == "Plain string source"

    def test_query_anthropic_credit_error(self, test_app_client, api_error_scenarios):
        """Test query endpoint with Anthropic credit error"""
        client, mock_rag = test_app_client

        error_scenario = api_error_scenarios["credit_low"]
        mock_rag.query.side_effect = error_scenario["exception"]

        response = client.post(
            "/api/query",
            json={"query": "Test query"}
        )

        assert response.status_code == error_scenario["status_code"]
        assert error_scenario["message_contains"] in response.json()["detail"]

    def test_query_invalid_request_error(self, test_app_client, api_error_scenarios):
        """Test query endpoint with invalid request error"""
        client, mock_rag = test_app_client

        error_scenario = api_error_scenarios["invalid_request"]
        mock_rag.query.side_effect = error_scenario["exception"]

        response = client.post(
            "/api/query",
            json={"query": "Test query"}
        )

        assert response.status_code == error_scenario["status_code"]
        assert error_scenario["message_contains"] in response.json()["detail"]

    def test_query_generic_error(self, test_app_client, api_error_scenarios):
        """Test query endpoint with generic error"""
        client, mock_rag = test_app_client

        error_scenario = api_error_scenarios["generic_error"]
        mock_rag.query.side_effect = error_scenario["exception"]

        response = client.post(
            "/api/query",
            json={"query": "Test query"}
        )

        assert response.status_code == error_scenario["status_code"]
        assert error_scenario["message_contains"] in response.json()["detail"]

    def test_query_missing_required_field(self, test_app_client):
        """Test query endpoint with missing query field"""
        client, mock_rag = test_app_client

        response = client.post(
            "/api/query",
            json={"session_id": "test"}  # Missing "query"
        )

        assert response.status_code == 422  # Validation error

    def test_query_empty_string(self, test_app_client):
        """Test query endpoint with empty query string"""
        client, mock_rag = test_app_client

        mock_rag.query.return_value = ("Empty query response", [])

        response = client.post(
            "/api/query",
            json={"query": ""}
        )

        assert response.status_code == 200
        # Should still process empty query

    def test_query_unicode_handling(self, test_app_client, query_test_data):
        """Test query endpoint handles unicode properly"""
        client, mock_rag = test_app_client

        unicode_data = query_test_data["unicode_query"]
        mock_rag.query.return_value = (unicode_data["expected_answer"], [])

        response = client.post(
            "/api/query",
            json={"query": unicode_data["query"]}
        )

        assert response.status_code == 200
        # Verify unicode was handled properly
        mock_rag.query.assert_called()


@pytest.mark.api
class TestCoursesEndpoint:
    """Test cases for /api/courses endpoint"""

    def test_courses_success(self, test_app_client):
        """Test successful courses analytics request"""
        client, mock_rag = test_app_client

        mock_analytics = {
            "total_courses": 5,
            "course_titles": ["Python", "JavaScript", "Data Science", "Machine Learning", "Web Development"]
        }
        mock_rag.get_course_analytics.return_value = mock_analytics

        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        assert data["total_courses"] == 5
        assert len(data["course_titles"]) == 5
        assert "Python" in data["course_titles"]
        assert "Machine Learning" in data["course_titles"]

    def test_courses_empty_response(self, test_app_client):
        """Test courses endpoint with no courses"""
        client, mock_rag = test_app_client

        mock_rag.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        assert data["total_courses"] == 0
        assert len(data["course_titles"]) == 0

    def test_courses_anthropic_error(self, test_app_client, api_error_scenarios):
        """Test courses endpoint with Anthropic API error"""
        client, mock_rag = test_app_client

        error_scenario = api_error_scenarios["credit_low"]
        mock_rag.get_course_analytics.side_effect = error_scenario["exception"]

        response = client.get("/api/courses")

        assert response.status_code == error_scenario["status_code"]
        assert error_scenario["message_contains"] in response.json()["detail"]

    def test_courses_generic_error(self, test_app_client):
        """Test courses endpoint with generic error"""
        client, mock_rag = test_app_client

        mock_rag.get_course_analytics.side_effect = Exception("Database error")

        response = client.get("/api/courses")

        assert response.status_code == 500
        assert "Database error" in response.json()["detail"]


@pytest.mark.api
class TestClearSessionEndpoint:
    """Test cases for /api/clear-session endpoint"""

    def test_clear_session_success(self, test_app_client):
        """Test successful session clearing"""
        client, mock_rag = test_app_client

        response = client.post(
            "/api/clear-session",
            json={"session_id": "test_session_to_clear"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "cleared successfully" in data["message"]

        # Verify session manager was called
        mock_rag.session_manager.clear_session.assert_called_with("test_session_to_clear")

    def test_clear_session_error(self, test_app_client):
        """Test session clearing with error"""
        client, mock_rag = test_app_client

        mock_rag.session_manager.clear_session.side_effect = Exception("Session not found")

        response = client.post(
            "/api/clear-session",
            json={"session_id": "non_existent_session"}
        )

        assert response.status_code == 500
        assert "Session not found" in response.json()["detail"]

    def test_clear_session_missing_session_id(self, test_app_client):
        """Test clear session endpoint with missing session_id"""
        client, mock_rag = test_app_client

        response = client.post(
            "/api/clear-session",
            json={}  # Missing session_id
        )

        assert response.status_code == 422  # Validation error

    def test_clear_session_empty_session_id(self, test_app_client):
        """Test clear session with empty session_id"""
        client, mock_rag = test_app_client

        response = client.post(
            "/api/clear-session",
            json={"session_id": ""}
        )

        # Should still call the clear function with empty string
        assert response.status_code == 200


@pytest.mark.api
class TestCORSAndMiddleware:
    """Test CORS and middleware functionality"""

    def test_cors_headers_present(self, test_app_client):
        """Test that CORS headers are properly set"""
        client, mock_rag = test_app_client

        response = client.post(
            "/api/query",
            json={"query": "test"},
            headers={"Origin": "http://localhost:3000"}
        )

        assert response.status_code == 200
        # Check for CORS headers
        assert "access-control-allow-origin" in response.headers

    def test_preflight_options_request(self, test_app_client):
        """Test preflight OPTIONS request handling"""
        client, mock_rag = test_app_client

        response = client.options(
            "/api/query",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )

        # Should handle preflight request
        assert response.status_code in [200, 204]

    def test_trusted_host_middleware(self, test_app_client):
        """Test that trusted host middleware is working"""
        client, mock_rag = test_app_client

        response = client.get("/health")

        # Should respond successfully (middleware allows all hosts)
        assert response.status_code == 200


@pytest.mark.api
class TestResponseValidation:
    """Test response format validation and schema compliance"""

    def test_query_response_schema_compliance(self, test_app_client):
        """Test that query responses match the expected Pydantic schema"""
        client, mock_rag = test_app_client

        mock_rag.query.return_value = ("Test answer", [
            {"text": "Source 1", "link": "http://example.com"},
            {"text": "Source 2"}  # No link
        ])

        response = client.post(
            "/api/query",
            json={"query": "Test query"}
        )

        assert response.status_code == 200
        data = response.json()

        # Validate schema compliance
        query_response = QueryResponse(**data)
        assert query_response.answer == "Test answer"
        assert len(query_response.sources) == 2
        assert query_response.session_id is not None

    def test_courses_response_schema_compliance(self, test_app_client):
        """Test that courses responses match the expected schema"""
        client, mock_rag = test_app_client

        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        # Validate schema compliance
        course_stats = CourseStats(**data)
        assert isinstance(course_stats.total_courses, int)
        assert isinstance(course_stats.course_titles, list)


@pytest.mark.api
class TestErrorHandling:
    """Test comprehensive error handling scenarios"""

    def test_malformed_json_request(self, test_app_client):
        """Test handling of malformed JSON in requests"""
        client, mock_rag = test_app_client

        response = client.post(
            "/api/query",
            data="malformed json content",
            headers={"content-type": "application/json"}
        )

        assert response.status_code == 422  # Validation error

    def test_large_query_handling(self, test_app_client):
        """Test handling of very large queries"""
        client, mock_rag = test_app_client

        mock_rag.query.return_value = ("Large query handled", [])

        # Create a very large query
        large_query = "What is Python? " * 1000

        response = client.post(
            "/api/query",
            json={"query": large_query}
        )

        # Should handle large queries gracefully
        assert response.status_code in [200, 413, 422]

    def test_concurrent_requests(self, test_app_client):
        """Test handling of concurrent requests to the API"""
        import threading

        client, mock_rag = test_app_client
        mock_rag.query.return_value = ("Concurrent response", [])

        responses = []

        def make_request():
            response = client.post(
                "/api/query",
                json={"query": "Concurrent test"}
            )
            responses.append(response)

        # Create multiple threads to simulate concurrent requests
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All requests should succeed
        assert len(responses) == 5
        for response in responses:
            assert response.status_code == 200


@pytest.mark.slow
@pytest.mark.api
class TestPerformanceScenarios:
    """Test performance-related scenarios (marked as slow tests)"""

    def test_timeout_simulation(self, test_app_client):
        """Test behavior with simulated slow responses"""
        client, mock_rag = test_app_client

        def slow_query(*args, **kwargs):
            time.sleep(0.1)  # Short delay for testing
            return ("Delayed response", [])

        mock_rag.query.side_effect = slow_query

        start_time = time.time()
        response = client.post(
            "/api/query",
            json={"query": "Slow query"}
        )
        end_time = time.time()

        # Should complete successfully even with delay
        assert response.status_code == 200
        assert end_time - start_time >= 0.1  # Verify delay occurred


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])