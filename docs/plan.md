# 작업 계획과 변경 기록

Phase별 상세 계획은 [roadmap.md](roadmap.md). 이 문서는 결정과 명세 대비 변경점만 기록한다.

## 결정 기록

| 날짜 | 결정 | 이유 |
|---|---|---|
| 2026-11-02 | tau2-bench v2.0.0 + `--language ko` 기준 | 한국어 팩 사용. 1.x 점수와는 비교하지 않음 |
| 2026-11-02 | 보조 LLM(사용자 시뮬레이터, 판정자) 전부 `SIM_MODEL`=gpt-6-luna | 비용. `cs-tau2` 래퍼로 적용. 공식 리더보드와 비교 불가 |
| 2026-11-02 | 외부 제안 "온톨로지 기반 5단계"는 일부만 흡수 | 아래 참고 |
| 2026-11-04 | 정책 판단 기준은 점수가 아니라 실서비스 | 학습 목적. 정답 시퀀스와 어긋나도 정책상 옳은 쪽을 택하고 차이를 기록 |
| 2026-11-04 | CONFIRM-01에 ITEM-02 통합. 1회 한정 액션만 소진 안내 추가 | 확인 메시지 하나로 충분. 01-policy-analysis 5절 |
| 2026-11-04 | 툴 틈 2개(item modified 후 주소·결제 변경, 같은 item 교환) 가드에서 차단 | 실서비스 기준 정책 위반 |
| 2026-11-04 | PROTO-01 완화: 독립 읽기만 병렬, 쓰기는 단독 1개, 텍스트·툴 혼합 금지 | tau2가 병렬 호출 지원(`MultiToolMessage`). 지연·토큰 절감, 쓰기는 확인·부분 실패 때문에 단독 |
| 2026-11-04 | Phase 2: `scripts/run_eval.py` 대신 `cs-tau2 run --agent langchain_agent` | registry 등록만 하면 기존 CLI가 같은 보정·같은 조건으로 실행. 스크립트를 따로 두면 조건이 갈라질 위험 |
| 2026-11-04 | Phase 2: LangChain은 chat model + bind_tools만, `create_agent` 미사용 | tau2 오케스트레이터가 툴을 실행하므로 에이전트 루프와 충돌 |
| 2026-11-04 | Phase 2 다중 trial 비교(3 trial) 생략 | 목표는 tau2 → LangChain 전환 확인. 1 trial 차이(0.70 vs 0.45)는 분산으로 판단, 프레임워크 비교는 Phase 7에서 trial 늘려 수행 |

## 외부 제안에서 흡수한 것

1. **Phase 1 추가**: 쓰기 툴 전제조건을 문서 표뿐 아니라 선언형 데이터(`cs_agent/domain/tool_specs.yaml` 예정)로도 정리한다.
   툴별 입력, 출력, 관련 엔티티(user, order, item, payment_method), 전제조건 rule_id를 담는다.
   Phase 3 도메인 판단과 Phase 4 가드가 같은 명세를 읽는다. 가벼운 Semantic Registry 역할.
2. **Phase 7 지표 추가**: 성공률(pass^k) 외에 정책 위반 건수, 대화당 툴 호출 수, 태스크당 비용.

## 보류한 것

- **Ontology-driven Planner**: retail은 목표가 대화 중 점진적으로 드러나고, 액션 조합이 단순하다.
  예상 실패 원인(정책 위반, 확인 누락, 인자 오류)과도 맞지 않는다.
  Phase 7 결과에서 정보 수집 순서 실패가 많이 남으면 그때 재검토한다. 아이디어는 `99-future-graph.md`에 기록.
