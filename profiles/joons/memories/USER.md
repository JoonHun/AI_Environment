Ko리언 사용자. 아주 긴 응답은 잘림(truncation) 에러 유발 → 짧게 핵심만, 긴 산출물은 파일로, 작업은 여러 작은 단계. "think off" = 긴 추론 서술 금지, 바로 실행해 간결하게 답할 것.
§
"hermes dashboard" = 브라우저 대시보드 http://IP:9120 (systemd hermes-dashboard-9120). 9/16 업데이트로 serve:9119는 데스크톱 전용 헤드리스(브라우저 404). "ollama-monitor" = GB10 services/ollama-monitor, port 5000.
§
환경: Gigabyte AI TOP ATOM(GB10, 128GB 통합메모리) 보유. 위계: Hermes desktop=로컬 PC(별도), gateway+에이전트+모델서빙=GB10(192.168.219.115). 내 terminal/execute_code는 GB10(게이트웨이 호스트)에서 실행됨 — ps/llama-server/ollama가 바로 보이는 이유.
§
Korean user prefers clear conceptual structures, text-based(ASCII) diagrams, checklists BEFORE execution. Dislikes sudden tool runs/black screens. "Why" 먼저: 현상(예 부팅 시 모델 자동로드)의 원인과 아키텍처를 도식화해 설명+방향(A/B)을 물어본 뒤 진행.
§
Arch: Dual Hermes Gateways for Discord routing — `--profile coding --port 8601` (qwen3.6) + `--profile english --port 8602` (gemma4), each mapped to specific channels. Ollama on GB10 set with `OLLAMA_MAX_LOADED_MODELS=3` for dual-model concurrent loading via 128GB unified memory.
§
작업 경계: 지시 한계에서 멈춤. 범위 넘어선 자동 진행 싫어함 → 명시적 승인 전 다음 단계 금지. 하나씩 진행; 코드만 수정하고 마지막에 한 번에 reload (매번 restart 금지).
§
아들이 영어 학습 중(text 기반). 사용자는 아들 말하기·듣기 실전 경험을 주고 싶어 함 — 이 게 음성 관련 요구의 실제 동기. 로컬(GB10+Ollama) 우선, 도커는 복잡성 때문에 꺼려함. Discord 실시간 음성채널 구현은 기술장벽이 커서 스스로 보류.
§
교과서 PDF 저장: 원본 고화질만 — 경량/압축본 불필요 (압축 스킵 지시).