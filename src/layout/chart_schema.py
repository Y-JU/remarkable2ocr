"""
Content-agnostic chart semantic schema: outline, containers, arrows, lists.
"""
from __future__ import annotations

from typing import Any, TypedDict


class OutlineItem(TypedDict, total=False):
    level: int
    text: str
    id: str
    children: list["OutlineItem"]


class Container(TypedDict, total=False):
    type: str
    id: str
    label: str
    lines: list[str]


class Arrow(TypedDict, total=False):
    from_id: str
    to_id: str
    style: str
    direction: str


class ListItem(TypedDict, total=False):
    text: str
    sub: list["ListItem"]


class ListBlock(TypedDict, total=False):
    type: str
    items: list[ListItem]


class ChartSchema(TypedDict, total=False):
    outline: list[OutlineItem]
    containers: list[Container]
    arrows: list[Arrow]
    lists: list[ListBlock]


CHART_SCHEMA_INSTRUCTION = """
输出一个 JSON 对象，包含以下结构（不要假设任何具体领域或用例）：

- outline: 数组。每项为 { "level": 1|2|..., "text": "该行文本", "id": "out_0" 等唯一 id }。一级大纲左对齐，level 为 1。
- containers: 数组。每项为 { "type": "rectangle"|"ellipse"|"longbar", "id": "c0", "label": "框标题（可选）", "lines": ["框内第1行","第2行"] }。
- arrows: 数组。每项为 { "from_id": "out_0 或 c0 等", "to_id": "目标 id", "style": "solid"|"dashed", "direction": "forward"|"back"|"bidirectional" }。
- lists: 数组。每项为 { "type": "bullet"|"ordered"|"arrow", "items": [{ "text": "项内容" }] }。

只输出一个 JSON 对象，不要其他说明。id 用于箭头起止引用。
"""
