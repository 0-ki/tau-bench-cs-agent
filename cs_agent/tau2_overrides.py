"""tau2 보조 LLM(사용자 시뮬레이터, 판정자 등) 기본 모델을 런타임에 일괄 교체한다.

upstream `tau2/config.py`는 수정하지 않는다. tau2는 패키지 import 시점에
`from tau2.config import X`로 값을 복사해 가므로, config만 바꿔서는 안 되고
이미 로드된 tau2 모듈 전역 변수와 pydantic 필드 기본값까지 같이 바꿔야 한다.
"""

import json
import os
import sys

# 교체 대상: 에이전트(DEFAULT_LLM_AGENT)를 제외한 모든 보조 LLM
_MODEL_KEYS = (
    "DEFAULT_LLM_USER",  # 사용자 시뮬레이터
    "DEFAULT_SEMANTIC_COMMUNICATE_MODEL",  # COMMUNICATE 판정자 (reward에 반영)
    "DEFAULT_LLM_NL_ASSERTIONS",  # NL assertion 판정자 (진단용)
    "DEFAULT_LLM_ENV_INTERFACE",  # 환경 인터페이스 에이전트
    "DEFAULT_LLM_EVAL_USER_SIMULATOR",  # tau2 review
    "DEFAULT_ELICITATION_LLM_USER",  # intake 도메인 사용자
    "DEFAULT_BENCHMARK_USER_MODEL",  # released benchmark 사용자
    "VOICE_USER_SIMULATOR_DECISION_MODEL",  # 음성 사용자 판단
)
# 판정자 reasoning 인자. 모델이 지원하지 않으면 SIM_JUDGE_ARGS로 덮어쓴다
_JUDGE_ARGS_KEYS = (
    "DEFAULT_SEMANTIC_COMMUNICATE_MODEL_ARGS",
    "DEFAULT_LLM_NL_ASSERTIONS_ARGS",
)

DEFAULT_SIM_MODEL = "openai/gpt-6-luna"


def sim_model() -> str:
    return os.getenv("SIM_MODEL") or DEFAULT_SIM_MODEL


def apply_overrides() -> dict:
    """적용된 값을 반환. tau2 import 이후, 실행 이전에 호출해야 한다."""
    import tau2  # noqa: F401  패키지 전체를 먼저 로드해 이후 덮어쓴 값이 유지되게 함
    import tau2.config as cfg
    from pydantic import BaseModel

    from cs_agent.pricing import register_prices

    register_prices()
    _patch_completion_for_gpt6()

    old_models = {getattr(cfg, key) for key in _MODEL_KEYS if hasattr(cfg, key)}
    values = {key: sim_model() for key in _MODEL_KEYS}
    if judge_args := os.getenv("SIM_JUDGE_ARGS"):
        values.update({key: json.loads(judge_args) for key in _JUDGE_ARGS_KEYS})

    # 1) 모듈 전역 변수 (`from tau2.config import X`로 복사된 값)
    models: set[type] = set()
    for name, module in list(sys.modules.items()):
        if not name.startswith("tau2") or module is None:
            continue
        for key, value in values.items():
            if hasattr(module, key):
                setattr(module, key, value)
        for obj in vars(module).values():
            if isinstance(obj, type) and issubclass(obj, BaseModel):
                models.add(obj)

    # 2) pydantic 필드 기본값 (클래스 정의 시점에 고정됨). 부모 클래스부터 재빌드
    for model_cls in sorted(models, key=lambda c: len(c.__mro__)):
        changed = False
        for field in model_cls.model_fields.values():
            if isinstance(field.default, str) and field.default in old_models:
                field.default = sim_model()
                changed = True
        if changed:
            model_cls.model_rebuild(force=True)

    # 3) 함수 기본 인자로 박힌 환경 인터페이스 모델
    from tau2.environment.utils.interface_agent import InterfaceAgent

    InterfaceAgent.__init__.__defaults__ = tuple(
        sim_model() if isinstance(d, str) and d in old_models else d
        for d in InterfaceAgent.__init__.__defaults__ or ()
    )
    return values


def _patch_completion_for_gpt6() -> None:
    """gpt-6 계열 호출 인자 보정. tau2는 llm_utils.completion으로 litellm을 호출한다.

    - temperature: 기본값(1)만 허용. tau2 기본값 0은 제거
    - reasoning_effort: litellm 1.82.6이 이 모델을 reasoning 모델로 몰라 거부하므로 명시 허용
    - chat completions에서 툴과 reasoning을 함께 쓸 수 없어, 툴이 있으면 reasoning_effort="none"
    """
    import tau2.utils.llm_utils as llm_utils

    original = llm_utils.completion

    def completion(*args, **kwargs):
        model = kwargs.get("model") or (args[0] if args else "")
        if "gpt-6" in model:
            kwargs.pop("temperature", None)
            if kwargs.get("tools"):
                kwargs["reasoning_effort"] = "none"
            if "reasoning_effort" in kwargs:
                kwargs["allowed_openai_params"] = ["reasoning_effort"]
        return original(*args, **kwargs)

    llm_utils.completion = completion


def main() -> None:
    """`tau2` CLI와 같지만 보조 LLM 기본값을 SIM_MODEL로 바꿔 실행한다."""
    from dotenv import load_dotenv

    load_dotenv()
    apply_overrides()
    from cs_agent.registry import register_agents

    register_agents()
    from tau2.cli import main as tau2_main

    tau2_main()
