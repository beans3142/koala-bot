"""
노션 기반 문제집 풀이현황 (live fetch).

흐름:
  1. /문제집풀이현황 → 노션에서 문제집 목록 live fetch
  2. 셀렉트 3개(문제집/그룹/채널) + 전송 버튼
  3. 전송 시 status 저장 + 임베드 메시지 생성
  4. 4시간 단위 자동 갱신 (00/04/08/12/16/20 KST), 수동 갱신 버튼은 관리자 전용

문제집 데이터는 DB에 저장하지 않음 — 갱신 때마다 노션에서 다시 fetch.
DB에는 (그룹, 문제집명) ↔ 채널/메시지/주차 매핑만 저장.
"""
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, time
from typing import List, Optional

from common.database import (
    get_role_users,
    save_notion_problem_set_status,
    get_notion_problem_set_status,
    get_all_notion_problem_set_status,
    delete_notion_problem_set_status,
)
from common.utils import load_data, get_kst_now, ensure_kst
from common.logger import get_logger
from common.oj import get_solved_for_oj, is_supported
from domain.notion_sync import sync_problem_sets

logger = get_logger()

_bot_for_scheduler = None


# ==================== 주차 계산 ====================

def get_current_week_range():
    """이번 주 월요일 00:00 KST ~ 일요일 23:59:59 KST"""
    now = get_kst_now()
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    sunday_end = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return monday, sunday_end


# ==================== 노션 fetch + 풀이 계산 ====================

async def fetch_problem_set_by_name(name: str) -> Optional[dict]:
    """노션에서 모든 문제집을 가져와 이름이 일치하는 첫 번째 반환"""
    try:
        all_sets = await sync_problem_sets()
    except Exception as e:
        logger.error(f"[notion_problem_set] 노션 fetch 실패: {e}")
        return None
    for ps in all_sets:
        if ps['name'] == name:
            return ps
    return None


async def compute_user_solving(problems: List[dict], users: List[dict]) -> List[dict]:
    """
    각 사용자별로 풀이 현황 계산.
    규칙: 유저가 OJ 핸들을 등록한 OJ의 문제만 그 유저의 합산 대상.
          (예: CF 문제 3개가 있어도 유저가 codeforces_handle 미등록이면
           그 유저의 total_problems 에서 CF 3개는 빠짐)

    반환: [{user_id, name, username, total_solved, total_problems, status, registered_ojs}]
    """
    oj_problems = {}
    for p in problems:
        oj_problems.setdefault(p['oj'], []).append(p['id'])

    results = []
    for user_info in users:
        user_solved = 0
        user_total = 0
        registered_ojs = []
        for oj, pids in oj_problems.items():
            handle_key = f"{oj}_handle" if oj != 'boj' else 'boj_handle'
            handle = user_info.get(handle_key)
            if not handle:
                # 핸들 미등록 → 이 OJ의 문제는 유저 합산에서 제외
                continue
            registered_ojs.append(oj)
            user_total += len(pids)
            try:
                solved_set = await get_solved_for_oj(oj, handle, pids)
            except Exception:
                solved_set = set()
            user_solved += len(solved_set)

        # 상태 이모지
        if user_total == 0:
            # 등록한 핸들이 어떤 OJ도 안 매칭 (또는 문제집에 핸들 등록한 OJ 문제 없음)
            status = "⚠️"
        elif user_solved == user_total:
            status = "✅"
        elif user_solved == 0:
            status = "📝"
        else:
            status = "📝"

        results.append({
            'user_id': user_info.get('user_id'),
            'name': user_info.get('name'),
            'username': user_info.get('username') or 'Unknown',
            'total_solved': user_solved,
            'total_problems': user_total,
            'status': status,
            'registered_ojs': registered_ojs,
        })
    return results


