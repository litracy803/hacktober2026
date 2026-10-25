# TritonRadar - UC San Diego events

TritonRadar turns UC San Diego student-organization information and public Instagram announcements into a searchable, evidence-backed campus event directory. The project includes a browser calendar prototype and a Python ingestion service that can collect organization posts through Bright Data and extract events with a vision-capable Gemma model.

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
tritonradar crawl --limit 25 --enrich
tritonradar instagram --accounts 10
uvicorn tritontrail.api:app --reload
```

Open <http://127.0.0.1:8000>. The default database is `data/tritonradar.db`.

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

If a profile fetch fails, TritonRadar records it in `instagram_account_issues` and continues to the next profile. Explicit “profile not found” errors are skipped in future syncs; ambiguous or temporary failures remain retryable. Review issues with `tritonradar instagram-issues`. To retry a skipped profile, call `POST /api/instagram/issues/{id}/retry`; it will be attempted during the next sync.

## Commands

```bash
tritonradar crawl --limit 50 --enrich
tritonradar enrich --limit 50
tritontrail socials --limit 100
tritonradar instagram --accounts 10 --posts-per-account 10
tritonradar instagram --fetch-only
tritonradar process-instagram --limit 50
tritonradar instagram-issues
tritonradar search "computer science career"
tritonradar stats
```
The `socials` command revisits each organization’s UCSD profile, follows up to three explicitly linked official websites, and extracts public Instagram, Facebook, TikTok, YouTube, LinkedIn, Discord, and Linktree URLs. It never logs into or crawls those social platforms. The API exposes `GET /api/organizations`, `GET /api/organizations/{id}`, `GET /api/stats`, and `POST /api/crawl`. The included UI provides search, source links, feature confidence, social-link verification state, and evidence snippets.

The default view shows three consecutive days. Use the arrows to move by three days and **Today** to jump to the current date. Event cards show start and end times and include an **Add to calendar** `.ics` download; the event description in the file contains the event tags, organization, location, and Instagram permalink when available. Filter groups now include event formats, practical/social interests, major and interests, and location in that order.
The API exposes `GET /api/organizations`, `GET /api/organizations/{id}`, `GET /api/events?tag=career`, `GET /api/instagram/issues`, `POST /api/instagram/issues/{id}/retry`, `GET /api/stats`, `POST /api/crawl`, and `POST /api/instagram/sync`. The service UI includes organization search and Instagram-derived events with tag filters and source-post links.

## Event extraction and review

Gemma extracts event title, dates, location, description, tags, confidence, and evidence from the caption and image. Missing or uncertain details remain unknown. Audience or demographic details are used only when the organization explicitly states them; they are never inferred from people shown in an image or from names. Review extracted details against the original post before treating them as confirmed calendar information.


## Add-to-calendar options

Event cards have an app-owned calendar menu with Google Calendar, Outlook, and downloadable `.ics` options. Tags, organization, location, and the Instagram permalink (when available) are included in the event details. The calendar menu works without a third-party script.

## Three-day calendar and busy times

The calendar now displays three consecutive days at once, with previous/next controls moving by three days. In the sidebar, **Busy times** lets students add recurring weekday intervals (such as Tuesday 5:00–8:00 PM); events that overlap any saved interval are filtered out. Busy intervals are saved in the browser's local storage on that device. The calendar cards use a full-width Add to calendar menu.

