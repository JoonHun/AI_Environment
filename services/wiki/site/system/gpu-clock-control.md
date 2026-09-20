# GPU Clock Control (GB10)

[summary] GB10 GPU의 클럭 상한을 2000MHz로 고정해 발열·전력을 억제하고, systemd 서비스로 부팅 시 자동 적용하는 관리 서비스.

## 1. 목적

| 목표 | 효과 |
|---|---|
| 발열 억제 | 클럭 제한 → 전력 감소 → 발열 감소 |
| 멀티 모델 안정성 | 2개 모델 동시 구동 시에도 온도 안정 유지 |
| 전력 절감 | 59W → 36W (약 38% 감소) |
| 영구화 | 리부팅 후에도 자동 적용 (systemd) |

## 2. 배경 수치 (GB10)

| 항목 | 설정 전 | 설정 후 |
|---|---|---|
| SM(그래픽) 클럭 | 2489 MHz | **1989 MHz** (cap 2000) |
| Video 클럭 | 2184 MHz | 1664 MHz |
| Max Clock (HW 최대) | 3003 MHz | 3003 MHz (불변) |
| 전력 | 59 W | **36 W** |
| GPU 사용률 | 94~95% | 90~96% |
| 온도 | 48~52 °C | 57~60 °C (풀로드 기준) |

> 💡 **Tip:** 온도가 풀로드 시 오히려 오르는 이유는, 느린 클럭(1989MHz)으로 같은 부하를 처리하다 보니
> 처리 시간이 길어져 발열이 누적되기 때문. 전력은 확실히 줄어든다.

## 3. GB10 특수사항

- 메모리 클럭은 `nvidia-smi -lmc`로 **조절 불가** — 통합 LPDDR5X가 시스템 컨트롤러 관할
- `-lgc`는 **Graphics/SM 클럭만** 조절 가능
- `Max Operating Temp` 등 일부 엔드포인트가 `N/A`로 노출 (비어있음)

## 4. 핵심 명령어

```bash
# 클럭 cap 설정 (최소 300, 최대 2000 MHz)
sudo nvidia-smi -lgc 300,2000

# cap 해제 (기본값 복귀)
sudo nvidia-smi -rgc

# 현재 상태 확인
nvidia-smi --query-gpu=temperature.gpu,power.draw,utilization.gpu,clocks.sm --format=csv
```

> ⚠️ `-lgc`는 **런타임 설정**이라 리부팅 시 원복된다. 영구 적용은 아래 5단계의 systemd 서비스가 필요.

## 5. systemd 서비스로 영구화

1. 유닛 파일 생성 (본 서비스는 `~/.hermes/services/gpu_clock_control/gpu-clkcap.service`)

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

2. 설치 + 활성화

```bash
sudo cp gpu-clkcap.service /etc/systemd/system/nvidia-gpu-clkcap.service
sudo systemctl daemon-reload
sudo systemctl enable --now nvidia-gpu-clkcap
```

3. 확인

```bash
systemctl is-active nvidia-gpu-clkcap    # active
systemctl is-enabled nvidia-gpu-clkcap   # enabled
```

## 6. 심볼릭 링크 (enable의 원리)

`systemctl enable`은 아래 심볼릭 링크를 만들어 **부팅 실행 목록에 등록**한다.

```
실제 파일 (본체)
/etc/systemd/system/nvidia-gpu-clkcap.service
        ↑
        │  가리킴
심볼릭 링크 (축자)
/etc/systemd/system/multi-user.target.wants/nvidia-gpu-clkcap.service
```

`multi-user.target.wants/` = "일반 부팅 모드에 도달하면 실행할 서비스 목록".
부팅 시 systemd가 이 폴더의 링크를 따라 실제 파일을 실행한다.

| 명령어 | 동작 |
|---|---|
| `systemctl enable` | wants/ 폴더에 심볼릭 링크 **추가** |
| `systemctl disable` | wants/ 폴더의 심볼릭 링크 **삭제** (본체 파일은 유지) |

확인: `ls -la /etc/systemd/system/multi-user.target.wants/ | grep nvidia-gpu-clkcap`

## 7. 해제 (원복)

> ⚠️ **두 가지가 독립적**이라 헷갈리기 쉬움. (1) 런타임 cap, (2) 부팅 자동 적용 — 한 축만 건드려도 다른 축은 그대로.

| 상황 | 명령어 | 지금 세션 | 리부팅 후 |
|---|---|---|---|
| 잠깐 (세션만) 해제 | `sudo nvidia-smi -rgc` | cap **OFF** | ⚠️ **다시 ON** |
| 다시 걸기 | `sudo nvidia-smi -lgc 300,2000` | cap ON | ON 유지 |
| 영구 자동 적용 끄기 | `sudo systemctl disable nvidia-gpu-clkcap` | ⚠️ cap 그대로 ON | OFF |
| **영구 끄기 + 지금도 풀기** | `disable --now` **+** `-rgc` | cap OFF | OFF |

**두 가지 함정**

1. **`-rgc`만 하면 → 리부팅하면 다시 cap이 걸린다.** 서비스는 여전히 `enabled`이라 부팅 시 `-lgc 300,2000`이 다시 실행. `-rgc`는 "이번 세션만" 해제.
2. **`disable --now`만 하면 → 지금 세션 cap은 안 풀린다.** `--now`(=stop)가 유닛 상태만 `inactive`로 바꿀 뿐, 드라이버의 실제 클럭 설정은 건드리지 않음. **지금 당장 풀려면 `-rgc`도 같이** 실행.

**영구 끄기 (정확한 2줄)**

```bash
sudo systemctl disable --now nvidia-gpu-clkcap   # 부팅 자동 적용 해제
sudo nvidia-smi -rgc                              # 지금 세션 cap도 즉시 해제
```

**다시 켜기 (1줄이면 됨)**

```bash
sudo systemctl enable --now nvidia-gpu-clkcap
```

> 💡 `disable`은 유닛 *파일*을 지우는 게 아니라 **심볼릭 링크(자동 실행 등록)만** 제거한다. 그래서 다시 켤 때 한 줄이면 충분.

## 8. 서비스 파일 구성

```
~/.hermes/services/gpu_clock_control/
├── README.md          # 목적·과정·명령어 상세 문서
├── set_clock.sh       # cap 설정 (인자로 값 변경 가능)
├── reset_clock.sh     # cap 해제
├── status.sh          # 상태 조회 (클럭·온도·전력·서비스)
└── gpu-clkcap.service # systemd 유닛 원본
```

## 9. 참고

- 설정일: 2026-09-10
- 장비: Gigabyte AI TOP ATOM (GB10), 128GB 통합 LPDDR5X
- Driver 580.173.02 / CUDA 13.0
- trade-off: 클럭 낮추면 추론 속도 일부 감소 (멀티 모델 동시 구동 시 체감 더 큼 — 메모리 대역폭 경쟁)
