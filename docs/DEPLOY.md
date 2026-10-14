# Deploying A2 (shared `demo-api` on Render, UI on Cloudflare Pages)

## 1. Mount the router in the shared demo-api

```python
import os
from fastapi import FastAPI

app = FastAPI()
if os.getenv("ENABLE_A2", "true") == "true":
    from extractor.api import router as a2_router   # lazy import keeps memory down when A2 is off
    app.include_router(a2_router, prefix="/a2")
```

* `POST /a2/extract` (multipart field `file`, PDF only) and `GET /a2/health`.
* When `GATEWAY_SECRET` is set the request must carry the same value in `X-Gateway-Secret` (the Pages Function adds it after the Turnstile check).
* Response (`Result`): `extraction` (all fields), `issues[]` (`code`, `severity`, `field`, `message`), `needs_review`, `pages`, `latency_ms`, `attempts`, `error`.
* Status codes: 403 wrong secret, 413 file over the size cap, 415 not a PDF, 502 LLM call failed. Scanned PDFs return 200 with `needs_review=true` and an issue `scanned_pdf`.

## 2. Settings

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | from llm-client | provider switch |
| `MAX_UPLOAD_MB` | 3 | upload cap |
| `MAX_PAGES` | 5 | pages read (a warning is added when truncated) |
| `GATEWAY_SECRET` | empty = off | shared secret with the edge function |
| `DEFAULT_CURRENCY` | empty | used only if a document prints no currency at all; empty means such documents go to review |
| `ENABLE_A2` | true | demo-api module switch |

Provider keys come from the host's environment (Render settings), never from the repo.

## 3. Memory (Render free = 512 MB)

Measured on Linux with the same code path as the API (FastAPI + pdfplumber + pdfium, 24 uploads of documents up to 4 pages, fake LLM): about 76 MB peak.
Measured in the Docker container with the real LLM client (openai SDK via llm-client): 40 MiB at start, 72.5 MiB after one real /extract call (docker stats, 2026-10-13).
Not measured: concurrent requests and 5-page / 3 MB uploads.

```powershell
docker stats --no-stream
```

No torch, no OCR engine, no local model.

## 4. What the demo-api must provide (not part of A2)

* per-IP rate limit and a daily budget kill-switch (counters in Neon);
* **fallback provider on 429.** The Groq free tier answered `429` on 35 of 36 documents during a steady evaluation run; a demo that depends on one free provider will fail;
* one `/health` per module; a visible "waking up" message (Render sleeps after 15 minutes idle, about 1 minute to wake).

## 5. The UI (own Cloudflare Pages project)

* **Sample files only.** Show the notice: "This demo uses free LLM tiers that may log inputs. Use the sample files or fictional documents."
* `python scripts/export_samples.py --out web/public/samples` copies 8 curated PDFs and a `samples.json` (clean invoice, wrong printed total, prompt injection, French format, a scan, repair shop, pharmacy, insurance).
* Show: the extracted fields next to the PDF, the `issues` list (errors red, warnings grey), a clear **needs review** badge, `latency_ms`, and one line explaining the flag.
* Fallback on every card: a 90-second video.
Verified 2026-10-13: image builds in about 50 s; /health and /extract work with a real LLM.

## 6. Container (build from the ai-studio root; untested until you run it)

```powershell
docker build -f projects/a2-extraction-api/Dockerfile -t a2-extraction .
docker run --rm -p 8002:8002 --env-file .env a2-extraction
curl.exe http://127.0.0.1:8002/health
curl.exe -F "file=@projects/a2-extraction-api/data/world5/invoices/world_00.pdf" http://127.0.0.1:8002/extract
```
