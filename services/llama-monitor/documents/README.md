# llama-monitor 문서

이 디렉토리는 `/home/joons/.hermes/services/llama-monitor/` 서비스의 문서를 담는다.

| 문서 | 내용 |
|---|---|
| [requirements.md](requirements.md) | **주 문서** — llama.cpp `llama-server`용 상태 대시보드의 시스템 요구사항 (ollama-monitor 분석 기반) |
| [log-format.md](log-format.md) | **파서 계약** — 실제 로그 388줄 검증: 진행/완료/MTP 라인 포맷, 정규식 9종, `/slots` API, Ollama와의 차이 |
| [PROGRESS.md](PROGRESS.md) | **진행 체크포인트** — 완료/다음 단계/주의 (세션 이어서 작업할 때 먼저 읽기) |

## 한줄 요약

LAN PC의 브라우저에서 `http://192.168.219.115:5002`을 열면
시스템(CPU/GPU/Memory/Storage) + 추이 + **포트별 서버 카드 4개**(11534~11537)를
볼 수 있다. 각 카드 = 1 포트 = 1 모델(llama.cpp는 포트:모델 1:1)로,
**모델 + 상태 스테퍼(Idle→Prefill→Decode) + prefill/decode t/s + MTP**를
한 화면에서 보여서 요청이 **추론 중인지 멈췄는지**를 즉시 판단한다.

## 관련

- 기존 Ollama용: `../../ollama-monitor/documents/` (같은 패턴의 검증된 구현)
