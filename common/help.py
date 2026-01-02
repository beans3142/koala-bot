"""
도움말 명령어
"""
import discord
from discord.ext import commands

def setup(bot):
    """봇에 명령어 등록"""
    
    @bot.command(name='도움말')
    async def help_command(ctx):
        """도움말"""
        await show_help(ctx)

    @bot.command(name='명령어')
    async def command_help(ctx):
        """명령어 도움말"""
        await show_help(ctx)

    async def show_help(ctx):
        """도움말 표시 - 상세한 설명과 예시 포함"""
        is_admin = ctx.author.guild_permissions.administrator if ctx.guild else False
        
        # 페이지별로 도움말 구성
        pages = []
        
        # 페이지 번호 계산
        total_pages = 4  # 기본: 유저, 역할등록, 과제제출, 과제확인
        if is_admin:
            total_pages = 9  # 관리자: + 역할관리, 과제관리, 그룹관리, 채널관리
        
        # 페이지 1: 유저 관리
        embed1 = discord.Embed(
            title="🤖 알고리즘 동아리 봇 도움말",
            description=f"**페이지 1/{total_pages}** - 👤 유저 관리",
            color=discord.Color.blue()
        )
        embed1.add_field(
            name="`/유저등록 <BOJ핸들>`",
            value="**설명:** 봇에 자신을 등록합니다. BOJ 핸들은 필수입니다.\n\n"
                  "**파라미터:**\n"
                  "• `BOJ핸들` (필수): 백준 온라인 저지 사용자 이름\n\n"
                  "**예시:**\n"
                  "• `/유저등록 beans3142`\n\n"
                  "**참고:**\n"
                  "• BOJ 핸들은 문제풀이 과제 제출 시 자동으로 해결 여부를 확인하는 데 필요합니다\n"
                  "• 존재하지 않는 BOJ 핸들은 등록할 수 없습니다",
            inline=False
        )
        embed1.add_field(
            name="`/내정보`",
            value="**설명:** 자신의 등록된 정보를 확인합니다. BOJ 핸들, 제출한 링크 수, 등록된 역할 등을 확인할 수 있습니다.\n\n"
                  "**예시:**\n"
                  "• `/내정보`\n\n"
                  "**표시되는 정보:**\n"
                  "• 백준 핸들 (등록 여부)\n"
                  "• 제출한 블로그 링크 수\n"
                  "• 등록된 역할 목록",
            inline=False
        )
        pages.append(embed1)
        
        # 페이지 2: 역할 관리 (일반 사용자)
        embed2 = discord.Embed(
            title="🤖 알고리즘 동아리 봇 도움말",
            description=f"**페이지 2/{total_pages}** - 🎭 역할 등록",
            color=discord.Color.blue()
        )
        embed2.add_field(
            name="`/역할 등록`",
            value="**설명:** 관리자가 제공한 토큰을 사용하여 역할을 받습니다.\n\n"
                  "**사용법:**\n"
                  "1. `/역할 등록` 명령어 실행\n"
                  "2. '등록 폼 열기' 버튼 클릭\n"
                  "3. Modal에서 토큰 입력 (필수)\n"
                  "4. BOJ 핸들 입력 (필수)\n\n"
                  "**예시:**\n"
                  "• `/역할 등록` → 버튼 클릭 → 토큰과 BOJ 핸들 입력\n\n"
                  "**참고:**\n"
                  "• 토큰은 한 번만 사용 가능합니다\n"
                  "• BOJ 핸들은 문제풀이 과제 제출 시 자동 확인에 필요합니다",
            inline=False
        )
        pages.append(embed2)
        
        # 페이지 5 (일반) / 6 (관리자): 역할 관리 (관리자)
        if is_admin:
            embed_role_admin = discord.Embed(
                title="🤖 알고리즘 동아리 봇 도움말",
                description=f"**페이지 6/{total_pages}** - 🎭 역할 관리 (관리자 전용)",
                color=discord.Color.blue()
            )
            embed_role_admin.add_field(
                name="`/역할 생성 <이름>`",
                value="**설명:** 새로운 Discord 역할을 생성하고 등록 토큰을 생성합니다.\n\n"
                      "**파라미터:**\n"
                      "• `이름` (필수): 생성할 역할 이름\n\n"
                      "**예시:**\n"
                      "• `/역할 생성 14기-기초`\n\n"
                      "**동작:**\n"
                      "• Discord 역할 생성 (랜덤 색상)\n"
                      "• 등록 토큰 생성 및 DM 전송",
                inline=False
            )
            embed_role_admin.add_field(
                name="`/역할 토큰 <이름>`",
                value="**설명:** 기존 역할의 등록 토큰을 확인합니다.\n\n"
                      "**파라미터:**\n"
                      "• `이름` (필수): 역할 이름\n\n"
                      "**예시:**\n"
                      "• `/역할 토큰 14기-기초`",
                inline=False
            )
            embed_role_admin.add_field(
                name="`/역할 리스트`",
                value="**설명:** 봇에 등록된 모든 역할과 토큰 목록을 확인합니다.\n\n"
                      "**예시:**\n"
                      "• `/역할 리스트`",
                inline=False
            )
            embed_role_admin.add_field(
                name="`/역할 삭제 <이름>`",
                value="**설명:** Discord 역할과 봇에 등록된 역할 정보를 삭제합니다.\n\n"
                      "**파라미터:**\n"
                      "• `이름` (필수): 삭제할 역할 이름\n\n"
                      "**예시:**\n"
                      "• `/역할 삭제 14기-기초`\n\n"
                      "**주의:** 봇 역할보다 위에 있는 역할은 삭제할 수 없습니다.",
                inline=False
            )
            pages.append(embed_role_admin)
        
        # 페이지 3: 과제 제출
        embed3 = discord.Embed(
            title="🤖 알고리즘 동아리 봇 도움말",
            description=f"**페이지 3/{total_pages}** - 📝 과제 제출",
            color=discord.Color.blue()
        )
        embed3.add_field(
            name="`/과제 제출 블로그 <링크>`",
            value="**설명:** Tistory 블로그 링크를 제출합니다. 운영진이 수동으로 확인합니다.\n\n"
                  "**파라미터:**\n"
                  "• `링크` (필수): Tistory 블로그 포스트 URL\n\n"
                  "**예시:**\n"
                  "• `/과제 제출 블로그 https://beans3142.tistory.com/112`\n\n"
                  "**참고:**\n"
                  "• Tistory 도메인만 제출 가능합니다\n"
                  "• 중복 제출은 불가능합니다\n"
                  "• 자동 검증 없이 운영진이 확인합니다",
            inline=False
        )
        embed3.add_field(
            name="`/과제 제출 문제풀이 <그룹명> <문제번호>`",
            value="**설명:** 백준에서 해결한 문제를 제출합니다. 봇이 자동으로 해결 여부를 확인합니다.\n\n"
                  "**파라미터:**\n"
                  "• `그룹명` (필수): 속한 그룹 이름 (Discord 역할 이름)\n"
                  "• `문제번호` (필수): 백준 문제 번호\n\n"
                  "**예시:**\n"
                  "• `/과제 제출 문제풀이 14기-기초 1000`\n\n"
                  "**동작:**\n"
                  "• 해당 그룹의 활성 문제풀이 과제 확인\n"
                  "• 백준 status 페이지에서 해결 여부 자동 확인\n"
                  "• 해결한 경우에만 제출 성공\n\n"
                  "**참고:**\n"
                  "• BOJ 핸들이 등록되어 있어야 합니다 (`/유저등록 <BOJ핸들>`)\n"
                  "• 해당 그룹에 활성화된 문제풀이 과제가 있어야 합니다",
            inline=False
        )
        embed3.add_field(
            name="`/과제 제출 모의테스트`",
            value="**설명:** 모의테스트 완료를 제출합니다. 지정된 문제들의 해결 여부를 자동으로 확인합니다.\n\n"
                  "**예시:**\n"
                  "• `/과제 제출 모의테스트`\n\n"
                  "**동작:**\n"
                  "• 자신이 속한 그룹의 활성 모의테스트 과제 확인\n"
                  "• 지정된 문제 번호들의 해결 여부 확인\n"
                  "• 최소 해결 문제 수를 만족하면 자동 인증\n\n"
                  "**참고:**\n"
                  "• BOJ 핸들이 등록되어 있어야 합니다\n"
                  "• 모든 문제를 해결하지 않아도 최소 해결 수를 만족하면 인증됩니다",
            inline=False
        )
        pages.append(embed3)
        
        # 페이지 4: 과제 확인
        embed4 = discord.Embed(
            title="🤖 알고리즘 동아리 봇 도움말",
            description=f"**페이지 4/{total_pages}** - 📋 과제 확인",
            color=discord.Color.blue()
        )
        embed4.add_field(
            name="`/과제 확인`",
            value="**설명:** 자신이 속한 그룹의 모든 과제와 본인의 제출 현황을 확인합니다.\n\n"
                  "**예시:**\n"
                  "• `/과제 확인`\n\n"
                  "**표시되는 정보:**\n"
                  "• 그룹별 과제 목록\n"
                  "• 각 과제의 제출 현황 (제출 완료/미제출, 진행률)\n"
                  "• 과제 마감일\n\n"
                  "**참고:** 여러 그룹에 속한 경우 모든 그룹의 과제가 표시됩니다.",
            inline=False
        )
        embed4.add_field(
            name="`/과제 목록 <그룹이름>`",
            value="**설명:** 등록된 과제 목록을 확인합니다. 그룹 이름을 지정해야 합니다.\n\n"
                  "**파라미터:**\n"
                  "• `그룹이름` (필수): 확인할 그룹 이름 (Discord 역할 이름)\n\n"
                  "**예시:**\n"
                  "• `/과제 목록 14기-기초`\n\n"
                  "**표시되는 정보:**\n"
                  "• 과제 이름 및 종류\n"
                  "• 과제 설정 (개수, 기간, 난이도 등)\n"
                  "• 과제 ID",
            inline=False
        )
        pages.append(embed4)
        
        # 페이지 7 (관리자): 과제 관리
        if is_admin:
            embed_assignment_admin = discord.Embed(
                title="🤖 알고리즘 동아리 봇 도움말",
                description=f"**페이지 7/{total_pages}** - 📝 과제 관리 (관리자 전용)",
                color=discord.Color.blue()
            )
            embed_assignment_admin.add_field(
                name="`/과제 생성 <그룹이름>`",
                value="**설명:** 새로운 과제를 생성합니다. GUI 방식으로 단계별로 입력합니다.\n\n"
                      "**사용법:**\n"
                      "1. `/과제 생성 <그룹이름>` 실행\n"
                      "2. Select Menu에서 과제 유형 선택\n"
                      "3. Modal에서 과제 정보 입력\n\n"
                      "**과제 유형:**\n"
                      "• 블로그: 과제 이름, 필요 개수\n"
                      "• 문제풀이: 과제 이름, 시작일, 마감일, 최소 티어\n"
                      "• 모의테스트: 과제 이름, 시작일, 마감일, 문제 번호, 최소 해결 수\n\n"
                      "**시간 형식:**\n"
                      "• `2024-12-31 15:20`, `7일`, `3시간`, `15:20`",
                inline=False
            )
            embed_assignment_admin.add_field(
                name="`/과제 수정`",
                value="**설명:** 기존 과제의 설정을 수정합니다.\n\n"
                      "**사용법:**\n"
                      "1. `/과제 수정` 실행\n"
                      "2. Select Menu에서 수정할 과제 선택\n"
                      "3. Modal에서 수정할 정보 입력\n\n"
                      "**수정 가능한 항목:**\n"
                      "• 과제 이름, 필요 개수, 시작일, 마감일, 최소 티어, 문제 번호 등\n\n"
                      "**참고:** 빈 필드는 기존 값이 유지됩니다.",
                inline=False
            )
            embed_assignment_admin.add_field(
                name="`/과제 삭제`",
                value="**설명:** 지정한 과제를 삭제합니다.\n\n"
                      "**사용법:**\n"
                      "1. `/과제 삭제` 실행\n"
                      "2. Select Menu에서 삭제할 과제 선택\n"
                      "3. 확인 버튼 클릭\n\n"
                      "**주의:** 삭제된 과제의 제출 기록도 함께 삭제됩니다.",
                inline=False
            )
            embed_assignment_admin.add_field(
                name="`/과제 모의테스트인증 [과제ID]`",
                value="**설명:** 모의테스트 과제의 자동 인증을 수동으로 실행합니다.\n\n"
                      "**파라미터:**\n"
                      "• `과제ID` (선택): 특정 과제만 인증\n\n"
                      "**예시:**\n"
                      "• `/과제 모의테스트인증` - 모든 활성 과제\n"
                      "• `/과제 모의테스트인증 14기-기초_모의테스트_20241229120000`\n\n"
                      "**참고:** 일요일 11시에 자동 실행됩니다.",
                inline=False
            )
            pages.append(embed_assignment_admin)
        
        # 페이지 5 (일반) / 8 (관리자): 그룹 관리
        if is_admin:
            embed5 = discord.Embed(
                title="🤖 알고리즘 동아리 봇 도움말",
                description=f"**페이지 8/{total_pages}** - 📁 그룹 관리 (관리자 전용)",
                color=discord.Color.blue()
            )
            embed5.add_field(
                name="`/그룹 생성 <이름> <역할>` (관리자 전용)",
                value="**설명:** 그룹 카테고리와 채널을 자동으로 생성합니다. 지정된 역할만 접근할 수 있습니다.\n\n"
                      "**파라미터:**\n"
                      "• `이름` (필수): 생성할 그룹 이름 (카테고리 이름)\n"
                      "• `역할` (필수): 접근 권한을 부여할 Discord 역할 이름\n\n"
                      "**예시:**\n"
                      "• `/그룹 생성 14기-기초 14기-기초`\n\n"
                      "**생성되는 채널:**\n"
                      "• 텍스트 채널: 공지 (Announcement), 채팅, 자유, 해설, 과제제출\n"
                      "• 음성 채널: 자유1, 자유2, 자유3\n\n"
                      "**참고:** 지정된 역할만 해당 채널들을 볼 수 있습니다.",
                inline=False
            )
            embed5.add_field(
                name="`/그룹 목록` (관리자 전용)",
                value="**설명:** 봇에 등록된 모든 그룹 목록을 확인합니다.\n\n"
                      "**예시:**\n"
                      "• `/그룹 목록`\n\n"
                      "**표시되는 정보:**\n"
                      "• 그룹 이름\n"
                      "• 연결된 역할 이름\n"
                      "• 생성일",
                inline=False
            )
            embed5.add_field(
                name="`/그룹 수정 <역할이름> <새그룹명>` (관리자 전용)",
                value="**설명:** 그룹의 이름을 수정합니다. 카테고리 이름은 수동으로 변경해야 합니다.\n\n"
                      "**파라미터:**\n"
                      "• `역할이름` (필수): 그룹에 연결된 역할 이름\n"
                      "• `새그룹명` (필수): 새로운 그룹 이름\n\n"
                      "**예시:**\n"
                      "• `/그룹 수정 14기-기초 15기-기초`",
                inline=False
            )
            embed5.add_field(
                name="`/그룹 삭제 <역할이름>` (관리자 전용)",
                value="**설명:** 그룹 정보를 데이터베이스에서 삭제합니다. 카테고리와 채널은 수동으로 삭제해야 합니다.\n\n"
                      "**파라미터:**\n"
                      "• `역할이름` (필수): 삭제할 그룹의 역할 이름\n\n"
                      "**예시:**\n"
                      "• `/그룹 삭제 14기-기초`\n\n"
                      "**참고:** 카테고리와 채널은 Discord에서 수동으로 삭제해야 합니다.",
                inline=False
            )
            embed5.add_field(
                name="`/그룹 제출현황 [역할이름]` (관리자 전용)",
                value="**설명:** 특정 그룹의 모든 과제에 대한 제출 현황을 확인합니다.\n\n"
                      "**파라미터:**\n"
                      "• `역할이름` (선택): 확인할 그룹의 역할 이름 (지정하지 않으면 모든 그룹)\n\n"
                      "**예시:**\n"
                      "• `/그룹 제출현황 14기-기초`\n\n"
                      "**표시되는 정보:**\n"
                      "• 그룹 내 모든 과제 목록\n"
                      "• 각 과제별 제출자 수 및 제출 현황",
                inline=False
            )
            pages.append(embed5)
        
        # 페이지 6 (일반) / 9 (관리자): 채널 관리 및 테스트
        if is_admin:
            embed6 = discord.Embed(
                title="🤖 알고리즘 동아리 봇 도움말",
                description=f"**페이지 9/{total_pages}** - 📢 채널 관리 및 🧪 테스트 (관리자 전용)",
                color=discord.Color.blue()
            )
            embed6.add_field(
                name="`/채널 공지 <채널이름> [역할이름]` (관리자 전용)",
                value="**설명:** Announcement 채널을 생성합니다. 지정된 역할만 접근할 수 있습니다.\n\n"
                      "**파라미터:**\n"
                      "• `채널이름` (필수): 생성할 채널 이름\n"
                      "• `역할이름` (선택): 접근 권한을 부여할 역할 (지정하지 않으면 @everyone)\n\n"
                      "**예시:**\n"
                      "• `/채널 공지 전체공지`\n"
                      "• `/채널 공지 그룹공지 14기-기초`",
                inline=False
            )
            embed6.add_field(
                name="`/채널 포럼 <채널이름> [역할이름]` (관리자 전용)",
                value="**설명:** Forum 채널을 생성합니다. 지정된 역할만 접근할 수 있습니다.\n\n"
                      "**파라미터:**\n"
                      "• `채널이름` (필수): 생성할 채널 이름\n"
                      "• `역할이름` (선택): 접근 권한을 부여할 역할\n\n"
                      "**예시:**\n"
                      "• `/채널 포럼 질문방`\n"
                      "• `/채널 포럼 질문방 14기-기초`",
                inline=False
            )
            embed6.add_field(
                name="`/테스트 모의테스트작동확인 <유저식별자> <연습세션URL>` (관리자 전용)",
                value="**설명:** 모의테스트 크롤링 기능이 정상 작동하는지 테스트합니다.\n\n"
                      "**파라미터:**\n"
                      "• `유저식별자` (필수): Discord 유저 ID 또는 BOJ 핸들\n"
                      "• `연습세션URL` (필수): 백준 연습 세션 URL\n\n"
                      "**예시:**\n"
                      "• `/테스트 모의테스트작동확인 beans3142 https://www.acmicpc.net/group/practice/view/9883/122`\n\n"
                      "**표시되는 정보:**\n"
                      "• 해당 유저의 해결한 문제 수\n"
                      "• 1문제 이상 해결한 모든 유저 랭킹\n\n"
                      "**참고:** 이 명령어는 디버깅 및 테스트용입니다.",
                inline=False
            )
            pages.append(embed6)
        
        # 페이지가 없으면 (일반 사용자이고 관리자 전용 페이지만 있는 경우)
        if not pages:
            embed = discord.Embed(
                title="🤖 알고리즘 동아리 봇 도움말",
                description="사용 가능한 명령어가 없습니다.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # 페이징 버튼 추가
        view = HelpPaginationView(pages, ctx.author)
        message = await ctx.send(embed=pages[0], view=view)
        view.message = message


class HelpPaginationView(discord.ui.View):
    """도움말 페이징 뷰"""
    
    def __init__(self, pages, author):
        super().__init__(timeout=300)
        self.pages = pages
        self.author = author
        self.current_page = 0
        self.message = None
        
        # 첫 페이지면 이전 버튼 비활성화
        if len(pages) <= 1:
            self.prev_button.disabled = True
            self.next_button.disabled = True
    
    @discord.ui.button(label='◀ 이전', style=discord.ButtonStyle.primary, disabled=True)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
            
            # 첫 페이지면 이전 버튼 비활성화
            if self.current_page == 0:
                self.prev_button.disabled = True
            if self.next_button.disabled:
                self.next_button.disabled = False
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label='다음 ▶', style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
            
            # 마지막 페이지면 다음 버튼 비활성화
            if self.current_page == len(self.pages) - 1:
                self.next_button.disabled = True
            if self.prev_button.disabled:
                self.prev_button.disabled = False
        else:
            await interaction.response.defer()
    
    async def on_timeout(self):
        """타임아웃 시 버튼 비활성화"""
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except:
                pass
