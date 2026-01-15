"""
그룹 주간 링크 제출 관리 명령어
"""
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, time
from common.utils import load_data
from common.database import (
    get_role_users,
    save_group_link_submission_status,
    get_group_link_submission_status,
    get_group_link_submission_status_by_message,
    get_all_group_link_submission_status,
    delete_group_link_submission_status,
    save_link_submission,
    get_link_submissions,
    get_user_link_submission,
    get_user_roles,
    get_user,
)
from discord.ext import tasks

def find_role_by_group_name(group_name: str, data: dict) -> str:
    """그룹 이름으로 역할 이름 찾기 (대소문자/공백 무시)"""
    target = (group_name or "").strip().lower()
    studies = data.get('studies', {})
    for role_name, study_data in studies.items():
        stored_group = (study_data.get('group_name') or role_name or "").strip().lower()
        stored_role = (role_name or "").strip().lower()
        if target == stored_group or target == stored_role:
            return role_name
    return None


# 링크 제출 자동 갱신용
_bot_for_link_submission = None


async def update_link_submission_status(group_name: str, bot_instance):
    """특정 그룹의 주간 링크 제출 현황 메시지 갱신 (기존 메시지 편집)"""
    status_info = get_group_link_submission_status(group_name)
    if not status_info:
        return

    channel_id = int(status_info['channel_id'])
    message_id = int(status_info['message_id'])
    role_name = status_info['role_name']
    week_start = datetime.fromisoformat(status_info['week_start'])
    week_end = datetime.fromisoformat(status_info['week_end'])

    now = datetime.now()
    # 기간 밖이면 갱신하지 않음
    if not (week_start <= now <= week_end):
        return

    channel = bot_instance.get_channel(channel_id)
    if not channel:
        return

    try:
        message = await channel.fetch_message(message_id)
    except discord.NotFound:
        delete_group_link_submission_status(group_name)
        return

    # 최신 데이터 로드
    data = load_data()

    # 역할을 가진 유저 목록 가져오기
    users = get_role_users(role_name)
    if not users:
        embed = discord.Embed(
            title=f"📝 '{group_name}' 그룹 풀이 제출",
            description=(
                f"기간: {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
                f"마지막 갱신: {now.strftime('%Y-%m-%d %H:%M')}\n"
                f"(멤버 없음)"
            ),
            color=discord.Color.blue(),
        )
        await message.edit(embed=embed, view=LinkSubmissionView())
        return

    # 링크 제출 데이터 가져오기
    week_start_str = week_start.isoformat()
    submissions = get_link_submissions(group_name, week_start_str)

    # 유저별 제출 정보 매핑
    submission_map = {}
    for sub in submissions:
        submission_map[sub['user_id']] = sub['links']

    # 결과 정렬 (제출한 순서대로)
    results = []
    guild = channel.guild if channel else None
    
    for user_info in users:
        user_id = user_info['user_id']
        username = user_info['username']
        links = submission_map.get(user_id, [])

        # Discord 서버에서 멤버 정보 가져오기 (display_name 사용)
        display_name = username
        if guild:
            member = guild.get_member(int(user_id))
            if member:
                display_name = member.display_name

        results.append({
            'user_id': user_id,
            'username': display_name,  # display_name 사용
            'links': links,
        })

    # 제출한 사람들을 먼저, 그 다음 미제출
    results.sort(key=lambda x: (len(x['links']) == 0, x['username']))

    # 메시지 생성 (요청 형식: "2026-01-12 ~ 2026-01-17 풀이 제출\n1. nickname - link1, link2\n...")
    title_text = f"{week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')} 풀이 제출"
    
    submission_lines = []
    for i, result in enumerate(results, 1):
        username = result['username']
        links = result['links']
        if links:
            links_str = ", ".join(links)
            submission_lines.append(f"{i}. {username} - {links_str}")
        else:
            submission_lines.append(f"{i}. {username} - (미제출)")

    embed = discord.Embed(
        title=f"📝 '{group_name}' 그룹 풀이 제출",
        description=(
            f"기간: {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
            f"마지막 갱신: {now.strftime('%Y-%m-%d %H:%M')}"
        ),
        color=discord.Color.blue(),
    )

    if submission_lines:
        submission_text = "\n".join(submission_lines)
        # Discord 임베드 필드 제한 (1024자) 처리
        if len(submission_text) > 1024:
            submission_text = submission_text[:1021] + "..."
        embed.add_field(
            name="제출 현황",
            value=submission_text,
            inline=False,
        )
    else:
        embed.add_field(
            name="제출 현황",
            value="아직 제출한 인원이 없습니다.",
            inline=False,
        )

    # 통계
    submitted_count = len([r for r in results if r['links']])
    total_count = len(results)
    embed.add_field(
        name="📈 통계",
        value=f"총 멤버: {total_count}명\n제출한 멤버: {submitted_count}명",
        inline=False,
    )

    # DB에 마지막 갱신 시간 저장
    save_group_link_submission_status(
        group_name,
        role_name,
        str(channel_id),
        str(message_id),
        week_start.isoformat(),
        week_end.isoformat(),
        now.isoformat(),
    )

    await message.edit(embed=embed, view=LinkSubmissionView())


