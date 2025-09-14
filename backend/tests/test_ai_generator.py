"""
Tests for ai_generator.py - AIGenerator tool integration functionality.

These tests help diagnose potential issues in AI tool calling that could
cause NetworkError in the RAG chatbot.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from typing import List, Dict, Any, Optional
import json

# Import the classes we're testing
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_generator import AIGenerator
from search_tools import ToolManager, CourseSearchTool


class MockAnthropicClient:
    """Mock Anthropic client for testing without real API calls"""
    
    def __init__(self):
        self.should_fail = False
        self.response_text = "Test AI response"
        self.should_use_tools = False
        self.tool_calls = []
        self.messages_history = []
        self.call_count = 0
        self.multi_round_responses = []  # For sequential responses in multi-round tests
        
    def messages(self):
        return self
        
    def create(self, **kwargs):
        """Mock create method for messages"""
        # Store the request for inspection
        self.messages_history.append(kwargs)
        self.call_count += 1
        
        if self.should_fail:
            raise Exception("Mock API error")
            
        # Create mock response
        mock_response = Mock()
        
        # Handle multi-round responses
        if self.multi_round_responses:
            response_config = self.multi_round_responses[min(self.call_count - 1, len(self.multi_round_responses) - 1)]
            
            if response_config.get("use_tools", False) and "tools" in kwargs:
                # Mock tool use response
                mock_response.stop_reason = "tool_use"
                mock_response.content = []
                
                for tool_call in response_config.get("tool_calls", []):
                    mock_block = Mock()
                    mock_block.type = "tool_use"
                    mock_block.name = tool_call["name"]
                    mock_block.input = tool_call["input"]
                    mock_block.id = f"tool_call_{len(mock_response.content)}"
                    mock_response.content.append(mock_block)
            else:
                # Mock direct text response
                mock_response.stop_reason = "end_turn"
                mock_block = Mock()
                mock_block.text = response_config.get("text", "Test response")
                mock_response.content = [mock_block]
                
        elif self.should_use_tools and "tools" in kwargs:
            # Mock tool use response (legacy behavior)
            mock_response.stop_reason = "tool_use"
            mock_response.content = []
            
            for tool_call in self.tool_calls:
                mock_block = Mock()
                mock_block.type = "tool_use"
                mock_block.name = tool_call["name"]
                mock_block.input = tool_call["input"]
                mock_block.id = f"tool_call_{len(mock_response.content)}"
                mock_response.content.append(mock_block)
        else:
            # Mock direct text response (legacy behavior)
            mock_response.stop_reason = "end_turn"
            mock_block = Mock()
            mock_block.text = self.response_text
            mock_response.content = [mock_block]
            
        return mock_response
    
    def reset(self):
        """Reset mock state for new tests"""
        self.call_count = 0
        self.messages_history = []
        self.multi_round_responses = []
        self.should_fail = False
        self.should_use_tools = False
        self.tool_calls = []


class MockToolManager:
    """Mock ToolManager for testing without real tools"""
    
    def __init__(self):
        self.tools_executed = []
        self.tool_results = {}
        
    def get_tool_definitions(self):
        """Return mock tool definitions"""
        return [
            {
                "name": "search_course_content",
                "description": "Search course materials",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Mock tool execution"""
        self.tools_executed.append({"name": tool_name, "args": kwargs})
        return self.tool_results.get(tool_name, f"Mock result for {tool_name}")


