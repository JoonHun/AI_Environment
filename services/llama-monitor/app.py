"""llama-monitor — LAN status dashboard for llama.cpp `llama-server` instances.

Design (adapted from ollama-monitor):
  * A background sampler thread samples system metrics (nvidia-smi / /proc)
    every N seconds and keeps a ring buffer for the trend chart, so API
    calls never block on slow subprocesses and the UI shows last-known
    values with a "stale" flag instead of silently freezing.
  * A second scanner thread re-reads each server's journal tail on a fixed
    cadence and parses llama.cpp's timing lines (n_gen/tg, prompt eval,
    eval time, draft acceptance, release) — the SAME shapes Ollama used,
    plus llama.cpp's MTP `draft acceptance` line.
  * **Multi-server**: config.yaml `servers[]` lists each llama-server.
    llama.cpp is 1 port = 1 model (unlike Ollama's 1-port-many-models), so
    the UI renders ONE card per server: model + state stepper + t/s + MTP.
  * **Probe target**: on-demand servers sit behind a raw-TCP proxy; probing
    the FRONT port would boot the backend. So we probe `backend_port` and
    distinguish standby (inactive, normal) from failed via `systemctl --user`.

Endpoints:
  GET  /               → dashboard HTML
  GET  /api/servers    → list of per-server samples (1 entry per card)
  GET  /api/history    → ring buffer for the trend chart
  GET  /api/health     → liveness probe
  POST /api/speed-test → REAL inference speed test against a named server
"""

import logging
import logging.handlers
import os
import re
import threading
import time
import datetime
import subprocess
import stat
from collections import deque

