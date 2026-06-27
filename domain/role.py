"""
역할 관리 명령어
"""
import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta, time
from common.utils import load_data, save_data, generate_token, hash_token, verify_token
from common.database import (
    get_role_users,
    save_weekly_status_message,
    get_weekly_status_message,
    get_user_by_boj_handle,
    get_user,
    create_or_update_user,
    add_user_role,
    remove_user_role,
)
from common.boj_utils import get_weekly_solved_count, verify_user_exists
from common.logger import setup_logger

logger = setup_logger()

# 출력 제외 대상 (원하는 사용자 ID 또는 BOJ 핸들을 여기에 추가)
EXCLUDED_USER_IDS = set()          # 예: {"123456789012345678"}
EXCLUDED_BOJ_HANDLES = set()       # 예: {"beans3142"}


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
            
            # 봇 알림 채널에 알림 전송
            from common.utils import send_bot_notification
            await send_bot_notification(
                ctx.guild,
                "🎭 역할 생성",
                f"**역할명:** {role_name}\n"
                f"**생성자:** {ctx.author.mention}",
                discord.Color.green()
            )
            
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

    def _get_token(role_name):
        d = load_data()
        if role_name not in d.get('role_tokens', {}):
            return None
        return d['role_tokens'][role_name].get('original_token', '토큰 정보 없음')

    async def _token_action(interaction, role_name):
        tok = _get_token(role_name)
        if tok is None:
            await interaction.response.send_message(f"❌ '{role_name}' 역할이 등록되지 않았습니다.", ephemeral=True)
            return
        try:
            await interaction.user.send(f"**역할:** {role_name}\n**토큰:** `{tok}`")
            await interaction.response.send_message(f"✅ '{role_name}' 토큰을 DM으로 보냈습니다.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"DM이 막혀있어 여기 표시합니다.\n**역할:** {role_name}\n**토큰:** `{tok}`", ephemeral=True)

    @role_group.command(name='토큰')
    @commands.has_permissions(administrator=True)
    async def role_token(ctx, *, role_name: str = None):
        """역할 토큰 확인 (관리자). 인자 없으면 드롭다운으로 역할 선택."""
        if role_name is None:
            await ctx.send("🎟️ 토큰을 볼 역할을 선택하세요:",
                           view=RolePickerView(ctx.author, _registered_role_names(), _token_action))
            return
        tok = _get_token(role_name)
        if tok is None:
            await ctx.send(f"❌ '{role_name}' 역할이 등록되지 않았습니다. `/역할 생성 {role_name}` 명령어로 먼저 생성해주세요.")
            return
        try:
            await ctx.author.send(f"**역할:** {role_name}\n**토큰:** `{tok}`")
            await ctx.send(f"✅ '{role_name}' 역할의 토큰을 DM으로 전송했습니다.")
        except discord.Forbidden:
            await ctx.send(f"**역할:** {role_name}\n**토큰:** `{tok}`")

    @role_group.command(name='목록')
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

    def _members_embed(guild, role_name):
        from common.database import get_role_users
        data = load_data()
        if role_name not in data.get('role_tokens', {}):
            return None, f"❌ '{role_name}' 역할이 등록되지 않았습니다."
        users = get_role_users(role_name)
        if not users:
            return None, f"❌ '{role_name}' 역할을 가진 멤버가 없습니다."
        embed = discord.Embed(
            title=f"👥 '{role_name}' 역할 멤버 목록",
            description=f"총 {len(users)}명", color=discord.Color.blue())
        role = discord.utils.get(guild.roles, name=role_name)
        member_list = []
        for i, user_info in enumerate(users[:25], 1):
            uid = user_info['user_id']
            member = guild.get_member(int(uid)) if uid else None
            display_name = member.display_name if member else user_info['username']
            status = "✅ 서버 내" if member else "⚠️ 서버 외"
            member_list.append(f"{i}. {display_name} ({user_info.get('boj_handle', '미등록')}) - {status}")
        if len(users) > 25:
            member_list.append(f"\n... 외 {len(users) - 25}명")
        embed.add_field(name="멤버 목록", value="\n".join(member_list) or "멤버 없음", inline=False)
        if role:
            dm = [m for m in guild.members if role in m.roles]
            embed.add_field(name="Discord 역할 멤버 수", value=f"{len(dm)}명", inline=True)
        return embed, None

    async def _members_action(interaction, role_name):
        embed, err = _members_embed(interaction.guild, role_name)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @role_group.command(name='멤버')
    @commands.has_permissions(administrator=True)
    async def role_members(ctx, *, role_name: str = None):
        """역할 멤버 목록 (관리자). 인자 없으면 드롭다운으로 역할 선택."""
        if role_name is None:
            await ctx.send("👥 멤버를 볼 역할을 선택하세요:",
                           view=RolePickerView(ctx.author, _registered_role_names(), _members_action))
            return
        embed, err = _members_embed(ctx.guild, role_name)
        await ctx.send(content=err) if err else await ctx.send(embed=embed)

    @role_group.command(name='부여')
    @commands.has_permissions(administrator=True)
    async def role_assign(ctx, role_name: str = None, discord_id: str = None, boj_handle: str = None):
        """디스코드 사용자에게 역할을 부여 (관리자 전용)
        - 인자 없이: 역할/사용자 드롭다운 패널 (권장)
        - /역할 부여 <역할명> <discord_id 또는 멘션> <boj_handle>: 직접 부여
        """
        # 인자 없으면 드롭다운 패널 진입 버튼 (본인만 보이는 ephemeral)
        if not role_name:
            await ctx.send(
                "🎫 역할 부여 — 아래 버튼을 누르면 본인만 보이는 설정창이 열립니다. "
                "(역할·사용자를 드롭다운으로 선택 · 버튼 영구)",
                view=RoleAssignEntryView())
            return
        # 일부 인자만 있으면 사용법 안내
        if not (role_name and discord_id and boj_handle):
            await ctx.send(
                "❌ 사용법: `/역할 부여` (드롭다운) 또는 `/역할 부여 <역할> <id> <boj>`",
                delete_after=10)
            return

        # 역할이 등록되어 있는지 확인
        data = load_data()
        if role_name not in data.get('role_tokens', {}):
            await ctx.send(f"❌ '{role_name}' 역할이 등록되지 않았습니다.")
            return

        # 디스코드 ID 정규화 (멘션 형태도 지원)
        clean_id = "".join(ch for ch in discord_id if ch.isdigit())
        if not clean_id:
            await ctx.send("❌ 디스코드 ID가 올바르지 않습니다. 숫자 ID 또는 멘션 형태로 입력해주세요.")
            return

        try:
            user_id_int = int(clean_id)
        except ValueError:
            await ctx.send("❌ 디스코드 ID를 정수로 변환할 수 없습니다.")
            return

        member = ctx.guild.get_member(user_id_int)
        if not member:
            await ctx.send(f"❌ 이 서버에서 디스코드 ID `{clean_id}` 사용자를 찾을 수 없습니다.")
            return

        # 역할 객체 찾기
        role_obj = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role_obj:
            await ctx.send(f"❌ 서버에서 '{role_name}' 역할을 찾을 수 없습니다.")
            return

        # BOJ 핸들 검증
        exists = await verify_user_exists(boj_handle)
        if not exists:
            await ctx.send(f"❌ 백준 아이디 '{boj_handle}'를 찾을 수 없습니다.")
            return

        # 디스코드 역할 부여
        try:
            await member.add_roles(role_obj, reason=f"관리자에 의한 역할 부여: {ctx.author}")
        except discord.Forbidden:
            await ctx.send("❌ 봇에게 역할을 부여할 권한이 없습니다. 역할 위치/권한을 확인해주세요.")
            return
        except Exception as e:
            await ctx.send(f"❌ 디스코드 역할 부여 중 오류가 발생했습니다: {str(e)}")
            return

        # DB에 사용자/역할/BOJ 핸들 저장
        user_id_str = str(member.id)
        create_or_update_user(user_id_str, str(member), boj_handle)
        add_user_role(user_id_str, role_name)

        # 봇 알림 채널에 알림 전송
        from common.utils import send_bot_notification
        await send_bot_notification(
            ctx.guild,
            "👤 역할 부여 (관리자)",
            f"**사용자:** {member.mention} ({member.display_name})\n"
            f"**역할:** {role_name}\n"
            f"**BOJ 핸들:** {boj_handle}\n"
            f"**부여자:** {ctx.author.mention}",
            discord.Color.blue()
        )

        await ctx.send(
            f"✅ `{member}` 사용자에게 '{role_name}' 역할을 부여하고, "
            f"BOJ 핸들 `{boj_handle}`를 등록했습니다."
        )

    async def _problem_status_embed(guild, role_name):
        data = load_data()
        if role_name not in data.get('role_tokens', {}):
            return None, f"❌ '{role_name}' 역할이 등록되지 않았습니다."
        users = get_role_users(role_name)
        if not users:
            return None, f"❌ '{role_name}' 역할을 가진 멤버가 없습니다."
        today = datetime.now()
        monday = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

        results = []
        for ui in users:
            bh = ui.get('boj_handle')
            base = {'username': ui['username'], 'boj_handle': bh or '미등록',
                    'user_id': ui.get('user_id'), 'solved_count': 0, 'problems': []}
            if not bh or bh == '미등록':
                results.append({**base, 'status': '❌ BOJ 핸들 미등록'})
                continue
            try:
                sd = await get_weekly_solved_count(bh, monday, sunday)
                results.append({**base, 'boj_handle': bh, 'solved_count': sd['count'],
                                'problems': sd.get('problems', []),
                                'status': '✅' if sd['count'] > 0 else '⚠️'})
            except Exception as e:
                results.append({**base, 'boj_handle': bh, 'status': f'❌ 오류: {str(e)[:30]}'})

        results.sort(key=lambda x: x['solved_count'], reverse=True)
        embed = discord.Embed(
            title=f"📊 '{role_name}' 역할 멤버 백준 문제풀이 현황",
            description=f"기간: {monday.strftime('%Y-%m-%d')} ~ {sunday.strftime('%Y-%m-%d')} (월~일)",
            color=discord.Color.blue())
        member_list = []
        total_solved = 0
        for i, r in enumerate(results[:25], 1):
            total_solved += r['solved_count']
            uid = r.get('user_id')
            if (uid and uid in EXCLUDED_USER_IDS) or (r['boj_handle'] and r['boj_handle'] in EXCLUDED_BOJ_HANDLES):
                continue
            rank = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            if r['boj_handle'] == '미등록':
                member_list.append(f"{rank} {r['username']} - {r['status']} BOJ 핸들 미등록")
            elif r['solved_count'] == 0:
                member_list.append(f"{rank} {r['boj_handle']} - {r['status']} 0개")
            else:
                ps = sorted(r.get('problems', []))
                if len(ps) <= 15:
                    member_list.append(f"{rank} {r['boj_handle']} - {r['status']} {r['solved_count']}개 [{', '.join(map(str, ps))}]")
                else:
                    member_list.append(f"{rank} {r['boj_handle']} - {r['status']} {r['solved_count']}개 [{', '.join(map(str, ps[:15]))}, ... 외 {len(ps) - 15}개]")
        if len(results) > 25:
            member_list.append(f"\n... 외 {len(results) - 25}명")
        embed.add_field(name="멤버별 문제풀이 현황", value="\n".join(member_list) or "멤버 없음", inline=False)
        active = len([r for r in results if r['solved_count'] > 0])
        embed.add_field(name="📈 통계",
                        value=f"총 멤버: {len(results)}명\n문제 풀은 멤버: {active}명\n총 해결한 문제: {total_solved}개",
                        inline=False)
        return embed, None

    async def _problem_status_action(interaction, role_name):
        await interaction.response.defer(ephemeral=True)
        embed, err = await _problem_status_embed(interaction.guild, role_name)
        if err:
            await interaction.followup.send(err, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @role_group.command(name='문제풀이현황')
    @commands.has_permissions(administrator=True)
    async def role_problem_status(ctx, *, role_name: str = None):
        """역할 멤버 주간(월~일) 백준 문제풀이 현황 (관리자). 인자 없으면 드롭다운."""
        if role_name is None:
            await ctx.send("📊 현황을 볼 역할을 선택하세요:",
                           view=RolePickerView(ctx.author, _registered_role_names(), _problem_status_action))
            return
        loading = await ctx.send("🔄 백준 문제풀이 현황을 조회하는 중...")
        embed, err = await _problem_status_embed(ctx.guild, role_name)
        if err:
            await loading.edit(content=err)
        else:
            await loading.edit(content=None, embed=embed)

    @role_group.command(name='주간현황설정')
    @commands.has_permissions(administrator=True)
    async def role_weekly_status_setup(ctx, *, role_name: str):
        """주간 문제풀이 현황 메시지 설정 (관리자 전용)"""
        # 역할이 등록되어 있는지 확인
        data = load_data()
        if role_name not in data.get('role_tokens', {}):
            await ctx.send(f"❌ '{role_name}' 역할이 등록되지 않았습니다.")
            return
        
        # 이번 주 월요일 계산
        today = datetime.now()
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        # 초기 임베드 생성
        embed = discord.Embed(
            title=f"📊 '{role_name}' 주간 문제풀이 현황",
            description=f"기간: {monday.strftime('%Y-%m-%d')} ~ {sunday.strftime('%Y-%m-%d')} (월~일)\n초기화 중...",
            color=discord.Color.blue()
        )
        
        message = await ctx.send(embed=embed)
        
        # 메시지 정보 저장
        save_weekly_status_message(role_name, str(ctx.channel.id), str(message.id), monday.strftime('%Y-%m-%d'))
        
        # 즉시 업데이트
        await update_weekly_status_for_role(role_name, ctx.bot)
        
        await ctx.send(f"✅ '{role_name}' 역할의 주간 문제풀이 현황 메시지가 설정되었습니다.\n📅 매시간(12시~00시) 자동 업데이트됩니다.\n📅 매주 월요일 00시에 새 주간 현황이 시작됩니다.")

    @role_group.command(name='주간현황갱신')
    @commands.has_permissions(administrator=True)
    async def role_weekly_status_refresh(ctx, *, role_name: str):
        """주간 문제풀이 현황 메시지 수동 갱신 (관리자 전용)"""
        # 역할이 등록되어 있는지 확인
        data = load_data()
        if role_name not in data.get('role_tokens', {}):
            await ctx.send(f"❌ '{role_name}' 역할이 등록되지 않았습니다.")
            return
        
        await ctx.send(f"🔄 '{role_name}' 역할의 주간 현황을 갱신하는 중...")
        await update_weekly_status_for_role(role_name, ctx.bot)
        await ctx.send(f"✅ '{role_name}' 역할의 주간 현황이 갱신되었습니다.")

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

    @role_group.command(name='제거')
    @commands.has_permissions(administrator=True)
    async def role_remove_member(ctx, role_name: str, boj_handle: str):
        """특정 역할에서 BOJ 핸들로 멤버 제거 (관리자 전용)
        사용법: /역할 제거 <역할명> <boj_handle>
        """
        # 역할 등록 여부 확인
        data = load_data()
        if role_name not in data.get('role_tokens', {}):
            await ctx.send(f"❌ '{role_name}' 역할이 등록되지 않았습니다.")
            return

        # BOJ 핸들로 사용자 찾기
        user = get_user_by_boj_handle(boj_handle)
        if not user:
            await ctx.send(f"❌ BOJ 핸들 '{boj_handle}'로 등록된 사용자를 찾을 수 없습니다.")
            return

        user_id = user['user_id']
        member = None
        try:
            member = ctx.guild.get_member(int(user_id))
        except:
            member = None

        # 디스코드 역할 제거
        role_obj = discord.utils.get(ctx.guild.roles, name=role_name)
        if member and role_obj and role_obj in member.roles:
            try:
                await member.remove_roles(role_obj, reason=f"관리자에 의한 제거: {ctx.author}")
            except discord.Forbidden:
                await ctx.send("❌ 봇에게 역할을 제거할 권한이 없습니다.")
                return
            except Exception as e:
                await ctx.send(f"❌ 디스코드 역할 제거 중 오류가 발생했습니다: {str(e)}")
                return

        # DB에서 역할 매핑 제거
        remove_user_role(user_id, role_name)

        await ctx.send(f"✅ '{boj_handle}' 사용자를 '{role_name}' 역할에서 제거했습니다.")

    @role_group.command(name='제거디스코드')
    @commands.has_permissions(administrator=True)
    async def role_remove_member_by_discord_id(ctx, role_name: str, discord_id: str):
        """특정 역할에서 디스코드 ID로 멤버 제거 (관리자 전용)
        사용법: /역할 제거디스코드 <역할명> <discord_id>
        """
        # 역할 등록 여부 확인
        data = load_data()
        if role_name not in data.get('role_tokens', {}):
            await ctx.send(f"❌ '{role_name}' 역할이 등록되지 않았습니다.")
            return

        # 멘션/숫자만 추출
        clean_id = "".join(ch for ch in discord_id if ch.isdigit())
        target_id = clean_id if clean_id else discord_id

        # 디스코드 ID로 사용자 찾기 (DB)
        user = get_user(target_id)
        if not user:
            await ctx.send(f"❌ 디스코드 ID '{discord_id}'로 등록된 사용자를 찾을 수 없습니다.")
            return

        user_id = user['user_id']
        member = None
        try:
            member = ctx.guild.get_member(int(user_id))
        except:
            member = None

        # 디스코드 역할 제거
        role_obj = discord.utils.get(ctx.guild.roles, name=role_name)
        if member and role_obj and role_obj in member.roles:
            try:
                await member.remove_roles(role_obj, reason=f"관리자에 의한 제거: {ctx.author}")
            except discord.Forbidden:
                await ctx.send("❌ 봇에게 역할을 제거할 권한이 없습니다.")
                return
            except Exception as e:
                await ctx.send(f"❌ 디스코드 역할 제거 중 오류가 발생했습니다: {str(e)}")
                return

        # DB에서 역할 매핑 제거
        remove_user_role(user_id, role_name)

        await ctx.send(f"✅ 디스코드 ID '{discord_id}' 사용자를 '{role_name}' 역할에서 제거했습니다.")

    async def _register_entry(ctx):
        # 관리자: 패널 게시 채널 선택 / 일반: 바로 등록 버튼
        if ctx.author.guild_permissions.administrator:
            await ctx.send(
                "📌 등록 패널을 어느 채널에 둘지 선택하세요. (그 채널에 토큰 가입·프로필 버튼이 게시됩니다)",
                view=RegisterSetupView(ctx.author))
        else:
            await ctx.send(
                "🎫 역할 등록 — 아래 버튼으로 토큰 가입 / 프로필 등록을 하세요.",
                view=RoleRegisterButtonView())

    @role_group.command(name='등록')
    async def role_register(ctx):
        """토큰으로 역할 등록 (관리자는 패널 채널 선택)"""
        await _register_entry(ctx)

    @bot.command(name='등록')
    async def register_command(ctx):
        """토큰으로 역할 등록 - /역할 등록과 동일"""
        await _register_entry(ctx)

def register_persistent_view(bot):
    """봇 재시작 후에도 기존 버튼이 작동하도록 persistent view 등록"""
    try:
        view = RoleRegisterButtonView()
        bot.add_view(view)
        bot.add_view(RoleAssignEntryView())
        print(f"[OK] Persistent view 등록 완료 (custom_id: role_register_button)")
        logger.info(f"Persistent view 등록 완료 (custom_id: role_register_button)")
    except Exception as e:
        print(f"[ERROR] Persistent view 등록 실패: {e}")
        logger.error(f"Persistent view 등록 실패: {e}")


class RoleRegisterButtonView(discord.ui.View):
    """등록 버튼 View (봇 재시작 후에도 작동)"""
    
    def __init__(self, author=None, modal=None):
        super().__init__(timeout=None)  # timeout=None으로 영구적으로 유지
        self.author = author
        self.modal = modal
    
    @discord.ui.button(label='🎫 역할 등록 (토큰)', style=discord.ButtonStyle.primary, custom_id='role_register_button')
    async def open_modal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 각 사용자가 자신의 정보를 입력할 수 있도록 새로운 Modal 생성
        modal = RoleRegisterModal(interaction.user)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='📝 프로필 등록/수정', style=discord.ButtonStyle.secondary, custom_id='profile_open_button')
    async def open_profile_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 이름·OJ 핸들 입력 (역할 등록과 분리)
        from domain.user import UserRegistrationModal
        from common.database import get_user
        existing = get_user(str(interaction.user.id)) or {}
        await interaction.response.send_modal(UserRegistrationModal(existing))


class RegisterSetupView(discord.ui.View):
    """`/등록`(관리자) — 등록 패널을 게시할 채널을 선택."""

    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
        self.ch = discord.ui.ChannelSelect(
            placeholder="등록 패널을 둘 채널 선택",
            channel_types=[discord.ChannelType.text],
            min_values=1, max_values=1)
        self.ch.callback = self._on
        self.add_item(self.ch)

    async def _on(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(self.ch.values[0].id)
        if channel is None:
            await interaction.response.send_message("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
            return
        perms = channel.permissions_for(channel.guild.me)
        if not perms.send_messages:
            await interaction.response.send_message(
                f"❌ 봇이 {channel.mention} 에 메시지를 보낼 권한이 없습니다.", ephemeral=True)
            return
        await channel.send(
            "🎫 **역할 등록**\n토큰으로 역할에 가입하고, 프로필(이름·OJ 핸들)을 등록하세요.",
            view=RoleRegisterButtonView())
        await interaction.response.edit_message(
            content=f"✅ {channel.mention} 에 등록 패널을 게시했습니다.", view=None)


class ProfilePromptView(discord.ui.View):
    """역할 등록 직후 프로필 입력을 유도하는 버튼 (ephemeral 응답용)."""

    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="📝 프로필 등록/수정", style=discord.ButtonStyle.primary)
    async def open_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        from domain.user import UserRegistrationModal
        from common.database import get_user
        existing = get_user(str(interaction.user.id)) or {}
        await interaction.response.send_modal(UserRegistrationModal(existing))


class RoleRegisterModal(discord.ui.Modal, title="역할 등록 (토큰)"):
    """역할 등록 Modal — 토큰만 입력. 이름·OJ 핸들은 /프로필 에서 분리 관리.

    이전에는 BOJ 핸들을 필수로 받고 검증했지만, 등록(역할)과 프로필(핸들)을
    분리하고 외부 사이트 의존을 없애기 위해 토큰만 받는다.
    멤버십은 DB(user_roles)에 기록되어야 채점/주간현황에 잡힌다.
    """

    def __init__(self, author=None):
        super().__init__(timeout=600)
        self.author = author

        self.token_input = discord.ui.TextInput(
            label="토큰",
            placeholder="관리자가 준 역할 등록 토큰",
            max_length=100,
            required=True,
        )
        self.add_item(self.token_input)

    async def on_submit(self, interaction: discord.Interaction):
        from common.utils import load_data, save_data, verify_token, send_bot_notification
        from common.database import create_or_update_user, add_user_role

        data = load_data()
        role_tokens = data.get('role_tokens', {})
        token = self.token_input.value.strip()

        # 토큰으로 역할 찾기
        role_name = None
        for name, token_info in role_tokens.items():
            stored_hash = token_info.get('token_hash')
            if stored_hash and verify_token(token, stored_hash):
                role_name = name
                break
        if not role_name:
            await interaction.response.send_message(
                "❌ 유효하지 않은 토큰입니다. 토큰을 다시 확인해주세요.", ephemeral=True)
            return

        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if not role:
            await interaction.response.send_message(
                f"❌ '{role_name}' 역할을 서버에서 찾을 수 없습니다. 관리자에게 문의해주세요.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message(
                f"✅ 이미 '{role_name}' 역할을 가지고 있습니다.\n"
                f"OJ 핸들 등록/수정은 아래 버튼으로.",
                ephemeral=True, view=ProfilePromptView())
            return

        try:
            await interaction.user.add_roles(role)
            user_id = str(interaction.user.id)

            # DB 기록 — 채점/주간현황(get_role_users)이 읽는 곳
            create_or_update_user(user_id, str(interaction.user))
            add_user_role(user_id, role_name)

            # JSON 호환 유지 (기존 코드들이 참조)
            data.setdefault('users', {})
            if user_id not in data['users']:
                data['users'][user_id] = {
                    'username': str(interaction.user),
                    'boj_handle': None,
                    'tistory_links': [],
                    'roles': [],
                    'submissions': {},
                }
            if role_name not in data['users'][user_id].setdefault('roles', []):
                data['users'][user_id]['roles'].append(role_name)
            save_data(data)

            await send_bot_notification(
                interaction.guild,
                "👤 역할 가입",
                f"**사용자:** {interaction.user.mention} ({interaction.user.display_name})\n"
                f"**역할:** {role_name}",
                discord.Color.green(),
            )

            await interaction.response.send_message(
                f"✅ '{role_name}' 역할이 부여되었습니다!\n"
                f"이제 **프로필**에서 이름과 OJ 핸들(백준·Codeforces 등)을 등록하면 "
                f"풀이현황·주간테스트에 집계됩니다. 아래 버튼으로 등록하세요.",
                ephemeral=True, view=ProfilePromptView())
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ 봇에게 역할을 부여할 권한이 없습니다. 서버 관리자에게 문의해주세요.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 오류가 발생했습니다: {str(e)}", ephemeral=True)

# ==================== /역할 부여 — 드롭다운 패널 ====================

class RoleAssignView(discord.ui.View):
    """역할 드롭다운 + 사용자 선택 + 부여 버튼 (ephemeral)."""

    def __init__(self, author, role_names):
        super().__init__(timeout=600)
        self.author = author
        self.selected_role = None
        self.selected_member = None

        opts = ([discord.SelectOption(label=r, value=r) for r in role_names[:25]]
                or [discord.SelectOption(label="(역할 없음)", value="__none__")])
        self.role_select = discord.ui.Select(placeholder="역할 선택", options=opts, row=0)
        self.role_select.callback = self._on_role
        self.add_item(self.role_select)

        self.user_select = discord.ui.UserSelect(
            placeholder="사용자 선택", min_values=1, max_values=1, row=1)
        self.user_select.callback = self._on_user
        self.add_item(self.user_select)

        self.assign_btn = discord.ui.Button(
            label="부여", emoji="✅", style=discord.ButtonStyle.success, disabled=True, row=2)
        self.assign_btn.callback = self._on_assign
        self.add_item(self.assign_btn)

    async def _check(self, interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ 본인만 사용할 수 있습니다.", ephemeral=True)
            return False
        return True

    def _refresh(self):
        self.assign_btn.disabled = not (self.selected_role and self.selected_member)

    async def _on_role(self, interaction):
        if not await self._check(interaction):
            return
        v = self.role_select.values[0]
        if v == "__none__":
            return
        self.selected_role = v
        for o in self.role_select.options:
            o.default = (o.value == v)
        self._refresh()
        await interaction.response.edit_message(view=self)

    async def _on_user(self, interaction):
        if not await self._check(interaction):
            return
        self.selected_member = self.user_select.values[0]
        self._refresh()
        await interaction.response.edit_message(view=self)

    async def _on_assign(self, interaction):
        if not await self._check(interaction):
            return
        if not (self.selected_role and self.selected_member):
            await interaction.response.send_message("❌ 역할과 사용자를 모두 선택하세요.", ephemeral=True)
            return

        from common.database import create_or_update_user, add_user_role
        from common.utils import load_data, save_data, send_bot_notification

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = self.selected_member
        role_name = self.selected_role
        role_obj = discord.utils.get(guild.roles, name=role_name)
        if not role_obj:
            await interaction.followup.send(f"❌ '{role_name}' 역할을 서버에서 찾을 수 없습니다.", ephemeral=True)
            return
        try:
            await member.add_roles(role_obj, reason=f"관리자 역할 부여: {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ 봇에게 역할 부여 권한이 없습니다. (봇 역할 위치/권한 확인)", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"❌ 역할 부여 오류: {e}", ephemeral=True)
            return

        uid = str(member.id)
        create_or_update_user(uid, str(member))
        add_user_role(uid, role_name)
        data = load_data()
        data.setdefault('users', {})
        if uid not in data['users']:
            data['users'][uid] = {'username': str(member), 'boj_handle': None,
                                  'tistory_links': [], 'roles': [], 'submissions': {}}
        if role_name not in data['users'][uid].setdefault('roles', []):
            data['users'][uid]['roles'].append(role_name)
        save_data(data)

        await send_bot_notification(
            guild, "👤 역할 부여 (관리자)",
            f"**사용자:** {member.mention} ({member.display_name})\n"
            f"**역할:** {role_name}\n**부여자:** {interaction.user.mention}",
            discord.Color.blue())
        await interaction.followup.send(
            f"✅ {member.mention} 에게 '{role_name}' 역할 부여 완료. "
            f"(OJ 핸들은 본인이 `/프로필`에서)", ephemeral=True)


class RoleAssignEntryView(discord.ui.View):
    """`/역할 부여` 진입 — 영구 버튼 → 본인만 보이는 역할/사용자 셀렉트."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="역할 부여 설정 (본인만)", emoji="⚙️",
                       style=discord.ButtonStyle.primary, custom_id="role_assign_open")
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.", ephemeral=True)
            return
        from common.utils import load_data
        data = load_data()
        role_names = list(data.get('role_tokens', {}).keys())
        if not role_names:
            await interaction.response.send_message(
                "❌ 등록된 역할이 없습니다. `/역할 생성`으로 먼저 만들어주세요.", ephemeral=True)
            return
        await interaction.response.send_message(
            content="🎫 역할 부여 — 역할과 사용자를 선택하고 **부여**를 누르세요.",
            view=RoleAssignView(interaction.user, role_names), ephemeral=True)


# ==================== 범용 역할 선택 패널 ====================

class RolePickerView(discord.ui.View):
    """역할 하나를 드롭다운으로 골라 action(interaction, role_name) 을 실행하는 범용 패널."""

    def __init__(self, author, role_names, action, placeholder="역할 선택"):
        super().__init__(timeout=300)
        self.author = author
        self.action = action
        opts = ([discord.SelectOption(label=r, value=r) for r in role_names[:25]]
                or [discord.SelectOption(label="(역할 없음)", value="__none__")])
        self.sel = discord.ui.Select(placeholder=placeholder, options=opts)
        self.sel.callback = self._cb
        self.add_item(self.sel)

    async def _cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ 본인만 사용할 수 있습니다.", ephemeral=True)
            return
        val = self.sel.values[0]
        if val == "__none__":
            await interaction.response.send_message("❌ 등록된 역할이 없습니다.", ephemeral=True)
            return
        await self.action(interaction, val)


def _registered_role_names():
    return list(load_data().get('role_tokens', {}).keys())


# ==================== 주간 문제풀이 현황 스케줄 작업 ====================

_bot_instance_for_schedule = None

async def update_weekly_status_for_role(role_name: str, bot_instance):
    """특정 역할의 주간 문제풀이 현황 메시지 업데이트"""
    try:
        # 저장된 메시지 정보 가져오기
        msg_info = get_weekly_status_message(role_name)
        if not msg_info:
            return
        
        channel_id = int(msg_info['channel_id'])
        message_id = int(msg_info['message_id'])
        week_start_date_str = msg_info['week_start_date']
        
        # 채널과 메시지 가져오기
        channel = bot_instance.get_channel(channel_id)
        if not channel:
            return
        
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            # 메시지가 삭제되었으면 DB에서도 삭제
            from common.database import delete_weekly_status_message
            delete_weekly_status_message(role_name)
            return
        
        # 이번 주 월요일~일요일 계산
        week_start = datetime.strptime(week_start_date_str, '%Y-%m-%d')
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        # 역할을 가진 유저 목록 가져오기
        users = get_role_users(role_name)
        
        if not users:
            embed = discord.Embed(
                title=f"📊 '{role_name}' 주간 문제풀이 현황",
                description=f"기간: {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}",
                color=discord.Color.blue()
            )
            embed.add_field(name="멤버 없음", value="이 역할을 가진 멤버가 없습니다.", inline=False)
            await message.edit(embed=embed)
            return
        
        # 각 유저의 백준 문제풀이 현황 조회
        results = []
        for user_info in users:
            boj_handle = user_info.get('boj_handle')
            if not boj_handle or boj_handle == '미등록':
                continue
            
            try:
                solved_data = await get_weekly_solved_count(boj_handle, week_start, week_end)
                results.append({
                    'username': user_info['username'],
                    'boj_handle': boj_handle,
                    'solved_count': solved_data['count'],
                    'problems': solved_data['problems']
                })
            except Exception as e:
                print(f"[주간 현황] {boj_handle} 조회 오류: {e}")
        
        # 결과 정렬 (해결한 문제 수 많은 순)
        results.sort(key=lambda x: x['solved_count'], reverse=True)
        
        # 임베드 생성
        embed = discord.Embed(
            title=f"📊 '{role_name}' 주간 문제풀이 현황",
            description=f"기간: {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')} (월~일)\n마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            color=discord.Color.blue()
        )
        
        # 멤버별 현황 표시 (최대 25명)
        member_list = []
        total_solved = 0
        for i, result in enumerate(results[:25], 1):
            username = result['username']
            boj_handle = result['boj_handle']
            solved_count = result['solved_count']
            problems = result.get('problems', [])
            total_solved += solved_count
            
            # 문제 번호 표시 (최대 15개, 나머지는 "외 N개"로 표시)
            if solved_count == 0:
                member_list.append(f"{i}. {username} ({boj_handle}) - ✅ 0개")
            else:
                problems_sorted = sorted(problems)
                if len(problems_sorted) <= 15:
                    problems_str = ", ".join(map(str, problems_sorted))
                    member_list.append(f"{i}. {username} ({boj_handle}) - ✅ {solved_count}개 [{problems_str}]")
                else:
                    problems_str = ", ".join(map(str, problems_sorted[:15]))
                    remaining = len(problems_sorted) - 15
                    member_list.append(f"{i}. {username} ({boj_handle}) - ✅ {solved_count}개 [{problems_str}, ... 외 {remaining}개]")
        
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
        
        await message.edit(embed=embed)
    except Exception as e:
        print(f"[주간 현황 업데이트 오류] {role_name}: {e}")

@tasks.loop(hours=1)
async def hourly_weekly_status_update():
    """매시간 주간 현황 메시지 업데이트 (12시~00시)"""
    if not _bot_instance_for_schedule:
        return
    
    current_hour = datetime.now().hour
    
    # 12시~23시만 실행 (00시는 월요일 새 메시지 생성 시간)
    if current_hour < 12 or current_hour >= 24:
        return
    
    # 모든 역할에 대해 업데이트
    data = load_data()
    role_tokens = data.get('role_tokens', {})
    
    for role_name in role_tokens.keys():
        await update_weekly_status_for_role(role_name, _bot_instance_for_schedule)

@tasks.loop(time=time(hour=0, minute=0))
async def monday_weekly_status_reset():
    """월요일 00시에 새 주간 현황 메시지 생성"""
    if not _bot_instance_for_schedule:
        return
    
    # 월요일인지 확인
    if datetime.now().weekday() != 0:  # 0 = 월요일
        return
    
    # 모든 역할에 대해 새 메시지 생성
    data = load_data()
    role_tokens = data.get('role_tokens', {})
    
    for role_name in role_tokens.keys():
        try:
            # 이번 주 월요일 계산
            today = datetime.now()
            days_since_monday = today.weekday()
            monday = today - timedelta(days=days_since_monday)
            monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
            sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
            
            # 기존 메시지가 있으면 채널 찾기
            old_msg_info = get_weekly_status_message(role_name)
            if old_msg_info:
                channel_id = int(old_msg_info['channel_id'])
                channel = _bot_instance_for_schedule.get_channel(channel_id)
                if channel:
                    # 새 메시지 생성
                    embed = discord.Embed(
                        title=f"📊 '{role_name}' 주간 문제풀이 현황",
                        description=f"기간: {monday.strftime('%Y-%m-%d')} ~ {sunday.strftime('%Y-%m-%d')} (월~일)\n초기화 중...",
                        color=discord.Color.blue()
                    )
                    message = await channel.send(embed=embed)
                    
                    # 새 메시지 정보 저장
                    save_weekly_status_message(role_name, str(channel.id), str(message.id), monday.strftime('%Y-%m-%d'))
                    
                    # 즉시 업데이트
                    await update_weekly_status_for_role(role_name, _bot_instance_for_schedule)
        except Exception as e:
            print(f"[주간 현황 리셋 오류] {role_name}: {e}")

def start_weekly_status_scheduler(bot_instance):
    """주간 현황 스케줄러 시작"""
    global _bot_instance_for_schedule
    _bot_instance_for_schedule = bot_instance
    
    if not hourly_weekly_status_update.is_running():
        hourly_weekly_status_update.start()
    
    if not monday_weekly_status_reset.is_running():
        monday_weekly_status_reset.start()
    
    print("[OK] 주간 문제풀이 현황 스케줄러 시작됨")

