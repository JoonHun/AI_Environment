# 원격 접속 (NVIDIA Sync)

[summary] Dall — Windows PC에서 Haee — AI TOP Atom (GB10)을 원격으로 제어하는 종합 방법: 터미널·IDE·웹 UI·데스크톱.

## 1. 접속 경로 개요

| 경로 | 프로토콜/도구 | 포트 | 용도 |
|---|---|---|---|
| 터미널 | SSH | 22 | 셸 명령 |
| IDE | NVIDIA Sync / VS Code Remote-SSH | — | 코드 편집 |
| 웹 UI | NVIDIA Sync (Custom App) | 5000/5001/9119 | 대시보드 |
| 데스크톱 | xRDP (mstsc) | 3389 | GUI 전체 |

상세 절차는 하위 페이지를 참조:

- [SSH 설정](/p/system/ssh)
- [NVIDIA Sync](/p/system/nvidia-sync)
- [원격 데스크톱](/p/system/remote-desktop)
- [원격 Hermes 접속](/p/system/remote-hermes)

## 2. 네트워크 전제

> ⚠️ **동일 LAN 전제:** mDNS 자동 감지는 Dall과 Haee가 같은 공유기에 연결된
> 때만 동작한다. 집 밖 접속은 NVIDIA Sync의 **Tailscale Integration**으로 대체한다.

## 3. 추천 워크플로우

1. 일상 터미널 작업 → SSH
2. 코드 작업 → VS Code Remote-SSH
3. 대시보드 확인 → NVIDIA Sync로 9119/5000 자동 터널링
4. GUI 화면 직접 조작이 꼭 필요할 때만 → xRDP (가장 무거움)
