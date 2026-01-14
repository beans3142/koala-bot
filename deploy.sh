#!/bin/bash
# Discord Bot 배포 스크립트 (서버에서 실행)
# GitHub Actions에서도 이 스크립트를 사용할 수 있습니다.

set -e  # 에러 발생 시 중단

echo "🚀 배포 시작..."

# 프로젝트 디렉토리 확인 및 이동
PROJECT_DIR="$HOME/discord-bot"
if [ ! -d "$PROJECT_DIR" ]; then
  echo "❌ 디렉토리가 없습니다: $PROJECT_DIR"
  echo "초기 설정이 필요합니다."
  exit 1
fi

cd "$PROJECT_DIR"

# Git pull
echo "📥 코드 업데이트 중..."
git fetch origin main
git reset --hard origin/main || {
  echo "⚠️ Git reset 실패, 수동 확인 필요"
  exit 1
}

# 가상환경 확인 및 생성
if [ ! -d "venv" ]; then
  echo "📦 가상환경 생성 중..."
  python3 -m venv venv
fi

# 가상환경 활성화 및 의존성 설치
echo "📦 의존성 설치 중..."
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

# 봇 재시작
echo "🔄 봇 재시작 중..."

# systemd 사용하는 경우 (권장)
if systemctl is-active --quiet discord-bot 2>/dev/null; then
  sudo systemctl restart discord-bot
  echo "✅ systemd로 봇 재시작 완료"
  sleep 3
  if systemctl is-active --quiet discord-bot; then
    echo "✅ 봇이 정상적으로 실행 중입니다"
  else
    echo "❌ 봇 재시작 실패. 로그 확인: sudo journalctl -u discord-bot -n 50"
    exit 1
  fi
else
  # 직접 실행하는 경우 (fallback)
  echo "⚠️ systemd 서비스가 없습니다. 직접 실행 모드로 전환..."
  pkill -f "python.*main.py" || true
  sleep 2
  nohup python main.py > bot.log 2>&1 &
  sleep 3
  if pgrep -f "python.*main.py" > /dev/null; then
    echo "✅ 봇 재시작 완료 (직접 실행)"
  else
    echo "❌ 봇 프로세스를 찾을 수 없습니다. 로그 확인: tail -f bot.log"
    exit 1
  fi
fi

echo "✅ 배포 완료!"

