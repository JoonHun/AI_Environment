# llama-monitor — 진행 체크포인트 (2026-09-10)

> 다음 세션에서 바로 이어서 작업하기 위한 상태 기록.
> 완료/진행중/다음 단계가 명확히 구분된다.
> **마지막 업데이트**: 2026-09-10 오후 (디자인 이식·레이아웃·카드 UI·stage 버그 수정 완료)

---

## 1. 목표
원격에서 요청을 보냈을 때 "동작 중인지 / 추론 중인지 / 멈췄는지"를
`http://192.168.219.115:5002` 대시보드로 즉시 판단하는 도구.
ollama-monitor(5000)의 검증된 뼈대(디자인 포함)를 재사용하되 **llama.cpp 다중 인스턴스**에 맞춤.

---

## 2. 완료 ✅

### 2.1 문서 (`documents/`)
- `requirements.md` — FR/API/UI/config/인수기준, `/slots` API 권위 + 포트별 카드 반영
- `log-format.md` — 실제 로그 388줄 검증된 파서 정규식 9종 + `/slots` 스키마
- `README.md` — 인덱스
- `PROGRESS.md` — 이 파일

### 2.2 인프라
- **venv** — ollama-monitor venv 복사 (flask/waitress/requests/yaml 확인)
- **config.yaml** — 4서버 정의
  - 11534 joons (상시) · 11535→1536 coding · 11536→1537 fallback · 11537→1538 english (온디맨드)
  - `backend_port` 분리 (proxy 프론트는 raw TCP tunnel이라 probe 금지 — 시작 시켜버림)
- **systemd user service** — `~/.config/systemd/user/llama-monitor.service`
  - `Restart=always`, `RestartSec=3`, `PYTHONUNBUFFERED=1`, `WantedBy=default.target`
  - `daemon-reload` + `enable --now` 완료. **kill 테스트로 자동 재기동 확인**(restart counter=1)
  - 부팅/세션 종료에도 살아남음 (linger 설정 여부는 별도)
  - 재기동: `systemctl --user restart llama-monitor.service` (문자열 pkill 금지 — shell 자신도 죽을 수 있음)

### 2.3 UI — ollama-monitor 디자인 완전 이식
- **Tailwind CDN + Inter 폰트 + Chart.js**, 다크 테마 `#0f172a`(body) / `#1e293b`(card)
- `text-4xl` 타이틀 + pulse 상태점, `font-mono` 수치 — ollama-monitor와 동일한 시각 언어
- 카드 12개 → 12개, 스크립트/스타일 전수 교체 (380줄 rewrite)
- **검증**: `Inter`·`cdn.tailwindcss.com`·`font-mono`·`status-pulse` 존재 / 구 테마(`#0f1117`,`#1a1d27`) 제거

### 2.4 용량 단위 통일 (GB, 소수 2자리)
- **계산**: 1000³(십진 GB), 라벨 "GB"
- **RAM 버그 수정**: `/proc/meminfo`의 "kB"는 실체 **KiB(1024B)** → `kB*1024/1000³`
  - 수정 전: 125.4 GB ❌ → 수정 후: **128.45 GB** ✓ (`free -b /1000³`와 정확히 일치)
  - 검증: `total(128.45) − used(43.61) == available(84.84)` ✓
- **Storage**: `shutil.disk_usage()`는 true bytes라 `÷1000³`이 처음부터 정확 → `/` = **982.82 GB**
  - 버그 1건: `storage[0]`이 `/boot/efi`(0.5GB)를 잡던 것 → **`/` 마운트 우선, 없으면 최대 마운트** 폴백
- **소수 2자리**: `app.py` `round(x, 2)` + UI `toFixed(2)` (Total 포함)
- 키명 `*_gib` → `*_gb` (app.py, index.html)

### 2.5 레이아웃 (3차 반복 → 최종 v3)
- **v1** 2단(좌 sticky | 우 scroll) → "이상해 졌어"
- **v2** 단일 세로 + sticky + 페이지 스크롤 → "세로 스크롤 어색해, 상단 정보 사라져"
- **v3 (최종)**:
  - `body h-screen overflow-hidden flex flex-col` → **페이지 스크롤 0**
  - 헤더 · 시스템 4카드 · Trend → `shrink-0` **절대 고정**
  - **`#servers`만 `flex-1 min-h-0 overflow-y-auto`** → 모델 카드 영역만 내부 세로 스크롤
  - 카드 1줄 1개(풀폭), config 순서(11534→11537)
  - **검증**: div 57/57, 순서 CPU→GPU→RAM→Storage→Trend→servers OK

### 2.6 서버 카드 UI 재구성 (사용자 지시 7건, 전부 반영)
1. **label(joons) 제거** — "다른 프로필이 같은 모델 쓰면 2개 표시되나?" → API가 config 고정 문자열만 반환(실시간 프로필 감지 불가) → UI에서 제거
2. **busy pill 제거** — stage 스테퍼와 100% 중복. `degraded/down`은 경고줄(⚠)이 커버
3. **모델 경로→이름만** — `s.model.split('/').pop()` basename, `title` attr으로 전체 경로
4. **헤더 순서**: `11534  Resident  qwen3.8-27b-mtp-q4_K_M.gguf  [스테퍼 우측 상단]`
5. **mode 라벨**: `resident` → **`Resident`**(카멜 케이스)
6. **4칸 stats** (grid-cols-4): **Prompt**(`prompt_tps`) · **Decode**(`tps`) · **3s avg**(`3s_tps`) · **Generated**(`tokens`)
   - 3칸→4칸: prefill t/s 누락 보완, "3초 평균" 문구 → "3s avg"
