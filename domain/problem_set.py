"""
문제집 및 모의테스트 관리 명령어
"""
import discord
from discord.ext import commands, tasks
from typing import List
from datetime import datetime, timedelta, time
from common.database import (
    create_problem_set,
    get_problem_set,
    get_all_problem_sets,
    update_problem_set,
    delete_problem_set,
    create_mock_test,
    get_mock_test,
    get_all_mock_tests,
    update_mock_test,
    delete_mock_test,
    get_role_users,
    get_user,
    save_group_problem_set_status,
    get_group_problem_set_status,
    get_all_group_problem_set_status,
    delete_group_problem_set_status,
    save_group_mock_test_status,
    get_group_mock_test_status,
    get_all_group_mock_test_status,
    delete_group_mock_test_status,
)
from common.utils import load_data, get_kst_now, ensure_kst
from domain.channel import find_role_by_group_name
from common.boj_utils import get_user_solved_problems_from_solved_ac
from common.utils import send_bot_notification
from common.logger import get_logger

logger = get_logger()

# 문제집 과제 자동 갱신용
_bot_for_problem_set = None

# 모의테스트 과제 자동 갱신용
_bot_for_mock_test = None


async def update_problem_set_status(group_name: str, problem_set_name: str, bot_instance):
    """문제집 과제 현황 메시지 갱신"""
    status_info = get_group_problem_set_status(group_name, problem_set_name)
    if not status_info:
        return
    
    channel_id = int(status_info['channel_id'])
    message_id = int(status_info['message_id'])
    role_name = status_info['role_name']
    week_start = datetime.fromisoformat(status_info['week_start'])
    week_end = datetime.fromisoformat(status_info['week_end'])
    
    # timezone-naive면 KST timezone 추가
    week_start = ensure_kst(week_start)
    week_end = ensure_kst(week_end)
    
    now = get_kst_now()
    # 기간 밖이면 갱신하지 않음 (단, 월요일 01시 정각은 마지막 크롤링 허용)
    if not (week_start <= now <= week_end + timedelta(minutes=5)):
        return
    
    channel = bot_instance.get_channel(channel_id)
    if not channel:
        return
    
    try:
        message = await channel.fetch_message(message_id)
    except discord.NotFound:
        delete_group_problem_set_status(group_name, problem_set_name)
        return
    
    # 문제집 정보 가져오기
    problem_set = get_problem_set(problem_set_name)
    if not problem_set:
        return
    
    problem_ids = problem_set['problem_ids']
    total_problems = len(problem_ids)
    
    # 그룹 멤버 가져오기
    users = get_role_users(role_name)
    if not users:
        embed = discord.Embed(
            title=f"📚 '{problem_set_name}' 문제집 과제",
            description=(
                f"**그룹:** {group_name}\n"
                f"**전체 문제 수:** {total_problems}개\n"
                f"**기간:** {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
                f"**마지막 갱신:** {now.strftime('%Y-%m-%d %H:%M')}\n"
                f"(멤버 없음)"
            ),
            color=discord.Color.blue(),
        )
        await message.edit(embed=embed, view=ProblemSetStatusView(group_name, problem_set_name))
        return
    
    # 각 멤버의 해결 현황 조회
    results = []
    for user_info in users:
        user_id = user_info['user_id']
        username = user_info.get('username', 'Unknown')
        boj_handle = user_info.get('boj_handle')
        
        if not boj_handle:
            results.append({
                'username': username,
                'boj_handle': None,
                'solved_count': 0,
                'total': total_problems,
                'unsolved_problems': problem_ids.copy(),
                'status': '⚠️'
            })
            continue
        
        try:
            # solved.ac에서 해결한 문제 목록 가져오기
            solved_problems = await get_user_solved_problems_from_solved_ac(boj_handle, target_problems=problem_ids)
            solved_set = set(solved_problems)
            
            # 문제집 문제 중 해결한 문제 수
            solved_count = len([pid for pid in problem_ids if pid in solved_set])
            
            # 안 푼 문제 번호 찾기
            unsolved_problems = [pid for pid in problem_ids if pid not in solved_set]
            
            results.append({
                'username': username,
                'boj_handle': boj_handle,
                'solved_count': solved_count,
                'total': total_problems,
                'unsolved_problems': unsolved_problems,
                'status': '✅' if solved_count == total_problems else '📝'
            })
        except Exception as e:
            logger.error(f"문제집 과제 현황 조회 오류 ({boj_handle}): {e}", exc_info=True)
            results.append({
                'username': username,
                'boj_handle': boj_handle,
                'solved_count': 0,
                'total': total_problems,
                'unsolved_problems': problem_ids.copy(),
                'status': '❌'
            })
    
    # 결과 정렬 (해결한 문제 수 내림차순)
    results.sort(key=lambda x: x['solved_count'], reverse=True)
    
    # 임베드 생성
    embed = discord.Embed(
        title=f"📚 '{problem_set_name}' 문제집 과제",
        description=(
            f"**그룹:** {group_name}\n"
            f"**전체 문제 수:** {total_problems}개\n"
            f"**기간:** {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
            f"**마지막 갱신:** {now.strftime('%Y-%m-%d %H:%M')}"
        ),
        color=discord.Color.blue()
    )
    
    # 멤버별 현황
    status_text = ""
    for i, result in enumerate(results[:20]):  # 최대 20명만 표시
        emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "•"
        boj_info = f" ({result['boj_handle']})" if result['boj_handle'] else ""
        
        # 안 푼 문제 번호 표시 (최대 5개)
        unsolved_info = ""
        if result['solved_count'] < result['total']:
            unsolved_problems = result.get('unsolved_problems', [])
            if unsolved_problems:
                display_count = min(5, len(unsolved_problems))
                unsolved_display = unsolved_problems[:display_count]
                unsolved_info = f" [{','.join(map(str, unsolved_display))}"
                if len(unsolved_problems) > 5:
                    unsolved_info += "..."
                unsolved_info += "]"
        
        status_text += f"{emoji} {result['username']}{boj_info} - {result['status']} [{result['solved_count']}/{result['total']}]{unsolved_info}\n"
    
    if len(results) > 20:
        status_text += f"\n... 외 {len(results) - 20}명"
    
    embed.add_field(
        name="멤버별 풀이 현황",
        value=status_text or "멤버가 없습니다.",
        inline=False
    )
    
    # 통계
    solved_all = sum(1 for r in results if r['solved_count'] == r['total'])
    solved_some = sum(1 for r in results if 0 < r['solved_count'] < r['total'])
    solved_none = sum(1 for r in results if r['solved_count'] == 0)
    
    embed.add_field(
        name="📈 통계",
        value=(
            f"**총 멤버:** {len(results)}명\n"
            f"**전부 해결:** {solved_all}명\n"
            f"**일부 해결:** {solved_some}명\n"
            f"**미해결:** {solved_none}명"
        ),
        inline=False
    )
    
    # DB에 마지막 갱신 시간 저장
    save_group_problem_set_status(
        group_name,
        problem_set_name,
        role_name,
        str(channel_id),
        str(message_id),
        week_start.isoformat(),
        week_end.isoformat(),
        now.isoformat(),
    )

    await message.edit(embed=embed, view=ProblemSetStatusView(group_name, problem_set_name))
    
    # 전체과제현황도 갱신
    from domain.channel import update_all_assignment_status
    await update_all_assignment_status(group_name, bot_instance)


