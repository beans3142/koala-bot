"""
알고리즘 동아리 관리용 Discord 봇
- 역할 관리
- Tistory 블로그 링크 제출
- 그룹/채널 관리
"""

import discord
from discord.ext import commands
import os
import sys
from dotenv import load_dotenv

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 환경변수 로드
load_dotenv()

# 로거 설정
from common.logger import setup_logger
logger = setup_logger()

# 봇 설정
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'{bot.user}로 로그인했습니다!')
    logger.info(f'서버 수: {len(bot.guilds)}')
    print(f'{bot.user}로 로그인했습니다!')
    print(f'서버 수: {len(bot.guilds)}')
    await bot.change_presence(activity=discord.Game(name="알고리즘 동아리 관리"))

@bot.event
async def on_command_error(ctx, error):
    logger.error(f'명령어 오류: {ctx.author} - {ctx.message.content} - {str(error)}')
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ 알 수 없는 명령어입니다. `/도움말`을 입력해주세요.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ 명령어에 필요한 인자가 누락되었습니다. `/도움말`을 확인해주세요.")
    else:
        await ctx.send(f"❌ 오류가 발생했습니다: {str(error)}")

# 모듈 로드
def load_modules():
    """모든 모듈 로드"""
    from domain import role, channel, assignment, study, user
    from common import help
    
    role.setup(bot)
    channel.setup(bot)
    help.setup(bot)
    user.setup(bot)
    study.setup(bot)
    assignment.setup(bot)

# 봇 실행
if __name__ == '__main__':
    # 데이터베이스 초기화 (SQLite 사용 시)
    try:
        from common import database
        database.init_database()
        print("[OK] SQLite 데이터베이스 초기화 완료")
    except ImportError:
        print("[WARN] database.py를 찾을 수 없습니다. JSON 방식으로 동작합니다.")
    
    load_modules()
    
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not TOKEN:
        print("[ERROR] DISCORD_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
        print("   .env 파일에 DISCORD_BOT_TOKEN=your_token_here 를 추가해주세요.")
    else:
        bot.run(TOKEN)
