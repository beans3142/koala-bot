"""
티어 역할 자동화 — 등록된 핸들의 티어를 크롤링해 Discord 역할을 자동 생성/부여/회수.

플랫폼:
  - solved.ac (백준): API user/show 의 tier(0~31) → Bronze~Master 밴드
  - Codeforces: API user.info 의 rank → newbie~legendary grandmaster
  - AtCoder: atcoder.jp/users/{handle}/history/json 의 최근 NewRating → 색 밴드

역할 이름: "[BOJ] Ruby ♦️", "[CF] Expert 🔵", "[AC] Blue 🔵" (밴드만, 이모지 포함)
색상은 밴드별 기본값으로 자동 생성. (운영자가 디스코드에서 자유롭게 바꿔도 됨 —
 봇은 '이름'으로 역할을 식별하므로 색을 바꿔도 계속 동작)

동작: 매일 1회 + /티어갱신(수동).
  멤버의 핸들로 밴드 계산 → 같은 prefix의 옛 티어 역할 회수 → 현재 역할 부여(없으면 생성).

전제: 봇에 '역할 관리' 권한 + 봇 역할이 티어 역할들보다 위에 있어야 함.
"""
import asyncio
import aiohttp
import discord
from discord.ext import commands, tasks
from datetime import time

from common.database import get_user
from common.logger import get_logger

logger = get_logger()

_bot_for_scheduler = None
_TIMEOUT = aiohttp.ClientTimeout(total=15)
# solved.ac 등은 UA 없으면 Cloudflare 403. 기존 boj_utils 와 동일한 UA 사용.
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# ──────────────────────────────────────────────
# 밴드 → (색 hex, 이모지). 어두운 색(파랑·은색)은 가독성 위해 살짝 밝게 보정.
# ──────────────────────────────────────────────
BOJ_COLORS = {
    "Bronze":   (0xAD5600, "🟫"),
    "Silver":   (0x8B98A8, "⚪"),
    "Gold":     (0xEC9A00, "🟡"),
    "Platinum": (0x27E2A4, "🟢"),
    "Diamond":  (0x00B4FC, "🔷"),
    "Ruby":     (0xFF0062, "♦️"),
    "Master":   (0xB491FF, "🟪"),
}

CF_COLORS = {
    "newbie":                    (0x9E9E9E, "⚪"),
    "pupil":                     (0x008000, "🟢"),
    "specialist":                (0x03A89E, "🟦"),
    "expert":                    (0x4757FF, "🔵"),
    "candidate master":          (0xAA00AA, "🟣"),
    "master":                    (0xFF8C00, "🟠"),
    "international master":       (0xFF8C00, "🟠"),
    "grandmaster":               (0xFF0000, "🔴"),
    "international grandmaster":  (0xFF0000, "🔴"),
    "legendary grandmaster":     (0xFF0000, "🔴"),
}

AC_BANDS = [
    (400,  "Gray",   0x9E9E9E, "⚪"),
    (800,  "Brown",  0x804000, "🟤"),
    (1200, "Green",  0x008000, "🟢"),
    (1600, "Cyan",   0x00C0C0, "🟦"),
    (2000, "Blue",   0x4757FF, "🔵"),
    (2400, "Yellow", 0xC0C000, "🟡"),
    (2800, "Orange", 0xFF8000, "🟠"),
    (10**9, "Red",   0xFF0000, "🔴"),
]


# ──────────────────────────────────────────────
# 밴드 계산
# ──────────────────────────────────────────────
def _boj_band(tier: int):
    if tier is None or tier <= 0:
        return None  # Unrated → 역할 없음
    if tier <= 5:    name = "Bronze"
    elif tier <= 10: name = "Silver"
    elif tier <= 15: name = "Gold"
    elif tier <= 20: name = "Platinum"
    elif tier <= 25: name = "Diamond"
    elif tier <= 30: name = "Ruby"
    else:            name = "Master"
    c, e = BOJ_COLORS[name]
    return (name, c, e)


def _ac_band(rating: int):
    if rating is None:
        return None
    for upper, name, color, emoji in AC_BANDS:
        if rating < upper:
            return (name, color, emoji)
    return None


# ──────────────────────────────────────────────
# 티어 fetch (실패하면 None — 역할 변경 없음)
# ──────────────────────────────────────────────
async def fetch_boj(handle: str):
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT, headers=_HEADERS) as s:
            async with s.get(f"https://solved.ac/api/v3/user/show?handle={handle}") as r:
                if r.status != 200:
                    return None
                d = await r.json(content_type=None)
        return _boj_band(d.get("tier", 0))
    except Exception as e:
        logger.warning(f"[tier_roles] solved.ac {handle} 실패: {e!r}")
        return None


async def fetch_cf(handle: str):
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT, headers=_HEADERS) as s:
            async with s.get(f"https://codeforces.com/api/user.info?handles={handle}") as r:
                d = await r.json(content_type=None)
        if d.get("status") != "OK" or not d.get("result"):
            return None
        rank = d["result"][0].get("rank")
        if not rank:
            return None  # 무등급
        c, e = CF_COLORS.get(rank.lower(), (0x9E9E9E, "⚪"))
        return (rank.title(), c, e)
    except Exception as e:
        logger.warning(f"[tier_roles] codeforces {handle} 실패: {e!r}")
        return None