async def update_mock_test_status(group_name: str, mock_test_name: str, bot_instance):
    """모의테스트 과제 현황 메시지 갱신"""
    status_info = get_group_mock_test_status(group_name, mock_test_name)
    if not status_info:
        return
    
    channel_id = int(status_info['channel_id'])
    message_id = int(status_info['message_id'])
    role_name = status_info['role_name']
    week_start = datetime.fromisoformat(status_info['week_start'])
    week_end = datetime.fromisoformat(status_info['week_end'])
    
    # timezone-naive면 KST timezone 추가
    week_start = ensure_kst(week_start)
    week_end = ensure_kst(week_end)
    
    now = get_kst_now()
    # 기간 밖이면 갱신하지 않음 (단, 월요일 01시 정각은 마지막 크롤링 허용)
    if not (week_start <= now <= week_end + timedelta(minutes=5)):
        return
    
    channel = bot_instance.get_channel(channel_id)
    if not channel:
        return
    
    try:
        message = await channel.fetch_message(message_id)
    except discord.NotFound:
        delete_group_mock_test_status(group_name, mock_test_name)
        return
    
    # 모의테스트 정보 가져오기
    mock_test = get_mock_test(mock_test_name)
    if not mock_test:
        return
    
    problem_ids = [int(x) for x in mock_test['problem_ids'].split(',') if x.strip()]
    total_problems = len(problem_ids)
    
    # 그룹 멤버 가져오기
    users = get_role_users(role_name)
    if not users:
        embed = discord.Embed(
            title=f"📝 '{mock_test_name}' 모의테스트 과제",
            description=(
                f"**그룹:** {group_name}\n"
                f"**전체 문제 수:** {total_problems}개\n"
                f"**기간:** {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
                f"**마지막 갱신:** {now.strftime('%Y-%m-%d %H:%M')}\n"
                f"(멤버 없음)"
            ),
            color=discord.Color.blue(),
        )
        await message.edit(embed=embed, view=MockTestStatusView(group_name, mock_test_name))
        return
    
    # 각 멤버의 해결 현황 조회
    results = []
    for user_info in users:
        user_id = user_info['user_id']
        username = user_info.get('username', 'Unknown')
        boj_handle = user_info.get('boj_handle')
        
        if not boj_handle:
            results.append({
                'username': username,
                'boj_handle': None,
                'solved_count': 0,
                'total': total_problems,
                'unsolved_problems': problem_ids.copy(),
                'status': '⚠️'
            })
            continue
        
        try:
            # solved.ac에서 해결한 문제 목록 가져오기
            solved_problems = await get_user_solved_problems_from_solved_ac(boj_handle, target_problems=problem_ids)
            solved_set = set(solved_problems)
            
            # 모의테스트 문제 중 해결한 문제 수
            solved_count = len([pid for pid in problem_ids if pid in solved_set])
            
            # 안 푼 문제 번호 찾기
            unsolved_problems = [pid for pid in problem_ids if pid not in solved_set]
            
            results.append({
                'username': username,
                'boj_handle': boj_handle,
                'solved_count': solved_count,
                'total': total_problems,
                'unsolved_problems': unsolved_problems,
                'status': '✅' if solved_count == total_problems else '📝'
            })
        except Exception as e:
            logger.error(f"모의테스트 과제 현황 조회 오류 ({boj_handle}): {e}", exc_info=True)
            results.append({
                'username': username,
                'boj_handle': boj_handle,
                'solved_count': 0,
                'total': total_problems,
                'unsolved_problems': problem_ids.copy(),
                'status': '❌'
            })
    
    # 결과 정렬 (해결한 문제 수 내림차순)
    results.sort(key=lambda x: x['solved_count'], reverse=True)
    
    # 임베드 생성
    embed = discord.Embed(
        title=f"📝 '{mock_test_name}' 모의테스트 과제",
        description=(
            f"**그룹:** {group_name}\n"
            f"**전체 문제 수:** {total_problems}개\n"
            f"**기간:** {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
            f"**마지막 갱신:** {now.strftime('%Y-%m-%d %H:%M')}"
        ),
        color=discord.Color.blue()
    )
    
    # 멤버별 현황
    status_text = ""
    for i, result in enumerate(results[:20]):  # 최대 20명만 표시
        emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "•"
        boj_info = f" ({result['boj_handle']})" if result['boj_handle'] else ""
        
        # 안 푼 문제 번호 표시 (최대 5개)
        unsolved_info = ""
        if result['solved_count'] < result['total']:
            unsolved_problems = result.get('unsolved_problems', [])
            if unsolved_problems:
                display_count = min(5, len(unsolved_problems))
                unsolved_display = unsolved_problems[:display_count]
                unsolved_info = f" [{','.join(map(str, unsolved_display))}"
                if len(unsolved_problems) > 5:
                    unsolved_info += "..."
                unsolved_info += "]"
        
        status_text += f"{emoji} {result['username']}{boj_info} - {result['status']} [{result['solved_count']}/{result['total']}]{unsolved_info}\n"
    
    if len(results) > 20:
        status_text += f"\n... 외 {len(results) - 20}명"
    
    embed.add_field(
        name="멤버별 풀이 현황",
        value=status_text or "멤버가 없습니다.",
        inline=False
    )
    
    # 통계
    solved_all = sum(1 for r in results if r['solved_count'] == r['total'])
    solved_some = sum(1 for r in results if 0 < r['solved_count'] < r['total'])
    solved_none = sum(1 for r in results if r['solved_count'] == 0)
    
    embed.add_field(
        name="📈 통계",
        value=(
            f"**총 멤버:** {len(results)}명\n"
            f"**전부 해결:** {solved_all}명\n"
            f"**일부 해결:** {solved_some}명\n"
            f"**미해결:** {solved_none}명"
        ),
        inline=False
    )
    
    # DB에 마지막 갱신 시간 저장
    save_group_mock_test_status(
        group_name,
        mock_test_name,
        role_name,
        str(channel_id),
        str(message_id),
        week_start.isoformat(),
        week_end.isoformat(),
        now.isoformat(),
    )

    await message.edit(embed=embed, view=MockTestStatusView(group_name, mock_test_name))
    
    # 전체과제현황도 갱신
    from domain.channel import update_all_assignment_status
    await update_all_assignment_status(group_name, bot_instance)


