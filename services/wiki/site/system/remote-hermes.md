# 원격 Hermes 접속

[summary] Dall — Windows PC의 Hermes Desktop을 Haee — AI TOP Atom (GB10)의 Ollama 서버에 연결해 로컬 추론으로 에이전트를 돌리는 설정.

## 1. 목표

```
Dall (Hermes Desktop)  ──  LAN  ──  Haee Ollama  http://192.168.219.115:11434/v1
        (에이전트 호스트)                                  (추론 엔진)
```

## 2. Haee Ollama LAN 노출

Ollama는 기본 `127.0.0.1`만 허용. LAN으로 여는 환경변수:

```bash
sudo systemctl edit ollama.service
```

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
Environment="OLLAMA_CONTEXT_LENGTH=65536"
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

IP 확인:

```bash
hostname -I    # 192.168.219.115
```

> 🔒 **보안:** `OLLAMA_HOST=0.0.0.0`는 LAN 전체에 API를 노출한다. 신뢰할 수 없는
> 네트워크에 연결 시 반드시 방화벽으로 11434 포트를 제한할 것.

## 3. Dall Hermes Desktop 설치

Hermes Desktop 공식 앱(`.exe`)은 Python·Git 등 종속성을 자동 구성한다. 터미널 수동 설치 불필요.

## 4. Provider 연동

Hermes Desktop 설정에서:

| 필드 | 값 |
|---|---|
| Inference Provider | Custom / OpenAI Compatible (Ollama) |
| Endpoint URL | `http://192.168.219.115:11434/v1` |
| API Key | (공란) |
| Model Name | `qwen3.8:27b` (Haee에 이미 pull된 모델) |

> 💡 **Tip:** `base_url`에 `/v1` 접미어 포함이 필수다. Model_name은 Haee의
> `ollama list`에 있는 이름 그대로. 이 구성이 `profiles/`의 `provider: custom` 패턴과
> 동일한 원리다.

## 5. 작동 테스트

> *"현재 내 PC 시스템 환경을 점검하고 텍스트 파일로 요약 리포트를 만들어줘."*

에이전트 도구 자율 실행 + Haee 로컬 추론 속도를 함께 검증한다.