7. **MTP + Last request 1줄**: last(입력토큰·decode속도·최종생성토큰 순) 좌측 정렬 / MTP·mean/step 우측 정렬
8. **경고**: `Stale → hang → err` 순서, `else if`→독립 `if`(동시 해당 시 전부 출력)

### 2.7 카드 텍스트 **전수 영문화**
- `모델 로딩 안 됨 (standby)` → `model not loaded (standby)`
- `입력 처리` → `Prompt` · `평균` → `avg` · `3초 평균` → `3s avg`
- `서버 N/N up` → `N/N servers up` · `서버 샘플링 중… (3초 대기)` → `sampling servers… (wait 3s)`
- `<html lang="ko">` → `lang="en"` · 경고 `stale — no log update since` → 시간만

### 2.8 last_seen 표시 방식 (최종)
- **항상 표시**(stale 조건부 아님) — 깜빡임 제거
- `stale` 문구 제거 → **날짜+시간만**: `2026-09-10 16:37:42`
- ISO `T` 제거: `String.replace('T',' ').slice(0,19)`
- hang/err 경보는 그 아래 독립 출력

### 2.9 모델 이름 강조 (FOCUS)
- `text-sm text-slate-300`(14px 회색) → **`text-lg text-white font-bold`**(18px 흰색 굵게)
- 잘림 폭 `max-w-[320px]` → `max-w-[480px]`
- 카드 헤더의 주인공으로 가독성 확보

### 2.10 **stage 분류 버그 수정** (decode 중에도 Prefill이 켜진 현상) — 핵심
- **현상**: 모델 동작이 끝나도(또는 decode 중에도) 스테퍼가 Prefill에 머물러 있음
- **직접 측정으로 규명한 원인**: 이 llama.cpp build의 `/slots`는
  - `is_processing=True` 상태가 prefill+decode를 **구분 불가**
  - **`n_prompt_tokens`가 decode 중에도 계속 증가**(실제 누적 토큰), `n_prompt_tokens_processed`는 prefill 길이에서 멈춤
  - `n_decoded`는 처리 중 `None`
  - → 기존 `processed < tokens → prefill` 분류가 **decode 내내 prefill**로 오인
- **수정** (`app.py`): API가 busy인데 `stage=prefill`일 때, **journal이 decode를 말하면 journal 우선**
  ```python
  # API의 prefill/decode 분류는 이 build에서 신뢰 불가 (n_prompt_tokens가 decode 중에도 증가)
  # journal의 n_gen 진행은 decode의 확실한 증거 (prefill 중엔 n_gen 없음)
  if api_stage == "prefill" and inf["stage"] == "decode":
      stage = "decode"
  ```
- **검증**: 실제 `/v1/completions`(200토큰) 트리거 + monitor 0.5s 샘플링
  - `busy/prefill → busy/decode → idle` 전환 정상 확인 (decode 구간 journal 우선으로 decode)

---

## 3. 핵심 설계 결정 (이유)
- **`/slots` API = "지금 바쁨/가쁨"의 권위** — 그러나 이 build에서는 **prefill/decode 구분은 journal이 권위** (2.10 참조)
- **1 포트 = 1 모델 = 1 카드** (Ollama의 2카드 구조와 다름)
- **on-demand standby**: backend off는 정상(`standby`) — down으로 오인 금지
- **용량 = 1000³ GB** (사용자 선택), meminfo "kB"=KiB에 주의
- **레이아웃 v3**: 페이지 스크롤 0, 모델 카드 영역만 스크롤 — "상단 정보 항상 보임" 원칙
- **카드 텍스트 전부 영문** — 사용자가 지시

## 4. 다음 단계 ⬜
1. **온디맨드 서버(11535~11537) 실동작 검증** — 실제 요청 넣고 busy→idle 전환·standby 표시 확인
2. **브라우저에서 시각 최종 확인** — (agent는 API JSON으로만 검증, 스크린샷 미확인)
3. (선택) `POST /api/speed-test` 실측
4. (선택) `linger` 설정 — 세션 로그아웃 후에도 user service 유지
5. (선택) `/slots`가 `n_decoded`를 채우면 API 분류로 복귀 가능 — 향후 llama.cpp 업그레이드 시 재확인

## 5. 주의
- **ollama-monitor(5000)은 건드리지 말 것.** llama-monitor만 5002.
- 재기동: `systemctl --user restart llama-monitor.service`
- llama.cpp엔 `all slots are idle` 마커 **없음** — idle은 `/slots`로.
- `eval time`이 `prompt eval time`에 포함 → `(?<!prompt )` lookbehind 필수.
- **이 build의 `/slots`**: `n_prompt_tokens`는 decode 중에도 증가 — prefill/decode 구분 불가 (2.10)
- app.log에 `/run/user/1000/doc` WARNING 스팸(2초 주기) — 잡음, 무시

## 6. 변경 파일 현황
| 파일 | 변경 |
|---|---|
| `app.py` | RAM `kB*1024/1000³`·Storage `÷1000³`·`round(x,2)`·`*_gb` 키·**stage journal 우선 로직** |
| `templates/index.html` | ollama-monitor 디자인 + 레이아웃 v3 + 카드 UI 7건 + 전수 영문화 + 모델이름 강조 + last_seen 항상표시 |
| `config.yaml` | 4서버 정의 (미변경) |
| `~/.config/systemd/user/llama-monitor.service` | 신규 (user service) |
| `documents/PROGRESS.md` | 이 문서 |
