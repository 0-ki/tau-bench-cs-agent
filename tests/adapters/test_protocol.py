from langchain_core.messages import AIMessage

from cs_agent.adapters.protocol import enforce

WRITES = frozenset({"cancel_pending_order", "return_delivered_order_items"})


def call(name: str, i: int = 0) -> dict:
    return {"id": f"c{i}", "name": name, "args": {}, "type": "tool_call"}


def test_text_only_passes():
    ai = AIMessage(content="안녕하세요")
    assert enforce(ai, WRITES) == (ai, [])


def test_parallel_reads_allowed():
    ai = AIMessage(content="", tool_calls=[call("get_order_details", 1), call("get_order_details", 2)])
    out, violations = enforce(ai, WRITES)
    assert violations == []
    assert len(out.tool_calls) == 2


def test_text_dropped_when_tool_calls():
    ai = AIMessage(content="취소해 드릴게요", tool_calls=[call("get_order_details")])
    out, violations = enforce(ai, WRITES)
    assert out.content == ""
    assert [v.kind for v in violations] == ["text_with_tool_calls"]


def test_write_mixed_with_reads_keeps_reads_only():
    ai = AIMessage(content="", tool_calls=[call("get_order_details", 1), call("cancel_pending_order", 2)])
    out, violations = enforce(ai, WRITES)
    assert [tc["name"] for tc in out.tool_calls] == ["get_order_details"]
    assert violations[0].kind == "write_with_others"
    assert violations[0].dropped == ("cancel_pending_order",)


def test_multiple_writes_keeps_first():
    ai = AIMessage(
        content="", tool_calls=[call("cancel_pending_order", 1), call("return_delivered_order_items", 2)]
    )
    out, violations = enforce(ai, WRITES)
    assert [tc["name"] for tc in out.tool_calls] == ["cancel_pending_order"]
    assert violations[0].kind == "multiple_writes"


def test_single_write_alone_passes():
    ai = AIMessage(content="", tool_calls=[call("cancel_pending_order")])
    assert enforce(ai, WRITES)[1] == []


def test_parallel_disabled_keeps_first():
    ai = AIMessage(content="", tool_calls=[call("get_order_details", 1), call("get_user_details", 2)])
    out, violations = enforce(ai, WRITES, allow_parallel_reads=False)
    assert len(out.tool_calls) == 1
    assert violations[0].kind == "parallel_disabled"
