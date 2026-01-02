"""
제출 명령어 (블로그, 문제풀이, 모의테스트)
"""
import discord
from discord.ext import commands
from datetime import datetime
from common.utils import load_data, save_data
from common.boj_utils import check_problem_solved, get_problem_tier
from common.logger import get_logger

logger = get_logger()

def setup(bot):
    """봇에 명령어 등록"""
    
    @bot.group(name='제출')
    async def submission_group(ctx):
        """제출 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 올바른 명령어를 입력해주세요. `/제출 블로그 <링크>` 또는 `/제출 문제풀이 <문제번호>` 형식으로 입력해주세요.")

    @submission_group.command(name='블로그')
    async def submit_blog(ctx, *, link: str):
        """블로그 링크 제출"""
        # Tistory 링크 검증
        if 'tistory.com' not in link:
            await ctx.send("❌ Tistory 블로그 링크만 제출 가능합니다.")
            logger.warning(f'블로그 제출 실패 (잘못된 링크): {ctx.author} - {link}')
            return
        
        data = load_data()
        user_id = str(ctx.author.id)
        
        if user_id not in data['users']:
            await ctx.send("❌ 먼저 `/유저등록` 명령어로 등록해주세요.")
            return
        
        # 중복 체크 (모든 제출 기록에서)
        all_links = []
        user_submissions = data['users'][user_id].get('submissions', {})
        for assignment_id, submissions in user_submissions.items():
            for sub in submissions:
                if isinstance(sub, dict) and sub.get('link'):
                    all_links.append(sub['link'])
        
        # tistory_links에서도 확인
        tistory_links = data['users'][user_id].get('tistory_links', [])
        for link_data in tistory_links:
            if isinstance(link_data, dict):
                all_links.append(link_data['link'])
            else:
                all_links.append(link_data)
        
        if link in all_links:
            await ctx.send("⚠️ 이미 제출된 링크입니다.")
            logger.info(f'블로그 제출 중복: {ctx.author} - {link}')
            return
        
        # 제출 저장 (과제 ID 없이 저장, 운영진이 나중에 확인)
        if 'submissions' not in data['users'][user_id]:
            data['users'][user_id]['submissions'] = {}
        
        # '블로그_일반' 키로 저장 (과제와 무관하게)
        if '블로그_일반' not in data['users'][user_id]['submissions']:
            data['users'][user_id]['submissions']['블로그_일반'] = []
        
        data['users'][user_id]['submissions']['블로그_일반'].append({
            'link': link,
            'submitted_at': datetime.now().isoformat(),
            'type': '블로그',
            'user_id': user_id,
            'username': str(ctx.author)
        })
        
        # 기존 tistory_links에도 추가 (호환성)
        if 'tistory_links' not in data['users'][user_id]:
            data['users'][user_id]['tistory_links'] = []
        data['users'][user_id]['tistory_links'].append({
            'link': link,
            'submitted_at': datetime.now().isoformat()
        })
        
        save_data(data)
        logger.info(f'블로그 제출: {ctx.author} ({user_id}) - {link}')
        await ctx.send(f"✅ 블로그 링크가 제출되었습니다!\n📝 링크: {link}\n💡 운영진이 확인할 예정입니다.")

    @submission_group.command(name='문제풀이')
    async def submit_problem(ctx, problem_id: int):
        """문제풀이 제출"""
        data = load_data()
        user_id = str(ctx.author.id)
        
        if user_id not in data['users']:
            await ctx.send("❌ 먼저 `/유저등록` 명령어로 등록해주세요.")
            return
        
        boj_handle = data['users'][user_id].get('boj_handle')
        if not boj_handle:
            await ctx.send("❌ BOJ 핸들이 등록되지 않았습니다. `/유저등록 <BOJ핸들>` 명령어로 등록해주세요.")
            return
        
        # 문제 해결 여부 확인 (status 페이지에서 확인)
        await ctx.send(f"🔄 문제 해결 여부를 확인하는 중... ({problem_id})")
        from common.boj_utils import check_problem_solved_from_status
        solve_info = await check_problem_solved_from_status(boj_handle, problem_id)
        
        if not solve_info or not solve_info.get('solved'):
            await ctx.send(f"❌ 문제 {problem_id}를 아직 해결하지 않았습니다.")
            logger.warning(f'문제풀이 제출 실패 (미해결): {ctx.author} ({user_id}) - 문제 {problem_id}')
            return
        
        # 제출 시간 정보 가져오기
        boj_submitted_at = solve_info.get('submitted_at')
        
        # 중복 체크 (모든 제출 기록에서)
        all_problems = []
        user_submissions = data['users'][user_id].get('submissions', {})
        for assignment_id, submissions in user_submissions.items():
            for sub in submissions:
                if isinstance(sub, dict) and sub.get('problem_id'):
                    all_problems.append(sub['problem_id'])
        
        if problem_id in all_problems:
            await ctx.send("⚠️ 이미 제출된 문제입니다.")
            logger.info(f'문제풀이 제출 중복: {ctx.author} ({user_id}) - 문제 {problem_id}')
            return
        
        # 제출 저장 (과제 ID 없이 저장, 운영진이 나중에 확인)
        if 'submissions' not in data['users'][user_id]:
            data['users'][user_id]['submissions'] = {}
        
        # '문제풀이_일반' 키로 저장 (과제와 무관하게)
        if '문제풀이_일반' not in data['users'][user_id]['submissions']:
            data['users'][user_id]['submissions']['문제풀이_일반'] = []
        
        # 문제 난이도 정보도 함께 저장
        problem_tier = await get_problem_tier(problem_id)
        tier_name = None
        if problem_tier:
            from common.boj_utils import number_to_tier
            tier_name = number_to_tier(problem_tier)
        
        data['users'][user_id]['submissions']['문제풀이_일반'].append({
            'problem_id': problem_id,
            'submitted_at': datetime.now().isoformat(),  # 봇에 제출한 시간
            'boj_submitted_at': boj_submitted_at,  # BOJ에서 실제로 해결한 시간
            'type': '문제풀이',
            'verified': True,
            'user_id': user_id,
            'username': str(ctx.author),
            'boj_handle': boj_handle,
            'tier': problem_tier,
            'tier_name': tier_name,
            'result': solve_info.get('result')
        })
        
        save_data(data)
        logger.info(f'문제풀이 제출: {ctx.author} ({user_id}) - 문제 {problem_id} (해결 확인됨)')
        
        if tier_name:
            await ctx.send(f"✅ 문제 {problem_id} 제출이 완료되었습니다!\n📊 난이도: {tier_name}\n💡 운영진이 확인할 예정입니다.")
        else:
            await ctx.send(f"✅ 문제 {problem_id} 제출이 완료되었습니다!\n💡 운영진이 확인할 예정입니다.")

    @submission_group.command(name='모의테스트')
    async def submit_mocktest(ctx, *, content: str = "완료"):
        """모의테스트 제출 (수동 확인)"""
        data = load_data()
        user_id = str(ctx.author.id)
        
        if user_id not in data['users']:
            await ctx.send("❌ 먼저 `/유저등록` 명령어로 등록해주세요.")
            return
        
        # 사용자의 역할 확인 (스터디 확인)
        user_roles = [role.name for role in ctx.author.roles if role.name != '@everyone']
        if not user_roles:
            await ctx.send("❌ 스터디에 등록되어 있지 않습니다.")
            return
        
        # 해당 스터디의 모의테스트 과제 찾기
        assignment = None
        assignment_id = None
        for role_name in user_roles:
            study_data = data.get('studies', {}).get(role_name, {})
            assignments = study_data.get('assignments', {})
            for aid, assgn in assignments.items():
                if assgn.get('type') == '모의테스트':
                    assignment = assgn
                    assignment_id = aid
                    break
            if assignment_id:
                break
        
        if not assignment:
            await ctx.send("❌ 제출할 모의테스트 과제를 찾을 수 없습니다.")
            return
        
        # 중복 체크
        user_submissions = data['users'][user_id].get('submissions', {}).get(assignment_id, [])
        if user_submissions:
            await ctx.send("⚠️ 이미 제출된 모의테스트입니다.")
            return
        
        # 제출 저장
        if 'submissions' not in data['users'][user_id]:
            data['users'][user_id]['submissions'] = {}
        if assignment_id not in data['users'][user_id]['submissions']:
            data['users'][user_id]['submissions'][assignment_id] = []
        
        config = assignment.get('config', {})
        boj_group_id = config.get('boj_group_id')
        
        data['users'][user_id]['submissions'][assignment_id].append({
            'content': content,
            'submitted_at': datetime.now().isoformat(),
            'type': '모의테스트',
            'boj_group_id': boj_group_id
        })
        
        save_data(data)
        logger.info(f'모의테스트 제출: {ctx.author} ({user_id}) - {content}')
        
        if boj_group_id:
            await ctx.send(f"✅ 모의테스트 제출이 완료되었습니다!\n📝 BOJ 그룹 ID: {boj_group_id}\n💡 운영진이 확인할 예정입니다.")
        else:
            await ctx.send(f"✅ 모의테스트 제출이 완료되었습니다!\n💡 운영진이 확인할 예정입니다.")

    @bot.command(name='제출목록')
    async def list_submissions(ctx, member: discord.Member = None):
        """제출한 링크 목록 확인"""
        target = member or ctx.author
        data = load_data()
        user_id = str(target.id)
        
        if user_id not in data['users'] or not data['users'][user_id].get('tistory_links'):
            await ctx.send(f"❌ {target.mention}님의 제출 기록이 없습니다.")
            return
        
        links = data['users'][user_id]['tistory_links']
        embed = discord.Embed(
            title=f"{target.display_name}님의 제출 목록",
            color=discord.Color.blue()
        )
        
        if not links:
            embed.description = "제출한 링크가 없습니다."
        else:
            for i, link_data in enumerate(links[:10], 1):  # 최대 10개만 표시
                if isinstance(link_data, dict):
                    link = link_data['link']
                    submitted_at = link_data.get('submitted_at', '')
                    if submitted_at:
                        try:
                            dt = datetime.fromisoformat(submitted_at)
                            date_str = dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            date_str = submitted_at
                        embed.add_field(
                            name=f"{i}. 링크",
                            value=f"[바로가기]({link})\n제출일: {date_str}",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name=f"{i}. 링크",
                            value=f"[바로가기]({link})",
                            inline=False
                        )
                else:
                    # 이전 형식 호환성
                    embed.add_field(
                        name=f"{i}. 링크",
                        value=f"[바로가기]({link_data})",
                        inline=False
                    )
        
        await ctx.send(embed=embed)

