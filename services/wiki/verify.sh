#!/usr/bin/env bash
set -u
B=http://127.0.0.1:5001
echo "=== listening on 5001? ==="
ss -ltn 2>/dev/null | grep ':5001 ' || echo "NOT LISTENING"
echo
echo "=== status codes ==="
for p in "" "p/system/hermes-agent-backend" "search?q=ollama" "p/nope/xyz"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$B/$p")
  echo "  /$p -> $code"
done
echo
echo "=== MASKING CHECK (want 0 leaks) ==="
html=$(curl -s "$B/p/system/hermes-agent-backend")
echo "  real password leaked?  -> $(echo "$html" | grep -c '112400')"
echo "  secret hex leaked?     -> $(echo "$html" | grep -c '3b48812349e9b94a037843469a89d23c')"
echo "  masked password shown? -> $(echo "$html" | grep -oE 'BASIC_AUTH_PASSWORD=***' | head -1)"
echo
echo "=== TOC anchors (want several ids) ==="
echo "  $(echo "$html" | grep -oE 'id=\"[a-z0-9-]+\"' | head -10 | tr '\n' ' ')"
echo
echo "=== code blocks + highlighting ==="
echo "  wiki-code blocks: $(echo "$html" | grep -c 'wiki-code')"
echo "  pygments spans:   $(echo "$html" | grep -c 'color:')"
echo
echo "=== nav label from nav.yaml (want: Hermes Agent 백엔드) ==="
echo "  $(curl -s http://127.0.0.1:5001/ | grep -oE 'Hermes Agent 백엔드' | head -1)"
echo "  section label     -> $(curl -s http://127.0.0.1:5001/ | grep -oE '시스템 환경 설정' | head -1)"
echo
echo "=== prev/next on page ==="
echo "  $(echo "$html" | grep -oE '(이전|다음)' | sort -u | tr '\n' ' ')"
