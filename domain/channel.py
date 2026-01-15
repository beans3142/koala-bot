"""
채널 관리 명령어 (그룹 생성)
"""
import discord
from discord.ext import commands
from datetime import datetime, timedelta, time
from common.utils import load_data, save_data, get_kst_now
from common.database import (
    get_role_users,
    save_group_weekly_status,
    get_group_weekly_status,
    get_group_weekly_status_by_message,
    get_all_group_weekly_status,
    delete_group_weekly_status,
)
from common.boj_utils import get_weekly_solved_count
from discord.ext import tasks

def find_role_by_group_name(group_name: str, data: dict) -> str:
    """그룹 이름으로 역할 이름 찾기 (대소문자/공백 무시)"""
    target = (group_name or "").strip().lower()
    studies = data.get('studies', {})
    for role_name, study_data in studies.items():
        stored_group = (study_data.get('group_name') or role_name or "").strip().lower()
        stored_role = (role_name or "").strip().lower()
        # 그룹 이름 필드 또는 역할 이름(키)과 일치하면 반환
        if target == stored_group or target == stored_role:
            return role_name
    return None


# 그룹 주간 현황 자동 갱신용
_bot_for_group_weekly = None


async def update_group_weekly_status(group_name: str, bot_instance):
    """특정 그룹의 주간 문제풀이 현황 메시지 갱신 (기존 메시지 편집)"""
    status_info = get_group_weekly_status(group_name)
    if not status_info:
        return

    channel_id = int(status_info['channel_id'])
    message_id = int(status_info['message_id'])
    role_name = status_info['role_name']
    week_start = datetime.fromisoformat(status_info['week_start'])
    week_end = datetime.fromisoformat(status_info['week_end'])

    now = get_kst_now()  # 한국 시간 사용
    # 기간 밖이면 갱신하지 않음
    if not (week_start <= now <= week_end):
        return

    channel = bot_instance.get_channel(channel_id)
    if not channel:
        return

    try:
        message = await channel.fetch_message(message_id)
    except discord.NotFound:
        delete_group_weekly_status(group_name)
        return

    # 최신 데이터 로드
    data = load_data()

    # 역할을 가진 유저 목록 가져오기
    users = get_role_users(role_name)
    if not users:
        embed = discord.Embed(
            title=f"📊 '{group_name}' 그룹 백준 문제풀이 현황",
            description=(
                f"기간: {week_start.strftime('%Y-%m-%d %H:%M')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
                f"마지막 갱신: {now.strftime('%Y-%m-%d %H:%M')}\n"
                f"(멤버 없음)"
            ),
            color=discord.Color.blue(),
        )
        await message.edit(embed=embed, view=GroupWeeklyStatusView())
        return

    # 각 유저의 백준 문제풀이 현황 조회
    results = []
    seen_user_ids = set()  # 중복 제거용
    guild = channel.guild if channel else None
    
    for user_info in users:
        user_id = user_info['user_id']
        
        # 중복 제거
        if user_id in seen_user_ids:
            continue
        seen_user_ids.add(user_id)
        
        username = user_info['username']
        boj_handle = user_info.get('boj_handle')
        
        # Discord 서버에서 멤버 정보 가져오기 (display_name 사용)
        display_name = username
        if guild:
            member = guild.get_member(int(user_id))
            if member:
                display_name = member.display_name

        if not boj_handle or boj_handle == '미등록':
            results.append(
                {
                    'username': display_name,  # display_name 사용
                    'boj_handle': boj_handle or '미등록',
                    'solved_count': 0,
                    'status': '❌ BOJ 핸들 미등록',
                }
            )
            continue

        try:
            solved_data = await get_weekly_solved_count(boj_handle, week_start, week_end)
            results.append(
                {
                    'username': display_name,  # display_name 사용
                    'boj_handle': boj_handle,
                    'solved_count': solved_data['count'],
                    'problems': solved_data.get('problems', []),
                    'status': '✅' if solved_data['count'] > 0 else '⚠️',
                }
            )
        except Exception as e:
            results.append(
                {
                    'username': display_name,  # display_name 사용
                    'boj_handle': boj_handle,
                    'solved_count': 0,
                    'status': f'❌ 오류: {str(e)[:30]}',
                }
            )

    # 결과 정렬 (해결한 문제 수 많은 순)
    results.sort(key=lambda x: x['solved_count'], reverse=True)

    embed = discord.Embed(
        title=f"📊 '{group_name}' 그룹 백준 문제풀이 현황",
        description=(
            f"기간: {week_start.strftime('%Y-%m-%d %H:%M')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
            f"마지막 갱신: {now.strftime('%Y-%m-%d %H:%M')}"
        ),
        color=discord.Color.blue(),
    )

    member_list = []
    total_solved = 0
    seen_user_ids = set()  # 중복 제거용
    
    for i, result in enumerate(results[:25], 1):
        status_icon = result['status']
        username = result['username']
        boj_handle = result['boj_handle']
        solved_count = result['solved_count']
        total_solved += solved_count

        rank_label = {1: "👑", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")

        # 디스코드 이름 (백준 ID) 형식으로 표시
        if boj_handle == '미등록':
            name_display = username
            member_list.append(f"{rank_label} {name_display} - {status_icon} BOJ 핸들 미등록")
        else:
            name_display = f"{username} ({boj_handle})"
            problems = result.get('problems', [])
            if solved_count == 0:
                member_list.append(f"{rank_label} {name_display} - {status_icon} 0개")
            else:
                # solved.ac 기반 계산에서는 문제 번호 목록이 없을 수 있으므로,
                # 목록이 비어 있으면 개수만 표시하고, 있을 때만 대괄호로 문제 번호를 보여준다.
                if not problems:
                    member_list.append(f"{rank_label} {name_display} - {status_icon} {solved_count}개")
                else:
                    problems_sorted = sorted(problems)
                    if len(problems_sorted) <= 15:
                        problems_str = ", ".join(map(str, problems_sorted))
                        member_list.append(
                            f"{rank_label} {name_display} - {status_icon} {solved_count}개 [{problems_str}]"
                        )
                    else:
                        problems_str = ", ".join(map(str, problems_sorted[:15]))
                        remaining = len(problems_sorted) - 15
                        member_list.append(
                            f"{rank_label} {name_display} - {status_icon} {solved_count}개 [{problems_str}, ... 외 {remaining}개]"
                        )

    if len(results) > 25:
        member_list.append(f"\n... 외 {len(results) - 25}명")

    embed.add_field(
        name="멤버별 문제풀이 현황",
        value="\n".join(member_list) if member_list else "멤버 없음",
        inline=False,
    )

    active_members = len([r for r in results if r['solved_count'] > 0])
    embed.add_field(
        name="📈 통계",
        value=(
            f"총 멤버: {len(results)}명\n"
            f"문제 풀은 멤버: {active_members}명\n"
            f"총 해결한 문제: {total_solved}개"
        ),
        inline=False,
    )

    # DB에 마지막 갱신 시간 저장
    save_group_weekly_status(
        group_name,
        role_name,
        str(channel_id),
        str(message_id),
        week_start.isoformat(),
        week_end.isoformat(),
        now.isoformat(),
    )

    await message.edit(embed=embed, view=GroupWeeklyStatusView())


@tasks.loop(time=[time(hour=h, minute=0) for h in range(0, 24)])
async def group_weekly_auto_update():
    """매시 정각 그룹 주간 현황 자동 갱신"""
    global _bot_for_group_weekly
    if not _bot_for_group_weekly:
        return

    now = datetime.now()
    for info in get_all_group_weekly_status():
        week_start = datetime.fromisoformat(info['week_start'])
        week_end = datetime.fromisoformat(info['week_end'])

        if week_start <= now <= week_end:
            await update_group_weekly_status(info['group_name'], _bot_for_group_weekly)
        elif now > week_end:
            # 기간이 지난 그룹은 DB에서 정리 (메시지는 그대로 둠)
            delete_group_weekly_status(info['group_name'])


class GroupWeeklyStatusView(discord.ui.View):
    """그룹 주간 현황 수동 갱신 버튼 View (persistent)"""

    def __init__(self):
        super().__init__(timeout=None)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        # 버튼 콜백에서 예외가 나면 "상호작용 실패"처럼 보일 수 있어서 사용자에게 안내
        try:
            msg = f"❌ 갱신 처리 중 오류가 발생했습니다: {type(error).__name__}: {error}"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    @discord.ui.button(
        label="갱신", emoji="🔄", style=discord.ButtonStyle.secondary, custom_id="group_weekly_refresh"
    )
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 메시지 기준으로 그룹 찾기
        info = get_group_weekly_status_by_message(str(interaction.channel.id), str(interaction.message.id))
        if not info:
            if interaction.response.is_done():
                await interaction.followup.send("❌ 이 메시지는 주간 현황으로 등록되어 있지 않습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 이 메시지는 주간 현황으로 등록되어 있지 않습니다.", ephemeral=True)
            return

        week_start = datetime.fromisoformat(info['week_start'])
        week_end = datetime.fromisoformat(info['week_end'])
        now = datetime.now()

        if not (week_start <= now <= week_end):
            if interaction.response.is_done():
                await interaction.followup.send("⚠️ 이 메시지의 기간이 종료되어 더 이상 갱신할 수 없습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ 이 메시지의 기간이 종료되어 더 이상 갱신할 수 없습니다.", ephemeral=True)
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        await update_group_weekly_status(info['group_name'], interaction.client)
        await interaction.followup.send("✅ 주간 현황이 갱신되었습니다.", ephemeral=True)


def register_group_weekly_views(bot):
    """봇 재시작 후에도 그룹 주간 현황 버튼이 작동하도록 persistent view 등록"""
    try:
        bot.add_view(GroupWeeklyStatusView())
        print(f"[OK] 그룹 주간 현황 persistent view 등록 완료 (custom_id: group_weekly_refresh)")
    except Exception as e:
        print(f"[ERROR] 그룹 주간 현황 persistent view 등록 실패: {e}")


def start_group_weekly_scheduler(bot):
    """그룹 주간 현황 자동 갱신 스케줄러 시작"""
    global _bot_for_group_weekly
    _bot_for_group_weekly = bot
    if not group_weekly_auto_update.is_running():
        group_weekly_auto_update.start()
def setup(bot):
    """봇에 명령어 등록"""
    
    @bot.group(name='그룹')
    async def group_group(ctx):
        """그룹 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 올바른 명령어를 입력해주세요. `/그룹 생성 <이름> <역할>` 형식으로 입력해주세요.")

    @group_group.command(name='생성')
    async def group_create(ctx, group_name: str, role_name: str):
        """그룹 생성 (카테고리 및 채널 자동 생성)"""
        # 역할 확인
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            await ctx.send(f"❌ '{role_name}' 역할을 찾을 수 없습니다.")
            return
        
        # 이미 같은 이름의 카테고리가 있는지 확인
        existing_category = discord.utils.get(ctx.guild.categories, name=group_name)
        if existing_category:
            await ctx.send(f"❌ '{group_name}' 이름의 카테고리가 이미 존재합니다.")
            return
        
        # 권한 오버라이드 설정
        # @everyone은 접근 불가
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)
        }
        
        try:
            # 카테고리 생성
            await ctx.send(f"🔄 '{group_name}' 그룹을 생성하는 중...")
            category = await ctx.guild.create_category(group_name, overwrites=overwrites)
            
            # 공지 채널 생성 (Announcement Channel) - 맨 앞에
            created_channels = []
            try:
                announcement_channel = await category.create_text_channel(
                    '공지',
                    type=discord.ChannelType.news,  # 공지 채널 타입
                    overwrites=overwrites
                )
                created_channels.append(announcement_channel.mention)
            except:
                # 공지 채널 생성 실패 시 일반 텍스트 채널로 생성
                announcement_channel = await category.create_text_channel('공지', overwrites=overwrites)
                created_channels.append(announcement_channel.mention)
            
            # 텍스트 채널 생성
            text_channels = ['풀이현황', '자유', '해설', '과제제출']
            for channel_name in text_channels:
                channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                created_channels.append(channel.mention)
            
            # 음성 채널 생성
            voice_channels = ['자유1', '자유2']
            for channel_name in voice_channels:
                channel = await category.create_voice_channel(channel_name, overwrites=overwrites)
                created_channels.append(channel.mention)
            
            # 완료 메시지
            embed = discord.Embed(
                title=f"✅ 그룹 '{group_name}' 생성 완료",
                description=f"**역할:** {role.mention}\n**카테고리:** {category.name}",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="생성된 텍스트 채널",
                value="\n".join([f"• {ch}" for ch in created_channels[:5]]),  # 공지 + 풀이현황 + 자유 + 해설 + 과제제출
                inline=False
            )
            
            embed.add_field(
                name="생성된 음성 채널",
                value="\n".join([f"• {ch}" for ch in created_channels[5:]]),  # 자유1 + 자유2
                inline=False
            )
            
            # 데이터베이스에 그룹 정보 저장
            data = load_data()
            if 'studies' not in data:
                data['studies'] = {}
            if role_name not in data['studies']:
                data['studies'][role_name] = {
                    'assignments': {},
                    'created_at': datetime.now().isoformat(),
                    'role_name': role_name,
                    'group_name': group_name
                }
            else:
                data['studies'][role_name]['group_name'] = group_name
            
            save_data(data)
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ 봇에게 채널을 생성할 권한이 없습니다. 서버 관리자에게 문의해주세요.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ 채널 생성 중 오류가 발생했습니다: {str(e)}")
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {str(e)}")

    # 그룹 과제 서브그룹
    @group_group.group(name='과제')
    async def group_assignment_group(ctx):
        """그룹 과제 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 올바른 명령어를 입력해주세요. `/그룹 과제 생성 링크제출 <그룹명>` 또는 `/그룹 과제 생성 문제풀이 <그룹명>` 형식으로 입력해주세요.")

    @group_assignment_group.group(name='생성')
    async def group_assignment_create_group(ctx):
        """그룹 과제 생성 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 올바른 명령어를 입력해주세요. `/그룹 과제 생성 링크제출 <그룹명>` 또는 `/그룹 과제 생성 문제풀이 <그룹명>` 형식으로 입력해주세요.")

    @group_assignment_create_group.command(name='링크제출')
    @commands.has_permissions(administrator=True)
    async def group_assignment_create_link_submission(ctx, *, group_name: str):
        """그룹 주간 링크 제출 메시지 생성 (관리자 전용)
        - 해당 채널에 고정 메시지 1개 생성
        - 월요일 00시 ~ 다음 주 월요일 01시까지 제출 가능
        - 정각 자동 갱신 + 수동 버튼 갱신
        """
        from domain.link_submission import (
            save_group_link_submission_status,
            update_link_submission_status,
            LinkSubmissionView,
        )

        data = load_data()

        # 그룹 이름으로 역할 찾기
        role_name = find_role_by_group_name(group_name, data)
        if not role_name:
            await ctx.send(
                f"❌ '{group_name}' 그룹을 찾을 수 없습니다.\n💡 `/그룹 목록` 명령어로 등록된 그룹을 확인하세요."
            )
            return

        # 역할 등록 여부 확인
        if role_name not in data.get('role_tokens', {}):
            await ctx.send(
                f"❌ '{group_name}' 그룹에 연결된 역할('{role_name}')이 등록되지 않았습니다."
            )
            return

        # 기준 주 계산 (명령어 실행일이 속한 주의 월요일 00시 ~ 다음 주 월요일 01시)
        today = datetime.now()
        days_since_monday = today.weekday()  # 0=월요일
        week_start = today - timedelta(days=days_since_monday)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7, hours=1)

        # 초기 임베드
        embed = discord.Embed(
            title=f"📝 '{group_name}' 그룹 풀이 제출",
            description=(
                f"기간: {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
                f"마지막 갱신: -"
            ),
            color=discord.Color.blue(),
        )

        msg = await ctx.send(embed=embed, view=LinkSubmissionView())

        # DB에 저장
        save_group_link_submission_status(
            group_name,
            role_name,
            str(ctx.channel.id),
            str(msg.id),
            week_start.isoformat(),
            week_end.isoformat(),
        )

        # 즉시 1회 갱신
        await update_link_submission_status(group_name, ctx.bot)
        await ctx.send(
            f"✅ '{group_name}' 그룹의 주간 링크 제출 메시지가 설정되었습니다.\n"
            f"📅 매시 정각 자동 갱신, 버튼으로 수동 갱신 및 제출 가능합니다."
        )

    @group_assignment_create_group.command(name='문제풀이')
    @commands.has_permissions(administrator=True)
    async def group_assignment_create_problem_solving(ctx, *, group_name: str):
        """그룹 주간 문제풀이 현황 메시지 생성 (관리자 전용)
        - 해당 채널에 고정 메시지 1개 생성
        - 월요일 00시 ~ 다음 주 월요일 01시까지 정각 자동 갱신 + 수동 버튼 갱신
        """
        data = load_data()

        # 그룹 이름으로 역할 찾기
        role_name = find_role_by_group_name(group_name, data)
        if not role_name:
            await ctx.send(
                f"❌ '{group_name}' 그룹을 찾을 수 없습니다.\n💡 `/그룹 목록` 명령어로 등록된 그룹을 확인하세요."
            )
            return

        # 역할 등록 여부 확인
        if role_name not in data.get('role_tokens', {}):
            await ctx.send(f"❌ '{group_name}' 그룹에 연결된 역할('{role_name}')이 등록되지 않았습니다.")
            return

        # 기준 주 계산 (명령어 실행일이 속한 주의 월요일 00시 ~ 다음 주 월요일 01시)
        today = datetime.now()
        days_since_monday = today.weekday()  # 0=월요일
        week_start = today - timedelta(days=days_since_monday)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7, hours=1)

        # 초기 임베드
        embed = discord.Embed(
            title=f"📊 '{group_name}' 그룹 백준 문제풀이 현황",
            description=(
                f"기간: {week_start.strftime('%Y-%m-%d %H:%M')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
                f"마지막 갱신: -"
            ),
            color=discord.Color.blue(),
        )

        msg = await ctx.send(embed=embed, view=GroupWeeklyStatusView())

        # DB에 저장
        save_group_weekly_status(
            group_name,
            role_name,
            str(ctx.channel.id),
            str(msg.id),
            week_start.isoformat(),
            week_end.isoformat(),
        )

        # 즉시 1회 갱신
        await update_group_weekly_status(group_name, ctx.bot)
        await ctx.send(
            f"✅ '{group_name}' 그룹의 주간 문제풀이 현황 메시지가 설정되었습니다.\n"
            f"📅 매시 정각 자동 갱신, 버튼으로 수동 갱신 가능합니다."
        )

    @group_assignment_group.command(name='갱신')
    @commands.has_permissions(administrator=True)
    async def group_assignment_refresh(ctx, assignment_type: str, *, group_name: str):
        """그룹 과제 현황 갱신 (관리자 전용)
        
        assignment_type: '링크제출' 또는 '문제풀이'
        """
        if assignment_type not in ['링크제출', '문제풀이']:
            await ctx.send("❌ 과제 유형은 '링크제출' 또는 '문제풀이'만 가능합니다.")
            return

        data = load_data()
        role_name = find_role_by_group_name(group_name, data)
        if not role_name:
            await ctx.send(
                f"❌ '{group_name}' 그룹을 찾을 수 없습니다.\n💡 `/그룹 목록` 명령어로 등록된 그룹을 확인하세요."
            )
            return

        if assignment_type == '링크제출':
            from domain.link_submission import update_link_submission_status
            await update_link_submission_status(group_name, ctx.bot)
            await ctx.send(f"✅ '{group_name}' 그룹의 링크 제출 현황이 갱신되었습니다.")
        elif assignment_type == '문제풀이':
            await update_group_weekly_status(group_name, ctx.bot)
            await ctx.send(f"✅ '{group_name}' 그룹의 문제풀이 현황이 갱신되었습니다.")

    @group_assignment_group.command(name='삭제')
    @commands.has_permissions(administrator=True)
    async def group_assignment_delete(ctx, assignment_type: str, *, group_name: str):
        """그룹 과제 삭제 (관리자 전용)
        
        assignment_type: '링크제출' 또는 '문제풀이'
        - DB에서 정보만 삭제 (메시지는 채널에 그대로 남음)
        """
        if assignment_type not in ['링크제출', '문제풀이']:
            await ctx.send("❌ 과제 유형은 '링크제출' 또는 '문제풀이'만 가능합니다.")
            return

        data = load_data()
        role_name = find_role_by_group_name(group_name, data)
        if not role_name:
            await ctx.send(
                f"❌ '{group_name}' 그룹을 찾을 수 없습니다.\n💡 `/그룹 목록` 명령어로 등록된 그룹을 확인하세요."
            )
            return

        if assignment_type == '링크제출':
            from domain.link_submission import (
                get_group_link_submission_status,
                delete_group_link_submission_status,
            )
            from common.database import delete_all_link_submissions_by_group
            info = get_group_link_submission_status(group_name)
            if not info:
                await ctx.send(f"❌ '{group_name}' 그룹의 링크 제출 메시지를 찾을 수 없습니다.")
                return
            delete_group_link_submission_status(group_name)
            # 해당 그룹의 모든 링크 제출 데이터도 삭제
            delete_all_link_submissions_by_group(group_name)
            channel = ctx.guild.get_channel(int(info['channel_id']))
            channel_name = channel.mention if channel else f"<#{info['channel_id']}>"
            await ctx.send(
                f"✅ '{group_name}' 그룹의 링크 제출 메시지 정보 및 제출 데이터가 삭제되었습니다.\n"
                f"📝 메시지는 {channel_name}에 그대로 남아있습니다."
            )
        elif assignment_type == '문제풀이':
            info = get_group_weekly_status(group_name)
            if not info:
                await ctx.send(f"❌ '{group_name}' 그룹의 주간 현황 메시지를 찾을 수 없습니다.")
                return
            delete_group_weekly_status(group_name)
            channel = ctx.guild.get_channel(int(info['channel_id']))
            channel_name = channel.mention if channel else f"<#{info['channel_id']}>"
            await ctx.send(
                f"✅ '{group_name}' 그룹의 주간 현황 메시지 정보가 삭제되었습니다.\n"
                f"📝 메시지는 {channel_name}에 그대로 남아있습니다."
            )

    @group_assignment_group.command(name='목록')
    @commands.has_permissions(administrator=True)
    async def group_assignment_list(ctx, *, group_name: str):
        """그룹 과제 목록 확인 (관리자 전용)
        
        특정 그룹의 링크제출과 문제풀이 현황 메시지 목록을 확인합니다.
        """
        from common.database import (
            get_group_weekly_status,
            get_group_link_submission_status,
        )
        
        data = load_data()
        role_name = find_role_by_group_name(group_name, data)
        if not role_name:
            await ctx.send(
                f"❌ '{group_name}' 그룹을 찾을 수 없습니다.\n💡 `/그룹 목록` 명령어로 등록된 그룹을 확인하세요."
            )
            return
        
        # 링크제출 현황 확인
        link_status = get_group_link_submission_status(group_name)
        # 문제풀이 현황 확인
        problem_status = get_group_weekly_status(group_name)
        
        if not link_status and not problem_status:
            await ctx.send(f"❌ '{group_name}' 그룹에 생성된 과제가 없습니다.")
            return
        
        embed = discord.Embed(
            title=f"📋 '{group_name}' 그룹 과제 목록",
            color=discord.Color.blue()
        )
        
        now = datetime.now()
        assignment_list = []
        
        # 링크제출 현황
        if link_status:
            channel_id = link_status['channel_id']
            week_start = datetime.fromisoformat(link_status['week_start'])
            week_end = datetime.fromisoformat(link_status['week_end'])
            
            channel = ctx.guild.get_channel(int(channel_id))
            channel_name = channel.mention if channel else f"<#{channel_id}>"
            
            if now < week_start:
                status = "⏳ 시작 전"
            elif week_start <= now <= week_end:
                status = "🟢 진행 중"
            else:
                status = "🔴 종료됨"
            
            assignment_list.append(
                f"**📝 링크제출**\n"
                f"채널: {channel_name}\n"
                f"기간: {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
                f"상태: {status}\n"
            )
        
        # 문제풀이 현황
        if problem_status:
            channel_id = problem_status['channel_id']
            week_start = datetime.fromisoformat(problem_status['week_start'])
            week_end = datetime.fromisoformat(problem_status['week_end'])
            
            channel = ctx.guild.get_channel(int(channel_id))
            channel_name = channel.mention if channel else f"<#{channel_id}>"
            
            if now < week_start:
                status = "⏳ 시작 전"
            elif week_start <= now <= week_end:
                status = "🟢 진행 중"
            else:
                status = "🔴 종료됨"
            
            assignment_list.append(
                f"**📊 문제풀이**\n"
                f"채널: {channel_name}\n"
                f"기간: {week_start.strftime('%Y-%m-%d %H:%M')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
                f"상태: {status}\n"
            )
        
        embed.description = "\n\n".join(assignment_list) if assignment_list else "과제 없음"
        await ctx.send(embed=embed)

    @group_group.command(name='주간현황목록')
    @commands.has_permissions(administrator=True)
    async def group_weekly_status_list(ctx):
        """생성된 그룹 주간 현황 메시지 목록 확인 (관리자 전용)"""
        from common.database import get_all_group_weekly_status
        
        all_status = get_all_group_weekly_status()
        
        if not all_status:
            await ctx.send("❌ 생성된 주간 현황 메시지가 없습니다.")
            return
        
        embed = discord.Embed(
            title="📋 생성된 그룹 주간 현황 목록",
            color=discord.Color.blue()
        )
        
        status_list = []
        now = datetime.now()
        for info in all_status:
            group_name = info['group_name']
            channel_id = info['channel_id']
            week_start = datetime.fromisoformat(info['week_start'])
            week_end = datetime.fromisoformat(info['week_end'])
            
            # 채널 정보 가져오기
            channel = ctx.guild.get_channel(int(channel_id))
            channel_name = channel.mention if channel else f"<#{channel_id}>"
            
            # 기간 상태 확인
            if now < week_start:
                status = "⏳ 시작 전"
            elif week_start <= now <= week_end:
                status = "🟢 진행 중"
            else:
                status = "🔴 종료됨"
            
            status_list.append(
                f"**{group_name}**\n"
                f"채널: {channel_name}\n"
                f"기간: {week_start.strftime('%Y-%m-%d %H:%M')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
                f"상태: {status}\n"
            )
        
        embed.description = "\n".join(status_list)
        await ctx.send(embed=embed)

    @group_group.command(name='주간현황삭제')
    @commands.has_permissions(administrator=True)
    async def group_weekly_status_delete(ctx, *, group_name: str):
        """그룹 주간 현황 메시지 삭제 (관리자 전용)
        - DB에서 정보만 삭제 (메시지는 채널에 그대로 남음)
        """
        from common.database import get_group_weekly_status, delete_group_weekly_status
        
        info = get_group_weekly_status(group_name)
        if not info:
            await ctx.send(f"❌ '{group_name}' 그룹의 주간 현황 메시지를 찾을 수 없습니다.")
            return
        
        # DB에서 삭제
        delete_group_weekly_status(group_name)
        
        channel = ctx.guild.get_channel(int(info['channel_id']))
        channel_name = channel.mention if channel else f"<#{info['channel_id']}>"
        
        await ctx.send(
            f"✅ '{group_name}' 그룹의 주간 현황 메시지 정보가 삭제되었습니다.\n"
            f"📝 메시지는 {channel_name}에 그대로 남아있습니다."
        )

    @group_group.command(name='문제풀이현황')
    @commands.has_permissions(administrator=True)
    async def group_problem_status(ctx, *, group_name: str):
        """특정 그룹 멤버들의 최근 7일(월~일) 백준 문제풀이 현황 (관리자 전용)"""
        data = load_data()
        
        # 그룹 이름으로 역할 찾기
        role_name = find_role_by_group_name(group_name, data)
        if not role_name:
            await ctx.send(f"❌ '{group_name}' 그룹을 찾을 수 없습니다.\n💡 `/그룹 목록` 명령어로 등록된 그룹을 확인하세요.")
            return
        
        # 역할이 등록되어 있는지 확인
        if role_name not in data.get('role_tokens', {}):
            await ctx.send(f"❌ '{group_name}' 그룹에 연결된 역할('{role_name}')이 등록되지 않았습니다.")
            return
        
        # 역할을 가진 유저 목록 가져오기
        users = get_role_users(role_name)
        
        if not users:
            await ctx.send(f"❌ '{group_name}' 그룹에 멤버가 없습니다.")
            return
        
        # 이번 주 월요일~일요일 계산
        today = datetime.now()
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        await ctx.send(f"🔄 최근 7일간(월~일) 백준 문제풀이 현황을 조회하는 중...\n📅 기간: {monday.strftime('%Y-%m-%d')} ~ {sunday.strftime('%Y-%m-%d')}")
        
        # 각 유저의 백준 문제풀이 현황 조회
        results = []
        for user_info in users:
            username = user_info['username']
            boj_handle = user_info.get('boj_handle')
            
            if not boj_handle or boj_handle == '미등록':
                results.append({
                    'username': username,
                    'boj_handle': boj_handle or '미등록',
                    'solved_count': 0,
                    'status': '❌ BOJ 핸들 미등록'
                })
                continue
            
            # 백준에서 최근 7일간 해결한 문제 수 조회
            try:
                solved_data = await get_weekly_solved_count(boj_handle, monday, sunday)
                results.append({
                    'username': username,
                    'boj_handle': boj_handle,
                    'solved_count': solved_data['count'],
                    'problems': solved_data.get('problems', []),
                    'status': '✅' if solved_data['count'] > 0 else '⚠️'
                })
            except Exception as e:
                results.append({
                    'username': username,
                    'boj_handle': boj_handle,
                    'solved_count': 0,
                    'status': f'❌ 오류: {str(e)[:30]}'
                })
        
        # 결과 정렬 (해결한 문제 수 많은 순)
        results.sort(key=lambda x: x['solved_count'], reverse=True)
        
        # 임베드 생성
        embed = discord.Embed(
            title=f"📊 '{group_name}' 그룹 백준 문제풀이 현황",
            description=f"기간: {monday.strftime('%Y-%m-%d')} ~ {sunday.strftime('%Y-%m-%d')} (월~일)",
            color=discord.Color.blue()
        )
        
        # 멤버별 현황 표시 (최대 25명, Discord 임베드 제한)
        member_list = []
        total_solved = 0
        for i, result in enumerate(results[:25], 1):
            status_icon = result['status']
            username = result['username']
            boj_handle = result['boj_handle']
            solved_count = result['solved_count']
            total_solved += solved_count
            
            if boj_handle == '미등록':
                member_list.append(f"{i}. {username} - {status_icon} BOJ 핸들 미등록")
            else:
                problems = result.get('problems', [])
                if solved_count == 0:
                    member_list.append(f"{i}. {boj_handle} - {status_icon} 0개")
                else:
                    # solved.ac 기반 계산에서는 문제 번호 목록이 없을 수 있으므로,
                    # 목록이 비어 있으면 개수만 표시하고, 있을 때만 대괄호로 문제 번호를 보여준다.
                    if not problems:
                        member_list.append(f"{i}. {boj_handle} - {status_icon} {solved_count}개")
                    else:
                        problems_sorted = sorted(problems)
                        if len(problems_sorted) <= 15:
                            problems_str = ", ".join(map(str, problems_sorted))
                            member_list.append(f"{i}. {boj_handle} - {status_icon} {solved_count}개 [{problems_str}]")
                        else:
                            problems_str = ", ".join(map(str, problems_sorted[:15]))
                            remaining = len(problems_sorted) - 15
                            member_list.append(f"{i}. {boj_handle} - {status_icon} {solved_count}개 [{problems_str}, ... 외 {remaining}개]")
        
        if len(results) > 25:
            member_list.append(f"\n... 외 {len(results) - 25}명")
        
        embed.add_field(
            name="멤버별 문제풀이 현황",
            value="\n".join(member_list) if member_list else "멤버 없음",
            inline=False
        )
        
        # 통계
        active_members = len([r for r in results if r['solved_count'] > 0])
        embed.add_field(
            name="📈 통계",
            value=f"총 멤버: {len(results)}명\n문제 풀은 멤버: {active_members}명\n총 해결한 문제: {total_solved}개",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @group_group.command(name='제출현황')
    @commands.has_permissions(administrator=True)
    async def group_submissions(ctx, *, role_name: str):
        """그룹 제출 현황 확인 (관리자 전용)"""
        from common.utils import load_data
        
        data = load_data()
        
        # 그룹(역할) 확인
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            await ctx.send(f"❌ '{role_name}' 그룹(역할)을 찾을 수 없습니다.")
            return
        
        # 해당 역할을 가진 멤버 찾기
        members_with_role = [member for member in ctx.guild.members if role in member.roles]
        
        if not members_with_role:
            await ctx.send(f"❌ '{role_name}' 그룹에 등록된 멤버가 없습니다.")
            return
        
        # 과제 정보 가져오기
        studies = data.get('studies', {})
        study_data = studies.get(role_name, {})
        assignments = study_data.get('assignments', {})
        
        if not assignments:
            await ctx.send(f"❌ '{role_name}' 그룹에 등록된 과제가 없습니다.")
            return
        
        # 제출 현황 생성
        embed = discord.Embed(
            title=f"📊 {role_name} 그룹 제출 현황",
            color=discord.Color.blue()
        )
        
        # 각 멤버별 제출 현황
        for member in members_with_role[:20]:  # 최대 20명
            user_id = str(member.id)
            user_data = data.get('users', {}).get(user_id, {})
            submissions = user_data.get('submissions', {})
            
            submission_info = []
            for assignment_id, assignment_info in assignments.items():
                assignment_type = assignment_info.get('type')
                user_submissions = submissions.get(assignment_id, [])
                
                if assignment_type == '블로그':
                    required_count = assignment_info.get('config', {}).get('count', 0)
                    submitted_count = len(user_submissions)
                    status = "✅" if submitted_count >= required_count else f"⚠️ {submitted_count}/{required_count}"
                    submission_info.append(f"{assignment_info.get('name', assignment_id)}: {status}")
                elif assignment_type == '문제풀이':
                    required_problems = assignment_info.get('config', {}).get('problems', [])
                    solved_count = sum(1 for sub in user_submissions if sub.get('verified', False))
                    status = "✅" if solved_count >= len(required_problems) else f"⚠️ {solved_count}/{len(required_problems)}"
                    submission_info.append(f"{assignment_info.get('name', assignment_id)}: {status}")
                elif assignment_type == '모의테스트':
                    submitted = len(user_submissions) > 0
                    status = "✅" if submitted else "❌"
                    submission_info.append(f"{assignment_info.get('name', assignment_id)}: {status}")
            
            if submission_info:
                embed.add_field(
                    name=member.display_name,
                    value="\n".join(submission_info),
                    inline=False
                )
        
        await ctx.send(embed=embed)

    @group_group.command(name='목록')
    @commands.has_permissions(administrator=True)
    async def group_list(ctx):
        """등록된 그룹 목록 확인 (관리자 전용)"""
        data = load_data()
        studies = data.get('studies', {})
        
        if not studies:
            await ctx.send("❌ 등록된 그룹이 없습니다.")
            return
        
        embed = discord.Embed(
            title="📋 등록된 그룹 목록",
            color=discord.Color.blue()
        )
        
        for role_name, study_data in studies.items():
            group_name = study_data.get('group_name', role_name)
            assignments = study_data.get('assignments', {})
            assignment_count = len(assignments)
            
            # 역할 확인
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            role_mention = role.mention if role else role_name
            
            embed.add_field(
                name=f"📚 {group_name}",
                value=f"**역할:** {role_mention}\n**과제 수:** {assignment_count}개",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @group_group.command(name='정보')
    @commands.has_permissions(administrator=True)
    async def group_info(ctx):
        """그룹 정보 조회 (관리자 전용)
        
        소속 인원, 과제 현황, 과제 제출 요약을 GUI로 확인합니다.
        
        사용법: /그룹 정보
        """
        data = load_data()
        studies = data.get('studies', {})
        
        if not studies:
            await ctx.send("❌ 등록된 그룹이 없습니다.")
            return
        
        # 현재 서버에 존재하는 역할 기준으로만 필터링
        available_roles = []
        for role_name, study_data in studies.items():
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if not role:
                continue
            group_name = study_data.get('group_name', role_name)
            available_roles.append((role_name, group_name))
        
        if not available_roles:
            await ctx.send("❌ 이 서버에서 사용할 수 있는 그룹이 없습니다.")
            return
        
        view = GroupInfoSelectView(available_roles, ctx.author)
        embed = discord.Embed(
            title="📚 그룹 정보",
            description="정보를 조회할 그룹을 선택하세요.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=view)

    @group_group.command(name='수정')
    @commands.has_permissions(administrator=True)
    async def group_modify(ctx, role_name: str, *, new_group_name: str):
        """그룹 이름 수정 (관리자 전용)"""
        data = load_data()
        
        if role_name not in data.get('studies', {}):
            await ctx.send(f"❌ '{role_name}' 그룹을 찾을 수 없습니다.")
            return
        
        # 역할 확인
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            await ctx.send(f"❌ '{role_name}' 역할을 찾을 수 없습니다.")
            return
        
        # 카테고리 이름 변경 시도
        old_group_name = data['studies'][role_name].get('group_name', role_name)
        category = discord.utils.get(ctx.guild.categories, name=old_group_name)
        
        if category:
            try:
                await category.edit(name=new_group_name)
            except discord.Forbidden:
                await ctx.send("❌ 봇에게 카테고리 이름을 변경할 권한이 없습니다.")
                return
            except Exception as e:
                await ctx.send(f"⚠️ 카테고리 이름 변경 실패: {str(e)}")
        
        # 데이터베이스 업데이트
        data['studies'][role_name]['group_name'] = new_group_name
        save_data(data)
        
        await ctx.send(f"✅ 그룹 이름이 '{old_group_name}'에서 '{new_group_name}'으로 변경되었습니다.")

    @group_group.command(name='삭제')
    @commands.has_permissions(administrator=True)
    async def group_delete(ctx, role_name: str):
        """그룹 삭제 (관리자 전용) - 데이터만 삭제, 카테고리는 수동 삭제"""
        data = load_data()
        
        if role_name not in data.get('studies', {}):
            await ctx.send(f"❌ '{role_name}' 그룹을 찾을 수 없습니다.")
            return
        
        # 그룹 정보 확인
        group_name = data['studies'][role_name].get('group_name', role_name)
        assignments = data['studies'][role_name].get('assignments', {})
        assignment_count = len(assignments)
        
        # 확인 View 생성
        view = GroupDeleteConfirmView(role_name, group_name, assignment_count, ctx.author)
        
        embed = discord.Embed(
            title="⚠️ 그룹 삭제 확인",
            description=f"**그룹:** {group_name}\n**역할:** {role_name}\n**과제 수:** {assignment_count}개\n\n"
                       f"이 작업은 되돌릴 수 없습니다!\n\n"
                       f"삭제되는 데이터:\n"
                       f"• 그룹 정보\n"
                       f"• 모든 과제 ({assignment_count}개)\n"
                       f"• 모든 제출 기록\n\n"
                       f"**참고:** 카테고리와 채널은 수동으로 삭제해야 합니다.\n\n"
                       f"정말 삭제하시겠습니까?",
            color=discord.Color.red()
        )
        
        await ctx.send(embed=embed, view=view)

    @group_group.command(name='전체삭제')
    @commands.has_permissions(administrator=True)
    async def group_delete_full(ctx, role_name: str):
        """그룹 전체 삭제 (관리자 전용) - 데이터, 카테고리, 채널 모두 삭제"""
        data = load_data()
        
        if role_name not in data.get('studies', {}):
            await ctx.send(f"❌ '{role_name}' 그룹을 찾을 수 없습니다.")
            return
        
        # 그룹 정보 확인
        group_name = data['studies'][role_name].get('group_name', role_name)
        assignments = data['studies'][role_name].get('assignments', {})
        assignment_count = len(assignments)
        
        # 카테고리 확인
        category = discord.utils.get(ctx.guild.categories, name=group_name)
        channel_count = len(category.channels) if category else 0
        
        # 확인 View 생성
        view = GroupFullDeleteConfirmView(role_name, group_name, assignment_count, channel_count, ctx.author)
        
        embed = discord.Embed(
            title="⚠️ 그룹 전체 삭제 확인",
            description=f"**그룹:** {group_name}\n**역할:** {role_name}\n**과제 수:** {assignment_count}개\n**채널 수:** {channel_count}개\n\n"
                       f"이 작업은 되돌릴 수 없습니다!\n\n"
                       f"삭제되는 항목:\n"
                       f"• 그룹 정보\n"
                       f"• 모든 과제 ({assignment_count}개)\n"
                       f"• 모든 제출 기록\n"
                       f"• 카테고리 및 모든 채널 ({channel_count}개)\n\n"
                       f"**경고:** 이 작업은 완전히 되돌릴 수 없습니다!\n\n"
                       f"정말 전체 삭제하시겠습니까?",
            color=discord.Color.red()
        )
        
        await ctx.send(embed=embed, view=view)

    class GroupInfoSelectView(discord.ui.View):
        """그룹 정보를 선택해서 보는 View"""
        
        def __init__(self, roles, author):
            super().__init__(timeout=300)
            self.roles = roles  # list of (role_name, group_name)
            self.author = author
            
            options = [
                discord.SelectOption(
                    label=group_name,
                    description=f"역할: {role_name}",
                    value=role_name
                )
                for role_name, group_name in roles[:25]
            ]
            
            self.select = discord.ui.Select(
                placeholder="그룹을 선택하세요...",
                options=options
            )
            self.select.callback = self.on_select
            self.add_item(self.select)
        
        async def on_select(self, interaction: discord.Interaction):
            if interaction.user != self.author:
                await interaction.response.send_message(
                    "❌ 이 메뉴는 명령어를 실행한 사용자만 사용할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            role_name = self.select.values[0]
            
            from common.utils import load_data
            data = load_data()
            
            studies = data.get('studies', {})
            study_data = studies.get(role_name)
            if not study_data:
                await interaction.response.send_message("❌ 그룹 데이터를 찾을 수 없습니다.", ephemeral=True)
                return
            
            group_name = study_data.get('group_name', role_name)
            guild = interaction.guild
            role = discord.utils.get(guild.roles, name=role_name)
            
            # 소속 인원 (discord id(BOJ 핸들) 형식)
            members = [m for m in guild.members if role in m.roles] if role else []
            member_count = len(members)
            users_data = data.get('users', {})
            
            # 과제 현황 (진행중 / 시작 전 / 종료)
            assignments = study_data.get('assignments', {})
            now = datetime.now()
            
            ongoing = []
            upcoming = []
            ended = []
            
            for assignment_id, assignment_info in assignments.items():
                a_type = assignment_info.get('type')
                a_name = assignment_info.get('name', assignment_id)
                config = assignment_info.get('config', {})
                start_date = config.get('start_date')
                deadline = config.get('deadline')
                
                start_str = ""
                end_str = ""
                status = "진행중"
                
                try:
                    if start_date:
                        sd = datetime.fromisoformat(start_date)
                        start_str = sd.strftime("%Y-%m-%d %H:%M")
                        if now < sd:
                            status = "시작 전"
                    if deadline:
                        dd = datetime.fromisoformat(deadline)
                        end_str = dd.strftime("%Y-%m-%d %H:%M")
                        if now > dd:
                            status = "종료"
                except Exception:
                    pass
                
                line = f"• {a_name} ({a_type})"
                if start_str or end_str:
                    line += f"\n  기간: {start_str or '?'} ~ {end_str or '?'}"
                
                if status == "진행중":
                    ongoing.append(line)
                elif status == "시작 전":
                    upcoming.append(line)
                else:
                    ended.append(line)
            
            # 제출 현황 요약 (과제별 완료 인원 수)
            summary_lines = []
            member_ids = [str(m.id) for m in members]
            
            for assignment_id, assignment_info in assignments.items():
                a_type = assignment_info.get('type')
                a_name = assignment_info.get('name', assignment_id)
                config = assignment_info.get('config', {})
                
                completed = 0
                total = len(member_ids)
                
                for uid in member_ids:
                    user = users_data.get(uid, {})
                    submissions = user.get('submissions', {}).get(assignment_id, [])
                    
                    if a_type == '블로그':
                        required_count = config.get('count', 0)
                        if required_count > 0 and len(submissions) >= required_count:
                            completed += 1
                    elif a_type == '문제풀이':
                        required_problems = config.get('problems', [])
                        if required_problems:
                            solved = [s.get('problem_id') for s in submissions if s.get('verified', False)]
                            if all(p in solved for p in required_problems):
                                completed += 1
                        else:
                            # 자유 문제풀이: 하나라도 인증된 제출이 있으면 완료
                            if any(s.get('verified', False) for s in submissions):
                                completed += 1
                    elif a_type == '모의테스트':
                        # 인증된 제출이 있거나, 제출이 하나라도 있으면 완료로 간주
                        if any(s.get('verified', False) for s in submissions) or submissions:
                            completed += 1
                
                if total > 0:
                    summary_lines.append(
                        f"• {a_name} ({a_type}) - 완료 {completed}/{total}명"
                    )
            
            # 페이지네이션 View 생성
            view = GroupInfoPaginationView(
                role_name, group_name, members, users_data, assignments, 
                ongoing, upcoming, ended, summary_lines, member_ids, self.author
            )
            
            # 첫 페이지 표시
            embed = view.get_page(0)
            await interaction.response.edit_message(embed=embed, view=view)
    
    class GroupInfoPaginationView(discord.ui.View):
        """그룹 정보 페이지네이션 View"""
        
        def __init__(self, role_name, group_name, members, users_data, assignments, 
                     ongoing, upcoming, ended, summary_lines, member_ids, author):
            super().__init__(timeout=300)
            self.role_name = role_name
            self.group_name = group_name
            self.members = members
            self.users_data = users_data
            self.assignments = assignments
            self.ongoing = ongoing
            self.upcoming = upcoming
            self.ended = ended
            self.summary_lines = summary_lines
            self.member_ids = member_ids
            self.author = author
            self.current_page = 0
            
            # 총 페이지 수 계산
            # 페이지 0: 기본 정보
            # 페이지 1~N: 각 과제별 상세 정보
            self.total_pages = 1 + len(assignments)
            self.update_buttons()
        
        def update_buttons(self):
            """버튼 상태 업데이트"""
            self.clear_items()
            
            # 이전 페이지 버튼
            prev_button = discord.ui.Button(
                label='◀ 이전',
                style=discord.ButtonStyle.secondary,
                disabled=self.current_page == 0
            )
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
            
            # 페이지 표시 버튼
            page_button = discord.ui.Button(
                label=f'{self.current_page + 1}/{self.total_pages}',
                style=discord.ButtonStyle.primary,
                disabled=True
            )
            self.add_item(page_button)
            
            # 다음 페이지 버튼
            next_button = discord.ui.Button(
                label='다음 ▶',
                style=discord.ButtonStyle.secondary,
                disabled=self.current_page >= self.total_pages - 1
            )
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        def get_page(self, page_num):
            """특정 페이지의 Embed 생성"""
            if page_num == 0:
                return self.get_summary_page()
            else:
                # 과제별 상세 페이지
                assignment_list = list(self.assignments.items())
                if page_num - 1 < len(assignment_list):
                    assignment_id, assignment_info = assignment_list[page_num - 1]
                    return self.get_assignment_detail_page(assignment_id, assignment_info)
                else:
                    return self.get_summary_page()
        
        def get_summary_page(self):
            """요약 페이지 (페이지 0)"""
            embed = discord.Embed(
                title=f"📚 {self.group_name} 그룹 정보",
                color=discord.Color.blue()
            )
            
            # 소속 인원 (discord id(BOJ 핸들) 형식)
            member_count = len(self.members)
            if self.members:
                member_lines = []
                for m in self.members[:25]:  # 최대 25명
                    uid = str(m.id)
                    user_data = self.users_data.get(uid, {})
                    boj_handle = user_data.get('boj_handle', '미등록')
                    member_lines.append(f"{m.display_name} ({boj_handle})")
                
                member_text = "\n".join(member_lines)
                if member_count > 25:
                    member_text += f"\n... 외 {member_count - 25}명"
            else:
                member_text = "등록된 인원이 없습니다."
            
            embed.add_field(
                name="👥 소속 인원",
                value=f"총 {member_count}명\n{member_text}",
                inline=False
            )
            
            # 과제 현황 필드
            if self.ongoing or self.upcoming or self.ended:
                status_texts = []
                if self.ongoing:
                    status_texts.append("**진행중**\n" + "\n".join(self.ongoing))
                if self.upcoming:
                    status_texts.append("\n**시작 전**\n" + "\n".join(self.upcoming))
                if self.ended:
                    status_texts.append("\n**종료됨**\n" + "\n".join(self.ended))
                
                status_text = "\n".join(status_texts)
                if len(status_text) > 1024:
                    status_text = status_text[:1021] + "..."
                
                embed.add_field(
                    name="📝 과제 현황",
                    value=status_text,
                    inline=False
                )
            else:
                embed.add_field(
                    name="📝 과제 현황",
                    value="등록된 과제가 없습니다.",
                    inline=False
                )
            
            # 제출 현황 요약 필드
            if self.summary_lines:
                summary_text = "\n".join(self.summary_lines)
                if len(summary_text) > 1024:
                    summary_text = summary_text[:1021] + "..."
                
                embed.add_field(
                    name="📊 제출 현황 요약",
                    value=summary_text,
                    inline=False
                )
            
            embed.set_footer(text="◀ 이전/다음 ▶ 버튼으로 상세 정보를 확인하세요")
            
            return embed
        
        def get_assignment_detail_page(self, assignment_id, assignment_info):
            """과제별 상세 페이지"""
            a_type = assignment_info.get('type')
            a_name = assignment_info.get('name', assignment_id)
            config = assignment_info.get('config', {})
            
            embed = discord.Embed(
                title=f"📋 {a_name} ({a_type}) 상세 정보",
                color=discord.Color.green()
            )
            
            # 기간 정보
            start_date = config.get('start_date')
            deadline = config.get('deadline')
            if start_date or deadline:
                try:
                    start_str = ""
                    end_str = ""
                    if start_date:
                        sd = datetime.fromisoformat(start_date)
                        start_str = sd.strftime("%Y-%m-%d %H:%M")
                    if deadline:
                        dd = datetime.fromisoformat(deadline)
                        end_str = dd.strftime("%Y-%m-%d %H:%M")
                    
                    embed.add_field(
                        name="⏰ 기간",
                        value=f"{start_str or '?'} ~ {end_str or '?'}",
                        inline=False
                    )
                except:
                    pass
            
            if a_type == '문제풀이':
                # 문제풀이 과제: 각 문제별로 사람들의 완료 여부 표시
                required_problems = config.get('problems', [])
                
                if required_problems:
                    # 지정된 문제 리스트가 있는 경우
                    for problem_id in required_problems:
                        problem_lines = []
                        completed_count = 0
                        
                        for m in self.members:
                            uid = str(m.id)
                            user_data = self.users_data.get(uid, {})
                            submissions = user_data.get('submissions', {}).get(assignment_id, [])
                            
                            solved = [s.get('problem_id') for s in submissions if s.get('verified', False)]
                            boj_handle = user_data.get('boj_handle', '미등록')
                            
                            if problem_id in solved:
                                problem_lines.append(f"✅ {m.display_name} ({boj_handle})")
                                completed_count += 1
                            else:
                                problem_lines.append(f"❌ {m.display_name} ({boj_handle})")
                        
                        problem_text = "\n".join(problem_lines[:20])  # 최대 20명
                        if len(self.members) > 20:
                            problem_text += f"\n... 외 {len(self.members) - 20}명"
                        
                        if len(problem_text) > 1024:
                            problem_text = problem_text[:1021] + "..."
                        
                        embed.add_field(
                            name=f"문제 {problem_id} - 완료 {completed_count}/{len(self.members)}명",
                            value=problem_text,
                            inline=False
                        )
                else:
                    # 자유 문제풀이: 제출한 문제 목록 표시
                    member_problems = {}
                    for m in self.members:
                        uid = str(m.id)
                        user_data = self.users_data.get(uid, {})
                        submissions = user_data.get('submissions', {}).get(assignment_id, [])
                        boj_handle = user_data.get('boj_handle', '미등록')
                        
                        solved_problems = [s.get('problem_id') for s in submissions if s.get('verified', False)]
                        if solved_problems:
                            member_problems[m.display_name] = {
                                'boj_handle': boj_handle,
                                'problems': solved_problems
                            }
                    
                    if member_problems:
                        problem_lines = []
                        for name, info in list(member_problems.items())[:15]:  # 최대 15명
                            problems_str = ", ".join(map(str, info['problems'][:10]))  # 최대 10개 문제
                            if len(info['problems']) > 10:
                                problems_str += f" 외 {len(info['problems']) - 10}개"
                            problem_lines.append(f"✅ {name} ({info['boj_handle']}): {problems_str}")
                        
                        problem_text = "\n".join(problem_lines)
                        if len(member_problems) > 15:
                            problem_text += f"\n... 외 {len(member_problems) - 15}명"
                        
                        if len(problem_text) > 1024:
                            problem_text = problem_text[:1021] + "..."
                        
                        embed.add_field(
                            name=f"제출 현황 - {len(member_problems)}/{len(self.members)}명 제출",
                            value=problem_text,
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="제출 현황",
                            value="아직 제출한 인원이 없습니다.",
                            inline=False
                        )
            
            elif a_type == '블로그':
                # 블로그 과제: 제출한 인원 목록
                required_count = config.get('count', 0)
                member_submissions = {}
                
                for m in self.members:
                    uid = str(m.id)
                    user_data = self.users_data.get(uid, {})
                    submissions = user_data.get('submissions', {}).get(assignment_id, [])
                    boj_handle = user_data.get('boj_handle', '미등록')
                    
                    if submissions:
                        member_submissions[m.display_name] = {
                            'boj_handle': boj_handle,
                            'count': len(submissions),
                            'required': required_count
                        }
                
                if member_submissions:
                    submission_lines = []
                    for name, info in list(member_submissions.items())[:20]:  # 최대 20명
                        status_icon = "✅" if info['count'] >= info['required'] else "⚠️"
                        submission_lines.append(f"{status_icon} {name} ({info['boj_handle']}): {info['count']}/{info['required']}개")
                    
                    submission_text = "\n".join(submission_lines)
                    if len(member_submissions) > 20:
                        submission_text += f"\n... 외 {len(member_submissions) - 20}명"
                    
                    if len(submission_text) > 1024:
                        submission_text = submission_text[:1021] + "..."
                    
                    embed.add_field(
                        name=f"제출 현황 - {len(member_submissions)}/{len(self.members)}명 제출",
                        value=submission_text,
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="제출 현황",
                        value="아직 제출한 인원이 없습니다.",
                        inline=False
                    )
            
            elif a_type == '모의테스트':
                # 모의테스트 과제: 제출 및 인증 현황
                problem_ids = config.get('problem_ids', [])
                member_status = {}
                
                for m in self.members:
                    uid = str(m.id)
                    user_data = self.users_data.get(uid, {})
                    submissions = user_data.get('submissions', {}).get(assignment_id, [])
                    boj_handle = user_data.get('boj_handle', '미등록')
                    
                    verified = any(s.get('verified', False) for s in submissions)
                    if problem_ids:
                        verified_submissions = [s for s in submissions if s.get('verified', False)]
                        if verified_submissions:
                            solved_problems = verified_submissions[0].get('solved_problems', [])
                            member_status[m.display_name] = {
                                'boj_handle': boj_handle,
                                'verified': verified,
                                'solved_count': len(solved_problems),
                                'total': len(problem_ids)
                            }
                        else:
                            member_status[m.display_name] = {
                                'boj_handle': boj_handle,
                                'verified': False,
                                'solved_count': 0,
                                'total': len(problem_ids)
                            }
                    else:
                        member_status[m.display_name] = {
                            'boj_handle': boj_handle,
                            'verified': verified,
                            'submitted': len(submissions) > 0
                        }
                
                if member_status:
                    status_lines = []
                    for name, info in list(member_status.items())[:20]:  # 최대 20명
                        if problem_ids:
                            status_icon = "✅" if info['verified'] else "❌"
                            status_lines.append(f"{status_icon} {name} ({info['boj_handle']}): {info['solved_count']}/{info['total']}개 해결")
                        else:
                            status_icon = "✅" if info.get('submitted', False) else "❌"
                            status_lines.append(f"{status_icon} {name} ({info['boj_handle']}): {'제출 완료' if info.get('submitted', False) else '미제출'}")
                    
                    status_text = "\n".join(status_lines)
                    if len(member_status) > 20:
                        status_text += f"\n... 외 {len(member_status) - 20}명"
                    
                    if len(status_text) > 1024:
                        status_text = status_text[:1021] + "..."
                    
                    embed.add_field(
                        name=f"제출 현황 - {len(member_status)}/{len(self.members)}명",
                        value=status_text,
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="제출 현황",
                        value="아직 제출한 인원이 없습니다.",
                        inline=False
                    )
            
            embed.set_footer(text=f"페이지 {self.current_page + 1}/{self.total_pages}")
            
            return embed
        
        async def prev_page(self, interaction: discord.Interaction):
            if interaction.user != self.author:
                await interaction.response.send_message(
                    "❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            if self.current_page > 0:
                self.current_page -= 1
                self.update_buttons()
                embed = self.get_page(self.current_page)
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.defer()
        
        async def next_page(self, interaction: discord.Interaction):
            if interaction.user != self.author:
                await interaction.response.send_message(
                    "❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            if self.current_page < self.total_pages - 1:
                self.current_page += 1
                self.update_buttons()
                embed = self.get_page(self.current_page)
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.defer()

    class GroupDeleteConfirmView(discord.ui.View):
        """그룹 삭제 확인 버튼 View"""
        
        def __init__(self, role_name, group_name, assignment_count, author):
            super().__init__(timeout=300)
            self.role_name = role_name
            self.group_name = group_name
            self.assignment_count = assignment_count
            self.author = author
        
        @discord.ui.button(label='✅ 삭제', style=discord.ButtonStyle.danger)
        async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
                return
            
            from common.utils import load_data, save_data
            from common.database import get_study_assignments, delete_assignment
            
            data = load_data()
            
            if self.role_name not in data.get('studies', {}):
                await interaction.response.send_message("❌ 그룹을 찾을 수 없습니다.", ephemeral=True)
                return
            
            # 해당 그룹의 모든 과제 ID 가져오기
            assignments = data['studies'][self.role_name].get('assignments', {})
            assignment_ids = list(assignments.keys())
            
            # DB에서 과제 삭제
            for assignment_id in assignment_ids:
                try:
                    delete_assignment(assignment_id)
                except Exception as e:
                    print(f"[그룹 삭제] 과제 삭제 오류 (무시 가능): {assignment_id} - {e}")
            
            # 데이터에서 그룹 삭제
            del data['studies'][self.role_name]
            save_data(data)
            
            await interaction.response.edit_message(
                content=f"✅ 그룹 '{self.group_name}'의 데이터가 삭제되었습니다.\n"
                       f"📊 삭제된 과제: {self.assignment_count}개\n"
                       f"💡 카테고리와 채널은 수동으로 삭제해주세요.",
                embed=None,
                view=None
            )
        
        @discord.ui.button(label='❌ 취소', style=discord.ButtonStyle.secondary)
        async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
                return
            
            await interaction.response.edit_message(
                content="❌ 그룹 삭제가 취소되었습니다.",
                embed=None,
                view=None
            )

    class GroupFullDeleteConfirmView(discord.ui.View):
        """그룹 전체 삭제 확인 버튼 View"""
        
        def __init__(self, role_name, group_name, assignment_count, channel_count, author):
            super().__init__(timeout=300)
            self.role_name = role_name
            self.group_name = group_name
            self.assignment_count = assignment_count
            self.channel_count = channel_count
            self.author = author
        
        @discord.ui.button(label='✅ 전체 삭제', style=discord.ButtonStyle.danger)
        async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            from common.utils import load_data, save_data
            from common.database import get_study_assignments, delete_assignment
            
            data = load_data()
            
            if self.role_name not in data.get('studies', {}):
                await interaction.followup.send("❌ 그룹을 찾을 수 없습니다.", ephemeral=True)
                return
            
            deleted_channels = 0
            deleted_category = False
            
            # 카테고리 찾기 및 삭제
            try:
                category = discord.utils.get(interaction.guild.categories, name=self.group_name)
                if category:
                    # 카테고리 내의 모든 채널 삭제
                    for channel in category.channels:
                        try:
                            await channel.delete()
                            deleted_channels += 1
                        except discord.Forbidden:
                            await interaction.followup.send(f"⚠️ 채널 '{channel.name}' 삭제 권한이 없습니다.", ephemeral=True)
                        except Exception as e:
                            await interaction.followup.send(f"⚠️ 채널 '{channel.name}' 삭제 중 오류: {str(e)}", ephemeral=True)
                    
                    # 카테고리 삭제
                    try:
                        await category.delete()
                        deleted_category = True
                    except discord.Forbidden:
                        await interaction.followup.send("⚠️ 카테고리 삭제 권한이 없습니다.", ephemeral=True)
                    except Exception as e:
                        await interaction.followup.send(f"⚠️ 카테고리 삭제 중 오류: {str(e)}", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"⚠️ 카테고리/채널 삭제 중 오류: {str(e)}", ephemeral=True)
            
            # 해당 그룹의 모든 과제 ID 가져오기
            assignments = data['studies'][self.role_name].get('assignments', {})
            assignment_ids = list(assignments.keys())
            
            # DB에서 과제 삭제
            for assignment_id in assignment_ids:
                try:
                    delete_assignment(assignment_id)
                except Exception as e:
                    print(f"[그룹 전체삭제] 과제 삭제 오류 (무시 가능): {assignment_id} - {e}")
            
            # 데이터에서 그룹 삭제
            del data['studies'][self.role_name]
            save_data(data)
            
            result_message = f"✅ 그룹 '{self.group_name}' 전체 삭제 완료\n"
            result_message += f"📊 삭제된 과제: {self.assignment_count}개\n"
            if deleted_category:
                result_message += f"🗂️ 카테고리 삭제 완료\n"
            if deleted_channels > 0:
                result_message += f"📁 삭제된 채널: {deleted_channels}개"
            
            if not deleted_category:
                result_message += "\n⚠️ 카테고리 삭제에 실패했습니다. 수동으로 삭제해주세요."
            
            await interaction.followup.send(result_message, ephemeral=True)
            
            # 원래 메시지도 업데이트
            try:
                await interaction.edit_original_response(
                    content=result_message,
                    embed=None,
                    view=None
                )
            except:
                pass
        
        @discord.ui.button(label='❌ 취소', style=discord.ButtonStyle.secondary)
        async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
                return
            
            await interaction.response.edit_message(
                content="❌ 그룹 전체 삭제가 취소되었습니다.",
                embed=None,
                view=None
            )

    @bot.group(name='채널')
    async def channel_group(ctx):
        """채널 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 올바른 명령어를 입력해주세요. `/도움말`을 확인해주세요.")

    @channel_group.command(name='공지')
    @commands.has_permissions(administrator=True)
    async def create_announcement(ctx, channel_name: str, role_name: str = None):
        """공지 채널 생성 (관리자 전용)"""
        # 이미 같은 이름의 채널이 있는지 확인
        existing_channel = discord.utils.get(ctx.guild.channels, name=channel_name)
        if existing_channel:
            await ctx.send(f"❌ '{channel_name}' 이름의 채널이 이미 존재합니다.")
            return
        
        # 권한 오버라이드 설정
        overwrites = {}
        if role_name:
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if not role:
                await ctx.send(f"❌ '{role_name}' 역할을 찾을 수 없습니다.")
                return
            
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_messages=True,
                    manage_messages=True  # 공지 채널은 관리 권한도 필요
                )
            }
        
        try:
            # 공지 채널 생성
            channel = await ctx.guild.create_text_channel(
                channel_name,
                type=discord.ChannelType.news,  # 공지 채널 타입
                overwrites=overwrites if overwrites else None
            )
            
            await ctx.send(f"✅ 공지 채널 '{channel_name}'이 생성되었습니다! {channel.mention}")
        except discord.Forbidden:
            await ctx.send("❌ 봇에게 채널을 생성할 권한이 없습니다. 서버 관리자에게 문의해주세요.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ 채널 생성 중 오류가 발생했습니다: {str(e)}")
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {str(e)}")

    @channel_group.command(name='포럼')
    @commands.has_permissions(administrator=True)
    async def create_forum(ctx, channel_name: str, role_name: str = None):
        """포럼 채널 생성 (관리자 전용)"""
        # 이미 같은 이름의 채널이 있는지 확인
        existing_channel = discord.utils.get(ctx.guild.channels, name=channel_name)
        if existing_channel:
            await ctx.send(f"❌ '{channel_name}' 이름의 채널이 이미 존재합니다.")
            return
        
        # 권한 오버라이드 설정
        overwrites = {}
        if role_name:
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if not role:
                await ctx.send(f"❌ '{role_name}' 역할을 찾을 수 없습니다.")
                return
            
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_messages=True,
                    create_public_threads=True,
                    create_private_threads=True
                )
            }
        
        try:
            # 포럼 채널 생성
            channel = await ctx.guild.create_forum_channel(
                channel_name,
                overwrites=overwrites if overwrites else None
            )
            
            await ctx.send(f"✅ 포럼 채널 '{channel_name}'이 생성되었습니다! {channel.mention}")
        except discord.Forbidden:
            await ctx.send("❌ 봇에게 채널을 생성할 권한이 없습니다. 서버 관리자에게 문의해주세요.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ 채널 생성 중 오류가 발생했습니다: {str(e)}")
        except AttributeError:
            await ctx.send("❌ 포럼 채널 생성은 Discord.py 2.0 이상 버전이 필요합니다.")
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {str(e)}")

