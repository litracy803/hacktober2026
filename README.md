# TritonRadar - UC San Diego events

TritonRadar turns UC San Diego student-organization information and public Instagram announcements into a searchable, evidence-backed campus event directory. The project includes a browser calendar prototype and a Python ingestion service that can collect organization posts through Bright Data and extract events with a vision-capable Gemma model.

## Run the connected app

Run FastAPI to serve the TritonRadar frontend and connect it to the event API. If there are no processed event records yet, the frontend shows illustrative sample cards. Opening `index.html` directly with `file://` only runs the demo; use the server URL for backend data.

The default view shows three consecutive days. Use the arrows to move by three days and **Today** to jump to the current date. Event cards include Google Calendar, Outlook, and `.ics` options. Tags, organization, location, and the Instagram permalink (when available) are included in event details. Busy-time blocks remain in browser storage because this prototype has no user accounts.

Each ingested event should populate `imageUrl` from the Instagram post image and `sourceUrl` with that post's permalink. Sample events leave those fields empty, so the UI shows a preview placeholder and “Post link pending.”

## Run the ingestion service

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
tritonradar crawl --limit 25 --enrich
tritonradar instagram --accounts 10
tritonradar crawl --pilot
tritonradar enrich --pilot
tritonradar socials --pilot
uvicorn tritontrail.api:app --reload
```

Refresh the browser page after the sync finishes. The default database is `data/tritonradar.db`.

## Instagram and Gemma setup

TritonRadar sends both organization text and post images to the configured Gemma model through an OpenAI-compatible endpoint. For a local Ollama server, configure:

```dotenv
GEMMA_BASE_URL=http://127.0.0.1:11434/v1
GEMMA_API_KEY=ollama
GEMMA_MODEL=gemma4:e4b
BRIGHTDATA_API_KEY=your-brightdata-key
```

Use a vision-capable Gemma model so event extraction can inspect flyer images. If `GEMMA_BASE_URL` is not configured, directory crawling still works and organization enrichment uses the keyword fallback; Instagram event extraction remains pending until Gemma is configured.
The ingestion flow reads Instagram handles already stored in the database, asks Bright Data's Instagram Posts Discover by URL dataset for recent posts, then sends each post's caption and image to Gemma. Bright Data and Gemma credentials stay server-side in environment variables; never put them in browser JavaScript. Image retention and API use should follow the relevant provider terms.

If a profile fetch fails, TritonRadar records it in `instagram_account_issues` and continues to the next profile. Explicit “profile not found” errors are skipped in future syncs; ambiguous or temporary failures remain retryable. Review issues with `tritonradar instagram-issues`. To retry a skipped profile, call `POST /api/instagram/issues/{id}/retry`; it will be attempted during the next sync.

The `--pilot` flag selects a stable 10-club cohort covering data science, computing, CASA/cultural, social, performance, service, identity/cultural, health-professional, sport, and product-management organizations. It is intended for repeatable end-to-end testing instead of relying on directory order.

## Commands

```bash
tritonradar crawl --limit 50 --enrich
tritonradar enrich --limit 50
tritonradar socials --limit 100
tritonradar instagram --accounts 10 --posts-per-account 10
tritonradar instagram --pilot --posts-per-account 5
tritonradar instagram --fetch-only
tritonradar process-instagram --pilot --limit 50
tritonradar instagram-issues
tritonradar search "computer science career"
tritonradar stats
```
The `socials` command revisits each organization’s UCSD profile, follows up to three explicitly linked official websites, and extracts public Instagram, Facebook, TikTok, YouTube, LinkedIn, Discord, and Linktree URLs. It never logs into or crawls those social platforms. The API exposes `GET /api/organizations`, `GET /api/organizations/{id}`, `GET /api/stats`, and `POST /api/crawl`. The included UI provides search, source links, feature confidence, social-link verification state, and evidence snippets.

The default view shows three consecutive days. Use the arrows to move by three days and **Today** to jump to the current date. Event cards show start and end times and include an **Add to calendar** `.ics` download; the event description in the file contains the event tags, organization, location, and Instagram permalink when available. Filter groups now include event formats, practical/social interests, major and interests, and location in that order.
The API exposes `GET /api/organizations`, `GET /api/organizations/{id}`, `GET /api/events?tag=career`, `GET /api/instagram/issues`, `POST /api/instagram/issues/{id}/retry`, `GET /api/stats`, `POST /api/crawl`, and `POST /api/instagram/sync`. Add `pilot=true` to crawl and Instagram sync requests to restrict work to the curated 10-club cohort. The CLI's `--pilot` flag applies the same cohort to crawling, social discovery, Instagram post retrieval, and Gemma extraction. The service UI includes organization search and Instagram-derived events with tag filters and source-post links.

## Event extraction and review

Gemma extracts event title, dates, location, description, tags, confidence, and evidence from the caption and image. Missing or uncertain details remain unknown. Audience or demographic details are used only when the organization explicitly states them; they are never inferred from people shown in an image or from names. Review extracted details against the original post before treating them as confirmed calendar information.


## Add-to-calendar options

Event cards have an app-owned calendar menu with Google Calendar, Outlook, and downloadable `.ics` options. Tags, organization, location, and the Instagram permalink (when available) are included in the event details. The calendar menu works without a third-party script.

## Three-day calendar and busy times

The calendar now displays three consecutive days at once, with previous/next controls moving by three days. In the sidebar, **Busy times** lets students add recurring weekday intervals (such as Tuesday 5:00–8:00 PM); events that overlap any saved interval are filtered out. Busy intervals are saved in the browser's local storage on that device. The calendar cards use a full-width Add to calendar menu.





