"""
역할 관리 명령어
"""
import discord
from discord.ext import commands
import random
from common.utils import load_data, save_data, generate_token, hash_token, verify_token

def setup(bot):
    """봇에 명령어 등록"""
    
    @bot.group(name='역할')
    async def role_group(ctx):
        """역할 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 올바른 명령어를 입력해주세요. `/도움말`을 확인해주세요.")

    @role_group.command(name='생성')
    @commands.has_permissions(administrator=True)
    async def role_create(ctx, *, role_name: str):
        """역할 생성 및 토큰 생성 (관리자 전용)"""
        # 이미 역할이 존재하는지 확인
        existing_role = discord.utils.get(ctx.guild.roles, name=role_name)
        if existing_role:
            await ctx.send(f"⚠️ '{role_name}' 역할이 이미 서버에 존재합니다.")
            return
        
        data = load_data()
        
        # 이미 등록된 역할인지 확인
        if role_name in data.get('role_tokens', {}):
            await ctx.send(f"⚠️ '{role_name}' 역할은 이미 등록되어 있습니다. `/역할 토큰 {role_name}` 명령어로 토큰을 확인하세요.")
            return
        
        # 랜덤 색상 생성
        color = discord.Color(random.randint(0, 0xFFFFFF))
        
        try:
            # 역할 생성 (권한은 기본값)
            role = await ctx.guild.create_role(
                name=role_name,
                color=color,
                reason=f"봇에 의해 생성됨 - {ctx.author}"
            )
            
            # 토큰 생성
            token = generate_token()
            token_hash = hash_token(token)
            
            # 데이터 저장
            if 'role_tokens' not in data:
                data['role_tokens'] = {}
            
            data['role_tokens'][role_name] = {
                'token_hash': token_hash,
                'original_token': token  # 관리자가 확인할 수 있도록 원본 토큰도 저장
            }
            save_data(data)
            
            # 토큰을 DM으로 전송 (보안을 위해)
            try:
                await ctx.author.send(
                    f"✅ 역할 '{role_name}'이 생성되었습니다.\n\n"
                    f"**토큰:** `{token}`\n\n"
                    f"⚠️ 이 토큰을 안전하게 보관하세요. 사용자에게 공유할 때만 사용하세요."
                )
                await ctx.send(f"✅ 역할 '{role_name}'이 생성되었습니다. 토큰은 DM으로 전송되었습니다.")
            except discord.Forbidden:
                # DM을 보낼 수 없는 경우 공개 채널에 표시
                await ctx.send(
                    f"✅ 역할 '{role_name}'이 생성되었습니다.\n"
                    f"**토큰:** `{token}`\n"
                    f"⚠️ 이 토큰을 안전하게 보관하세요."
                )
        except discord.Forbidden:
            await ctx.send("❌ 봇에게 역할을 생성할 권한이 없습니다. 서버 관리자에게 문의해주세요.")
        except Exception as e:
            await ctx.send(f"❌ 역할 생성 중 오류가 발생했습니다: {str(e)}")

    @role_group.command(name='토큰')
    @commands.has_permissions(administrator=True)
    async def role_token(ctx, *, role_name: str):
        """역할의 토큰 확인 (관리자 전용)"""
        data = load_data()
        
        if role_name not in data.get('role_tokens', {}):
            await ctx.send(f"❌ '{role_name}' 역할이 등록되지 않았습니다. `/역할 생성 {role_name}` 명령어로 먼저 생성해주세요.")
            return
        
        token_info = data['role_tokens'][role_name]
        original_token = token_info.get('original_token', '토큰 정보 없음')
        
        # DM으로 토큰 전송
        try:
            await ctx.author.send(
                f"**역할:** {role_name}\n"
                f"**토큰:** `{original_token}`"
            )
            await ctx.send(f"✅ '{role_name}' 역할의 토큰을 DM으로 전송했습니다.")
        except discord.Forbidden:
            await ctx.send(
                f"**역할:** {role_name}\n"
                f"**토큰:** `{original_token}`"
            )

    @role_group.command(name='리스트')
    @commands.has_permissions(administrator=True)
    async def role_list(ctx):
        """등록된 역할 목록 확인 (관리자 전용)"""
        data = load_data()
        role_tokens = data.get('role_tokens', {})
        
        if not role_tokens:
            await ctx.send("❌ 등록된 역할이 없습니다.")
            return
        
        embed = discord.Embed(
            title="📋 등록된 역할 목록",
            color=discord.Color.blue()
        )
        
        for role_name, token_info in role_tokens.items():
            original_token = token_info.get('original_token', '토큰 정보 없음')
            embed.add_field(
                name=f"🎭 {role_name}",
                value=f"토큰: `{original_token}`",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @role_group.command(name='삭제')
    @commands.has_permissions(administrator=True)
    async def role_delete(ctx, *, role_name: str):
        """역할 삭제 (관리자 전용)"""
        # 역할 찾기
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            await ctx.send(f"❌ '{role_name}' 역할을 서버에서 찾을 수 없습니다.")
            return
        
        # 봇 역할보다 위에 있는 역할은 삭제 불가
        bot_member = ctx.guild.get_member(ctx.bot.user.id)
        if bot_member and role >= bot_member.top_role:
            await ctx.send(f"❌ 봇 역할보다 위에 있는 역할은 삭제할 수 없습니다.")
            return
        
        data = load_data()
        
        try:
            # 디스코드에서 역할 삭제
            await role.delete(reason=f"봇에 의해 삭제됨 - {ctx.author}")
            
            # 데이터에서 토큰 정보 삭제
            if role_name in data.get('role_tokens', {}):
                del data['role_tokens'][role_name]
                save_data(data)
            
            await ctx.send(f"✅ '{role_name}' 역할이 삭제되었습니다.")
        except discord.Forbidden:
            await ctx.send("❌ 봇에게 역할을 삭제할 권한이 없습니다. 서버 관리자에게 문의해주세요.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ 역할 삭제 중 오류가 발생했습니다: {str(e)}")
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {str(e)}")

    @role_group.command(name='등록')
    async def role_register(ctx):
        """토큰으로 역할 등록 및 BOJ 핸들 등록 (GUI 방식)"""
        # Modal 띄우기
        modal = RoleRegisterModal(ctx.author)
        await ctx.send("📝 아래 버튼을 눌러 등록 폼을 열어주세요.", view=RoleRegisterButtonView(ctx.author, modal))
    
    @bot.command(name='등록')
    async def register_command(ctx):
        """토큰으로 역할 등록 및 BOJ 핸들 등록 (GUI 방식) - /역할 등록과 동일"""
        # Modal 띄우기
        modal = RoleRegisterModal(ctx.author)
        await ctx.send("📝 아래 버튼을 눌러 등록 폼을 열어주세요.", view=RoleRegisterButtonView(ctx.author, modal))


class RoleRegisterButtonView(discord.ui.View):
    """등록 버튼 View"""
    
    def __init__(self, author, modal):
        super().__init__(timeout=300)
        self.author = author
        self.modal = modal
    
    @discord.ui.button(label='📝 등록 폼 열기', style=discord.ButtonStyle.primary)
    async def open_modal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        await interaction.response.send_modal(self.modal)


class RoleRegisterModal(discord.ui.Modal, title="역할 및 BOJ 핸들 등록"):
    """역할 등록 Modal"""
    
    def __init__(self, author):
        super().__init__(timeout=600)
        self.author = author
        
        # 토큰 입력
        self.token_input = discord.ui.TextInput(
            label="토큰",
            placeholder="역할 등록 토큰을 입력하세요",
            max_length=100,
            required=True
        )
        self.add_item(self.token_input)
        
        # BOJ 핸들 입력 (필수)
        self.boj_input = discord.ui.TextInput(
            label="BOJ 핸들",
            placeholder="백준 핸들을 입력하세요",
            max_length=50,
            required=True
        )
        self.add_item(self.boj_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        from common.utils import load_data, save_data, verify_token
        from common.boj_utils import verify_user_exists
        
        data = load_data()
        role_tokens = data.get('role_tokens', {})
        
        token = self.token_input.value.strip()
        boj_handle = self.boj_input.value.strip()
        
        # BOJ 핸들 검증
        exists = await verify_user_exists(boj_handle)
        if not exists:
            await interaction.response.send_message(f"❌ 백준 아이디 '{boj_handle}'를 찾을 수 없습니다.", ephemeral=True)
            return
        
        # 토큰으로 역할 찾기
        role_name = None
        for name, token_info in role_tokens.items():
            stored_hash = token_info.get('token_hash')
            if stored_hash and verify_token(token, stored_hash):
                role_name = name
                break
        
        if not role_name:
            await interaction.response.send_message("❌ 유효하지 않은 토큰입니다. 토큰을 다시 확인해주세요.", ephemeral=True)
            return
        
        # 역할 찾기
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if not role:
            await interaction.response.send_message(f"❌ '{role_name}' 역할을 서버에서 찾을 수 없습니다. 관리자에게 문의해주세요.", ephemeral=True)
            return
        
        # 이미 역할을 가지고 있는지 확인
        if role in interaction.user.roles:
            await interaction.response.send_message(f"✅ 이미 '{role_name}' 역할을 가지고 있습니다.", ephemeral=True)
            return
        
        # 역할 부여
        try:
            await interaction.user.add_roles(role)
            
            # 데이터 저장
            user_id = str(interaction.user.id)
            if user_id not in data['users']:
                data['users'][user_id] = {
                    'username': str(interaction.user),
                    'boj_handle': None,
                    'tistory_links': [],
                    'roles': [],
                    'submissions': {}
                }
            
            # 역할 정보 저장
            if role_name not in data['users'][user_id]['roles']:
                data['users'][user_id]['roles'].append(role_name)
            
            # BOJ 핸들 저장
            data['users'][user_id]['boj_handle'] = boj_handle
            
            save_data(data)
            
            message = f"✅ '{role_name}' 역할이 부여되었습니다!\n📝 BOJ 핸들 '{boj_handle}'가 등록되었습니다."
            
            await interaction.response.send_message(message, ephemeral=False)
        except discord.Forbidden:
            await interaction.response.send_message("❌ 봇에게 역할을 부여할 권한이 없습니다. 서버 관리자에게 문의해주세요.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 오류가 발생했습니다: {str(e)}", ephemeral=True)

