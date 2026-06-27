"""
도움말 명령어 — 일관된 컴팩트 포맷 + 카테고리 드롭다운 + 명령 인자 조회.

  /도움말            → 카테고리 드롭다운으로 전체 탐색
  /도움말 <명령어>    → 특정 명령 상세 (예: /도움말 주간테스트)
  별칭: /help /명령어 /command

명령 설명은 아래 COMMANDS 레지스트리 한 곳에서만 관리한다.
새 명령을 추가하면 여기 한 줄 추가하면 도움말에 자동 반영.
"""
import discord
from discord.ext import commands

# ──────────────────────────────────────────────────────────────
# 명령 레지스트리
#   cat   : 카테고리 (드롭다운 그룹)
#   key   : 조회용 키워드 (/도움말 <key> 매칭, 슬래시 제외)
#   sig   : 표시용 시그니처
#   desc  : 한 줄 설명
#   ex    : 예시 (선택)
#   note  : 참고 한 줄 (선택)
#   admin : 관리자 전용 여부
# ──────────────────────────────────────────────────────────────
COMMANDS = [
    # 👤 유저
    {"cat": "유저", "key": "프로필", "sig": "/프로필",
     "desc": "이름과 OJ 핸들(백준·Codeforces·AtCoder)을 등록·수정합니다.",
     "ex": "/프로필 → 버튼 → 폼 입력",
     "note": "이름만 필수, 핸들은 선택. 다시 실행하면 수정.", "admin": False},
    {"cat": "유저", "key": "내정보", "sig": "/내정보",
     "desc": "내가 등록한 이름·OJ 핸들·참여 그룹을 확인합니다.", "admin": False},
    {"cat": "유저", "key": "등록", "sig": "/등록",
     "desc": "관리자가 준 토큰으로 역할에 가입합니다. (토큰만 입력)",
     "ex": "/등록 → 버튼 → 토큰 입력",
     "note": "가입 후 같은 메시지의 '프로필' 버튼이나 /프로필로 OJ 핸들을 등록하세요.", "admin": False},

    # 🎭 역할 (관리자)
    {"cat": "역할", "key": "역할 생성", "sig": "/역할 생성 <이름>",
     "desc": "역할을 만들고 가입용 토큰을 발급합니다. 토큰은 DM으로 전송.",
     "ex": "/역할 생성 21기-기초", "admin": True},
    {"cat": "역할", "key": "역할 목록", "sig": "/역할 목록",
     "desc": "등록된 모든 역할과 토큰을 봅니다.", "admin": True},
    {"cat": "역할", "key": "역할 토큰", "sig": "/역할 토큰 <역할명>",
     "desc": "특정 역할의 가입 토큰을 DM으로 다시 받습니다.", "admin": True},
    {"cat": "역할", "key": "역할 부여", "sig": "/역할 부여",
     "desc": "역할과 사용자를 드롭다운으로 골라 수동 부여합니다.",
     "ex": "/역할 부여 → 버튼 → 역할·사용자 선택 → 부여",
     "note": "OJ 핸들은 더 받지 않습니다. 본인이 /프로필에서 등록.", "admin": True},
    {"cat": "역할", "key": "역할 제거", "sig": "/역할 제거 <역할> <boj>",
     "desc": "BOJ 핸들로 역할에서 멤버를 제거합니다.", "admin": True},
    {"cat": "역할", "key": "역할 제거디스코드", "sig": "/역할 제거디스코드 <역할> <id>",
     "desc": "Discord ID(또는 멘션)로 역할에서 멤버를 제거합니다.", "admin": True},
    {"cat": "역할", "key": "역할 멤버", "sig": "/역할 멤버 <역할명>",
     "desc": "역할 멤버 목록과 서버 내/외 상태를 봅니다. (최대 25명)", "admin": True},
    {"cat": "역할", "key": "역할 삭제", "sig": "/역할 삭제 <역할명>",
     "desc": "역할과 등록 정보·토큰을 모두 삭제합니다.", "admin": True},
    {"cat": "역할", "key": "역할 문제풀이현황", "sig": "/역할 문제풀이현황 <역할명>",
     "desc": "역할 멤버의 이번 주(월~일) 백준 문제풀이 현황을 한 번 조회합니다.", "admin": True},
    {"cat": "역할", "key": "티어갱신", "sig": "/티어갱신",
     "desc": "등록된 핸들로 solved.ac·CF·AtCoder 티어 역할을 자동 생성·부여합니다.",
     "note": "매일 04:30 자동 갱신. 봇 역할이 티어 역할보다 위 + '역할 관리' 권한 필요.", "admin": True},
    {"cat": "역할", "key": "역할 주간현황설정", "sig": "/역할 주간현황설정 <역할명>",
     "desc": "이 채널에 역할 주간현황 보드를 만듭니다. 자동 갱신 + 갱신 버튼.", "admin": True},

    # 📁 그룹 (관리자)
    {"cat": "그룹", "key": "그룹 생성", "sig": "/그룹 생성 <이름> <역할>",
     "desc": "카테고리와 채널 세트(공지·풀이현황·자유·해설·과제제출·음성2)를 만듭니다.",
     "ex": "/그룹 생성 21기-기초 21기-기초", "admin": True},
    {"cat": "그룹", "key": "그룹 목록", "sig": "/그룹 목록",
     "desc": "등록된 모든 그룹을 봅니다.", "admin": True},
    {"cat": "그룹", "key": "그룹 수정", "sig": "/그룹 수정 <역할> <새이름>",
     "desc": "그룹(카테고리) 이름을 바꿉니다.", "admin": True},
    {"cat": "그룹", "key": "그룹 삭제", "sig": "/그룹 삭제 <역할>",
     "desc": "그룹 정보를 DB에서 삭제합니다. (채널은 수동 삭제)", "admin": True},
    {"cat": "그룹", "key": "그룹 정보", "sig": "/그룹 정보",
     "desc": "드롭다운으로 그룹을 골라 인원·과제 현황을 봅니다.", "admin": True},

    # 📝 과제·현황 (관리자)
    {"cat": "과제", "key": "그룹 문제풀이현황", "sig": "/그룹 문제풀이현황 <그룹>",
     "desc": "그룹 멤버의 이번 주(월~일) 백준 문제풀이 현황을 한 번 조회합니다.", "admin": True},
    {"cat": "과제", "key": "그룹 주간현황설정", "sig": "/그룹 주간현황설정 <그룹>",
     "desc": "이 채널에 그룹 주간현황 보드를 만듭니다. 자동 갱신 + 갱신 버튼.", "admin": True},
    {"cat": "과제", "key": "그룹 주간현황목록", "sig": "/그룹 주간현황목록",
     "desc": "만들어진 주간현황 보드 목록과 상태를 봅니다.", "admin": True},
    {"cat": "과제", "key": "그룹 주간현황삭제", "sig": "/그룹 주간현황삭제 <그룹>",
     "desc": "주간현황 보드 정보를 DB에서 삭제합니다. (메시지는 남음)", "admin": True},
    {"cat": "과제", "key": "그룹 문제풀이과제", "sig": "/그룹 문제풀이과제 <그룹>",
     "desc": "주간 문제풀이 과제를 만듭니다.", "admin": True},
    {"cat": "과제", "key": "그룹 링크제출", "sig": "/그룹 링크제출 <그룹>",
     "desc": "링크 제출 과제를 만듭니다.", "admin": True},
    {"cat": "과제", "key": "그룹 문제집과제", "sig": "/그룹 문제집과제 <그룹> <문제집>",
     "desc": "문제집 기반 과제를 만듭니다.", "admin": True},
    {"cat": "과제", "key": "그룹 모의테스트", "sig": "/그룹 모의테스트 <그룹> <테스트>",
     "desc": "모의테스트 과제를 만듭니다.", "admin": True},
    {"cat": "과제", "key": "그룹 전체과제", "sig": "/그룹 전체과제 <그룹>",
     "desc": "모든 과제를 한 표로 통합한 보드를 만듭니다. (과제별 부분 갱신 버튼)", "admin": True},
    {"cat": "과제", "key": "그룹 과제목록", "sig": "/그룹 과제목록 <그룹>",
     "desc": "진행 중인 과제 목록을 봅니다.", "admin": True},

    # 🏆 문제집·테스트 (관리자)
    {"cat": "문제집·테스트", "key": "문제집풀이현황", "sig": "/문제집풀이현황",
     "desc": "노션 문제집을 골라 멤버별 풀이 현황(N/M) 보드를 만듭니다. 4시간 자동 갱신.",
     "note": "노션 문제집 페이지에 CF/백준 문제 링크를 넣으면 자동 채점됩니다.", "admin": True},
    {"cat": "문제집·테스트", "key": "주간테스트", "sig": "/주간테스트 <소스>",
     "desc": "Codeforces 대회 1개를 가상참가 기준으로 채점하는 주말 보드를 만듭니다.",
     "ex": "/주간테스트 https://codeforces.com/contest/2000",
     "note": "소스=CF 대회링크·노션링크·contestId. 2문제↑ 통과. 월 00시 결산.", "admin": True},

    # ❓ 도움말
    {"cat": "도움말", "key": "도움말", "sig": "/도움말 [명령어]",
     "desc": "명령어 도움말을 봅니다. 명령어를 붙이면 그 명령의 상세를 봅니다.",
     "ex": "/도움말 주간테스트", "admin": False},
]

