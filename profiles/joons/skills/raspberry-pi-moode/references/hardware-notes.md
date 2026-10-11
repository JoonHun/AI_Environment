# Hardware notes for Pi music builds

## Power
| Board | Requirement |
|---|---|
| Pi 4 B | 5V 3A USB-C (2.5A acceptable only if downstream USB draw < 500mA) |
| Pi Zero 2 W | 5V 2.5A; **no 3.5mm jack** — needs a USB DAC dongle |
| Speaker USB-C ports | Typically 5V 1A, often "Service only" — never sufficient for a Pi |

## JBL Authentics 500 (user's speaker)
- Inputs: 3.5mm aux (line level; auto-switches when cable inserted + playback starts), Bluetooth 5.3 (SBC only), Wi-Fi, Ethernet, AirPlay/Chromecast.
- USB-C: 5V 1A, service-only on non-US versions.
- Best path for a Pi build: 3.5mm aux from the Pi.

## ESP32 (S3 N16R8) audio-drop diagnosis — for the user's original rig
Compute power is rarely the cause. In order of likelihood:
1. **Single WiFi radio contention** — WebDAV streaming and the control web server share one radio; control traffic (polling, page refreshes) starves the stream. Fix: REST one-shot requests only, no long polling/auto-refresh; separate control and stream tasks onto different cores.
2. **Brownout vs task watchdog reset** — check the serial monitor for "Reset reason"; brownout → bigger 5V supply; WDT → task structure.
3. **Small RX buffer + weak WebDAV Range handling** — enlarge PSRAM ring buffer (4–6 MB), disable WiFi power save, prefer the NAS's plain HTTP URI service over WebDAV.

## moOde facts
- Web UI on port 80; REST API at `moodeapi.php` (e.g. `?action=get_now_playing`) for wiring extra remotes later.
- MPD is the engine (`mpc` CLI works over SSH); output device managed via the `_audioout` virtual ALSA device.
- `moodeutl --help` for status/logs; `sudo /var/www/util/libupd-submit.php` = Update library from CLI.
