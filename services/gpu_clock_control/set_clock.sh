#!/usr/bin/env bash
# set_clock.sh — GPU 클럭 cap 설정
# 용도: nvidia-smi -lgc로 Graphics/SM 클럭 상한 고정
# 사용: sudo bash set_clock.sh [min,max]   (기본 300,2000)

set -euo pipefail

CLOCK_RANGE="${1:-300,2000}"

echo "→ GPU 클럭 cap 설정: ${CLOCK_RANGE} MHz"
sudo nvidia-smi -lgc "${CLOCK_RANGE}"

echo "→ 적용 확인:"
nvidia-smi --query-gpu=clocks.sm,power.draw,temperature.gpu --format=csv
