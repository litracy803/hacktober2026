SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS organizations (
  id TEXT PRIMARY KEY, official_name TEXT NOT NULL, directory_url TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '', category TEXT, status TEXT NOT NULL DEFAULT 'active',
  enrichment_status TEXT NOT NULL DEFAULT 'pending_enrichment', normalized_name TEXT,
  summary TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  url TEXT NOT NULL, source_type TEXT NOT NULL, content_hash TEXT NOT NULL, raw_text TEXT NOT NULL DEFAULT '', fetched_at TEXT NOT NULL,
  UNIQUE(organization_id, url, content_hash)
);
CREATE TABLE IF NOT EXISTS aliases (organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, alias TEXT NOT NULL, PRIMARY KEY(organization_id, alias));
CREATE TABLE IF NOT EXISTS features (
  id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  tag TEXT NOT NULL, confidence TEXT NOT NULL DEFAULT 'unknown', evidence TEXT NOT NULL DEFAULT '', source_url TEXT,
  UNIQUE(organization_id, tag)
);
CREATE TABLE IF NOT EXISTS social_accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  platform TEXT NOT NULL, handle TEXT, url TEXT NOT NULL, verification TEXT NOT NULL DEFAULT 'official_link', evidence TEXT NOT NULL DEFAULT '', source_url TEXT,
  UNIQUE(organization_id, url)
);
CREATE TABLE IF NOT EXISTS evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  field_name TEXT NOT NULL, quote TEXT NOT NULL, source_url TEXT, confidence TEXT NOT NULL DEFAULT 'unknown'
);
CREATE TABLE IF NOT EXISTS enrichment_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  model TEXT NOT NULL, prompt_version TEXT NOT NULL, input_hash TEXT NOT NULL, raw_response TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS organizations_fts USING fts5(
  organization_id UNINDEXED, official_name, normalized_name, description, summary, aliases, features
);
"""
