"""
Agent builder for the shopping chat agent with configurable LLM backend.
"""
import os
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

from openai import OpenAI

from .prompts import get_full_system_prompt
from .tools import get_all_tools

logger = logging.getLogger(__name__)

# Thread pool for async LLM calls
_executor = ThreadPoolExecutor(max_workers=4)

# LLM Configuration
USE_GEMINI = os.getenv("USE_GEMINI", "false").lower() == "true"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class ShoppingAgent:
    def __init__(self):
        # Initialize LLM client
        if USE_GEMINI:
            if not GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY required when USE_GEMINI=true")
            self.client = OpenAI(base_url=GEMINI_BASE_URL, api_key=GEMINI_API_KEY)
            self.model = GEMINI_MODEL
            logger.info(f"Initialized with Gemini: {GEMINI_MODEL}")
        else:
            self.client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
            self.model = OLLAMA_MODEL
            logger.info(f"Initialized with Ollama: {OLLAMA_MODEL}")

        self.tools = get_all_tools()
        self.system_prompt = get_full_system_prompt()
        self.conversation_history: dict[str, list] = {}
        self.tool_declarations = self._build_tool_declarations()
        logger.info(f"Loaded {len(self.tools)} tools: {[t.name for t in self.tools]}")

    def _build_tool_declarations(self) -> list:
        """Convert LangChain tools to OpenAI format."""
        declarations = []
        for tool in self.tools:
            schema = tool.args_schema.schema() if hasattr(tool, 'args_schema') and tool.args_schema else {}
            declarations.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": schema.get("properties", {}),
                        "required": schema.get("required", [])
                    }
                }
            })
        return declarations

    def _get_history(self, session_id: str) -> list:
        """Get chat history for session."""
        return self.conversation_history.setdefault(session_id, [])

    def _add_to_history(self, session_id: str, user_msg: str, ai_msg: str):
        """Add exchange to history, keep last 20 messages."""
        history = self._get_history(session_id)
        history.extend([
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": ai_msg}
        ])
        if len(history) > 20:
            self.conversation_history[session_id] = history[-20:]

    def clear_history(self, session_id: str):
        """Clear session history."""
        self.conversation_history.pop(session_id, None)

    def _execute_tool(self, tool_name: str, tool_args: dict, session_id: str) -> str:
        """Execute a tool by name and return result."""
        for tool in self.tools:
            if tool.name == tool_name:
                try:
                    return str(tool.invoke(tool_args))
                except Exception as e:
                    logger.error(f"[{session_id}] Tool error: {e}", exc_info=True)
                    return f"Error: {str(e)}"
        return f"Tool {tool_name} not found"

    def _call_llm(self, messages: list, use_tools: bool = True) -> object:
        """Make synchronous LLM call."""
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        if use_tools:
            params["tools"] = self.tool_declarations
            params["tool_choice"] = "auto"
        return self.client.chat.completions.create(**params)

    async def _call_llm_async(self, messages: list, use_tools: bool = True) -> object:
        """Make async LLM call using executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, lambda: self._call_llm(messages, use_tools))

    def _get_phones_from_tool(self, tool_name: str, tool_args: dict) -> list[dict]:
        """Extract phone cards from tool call using phone_service."""
        from data.phone_service import phone_service

        if tool_name == "compare_phones":
            names = [n.strip() for n in tool_args.get("phone_names", "").split(",")]
            phones = []
            for name in names:
                phone = phone_service.get_phone_by_name(name) or phone_service.get_phone_by_id(name)
                if phone:
                    phones.append(self._format_card(phone))
            return phones

        if tool_name == "get_phone_details":
            name = tool_args.get("phone_name", "")
            phone = phone_service.get_phone_by_name(name) or phone_service.get_phone_by_id(name)
            return [self._format_card(phone)] if phone else []

        if tool_name == "search_phones":
            # Re-execute search to get phones for cards
            # This uses the same logic as the tool itself
            from .tools import search_phones
            # Get the raw phones from service based on args
            use_case = (tool_args.get("use_case") or "").lower()
            max_price = self._safe_int(tool_args.get("max_price"))
            min_price = self._safe_int(tool_args.get("min_price"))
            min_ram = self._safe_int(tool_args.get("min_ram"))
            limit = self._safe_int(tool_args.get("limit")) or 5
            brand = tool_args.get("brand")

            # Route to service methods
            if any(term in use_case for term in ["camera", "photo"]):
                results = phone_service.get_best_camera_phones(max_price=max_price, limit=limit)
            elif any(term in use_case for term in ["gaming", "game"]):
                results = phone_service.get_gaming_phones(max_price=max_price, limit=limit)
            elif any(term in use_case for term in ["battery"]):
                results = phone_service.get_best_battery_phones(max_price=max_price, limit=limit)
            elif any(term in use_case for term in ["compact", "small"]):
                results = phone_service.get_compact_phones(min_price=min_price, max_price=max_price, min_ram=min_ram, limit=limit)
            elif brand:
                results = phone_service.get_phones_by_brand(brand, max_price=max_price, limit=limit)
            else:
                results = phone_service.search_phones(
                    brand=brand, min_price=min_price, max_price=max_price, min_ram=min_ram, limit=limit
                )

            return [self._format_card(p) for p in results]

        return []

    def _format_card(self, phone: dict) -> dict:
        """Format phone for UI card."""
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

    @staticmethod
    def _safe_int(value) -> int | None:
        """Safely convert to int."""
        try:
            return int(value) if value else None
        except (ValueError, TypeError):
            return None

    def _finalize_response(self, final_response: str, collected_phones: list, comparison_table: str | None) -> dict:
        """Build final response dict with deduped phones."""
        # Prepend comparison table if LLM didn't include it
        if comparison_table and "---" not in final_response:
            final_response = f"{comparison_table}\n\n{final_response}"

        # Deduplicate phones
        seen = set()
        phones = []
        for p in collected_phones:
            if p['id'] not in seen:
                seen.add(p['id'])
                phones.append(p)

        return {
            "response": final_response,
            "phones": phones[:5],
            "type": "recommendation" if phones else "general"
        }

    async def chat(self, message: str, session_id: str = "default") -> dict:
        """Process chat message and return response."""
        logger.info(f"[{session_id}] Message: {message[:100]}...")

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self._get_history(session_id))
        messages.append({"role": "user", "content": message})

        try:
            collected_phones = []
            comparison_table = None

            for _ in range(5):  # Max iterations
                response = self._call_llm(messages)
                assistant_message = response.choices[0].message

                if not assistant_message.tool_calls:
                    final_response = assistant_message.content or "I found some information for you."
                    break

                # Process tool calls
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in assistant_message.tool_calls
                    ]
                })

                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    logger.info(f"[{session_id}] Tool: {tool_name}, args: {tool_args}")
                    tool_result = self._execute_tool(tool_name, tool_args, session_id)

                    # Collect phones for UI cards
                    phones = self._get_phones_from_tool(tool_name, tool_args)
                    collected_phones.extend(phones)

                    # Capture comparison table
                    if tool_name == "compare_phones" and "---" in tool_result:
                        comparison_table = tool_result

                    messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": tool_result})
            else:
                final_response = response.choices[0].message.content or "I found some information for you."

            self._add_to_history(session_id, message, final_response)
            return self._finalize_response(final_response, collected_phones, comparison_table)

        except Exception as e:
            logger.error(f"[{session_id}] Error: {e}", exc_info=True)
            return {"response": "I encountered an error. Please try again.", "phones": [], "type": "error"}

    async def chat_stream(self, message: str, session_id: str = "default") -> AsyncGenerator[dict, None]:
        """Process chat message with streaming status updates."""
        # Generate thinking message
        thinking = await self._generate_status(message)
        yield {"type": "status", "message": thinking}

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self._get_history(session_id))
        messages.append({"role": "user", "content": message})

        try:
            collected_phones = []
            comparison_table = None

            for iteration in range(5):
                response = await self._call_llm_async(messages)
                assistant_message = response.choices[0].message

                if not assistant_message.tool_calls:
                    final_response = assistant_message.content or "I found some information for you."
                    break

                # Process tool calls with status updates
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in assistant_message.tool_calls
                    ]
                })

                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    # Status update for tool - LLM generates message
                    status = await self._generate_status(f"Searching: {tool_name} with {tool_args}")
                    yield {"type": "status", "message": status}

                    logger.info(f"[{session_id}] Tool: {tool_name}, args: {tool_args}")
                    tool_result = self._execute_tool(tool_name, tool_args, session_id)

                    phones = self._get_phones_from_tool(tool_name, tool_args)
                    collected_phones.extend(phones)

                    if tool_name == "compare_phones" and "---" in tool_result:
                        comparison_table = tool_result

                    messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": tool_result})

                # Analysis status
                status = await self._generate_status(f"Analyzing results (step {iteration + 1})")
                yield {"type": "status", "message": status}
            else:
                final_response = response.choices[0].message.content or "I found some information for you."

            self._add_to_history(session_id, message, final_response)
            result = self._finalize_response(final_response, collected_phones, comparison_table)

            yield {
                "type": "complete",
                "response": result["response"],
                "phones": result["phones"],
                "response_type": result["type"]
            }

        except Exception as e:
            logger.error(f"[{session_id}] Error: {e}", exc_info=True)
            yield {"type": "complete", "response": "I encountered an error. Please try again.", "phones": [], "response_type": "error"}

    async def _generate_status(self, context: str) -> str:
        """Generate dynamic status message using LLM."""
        try:
            response = await self._call_llm_async([
                {"role": "system", "content": "Generate a short (5-10 words) friendly status message for a phone shopping assistant. End with '...'"},
                {"role": "user", "content": context}
            ], use_tools=False)
            return response.choices[0].message.content.strip().strip('"')
        except:
            return "Working on it..."


# Singleton
_agent_instance = None


def get_agent() -> ShoppingAgent:
    """Get or create agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ShoppingAgent()
    return _agent_instance
