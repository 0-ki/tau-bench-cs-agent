# 사용 버전

| 항목 | 버전 | 비고 |
|---|---|---|
| tau2-bench | v2.0.0 (`989d328`) | git submodule, 수정 없음. 실행 기준 `--language ko` |
| Python | 3.12.13 | `.python-version`, uv 관리 |
| uv | 0.10.8 | |
| litellm | 1.82.6 | tau2가 `<1.82.7`로 제한 |
| langchain-core | 1.7.4 | Phase 2 |
| langchain-openai | 1.7.3 | Phase 2. openai SDK 3.42.1 |
| pydantic-settings | 2.16.2 | Phase 2 설정 |
| pyyaml | 6.0.3 | `tool_specs.yaml` 로더 |

정확한 전체 의존성은 `uv.lock`에 고정. LangGraph / deepagents는 해당 Phase에서 추가.
