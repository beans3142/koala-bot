"""
주간테스트 — Codeforces 대회 가상참가 기반 채점.

흐름:
  1. /주간테스트 <소스>  (소스 = CF 대회 링크 또는 노션 페이지 링크 또는 contestId)
     → 소스에서 contestId 추출
  2. (본인만 보이는 ephemeral) 그룹/채널 셀렉트 + 전송 버튼
  3. 전송 시 보드 메시지 생성 + status 저장
  4. 주말(토~일) 동안 매시 자동 갱신, 월요일 01:00 KST 최종 결산
  5. 보드의 [🔄 갱신] / [🏁 즉시 결산] 버튼으로 수동 조작 (관리자)

채점 정책:
  - 대상 대회에서 verdict==OK 인 문제를 distinct 카운트.
  - 참가 유형(가상/연습/실전)·제출 시각 무관 — "그 대회 문제를 풀었나"만 본다.
  - threshold(기본 2) 문제 이상이면 ✅ 통과.

문제집 데이터처럼 노션을 매번 다시 읽지 않는다 — contestId 만 저장하고
갱신 때마다 CF API(user.status)로 멤버별 풀이 수를 재계산한다.
"""
import re
import asyncio
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, time
from typing import List, Optional

import aiohttp

from common.database import (
    get_role_users,
    save_weekly_test_status,
    get_weekly_test_status,
    get_all_weekly_test_status,
    delete_weekly_test_status,
)
from common.utils import load_data, get_kst_now, ensure_kst
from common.logger import get_logger
from common.oj.codeforces import get_contest_result
from domain.notion_sync import collect_urls_from_page

logger = get_logger()

DEFAULT_THRESHOLD = 2  # 통과 기준 문제 수
_bot_for_scheduler = None


# ==================== 기간 계산 (주말 윈도우) ====================

def get_weekend_range():
    """
    이번 주 주말 윈도우와 종료(결산) 시각 반환.
      week_start = 이번 주 토요일 00:00 KST
      week_end   = 이번 주 일요일 23:59:59 KST
      settle_at  = 다음 주 월요일 00:00 KST (종료 = 최종 결산)
    """
    now = get_kst_now()
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    saturday = monday + timedelta(days=5)
    sunday_end = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    settle_at = monday + timedelta(days=7)  # 다음 월요일 00:00 (종료/결산)
    return saturday, sunday_end, settle_at


# ==================== 소스 → contestId 파싱 ====================

# CF 대회/문제 링크에서 contestId 추출
_CF_CONTEST_RE = re.compile(
    r"codeforces\.com/(?:contest|contests|gym)/(\d+)", re.IGNORECASE)
_CF_PROBLEMSET_RE = re.compile(
    r"codeforces\.com/problemset/problem/(\d+)/[A-Za-z0-9]+", re.IGNORECASE)
_NOTION_RE = re.compile(r"notion\.(so|site)", re.IGNORECASE)


def extract_contest_id_from_text(text: str) -> Optional[str]:
    """문자열에서 CF contestId 추출 (대회/문제 링크 또는 순수 숫자)."""
    text = text.strip()
    m = _CF_CONTEST_RE.search(text)
    if m:
        return m.group(1)
    m = _CF_PROBLEMSET_RE.search(text)
    if m:
        return m.group(1)
    if text.isdigit():
        return text
    return None


def _extract_notion_page_id(url: str) -> Optional[str]:
    """노션 URL에서 32자리 page id 추출."""
    last = url.split('?')[0].rstrip('/').split('/')[-1]
    last = last.replace('-', '')
    m = re.search(r"([0-9a-fA-F]{32})$", last)
    return m.group(1) if m else None