# 카테고리 표시 순서 + 라벨(이모지)
CATEGORY_LABELS = [
    ("유저", "👤 유저"),
    ("역할", "🎭 역할 관리"),
    ("그룹", "📁 그룹 관리"),
    ("과제", "📝 과제·현황"),
    ("문제집·테스트", "🏆 문제집·테스트"),
    ("도움말", "❓ 도움말"),
]


def _visible(is_admin: bool):
    """권한에 맞는 명령만."""
    return [c for c in COMMANDS if is_admin or not c["admin"]]


def _categories(is_admin: bool):
    """표시할 카테고리(key, label) 목록 — 해당 권한에 명령이 있는 것만."""
    cmds = _visible(is_admin)
    present = {c["cat"] for c in cmds}
    return [(k, label) for k, label in CATEGORY_LABELS if k in present]


def _render_command(c: dict) -> str:
    """명령 1개를 컴팩트하게 렌더 (일관 포맷)."""
    lock = " 🔒" if c["admin"] else ""
    lines = [f"**{c['sig']}**{lock}", c["desc"]]
    if c.get("ex"):
        lines.append(f"`예) {c['ex']}`")
    if c.get("note"):
        lines.append(f"ⓘ {c['note']}")
    return "\n".join(lines)


CATEGORY_DESC = {
    "유저": "프로필·OJ 핸들 등록, 역할 가입",
    "역할": "역할 생성·부여, 티어 역할 (관리자)",
    "그룹": "스터디 그룹 생성·관리 (관리자)",
    "과제": "주간현황·과제 보드 (관리자)",
    "문제집·테스트": "노션 문제집 현황, CF 주간테스트 (관리자)",
    "도움말": "이 도움말",
}


