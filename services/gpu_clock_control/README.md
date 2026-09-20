# GPU Clock Control

GB10 (Grace Blackwell Superchip) GPU 클럭 캡을 관리하는 서비스.

## 목적

- GB10 GPU 발열 억제: 클럭을 최대 2000MHz로 제한하여 전력/발열 감소
- 멀티 모델 동시 구동(2개 모델) 시에도 온도가 안정적으로 유지되도록 관리
- 리부팅 시에도 자동 적용되도록 systemd 서비스로 영구화

## 배경

| 항목 | 값 |
|---|---|
| GPU | NVIDIA GB10 (Grace Blackwell Superchip) |
| 통합 메모리 | 128GB LPDDR5X (CPU/GPU 공유) |
| 기본 최대 클럭 | 3003 MHz |
| 설정 전 SM 클럭 | 2489 MHz (실측) |
| 설정 전 전력 | 59W |
| 설정 전 온도 | 48~52°C |
| 설정 후 SM 클럭 | 1989 MHz (cap 2000MHz) |
| 설정 후 전력 | 36~37W (~38% 절감) |
| 설정 후 온도 | 57~58°C (95% 부하 기준) |

### 왜 클럭을 낮추는가?

1. **발열 억제** — 클럭을 낮추면 전력이 줄고 발열이 감소
2. **멀티 모델 안정성** — 2개 모델 동시 구동 시에도 온도가 안정적으로 유지
3. **전력 절감** — 59W → 36W (약 38% 감소)

### GB10 특수사항

- 메모리 클럭은 `nvidia-smi -lmc`로 조절 불가 (통합 메모리, 시스템 컨트롤러 관할)
- `-lgc`는 **Graphics/SM 클럭만** 조절 가능
- Memory Clock, Max Operating Temp 등은 `N/A`로 노출 (엔드포인트 비어있음)

## 수행 과정

### 1단계: 현재 상태 확인

```bash
nvidia-smi
nvidia-smi -q -d CLOCK,TEMPERATURE,PERFORMANCE
nvidia-smi --query-gpu=temperature.gpu,power.draw,utilization.gpu,clocks.sm --format=csv
```

### 2단계: 클럭 cap 설정 (런타임)

```bash
sudo nvidia-smi -lgc 300,2000
# → "GPU clocks set to (gpuClkMin 300, gpuClkMax 2000) for GPU 0000000F:01:00.0"
```

### 3단계: 적용 확인

```bash
nvidia-smi -q -d CLOCK,TEMPERATURE,PERFORMANCE | grep -E "Graphics|SM|Applications"
# → Graphics: 1989 MHz (cap 2000MHz 아래 정상 동작)

nvidia-smi --query-gpu=temperature.gpu,power.draw,utilization.gpu,clocks.sm --format=csv
# → 58°C, 36.7W, 95%, 1989 MHz
```

### 4단계: systemd 서비스로 영구화 (리부팅 시 자동 적용)

```bash
sudo nano /etc/systemd/system/nvidia-gpu-clkcap.service
```

```ini
[Unit]
Description=NVIDIA GPU Clock Cap (300-2000 MHz)
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/nvidia-smi -lgc 300,2000
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable nvidia-gpu-clkcap.service
sudo systemctl start nvidia-gpu-clkcap.service
```

### 5단계: 확인

```bash
sudo systemctl status nvidia-gpu-clkcap
nvidia-smi --query-gpu=clocks.sm --format=csv
```

## 심볼릭 링크에 대해

`sudo systemctl enable` 실행 시 아래와 같은 심볼릭 링크가 생성됩니다:

```
Created symlink /etc/systemd/system/multi-user.target.wants/nvidia-gpu-clkcap.service
              → /etc/systemd/system/nvidia-gpu-clkcap.service
```

### 심볼릭 링크란?

실제 파일의 **위치를 가리키는 축자(지시 메모)** 입니다. 파일 자체가 아니라 "그 파일이 어디에 있는지"를 가리킵니다.

```
실제 파일 (본체)
/etc/systemd/system/nvidia-gpu-clkcap.service
        ↑
        │  (가리킴)
        │
심볼릭 링크 (축자)
/etc/systemd/system/multi-user.target.wants/nvidia-gpu-clkcap.service
```

### 왜 systemd가 이렇게 만들까?

`multi-user.target.wants/` 폴더 = **"일반 부팅 모드에 도달하면 실행할 서비스 목록"**

