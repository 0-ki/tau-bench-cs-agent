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
| CONFIRM-01 | 16 | DB 변경 전 상세를 나열하고 명시적 "yes"를 받는다 | HARD (절차) | 에이전트 |
| INFO-01 | 18 | 툴·사용자가 주지 않은 정보·절차를 지어내지 않음. 주관적 추천 금지 | SOFT | — |
| PROTO-01 | 20 | 한 턴에 툴 호출 1개 또는 응답 1개. 동시에 하지 않음 | HARD (프로토콜) | 에이전트 (어댑터에서 강제 가능) |
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
| ITEM-02 | 110 | 수정할 항목을 다 말했는지 고객에게 확인 요청 | SOFT (절차, 가드 체크 후보) | 에이전트 |
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
| `modify_pending_order_items` | AUTH-01, SCOPE-01, CONFIRM-01, MOD-01, ACT-02, ITEM-01~04, DOM-02 | order_id, item_ids, new_item_ids, payment_method_id | `pending (item modified)` | user, order, item, product, payment_method |
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
6. **항목 모으기 (ACT-02, ITEM-02, EXC-01)**: 1회 제한은 상태 전이로 툴이 강제하지만, 일부만 넣고 호출하면 나머지를 영영 못 바꾼다. 되돌릴 수 없는 실수.
7. **프로토콜 (PROTO-01)**, **이관 순서 (XFER-01)**: 툴 밖의 규칙.

툴이 이미 막는 것(Phase 3에서 중복 구현하되, 가드가 먼저 걸러 에러 왕복을 줄이는 용도): 상태 조건, 취소 사유 값, 결제수단 존재·상이·잔액, 같은 상품·재고, 반품 환불 수단, 항목 존재·개수.

## 4. 실패 가설

베이스라인 5태스크 실패 1건은 시뮬레이터 오류(동의 + `###STOP###` 동시)였고, 에이전트 정책 위반은 관찰되지 않았다. 표본이 작아 아래는 정책·툴 틈 기반 가설이다.

| # | 가설 | 관련 rule_id | Phase 4 대응 |
|---|---|---|---|
| H1 | 여러 항목 수정·교환에서 일부만 넣고 호출해 나머지 요청을 처리 못 함 | ACT-02, ITEM-02, EXC-01 | 호출 전 "더 바꿀 항목 없음" 확인을 pending action 조건으로 |
| H2 | 차액·환불 결제수단을 잘못 고르거나 묻지 않고 기본값 사용 | ITEM-04, RET-03, EXC-03 | 결제수단을 사용자 발화에서 확정한 경우에만 제안 |
| H3 | 확인 없이 실행하거나, 제안 내용과 다른 params로 실행 | CONFIRM-01 | params_hash 일치 |
| H4 | product_id/item_id 혼동, 다른 상품 variant로 교체 시도 → 툴 에러 왕복 | DOM-02, ITEM-03, EXC-02 | 도메인 Decision으로 사전 차단 |
| H5 | 사용자가 user_id를 먼저 주면 인증 단계를 건너뜀 | AUTH-01 | 인증 상태 없으면 쓰기 툴 차단 |
| H6 | 시뮬레이터 오류(동의·종료 동시, 시나리오 이탈) | — | 막을 수 없음. 별도 집계 |

검증하려면 베이스라인을 20태스크로 늘리는 것을 제안한다.
- 예상 호출: 5태스크 66회(판정자 제외) 기준 약 **260~900회**.
- 예상 비용: 5태스크 $0.008 기준 약 **$0.03~0.05** (판정자 별도, 같은 수준).

## 5. 검토 요청

- HARD/SOFT 경계: CONFIRM-01, PROTO-01, ITEM-02(항목 다 말했는지 확인)를 HARD로 둘지.
- 3절 4·5번 툴 틈을 가드에서 막을지. 막으면 정책에는 맞지만, 정답 액션 시퀀스가 틈을 이용하는 태스크가 있으면 점수가 떨어질 수 있다. Phase 4에서 태스크 정답과 대조한다.
- 20태스크 베이스라인 실행 여부.
