from __future__ import annotations

import argparse
import json
import sys

from .config import settings
from .crawler import Crawler
from .db import Database
from .instagram import InstagramIngestor


def main() -> None:
    parser = argparse.ArgumentParser(prog="tritontrail")
    sub = parser.add_subparsers(dest="command", required=True)
    crawl = sub.add_parser("crawl", help="Crawl the UCSD directory")
    crawl.add_argument("--limit", type=int)
    crawl.add_argument("--enrich", action="store_true")
    crawl.add_argument("--pilot", action="store_true", help="Use the curated 10-club pilot cohort")
    crawl.add_argument("--fast", action="store_true", help="Skip linked-club-website discovery during this pass")
    enrich = sub.add_parser("enrich", help="Enrich pending organizations with Gemma")
    enrich.add_argument("--limit", type=int, default=50)
    enrich.add_argument("--pilot", action="store_true", help="Use the curated 10-club pilot cohort")
    enrich.add_argument("--fast", action="store_true", help="Skip linked-club-website discovery during this pass")
    socials = sub.add_parser("socials", help="Discover social links from official club websites")
    socials.add_argument("--limit", type=int, default=100)
    socials.add_argument("--pilot", action="store_true", help="Use the curated 10-club pilot cohort")
    socials.add_argument("--offline", action="store_true", help="Re-process saved official source pages without network requests")
    socials.add_argument("--search", action="store_true", help="Ask Google-grounded Gemma for candidates where no Instagram link was found")
    search = sub.add_parser("search", help="Search indexed organizations")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--tag")
    sub.add_parser("stats")
    instagram = sub.add_parser("instagram", help="Fetch Instagram posts through Bright Data and extract events with Gemma")
    instagram.add_argument("--accounts", type=int)
    instagram.add_argument("--posts-per-account", type=int)
    instagram.add_argument("--fetch-only", action="store_true")
    process = sub.add_parser("process-instagram", help="Process saved Instagram posts with Gemma")
    process.add_argument("--limit", type=int, default=50)
    issues = sub.add_parser("instagram-issues", help="List Instagram profiles that need attention")
    issues.add_argument("--all", action="store_true", help="Include issues that later recovered")
    issues.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    db = Database(settings.db_path)
    def progress(current: int, total: int, label: str) -> None:
        percent = int((current / total) * 100) if total else 100
        print(f"[{current}/{total} {percent:3d}%] {label}", file=sys.stderr, flush=True)

    if args.command == "crawl":
        result = Crawler(settings, db).crawl(args.limit, args.enrich, progress, args.pilot, args.fast)
    elif args.command == "enrich":
        result = Crawler(settings, db).enrich_pending(args.limit, progress, args.pilot, args.fast)
    elif args.command == "socials":
        result = Crawler(settings, db).discover_socials(args.limit, progress, args.pilot, offline=args.offline, search=args.search)
    elif args.command == "search":
        result = db.search(args.query, args.tag)
    elif args.command == "instagram":
        ingestor = InstagramIngestor(settings, db)
        result = ingestor.fetch_posts(args.accounts, args.posts_per_account) if args.fetch_only else ingestor.sync(args.accounts, args.posts_per_account)
    elif args.command == "process-instagram":
        result = InstagramIngestor(settings, db).process_pending(args.limit)
    elif args.command == "instagram-issues":
        result = db.instagram_issues(args.all, args.limit)
    else:
        result = db.stats()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
