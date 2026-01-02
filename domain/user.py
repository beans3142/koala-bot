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
        data = load_data()
        user_id = str(ctx.author.id)
        
        if user_id not in data['users']:
            await ctx.send("❌ 등록된 정보가 없습니다. `/유저등록` 명령어로 먼저 등록해주세요.")
            return
        
        user_data = data['users'][user_id]
        embed = discord.Embed(
            title=f"{ctx.author.display_name}님의 정보",
            color=discord.Color.blue()
        )
        
        if user_data.get('boj_handle'):
            embed.add_field(name="백준 핸들", value=user_data['boj_handle'], inline=True)
        else:
            embed.add_field(name="백준 핸들", value="미등록", inline=True)
        
        embed.add_field(name="제출한 링크 수", value=f"{len(user_data.get('tistory_links', []))}개", inline=True)
        
        # 등록된 역할 표시
        roles = user_data.get('roles', [])
        if roles:
            embed.add_field(name="등록된 역할", value=", ".join(roles), inline=False)
        
        await ctx.send(embed=embed)

