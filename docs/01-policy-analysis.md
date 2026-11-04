# Phase 1. 정책 분석

원문: `tau2-bench/data/tau2/domains/retail/policy.md` (줄 번호 = 이 파일 기준).
한국어 팩은 정책을 영어 그대로 두고 일부 표현만 지역화한다(zip code → postal code). 규칙은 같다.
툴 대조 대상: `tau2-bench/src/tau2/domains/retail/tools.py`.

분류:
- **HARD**: 조건이 명확하고 위반하면 DB 상태가 틀어진다. Phase 3 도메인 객체 / Phase 4 가드가 코드로 강제한다.
- **SOFT**: 응대 방식, 설명, 판단. 프롬프트에 남긴다.
- **툴 검증** 열: `툴` = upstream 툴이 이미 막음, `에이전트` = 툴이 막지 않아 에이전트(가드)가 막아야 함, `—` = 해당 없음.

## 1. 규칙 분류표

### 공통

| rule_id | 줄 | 규칙 | 분류 | 툴 검증 |
|---|---|---|---|---|
| AUTH-01 | 10 | 대화 시작 시 이메일 또는 이름+우편번호로 user_id를 찾아 인증. 사용자가 user_id를 직접 줘도 생략 불가 | HARD | 에이전트 |
| AUTH-02 | 12 | 인증 후에만 주문·상품·프로필 정보 제공 | HARD | 에이전트 |
| SCOPE-01 | 14 | 한 대화에 한 사용자. 다른 사용자 관련 요청은 거부 (= 대상 주문·결제수단은 인증된 사용자 소유여야 함) | HARD | 에이전트 (결제수단은 `order.user_id` 기준으로만 확인) |
| CONFIRM-01 | 16, 110, 130 | DB 변경 전 상세를 짧게 나열하고 명시적 "yes"를 받는다. 1회 한정 액션(상품 수정, 교환)이면 "주문당 1회, 이번에 소진" 안내를 덧붙인다 (ITEM-02 흡수) | HARD (절차) | 에이전트 |
| INFO-01 | 18 | 툴·사용자가 주지 않은 정보·절차를 지어내지 않음. 주관적 추천 금지 | SOFT | — |
| PROTO-01 | 20 | 한 메시지에 텍스트 또는 툴 호출만. 독립 읽기는 병렬 허용, 쓰기는 단독 1개 (원문 "한 번에 하나"를 완화) | HARD (프로토콜) | 에이전트 (어댑터에서 강제) |
| DENY-01 | 22 | 정책 위반 요청은 거부 | SOFT (메타) | — |
| XFER-01 | 24 | 범위 밖일 때만 이관. `transfer_to_human_agents` 호출 후 고정 문구 전송 | SOFT (판단) + HARD (순서·문구) | 에이전트 |
| CAP-01 | 3–8 | 가능한 업무: pending 취소·수정, delivered 반품·교환, 기본 주소 변경, 본인 정보 조회 | SOFT (XFER-01 판단 근거) | — |
| DOM-01 | 28 | DB 시각은 EST 24시간제 | SOFT (설명) | — |
| DOM-02 | 62 | product_id와 item_id를 혼동하지 않음 | HARD (입력 검증) | 툴 (일부: 없는 id면 에러) |
| ACT-01 | 82 | 액션은 pending 또는 delivered 주문에만 | HARD | 툴 |
| ACT-02 | 84 | 교환·상품 수정은 주문당 1회. 바꿀 항목을 전부 모은 뒤 한 번에 호출 | HARD (1회) + SOFT (모으기) | 툴 (상태 전이로 2회째 차단) / 에이전트 (모으기) |

### 주문 취소 (`cancel_pending_order`)

| rule_id | 줄 | 규칙 | 분류 | 툴 검증 |
|---|---|---|---|---|
| CAN-01 | 88 | status == `pending`일 때만. 실행 전 상태 확인 | HARD | 툴 (정확히 `pending`, `pending (item modified)`는 거부) |
| CAN-02 | 90 | 사용자가 order_id와 사유를 확인. 사유는 `no longer needed` / `ordered by mistake`만 | HARD | 툴 (사유 값) / 에이전트 (사용자 확인) |
| CAN-03 | 92 | 결과 설명: `cancelled`, 기프트카드는 즉시 환불, 그 외 5~7영업일 | SOFT | — |

