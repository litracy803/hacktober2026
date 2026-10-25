# Organa — UC San Diego events

A Hacktoberfest prototype for turning public UCSD student organization announcements into searchable, filterable campus events.

## Run it

Open `index.html` in a browser. The current demo uses six illustrative sample events so the filtering UI can be reviewed without API credentials.

## Proposed ingestion pipeline

1. Import the public organization directory at [studentorg.ucsd.edu](https://studentorg.ucsd.edu/), then extract each org's listed social handles. Keep the source URL and last-checked timestamp for every record.
2. Submit discovered public Instagram profile/post URLs to Bright Data's Instagram Posts Discover API from a server-side job. Keep Bright Data credentials in environment secrets; never ship them to browser JavaScript.
3. Normalize post caption, image URL, permalink, timestamp, and organization identity. Send the caption plus image to Gemma 4 for structured event extraction: title, date/time, location, description, tags, confidence, and evidence snippets.
4. Validate dates, deduplicate by source post URL, and queue low-confidence or incomplete results for human review. Persist confirmed events for the frontend to query.
5. Filter by event type, free items/food, location, majors/interests, and explicit audience eligibility. Show the original post link and an AI-generated label so students can verify details.

## Important product choices

- Demographic filters must be based on eligibility or audience language explicitly published by the organization (for example, “open to first-generation students”), never inferred from people shown in images or from names.
- “Free” and other practical details should carry an evidence snippet and confidence; do not silently turn an uncertain model guess into a promise.
- Respect Instagram/Bright Data terms, UCSD site terms, rate limits, attribution, and image retention requirements. For the hackathon demo, prefer a small pilot set of orgs and cache results.
- Gemma 4 supports image and text inputs, making a multimodal extraction step feasible. Keep extraction constrained to a JSON schema and make the source post available for correction.

## Suggested event schema

```json
{
  "id": "stable-id",
  "organization": "Student organization name",
  "title": "Event title",
  "starts_at": "2026-10-27T16:00:00-07:00",
  "ends_at": null,
  "location": "Price Center",
  "description": "Short summary",
  "tags": ["Pre-professional", "Free", "Business"],
  "eligibility": [],
  "evidence": {"date": "caption phrase", "free": "free pizza"},
  "confidence": 0.91,
  "source_url": "https://www.instagram.com/p/...",
  "source_posted_at": "2026-10-20T19:10:00Z",
  "review_status": "needs_review"
}
```

## Next implementation slice

Add a server-side importer and database only after confirming the Bright Data dataset/API access mode, event volume, and whether org accounts are collected from linked directory records or provided by orgs. The client-only demo deliberately does not make external requests.
