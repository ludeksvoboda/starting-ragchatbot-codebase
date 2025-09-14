"""
Shared test fixtures and configuration for the RAG system tests.

This module provides common fixtures, mocks, and test utilities used across
all test files in the test suite.
"""

import pytest
import tempfile
import shutil
import os
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List, Any, Optional
from fastapi.testclient import TestClient

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules without importing the main app to avoid static file issues
try:
    from config import Config
    from models import Course, Lesson, CourseChunk
except ImportError:
    # Fallback if imports fail
    Config = None
    Course = None
    Lesson = None
    CourseChunk = None


class MockRAGSystem:
    """
    Mock RAG system for consistent testing across all test files.

    This mock provides configurable responses and error conditions
    for testing different scenarios.
    """

    def __init__(self):
        self.should_fail = False
        self.should_timeout = False
        self.query_response = "Test response from RAG system"
        self.query_sources = [{"text": "Test source", "link": "http://example.com"}]
        self.session_id = "test_session_123"
        self.analytics_data = {
            "total_courses": 3,
            "course_titles": ["Introduction to Python", "Advanced JavaScript", "Data Science Fundamentals"]
        }
        self.queries_received = []

        # Mock session manager
        self.session_manager = Mock()
        self.session_manager.create_session.return_value = self.session_id
        self.session_manager.clear_session.return_value = None
        self.session_manager.get_session_history.return_value = []

    def query(self, query_text: str, session_id: str = None) -> tuple:
        """Mock query method with configurable responses."""
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
        """Mock analytics method."""
        if self.should_fail:
            raise Exception("Mock analytics error")

        return self.analytics_data

    def add_course_folder(self, folder_path: str, clear_existing: bool = False):
        """Mock course folder addition."""
        return 3, 150  # courses, chunks

    def reset(self):
        """Reset mock state between tests."""
        self.should_fail = False
        self.should_timeout = False
        self.queries_received = []


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self):
        self.ANTHROPIC_API_KEY = "test_api_key"
        self.CHUNK_SIZE = 1000
        self.CHUNK_OVERLAP = 200
        self.MAX_RESULTS = 5
        self.DATABASE_PATH = "./test_chroma_db"
        self.DOCS_FOLDER = "./test_docs"


@pytest.fixture
def mock_rag_system():
    """
    Fixture providing a mock RAG system for testing.

    Returns:
        MockRAGSystem: Configured mock RAG system
    """
    mock_system = MockRAGSystem()
    yield mock_system
    mock_system.reset()


@pytest.fixture
def mock_config():
    """
    Fixture providing a mock configuration for testing.

    Returns:
        MockConfig: Test configuration object
    """
    return MockConfig()


@pytest.fixture
def api_client():
    """
    Fixture providing a FastAPI test client.

    This client is configured to work with the mocked RAG system
    and avoids issues with static file serving in the test environment.

    Returns:
        TestClient: Configured FastAPI test client
    """
    # This fixture is deprecated in favor of test_app_client in test_api_endpoints.py
    # which creates its own test app without static file mounting issues
    pytest.skip("Use test_app_client fixture from test_api_endpoints.py instead")


@pytest.fixture
def sample_courses():
    """
    Fixture providing sample course data for testing.

    Returns:
        List[Dict] or List[Course]: List of sample course objects or dicts
    """
    if Course and Lesson:
        return [
            Course(
                title="Introduction to Python",
                instructor="Dr. Jane Smith",
                description="A comprehensive introduction to Python programming",
                lessons=[
                    Lesson(title="Variables and Data Types", content="Learn about Python variables..."),
                    Lesson(title="Control Structures", content="Understanding loops and conditionals..."),
                ]
            ),
            Course(
                title="Advanced JavaScript",
                instructor="Prof. John Doe",
                description="Advanced concepts in JavaScript development",
                lessons=[
                    Lesson(title="Async Programming", content="Understanding promises and async/await..."),
                    Lesson(title="ES6 Features", content="Modern JavaScript features..."),
                ]
            ),
            Course(
                title="Data Science Fundamentals",
                instructor="Dr. Alice Johnson",
                description="Introduction to data science concepts",
                lessons=[
                    Lesson(title="Data Analysis", content="Working with pandas and numpy..."),
                    Lesson(title="Visualization", content="Creating charts with matplotlib..."),
                ]
            )
        ]
    else:
        # Return dictionary data if models aren't available
        return [
            {
                "title": "Introduction to Python",
                "instructor": "Dr. Jane Smith",
                "description": "A comprehensive introduction to Python programming",
                "lessons": [
                    {"title": "Variables and Data Types", "content": "Learn about Python variables..."},
                    {"title": "Control Structures", "content": "Understanding loops and conditionals..."},
                ]
            },
            {
                "title": "Advanced JavaScript",
                "instructor": "Prof. John Doe",
                "description": "Advanced concepts in JavaScript development",
                "lessons": [
                    {"title": "Async Programming", "content": "Understanding promises and async/await..."},
                    {"title": "ES6 Features", "content": "Modern JavaScript features..."},
                ]
            }
        ]


