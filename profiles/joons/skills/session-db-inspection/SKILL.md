---
name: session-db-inspection
description: "Inspect session SQLite stores for triage and audits."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Sessions, Cleanup, SQLite, Troubleshooting]
    category: productivity
    related_skills: [session-librarian]
---

# Session DB Inspection

Direct SQLite inspection of the per-profile session store, for cases the CLI and FTS can't reach: "which sessions are actually empty?", "does this tab correspond to a real row?", "what did the user actually type in this session?", cross-profile audits.

## When to Use

- User reports a tab/session that shouldn't be there (phantom tab, ghost session).
- You need the exact message count or raw user prompts for triage.
- You're auditing multiple profiles at once (CLI is single-profile).
- The `session_search` FTS results don't match what the UI shows (index lag, stale rows).
- Deciding whether a session is safe to delete vs. archive — you need the real message content, not the title.

## The Store

| Path | What it is |
|---|---|
| `~/.hermes/profiles/<profile>/state.db` | **The session store.** Tables: `sessions`, `messages`, `messages_fts` (FTS5), `messages_fts_trigram`, plus metadata tables. One file per profile. |
| `~/.hermes/profiles/<profile>/desktop/interrupted_turns.json` | Desktop UI lease state (in-flight turns). NOT the session store. |
| `~/.hermes/profiles/<profile>/runtime/active_sessions.json` | Live session leases (pid, surface, live_session_id). NOT the session store. |
| `~/.hermes/profiles/<profile>/projects.db` | Projects/repos. Separate concern. |

Each profile (`joons`, `coding`, `english`, …) has its own `state.db`. There is no shared cross-profile DB.

## Key Queries

```sql
-- Full inventory with real message counts
SELECT s.id, s.title, s.source, s.archived, s.pinned, s.hidden,
       (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS msgs
FROM sessions s
ORDER BY s.started_at DESC;

-- Find truly empty sessions (the phantom-tab case)
SELECT s.id, s.title, s.source, s.started_at
FROM sessions s
LEFT JOIN messages m ON m.session_id = s.id
GROUP BY s.id
HAVING COUNT(m.id) = 0;

-- Raw user prompts for triage (read-only)
SELECT id, substr(content, 1, 200) AS prompt
FROM messages
WHERE session_id = '<id>' AND role = 'user'
ORDER BY id;

-- Sessions that never ended (open-ended)
SELECT id, title, started_at, last_activity_at
FROM sessions
WHERE ended_at IS NULL
ORDER BY started_at DESC;

-- FTS vs. real message count (index drift check)
SELECT 'fts' AS src, COUNT(*) FROM messages_fts
UNION ALL
SELECT 'real', COUNT(*) FROM messages;
```

## Rules

- **Always `PRAGMA integrity_check;` before AND after any bulk write to `state.db`.** A single corrupt row surfaces in the UI as "session not found" — indistinguishable from a deleted session without the integrity check.
- **DB row count is ground truth for "is it empty" or "does it exist".** The desktop tab bar can retain UI state across a gateway reset even when the DB is clean. If the DB has no row, the fix is a UI restart, not a delete. Do NOT delete a non-existent row.
- **Never hand-edit `sessions.title`.** Use `hermes sessions rename <id> <title>`. The DB has `UNIQUE INDEX idx_sessions_title_unique ON sessions(title) WHERE title IS NOT NULL` — a direct UPDATE bypasses rename auditing and can collide silently.
- **Count from `messages`, not `messages_fts`.** The FTS table is a view; it can lag after a crash or mid-write. For decisions (delete? archive?), use the real table.
- **Cross-profile audit:** point `sqlite3` at each profile's `state.db` directly. `hermes sessions` commands only act on the current profile. Read-only queries are safe; writes require stopping the profile's gateway first.
- **Stale leases:** `runtime/active_sessions.json` can hold entries for pids that no longer exist (gateway was reset). These are not sessions — do not confuse a lease entry with a session row. A lease with a dead pid is a UI artifact, fixable by restarting the desktop app or the gateway.

## Pitfalls

- **The CLI's `--include-archived` is a `prune` flag, NOT a `sessions list` flag.** `hermes sessions list` does not accept it. For "show me every session including hidden/archived", query the DB directly.
- **`desktop/interrupted_turns.json` and `runtime/active_sessions.json` are NOT the session store.** They track in-flight work. A user pointing at a tab is pointing at a `sessions` row (or the lack of one), not at a lease file.
- **Multiple messages per user turn is normal.** Compaction, retries, and out-of-band injections can produce 2-3 duplicate user rows for the same prompt. When counting "how many user turns", deduplicate on content prefix, not on row count.
- **A session with `ended_at IS NULL` is still open.** `prune` only selects ended sessions by default. To delete an open-ended session, use `hermes sessions delete <id>` directly — it works regardless of `ended_at`.
