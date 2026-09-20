---
name: email-sender
description: Send email via Gmail SMTP from any Hermes profile.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Email, SMTP, Gmail, Agent, Automation]
    related_skills: [himalaya, google-workspace]
---

# Email Sender Skill

Send email via Gmail SMTP from any Hermes profile using centralized credentials. Other agents can call this skill to send mail with provided recipients and content.

## Reference
See `references/central-smtp-design.md` for cross-profile design details and lessons learned.
See `references/gmail-compat-html.md` for how to author HTML email bodies that actually render correctly in Gmail (table-based layout, no flex/grid, no `<script>`; tabs/toggles/`<style>` blocks are stripped).

## When to Use
- Agent needs to send email via Gmail SMTP
- Need cross-profile email sending capability
- Reusable email dispatch for multiple agents
- Use `/home/joons/.hermes/services/smtp-service/smtp_sender.py` as implementation

## Prerequisites
- Gmail account with 2FA enabled
- Google App Password generated
- Central credentials file at `/home/joons/.hermes/services/smtp-service/.env`
- Python with smtplib

## Environment
Central credentials file: `/home/joons/.hermes/services/smtp-service/.env`
SMTP sender script: `/home/joons/.hermes/services/smtp-service/smtp_sender.py`
Log file: `/home/joons/.hermes/services/smtp-service/smtp.log`
Keys:
- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=587`
- `SMTP_USER=...`
- `SMTP_PASS=...`

**Cross-profile design:** Credentials are centralized to allow any Hermes profile to send mail. Files must be placed under `/home/joons/.hermes/services/smtp-service/`. Each profile `.env` may reference `SMTP_SERVICE_PATH` for discovery. Central file must have `600` permissions and be gitignored.

## Procedure
1. Load credentials from central `.env` at `/home/joons/.hermes/services/smtp-service/.env`
2. Validate required fields: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
3. Run `/home/joons/.hermes/services/smtp-service/smtp_sender.py` with parameters:
   - `to` (recipient email)
   - `subject` (email subject)
   - `body` (email body text)
   - `html_file_path` (optional, overrides body with file content)
4. Send via SMTP with TLS using smtplib
5. Log result to `/home/joons/.hermes/services/smtp-service/smtp.log`
6. Automatically append AI Agent disclaimer footer (bilingual Korean/English) to all emails

## Pitfalls
- App Password required for 2FA accounts
- Central file must be readable by all profiles; cross-profile read requires `cross_profile=True` opt-out for file access
- Do not commit `.env` to git; use `.gitignore`
- Rate limiting on Gmail
- **HTML body compatibility:** Gmail strips `<script>`, external `<style>`, `display:flex/grid`, `position:sticky`, and all `on*=` handlers. Anything interactive (tabs, accordions, hover-only reveals) is dead on arrival. Use table-based layout with inline styles and show all sections consecutively. See `references/gmail-compat-html.md` for the golden rules + known-good skeleton + a quick diagnostic checklist.
- **User preference:** Step-by-step execution with intermediate state reports, no sudden tool runs. User wants concise core answers, long outputs to files
- **User constraint:** Explicit approval required before next step; do not auto-progress. Stop at instruction boundary
- HTML file content is embedded directly in email body, not linked. Internal IP links are unusable externally — always embed file content
- AI Agent disclaimer footer is automatically appended in both Korean and English for all emails
- Central credential design required after user corrected single-profile limitation. Use `/home/joons/.hermes/services/smtp-service/.env` for all profiles

## Verification
- Test send to self
- Check logs for success
