Arch: 2개 Hermes profile Gateway(systemd user 서비스, 포트 불필요)로 Discord 멀티봇 구동. coding=Qwen, english=Gemma. Ollama OLLAMA_MAX_LOADED_MODELS=3 → 2모델 동시 적재(GB10 128GB 통합메모리).
§
Hermes Discord 연결 시 3단계 게이트: 1) DISCORD_BOT_TOKEN(프로파일 .env), 2) DISCORD_ALLOWED_USERS(게이트웨이 인증, default-deny), 3) DISCORD_FREE_RESPONSE_CHANNELS(멘션 없이 응답). 세 개 모두 프로파일 .env 필요.
§
token-env 키는 이 Hermes 버전에서 미지원. 고정 env 키 DISCORD_BOT_TOKEN만 조회. 프로파일 .env에 DISCORD_BOT_TOKEN=으로 직접 기록.
§
Ollama Modelfiles: ~/ollama-modelfiles, 이름 규칙 Modelfile.<모델>_<크기>B_<컨텍스트>K[_MTP]_<Q4|Q8> (양자화 접미 항상 마지막, Q4=Q4_K_M). 커스텀 모델명은 <모델>-nctx-<ctxK>[-mtp] (예: qwen3.8-nctx-128k-mtp).
§
GitHub: JoonHun (joonhun.shin@gmail.com) — private repo JoonHun/hermes-config tracks ~/.hermes (profiles/coding·english config·SOUL·skills·memories, skills, services/ollama-monitor, desktop-plugins). Git 2.43, global user=joonhun, defaultBranch=default, credential.helper=store(~/.git-credentials). .gitignore excludes .env/auth.json/*.db/venv/caches/logs. hermes-agent/ has own git, not tracked.
§
Ollama 모델명 규칙: <패밀리>_<파라미터>_<컨텍스트>K[_확장] (예: qwen3.8_27B_128K_Q4) — 그룹핑은 첫 '_' 앞 문자열(qwen3.8, qwen3.6 별도). alias는 <패밀리>:<파라미터>b. ollama-monitor 그룹핑 시 _ 기준(알파벳 접두 아님).
§
프로파일별 모델(2026-08-27 정리): default=muse-glimmer_30B_128K_Q4_dflash(19.8G), coding=qwen3.6_35B_128K_Q4_CODING_MTP(22.6G). 커스텀명 접미는 base 구분자 반드시 보존(dflash·CODING_MTP 등, quant 접미 앞에). Ollama 리네임=재create+rm(레이어 공유, 즉시).
§
Project turzx_custom (~/.hermes/services/turzx_custom) - Turing screen monitoring for GB10. Status: Phase 2-A (Library Analysis). Architecture: Custom code referencing turing-smart-screen-python (no fork). Workflow: Req -> Design -> Impl -> Verify steps.
§
User prefers thorough planning (req→design→impl→verify) before execution. Explicitly corrected "let's plan first, not code first." Dislikes rushing into implementation without analysis.
§
Project "turzx_custom": Turing Smart Screen 9.2 (TUR_USB protocol) monitor for NVIDIA GB10. Features: Ollama API integration, GB10 unified memory metrics, SSH/HTTP-based screen saver. Tech: Python, psutil, nvidia-smi, PIL. Configurable via config.yaml + CLI configure.py. Dir: ~/.hermes/services/turzx_custom/.