### 대기 주문 수정 (공통 + 주소 `modify_pending_order_address`)

| rule_id | 줄 | 규칙 | 분류 | 툴 검증 |
|---|---|---|---|---|
| MOD-01 | 96 | status == `pending`일 때만 | HARD | **틈**: 주소·결제 툴은 `"pending" in status`로 검사해 `pending (item modified)`도 통과 |
| MOD-02 | 98 | 수정 가능 항목은 배송지, 결제수단, 상품 옵션뿐 | HARD | 툴 (툴이 그것뿐) |

### 결제수단 변경 (`modify_pending_order_payment`)

| rule_id | 줄 | 규칙 | 분류 | 툴 검증 |
|---|---|---|---|---|
| PAY-01 | 102 | 기존과 다른 단일 결제수단 1개 | HARD | 툴 (결제 1건, 다른 id) |
| PAY-02 | 104 | 기프트카드면 잔액 ≥ 주문 총액 | HARD | 툴 |
| PAY-03 | 106 | 결과 설명: 상태 유지, 기존 수단 환불(기프트카드 즉시, 그 외 5~7영업일) | SOFT | — |

### 상품 수정 (`modify_pending_order_items`)

| rule_id | 줄 | 규칙 | 분류 | 툴 검증 |
|---|---|---|---|---|
| ITEM-01 | 110 | 주문당 1회. 이후 상태 `pending (item modified)`, 더 이상 수정·취소 불가 | HARD | 툴 (상품 재수정·취소 차단) / **틈**: 주소·결제 수정은 통과 |
| ITEM-03 | 112 | 같은 상품의 다른 옵션, 재고 있는 variant로만. 상품 종류 변경 불가 | HARD | 툴 (같은 product, available, 다른 id) |
| ITEM-04 | 114 | 차액 결제·환불용 결제수단 필요. 기프트카드면 잔액 ≥ 차액 | HARD | 툴 |

### 반품 (`return_delivered_order_items`)

| rule_id | 줄 | 규칙 | 분류 | 툴 검증 |
|---|---|---|---|---|
| RET-01 | 118 | status == `delivered`일 때만 | HARD | 툴 |
| RET-02 | 120 | 사용자가 order_id와 반품 항목 목록을 확인 | HARD (절차) | 에이전트 (항목 존재는 툴) |
| RET-03 | 122–124 | 환불 수단은 원 결제수단 또는 기존 기프트카드 | HARD | 툴 |
| RET-04 | 126 | 결과 설명: `return requested`, 반품 안내 이메일 | SOFT | — |

### 교환 (`exchange_delivered_order_items`)

| rule_id | 줄 | 규칙 | 분류 | 툴 검증 |
|---|---|---|---|---|
| EXC-01 | 130 | status == `delivered`일 때만. 교환 항목을 다 말했는지 확인 요청 | HARD + SOFT | 툴 (상태) / 에이전트 (확인 요청) |
| EXC-02 | 132 | 같은 상품의 다른 옵션, 재고 있는 variant로만 | HARD | 툴 (같은 product, available) / **틈**: 같은 item_id로 교환 허용 |
| EXC-03 | 134 | 차액용 결제수단. 기프트카드면 잔액 ≥ 차액 | HARD | 툴 |
| EXC-04 | 136 | 결과 설명: `exchange requested`, 이메일 안내, 새 주문 불필요 | SOFT | — |

### 사용자 주소 변경 (`modify_user_address`)

| rule_id | 줄 | 규칙 | 분류 | 툴 검증 |
|---|---|---|---|---|
| UADDR-01 | 7 | 인증된 본인의 기본 주소만 변경 | HARD | **틈**: 툴은 user 존재만 확인 |


## 2. 툴 분류

