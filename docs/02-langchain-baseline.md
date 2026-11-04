# Phase 2. LangChain 베이스라인 에이전트

목표: 프레임워크 비교의 기준점. 가드 없음. 정책 전체를 프롬프트로 주고 tau2 툴을 그대로 쓴다.
tau2 `llm_agent`와 **같은 시스템 프롬프트, 같은 툴**을 쓰고 LLM 호출 계층만 LangChain으로 바꿨다.
그래서 두 에이전트의 점수 차이는 프롬프트가 아니라 호출 계층과 PROTO-01 보정에서 나온다.

## 구조

```
tau2 오케스트레이터
  │  UserMessage | ToolMessage | MultiToolMessage
  ▼
LangChainAgent.generate_next_message          cs_agent/adapters/langchain_agent.py
  1. state.messages에 입력 추가
  2. to_lc_messages()  tau2 → LangChain        cs_agent/adapters/convert.py
  3. ChatOpenAI.bind_tools(...).invoke()
  4. protocol.enforce()  PROTO-01 보정          cs_agent/adapters/protocol.py
  5. to_tau2_assistant()  LangChain → tau2 (cost, usage 포함)
  │  AssistantMessage (텍스트 또는 tool_calls)
  ▼
tau2 오케스트레이터가 툴 실행 → 다음 턴
```

- 등록: `cs_agent/registry.py`가 tau2 registry에 `langchain_agent`로 등록한다. `cs-tau2`가 실행 전에 호출한다.
- 실행: `cs-tau2 run --agent langchain_agent ...`. 보조 LLM 교체와 gpt-6 보정이 `llm_agent` 실행과 똑같이 적용된다.
- 언어 지시: tau2가 `domain_policy` 끝에 한국어 지시를 붙여서 넘겨준다. 어댑터는 따로 처리하지 않는다.

### LangChain에서 쓴 것과 안 쓴 것

| 쓴 것 | 이유 |
|---|---|
| `ChatOpenAI` + `bind_tools` | 프로바이더별 메시지·툴 스키마 변환, 재시도·타임아웃, usage 집계 |
| 메시지 타입 (`AIMessage`, `ToolMessage` 등) | tau2 ↔ 모델 사이 공통 표현 |

| 안 쓴 것 | 이유 |
|---|---|
| `create_agent` / AgentExecutor | 툴을 직접 실행하는 루프다. tau2에서는 오케스트레이터가 툴을 실행하므로 루프 소유권이 충돌한다 |
| LangChain `@tool` | tau2 `Tool.openai_schema`를 그대로 넘기면 된다. 래핑하면 스키마가 달라질 위험만 생긴다 |

### tau2는 백엔드만이 아니다: 루프 소유권

tau2는 툴·DB(백엔드)만 주는 게 아니라 **턴 루프를 돌리는 오케스트레이터**이기도 하다.
"LLM 호출 → 툴 실행 → 결과 전달 → 다시 LLM" 루프를 tau2가 돌리고, 에이전트는 매 턴 다음 행동 하나만 정한다.

이유는 채점 방식이다. 평가기는 대화 기록에 남은 tool_call을 새 DB에 다시 실행해 정답 DB와 비교한다
(`tau2/evaluator/evaluator_env.py`, `set_state(message_history=full_trajectory)`).
에이전트가 내부에서 툴을 직접 실행하면 그 호출이 기록에 남지 않아 DB 점수가 틀어진다.
그래서 루프를 소유하는 `create_agent`는 쓸 수 없고, 이 Phase에서 LangChain은 LLM 호출 클라이언트 역할만 한다.

루프를 직접 짜는 방법은 세 가지다.

| 방법 | 루프 주인 | 배우는 것 | 채점 | Phase |
|---|---|---|---|---|
| A. 한 턴 = 행동 하나 (지금) | tau2 | 프롬프트, 메시지·툴 변환, 프로토콜 | 됨 | 2 |
| B. 그래프가 루프를 소유하고, 툴 호출 지점에서 tau2에 넘기고 멈췄다가 결과가 오면 재개 | 내 코드 (LangGraph) | 상태 그래프, 노드 설계, 체크포인트, interrupt, 가드 위치 | 됨 | 5 |
| C. tau2 툴을 순수 백엔드로 쓰고 루프를 직접 실행 | 내 코드 | 실서비스와 같은 전체 루프 | 안 됨 (내가 고객 역할) | 4 interactive |

Phase 2는 비교 기준점이라 일부러 A로 얇게 만들었다. Q5 비교 때 이 점을 기준선으로 삼는다.

### PROTO-01 보정 (`protocol.enforce`)

| 모델 출력 | 처리 |
|---|---|
| 텍스트만 / 툴 호출 1개 / 독립 읽기 여러 개 | 그대로 |
| 텍스트 + 툴 호출 | 텍스트 제거 |
| 읽기 + 쓰기 | 쓰기 제거, 읽기만 실행. 모델이 결과를 보고 쓰기를 다시 판단 |
| 쓰기 여러 개 | 첫 번째만 |

보정한 메시지가 대화 기록에 남으므로 모델은 실제 실행된 호출만 본다. 보정할 때마다 `PROTO-01 위반 보정` 경고 로그를 남긴다.
쓰기 툴 목록은 `tool_specs.yaml`에서 읽는다.

