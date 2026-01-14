# KOALA Discord Bot

KOALA 알고리즘 동아리 관리용 Discord 봇입니다.

## 사용 라이브러리

- `discord.py` - Discord 봇 프레임워크
- `python-dotenv` - 환경변수 관리
- `aiohttp` - 비동기 HTTP 클라이언트
- `beautifulsoup4` - HTML 파싱
- `lxml` - XML/HTML 파서

## 설치 및 실행

```bash
pip install -r requirements.txt
```

`.env` 파일 생성 후 Discord 봇 토큰 설정:

```
DISCORD_BOT_TOKEN=your_bot_token_here
```

```bash
python main.py
```

## 배포

Oracle Cloud Infrastructure (OCI)에 배포하는 방법은 [DEPLOYMENT.md](DEPLOYMENT.md)를 참고하세요.

### CI/CD

- `main` 브랜치에 푸시하면 GitHub Actions가 자동으로 OCI 서버에 배포합니다.
- 워크플로우 파일: `.github/workflows/deploy.yml`

### 시스템 아키텍처 개요

- **로컬 / GitHub**
  - 코드는 GitHub 레포지토리 [`beans3142/koala-bot`](https://github.com/beans3142/koala-bot)에 저장됩니다.
  - `main` 브랜치에 변경 사항을 푸시하면 `deploy.yml` 워크플로우가 실행됩니다.
- **배포 파이프라인**
  - GitHub Actions → SSH 로 **OCI 인스턴스(ubuntu 사용자)** 에 접속합니다.
  - 원격 서버의 `~/discord-bot` 디렉터리에서 `git fetch/reset`, `venv` 패키지 설치를 수행합니다.
  - 이후 `systemd` 서비스 `discord-bot` 을 재시작하여 새 코드를 반영합니다.
- **서버 런타임**
  - 서비스 파일은 `/etc/systemd/system/discord-bot.service` 에 위치하며, `ExecStart=/home/ubuntu/discord-bot/venv/bin/python main.py` 를 실행합니다.
  - 애플리케이션 데이터(역할 토큰, 유저/과제 정보 등)는 모두 `bot_data.db`(SQLite) 에 저장되며, 이 파일은 Git에 커밋되지 않습니다.
  - 필요 시 로컬 ↔ 서버 간 데이터 동기화는 `bot_data.db` 를 직접 복사(scp)하는 방식으로 수행합니다.