| 구분 | 툴 |
|---|---|
| 읽기 (7) | `find_user_id_by_email`, `find_user_id_by_name_zip`, `get_user_details`, `get_order_details`, `get_product_details`, `get_item_details`, `list_all_product_types` |
| 쓰기 (7) | `cancel_pending_order`, `modify_pending_order_address`, `modify_pending_order_payment`, `modify_pending_order_items`, `return_delivered_order_items`, `exchange_delivered_order_items`, `modify_user_address` |
| 기타 (2) | `calculate`, `transfer_to_human_agents` |


### 쓰기 툴 명세

| 툴 | 사전 조건 (rule_id) | 입력 | 결과 상태 | 엔티티 |
|---|---|---|---|---|
| `cancel_pending_order` | AUTH-01, SCOPE-01, CONFIRM-01, CAN-01, CAN-02 | order_id, reason | `cancelled`, 환불 기록 | user, order, payment_method |
| `modify_pending_order_address` | AUTH-01, SCOPE-01, CONFIRM-01, MOD-01, ITEM-01 | order_id, address1, address2, city, state, country, zip | 상태 유지, 주소 변경 | user, order |
| `modify_pending_order_payment` | AUTH-01, SCOPE-01, CONFIRM-01, MOD-01, ITEM-01, PAY-01, PAY-02 | order_id, payment_method_id | 상태 유지, 결제·환불 기록 | user, order, payment_method |
| `modify_pending_order_items` | AUTH-01, SCOPE-01, CONFIRM-01, MOD-01, ACT-02, ITEM-01, ITEM-03, ITEM-04, DOM-02 | order_id, item_ids, new_item_ids, payment_method_id | `pending (item modified)` | user, order, item, product, payment_method |
| `return_delivered_order_items` | AUTH-01, SCOPE-01, CONFIRM-01, RET-01~03 | order_id, item_ids, payment_method_id | `return requested` | user, order, item, payment_method |
| `exchange_delivered_order_items` | AUTH-01, SCOPE-01, CONFIRM-01, ACT-02, EXC-01~03, DOM-02 | order_id, item_ids, new_item_ids, payment_method_id | `exchange requested` | user, order, item, product, payment_method |
| `modify_user_address` | AUTH-01, SCOPE-01, CONFIRM-01, UADDR-01 | user_id, address1, address2, city, state, country, zip | 기본 주소 변경 | user |

같은 내용을 선언형으로 [`cs_agent/domain/tool_specs.yaml`](../cs_agent/domain/tool_specs.yaml)에 둔다.

## 3. 툴이 막지 않는 것 (가드가 막아야 할 것)

upstream 툴은 데이터 정합성(존재, 상태, 잔액, 같은 상품)만 본다. 대화 맥락이 필요한 규칙은 전부 에이전트 몫이다.

1. **인증 (AUTH-01, AUTH-02)**: 툴은 인증 여부를 모른다. user_id만 알면 누구 주문이든 조회·수정된다.
2. **소유 관계 (SCOPE-01, UADDR-01)**: 어떤 툴도 "대상 주문이 인증된 사용자 것인가"를 보지 않는다. 결제수단은 `order.user_id` 기준으로 찾으므로 주문 주인 것이긴 하지만, 그 주인이 대화 상대인지는 모른다.
3. **명시적 확인 (CONFIRM-01, CAN-02, RET-02)**: 툴 호출 = 즉시 실행.
4. **상품 수정 후 주소·결제 변경 (MOD-01, ITEM-01)**: `_is_pending_order`가 `"pending" in status`라서 `pending (item modified)` 주문의 주소·결제가 바뀐다. 정책상 불가.
5. **같은 item으로 교환 (EXC-02)**: 상품 수정 툴은 `item_id == new_item_id`를 막지만 교환 툴은 막지 않는다.
6. **항목 모으기 (ACT-02, CONFIRM-01, EXC-01)**: 1회 제한은 상태 전이로 툴이 강제하지만, 일부만 넣고 호출하면 나머지를 영영 못 바꾼다. 되돌릴 수 없는 실수.
7. **프로토콜 (PROTO-01)**, **이관 순서 (XFER-01)**: 툴 밖의 규칙.

툴이 이미 막는 것(Phase 3에서 중복 구현하되, 가드가 먼저 걸러 에러 왕복을 줄이는 용도): 상태 조건, 취소 사유 값, 결제수단 존재·상이·잔액, 같은 상품·재고, 반품 환불 수단, 항목 존재·개수.

