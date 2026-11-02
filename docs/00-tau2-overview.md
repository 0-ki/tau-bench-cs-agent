# 00. tau2-bench 개요 (Phase 0)

기준 버전: `tau2-bench` **v2.0.0** 릴리스 태그 (커밋 `989d328`, 2026-10-19). 서브모듈 `tau2-bench/`에 고정.
실행 기준: **retail + `--language ko`** (한국어 팩).

> `main`에는 v2.0.0 이후 커밋이 더 있지만, 재현성을 위해 릴리스 태그에 고정했다.
> 2.0 점수는 1.x 리더보드와 비교되지 않는다 (retail 태스크 50개 교체, COMMUNICATE 채점 방식 변경 등).

## 0. 한국어 팩(`--language ko`)이 바꾸는 것

| 항목 | 내용 |
|---|---|
| 태스크 | retail 동결 subset **50개** (`retail_50`). 영어 2.0과 같은 태스크 집합 |
| DB | 이름·주소 등을 한국식으로 현지화 (`data/tau2/multilingual/ko/regional/retail.json`). 성이 먼저 표시되지만 툴 인자의 first/last 의미는 유지 |
| 금액 | **원본 1단위 = 1,000 KRW** 고정 배율. 가격·환불 모두 같은 배율. 실제 환율 아님 |
| 정책 | **영어 그대로**, 일부 표현만 지역화 (예: zip code → postal code). 규칙 자체는 동일 |
| 에이전트 | 시스템 프롬프트에 한국어 응답 지시 추가 (`agent_language_clause`) |
| 사용자 시뮬레이터 | 한국어 페르소나(존댓말 수준, 거절 화법 등)로 말함 |
| ID, 툴 형식 | 변경 없음. 주문 ID `#W...`, 툴 이름·인자 구조 동일 |

`--no-localize-db`를 쓰면 원본 DB·태스크를 쓰면서 대화만 한국어로 한다.
우리에게 중요한 점: Phase 4 bench 모드의 "명시적 동의" 판단은 **한국어 발화**("네, 진행해 주세요", 우회 거절 "글쎄요, 그건 좀…")를 대상으로 해야 한다.

## 1. 설치와 실행 구조

```
tau-bench-cs-agent/          # 내 uv 프로젝트 (cs-agent)
├── tau2-bench/              # git submodule, 수정 금지
└── pyproject.toml           # tau2 = { path = "tau2-bench", editable = true }
```

- `uv sync` 한 번으로 tau2와 내 패키지가 같은 `.venv`에 설치된다. Python 3.12.13.
- `.env`는 **프로젝트 루트**에 둔다. tau2는 `load_dotenv()`(python-dotenv의 `find_dotenv`)로
  `tau2/utils/utils.py` 위치부터 상위 디렉터리를 거슬러 올라가며 `.env`를 찾으므로 루트 `.env`가 잡힌다.
- 데이터 디렉터리는 `tau2-bench/data`(소스 기준). 결과도 `tau2-bench/data/simulations/`에 저장된다.
  서브모듈 안에 untracked 파일이 생기는 것뿐이고 upstream 코드는 바뀌지 않는다.
- Windows 주의: 콘솔 코드페이지 cp949에서 이모지 출력이 `UnicodeEncodeError`를 낸다.
  `PYTHONUTF8=1` 환경 변수를 켜고 실행한다.

## 2. 에이전트 인터페이스 (`src/tau2/agent/README.md`)

텍스트(턴제) 평가는 `HalfDuplexAgent`를 상속한다.

| 항목 | 내용 |
|---|---|
| 생성자 | `__init__(tools: list[Tool], domain_policy: str, ...)`. LLM을 쓰면 `LLMConfigMixin`으로 `llm`, `llm_args` 추가 |
| `get_init_state(message_history)` | 초기 상태 반환 (보통 시스템 메시지 + 이전 대화) |
| `generate_next_message(message, state)` | 입력 `UserMessage \| ToolMessage \| MultiToolMessage`, 출력 `(AssistantMessage, state)` |
| 툴 호출 방식 | 에이전트가 툴을 **직접 실행하지 않는다**. `AssistantMessage.tool_calls`를 돌려주면 오케스트레이터가 환경에서 실행하고, 결과를 `ToolMessage`로 다음 턴 입력에 넣어준다 |
| 정책 | 텍스트 1회 응답 또는 툴 호출 1회 중 하나만 (retail 정책 문서에도 명시: "at most one tool call at a time") |
| 종료 | 에이전트가 `###STOP###`류 토큰을 내거나 사용자 시뮬레이터가 `###STOP###` / `###TRANSFER###` / `###OUT-OF-SCOPE###`를 내면 끝 |