async def parse_contest_source(source: str) -> Optional[str]:
    """
    소스에서 contestId(str) 추출.
      - CF 대회/문제 링크 또는 순수 숫자 → 즉시 추출
      - 노션 페이지 링크 → 페이지 본문을 읽어 첫 CF 링크에서 추출
    실패 시 None.
    """
    source = (source or "").strip()
    if not source:
        return None

    # 1) CF 링크 / 숫자 직접
    cid = extract_contest_id_from_text(source)
    if cid:
        return cid

    # 2) 노션 링크
    if _NOTION_RE.search(source):
        page_id = _extract_notion_page_id(source)
        if not page_id:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                urls = await collect_urls_from_page(session, page_id)
        except Exception as e:
            logger.error(f"[weekly_test] 노션 페이지 읽기 실패: {e}")
            return None
        for u in urls:
            cid = extract_contest_id_from_text(u)
            if cid:
                return cid
        return None

    return None


# ==================== 채점 ====================

async def score_members(contest_id: str, users: List[dict], threshold: int) -> List[dict]:
    """
    멤버별 CF 대회 풀이 수 채점.
    반환: [{name, handle, solved(int|None), passed(bool), missing(bool)}]
      - missing: codeforces_handle 미등록
      - solved=None: CF API 조회 실패
    """
    results = []
    for u in users:
        handle = u.get('codeforces_handle')
        display = u.get('name') or u.get('username') or 'Unknown'
        base = {'name': display, 'handle': handle, 'missing': not handle, 'fail': False,
                'solved': 0, 'passed': False, 'has_virtual': False, 'v_solved': 0, 'v_penalty': 0}
        if not handle:
            results.append(base)
            continue

        res = await get_contest_result(handle, contest_id)
        await asyncio.sleep(0.5)  # CF 레이트리밋 보호

        if res is None:
            results.append({**base, 'fail': True})
            continue

        results.append({**base,
                        'solved': res['solved_any'],
                        'passed': res['solved_any'] >= threshold,
                        'has_virtual': res['has_virtual'],
                        'v_solved': res['v_solved'],
                        'v_penalty': res['v_penalty']})
    return results


