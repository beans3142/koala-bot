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
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# 환경변수 로드 (스크립트 파일 위치 기준으로 .env 파일 찾기)
env_path = os.path.join(script_dir, '.env')
load_dotenv(env_path)

# 로거 설정
from common.logger import setup_logger
logger = setup_logger()

# 봇 설정
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True


class KoalaBot(commands.Bot):
    async def setup_hook(self) -> None:
        """
        discord.py가 내부 이벤트 루프를 준비한 뒤 호출됨.
        persistent view 등록은 여기서 해야 'no running event loop'가 나지 않음.
        """
        from domain.role import register_persistent_view
        from domain.channel import register_group_weekly_views
        from domain.link_submission import register_link_submission_views

        register_persistent_view(self)
        register_group_weekly_views(self)
        register_link_submission_views(self)
        print("[OK] Persistent views 등록 완료")


bot = KoalaBot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'{bot.user}로 로그인했습니다!')
    logger.info(f'서버 수: {len(bot.guilds)}')
    print(f'{bot.user}로 로그인했습니다!')
    print(f'서버 수: {len(bot.guilds)}')
    await bot.change_presence(activity=discord.Game(name="알고리즘 동아리 관리"))
    
    # 스케줄러는 이벤트 루프가 준비된 뒤 시작
    from domain.role import start_weekly_status_scheduler
    from domain.channel import start_group_weekly_scheduler
    from domain.link_submission import start_link_submission_scheduler

    start_weekly_status_scheduler(bot)
    start_group_weekly_scheduler(bot)
    start_link_submission_scheduler(bot)

@bot.event
async def on_command_error(ctx, error):
    logger.error(f'명령어 오류: {ctx.author} - {ctx.message.content} - {str(error)}')
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ 알 수 없는 명령어입니다. `/도움말`을 입력해주세요.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ 명령어에 필요한 인자가 누락되었습니다. `/도움말`을 확인해주세요.")
    else:
        await ctx.send(f"❌ 오류가 발생했습니다: {str(error)}")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    """인터랙션 에러 핸들링"""
    # NOTE:
    # discord.py의 View/Modal 콜백이 interaction에 응답(ACK)하는 책임을 집니다.
    # 여기서 모든 component interaction을 선-ACK(defer)하면, 각 버튼 콜백에서
    # interaction.response.* 를 호출할 때 "Interaction has already been acknowledged(40060)"
    # 가 발생해 버튼이 동작하지 않습니다.
    # 따라서 전역적으로 defer 하지 않습니다.
    return

# 모듈 로드
def load_modules():
    """모든 모듈 로드"""
    from domain import role, channel, study, user, link_submission, problem_set
    from common import help
    
    role.setup(bot)
    channel.setup(bot)
    help.setup(bot)
    user.setup(bot)
    study.setup(bot)
    link_submission.setup(bot)
    problem_set.setup(bot)

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
