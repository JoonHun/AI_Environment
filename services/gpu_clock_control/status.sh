#!/usr/bin/env bash
# status.sh — GPU 현재 상태 조회 (클럭/온도/전력/사용률)
# 용도: 발열·클럭·전력 한눈에 확인
# 사용: bash status.sh

set -euo pipefail

echo "=== GPU 상태 ==="
nvidia-smi --query-gpu=temperature.gpu,power.draw,utilization.gpu,clocks.sm,clocks.video,clocks.max.sm --format=csv
echo ""
echo "=== systemd 서비스 상태 ==="
systemctl is-active nvidia-gpu-clkcap 2>/dev/null || echo "nvidia-gpu-clkcap: (서비스 미설치)"
systemctl is-enabled nvidia-gpu-clkcap 2>/dev/null || true
