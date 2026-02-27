# remarkable2ocr

Turn reMarkable handwritten notes (or any note image) into an **editable layout**: scan notebooks or camera images → OCR with OpenAI SDK (OpenAI, DeepSeek, etc.) → interactive HTML with draggable blocks, connectors, and alignment guides.

**Install to run:** clone → `python -m venv .venv` → `pip install -r requirements.txt` → copy `.env.example` to `.env` and set `OCR_API_KEY` → `python main.py`.

---

## Background

- **Input:** Notes from a [reMarkable](https://remarkable.com/) tablet (xochitl data) or photos of handwritten pages (e.g. in `data/xochitl/camera/<project>/`).
- **Goal:** Preserve structure (lines, boxes, arrows, colors) and make it editable in the browser: move blocks, edit text, add/remove links, group with frames, copy text.
- **Flow:** Raw data → page images → OCR (text + position + links/shape/color) → cached JSON → multi-page `layout.html` with drag-and-drop and connectors.

---

## Architecture

The pipeline is split into three modules under `src/`, plus config:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  main.py                                                                │
│  (orchestrates: optional --pull → list/camera → render → OCR → layout)  │
└─────────────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────────────┐
│  src/remarkable │  │   src/ocr       │  │  src/layout                  │
│  ─────────────  │  │  ─────────────  │  │  ──────────────────────────  │
│  • list_notebook│  │  • ocr_image()  │  │  • render_ocr_to_html_multi  │
│  • render_*_png │  │    (OpenAI SDK, │  │    → layout.html (divs,      │
│  • pull_xochitl │  │     cache JSON) │  │      links, guides)          │
│                 │  │                 │  │  • write_ocr_preview_html    │
│  data/xochitl   │  │  page PNG →     │  │  • render_ocr_overlay        │
│  → pages/*.png  │  │  ocr/*.json     │  │  (+ chart schema / SVG       │
│                 │  │                 │  │   for semantic parsing)      │
│                 │  │                 │  │  • semantic_parse()          │
│                 │  │                 │  │    (OpenAI SDK)              │
└─────────────────┘  └─────────────────┘  └──────────────────────────────┘
         │                    │                    │
         └────────────────────┴────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │  src/config       │
                    │  .env, DATA_DIR,  │
                    │  OCR_API_KEY,     │
                    │  REMARKABLE_*     │
                    └───────────────────┘
```

| Module | Role | Input → Output |
|--------|------|----------------|
| **remarkable** | Device data and rendering | `data/xochitl` (or device via `--pull`) → `output/<name>/pages/*.png` |
| **ocr** | Handwriting recognition | Page image → LLM (OpenAI SDK) → `output/<name>/ocr/page_*.json` (text, y/x ratio, links, shape, color, confidence) |
| **layout** | Editable UI | OCR JSON (+ page images) → `layout.html`, `.debug/ocr_preview.html`, `ocr_overlay_*.png` |
| **config** | Environment | `.env` → `DATA_DIR`, `OCR_API_KEY`, `REMARKABLE_HOST`, etc. |

- **Notebook mode:** `list_notebooks()` → for each notebook, `render_notebook_pages()` → for each page, `ocr_image()` → `render_ocr_to_html_multi(all_ocr)`.
- **Camera mode:** One or more images in `data/xochitl/camera/<project>/` → same OCR + layout pipeline → `output/<project>/`.

---

## Quick start

```bash
git clone https://github.com/caucyj/remarkable2ocr.git && cd remarkable2ocr
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY=your_gemini_api_key
python main.py
```

## Run

From the project root:

```bash
python main.py
```

- **Default:** Uses local OCR cache under `output/<notebook>/ocr/page_*.json` when present; no API call for cached pages.
- **Force re-OCR:** `python main.py --no-cache`
- **Pull from reMarkable then process:** `python main.py --pull` (fails if device not connected)
- **Pull + no cache:** `python main.py --pull --no-cache`
- **Camera image(s):** Put image(s) in `data/xochitl/camera/<name>/` (e.g. `.jpg` or `.png`), then:
  ```bash
  python main.py --camera <name>
  ```
  Output goes to `output/<name>/`. Optional: `--camera <name> --no-cache`

## Environment

- Python 3.10+
- Create `.env` in project root (see `.env.example`):
  - `OCR_API_KEY` — required for OCR (supports `OPENAI_API_KEY`, `GOOGLE_API_KEY` as fallback)
  - `OCR_BASE_URL` — optional (e.g. for local models or other providers)
  - `OCR_MODEL_NAME` — optional (default `gpt-4o`)
  - `DATA_DIR` — xochitl data directory (default `data/xochitl`)
  - `REMARKABLE_HOST` — device host for `--pull` (default `10.11.99.1`)
  - `REMARKABLE_USER` — SSH user (default `root`)
  - `REMARKABLE_XOCHITL_PATH` — path on device (default `/home/root/.local/share/remarkable/xochitl`)
- Install: `pip install -r requirements.txt`

For `--pull`, ensure the reMarkable is on the same network (e.g. USB or Wi‑Fi) and SSH works (`ssh root@10.11.99.1`). Install `rsync` if missing.

## Output

- `output/<notebook_or_project>/pages/` — page PNGs
- `output/<notebook_or_project>/ocr/` — OCR JSON cache (`page_0.json`, …)
- `output/<notebook_or_project>/layout.html` — multi-page layout (draggable divs, connectors, alignment guides)
- `output/<notebook_or_project>/.debug/` — `ocr_preview.html`, `ocr_overlay_*.png`

## Testing

Automated tests run on every push and pull request via [GitHub Actions](.github/workflows/test.yml). To run locally:

```bash
pip install -r requirements-dev.txt
python3 -m pytest --cov=src --cov=main --cov-report=html tests/ -v
```

Testing coverage report is generated in `htmlcov/`.

## See also

- [awesome-reMarkable](https://github.com/reHackable/awesome-reMarkable) — A curated list of projects related to the reMarkable tablet (APIs, cloud tools, GUI clients, templates, and more). Useful for discovering other tools and integrations.