def build_test_embed(contest_id: str, group_name: str, role_name: str,
                     threshold: int, week_start: datetime, week_end: datetime,
                     settle_at: datetime, results: List[dict],
                     updated_at: datetime, settled: bool,
                     total_problems: Optional[int] = None) -> discord.Embed:
    contest_url = f"https://codeforces.com/contest/{contest_id}"
    total_note = f" (총 {total_problems}문제)" if total_problems else ""

    title = f"🏆 주간테스트 — Codeforces Round {contest_id}"
    color = discord.Color.gold() if settled else discord.Color.blue()

    desc = (
        f"**대회:** [{contest_id}]({contest_url}){total_note}\n"
        f"**그룹:** {group_name}\n"
        f"**기간:** {week_start.strftime('%m-%d(토)')} ~ {week_end.strftime('%m-%d(일)')}\n"
        f"**통과 기준:** {threshold}문제 이상\n"
        f"**갱신:** {updated_at.strftime('%Y-%m-%d %H:%M')}"
    )
    if settled:
        desc = "🏁 **결산 완료** (최종 결과)\n\n" + desc
    else:
        desc += f"\n**결산 예정:** {settle_at.strftime('%m-%d(월) %H:%M')}"

    embed = discord.Embed(title=title, description=desc, color=color)

    if not results:
        embed.add_field(name="멤버", value="(없음)", inline=False)
        return embed

    # ── 섹션 1: 통과 현황 (2문제↑, 풀이 방식 무관) ──
    pass_sorted = sorted(results, key=lambda r: (r['passed'], r['solved']), reverse=True)
    plines = []
    for r in pass_sorted[:30]:
        if r['missing']:
            plines.append(f"⚠️ {r['name']} *(CF 핸들 미등록)*")
        elif r['fail']:
            plines.append(f"❌ {r['name']} *(조회 실패)*")
        else:
            mark = "✅" if r['passed'] else "📝"
            plines.append(f"{mark} {r['name']} [{r['solved']}]")
    pval = "\n".join(plines)
    if len(pval) > 1020:
        pval = pval[:1015] + "\n…"
    passed = sum(1 for r in results if r['passed'])
    scored = sum(1 for r in results if not r['missing'] and not r['fail'])
    embed.add_field(
        name=f"✅ 통과 현황 ({threshold}문제↑ · 방식 무관) — {passed}/{scored}명",
        value=pval or "(없음)", inline=False)

    # ── 섹션 2: 랭킹 (가상참가 기록 · ICPC: 문제수↓, 페널티↑) ──
    virt = [r for r in results if r['has_virtual']]
    virt.sort(key=lambda r: (-r['v_solved'], r['v_penalty']))
    if virt:
        rlines = []
        for i, r in enumerate(virt[:25], 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            rlines.append(f"{medal} {r['name']}  {r['v_solved']}솔브 · {r['v_penalty']}분")
        rval = "\n".join(rlines)
        if len(rval) > 1020:
            rval = rval[:1015] + "\n…"
    else:
        rval = "아직 가상참가(virtual) 기록이 없습니다. CF에서 이 대회를 **가상참가**로 풀면 랭킹에 반영됩니다."
    embed.add_field(name="🏅 랭킹 (가상참가 · ICPC)", value=rval, inline=False)

    return embed


# ==================== 갱신 ====================

async def update_test_message(group_name: str, contest_id: str, bot_instance,
                              force_settle: bool = False) -> bool:
    """status 1건 갱신 — 채점 + 메시지 edit. force_settle 이면 결산 처리."""
    info = get_weekly_test_status(group_name, contest_id)
    if not info:
        return False

    if int(info.get('settled', 0)) == 1 and not force_settle:
        return False  # 이미 결산됨

    week_start = ensure_kst(datetime.fromisoformat(info['week_start']))
    week_end = ensure_kst(datetime.fromisoformat(info['week_end']))
    settle_at = ensure_kst(datetime.fromisoformat(info['settle_at']))
    threshold = int(info.get('threshold', DEFAULT_THRESHOLD))
    role_name = info['role_name']
    now = get_kst_now()

    channel = bot_instance.get_channel(int(info['channel_id']))
    if not channel:
        return False
    try:
        message = await channel.fetch_message(int(info['message_id']))
    except discord.NotFound:
        delete_weekly_test_status(group_name, contest_id)
        return False
    except Exception as e:
        logger.warning(f"[weekly_test] 메시지 조회 실패: {e}")
        return False

    users = get_role_users(role_name)
    results = await score_members(contest_id, users, threshold)

    will_settle = force_settle or now >= settle_at
    embed = build_test_embed(
        contest_id, group_name, role_name, threshold,
        week_start, week_end, settle_at, results, now, will_settle,
    )
    await message.edit(embed=embed, view=WeeklyTestRefreshView())

    save_weekly_test_status(
        group_name, contest_id, role_name, threshold,
        info['channel_id'], info['message_id'],
        week_start.isoformat(), week_end.isoformat(), settle_at.isoformat(),
        now.isoformat(), settled=1 if will_settle else 0,
    )
    return True


# ==================== 스케줄러 ====================

REFRESH_HOURS = (0, 4, 8, 12, 16, 20)  # 4시간 주기 갱신 (KST). 월 00:00 틱이 최종 결산.


@tasks.loop(time=[time(hour=h, minute=0) for h in REFRESH_HOURS])
async def weekly_test_auto_update():
    """4시간 주기(00·04·08·12·16·20 KST) 보드 갱신. 월 00:00 틱에서 종료/결산."""
    if not _bot_for_scheduler:
        return
    now = get_kst_now()
    for info in get_all_weekly_test_status():
        if int(info.get('settled', 0)) == 1:
            continue
        try:
            week_start = ensure_kst(datetime.fromisoformat(info['week_start']))
            settle_at = ensure_kst(datetime.fromisoformat(info['settle_at']))
        except Exception:
            continue
        # 주말 윈도우(토 00:00) ~ 종료(월 00:00) +5분 사이에만 갱신.
        # 월 00:00 틱에서 now>=settle_at 가 되어 update_test_message 가 결산 처리.
        if week_start <= now <= settle_at + timedelta(minutes=5):
            try:
                await update_test_message(
                    info['group_name'], info['contest_id'], _bot_for_scheduler
                )
            except Exception as e:
                logger.error(
                    f"[weekly_test 자동갱신] {info['group_name']} - {info['contest_id']}: {e}",
                    exc_info=True,
                )


def start_weekly_test_scheduler(bot_instance):
    """on_ready 에서 호출"""
    global _bot_for_scheduler
    _bot_for_scheduler = bot_instance
    if not weekly_test_auto_update.is_running():
        weekly_test_auto_update.start()
        logger.info("[weekly_test] 자동 갱신/결산 스케줄러 시작 (4시간 주기 00·04·08·12·16·20, 월 00:00 종료/결산)")


# ==================== 보드 버튼 (persistent) ====================

class WeeklyTestRefreshView(discord.ui.View):
    """보드에 붙는 갱신/결산 버튼 (persistent)."""

    def __init__(self):
        super().__init__(timeout=None)

    def _find_status(self, interaction: discord.Interaction):
        for s in get_all_weekly_test_status():
            if (str(s['channel_id']) == str(interaction.channel.id)
                    and str(s['message_id']) == str(interaction.message.id)):
                return s
        return None

    @discord.ui.button(label="갱신", emoji="🔄", style=discord.ButtonStyle.secondary,
                       custom_id="weekly_test_refresh")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 갱신 가능합니다.", ephemeral=True)
            return
        info = self._find_status(interaction)
        if not info:
            await interaction.response.send_message(
                "❌ 이 메시지는 주간테스트로 등록되어 있지 않습니다.", ephemeral=True)
            return
        if int(info.get('settled', 0)) == 1:
            await interaction.response.send_message(
                "🏁 이미 결산이 완료된 주간테스트입니다.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            ok = await update_test_message(info['group_name'], info['contest_id'], interaction.client)
        except Exception as e:
            logger.error(f"[weekly_test 갱신] 실패: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 갱신 중 오류: {e}", ephemeral=True)
            return
        await interaction.followup.send("✅ 갱신 완료" if ok else "⚠️ 갱신 실행되지 않음", ephemeral=True)

    @discord.ui.button(label="즉시 결산", emoji="🏁", style=discord.ButtonStyle.danger,
                       custom_id="weekly_test_settle")
    async def settle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 결산 가능합니다.", ephemeral=True)
            return
        info = self._find_status(interaction)
        if not info:
            await interaction.response.send_message(
                "❌ 이 메시지는 주간테스트로 등록되어 있지 않습니다.", ephemeral=True)
            return
        if int(info.get('settled', 0)) == 1:
            await interaction.response.send_message("🏁 이미 결산되었습니다.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            ok = await update_test_message(
                info['group_name'], info['contest_id'], interaction.client, force_settle=True)
        except Exception as e:
            logger.error(f"[weekly_test 결산] 실패: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 결산 중 오류: {e}", ephemeral=True)
            return
        await interaction.followup.send("🏁 결산 완료 — 보드가 최종 결과로 고정됩니다." if ok
                                        else "⚠️ 결산 실행되지 않음", ephemeral=True)


def register_weekly_test_views(bot):
    # 영구 버튼: 보드 갱신/결산 + 셋업 진입(DynamicItem) — 봇 재시작 후에도 동작
    bot.add_dynamic_items(WeeklyTestSetupButton)
    bot.add_view(WeeklyTestRefreshView())


# ==================== 셋업 (ephemeral, 영구 버튼) ====================

async def _open_setup_panel(interaction: discord.Interaction, contest_id: str, author_id: int):
    """'설정 열기' 클릭 → 본인만 보이는 그룹/채널 셀렉트 패널."""
    if interaction.user.id != author_id:
        await interaction.response.send_message(
            "❌ 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
        return
    data = load_data()
    studies = data.get('studies', {})
    role_tokens = data.get('role_tokens', {})
    # 그룹(스터디)만이 아니라 '등록된 모든 역할'을 대상으로. 그룹명 있으면 표시.
    groups = [(rn, (studies.get(rn) or {}).get('group_name', rn)) for rn in role_tokens]
    groups.sort(key=lambda x: x[1])
    if not groups:
        await interaction.response.send_message(
            "❌ 등록된 역할이 없습니다. `/역할 생성`으로 먼저 만들어주세요.", ephemeral=True)
        return
    view = WeeklyTestSelectView(interaction.user, contest_id, groups)
    await interaction.response.send_message(
        content=(
            f"🏆 주간테스트 설정 — 대회 **{contest_id}**\n"
            f"그룹과 보드를 띄울 채널을 선택하고 **전송**을 누르세요."
        ),
        view=view, ephemeral=True,
    )


class WeeklyTestSetupButton(discord.ui.DynamicItem[discord.ui.Button],
                            template=r'wt_setup:(?P<cid>\d+):(?P<uid>\d+)'):
    """영구(persistent) '설정 열기' 버튼. custom_id 에 contest_id/author 인코딩 →
    봇 재시작 후에도 살아남아 '상호작용 실패' 없이 동작."""

    def __init__(self, contest_id: str, author_id: int):
        self.contest_id = str(contest_id)
        self.author_id = int(author_id)
        super().__init__(discord.ui.Button(
            label="설정 열기 (본인만)", emoji="⚙️",
            style=discord.ButtonStyle.primary,
            custom_id=f"wt_setup:{contest_id}:{author_id}",
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match['cid'], int(match['uid']))

    async def callback(self, interaction: discord.Interaction):
        await _open_setup_panel(interaction, self.contest_id, self.author_id)


def make_setup_view(contest_id: str, author_id: int) -> discord.ui.View:
    """영구 셋업 버튼을 담은 View."""
    view = discord.ui.View(timeout=None)
    view.add_item(WeeklyTestSetupButton(contest_id, author_id))
    return view


class WeeklyTestSelectView(discord.ui.View):
    """그룹/채널 셀렉트 + 전송 (ephemeral 메시지에 붙음)."""

    def __init__(self, author: discord.Member, contest_id: str, groups: List[tuple]):
        super().__init__(timeout=600)
        self.author = author
        self.contest_id = contest_id
        self.groups = groups
        self.selected_role_name: Optional[str] = None
        self.selected_group_name: Optional[str] = None
        self.selected_channel_id: Optional[int] = None

        self.group_select = discord.ui.Select(
            placeholder="그룹 선택" + (f" (최대 25, 현재 {len(groups)})" if len(groups) > 25 else ""),
            min_values=1, max_values=1, row=0,
            options=[
                discord.SelectOption(label=gn, description=f"역할: {rn}", value=rn)
                for rn, gn in groups[:25]
            ],
        )
        self.group_select.callback = self._on_group
        self.add_item(self.group_select)

        self.channel_select = discord.ui.ChannelSelect(
            placeholder="보드 표시 채널 선택",
            channel_types=[discord.ChannelType.text],
            min_values=1, max_values=1, row=1,
        )
        self.channel_select.callback = self._on_channel
        self.add_item(self.channel_select)

        self.submit_btn = discord.ui.Button(
            label="전송", style=discord.ButtonStyle.success, emoji="✅", row=2, disabled=True)
        self.submit_btn.callback = self._on_submit
        self.add_item(self.submit_btn)

        cancel = discord.ui.Button(label="취소", style=discord.ButtonStyle.secondary, row=2)
        cancel.callback = self._on_cancel
        self.add_item(cancel)

    async def _check(self, interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ 본인만 사용할 수 있습니다.", ephemeral=True)
            return False
        return True

    def _update_submit(self):
        self.submit_btn.disabled = not (self.selected_role_name and self.selected_channel_id)

    async def _on_group(self, interaction: discord.Interaction):
        if not await self._check(interaction):
            return
        rn = self.group_select.values[0]
        self.selected_role_name = rn
        for r, g in self.groups:
            if r == rn:
                self.selected_group_name = g
                break
        for opt in self.group_select.options:
            opt.default = (opt.value == rn)
        self._update_submit()
        await interaction.response.edit_message(view=self)

    async def _on_channel(self, interaction: discord.Interaction):
        if not await self._check(interaction):
            return
        self.selected_channel_id = self.channel_select.values[0].id
        self._update_submit()
        await interaction.response.edit_message(view=self)

    async def _on_cancel(self, interaction: discord.Interaction):
        if not await self._check(interaction):
            return
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(content="❌ 취소되었습니다.", view=self)
        self.stop()

    async def _on_submit(self, interaction: discord.Interaction):
        if not await self._check(interaction):
            return
        if not (self.selected_role_name and self.selected_channel_id):
            await interaction.response.send_message("❌ 그룹과 채널을 모두 선택하세요.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        channel = interaction.client.get_channel(self.selected_channel_id)
        if not channel:
            await interaction.followup.send("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
            return
        perms = channel.permissions_for(channel.guild.me)
        if not (perms.send_messages and perms.embed_links):
            await interaction.followup.send(
                f"❌ 봇에게 {channel.mention} 채널 메시지/임베드 권한이 없습니다.", ephemeral=True)
            return

        week_start, week_end, settle_at = get_weekend_range()
        now = get_kst_now()
        users = get_role_users(self.selected_role_name)
        results = await score_members(self.contest_id, users, DEFAULT_THRESHOLD)

        embed = build_test_embed(
            self.contest_id, self.selected_group_name, self.selected_role_name,
            DEFAULT_THRESHOLD, week_start, week_end, settle_at,
            results, now, settled=False,
        )
        sent = await channel.send(embed=embed, view=WeeklyTestRefreshView())

        save_weekly_test_status(
            self.selected_group_name, self.contest_id, self.selected_role_name,
            DEFAULT_THRESHOLD, str(channel.id), str(sent.id),
            week_start.isoformat(), week_end.isoformat(), settle_at.isoformat(),
            now.isoformat(), settled=0,
        )

        for c in self.children:
            c.disabled = True
        await interaction.followup.send(
            f"✅ 주간테스트(대회 {self.contest_id})를 {channel.mention} 에 등록했습니다.\n"
            f"기간: {week_start.strftime('%m-%d(토)')} ~ {week_end.strftime('%m-%d(일)')}\n"
            f"매시 자동 갱신, {settle_at.strftime('%m-%d(월) %H:%M')} 최종 결산됩니다.",
            ephemeral=True,
        )
        try:
            await interaction.edit_original_response(content=f"✅ 등록 완료 — {channel.mention}", view=self)
        except Exception:
            pass
        self.stop()


# ==================== 명령어 ====================

def setup(bot: commands.Bot):

    @bot.command(name='주간테스트')
    @commands.has_permissions(administrator=True)
    async def weekly_test(ctx: commands.Context, *, source: str = None):
        """주간테스트 등록 (관리자). 사용법: /주간테스트 <CF대회링크 | 노션링크 | contestId>"""
        if not source:
            await ctx.send(
                "❌ 소스를 입력하세요.\n"
                "사용법: `/주간테스트 <CF 대회 링크 | 노션 페이지 링크 | contestId>`\n"
                "예: `/주간테스트 https://codeforces.com/contest/2000` 또는 `/주간테스트 2000`"
            )
            return

        loading = await ctx.send("🔄 소스에서 대회를 확인하는 중...")
        try:
            contest_id = await parse_contest_source(source)
        except Exception as e:
            logger.error(f"[/주간테스트] 소스 파싱 실패: {e}", exc_info=True)
            await loading.edit(content=f"❌ 소스 파싱 실패: {e}")
            return

        if not contest_id:
            await loading.edit(
                content=(
                    "❌ 소스에서 CF 대회를 찾지 못했습니다.\n"
                    "CF 대회 링크(`codeforces.com/contest/2000`), contestId(`2000`), "
                    "또는 CF 링크가 포함된 노션 페이지 링크를 넣어주세요."
                )
            )
            return

        await loading.edit(
            content=(
                f"🏆 대회 **{contest_id}** 확인됨. 아래 버튼으로 그룹/채널을 설정하세요. "
                f"(설정 창은 본인만 보입니다 · 버튼은 영구적이라 재시작 후에도 동작)"
            ),
            view=make_setup_view(contest_id, ctx.author.id),
        )

    @weekly_test.error
    async def weekly_test_error(ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ 관리자 권한이 필요합니다.")