@tasks.loop(time=[time(hour=h, minute=0) for h in range(0, 24)])
async def problem_set_auto_update():
    """매시 정각 문제집 과제 자동 갱신"""
    global _bot_for_problem_set
    if not _bot_for_problem_set:
        return
    
    now = get_kst_now()
    for info in get_all_group_problem_set_status():
        week_start = datetime.fromisoformat(info['week_start'])
        week_end = datetime.fromisoformat(info['week_end'])
        
        # timezone-naive면 KST timezone 추가
        week_start = ensure_kst(week_start)
        week_end = ensure_kst(week_end)
        
        # 월요일 01시 정각이면 마지막 크롤링 후 DB 삭제
        if now.weekday() == 0 and now.hour == 1 and now.minute == 0:
            await update_problem_set_status(info['group_name'], info['problem_set_name'], _bot_for_problem_set)
            # DB에서 삭제
            delete_group_problem_set_status(info['group_name'], info['problem_set_name'])
            # 봇 알림 채널에 알림 전송
            await send_bot_notification(
                _bot_for_problem_set.get_guild(int(info.get('guild_id', 0)) or None),
                "🗑️ 문제집 과제 종료",
                f"**그룹:** {info['group_name']}\n"
                f"**문제집:** {info['problem_set_name']}\n"
                f"**기간 종료:** {week_end.strftime('%Y-%m-%d %H:%M')}",
                discord.Color.orange()
            )
            continue
        
        # 기간 내에만 갱신
        if week_start <= now <= week_end:
            await update_problem_set_status(info['group_name'], info['problem_set_name'], _bot_for_problem_set)


@tasks.loop(time=[time(hour=1, minute=0)])
async def mock_test_auto_update():
    """월요일 01시 정각 모의테스트 과제 자동 갱신 (한번만 수행)"""
    global _bot_for_mock_test
    if not _bot_for_mock_test:
        return
    
    now = get_kst_now()
    # 월요일 01시에만 실행
    if now.weekday() != 0 or now.hour != 1 or now.minute != 0:
        return
    
    for info in get_all_group_mock_test_status():
        week_start = datetime.fromisoformat(info['week_start'])
        week_end = datetime.fromisoformat(info['week_end'])
        
        # timezone-naive면 KST timezone 추가
        week_start = ensure_kst(week_start)
        week_end = ensure_kst(week_end)
        
        # 기간 내에만 갱신 (월요일 01시 정각은 마지막 크롤링 허용)
        if week_start <= now <= week_end + timedelta(minutes=5):
            await update_mock_test_status(info['group_name'], info['mock_test_name'], _bot_for_mock_test)
            # DB에서 삭제
            delete_group_mock_test_status(info['group_name'], info['mock_test_name'])
            # 봇 알림 채널에 알림 전송
            await send_bot_notification(
                _bot_for_mock_test.get_guild(int(info.get('guild_id', 0)) or None),
                "🗑️ 모의테스트 과제 종료",
                f"**그룹:** {info['group_name']}\n"
                f"**모의테스트:** {info['mock_test_name']}\n"
                f"**기간 종료:** {week_end.strftime('%Y-%m-%d %H:%M')}",
                discord.Color.orange()
            )


class ProblemSetStatusView(discord.ui.View):
    """문제집 과제 현황 수동 갱신 버튼 View (persistent)"""
    
    def __init__(self, group_name: str, problem_set_name: str):
        super().__init__(timeout=None)
        self.group_name = group_name
        self.problem_set_name = problem_set_name
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        try:
            msg = f"❌ 갱신 처리 중 오류가 발생했습니다: {type(error).__name__}: {error}"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass
    
    @discord.ui.button(
        label="갱신", emoji="🔄", style=discord.ButtonStyle.secondary,
        custom_id="problem_set_status_refresh"  # 고정된 custom_id 사용
    )
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 메시지 기준으로 문제집 과제 찾기 (모든 문제집 과제를 확인하여 해당 메시지 찾기)
        all_statuses = get_all_group_problem_set_status()
        info = None
        for status in all_statuses:
            if str(status['channel_id']) == str(interaction.channel.id) and str(status['message_id']) == str(interaction.message.id):
                info = status
                break
        
        if not info:
            # fallback: self에 저장된 정보 사용
            info = get_group_problem_set_status(self.group_name, self.problem_set_name)
        if not info:
            if interaction.response.is_done():
                await interaction.followup.send("❌ 이 메시지는 문제집 과제로 등록되어 있지 않습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 이 메시지는 문제집 과제로 등록되어 있지 않습니다.", ephemeral=True)
            return
        
        week_start = datetime.fromisoformat(info['week_start'])
        week_end = datetime.fromisoformat(info['week_end'])
        
        # timezone-naive면 KST timezone 추가
        week_start = ensure_kst(week_start)
        week_end = ensure_kst(week_end)
        
        now = get_kst_now()
        
        if not (week_start <= now <= week_end + timedelta(minutes=5)):
            if interaction.response.is_done():
                await interaction.followup.send("⚠️ 이 메시지의 기간이 종료되어 더 이상 갱신할 수 없습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ 이 메시지의 기간이 종료되어 더 이상 갱신할 수 없습니다.", ephemeral=True)
            return
        
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        # info에서 그룹명과 문제집명 가져오기
        group_name = info['group_name']
        problem_set_name = info['problem_set_name']
        await update_problem_set_status(group_name, problem_set_name, interaction.client)
        await interaction.followup.send("✅ 문제집 과제 현황이 갱신되었습니다.", ephemeral=True)