**등록 방식.** 팩토리 함수 `create_agent(tools, domain_policy, **kwargs)`(kwargs에 `llm`, `llm_args`, `task`)를
`registry.register_agent_factory(factory, "name")`로 등록한다.
코어 에이전트는 `src/tau2/registry.py`를 고치지만, `examples/agents/minimal_text_agent.py`는
**내 코드에서 registry를 import해 등록한 뒤 `run_domain(TextRunConfig(...))`을 호출**한다.
→ 우리는 이 방식을 쓴다. `cs_agent/registry.py`에서 등록하고 `scripts/run_eval.py`로 실행.
upstream 수정이 필요 없다. (단 `tau2 run` CLI는 별도 프로세스라 내 에이전트를 모른다.
결과 파일 포맷은 같으므로 `tau2 view`로는 그대로 볼 수 있다.)

## 3. retail 도메인

- 정책: `data/tau2/domains/retail/policy.md` (136줄). Phase 1에서 규칙 분해.
- DB: `db.json` — products 50, users 500, orders 1000.
- 태스크: 원본 `tasks.json` 114개. 한국어 팩은 그중 동결 subset 50개를 현지화해서 쓴다.
- 툴 (`src/tau2/domains/retail/tools.py`, `@is_tool(ToolType.X)` 데코레이터로 분류):

| 종류 | 툴 |
|---|---|
| READ | `find_user_id_by_email`, `find_user_id_by_name_zip`, `get_order_details`, `get_product_details`, `get_item_details`, `get_user_details`, `list_all_product_types` |
| WRITE | `cancel_pending_order`, `exchange_delivered_order_items`, `modify_pending_order_address`, `modify_pending_order_items`, `modify_pending_order_payment`, `modify_user_address`, `return_delivered_order_items` |
| GENERIC | `calculate`, `transfer_to_human_agents` |

툴 내부에도 일부 검증(예: 주문 상태가 pending인지)이 있지만, 정책 전체를 강제하지는 않는다.
"확인 받기", "본인 인증", "한 사용자만" 같은 규칙은 **에이전트 몫**이다. Phase 1에서 정리.

## 4. 평가 방식 (`docs/evaluation.md`)

- 최종 reward = `reward_basis`에 든 항목 점수의 **곱**. retail 기본값은 `["DB", "COMMUNICATE"]`.
- **DB**: 태스크의 `evaluation_criteria.actions`(정답 궤적 1개)를 새 환경에 재생해 목표 DB를 만들고,
  에이전트 실행 후 DB 해시와 비교. 순서·경로가 달라도 **최종 DB 상태가 같으면 통과**.
  → 읽기 툴 호출은 점수에 영향 없음. 잘못된 쓰기 1번이면 0점. 해야 할 쓰기를 안 해도 0점.
- **COMMUNICATE**: `communicate_info` 정보를 에이전트가 고객에게 전달했는지. 2.0 기본은 **고정된 LLM 판정자**
  (`--communicate-scorer semantic`, 판정 모델 `gpt-5.5` reasoning low — `src/tau2/config.py` 기준.
  README의 `gpt-5.4-mini`는 NL-assertion 판정자이며 COMMUNICATE와 별개). 한국어 대화라서 substring 대신 의미 비교를 쓴다.
  → 판정자 호출용 **OpenAI 키가 필요**하고, 그만큼 호출 비용이 추가된다. 판정 모델은 `--communicate-judge`로 바꿀 수 있지만 그러면 점수 비교성이 깨진다.
  예: 환불 금액 같은 숫자를 정확히 말해야 하는 태스크.
- **ACTION**: retail에서는 점수에 쓰지 않음. 진단용 `partial_action_reward`(m/n)만 `tau2 view`에 나온다.
- 시뮬레이션이 `AGENT_STOP` / `USER_STOP`이 아니라 max_steps, 툴 에러 초과 등으로 끝나면 reward 0.
- **pass^k**: 같은 태스크를 k번 돌렸을 때 **k번 모두 성공할 확률**(n번 중 c번 성공이면 C(c,k)/C(n,k)의 태스크 평균).
  pass^1은 평균 성공률. k가 커질수록 "일관성"을 본다. CS 에이전트는 한 번 맞히는 것보다 매번 맞히는 게 중요해서 이 지표를 쓴다.

