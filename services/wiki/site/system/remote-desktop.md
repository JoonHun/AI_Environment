# 원격 데스크톱 (xRDP)

[summary] Dall — Windows PC의 기본 원격 데스크톱(`mstsc`)으로 Haee — AI TOP Atom (GB10)의 GUI 화면을 직접 조작하는 xRDP 설정.

## 1. 특성

> ⚠️ **동시 로그인 금지:** Haee 자체 GUI에서 이미 로그인된 상태에서 원격 접속하면
> 검은 화면이 나오거나 연결이 끊긴다. 원격 접속 전 Haee 화면에서 **반드시 로그아웃**할 것.
> 화면은 연결되지만 **속도가 느리며**, SSH/IDE보다 무겁다. 가벼운 작업은 다른 경로를 우선해라.

## 2. Haee 측 설정 (SSH 터미널에서)

```bash
sudo apt update
sudo apt install xrdp -y
```

```bash
# 인증서 접근 권한 부여 (접속 오류 방지)
sudo adduser xrdp ssl-cert
```

```bash
# xRDP 전용 포트 3389 열기
sudo ufw allow 3389/tcp
sudo ufw reload
```

```bash
# 서비스 재시작 + 자동 시작 등록
sudo systemctl restart xrdp
sudo systemctl enable xrdp
```

## 3. Dall 측 접속

1. `Win + R` → `mstsc` → **[원격 데스크톱 연결]**
2. 컴퓨터: `192.168.219.115` 입력 → **[연결]**
3. 보안 경고에 **[예(Y)]**
4. xRDP 로그인 화면(`Session: Xorg`)에 Haee 리눅스 계정 ID/비밀번호 입력 → [OK]

> 💡 **검은 화면 해결:** 접속 전 Haee 로컬 GUI에서 로그아웃이 1순위 원인. 이후에도
> 검은 화면이면 `sudo systemctl restart xrdp` 후 재시도.

## 4. 용도

- `nvidia-smi`, 기가바이트 AI TOP Utility 같은 GUI 창을 마우스로 직접 조작할 때
- 터미널/IDE로 해결이 안 되는 GUI 의존 작업에만 제한적으로 사용