```
부팅 → multi-user.target 도달
     → wants/ 폴더에서 심볼릭 링크 발견
     → 링크가 가리키는 실제 파일 읽기
     → nvidia-smi -lgc 300,2000 실행
```

### enable / disable = 등록 / 삭제

| 명령어 | 동작 |
|---|---|
| `systemctl enable` | wants/ 폴더에 심볼릭 링크 **추가** (실행 목록 등록) |
| `systemctl disable` | wants/ 폴더의 심볼릭 링크 **삭제** (실행 목록에서 제거) |

본체 파일은 enable/disable에 의해 **삭제되지 않습니다.**

### 확인 방법

```bash
ls -la /etc/systemd/system/multi-user.target.wants/ | grep nvidia-gpu-clkcap
# nvidia-gpu-clkcap.service -> /etc/systemd/system/nvidia-gpu-clkcap.service
```

`→` 화살표로 어디를 가리키는지 바로 확인됩니다.

## 명령어 cheatsheet

| 명령어 | 설명 |
|---|---|
| `sudo nvidia-smi -lgc 300,2000` | 클럭 cap 설정 (300~2000MHz) |
| `sudo nvidia-smi -rgc` | 클럭 cap 해제 (기본값 복귀) |
| `nvidia-smi --query-gpu=clocks.sm --format=csv` | 현재 SM 클럭 확인 |
| `nvidia-smi -q -d CLOCK,TEMPERATURE,PERFORMANCE` | 상세 정보 |
| `sudo systemctl status nvidia-gpu-clkcap` | 서비스 상태 |
| `sudo systemctl disable nvidia-gpu-clkcap` | 서비스 비활성화 |
| `sudo systemctl enable nvidia-gpu-clkcap` | 서비스 활성화 |

## 주의사항

- `nvidia-smi -lgc`는 **런타임 설정** — 리부팅 시 원복됨
- 영구 적용은 systemd 서비스 또는 부팅 스크립트 필요
- 클럭을 낮추면 **추론 속도가 감소** (trade-off)
- GB10은 메모리 클럭 조절 불가 — SM 클럭만 조절 가능
- 2개 모델 동시 구동 시 메모리 대역폭 경쟁으로 체감 속도 저하 (물리적 한계)

## 해제 시 주의 (두 축이 독립적)

> ⚠️ **(1) 런타임 cap**과 **(2) 부팅 자동 적용**은 서로 독립적. 한 축만 건드려도 다른 축은 그대로.

| 상황 | 명령어 | 지금 세션 | 리부팅 후 |
|---|---|---|---|
| 잠깐 (세션만) 해제 | `sudo nvidia-smi -rgc` | cap OFF | ⚠️ 다시 ON |
| 다시 걸기 | `sudo nvidia-smi -lgc 300,2000` | cap ON | ON 유지 |
| 영구 자동 적용 끄기 | `sudo systemctl disable nvidia-gpu-clkcap` | ⚠️ cap 그대로 ON | OFF |
| **영구 끄기 + 지금도 풀기** | `disable --now` **+** `-rgc` | cap OFF | OFF |

**두 가지 함정**

1. **`-rgc`만 하면 → 리부팅하면 다시 cap이 걸린다.** 서비스는 여전히 `enabled`이라 부팅 시 `-lgc 300,2000`이 다시 실행.
2. **`disable --now`만 하면 → 지금 세션 cap은 안 풀린다.** `--now`(=stop)가 유닛 상태만 바꿀 뿐, 드라이버의 실제 클럭 설정은 건드리지 않음.

**영구 끄기 (2줄)**

```bash
sudo systemctl disable --now nvidia-gpu-clkcap   # 부팅 자동 적용 해제
sudo nvidia-smi -rgc                              # 지금 세션 cap도 즉시 해제
```

**다시 켜기 (1줄)**

```bash
sudo systemctl enable --now nvidia-gpu-clkcap
```

> 💡 `disable`은 유닛 파일을 지우는 게 아니라 **심볼릭 링크(자동 실행 등록)만** 제거한다.

## 파일 구조

```
gpu_clock_control/
├── README.md          # 이 문서
├── set_clock.sh       # 클럭 cap 설정 스크립트
├── reset_clock.sh     # 클럭 cap 해제 스크립트
├── status.sh          # 현재 상태 조회 스크립트
└── gpu-clkcap.service # systemd 유닛 파일 (복사용)
```

## 참고

- 설정일: 2026-09-10
- 장비: Gigabyte AI TOP ATOM (GB10)
- OS: Linux 6.17.0-1031-nvidia
- Driver: 580.173.02
- CUDA: 13.0
