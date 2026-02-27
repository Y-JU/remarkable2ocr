
import pytest
from pathlib import Path
from src.layout.render_chart import (
    render_to_html,
    render_to_svg,
    _render_outline_items,
    _render_container_html,
    _render_arrow_html,
    _render_list_html,
    _build_svg_content
)

class TestRenderChart:
    @pytest.fixture
    def sample_chart(self):
        return {
            "outline": [
                {"text": "Root", "level": 1, "children": [
                    {"text": "Child 1", "level": 2}
                ]}
            ],
            "containers": [
                {"type": "rectangle", "label": "Rect", "lines": ["Line 1"]},
                {"type": "ellipse", "label": "Oval", "lines": ["Line 2"]},
                {"type": "longbar", "label": "Bar", "lines": []}
            ],
            "lists": [
                {"type": "bullet", "items": [{"text": "Item 1"}]}
            ],
            "arrows": [
                {"from_id": "1", "to_id": "2", "style": "solid"}
            ]
        }

    def test_render_outline_items(self):
        items = [
            {"text": "A", "level": 1, "id": "1"},
            {"text": "B", "level": 2, "id": "2"}
        ]
        html = _render_outline_items(items)
        assert '<div class="outline-l1" data-id="1">A</div>' in html
        assert '<div class="outline-l2" data-id="2">B</div>' in html

    def test_render_container_html(self):
        # Rectangle
        c = {"type": "rectangle", "label": "Test", "lines": ["A", "B"]}
        html = _render_container_html(c)
        assert "container-rectangle" in html
        assert "Test" in html
        assert "A<br>B" in html

        # Ellipse
        c = {"type": "ellipse", "label": "Test"}
        html = _render_container_html(c)
        assert "container-ellipse" in html
        assert "<ellipse" in html

        # Longbar
        c = {"type": "longbar", "label": "Test"}
        html = _render_container_html(c)
        assert "container-longbar" in html

    def test_render_arrow_html(self):
        a = {"from_id": "1", "to_id": "2", "style": "dashed", "direction": "back"}
        html = _render_arrow_html(a, 0)
        assert 'stroke-dasharray: 6 4' in html
        assert 'marker-start="url(#arrow-back)"' in html

    def test_render_list_html(self):
        # Bullet
        l = {"type": "bullet", "items": [{"text": "A"}]}
        html = _render_list_html(l)
        # Note: default tag is "ul" but no class "chart-list " (with space?)
        # Implementation: tag="ul", css="", lis="<li>A</li>"
        # return f'<{tag} class="chart-list {css}">{lis}</{tag}>'
        # so class="chart-list "
        assert "<ul>" not in html # Because it has attributes
        assert "<ul" in html
        assert "chart-list" in html
        assert "<li>A</li>" in html
        
        # Ordered
        l = {"type": "ordered", "items": [{"text": "A"}]}
        html = _render_list_html(l)
        assert "<ol" in html

    def test_render_to_html(self, tmp_path, sample_chart):
        out = tmp_path / "chart.html"
        res = render_to_html(sample_chart, out)
        assert res.exists()
        content = res.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Root" in content
        assert "Rect" in content

    def test_render_to_svg(self, tmp_path, sample_chart):
        out = tmp_path / "chart.svg"
        res = render_to_svg(sample_chart, out)
        assert res.exists()
        content = res.read_text(encoding="utf-8")
        assert "<svg" in content
        assert "<rect" in content
        assert "<ellipse" in content