## 4. 실패 가설

베이스라인 5태스크 실패 1건은 시뮬레이터 오류(동의 + `###STOP###` 동시)였고, 에이전트 정책 위반은 관찰되지 않았다. 표본이 작아 아래는 정책·툴 틈 기반 가설이다.

| # | 가설 | 관련 rule_id | Phase 4 대응 |
|---|---|---|---|
| H1 | 여러 항목 수정·교환에서 일부만 넣고 호출해 나머지 요청을 처리 못 함 | ACT-02, CONFIRM-01, EXC-01 | 호출 전 "더 바꿀 항목 없음" 확인을 pending action 조건으로 |
| H2 | 차액·환불 결제수단을 잘못 고르거나 묻지 않고 기본값 사용 | ITEM-04, RET-03, EXC-03 | 결제수단을 사용자 발화에서 확정한 경우에만 제안 |
| H3 | 확인 없이 실행하거나, 제안 내용과 다른 params로 실행 | CONFIRM-01 | params_hash 일치 |
| H4 | product_id/item_id 혼동, 다른 상품 variant로 교체 시도 → 툴 에러 왕복 | DOM-02, ITEM-03, EXC-02 | 도메인 Decision으로 사전 차단 |
| H5 | 사용자가 user_id를 먼저 주면 인증 단계를 건너뜀 | AUTH-01 | 인증 상태 없으면 쓰기 툴 차단 |
| H6 | 시뮬레이터 오류(동의·종료 동시, 시나리오 이탈) | — | 막을 수 없음. 별도 집계 |

### 20태스크 검증 결과 (2026-11-04)

실행: `baseline-ko-llm_agent-20`, 기본 `llm_agent`, trial 1. **Pass^1 0.70 (14/20)**.

| 태스크 | 실패 지점 | 분류 | 가설 |
|---|---|---|---|
| 6 | 에이전트는 확인까지 정상. 시뮬레이터가 "네 … `###STOP###`"을 한 메시지로 보내 교환 미실행 | 시뮬레이터 오류 | H6 |
| 19 | 사무용 의자 최저가 옵션(466,440원)이 **품절**인데 "재고 있음"으로 안내. 절감액 47,020원(정답 41,640원). 반품 실행 전 상세 나열·"네" 확인 없음. 같은 주문에 반품 후 교환이 불가능하다는 것도 미리 알리지 않음 | 에이전트 | H4, H3, H8 |
| 25 | 환불 수단을 묻지 않고, 확인도 없이 PayPal로 반품 실행. 사용자는 Amex를 원했고 정책상 불가하므로 정답은 쓰기 없음 | 에이전트 (정책 위반 쓰기) | H2, H3 |
| 32 | 첫 요청(분실 태블릿 환불)이 범위 밖이라 바로 이관. 뒤에 남은 범위 내 요청(취소 2건, 반품 1건)을 못 받음 | 에이전트 | H7 |
| 36 | 분할 결제 불가 → 바로 이관. "불가"라고 안내하고 대안을 물어야 했음 | 에이전트 | H7 |
| 38 | 36과 같음 | 에이전트 | H7 |

집계: 에이전트 실패 5건, 시뮬레이터 오류 1건. 시뮬레이터 오류를 빼면 에이전트 기준 15/20 성공.

가설 판정:
- **H1 (항목 일부만 넣고 호출)**: 미관찰. 에이전트가 "교환은 한 번만" 안내를 스스로 함(6, 19).
- **H2 (결제수단 임의 선택)**: 관찰 1건(25).
- **H3 (확인 없이 실행)**: 관찰 2건(19, 25). 둘 다 반품. 사용자가 의사를 밝히면 그걸 확인으로 간주하고 바로 실행.
- **H4 (상품·variant 오류)**: 관찰 1건(19). id 혼동이 아니라 품절 variant를 최저가로 안내.
- **H5 (인증 생략)**: 미관찰. 다만 정보를 받기 전에 빈 인자(`email: ""`, `zip: ""`)로 조회 툴을 먼저 부르는 패턴이 4건(25, 32, 36, 38).
- **H6 (시뮬레이터 오류)**: 관찰 1건(6).

