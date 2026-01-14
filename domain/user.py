"""
유저 관리 명령어
"""
import discord
from discord.ext import commands
from common.utils import load_data, save_data
from common.boj_utils import verify_user_exists

def setup(bot):
    """봇에 명령어 등록"""
    
    @bot.command(name='유저등록')
    async def user_register(ctx, boj_handle: str):
        """유저 등록 (BOJ 핸들 필수)"""
        data = load_data()
        user_id = str(ctx.author.id)
        
        # BOJ 핸들 검증
        exists = await verify_user_exists(boj_handle)
        if not exists:
            await ctx.send(f"❌ 백준 아이디 '{boj_handle}'를 찾을 수 없습니다.")
            return
        
        if user_id not in data['users']:
            data['users'][user_id] = {
                'username': str(ctx.author),
                'boj_handle': boj_handle,
                'tistory_links': [],
                'roles': [],
                'submissions': {}
            }
        else:
            data['users'][user_id]['boj_handle'] = boj_handle
        
        save_data(data)
        await ctx.send(f"✅ 유저 등록이 완료되었습니다!\n**백준 핸들:** {boj_handle}")

    @bot.command(name='내정보')
    async def my_info(ctx):
        """내 정보 확인"""
        from common.database import get_user_roles
        
        user_id = str(ctx.author.id)
        
        # DB에서 사용자 정보 가져오기
        from common.database import get_user
        user_db = get_user(user_id)
        
        if not user_db:
            await ctx.send("❌ 등록된 정보가 없습니다. `/역할 등록` 명령어로 먼저 등록해주세요.")
            return
        
        embed = discord.Embed(
            title=f"{ctx.author.display_name}님의 정보",
            color=discord.Color.blue()
        )
        
        # 백준 핸들 (백준 닉네임)
        boj_handle = user_db.get('boj_handle')
        if boj_handle:
            embed.add_field(name="백준 핸들", value=boj_handle, inline=True)
        else:
            embed.add_field(name="백준 핸들", value="미등록", inline=True)
        
        # 참여 그룹 (역할) 목록
        roles = get_user_roles(user_id)
        if roles:
            # 그룹 이름도 함께 표시
            data = load_data()
            studies = data.get('studies', {})
            group_info = []
            for role_name in roles:
                study_data = studies.get(role_name, {})
                group_name = study_data.get('group_name', role_name)
                group_info.append(f"{group_name} ({role_name})")
            
            embed.add_field(
                name="참여 그룹",
                value="\n".join(group_info) if group_info else ", ".join(roles),
                inline=False
            )
        else:
            embed.add_field(name="참여 그룹", value="없음", inline=False)
        
        # 제출한 링크 수 (기존 JSON 데이터에서)
        data = load_data()
        user_data = data.get('users', {}).get(user_id, {})
        embed.add_field(name="제출한 링크 수", value=f"{len(user_data.get('tistory_links', []))}개", inline=True)
        
        await ctx.send(embed=embed)