## 프로덕션 관례

| 관례 | 적용 | 실무 대안 |
|---|---|---|
| 설정 관리 | `pydantic-settings` `AgentSettings`(`CS_AGENT_*` 환경 변수): 타임아웃, 재시도 횟수, 병렬 읽기 허용 | dynaconf, Hydra, 12-factor 환경 변수 직접 읽기 |
| 타임아웃·재시도 | `ChatOpenAI(timeout=60, max_retries=3)`. 429·5xx를 SDK가 지수 백오프로 재시도 | tenacity로 직접 감싸기, 게이트웨이(LiteLLM proxy) 레벨 재시도 |
| 녹화 응답 테스트 | `tests/adapters/fixtures/*.json` 응답을 가짜 chat model로 재생. API 키·네트워크 없이 변환과 PROTO-01 보정 검증 | VCR.py·pytest-recording으로 HTTP 녹화, LangSmith 데이터셋 |

비용: `litellm.cost_per_token`과 `cs_agent.pricing` 단가표를 써서 tau2 `llm_agent`와 같은 기준으로 계산한다.

## 테스트

```bash
PYTHONUTF8=1 uv run pytest tests -q
```

- `test_protocol.py`: PROTO-01 보정 7가지 경우
- `test_langchain_agent.py`: 녹화 응답 4턴(단일 읽기 → 병렬 읽기+텍스트 → 읽기+쓰기 → 확인 문구), 모델에 넘어간 메시지 순서, gpt-6 인자 보정

## 결과

### 스모크 (1태스크, 2026-11-04)

| 태스크 | reward | 에이전트 메시지 | 에이전트 비용 | PROTO-01 보정 |
|---|---|---|---|---|
| 6 | 1.0 | 14 | $0.0021 | 0 |

### 20태스크 비교 (2026-11-04, trial 1)

실행: `baseline-ko-langchain_agent-20`. 조건은 `llm_agent` 20태스크와 같음.

| 지표 | llm_agent | langchain_agent |
|---|---|---|
| Pass^1 | **0.70** (14/20) | **0.45** (9/20) |
| 시뮬레이터 오류 | 1 | 3 |
| 에이전트 실패 | 5 | 8 |
| 에이전트 비용 합계 | $0.031 | $0.030 |
| 툴 호출 수 | 202 | 171 |
| 병렬 호출 메시지 | 19 | 8 |
| PROTO-01 보정 | (해당 없음) | 0건 |

langchain_agent 실패 11건 분류:

| 분류 | 태스크 | 내용 |
|---|---|---|
| 시뮬레이터 오류 | 14, 18, 38 | 14: 동의와 `###STOP###` 동시. 18: 첫 메시지에서 바로 `###STOP###`. 38: 시나리오에 없는 취소 사유("실수로 주문함")를 사용자가 지정, 에이전트는 그대로 따름 |
| H7 이른 이관 | 6, 16, 19 | 범위 밖 요청이나 인증 실패 후 바로 상담원 연결 |
| H10 한국어 이름 파싱 (신규) | 8, 17 | "고 미나"를 `Mina/Go`로 로마자 변환, "전 하나고"의 "전"을 성이 아니라 "저는"으로 읽음. 인증 실패 후 포기 |
| H4 상품·계산 오류 | 23, 30, 36 | 23: 다른 variant로 교환. 30: 스니커즈를 등산화 주문으로 잘못 매핑. 36: 최저가 옵션으로 한도 이하가 가능한데 불가로 판단하고 취소 |

### 해석

- **어댑터 버그로 보이지 않는다.** 새로 실패한 태스크를 보면 원인이 모두 Phase 1에서 이미 본 유형(H4, H7)이거나 시뮬레이터 오류다. 인증 조회 행동도 두 에이전트가 비슷하다.

  | 지표 | llm_agent | langchain_agent |
  |---|---|---|
  | 사용자 조회 호출 | 57 | 56 |
  | 빈 인자 호출 (H9) | 14 | 17 |
  | `User not found` | 37 | 41 |

  llm_agent도 8번에서 가짜 이메일과 로마자 이름으로 여러 번 실패한 뒤에야 성공했다. 같은 약점이 있고 이번엔 운 좋게 회복한 것이다.
- **차이의 대부분은 분산이다.** temperature 1, trial 1이라 태스크 하나의 성패가 크게 흔들린다. 시뮬레이터 오류만 1건 → 3건으로 늘었다.
- **H10 추가.** 한국어 팩에서 성·이름 분리와 로마자 변환은 두 에이전트 공통 약점이다. Phase 3·4에서 `find_user_id_by_name_zip` 실패 시 성·이름을 뒤집어 재시도하는 규칙 후보로 둔다.

### 다음 측정 제안

1 trial로는 프레임워크 차이를 말할 수 없다. 두 에이전트를 20태스크 × 3 trial로 다시 돌려 pass^1 평균과 pass^3를 비교하는 것을 제안한다.
- 예상 비용: 에이전트 약 $0.18, 사용자 시뮬레이터 약 $0.05, 판정자 별도.
