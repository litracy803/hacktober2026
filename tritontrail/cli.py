from __future__ import annotations

import argparse
import json

from .config import settings
from .crawler import Crawler
from .db import Database
from .instagram import InstagramIngestor


def main() -> None:
    parser = argparse.ArgumentParser(prog="tritonradar")
    sub = parser.add_subparsers(dest="command", required=True)
    crawl = sub.add_parser("crawl", help="Crawl the UCSD directory")
    crawl.add_argument("--limit", type=int)
    crawl.add_argument("--enrich", action="store_true")
    enrich = sub.add_parser("enrich", help="Enrich pending organizations with Gemma")
    enrich.add_argument("--limit", type=int, default=50)
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
    args = parser.parse_args()
    db = Database(settings.db_path)
    if args.command == "crawl":
        result = Crawler(settings, db).crawl(args.limit, args.enrich)
    elif args.command == "enrich":
        result = Crawler(settings, db).enrich_pending(args.limit)
    elif args.command == "search":
        result = db.search(args.query, args.tag)
    elif args.command == "instagram":
        ingestor = InstagramIngestor(settings, db)
        result = ingestor.fetch_posts(args.accounts, args.posts_per_account) if args.fetch_only else ingestor.sync(args.accounts, args.posts_per_account)
    elif args.command == "process-instagram":
        result = InstagramIngestor(settings, db).process_pending(args.limit)
    else:
        result = db.stats()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
