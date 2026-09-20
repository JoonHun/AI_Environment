---
name: setup-discord-multi-bot
description: "Discord 멀티 봇 아키텍처 설정: 채널별 프로파일 매칭 다중 Gateway 구동."
version: 1.0.0
platforms: [linux]
---

# Hermes Discord Multi-Bot Setup

## Trigger
Use when the user wants to connect multiple Discord bots, each driven by a separate Hermes profile (different persona/model per channel).

## Architecture
One server → Multiple Bots → Each bot runs as an independent Gateway with its own `--profile`.
Data flow: `[Discord Channel #N] -> [Bot N] -> [Gateway N (Port N)] -> [Ollama (Model N)]`

## Prerequisites
1. **Bot Tokens**: Create two separate applications in [Discord Developer Portal](https://discord.com/developer/applications). Each gets its own `Token`. Invite to your Discord Server with "Message Content Intent" enabled.
2. **Profile Configs**: Ensure each profile (`~/.hermes/profiles/<name>/config.yaml`) has the correct `model.default` and `base_url` pointing to Ollama.
3. **Ollama Concurrency** (local): If bots share the same local Ollama instance, set:
   ```bash
   export OLLAMA_MAX_LOADED_MODELS=3  # or higher based on VRAM/RAM capacity
   ```
   To VERIFY it (the `/proc/<ollama_pid>/environ` read can be permission-denied), check the systemd unit instead:
   ```bash
   systemctl cat ollama 2>/dev/null | grep -A2 Environment
   systemctl --user cat ollama 2>/dev/null | grep -A2 Environment
   ```
   On this GB10 box it lives in `/etc/systemd/system/ollama.service.d/override.conf` as `Environment="OLLAMA_MAX_LOADED_MODELS=3"`.

## Implementation Steps (High-Level)
1. Verify `OLLAMA_MAX_LOADED_MODELS` is set to at least 2+ for concurrent model loading.
2. Add/verify `model.default` and `base_url` in each profile's `config.yaml` (pointing to Ollama via localhost:11434/v1 or the GB10 server IP).
3. **Three-gate auth — all keys go in the PROFILE `.env`** (not global, and NOT via `token-env` in config.yaml — this Hermes version has NO `token-env` support; the adapter's `_is_connected()` only reads the fixed key `DISCORD_BOT_TOKEN`):
   ```bash
   # ~/.hermes/profiles/<name>/.env   (one file per profile)
   DISCORD_BOT_TOKEN=***
   DISCORD_ALLOWED_USERS=<your-discord-user-id>   # gateway-level allowlist (default-deny without this)
   DISCORD_FREE_RESPONSE_CHANNELS=<channel-id>    # allows reply without @mention in that channel
   ```
   - `DISCORD_ALLOWED_USERS`: gateway authentication layer. Without this, every inbound message gets `Unauthorized user: <uid> (<name>) on discord` in the log and is silently dropped. Find your Discord user ID from the warning log or Discord user settings.
   - `DISCORD_FREE_RESPONSE_CHANNELS`: adapter-level mention gate. `DISCORD_IGNORE_NO_MENTION` defaults to `true`, so messages that don't `@mention` the bot are silently dropped even if auth passes. Add the channel ID here to enable "free response" (reply to all messages in that channel, mention optional).
4. **Wire each profile's config** (`config.yaml`): set BOTH `platforms.discord.channels` AND `gateway.discord.channels`. **Do NOT set `token-env`** — it is silently ignored in this Hermes version. Token comes from the profile `.env` above.
   ```yaml
   # ~/.hermes/profiles/<name>/config.yaml
   platforms:
     discord:
       channels:
         - "<channel-id>"
   gateway:
     discord:
       channels:
         - "<channel-id>"
   ```
5. Launch via **systemd user services** (nohup / `&` will die with the shell):
   ```bash
   # ~/.config/systemd/user/hermes-gateway-<name>.service
   [Unit]
   Description=Hermes Agent Gateway - <name>
   After=network-online.target
   Wants=network-online.target

   [Service]
   ExecStart=/home/joons/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway run --profile <name>
   WorkingDirectory=%h/.hermes/profiles/<name>
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=default.target
   ```
   ```bash
   systemctl --user daemon-reload
   systemctl --user enable --now hermes-gateway-<name>.service
   ```
   **Do NOT put `HERMES_HOME` or `--port` in the systemd unit** — `--port` is not a recognized CLI flag in this version; `HERMES_HOME=~/.hermes` (global) overrides profile home resolution and causes the gateway to load global config (empty channels). The `--profile <name>` flag alone is sufficient for correct profile isolation.

## Pitfalls
- **OLLAMA_MAX_LOADED_MODELS defaults to 1**: Without this set, loading a second model forces unloading the first. Every time a Gateway sends a request, it pauses until Ollama finishes the other model's response for that slot. Set to `3+` to avoid cross-bot latency spikes.
- **Same port conflict**: Cannot launch two Gateways on the same host:port without `--port` override (usually fails with "Address already in use").
- **Channel binding is via Discord API, not Hermes**: The bot token itself dictates which channels it has access to. You assign channels *in Discord admin*, not inside hermes config.
- **Hermes does not auto-route by channel name**: Each Gateway processes messages arriving to its own Bot Token's server/channels with full access. If you share one Bot Token across multiple profiles, routing must be manual via Hermes configuration (e.g., `channels_to_profiles` or a dispatch script).
- **Platform config structure**: Do NOT use `platforms.discord.token-env` — it is silently
  ignored by the discord adapter in this build. Put all Discord-related env vars
  (`DISCORD_BOT_TOKEN`, `DISCORD_ALLOWED_USERS`, `DISCORD_FREE_RESPONSE_CHANNELS`) in the
  profile's `.env` at `~/.hermes/profiles/<name>/.env`. In `config.yaml`, only `channels` is
  needed under both `platforms.discord.*` and `gateway.discord.*`.
- **Global `.env` must allow gateways**: `~/.hermes/.env`의 `# GATEWAY_ALLOW_ALL_USERS=false`를 주석 해제(`GATEWAY_ALLOW_ALL_USERS=true`)해야 게이트웨이가 플랫폼을 인식함. 프로필별 `.env`에 토큰 설정만 있고 글로벌 설정이 비활성화되면 모든 플랫폼이 거부됨.
- **Gateway `.discord.channels: []` kills everything**: Even if valid `platforms.discord` structure exists, an empty `gateway.discord.channels: []` causes the gateway to die with "No messaging platforms enabled". Always ensure `gateway.discord.channels` has at least one channel ID entry. This field is checked FIRST before `platforms:` by the Hermes Gateway runtime — if it's empty, the platform is treated as disabled regardless of what `platforms:` says. When you set it via `hermes config set`, you'll see `⚠ 'gateway.discord.channels' is not a recognized config key — it was saved anyway`. **That warning is expected and harmless — the value IS saved and IS the field the runtime checks first. Do NOT delete it on the strength of the warning.**
- **Token storage policy**: 봇 토큰은 절대 `config.yaml`에 기록하지 않음. 프로파일별 `.env`에 고정 키 `DISCORD_BOT_TOKEN=***
- **`token-env` is a dead key in this build**: setting `platforms.discord.token-env: X` in `config.yaml` is silently ignored — the adapter's `_is_connected()` reads only the fixed env key `DISCORD_BOT_TOKEN`. The profile's `.env` is what the gateway reads at profile startup; there is no global-vs-profile precedence issue as long as the profile `.env` carries the key.

## Configuration Reference
### Profile `/home/joons/.hermes/profiles/<name>/config.yaml`
```yaml
model:
  provider: custom
  default: model-name:latest
  base_url: http://localhost:11434/v1

platforms:
  discord:
    channels:
      - "<channel-id>"
# NOTE: no token-env key here — it is dead in this build (see Pitfalls).
```

### Global `/home/joons/.hermes/.env` (optional convenience)
```
GATEWAY_ALLOW_ALL_USERS=true
```
> The per-profile `.env` files at `~/.hermes/profiles/<name>/.env` carry all Discord-related
> keys (`DISCORD_BOT_TOKEN`, `DISCORD_ALLOWED_USERS`, `DISCORD_FREE_RESPONSE_CHANNELS`). This was
> verified working in this session — both bots connected and handled messages after setting
> these keys in their respective profile `.env` files. The earlier claim "Gateway ignores
> per-profile .env" is incorrect.

### Discord Developer Portal Checklist
- [ ] Message Content Intent: ON
- [ ] Permissions: Send Messages, Read Message History, Use Application Commands
- [ ] OAuth2 scopes: `bot` + `applications.commands`
- [ ] Invite URL 생성 후 서버에 추가

### Channel IDs (current setup)
- Coding: `1542009729327435776`
- English: `1542009593142579302`

## Persona per channel
Channel-specific persona lives in that profile's `SOUL.md` (the identity slot — the ONLY
persona file auto-injected; `system_prompt.md` is NOT read by the runtime). Set it up per
the `hermes-profile-customization` skill. Watch for the invisible-Unicode block: a dirty
`SOUL.md` is silently refused (`[BLOCKED: SOUL.md contained potential prompt injection
(invisible_unicode_U+XXXX)]`), so after moving persona content into `SOUL.md`, scan for and
strip U+200B-class characters, then `/new` the channel.

## Verification
1. Check logs: `grep -i discord ~/.hermes/logs/gateway.log | tail -20` on each profile's log dir.
2. Confirm port binding: `ss -tulnp | grep 86[0-9][0-8]` (or similar port range).
3. Send a test message per channel; confirm the correct model responds in logs and Discord.
