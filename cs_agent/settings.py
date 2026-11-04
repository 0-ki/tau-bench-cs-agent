"""에이전트 런타임 설정. 환경 변수(`CS_AGENT_*`)나 .env로 덮어쓴다."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CS_AGENT_", env_file=".env", extra="ignore")

    # LLM 호출 하나가 무한정 걸리면 시뮬레이션 전체가 멈추므로 상한을 둔다
    request_timeout_s: float = 60.0
    # 429·5xx는 SDK가 지수 백오프로 재시도한다
    max_retries: int = 3
    # PROTO-01: 독립 읽기 병렬 허용 여부. False면 모든 호출을 1개로 제한
    allow_parallel_reads: bool = True