def build_status_embed(problem_set_name: str, group_name: str, week_start: datetime,
                       week_end: datetime, problems: List[dict],
                       results: List[dict], updated_at: datetime,
                       fetch_error: Optional[str] = None) -> discord.Embed:
    """풀이현황 임베드 생성"""
    if fetch_error:
        embed = discord.Embed(
            title=f"📚 [{problem_set_name}] 풀이현황",
            description=f"⚠️ {fetch_error}",
            color=discord.Color.orange(),
        )
        embed.set_footer(text=f"갱신: {updated_at.strftime('%Y-%m-%d %H:%M')}")
        return embed

    # OJ별 문제 수
    oj_count = {}
    for p in problems:
        oj_count[p['oj']] = oj_count.get(p['oj'], 0) + 1
    total = sum(oj_count.values())
    oj_summary = " · ".join(
        f"{oj.upper()} {c}" + ("(?)" if not is_supported(oj) else "")
        for oj, c in sorted(oj_count.items())
    ) or "(문제 없음)"

    embed = discord.Embed(
        title=f"📚 [{problem_set_name}] 풀이현황",
        description=(
            f"**그룹:** {group_name}\n"
            f"**기간:** {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}\n"
            f"**문제:** {oj_summary} (총 {total}개)\n"
            f"**갱신:** {updated_at.strftime('%Y-%m-%d %H:%M')}"
        ),
        color=discord.Color.blue(),
    )

    # 결과 정렬 (총 풀이수 내림차순)
    results = sorted(results, key=lambda r: r['total_solved'], reverse=True)

    if not results:
        embed.add_field(name="멤버", value="(없음)", inline=False)
        return embed

    # 멤버별 현황 (어떤 문제인지는 표시 X — N/M만)
    lines = []
    for i, r in enumerate(results[:25]):
        if i == 0: emoji = "🥇"
        elif i == 1: emoji = "🥈"
        elif i == 2: emoji = "🥉"
        else: emoji = "•"

        display = r['name'] or r['username']
        # 미등록 OJ 안내 (해당 멤버가 핸들 등록 안 한 OJ가 문제집에 있는 경우)
        missing_ojs = [
            oj for oj in oj_count.keys()
            if oj not in r.get('registered_ojs', [])
        ]
        missing_note = (
            f" *(미등록: {', '.join(o.upper() for o in missing_ojs)})*"
            if missing_ojs and r['total_problems'] > 0 else ""
        )
        if r['total_problems'] == 0:
            # 등록 핸들이 0개거나 모든 핸들이 무관한 경우
            missing_note = " *(핸들 미등록)*"

        lines.append(
            f"{emoji} {display} {r['status']} **[{r['total_solved']}/{r['total_problems']}]**{missing_note}"
        )

    if len(results) > 25:
        lines.append(f"... 외 {len(results) - 25}명")

    # field value는 1024자 제한 — 넘치면 잘라냄
    value = "\n".join(lines)
    if len(value) > 1020:
        value = value[:1020] + "..."
    embed.add_field(name="멤버별 풀이 현황", value=value, inline=False)

    # 통계
    solved_all = sum(1 for r in results if r['total_problems'] > 0 and r['total_solved'] == r['total_problems'])
    solved_some = sum(1 for r in results if 0 < r['total_solved'] < r['total_problems'])
    solved_none = sum(1 for r in results if r['total_solved'] == 0)
    embed.add_field(
        name="📈 통계",
        value=(
            f"총 멤버 {len(results)}명 · "
            f"전부 해결 {solved_all} · "
            f"일부 {solved_some} · "
            f"미해결 {solved_none}"
        ),
        inline=False,
    )
    return embed


