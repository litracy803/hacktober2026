# TritonTrail

TritonTrail turns the public UC San Diego student-organization directory into a searchable, evidence-backed organization index. It crawls the official directory, extracts source facts and outbound links, optionally enriches each organization with Gemma, and stores the result in a queryable SQLite database.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
tritontrail crawl --limit 25 --enrich
uvicorn tritontrail.api:app --reload
```

Open <http://127.0.0.1:8000>. The default database is `data/tritontrail.db`.

## Gemma

Gemma is called through an OpenAI-compatible chat-completions endpoint. This works with a local Ollama server or another compatible gateway:

```dotenv
GEMMA_BASE_URL=http://127.0.0.1:11434/v1
GEMMA_API_KEY=ollama
GEMMA_MODEL=gemma3:4b
```

If the endpoint is not configured, crawling still works and stores deterministic data plus a keyword-based fallback marked `pending_enrichment`.

## Commands

```bash
tritontrail crawl --limit 50 --enrich
tritontrail enrich --limit 50
tritontrail search "computer science career"
tritontrail stats
```

The API exposes `GET /api/organizations`, `GET /api/organizations/{id}`, `GET /api/stats`, and `POST /api/crawl`. The included UI provides search, source links, feature confidence, social-link verification state, and evidence snippets.

The crawler uses a descriptive user agent, caching through content hashes, a low request rate, retries at the HTTP client layer, and a bounded crawl limit. It does not log into or scrape social platforms. It stores only social URLs explicitly linked from the UCSD directory or a club website; future externally discovered accounts should be represented as unverified candidates.

Each record preserves the distinction between deterministic source facts, Gemma classifications, supporting evidence, and unknown fields. SQLite FTS5 powers local search; the repository layer is deliberately small so it can move to PostgreSQL later.
