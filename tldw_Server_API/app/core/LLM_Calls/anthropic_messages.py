from __future__ import annotations

import inspect
import json
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional


def _blocks_to_text(blocks: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = block.get("text")
            if text is not None:
                parts.append(str(text))
    return "".join(parts)


def _system_to_text(system: Any) -> Optional[str]:
    if system is None:
        return None
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        text = _blocks_to_text([b for b in system if isinstance(b, dict)])
        return text if text else None
    return None


def _image_block_to_openai_part(block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    source = block.get("source")
    if not isinstance(source, dict):
        return None
    src_type = source.get("type")
    if src_type == "base64":
        media_type = source.get("media_type") or "application/octet-stream"
        data = source.get("data") or ""
        url = f"data:{media_type};base64,{data}"
    elif src_type == "url":
        url = source.get("url")
    else:
        return None
    if not isinstance(url, str) or not url:
        return None
    return {"type": "image_url", "image_url": {"url": url}}


def _tool_result_to_text(block: Dict[str, Any]) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return _blocks_to_text([b for b in content if isinstance(b, dict)])
    if content is None:
        return ""
    try:
        return json.dumps(content, ensure_ascii=True)
    except Exception:
        return str(content)


def _tool_use_to_openai_call(block: Dict[str, Any], tool_index: int) -> Optional[Dict[str, Any]]:
    name = block.get("name")
    tool_id = block.get("id") or f"tool_{tool_index}"
    if not isinstance(name, str) or not name:
        return None
    arguments = block.get("input")
    try:
        arguments_json = json.dumps(arguments, ensure_ascii=True, separators=(",", ":"))
    except Exception:
        arguments_json = "{}"
    return {
        "index": tool_index,
        "id": tool_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments_json},
    }


def anthropic_messages_to_openai(
    messages: List[Dict[str, Any]],
    system: Optional[Any],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    system_message = _system_to_text(system)
    openai_messages: List[Dict[str, Any]] = []
    tool_result_counter = 0

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role not in {"user", "assistant"}:
            continue

        if isinstance(content, str):
            openai_messages.append({"role": role, "content": content})
            continue

        if not isinstance(content, list):
            openai_messages.append({"role": role, "content": ""})
            continue

        if role == "assistant":
            text_parts: List[str] = []
            tool_calls: List[Dict[str, Any]] = []
            tool_index = 0
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "text":
                    text = block.get("text")
                    if text is not None:
                        text_parts.append(str(text))
                elif block_type == "tool_use":
                    call = _tool_use_to_openai_call(block, tool_index)
                    if call:
                        tool_calls.append(call)
                        tool_index += 1
            message_payload: Dict[str, Any] = {
                "role": "assistant",
                "content": "".join(text_parts),
            }
            if tool_calls:
                message_payload["tool_calls"] = tool_calls
            openai_messages.append(message_payload)
            continue

        # user role with mixed content
        user_parts: List[Dict[str, Any]] = []
        has_image = False

        def _flush_user_parts() -> None:
            nonlocal user_parts, has_image
            if not user_parts:
                return
            if has_image or len(user_parts) > 1:
                openai_messages.append({"role": "user", "content": list(user_parts)})
            else:
                text_part = user_parts[0]
                openai_messages.append({"role": "user", "content": text_part.get("text", "")})
            user_parts = []
            has_image = False

        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text")
                if text is not None:
                    user_parts.append({"type": "text", "text": str(text)})
            elif block_type == "image":
                part = _image_block_to_openai_part(block)
                if part:
                    user_parts.append(part)
                    has_image = True
            elif block_type == "tool_result":
                _flush_user_parts()
                tool_id = block.get("tool_use_id") or block.get("id")
                if not tool_id:
                    tool_id = f"tool_result_{tool_result_counter}"
                    tool_result_counter += 1
                openai_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": _tool_result_to_text(block),
                    }
                )
            else:
                # Ignore unknown user blocks to avoid injecting unsupported content types.
                continue

        _flush_user_parts()

    return openai_messages, system_message


