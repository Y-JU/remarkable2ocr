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
Output a single JSON object with the following structure (do not assume any specific domain or use case):

- outline: array. Each item { "level": 1|2|..., "text": "line text", "id": "out_0" or other unique id }. Top-level outline left-aligned, level 1.
- containers: array. Each item { "type": "rectangle"|"ellipse"|"longbar", "id": "c0", "label": "box title (optional)", "lines": ["line 1 inside box", "line 2"] }.
- arrows: array. Each item { "from_id": "out_0 or c0 etc", "to_id": "target id", "style": "solid"|"dashed", "direction": "forward"|"back"|"bidirectional" }.
- lists: array. Each item { "type": "bullet"|"ordered"|"arrow", "items": [{ "text": "item content" }] }.

Output only one JSON object, no other text. ids are used for arrow from/to references.
"""
