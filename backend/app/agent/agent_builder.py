"""
Agent builder for the shopping chat agent using Ollama (local LLM).
"""
import os
import json
import logging
import httpx
from openai import OpenAI

from .prompts import get_full_system_prompt, is_adversarial_query, ADVERSARIAL_RESPONSES, get_tech_explanation
from .tools import get_all_tools


logger = logging.getLogger(__name__)


# Ollama Configuration (local LLM)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")


class ShoppingAgent:
    def __init__(self):
        logger.info(f"Initializing ShoppingAgent with Ollama model: {OLLAMA_MODEL}")
        logger.debug(f"Ollama base URL: {OLLAMA_BASE_URL}")

        # Create OpenAI client pointing to Ollama (OpenAI-compatible API)
        self.client = OpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",  # Ollama doesn't require an API key, but OpenAI client needs one
        )

        self.tools = get_all_tools()
        logger.info(f"Loaded {len(self.tools)} tools: {[t.name for t in self.tools]}")
        self.system_prompt = get_full_system_prompt()
        self.conversation_history: dict[str, list] = {}  # session_id -> messages
        self.model = OLLAMA_MODEL

        # Convert tools to OpenAI format
        self.tool_declarations = self._convert_tools_to_openai_format()
        logger.info("ShoppingAgent initialized successfully")

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
                    logger.info(f"[{session_id}] Returning tech explanation for: {term}")
                    self._add_to_history(session_id, message, explanation)
                    return {
                        "response": explanation,
                        "phones": [],
                        "type": "explanation"
                    }

        # Get chat history
        chat_history = self._get_chat_history(session_id)
        logger.debug(f"[{session_id}] Chat history length: {len(chat_history)}")

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
                                    logger.debug(f"[{session_id}] Tool result: {str(tool_result)[:200]}...")

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
                logger.info(f"[{session_id}] Prepended comparison table to response")

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

            logger.info(f"[{session_id}] Response generated - length: {len(final_response)}, phones: {len(phones)}, iterations: {iteration}")

            return {
                "response": final_response,
                "phones": phones,
                "type": "recommendation" if phones else "general"
            }

        except Exception as e:
            error_msg = f"I encountered an error processing your request. Please try again."
            logger.error(f"[{session_id}] Agent error: {e}", exc_info=True)
            return {
                "response": error_msg,
                "phones": [],
                "type": "error"
            }

    def _extract_phones_from_response(self, response: str) -> list[dict]:
        """Extract phone data from agent response for UI display."""
        from ..data.phone_service import phone_service
        import re

        phones = []
        response_lower = response.lower()

        for phone in phone_service.get_all_phones():
            phone_name = phone['name'].lower()

            # Check for exact match first
            if phone_name in response_lower:
                phones.append(self._format_phone_card(phone))
                continue

            # Build smart matching patterns for common phone naming conventions
            # e.g., "OnePlus 12R" should match "oneplus 12r" or "12r"
            # but "12" alone should NOT match "OnePlus 12" (too ambiguous)

            # Extract brand and model
            brand = phone['brand'].lower()
            model = phone_name.replace(brand, "").replace("galaxy", "").strip()

            # Try "Brand Model" pattern (e.g., "OnePlus 12R", "Samsung S24")
            brand_model_pattern = r'\b' + re.escape(brand) + r'\s+' + re.escape(model) + r'\b'
            if re.search(brand_model_pattern, response_lower):
                phones.append(self._format_phone_card(phone))
                continue

            # Try matching the full model if it's distinctive enough (3+ chars, not just numbers)
            if len(model) >= 3 and not model.isdigit():
                model_pattern = r'\b' + re.escape(model) + r'\b'
                if re.search(model_pattern, response_lower):
                    phones.append(self._format_phone_card(phone))
                    continue

        # Remove duplicates while preserving order
        seen = set()
        unique_phones = []
        for p in phones:
            if p['id'] not in seen:
                seen.add(p['id'])
                unique_phones.append(p)

        return unique_phones[:5]

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
            max_price = int(tool_args.get("max_price", 0)) if tool_args.get("max_price") else None
            brand = tool_args.get("brand")
            results = phone_service.search_phones(
                brand=brand,
                max_price=max_price,
                limit=int(tool_args.get("limit", 5))
            )
            phones = [self._format_phone_card(p) for p in results]

        elif tool_name == "get_best_camera_phones":
            max_price = int(tool_args.get("max_price")) if tool_args.get("max_price") else None
            results = phone_service.get_best_camera_phones(max_price=max_price, limit=int(tool_args.get("limit", 5)))
            phones = [self._format_phone_card(p) for p in results]

        elif tool_name == "get_best_battery_phones":
            max_price = int(tool_args.get("max_price")) if tool_args.get("max_price") else None
            results = phone_service.get_best_battery_phones(max_price=max_price, limit=int(tool_args.get("limit", 5)))
            phones = [self._format_phone_card(p) for p in results]

        elif tool_name == "get_gaming_phones":
            max_price = int(tool_args.get("max_price")) if tool_args.get("max_price") else None
            results = phone_service.get_gaming_phones(max_price=max_price, limit=int(tool_args.get("limit", 5)))
            phones = [self._format_phone_card(p) for p in results]

        elif tool_name == "get_compact_phones":
            max_price = int(tool_args.get("max_price")) if tool_args.get("max_price") else None
            results = phone_service.get_compact_phones(max_price=max_price, limit=int(tool_args.get("limit", 5)))
            phones = [self._format_phone_card(p) for p in results]

        elif tool_name == "get_phones_by_brand":
            brand = tool_args.get("brand", "")
            max_price = int(tool_args.get("max_price")) if tool_args.get("max_price") else None
            results = phone_service.get_phones_by_brand(brand=brand, max_price=max_price, limit=int(tool_args.get("limit", 10)))
            phones = [self._format_phone_card(p) for p in results]

        return phones

    def _format_phone_card(self, phone: dict) -> dict:
        """Format phone data for UI card display."""
        return {
            "id": phone["id"],
            "name": phone["name"],
            "brand": phone["brand"],
            "price": phone["price"],
            "image_url": phone.get("image_url", ""),
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
