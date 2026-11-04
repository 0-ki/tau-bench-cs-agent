# 로드맵: Phase 0~7

τ-bench(v2.0.0) retail 한국어 팩 위에서 CS 에이전트를 단계적으로 만들고, 각 설계 선택의 효과를 점수로 확인한다.
결정 기록과 명세 대비 변경점은 [plan.md](plan.md)에 남긴다.

## 공통 규칙

- 각 Phase가 끝나면 멈추고 결과를 보고한 뒤 검토를 받는다.
- upstream `tau2-bench/`는 수정하지 않는다. 불가피하면 먼저 제안하고 이 문서에 파일과 이유를 기록한다.
- 같은 비교 조건을 유지한다: `--domain retail --language ko`, `SIM_MODEL`(사용자 시뮬레이터 + 판정자) 고정, `cs-tau2`로 실행.
- 평가는 작은 태스크 수(5개)로 먼저 돌린다. 규모를 키우기 전에는 예상 호출 수와 비용을 보고한다.
- 사용한 라이브러리 버전은 [versions.md](versions.md)에 고정한다.
- **프로덕션 관례로 작성**: 벤치마크용이라도 실서비스에 그대로 가져갈 수 있는 형태로 짠다. 코드를 쓰면서 실무 관례를 익히는 것이 목적이다.
  - 예: 설정은 pydantic-settings, 구조화 로깅, 타임아웃·재시도·rate limit 처리, 툴 입력 검증과 에러 표준화, 트레이싱(LangSmith 또는 OTel), 비용·토큰 계측, 체크포인터 영속화, 테스트(단위 + 녹화 응답 기반), 타입 체크와 lint.
  - 각 Phase에서 프로덕션 관례 1~3개를 골라 적용한다. 무엇을 왜 골랐는지와 실무에서 흔히 쓰는 대안을 Phase 문서의 "프로덕션 관례" 절에 짧게 남긴다.
  - 이미 설명한 기초 개념은 문서로 반복하지 않는다. 코드 주석은 한국어로, 왜 이렇게 했는지만 단다.
- 실패를 분류할 때 **시뮬레이터 오류**(동의와 `###STOP###`을 동시에 보냄, 시나리오 이탈 등)는 에이전트 실패와 따로 센다.

## 한눈에 보기

| Phase | 주제 | 핵심 질문 | 산출 문서 | 상태 |
|---|---|---|---|---|
| 0 | 환경 구성과 베이스라인 | — | `00-tau2-overview.md` | **완료** (Pass^1 0.80, 5태스크) |
| 1 | 정책 분석 (코드 없음) | Q1 준비 | `01-policy-analysis.md`, `tool_specs.yaml` | **완료** (20태스크 Pass^1 0.70, 가설 H1~H9) |
| 2 | LangChain 베이스라인 | Q5 | `02-langchain-baseline.md` | **완료** (20태스크 Pass^1 0.45, 1 trial) |
| 3 | 도메인 계층 (DDD) | Q1, Q2 | `03-domain-layer.md` | 다음 |
| 4 | 가드 계층과 에이전트 저장소 | Q2, Q3, Q4 | `04-guard-layer.md` | 대기 |
| 5 | LangGraph 버전 | Q3, Q5 | `05-langgraph.md` | 대기 |
| 6 | Deep Agents 실험 | Q5 | `06-deepagents.md` | 대기 |
| 7 | 평가 정리 | Q1~Q5 | `07-results.md` | 대기 |
| — | 그래프·온톨로지 (범위 밖) | Q6 | `99-future-graph.md` | 아이디어만 |

핵심 질문:
Q1 정책 판단을 코드로 옮기면 준수율이 오르는가 / Q2 Decision(rule_id, reason)과 "설명만 하는 LLM" 구조가 동작하는가 /
Q3 제안 → 확인 → 재검증 → 실행 → 기록 흐름과 파라미터 불변 보장 / Q4 에이전트 저장소의 스키마와 책임 /
Q5 LangChain, LangGraph, Deep Agents의 득실 / Q6 그래프 DB는 확장 지점만.

## 의존 관계

```
Phase 0 ─▶ Phase 1 ─┬─▶ Phase 2 ──────────────┐
                    └─▶ Phase 3 ─▶ Phase 4 ───┼─▶ Phase 5 ─▶ Phase 6 ─▶ Phase 7
                                              │
           (Phase 2의 어댑터와 측정 스크립트를 Phase 4~6이 재사용)
```

Phase 2와 Phase 3은 서로 의존하지 않는다. 순서는 명세대로 2 → 3으로 진행한다.

---

## Phase 0. 환경 구성과 베이스라인 — 완료

- tau2-bench v2.0.0 서브모듈, uv 프로젝트, `cs-tau2` 래퍼(보조 LLM 교체, gpt-6 인자 보정, 단가 등록)
- 기본 `llm_agent` 베이스라인: retail ko 5태스크, Pass^1 0.80. 실패 1건은 시뮬레이터 오류
- 상세: [00-tau2-overview.md](00-tau2-overview.md)

