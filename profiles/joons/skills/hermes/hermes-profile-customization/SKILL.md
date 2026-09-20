---
name: hermes-profile-customization
description: Use when adding/changing a profile's prompt persona.
---

# Hermes profile customization (persona / standing prompt)

## Trigger
User wants to "add/remove/change X in my profile's prompt" (a standing instruction, persona,
behavior rule, or code-review format) for any Hermes profile.

## Where the pieces live (per profile)
A profile at `~/.hermes/profiles/<name>/` (root profile: `~/.hermes/`) has:
- `SOUL.md` — the identity slot; replaces the built-in default identity block in the system
  prompt. **This is the ONLY persona file the gateway/agent auto-injects** (verified in
  `agent/system_prompt.py`: `load_soul_md` is the identity read; no loader exists for
  `system_prompt.md`). Often a one-liner (e.g. "coding assitant") — which is the most
  common reason a user reports "persona is not applied": the slot is effectively empty.
- `system_prompt.md` — user-written standing rules, kept by hand. **In this build it is NOT
  injected at runtime** — the file can hold a full persona and still be silently ignored.
  When it holds the real persona, migrate that content into `SOUL.md`.
- `config.yaml` — model, temperature, environment metadata; not for behavioral prose.
- `USER.md` / `MEMORY.md` — user-profile and agent-memory stores.

## Steps
1. Read BOTH `SOUL.md` and `system_prompt.md` in the profile dir.
2. **Make `SOUL.md` the persona carrier.** If `SOUL.md` is a stub and `system_prompt.md`
   holds the real persona (numbered role/rules), put that content in `SOUL.md`:
   backup first (`cp SOUL.md SOUL.md.bak`), then `cp system_prompt.md SOUL.md`.
   Keep it within the context-file cap — default scales with model context (floor 20K chars),
   so multi-KB personas are fine and not truncated.
3. Restart the gateway service (per-profile persona is read at session start; running
   sessions keep the old prompt in memory): `systemctl --user restart hermes-gateway-<name>`.
4. Tell the user to run `/new` in the Discord channel (or start a fresh chat session) so a
   new session picks up the new `SOUL.md`. The first reply should already reflect the persona
   (correct language / format rules).

## Pitfalls
- **Hidden Unicode → SOUL.md is REFUSED, not truncated**: Hermes security-scans SOUL.md before
  injection. Invisible characters — zero-width space U+200B/C/D, ZWJ U+200D, BOM U+FEFF,
  soft-hyphen U+00AD, variation selectors U+FE00–FE0F, word-joiner U+2060, bidi marks — trip
  the scanner and the whole file is dropped with
  `[BLOCKED: SOUL.md contained potential prompt injection (invisible_unicode_U+XXXX). Content not loaded.]`
  in the system prompt — the persona silently fails to load with no error in the Discord
  channel. Verify cleanliness before/after editing:
  `python3 -c "import sys;t=open(sys.argv[1],encoding='utf-8').read();print('clean' if not any(ord(c) in {0x200B,0x200C,0x200D,0x200E,0x200F,0xFEFF,0x2060,0x00AD,0x180E,0x202A,0x202B,0x202C,0x202D,0x202E} for c in t) else 'DIRTY')" SOUL.md`
  (Also strip `0x00` null bytes if present.) A common source: a persona copied from a
  renderer that inserts a zero-width space to force a line break. Symptoms when dirty: the
  file renders fine in an editor (hidden chars are invisible) but the agent's system prompt
  contains the BLOCKED line, and the persona's first line (e.g. a "Role:" sentence) is
  missing from the prompt.
- Do not confuse `config.yaml` prose (`ide_environment`, `preferred_languages`) with the
  behavioral prompt — config is metadata, prompt files are behavior.
- Cross-profile: the active profile's files are at `~/.hermes/profiles/<active>/`, not the root
  `~/.hermes/`. Writing to another profile requires explicit user direction and
  `cross_profile=True` on write tools.
- After editing, re-read the file once to confirm placement before telling the user it's done.
- When `SOUL.md` already holds a numbered rules list, append and preserve numbering so the
  user's prior mental map stays valid. (Only when `SOUL.md` is a stub and you're moving
  `system_prompt.md` content in is a wholesale replace appropriate.)

## Verification
- `read_file` the tail of the file after the patch to confirm the new block sits between the
  last numbered rule and any trailer section.
- Tell the user: "applies to new sessions; run `/new` if you want it live now."