async def update_status_message(group_name: str, problem_set_name: str, bot_instance):
    """status 1건 갱신 — 노션 fetch + 풀이 계산 + 메시지 edit"""
    info = get_notion_problem_set_status(group_name, problem_set_name)
    if not info:
        return False

    week_start = ensure_kst(datetime.fromisoformat(info['week_start']))
    week_end = ensure_kst(datetime.fromisoformat(info['week_end']))
    now = get_kst_now()

    # 기간 밖이면 skip
    if not (week_start <= now <= week_end + timedelta(minutes=5)):
        return False

    channel = bot_instance.get_channel(int(info['channel_id']))
    if not channel:
        return False

    try:
        message = await channel.fetch_message(int(info['message_id']))
    except discord.NotFound:
        delete_notion_problem_set_status(group_name, problem_set_name)
        return False
    except Exception as e:
        logger.warning(f"[notion_problem_set] 메시지 조회 실패: {e}")
        return False

    # 노션에서 문제집 fetch
    ps = await fetch_problem_set_by_name(problem_set_name)
    if ps is None:
        embed = build_status_embed(
            problem_set_name, group_name, week_start, week_end,
            [], [], now,
            fetch_error="노션에서 문제집을 찾지 못했습니다 (제목이 변경되었거나 페이지 삭제 가능성)."
        )
        await message.edit(embed=embed, view=NotionProblemSetRefreshView())
        return True

    role_name = info['role_name']
    users = get_role_users(role_name)
    results = await compute_user_solving(ps['problems'], users)

    embed = build_status_embed(
        problem_set_name, group_name, week_start, week_end,
        ps['problems'], results, now,
    )
    await message.edit(embed=embed, view=NotionProblemSetRefreshView())

    # 마지막 갱신 시각 저장
    save_notion_problem_set_status(
        group_name, problem_set_name, role_name,
        info['channel_id'], info['message_id'],
        week_start.isoformat(), week_end.isoformat(),
        now.isoformat(),
    )
    return True


# ==================== 자동 갱신 스케줄러 ====================

@tasks.loop(time=[time(hour=h, minute=0) for h in (0, 4, 8, 12, 16, 20)])
async def notion_problem_set_auto_update():
    """4시간 단위 자동 갱신 (00/04/08/12/16/20 KST)"""
    if not _bot_for_scheduler:
        return
    now = get_kst_now()
    for info in get_all_notion_problem_set_status():
        try:
            week_start = ensure_kst(datetime.fromisoformat(info['week_start']))
            week_end = ensure_kst(datetime.fromisoformat(info['week_end']))
        except Exception:
            continue
        if week_start <= now <= week_end:
            try:
                await update_status_message(
                    info['group_name'], info['problem_set_name'], _bot_for_scheduler
                )
            except Exception as e:
                logger.error(
                    f"[notion_problem_set 자동갱신] {info['group_name']} - {info['problem_set_name']}: {e}",
                    exc_info=True
                )


@tasks.loop(time=[time(hour=3, minute=0)])
async def jungol_daily_refresh():
    """매일 새벽 3시 Jungol 캐시 일괄 갱신 (Playwright 사용)"""
    if not _bot_for_scheduler:
        return
    try:
        # 모든 활성 status 의 문제집들에서 Jungol 문제 ID 수집
        from domain.notion_sync import sync_problem_sets
        from common.oj.jungol_scraper import scrape_jungol_problems

        all_status = get_all_notion_problem_set_status()
        if not all_status:
            logger.info("[jungol 일별갱신] 활성 status 없음, skip")
            return

        # 활성 (week_start <= now <= week_end) 인 것만
        now = get_kst_now()
        active_names = set()
        for s in all_status:
            try:
                ws = ensure_kst(datetime.fromisoformat(s['week_start']))
                we = ensure_kst(datetime.fromisoformat(s['week_end']))
            except Exception:
                continue
            if ws <= now <= we:
                active_names.add(s['problem_set_name'])

        if not active_names:
            logger.info("[jungol 일별갱신] 활성 주차의 문제집 없음, skip")
            return

        all_sets = await sync_problem_sets()
        jungol_pids = set()
        active_role_names = set()
        for ps in all_sets:
            if ps['name'] not in active_names:
                continue
            for p in ps['problems']:
                if p['oj'] == 'jungol':
                    jungol_pids.add(str(p['id']))
        # 활성 status 의 그룹들에 속한 멤버의 jungol_handle 모음
        for s in all_status:
            ws = ensure_kst(datetime.fromisoformat(s['week_start']))
            we = ensure_kst(datetime.fromisoformat(s['week_end']))
            if ws <= now <= we:
                active_role_names.add(s['role_name'])

        target_handles = set()
        for role_name in active_role_names:
            for u in get_role_users(role_name):
                jh = u.get('jungol_handle')
                if jh:
                    target_handles.add(jh)

        if not jungol_pids:
            logger.info("[jungol 일별갱신] Jungol 문제 없음, skip")
            return

        logger.info(
            f"[jungol 일별갱신] {len(jungol_pids)}개 문제, 타겟 멤버 {len(target_handles)}명 — 스크래핑 시작"
        )
        await scrape_jungol_problems(
            list(jungol_pids),
            target_handles=target_handles if target_handles else None,
        )
        logger.info("[jungol 일별갱신] 완료")
    except Exception as e:
        logger.error(f"[jungol 일별갱신] 오류: {e}", exc_info=True)


