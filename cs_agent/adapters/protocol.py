"""PROTO-01 강제: 한 메시지에 텍스트 또는 툴 호출만. 독립 읽기는 병렬 허용, 쓰기는 단독 1개.

모델 출력을 고쳐서 내보내고, 고친 내용을 위반 목록으로 돌려준다. 고친 메시지가 대화 기록에
그대로 남으므로 모델은 다음 턴에 실제로 실행된 호출만 보게 된다.
"""

from dataclasses import dataclass

from langchain_core.messages import AIMessage


@dataclass(frozen=True)
class Violation:
    kind: str  # text_with_tool_calls | write_with_others | multiple_writes | parallel_disabled
    dropped: tuple[str, ...]


def enforce(
    ai: AIMessage, write_tools: frozenset[str], *, allow_parallel_reads: bool = True
) -> tuple[AIMessage, list[Violation]]:
    calls = list(ai.tool_calls)
    if not calls:
        return ai, []

    violations: list[Violation] = []
    content = ai.content
    if _has_text(content):
        # 툴 호출과 함께 나온 텍스트는 확인 전 안내("취소해 드릴게요")일 수 있어 버린다
        violations.append(Violation("text_with_tool_calls", (str(content)[:200],)))
        content = ""

    writes = [c for c in calls if c["name"] in write_tools]
    if writes and len(calls) > 1:
        reads = [c for c in calls if c["name"] not in write_tools]
        if reads:
            # 읽기를 먼저 실행한다. 쓰기는 결과를 본 뒤 모델이 다시 판단한다
            violations.append(Violation("write_with_others", tuple(c["name"] for c in writes)))
            calls = reads
        else:
            violations.append(Violation("multiple_writes", tuple(c["name"] for c in writes[1:])))
            calls = writes[:1]

    if not allow_parallel_reads and len(calls) > 1:
        violations.append(Violation("parallel_disabled", tuple(c["name"] for c in calls[1:])))
        calls = calls[:1]

    if not violations:
        return ai, []
    return ai.model_copy(update={"content": content, "tool_calls": calls}), violations


def _has_text(content: str | list) -> bool:
    if isinstance(content, str):
        return bool(content.strip())
    return any(isinstance(p, dict) and p.get("text", "").strip() for p in content)