@tasks.loop(time=[time(hour=h, minute=0) for h in range(0, 24)])
async def link_submission_auto_update():
    """매시 정각 링크 제출 현황 자동 갱신"""
    global _bot_for_link_submission
    if not _bot_for_link_submission:
        return

    now = datetime.now()
    for info in get_all_group_link_submission_status():
        week_start = datetime.fromisoformat(info['week_start'])
        week_end = datetime.fromisoformat(info['week_end'])

        if week_start <= now <= week_end:
            await update_link_submission_status(info['group_name'], _bot_for_link_submission)
        elif now > week_end:
            # 기간이 지난 그룹은 DB에서 정리 (메시지는 그대로 둠)
            delete_group_link_submission_status(info['group_name'])


class LinkSubmissionView(discord.ui.View):
    """링크 제출 현황 수동 갱신 및 제출 버튼 View (persistent)"""

    def __init__(self):
        super().__init__(timeout=None)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        try:
            msg = f"❌ 처리 중 오류가 발생했습니다: {type(error).__name__}: {error}"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    @discord.ui.button(
        label="갱신", emoji="🔄", style=discord.ButtonStyle.secondary, custom_id="link_submission_refresh"
    )
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 메시지 기준으로 그룹 찾기
        info = get_group_link_submission_status_by_message(
            str(interaction.channel.id), str(interaction.message.id)
        )
        if not info:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "❌ 이 메시지는 링크 제출로 등록되어 있지 않습니다.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ 이 메시지는 링크 제출로 등록되어 있지 않습니다.", ephemeral=True
                )
            return

        week_start = datetime.fromisoformat(info['week_start'])
        week_end = datetime.fromisoformat(info['week_end'])
        now = datetime.now()

        if not (week_start <= now <= week_end):
            if interaction.response.is_done():
                await interaction.followup.send(
                    "⚠️ 이 메시지의 기간이 종료되어 더 이상 갱신할 수 없습니다.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "⚠️ 이 메시지의 기간이 종료되어 더 이상 갱신할 수 없습니다.", ephemeral=True
                )
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        await update_link_submission_status(info['group_name'], interaction.client)
        await interaction.followup.send("✅ 링크 제출 현황이 갱신되었습니다.", ephemeral=True)

    @discord.ui.button(
        label="제출", emoji="📝", style=discord.ButtonStyle.primary, custom_id="link_submission_submit"
    )
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 메시지 기준으로 그룹 찾기
        info = get_group_link_submission_status_by_message(
            str(interaction.channel.id), str(interaction.message.id)
        )
        if not info:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "❌ 이 메시지는 링크 제출로 등록되어 있지 않습니다.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ 이 메시지는 링크 제출로 등록되어 있지 않습니다.", ephemeral=True
                )
            return

        week_start = datetime.fromisoformat(info['week_start'])
        week_end = datetime.fromisoformat(info['week_end'])
        now = datetime.now()

        if not (week_start <= now <= week_end):
            if interaction.response.is_done():
                await interaction.followup.send(
                    "⚠️ 제출 기간이 종료되었습니다.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "⚠️ 제출 기간이 종료되었습니다.", ephemeral=True
                )
            return

        # 사용자가 속한 그룹 확인
        user_id = str(interaction.user.id)
        user_roles = get_user_roles(user_id)
        data = load_data()
        studies = data.get('studies', {})

        # 사용자가 속한 그룹 목록 생성
        available_groups = []
        for role_name in user_roles:
            study_data = studies.get(role_name, {})
            group_name = study_data.get('group_name', role_name)
            # 현재 메시지의 그룹과 일치하는지 확인
            if group_name == info['group_name']:
                available_groups.append((role_name, group_name))

        if not available_groups:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "❌ 이 그룹의 멤버가 아닙니다.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ 이 그룹의 멤버가 아닙니다.", ephemeral=True
                )
            return

        # 기존 제출 데이터 가져오기
        week_start_str = week_start.isoformat()
        existing_submission = get_user_link_submission(
            info['group_name'], user_id, week_start_str
        )
        existing_links = existing_submission['links'] if existing_submission else []

        # Modal 표시
        modal = LinkSubmissionModal(
            info['group_name'], week_start_str, existing_links
        )
        await interaction.response.send_modal(modal)