class MockTestStatusView(discord.ui.View):
    """모의테스트 과제 현황 수동 갱신 버튼 View (persistent)"""
    
    def __init__(self, group_name: str, mock_test_name: str):
        super().__init__(timeout=None)
        self.group_name = group_name
        self.mock_test_name = mock_test_name
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        try:
            msg = f"❌ 갱신 처리 중 오류가 발생했습니다: {type(error).__name__}: {error}"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass
    
    @discord.ui.button(
        label="갱신", emoji="🔄", style=discord.ButtonStyle.secondary,
        custom_id="mock_test_status_refresh"  # 고정된 custom_id 사용
    )
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 메시지 기준으로 모의테스트 과제 찾기 (모든 모의테스트 과제를 확인하여 해당 메시지 찾기)
        all_statuses = get_all_group_mock_test_status()
        info = None
        for status in all_statuses:
            if str(status['channel_id']) == str(interaction.channel.id) and str(status['message_id']) == str(interaction.message.id):
                info = status
                break
        
        if not info:
            # fallback: self에 저장된 정보 사용
            info = get_group_mock_test_status(self.group_name, self.mock_test_name)
        if not info:
            if interaction.response.is_done():
                await interaction.followup.send("❌ 이 메시지는 모의테스트 과제로 등록되어 있지 않습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 이 메시지는 모의테스트 과제로 등록되어 있지 않습니다.", ephemeral=True)
            return
        
        week_start = datetime.fromisoformat(info['week_start'])
        week_end = datetime.fromisoformat(info['week_end'])
        
        # timezone-naive면 KST timezone 추가
        week_start = ensure_kst(week_start)
        week_end = ensure_kst(week_end)
        
        now = get_kst_now()
        
        if not (week_start <= now <= week_end + timedelta(minutes=5)):
            if interaction.response.is_done():
                await interaction.followup.send("⚠️ 이 메시지의 기간이 종료되어 더 이상 갱신할 수 없습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ 이 메시지의 기간이 종료되어 더 이상 갱신할 수 없습니다.", ephemeral=True)
            return
        
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        # info에서 그룹명과 모의테스트명 가져오기
        group_name = info['group_name']
        mock_test_name = info['mock_test_name']
        await update_mock_test_status(group_name, mock_test_name, interaction.client)
        await interaction.followup.send("✅ 모의테스트 과제 현황이 갱신되었습니다.", ephemeral=True)


def register_problem_set_views(bot):
    """봇 재시작 후에도 문제집 과제 버튼이 작동하도록 persistent view 등록"""
    try:
        # ProblemSetStatusView 등록 (custom_id는 고정되어 있음)
        # 실제 그룹명과 문제집명은 메시지 ID로 찾음
        bot.add_view(ProblemSetStatusView("", ""))  # 빈 값으로 초기화, 실제 값은 메시지에서 찾음
        print(f"[OK] 문제집 과제 persistent view 등록 완료 (custom_id: problem_set_status_refresh)")
    except Exception as e:
        print(f"[ERROR] 문제집 과제 persistent view 등록 실패: {e}")


