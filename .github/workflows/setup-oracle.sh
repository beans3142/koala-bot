#!/bin/bash
# Oracle Cloud 초기 설정 스크립트 (원격 실행용)

echo "🔧 Oracle Cloud 초기 설정 시작..."

# 시스템 업데이트
sudo yum update -y

# Python 3.9 및 필수 패키지 설치
sudo yum install -y python39 python39-pip git

# 프로젝트 디렉토리 생성
mkdir -p ~/discord-bot
cd ~/discord-bot

# Git 저장소 클론 (처음 한 번만)
if [ ! -d ".git" ]; then
    echo "📥 Git 저장소 클론 중..."
    # 아래 URL을 실제 저장소 URL로 변경하세요
    # git clone https://github.com/your-username/your-repo.git .
    echo "⚠️ Git 저장소 URL을 설정하고 실행하세요!"
    exit 1
fi

# 가상환경 생성
if [ ! -d "venv" ]; then
    echo "📦 가상환경 생성 중..."
    python3.9 -m venv venv
fi

# 가상환경 활성화
source venv/bin/activate

# 의존성 설치
echo "📥 의존성 설치 중..."
pip install --upgrade pip
pip install -r requirements.txt

# Playwright Chromium 시스템 의존성 + 브라우저 설치 (Jungol 일별 캐시 갱신용)
echo "🌐 Playwright Chromium 설치 중..."
# Oracle Linux (RHEL 계열)에서 Chromium 실행에 필요한 라이브러리들
sudo yum install -y \
    nss nspr atk at-spi2-atk cups-libs libdrm libXcomposite libXdamage \
    libXfixes libXrandr libgbm libxshmfence pango cairo alsa-lib \
    || echo "⚠️ 일부 시스템 라이브러리 설치 실패 (이미 있을 수 있음)"
python -m playwright install chromium

# .env 파일 확인
if [ ! -f .env ]; then
    echo "⚠️ .env 파일이 없습니다!"
    echo "다음 명령어로 생성하세요:"
    echo "  nano .env"
    echo "  # DISCORD_BOT_TOKEN=your_token_here"
fi

# systemd 서비스 파일 생성 (선택사항)
echo "📝 systemd 서비스 파일 생성 중..."
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

echo "✅ 초기 설정 완료!"
echo ""
echo "📋 다음 단계:"
echo "1. .env 파일 생성: nano ~/discord-bot/.env"
echo "2. DISCORD_BOT_TOKEN 설정"
echo "3. systemd 서비스 시작: sudo systemctl start discord-bot"
echo "4. 자동 시작 설정: sudo systemctl enable discord-bot"
echo "5. 로그 확인: sudo journalctl -u discord-bot -f"

