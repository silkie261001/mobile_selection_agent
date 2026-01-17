"""
Agent builder for the shopping chat agent with configurable LLM backend (Ollama or Gemini).
"""
import os
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator
from openai import OpenAI

from .prompts import get_full_system_prompt, is_adversarial_query, ADVERSARIAL_RESPONSES, get_tech_explanation
from .tools import get_all_tools

# Thread pool for running synchronous OpenAI calls
_executor = ThreadPoolExecutor(max_workers=4)


logger = logging.getLogger(__name__)


# LLM Provider Configuration
# Set USE_GEMINI=true to use Gemini API, otherwise defaults to Ollama
USE_GEMINI = os.getenv("USE_GEMINI", "false").lower() == "true"

# Ollama Configuration (local LLM)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class ShoppingAgent:
    def __init__(self):
        self.use_gemini = USE_GEMINI

        if self.use_gemini:
            if not GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY environment variable is required when USE_GEMINI=true")
            logger.info(f"Initializing ShoppingAgent with Gemini model: {GEMINI_MODEL}")
            self.client = OpenAI(
                base_url=GEMINI_BASE_URL,
                api_key=GEMINI_API_KEY,
            )
            self.model = GEMINI_MODEL
        else:
            logger.info(f"Initializing ShoppingAgent with Ollama model: {OLLAMA_MODEL}")
            logger.debug(f"Ollama base URL: {OLLAMA_BASE_URL}")
            self.client = OpenAI(
                base_url=OLLAMA_BASE_URL,
                api_key="ollama",  # Ollama doesn't require an API key
            )
            self.model = OLLAMA_MODEL

        self.tools = get_all_tools()
        logger.info(f"Loaded {len(self.tools)} tools: {[t.name for t in self.tools]}")
        self.system_prompt = get_full_system_prompt()
        self.conversation_history: dict[str, list] = {}  # session_id -> messages

        # Convert tools to OpenAI format
        self.tool_declarations = self._convert_tools_to_openai_format()
        logger.info(f"ShoppingAgent initialized successfully (Provider: {'Gemini' if self.use_gemini else 'Ollama'})")

    def _convert_tools_to_openai_format(self) -> list:
        """Convert LangChain tools to OpenAI function format."""
        functions = []
        for tool in self.tools:
            # Get schema from tool
            if hasattr(tool, 'args_schema') and tool.args_schema:
                schema = tool.args_schema.schema()
                properties = schema.get("properties", {})
                required = schema.get("required", [])
            else:
                properties = {}
                required = []

            func = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required if required else []
                    }
                }
            }
            functions.append(func)

        return functions

    def _get_chat_history(self, session_id: str) -> list:
        """Get chat history for a session."""
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []
        return self.conversation_history[session_id]

    def _add_to_history(self, session_id: str, human_msg: str, ai_msg: str):
        """Add messages to chat history."""
        history = self._get_chat_history(session_id)
        history.append({"role": "user", "content": human_msg})
        history.append({"role": "assistant", "content": ai_msg})
        # Keep only last 10 exchanges (20 messages)
        if len(history) > 20:
            self.conversation_history[session_id] = history[-20:]

    def clear_history(self, session_id: str):
        """Clear chat history for a session."""
        if session_id in self.conversation_history:
            del self.conversation_history[session_id]

    async def chat(self, message: str, session_id: str = "default") -> dict:
        """
        Process a chat message and return a response.
        """
        logger.info(f"[{session_id}] Processing message: {message[:100]}...")

        # Check for adversarial queries first
        is_adversarial, response_key = is_adversarial_query(message)
        if is_adversarial:
            logger.warning(f"[{session_id}] Adversarial query detected: {response_key}")
            response = ADVERSARIAL_RESPONSES.get(response_key, ADVERSARIAL_RESPONSES["jailbreak_attempt"])
            return {
                "response": response,
                "phones": [],
                "type": "safety_redirect"
            }

        # Check for technical term explanations
        tech_terms = ["ois", "eis", "amoled", "ltpo", "refresh rate", "5g", "ip68", "periscope", "tensor"]
        message_lower = message.lower()
        for term in tech_terms:
            if f"explain {term}" in message_lower or f"what is {term}" in message_lower or f"what's {term}" in message_lower:
                explanation = get_tech_explanation(term)
                if explanation:
                    self._add_to_history(session_id, message, explanation)
                    return {
                        "response": explanation,
                        "phones": [],
                        "type": "explanation"
                    }

        # Get chat history
        chat_history = self._get_chat_history(session_id)

        try:
            # Build messages with history
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(chat_history)
            messages.append({"role": "user", "content": message})

            # Call the model with tools
            max_iterations = 5
            iteration = 0
            final_response = ""
            collected_phones = []  # Track phones from tool calls
            comparison_table = None  # Track comparison table for inclusion in response

            while iteration < max_iterations:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.tool_declarations,
                    tool_choice="auto",
                    temperature=0.7,
                    max_tokens=2048,
                )

                assistant_message = response.choices[0].message

                # Check for tool calls
                if assistant_message.tool_calls:
                    # Add assistant message with tool calls to messages
                    messages.append({
                        "role": "assistant",
                        "content": assistant_message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in assistant_message.tool_calls
                        ]
                    })

                    # Execute each tool call
                    for tool_call in assistant_message.tool_calls:
                        tool_name = tool_call.function.name
                        try:
                            tool_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            tool_args = {}

                        logger.info(f"[{session_id}] Tool call: {tool_name} with args: {tool_args}")

                        # Execute the tool
                        tool_result = None
                        for tool in self.tools:
                            if tool.name == tool_name:
                                try:
                                    tool_result = tool.invoke(tool_args)

                                    # Collect phones from tool calls for UI cards
                                    phones_from_tool = self._get_phones_from_tool_call(tool_name, tool_args)
                                    collected_phones.extend(phones_from_tool)

                                    # Capture comparison table to include in response
                                    if tool_name == "compare_phones" and tool_result and "---" in str(tool_result):
                                        comparison_table = str(tool_result)

                                except Exception as e:
                                    logger.error(f"[{session_id}] Tool error: {e}", exc_info=True)
                                    tool_result = f"Error executing tool: {str(e)}"
                                break

                        if tool_result is None:
                            logger.warning(f"[{session_id}] Tool not found: {tool_name}")
                            tool_result = f"Tool {tool_name} not found"

                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(tool_result)
                        })

                    iteration += 1
                else:
                    # No tool calls, extract text response
                    final_response = assistant_message.content or ""
                    break

            if not final_response and response:
                try:
                    final_response = response.choices[0].message.content or ""
                except:
                    final_response = "I found some information for you."

            # If we have a comparison table and LLM didn't include it, prepend it
            if comparison_table and "---" not in final_response:
                # Extract just the table part (before the Analysis section if present)
                table_parts = comparison_table.split("## Analysis")
                table_only = table_parts[0].strip()
                final_response = f"{table_only}\n\n{final_response}"

            # Add to history
            self._add_to_history(session_id, message, final_response)

            # Use phones collected from tool calls (deduplicated)
            seen_ids = set()
            phones = []
            for p in collected_phones:
                if p['id'] not in seen_ids:
                    seen_ids.add(p['id'])
                    phones.append(p)
            phones = phones[:5]  # Limit to 5 cards

            return {
                "response": final_response,
                "phones": phones,
                "type": "recommendation" if phones else "general"
            }

        except Exception as e:
            logger.error(f"[{session_id}] Agent error: {e}", exc_info=True)
            return {
                "response": "I encountered an error processing your request. Please try again.",
                "phones": [],
                "type": "error"
            }

    async def chat_stream(self, message: str, session_id: str = "default") -> AsyncGenerator[dict, None]:
        """
        Process a chat message and stream status updates.
        Uses LLM to generate dynamic thinking messages.
        Yields status events and final response.
        """

        # Ask LLM to generate a thinking message for the user's query
        thinking_msg = await self._generate_thinking_message(message)
        yield {"type": "status", "message": thinking_msg}

        # Check for adversarial queries
        is_adversarial, response_key = is_adversarial_query(message)
        if is_adversarial:
            logger.warning(f"[{session_id}] Adversarial query detected: {response_key}")
            response = ADVERSARIAL_RESPONSES.get(response_key, ADVERSARIAL_RESPONSES["jailbreak_attempt"])
            yield {
                "type": "complete",
                "response": response,
                "phones": [],
                "response_type": "safety_redirect"
            }
            return

        # Check for technical term explanations
        tech_terms = ["ois", "eis", "amoled", "ltpo", "refresh rate", "5g", "ip68", "periscope", "tensor"]
        message_lower = message.lower()
        for term in tech_terms:
            if f"explain {term}" in message_lower or f"what is {term}" in message_lower or f"what's {term}" in message_lower:
                explanation = get_tech_explanation(term)
                if explanation:
                    logger.info(f"[{session_id}] Returning tech explanation for: {term}")
                    self._add_to_history(session_id, message, explanation)
                    yield {
                        "type": "complete",
                        "response": explanation,
                        "phones": [],
                        "response_type": "explanation"
                    }
                    return

        # Get chat history
        chat_history = self._get_chat_history(session_id)

        try:
            # Build messages with history
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(chat_history)
            messages.append({"role": "user", "content": message})

            # Call the model with tools
            max_iterations = 5
            iteration = 0
            final_response = ""
            collected_phones = []
            comparison_table = None

            while iteration < max_iterations:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    _executor,
                    lambda: self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        tools=self.tool_declarations,
                        tool_choice="auto",
                        temperature=0.7,
                        max_tokens=2048,
                    )
                )

                assistant_message = response.choices[0].message

                # Check for tool calls
                if assistant_message.tool_calls:
                    messages.append({
                        "role": "assistant",
                        "content": assistant_message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in assistant_message.tool_calls
                        ]
                    })

                    # Execute each tool call
                    for tool_call in assistant_message.tool_calls:
                        tool_name = tool_call.function.name
                        try:
                            tool_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            tool_args = {}

                        # Ask LLM to generate status message for this tool call
                        tool_status = await self._generate_tool_status(tool_name, tool_args)
                        yield {"type": "status", "message": tool_status}

                        logger.info(f"[{session_id}] Tool call: {tool_name} with args: {tool_args}")

                        # Execute the tool
                        tool_result = None
                        for tool in self.tools:
                            if tool.name == tool_name:
                                try:
                                    tool_result = tool.invoke(tool_args)

                                    phones_from_tool = self._get_phones_from_tool_call(tool_name, tool_args)
                                    collected_phones.extend(phones_from_tool)

                                    if tool_name == "compare_phones" and tool_result and "---" in str(tool_result):
                                        comparison_table = str(tool_result)

                                except Exception as e:
                                    logger.error(f"[{session_id}] Tool error: {e}", exc_info=True)
                                    tool_result = f"Error executing tool: {str(e)}"
                                break

                        if tool_result is None:
                            tool_result = f"Tool {tool_name} not found"

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(tool_result)
                        })

                    iteration += 1

                    # Generate a dynamic "analyzing" message
                    analyze_msg = await self._generate_analysis_status(iteration, max_iterations)
                    yield {"type": "status", "message": analyze_msg}
                else:
                    final_response = assistant_message.content or ""
                    break

            if not final_response and response:
                try:
                    final_response = response.choices[0].message.content or ""
                except:
                    final_response = "I found some information for you."

            # If we have a comparison table and LLM didn't include it, prepend it
            if comparison_table and "---" not in final_response:
                table_parts = comparison_table.split("## Analysis")
                table_only = table_parts[0].strip()
                final_response = f"{table_only}\n\n{final_response}"

            # Add to history
            self._add_to_history(session_id, message, final_response)

            # Use phones collected from tool calls (deduplicated)
            seen_ids = set()
            phones = []
            for p in collected_phones:
                if p['id'] not in seen_ids:
                    seen_ids.add(p['id'])
                    phones.append(p)
            phones = phones[:5]

            logger.info(f"[{session_id}] Response generated - length: {len(final_response)}, phones: {len(phones)}, iterations: {iteration}")

            yield {
                "type": "complete",
                "response": final_response,
                "phones": phones,
                "response_type": "recommendation" if phones else "general"
            }

        except Exception as e:
            error_msg = f"I encountered an error processing your request. Please try again."
            logger.error(f"[{session_id}] Agent error: {e}", exc_info=True)
            yield {
                "type": "complete",
                "response": error_msg,
                "phones": [],
                "response_type": "error"
            }

    async def _generate_thinking_message(self, user_query: str) -> str:
        """Ask LLM to generate a short thinking/status message for the user's query."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                _executor,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a phone shopping assistant. Generate a very short (5-10 words max) friendly status message indicating you're working on the user's query. Be creative and specific to what they asked. Just return the status message ending with '...', nothing else."
                        },
                        {"role": "user", "content": user_query}
                    ],
                    temperature=0.9,
                    max_tokens=30,
                )
            )
            return response.choices[0].message.content.strip().strip('"')
        except Exception as e:
            logger.warning(f"Failed to generate thinking message: {e}")
            return "Working on it..."

    async def _generate_tool_status(self, tool_name: str, tool_args: dict) -> str:
        """Ask LLM to generate a status message for the tool being called."""
        try:
            tool_context = f"Tool: {tool_name}, Arguments: {json.dumps(tool_args)}"
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                _executor,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "Generate a very short (5-10 words max) friendly status message for a phone shopping assistant executing a database search. Be specific about the search criteria. Just return the message ending with '...', nothing else."
                        },
                        {"role": "user", "content": tool_context}
                    ],
                    temperature=0.9,
                    max_tokens=30,
                )
            )
            return response.choices[0].message.content.strip().strip('"')
        except Exception as e:
            logger.warning(f"Failed to generate tool status: {e}")
            return "Searching..."

    async def _generate_analysis_status(self, iteration: int, max_iterations: int) -> str:
        """Ask LLM to generate a status message while analyzing results."""
        try:
            context = f"Iteration {iteration} of {max_iterations}, analyzing phone search results"
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                _executor,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "Generate a very short (5-8 words max) status message for analyzing search results. Be creative. Just return the message ending with '...', nothing else."
                        },
                        {"role": "user", "content": context}
                    ],
                    temperature=0.9,
                    max_tokens=20,
                )
            )
            return response.choices[0].message.content.strip().strip('"')
        except Exception as e:
            logger.warning(f"Failed to generate analysis status: {e}")
            return "Analyzing..."

    def _get_phones_from_tool_call(self, tool_name: str, tool_args: dict) -> list[dict]:
        """Get phone card data directly from tool call parameters."""
        from ..data.phone_service import phone_service

        phones = []

        if tool_name == "compare_phones":
            # Get exact phones being compared
            phone_names = tool_args.get("phone_names", "")
            names = [n.strip() for n in phone_names.split(",")]
            for name in names:
                phone = phone_service.get_phone_by_name(name)
                if not phone:
                    phone = phone_service.get_phone_by_id(name)
                if phone:
                    phones.append(self._format_phone_card(phone))

        elif tool_name == "get_phone_details":
            phone_name = tool_args.get("phone_name", "")
            phone = phone_service.get_phone_by_name(phone_name)
            if not phone:
                phone = phone_service.get_phone_by_id(phone_name)
            if phone:
                phones.append(self._format_phone_card(phone))

        elif tool_name == "search_phones":
            # Handle the unified search_phones tool with use_case parameter
            use_case = tool_args.get("use_case", "").lower() if tool_args.get("use_case") else None
            min_price = None
            max_price = None
            min_ram = None
            if tool_args.get("min_price"):
                try:
                    min_price = int(tool_args.get("min_price"))
                except (ValueError, TypeError):
                    pass
            if tool_args.get("max_price"):
                try:
                    max_price = int(tool_args.get("max_price"))
                except (ValueError, TypeError):
                    pass
            if tool_args.get("min_ram"):
                try:
                    min_ram = int(tool_args.get("min_ram"))
                except (ValueError, TypeError):
                    pass

            limit = 5
            if tool_args.get("limit"):
                try:
                    limit = int(tool_args.get("limit"))
                except (ValueError, TypeError):
                    pass

            brand = tool_args.get("brand")

            # Route based on use_case
            if use_case in ["camera", "photography", "photo", "photos"]:
                results = phone_service.get_best_camera_phones(max_price=max_price, limit=limit)
            elif use_case in ["gaming", "game", "games"]:
                results = phone_service.get_gaming_phones(max_price=max_price, limit=limit)
            elif use_case in ["battery", "battery life", "long battery"]:
                results = phone_service.get_best_battery_phones(max_price=max_price, limit=limit)
            elif use_case in ["compact", "small", "one-hand", "one hand"]:
                results = phone_service.get_compact_phones(min_price=min_price, max_price=max_price, min_ram=min_ram, limit=limit)
            elif brand:
                results = phone_service.get_phones_by_brand(brand, max_price=max_price, limit=limit)
            else:
                results = phone_service.search_phones(
                    brand=brand,
                    min_price=min_price,
                    max_price=max_price,
                    min_ram=min_ram,
                    limit=limit
                )

            phones = [self._format_phone_card(p) for p in results]

        return phones

    def _format_phone_card(self, phone: dict) -> dict:
        """Format phone data for UI card display."""
        return {
            "id": phone["id"],
            "name": phone["name"],
            "brand": phone["brand"],
            "price": phone["price"],
            "display": f"{phone['display']['size']}\" {phone['display']['type']}",
            "camera": phone["camera"]["main"],
            "battery": f"{phone['battery']['capacity']}mAh",
            "rating": phone.get("rating", 0),
            "highlights": phone.get("highlights", []),
        }


# Singleton instance
_agent_instance = None


def get_agent() -> ShoppingAgent:
    """Get or create the shopping agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ShoppingAgent()
    return _agent_instance
