#!/bin/sh
# @reboot health check after v0.21.6 update (2026-10-11)
OUT=/home/joons/.hermes/reboot-health.log
{
  echo "=== reboot health $(date '+%F %T') ==="
  for u in hermes-gateway-joons hermes-serve-9119 hermes-dashboard-9120 llama-monitor llama-proxy-34; do
    printf '%-24s %s\n' "$u" "$(systemctl --user is-active "$u" 2>/dev/null)"
  done
  echo "hermes --version: $(/home/joons/.local/bin/hermes --version 2>/dev/null | head -1 || hermes --version 2>/dev/null | head -1)"
  # 11534 (27B 상주 모델) — 부팅 직후 로드 중일 수 있으므로 짧게 대기
  for i in 1 2 3 4 5 6; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:11534/health 2>/dev/null)
    [ "$code" = "200" ] && break
    sleep 10
  done
  echo "11534 /health: $code"
  echo "5000 monitor:  $(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:5000/ 2>/dev/null)"
} >> "$OUT" 2>&1
