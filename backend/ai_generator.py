import anthropic
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import json


class TerminationReason(Enum):
    """Reasons why sequential tool calling terminates"""
    MAX_ROUNDS_REACHED = "max_rounds_reached"
    NO_TOOLS_REQUESTED = "no_tools_requested"
    TOOL_EXECUTION_ERROR = "tool_execution_error"


@dataclass
class ToolCallState:
    """Track state across tool calling rounds"""
    current_round: int = 0
    max_rounds: int = 2
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tools_executed: List[str] = field(default_factory=list)
    
    def is_complete(self) -> bool:
        """Check if we should terminate tool calling"""
        return self.current_round >= self.max_rounds
    
    def add_tool_execution(self, tool_name: str) -> None:
        """Track executed tools for debugging/logging"""
        self.tools_executed.append(f"Round {self.current_round}: {tool_name}")


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to comprehensive tools for course information.

Tool Usage Guidelines:
- **Sequential Tool Calling**: You can make up to 2 rounds of tool calls to gather comprehensive information
- **Content Search Tool**: Use to search INSIDE lessons for specific topics, concepts, explanations, or detailed content
- **Course Outline Tool**: Use to get lesson lists, course structure, titles, or to understand WHAT exists in a course
- **Strategy**: Consider what information you need upfront and plan your tool usage accordingly
- Synthesize all tool results into accurate, fact-based responses
- If tools yield no results, state this clearly without offering alternatives

Tool Selection Rules:
- **"What is lesson X about?"** → Use outline tool first to get lesson title/structure
- **"How many lessons?"** → Use outline tool 
- **"Course structure/outline?"** → Use outline tool
- **"List all lessons?"** → Use outline tool
- **"Search for [topic] in course"** → Use content search tool
- **"Explain [concept] from lesson"** → Use content search tool

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course content questions**: Use content search tool first, then additional tools if needed
- **Course outline/structure questions**: Use outline tool first, then content search if needed  
- **Complex queries**: May require multiple tool calls across rounds to fully address
- **Multi-step queries**: Use first round to gather initial information, second round to refine or get additional details
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
 - Do not mention "based on the search results" or "using the tool"

For Course Outline Queries:
- Always return the complete course title, course link (if available), and full lesson list
- Include lesson numbers and lesson titles for each lesson
- Present information in a clear, organized format

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with support for up to 2 sequential tool calling rounds.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Initialize tool call state
        state = ToolCallState(
            messages=[{"role": "user", "content": query}],
            max_rounds=2
        )
        
        # Build base system content
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Sequential tool calling loop
        while not state.is_complete():
            state.current_round += 1
            
            # Get round-specific system prompt
            round_system_content = self._get_round_system_prompt(system_content, state.current_round)
            
            # Prepare API call parameters
            api_params = {
                **self.base_params,
                "messages": state.messages.copy(),
                "system": round_system_content
            }
            
            # Add tools if available and not at max rounds
            if tools and state.current_round <= state.max_rounds:
                api_params["tools"] = tools
                api_params["tool_choice"] = {"type": "auto"}
            
            try:
                # Get response from Claude
                response = self.client.messages.create(**api_params)
                
                # Add assistant response to messages
                state.messages.append({"role": "assistant", "content": response.content})
                
                # Check if tools were used
                if response.stop_reason == "tool_use" and tool_manager:
                    # Execute tools and add results
                    tool_error = self._execute_round_tools(response, state, tool_manager)
                    
                    # If tool execution failed, terminate
                    if tool_error:
                        return f"Unable to complete search: {tool_error}"
                        
                else:
                    # No tools used, we're done
                    return response.content[0].text
                    
            except Exception as e:
                # API error, return what we have or error message
                return f"Error generating response: {str(e)}"
        
        # Max rounds reached, make final call without tools
        final_system_content = f"{system_content}\n\nTool calling rounds complete. Provide your final answer based on all available information."
        
        final_params = {
            **self.base_params,
            "messages": state.messages,
            "system": final_system_content
        }
        
        try:
            final_response = self.client.messages.create(**final_params)
            return final_response.content[0].text
        except Exception as e:
            return f"Error generating final response: {str(e)}"
    
    def _get_round_system_prompt(self, base_system_content: str, round_number: int) -> str:
        """
        Generate round-specific system prompt with guidance.
        
        Args:
            base_system_content: Base system prompt content
            round_number: Current round (1 or 2)
            
        Returns:
            System prompt with round-specific guidance
        """
        if round_number == 1:
            round_guidance = "\nThis is your first opportunity to use tools. Consider what information you need to fully answer the user's question and gather initial data."
        elif round_number == 2:
            round_guidance = "\nThis is your second and final opportunity to use tools. Based on previous results, determine if additional information is needed to complete your answer."
        else:
            round_guidance = "\nTool calling rounds are complete. Provide your final answer based on all available information."
            
        return f"{base_system_content}{round_guidance}"
    
    def _execute_round_tools(self, response, state: ToolCallState, tool_manager) -> Optional[str]:
        """
        Execute all tool calls from current round and add results to state.
        
        Args:
            response: Claude's response containing tool calls
            state: Current tool call state to update
            tool_manager: Tool execution manager
            
        Returns:
            Error message if tool execution fails, None if successful
        """
        tool_results = []
        
        for content_block in response.content:
            if content_block.type == "tool_use":
                # Print tool call information to terminal
                print(f"\n🔧 [Round {state.current_round}] Tool Call:")
                print(f"   Tool: {content_block.name}")
                print(f"   Input: {json.dumps(content_block.input, indent=2)}")
                
                try:
                    # Execute the tool
                    tool_result = tool_manager.execute_tool(
                        content_block.name, 
                        **content_block.input
                    )
                    
                    # Print successful result (truncated if too long)
                    result_preview = tool_result[:200] + "..." if len(tool_result) > 200 else tool_result
                    print(f"   ✅ Result: {result_preview}")
                    
                    # Track tool execution
                    state.add_tool_execution(content_block.name)
                    
                    # Add result
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result
                    })
                    
                except Exception as e:
                    # Print error information
                    print(f"   ❌ Error: {str(e)}")
                    
                    # Tool execution failed
                    error_msg = f"Tool {content_block.name} failed: {str(e)}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": error_msg,
                        "is_error": True
                    })
                    return error_msg
        
        # Add tool results to state messages
        if tool_results:
            state.messages.append({"role": "user", "content": tool_results})
        
        return None