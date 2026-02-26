# Handwritten notes to layout

Scan reMarkable `data/xochitl` notebooks → render pages → OCR (Gemini) → layout HTML. **Install to run:** clone → `python -m venv .venv` → `pip install -r requirements.txt` → copy `.env.example` to `.env` and set `GOOGLE_API_KEY` → `python main.py`.

## Quick start

```bash
git clone <repo> && cd awesome-reMarkable
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

- **Default:** Uses local OCR cache under `output/<notebook>/ocr/page_*.json` when present; no Gemini API call for cached pages.
- **Force re-OCR:** `python main.py --no-cache`
- **Pull from reMarkable then process:** `python main.py --pull` (fails if device not connected)
- **Pull + no cache:** `python main.py --pull --no-cache`
- **Camera image:** Put an image in `data/xochitl/camera/<name>/` (e.g. one `.jpg` or `.png`), then:
  ```bash
  python main.py --camera <name>
  ```
  Output goes to `output/<name>/`. Optional: `--camera <name> --no-cache`

## Environment

- Python 3.10+
- Create `.env` in project root (see `.env.example`):
  - `GOOGLE_API_KEY` — required for Gemini OCR (optional if using cache only)
  - `DATA_DIR` — xochitl data directory (default `data/xochitl`)
  - `REMARKABLE_HOST` — device host for `--pull` (default `10.11.99.1`)
  - `REMARKABLE_USER` — SSH user (default `root`)
  - `REMARKABLE_XOCHITL_PATH` — path on device (default `/home/root/.local/share/remarkable/xochitl`)
- Install: `pip install -r requirements.txt`

For `--pull`, ensure the reMarkable is on the same network (e.g. USB or Wi‑Fi) and SSH works (`ssh root@10.11.99.1`). Install `rsync` if missing.

## Output

- `output/<notebook_or_project>/pages/` — page PNGs
- `output/<notebook_or_project>/ocr/` — OCR JSON cache (`page_0.json`, …)
- `output/<notebook_or_project>/layout.html` — multi-page layout (draggable divs, links, alignment guides)
- `output/<notebook_or_project>/.debug/` — `ocr_preview.html`, `ocr_overlay_*.png`
