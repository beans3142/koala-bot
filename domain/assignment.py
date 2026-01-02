"""
과제 관리 명령어 (CRUD 및 제출)
"""
import discord
import re
from discord.ext import commands, tasks
from datetime import datetime, timedelta, time
from common.utils import load_data, save_data, parse_datetime
from common.boj_utils import check_problem_solved_from_status, get_problem_tier, number_to_tier, get_group_practice_ranking
from common.logger import get_logger

logger = get_logger()

def setup(bot):
    """봇에 명령어 등록"""
    global _bot_instance, auto_verify_mocktest
    
    _bot_instance = bot
    
    # 봇이 준비된 후 스케줄러 시작
    @bot.event
    async def on_ready():
        if not auto_verify_mocktest.is_running():
            auto_verify_mocktest.start()
    
    @bot.group(name='과제')
    async def assignment_group(ctx):
        """과제 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 올바른 명령어를 입력해주세요. `/도움말`을 확인해주세요.")

    @assignment_group.command(name='생성')
    @commands.has_permissions(administrator=True)
    async def assignment_create(ctx, group_name: str):
        """과제 생성 (관리자 전용)
        
        스터디 그룹에 새로운 과제를 생성합니다. 과제 유형에 따라 다른 파라미터가 필요합니다.
        
        📝 **기본 형식**
        `/과제 생성 [그룹 이름] [유형] [파라미터들...]`
        
        ---
        
        📚 **1. 블로그 과제**
        
        **형식:** `/과제 생성 [그룹 이름] 블로그 [개수]`
        
        **파라미터 설명:**
        - `[그룹 이름]`: Discord 역할 이름 (예: "14기-기초", "15기-심화")
        - `블로그`: 과제 유형 (고정)
        - `[개수]`: 필요한 블로그 포스트 개수 (숫자, 필수)
        
        **예시:**
        ```
        /과제 생성 14기-기초 블로그 3
        → 14기-기초 그룹에 블로그 포스트 3개를 제출하는 과제 생성
        ```
        
        **동작 방식:**
        - 시작일: 현재 시간 (즉시 시작)
        - 마감일: 없음 (제출 개수만 확인)
        - 사용자는 `/과제 제출 블로그 <링크>` 명령어로 블로그 링크를 제출
        - 운영진이 수동으로 확인
        
        ---
        
        💻 **2. 문제풀이 과제**
        
        **형식:** `/과제 생성 [그룹 이름] 문제풀이 [시작시간] [종료시간] [개수] [최소 티어 제한]`
        
        **파라미터 설명:**
        - `[그룹 이름]`: Discord 역할 이름
        - `문제풀이`: 과제 유형 (고정)
        - `[시작시간]`: 과제 시작 시간 (선택, 기본값: 현재 시간)
          - 형식: "2024-12-31", "2024-12-31 00:00", "7일" (현재로부터 7일 후)
        - `[종료시간]`: 과제 마감 시간 (필수)
          - 형식: "2024-12-31 23:59", "1주" (시작일로부터 1주 후)
        - `[개수]`: 해결해야 할 문제 개수 (선택, 기본값: 제한 없음)
        - `[최소 티어 제한]`: 최소 난이도 제한 (선택, 기본값: 제한 없음)
          - 형식: "Bronze V", "Silver I", "Gold II" 등
        
        **예시:**
        ```
        /과제 생성 14기-기초 문제풀이 2024-12-31 2025-01-07 5 Gold I
        → 2024-12-31부터 2025-01-07까지, Gold I 이상 난이도 문제 5개 해결
        
        /과제 생성 14기-기초 문제풀이 7일 3
        → 현재로부터 7일 후까지, 난이도 제한 없이 문제 3개 해결
        
        /과제 생성 14기-기초 문제풀이 2024-12-31 23:59 1주
        → 2024-12-31 23:59부터 1주 동안, 난이도 제한 없이 자유 문제풀이
        ```
        
        **동작 방식:**
        - 시작일과 종료일 사이에만 과제가 활성화됨
        - 사용자는 `/과제 제출 문제풀이 [그룹명] [문제번호]` 명령어로 제출
        - 백준에서 실제로 해결했는지 자동 확인
        - 난이도 제한이 있으면 해당 티어 이상 문제만 인정
        
        ---
        
        🎯 **3. 모의테스트 과제**
        
        **형식:** `/과제 생성 [그룹 이름] 모의테스트 [시작시간] [종료시간] [문제번호들] [최소 solve 수]`
        
        **파라미터 설명:**
        - `[그룹 이름]`: Discord 역할 이름
        - `모의테스트`: 과제 유형 (고정)
        - `[시작시간]`: 과제 시작 시간 (선택, 기본값: 현재 시간)
          - 형식: "2024-12-31", "2024-12-31 00:00", "7일"
        - `[종료시간]`: 과제 마감 시간 (필수)
          - 형식: "2024-12-31 23:59", "1주"
        - `[문제번호들]`: 해결해야 할 문제 번호 리스트 (필수)
          - 형식: 쉼표로 구분, 예: "1000,1001,1002,1003"
          - 공백 없이 입력: "1000,1001,1002" ✅
          - 공백 포함 가능: "1000, 1001, 1002" ✅
        - `[최소 solve 수]`: 최소 해결 문제 수 (선택, 기본값: 1)
          - 모든 문제를 해결해야 하면 문제 개수와 동일하게 설정
        
        **예시:**
        ```
        /과제 생성 14기-기초 모의테스트 2024-12-31 2025-01-07 1000,1001,1002,1003 4
        → 2024-12-31부터 2025-01-07까지, 문제 1000, 1001, 1002, 1003 중 최소 4개 해결
        
        /과제 생성 14기-기초 모의테스트 7일 1000,1001,1002 1
        → 현재로부터 7일 후까지, 문제 1000, 1001, 1002 중 최소 1개 해결 (기본값)
        
        /과제 생성 14기-기초 모의테스트 2024-12-31 23:59 1주 1000,1001,1002,1003,1004 3
        → 2024-12-31 23:59부터 1주 동안, 5개 문제 중 최소 3개 해결
        ```
        
        **동작 방식:**
        - 시작일과 종료일 사이에만 과제가 활성화됨
        - 사용자는 `/과제 제출 모의테스트` 명령어로 제출
        - 제출 시 백준에서 지정된 문제들의 해결 여부를 자동 확인
        - 모든 문제를 해결했으면 자동 인증, 일부만 해결했으면 미해결 문제 표시
        - 종료 시간에 자동으로 그룹 내 모든 인원의 해결 여부를 확인하여 인증 (일요일 11시 자동 실행)
        
        **시간 형식 가이드:**
        - 상대 시간: "7일" (현재로부터 7일 후), "1주" (현재로부터 1주 후), "2주"
        - 절대 시간: "2024-12-31" (해당 날짜 00:00), "2024-12-31 23:59", "2024/12/31"
        - 시간 미지정 시 날짜만 입력하면 00:00으로 설정됨
        
        **주의사항:**
        - 그룹 이름은 Discord 서버에 존재하는 역할 이름과 정확히 일치해야 합니다
        - 문제풀이와 모의테스트는 시작시간과 종료시간을 모두 입력해야 합니다
        - 모의테스트의 문제 번호는 백준 문제 번호를 정확히 입력해야 합니다
        - 사용자는 `/유저등록 <BOJ핸들>` 명령어로 BOJ 핸들을 등록해야 자동 확인이 가능합니다
        """
        # 그룹(역할) 확인
        role = discord.utils.get(ctx.guild.roles, name=group_name)
        if not role:
            await ctx.send(f"❌ '{group_name}' 그룹(역할)을 찾을 수 없습니다.\n💡 서버에 존재하는 역할 이름을 정확히 입력해주세요.")
            return
        
        # 과제 유형 선택 View 생성
        type_view = AssignmentTypeSelectView(group_name, ctx.author)
        embed = discord.Embed(
            title="📝 과제 생성",
            description=f"**선택한 그룹:** {group_name}\n\n과제 유형을 선택하세요:",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=type_view)

    @assignment_group.command(name='수정')
    @commands.has_permissions(administrator=True)
    async def assignment_modify(ctx, group_name: str = None, assignment_name: str = None):
        """과제 수정 (관리자 전용)
        
        기존 과제의 설정을 수정합니다. 그룹명과 과제 이름으로 찾습니다.
        
        사용법:
        - 그룹 선택: /과제 수정
        - 직접 수정: /과제 수정 <그룹명> <과제이름>
        
        예시:
        - /과제 수정 (그룹 선택 후 과제 선택)
        - /과제 수정 21기-코딩테스트 1주차
        """
        data = load_data()
        
        # 그룹명이 없으면 그룹 선택
        if not group_name:
            # 모든 그룹 수집
            all_groups = list(data.get('studies', {}).keys())
            
            if not all_groups:
                await ctx.send("❌ 등록된 그룹이 없습니다.")
                return
            
            # 그룹 선택 View 생성
            view = GroupSelectForModifyView(all_groups, ctx.author)
            embed = discord.Embed(
                title="📝 과제 수정",
                description="수정할 과제가 속한 그룹을 선택하세요:",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed, view=view)
            return
        
        # 그룹 확인
        if group_name not in data.get('studies', {}):
            await ctx.send(f"❌ '{group_name}' 그룹을 찾을 수 없습니다.")
            return
        
        # 과제 이름이 없으면 해당 그룹의 과제 목록 표시
        if not assignment_name:
            assignments = data['studies'][group_name].get('assignments', {})
            if not assignments:
                await ctx.send(f"❌ '{group_name}' 그룹에 등록된 과제가 없습니다.")
                return
            
            # 과제 목록 생성
            assignment_list = []
            for aid, assignment in assignments.items():
                assignment_list.append({
                    'id': aid,
                    'name': assignment.get('name', aid),
                    'type': assignment.get('type', '알 수 없음'),
                    'study': group_name
                })
            
            view = AssignmentSelectView(assignment_list, ctx.author)
            embed = discord.Embed(
                title="📝 과제 수정",
                description=f"**그룹:** {group_name}\n\n수정할 과제를 선택하세요:",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed, view=view)
            return
        
        # 그룹명과 과제 이름으로 과제 찾기
        assignments = data['studies'][group_name].get('assignments', {})
        found_assignment = None
        found_assignment_id = None
        
        for aid, assignment in assignments.items():
            if assignment.get('name') == assignment_name:
                found_assignment = assignment
                found_assignment_id = aid
                break
        
        if not found_assignment:
            await ctx.send(f"❌ '{group_name}' 그룹에서 '{assignment_name}' 과제를 찾을 수 없습니다.")
            return
        
        # Modal 띄우기
        modal = AssignmentModifyModal(found_assignment, found_assignment_id, group_name)
        await ctx.send("📝 아래 버튼을 눌러 수정 폼을 열어주세요.", view=AssignmentModifyButtonView(ctx.author, modal))

    @assignment_group.command(name='삭제')
    @commands.has_permissions(administrator=True)
    async def assignment_delete(ctx, group_name: str = None, assignment_name: str = None):
        """과제 삭제 (관리자 전용)
        
        기존 과제를 삭제합니다. 그룹명과 과제 이름으로 찾습니다.
        
        사용법:
        - 그룹 선택: /과제 삭제
        - 직접 삭제: /과제 삭제 <그룹명> <과제이름>
        
        예시:
        - /과제 삭제 (그룹 선택 후 과제 선택)
        - /과제 삭제 21기-코딩테스트 1주차
        """
        data = load_data()
        
        # 그룹명이 없으면 그룹 선택
        if not group_name:
            # 모든 그룹 수집
            all_groups = list(data.get('studies', {}).keys())
            
            if not all_groups:
                await ctx.send("❌ 등록된 그룹이 없습니다.")
                return
            
            # 그룹 선택 View 생성
            view = GroupSelectForDeleteView(all_groups, ctx.author)
            embed = discord.Embed(
                title="🗑️ 과제 삭제",
                description="삭제할 과제가 속한 그룹을 선택하세요:",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, view=view)
            return
        
        # 그룹 확인
        if group_name not in data.get('studies', {}):
            await ctx.send(f"❌ '{group_name}' 그룹을 찾을 수 없습니다.")
            return
        
        # 과제 이름이 없으면 해당 그룹의 과제 목록 표시
        if not assignment_name:
            assignments = data['studies'][group_name].get('assignments', {})
            if not assignments:
                await ctx.send(f"❌ '{group_name}' 그룹에 등록된 과제가 없습니다.")
                return
            
            # 과제 목록 생성
            assignment_list = []
            for aid, assignment in assignments.items():
                assignment_list.append({
                    'id': aid,
                    'name': assignment.get('name', aid),
                    'type': assignment.get('type', '알 수 없음'),
                    'study': group_name
                })
            
            view = AssignmentDeleteView(assignment_list, ctx.author)
            embed = discord.Embed(
                title="🗑️ 과제 삭제",
                description=f"**그룹:** {group_name}\n\n삭제할 과제를 선택하세요:",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, view=view)
            return
        
        # 그룹명과 과제 이름으로 과제 찾기 및 삭제
        assignments = data['studies'][group_name].get('assignments', {})
        deleted = False
        found_assignment_id = None
        
        for aid, assignment in assignments.items():
            if assignment.get('name') == assignment_name:
                found_assignment_id = aid
                del assignments[aid]
                deleted = True
                break
        
        if not deleted:
            await ctx.send(f"❌ '{group_name}' 그룹에서 '{assignment_name}' 과제를 찾을 수 없습니다.")
            return
        
        # DB에서도 삭제
        from common.database import delete_assignment
        delete_assignment(found_assignment_id)
        
        save_data(data)
        await ctx.send(f"✅ 과제 '{assignment_name}'이 삭제되었습니다.")
    
    # 추가 명령어 등록
    setup_commands(bot, assignment_group)


class AssignmentTypeSelectView(discord.ui.View):
    """과제 유형 선택 Select Menu"""
    
    def __init__(self, group_name, author):
        super().__init__(timeout=300)
        self.group_name = group_name
        self.author = author
        
        options = [
            discord.SelectOption(label="블로그", value="블로그", description="블로그 포스트 제출 과제"),
            discord.SelectOption(label="문제풀이", value="문제풀이", description="백준 문제 풀이 과제"),
            discord.SelectOption(label="모의테스트", value="모의테스트", description="모의테스트 과제")
        ]
        
        self.select = discord.ui.Select(
            placeholder="과제 유형을 선택하세요...",
            options=options
        )
        self.select.callback = self.on_select
        self.add_item(self.select)
    
    async def on_select(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 메뉴는 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        assignment_type = self.select.values[0]
        
        # Modal 띄우기
        modal = AssignmentCreateModal(self.group_name, assignment_type, self.author)
        await interaction.response.send_modal(modal)


class AssignmentCreateModal(discord.ui.Modal, title="과제 생성"):
    """과제 생성 Modal"""
    
    def __init__(self, group_name, assignment_type, author):
        super().__init__(timeout=600)
        self.group_name = group_name
        self.assignment_type = assignment_type
        self.author = author
        
        # 과제 이름 (필수)
        self.name_input = discord.ui.TextInput(
            label="과제 이름",
            placeholder="예: 1주차, 2주차, 중간고사 대비 등",
            max_length=100,
            required=True
        )
        self.add_item(self.name_input)
        
        # 과제 타입별 필드 추가
        if assignment_type == '블로그':
            self.count_input = discord.ui.TextInput(
                label="필요 개수",
                placeholder="예: 3",
                max_length=10,
                required=True
            )
            self.add_item(self.count_input)
        
        elif assignment_type == '문제풀이':
            self.start_input = discord.ui.TextInput(
                label="시작일",
                placeholder="예: 2024-12-31 15:20 또는 15:20",
                max_length=50,
                required=False
            )
            self.add_item(self.start_input)
            
            self.deadline_input = discord.ui.TextInput(
                label="마감일",
                placeholder="예: 2024-12-31 15:25 또는 15:25",
                max_length=50,
                required=True
            )
            self.add_item(self.deadline_input)
            
            self.tier_input = discord.ui.TextInput(
                label="최소 티어 (선택)",
                placeholder="예: Gold I (비워두면 제한 없음)",
                max_length=20,
                required=False
            )
            self.add_item(self.tier_input)
        
        elif assignment_type == '모의테스트':
            self.start_input = discord.ui.TextInput(
                label="시작일",
                placeholder="예: 2024-12-31 15:20 또는 15:20",
                max_length=50,
                required=False
            )
            self.add_item(self.start_input)
            
            self.deadline_input = discord.ui.TextInput(
                label="마감일",
                placeholder="예: 2024-12-31 15:25 또는 15:25",
                max_length=50,
                required=True
            )
            self.add_item(self.deadline_input)
            
            self.problems_input = discord.ui.TextInput(
                label="문제 번호 (쉼표로 구분)",
                placeholder="예: 1000,1001,1002",
                max_length=500,
                required=True
            )
            self.add_item(self.problems_input)
            
            self.min_solved_input = discord.ui.TextInput(
                label="최소 해결 수",
                placeholder="예: 1",
                default="1",
                max_length=10,
                required=False
            )
            self.add_item(self.min_solved_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        from common.utils import load_data, save_data, parse_datetime
        from common.boj_utils import tier_to_number, number_to_tier
        
        data = load_data()
        
        # 스터디(역할) 확인
        role = discord.utils.get(interaction.guild.roles, name=self.group_name)
        if not role:
            await interaction.response.send_message(f"❌ '{self.group_name}' 그룹을 찾을 수 없습니다.", ephemeral=True)
            return
        
        assignment_name = self.name_input.value.strip()
        if not assignment_name:
            await interaction.response.send_message("❌ 과제 이름을 입력해주세요.", ephemeral=True)
            return
        
        config = {}
        
        if self.assignment_type == '블로그':
            try:
                config['count'] = int(self.count_input.value.strip())
            except ValueError:
                await interaction.response.send_message("❌ 개수는 숫자여야 합니다.", ephemeral=True)
                return
            
            config['start_date'] = datetime.now().isoformat()
        
        elif self.assignment_type == '문제풀이':
            # 시작일
            if self.start_input.value.strip():
                start_dt = parse_datetime(self.start_input.value.strip())
                if start_dt:
                    config['start_date'] = start_dt.isoformat()
                else:
                    await interaction.response.send_message("❌ 시작일 형식이 올바르지 않습니다.", ephemeral=True)
                    return
            else:
                config['start_date'] = datetime.now().isoformat()
            
            # 마감일
            deadline_dt = parse_datetime(self.deadline_input.value.strip())
            if deadline_dt:
                config['deadline'] = deadline_dt.isoformat()
                start_dt = datetime.fromisoformat(config['start_date'])
                config['deadline_days'] = (deadline_dt - start_dt).days
            else:
                await interaction.response.send_message("❌ 마감일 형식이 올바르지 않습니다.", ephemeral=True)
                return
            
            # 최소 티어
            if self.tier_input.value.strip():
                tier_num = tier_to_number(self.tier_input.value.strip())
                if tier_num is not None:
                    config['min_tier'] = tier_num
                else:
                    await interaction.response.send_message("❌ 티어 형식이 올바르지 않습니다. (예: G2 또는 Gold I)", ephemeral=True)
                    return
            else:
                config['min_tier'] = None
            
            config['problems'] = []
        
        elif self.assignment_type == '모의테스트':
            # 시작일
            if self.start_input.value.strip():
                start_dt = parse_datetime(self.start_input.value.strip())
                if start_dt:
                    config['start_date'] = start_dt.isoformat()
                else:
                    await interaction.response.send_message("❌ 시작일 형식이 올바르지 않습니다.", ephemeral=True)
                    return
            else:
                config['start_date'] = datetime.now().isoformat()
            
            # 마감일
            deadline_dt = parse_datetime(self.deadline_input.value.strip())
            if deadline_dt:
                config['deadline'] = deadline_dt.isoformat()
            else:
                await interaction.response.send_message("❌ 마감일 형식이 올바르지 않습니다.", ephemeral=True)
                return
            
            # 문제 번호
            try:
                problem_ids = [int(p.strip()) for p in self.problems_input.value.strip().split(',') if p.strip()]
                if not problem_ids:
                    await interaction.response.send_message("❌ 문제 번호를 올바르게 입력해주세요.", ephemeral=True)
                    return
                config['problem_ids'] = problem_ids
            except ValueError:
                await interaction.response.send_message("❌ 문제 번호는 숫자여야 합니다. (예: 1000,1001,1002)", ephemeral=True)
                return
            
            # 최소 solve 수
            min_solved = 1
            if self.min_solved_input.value.strip():
                try:
                    min_solved = int(self.min_solved_input.value.strip())
                except ValueError:
                    min_solved = 1
            config['min_solved'] = min_solved
        
        # 과제 ID 생성
        assignment_id = f"{self.group_name}_{self.assignment_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 데이터 저장
        if 'studies' not in data:
            data['studies'] = {}
        if self.group_name not in data['studies']:
            data['studies'][self.group_name] = {'assignments': {}}
        
        data['studies'][self.group_name]['assignments'][assignment_id] = {
            'type': self.assignment_type,
            'name': assignment_name,
            'config': config,
            'created_at': datetime.now().isoformat(),
            'created_by': str(interaction.user.id)
        }
        
        save_data(data)
        
        # 응답 메시지
        embed = discord.Embed(
            title=f"✅ 과제 생성 완료",
            description=f"**과제명:** {assignment_name}\n**스터디:** {self.group_name}\n**종류:** {self.assignment_type}",
            color=discord.Color.green()
        )
        
        # 시작일 표시
        start_dt = datetime.fromisoformat(config.get('start_date'))
        start_str = start_dt.strftime('%Y-%m-%d %H:%M')
        embed.add_field(name="시작일", value=start_str, inline=True)
        
        if self.assignment_type == '블로그':
            embed.add_field(name="필요 개수", value=f"{config.get('count', 0)}개", inline=True)
        elif self.assignment_type == '문제풀이':
            deadline_dt = datetime.fromisoformat(config.get('deadline'))
            deadline_str = deadline_dt.strftime('%Y-%m-%d %H:%M')
            embed.add_field(name="마감일", value=deadline_str, inline=True)
            if config.get('min_tier'):
                from common.boj_utils import number_to_tier_short
                embed.add_field(name="최소 난이도", value=number_to_tier_short(config['min_tier']), inline=True)
        elif self.assignment_type == '모의테스트':
            problem_ids = config.get('problem_ids', [])
            embed.add_field(name="문제 번호", value=f"{len(problem_ids)}개: {', '.join(map(str, problem_ids))}", inline=False)
            deadline_dt = datetime.fromisoformat(config.get('deadline'))
            deadline_str = deadline_dt.strftime('%Y-%m-%d %H:%M')
            embed.add_field(name="마감일", value=deadline_str, inline=True)
            min_solved = config.get('min_solved', 1)
            embed.add_field(name="최소 해결 수", value=f"{min_solved}개", inline=True)
        
        embed.add_field(name="과제 ID", value=f"`{assignment_id}`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=False)


class GroupSelectForModifyView(discord.ui.View):
    """과제 수정을 위한 그룹 선택 View"""
    
    def __init__(self, groups, author):
        super().__init__(timeout=300)
        self.groups = groups
        self.author = author
        
        options = []
        for group in groups[:25]:
            options.append(discord.SelectOption(
                label=group,
                description=f"{group} 그룹의 과제 수정",
                value=group
            ))
        
        self.select = discord.ui.Select(
            placeholder="그룹을 선택하세요...",
            options=options
        )
        self.select.callback = self.on_select
        self.add_item(self.select)
    
    async def on_select(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 메뉴는 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        group_name = self.select.values[0]
        from common.utils import load_data
        data = load_data()
        
        assignments = data.get('studies', {}).get(group_name, {}).get('assignments', {})
        if not assignments:
            await interaction.response.send_message(f"❌ '{group_name}' 그룹에 등록된 과제가 없습니다.", ephemeral=True)
            return
        
        assignment_list = []
        for aid, assignment in assignments.items():
            assignment_list.append({
                'id': aid,
                'name': assignment.get('name', aid),
                'type': assignment.get('type', '알 수 없음'),
                'study': group_name
            })
        
        view = AssignmentSelectView(assignment_list, self.author)
        embed = discord.Embed(
            title="📝 과제 수정",
            description=f"**그룹:** {group_name}\n\n수정할 과제를 선택하세요:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)


class GroupSelectForDeleteView(discord.ui.View):
    """과제 삭제를 위한 그룹 선택 View"""
    
    def __init__(self, groups, author):
        super().__init__(timeout=300)
        self.groups = groups
        self.author = author
        
        options = []
        for group in groups[:25]:
            options.append(discord.SelectOption(
                label=group,
                description=f"{group} 그룹의 과제 삭제",
                value=group
            ))
        
        self.select = discord.ui.Select(
            placeholder="그룹을 선택하세요...",
            options=options
        )
        self.select.callback = self.on_select
        self.add_item(self.select)
    
    async def on_select(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 메뉴는 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        group_name = self.select.values[0]
        from common.utils import load_data
        data = load_data()
        
        assignments = data.get('studies', {}).get(group_name, {}).get('assignments', {})
        if not assignments:
            await interaction.response.send_message(f"❌ '{group_name}' 그룹에 등록된 과제가 없습니다.", ephemeral=True)
            return
        
        assignment_list = []
        for aid, assignment in assignments.items():
            assignment_list.append({
                'id': aid,
                'name': assignment.get('name', aid),
                'type': assignment.get('type', '알 수 없음'),
                'study': group_name
            })
        
        view = AssignmentDeleteView(assignment_list, self.author)
        embed = discord.Embed(
            title="🗑️ 과제 삭제",
            description=f"**그룹:** {group_name}\n\n삭제할 과제를 선택하세요:",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=view)


class AssignmentModifyButtonView(discord.ui.View):
    """과제 수정 Modal을 여는 버튼 View"""
    
    def __init__(self, author, modal):
        super().__init__(timeout=300)
        self.author = author
        self.modal = modal
    
    @discord.ui.button(label='📝 수정 폼 열기', style=discord.ButtonStyle.primary)
    async def open_modal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        await interaction.response.send_modal(self.modal)


class AssignmentSelectView(discord.ui.View):
    """과제 선택 Select Menu"""
    
    def __init__(self, assignments, author):
        super().__init__(timeout=300)
        self.assignments = assignments
        self.author = author
        
        # Select Menu 옵션 생성 (최대 25개)
        options = []
        for i, assignment in enumerate(assignments[:25]):
            label = assignment['name'][:100]  # 최대 100자
            description = f"{assignment['type']} - {assignment['study']}"[:100]
            options.append(discord.SelectOption(
                label=label,
                description=description,
                value=assignment['id']
            ))
        
        self.select = discord.ui.Select(
            placeholder="과제를 선택하세요...",
            options=options
        )
        self.select.callback = self.on_select
        self.add_item(self.select)
    
    async def on_select(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 메뉴는 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        assignment_id = self.select.values[0]
        assignment = next((a for a in self.assignments if a['id'] == assignment_id), None)
        
        if not assignment:
            await interaction.response.send_message("❌ 과제를 찾을 수 없습니다.", ephemeral=True)
            return
        
        # 과제 정보 표시 및 수정 Modal 띄우기
        from common.utils import load_data
        data = load_data()
        
        # 과제 찾기
        found_assignment = None
        study_name = None
        for study, study_data in data.get('studies', {}).items():
            if assignment_id in study_data.get('assignments', {}):
                found_assignment = study_data['assignments'][assignment_id]
                study_name = study
                break
        
        if not found_assignment:
            await interaction.response.send_message("❌ 과제를 찾을 수 없습니다.", ephemeral=True)
            return
        
        # Modal 띄우기
        modal = AssignmentModifyModal(found_assignment, assignment_id, study_name)
        await interaction.response.send_modal(modal)


class AssignmentModifyModal(discord.ui.Modal, title="과제 수정"):
    """과제 수정 Modal"""
    
    def __init__(self, assignment, assignment_id, study_name):
        super().__init__(timeout=600)
        self.assignment = assignment
        self.assignment_id = assignment_id
        self.study_name = study_name
        self.assignment_type = assignment.get('type')
        self.config = assignment.get('config', {})
        
        # 과제 이름
        self.name_input = discord.ui.TextInput(
            label="과제 이름",
            placeholder="과제 이름을 입력하세요",
            default=assignment.get('name', ''),
            max_length=100,
            required=False
        )
        self.add_item(self.name_input)
        
        # 과제 타입별 필드 추가
        if self.assignment_type == '블로그':
            count = self.config.get('count', 0)
            self.count_input = discord.ui.TextInput(
                label="필요 개수",
                placeholder="블로그 포스트 개수",
                default=str(count) if count else '',
                max_length=10,
                required=False
            )
            self.add_item(self.count_input)
        
        elif self.assignment_type == '문제풀이':
            # 시작일
            start_date = self.config.get('start_date')
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date)
                    start_str = start_dt.strftime('%Y-%m-%d %H:%M')
                except:
                    start_str = ''
            else:
                start_str = ''
            
            self.start_input = discord.ui.TextInput(
                label="시작일",
                placeholder="예: 2024-12-31 15:20 또는 15:20",
                default=start_str,
                max_length=50,
                required=False
            )
            self.add_item(self.start_input)
            
            # 마감일
            deadline = self.config.get('deadline')
            if deadline:
                try:
                    deadline_dt = datetime.fromisoformat(deadline)
                    deadline_str = deadline_dt.strftime('%Y-%m-%d %H:%M')
                except:
                    deadline_str = ''
            else:
                deadline_str = ''
            
            self.deadline_input = discord.ui.TextInput(
                label="마감일",
                placeholder="예: 2024-12-31 15:25 또는 15:25",
                default=deadline_str,
                max_length=50,
                required=False
            )
            self.add_item(self.deadline_input)
            
            # 최소 티어
            min_tier = self.config.get('min_tier')
            if min_tier:
                from common.boj_utils import number_to_tier_short
                tier_name = number_to_tier_short(min_tier)
            else:
                tier_name = ''
            
            self.tier_input = discord.ui.TextInput(
                label="최소 티어 (선택)",
                placeholder="예: G2 또는 Gold I (비워두면 제한 없음)",
                default=tier_name,
                max_length=20,
                required=False
            )
            self.add_item(self.tier_input)
        
        elif self.assignment_type == '모의테스트':
            # 시작일
            start_date = self.config.get('start_date')
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date)
                    start_str = start_dt.strftime('%Y-%m-%d %H:%M')
                except:
                    start_str = ''
            else:
                start_str = ''
            
            self.start_input = discord.ui.TextInput(
                label="시작일",
                placeholder="예: 2024-12-31 15:20 또는 15:20",
                default=start_str,
                max_length=50,
                required=False
            )
            self.add_item(self.start_input)
            
            # 마감일
            deadline = self.config.get('deadline')
            if deadline:
                try:
                    deadline_dt = datetime.fromisoformat(deadline)
                    deadline_str = deadline_dt.strftime('%Y-%m-%d %H:%M')
                except:
                    deadline_str = ''
            else:
                deadline_str = ''
            
            self.deadline_input = discord.ui.TextInput(
                label="마감일",
                placeholder="예: 2024-12-31 15:25 또는 15:25",
                default=deadline_str,
                max_length=50,
                required=False
            )
            self.add_item(self.deadline_input)
            
            # 문제 번호
            problem_ids = self.config.get('problem_ids', [])
            problem_ids_str = ','.join(map(str, problem_ids)) if problem_ids else ''
            
            self.problems_input = discord.ui.TextInput(
                label="문제 번호 (쉼표로 구분)",
                placeholder="예: 1000,1001,1002",
                default=problem_ids_str,
                max_length=500,
                required=False
            )
            self.add_item(self.problems_input)
            
            # 최소 solve 수
            min_solved = self.config.get('min_solved', 1)
            self.min_solved_input = discord.ui.TextInput(
                label="최소 해결 수",
                placeholder="예: 1",
                default=str(min_solved),
                max_length=10,
                required=False
            )
            self.add_item(self.min_solved_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        from common.utils import load_data, save_data
        data = load_data()
        
        # 과제 찾기
        assignment = data['studies'][self.study_name]['assignments'][self.assignment_id]
        config = assignment.get('config', {})
        
        # 이름 수정
        if self.name_input.value.strip():
            assignment['name'] = self.name_input.value.strip()
        
        # 타입별 수정
        if self.assignment_type == '블로그':
            if self.count_input.value.strip():
                try:
                    config['count'] = int(self.count_input.value.strip())
                except ValueError:
                    await interaction.response.send_message("❌ 개수는 숫자여야 합니다.", ephemeral=True)
                    return
        
        elif self.assignment_type == '문제풀이':
            # 시작일
            if self.start_input.value.strip():
                start_dt = parse_datetime(self.start_input.value.strip())
                if start_dt:
                    config['start_date'] = start_dt.isoformat()
                else:
                    await interaction.response.send_message("❌ 시작일 형식이 올바르지 않습니다.", ephemeral=True)
                    return
            
            # 마감일
            if self.deadline_input.value.strip():
                deadline_dt = parse_datetime(self.deadline_input.value.strip())
                if deadline_dt:
                    config['deadline'] = deadline_dt.isoformat()
                    if config.get('start_date'):
                        start_dt = datetime.fromisoformat(config['start_date'])
                        config['deadline_days'] = (deadline_dt - start_dt).days
                else:
                    await interaction.response.send_message("❌ 마감일 형식이 올바르지 않습니다.", ephemeral=True)
                    return
            
            # 최소 티어
            if self.tier_input.value.strip():
                from common.boj_utils import tier_to_number
                tier_num = tier_to_number(self.tier_input.value.strip())
                if tier_num is not None:
                    config['min_tier'] = tier_num
                else:
                    await interaction.response.send_message("❌ 티어 형식이 올바르지 않습니다. (예: G2 또는 Gold I)", ephemeral=True)
                    return
            else:
                config['min_tier'] = None
        
        elif self.assignment_type == '모의테스트':
            # 시작일
            if self.start_input.value.strip():
                start_dt = parse_datetime(self.start_input.value.strip())
                if start_dt:
                    config['start_date'] = start_dt.isoformat()
                else:
                    await interaction.response.send_message("❌ 시작일 형식이 올바르지 않습니다.", ephemeral=True)
                    return
            
            # 마감일
            if self.deadline_input.value.strip():
                deadline_dt = parse_datetime(self.deadline_input.value.strip())
                if deadline_dt:
                    config['deadline'] = deadline_dt.isoformat()
                else:
                    await interaction.response.send_message("❌ 마감일 형식이 올바르지 않습니다.", ephemeral=True)
                    return
            
            # 문제 번호
            if self.problems_input.value.strip():
                try:
                    problem_ids = [int(p.strip()) for p in self.problems_input.value.strip().split(',') if p.strip()]
                    if problem_ids:
                        config['problem_ids'] = problem_ids
                except ValueError:
                    await interaction.response.send_message("❌ 문제 번호는 숫자여야 합니다. (예: 1000,1001,1002)", ephemeral=True)
                    return
            
            # 최소 solve 수
            if self.min_solved_input.value.strip():
                try:
                    config['min_solved'] = int(self.min_solved_input.value.strip())
                except ValueError:
                    await interaction.response.send_message("❌ 최소 해결 수는 숫자여야 합니다.", ephemeral=True)
                    return
        
        assignment['config'] = config
        save_data(data)
        
        await interaction.response.send_message(f"✅ 과제 '{assignment.get('name', self.assignment_id)}'이 수정되었습니다!", ephemeral=False)


class AssignmentDeleteView(discord.ui.View):
    """과제 삭제 Select Menu"""
    
    def __init__(self, assignments, author):
        super().__init__(timeout=300)
        self.assignments = assignments
        self.author = author
        
        # Select Menu 옵션 생성 (최대 25개)
        options = []
        for i, assignment in enumerate(assignments[:25]):
            label = assignment['name'][:100]  # 최대 100자
            description = f"{assignment['type']} - {assignment['study']}"[:100]
            options.append(discord.SelectOption(
                label=label,
                description=description,
                value=assignment['id']
            ))
        
        self.select = discord.ui.Select(
            placeholder="삭제할 과제를 선택하세요...",
            options=options
        )
        self.select.callback = self.on_select
        self.add_item(self.select)
    
    async def on_select(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 메뉴는 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        assignment_id = self.select.values[0]
        assignment = next((a for a in self.assignments if a['id'] == assignment_id), None)
        
        if not assignment:
            await interaction.response.send_message("❌ 과제를 찾을 수 없습니다.", ephemeral=True)
            return
        
        # 확인 버튼과 함께 표시
        confirm_view = ConfirmDeleteView(assignment_id, assignment['name'], self.author)
        embed = discord.Embed(
            title="⚠️ 과제 삭제 확인",
            description=f"**과제:** {assignment['name']}\n**종류:** {assignment['type']}\n**그룹:** {assignment['study']}\n\n정말 삭제하시겠습니까?",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)


class ConfirmDeleteView(discord.ui.View):
    """삭제 확인 버튼"""
    
    def __init__(self, assignment_id, assignment_name, author):
        super().__init__(timeout=300)
        self.assignment_id = assignment_id
        self.assignment_name = assignment_name
        self.author = author
    
    @discord.ui.button(label='✅ 삭제', style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        from common.utils import load_data, save_data
        data = load_data()
        
        # 과제 찾기 및 삭제
        deleted = False
        for study, study_data in data.get('studies', {}).items():
            if self.assignment_id in study_data.get('assignments', {}):
                del study_data['assignments'][self.assignment_id]
                deleted = True
                break
        
        if deleted:
            # DB에서도 삭제
            from common.database import delete_assignment
            delete_assignment(self.assignment_id)
            
            save_data(data)
            await interaction.response.edit_message(
                content=f"✅ 과제 '{self.assignment_name}'이 삭제되었습니다.",
                embed=None,
                view=None
            )
        else:
            await interaction.response.send_message("❌ 과제를 찾을 수 없습니다.", ephemeral=True)
    
    @discord.ui.button(label='❌ 취소', style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="❌ 삭제가 취소되었습니다.",
            embed=None,
            view=None
        )


def setup_commands(bot, assignment_group):
    """setup 함수 내에서 호출할 명령어 등록 함수"""

    @assignment_group.command(name='목록')
    async def assignment_list(ctx, study_name: str):
        """과제 목록 확인
        
        등록된 과제 목록을 확인합니다. 그룹 이름을 지정해야 합니다.
        
        사용법: /과제 목록 <그룹이름>
        
        예시:
        - /과제 목록 14기-기초
        
        파라미터:
        - study_name: 그룹 이름 (필수, Discord 역할 이름)
        """
        data = load_data()
        studies = data.get('studies', {})
        
        # 특정 그룹의 과제만 표시
        if study_name not in studies:
            await ctx.send(f"❌ '{study_name}' 그룹을 찾을 수 없습니다.")
            return
        
        assignments = studies[study_name].get('assignments', {})
        if not assignments:
            await ctx.send(f"❌ '{study_name}' 그룹에 등록된 과제가 없습니다.")
            return
        
        embed = discord.Embed(
            title=f"📋 {study_name} 그룹 과제 목록",
            color=discord.Color.blue()
        )
        
        for assignment_id, assignment in assignments.items():
            assignment_type = assignment.get('type')
            assignment_name = assignment.get('name', assignment_id)
            
            info = f"**종류:** {assignment_type}\n"
            config = assignment.get('config', {})
            
            if assignment_type == '블로그':
                info += f"**필요 개수:** {config.get('count', 0)}개"
            elif assignment_type == '문제풀이':
                info += f"**기간:** {config.get('deadline_days', 7)}일\n"
                if config.get('min_tier'):
                    from common.boj_utils import number_to_tier_short
                    info += f"**최소 난이도:** {number_to_tier_short(config['min_tier'])}\n"
                problems = config.get('problems', [])
                if problems:
                    info += f"**문제 목록:** {', '.join(map(str, problems[:5]))}"
                    if len(problems) > 5:
                        info += f" 외 {len(problems) - 5}개"
                else:
                    info += "**문제 목록:** 자유 문제풀이"
            elif assignment_type == '모의테스트':
                problem_ids = config.get('problem_ids', [])
                if problem_ids:
                    info += f"**문제 번호:** {', '.join(map(str, problem_ids))}\n"
                    info += f"**최소 해결 수:** {config.get('min_solved', 1)}개"
                deadline = config.get('deadline')
                if deadline:
                    try:
                        deadline_dt = datetime.fromisoformat(deadline)
                        info += f"\n**마감일:** {deadline_dt.strftime('%Y-%m-%d %H:%M')}"
                    except:
                        pass
            
            embed.add_field(
                name=assignment_name,
                value=f"{info}\n**ID:** `{assignment_id}`",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @assignment_group.group(name='제출')
    async def assignment_submit_group(ctx):
        """과제 제출 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 올바른 명령어를 입력해주세요.\n"
                          "💡 사용 가능한 명령어:\n"
                          "• `/과제 제출 블로그 <링크>`\n"
                          "• `/과제 제출 문제풀이` (GUI로 그룹 선택 후 문제 번호 입력)\n"
                          "• `/과제 제출 모의테스트`")

    @assignment_submit_group.command(name='블로그')
    async def submit_blog(ctx, *, link: str):
        """블로그 링크 제출
        
        Tistory 블로그 링크를 제출합니다. 운영진이 확인할 예정입니다.
        
        사용법: /과제 제출 블로그 <링크>
        
        예시: /과제 제출 블로그 https://beans3142.tistory.com/112
        
        파라미터:
        - link: Tistory 블로그 링크 (tistory.com 도메인 포함)
        
        참고: 블로그 링크는 자동으로 검증되지 않으며, 운영진이 수동으로 확인합니다.
        """
        # Tistory 링크 검증
        if 'tistory.com' not in link:
            await ctx.send("❌ Tistory 블로그 링크만 제출 가능합니다.")
            logger.warning(f'블로그 제출 실패 (잘못된 링크): {ctx.author} - {link}')
            return
        
        data = load_data()
        user_id = str(ctx.author.id)
        
        if user_id not in data['users']:
            await ctx.send("❌ 먼저 `/유저등록` 명령어로 등록해주세요.")
            return
        
        # 중복 체크 (모든 제출 기록에서)
        all_links = []
        user_submissions = data['users'][user_id].get('submissions', {})
        for assignment_id, submissions in user_submissions.items():
            for sub in submissions:
                if isinstance(sub, dict) and sub.get('link'):
                    all_links.append(sub['link'])
        
        # tistory_links에서도 확인
        tistory_links = data['users'][user_id].get('tistory_links', [])
        for link_data in tistory_links:
            if isinstance(link_data, dict):
                all_links.append(link_data['link'])
        else:
                all_links.append(link_data)
        
        if link in all_links:
            await ctx.send("⚠️ 이미 제출된 링크입니다.")
            logger.info(f'블로그 제출 중복: {ctx.author} - {link}')
            return
        
        # 제출 저장 (과제 ID 없이 저장, 운영진이 나중에 확인)
        if 'submissions' not in data['users'][user_id]:
            data['users'][user_id]['submissions'] = {}
        
        # '블로그_일반' 키로 저장 (과제와 무관하게)
        if '블로그_일반' not in data['users'][user_id]['submissions']:
            data['users'][user_id]['submissions']['블로그_일반'] = []
        
        data['users'][user_id]['submissions']['블로그_일반'].append({
            'link': link,
            'submitted_at': datetime.now().isoformat(),
            'type': '블로그',
            'user_id': user_id,
            'username': str(ctx.author)
        })
        
        # 기존 tistory_links에도 추가 (호환성)
        if 'tistory_links' not in data['users'][user_id]:
            data['users'][user_id]['tistory_links'] = []
        data['users'][user_id]['tistory_links'].append({
            'link': link,
            'submitted_at': datetime.now().isoformat()
        })
        
        save_data(data)
        logger.info(f'블로그 제출: {ctx.author} ({user_id}) - {link}')
        await ctx.send(f"✅ 블로그 링크가 제출되었습니다!\n📝 링크: {link}\n💡 운영진이 확인할 예정입니다.")

    @assignment_submit_group.command(name='문제풀이')
    async def submit_problem(ctx):
        """문제풀이 제출 (GUI)
        
        백준에서 해결한 문제를 제출합니다. 봇이 자동으로 해결 여부를 확인합니다.
        
        사용법: /과제 제출 문제풀이
        
        참고:
        - 그룹 선택 후 문제 번호를 입력하면 됩니다.
        - 해당 그룹에 활성화된 문제풀이 과제가 있어야 합니다.
        - 백준에서 실제로 해결한 문제만 제출 가능합니다.
        - 문제 해결 여부는 백준 status 페이지에서 확인됩니다.
        """
        data = load_data()
        user_id = str(ctx.author.id)
        
        if user_id not in data['users']:
            await ctx.send("❌ 먼저 `/유저등록` 명령어로 등록해주세요.")
            return
        
        boj_handle = data['users'][user_id].get('boj_handle')
        if not boj_handle:
            await ctx.send("❌ BOJ 핸들이 등록되지 않았습니다. `/유저등록 <BOJ핸들>` 명령어로 등록해주세요.")
            return
        
        # 사용자의 역할 확인
        user_roles = [role.name for role in ctx.author.roles if role.name != '@everyone']
        if not user_roles:
            await ctx.send("❌ 그룹에 등록되어 있지 않습니다.")
            return
        
        # 활성 문제풀이 과제가 있는 그룹 찾기
        studies = data.get('studies', {})
        available_groups = []
        
        for user_role in user_roles:
            if user_role in studies:
                study_data = studies[user_role]
                assignments = study_data.get('assignments', {})
                # 활성 문제풀이 과제가 있는지 확인
                for assignment_id, assignment_info in assignments.items():
                    if assignment_info.get('type') == '문제풀이':
                        config = assignment_info.get('config', {})
                        start_date = config.get('start_date')
                        deadline = config.get('deadline')
                        is_active = True
                        now = datetime.now()
                        
                        if start_date:
                            try:
                                start_dt = datetime.fromisoformat(start_date)
                                if now < start_dt:
                                    is_active = False
                            except:
                                pass
                        
                        if deadline:
                            try:
                                deadline_dt = datetime.fromisoformat(deadline)
                                if now > deadline_dt:
                                    is_active = False
                            except:
                                pass
                        
                        if is_active:
                            group_display_name = study_data.get('group_name', user_role)
                            available_groups.append({
                                'role_name': user_role,
                                'group_name': group_display_name,
                                'assignment_id': assignment_id,
                                'assignment_name': assignment_info.get('name', assignment_id)
                            })
                            break
        
        if not available_groups:
            await ctx.send("❌ 활성화된 문제풀이 과제가 있는 그룹을 찾을 수 없습니다.")
            return
        
        # 그룹 선택 View 표시
        view = ProblemSubmitGroupSelectView(available_groups, ctx.author)
        embed = discord.Embed(
            title="📝 문제풀이 제출",
            description="제출할 그룹을 선택하세요:",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=view, ephemeral=True)


