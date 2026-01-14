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

- `main` 브랜치에 푸시하면 자동으로 OCI 서버에 배포됩니다.
- GitHub Actions 워크플로우: `.github/workflows/deploy.yml`