새 가설:

| # | 가설 | 관련 rule_id | 대응 |
|---|---|---|---|
| H7 | 요청 하나가 범위 밖이면 대화 전체를 이관. 불가 안내 후 남은 요청을 이어가야 함 | XFER-01, DENY-01 | 프롬프트: "불가 안내 → 다른 요청 확인 → 그래도 범위 밖일 때만 이관". 가드: 이관 전에 사용자가 이관을 원했는지 확인 |
| H8 | 같은 주문에 대한 액션끼리 배타적임(반품하면 교환 불가)을 모르고 순차 실행 | ACT-01, RET-01, EXC-01 | 도메인 Decision이 "이 액션 후 불가능해지는 액션"을 반환. 제안 단계에서 안내 |
| H9 | 정보 없이 빈 인자로 조회 툴 호출 | AUTH-01 | 어댑터·가드에서 빈 필수 인자 차단 |
| H10 | 한국어 이름의 성·이름 분리 오류, 로마자 변환 (Phase 2에서 발견: langchain 8·17, llm_agent 8에서도 재시도 다수) | AUTH-01 | 조회 실패 시 성·이름 뒤집기 재시도, 로마자 변환 금지를 프롬프트·가드에 |

Phase 3~4 우선순위: **H3·H2(확인·결제수단, 정책 위반 쓰기) > H7(이관) > H4·H8(도메인 계산) > H9**.

## 프로덕션 관례

코드 작성이 없는 단계라 1개만 적용했다.

| 관례 | 적용 | 실무 대안 |
|---|---|---|
| 명세를 데이터로, 단일 출처 | 규칙·툴 사전 조건을 `tool_specs.yaml`에 두고 문서·도메인·가드·어댑터가 같은 파일을 읽는다(Phase 2 어댑터가 쓰기 툴 목록을 여기서 읽음) | OpenAPI 확장 필드(`x-preconditions`), OPA/Rego 같은 정책 엔진, DB 정책 테이블 |

## 5. 확정 사항 (2026-11-04)

관점: 벤치마크 점수가 아니라 실서비스 기준으로 판단한다.

- **CONFIRM-01 + ITEM-02 통합**: 확인은 하나의 규칙. 나열은 짧고 보기 쉽게(무엇을, 어느 주문, 금액·결제수단).
  1회 한정 액션일 때만 "주문당 1회만 가능하고 이번에 소진된다"는 안내를 추가한다.
- **툴 틈 두 개는 가드에서 막는다**: `pending (item modified)` 주문의 주소·결제 변경, 같은 item_id로 교환.
  태스크 정답과 어긋나 점수가 떨어지면 원인으로 기록만 하고 가드는 유지한다.
- **PROTO-01**: 독립 읽기만 병렬 허용. 쓰기는 한 메시지에 단독 1개. 텍스트와 툴 호출 혼합 금지. 근거는 6절. Phase 2 어댑터에서 강제.

## 6. PROTO-01 정리

tau2는 한 메시지의 툴 호출 여러 개를 지원한다(`MultiToolMessage`로 결과를 한꺼번에 돌려줌). 정책 원문은 "한 번에 하나"다.

| 경우 | 판단 |
|---|---|
| 텍스트 + 툴 호출을 한 메시지에 | 금지. 확인 전에 실행되는 꼴 |
| 서로 독립인 읽기 여러 개 (주문 3건 조회 등) | 병렬 허용. 왕복 수와 지연이 준다 |
| 앞 결과가 다음 인자인 호출 (`find_user_id_*` → `get_user_details`) | 자연히 순차. 인자를 모르니 병렬로 낼 수 없다 |
| 쓰기 | 한 메시지에 하나만, 다른 호출과 섞지 않음. 확인이 액션마다 필요하고 부분 실패 처리가 복잡해진다 |

순차만 강제할 때: 순서가 결정적이고 로그·가드·재현이 단순하다. 대신 읽기마다 왕복이 생겨 지연과 토큰(매 호출 문맥 재전송)이 는다.