class ProblemSubmitGroupSelectView(discord.ui.View):
    """문제풀이 제출을 위한 그룹 선택 View"""
    
    def __init__(self, groups, author):
        super().__init__(timeout=300)
        self.groups = groups
        self.author = author
        
        options = []
        for group in groups[:25]:  # 최대 25개
            options.append(discord.SelectOption(
                label=group['group_name'],
                description=f"과제: {group['assignment_name']}",
                value=group['role_name']
            ))
        
        self.select = discord.ui.Select(
            placeholder="그룹을 선택하세요...",
            options=options
        )
        self.select.callback = self.on_select
        self.add_item(self.select)
    
    async def on_select(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 메뉴는 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        selected_role = self.select.values[0]
        selected_group = next((g for g in self.groups if g['role_name'] == selected_role), None)
        
        if not selected_group:
            await interaction.response.send_message("❌ 선택한 그룹을 찾을 수 없습니다.", ephemeral=True)
            return
        
        # 문제 번호 입력 Modal 표시
        modal = ProblemSubmitModal(selected_group)
        await interaction.response.send_modal(modal)


class ProblemSubmitModal(discord.ui.Modal, title="문제풀이 제출"):
    """문제 번호 입력 Modal"""
    
    def __init__(self, group_info):
        super().__init__(timeout=600)
        self.group_info = group_info
        
        self.problem_id_input = discord.ui.TextInput(
            label="문제 번호",
            placeholder="예: 1000",
            max_length=10,
            required=True
        )
        self.add_item(self.problem_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        # 문제 번호 파싱
        try:
            problem_id = int(self.problem_id_input.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ 문제 번호는 숫자여야 합니다.", ephemeral=True)
            return
        
        from common.utils import load_data, save_data
        from common.boj_utils import check_problem_solved_from_status, get_problem_tier, number_to_tier, number_to_tier_short
        from common.logger import get_logger
        
        logger = get_logger()
        data = load_data()
        user_id = str(interaction.user.id)
        
        boj_handle = data['users'][user_id].get('boj_handle')
        if not boj_handle:
            await interaction.response.send_message("❌ BOJ 핸들이 등록되지 않았습니다.", ephemeral=True)
            return
        
        role_name = self.group_info['role_name']
        assignment_id = self.group_info['assignment_id']
        
        # 활성 과제 확인
        studies = data.get('studies', {})
        study_data = studies.get(role_name, {})
        assignments = study_data.get('assignments', {})
        assignment_info = assignments.get(assignment_id)
        
        if not assignment_info:
            await interaction.response.send_message("❌ 과제를 찾을 수 없습니다.", ephemeral=True)
            return
        
        # 활성 상태 재확인
        config = assignment_info.get('config', {})
        start_date = config.get('start_date')
        deadline = config.get('deadline')
        is_active = True
        now = datetime.now()
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                if now < start_dt:
                    is_active = False
            except:
                pass
        
        if deadline:
            try:
                deadline_dt = datetime.fromisoformat(deadline)
                if now > deadline_dt:
                    is_active = False
            except:
                pass
        
        if not is_active:
            await interaction.response.send_message("❌ 해당 과제가 활성화되지 않았습니다.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # 문제 해결 여부 확인
        await interaction.followup.send(f"🔄 문제 해결 여부를 확인하는 중... ({problem_id})", ephemeral=True)
        solve_info = await check_problem_solved_from_status(boj_handle, problem_id)
        
        if not solve_info or not solve_info.get('solved'):
            await interaction.followup.send(f"❌ 문제 {problem_id}를 아직 해결하지 않았습니다.", ephemeral=True)
            logger.warning(f'문제풀이 제출 실패 (미해결): {interaction.user} ({user_id}) - 문제 {problem_id}')
            return
        
        # 제출 시간 정보 가져오기
        boj_submitted_at = solve_info.get('submitted_at')
        
        # 최근 7일 이내 해결한 문제인지 확인
        if boj_submitted_at:
            try:
                submitted_dt = datetime.fromisoformat(boj_submitted_at)
                now = datetime.now()
                days_diff = (now - submitted_dt).days
                
                if days_diff > 7:
                    await interaction.followup.send(
                        f"❌ 문제 {problem_id}는 {days_diff}일 전에 해결한 문제입니다.\n"
                        f"💡 최근 7일 이내에 해결한 문제만 제출할 수 있습니다.\n"
                        f"📅 해결일: {submitted_dt.strftime('%Y-%m-%d %H:%M')}",
                        ephemeral=True
                    )
                    logger.warning(f'문제풀이 제출 실패 (7일 초과): {interaction.user} ({user_id}) - 문제 {problem_id}, {days_diff}일 전')
                    return
            except (ValueError, TypeError) as e:
                # 시간 파싱 실패 시 경고만 하고 계속 진행 (상대 시간인 경우 등)
                logger.warning(f'제출 시간 파싱 실패: {boj_submitted_at}, 오류: {e}')
                # 상대 시간인 경우 현재 시간으로 간주하여 허용
        
        # 중복 체크
        user_submissions = data['users'][user_id].get('submissions', {})
        assignment_submissions = user_submissions.get(assignment_id, [])
        
        existing_problems = [sub.get('problem_id') for sub in assignment_submissions if isinstance(sub, dict) and sub.get('problem_id')]
        if problem_id in existing_problems:
            await interaction.followup.send("⚠️ 이미 제출된 문제입니다.", ephemeral=True)
            logger.info(f'문제풀이 제출 중복: {interaction.user} ({user_id}) - 문제 {problem_id}')
            return
        
        # 제출 저장
        if 'submissions' not in data['users'][user_id]:
            data['users'][user_id]['submissions'] = {}
        if assignment_id not in data['users'][user_id]['submissions']:
            data['users'][user_id]['submissions'][assignment_id] = []
        
        # 문제 난이도 정보도 함께 저장
        problem_tier = await get_problem_tier(problem_id)
        tier_name = None
        tier_name_short = None
        if problem_tier:
            tier_name = number_to_tier(problem_tier)
            tier_name_short = number_to_tier_short(problem_tier)
        
        data['users'][user_id]['submissions'][assignment_id].append({
            'problem_id': problem_id,
            'submitted_at': datetime.now().isoformat(),
            'boj_submitted_at': boj_submitted_at,
            'type': '문제풀이',
            'verified': True,
            'user_id': user_id,
            'username': str(interaction.user),
            'boj_handle': boj_handle,
            'tier': problem_tier,
            'tier_name': tier_name,
            'tier_name_short': tier_name_short,
            'result': solve_info.get('result')
        })
        
        save_data(data)
        group_display_name = self.group_info['group_name']
        logger.info(f'문제풀이 제출: {interaction.user} ({user_id}) - 그룹: {group_display_name}, 문제: {problem_id} (해결 확인됨)')
        
        assignment_name = assignment_info.get('name', assignment_id)
        if tier_name_short:
            await interaction.followup.send(
                f"✅ 문제 {problem_id} 제출이 완료되었습니다!\n📚 과제: {assignment_name}\n📊 난이도: {tier_name_short}",
                ephemeral=True
            )
        elif tier_name:
            await interaction.followup.send(
                f"✅ 문제 {problem_id} 제출이 완료되었습니다!\n📚 과제: {assignment_name}\n📊 난이도: {tier_name}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"✅ 문제 {problem_id} 제출이 완료되었습니다!\n📚 과제: {assignment_name}",
                ephemeral=True
            )


def setup_mocktest_command(assignment_submit_group):
    @assignment_submit_group.command(name='모의테스트')
    async def submit_mocktest(ctx, *, content: str = "완료"):
        """모의테스트 제출
        
        모의테스트 완료를 제출합니다. 연습 세션 URL이 설정된 경우 자동으로 인증됩니다.
        
        사용법: /과제 제출 모의테스트 [내용]
        
        예시:
        - /과제 제출 모의테스트
        - /과제 제출 모의테스트 완료
        
        파라미터:
        - content: 제출 내용 (선택, 기본값: "완료")
        
        참고:
        - 연습 세션 URL이 설정된 과제의 경우, 백준에서 해결한 문제 수를 자동으로 확인합니다.
        - 최소 문제 수를 만족하면 자동 인증됩니다.
        - 연습 세션 URL이 없는 경우 운영진이 수동으로 확인합니다.
        """
        data = load_data()
        user_id = str(ctx.author.id)
        
        if user_id not in data['users']:
            await ctx.send("❌ 먼저 `/유저등록` 명령어로 등록해주세요.")
            return
        
        boj_handle = data['users'][user_id].get('boj_handle')
        if not boj_handle:
            await ctx.send("❌ BOJ 핸들이 등록되지 않았습니다. `/유저등록 <BOJ핸들>` 명령어로 등록해주세요.")
            return
        
        # 사용자의 역할 확인 (그룹 확인)
        user_roles = [role.name for role in ctx.author.roles if role.name != '@everyone']
        if not user_roles:
            await ctx.send("❌ 그룹에 등록되어 있지 않습니다.")
            return
        
        # 해당 그룹의 활성 모의테스트 과제 찾기
        assignment = None
        assignment_id = None
        for role_name in user_roles:
            study_data = data.get('studies', {}).get(role_name, {})
            assignments = study_data.get('assignments', {})
            for aid, assgn in assignments.items():
                if assgn.get('type') == '모의테스트':
                    # 시작일과 마감일 확인
                    config = assgn.get('config', {})
                    start_date = config.get('start_date')
                    deadline = config.get('deadline')
                    is_active = True
                    now = datetime.now()
                    
                    if start_date:
                        try:
                            start_dt = datetime.fromisoformat(start_date)
                            if now < start_dt:
                                is_active = False
                        except:
                            pass
                    
                    if deadline:
                        try:
                            deadline_dt = datetime.fromisoformat(deadline)
                            if now > deadline_dt:
                                is_active = False
                        except:
                            pass
                    
                    if is_active:
                        assignment = assgn
                        assignment_id = aid
                        break
            if assignment_id:
                break
        
        if not assignment:
            await ctx.send("❌ 제출할 활성 모의테스트 과제를 찾을 수 없습니다.")
            return
        
        # 중복 체크
        user_submissions = data['users'][user_id].get('submissions', {}).get(assignment_id, [])
        if user_submissions:
            await ctx.send("⚠️ 이미 제출된 모의테스트입니다.")
            return
        
        # 문제 해결 확인 (자동 인증)
        config = assignment.get('config', {})
        problem_ids = config.get('problem_ids', [])
        
        if problem_ids:
            min_solved = config.get('min_solved', 1)
            await ctx.send(f"🔄 문제 해결 여부를 확인하는 중... ({len(problem_ids)}개 문제, 최소 {min_solved}개 해결 필요)")
            
            solved_problems = []
            failed_problems = []
            
            for problem_id in problem_ids:
                result = await check_problem_solved_from_status(boj_handle, problem_id)
                if result and result.get('solved', False):
                    solved_problems.append(problem_id)
                else:
                    failed_problems.append(problem_id)
            
            solved_count = len(solved_problems)
            if solved_count >= min_solved:
                # 최소 해결 수 만족 - 자동 인증
                if 'submissions' not in data['users'][user_id]:
                    data['users'][user_id]['submissions'] = {}
                if assignment_id not in data['users'][user_id]['submissions']:
                    data['users'][user_id]['submissions'][assignment_id] = []
                
                data['users'][user_id]['submissions'][assignment_id].append({
                    'content': f"자동 인증 (해결: {solved_count}/{len(problem_ids)}개, 최소 {min_solved}개 필요)",
                    'submitted_at': datetime.now().isoformat(),
                    'type': '모의테스트',
                    'problem_ids': problem_ids,
                    'solved_problems': solved_problems,
                    'verified': True
                })
                save_data(data)
                logger.info(f'모의테스트 자동 인증: {ctx.author} ({user_id}) - 해결: {solved_count}/{len(problem_ids)}개 (최소 {min_solved}개 필요)')
                
                solved_str = ', '.join(map(str, solved_problems)) if solved_problems else "없음"
                failed_str = ', '.join(map(str, failed_problems)) if failed_problems else "없음"
                
                if solved_count == len(problem_ids):
                    await ctx.send(f"✅ 모의테스트 자동 인증 완료!\n📊 해결한 문제: {solved_count}/{len(problem_ids)}개 (모두 해결!)\n✅ 해결한 문제: {solved_str}")
                else:
                    await ctx.send(f"✅ 모의테스트 자동 인증 완료!\n📊 해결한 문제: {solved_count}/{len(problem_ids)}개 (최소 {min_solved}개 필요)\n✅ 해결한 문제: {solved_str}\n❌ 미해결 문제: {failed_str}")
                return
            else:
                # 최소 해결 수 미달
                solved_str = ', '.join(map(str, solved_problems)) if solved_problems else "없음"
                failed_str = ', '.join(map(str, failed_problems)) if failed_problems else "없음"
                await ctx.send(f"❌ 최소 해결 문제 수를 만족하지 못했습니다.\n✅ 해결한 문제 ({solved_count}/{len(problem_ids)}개): {solved_str}\n❌ 미해결 문제: {failed_str}\n💡 최소 {min_solved}개 이상 해결해야 합니다.")
                return
        
        # 문제 리스트가 없는 경우 (구형식 호환)
        if 'submissions' not in data['users'][user_id]:
            data['users'][user_id]['submissions'] = {}
        if assignment_id not in data['users'][user_id]['submissions']:
            data['users'][user_id]['submissions'][assignment_id] = []
        
        data['users'][user_id]['submissions'][assignment_id].append({
            'content': content,
            'submitted_at': datetime.now().isoformat(),
            'type': '모의테스트',
            'verified': False
        })
        
        save_data(data)
        logger.info(f'모의테스트 제출: {ctx.author} ({user_id}) - {content}')
        await ctx.send(f"✅ 모의테스트 제출이 완료되었습니다!\n💡 운영진이 확인할 예정입니다.")

    @assignment_group.command(name='확인')
    async def assignment_check(ctx):
        """과제 확인 및 제출 현황
        
        자신이 속한 그룹의 모든 과제와 본인의 제출 현황을 확인합니다.
        
        사용법: /과제 확인
        
        표시되는 정보:
        - 그룹별 과제 목록
        - 각 과제의 제출 현황 (제출 완료/미제출, 진행률)
        - 과제 마감일 (문제풀이 과제의 경우)
        
        참고: 여러 그룹에 속한 경우 모든 그룹의 과제가 표시됩니다.
        """
        data = load_data()
        user_id = str(ctx.author.id)
        
        if user_id not in data['users']:
            await ctx.send("❌ 먼저 `/유저등록` 명령어로 등록해주세요.")
            return
        
        # 사용자의 역할 확인 (그룹 확인)
        user_roles = [role.name for role in ctx.author.roles if role.name != '@everyone']
        if not user_roles:
            await ctx.send("❌ 그룹에 등록되어 있지 않습니다.")
            return
        
        # 사용자의 제출 정보
        user_submissions = data['users'][user_id].get('submissions', {})
        
        # 각 그룹별로 과제 확인
        embed = discord.Embed(
            title="📋 내 과제 및 제출 현황",
            color=discord.Color.blue()
        )
        
        found_assignments = False
        
        for role_name in user_roles:
            study_data = data.get('studies', {}).get(role_name, {})
            assignments = study_data.get('assignments', {})
            
            if not assignments:
                continue
            
            found_assignments = True
            assignment_list = []
            
            for assignment_id, assignment_info in assignments.items():
                assignment_type = assignment_info.get('type')
                assignment_name = assignment_info.get('name', assignment_id)
                config = assignment_info.get('config', {})
                
                # 제출 현황 확인
                user_assignment_submissions = user_submissions.get(assignment_id, [])
                
                status_text = ""
                if assignment_type == '블로그':
                    required_count = config.get('count', 0)
                    submitted_count = len(user_assignment_submissions)
                    status_icon = "✅" if submitted_count >= required_count else f"⚠️ {submitted_count}/{required_count}"
                    status_text = f"{status_icon} 제출: {submitted_count}개 / 필요: {required_count}개"
                elif assignment_type == '문제풀이':
                    required_problems = config.get('problems', [])
                    if required_problems:
                        solved_problems = [sub.get('problem_id') for sub in user_assignment_submissions if sub.get('verified', False)]
                        solved_count = len([p for p in required_problems if p in solved_problems])
                        status_icon = "✅" if solved_count >= len(required_problems) else f"⚠️ {solved_count}/{len(required_problems)}"
                        status_text = f"{status_icon} 해결: {solved_count}개 / 필요: {len(required_problems)}개"
                    else:
                        # 자유 문제풀이
                        solved_count = len([sub for sub in user_assignment_submissions if sub.get('verified', False)])
                        status_text = f"✅ 제출: {solved_count}개"
                elif assignment_type == '모의테스트':
                    problem_ids = config.get('problem_ids', [])
                    if problem_ids:
                        # 해결한 문제 확인
                        verified_submissions = [s for s in user_assignment_submissions if s.get('verified', False)]
                        if verified_submissions:
                            solved_problems = verified_submissions[0].get('solved_problems', [])
                            solved_count = len(solved_problems)
                            status_icon = "✅" if solved_count == len(problem_ids) else f"⚠️ {solved_count}/{len(problem_ids)}"
                            status_text = f"{status_icon} 해결: {solved_count}개 / 필요: {len(problem_ids)}개"
                        else:
                            status_text = "❌ 미제출"
                    else:
                        submitted = len(user_assignment_submissions) > 0
                        status_icon = "✅" if submitted else "❌"
                        status_text = f"{status_icon} {'제출 완료' if submitted else '미제출'}"
                
                # 기간 정보 추가
                deadline_info = ""
                if assignment_type == '문제풀이':
                    deadline = assignment_info.get('deadline')
                    if deadline:
                        try:
                            deadline_dt = datetime.fromisoformat(deadline)
                            deadline_info = f"\n⏰ 마감: {deadline_dt.strftime('%Y-%m-%d %H:%M')}"
                        except:
                            pass
                
                assignment_list.append(f"**{assignment_name}** ({assignment_type})\n{status_text}{deadline_info}\n`ID: {assignment_id}`")
            
            if assignment_list:
                embed.add_field(
                    name=f"📚 {role_name}",
                    value="\n\n".join(assignment_list),
                    inline=False
                )
        
        if not found_assignments:
            await ctx.send("❌ 등록된 과제가 없습니다.")
            return
        
        await ctx.send(embed=embed)

    @assignment_group.command(name='모의테스트인증')
    @commands.has_permissions(administrator=True)
    async def verify_mocktest(ctx, assignment_id: str = None):
        """모의테스트 자동 인증 실행 (관리자 전용)
        
        모의테스트 과제의 자동 인증을 수동으로 실행합니다. 지정된 문제들의 해결 여부를 확인하여 인증합니다.
        
        사용법:
        - 모든 활성 과제: /과제 모의테스트인증
        - 특정 과제: /과제 모의테스트인증 <과제ID>
        
        예시:
        - /과제 모의테스트인증
        - /과제 모의테스트인증 14기-기초_모의테스트_20241229120000
        
        파라미터:
        - assignment_id: 인증할 과제 ID (선택, 지정하지 않으면 모든 활성 과제 인증)
        
        참고:
        - 문제 번호 리스트가 설정된 활성 과제만 인증됩니다.
        - 최소 문제 수를 만족하는 사용자만 자동 인증됩니다.
        - 일요일 11시에 자동으로 실행되지만, 수동 실행도 가능합니다.
        - 각 사용자의 BOJ 핸들이 등록되어 있어야 합니다.
        """
        data = load_data()
        
        # 모든 활성 모의테스트 과제 찾기
        mocktest_assignments = []
        for study_name, study_data in data.get('studies', {}).items():
            assignments = study_data.get('assignments', {})
            for aid, assgn in assignments.items():
                if assgn.get('type') == '모의테스트':
                    config = assgn.get('config', {})
                    problem_ids = config.get('problem_ids', [])
                    
                    if not problem_ids:
                        continue
                    
                    # 시작일과 마감일 확인
                    start_date = config.get('start_date')
                    deadline = config.get('deadline')
                    is_active = True
                    now = datetime.now()
                    
                    if start_date:
                        try:
                            start_dt = datetime.fromisoformat(start_date)
                            if now < start_dt:
                                is_active = False
                        except:
                            pass
                    
                    if deadline:
                        try:
                            deadline_dt = datetime.fromisoformat(deadline)
                            if now > deadline_dt:
                                is_active = False
                        except:
                            pass
                    
                    if is_active:
                        mocktest_assignments.append((study_name, aid, assgn))
        
        if assignment_id:
            # 특정 과제만 인증
            mocktest_assignments = [(s, a, ass) for s, a, ass in mocktest_assignments if a == assignment_id]
            if not mocktest_assignments:
                await ctx.send(f"❌ 과제 ID '{assignment_id}'를 찾을 수 없거나 활성화되지 않았습니다.")
                return
        
        if not mocktest_assignments:
            await ctx.send("❌ 인증할 활성 모의테스트 과제가 없습니다.")
            return
        
        await ctx.send(f"🔄 {len(mocktest_assignments)}개의 모의테스트 과제 인증을 시작합니다...")
        
        total_verified = 0
        for study_name, assignment_id, assignment in mocktest_assignments:
            config = assignment.get('config', {})
            problem_ids = config.get('problem_ids', [])
            min_solved = config.get('min_solved', 1)
            
            if not problem_ids:
                continue
            
            # 해당 그룹의 모든 사용자 확인
            role = discord.utils.get(ctx.guild.roles, name=study_name)
            if not role:
                continue
            
            members_with_role = [member for member in ctx.guild.members if role in member.roles]
            
            for member in members_with_role:
                user_id = str(member.id)
                if user_id not in data.get('users', {}):
                    continue
                
                boj_handle = data['users'][user_id].get('boj_handle')
                if not boj_handle:
                    continue
                
                # 문제 해결 여부 확인
                solved_problems = []
                for problem_id in problem_ids:
                    result = await check_problem_solved_from_status(boj_handle, problem_id)
                    if result and result.get('solved', False):
                        solved_problems.append(problem_id)
                
                solved_count = len(solved_problems)
                if solved_count >= min_solved:
                    # 자동 인증
                    if 'submissions' not in data['users'][user_id]:
                        data['users'][user_id]['submissions'] = {}
                    if assignment_id not in data['users'][user_id]['submissions']:
                        data['users'][user_id]['submissions'][assignment_id] = []
                    
                    # 중복 체크
                    existing = [s for s in data['users'][user_id]['submissions'][assignment_id] 
                               if s.get('verified', False)]
                    if not existing:
                        data['users'][user_id]['submissions'][assignment_id].append({
                            'content': f"자동 인증 (해결: {solved_count}/{len(problem_ids)}개)",
                            'submitted_at': datetime.now().isoformat(),
                            'type': '모의테스트',
                            'problem_ids': problem_ids,
                            'solved_problems': solved_problems,
                            'verified': True
                        })
                        total_verified += 1
        
        save_data(data)
        logger.info(f'모의테스트 자동 인증 완료: {total_verified}명 인증됨')
        await ctx.send(f"✅ 모의테스트 자동 인증 완료!\n📊 총 {total_verified}명이 인증되었습니다.")

    @bot.group(name='테스트')
    @commands.has_permissions(administrator=True)
    async def test_group(ctx):
        """테스트 명령어 그룹 (관리자 전용)"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 올바른 명령어를 입력해주세요. `/테스트 모의테스트작동확인 <유저id> <링크>`")

    @test_group.command(name='모의테스트작동확인')
    @commands.has_permissions(administrator=True)
    async def test_mocktest_verification(ctx, user_identifier: str, practice_url: str):
        """모의테스트 크롤링 작동 확인 (관리자 전용)
        
        백준 연습 세션 크롤링이 정상 작동하는지 테스트합니다.
        
        사용법: /테스트 모의테스트작동확인 <유저식별자> <연습세션URL>
        
        예시:
        - Discord ID로: /테스트 모의테스트작동확인 123456789012345678 https://www.acmicpc.net/group/practice/view/9883/122
        - BOJ 핸들로: /테스트 모의테스트작동확인 beans3142 https://www.acmicpc.net/group/practice/view/9883/122
        
        파라미터:
        - user_identifier: Discord 유저 ID 또는 BOJ 핸들
        - practice_url: 백준 연습 세션 URL (예: https://www.acmicpc.net/group/practice/view/9883/122)
        
        표시되는 정보:
        - 해당 유저의 해결한 문제 수
        - 1문제 이상 해결한 모든 유저 랭킹 (상위부터 정렬)
        - 크롤링 성공/실패 여부
        
        참고: 이 명령어는 디버깅 및 테스트용입니다.
        """
        data = load_data()
        logger.info(f'테스트 명령어 실행: {ctx.author} - user_identifier={user_identifier}, url={practice_url}')
        
        # 유저 찾기 (Discord ID 또는 BOJ 핸들로 검색)
        user_id = None
        boj_handle = None
        
        # 먼저 Discord ID로 시도
        if user_identifier in data.get('users', {}):
            user_id = user_identifier
            boj_handle = data['users'][user_id].get('boj_handle')
            logger.info(f'Discord ID로 유저 찾음: {user_id}, BOJ 핸들: {boj_handle}')
        else:
            # BOJ 핸들로 검색
            for uid, user_data in data.get('users', {}).items():
                if user_data.get('boj_handle') == user_identifier:
                    user_id = uid
                    boj_handle = user_identifier
                    logger.info(f'BOJ 핸들로 유저 찾음: Discord ID={user_id}, BOJ 핸들={boj_handle}')
                    break
        
        if not user_id:
            await ctx.send(f"❌ 유저를 찾을 수 없습니다. (입력: '{user_identifier}')\n💡 Discord 유저 ID 또는 BOJ 핸들을 입력해주세요.")
            logger.warning(f'유저를 찾을 수 없음: {user_identifier}')
            return
        
        if not boj_handle:
            await ctx.send(f"❌ 유저 ID '{user_id}'에 등록된 BOJ 핸들이 없습니다.")
            logger.warning(f'BOJ 핸들이 없음: {user_id}')
            return
        
        await ctx.send(f"🔄 연습 세션 크롤링 테스트 중...\n📝 URL: {practice_url}\n👤 Discord ID: {user_id}\n👤 BOJ 핸들: {boj_handle}")
        logger.info(f'크롤링 시작: URL={practice_url}, BOJ 핸들={boj_handle}')
        
        # 랭킹 가져오기
        ranking = await get_group_practice_ranking(practice_url)
        logger.info(f'크롤링 결과: 랭킹 데이터 {len(ranking)}개 유저')
        
        if not ranking:
            await ctx.send("❌ 랭킹 데이터를 가져올 수 없습니다. 로그인 실패 또는 URL 오류일 수 있습니다.")
            logger.error(f'랭킹 데이터 가져오기 실패: URL={practice_url}')
            return
        
        # 결과 표시
        embed = discord.Embed(
            title="🧪 모의테스트 크롤링 테스트 결과",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="연습 세션 URL",
            value=practice_url,
            inline=False
        )
        
        embed.add_field(
            name="BOJ 핸들",
            value=boj_handle,
            inline=True
        )
        
        if boj_handle in ranking:
            solved_count = ranking[boj_handle]
            embed.add_field(
                name="해결한 문제 수",
                value=f"✅ {solved_count}개",
                inline=True
            )
            embed.color = discord.Color.green()
        else:
            embed.add_field(
                name="해결한 문제 수",
                value="❌ 랭킹에서 찾을 수 없음",
                inline=True
            )
            embed.color = discord.Color.red()
        
        # 1문제 이상 해결한 모든 유저 표시
        if ranking:
            ranking_list = []
            # 1문제 이상 해결한 유저만 필터링
            solved_users = [(uid, count) for uid, count in ranking.items() if count >= 1]
            sorted_ranking = sorted(solved_users, key=lambda x: x[1], reverse=True)
            
            for i, (uid, count) in enumerate(sorted_ranking, 1):
                marker = "👤" if uid == boj_handle else "  "
                ranking_list.append(f"{marker} {i}. {uid}: {count}개")
            
            if ranking_list:
                embed.add_field(
                    name=f"랭킹 (1문제 이상 해결: 총 {len(ranking_list)}명)",
                    value="\n".join(ranking_list),
                    inline=False
                )
            else:
                embed.add_field(
                    name="랭킹",
                    value="1문제 이상 해결한 유저가 없습니다.",
                    inline=False
                )
        
        await ctx.send(embed=embed)

    @test_group.command(name='DB초기화')
    @commands.has_permissions(administrator=True)
    async def test_db_reset(ctx):
        """데이터베이스 초기화 (관리자 전용)
        
        ⚠️ **주의: 이 명령어는 모든 데이터를 삭제합니다!**
        
        삭제되는 데이터:
        - 모든 사용자 정보
        - 모든 역할 토큰
        - 모든 그룹 및 과제
        - 모든 제출 기록
        
        사용법: /테스트 DB초기화
        
        예시:
        - /테스트 DB초기화
        
        참고: 이 명령어는 되돌릴 수 없습니다. 신중하게 사용하세요.
        """
        # 확인 View 생성
        view = DBResetConfirmView(ctx.author)
        embed = discord.Embed(
            title="⚠️ 데이터베이스 초기화 확인",
            description="**이 작업은 되돌릴 수 없습니다!**\n\n"
                       "다음 데이터가 모두 삭제됩니다:\n"
                       "• 모든 사용자 정보\n"
                       "• 모든 역할 토큰\n"
                       "• 모든 그룹 및 과제\n"
                       "• 모든 제출 기록\n\n"
                       "정말 초기화하시겠습니까?",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, view=view)


class DBResetConfirmView(discord.ui.View):
    """DB 초기화 확인 버튼 View"""
    
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
    
    @discord.ui.button(label='✅ 초기화', style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        try:
            from common.database import reset_database
            reset_database()
            
            await interaction.response.edit_message(
                content="✅ 데이터베이스가 초기화되었습니다.\n💡 모든 데이터가 삭제되고 테이블이 재생성되었습니다.",
                embed=None,
                view=None
            )
            logger.warning(f'데이터베이스 초기화: {interaction.user} ({interaction.user.id})')
        except Exception as e:
            await interaction.response.send_message(f"❌ 데이터베이스 초기화 중 오류가 발생했습니다: {str(e)}", ephemeral=True)
            logger.error(f'DB 초기화 오류: {e}')
    
    @discord.ui.button(label='❌ 취소', style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content="❌ 데이터베이스 초기화가 취소되었습니다.",
            embed=None,
            view=None
        )

# 전역 bot 변수 (스케줄러에서 사용)
_bot_instance = None

@tasks.loop(time=time(hour=11, minute=0))  # 매일 11시
async def auto_verify_mocktest():
    """일요일 11시에 모의테스트 자동 인증 (종료 시간 확인)"""
    # 일요일 확인 (0 = 월요일, 6 = 일요일)
    if datetime.now().weekday() != 6:  # 일요일이 아니면 스킵
        return
    
    if not _bot_instance:
        return
    
    from common.utils import load_data, save_data
    
    # 봇이 준비될 때까지 대기
    await _bot_instance.wait_until_ready()
    
    data = load_data()
    
    # 모든 활성 모의테스트 과제 찾기 (종료 시간이 지난 과제만)
    for study_name, study_data in data.get('studies', {}).items():
        assignments = study_data.get('assignments', {})
        for assignment_id, assignment in assignments.items():
            if assignment.get('type') == '모의테스트':
                config = assignment.get('config', {})
                problem_ids = config.get('problem_ids', [])
                
                if not problem_ids:
                    continue
                
                # 시작일과 마감일 확인
                start_date = config.get('start_date')
                deadline = config.get('deadline')
                now = datetime.now()
                
                # 종료 시간이 지났는지 확인
                if not deadline:
                    continue
                
                try:
                    deadline_dt = datetime.fromisoformat(deadline)
                    # 종료 시간이 지나지 않았으면 스킵
                    if now < deadline_dt:
                        continue
                except:
                    continue
                
                min_solved = config.get('min_solved', 1)
                
                # 모든 서버에서 해당 그룹 찾기
                for guild in _bot_instance.guilds:
                    role = discord.utils.get(guild.roles, name=study_name)
                    if not role:
                        continue
                    
                    members_with_role = [member for member in guild.members if role in member.roles]
                    
                    for member in members_with_role:
                        user_id = str(member.id)
                        if user_id not in data.get('users', {}):
                            continue
                        
                        boj_handle = data['users'][user_id].get('boj_handle')
                        if not boj_handle:
                            continue
                        
                        # 문제 해결 여부 확인
                        solved_problems = []
                        for problem_id in problem_ids:
                            result = await check_problem_solved_from_status(boj_handle, problem_id)
                            if result and result.get('solved', False):
                                solved_problems.append(problem_id)
                        
                        solved_count = len(solved_problems)
                        if solved_count >= min_solved:
                            # 자동 인증
                            if 'submissions' not in data['users'][user_id]:
                                data['users'][user_id]['submissions'] = {}
                            if assignment_id not in data['users'][user_id]['submissions']:
                                data['users'][user_id]['submissions'][assignment_id] = []
                            
                            # 중복 체크
                            existing = [s for s in data['users'][user_id]['submissions'][assignment_id] 
                                       if s.get('verified', False)]
                            if not existing:
                                data['users'][user_id]['submissions'][assignment_id].append({
                                    'content': f"자동 인증 (해결: {solved_count}/{len(problem_ids)}개)",
                                    'submitted_at': datetime.now().isoformat(),
                                    'type': '모의테스트',
                                    'problem_ids': problem_ids,
                                    'solved_problems': solved_problems,
                                    'verified': True
                                })
                
                save_data(data)
                logger.info(f'모의테스트 자동 인증 완료: {study_name} - {assignment_id}')