def setup(bot):
    """봇에 명령어 등록"""
    global _bot_for_problem_set
    _bot_for_problem_set = bot
    
    @bot.group(name='문제집')
    async def problem_set_group(ctx):
        """문제집 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 올바른 명령어를 입력해주세요. `/문제집 생성`, `/문제집 풀이현황`, `/문제집 수정`, `/문제집 삭제` 중 하나를 사용하세요.")
    
    @problem_set_group.command(name='생성')
    @commands.has_permissions(administrator=True)
    async def problem_set_create(ctx, *, name: str):
        """문제집 생성 (관리자 전용) - 폼으로 문제 번호 입력"""
        # 이미 존재하는지 확인
        existing = get_problem_set(name)
        if existing:
            await ctx.send(f"❌ '{name}' 문제집이 이미 존재합니다.")
            return
        
        # 버튼을 사용하여 Modal 열기
        view = ProblemSetCreateView(name, ctx.author)
        await ctx.send(f"문제집 '{name}'을(를) 생성합니다. 아래 버튼을 눌러 문제 번호를 입력해주세요.", view=view)
    
    @problem_set_group.command(name='풀이현황')
    @commands.has_permissions(administrator=True)
    async def problem_set_status(ctx, name: str, *, group_name: str):
        """문제집 풀이 현황 조회 (관리자 전용)"""
        # 문제집 확인
        problem_set = get_problem_set(name)
        if not problem_set:
            await ctx.send(f"❌ '{name}' 문제집을 찾을 수 없습니다.")
            return
        
        # 그룹 확인
        data = load_data()
        role_name = find_role_by_group_name(group_name, data)
        if not role_name:
            await ctx.send(f"❌ '{group_name}' 그룹을 찾을 수 없습니다.")
            return
        
        # 그룹 멤버 가져오기
        users = get_role_users(role_name)
        if not users:
            await ctx.send(f"❌ '{group_name}' 그룹에 멤버가 없습니다.")
            return
        
        # 문제집 문제 목록
        problem_ids = problem_set['problem_ids']
        total_problems = len(problem_ids)
        
        if total_problems == 0:
            await ctx.send(f"❌ '{name}' 문제집에 문제가 없습니다.")
            return
        
        # 각 멤버의 해결 현황 조회
        initial_message = await ctx.send(f"🔄 문제집 풀이 현황을 조회하는 중...\n📚 문제집: {name}\n👥 그룹: {group_name}")
        
        results = []
        for user_info in users:
            user_id = user_info['user_id']
            username = user_info.get('username', 'Unknown')
            boj_handle = user_info.get('boj_handle')
            
            if not boj_handle:
                results.append({
                    'username': username,
                    'boj_handle': None,
                    'solved_count': 0,
                    'total': total_problems,
                    'unsolved_problems': problem_ids.copy(),  # BOJ 핸들이 없으면 모든 문제를 미해결로 표시
                    'status': '⚠️'
                })
                continue
            
            try:
                # solved.ac에서 해결한 문제 목록 가져오기
                # 최적화: 문제집 문제 목록을 전달하여 효율적으로 확인
                solved_problems = await get_user_solved_problems_from_solved_ac(boj_handle, target_problems=problem_ids)
                solved_set = set(solved_problems)
                
                # 문제집 문제 중 해결한 문제 수
                solved_count = len([pid for pid in problem_ids if pid in solved_set])
                
                # 안 푼 문제 번호 찾기
                unsolved_problems = [pid for pid in problem_ids if pid not in solved_set]
                
                results.append({
                    'username': username,
                    'boj_handle': boj_handle,
                    'solved_count': solved_count,
                    'total': total_problems,
                    'unsolved_problems': unsolved_problems,
                    'status': '✅' if solved_count == total_problems else '📝'
                })
            except Exception as e:
                logger.error(f"문제집 현황 조회 오류 ({boj_handle}): {e}", exc_info=True)
                results.append({
                    'username': username,
                    'boj_handle': boj_handle,
                    'solved_count': 0,
                    'total': total_problems,
                    'unsolved_problems': problem_ids.copy(),  # 에러 시 모든 문제를 미해결로 표시
                    'status': '❌'
                })
        
        # 결과 정렬 (해결한 문제 수 내림차순)
        results.sort(key=lambda x: x['solved_count'], reverse=True)
        
        # 임베드 생성
        embed = discord.Embed(
            title=f"📚 '{name}' 문제집 풀이 현황",
            description=f"**그룹:** {group_name}\n**전체 문제 수:** {total_problems}개",
            color=discord.Color.blue()
        )
        
        # 멤버별 현황
        status_text = ""
        for i, result in enumerate(results[:20]):  # 최대 20명만 표시
            emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "•"
            boj_info = f" ({result['boj_handle']})" if result['boj_handle'] else ""
            
            # 안 푼 문제 번호 표시 (최대 5개)
            unsolved_info = ""
            if result['solved_count'] < result['total']:
                unsolved_problems = result.get('unsolved_problems', [])
                if unsolved_problems:
                    display_count = min(5, len(unsolved_problems))
                    unsolved_display = unsolved_problems[:display_count]
                    unsolved_info = f" [{','.join(map(str, unsolved_display))}"
                    if len(unsolved_problems) > 5:
                        unsolved_info += "..."
                    unsolved_info += "]"
            
            status_text += f"{emoji} {result['username']}{boj_info} - {result['status']} [{result['solved_count']}/{result['total']}]{unsolved_info}\n"
        
        if len(results) > 20:
            status_text += f"\n... 외 {len(results) - 20}명"
        
        embed.add_field(
            name="멤버별 풀이 현황",
            value=status_text or "멤버가 없습니다.",
            inline=False
        )
        
        # 통계
        solved_all = sum(1 for r in results if r['solved_count'] == r['total'])
        solved_some = sum(1 for r in results if 0 < r['solved_count'] < r['total'])
        solved_none = sum(1 for r in results if r['solved_count'] == 0)
        
        embed.add_field(
            name="📈 통계",
            value=(
                f"**총 멤버:** {len(results)}명\n"
                f"**전부 해결:** {solved_all}명\n"
                f"**일부 해결:** {solved_some}명\n"
                f"**미해결:** {solved_none}명"
            ),
            inline=False
        )
        
        await initial_message.edit(content=None, embed=embed)
    
    @problem_set_group.command(name='수정')
    @commands.has_permissions(administrator=True)
    async def problem_set_update(ctx, *, name: str):
        """문제집 수정 (관리자 전용) - 폼으로 문제 번호 수정"""
        # 문제집 확인
        problem_set = get_problem_set(name)
        if not problem_set:
            await ctx.send(f"❌ '{name}' 문제집을 찾을 수 없습니다.")
            return
        
        # 기존 문제 번호 문자열로 변환
        existing_problems = ','.join(map(str, problem_set['problem_ids']))
        
        # 버튼을 사용하여 Modal 열기
        view = ProblemSetUpdateView(name, existing_problems, ctx.author)
        await ctx.send(f"문제집 '{name}'을(를) 수정합니다. 아래 버튼을 눌러 문제 번호를 수정해주세요.", view=view)
    
    @problem_set_group.command(name='삭제')
    @commands.has_permissions(administrator=True)
    async def problem_set_delete(ctx, *, name: str):
        """문제집 삭제 (관리자 전용)"""
        # 문제집 확인
        problem_set = get_problem_set(name)
        if not problem_set:
            await ctx.send(f"❌ '{name}' 문제집을 찾을 수 없습니다.")
            return
        
        # 삭제 확인 View
        view = ProblemSetDeleteConfirmView(name, ctx.author)
        embed = discord.Embed(
            title=f"⚠️ 문제집 삭제 확인",
            description=(
                f"**문제집명:** {name}\n"
                f"**문제 수:** {len(problem_set['problem_ids'])}개\n\n"
                f"이 작업은 되돌릴 수 없습니다!\n\n"
                f"정말 삭제하시겠습니까?"
            ),
            color=discord.Color.red()
        )
        
        await ctx.send(embed=embed, view=view)
    
    @problem_set_group.command(name='목록')
    async def problem_set_list(ctx):
        """문제집 목록 조회"""
        problem_sets = get_all_problem_sets()
        
        if not problem_sets:
            await ctx.send("❌ 등록된 문제집이 없습니다.")
            return
        
        embed = discord.Embed(
            title="📚 문제집 목록",
            color=discord.Color.blue()
        )
        
        for ps in problem_sets[:20]:  # 최대 20개만 표시
            created_by = ps.get('created_by', 'Unknown')
            problem_count = len(ps['problem_ids'])
            embed.add_field(
                name=f"📚 {ps['name']}",
                value=f"문제 수: {problem_count}개\n생성자: <@{created_by}>",
                inline=True
            )
        
        if len(problem_sets) > 20:
            embed.set_footer(text=f"... 외 {len(problem_sets) - 20}개")
        
        await ctx.send(embed=embed)
    
    # 모의테스트 명령어
    @bot.group(name='모의테스트')
    async def mock_test_group(ctx):
        """모의테스트 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 올바른 명령어를 입력해주세요. `/모의테스트 생성`, `/모의테스트 풀이현황`, `/모의테스트 수정`, `/모의테스트 삭제` 중 하나를 사용하세요.")
    
    @mock_test_group.command(name='생성')
    @commands.has_permissions(administrator=True)
    async def mock_test_create(ctx, *, name: str):
        """모의테스트 생성 (관리자 전용) - 폼으로 문제 번호 입력"""
        # 이미 존재하는지 확인
        existing = get_mock_test(name)
        if existing:
            await ctx.send(f"❌ '{name}' 모의테스트가 이미 존재합니다.")
            return
        
        # 버튼을 사용하여 Modal 열기
        view = MockTestCreateView(name, ctx.author)
        await ctx.send(f"모의테스트 '{name}'을(를) 생성합니다. 아래 버튼을 눌러 문제 번호를 입력해주세요.", view=view)
    
    @mock_test_group.command(name='풀이현황')
    @commands.has_permissions(administrator=True)
    async def mock_test_status(ctx, name: str, *, group_name: str):
        """모의테스트 풀이 현황 조회 (관리자 전용)"""
        # 모의테스트 확인
        mock_test = get_mock_test(name)
        if not mock_test:
            await ctx.send(f"❌ '{name}' 모의테스트를 찾을 수 없습니다.")
            return
        
        # 그룹 확인
        data = load_data()
        role_name = find_role_by_group_name(group_name, data)
        if not role_name:
            await ctx.send(f"❌ '{group_name}' 그룹을 찾을 수 없습니다.")
            return
        
        # 그룹 멤버 가져오기
        users = get_role_users(role_name)
        if not users:
            await ctx.send(f"❌ '{group_name}' 그룹에 멤버가 없습니다.")
            return
        
        # 모의테스트 문제 목록
        problem_ids = [int(x) for x in mock_test['problem_ids'].split(',') if x.strip()]
        total_problems = len(problem_ids)
        
        if total_problems == 0:
            await ctx.send(f"❌ '{name}' 모의테스트에 문제가 없습니다.")
            return
        
        # 각 멤버의 해결 현황 조회
        initial_message = await ctx.send(f"🔄 모의테스트 풀이 현황을 조회하는 중...\n📝 모의테스트: {name}\n👥 그룹: {group_name}")
        
        results = []
        for user_info in users:
            user_id = user_info['user_id']
            username = user_info.get('username', 'Unknown')
            boj_handle = user_info.get('boj_handle')
            
            if not boj_handle:
                results.append({
                    'username': username,
                    'boj_handle': None,
                    'solved_count': 0,
                    'total': total_problems,
                    'unsolved_problems': problem_ids.copy(),  # BOJ 핸들이 없으면 모든 문제를 미해결로 표시
                    'status': '⚠️'
                })
                continue
            
            try:
                # solved.ac에서 해결한 문제 목록 가져오기
                # 최적화: 모의테스트 문제 목록을 전달하여 효율적으로 확인
                solved_problems = await get_user_solved_problems_from_solved_ac(boj_handle, target_problems=problem_ids)
                solved_set = set(solved_problems)
                
                # 모의테스트 문제 중 해결한 문제 수
                solved_count = len([pid for pid in problem_ids if pid in solved_set])
                
                # 안 푼 문제 번호 찾기
                unsolved_problems = [pid for pid in problem_ids if pid not in solved_set]
                
                results.append({
                    'username': username,
                    'boj_handle': boj_handle,
                    'solved_count': solved_count,
                    'total': total_problems,
                    'unsolved_problems': unsolved_problems,
                    'status': '✅' if solved_count == total_problems else '📝'
                })
            except Exception as e:
                logger.error(f"모의테스트 현황 조회 오류 ({boj_handle}): {e}", exc_info=True)
                results.append({
                    'username': username,
                    'boj_handle': boj_handle,
                    'solved_count': 0,
                    'total': total_problems,
                    'unsolved_problems': problem_ids.copy(),  # 에러 시 모든 문제를 미해결로 표시
                    'status': '❌'
                })
        
        # 결과 정렬 (해결한 문제 수 내림차순)
        results.sort(key=lambda x: x['solved_count'], reverse=True)
        
        # 임베드 생성
        embed = discord.Embed(
            title=f"📝 '{name}' 모의테스트 풀이 현황",
            description=f"**그룹:** {group_name}\n**전체 문제 수:** {total_problems}개",
            color=discord.Color.purple()
        )
        
        # 멤버별 현황
        status_text = ""
        for i, result in enumerate(results[:20]):  # 최대 20명만 표시
            emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "•"
            boj_info = f" ({result['boj_handle']})" if result['boj_handle'] else ""
            
            # 안 푼 문제 번호 표시 (최대 5개)
            unsolved_info = ""
            if result['solved_count'] < result['total']:
                unsolved_problems = result.get('unsolved_problems', [])
                if unsolved_problems:
                    display_count = min(5, len(unsolved_problems))
                    unsolved_display = unsolved_problems[:display_count]
                    unsolved_info = f" [{','.join(map(str, unsolved_display))}"
                    if len(unsolved_problems) > 5:
                        unsolved_info += "..."
                    unsolved_info += "]"
            
            status_text += f"{emoji} {result['username']}{boj_info} - {result['status']} [{result['solved_count']}/{result['total']}]{unsolved_info}\n"
        
        if len(results) > 20:
            status_text += f"\n... 외 {len(results) - 20}명"
        
        embed.add_field(
            name="멤버별 풀이 현황",
            value=status_text or "멤버가 없습니다.",
            inline=False
        )
        
        # 통계
        solved_all = sum(1 for r in results if r['solved_count'] == r['total'])
        solved_some = sum(1 for r in results if 0 < r['solved_count'] < r['total'])
        solved_none = sum(1 for r in results if r['solved_count'] == 0)
        
        embed.add_field(
            name="📈 통계",
            value=(
                f"**총 멤버:** {len(results)}명\n"
                f"**전부 해결:** {solved_all}명\n"
                f"**일부 해결:** {solved_some}명\n"
                f"**미해결:** {solved_none}명"
            ),
            inline=False
        )
        
        await initial_message.edit(content=None, embed=embed)
    
    @mock_test_group.command(name='수정')
    @commands.has_permissions(administrator=True)
    async def mock_test_update(ctx, *, name: str):
        """모의테스트 수정 (관리자 전용) - 폼으로 문제 번호 수정"""
        # 모의테스트 확인
        mock_test = get_mock_test(name)
        if not mock_test:
            await ctx.send(f"❌ '{name}' 모의테스트를 찾을 수 없습니다.")
            return
        
        # 기존 문제 번호 문자열로 변환
        existing_problems = ','.join(map(str, mock_test['problem_ids']))
        
        # 버튼을 사용하여 Modal 열기
        view = MockTestUpdateView(name, existing_problems, ctx.author)
        await ctx.send(f"모의테스트 '{name}'을(를) 수정합니다. 아래 버튼을 눌러 문제 번호를 수정해주세요.", view=view)
    
    @mock_test_group.command(name='삭제')
    @commands.has_permissions(administrator=True)
    async def mock_test_delete(ctx, *, name: str):
        """모의테스트 삭제 (관리자 전용)"""
        # 모의테스트 확인
        mock_test = get_mock_test(name)
        if not mock_test:
            await ctx.send(f"❌ '{name}' 모의테스트를 찾을 수 없습니다.")
            return
        
        # 삭제 확인 View
        view = MockTestDeleteConfirmView(name, ctx.author)
        embed = discord.Embed(
            title=f"⚠️ 모의테스트 삭제 확인",
            description=(
                f"**모의테스트명:** {name}\n"
                f"**문제 수:** {len(mock_test['problem_ids'])}개\n\n"
                f"이 작업은 되돌릴 수 없습니다!\n\n"
                f"정말 삭제하시겠습니까?"
            ),
            color=discord.Color.red()
        )
        
        await ctx.send(embed=embed, view=view)
    
    @mock_test_group.command(name='목록')
    async def mock_test_list(ctx):
        """모의테스트 목록 조회"""
        mock_tests = get_all_mock_tests()
        
        if not mock_tests:
            await ctx.send("❌ 등록된 모의테스트가 없습니다.")
            return
        
        embed = discord.Embed(
            title="📝 모의테스트 목록",
            color=discord.Color.purple()
        )
        
        for mt in mock_tests[:20]:  # 최대 20개만 표시
            created_by = mt.get('created_by', 'Unknown')
            problem_count = len(mt['problem_ids'])
            embed.add_field(
                name=f"📝 {mt['name']}",
                value=f"문제 수: {problem_count}개\n생성자: <@{created_by}>",
                inline=True
            )
        
        if len(mock_tests) > 20:
            embed.set_footer(text=f"... 외 {len(mock_tests) - 20}개")
        
        await ctx.send(embed=embed)
    
    # 자동 갱신 태스크는 on_ready에서 시작 (봇이 준비된 후)


