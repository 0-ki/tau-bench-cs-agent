"""tau2 메시지 ↔ LangChain 메시지 변환. LLM 호출 없이 테스트할 수 있게 순수 함수로 둔다."""

import json

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from tau2.data_model.message import (
    AssistantMessage,
    Message,
    MultiToolMessage,
    ToolCall,
    UserMessage,
)
from tau2.data_model.message import SystemMessage as Tau2SystemMessage
from tau2.data_model.message import ToolMessage as Tau2ToolMessage


def to_lc_messages(messages: list[Message]) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for m in messages:
        if isinstance(m, Tau2SystemMessage):
            out.append(SystemMessage(content=m.content or ""))
        elif isinstance(m, UserMessage):
            out.append(HumanMessage(content=m.content or ""))
        elif isinstance(m, AssistantMessage):
            out.append(
                AIMessage(
                    content=m.content or "",
                    tool_calls=[
                        {"id": tc.id, "name": tc.name, "args": tc.arguments, "type": "tool_call"}
                        for tc in m.tool_calls or []
                    ],
                )
            )
        elif isinstance(m, Tau2ToolMessage):
            out.append(ToolMessage(content=m.content or "", tool_call_id=m.id))
        elif isinstance(m, MultiToolMessage):
            out.extend(ToolMessage(content=t.content or "", tool_call_id=t.id) for t in m.tool_messages)
        else:
            raise TypeError(f"지원하지 않는 tau2 메시지: {type(m).__name__}")
    return out


def to_tau2_assistant(ai: AIMessage, *, cost: float | None, usage: dict | None) -> AssistantMessage:
    tool_calls = [
        ToolCall(id=tc["id"] or "", name=tc["name"], arguments=tc["args"], requestor="assistant")
        for tc in ai.tool_calls
    ]
    return AssistantMessage(
        role="assistant",
        # 텍스트·툴 혼합은 protocol.enforce가 먼저 걸러낸다
        content=_text(ai) or None,
        tool_calls=tool_calls or None,
        cost=cost,
        usage=usage,
        raw_data=json.loads(ai.model_dump_json(include={"content", "tool_calls", "response_metadata"})),
    )


def _text(ai: AIMessage) -> str:
    if isinstance(ai.content, str):
        return ai.content
    return "".join(p.get("text", "") for p in ai.content if isinstance(p, dict))
