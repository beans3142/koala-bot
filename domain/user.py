"""
유저 관리 명령어
"""
import discord
from discord.ext import commands
from common.utils import load_data, save_data
from common.boj_utils import verify_user_exists
from common.database import create_or_update_user, get_user, get_user_roles
from common.logger import get_logger

logger = get_logger()


class UserRegistrationModal(discord.ui.Modal, title="유저 등록"):
    """이름(필수) + 4개 OJ ID(선택사항) 입력 폼"""

    def __init__(self, existing: dict | None = None):
        super().__init__(timeout=300)
        existing = existing or {}

        self.name_input = discord.ui.TextInput(
            label="이름 (본명, 필수)",
            placeholder="홍길동",
            required=True,
            max_length=50,
            default=existing.get('name') or '',
        )
        self.boj_input = discord.ui.TextInput(
            label="BOJ ID (선택사항)",
            placeholder="acmicpc.net/user/{이 아이디}",
            required=False,
            max_length=50,
            default=existing.get('boj_handle') or '',
        )
        self.codeforces_input = discord.ui.TextInput(
            label="Codeforces ID (선택사항)",
            placeholder="codeforces.com/profile/{이 아이디}",
            required=False,
            max_length=50,
            default=existing.get('codeforces_handle') or '',
        )
        self.atcoder_input = discord.ui.TextInput(
            label="AtCoder ID (선택사항)",
            placeholder="atcoder.jp/users/{이 아이디}",
            required=False,
            max_length=50,
            default=existing.get('atcoder_handle') or '',
        )
        self.jungol_input = discord.ui.TextInput(
            label="Jungol ID (선택사항)",
            placeholder="정올 로그인 ID",
            required=False,
            max_length=50,
            default=existing.get('jungol_handle') or '',
        )

        self.add_item(self.name_input)
        self.add_item(self.boj_input)
        self.add_item(self.codeforces_input)
        self.add_item(self.atcoder_input)
        self.add_item(self.jungol_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            name = self.name_input.value.strip()
            boj = self.boj_input.value.strip() or None
            cf = self.codeforces_input.value.strip() or None
            ac = self.atcoder_input.value.strip() or None
            jn = self.jungol_input.value.strip() or None

            if not name:
                await interaction.response.send_message("❌ 이름은 필수입니다.", ephemeral=True)
                return

            create_or_update_user(
                user_id=str(interaction.user.id),
                username=str(interaction.user),
                name=name,
                boj_handle=boj,
                codeforces_handle=cf,
                atcoder_handle=ac,
                jungol_handle=jn,
            )

            lines = [f"✅ 등록 완료: **{name}**"]
            if boj: lines.append(f"• BOJ: `{boj}`")
            if cf: lines.append(f"• Codeforces: `{cf}`")
            if ac: lines.append(f"• AtCoder: `{ac}`")
            if jn: lines.append(f"• Jungol: `{jn}`")
            if not (boj or cf or ac or jn):
                lines.append("ⓘ OJ ID 미등록 — 풀이 현황 조회 시 표시되지 않습니다.")

            await interaction.response.send_message("\n".join(lines), ephemeral=True)
        except Exception as e:
            logger.error(f"[유저등록] 저장 실패: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 등록 중 오류: {type(e).__name__}: {e}", ephemeral=True
            )


class UserRegistrationView(discord.ui.View):
    """폼 열기 버튼 — 누를 때마다 최신 DB 값을 읽어 폼에 채움"""
    def __init__(self, author: discord.Member):
        super().__init__(timeout=600)
        self.author = author

    @discord.ui.button(label="등록 / 수정", style=discord.ButtonStyle.primary, emoji="📝")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        # 매번 최신 값을 다시 읽어와서 폼에 채움
        existing = get_user(str(interaction.user.id)) or {}
        await interaction.response.send_modal(UserRegistrationModal(existing))


def setup(bot):
    """봇에 명령어 등록"""

    @bot.command(name='등록')
    async def user_register_form(ctx: commands.Context):
        """이름 + 4개 OJ ID 입력 폼 (이름만 필수). 다시 눌러 수정도 가능."""
        existing = get_user(str(ctx.author.id)) or {}
        view = UserRegistrationView(ctx.author)
        if existing.get('name'):
            msg = (
                f"📝 **{existing.get('name')}** 님의 등록 정보를 수정할 수 있습니다.\n"
                f"버튼을 누르면 현재 저장된 값이 폼에 자동 채워집니다 (최신 값).\n"
                f"여러 번 눌러서 수정 가능 (10분간 유효)."
            )
        else:
            msg = (
                "📝 유저 정보를 등록합니다. 아래 버튼을 누르세요.\n"
                "이미 등록한 경우에도 다시 눌러 수정할 수 있습니다 (10분간 유효)."
            )
        await ctx.send(msg, view=view)

    @bot.command(name='유저등록')
    async def user_register_quick(ctx: commands.Context, boj_handle: str):
        """(레거시) BOJ 핸들만 빠르게 등록 — 새 사용자는 /등록 권장"""
        exists = await verify_user_exists(boj_handle)
        if not exists:
            await ctx.send(f"❌ 백준 아이디 '{boj_handle}'를 찾을 수 없습니다.")
            return

        create_or_update_user(
            user_id=str(ctx.author.id),
            username=str(ctx.author),
            boj_handle=boj_handle,
        )
        await ctx.send(
            f"✅ BOJ 핸들 등록 완료: **{boj_handle}**\n"
            f"ⓘ 이름·다른 OJ도 등록하려면 `/등록` 명령어를 사용하세요."
        )

    @bot.command(name='내정보')
    async def my_info(ctx):
        """내 정보 확인"""
        user_id = str(ctx.author.id)
        user_db = get_user(user_id)

        if not user_db:
            await ctx.send("❌ 등록된 정보가 없습니다. `/등록` 명령어로 먼저 등록해주세요.")
            return

        name = user_db.get('name')
        title = f"{name}님의 정보" if name else f"{ctx.author.display_name}님의 정보"
        embed = discord.Embed(title=title, color=discord.Color.blue())

        if name:
            embed.add_field(name="이름", value=name, inline=True)

        # OJ 핸들들
        oj_fields = [
            ('BOJ', user_db.get('boj_handle')),
            ('Codeforces', user_db.get('codeforces_handle')),
            ('AtCoder', user_db.get('atcoder_handle')),
            ('Jungol', user_db.get('jungol_handle')),
        ]
        for label, value in oj_fields:
            embed.add_field(name=label, value=value or "미등록", inline=True)

        # 참여 그룹
        roles = get_user_roles(user_id)
        if roles:
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
                inline=False,
            )
        else:
            embed.add_field(name="참여 그룹", value="없음", inline=False)

        # 제출한 링크 수 (기존 JSON 데이터)
        data = load_data()
        user_data = data.get('users', {}).get(user_id, {})
        embed.add_field(
            name="제출한 링크 수",
            value=f"{len(user_data.get('tistory_links', []))}개",
            inline=True,
        )

        await ctx.send(embed=embed)