**우리 프로젝트에 주는 함의.** DB 해시 비교라서 "정책상 하면 안 되는 쓰기"를 막는 가드(Phase 4)가
점수에 직접 반영된다. 반대로 가드가 정당한 쓰기까지 막으면 바로 0점이 된다.

## 5. 사용자 시뮬레이터 (`src/tau2/user/user_simulator.py`)

- LLM(`--user-llm`)이 고객 역할. 시스템 프롬프트 = 공통 가이드라인
  (`data/tau2/user_simulator/simulation_guidelines.md`) + 태스크의 `user_scenario.instructions`
  (`reason_for_call`, `known_info`, `unknown_info`, `task_instructions`).
- 가이드라인 요지: 한 번에 한 메시지, 시나리오에 없는 정보는 지어내지 않음, 정보는 **물어볼 때 점진적으로** 공개,
  목표 달성 시 `###STOP###`, 이관되면 `###TRANSFER###`, 시나리오로 진행 불가하면 `###OUT-OF-SCOPE###`.
- 따라서 bench 모드의 "고객 확인(yes)"도 이 LLM이 말한다. Phase 4 동의 판단은 이 시뮬레이터 발화를 대상으로 한다.
- 시뮬레이터 자체의 실수(정보 누락, 성급한 STOP)도 점수 노이즈가 된다. 사용자 모델은 실험 내내 고정한다.

## 6. 보조 LLM 일괄 교체 (`cs-tau2`)

사용자 시뮬레이터와 판정자는 모두 **`SIM_MODEL`(기본 `openai/gpt-6-luna`)**로 통일한다. 에이전트 모델만 따로 고른다.

| tau2 기본값 (`config.py`) | 역할 | 원래 모델 |
|---|---|---|
| `DEFAULT_LLM_USER` | 사용자 시뮬레이터 | gpt-4.1 |
| `DEFAULT_SEMANTIC_COMMUNICATE_MODEL` | COMMUNICATE 판정 (**reward 반영**) | gpt-5.5 |
| `DEFAULT_LLM_NL_ASSERTIONS` | NL assertion 판정 (진단용) | gpt-5.4-mini |
| `DEFAULT_LLM_ENV_INTERFACE`, `DEFAULT_LLM_EVAL_USER_SIMULATOR` 등 | 환경 인터페이스, `tau2 review` | gpt-4.1, claude-opus-4-5 |

- 구현: [`cs_agent/tau2_overrides.py`](../cs_agent/tau2_overrides.py). upstream 수정 없이 런타임에 교체한다.
  tau2는 import 시점에 `from tau2.config import X`로 값을 복사하고, pydantic 필드 기본값과 함수 기본 인자로도 굳혀 둔다.
  그래서 config 모듈 하나만 바꾸면 적용되지 않는다. 래퍼는 로드된 tau2 모듈 전역 변수, pydantic 필드 기본값,
  `InterfaceAgent` 기본 인자를 모두 바꾼다.
- 실행은 `tau2` 대신 **`cs-tau2`**를 쓴다. 인자는 `tau2`와 같다.
- dry-run으로 `llm_user`, `communicate_scoring.model`이 `openai/gpt-6-luna`로 바뀐 것을 확인했다.
- 주의 1: 판정 모델을 바꿨으므로 **공식 리더보드 점수와는 비교할 수 없다.** 프로젝트 내부 비교(Phase 2~7)용이다.
- 주의 2: litellm 1.82.6 가격표에 gpt-6 계열이 없어서 [`cs_agent/pricing.py`](../cs_agent/pricing.py)에서 단가를 등록한다
  (USD/1M: luna 0.10/0.50, cached 0.01 등). 그래야 tau2 비용 집계가 맞게 나온다. 검증한 값: luna 입력 1만, 출력 1만 토큰 → $0.001 + $0.005.
  - 한 요청이 입력 272K 토큰을 넘으면 litellm이 OpenAI 장문 할증(입력 2배, 출력 1.5배)을 자동 적용한다. 이 프로젝트 대화 길이에서는 해당 없음.
  - 응답의 model 필드가 날짜 붙은 이름(예: `gpt-6-luna-2026-..`)으로 오면 단가를 못 찾아 비용 0이 된다. 첫 실제 실행에서 확인한다.
