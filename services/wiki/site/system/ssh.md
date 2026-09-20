# SSH 설정

[summary] Dall — Windows PC에서 Haee — AI TOP Atom (GB10) SSH 터미널 접속, 방화벽, VS Code 연동.

## 1. 아키텍처

```
Dall (Windows 11)  ──  LAN 192.168.x.x  ──  Haee (ai top atom, Ubuntu)
        SSH client (built-in)                 OpenSSH Server (port 22)
```

## 2. Haee 측 (서버) 설정

```bash
sudo apt update
sudo apt install openssh-server -y
sudo systemctl status ssh          # Active: active (running)
```

## 3. IP 확인

```bash
ip a
# inet 192.168.219.115/24 → 이 주소가 Dall에서 접속할 IP
```

## 4. Dall 측 접속

Windows 10/11은 OpenSSH 클라이언트가 내장되어 별도 설치 불필요.

```powershell
# PowerShell 또는 CMD
ssh joonsoo@192.168.219.115
# 첫 접속 시 yes → 비밀번호 입력 (화면 비표시 정상)
```

## 5. 방화벽 (UFW)

`Connection timed out` / `Connection refused` 시:

```bash
sudo ufw allow 22/tcp
sudo ufw reload
```

## 6. VS Code Remote-SSH

> 💡 **Tip:** VS Code `[Remote - SSH]` 확장을 설치하면 터미널 제어 + 파일 편집을
> Windows 환경에서 마치 로컬처럼 수행할 수 있다. `~/.ssh/config`에 Haee 엔트리 등록 권장.

```
Host atom
  HostName 192.168.219.115
  User joonsoo
```

> ⚠️ **고정 IP:** 공유기 설정에서 Haee의 MAC→IP 바인딩(fixed IP)을 설정해
> DHCP 변동으로 접속이 깨지는 것을 방지한다.