def start_notion_problem_set_scheduler(bot_instance):
    """on_ready 에서 호출"""
    global _bot_for_scheduler
    _bot_for_scheduler = bot_instance
    if not notion_problem_set_auto_update.is_running():
        notion_problem_set_auto_update.start()
        logger.info("[notion_problem_set] 자동 갱신 스케줄러 시작 (4시간 단위 - 00/04/08/12/16/20 KST)")
    if not jungol_daily_refresh.is_running():
        jungol_daily_refresh.start()
        logger.info("[notion_problem_set] Jungol 일별 갱신 스케줄러 시작 (매일 03:00)")


# ==================== 갱신 버튼 (persistent) ====================

class NotionProblemSetRefreshView(discord.ui.View):
    """메시지에 붙는 수동 갱신 버튼 (persistent, custom_id 고정)"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="갱신", emoji="🔄", style=discord.ButtonStyle.secondary,
        custom_id="notion_problem_set_refresh",
    )
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 관리자 전용
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 관리자만 갱신 가능합니다.", ephemeral=True
            )
            return
        # 메시지 기준으로 status 찾기
        all_status = get_all_notion_problem_set_status()
        info = None
        for s in all_status:
            if (str(s['channel_id']) == str(interaction.channel.id)
                    and str(s['message_id']) == str(interaction.message.id)):
                info = s
                break
        if not info:
            await interaction.response.send_message(
                "❌ 이 메시지는 풀이현황으로 등록되어 있지 않습니다.", ephemeral=True
            )
            return

        week_start = ensure_kst(datetime.fromisoformat(info['week_start']))
        week_end = ensure_kst(datetime.fromisoformat(info['week_end']))
        now = get_kst_now()
        if not (week_start <= now <= week_end + timedelta(minutes=5)):
            await interaction.response.send_message(
                "⚠️ 이 메시지의 주차가 종료되어 더 이상 갱신할 수 없습니다.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            ok = await update_status_message(
                info['group_name'], info['problem_set_name'], interaction.client
            )
        except Exception as e:
            logger.error(f"[/갱신] 실패: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 갱신 중 오류: {e}", ephemeral=True)
            return
        if ok:
            await interaction.followup.send("✅ 갱신 완료", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ 갱신 실행되지 않음 (기간 외 또는 메시지 누락)", ephemeral=True)


def register_notion_problem_set_refresh_view(bot):
    """봇 시작 시 persistent view 등록"""
    bot.add_view(NotionProblemSetRefreshView())


# ==================== 등록 폼 (셀렉트 3개 + 페이지네이션) ====================

class NotionProblemSetSetupView(discord.ui.View):
    """
    문제집/그룹/채널 셀렉트 + 전송 버튼.
    문제집 25개 초과 시 ◀ ▶ 페이지네이션.
    """

    def __init__(
        self,
        author: discord.Member,
        problem_sets: List[dict],
        groups: List[tuple],  # (role_name, group_name)
    ):
        super().__init__(timeout=600)
        self.author = author
        self.problem_sets = problem_sets
        self.groups = groups
        self.ps_page = 0
        self.ps_pages = max(1, (len(problem_sets) + 24) // 25)

        self.selected_problem_set_name: Optional[str] = None
        self.selected_role_name: Optional[str] = None
        self.selected_group_name: Optional[str] = None
        self.selected_channel_id: Optional[int] = None

        # 셀렉트 컴포넌트들
        self.ps_select = discord.ui.Select(
            placeholder=self._ps_placeholder(),
            min_values=1, max_values=1,
            row=0,
        )
        self.ps_select.callback = self._on_ps_select
        self._refresh_ps_options()

        self.group_select = discord.ui.Select(
            placeholder="그룹 선택" + (f" (최대 25개, 현재 {len(groups)}개)" if len(groups) > 25 else ""),
            min_values=1, max_values=1,
            row=1,
            options=[
                discord.SelectOption(label=gn, description=f"역할: {rn}", value=rn)
                for rn, gn in groups[:25]
            ] or [discord.SelectOption(label="(그룹 없음)", value="__none__", default=False)],
        )
        if not groups:
            self.group_select.disabled = True
        self.group_select.callback = self._on_group_select

        self.channel_select = discord.ui.ChannelSelect(
            placeholder="표시 채널 선택",
            channel_types=[discord.ChannelType.text],
            min_values=1, max_values=1,
            row=2,
        )
        self.channel_select.callback = self._on_channel_select

        self.add_item(self.ps_select)
        self.add_item(self.group_select)
        self.add_item(self.channel_select)

        # 페이지네이션 (문제집)
        if self.ps_pages > 1:
            self.prev_btn = discord.ui.Button(
                label="◀ 이전", style=discord.ButtonStyle.secondary, row=3
            )
            self.next_btn = discord.ui.Button(
                label="다음 ▶", style=discord.ButtonStyle.secondary, row=3
            )
            self.prev_btn.callback = self._on_prev
            self.next_btn.callback = self._on_next
            self.add_item(self.prev_btn)
            self.add_item(self.next_btn)

        # 전송 / 취소
        self.submit_btn = discord.ui.Button(
            label="전송", style=discord.ButtonStyle.success, emoji="✅", row=4, disabled=True
        )
        self.submit_btn.callback = self._on_submit
        self.add_item(self.submit_btn)

        cancel_btn = discord.ui.Button(
            label="취소", style=discord.ButtonStyle.secondary, row=4
        )
        cancel_btn.callback = self._on_cancel
        self.add_item(cancel_btn)

    # ---- helpers ----

    def _ps_placeholder(self) -> str:
        if not self.problem_sets:
            return "(노션에 문제집 없음)"
        if self.ps_pages > 1:
            return f"문제집 선택 (페이지 {self.ps_page + 1}/{self.ps_pages}, 총 {len(self.problem_sets)}개)"
        return "문제집 선택"

    def _refresh_ps_options(self):
        start = self.ps_page * 25
        end = start + 25
        page_items = self.problem_sets[start:end]
        opts = []
        for ps in page_items:
            count = len(ps.get('problems', []))
            label = ps['name'][:100]
            desc = f"문제 {count}개"
            opts.append(discord.SelectOption(
                label=label,
                description=desc,
                value=ps['name'][:100],
                default=(ps['name'] == self.selected_problem_set_name),
            ))
        if not opts:
            opts = [discord.SelectOption(label="(없음)", value="__none__")]
            self.ps_select.disabled = True
        else:
            self.ps_select.disabled = False
        self.ps_select.options = opts
        self.ps_select.placeholder = self._ps_placeholder()

    def _update_submit_state(self):
        ready = bool(
            self.selected_problem_set_name
            and self.selected_role_name
            and self.selected_channel_id
        )
        self.submit_btn.disabled = not ready

    async def _check_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ 이 메뉴는 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True
            )
            return False
        return True

    # ---- callbacks ----

    async def _on_ps_select(self, interaction: discord.Interaction):
        if not await self._check_author(interaction):
            return
        val = self.ps_select.values[0]
        if val == "__none__":
            return
        self.selected_problem_set_name = val
        self._refresh_ps_options()
        self._update_submit_state()
        await interaction.response.edit_message(view=self)

    async def _on_group_select(self, interaction: discord.Interaction):
        if not await self._check_author(interaction):
            return
        rn = self.group_select.values[0]
        if rn == "__none__":
            return
        self.selected_role_name = rn
        # group_name 찾기
        for r, g in self.groups:
            if r == rn:
                self.selected_group_name = g
                break
        # default 표시 갱신
        for opt in self.group_select.options:
            opt.default = (opt.value == rn)
        self._update_submit_state()
        await interaction.response.edit_message(view=self)

    async def _on_channel_select(self, interaction: discord.Interaction):
        if not await self._check_author(interaction):
            return
        ch = self.channel_select.values[0]
        self.selected_channel_id = ch.id
        self._update_submit_state()
        await interaction.response.edit_message(view=self)

    async def _on_prev(self, interaction: discord.Interaction):
        if not await self._check_author(interaction):
            return
        if self.ps_page > 0:
            self.ps_page -= 1
            self._refresh_ps_options()
        await interaction.response.edit_message(view=self)

    async def _on_next(self, interaction: discord.Interaction):
        if not await self._check_author(interaction):
            return
        if self.ps_page < self.ps_pages - 1:
            self.ps_page += 1
            self._refresh_ps_options()
        await interaction.response.edit_message(view=self)

    async def _on_cancel(self, interaction: discord.Interaction):
        if not await self._check_author(interaction):
            return
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="❌ 취소되었습니다.", view=self)
        self.stop()

    async def _on_submit(self, interaction: discord.Interaction):
        if not await self._check_author(interaction):
            return

        ps_name = self.selected_problem_set_name
        role_name = self.selected_role_name
        group_name = self.selected_group_name
        channel_id = self.selected_channel_id

        if not (ps_name and role_name and channel_id):
            await interaction.response.send_message("❌ 모두 선택해주세요.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # 채널 권한 체크
        channel = interaction.client.get_channel(channel_id)
        if not channel:
            await interaction.followup.send("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
            return
        perms = channel.permissions_for(channel.guild.me)
        if not (perms.send_messages and perms.embed_links):
            await interaction.followup.send(
                f"❌ 봇에게 {channel.mention} 채널에 메시지/임베드 권한이 없습니다.",
                ephemeral=True,
            )
            return

        # 노션에서 문제집 fetch (전송 시점 데이터)
        ps = await fetch_problem_set_by_name(ps_name)
        if ps is None:
            await interaction.followup.send(
                f"❌ 노션에서 '{ps_name}' 문제집을 찾을 수 없습니다.", ephemeral=True
            )
            return

        # 주차 계산 + 사용자 풀이 계산
        week_start, week_end = get_current_week_range()
        users = get_role_users(role_name)
        results = await compute_user_solving(ps['problems'], users)
        now = get_kst_now()

        embed = build_status_embed(
            ps_name, group_name, week_start, week_end,
            ps['problems'], results, now,
        )

        # 채널에 메시지 전송
        sent = await channel.send(embed=embed, view=NotionProblemSetRefreshView())

        # status 저장 (덮어쓰기 — 중복 시 교체)
        save_notion_problem_set_status(
            group_name, ps_name, role_name,
            str(channel.id), str(sent.id),
            week_start.isoformat(), week_end.isoformat(),
            now.isoformat(),
        )

        # 셋업 메시지 정리
        for child in self.children:
            child.disabled = True
        await interaction.followup.send(
            f"✅ '{ps_name}' 풀이현황을 {channel.mention} 에 등록했습니다.\n"
            f"기간: {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}\n"
            f"00/04/08/12/16/20시 KST 자동 갱신됩니다.",
            ephemeral=True,
        )
        try:
            await interaction.edit_original_response(
                content=f"✅ 등록 완료 — {channel.mention}", view=self
            )
        except Exception:
            pass
        self.stop()


# ==================== 명령어 등록 ====================

def setup(bot: commands.Bot):

    @bot.command(name='문제집풀이현황')
    @commands.has_permissions(administrator=True)
    async def open_setup(ctx: commands.Context):
        """노션 문제집 풀이현황 등록 (관리자 전용)"""
        loading = await ctx.send("🔄 노션에서 문제집 목록을 가져오는 중...")

        # 노션에서 문제집 fetch
        try:
            problem_sets = await sync_problem_sets()
        except Exception as e:
            logger.error(f"[/문제집풀이현황] 노션 fetch 실패: {e}", exc_info=True)
            await loading.edit(content=f"❌ 노션 fetch 실패: {e}")
            return

        if not problem_sets:
            await loading.edit(
                content=(
                    "⚠️ 노션에 문제집(L4 자식 페이지)이 없습니다.\n"
                    "문제집 페이지 아래에 자식 페이지를 만들고 OJ 링크를 작성해주세요."
                )
            )
            return

        # 그룹 목록
        data = load_data()
        studies = data.get('studies', {})
        groups = []
        for role_name, study_data in studies.items():
            group_name = study_data.get('group_name', role_name)
            groups.append((role_name, group_name))
        groups.sort(key=lambda x: x[1])

        if not groups:
            await loading.edit(content="❌ 등록된 그룹이 없습니다. `/그룹 생성`으로 먼저 그룹을 만들어주세요.")
            return

        view = NotionProblemSetSetupView(ctx.author, problem_sets, groups)
        await loading.edit(
            content=(
                f"📚 노션 문제집 풀이현황 등록\n"
                f"문제집 {len(problem_sets)}개 · 그룹 {len(groups)}개 발견\n"
                f"아래에서 문제집/그룹/채널을 모두 선택한 후 **전송** 버튼을 누르세요."
            ),
            view=view,
        )

    @open_setup.error
    async def setup_error(ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ 관리자 권한이 필요합니다.")

    @bot.command(name='정올수집')
    @commands.has_permissions(administrator=True)
    async def jungol_collect_info(ctx: commands.Context):
        """Jungol userscript 사용 안내 (관리자 전용).
        운영자가 본인 브라우저(한국 IP)로 정올 데이터 긁어 봇에 POST 하는 방식."""
        import os
        bot_base = os.getenv('BOT_PUBLIC_URL', 'http://168.107.5.212:8080')
        token_set = bool(os.getenv('BOT_ADMIN_TOKEN'))

        # 활성 Jungol 문제 미리보기
        try:
            from domain.notion_sync import sync_problem_sets
            all_status = get_all_notion_problem_set_status()
            now = get_kst_now()
            active = set()
            for s in all_status:
                ws = ensure_kst(datetime.fromisoformat(s['week_start']))
                we = ensure_kst(datetime.fromisoformat(s['week_end']))
                if ws <= now <= we:
                    active.add(s['problem_set_name'])
            jungol_pids = set()
            if active:
                all_sets = await sync_problem_sets()
                for ps in all_sets:
                    if ps['name'] in active:
                        for p in ps['problems']:
                            if p['oj'] == 'jungol':
                                jungol_pids.add(str(p['id']))
        except Exception:
            jungol_pids = set()

        embed = discord.Embed(
            title="🐨 Jungol 데이터 수집 안내",
            description=(
                "정올은 datacenter IP 차단으로 봇이 직접 못 긁습니다. "
                "운영자 브라우저(한국 IP) 거쳐서 데이터 수집하는 방식.\n\n"
                "**1회 셋업** (5분):\n"
                "1. Tampermonkey 확장 설치\n"
                "   - Chrome: https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo\n"
                "2. 봇 저장소의 `userscript/jungol_crawler.user.js` 내용을 Tampermonkey에 추가\n"
                "   - GitHub raw URL 통해 자동 설치도 가능\n"
                "3. 첫 실행 시 admin 토큰 입력 (PM 으로 알려드립니다)\n\n"
                "**사용법**:\n"
                "- jungol.co.kr 어디든 접속 → 우측 하단 🐨 KOALA 버튼 표시됨\n"
                "- **📥 일괄 수집** 클릭 → 활성 문제집의 모든 Jungol 문제 자동 긁어 봇으로 전송\n"
                "- **이 페이지만 수집** → 현재 보는 문제만"
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="🔌 봇 서버",
            value=f"`{bot_base}`\nadmin 토큰 설정: {'✅' if token_set else '❌ BOT_ADMIN_TOKEN 미설정'}",
            inline=False,
        )
        if jungol_pids:
            preview = ", ".join(sorted(jungol_pids)[:20])
            if len(jungol_pids) > 20:
                preview += f" ... (+{len(jungol_pids) - 20})"
            embed.add_field(
                name=f"📋 현재 수집 대상 Jungol 문제 ({len(jungol_pids)}개)",
                value=preview,
                inline=False,
            )
        else:
            embed.add_field(
                name="📋 현재 수집 대상",
                value="활성 문제집의 Jungol 문제 0개 — `/문제집풀이현황` 으로 먼저 활성화하세요",
                inline=False,
            )
        await ctx.send(embed=embed, ephemeral=True if hasattr(ctx, 'interaction') else False)
