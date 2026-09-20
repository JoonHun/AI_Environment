---
name: turing-smart-screen
description: TURZX 9.2인치 화면에 사용자 메트릭 표시하는 프로젝트.
---
# Turing Smart Screen 프로젝트 계획 및 분석

이 스킬은 GitHub mathoudebine/turing-smart-screen-python 라이브러리에 의존하여 TURZX/Turing Smart Screen 9.2인치에 사용자 정의 메트릭을 표시하는 프로젝트의 설계, 분석, 구현 절차를 담고 있습니다.

## 절차

1. **타겟 리비전 확인**: `library/display.py`의 `REVISION` 팩토리 매핑에서 타겟 리비전을 확인하세요.
2. **protocol 레이어 분석**: `library/lcd/lcd_comm_{리비전}.py`를 읽어서 초기화 흐름, 암호화 키, 그리고 핵심 `display_*` API를 추출하세요. TUR_USB의 경우 `find_usb_device()`와 DES 키 `slv3tuzx`가 필수입니다.
3. **재사용 범위 선정**: 대부분의 경우 `LcdComm`의 초기화, `SetBrightness()`, `DisplayPILImage()` 세 가지만 가져오면 충분합니다. 컴포넌트(원형차트, 막대차트)는 `PIL.ImageDraw`로 직접 그립니다.
4. **GB10 특화 측정기 구현**: GB10는 Grace CPU와 Blackwell GPU가 통합된 119GB LPDDR5X 메모리를 사용합니다. CPU 온도는 리눅스 `/sys` 접근이 불가능하며, NVIDIA GB10 칩셋은 `nvidia-smi`로만 접근할 수 있습니다.
5. **구현**: 엔진추상화 (Ollama → 추후 다른引擎)와 config.yaml 기반 레이아웃 엔진을 구현합니다.
6. **실행 및 검증**: 실제 장치 연결 여부에 따라 실제 장치 또는 시뮬레이터(`REVISION=SIMU`)를 통해 테스트합니다.
