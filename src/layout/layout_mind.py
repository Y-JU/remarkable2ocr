"""
Export OCR layout to XMind mind map; preserve link relationships as parent-child.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _collect_lines(all_ocr_pages: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Flatten OCR pages to a single list of lines (with optional links)."""
    lines: list[dict[str, Any]] = []
    for page in all_ocr_pages:
        for row in page:
            text = (row.get("text") or "").strip()
            if not text:
                continue
            lines.append(dict(row))
    return lines


def _build_tree_from_links(
    lines: list[dict[str, Any]],
) -> list[tuple[str, list[int]]]:
    """
    Build a tree from OCR lines using links: node i has children links[i].
    Returns list of (title, list of child indices) for each node; indices refer to lines.
    Nodes already added as descendant of root are skipped when encountered again (first parent wins).
    """
    n = len(lines)
    # title for index i
    titles = [(lines[i].get("text") or "").strip() or f"Item {i}" for i in range(n)]
    # children of i = links[i] if present, else []
    links: list[list[int]] = []
    for i in range(n):
        raw = lines[i].get("links")
        if isinstance(raw, list):
            kids = [int(k) for k in raw if isinstance(k, (int, float)) and 0 <= int(k) < n]
        else:
            kids = []
        links.append(kids)

    # BFS from 0: root = 0, then add links[0] as children, etc. Skip nodes already added.
    added: set[int] = set()
    result: list[tuple[str, list[int]]] = []
    stack = [0]
    while stack:
        i = stack.pop()
        if i in added:
            continue
        added.add(i)
        children = [j for j in links[i] if j not in added]
        result.append((titles[i], children))
        for j in reversed(children):
            stack.append(j)
    # Append any remaining nodes (no incoming link from 0) as extra roots' children in order
    for i in range(n):
        if i not in added:
            result.append((titles[i], []))
    return result


def build_xmind(
    all_ocr_pages: list[list[dict[str, Any]]],
    out_path: Path | str,
    *,
    sheet_title: str = "OCR Layout",
) -> Path:
    """
    Build an XMind mind map from OCR layout (all pages flattened).
    Uses OCR "links" to define parent-child: line i with links=[j,k] becomes topic i with children j, k.
    Saves to out_path (e.g. project_name.xmind).
    """
    try:
        from py_xmind16 import Workbook
    except ImportError as e:
        raise ImportError("py-xmind16 is required for --xmind. Install with: pip install py-xmind16") from e

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = _collect_lines(all_ocr_pages)
    if not lines:
        # Empty workbook with one root
        workbook = Workbook()
        sheet = workbook.create_sheet(sheet_title)
        root = sheet.get_root_topic()
        root.title = "(No content)"
        workbook.save(str(out_path))
        return out_path

    tree = _build_tree_from_links(lines)
    # Map index in lines -> (title, children indices). tree is list of (title, child_indices) in BFS order.
    # We need to build the xmind: root = tree[0], then recursively add children by index.
    # Actually tree might have multiple roots (nodes not reachable from 0). So we have a forest.
    # Build one root topic "OCR Layout" and attach first tree root as subtopic, then others.
    workbook = Workbook()
    sheet = workbook.create_sheet(sheet_title)
    root = sheet.get_root_topic()

    # Single root: use first line as root topic, then add its children recursively
    if len(lines) == 1:
        root.title = tree[0][0]
        workbook.save(str(out_path))
        return out_path

    # Use first line as root
    root.title = tree[0][0]
    # We need to recursively add subtopics. tree[i] = (title, [child indices in lines]).
    # But tree is in BFS order - so tree[0] is first node, tree[1], tree[2]... are in discovery order.
    # The "children" in tree[0] are indices into lines (0-based). So we need a way to add topic for line index j as child of current topic. Build a map: index -> (title, children_indices)
    index_to_node: list[tuple[str, list[int]]] = []
    for i in range(len(lines)):
        title = (lines[i].get("text") or "").strip() or f"Item {i}"
        raw = lines[i].get("links")
        kids = []
        if isinstance(raw, list):
            n = len(lines)
            kids = [int(k) for k in raw if isinstance(k, (int, float)) and 0 <= int(k) < n]
        index_to_node.append((title, kids))

    def add_children(parent_topic: Any, node_index: int, visited: set[int]) -> None:
        if node_index in visited:
            return
        visited.add(node_index)
        title, child_indices = index_to_node[node_index]
        for j in child_indices:
            if j in visited:
                continue
            child_title, _ = index_to_node[j]
            sub = parent_topic.add_subtopic(child_title)
            add_children(sub, j, visited)

    visited: set[int] = {0}
    for j in index_to_node[0][1]:
        if j not in visited:
            child_title, _ = index_to_node[j]
            sub = root.add_subtopic(child_title)
            add_children(sub, j, visited)

    # Remaining nodes (not under 0) as direct subtopics of root
    for i in range(1, len(lines)):
        if i not in visited:
            root.add_subtopic(index_to_node[i][0])
            visited.add(i)

    workbook.save(str(out_path))
    return out_path


def load_xmind_topic_titles(xmind_path: Path | str) -> list[str]:
    """Load an .xmind file and return all topic titles in traversal order (for tests)."""
    from py_xmind16 import Workbook

    w = Workbook.load(str(xmind_path))
    titles: list[str] = []

    def walk(topic: Any) -> None:
        t = getattr(topic, "title", None)
        if t:
            titles.append(str(t).strip())
        for st in getattr(topic, "subtopics", []) or []:
            walk(st)

    for sheet in (w.get_sheet(i) for i in range(w.sheet_count)):
        root = sheet.root_topic
        if root:
            walk(root)
    return titles


def load_xmind_parent_child_pairs(xmind_path: Path | str) -> list[tuple[str, str]]:
    """Load an .xmind file and return (parent_title, child_title) for each link (for validation)."""
    from py_xmind16 import Workbook

    w = Workbook.load(str(xmind_path))
    pairs: list[tuple[str, str]] = []

    def walk(parent_title: str | None, topic: Any) -> None:
        t = getattr(topic, "title", None)
        if t:
            current = str(t).strip()
            if parent_title is not None:
                pairs.append((parent_title, current))
            for st in getattr(topic, "subtopics", []) or []:
                walk(current, st)

    for sheet in (w.get_sheet(i) for i in range(w.sheet_count)):
        root = sheet.root_topic
        if root:
            walk(None, root)
    return pairs
