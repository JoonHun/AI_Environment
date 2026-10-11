Arch: 2개 Hermes profile Gateway(systemd user 서비스, 포트 불필요)로 Discord 멀티봇 구동. coding=Qwen, english=Gemma. Ollama OLLAMA_MAX_LOADED_MODELS=3 → 2모델 동시 적재(GB10 128GB 통합메모리).
§
Hermes Discord 연결 시 3단계 게이트: 1) DISCORD_BOT_TOKEN(프로파일 .env), 2) DISCORD_ALLOWED_USERS(게이트웨이 인증, default-deny), 3) DISCORD_FREE_RESPONSE_CHANNELS(멘션 없이 응답). 세 개 모두 프로파일 .env 필요.
§
Ollama: GB10 메모리 대역폭 제한. Qwen 27B decode Q4_K_M~26.2>Q8~18.9 tok/s(단독MTP,draft=4). NVFP4는 sm_121+Ollama0.32 비결정론적(안정화 전 비권장). MTP 효과 큼. Modelfiles: ~/ollama-modelfiles, 접미 _Q4|_Q8.
§
GitHub: JoonHun (joonhun.shin@gmail.com) — private repo JoonHun/hermes-config tracks ~/.hermes (profiles/coding·english config·SOUL·skills·memories, skills, services/ollama-monitor, desktop-plugins). Git 2.43, global user=joonhun, defaultBranch=default, credential.helper=store(~/.git-credentials). .gitignore excludes .env/auth.json/*.db/venv/caches/logs. hermes-agent/ has own git, not tracked.
§
Ollama 모델명 규칙: <패밀리>_<파라미터>_<컨텍스트>K[_확장] (예: qwen3.8_27B_128K_Q4) — 그룹핑은 첫 '_' 앞 문자열(qwen3.8, qwen3.6 별도). alias는 <패밀리>:<파라미터>b. ollama-monitor 그룹핑 시 _ 기준(알파벳 접두 아님).
§
프로파일별 모델(9/18): default=qwen3.8-27b-mtp-q4_k_m@11534(상주), coding=qwen3.6-35b-a3b@11535, english=gemma-4-E4B-q4_k_m@11536(on-demand,MTP Q8draft+mmproj). 전부 llama.cpp, Ollama(11434) 동결.
§
coding 포트(11535/llama-server-coding) 모델은 사용자가 자유롭게 바꿔 테스트 중 — 특정 모델 고정으로 간주 금지. 9/27엔 gpt-oss-120b-MXFP4 적재 확인.
§
wiki: ~/.hermes/services/wiki — 페이지 site/<섹션>/<slug>.md + nav.yaml 등록 + server.py :5001. gpu_clock_control: GB10 클럭cap 300-2000, systemd nvidia-gpu-clkcap(-lgc/-rgc), doc=wiki system/gpu-clock-control.
§
사용자는 배운 내용을 개인 wiki에 문서화하길 원함(목적+수행과정+함정 상세 기록).
§
11534(27b)만 항상 상주, 11535/11536/11537=on-demand(proxy 첫 POST 시 backend 시작). 보조모델로 작업 시 로딩수십초+대역폭경쟁 발생. 압축 트리거=토큰수(75%)라 KV양자화 무관.
§
비전: gemma4:26b(MoE,~18GB) Ollama 11434에 설치 — 한글 OCR/전사 OK(사용자 지정). vision_analyze는 메인모델(qwen3.8,비전없음)로 라우팅→500; 이미지 전사는 gemma4 chat API images[base64] 직접 호출.
§
명령 규율(반복 실수 방지, 사용자 강요청): '제시/방법 알려줘'=tool call 0회, 텍스트만. 명시적 '진행해/적용해/수정해' 후 실행. tool call 직전 첫 줄에 '지시:… / 할 일:…' 1줄. 승인 범위 이상(추가 변경 끼워넣기) 절대 금지. approvals.mode=manual로 시스템 강제 활성. git 개념은 표준 용어 그대로(upstream/fork/main) — 비유어(본가 등)는 혼란 유발.