async def fetch_ac(handle: str):
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT, headers=_HEADERS) as s:
            async with s.get(f"https://atcoder.jp/users/{handle}/history/json") as r:
                if r.status != 200:
                    return None
                d = await r.json(content_type=None)
        if not d:
            return None
        return _ac_band(d[-1].get("NewRating"))
    except Exception as e:
        logger.warning(f"[tier_roles] atcoder {handle} 실패: {e!r}")
        return None


# 플랫폼 정의: (prefix, DB 핸들 키, fetch 함수)
PLATFORMS = [
    ("[BOJ]", "boj_handle",        fetch_boj),
    ("[CF]",  "codeforces_handle", fetch_cf),
    ("[AC]",  "atcoder_handle",    fetch_ac),
]


# ──────────────────────────────────────────────
# 역할 적용 (생성/부여/회수)
# ──────────────────────────────────────────────
async def _apply(guild: discord.Guild, member: discord.Member, prefix: str, band):
    desired_name = None
    color = None
    if band:
        name, color, emoji = band
        desired_name = f"{prefix} {name} {emoji}"

    # 같은 플랫폼의 옛 티어 역할 회수 (desired 제외)
    stale = [r for r in member.roles
             if r.name.startswith(prefix + " ") and r.name != desired_name]
    if stale:
        try:
            await member.remove_roles(*stale, reason="티어 역할 갱신")
        except discord.Forbidden:
            logger.warning(f"[tier_roles] {member} 역할 회수 권한 없음")
        except Exception as e:
            logger.warning(f"[tier_roles] 역할 회수 실패: {e}")

    if not desired_name:
        return  # 무등급/조회실패 → 부여 없음

    role = discord.utils.get(guild.roles, name=desired_name)
    if role is None:
        try:
            role = await guild.create_role(
                name=desired_name, colour=discord.Colour(color),
                mentionable=False, reason="티어 역할 자동 생성")
        except discord.Forbidden:
            logger.warning(f"[tier_roles] 역할 생성 권한 없음: {desired_name}")
            return
        except Exception as e:
            logger.warning(f"[tier_roles] 역할 생성 실패({desired_name}): {e}")
            return

    if role not in member.roles:
        try:
            await member.add_roles(role, reason="티어 역할 갱신")
        except discord.Forbidden:
            logger.warning(f"[tier_roles] {member} 역할 부여 권한 없음 (봇 역할 위치 확인)")
        except Exception as e:
            logger.warning(f"[tier_roles] 역할 부여 실패: {e}")


async def sync_member(guild: discord.Member, member: discord.Member, udb: dict):
    for prefix, handle_key, fetcher in PLATFORMS:
        handle = udb.get(handle_key)
        if not handle:
            continue
        band = await fetcher(handle)
        await _apply(guild, member, prefix, band)
        await asyncio.sleep(0.2)  # API 레이트리밋 보호


async def sync_all(guild: discord.Guild) -> dict:
    """길드 전체 멤버 티어 역할 갱신. 반환: {processed, skipped}"""
    processed = 0
    for member in guild.members:
        if member.bot:
            continue
        udb = get_user(str(member.id))
        if not udb:
            continue
        if not (udb.get("boj_handle") or udb.get("codeforces_handle") or udb.get("atcoder_handle")):
            continue
        try:
            await sync_member(guild, member, udb)
            processed += 1
        except Exception as e:
            logger.error(f"[tier_roles] {member} 갱신 오류: {e}", exc_info=True)
        await asyncio.sleep(0.2)
    return {"processed": processed}


# ──────────────────────────────────────────────
# 스케줄러 (매일 04:30 KST)
# ──────────────────────────────────────────────
@tasks.loop(time=[time(hour=4, minute=30)])
async def tier_role_daily_sync():
    if not _bot_for_scheduler:
        return
    for guild in _bot_for_scheduler.guilds:
        try:
            res = await sync_all(guild)
            logger.info(f"[tier_roles] 일일 갱신 {guild.name}: {res['processed']}명")
        except Exception as e:
            logger.error(f"[tier_roles] 일일 갱신 오류({guild.name}): {e}", exc_info=True)


def start_tier_role_scheduler(bot):
    global _bot_for_scheduler
    _bot_for_scheduler = bot
    if not tier_role_daily_sync.is_running():
        tier_role_daily_sync.start()
        logger.info("[tier_roles] 티어 역할 일일 갱신 스케줄러 시작 (매일 04:30 KST)")


# ──────────────────────────────────────────────
# 명령어
# ──────────────────────────────────────────────
def setup(bot: commands.Bot):

    @bot.command(name="티어갱신")
    @commands.has_permissions(administrator=True)
    async def tier_sync_cmd(ctx: commands.Context):
        """등록된 핸들 기준으로 전체 멤버 티어 역할을 즉시 갱신 (관리자)."""
        msg = await ctx.send("🔄 티어 역할 갱신 중... (멤버 수에 따라 시간이 걸립니다)")
        try:
            res = await sync_all(ctx.guild)
        except Exception as e:
            logger.error(f"[/티어갱신] 오류: {e}", exc_info=True)
            await msg.edit(content=f"❌ 오류: {e}")
            return
        await msg.edit(
            content=f"✅ 티어 역할 갱신 완료 — {res['processed']}명 처리.\n"
                    f"ⓘ 역할이 안 보이면 봇 역할이 티어 역할보다 위에 있는지, "
                    f"'역할 관리' 권한이 있는지 확인하세요.")

    @tier_sync_cmd.error
    async def _err(ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ 관리자 권한이 필요합니다.", delete_after=10)