- 주의 3: gpt-6 계열은 tau2 기본 호출 인자와 맞지 않는다. 래퍼가 `llm_utils.completion`을 감싸서 자동 보정한다.
  - `temperature`는 기본값 1만 허용한다. tau2 기본값 0을 넣으면 `BadRequestError`가 나므로 제거한다.
    → **같은 태스크도 실행마다 결과가 달라질 수 있다.** pass^k 측정 때 trial 수를 넉넉히 잡는다.
  - chat completions API에서는 툴과 reasoning을 같이 쓸 수 없다("Function tools with reasoning_effort are not supported").
    그래서 툴이 있는 호출(에이전트)에는 `reasoning_effort="none"`을 넣는다. 에이전트는 reasoning 없이 동작한다.
  - litellm 1.82.6은 이 모델을 reasoning 모델로 모른다. 그래서 `reasoning_effort`를 거부하므로 `allowed_openai_params`로 허용한다.
  - 판정자와 사용자 시뮬레이터는 툴이 없어서 reasoning을 쓸 수 있다 (판정자 기본 `low`).

## 7. 실행과 결과 확인

```bash
# 베이스라인: 기본 llm_agent, retail 5개, trial 1
PYTHONUTF8=1 uv run cs-tau2 run --domain retail --language ko \
  --agent-llm "$AGENT_MODEL" \
  --num-tasks 5 --num-trials 1 --save-to baseline-ko-llm_agent-5
```

- `--dry-run`을 붙이면 호출 없이 실행 계획만 출력한다 (확인함).
- 예상 LLM 호출: 태스크당 에이전트 약 10~30회 + 사용자 약 5~15회 + COMMUNICATE 판정 → 5태스크 기준 대략 **80~230회**.
- 결과: `tau2-bench/data/simulations/baseline-ko-llm_agent-5/results.json`

### 베이스라인 결과 (2026-11-02, 에이전트·시뮬레이터 모두 gpt-6-luna, 에이전트 reasoning none)

| 지표 | 값 |
|---|---|
| 태스크 | 5개 (6, 8, 11, 13, 14 `_ko_identity`), trial 1 |
| Pass^1 | **0.80** (4/5) |
| DB 일치 | 4/5 |
| 읽기 액션 일치 | 22/22 |
| 쓰기 액션 일치 | 5/7 |
| LLM 호출 | 에이전트 45회 $0.0066, 사용자 21회 $0.0016 (판정자 제외) |

- 실패한 14번은 **에이전트가 아니라 사용자 시뮬레이터 실수**다. 에이전트는 반품 2건을 정확히 제안하고 "네"를 요청했다.
  그런데 시뮬레이터가 `네, 진행해 주세요.###STOP###`처럼 동의와 종료 토큰을 한 메시지에 함께 보냈다.
  그래서 대화가 끝나 실행되지 못했다. 값싼 모델을 시뮬레이터로 쓸 때 생기는 노이즈다.
  가드를 붙여도 이 유형은 막을 수 없으므로 실패 분류에서 "시뮬레이터 오류"로 따로 센다.
- `tau2 view`의 `Avg Cost/Conversation`이 `n/a`로 나온다. 한국어 팩은 첫 인사("안녕하세요, 무엇을 도와드릴까요?")를
  고정 메시지로 넣는데, 이 메시지에 cost가 없다. tau2 `get_cost`는 cost 없는 메시지가 하나라도 있으면 합계를 None으로 만든다.
  위 비용은 메시지별 cost를 직접 합산한 값이다.
- 보기:
  ```bash
  PYTHONUTF8=1 uv run tau2 view --file tau2-bench/data/simulations/baseline-llm_agent-5/results.json
  PYTHONUTF8=1 uv run tau2 view --dir tau2-bench/data/simulations --only-show-failed
  ```
  화면에서: 전체 지표(평균 reward, pass^k) → 시뮬레이션 선택 → 대화 전문, 툴 호출, reward 내역
  (DB 일치 여부, COMMUNICATE 체크, `Partial Action Reward: m/n`).
- `tau2 play`: 내가 에이전트 역할을 직접 해볼 수 있다. 정책 감 잡기에 유용.

## 8. 용어

- **reward_basis**: 최종 점수에 곱해지는 평가 항목 목록.
- **pass^k**: 위 4절 참고.
- **half-duplex**: 한 번에 한쪽만 말하는 턴제 대화. 텍스트 평가가 여기에 해당.
- **orchestrator**: 에이전트·사용자·환경 사이에서 메시지를 전달하고 툴을 실행하는 루프.