class TestAIGenerator:
    """Test cases for AIGenerator"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.mock_client = MockAnthropicClient()
        self.ai_generator = AIGenerator("fake-api-key", "claude-sonnet-4")
        
        # Replace the real client with our mock
        self.ai_generator.client = Mock()
        self.ai_generator.client.messages.create = self.mock_client.create
        
        # Reset mock state for each test
        self.mock_client.reset()
    
    def test_initialization(self):
        """Test AIGenerator initialization"""
        assert self.ai_generator.model == "claude-sonnet-4"
        assert self.ai_generator.base_params["model"] == "claude-sonnet-4"
        assert self.ai_generator.base_params["temperature"] == 0
        assert self.ai_generator.base_params["max_tokens"] == 800
    
    def test_generate_response_simple(self):
        """Test simple response generation without tools"""
        self.mock_client.response_text = "This is a test response"
        
        result = self.ai_generator.generate_response("What is Python?")
        
        assert result == "This is a test response"
        assert len(self.mock_client.messages_history) == 1
        
        # Verify the request structure
        request = self.mock_client.messages_history[0]
        assert request["messages"][0]["content"] == "What is Python?"
        assert request["messages"][0]["role"] == "user"
        assert self.ai_generator.SYSTEM_PROMPT in request["system"]
    
    def test_generate_response_with_conversation_history(self):
        """Test response generation with conversation history"""
        history = "Previous conversation context"
        self.mock_client.response_text = "Response with context"
        
        result = self.ai_generator.generate_response(
            "Follow up question",
            conversation_history=history
        )
        
        assert result == "Response with context"
        
        # Verify history is included in system prompt
        request = self.mock_client.messages_history[0]
        assert history in request["system"]
    
    def test_generate_response_with_tools_no_usage(self):
        """Test response with tools available but not used"""
        mock_tool_manager = MockToolManager()
        self.mock_client.response_text = "Direct answer without tools"
        
        result = self.ai_generator.generate_response(
            "General knowledge question",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager
        )
        
        assert result == "Direct answer without tools"
        assert len(mock_tool_manager.tools_executed) == 0
        
        # Verify tools were provided in request
        request = self.mock_client.messages_history[0]
        assert "tools" in request
        assert len(request["tools"]) == 1
    
    def test_generate_response_with_tool_usage(self):
        """Test response generation with tool usage"""
        mock_tool_manager = MockToolManager()
        mock_tool_manager.tool_results["search_course_content"] = "Found course content about Python"
        
        # Setup mock to indicate tool usage
        self.mock_client.should_use_tools = True
        self.mock_client.tool_calls = [
            {
                "name": "search_course_content",
                "input": {"query": "Python programming"}
            }
        ]
        self.mock_client.response_text = "Based on the search results, Python is..."
        
        result = self.ai_generator.generate_response(
            "What is Python?",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager
        )
        
        assert result == "Based on the search results, Python is..."
        # With sequential calling, tools might be executed multiple times
        assert len(mock_tool_manager.tools_executed) >= 1
        
        # Verify tool was executed correctly
        tool_execution = mock_tool_manager.tools_executed[0]
        assert tool_execution["name"] == "search_course_content"
        assert tool_execution["args"]["query"] == "Python programming"
        
        # Should have made at least two API calls for tool workflow
        assert len(self.mock_client.messages_history) >= 2
    
    def test_handle_tool_execution_error(self):
        """Test tool execution when tool manager fails"""
        mock_tool_manager = Mock()
        mock_tool_manager.get_tool_definitions.return_value = [{"name": "test_tool"}]
        mock_tool_manager.execute_tool.side_effect = Exception("Tool execution failed")
        
        # Setup mock for tool use
        self.mock_client.should_use_tools = True
        self.mock_client.tool_calls = [
            {
                "name": "test_tool",
                "input": {"query": "test"}
            }
        ]
        
        # This should not crash, but handle the error gracefully
        # The implementation should catch tool execution errors
        try:
            result = self.ai_generator.generate_response(
                "test query",
                tools=mock_tool_manager.get_tool_definitions(),
                tool_manager=mock_tool_manager
            )
            # If we get here, error was handled
            assert True
        except Exception as e:
            # If we get here, error was not handled properly
            pytest.fail(f"Tool execution error not handled: {e}")
    
    def test_api_error_handling(self):
        """Test handling of Anthropic API errors"""
        self.mock_client.should_fail = True
        
        result = self.ai_generator.generate_response("test query")
        
        # Should handle error gracefully and return error message
        assert "Error generating response" in result
        assert "Mock API error" in result
    
    def test_system_prompt_content(self):
        """Test that system prompt contains expected content"""
        system_prompt = self.ai_generator.SYSTEM_PROMPT
        
        # Check for key elements that should be in the system prompt
        assert "course materials" in system_prompt.lower()
        assert "tool" in system_prompt.lower()
        assert "search" in system_prompt.lower()
    
    def test_handle_tool_execution_workflow(self):
        """Test the complete tool execution workflow"""
        # Create real tool manager with mock vector store
        class LocalMockVectorStore:
            def __init__(self):
                self.search_results = []
            
            def search(self, query, course_name=None, lesson_number=None):
                from vector_store import SearchResults
                return SearchResults(
                    documents=self.search_results,
                    metadata=[{'course_title': 'Test Course', 'lesson_number': 1}] * len(self.search_results),
                    distances=[0.1] * len(self.search_results)
                )
            
            def get_lesson_link(self, course_title, lesson_number):
                return f"https://example.com/{course_title}/lesson/{lesson_number}"
        
        mock_vector_store = LocalMockVectorStore()
        mock_vector_store.search_results = ["Python is a programming language"]
        
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        tool_manager.register_tool(search_tool)
        
        # Setup mock for tool usage
        self.mock_client.should_use_tools = True
        self.mock_client.tool_calls = [
            {
                "name": "search_course_content",
                "input": {"query": "Python programming"}
            }
        ]
        self.mock_client.response_text = "Based on search: Python is a language"
        
        result = self.ai_generator.generate_response(
            "What is Python?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )
        
        assert result == "Based on search: Python is a language"
        
        # Verify the workflow - should have at least 2 API calls
        assert len(self.mock_client.messages_history) >= 2
        
        # First call should have tools
        first_request = self.mock_client.messages_history[0]
        assert "tools" in first_request
        
        # Subsequent calls should handle tool results
        if len(self.mock_client.messages_history) > 1:
            later_request = self.mock_client.messages_history[1]
            assert len(later_request["messages"]) >= 2  # user + assistant + tool results
            
            # Tool results should be in the messages
            tool_result_message = None
            for message in later_request["messages"]:
                if message["role"] == "user" and isinstance(message["content"], list):
                    tool_result_message = message
                    break
            
            if tool_result_message:
                assert len(tool_result_message["content"]) > 0
                assert tool_result_message["content"][0]["type"] == "tool_result"
    
    def test_sequential_tool_calling_two_rounds(self):
        """Test sequential tool calling with 2 rounds"""
        self.mock_client.reset()
        
        mock_tool_manager = MockToolManager()
        mock_tool_manager.tool_results = {
            "search_course_content": "Found Python basics course",
            "get_course_outline": "Python course has 5 lessons"
        }
        
        # Setup for 2 rounds of tool calls
        self.mock_client.multi_round_responses = [
            {
                "use_tools": True,
                "tool_calls": [{"name": "search_course_content", "input": {"query": "Python basics"}}],
                "text": "First round response"
            },
            {
                "use_tools": True, 
                "tool_calls": [{"name": "get_course_outline", "input": {"course_name": "Python Basics"}}],
                "text": "Second round response"
            },
            {
                "use_tools": False,
                "text": "Final response with all information from both searches"
            }
        ]
        
        result = self.ai_generator.generate_response(
            "Find a Python basics course and tell me its structure",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager
        )
        
        # Should have executed both tools
        assert len(mock_tool_manager.tools_executed) == 2
        assert mock_tool_manager.tools_executed[0]["name"] == "search_course_content"
        assert mock_tool_manager.tools_executed[1]["name"] == "get_course_outline"
        
        # Should have made 3 API calls (2 tool rounds + final)
        assert self.mock_client.call_count == 3
        assert result == "Final response with all information from both searches"
    
    def test_sequential_tool_calling_early_termination(self):
        """Test early termination when no tools are used in round 1"""
        self.mock_client.reset()
        
        mock_tool_manager = MockToolManager()
        
        # Setup for immediate termination (no tools used)
        self.mock_client.multi_round_responses = [
            {
                "use_tools": False,
                "text": "Direct answer without needing tools"
            }
        ]
        
        result = self.ai_generator.generate_response(
            "What is Python?",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager
        )
        
        # Should have executed no tools
        assert len(mock_tool_manager.tools_executed) == 0
        
        # Should have made only 1 API call
        assert self.mock_client.call_count == 1
        assert result == "Direct answer without needing tools"
    
    def test_sequential_tool_calling_max_rounds(self):
        """Test termination when hitting max 2 rounds"""
        self.mock_client.reset()
        
        mock_tool_manager = MockToolManager()
        mock_tool_manager.tool_results = {
            "search_course_content": "Search result"
        }
        
        # Setup for max rounds (2 rounds of tools + final)
        self.mock_client.multi_round_responses = [
            {
                "use_tools": True,
                "tool_calls": [{"name": "search_course_content", "input": {"query": "first search"}}],
                "text": "Round 1"
            },
            {
                "use_tools": True,
                "tool_calls": [{"name": "search_course_content", "input": {"query": "second search"}}], 
                "text": "Round 2"
            },
            {
                "use_tools": False,
                "text": "Final response after max rounds reached"
            }
        ]
        
        result = self.ai_generator.generate_response(
            "Complex multi-step query",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager
        )
        
        # Should have executed 2 tools (max rounds)
        assert len(mock_tool_manager.tools_executed) == 2
        
        # Should have made 3 API calls (2 rounds + final)
        assert self.mock_client.call_count == 3
        assert result == "Final response after max rounds reached"
    
    def test_sequential_tool_calling_tool_error(self):
        """Test handling of tool execution errors in sequential calling"""
        self.mock_client.reset()
        
        mock_tool_manager = Mock()
        mock_tool_manager.get_tool_definitions.return_value = [{"name": "failing_tool"}]
        mock_tool_manager.execute_tool.side_effect = Exception("Tool execution failed")
        
        # Setup for tool error
        self.mock_client.multi_round_responses = [
            {
                "use_tools": True,
                "tool_calls": [{"name": "failing_tool", "input": {"query": "test"}}],
                "text": "Tool call attempted"
            }
        ]
        
        result = self.ai_generator.generate_response(
            "Query that triggers tool error",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager
        )
        
        # Should handle error gracefully
        assert "Unable to complete search" in result
        assert "Tool execution failed" in result
        
        # Should have made only 1 API call before error
        assert self.mock_client.call_count == 1
    
    def test_round_specific_system_prompts(self):
        """Test that system prompts are modified per round"""
        self.mock_client.reset()
        
        mock_tool_manager = MockToolManager()
        mock_tool_manager.tool_results["search_course_content"] = "Test result"
        
        # Setup for 2 rounds to test system prompts
        self.mock_client.multi_round_responses = [
            {
                "use_tools": True,
                "tool_calls": [{"name": "search_course_content", "input": {"query": "test"}}],
                "text": "Round 1"
            },
            {
                "use_tools": False,
                "text": "Final response"
            }
        ]
        
        result = self.ai_generator.generate_response(
            "Test query",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager
        )
        
        # Check that system prompts were different for each round
        assert len(self.mock_client.messages_history) == 2
        
        round1_system = self.mock_client.messages_history[0]["system"]
        round2_system = self.mock_client.messages_history[1]["system"]
        
        assert "first opportunity to use tools" in round1_system
        assert "second and final opportunity" in round2_system
        assert round1_system != round2_system


class TestAIGeneratorIntegration:
    """Integration tests for AIGenerator with real tool components"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.mock_client = MockAnthropicClient()
        self.ai_generator = AIGenerator("fake-api-key", "claude-sonnet-4")
        self.ai_generator.client = Mock()
        self.ai_generator.client.messages.create = self.mock_client.create
        self.mock_client.reset()
    
    def test_integration_with_search_tool(self):
        """Test full integration with CourseSearchTool"""
        # Use the MockVectorStore from this file instead
        class LocalMockVectorStore:
            def __init__(self):
                self.search_results = []
            
            def search(self, query, course_name=None, lesson_number=None):
                from vector_store import SearchResults
                return SearchResults(
                    documents=self.search_results,
                    metadata=[{'course_title': 'Test Course', 'lesson_number': 1}] * len(self.search_results),
                    distances=[0.1] * len(self.search_results)
                )
            
            def get_lesson_link(self, course_title, lesson_number):
                return f"https://example.com/{course_title}/lesson/{lesson_number}"
        
        mock_vector_store = LocalMockVectorStore()
        mock_vector_store.search_results = ["Course content about data structures"]
        
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        tool_manager.register_tool(search_tool)
        
        # Test tool registration
        definitions = tool_manager.get_tool_definitions()
        assert len(definitions) == 1
        assert definitions[0]["name"] == "search_course_content"
        
        # Test that AI can use the tool
        self.mock_client.should_use_tools = True
        self.mock_client.tool_calls = [
            {
                "name": "search_course_content", 
                "input": {"query": "data structures", "course_name": "Computer Science"}
            }
        ]
        self.mock_client.response_text = "Data structures are fundamental concepts..."
        
        result = self.ai_generator.generate_response(
            "Tell me about data structures",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )
        
        assert "Data structures are fundamental concepts..." in result
        
        # Verify sources were tracked
        sources = tool_manager.get_last_sources()
        assert len(sources) == 1
    
    def test_multiple_tool_calls(self):
        """Test AI making multiple tool calls in sequence"""
        # Use local mock vector store
        class LocalMockVectorStore:
            def __init__(self):
                self.search_results = []
            
            def search(self, query, course_name=None, lesson_number=None):
                from vector_store import SearchResults
                return SearchResults(
                    documents=self.search_results,
                    metadata=[{'course_title': 'Test Course', 'lesson_number': 1}] * len(self.search_results),
                    distances=[0.1] * len(self.search_results)
                )
            
            def get_lesson_link(self, course_title, lesson_number):
                return f"https://example.com/{course_title}/lesson/{lesson_number}"
        
        mock_vector_store = LocalMockVectorStore()
        mock_vector_store.search_results = ["Result for tool call"]
        
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        tool_manager.register_tool(search_tool)
        
        # Setup multiple tool calls
        self.mock_client.should_use_tools = True
        self.mock_client.tool_calls = [
            {
                "name": "search_course_content",
                "input": {"query": "Python basics"}
            },
            {
                "name": "search_course_content", 
                "input": {"query": "Python advanced", "course_name": "Advanced Python"}
            }
        ]
        self.mock_client.response_text = "Combined results from multiple searches"
        
        result = self.ai_generator.generate_response(
            "Compare Python basics and advanced topics",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )
        
        assert result == "Combined results from multiple searches"
        
        # Should have executed both tool calls
        # Note: In actual implementation, we'd need to track tool executions better
    
    def test_error_recovery(self):
        """Test error recovery when tools fail"""
        # Create a tool manager that will fail
        failing_tool_manager = Mock()
        failing_tool_manager.get_tool_definitions.return_value = [
            {"name": "failing_tool", "description": "A tool that fails"}
        ]
        failing_tool_manager.execute_tool.side_effect = Exception("Tool failed")
        
        self.mock_client.should_use_tools = True
        self.mock_client.tool_calls = [
            {
                "name": "failing_tool",
                "input": {"query": "test"}
            }
        ]
        self.mock_client.response_text = "I couldn't search, but here's general info"
        
        # Should handle tool failure gracefully
        result = self.ai_generator.generate_response(
            "test query",
            tools=failing_tool_manager.get_tool_definitions(),
            tool_manager=failing_tool_manager
        )
        
        # Should still return a response despite tool failure
        assert result is not None
        assert len(result) > 0


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])