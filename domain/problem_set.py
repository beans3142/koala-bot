"""
문제집 및 모의테스트 관리 명령어
"""
import discord
from discord.ext import commands
from typing import List
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
)
from common.utils import load_data
from domain.channel import find_role_by_group_name
from common.boj_utils import get_user_solved_problems_from_solved_ac
from common.utils import send_bot_notification
from common.logger import get_logger

logger = get_logger()


def setup(bot):
    """봇에 명령어 등록"""
    
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
        embed = discord.Embed(
            title="📚 문제집 생성",
            description=f"**문제집명:** {name}\n\n아래 버튼을 클릭하여 문제 번호를 입력하세요.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=view)
    
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
                
                results.append({
                    'username': username,
                    'boj_handle': boj_handle,
                    'solved_count': solved_count,
                    'total': total_problems,
                    'status': '✅' if solved_count == total_problems else '📝'
                })
            except Exception as e:
                logger.error(f"문제집 현황 조회 오류 ({boj_handle}): {e}", exc_info=True)
                results.append({
                    'username': username,
                    'boj_handle': boj_handle,
                    'solved_count': 0,
                    'total': total_problems,
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
            status_text += f"{emoji} {result['username']}{boj_info} - {result['status']} [{result['solved_count']}/{result['total']}]\n"
        
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
        
        # 버튼을 사용하여 Modal 열기
        existing_problems = ','.join(map(str, problem_set['problem_ids']))
        view = ProblemSetUpdateView(name, existing_problems, ctx.author)
        embed = discord.Embed(
            title="📚 문제집 수정",
            description=f"**문제집명:** {name}\n**현재 문제 수:** {len(problem_set['problem_ids'])}개\n\n아래 버튼을 클릭하여 문제 번호를 수정하세요.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=view)
    
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
            title="⚠️ 문제집 삭제 확인",
            description=f"**문제집명:** {name}\n**문제 수:** {len(problem_set['problem_ids'])}개\n\n"
                       f"이 작업은 되돌릴 수 없습니다!\n\n"
                       f"정말 삭제하시겠습니까?",
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
    
    # ==================== 모의테스트 명령어 ====================
    
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
        embed = discord.Embed(
            title="📝 모의테스트 생성",
            description=f"**모의테스트명:** {name}\n\n아래 버튼을 클릭하여 문제 번호를 입력하세요.",
            color=discord.Color.purple()
        )
        await ctx.send(embed=embed, view=view)
    
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
        problem_ids = mock_test['problem_ids']
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
                
                results.append({
                    'username': username,
                    'boj_handle': boj_handle,
                    'solved_count': solved_count,
                    'total': total_problems,
                    'status': '✅' if solved_count == total_problems else '📝'
                })
            except Exception as e:
                logger.error(f"모의테스트 현황 조회 오류 ({boj_handle}): {e}", exc_info=True)
                results.append({
                    'username': username,
                    'boj_handle': boj_handle,
                    'solved_count': 0,
                    'total': total_problems,
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
            status_text += f"{emoji} {result['username']}{boj_info} - {result['status']} [{result['solved_count']}/{result['total']}]\n"
        
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
        
        # 버튼을 사용하여 Modal 열기
        existing_problems = ','.join(map(str, mock_test['problem_ids']))
        view = MockTestUpdateView(name, existing_problems, ctx.author)
        embed = discord.Embed(
            title="📝 모의테스트 수정",
            description=f"**모의테스트명:** {name}\n**현재 문제 수:** {len(mock_test['problem_ids'])}개\n\n아래 버튼을 클릭하여 문제 번호를 수정하세요.",
            color=discord.Color.purple()
        )
        await ctx.send(embed=embed, view=view)
    
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
            title="⚠️ 모의테스트 삭제 확인",
            description=f"**모의테스트명:** {name}\n**문제 수:** {len(mock_test['problem_ids'])}개\n\n"
                       f"이 작업은 되돌릴 수 없습니다!\n\n"
                       f"정말 삭제하시겠습니까?",
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


# ==================== View 클래스 (Modal 열기용) ====================

class ProblemSetCreateView(discord.ui.View):
    """문제집 생성 버튼 View"""
    
    def __init__(self, name: str, author):
        super().__init__(timeout=300)
        self.name = name
        self.author = author
    
    @discord.ui.button(label='📝 문제 번호 입력', style=discord.ButtonStyle.primary)
    async def create_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        modal = ProblemSetCreateModal(self.name)
        await interaction.response.send_modal(modal)


class ProblemSetUpdateView(discord.ui.View):
    """문제집 수정 버튼 View"""
    
    def __init__(self, name: str, existing_problems: str, author):
        super().__init__(timeout=300)
        self.name = name
        self.existing_problems = existing_problems
        self.author = author
    
    @discord.ui.button(label='📝 문제 번호 수정', style=discord.ButtonStyle.primary)
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        modal = ProblemSetUpdateModal(self.name, self.existing_problems)
        await interaction.response.send_modal(modal)


class MockTestCreateView(discord.ui.View):
    """모의테스트 생성 버튼 View"""
    
    def __init__(self, name: str, author):
        super().__init__(timeout=300)
        self.name = name
        self.author = author
    
    @discord.ui.button(label='📝 문제 번호 입력', style=discord.ButtonStyle.primary)
    async def create_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        modal = MockTestCreateModal(self.name)
        await interaction.response.send_modal(modal)


class MockTestUpdateView(discord.ui.View):
    """모의테스트 수정 버튼 View"""
    
    def __init__(self, name: str, existing_problems: str, author):
        super().__init__(timeout=300)
        self.name = name
        self.existing_problems = existing_problems
        self.author = author
    
    @discord.ui.button(label='📝 문제 번호 수정', style=discord.ButtonStyle.primary)
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        modal = MockTestUpdateModal(self.name, self.existing_problems)
        await interaction.response.send_modal(modal)


# ==================== Modal 클래스 ====================

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
        # 문제 번호 파싱
        problems_text = self.problems_input.value.strip()
        if not problems_text:
            await interaction.response.send_message("❌ 문제 번호를 입력해주세요.", ephemeral=True)
            return
        
        # 쉼표로 구분하여 문제 번호 리스트 생성
        problem_ids = []
        for pid_str in problems_text.split(','):
            pid_str = pid_str.strip()
            if pid_str.isdigit():
                problem_ids.append(int(pid_str))
        
        if not problem_ids:
            await interaction.response.send_message("❌ 유효한 문제 번호를 입력해주세요.", ephemeral=True)
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


class ProblemSetUpdateModal(discord.ui.Modal, title="문제집 수정"):
    """문제집 수정 Modal"""
    
    def __init__(self, name: str, existing_problems: str):
        super().__init__(timeout=300)
        self.name = name
        
        self.problems_input = discord.ui.TextInput(
            label="문제 번호 (쉼표로 구분)",
            placeholder="1000, 1001, 1002",
            style=discord.TextStyle.paragraph,
            default=existing_problems,
            required=True,
            max_length=2000,
        )
        self.add_item(self.problems_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        # 문제 번호 파싱
        problems_text = self.problems_input.value.strip()
        if not problems_text:
            await interaction.response.send_message("❌ 문제 번호를 입력해주세요.", ephemeral=True)
            return
        
        # 쉼표로 구분하여 문제 번호 리스트 생성
        problem_ids = []
        for pid_str in problems_text.split(','):
            pid_str = pid_str.strip()
            if pid_str.isdigit():
                problem_ids.append(int(pid_str))
        
        if not problem_ids:
            await interaction.response.send_message("❌ 유효한 문제 번호를 입력해주세요.", ephemeral=True)
            return
        
        # 중복 제거 및 정렬
        problem_ids = sorted(list(set(problem_ids)))
        
        # DB 업데이트
        update_problem_set(self.name, problem_ids)
        
        await interaction.response.send_message(
            f"✅ 문제집 '{self.name}'이(가) 수정되었습니다!\n문제 수: {len(problem_ids)}개",
            ephemeral=True
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
        # 문제 번호 파싱
        problems_text = self.problems_input.value.strip()
        if not problems_text:
            await interaction.response.send_message("❌ 문제 번호를 입력해주세요.", ephemeral=True)
            return
        
        # 쉼표로 구분하여 문제 번호 리스트 생성
        problem_ids = []
        for pid_str in problems_text.split(','):
            pid_str = pid_str.strip()
            if pid_str.isdigit():
                problem_ids.append(int(pid_str))
        
        if not problem_ids:
            await interaction.response.send_message("❌ 유효한 문제 번호를 입력해주세요.", ephemeral=True)
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


class MockTestUpdateModal(discord.ui.Modal, title="모의테스트 수정"):
    """모의테스트 수정 Modal"""
    
    def __init__(self, name: str, existing_problems: str):
        super().__init__(timeout=300)
        self.name = name
        
        self.problems_input = discord.ui.TextInput(
            label="문제 번호 (쉼표로 구분)",
            placeholder="1000, 1001, 1002",
            style=discord.TextStyle.paragraph,
            default=existing_problems,
            required=True,
            max_length=2000,
        )
        self.add_item(self.problems_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        # 문제 번호 파싱
        problems_text = self.problems_input.value.strip()
        if not problems_text:
            await interaction.response.send_message("❌ 문제 번호를 입력해주세요.", ephemeral=True)
            return
        
        # 쉼표로 구분하여 문제 번호 리스트 생성
        problem_ids = []
        for pid_str in problems_text.split(','):
            pid_str = pid_str.strip()
            if pid_str.isdigit():
                problem_ids.append(int(pid_str))
        
        if not problem_ids:
            await interaction.response.send_message("❌ 유효한 문제 번호를 입력해주세요.", ephemeral=True)
            return
        
        # 중복 제거 및 정렬
        problem_ids = sorted(list(set(problem_ids)))
        
        # DB 업데이트
        update_mock_test(self.name, problem_ids)
        
        await interaction.response.send_message(
            f"✅ 모의테스트 '{self.name}'이(가) 수정되었습니다!\n문제 수: {len(problem_ids)}개",
            ephemeral=True
        )


# ==================== View 클래스 ====================

class ProblemSetDeleteConfirmView(discord.ui.View):
    """문제집 삭제 확인 버튼 View"""
    
    def __init__(self, name: str, author):
        super().__init__(timeout=300)
        self.name = name
        self.author = author
    
    @discord.ui.button(label='✅ 삭제', style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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


class MockTestDeleteConfirmView(discord.ui.View):
    """모의테스트 삭제 확인 버튼 View"""
    
    def __init__(self, name: str, author):
        super().__init__(timeout=300)
        self.name = name
        self.author = author
    
    @discord.ui.button(label='✅ 삭제', style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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