class LinkSubmissionModal(discord.ui.Modal, title="링크 제출"):
    """링크 제출 Modal"""

    def __init__(self, group_name: str, week_start: str, existing_links: list):
        super().__init__(timeout=300)
        self.group_name = group_name
        self.week_start = week_start
        self.existing_links = existing_links

        # 링크 입력 필드
        links_text = "\n".join(existing_links) if existing_links else ""
        self.links_input = discord.ui.TextInput(
            label="링크 (한 줄에 하나씩 입력)",
            placeholder="https://example.com/blog1\nhttps://example.com/blog2",
            style=discord.TextStyle.paragraph,
            default=links_text,
            required=False,
            max_length=2000,
        )
        self.add_item(self.links_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        # 링크 파싱
        links_text = self.links_input.value.strip()
        if not links_text:
            await interaction.response.send_message(
                "❌ 링크를 입력해주세요.", ephemeral=True
            )
            return

        # 줄바꿈으로 구분된 링크 리스트 생성
        links = [link.strip() for link in links_text.split("\n") if link.strip()]

        if not links:
            await interaction.response.send_message(
                "❌ 유효한 링크를 입력해주세요.", ephemeral=True
            )
            return

        # 링크 저장
        save_link_submission(self.group_name, user_id, self.week_start, links)

        # 메시지 갱신
        await update_link_submission_status(self.group_name, interaction.client)

        await interaction.response.send_message(
            f"✅ 링크 제출이 완료되었습니다!\n제출한 링크: {len(links)}개", ephemeral=True
        )


def register_link_submission_views(bot):
    """봇 재시작 후에도 링크 제출 버튼이 작동하도록 persistent view 등록"""
    try:
        bot.add_view(LinkSubmissionView())
        print(f"[OK] 링크 제출 persistent view 등록 완료 (custom_id: link_submission_refresh, link_submission_submit)")
    except Exception as e:
        print(f"[ERROR] 링크 제출 persistent view 등록 실패: {e}")


def start_link_submission_scheduler(bot):
    """링크 제출 자동 갱신 스케줄러 시작"""
    global _bot_for_link_submission
    _bot_for_link_submission = bot
    if not link_submission_auto_update.is_running():
        link_submission_auto_update.start()


def setup(bot):
    """봇에 명령어 등록 (명령어는 domain/channel.py의 /그룹 과제 생성 링크제출로 이동됨)"""
    pass