import requests
import yaml
from flask import Flask, jsonify, render_template, request
from waitress import serve

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULTS = {
    "host": "0.0.0.0",
    "port": 5002,
    "sample_interval_sec": 2,
    "history_points": 1800,
    "http_timeout_sec": 6,
    "gpu_cmd_timeout_sec": 6,
    "log_level": "INFO",
    "log_max_bytes": 1_048_576,
    "log_backup_count": 3,
    "live_token_poll_sec": 3,
    "live_token_tail_lines": 2000,
    "stale_threshold_sec": 8,
    "speed_test": {
        "enabled": True,
        "num_predict": 256,
        "timeout_sec": 180,
        "secret": "",
    },
    "servers": [
        # Fallback: the resident Qwen3.8 server (verified live on 11534).
        {"port": 11534, "backend_port": 11534, "label": "joons",
         "mode": "resident", "journal_unit": "llama-server-38"},
    ],
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    path = os.path.join(APP_DIR, "config.yaml")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        cfg = _deep_merge(DEFAULTS, user_cfg)
    else:
        print(f"WARNING: {path} not found — using built-in defaults")
    # servers is a list — deep-merge must not merge two lists element-wise.
    if isinstance(user_cfg.get("servers"), list):
        cfg["servers"] = user_cfg["servers"]
    return cfg


CFG = load_config()
HTTP_TO = CFG["http_timeout_sec"]
GPU_TO = CFG["gpu_cmd_timeout_sec"]
STALE_S = int(CFG["stale_threshold_sec"])

# ---------------------------------------------------------------------------
# Logging (rotating)
# ---------------------------------------------------------------------------

_log = logging.getLogger("llama-monitor")
_log.setLevel(getattr(logging, str(CFG["log_level"]).upper(), logging.INFO))
_handler = logging.handlers.RotatingFileHandler(
    os.path.join(APP_DIR, "app.log"),
    maxBytes=CFG["log_max_bytes"],
    backupCount=CFG["log_backup_count"],
    encoding="utf-8",
)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
_log.addHandler(_handler)

app = Flask(__name__, template_folder=os.path.join(APP_DIR, "templates"))


def sub(cmd: list, timeout: float = GPU_TO) -> tuple[int, str]:
    """Run a command, never raise; return (exit_code, stdout)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except Exception as e:  # noqa: BLE001 — sampler must survive anything
        return 1, f"error: {e}"


def _num(x):
    """'93' → 93.0; '[N/A]' / '' → None."""
    if x is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(x).replace(",", ""))
    return float(m.group()) if m else None


# ---------------------------------------------------------------------------
# System collectors (GB10 / unified-memory aware) — reused from ollama-monitor
# ---------------------------------------------------------------------------

def sample_gpu() -> dict:
    """GPU util/temp/power + per-process VRAM + unified RAM pool."""
    out = {
        "available": False, "name": None, "util_pct": None, "temp_c": None,
        "power_w": None, "processes": [], "vram_proc_mib": None,
        "ram": {"total_gb": None, "available_gb": None, "used_gb": None},
    }
    code, name = sub(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    out["name"] = name.splitlines()[0].strip() if code == 0 and name else None
    code, csvline = sub([
        "nvidia-smi",
        "--query-gpu=utilization.gpu,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ])
    if code == 0 and csvline:
        util_s, temp_s, power_s = [p.strip() for p in csvline.split(",")[:3]]
        out["available"] = True
        out["util_pct"] = _num(util_s)
        out["temp_c"] = _num(temp_s)
        out["power_w"] = _num(power_s)

    code, apps = sub([
        "nvidia-smi",
        "--query-compute-apps=pid,process_name,used_memory",
        "--format=csv,noheader",
    ])
    if code == 0 and apps:
        for line in apps.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                mem = _num(parts[2])
                out["processes"].append({
                    "pid": int(_num(parts[0]) or 0),
                    "name": parts[1].rsplit("/", 1)[-1],
                    "mem_mib": int(mem) if mem is not None else 0,
                })
        if out["processes"]:
            out["vram_proc_mib"] = sum(p["mem_mib"] for p in out["processes"])

    # Unified memory pool (the "real" VRAM ceiling on GB10)
    try:
        info = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                m = re.match(r"(MemTotal|MemAvailable):\s+(\d+) kB", line)
                if m:
                    info[m.group(1)] = int(m.group(2))
        if "MemTotal" in info and "MemAvailable" in info:
            # meminfo "kB" is really KiB (1024 B). Convert to decimal GB (1000^3):
            # bytes = kB * 1024 ; GB = bytes / 1000^3
            total = info["MemTotal"] * 1024 / 1000**3
            avail = info["MemAvailable"] * 1024 / 1000**3
            out["ram"] = {"total_gb": round(total, 2),
                          "available_gb": round(avail, 2),
                          "used_gb": round(total - avail, 2)}
    except Exception as e:  # noqa: BLE001
        _log.warning("meminfo read failed: %s", e)
    return out


_PREV_CPU = {"idle": None, "total": None, "ts": 0.0}


def _read_cpu_totals():
    with open("/proc/stat", "r", encoding="utf-8") as f:
        line = f.readline()
    parts = line.split()
    if not parts or parts[0] != "cpu":
        return None
    vals = [int(x) for x in parts[1:]]
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    return idle, sum(vals)


def sample_cpu() -> dict:
    """CPU util % (delta of /proc/stat), hottest acpitz zone, core count."""
    out = {"util_pct": None, "temp_c": None, "power_w": None,
           "power_note": "N/A (power sensor not exposed)", "cores": os.cpu_count()}
    try:
        sample = _read_cpu_totals()
        if sample:
            idle, total = sample
            now = time.time()
            p = _PREV_CPU
            if p["total"] is not None and total > p["total"] and now > p["ts"]:
                d_idle, d_total = idle - p["idle"], total - p["total"]
                if d_total > 0:
                    out["util_pct"] = round(max(0.0, min(100.0, 100.0 * (1 - d_idle / d_total)), 1))
            p["idle"], p["total"], p["ts"] = idle, total, now
    except Exception as e:  # noqa: BLE001
        _log.warning("cpu util read failed: %s", e)
    try:
        import glob
        best = None
        for z in glob.glob("/sys/class/thermal/thermal_zone*"):
            try:
                with open(z + "/type", "r", encoding="utf-8") as f:
                    if "acpitz" not in f.read():
                        continue
                with open(z + "/temp", "r", encoding="utf-8") as f:
                    t = int(f.read().strip())
                if best is None or t > best:
                    best = t
            except Exception:  # noqa: BLE001
                continue
        if best is not None:
            out["temp_c"] = round(best / 1000.0, 1)
    except Exception as e:  # noqa: BLE001
        _log.warning("thermal zone read failed: %s", e)
    return out


def sample_storage() -> dict:
    """Disk usage for real filesystems (filters virtual/FUSE mounts)."""
    try:
        import shutil
        mounts = {}
        with open("/proc/mounts", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                fs, dev = parts[1], parts[0]
                if fs.startswith("/proc") or fs.startswith("/sys") or fs.startswith("--"):
                    continue
                if "snap" in fs or "loop" in dev or "tmpfs" in dev:
                    continue
                if "efivar" in fs or "udev" in dev or "devpts" in dev or "hugetlb" in dev:
                    continue
                if "mqueue" in dev or "sunrpc" in dev or "rpc_pipe" in fs:
                    continue
                # FUSE/portal/gvfs per-user mounts — statvfs often PermissionError.
                if "fuse" in dev or "fuse" in fs or "gvfs" in dev or "portal" in dev or "fusectl" in dev:
                    continue
                if dev not in mounts:
                    mounts[dev] = fs
        out = []
        for dev, fs in sorted(mounts.items()):
            try:
                usage = shutil.disk_usage(fs)   # per-mount tolerant: skip on error
            except Exception:  # noqa: BLE001
                continue
            out.append({"device": dev, "mount": fs,
                        "total_gb": round(usage.total / (1000 ** 3), 2),
                        "used_gb": round(usage.used / (1000 ** 3), 2),
                        "free_gb": round(usage.free / (1000 ** 3), 2)})
        return out
    except Exception as e:  # noqa: BLE001
        _log.warning("storage sampling failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Per-server inference state (journal tail + /slots API)
#
# llama.cpp log shapes (verified against live 388-line capture):
#   progress (~3s while a task runs):
#       slot print_timing: id  3 | task 18379 | n_gen = 101, tg = 24.43 t/s, tg_3s = 24.68 t/s
#   task start (prefill begin):
#       slot launch_slot_: id  3 | task 18379 | processing task, is_child = 0
#   completion (4-line block):
#       slot print_timing: id  3 | task 22774 | prompt eval time = 5107.82 ms / 2668 tokens ( 1.91 ms per token, 522.34 tokens per second)
#       slot print_timing: id  3 | task 22774 |        eval time = 65322.16 ms / 1330 tokens ( 49.15 ms per token, 20.35 tokens per second)
#       slot print_timing: id  3 | task 22774 |       total time = 70429.97 ms / 3998 tokens
#   MTP speculative stats (MTP builds only, once per task):
#       slot print_timing: id  3 | task 22774 | draft acceptance = 0.68627 ( 770 accepted / 1122 generated), mean len = 2.37
#   task end (slot release):
#       slot      release: id  3 | task 22774 | stop processing: n_tokens = 58119, truncated = 0
#
# NOTE: llama.cpp has NO "all slots are idle" marker — idle is derived from
# /slots is_processing==False and the release marker.
# ---------------------------------------------------------------------------

RE_NGEN    = re.compile(r"n_gen\s*=\s*(\d+)")
RE_TG      = re.compile(r"tg\s*=\s*([\d.]+)\s*t/s")
RE_TG3S    = re.compile(r"tg_3s\s*=\s*([\d.]+)\s*t/s")
RE_TASK    = re.compile(r"task\s+(\d+)")
# (?<!prompt ) lookbehind: `eval time` also matches inside `prompt eval time`.
RE_EVAL    = re.compile(r"(?<!prompt )eval\s+time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens")
RE_PROMPT  = re.compile(r"prompt\s+eval\s+time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens\s*\(\s*[\d.]+\s*ms\s+per\s+token,\s*([\d.]+)\s+tokens\s+per\s+second")
RE_TOTAL   = re.compile(r"total\s+time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens")
RE_DRAFT   = re.compile(r"draft\s+acceptance\s*=\s*([\d.]+)\s*\(\s*(\d+)\s+accepted\s*/\s*(\d+)\s+generated\)\s*,\s*mean\s+len\s*=\s*([\d.]+)")
RE_START   = re.compile(r"launch_slot_:\s*.*task\s+(\d+)\s*\|\s*processing")
RE_RELEASE = re.compile(r"release:\s*.*task\s+(\d+)\s*\|.*n_tokens\s*=\s*(\d+)")

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def _journal_unit_tail(unit: str, n: int) -> tuple[bool, list]:
    """Return (ok, lines) for the last n lines of a systemd USER unit.
    On-demand server backends run as user services — use --user."""
    code, out = sub(["journalctl", "--user", "-u", unit, "-n", str(n),
                     "--no-pager", "--since", "30 min ago"], timeout=8)
    if code != 0:
        return False, []
    return True, out.splitlines()


def _parse_journal_ts(line: str) -> str:
    """Best-effort ISO timestamp from a journal line's leading 'Mon DD HH:MM:SS'."""
    m = re.match(r"([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})", line)
    if not m:
        return time.strftime("%Y-%m-%d %H:%M:%S")
    now = time.localtime()
    try:
        dt = datetime.datetime(now.tm_year, MONTHS.get(m.group(1), now.tm_mon),
                               int(m.group(2)), int(m.group(3)),
                               int(m.group(4)), int(m.group(5)))
        return dt.isoformat(timespec="seconds")
    except Exception:  # noqa: BLE001
        return time.strftime("%Y-%m-%d %H:%M:%S")


def _service_active(unit: str) -> bool:
    code, _ = sub(["systemctl", "--user", "is-active", "--quiet", unit], timeout=5)
    return code == 0


def sample_server_inference(srv: dict) -> dict:
    """Parse one server's journal tail → progress/final/prompt/MTP + stage."""
    unit = srv.get("journal_unit", "")
    live = {
        "active": False, "state": "idle", "stage": "idle",
        "tokens": 0, "tps": None, "tps_3s": None,
        "final_tokens": None, "final_ms": None, "final_tps": None,
        "prompt_tokens": None, "prompt_ms": None, "prompt_tps": None,
        "mtp_accept": None, "mtp_accepted": None, "mtp_generated": None, "mtp_mean_len": None,
        "total_ms": None, "total_tokens": None,
        "task_id": None, "session_tokens": None, "truncated": None,
        "last_seen": None, "log_ok": True,
    }
    if not unit:
        return live

    ok, lines = _journal_unit_tail(unit, int(CFG.get("live_token_tail_lines", 2000)))
    if not ok:
        live["log_ok"] = False
        return live

    last_start_idx = -1
    last_speed_idx = -1
    latest_progress = latest_final = latest_prompt = latest_draft = None
    latest_total = None
    release_tokens = release_trunc = None

    for idx, line in enumerate(lines):
        if RE_START.search(line):
            last_start_idx = idx
        if RE_RELEASE.search(line):
            m = RE_RELEASE.search(line)
            release_tokens = int(m.group(2))
            # truncated is right after n_tokens in the same line
            mt = re.search(r"truncated\s*=\s*(\d+)", line)
            if mt:
                release_trunc = int(mt.group(1))
        # Order matters: check prompt before eval (lookbehind also guards it).
        if RE_PROMPT.search(line):
            latest_prompt = line
            continue
        if RE_DRAFT.search(line):
            latest_draft = line
            continue
        if RE_TOTAL.search(line):
            latest_total = line
            continue
        if "print_timing" in line:
            if RE_NGEN.search(line):
                last_speed_idx = idx
                latest_progress = line
                continue
            m_f = RE_EVAL.search(line)
            if m_f:
                last_speed_idx = idx
                latest_final = line
                continue

    def _grab(regex, line, groups=1):
        if not line:
            return None
        m = regex.search(line)
        if not m:
            return None
        if groups == 1:
            return m.group(1)
        return m.groups()

    # ---- progress -----------------------------------------------------------
    if latest_progress:
        live["tokens"] = int(_num(_grab(RE_NGEN, latest_progress)) or 0)
        live["tps"] = _num(_grab(RE_TG, latest_progress))
        live["tps_3s"] = _num(_grab(RE_TG3S, latest_progress))
        live["last_seen"] = _parse_journal_ts(latest_progress)
        live["task_id"] = _grab(RE_TASK, latest_progress)
    # ---- final decode summary ----------------------------------------------
    if latest_final:
        m = RE_EVAL.search(latest_final)
        live["final_ms"] = _num(m.group(1))
        live["final_tokens"] = int(_num(m.group(2)) or 0)
        live["final_tps"] = round(live["final_tokens"] / (live["final_ms"] / 1000.0), 2) if live["final_ms"] else None
        if not live["last_seen"]:
            live["last_seen"] = _parse_journal_ts(latest_final)
    # ---- prompt (prefill) summary ------------------------------------------
    if latest_prompt:
        m = RE_PROMPT.search(latest_prompt)
        live["prompt_ms"] = _num(m.group(1))
        live["prompt_tokens"] = int(_num(m.group(2)) or 0)
        live["prompt_tps"] = _num(m.group(3))
        if live["prompt_tps"] is None and live["prompt_ms"] and live["prompt_tokens"]:
            live["prompt_tps"] = round(live["prompt_tokens"] / (live["prompt_ms"] / 1000.0), 2)
    # ---- MTP ----------------------------------------------------------------
    if latest_draft:
        m = RE_DRAFT.search(latest_draft)
        live["mtp_accept"] = _num(m.group(1))
        live["mtp_accepted"] = int(_num(m.group(2)) or 0)
        live["mtp_generated"] = int(_num(m.group(3)) or 0)
        live["mtp_mean_len"] = _num(m.group(4))
    # ---- total --------------------------------------------------------------
    if latest_total:
        m = RE_TOTAL.search(latest_total)
        live["total_ms"] = _num(m.group(1))
        live["total_tokens"] = int(_num(m.group(2)) or 0)
    # ---- session / release --------------------------------------------------
    if release_tokens is not None:
        live["session_tokens"] = release_tokens
        live["truncated"] = release_trunc
    # ---- active / state / stage --------------------------------------------
    active = last_speed_idx > last_start_idx  # progress line after most recent start
    if active:
        live["state"] = "generating"
    elif last_speed_idx >= 0 and live["last_seen"] is not None:
        live["state"] = "just-finished"
    else:
        live["state"] = "idle"
    # stage: newest of (start / progress) — progress newer → decode, else prefill
    newest = max(last_start_idx, last_speed_idx)
    if newest < 0:
        live["stage"] = "idle"
    elif last_speed_idx >= last_start_idx and live.get("tps") is not None:
        live["stage"] = "decode"
    else:
        live["stage"] = "prefill"
    live["active"] = active
    return live


def sample_server_http(srv: dict) -> dict:
    """Probe the backend (NOT the proxy front) → up/version/model/slots."""
    base = f"http://127.0.0.1:{srv.get('backend_port', srv['port'])}".rstrip("/")
    out = {"up": False, "version": None, "model": None, "slots": [], "error": None}

    # /health
    try:
        r = requests.get(base + "/health", timeout=HTTP_TO)
        if r.status_code == 200:
            out["up"] = True
    except Exception as e:  # noqa: BLE001
        out["error"] = f"health: {e.__class__.__name__}"

    # /v1/models (version + first model name + meta)
    if out["up"]:
        try:
            j = requests.get(base + "/v1/models", timeout=HTTP_TO).json()
            data = j.get("data", [])
            if data:
                m = data[0]
                out["model"] = m.get("id")
                # llama.cpp exposes model size/params in some builds
                out["size"] = m.get("size")
                # Full meta (n_params, n_ctx, size, ftype, n_vocab, n_embd)
                meta = m.get("meta", {})
                out["meta"] = meta
        except Exception:  # noqa: BLE001
            pass

    # /slots (realtime state — 1st-class source)
    if out["up"]:
        try:
            slots = requests.get(base + "/slots", timeout=HTTP_TO).json()
            for s in slots:
                is_proc = bool(s.get("is_processing"))
                np, npp = s.get("n_prompt_tokens", 0), s.get("n_prompt_tokens_processed", 0)
                if is_proc:
                    stage = "prefill" if (npp < np) else "decode"
                else:
                    stage = "idle"
                out["slots"].append({
                    "id": s.get("id"), "stage": stage,
                    "is_processing": is_proc, "task": s.get("id_task"),
                    "prompt_tokens": np, "prompt_processed": npp,
                    "n_ctx": s.get("n_ctx"), "speculative": s.get("speculative"),
                })
            # server-level realtime stage = busiest slot
            if out["slots"]:
                stages = [s["stage"] for s in out["slots"]]
                if "decode" in stages:
                    out["stage"] = "decode"
                elif "prefill" in stages:
                    out["stage"] = "prefill"
                else:
                    out["stage"] = "idle"
                out["active"] = any(s["is_processing"] for s in out["slots"])
        except Exception as e:  # noqa: BLE001
            _log.debug("slots failed on %s: %s", srv["port"], e)
    return out


def build_server_sample(srv: dict) -> dict:
    """One card's data = http probe + journal inference + status classification.

    Classification is **/slots-authoritative**: the API knows whether a slot is
    processing RIGHT NOW, so it decides busy/idle and prefill/decode. The
    journal (n_gen/tg) supplies speed + MTP + last-task numbers.
      * API active  → busy  (stage = busiest slot)   ← server is alive
      * API idle    → idle  (loaded, no task)
      * API down    → standby (on-demand) / down|degraded (resident)
    Hang = API says decode, but n_gen hasn't grown across successive polls
    (the one real "frozen" case). Prefill never flags stale — it legitimately
    emits no n_gen lines.
    """
    http = sample_server_http(srv)
    inf = sample_server_inference(srv)
    mode = srv.get("mode", "resident")
    unit = srv.get("journal_unit", "")
    port = srv["port"]
    api_active = bool(http.get("active"))
    api_stage = http.get("stage") or "idle"   # idle | prefill | decode

    # ── model size + parameters (from /v1/models meta, API-authoritative) ──
    meta = http.get("meta") or {}
    n_params = meta.get("n_params")
    n_ctx_api = meta.get("n_ctx")
    file_bytes = meta.get("size")
    ftype = meta.get("ftype") or ""
    # Format params: 27,320,697,856 → "27.3B"
    params_label = None
    if n_params:
        pb = n_params / 1e9
        if pb >= 1:
            params_label = f"{pb:.1f}B".replace(".0B", "B")
        else:
            params_label = f"{int(n_params / 1e6)}M"
    # File size in GB
    file_gb = None
    if file_bytes:
        file_gb = round(file_bytes / (1024 ** 3), 1)
    # Context from API (authoritative; /slots may override per-slot)
    ctx_tokens = n_ctx_api  # e.g. 262144
    # Per-slot ctx usage: SUM n_prompt_tokens across ALL slots (total context in use)
    ctx_used_tokens = 0
    if http.get("slots"):
        for sl in http["slots"]:
            pt = sl.get("prompt_tokens", 0) or 0
            ctx_used_tokens += pt

    # --- classify status (API is the source of truth for "right now") ------
    # NOTE: this llama.cpp build keeps n_prompt_tokens growing through decode
    # (n_prompt_tokens_processed stays at the prefill length), so /slots CANNOT
    # distinguish prefill from decode. The journal n_gen progress line is the
    # reliable decode marker → prefer it when the API says "prefill".
    if http["up"]:
        if api_active:
            stage = api_stage
            if stage == "prefill" and inf.get("stage") == "decode" and inf.get("tps") is not None:
                stage = "decode"   # n_gen is flowing → actually decoding
            status, stage = "busy", stage
        else:
            status, stage = "idle", "idle"
    else:
        if mode == "on-demand":
            status, stage = "standby", "idle"   # proxy idle-stopped → NORMAL
        else:
            svc_active = _service_active(unit) if unit else False
            status, stage = ("degraded" if svc_active else "down"), "idle"

    # --- decode progress tracking (hang detection, watchdog pattern) -------
    # During active decode llama.cpp logs n_gen every ~3s, so the token count
    # should grow each poll. If it stays flat for HANG_THRESHOLD seconds while
    # the API still says "decoding", the server is almost certainly frozen.
    # Prefill emits NO n_gen lines → never enters this branch (stage!=decode).
    hang = False
    HANG_THRESHOLD = max(int(CFG.get("live_token_poll_sec", 3)) * 2 + 4, 10)
    if status == "busy" and stage == "decode":
        ngen_now = int(inf.get("tokens") or 0)
        now = time.time()
        rec = PROGRESS.get(port)
        if rec is not None and ngen_now > rec.get("ngen", -1):
            PROGRESS[port] = {"ngen": ngen_now, "stuck_since": None}  # progress → reset
        else:
            if rec is None:
                PROGRESS[port] = {"ngen": ngen_now, "stuck_since": now}
            elif rec.get("stuck_since") is None:
                rec["stuck_since"] = now
            else:
                hang = (now - rec["stuck_since"]) > HANG_THRESHOLD
    else:
        PROGRESS.pop(port, None)

    # --- stale: journal line age (informational; NOT a hang signal) --------
    stale = False
    if inf.get("last_seen"):
        try:
            ls = datetime.datetime.fromisoformat(inf["last_seen"])
            stale = (datetime.datetime.now() - ls).total_seconds() > STALE_S
        except Exception:  # noqa: BLE001
            stale = False

    return {
        "port": srv["port"],
        "label": srv.get("label", str(srv["port"])),
        "mode": mode,
        "journal_unit": unit,
        "status": status,           # busy | idle | standby | degraded | down
        "stage": stage,             # idle | prefill | decode
        "up": http["up"],
        "model": http["model"],
        "version": http["version"],
        "size": http.get("size"),
        "params": params_label,
        "file_gb": file_gb,
        "ftype": ftype,
        "ctx_tokens": ctx_tokens,
        "ctx_used_tokens": ctx_used_tokens,
        "slots": http["slots"],
        # active: journal's "active" lags (last-run residue) — only trust it while
        # the server is actually up, so an unloaded on-demand server reads active=false.
        "active": bool(http.get("active")) or (bool(inf.get("active")) and http["up"]),
        "stale": stale,
        "hang": hang,
        # error: a standby (on-demand, backend stopped) probe failure is EXPECTED,
        # not an error — suppress it so standby cards don't show a red error line.
        "error": None if status == "standby" else http["error"],
        # inference (journal)
        "tokens": inf["tokens"],
        "tps": inf["tps"],
        "tps_3s": inf["tps_3s"],
        "final_tokens": inf["final_tokens"],
        "final_tps": inf["final_tps"],
        "prompt_tokens": inf["prompt_tokens"],
        "prompt_tps": inf["prompt_tps"],
        "prompt_ms": inf["prompt_ms"],
        "mtp_accept": inf["mtp_accept"],
        "mtp_mean_len": inf["mtp_mean_len"],
        "mtp_accepted": inf["mtp_accepted"],
        "mtp_generated": inf["mtp_generated"],
        "total_ms": inf["total_ms"],
        "session_tokens": inf["session_tokens"],
        "truncated": inf["truncated"],
        "task_id": inf["task_id"],
        "last_seen": inf["last_seen"],
        "log_ok": inf["log_ok"],
    }


# ---------------------------------------------------------------------------
# Sampler thread + ring buffer (system trend)
# ---------------------------------------------------------------------------

def build_system_sample() -> dict:
    return {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": time.time(),
        "gpu": sample_gpu(),
        "cpu": sample_cpu(),
        "storage": sample_storage(),
    }


STATE = {"latest_system": None}
HISTORY = deque(maxlen=CFG["history_points"])
SERVER_STATE = {}   # port → latest server sample
# External fan (ESP32) — latest report: rpm + LED color. Served to the
# dashboard via GET /api/external-fan; fed to the ESP32 via
# GET /api/external-fan/temp (contract: esp32-fan-controller.md §5.2).
FAN_STATE = {"rpm": None, "led": None, "last_ts": None, "last_epoch": 0.0}
# Per-port decode-progress tracker: (n_gen, epoch) of the last poll where the
# server was actively decoding. Used to detect a hang — API says "decoding"
# but n_gen hasn't grown across successive polls.
PROGRESS = {}
LOCK = threading.Lock()


def sampler_loop():
    while True:
        sys_sample = build_system_sample()
        with LOCK:
            STATE["latest_system"] = sys_sample
            HISTORY.append(sys_sample)
        time.sleep(CFG["sample_interval_sec"])


def servers_loop():
    """Sample every configured server on the live-token cadence.
    Journal timing lines arrive every ~3s during a task, so 3s keeps the
    cards in sync; the /slots API also updates live."""
    while True:
        for srv in CFG["servers"]:
            try:
                sample = build_server_sample(srv)
            except Exception as e:  # noqa: BLE001
                _log.warning("server %s sample failed: %s", srv["port"], e)
                sample = {"port": srv["port"], "label": srv.get("label"),
                          "status": "down", "stage": "idle", "up": False,
                          "error": str(e)}
            with LOCK:
                SERVER_STATE[srv["port"]] = sample
        time.sleep(int(CFG.get("live_token_poll_sec", 3)))


threading.Thread(target=sampler_loop, name="sampler", daemon=True).start()
threading.Thread(target=servers_loop, name="servers", daemon=True).start()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    # Static "Last Updated": the app's own modification time (not the
    # dynamic data-refresh timestamp the dashboard used to show here).
    app_mtime = time.strftime("%Y-%m-%d %H:%M:%S",
                              time.localtime(os.path.getmtime(__file__)))
    return render_template("index.html", app_mtime=app_mtime)


@app.route("/api/health")
def health():
    with LOCK:
        latest = STATE["latest_system"]
        servers = list(SERVER_STATE.values())
    any_up = any(s.get("up") for s in servers)
    return jsonify({
        "status": "ok" if (latest and any_up) else "stale",
        "ts": latest["ts"] if latest else None,
        "gpu_available": (latest or {}).get("gpu", {}).get("available"),
        "servers_up": sum(1 for s in servers if s.get("up")),
        "servers_total": len(CFG["servers"]),
    }), 200


@app.route("/api/servers")
def api_servers():
    """One entry per server card, in config order."""
    with LOCK:
        items = [dict(SERVER_STATE[s["port"]]) for s in CFG["servers"]
                 if s["port"] in SERVER_STATE]
        latest = STATE["latest_system"]
    return jsonify({"ts": latest["ts"] if latest else None, "servers": items})


@app.route("/api/status")
def api_status():
    """Latest system sample (CPU/GPU/RAM/Storage) for the 1st-row cards."""
    with LOCK:
        latest = STATE["latest_system"]
    if latest is None:
        return jsonify({"error": "sampler not ready yet, retry in 2s"}), 503
    return jsonify(latest)


@app.route("/api/history")
def api_history():
    with LOCK:
        items = list(HISTORY)
    if len(items) > 240:
        step = len(items) // 240
        items = items[::step]
    return jsonify([
        {"t": s["epoch"],
         "cpu": (s.get("cpu") or {}).get("util_pct"),
         "util": s["gpu"]["util_pct"],
         "vram": (s["gpu"]["vram_proc_mib"] or 0) / 1024.0,
         "ram": (s["gpu"]["ram"]["used_gb"])}
        for s in items
    ])


# ---------------------------------------------------------------------------
# External fan (ESP32) endpoints
# ---------------------------------------------------------------------------

@app.route("/api/external-fan/temp")
def ext_fan_temp():
    """Temperature source for the ESP32 fan controller.
    Contract (esp32-fan-controller.md §5.2): value < 0 = unavailable →
    the controller enters safe mode (80% fan, yellow LED)."""
    with LOCK:
        s = STATE["latest_system"]
    stale = s is None or (s.get("epoch") or 0) < time.time() - 30
    if stale:
        return jsonify({"gpu_temp_c": -1.0, "cpu_temp_c": -1.0})
    return jsonify({
        "gpu_temp_c": (s.get("gpu") or {}).get("temp_c"),
        "cpu_temp_c": (s.get("cpu") or {}).get("temp_c"),
    })


@app.route("/api/external-fan", methods=["GET", "POST"])
def ext_fan():
    """POST = ESP32 reports {fan_rpm, led_r/g/b}; GET = dashboard reads it."""
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        rpm = payload.get("fan_rpm")
        led = [payload.get("led_r"), payload.get("led_g"), payload.get("led_b")]
        if any(x is None for x in led):
            led = None
        with LOCK:
            FAN_STATE["rpm"] = int(rpm) if isinstance(rpm, (int, float)) else None
            FAN_STATE["led"] = led
            FAN_STATE["last_ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
            FAN_STATE["last_epoch"] = time.time()
        return jsonify({"status": "ok"})
    with LOCK:
        snap = dict(FAN_STATE)
    return jsonify({
        "fan_rpm": snap["rpm"],
        "led_rgb": snap["led"],
        "last_ts": snap["last_ts"],
        "last_epoch": snap["last_epoch"],
        "online": (time.time() - snap["last_epoch"]) < 30,
    })


@app.route("/api/speed-test", methods=["POST"])
def speed_test():
    """REAL inference test against a named server (generate N tokens, time it)."""
    st = CFG["speed_test"]
    if not st.get("enabled", True):
        return jsonify({"error": "speed test disabled in config.yaml"}), 403
    secret = st.get("secret", "")
    if secret and request.headers.get("X-Monitor-Secret", "") != secret:
        return jsonify({"error": "bad secret"}), 401

    payload = request.get_json(silent=True) or {}
    port = payload.get("port")
    srv = next((s for s in CFG["servers"] if s["port"] == port), None)
    if not srv:
        srv = CFG["servers"][0]
    base = f"http://127.0.0.1:{srv.get('backend_port', srv['port'])}"
    num_predict = int(st.get("num_predict", 256))
    try:
        r = requests.post(
            base + "/v1/completions",
            json={"prompt": "Write a short, friendly greeting.",
                  "max_tokens": num_predict, "temperature": 0.5, "stream": False},
            timeout=st.get("timeout_sec", 180),
        )
        r.raise_for_status()
        j = r.json()
    except Exception as e:  # noqa: BLE01
        _log.error("speed test failed: %s", e)
        return jsonify({"error": str(e)}), 502

    usage = j.get("usage", {})
    n = usage.get("completion_tokens") or 0
    # llama.cpp returns t/s in some builds; fall back to a wall-clock estimate
    tps = None
    if "tokens_per_second" in j:
        tps = round(j["tokens_per_second"], 1)
    return jsonify({"status": "success", "port": srv["port"],
                    "model": srv["label"], "tokens": n, "tps": tps,
                    "raw": {k: j.get(k) for k in ("usage", "created_at")}})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _log.info("starting llama-monitor on %s:%s (%d servers: %s)",
              CFG["host"], CFG["port"], len(CFG["servers"]),
              [s["port"] for s in CFG["servers"]])
    serve(app, host=CFG["host"], port=CFG["port"], threads=4)
