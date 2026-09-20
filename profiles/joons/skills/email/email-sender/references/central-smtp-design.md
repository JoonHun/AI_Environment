# Centralized SMTP Design - Cross-Profile Email

## Context
Gmail SMTP email sending needed across multiple Hermes profiles. Single-profile credential storage insufficient.

## Solution
Central credential storage at `/home/joons/.hermes/services/smtp-service/.env`

### File Layout
```
/home/joons/.hermes/services/smtp-service/
├── .env               # credentials, 600 perms, gitignored
├── .env.example       # template
├── .gitignore
└── document/
    └── plan.md
```

### Security
- Permissions: 600
- Gitignore: .env
- Cross-profile access requires explicit opt-out
- App Password for 2FA accounts

### Workflow
1. Central `.env` holds SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
2. Skill loads credentials from central path
3. Any Hermes profile can invoke skill
4. Step-by-step execution with user checkpoint

## Lessons
- User corrected single-profile design mid-session
- Centralization required for multi-profile access
- User prefers explicit approvals between steps
- Do not run tools without verification