def anthropic_tools_to_openai(tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if not tools:
        return None
    converted: List[Dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            continue
        description = tool.get("description")
        input_schema = tool.get("input_schema")
        payload: Dict[str, Any] = {
            "type": "function",
            "function": {
                "name": name,
                "description": description or "",
                "parameters": input_schema if isinstance(input_schema, dict) else {},
            },
        }
        converted.append(payload)
    return converted or None


def anthropic_tool_choice_to_openai(choice: Any) -> Any:
    if choice is None:
        return None
    if isinstance(choice, str):
        lowered = choice.lower().strip()
        if lowered in {"auto", "none"}:
            return lowered
        if lowered == "any":
            return "required"
        # Treat other strings as tool name hints
        return {"type": "function", "function": {"name": choice}}
    if isinstance(choice, dict):
        tool_type = choice.get("type")
        if tool_type == "tool":
            name = choice.get("name")
            if isinstance(name, str) and name:
                return {"type": "function", "function": {"name": name}}
        if tool_type == "any":
            return "required"
        if tool_type == "auto":
            return "auto"
    return choice


def _openai_content_to_blocks(content: Any) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    if isinstance(content, str):
        if content:
            blocks.append({"type": "text", "text": content})
        return blocks
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "text":
                text = part.get("text")
                if text is not None:
                    blocks.append({"type": "text", "text": str(text)})
            elif ptype == "image_url":
                image_url = part.get("image_url") or {}
                url = image_url.get("url")
                if isinstance(url, str) and url:
                    blocks.append({"type": "image", "source": {"type": "url", "url": url}})
    return blocks


def _finish_reason_to_stop_reason(reason: Optional[str]) -> Optional[str]:
    if not reason:
        return None
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "function_call": "tool_use",
        "content_filter": "stop_sequence",
    }
    return mapping.get(reason, reason)


def openai_response_to_anthropic(response: Dict[str, Any], *, model: Optional[str]) -> Dict[str, Any]:
    choice = None
    if isinstance(response.get("choices"), list) and response["choices"]:
        choice = response["choices"][0]
    message = (choice or {}).get("message") or {}
    content_blocks = _openai_content_to_blocks(message.get("content"))

    tool_calls = message.get("tool_calls") or []
    if isinstance(tool_calls, list):
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            func = tc.get("function") or {}
            name = func.get("name") or ""
            args = func.get("arguments")
            input_obj: Any = {}
            if isinstance(args, str):
                try:
                    input_obj = json.loads(args)
                except Exception:
                    input_obj = args
            elif args is not None:
                input_obj = args
            content_blocks.append(
                {
                    "type": "tool_use",
                    "id": tc.get("id") or f"tool_{len(content_blocks)}",
                    "name": name,
                    "input": input_obj,
                }
            )

    finish_reason = (choice or {}).get("finish_reason")
    usage = response.get("usage") or {}
    input_tokens = usage.get("prompt_tokens") or 0
    output_tokens = usage.get("completion_tokens") or 0

    msg_id = response.get("id") or f"msg_{uuid.uuid4().hex}"
    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "model": model or response.get("model"),
        "content": content_blocks,
        "stop_reason": _finish_reason_to_stop_reason(finish_reason),
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    }


def _sse_event(event_type: str, payload: Dict[str, Any]) -> str:
    if "type" not in payload:
        payload = dict(payload)
        payload["type"] = event_type
    return f"event: {event_type}\n" + f"data: {json.dumps(payload, ensure_ascii=True)}\n\n"


def _parse_openai_sse_line(line: str) -> Optional[Dict[str, Any]]:
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.lower() == "data: [done]":
        return {"_done": True}
    if not stripped.startswith("data:"):
        return None
    payload = stripped[len("data:") :].strip()
    if not payload:
        return None
    try:
        data = json.loads(payload)
    except Exception:
        return None
    return data


async def _aiter_lines(stream: Any) -> AsyncIterator[str]:
    if hasattr(stream, "__aiter__"):
        async for item in stream:
            if item is None:
                continue
            yield item.decode("utf-8") if isinstance(item, (bytes, bytearray)) else str(item)
    else:
        for item in stream:
            if item is None:
                continue
            yield item.decode("utf-8") if isinstance(item, (bytes, bytearray)) else str(item)


async def _maybe_close_stream(stream: Any) -> None:
    if stream is None:
        return
    close_fn = getattr(stream, "aclose", None)
    if callable(close_fn):
        try:
            result = close_fn()
            if inspect.isawaitable(result):
                await result
        except Exception:
            pass
        return
    close_fn = getattr(stream, "close", None)
    if callable(close_fn):
        try:
            result = close_fn()
            if inspect.isawaitable(result):
                await result
        except Exception:
            pass