@pytest.fixture
def sample_chunks():
    """
    Fixture providing sample course chunks for testing.

    Returns:
        List[CourseChunk] or List[Dict]: List of sample course chunk objects or dicts
    """
    if CourseChunk:
        return [
            CourseChunk(
                course_title="Introduction to Python",
                lesson_title="Variables and Data Types",
                content="Python variables are containers for storing data values...",
                chunk_id="python_vars_1"
            ),
            CourseChunk(
                course_title="Introduction to Python",
                lesson_title="Control Structures",
                content="Python has several control structures like if statements...",
                chunk_id="python_control_1"
            ),
            CourseChunk(
                course_title="Advanced JavaScript",
                lesson_title="Async Programming",
                content="JavaScript async programming allows non-blocking operations...",
                chunk_id="js_async_1"
            )
        ]
    else:
        # Return dictionary data if models aren't available
        return [
            {
                "course_title": "Introduction to Python",
                "lesson_title": "Variables and Data Types",
                "content": "Python variables are containers for storing data values...",
                "chunk_id": "python_vars_1"
            },
            {
                "course_title": "Introduction to Python",
                "lesson_title": "Control Structures",
                "content": "Python has several control structures like if statements...",
                "chunk_id": "python_control_1"
            },
            {
                "course_title": "Advanced JavaScript",
                "lesson_title": "Async Programming",
                "content": "JavaScript async programming allows non-blocking operations...",
                "chunk_id": "js_async_1"
            }
        ]


@pytest.fixture
def temp_docs_folder():
    """
    Fixture providing a temporary docs folder for testing.

    Creates a temporary directory with sample document files,
    then cleans up after the test.

    Returns:
        str: Path to temporary docs folder
    """
    temp_dir = tempfile.mkdtemp(prefix="test_docs_")

    # Create sample documents
    sample_docs = {
        "python_course.txt": """
Introduction to Python

Instructor: Dr. Jane Smith

Lesson 1: Variables and Data Types
Python variables are containers for storing data values. Unlike other programming languages, Python has no command for declaring a variable.

Lesson 2: Control Structures
Python uses indentation to indicate a block of code. Control structures like if statements, for loops, and while loops are essential.
        """,
        "javascript_course.txt": """
Advanced JavaScript

Instructor: Prof. John Doe

Lesson 1: Async Programming
JavaScript async programming allows you to perform non-blocking operations using promises and async/await syntax.

Lesson 2: ES6 Features
Modern JavaScript includes many new features like arrow functions, destructuring, and template literals.
        """
    }

    for filename, content in sample_docs.items():
        with open(os.path.join(temp_dir, filename), 'w') as f:
            f.write(content.strip())

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_db_path():
    """
    Fixture providing a temporary database path for testing.

    Creates a temporary directory for the test database,
    then cleans up after the test.

    Returns:
        str: Path to temporary database directory
    """
    temp_dir = tempfile.mkdtemp(prefix="test_chroma_db_")
    yield temp_dir

    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def mock_anthropic_client():
    """
    Fixture providing a mock Anthropic API client.

    Returns:
        Mock: Mock Anthropic client with configurable responses
    """
    mock_client = Mock()

    # Mock message response
    mock_message = Mock()
    mock_message.content = [Mock()]
    mock_message.content[0].text = "Mock AI response"

    mock_client.messages.create.return_value = mock_message

    return mock_client


@pytest.fixture
def api_error_scenarios():
    """
    Fixture providing common API error scenarios for testing.

    Returns:
        Dict: Dictionary of error scenarios and their expected responses
    """
    return {
        "credit_low": {
            "exception": Exception("credit balance is too low"),
            "status_code": 402,
            "message_contains": "credit balance too low"
        },
        "invalid_request": {
            "exception": Exception("invalid_request_error: bad parameters"),
            "status_code": 400,
            "message_contains": "API request error"
        },
        "generic_error": {
            "exception": Exception("Internal server error"),
            "status_code": 500,
            "message_contains": "Internal server error"
        }
    }


@pytest.fixture(autouse=True)
def setup_test_environment():
    """
    Fixture that runs before each test to set up the test environment.

    This fixture automatically runs before each test and ensures:
    - Clean state for each test
    - Proper environment variables
    - Mock external dependencies
    """
    # Set test environment variables
    os.environ["ANTHROPIC_API_KEY"] = "test_key"

    yield

    # Cleanup after test
    # Remove any test-specific environment variables if needed


@pytest.fixture
def query_test_data():
    """
    Fixture providing test data for query testing.

    Returns:
        Dict: Test queries and expected responses
    """
    return {
        "simple_query": {
            "query": "What is Python?",
            "expected_answer": "Python is a programming language",
            "expected_sources": [{"text": "Python documentation", "link": "http://python.org"}]
        },
        "course_specific": {
            "query": "Tell me about variables in the Python course",
            "expected_answer": "Variables in Python are containers for data",
            "expected_sources": [{"text": "Python course lesson 1"}]
        },
        "empty_query": {
            "query": "",
            "expected_answer": "Please provide a question",
            "expected_sources": []
        },
        "unicode_query": {
            "query": "What is Python? 中文 émojis 🐍",
            "expected_answer": "Python with unicode support",
            "expected_sources": []
        }
    }


# Mark slow tests
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "api: marks tests as API tests")