from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .schema import SCHEMA


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connection() as conn:
            conn.executescript(SCHEMA)

    def upsert_organization(self, record: dict[str, Any]) -> None:
        stamp = now()
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO organizations
                (id, official_name, directory_url, description, category, updated_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET official_name=excluded.official_name,
                directory_url=excluded.directory_url, description=excluded.description,
                category=excluded.category, updated_at=excluded.updated_at""",
                (record["id"], record["official_name"], record["directory_url"],
                 record.get("description", ""), record.get("category"), stamp, stamp),
            )

    def save_source(self, organization_id: str, source: dict[str, Any]) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sources (organization_id,url,source_type,content_hash,raw_text,fetched_at) VALUES (?,?,?,?,?,?)",
                (organization_id, source["url"], source["source_type"], source["content_hash"], source.get("raw_text", ""), now()),
            )

    def save_social_links(self, organization_id: str, links: list[dict[str, str]]) -> None:
        with self.connection() as conn:
            for link in links:
                conn.execute(
                    "INSERT OR IGNORE INTO social_accounts (organization_id,platform,handle,url,verification,evidence,source_url) VALUES (?,?,?,?,?,?,?)",
                    (organization_id, link["platform"], link.get("handle"), link["url"], link.get("verification", "official_link"), link.get("evidence", ""), link.get("source_url")),
                )

    def clear_social_links(self, organization_id: str, verification: str) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM social_accounts WHERE organization_id=? AND verification=?", (organization_id, verification))

    def save_enrichment(self, organization_id: str, payload: dict[str, Any], raw_response: str, model: str, input_hash: str, status: str, error: str | None = None) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM aliases WHERE organization_id=?", (organization_id,))
            conn.execute("DELETE FROM features WHERE organization_id=?", (organization_id,))
            conn.execute("DELETE FROM evidence WHERE organization_id=?", (organization_id,))
            for alias in payload.get("aliases", []):
                if alias:
                    conn.execute("INSERT OR IGNORE INTO aliases VALUES (?,?)", (organization_id, str(alias)))
            for feature in payload.get("features", []):
                if isinstance(feature, str):
                    feature = {"tag": feature}
                if feature.get("tag"):
                    conn.execute("INSERT OR IGNORE INTO features (organization_id,tag,confidence,evidence,source_url) VALUES (?,?,?,?,?)", (organization_id, feature["tag"], feature.get("confidence", "unknown"), feature.get("evidence", ""), feature.get("source_url")))
            for item in payload.get("evidence", []):
                if item.get("quote"):
                    conn.execute("INSERT INTO evidence (organization_id,field_name,quote,source_url,confidence) VALUES (?,?,?,?,?)", (organization_id, item.get("field", "general"), item["quote"], item.get("source_url"), item.get("confidence", "unknown")))
            conn.execute("UPDATE organizations SET normalized_name=?, summary=?, enrichment_status=?, updated_at=? WHERE id=?", (payload.get("normalized_name"), payload.get("summary"), status, now(), organization_id))
            conn.execute("INSERT INTO enrichment_runs (organization_id,model,prompt_version,input_hash,raw_response,status,error,created_at) VALUES (?,?,?,?,?,?,?,?)", (organization_id, model, "v1", input_hash, raw_response, status, error, now()))
            self._refresh_fts(conn, organization_id)

    def _refresh_fts(self, conn: sqlite3.Connection, organization_id: str) -> None:
        row = conn.execute("SELECT official_name,normalized_name,description,summary FROM organizations WHERE id=?", (organization_id,)).fetchone()
        if not row:
            return
        aliases = " ".join(r[0] for r in conn.execute("SELECT alias FROM aliases WHERE organization_id=?", (organization_id,)))
        features = " ".join(r[0] for r in conn.execute("SELECT tag FROM features WHERE organization_id=?", (organization_id,)))
        conn.execute("DELETE FROM organizations_fts WHERE organization_id=?", (organization_id,))
        conn.execute("INSERT INTO organizations_fts VALUES (?,?,?,?,?,?,?)", (organization_id, row["official_name"], row["normalized_name"] or "", row["description"], row["summary"] or "", aliases, features))

    def rebuild_search_index(self) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM organizations_fts")
            for row in conn.execute("SELECT id FROM organizations"):
                self._refresh_fts(conn, row[0])

    def search(self, query: str = "", tag: str | None = None, limit: int = 25, offset: int = 0) -> list[dict[str, Any]]:
        with self.connection() as conn:
            params: list[Any] = []
            if query.strip():
                sql = "SELECT o.*, bm25(organizations_fts) AS rank FROM organizations_fts JOIN organizations o ON o.id=organizations_fts.organization_id WHERE organizations_fts MATCH ?"
                params.append(query.replace('"', ''))
            else:
                sql = "SELECT o.*, 0 AS rank FROM organizations o"
            if tag:
                sql += " JOIN features ft ON ft.organization_id=o.id AND ft.tag=?"
                params.append(tag)
            sql += " ORDER BY rank, o.official_name LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = conn.execute(sql, params).fetchall()
            return [self._summary(conn, dict(row)) for row in rows]

    def get(self, organization_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM organizations WHERE id=?", (organization_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            result["aliases"] = [r[0] for r in conn.execute("SELECT alias FROM aliases WHERE organization_id=? ORDER BY alias", (organization_id,))]
            result["features"] = [dict(r) for r in conn.execute("SELECT tag,confidence,evidence,source_url FROM features WHERE organization_id=? ORDER BY tag", (organization_id,))]
            result["social_accounts"] = [dict(r) for r in conn.execute("SELECT platform,handle,url,verification,evidence,source_url FROM social_accounts WHERE organization_id=? ORDER BY platform", (organization_id,))]
            result["evidence"] = [dict(r) for r in conn.execute("SELECT field_name,quote,source_url,confidence FROM evidence WHERE organization_id=? ORDER BY id", (organization_id,))]
            return result

    @staticmethod
    def _summary(conn: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
        row["features"] = [r[0] for r in conn.execute("SELECT tag FROM features WHERE organization_id=? ORDER BY tag", (row["id"],))]
        row["social_count"] = conn.execute("SELECT COUNT(*) FROM social_accounts WHERE organization_id=?", (row["id"],)).fetchone()[0]
        return row

    def pending_enrichment(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM organizations WHERE enrichment_status='pending_enrichment' ORDER BY updated_at LIMIT ?", (limit,))]

    def organizations(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM organizations ORDER BY official_name LIMIT ?", (limit,))]
    def instagram_accounts(self, limit: int | None = None) -> list[dict[str, Any]]:
        with self.connection() as conn:
            sql = """SELECT sa.organization_id, o.official_name, sa.handle, sa.url
                     FROM social_accounts sa JOIN organizations o ON o.id=sa.organization_id
                     WHERE sa.platform='instagram' AND sa.handle IS NOT NULL AND sa.handle!=''
                     AND NOT EXISTS (SELECT 1 FROM instagram_account_issues i
                                     WHERE i.organization_id=sa.organization_id AND i.account_url=sa.url
                                     AND i.status='profile_missing')
                     ORDER BY o.official_name"""
            params: tuple[Any, ...] = ()
            if limit is not None:
                sql += " LIMIT ?"
                params = (limit,)
            return [dict(r) for r in conn.execute(sql, params)]

    def record_instagram_issue(self, organization_id: str, account_url: str, handle: str, issue_type: str, detail: str) -> None:
        stamp = now()
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO instagram_account_issues
                (organization_id,account_url,handle,issue_type,detail,status,attempts,first_seen,last_seen,recovered_at)
                VALUES (?,?,?,?,?,?,1,?,?,NULL)
                ON CONFLICT(organization_id,account_url) DO UPDATE SET
                handle=excluded.handle, issue_type=excluded.issue_type, detail=excluded.detail,
                status=excluded.status, attempts=instagram_account_issues.attempts+1,
                last_seen=excluded.last_seen, recovered_at=NULL""",
                (organization_id, account_url, handle, issue_type, detail[:2000],
                 "profile_missing" if issue_type == "profile_missing" else "retryable", stamp, stamp),
            )

    def resolve_instagram_issue(self, organization_id: str, account_url: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE instagram_account_issues SET status='recovered', recovered_at=? WHERE organization_id=? AND account_url=?",
                (now(), organization_id, account_url),
            )

    def instagram_issues(self, include_recovered: bool = False, limit: int = 200) -> list[dict[str, Any]]:
        with self.connection() as conn:
            where = "" if include_recovered else "WHERE i.status!='recovered'"
            return [dict(r) for r in conn.execute(
                f"""SELECT i.*, o.official_name FROM instagram_account_issues i
                    JOIN organizations o ON o.id=i.organization_id {where}
                    ORDER BY CASE i.status WHEN 'profile_missing' THEN 0 ELSE 1 END, i.last_seen DESC LIMIT ?""",
                (limit,),
            )]

    def retry_instagram_issue(self, issue_id: int) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                "UPDATE instagram_account_issues SET status='retryable', issue_type='manual_retry', recovered_at=NULL WHERE id=?",
                (issue_id,),
            )
            return cursor.rowcount > 0

    def save_social_post(self, organization_id: str, post: dict[str, Any]) -> None:
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO social_posts
                (id, organization_id, post_url, image_url, caption, posted_at, location,
                 event_data, extraction_status, extraction_error, fetched_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(organization_id, post_url) DO UPDATE SET
                event_data=CASE WHEN social_posts.caption!=excluded.caption OR COALESCE(social_posts.image_url,'')!=COALESCE(excluded.image_url,'') THEN excluded.event_data ELSE social_posts.event_data END,
                extraction_status=CASE WHEN social_posts.caption!=excluded.caption OR COALESCE(social_posts.image_url,'')!=COALESCE(excluded.image_url,'') THEN excluded.extraction_status ELSE social_posts.extraction_status END,
                extraction_error=CASE WHEN social_posts.caption!=excluded.caption OR COALESCE(social_posts.image_url,'')!=COALESCE(excluded.image_url,'') THEN excluded.extraction_error ELSE social_posts.extraction_error END,
                image_url=excluded.image_url, caption=excluded.caption, posted_at=excluded.posted_at,
                location=excluded.location,
                updated_at=excluded.updated_at""",
                (post["id"], organization_id, post["post_url"], post.get("image_url"),
                 post.get("caption", ""), post.get("posted_at"), post.get("location"),
                 json.dumps(post.get("event_data", {})), post.get("extraction_status", "pending"),
                 post.get("extraction_error"), now(), now()),
            )

    def events(self, tag: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """SELECT p.*, o.official_name FROM social_posts p
                   JOIN organizations o ON o.id=p.organization_id
                   WHERE p.extraction_status='processed' ORDER BY p.posted_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                try:
                    item["event"] = json.loads(item.pop("event_data"))
                except (TypeError, json.JSONDecodeError):
                    item["event"] = {}
                if not item["event"].get("is_event"):
                    continue
                if tag and tag.lower() not in [str(x).lower() for x in item["event"].get("tags", [])]:
                    continue
                result.append(item)
            return result

    def pending_posts(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT p.*, o.official_name FROM social_posts p JOIN organizations o ON o.id=p.organization_id WHERE p.extraction_status IN ('pending','failed') ORDER BY p.fetched_at LIMIT ?",
                (limit,),
            )]

    def stats(self) -> dict[str, int]:
        with self.connection() as conn:
            return {"organizations": conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0], "enriched": conn.execute("SELECT COUNT(*) FROM organizations WHERE enrichment_status='enriched'").fetchone()[0], "social_accounts": conn.execute("SELECT COUNT(*) FROM social_accounts").fetchone()[0], "review_needed": conn.execute("SELECT COUNT(*) FROM organizations WHERE enrichment_status='review_needed'").fetchone()[0], "instagram_posts": conn.execute("SELECT COUNT(*) FROM social_posts").fetchone()[0], "events": conn.execute("SELECT COUNT(*) FROM social_posts WHERE extraction_status='processed' AND json_extract(event_data, '$.is_event')=1").fetchone()[0], "instagram_account_issues": conn.execute("SELECT COUNT(*) FROM instagram_account_issues WHERE status!='recovered'").fetchone()[0]}
