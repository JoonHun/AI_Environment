---
name: raspberry-pi-moode
description: "Use when building a Raspberry Pi music player with moOde."
---

Raspberry Pi as an always-on network music player (moOde web UI, port 80); the phone is only a web-UI remote; audio out via 3.5mm to a speaker's aux input. Playback survives phone disconnect because the Pi is the player, not the phone.

## When to Use

- Building a Pi-based network music player with moOde (image flash → NAS library → output → remote verification).
- Deciding power/output wiring for a Pi audio rig, or whether a speaker can power a Pi.
- Diagnosing streaming audio dropouts/resets on ESP32 or Pi streaming rigs.

## Procedure

1. **Flash the moOde dedicated image** with Raspberry Pi Imager: "Media Player OS" section → moOde audio player (latest release). moOde 10 has NO install script for a plain Pi OS — never flash Pi OS Lite and try to add moOde; re-flash the SD instead.
2. In Imager's "Edit OS Settings" set ALL of: hostname (e.g. `moode`), username/password, **SSH enabled**, WiFi SSID/password. moOde does not function correctly without login + SSH configured.
3. First boot: the system **auto-reboots 3 times** while applying Imager settings. Wait ~10 min; no power cycling.
4. Verify from the gateway host (agent terminal): `ping <ip>`, then `sshpass -p '<pass>' ssh -o StrictHostKeyChecking=no <user>@<ip>` with a read-only probe: `head -2 /etc/os-release; dpkg -l | grep -i moode; systemctl is-active mpd; aplay -l; ss -tlnp | grep :80`.
5. Browser: `http://<ip>` (or `moode.local`). Menu(m) > Configure > Audio → pick the output device for the target jack.
6. Menu(m) > Configure > Library → `CREATE music source` (Type SMB with share path + creds, or HTTP with NAS URI) → SAVE → green checkmark confirms mount → Menu(m) > Update library and wait for the spinner.
7. Connect 3.5mm cable Pi → speaker aux. Most aux-input speakers auto-switch to the cable. Play a track, then test the remote requirement: disconnect/turn off the phone, playback must continue.

## Pitfalls

- **Re-flashing changes the SSH host key.** Run `ssh-keygen -R <ip>` on BOTH the gateway host and the user's PC before connecting, or both sides fail with "REMOTE HOST IDENTIFICATION HAS CHANGED".
- **Pi 4 analog 3.5mm is not a visible ALSA card.** `aplay -l` shows only `vc4hdmi0/1` cards; the headphone jack is routed inside the vc4hdmi driver and moOde selects it through its `_audioout` virtual device. Choose the output in moOde's Audio config — don't hunt for a "Headphone" card and don't conclude the jack is absent.
- **Power: never feed the Pi from a speaker's USB port.** Speaker USB-C ports are typically 5V 1A and often marked "Service only" (JBL Authentics 500: 5V 1A). Pi 4 needs 5V 3A — an under-powered supply produces brownout reboots, the exact failure mode of the ESP32 streaming rig this replaced. Use a proper 5V 3A USB-C supply.
- **Agent cannot run sudo on the Pi** — piping the password into `sudo -S` is blocked as a brute-force vector. Hand the user the exact sudo command, have them run it in their own terminal, and proceed after they say done.
- **User workflow for Pi builds:** show a numbered checklist/plan first, execute one step per response, no un-requested sudo runs, report each step's real output.
- NAS sources: prefer SMB share (moOde shows the folder tree as-is, best pick-a-song UX) over HTTP URI; IPTime NAS supports both.

## References

- `references/hardware-notes.md` — Pi power/output table, JBL Authentics 500 port notes, ESP32 audio-drop diagnosis checklist.
