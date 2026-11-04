"""녹화 응답으로 어댑터 전체 턴을 돌린다. 네트워크·API 키 없이 실행된다."""

import json
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from tau2.data_model.message import MultiToolMessage, UserMessage
from tau2.data_model.message import ToolMessage as Tau2ToolMessage
from tau2.domains.retail.environment import get_environment

from cs_agent.adapters.langchain_agent import LangChainAgent, build_chat_model
from cs_agent.settings import AgentSettings

FIXTURES = Path(__file__).parent / "fixtures"


class RecordedChatModel(FakeMessagesListChatModel):
    """녹화 응답을 순서대로 내고, 받은 입력을 기록한다."""

    seen: list = []

    def bind_tools(self, tools, **kwargs):
        return self

    def invoke(self, input, *args, **kwargs):
        self.seen.append(list(input))
        return super().invoke(input, *args, **kwargs)


def load(name: str) -> list[AIMessage]:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return [
        AIMessage(
            content=r["content"],
            tool_calls=[{**tc, "type": "tool_call"} for tc in r["tool_calls"]],
            usage_metadata=r["usage_metadata"],
        )
        for r in data["responses"]
    ]


@pytest.fixture
def agent():
    env = get_environment()
    model = RecordedChatModel(responses=load("cancel_flow.json"), seen=[])
    return LangChainAgent(
        tools=env.get_tools(),
        domain_policy=env.get_policy(),
        llm="openai/gpt-6-luna",
        chat_model=model,
        settings=AgentSettings(),
    )


def tool_result(call_id: str, content: str) -> Tau2ToolMessage:
    return Tau2ToolMessage(id=call_id, role="tool", content=content, requestor="assistant")


def test_full_turn_sequence(agent):
    state = agent.get_init_state()

    # 1) 단일 읽기
    reply, state = agent.generate_next_message(UserMessage(role="user", content="주문 취소하고 싶어요"), state)
    assert [tc.name for tc in reply.tool_calls] == ["find_user_id_by_email"]
    assert reply.content is None
    assert reply.usage["prompt_tokens"] == 1200

    # 2) 병렬 읽기 + 텍스트 → 텍스트만 제거
    reply, state = agent.generate_next_message(tool_result("call_1", "user_a"), state)
    assert [tc.id for tc in reply.tool_calls] == ["call_2", "call_3"]
    assert reply.content is None

    # 3) 읽기 + 쓰기 혼합 → 쓰기 제거
    multi = MultiToolMessage(
        role="tool", tool_messages=[tool_result("call_2", "{}"), tool_result("call_3", "{}")]
    )
    reply, state = agent.generate_next_message(multi, state)
    assert [tc.name for tc in reply.tool_calls] == ["get_order_details"]

    # 4) 확인 요청 텍스트
    reply, state = agent.generate_next_message(tool_result("call_4", "{}"), state)
    assert reply.tool_calls is None
    assert "네" in reply.content


def test_history_sent_to_model_matches_tau2(agent):
    state = agent.get_init_state()
    _, state = agent.generate_next_message(UserMessage(role="user", content="hi"), state)
    _, state = agent.generate_next_message(tool_result("call_1", "user_a"), state)

    last_input = agent.model.seen[-1]
    assert isinstance(last_input[1], HumanMessage)
    assert isinstance(last_input[2], AIMessage) and last_input[2].tool_calls[0]["id"] == "call_1"
    assert isinstance(last_input[3], ToolMessage) and last_input[3].tool_call_id == "call_1"
    assert "<policy>" in last_input[0].content


def test_gpt6_args_adjusted():
    model = build_chat_model("openai/gpt-6-luna", {"temperature": 0.0}, AgentSettings())
    assert model.temperature is None
    assert model.reasoning_effort == "none"
    assert model.model_name == "gpt-6-luna"


def test_unsupported_provider():
    with pytest.raises(ValueError):
        build_chat_model("anthropic/claude-x", {}, AgentSettings())
