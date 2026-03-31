"""
Travel planning agent powered by OpenAI function calling.

Manages multi-turn conversations, executes tool calls against the
travel services, and streams responses back to the client.
"""

import json
import logging
from openai import OpenAI
from config import Config
from agents.tools import TOOLS, SYSTEM_PROMPT
from services.flight_service import search_flights
from services.hotel_service import search_hotels
from services.car_service import search_car_rentals, search_transit

logger = logging.getLogger(__name__)

client = OpenAI(api_key=Config.OPENAI_API_KEY)

MODEL = "gpt-4o"
MAX_TOOL_ROUNDS = 8  # safety limit on agentic loops


# ── Tool dispatcher ────────────────────────────────────────────────────

def _execute_tool(name: str, arguments: dict) -> str:
    """Run a tool and return a JSON-serialisable result string."""
    try:
        if name == "search_flights":
            result = search_flights(**arguments)
        elif name == "search_hotels":
            result = search_hotels(**arguments)
        elif name == "search_car_rentals":
            result = search_car_rentals(**arguments)
        elif name == "search_transit":
            result = search_transit(**arguments)
        elif name == "build_itinerary":
            # build_itinerary is "passthrough" — the model already built the
            # JSON structure; we just acknowledge it so the model can present it.
            result = arguments.get("itinerary", arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        logger.exception("Tool execution error for %s", name)
        result = {"error": str(exc)}

    return json.dumps(result, default=str)


# ── Streaming agent loop ──────────────────────────────────────────────

def run_agent(conversation_history: list[dict]) -> dict:
    """
    Execute the agent loop (non-streaming).

    Parameters
    ----------
    conversation_history : list[dict]
        The full message history in OpenAI's messages format.
        Must start with {"role": "system", "content": SYSTEM_PROMPT}
        followed by user/assistant turns.

    Returns
    -------
    dict with keys:
        - "reply": str — the assistant's final text reply
        - "itinerary": dict | None — if build_itinerary was called, the full itinerary object
        - "tool_calls_made": list[str] — names of tools invoked
        - "messages": list[dict] — updated conversation history including assistant + tool messages
    """

    messages = list(conversation_history)
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    itinerary_data = None
    tool_names_called: list[str] = []

    for _round in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.4,
        )

        choice = response.choices[0]
        assistant_msg = choice.message

        # Append the assistant message to history
        msg_dict: dict = {"role": "assistant", "content": assistant_msg.content or ""}
        if assistant_msg.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in assistant_msg.tool_calls
            ]
        messages.append(msg_dict)

        # If no tool calls, we're done
        if not assistant_msg.tool_calls:
            break

        # Execute each tool call and append results
        for tc in assistant_msg.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            logger.info("Calling tool %s with %s", fn_name, json.dumps(fn_args)[:200])
            tool_names_called.append(fn_name)

            result_str = _execute_tool(fn_name, fn_args)

            # Capture itinerary if build_itinerary was called
            if fn_name == "build_itinerary":
                try:
                    itinerary_data = json.loads(result_str)
                except Exception:
                    itinerary_data = fn_args.get("itinerary", fn_args)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

    final_text = messages[-1].get("content", "") if messages[-1]["role"] == "assistant" else ""

    return {
        "reply": final_text,
        "itinerary": itinerary_data,
        "tool_calls_made": tool_names_called,
        "messages": messages,
    }


def run_agent_streaming(conversation_history: list[dict]):
    """
    Generator that yields Server-Sent-Event style dicts for real-time
    streaming to the frontend.

    Yields dicts with keys:
        - type: "token" | "tool_start" | "tool_result" | "itinerary" | "done" | "error"
        - data: the payload
    """

    messages = list(conversation_history)
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    itinerary_data = None
    tool_names_called: list[str] = []

    for _round in range(MAX_TOOL_ROUNDS):
        # Stream the response
        stream = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.4,
            stream=True,
        )

        collected_content = ""
        collected_tool_calls: dict[int, dict] = {}

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            # Stream text tokens
            if delta.content:
                collected_content += delta.content
                yield {"type": "token", "data": delta.content}

            # Accumulate tool calls
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in collected_tool_calls:
                        collected_tool_calls[idx] = {
                            "id": tc_delta.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    if tc_delta.id:
                        collected_tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            collected_tool_calls[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            collected_tool_calls[idx]["arguments"] += tc_delta.function.arguments

        # Build the assistant message for history
        msg_dict: dict = {"role": "assistant", "content": collected_content}
        if collected_tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                }
                for tc in collected_tool_calls.values()
            ]
        messages.append(msg_dict)

        # If no tool calls, we're done
        if not collected_tool_calls:
            break

        # Execute tool calls
        for tc in collected_tool_calls.values():
            fn_name = tc["name"]
            try:
                fn_args = json.loads(tc["arguments"])
            except json.JSONDecodeError:
                fn_args = {}

            tool_names_called.append(fn_name)
            yield {"type": "tool_start", "data": {"tool": fn_name, "args": fn_args}}

            result_str = _execute_tool(fn_name, fn_args)

            if fn_name == "build_itinerary":
                try:
                    itinerary_data = json.loads(result_str)
                except Exception:
                    itinerary_data = fn_args.get("itinerary", fn_args)
                yield {"type": "itinerary", "data": itinerary_data}

            yield {"type": "tool_result", "data": {"tool": fn_name, "preview": result_str[:300]}}

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result_str,
            })

    yield {
        "type": "done",
        "data": {
            "itinerary": itinerary_data,
            "tools_used": tool_names_called,
            "message_count": len(messages),
        },
    }
