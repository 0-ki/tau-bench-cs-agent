# 사용 버전

| 항목 | 버전 | 비고 |
|---|---|---|
| tau2-bench | v2.0.0 (`989d328`) | git submodule, 수정 없음. 실행 기준 `--language ko` |
| Python | 3.12.13 | `.python-version`, uv 관리 |
| uv | 0.10.8 | |
| litellm | 1.82.6 | tau2가 `<1.82.7`로 제한 |

정확한 전체 의존성은 `uv.lock`에 고정. LangChain / LangGraph / deepagents는 해당 Phase에서 추가.
