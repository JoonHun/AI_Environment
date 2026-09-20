Ko리언 사용자. 아주 긴 응답은 잘림(truncation) 에러를 반복해서 유발 → 응답은 짧게 핵심만, 긴 산출물은 파일로 전달, 작업은 여러 작은 단계로 나누라는 선호가 명시적으로 있음.
§
용어: 사용자 말 "hermes dashboard" = 웹 대시보드(http://IP:9119, Hermes Gateway) — 데스크톱 GUI가 아님. "ollama-monitor" = GB10 서버(192.168.219.115) ~/.hermes/services/ollama-monitor의 자체 Flask 대시보드, systemd user service 'ollama-monitor'로 port 5000 도중.
§
환경: Gigabyte AI TOP ATOM (GB10) 장비 보유 (NVIDIA GB10 Grace Blackwell Superchip, 128GB 통합 LPDDR5X 메모리). 로컬 Ollama 서버(192.168.219.115)로 활용 중.
§
Korean user prefers clear conceptual structures, text-based diagrams, and checklists BEFORE actual execution. Dislikes sudden tool runs or rendering failures (black screens).
§
Arch: Dual Hermes Gateways for Discord routing — `--profile coding --port 8601` (qwen3.6) + `--profile english --port 8602` (gemma4), each mapped to specific channels. Ollama on GB10 set with `OLLAMA_MAX_LOADED_MODELS=3` for dual-model concurrent loading via 128GB unified memory.
§
작업 경계: 지시 한계에서 멈춤을 명확히 요구함(예: “그 다음 진행하지마”). 범위 넘어선 자동 진행 싫어함 → 명시적 승인 전 다음 단계 개시 금지.