def build_overview_embed(is_admin: bool) -> discord.Embed:
    """전체 개요 — 카테고리 + 한 줄 설명만 (간결). 상세는 드롭다운/인자."""
    embed = discord.Embed(
        title="🤖 KOALA 봇 도움말",
        description=(
            "아래 **드롭다운**에서 분야를 고르면 상세 사용법이 나와요.\n"
            "특정 명령은 `/도움말 <명령어>` — 예: `/도움말 주간테스트`"
        ),
        color=discord.Color.blurple(),
    )
    for cat_key, label in _categories(is_admin):
        n = len([c for c in _visible(is_admin) if c["cat"] == cat_key])
        desc = CATEGORY_DESC.get(cat_key, "")
        embed.add_field(name=f"{label}  ·  {n}개", value=desc or "​", inline=False)
    embed.set_footer(text="🔒 관리자 전용 · 별칭 /help /명령어 /command")
    return embed


def build_category_embed(cat_key: str, is_admin: bool) -> discord.Embed:
    """카테고리 1개의 모든 명령 상세."""
    label = dict(CATEGORY_LABELS).get(cat_key, cat_key)
    cmds = [c for c in _visible(is_admin) if c["cat"] == cat_key]
    body = "\n\n".join(_render_command(c) for c in cmds) or "(명령 없음)"
    return discord.Embed(
        title=f"🤖 도움말 — {label}",
        description=body,
        color=discord.Color.blurple(),
    )


