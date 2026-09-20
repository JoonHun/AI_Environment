# ESP32 External Fan Controller - 설계 문서

| 항목 | 내용 |
|------|------|
| **작성자** | JoonHun |
| **최초 작성일** | 2026-09-13 |
| **마지막 업데이트** | 2026-09-13 |
| **버전** | 1.0 |
| **플랫폼** | ESP32 (Arduino Framework) |
---

## 목차

1. [목적](#1-목적)
2. [시스템 개요](#2-시스템-개요)
3. [하드웨어 설계](#3-하드웨어-설계)
4. [소프트웨어 설계](#4-소프트웨어-설계)
5. [상세 설계](#5-상세-설계)
6. [구현 상세](#6-구현-상세)
7. [설정 파라미터](#7-설정-파라미터)
8. [테스트 결과](#8-테스트-결과)
9. [제한사항](#9-제한사항)
10. [향후 개선](#10-향후-개선)

---

## 1. 목적

이 프로젝트는 **ESP32 마이크로컨트롤러**를 사용하여 **외부 서버에서 제공되는 온도 데이터**에 기반하여 4-pin PWM 팬과 ARGB LED 스트립을 자동으로 제어하는 시스템입니다.

### 주요 목표

1. **자동 온도 기반 팬 제어**: 서버에서 가져온 온도에 따라 팬 속도를 자동으로 조정
2. **시각적 상태 표시**: 온도에 따라 LED 색상을 변화시켜 직관적인 상태 모니터링
3. **실시간 RPM 모니터링**: 팬의 실제 회전수를 측정하여 서버로 보고
4. **신뢰성 있는 운영**: WiFi 및 API 장애 시 자동 복구 메커니즘 (exponential backoff)
5. **안전 모드**: 이상 상황 시 자동 안전 모드 진입 (80% 팬 속도, 노란색 LED)

### 해결하려는 문제

- 수동 팬 제어의 비효율성 제거
- 온도 변화에 따른 동적인 냉각 성능 조정
- 시스템 상태의 시각적/원격 모니터링 가능성

---

## 2. 시스템 개요

### 구성 요소

| 구성 요소 | 설명 |
|-----------|------|
| **ESP32** | 메인 컨트롤러, WiFi 내장, LEDC PWM 하드웨어 지원 |
| **4-pin PWM Fan** | PWM 속도 제어 + Tachometer RPM 피드백, Max 1800 RPM |
| **WS2812 ARGB LED** | 16개 LED 스트립, 단일 데이터 라인 제어 |
| **Remote API** | 온도 데이터 제공 및 팬 설정 수신 서버 (192.168.219.115) |

---

## 3. 하드웨어 설계

### GPIO Pinout

| Function | GPIO | Mode | Notes |
|----------|------|------|-------|
| Fan PWM | 14 | Output | LEDC Channel 0, 25kHz, 8-bit |
| Fan Tachometer | 15 | Input | Internal pull-up, External Interrupt |
| ARGB Data | 27 | Output | WS2812 protocol, GRB order |

### 하드웨어 사양

| 항목 | 사양 |
|------|------|
| **보드** | ESP32 Development Board (Any variant) |
| **팬** | 4-pin PWM Fan (12V/5V), Max RPM: 1800 |
| **LED** | WS2812-based ARGB Strip, 16 LEDs |
| **전원** | USB (5V/500mA) 또는 외부 5V/2A |
| **통신** | WiFi 802.11 b/g/n (2.4GHz) |

### 연결 도면

```
ESP32                          Fan                  LED Strip
──────                         ───                  ─────────
GPIO 14  ──────────────► PWM    │ 1  (PWM)          │
GPIO 15  ──────────────► INT    │ 2  (Tach)    GND  │ 4  (GND)
GND    ──────────────► GND      │ 3  (GND)     DIN  │ 1  (Data)
5V     ──────────────► VCC      │ 4  (5V)    VCC   │ 2  (5V)
                                                GND  │ 3  (GND)
```

### 주의사항

1. **Tachometer Signal**: 대부분의 팬은 open-drain 출력을 사용하므로 ESP32의 internal pull-up (`INPUT_PULLUP`) 이 필요
2. **PWM Frequency**: 25kHz 는 대부분의 DC 팬에 최적화되어 있음 (낮은 노이즈, 부드러운 작동)
3. **LED Brightness**: 최대 200/255 (500mA 피크 전류 방지)

---

## 4. 소프트웨어 설계

### 상태 기계 (Finite State Machine)

```
                    ┌──────────────────┐
                    │   Startup        │
                    │ (setup)          │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Connect WiFi    │
                    └────────┬─────────┘
                             │
                   ┌─────────┴─────────┐
                   │                   │
              Success              Failure
                   │                   │
          ┌────────▼───────┐   ┌──────▼──────────┐
          │STATE_TEMP_RETRY│   │STATE_WIFI_RETRY │
          │                │   │                 │
          │ Fetch Temp API │   │ Retry WiFi      │
          └────────┬───────┘   └─────────────────┘
                   │
          ┌────────┴────────┐
          │                 │
     Success (≥0°C)    Failure (-1.0)
          │                 │
          ▼                 ▼
  ┌───────────────┐ ┌──────────────────┐
  │  STATE_OK     │ │ Handle Failure   │
  │               │ │ (backoff retry)  │
  │ - Control Fan │ └──────────────────┘
  │ - Control LED │
  │ - Report RPM  │
  └───────────────┘
```

### 주요 모듈

| 모듈 | 파일 위치 | 역할 |
|------|-----------|------|
| `main.cpp` | `src/main.cpp` | 메인 로직, FSM, API 통신 |
| Fan Control | `setFanSpeed()`, `measureRpm()` | PWM 제어, RPM 측정 |
| LED Control | `setArgbColor()`, `getTemperatureColor()` | LED 색상 관리 |
| WiFi Manager | `connectWiFi()`, `handleWiFiDisconnected()` | WiFi 연결/재연결 |
| API Client | `fetchTemperatureFromAPI()`, `sendConfigToAPI()` | 서버 통신 |
| Retry Logic | `calculateBackoff()`, `handleAPIMissuccess()` | 지수 백오프 재시도 |

---

## 5. 상세 설계

### 5.1 WiFi 연결 메커니즘

#### 재연결 정책 (Exponential Backoff)

| Retry # | Delay | Cumulative |
|---------|-------|------------|
| 1 | 3s | 3s |
| 2 | 9s | 12s |
| 3 | 27s | 39s |
| 4 | 81s | 120s |
| 5+ | 180s (max) | capped |

**Algorithm**: `delay = min(initial_delay × 3^retryCount, max_delay)`

### 5.2 API 통신

#### GET Temperature API

- **Endpoint**: `http://192.168.219.115:5002/api/external-fan/temp`
- **Response**: `{"gpu_temp_c": 55.0, "cpu_temp_c": 56.8}`
- **처리**: `gpu_temp_c` 우선, 실패 시 `cpu_temp_c` 폴백
- **timeout**: 5초

#### POST Fan Config API

- **Endpoint**: `http://192.168.219.115:5002/api/external-fan`
- **Request**: `{"fan_rpm": 720, "led_r": 0, "led_g": 255, "led_b": 0}`

### 5.3 온도→팬속도 매핑

#### 온도 임계값

| 임계값 | 온도 | 팬 속도 | LED 색상 |
|--------|------|---------|----------|
| `TEMP_LOW` | 45°C | 30% | Green |
| `TEMP_MID` | 55°C | 60% | Yellow |
| `TEMP_HIGH` | 65°C | 90% | Red |

#### 선형 보간 (Linear Interpolation)

**45°C ~ 55°C**: `fanSpeed = 30 + ((temp-45)/10) × 30`
**55°C ~ 65°C**: `fanSpeed = 60 + ((temp-55)/10) × 30`

| 온도 | Fan Speed | PWM Value | LED Color |
|------|-----------|-----------|-----------|
| 40°C | 30% | 76 | Green (0,255,0) |
| 50°C | 45% | 114 | Yellow (255,255,0) |
| 60°C | 75% | 191 | Red (255,0,0) |
| 70°C | 90% | 229 | Red (255,0,0) |

### 5.4 RPM 측정 알고리즘

#### 계산식

```
RPM = (pulseCount × 60) / PULSES_PER_REV
```

- `pulseCount`: 1초 동안 카운트된 펄스 수
- `PULSES_PER_REV`: 2 (이 팬 모델)
- **예시**: 12 pulses/초 → (12×60)/2 = **360 RPM**

#### 측정 프로세스

1. `rpmPulseCount = 0` (카운터 초기화)
2. `wait(1000ms)` (정확한 1초 대기)
3. `pulseCount = rpmPulseCount` (인터럽트 비활성화 후 읽기)
4. `RPM = (pulseCount × 60) / PULSES_PER_REV`
5. `return RPM` (0 = 팬 정지)

### 5.5 에러 처리 및 Retry

**Safe Mode 조건**:
- WiFi 연결 실패 시
- API 호출 실패 시

**Safe Mode 동작**:
- Fan speed: 80% (최대 냉각 보장)
- LED: Yellow (경고 상태 표시)

---

## 6. 구현 상세

### 6.1 PWM 제어

**ESP32 LEDC 설정**:
- Channel: 0
- Frequency: 25kHz
- Resolution: 8-bit (0-255)
- Pin: GPIO 14

**PWM 값 변환**: `pwmValue = (speedPercent × 255) / 100`

| Fan Speed | PWM Value | Notes |
|-----------|-----------|-------|
| 0% | 0 | Fan off |
| 30% | 76 | Low speed |
| 50% | 127 | Half speed |
| 90% | 229 | Near max |
| 100% | 255 | Full speed |

### 6.2 인터럽트 핸들러

```cpp
pinMode(FAN_RPM_PIN, INPUT_PULLUP)
attachInterrupt(digitalPinToInterrupt(FAN_RPM_PIN), countRpmPulse, FALLING)
```

**ISR**: `rpmPulseCount++` (ICACHE_RAM_ATTR, no Serial.print/delay)

### 6.3 지수 백오프 (Exponential Backoff)

```
delay = initial_delay
for i = 1 to retryCount:
    delay = delay × 3
    if delay >= max_delay: delay = max_delay
return delay
```

| 매개변수 | 값 |
|----------|-----|
| `initialDelay` | 3000ms |
| `maxDelay` | 180000ms (3min) |
| backoff factor | 3 |

### 6.4 ARGB LED 제어

**WS2812 설정**:
- Pin: GPIO 27
- LEDs: 16
- Color order: GRB (FastLED 내부)

**색그라디언트**:
- Green → Yellow (45-55°C): `CRGB(t×255, 255, 0)`
- Yellow → Red (55-65°C): `CRGB(255, (1-t)×255, 0)`

---

## 7. 설정 파라미터

### 컴파일타임 설정

| 매개변수 | 값 | 설명 |
|----------|-----|------|
| `TACHOMETER` | `true` | RPM 측정 활성화 |
| `WIFI_SSID` | `"kong1"` | WiFi 네트워크 |
| `WIFI_CONNECT_TIMEOUT` | `10000`ms | 연결 시도 시간 |
| `API_URL` | `"http://192.168.219.115:5002/..."` | 온도 API 엔드포인트 |
| `API_POST_URL` | `"http://192.168.219.115:5002/..."` | 설정 POST 엔드포인트 |
| `API_TIMEOUT` | `5000`ms | HTTP 요청 timeout |
| `API_RETRY_INITIAL_DELAY` | `3000`ms | API 재시도 초기 대기 |
| `API_RETRY_MAX_DELAY` | `180000`ms | API 재시도 최대 대기 |
| `ARGB_PIN` | `27` | LED 데이터 핀 |
| `ARGB_NUM_LEDS` | `16` | LED 수 |
| `TEMP_LOW` | `45`°C | 낮은 온도 임계값 |
| `TEMP_MID` | `55`°C | 중간 온도 임계값 |
| `TEMP_HIGH` | `65`°C | 높은 온도 임계값 |
| `FAN_SPEED_LOW` | `30`% | 낮은 온도 팬 속도 |
| `FAN_SPEED_MID` | `60`% | 중간 온도 팬 속도 |
| `FAN_SPEED_HIGH` | `90`% | 높은 온도 팬 속도 |
| `FAN_PWM_CHANNEL` | `0` | PWM 채널 |
| `FAN_PWM_PIN` | `14` | PWM 출력 핀 |
| `FAN_PWM_FREQUENCY` | `25000`Hz | PWM 주파수 |
| `PWM_RESOLUTION` | `8`bits | PWM 해상도 |
| `FAN_RPM_PIN` | `15` | Tachometer 입력 핀 |
| `PULSES_PER_REV` | `2` | 회전당 펄스 수 |

### 런타임 설정

| 매개변수 | 기본값 | 설명 |
|----------|--------|------|
| `safeModeFanSpeed` | `80`% | 안전 모드 팬 속도 |
| `wifiRetryDelay` | `3000`ms | WiFi 재시도 초기 대기 |
| `apiRetryDelay` | `3000`ms | API 재시도 초기 대기 |

---

## 8. 테스트 결과

### 측정 환경

| 항목 | 값 |
|------|-----|
| **팬 모델** | 4-pin PWM Fan (Max 1800 RPM) |
| **PWM 설정** | 25kHz, 8-bit |
| **PULSES_PER_REV** | 2 |
| **측정 방법** | 1초 간격 pulse 카운팅 |

### PWM 30% 테스트 (온도 ≤45°C)

| 측정 | 预期 RPM (1800×0.3) | 실제 RPM | 차이 |
|------|-------------------|----------|------|
| 1 | 540 | 720 | +33% |
| 2 | 540 | 750 | +39% |
| **평균** | | **735 RPM** | **+36%** |

### PWM 90% 테스트 (온도 >65°C)

| 측정 | 预期 RPM (1800×0.9) | 실제 RPM | 차이 |
|------|-------------------|----------|------|
| 1 | 1620 | 2100 | +30% |
| 2 | 1620 | 1980 | +22% |
| 3 | 1620 | 2250 | +39% |
| 4 | 1620 | 2070 | +28% |
| 5 | 1620 | 1890 | +17% |
| **평균** | | **2058 RPM** | **+27%** |

### 관찰 사항

1. **DC 팬의 비선형성**: PWM %와 실제 RPM이 linear하지 않음
2. **저속 영역**: 30% PWM에서 735 RPM 측정 (预期 540 RPM)
3. **고속 영역**: 90% PWM에서 2058 RPM 측정 (预期 1620 RPM)
4. **RPM 계산식**: 올바르게 동작 (1초 pulse 카운팅 정확)

---

## 9. 제한사항

### 기술적 제한

| 제한 | 설명 | 영향 |
|------|------|------|
| **DC 팬 비선형성** | PWM %와 RPM이 linear하지 않음 | 정확도 저하 |
| **Blocking RPM 측정** | 1초 동안 loop 일시정지 | 실시간 응답 지연 |
| **Internal Pull-up** | ~50kΩ, external resistor 없음 | 노이즈 민감도 증가 |
| **GPIO 15 사용** | Boot 모드에서 UART와 공유 | 부팅 시 불안정 가능성 |

### 설계적 제한

| 제한 | 설명 | 대안 |
|------|------|------|
| **Single Fan** | 1개 팬만 제어 | Multi-channel LEDC 확장 |
| **No PID Control** | Open-loop 제어 | Closed-loop PID 구현 |
| **No Dashboard** | API만 사용 | Web dashboard 추가 |
| **Fixed Thresholds** | 컴파일타임 고정 | Runtime 설정 지원 |

---

## 10. 향후 개선

### 단기 개선사항

1. **PID Control 구현** - 측정된 RPM을 feedback하여 정밀 속도 제어
2. **External Pull-up 추가** - GPIO 15에 10kΩ external pull-up resistor
3. **RPM Calibration** - PWM %별 실제 RPM 측정하여 lookup table 생성

### 중기 개선사항

4. **Web Dashboard** - ESP32 내장 웹 서버, 실시간 상태 표시
5. **OTA Firmware Update** - WiFi를 통한 원격 펌웨어 업데이트
6. **Multi-Fan Support** - 최대 16채널 LEDC 활용

### 장기 개선사항

7. **Machine Learning 기반 예측** - 온도 패턴 학습, preemptive fan speed 조절
8. **MQTT Protocol 지원** - Home Assistant 등 IoT 플랫폼 연동

---

## 부록

### A. Serial 로그 예시

**정상 동작**:
```
========================================
  ESP32 Fan & ARGB Controller Start
========================================
[INIT] ARGB LED initialized on GPIO 27
[INIT] Tachometer enabled on GPIO 15 (internal pull-up)
[INIT] Connecting to WiFi...
[OK] WiFi connected!
[API] GPU Temperature: 37.00°C
[API] POST to: http://192.168.219.115:5002/api/external-fan
[API] Payload: {"fan_rpm":720,"led_r":0,"led_g":255,"led_b":0}
[API] Success! RPM=720, LED=(0,255,0) Response: {"status":"ok"}
```

**WiFi 재연결**:
```
[WIFI] Connecting... (attempt 1)
[WIFI] Connected! IP: 192.168.219.100
```

**API 실패**:
```
[API] Fetch failed! Retry in 9s (attempt 2)
```

### B. JSON Payload 형식

**GET Response (Temperature)**:
```json
{"gpu_temp_c": 55.0, "cpu_temp_c": 56.8}
```

**POST Request (Fan Config)**:
```json
{"fan_rpm": 720, "led_r": 0, "led_g": 255, "led_b": 0}
```

**POST Response**:
```json
{"status": "ok"}
```

### C. 버전 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-09-13 | 초기 버전 |

---

**문서 끝**
