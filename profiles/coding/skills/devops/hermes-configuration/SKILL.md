---
name: hermes-configuration
description: "Manage Hermes profiles, gateways, systemd services."
version: 1.0.0
---

# Hermes Config — profiles, gateways, systemd, bots

## Desktop vs Gateway — which needs what

| Surface | Gateway Needed? | How to use |
|---------|----------------|------------|
| **Desktop GUI** | No | Select profile in sidebar → new session |
| `hermes --profile X chat` | No | Direct CLI call |
| `hermes chat -q "..."` | No | One-shot, no persistent process |
| **Discord bot** | Yes | `hermes-gateway-<profile>.service` systemd |
| **Telegram** | Yes | `hermes-gateway-<profile>.service` systemd |
| **WebSocket/HTTP** | Yes | `hermes gateway start` |

## Pitfalls

### Desktop "bot" is just a profile
Adding a bot in Desktop GUI only creates `~/.hermes/profiles/<name>/`.
The process does NOT start automatically.
- **Fix:** select profile in sidebar and start a session, OR run `hermes --profile <name> chat` in terminal.

### `hermes bot` CLI does not exist
Calling `hermes bot --help` → `invalid choice: 'bot'`.
Bot management is done at profile + systemd/service layer, not via a `bot` subcommand.

### systemd service removal must include `reset-failed`
```bash
systemctl --user disable <service>
systemctl --user stop <service>
rm -f ~/.config/systemd/user/<service>.service
systemctl --user daemon-reload
systemctl --user reset-failed   # without this, "not-found failed" remains
```

### Discord tokens
Write `DISCORD_BOT_TOKEN=<token>` directly in `.env`.
The `token-env` config key is NOT supported in this Hermes version.

### Gateway reads only global `~/.hermes/.env`
NOT per-profile `.env`. Each bot needs a unique env key (e.g. `CODING_DISCORD_BOT_TOKEN`, `ENGLISH_DISCORD_BOT_TOKEN`).