def start_problem_set_scheduler(bot_instance):
    """문제집 과제 자동 갱신 스케줄러 시작"""
    global _bot_for_problem_set
    _bot_for_problem_set = bot_instance
    if not problem_set_auto_update.is_running():
        problem_set_auto_update.start()
        logger.info("문제집 과제 자동 갱신 스케줄러 시작")


class ProblemSetCreateModal(discord.ui.Modal, title="문제집 생성"):
    """문제집 생성 Modal"""
    
    def __init__(self, name: str):
        super().__init__(timeout=300)
        self.name = name
        
        self.problems_input = discord.ui.TextInput(
            label="문제 번호 (쉼표로 구분)",
            placeholder="1000, 1001, 1002",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000,
        )
        self.add_item(self.problems_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 문제 번호 파싱
            problems_text = self.problems_input.value.strip()
            problem_ids = []
            
            for part in problems_text.split(','):
                part = part.strip()
                if part:
                    try:
                        problem_id = int(part)
                        if problem_id > 0:
                            problem_ids.append(problem_id)
                    except ValueError:
                        continue
            
            if not problem_ids:
                await interaction.response.send_message("❌ 유효한 문제 번호가 없습니다.", ephemeral=True)
                return
            
            # 중복 제거 및 정렬
            problem_ids = sorted(list(set(problem_ids)))
            
            # DB에 저장
            create_problem_set(self.name, problem_ids, str(interaction.user.id))
            
            # 알림 전송
            await send_bot_notification(
                interaction.guild,
                "📚 문제집 생성",
                f"**문제집명:** {self.name}\n"
                f"**문제 수:** {len(problem_ids)}개\n"
                f"**생성자:** {interaction.user.mention}",
                discord.Color.green()
            )
            
            await interaction.response.send_message(
                f"✅ 문제집 '{self.name}'이(가) 생성되었습니다!\n문제 수: {len(problem_ids)}개",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"문제집 생성 오류: {e}", exc_info=True)
            await interaction.response.send_message("❌ 문제집 생성 중 오류가 발생했습니다.", ephemeral=True)


class ProblemSetCreateView(discord.ui.View):
    """문제집 생성 버튼 View"""
    def __init__(self, name: str, author: discord.Member):
        super().__init__(timeout=300)
        self.name = name
        self.author = author
    
    @discord.ui.button(label='문제 번호 입력', style=discord.ButtonStyle.primary)
    async def create_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        modal = ProblemSetCreateModal(self.name)
        await interaction.response.send_modal(modal)


class ProblemSetUpdateModal(discord.ui.Modal, title="문제집 수정"):
    """문제집 수정 Modal"""
    
    def __init__(self, name: str, existing_problems: str):
        super().__init__(timeout=300)
        self.name = name
        
        self.problems_input = discord.ui.TextInput(
            label="문제 번호 (쉼표로 구분)",
            placeholder="1000, 1001, 1002",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000,
            default=existing_problems,
        )
        self.add_item(self.problems_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 문제 번호 파싱
            problems_text = self.problems_input.value.strip()
            problem_ids = []
            
            for part in problems_text.split(','):
                part = part.strip()
                if part:
                    try:
                        problem_id = int(part)
                        if problem_id > 0:
                            problem_ids.append(problem_id)
                    except ValueError:
                        continue
            
            if not problem_ids:
                await interaction.response.send_message("❌ 유효한 문제 번호가 없습니다.", ephemeral=True)
                return
            
            # 중복 제거 및 정렬
            problem_ids = sorted(list(set(problem_ids)))
            
            # DB에 저장
            update_problem_set(self.name, problem_ids)
            
            await interaction.response.send_message(
                f"✅ 문제집 '{self.name}'이(가) 수정되었습니다!\n문제 수: {len(problem_ids)}개",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"문제집 수정 오류: {e}", exc_info=True)
            await interaction.response.send_message("❌ 문제집 수정 중 오류가 발생했습니다.", ephemeral=True)


class ProblemSetUpdateView(discord.ui.View):
    """문제집 수정 버튼 View"""
    def __init__(self, name: str, existing_problems: str, author: discord.Member):
        super().__init__(timeout=300)
        self.name = name
        self.author = author
    
    @discord.ui.button(label='문제 번호 수정', style=discord.ButtonStyle.primary)
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        modal = ProblemSetUpdateModal(self.name, self.existing_problems)
        await interaction.response.send_modal(modal)


class ProblemSetDeleteConfirmView(discord.ui.View):
    """문제집 삭제 확인 버튼 View"""
    
    def __init__(self, name: str, author: discord.Member):
        super().__init__(timeout=300)
        self.name = name
        self.author = author
    
    @discord.ui.button(label='✅ 삭제', style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        # 삭제
        delete_problem_set(self.name)
        
        # 알림 전송
        await send_bot_notification(
            interaction.guild,
            "🗑️ 문제집 삭제",
            f"**문제집명:** {self.name}\n"
            f"**삭제자:** {interaction.user.mention}",
            discord.Color.red()
        )
        
        await interaction.response.edit_message(
            content=f"✅ 문제집 '{self.name}'이(가) 삭제되었습니다.",
            embed=None,
            view=None
        )
    
    @discord.ui.button(label='❌ 취소', style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="❌ 문제집 삭제가 취소되었습니다.",
            embed=None,
            view=None
        )


class MockTestCreateModal(discord.ui.Modal, title="모의테스트 생성"):
    """모의테스트 생성 Modal"""
    
    def __init__(self, name: str):
        super().__init__(timeout=300)
        self.name = name
        
        self.problems_input = discord.ui.TextInput(
            label="문제 번호 (쉼표로 구분)",
            placeholder="1000, 1001, 1002",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000,
        )
        self.add_item(self.problems_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 문제 번호 파싱
            problems_text = self.problems_input.value.strip()
            problem_ids = []
            
            for part in problems_text.split(','):
                part = part.strip()
                if part:
                    try:
                        problem_id = int(part)
                        if problem_id > 0:
                            problem_ids.append(problem_id)
                    except ValueError:
                        continue
            
            if not problem_ids:
                await interaction.response.send_message("❌ 유효한 문제 번호가 없습니다.", ephemeral=True)
                return
            
            # 중복 제거 및 정렬
            problem_ids = sorted(list(set(problem_ids)))
            
            # DB에 저장
            create_mock_test(self.name, problem_ids, str(interaction.user.id))
            
            # 알림 전송
            await send_bot_notification(
                interaction.guild,
                "📝 모의테스트 생성",
                f"**모의테스트명:** {self.name}\n"
                f"**문제 수:** {len(problem_ids)}개\n"
                f"**생성자:** {interaction.user.mention}",
                discord.Color.green()
            )
            
            await interaction.response.send_message(
                f"✅ 모의테스트 '{self.name}'이(가) 생성되었습니다!\n문제 수: {len(problem_ids)}개",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"모의테스트 생성 오류: {e}", exc_info=True)
            await interaction.response.send_message("❌ 모의테스트 생성 중 오류가 발생했습니다.", ephemeral=True)


class MockTestCreateView(discord.ui.View):
    """모의테스트 생성 버튼 View"""
    def __init__(self, name: str, author: discord.Member):
        super().__init__(timeout=300)
        self.name = name
        self.author = author
    
    @discord.ui.button(label='문제 번호 입력', style=discord.ButtonStyle.primary)
    async def create_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        modal = MockTestCreateModal(self.name)
        await interaction.response.send_modal(modal)


class MockTestUpdateModal(discord.ui.Modal, title="모의테스트 수정"):
    """모의테스트 수정 Modal"""
    
    def __init__(self, name: str, existing_problems: str):
        super().__init__(timeout=300)
        self.name = name
        
        self.problems_input = discord.ui.TextInput(
            label="문제 번호 (쉼표로 구분)",
            placeholder="1000, 1001, 1002",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000,
            default=existing_problems,
        )
        self.add_item(self.problems_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 문제 번호 파싱
            problems_text = self.problems_input.value.strip()
            problem_ids = []
            
            for part in problems_text.split(','):
                part = part.strip()
                if part:
                    try:
                        problem_id = int(part)
                        if problem_id > 0:
                            problem_ids.append(problem_id)
                    except ValueError:
                        continue
            
            if not problem_ids:
                await interaction.response.send_message("❌ 유효한 문제 번호가 없습니다.", ephemeral=True)
                return
            
            # 중복 제거 및 정렬
            problem_ids = sorted(list(set(problem_ids)))
            
            # DB에 저장
            update_mock_test(self.name, problem_ids)
            
            await interaction.response.send_message(
                f"✅ 모의테스트 '{self.name}'이(가) 수정되었습니다!\n문제 수: {len(problem_ids)}개",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"모의테스트 수정 오류: {e}", exc_info=True)
            await interaction.response.send_message("❌ 모의테스트 수정 중 오류가 발생했습니다.", ephemeral=True)


class MockTestUpdateView(discord.ui.View):
    """모의테스트 수정 버튼 View"""
    def __init__(self, name: str, existing_problems: str, author: discord.Member):
        super().__init__(timeout=300)
        self.name = name
        self.existing_problems = existing_problems
        self.author = author
    
    @discord.ui.button(label='문제 번호 수정', style=discord.ButtonStyle.primary)
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        modal = MockTestUpdateModal(self.name, self.existing_problems)
        await interaction.response.send_modal(modal)


class MockTestDeleteConfirmView(discord.ui.View):
    """모의테스트 삭제 확인 버튼 View"""
    
    def __init__(self, name: str, author: discord.Member):
        super().__init__(timeout=300)
        self.name = name
        self.author = author
    
    @discord.ui.button(label='✅ 삭제', style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        # 삭제
        delete_mock_test(self.name)
        
        # 알림 전송
        await send_bot_notification(
            interaction.guild,
            "🗑️ 모의테스트 삭제",
            f"**모의테스트명:** {self.name}\n"
            f"**삭제자:** {interaction.user.mention}",
            discord.Color.red()
        )
        
        await interaction.response.edit_message(
            content=f"✅ 모의테스트 '{self.name}'이(가) 삭제되었습니다.",
            embed=None,
            view=None
        )
    
    @discord.ui.button(label='❌ 취소', style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="❌ 모의테스트 삭제가 취소되었습니다.",
            embed=None,
            view=None
        )
