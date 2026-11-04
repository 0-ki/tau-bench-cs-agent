"""cs_agent 에이전트를 tau2 registry에 등록한다. upstream registry.py는 건드리지 않는다."""

from tau2.registry import registry

from cs_agent.adapters.langchain_agent import create_langchain_agent

AGENTS = {"langchain_agent": create_langchain_agent}


def register_agents() -> None:
    for name, factory in AGENTS.items():
        if registry.get_agent_factory(name) is None:
            registry.register_agent_factory(factory, name)
