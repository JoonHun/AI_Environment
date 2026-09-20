# NVIDIA Sync (AI TOP Atom)

[summary] `ai top atom`과 Windows PC를 `nvidia sync`로 이어 한 번의 클릭으로 IDE·터미널·웹 UI를 원격 연동하는 공식 유틸리티.

## 1. 역할

| 기능 | 설명 |
|---|---|
| IDE 원격 | Windows에서 VS Code / Cursor 아이콘 클릭 → ATOM 내부 리눅스에서 실행 |
| 터미널 | Sync UI에서 터미널 오픈 → `nvidia-smi` 등 즉시 실행 |
| 포트 포워딩 | `Custom Application`으로 웹 UI(5000/5001/9119) 자동 터널링 |
| Tailscale | 외부 접속용 VPN 토큰 내장 |

## 2. 사전 준비

1. `ai top atom` 전원 ON + 네트워크 연결
2. ATOM 터미널에서 `ip a` → IP 기록(예: `192.168.219.115`)

## 3. Windows PC 설치

- [NVIDIA Sync 다운로드](https://build.nvidia.com/spark/connect-to-your-spark/sync)에서 `.exe` 설치
- 설치 후 작업표시줄 트레이 아이콘에서 UI 열기

## 4. 장치 등록

1. UI에서 **[Add Device] / [+]** 클릭
2. mDNS 자동 검색(`atom-hostname.local`) 또는 수동 IP 입력
3. ATOM 계정 **사용자 이름 / 비밀번호** 입력
4. 인증 성공 → SSH 키 터널이 자동으로 구축됨

## 5. 활용

| 액션 | 결과 |
|---|---|
| VS Code 아이콘 클릭 | Windows 화면에 IDE, 계산·파일은 ATOM에서 |
| 터미널 버튼 | `nvidia-smi`, `ollama list` 직접 실행 |
| `Custom Application` | `localhost:5000`, `localhost:5001` 등 웹 UI 자동 접속 |

## 6. 외부 접속

> 💡 **Tip:** 집 밖에서 접속하려면 Sync UI의 **Tailscale Integration**을 활성화하면 복잡한 포트포워딩 없이
> 안전한 VPN 터널로 접속할 수 있다. mDNS 자동 감지는 같은 LAN이 전제이며, 실패 시 IP 수동 입력이 대안이다.