## Phase 1. 정책 분석 (코드 작성 없음) — 완료

**목표.** 정책을 "코드로 강제할 규칙"과 "프롬프트에 남길 규칙"으로 나눈다. 이 분류표가 Phase 3, 4의 명세가 된다.

**작업.**
1. `policy.md`(한국어 팩 버전 포함)를 문장 단위로 쪼개고, 규칙마다 `rule_id`와 원문 위치(줄 번호)를 붙인다.
2. 분류 기준:
   - **딱딱한 규칙**: 조건이 명확하고, 위반하면 DB 상태가 틀어진다. 예: 주문 상태(pending/delivered), 인증 선행, 본인 소유, 결제수단 조건, 같은 상품의 변형으로만 교환, 1회 한정 수정
   - **부드러운 규칙**: 응대 방식, 정보 수집 순서, 이관 기준, 설명 방식
3. 툴을 읽기/쓰기/기타로 나누고, 쓰기 툴 7개마다 사전 조건, 필요한 입력, 출력, 관련 엔티티, 연결된 rule_id를 정리한다.
4. 3번 결과를 선언형 데이터 `cs_agent/domain/tool_specs.yaml`로도 쓴다 (가벼운 Semantic Registry).
5. upstream 툴 내부에 이미 있는 검증과 정책 규칙을 대조한다. 툴이 막는 것, 툴이 막지 않아 에이전트가 막아야 하는 것을 구분한다.
6. 베이스라인 실패 사례로 "어떤 규칙 위반이 많은가" 가설을 세운다. 필요하면 베이스라인을 20태스크로 늘린다 (실행 전 비용 보고).

**산출물.** `docs/01-policy-analysis.md`(분류표, 툴 표, 가설), `cs_agent/domain/tool_specs.yaml`

**완료 기준.** 분류표를 사용자가 검토하고 확정한다.

## Phase 2. LangChain 베이스라인 에이전트 — 완료

**목표.** 프레임워크 비교의 기준점을 만든다. 가드 없이, 정책 전체를 프롬프트로 주고 tau2 툴을 그대로 쓴다.

**작업.**
1. 설치된 LangChain 버전의 소스와 공식 문서를 확인한 뒤, 버전을 고정한다.
2. 어댑터 `cs_agent/adapters/langchain_agent.py`: tau2 `HalfDuplexAgent` ↔ LangChain 메시지·툴 변환.
   - tau2 `Tool`을 LangChain 툴 스키마로 노출하되, **실행은 tau2 오케스트레이터가 한다**. 에이전트는 tool_call만 반환한다.
   - 한 턴에 텍스트 1개 또는 툴 호출 1개만 내보낸다 (정책 + 프로토콜).
3. `cs_agent/registry.py`에서 등록하고, `scripts/run_eval.py`로 `run_domain`을 실행한다 (`cs-tau2`와 같은 보정 적용).
4. tau2 `llm_agent`와 같은 조건(같은 태스크, 모델, trial)으로 비교한다.

**산출물.** 어댑터, 실행 스크립트, `docs/02-langchain-baseline.md`(구조, 점수, 실패 유형)

**완료 기준.** 기본 에이전트와 점수 차이를 설명할 수 있다. 차이가 크면 원인(프롬프트, 메시지 변환)을 찾는다.

## Phase 3. 도메인 계층 (DDD)

**목표.** 딱딱한 규칙을 LLM 없이 판단하는 도메인 객체로 만든다.

**작업.**
1. 정책 객체: 주문 취소, 배송지 변경, 결제수단 변경, 상품 변경, 반품, 교환, 사용자 주소 변경.
2. 모든 판단은 `Decision(allowed, rule_id, reason, computed_values)`를 반환한다.
   - `reason`과 `computed_values`(환불 금액, 가격 차액 등)가 LLM이 고객에게 설명할 재료다.
   - 금액은 한국어 팩의 KRW 배율(원본 1단위 = 1,000원) 값을 그대로 쓴다.
3. 정책 값(허용 상태, 조건)은 `PolicyRepository` 인터페이스 뒤에 둔다. 지금은 상수 구현이고, 나중에 설정·테이블·그래프 구현으로 바꿀 수 있다.
4. 입력은 tau2 DB 조회 결과(읽기 툴 결과)를 도메인 모델로 바꾼 것이다. tau2 DB에 직접 접근하지 않는다.
5. `tool_specs.yaml`의 rule_id와 정책 객체를 연결한다.
6. pytest로 규칙별 단위 테스트(허용, 거부, 경계 사례)를 만든다. LLM 없이 돌아가야 한다.

**산출물.** `cs_agent/domain/`, `tests/domain/`, `docs/03-domain-layer.md`

**완료 기준.** 분류표의 딱딱한 규칙마다 테스트가 있고 전부 통과한다.

## Phase 4. 가드 계층과 에이전트 저장소

**목표.** 쓰기를 "제안 → 명시적 확인 → 재검증 → 실행 → 기록" 흐름으로만 일어나게 하고, 점수 변화를 측정한다.