def build_command_embed(c: dict) -> discord.Embed:
    """단일 명령 상세 (/도움말 <명령어>)."""
    label = dict(CATEGORY_LABELS).get(c["cat"], c["cat"])
    return discord.Embed(
        title=f"📖 {c['sig']}",
        description=_render_command(c),
        color=discord.Color.blurple(),
    ).set_footer(text=f"카테고리: {label}")


def find_commands(query: str):
    """질의어로 명령 검색. 정확/접두/부분 순으로."""
    q = query.strip().lstrip("/").strip().lower()
    if not q:
        return []
    exact = [c for c in COMMANDS if c["key"].lower() == q]
    if exact:
        return exact
    pref = [c for c in COMMANDS if c["key"].lower().startswith(q)]
    if pref:
        return pref
    return [c for c in COMMANDS if q in c["key"].lower() or q in c["sig"].lower()]


# ──────────────────────────────────────────────────────────────
# 드롭다운 뷰 (명령 실행자만 조작)
# ──────────────────────────────────────────────────────────────
class HelpView(discord.ui.View):
    def __init__(self, author: discord.abc.User, is_admin: bool):
        super().__init__(timeout=300)
        self.author = author
        self.is_admin = is_admin

        options = [discord.SelectOption(label="전체 개요", value="__overview__", emoji="🏠")]
        for cat_key, label in _categories(is_admin):
            # 라벨에서 이모지+텍스트 분리해 SelectOption 구성
            emoji, _, text = label.partition(" ")
            options.append(discord.SelectOption(label=text or label, value=cat_key, emoji=emoji))

        self.select = discord.ui.Select(placeholder="카테고리 선택", options=options, min_values=1, max_values=1)
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        val = self.select.values[0]
        if val == "__overview__":
            embed = build_overview_embed(self.is_admin)
        else:
            embed = build_category_embed(val, self.is_admin)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


def setup(bot):
    # 기본 help 명령 제거 (커스텀 도움말로 대체)
    bot.help_command = None

    @bot.command(name="도움말", aliases=["help", "명령어", "command"])
    async def help_command(ctx: commands.Context, *, query: str = None):
        is_admin = ctx.author.guild_permissions.administrator if ctx.guild else False

        # 인자가 있으면 특정 명령 상세
        if query:
            matches = find_commands(query)
            matches = [c for c in matches if is_admin or not c["admin"]]
            if not matches:
                await ctx.send(
                    f"❓ `{query}` 와 일치하는 명령을 찾지 못했습니다. `/도움말` 로 전체를 보세요.")
                return
            if len(matches) == 1:
                await ctx.send(embed=build_command_embed(matches[0]))
                return
            # 여러 개 매칭 → 시그니처 목록
            listing = "\n".join(f"• `{c['sig']}`" for c in matches[:15])
            embed = discord.Embed(
                title=f"🔎 '{query}' 관련 명령 {len(matches)}개",
                description=listing + "\n\n더 정확히 입력하면 상세가 나옵니다.",
                color=discord.Color.blurple(),
            )
            await ctx.send(embed=embed)
            return

        # 인자 없으면 개요 + 드롭다운
        view = HelpView(ctx.author, is_admin)
        await ctx.send(embed=build_overview_embed(is_admin), view=view)
