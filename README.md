# TritonTrail

TritonTrail turns UC San Diego student-organization information and public Instagram announcements into a searchable, evidence-backed campus event directory. It stores organizations and their official social links, fetches bounded post batches through Bright Data, passes post captions and images to a multimodal Gemma model, and makes extracted events available for tag filtering.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
tritontrail crawl --limit 25 --enrich
tritontrail instagram --accounts 10
uvicorn tritontrail.api:app --reload
```

Open <http://127.0.0.1:8000>. The default database is `data/tritontrail.db`.

## Gemma

Gemma is called through an OpenAI-compatible chat-completions endpoint. Use a vision-capable Gemma 4 model (or a compatible vision-capable Gemma 3 model); a text-only model cannot inspect flyers. Configure a local Ollama server or another compatible gateway:

```dotenv
GEMMA_BASE_URL=http://127.0.0.1:11434/v1
GEMMA_API_KEY=ollama
GEMMA_MODEL=gemma4:e4b
BRIGHTDATA_API_KEY=your-brightdata-key
```

Bright Data's Instagram Posts Discover by URL dataset returns each account's recent post caption, timestamp, URL, and image URL. TritonTrail downloads supported Instagram CDN images (up to `IMAGE_MAX_BYTES`) and sends image bytes plus the caption to Gemma. The Bright Data/Gemma APIs are opt-in and require your own credentials. If either is not configured, directory crawling remains available.

## Commands

```bash
tritontrail crawl --limit 50 --enrich
tritontrail enrich --limit 50
tritontrail instagram --accounts 10 --posts-per-account 10
tritontrail instagram --fetch-only
tritontrail process-instagram --limit 50
tritontrail search "computer science career"
tritontrail stats
```

The API exposes `GET /api/organizations`, `GET /api/organizations/{id}`, `GET /api/events?tag=career`, `GET /api/stats`, `POST /api/crawl`, and `POST /api/instagram/sync`. The included UI provides organization search and an Instagram-derived event view with tag filters and source-post links.

Directory crawling uses a descriptive user agent, caching through content hashes, a low request rate, and bounded limits. Instagram post collection is delegated to Bright Data and uses only handles already present in the database. Post records retain the source URL and extraction status. The event extractor returns unknown/null values when dates, cost, location, or audience are unsupported; demographic traits are never inferred. Review extracted events before relying on them as a complete calendar.

Each record preserves the distinction between deterministic source facts, Gemma classifications, supporting evidence, and unknown fields. SQLite FTS5 powers local search; the repository layer is deliberately small so it can move to PostgreSQL later.
