# TritonTrail - UC San Diego events

TritonTrail turns UC San Diego student-organization information and public Instagram announcements into a searchable, evidence-backed campus event directory. The project includes a browser calendar prototype and a Python ingestion service that can collect organization posts through Bright Data and extract events with a vision-capable Gemma model.

## Run the frontend prototype

Open `index.html` in a browser. The current demo uses illustrative sample events so the calendar and filters can be reviewed without API credentials.

The default view is a Monday–Sunday calendar grid. Use the arrows to move between weeks and **Today** to jump to the current week. Event cards show start and end times and include an **Add to calendar** `.ics` download. The calendar filters event format, practical/social interests, majors/interests, and location. Multiple selected filters use broad matching; search text narrows those results. The filter sidebar can be collapsed and reopened with the Filters button.

Each ingested event should populate `imageUrl` from the Instagram post image and `sourceUrl` with that post's permalink. Sample events leave those fields empty, so the UI shows a preview placeholder and “Post link pending” rather than implying mock media or links are real.

## Run the ingestion service

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
tritontrail crawl --limit 25 --enrich
tritontrail instagram --accounts 10
tritontrail crawl --pilot
tritontrail enrich --pilot
tritontrail socials --pilot --offline
tritontrail crawl --pilot --fast
tritontrail enrich --pilot --fast
uvicorn tritontrail.api:app --reload
```

Open <http://127.0.0.1:8000>. The default database is `data/tritontrail.db`.

## Instagram and Gemma setup

Google AI Studio is the default provider. Install the SDK and put your AI Studio key in `.env`:

```bash
pip install google-genai
```

```dotenv
GEMMA_PROVIDER=google
GEMINI_API_KEY=your_google_ai_studio_key
GEMMA_MODEL=gemma-4-26b-a4b-it
```

The project also supports an OpenAI-compatible local endpoint such as Ollama:

```dotenv
GEMMA_PROVIDER=ollama
GEMMA_BASE_URL=http://127.0.0.1:11434/v1
GEMMA_API_KEY=ollama
GEMMA_MODEL=gemma4:e4b
BRIGHTDATA_API_KEY=your-brightdata-key
```

If the selected provider is not configured, crawling still works and stores deterministic data plus a keyword-based fallback marked `pending_enrichment`.
The ingestion flow reads Instagram handles already stored in the database, asks Bright Data's Instagram Posts Discover by URL dataset for recent posts, then sends each post's caption and image to Gemma. Bright Data and Gemma credentials stay server-side in environment variables; never put them in browser JavaScript. Image retention and API use should follow the relevant provider terms.

If a profile fetch fails, TritonTrail records it in `instagram_account_issues` and continues to the next profile. Explicit “profile not found” errors are skipped in future syncs; ambiguous or temporary failures remain retryable. Review issues with `tritontrail instagram-issues`. To retry a skipped profile, call `POST /api/instagram/issues/{id}/retry`; it will be attempted during the next sync.

The `--pilot` flag selects a stable 10-club cohort covering data science, computing, CASA/cultural, social, performance, service, identity/cultural, health-professional, sport, and product-management organizations. It is intended for repeatable end-to-end testing instead of relying on directory order.

`--fast` skips linked-club-website discovery during crawl/enrichment. Run `socials --pilot` afterward when you want the slower social-link pass.

`socials --offline` re-processes saved UCSD directory pages without network requests. It recognizes both `@handles` and bare values in the directory's Social Media field. Add `--search` to ask Google-grounded Gemma for candidates only for clubs that still have no Instagram result; these are labeled `search_grounded_candidate` for review.

## Commands

```bash
tritontrail crawl --limit 50 --enrich
tritontrail enrich --limit 50
tritontrail socials --limit 100
tritontrail instagram --accounts 10 --posts-per-account 10
tritontrail instagram --fetch-only
tritontrail process-instagram --limit 50
tritontrail instagram-issues
tritontrail search "computer science career"
tritontrail stats
```
The `socials` command revisits each organization’s UCSD profile, follows up to three explicitly linked official websites, and extracts public Instagram, Facebook, TikTok, YouTube, LinkedIn, Discord, and Linktree URLs. It never logs into or crawls those social platforms. The API exposes `GET /api/organizations`, `GET /api/organizations/{id}`, `GET /api/stats`, and `POST /api/crawl`. The included UI provides search, source links, feature confidence, social-link verification state, and evidence snippets.

The API exposes `GET /api/organizations`, `GET /api/organizations/{id}`, `GET /api/events?tag=career`, `GET /api/instagram/issues`, `POST /api/instagram/issues/{id}/retry`, `GET /api/stats`, `POST /api/crawl`, and `POST /api/instagram/sync`. The service UI includes organization search and Instagram-derived events with tag filters and source-post links.

## Event extraction and review

Gemma extracts event title, dates, location, description, tags, confidence, and evidence from the caption and image. Missing or uncertain details remain unknown. Audience or demographic details are used only when the organization explicitly states them; they are never inferred from people shown in an image or from names. Review extracted details against the original post before treating them as confirmed calendar information.

A suggested event record includes a stable ID, organization, title, start/end time, location, description, tags, eligibility, evidence, confidence, source permalink, source-post timestamp, and review status.
