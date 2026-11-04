"""Phase 2 LangChain 베이스라인 에이전트.

tau2 `llm_agent`와 같은 시스템 프롬프트·같은 툴로 LLM 호출 계층만 LangChain으로 바꾼 것이다.
툴 실행은 tau2 오케스트레이터가 하므로 에이전트 루프(create_agent 등)는 쓰지 않고
chat model + bind_tools만 쓴다. 에이전트는 한 턴에 AssistantMessage 하나를 돌려줄 뿐이다.
"""

import time
from typing import Optional

import litellm
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel
from tau2.agent.base.llm_config import LLMConfigMixin
from tau2.agent.base_agent import HalfDuplexAgent, ValidAgentInputMessage, is_valid_agent_history_message
from tau2.agent.llm_agent import AGENT_INSTRUCTION, SYSTEM_PROMPT
from tau2.data_model.message import APICompatibleMessage, AssistantMessage, Message, SystemMessage
from tau2.environment.tool import Tool

from cs_agent.adapters import protocol
from cs_agent.adapters.convert import to_lc_messages, to_tau2_assistant
from cs_agent.domain.specs import write_tool_names
from cs_agent.settings import AgentSettings


class LangChainAgentState(BaseModel):
    system_messages: list[SystemMessage]
    messages: list[APICompatibleMessage]


class LangChainAgent(LLMConfigMixin, HalfDuplexAgent[LangChainAgentState]):
    def __init__(
        self,
        tools: list[Tool],
        domain_policy: str,
        llm: str,
        llm_args: Optional[dict] = None,
        *,
        chat_model: BaseChatModel | None = None,
        settings: AgentSettings | None = None,
    ):
        super().__init__(tools=tools, domain_policy=domain_policy, llm=llm, llm_args=llm_args)
        self.settings = settings or AgentSettings()
        self.write_tools = write_tool_names()
        # 테스트는 녹화 응답을 내는 가짜 모델을 주입한다
        model = chat_model or build_chat_model(llm, self.llm_args, self.settings)
        self.model = model.bind_tools([t.openai_schema for t in tools])
        self.log = logger.bind(agent="langchain_agent", llm=llm)

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT.format(domain_policy=self.domain_policy, agent_instruction=AGENT_INSTRUCTION)

    def get_init_state(self, message_history: Optional[list[Message]] = None) -> LangChainAgentState:
        history = message_history or []
        assert all(is_valid_agent_history_message(m) for m in history)
        return LangChainAgentState(
            system_messages=[SystemMessage(role="system", content=self.system_prompt)],
            messages=list(history),
        )

    def generate_next_message(
        self, message: ValidAgentInputMessage, state: LangChainAgentState
    ) -> tuple[AssistantMessage, LangChainAgentState]:
        state.messages.append(message)
        lc_messages = to_lc_messages(state.system_messages + state.messages)

        started = time.perf_counter()
        ai: AIMessage = self.model.invoke(lc_messages)
        elapsed = time.perf_counter() - started

        ai, violations = protocol.enforce(
            ai, self.write_tools, allow_parallel_reads=self.settings.allow_parallel_reads
        )
        for v in violations:
            self.log.warning("PROTO-01 위반 보정 kind={} dropped={}", v.kind, v.dropped)

        usage = _usage(ai)
        reply = to_tau2_assistant(ai, cost=_cost(self.llm, usage), usage=usage)
        reply.generation_time_seconds = elapsed
        self.log.debug(
            "turn tools={} tokens={} {:.2f}s",
            [tc.name for tc in reply.tool_calls or []],
            usage,
            elapsed,
        )
        state.messages.append(reply)
        return reply, state


def build_chat_model(llm: str, llm_args: dict, settings: AgentSettings) -> BaseChatModel:
    provider, _, model = llm.partition("/")
    if not model:
        provider, model = "openai", provider
    if provider != "openai":
        raise ValueError(f"지원하지 않는 프로바이더: {provider} (현재 openai만)")

    args = dict(llm_args)
    if "gpt-6" in model:
        # gpt-6 계열: temperature는 기본값만 허용, 툴과 reasoning 동시 사용 불가 (tau2_overrides와 같은 보정)
        args.pop("temperature", None)
        args["reasoning_effort"] = "none"
    return ChatOpenAI(
        model=model,
        timeout=settings.request_timeout_s,
        max_retries=settings.max_retries,
        **args,
    )


def _usage(ai: AIMessage) -> dict | None:
    meta = ai.usage_metadata
    if not meta:
        return None
    return {
        "prompt_tokens": meta["input_tokens"],
        "completion_tokens": meta["output_tokens"],
        "cached_tokens": (meta.get("input_token_details") or {}).get("cache_read", 0),
    }


def _cost(llm: str, usage: dict | None) -> float | None:
    """tau2 비용 집계와 맞추려고 litellm 단가표(cs_agent.pricing으로 등록)를 그대로 쓴다."""
    if usage is None:
        return None
    try:
        prompt, completion = litellm.cost_per_token(
            model=llm,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            cache_read_input_tokens=usage["cached_tokens"],
        )
    except Exception:  # 단가 미등록 모델이면 비용만 비우고 진행
        return None
    return prompt + completion


def create_langchain_agent(tools, domain_policy, **kwargs) -> LangChainAgent:
    """tau2 registry용 팩토리. `--agent langchain_agent`로 선택한다."""
    return LangChainAgent(
        tools=tools,
        domain_policy=domain_policy,
        llm=kwargs.get("llm"),
        llm_args=kwargs.get("llm_args"),
    )
