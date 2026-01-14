# 배포 가이드

Discord Bot을 Oracle Cloud Infrastructure (OCI)에 배포하는 방법입니다.

## 📋 사전 준비사항

1. **OCI 인스턴스 생성 완료**
   - Shape: `VM.Standard.E2.1.Micro` (Always Free)
   - OS: Ubuntu 22.04 (또는 Oracle Linux)
   - Public IP 할당 완료

2. **GitHub Secrets 설정**
   - 저장소 Settings → Secrets and variables → Actions에서 다음 추가:
     - `ORACLE_HOST`: OCI 인스턴스 공인 IP 주소
     - `ORACLE_USER`: `ubuntu` (Ubuntu 이미지) 또는 `opc` (Oracle Linux)
     - `ORACLE_SSH_PRIVATE_KEY`: SSH 개인키 전체 내용 (`.pem` 파일 내용)

## 🚀 초기 설정 (서버에서 1회만 실행)

### 1. SSH 접속

```bash
ssh -i <다운받은-키>.pem ubuntu@<공인IP>
```

### 2. 필수 패키지 설치

**Ubuntu:**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

**Oracle Linux:**
```bash
sudo yum update -y
sudo yum install -y python39 python39-pip git
```

### 3. 프로젝트 클론 및 초기 설정

```bash
cd ~
git clone https://github.com/<your-username>/<your-repo>.git discord-bot
cd discord-bot

# 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. 환경변수 설정

```bash
# .env 파일 생성
nano .env
```

다음 내용 추가:
```
DISCORD_BOT_TOKEN=your_bot_token_here
```

### 5. systemd 서비스 설정 (권장)

**Ubuntu 사용자:**
```bash
sudo tee /etc/systemd/system/discord-bot.service > /dev/null <<EOF
[Unit]
Description=Discord Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/discord-bot
Environment="PATH=/home/ubuntu/discord-bot/venv/bin"
ExecStart=/home/ubuntu/discord-bot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

**Oracle Linux (opc 사용자):**
```bash
sudo tee /etc/systemd/system/discord-bot.service > /dev/null <<EOF
[Unit]
Description=Discord Bot
After=network.target

[Service]
Type=simple
User=opc
WorkingDirectory=/home/opc/discord-bot
Environment="PATH=/home/opc/discord-bot/venv/bin"
ExecStart=/home/opc/discord-bot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

서비스 활성화:
```bash
sudo systemctl daemon-reload
sudo systemctl enable discord-bot
sudo systemctl start discord-bot
```

### 6. 배포 스크립트 권한 설정

```bash
chmod +x deploy.sh
```

## 🔄 자동 배포 (CI/CD)

### GitHub Actions 설정

1. **Secrets 설정 확인**
   - `ORACLE_HOST`, `ORACLE_USER`, `ORACLE_SSH_PRIVATE_KEY` 모두 설정되어 있는지 확인

2. **자동 배포 동작**
   - `main` 브랜치에 푸시하면 자동으로 배포됩니다
   - GitHub Actions 탭에서 배포 상태 확인 가능

3. **수동 배포**
   - GitHub Actions 탭 → "Deploy Discord Bot to Oracle Cloud" → "Run workflow" 클릭

## 📝 수동 배포 (서버에서 직접 실행)

서버에 SSH 접속 후:

```bash
cd ~/discord-bot
./deploy.sh
```

또는 GitHub Actions 워크플로우를 사용하지 않고 직접:

```bash
cd ~/discord-bot
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart discord-bot
```

## 🔍 로그 확인

### systemd 사용 시:
```bash
# 실시간 로그
sudo journalctl -u discord-bot -f

# 최근 50줄
sudo journalctl -u discord-bot -n 50

# 서비스 상태 확인
sudo systemctl status discord-bot
```

### 직접 실행 시:
```bash
tail -f ~/discord-bot/bot.log
```

## 🛠️ 문제 해결

### 배포 실패 시
1. GitHub Actions 로그 확인
2. 서버에 SSH 접속하여 수동으로 `./deploy.sh` 실행
3. 로그 확인하여 에러 원인 파악

### 봇이 실행되지 않을 때
```bash
# 서비스 상태 확인
sudo systemctl status discord-bot

# 로그 확인
sudo journalctl -u discord-bot -n 100

# 수동 실행 테스트
cd ~/discord-bot
source venv/bin/activate
python main.py
```

### Git pull 실패 시
```bash
cd ~/discord-bot
git status
git fetch origin
git reset --hard origin/main
```

## 💰 비용 확인

OCI 콘솔에서:
- **Billing → Cost Analysis**에서 실제 비용 확인
- Always Free 범위 내에서 사용하면 **$0.00**으로 표시됩니다

## 📚 참고사항

- Always Free 인스턴스는 **월 2개까지** 생성 가능
- Block Volume 총합 **200GB까지** 무료
- 네트워크 트래픽은 **월 10TB까지** 무료

