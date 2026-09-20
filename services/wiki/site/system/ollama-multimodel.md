# Ollama 다중 모델 동시 서빙

[summary] 두 개 이상의 모델을 VRAM/RAM에 함께 올려놓고 독립 프로필별 추론을 동시에 처리하는 `OLLAMA_MAX_LOADED_MODELS` 설정.

## 1. 왜 필요한가

| 프로필 | 모델 | 동시 사용 |
|---|---|---|
| coding | `qwen3.8:27b` | coding 채널 활성 시 |
| english | `gemma4:26b` | english 채널 활성 시 |
| default | (상기 공유) | — |

Ollama 기본값은 `OLLAMA_MAX_LOADED_MODELS=1` — 새 모델 요청 시 기존 모델을 메모리에서
빼고 새 모델을 올린다. 이 상태에서 두 채널이 동시에 요청하면 서로를 끌어내리면서
**서로 응답이 늦어진다.**

## 2. 핵심 환경 변수

| 변수 | 역할 | 기본값 | 권장 |
|---|---|---|---|
| `OLLAMA_MAX_LOADED_MODELS` | 동시에 상주 모델 수 | 1 | 3 |
| `OLLAMA_NUM_PARALLEL` | 모델당 동시 요청 수 | 1 | 2 |

## 3. Linux (systemd) 설정

```bash
sudo systemctl edit ollama.service
```

```ini
[Service]
Environment="OLLAMA_MAX_LOADED_MODELS=3"
Environment="OLLAMA_NUM_PARALLEL=2"
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

## 4. Windows (PowerShell)

```powershell
# Ollama 트레이 아이콘에서 Quit 한 후
$env:OLLAMA_MAX_LOADED_MODELS="3"
$env:OLLAMA_NUM_PARALLEL="2"
ollama serve
```

## 5. macOS

```bash
# Ollama 앱 종료 후
export OLLAMA_MAX_LOADED_MODELS=3
export OLLAMA_NUM_PARALLEL=2
ollama serve
```

## 6. 메모리 계산

| 모델 | Q4 quant 규모 |
|---|---|
| qwen3.8:27b | ~16.9 GB |
| gemma4:26b | ~15.5 GB |
| 합계 (2개 동시) | ~32 GB |
| 통합 RAM | 128 GB |

> ✅ **결과:** 128GB 통합 메모리로 두 모델 동시 상주 여유 확보. context window 추가로
> VRAM/RAM을 더 소모하므로 `OLLAMA_NUM_PARALLEL`을 과도하게 올리지 말 것.
