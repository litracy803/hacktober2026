from __future__ import annotations

import argparse
import json

from .config import settings
from .crawler import Crawler
from .db import Database


def main() -> None:
    parser = argparse.ArgumentParser(prog="tritontrail")
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
    args = parser.parse_args()
    db = Database(settings.db_path)
    if args.command == "crawl":
        result = Crawler(settings, db).crawl(args.limit, args.enrich)
    elif args.command == "enrich":
        result = Crawler(settings, db).enrich_pending(args.limit)
    elif args.command == "search":
        result = db.search(args.query, args.tag)
    else:
        result = db.stats()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
