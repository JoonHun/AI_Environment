#!/usr/bin/env bash
# reset_clock.sh — GPU 클럭 cap 해제 (기본값 복귀)
# 용도: nvidia-smi -rgc로 런타임 클럭 제한 해제
# 사용: sudo bash reset_clock.sh

set -euo pipefail

echo "→ GPU 클럭 cap 해제 (기본값으로 복귀)"
sudo nvidia-smi -rgc

echo "→ 현재 상태:"
nvidia-smi --query-gpu=clocks.sm,power.draw,temperature.gpu --format=csv
