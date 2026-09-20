# Ollama 설치 (AI TOP Atom)

[summary] `ai top atom` GPU 머신에 Ollama를 단일 커맨드로 설치하고 첫 모델을 검증하는 절차.

## 1. 환경

| 항목 | 값 |
|---|---|
| 호스트 | Haee — AI TOP Atom (GB10, 128GB 통합 메모리) |
| OS | Ubuntu Linux |
| Ollama 경로 | `/usr/share/ollama/` |
| LAN IP | 192.168.219.115 |

## 2. 설치

SSH 터미널로 Haee에 접속한 상태에서:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

- 스크립트가 NVIDIA/CUDA 드라이버를 자동 감지해 최적화 설치를 수행
- 루트 비밀번호를 요구하면 Haee 계정 비밀번호 입력

## 3. 검증

```bash
sudo systemctl status ollama
```

`Active: active (running)` 확인. `q`로 빠져나오기.

## 4. 첫 모델 다운로드

```bash
ollama run llama3.1
```

- 약 4.7GB 모델 다운로드 게이지 → 100% → 대화 프롬프트 `>>>`
- `Hi, introduce yourself.` → GPU 가속 답변 확인
- `/bye` 로 종료

## 5. 실사용 모델 풀

| 모델 | 용도 |
|---|---|
| `qwen3.8:27b` | coding (Q4_MTP, 128K ctx) |
| `gemma4:26b` | english 페르소나 |
| `llama3.3:70b` | 고성과 대형 |
| `muse-glimmer:30b` | 실험용 |

```bash
ollama pull qwen3.8:27b
ollama pull llama3.3:70b
ollama pull gemma4:26b
ollama pull muse-glimmer:30b
```

## 6. 모델 스토리지 심볼릭 링크

기존 사용자 디렉터리와 통합할 때:

```bash
ln -s -f /usr/share/ollama/.ollama/models ollama_model
```

> 💡 **Tip:** `ai top atom`은 통합 메모리 128GB라 27B~70B 모델도 여유롭게 구동. VRAM 부족을 걱정할 수준이 아님을 유의.
