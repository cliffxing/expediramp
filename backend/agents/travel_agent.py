"""
Travel planning agent powered by OpenAI function calling.
"""

import json
import logging
from datetime import datetime
from openai import OpenAI
from config import Config
from agents.tools import TOOLS, SYSTEM_PROMPT
from services.flight_service import search_flights, search_flights_roundtrip
from services.hotel_service import search_hotels
from services.car_service import search_transit
from services.activity_service import search_activities

logger = logging.getLogger(__name__)

client = OpenAI(api_key=Config.OPENAI_API_KEY)
MODEL = "gpt-4o"
MAX_TOOL_ROUNDS = 8

def _get_system_prompt():
    """Inject the current date so the AI never searches in the past."""
    current_date_str = datetime.now().strftime("%Y-%m-%d")
    return SYSTEM_PROMPT.replace("{CURRENT_DATE}", current_date_str)

def _execute_tool(name: str, arguments: dict) -> str:
    try:
        if name == "search_flights":
            result = search_flights(**arguments)
        elif name == "search_flights_roundtrip":
            result = search_flights_roundtrip(**arguments)
        elif name == "search_hotels":
            result = search_hotels(**arguments)
        elif name == "search_transit":
            result = search_transit(**arguments)
        elif name == "search_activities":
            result = search_activities(**arguments)
        elif name == "build_daily_itinerary":
            result = arguments.get("itinerary", arguments)
        elif name == "build_itinerary":
            result = arguments.get("itinerary", arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        logger.exception("Tool execution error for %s", name)
        result = {"error": str(exc)}
    return json.dumps(result, default=str)


def run_agent(conversation_history: list[dict]) -> dict:
    messages = list(conversation_history)
    system_content = _get_system_prompt()
    
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": system_content})
    else:
        messages[0]["content"] = system_content

    itinerary_data = None
    tool_names_called = []

    for _round in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto", temperature=0.4
        )
        assistant_msg = response.choices[0].message
        msg_dict = {"role": "assistant", "content": assistant_msg.content or ""}
        
        if assistant_msg.tool_calls:
            msg_dict["tool_calls"] = [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in assistant_msg.tool_calls]
        messages.append(msg_dict)

        if not assistant_msg.tool_calls: break

        for tc in assistant_msg.tool_calls:
            fn_name = tc.function.name
            try: fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError: fn_args = {}

            logger.info("Calling tool %s", fn_name)
            tool_names_called.append(fn_name)
            result_str = _execute_tool(fn_name, fn_args)

            if fn_name == "build_itinerary" or fn_name == "build_daily_itinerary":
                try: itinerary_data = json.loads(result_str)
                except Exception: itinerary_data = fn_args.get("itinerary", fn_args)

            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})

    return {
        "reply": messages[-1].get("content", "") if messages[-1]["role"] == "assistant" else "",
        "itinerary": itinerary_data,
        "tool_calls_made": tool_names_called,
        "messages": messages,
    }

def run_agent_streaming(conversation_history: list[dict]):
    messages = list(conversation_history)
    system_content = _get_system_prompt()

    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": system_content})
    else:
        messages[0]["content"] = system_content

    itinerary_data = None
    tool_names_called = []

    for _round in range(MAX_TOOL_ROUNDS):
        stream = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto", temperature=0.4, stream=True
        )
        collected_content = ""
        collected_tool_calls = {}

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None: continue

            if delta.content:
                collected_content += delta.content
                yield {"type": "token", "data": delta.content}

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in collected_tool_calls:
                        collected_tool_calls[idx] = {"id": tc_delta.id or "", "name": "", "arguments": ""}
                    if tc_delta.id: collected_tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name: collected_tool_calls[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments: collected_tool_calls[idx]["arguments"] += tc_delta.function.arguments

        msg_dict = {"role": "assistant", "content": collected_content}
        if collected_tool_calls:
            msg_dict["tool_calls"] = [{"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}} for tc in collected_tool_calls.values()]
        messages.append(msg_dict)

        if not collected_tool_calls: break

        for tc in collected_tool_calls.values():
            fn_name = tc["name"]
            try: fn_args = json.loads(tc["arguments"])
            except json.JSONDecodeError: fn_args = {}

            tool_names_called.append(fn_name)
            yield {"type": "tool_start", "data": {"tool": fn_name, "args": fn_args}}

            result_str = _execute_tool(fn_name, fn_args)

            if fn_name == "build_itinerary" or fn_name == "build_daily_itinerary":
                try: itinerary_data = json.loads(result_str)
                except Exception: itinerary_data = fn_args.get("itinerary", fn_args)
                yield {"type": "itinerary", "data": itinerary_data}

            yield {"type": "tool_result", "data": {"tool": fn_name, "preview": result_str[:300]}}
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result_str})

    yield {
        "type": "done",
        "data": {"itinerary": itinerary_data, "tools_used": tool_names_called, "message_count": len(messages)},
    }