**작업.**
1. 쓰기 툴 래퍼(`cs_agent/guard/`):
   - 사전 검증: 본인 인증 여부, 소유 관계, 도메인 Decision
   - 바로 실행하지 않고 pending action을 만든다 (params, `params_hash`, 만료 시간)
   - 명시적 확인이 있을 때만 실행한다. 실행 직전 최신 상태로 재검증하고, 실행하고, 결과를 기록한다
   - 거부와 실패도 사유와 함께 기록한다
2. 확인 모드:
   - **bench 모드**: 시뮬레이터 발화가 명시적 동의인지 판단하고, 동의한 내용과 실행 params가 같을 때만 실행한다.
     코드로 판단하는 범위(params_hash 일치, 제안 직후 발화인지, 만료 여부)와 LLM으로 판단하는 범위(한국어 동의 표현, 돌려 말하는 거절)를 나누고 장단점을 비교한다.
   - **interactive 모드**: 로컬 CLI에서 내가 고객 역할을 하고, 실행 전 확인을 별도 이벤트로 받는다.
3. tau2 프로토콜과 맞추는 방법을 설계한다. 툴 실행은 오케스트레이터가 하므로, 가드는 "툴 호출을 내보낼지"를 결정하는 위치에 둔다.
4. 에이전트 저장소: SQLite + SQLAlchemy로 시작하고, 스키마가 안정되면 docker-compose PostgreSQL로 옮긴다.
   - `action_requests`(상태 머신: proposed → confirmed → executing → executed / rejected / failed / expired)
   - `consents`(동의 발화, 판단 근거, 대상 params_hash)
   - `action_logs`(전이, Decision, 결과)
   - tau2 DB(쇼핑몰 원천 데이터)는 복제하지 않고 ID로만 참조한다.
5. Phase 2와 같은 조건으로 점수를 비교한다.

**산출물.** `cs_agent/guard/`, `cs_agent/store/`, 마이그레이션, `docs/04-guard-layer.md`(상태 전이, 스키마, 점수 변화, 남은 실패 유형)

**완료 기준.** 정책 위반 쓰기가 0건이다. 정당한 쓰기를 가드가 막아서 생긴 실패는 원인별로 정리한다.

## Phase 5. LangGraph 버전

**목표.** 같은 기능을 명시적 상태 그래프로 재구성하고, 구조와 디버깅 측면에서 비교한다.

**작업.**
1. 노드 구성을 제안하고 근거를 설명한다. 후보: 인증 확인 → 정보 수집 → 도메인 판단 → 제안 → 확인 대기 → 재검증·실행 → 응답.
2. checkpointer로 대화 상태를 영속화하고, interactive 모드에서 interrupt로 승인 흐름을 구현한다.
3. bench 모드에서는 tau2 턴 루프와 그래프 실행 단위를 맞춘다 (한 `generate_next_message` = 그래프 한 구간).
4. LangChain 버전 대비 코드 구조, 디버깅 용이성, 점수를 비교한다.

**산출물.** `cs_agent/adapters/langgraph_agent.py`, `docs/05-langgraph.md`

## Phase 6. Deep Agents 실험

**목표.** 플래닝, 서브에이전트, 하네스가 CS 대화에 도움이 되는지, 지연과 비용만 늘리는지 관찰한다.

**작업.**
1. 같은 툴(가드 포함)을 붙인 Deep Agents 버전을 만든다.
2. 내장 기능을 켜고 끄는 ablation: 플래닝 on/off, 서브에이전트 on/off.
3. 세 프레임워크를 비교한다: 구조, 제어 가능성, 점수, 비용, 지연.

**산출물.** `cs_agent/adapters/deepagents_agent.py`, `docs/06-deepagents.md`(비교표)

## Phase 7. 평가 정리

**목표.** 최종 후보들을 같은 조건에서 크게 돌려 핵심 질문에 답한다.

**작업.**
1. 최종 후보로 retail ko 50태스크 전체를 trial 여러 번 실행한다. 실행 전 예상 호출 수와 비용을 보고한다.
   temperature가 1로 고정이라 변동이 크므로 trial을 넉넉히 잡는다.
2. 지표:
   - pass^1, pass^k
   - 정책 위반 건수
   - 대화당 툴 호출 수
   - 태스크당 비용과 지연
3. 실패 대화 분류: 정책 위반, 정보 수집 실패, 확인 누락, 툴 인자 오류, 시뮬레이터 오류.
4. 핵심 질문 Q1~Q5에 대한 이 프로젝트 기준의 답을 쓴다.

**산출물.** `scripts/analyze_failures.py`, `docs/07-results.md`

## 이후 (범위 밖)

- 그래프 DB, 정책 지식 그래프, 연결 기반 악용 탐지: [99-future-graph.md](99-future-graph.md)
- 가벼운 온톨로지와 플래너 실습: Phase 7 이후, airline 같은 더 복잡한 도메인에서 진행할 수 있다.
- 음성, banking_knowledge(RAG) 도메인은 다루지 않는다.