def _extract_choice(data: Dict[str, Any]) -> Dict[str, Any]:
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0]
        if isinstance(choice, dict):
            return choice
    return {}


async def openai_stream_to_anthropic(
    stream: Any,
    *,
    model: Optional[str],
) -> AsyncIterator[str]:
    message_id = f"msg_{uuid.uuid4().hex}"
    message_started = False
    text_block_index: Optional[int] = None
    next_block_index = 0
    open_blocks: List[int] = []
    tool_blocks: Dict[str, Dict[str, Any]] = {}
    final_usage: Dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    try:
        async for raw_line in _aiter_lines(stream):
            data = _parse_openai_sse_line(raw_line)
            if not data:
                continue
            if data.get("_done"):
                break

            choice = _extract_choice(data)
            delta = choice.get("delta") or {}
            finish_reason = choice.get("finish_reason")

            if not message_started:
                message_started = True
                yield _sse_event(
                    "message_start",
                    {
                        "message": {
                            "id": message_id,
                            "type": "message",
                            "role": "assistant",
                            "model": model or data.get("model"),
                            "content": [],
                            "stop_reason": None,
                            "stop_sequence": None,
                            "usage": dict(final_usage),
                        }
                    },
                )

            if isinstance(delta, dict):
                content = delta.get("content")
                if content is not None:
                    if text_block_index is None:
                        text_block_index = next_block_index
                        next_block_index += 1
                        open_blocks.append(text_block_index)
                        yield _sse_event(
                            "content_block_start",
                            {
                                "index": text_block_index,
                                "content_block": {"type": "text", "text": ""},
                            },
                        )
                    yield _sse_event(
                        "content_block_delta",
                        {
                            "index": text_block_index,
                            "delta": {"type": "text_delta", "text": str(content)},
                        },
                    )

                tool_calls = delta.get("tool_calls")
                if isinstance(tool_calls, list):
                    for tool_delta in tool_calls:
                        if not isinstance(tool_delta, dict):
                            continue
                        func = tool_delta.get("function") or {}
                        name = func.get("name")
                        args = func.get("arguments")
                        tool_id = tool_delta.get("id") or f"tool_{tool_delta.get('index', next_block_index)}"
                        state = tool_blocks.get(tool_id)
                        if state is None:
                            state = {
                                "index": next_block_index,
                                "name": name if isinstance(name, str) else None,
                                "buffer": "",
                            }
                            tool_blocks[tool_id] = state
                            next_block_index += 1
                            open_blocks.append(state["index"])
                            yield _sse_event(
                                "content_block_start",
                                {
                                    "index": state["index"],
                                    "content_block": {
                                        "type": "tool_use",
                                        "id": tool_id,
                                        "name": state["name"] or "",
                                        "input": {},
                                    },
                                },
                            )
                        elif isinstance(name, str) and name and not state.get("name"):
                            state["name"] = name
                            yield _sse_event(
                                "content_block_delta",
                                {
                                    "index": state["index"],
                                    "delta": {"type": "tool_use_delta", "name": name},
                                },
                            )
                        if isinstance(args, str) and args:
                            state["buffer"] += args
                            yield _sse_event(
                                "content_block_delta",
                                {
                                    "index": state["index"],
                                    "delta": {"type": "input_json_delta", "partial_json": args},
                                },
                            )

            usage = data.get("usage")
            if isinstance(usage, dict):
                prompt_tokens = usage.get("prompt_tokens")
                completion_tokens = usage.get("completion_tokens")
                if isinstance(prompt_tokens, int):
                    final_usage["input_tokens"] = prompt_tokens
                if isinstance(completion_tokens, int):
                    final_usage["output_tokens"] = completion_tokens

            if finish_reason:
                stop_reason = _finish_reason_to_stop_reason(finish_reason)
                for idx in list(open_blocks):
                    yield _sse_event(
                        "content_block_stop",
                        {"index": idx},
                    )
                yield _sse_event(
                    "message_delta",
                    {
                        "delta": {
                            "stop_reason": stop_reason,
                            "stop_sequence": None,
                        },
                        "usage": dict(final_usage),
                    },
                )
                yield _sse_event("message_stop", {})
                return

        if message_started:
            for idx in list(open_blocks):
                yield _sse_event("content_block_stop", {"index": idx})
            yield _sse_event(
                "message_delta",
                {"delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": dict(final_usage)},
            )
            yield _sse_event("message_stop", {})
    finally:
        await _maybe_close_stream(stream)
