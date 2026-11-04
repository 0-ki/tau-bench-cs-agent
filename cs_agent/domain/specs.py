"""tool_specs.yaml 로더. 가드·어댑터가 툴 분류를 하드코딩하지 않도록 명세 한 곳에서 읽는다."""

from functools import cache
from pathlib import Path

import yaml

SPECS_PATH = Path(__file__).with_name("tool_specs.yaml")


@cache
def load_specs() -> dict:
    return yaml.safe_load(SPECS_PATH.read_text(encoding="utf-8"))


def write_tool_names() -> frozenset[str]:
    return frozenset(load_specs()["tools"]["write"])
