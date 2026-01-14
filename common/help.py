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
        total_pages = 2  # 기본: 유저 관리, 역할 등록
        if is_admin:
            total_pages = 5  # 관리자: + 역할 관리, 그룹 관리, 문제풀이 현황
        
        # 페이지 1: 유저 관리
        embed1 = discord.Embed(
            title="🤖 알고리즘 동아리 봇 도움말",
            description=f"**페이지 1/{total_pages}** - 👤 유저 관리",
            color=discord.Color.blue()
        )
        embed1.add_field(
            name="`/내정보`",
            value="**설명:** 자신의 등록된 정보를 확인합니다.\n\n"
                  "**사용법:**\n"
                  "• `/내정보`\n\n"
                  "**예시:**\n"
                  "```\n/내정보\n```\n\n"
                  "**표시되는 정보:**\n"
                  "• **백준 핸들**: 등록된 백준 온라인 저지 닉네임 (백준 닉네임)\n"
                  "• **참여 그룹**: 현재 참여 중인 그룹 목록 (그룹 이름 + 역할 이름)\n"
                  "  - 예: `21기-기초 (21기-기초)`, `21기-실전 (21기-실전)`\n"
                  "• **제출한 링크 수**: Tistory 블로그 링크 제출 횟수\n\n"
                  "**참고:**\n"
                  "• 역할을 등록하면 자동으로 정보가 저장됩니다\n"
                  "• 여러 그룹에 참여한 경우 모든 그룹이 표시됩니다",
            inline=False
        )
        pages.append(embed1)
        
        # 페이지 2: 역할 등록 (일반 사용자)
        embed2 = discord.Embed(
            title="🤖 알고리즘 동아리 봇 도움말",
            description=f"**페이지 2/{total_pages}** - 🎭 역할 등록",
            color=discord.Color.blue()
        )
        embed2.add_field(
            name="`/역할 등록`",
            value="**설명:** 관리자가 제공한 토큰을 사용하여 역할을 받고 BOJ 핸들을 등록합니다.\n\n"
                  "**사용법:**\n"
                  "1. `/역할 등록` 명령어 실행\n"
                  "2. 나타나는 '📝 등록 폼 열기' 버튼 클릭\n"
                  "3. Modal 창에서 다음 정보 입력:\n"
                  "   - **토큰**: 관리자가 제공한 역할 등록 토큰 (필수)\n"
                  "   - **BOJ 핸들**: 백준 온라인 저지 사용자 이름 (필수)\n"
                  "4. 제출 버튼 클릭\n\n"
                  "**예시:**\n"
                  "```\n/역할 등록\n```\n"
                  "→ 버튼 클릭 → Modal에서 입력:\n"
                  "  - 토큰: `abc123def456`\n"
                  "  - BOJ 핸들: `beans3142`\n\n"
                  "**동작 과정:**\n"
                  "1. 토큰 검증 (유효한 토큰인지 확인)\n"
                  "2. BOJ 핸들 검증 (백준에 존재하는 사용자인지 확인)\n"
                  "3. Discord 역할 부여 (서버에서 해당 역할 자동 부여)\n"
                  "4. 정보 저장 (DB에 사용자 정보 및 역할 정보 저장)\n\n"
                  "**주의사항:**\n"
                  "• 토큰은 한 번만 사용 가능합니다 (재사용 불가)\n"
                  "• BOJ 핸들은 문제풀이 현황 조회에 필요합니다\n"
                  "• 이미 역할을 가지고 있으면 중복 등록되지 않습니다\n"
                  "• 존재하지 않는 BOJ 핸들은 등록할 수 없습니다",
            inline=False
        )
        pages.append(embed2)
        
        # 관리자 전용 페이지들
        if is_admin:
            # 페이지 3: 역할 관리 (관리자)
            embed_role_admin = discord.Embed(
                title="🤖 알고리즘 동아리 봇 도움말",
                description=f"**페이지 3/{total_pages}** - 🎭 역할 관리 (관리자 전용)",
                color=discord.Color.blue()
            )
            embed_role_admin.add_field(
                name="`/역할 생성 <이름>`",
                value="**설명:** 새로운 Discord 역할을 생성하고 등록 토큰을 생성합니다.\n\n"
                      "**파라미터:**\n"
                      "• `이름` (필수): 생성할 역할 이름 (공백 포함 가능)\n\n"
                      "**사용법:**\n"
                      "```\n/역할 생성 21기-기초\n/역할 생성 21기-실전\n/역할 생성 21기-심화\n```\n\n"
                      "**동작 과정:**\n"
                      "1. Discord 역할 생성 (랜덤 색상 자동 할당)\n"
                      "2. 등록 토큰 생성 (고유한 토큰 자동 생성)\n"
                      "3. 토큰을 DM으로 전송 (보안을 위해)\n"
                      "4. 봇에 역할 정보 등록\n\n"
                      "**예시 출력:**\n"
                      "```\n✅ 역할 '21기-기초'이 생성되었습니다. 토큰은 DM으로 전송되었습니다.\n```\n\n"
                      "**주의사항:**\n"
                      "• 이미 존재하는 역할 이름은 생성할 수 없습니다\n"
                      "• 토큰은 안전하게 보관하고 사용자에게만 공유하세요\n"
                      "• DM을 받을 수 없는 경우 공개 채널에 토큰이 표시됩니다",
                inline=False
            )
            embed_role_admin.add_field(
                name="`/역할 목록`",
                value="**설명:** 봇에 등록된 모든 역할과 해당 토큰 목록을 확인합니다.\n\n"
                      "**사용법:**\n"
                      "```\n/역할 목록\n```\n\n"
                      "**예시 출력:**\n"
                      "```\n📋 등록된 역할 목록\n\n🎭 21기-기초\n토큰: `abc123def456`\n\n🎭 21기-실전\n토큰: `xyz789ghi012`\n\n🎭 21기-심화\n토큰: `mno345pqr678`\n```\n\n"
                      "**참고:**\n"
                      "• 등록된 모든 역할의 이름과 토큰이 표시됩니다\n"
                      "• 토큰은 역할 등록 시 사용자가 입력해야 하는 값입니다",
                inline=False
            )
            embed_role_admin.add_field(
                name="`/역할 삭제 <이름>`",
                value="**설명:** Discord 역할과 봇에 등록된 역할 정보를 삭제합니다.\n\n"
                      "**파라미터:**\n"
                      "• `이름` (필수): 삭제할 역할 이름 (공백 포함 가능)\n\n"
                      "**사용법:**\n"
                      "```\n/역할 삭제 21기-기초\n```\n\n"
                      "**동작 과정:**\n"
                      "1. Discord 서버에서 역할 삭제\n"
                      "2. 봇 데이터베이스에서 역할 정보 삭제\n"
                      "3. 해당 역할의 토큰 정보도 함께 삭제\n\n"
                      "**예시 출력:**\n"
                      "```\n✅ '21기-기초' 역할이 삭제되었습니다.\n```\n\n"
                      "**주의사항:**\n"
                      "• 봇 역할보다 위에 있는 역할은 삭제할 수 없습니다\n"
                      "• 삭제된 역할의 멤버들은 자동으로 역할이 제거됩니다\n"
                      "• 삭제된 역할의 토큰은 더 이상 사용할 수 없습니다",
                inline=False
            )
            embed_role_admin.add_field(
                name="`/역할 부여 <역할명> <discord_id> <boj_handle>`",
                value="**설명:** 특정 사용자에게 역할을 부여하고 BOJ 핸들을 등록합니다. (수동 관리용)\n\n"
                      "**파라미터:**\n"
                      "• `역할명` (필수): 부여할 역할 이름\n"
                      "• `discord_id` (필수): Discord 사용자 ID 또는 멘션 (`@사용자`)\n"
                      "• `boj_handle` (필수): 백준 온라인 저지 사용자 이름\n\n"
                      "**사용법:**\n"
                      "```\n/역할 부여 21기-심화 355920153315377152 beans3142\n/역할 부여 21기-심화 @유완규 beans3142\n```\n\n"
                      "**동작 과정:**\n"
                      "1. 역할 존재 여부 확인\n"
                      "2. BOJ 핸들 검증 (백준에 존재하는지 확인)\n"
                      "3. Discord 역할 부여\n"
                      "4. DB에 사용자 정보 및 역할 정보 저장\n\n"
                      "**예시 출력:**\n"
                      "```\n✅ '21기-심화' 역할이 부여되었습니다!\n📝 BOJ 핸들 'beans3142'가 등록되었습니다.\n```\n\n"
                      "**사용 시나리오:**\n"
                      "• 운영진이 직접 사용자를 그룹에 추가할 때\n"
                      "• 토큰 없이 빠르게 역할을 부여해야 할 때\n"
                      "• 사용자가 토큰을 잃어버렸을 때 대체 방법으로 사용",
                inline=False
            )
            embed_role_admin.add_field(
                name="`/역할 제거 <역할명> <boj_handle>`",
                value="**설명:** BOJ 핸들로 특정 역할에서 멤버를 제거합니다.\n\n"
                      "**파라미터:**\n"
                      "• `역할명` (필수): 제거할 역할 이름\n"
                      "• `boj_handle` (필수): 백준 핸들\n\n"
                      "**사용법:**\n"
                      "```\n/역할 제거 21기-심화 beans3142\n```\n\n"
                      "**동작 과정:**\n"
                      "1. BOJ 핸들로 사용자 찾기\n"
                      "2. Discord 역할 제거\n"
                      "3. DB에서 역할 정보 삭제\n\n"
                      "**예시 출력:**\n"
                      "```\n✅ 'beans3142' 사용자가 '21기-심화' 역할에서 제거되었습니다.\n```\n\n"
                      "**참고:**\n"
                      "• BOJ 핸들로 사용자를 찾아 제거합니다\n"
                      "• 같은 BOJ 핸들을 가진 여러 계정이 있으면 모두 제거됩니다",
                inline=False
            )
            embed_role_admin.add_field(
                name="`/역할 제거디스코드 <역할명> <discord_id>`",
                value="**설명:** Discord ID로 특정 역할에서 멤버를 제거합니다.\n\n"
                      "**파라미터:**\n"
                      "• `역할명` (필수): 제거할 역할 이름\n"
                      "• `discord_id` (필수): Discord 사용자 ID 또는 멘션 (`@사용자`)\n\n"
                      "**사용법:**\n"
                      "```\n/역할 제거디스코드 21기-심화 355920153315377152\n/역할 제거디스코드 21기-심화 @유완규\n```\n\n"
                      "**동작 과정:**\n"
                      "1. Discord ID로 사용자 찾기\n"
                      "2. Discord 역할 제거\n"
                      "3. DB에서 역할 정보 삭제\n\n"
                      "**예시 출력:**\n"
                      "```\n✅ 'waekyu.' 사용자가 '21기-심화' 역할에서 제거되었습니다.\n```\n\n"
                      "**참고:**\n"
                      "• Discord ID로 정확히 특정 사용자를 제거할 수 있습니다\n"
                      "• 멘션(`@사용자`) 또는 숫자 ID 모두 사용 가능합니다",
                inline=False
            )
            embed_role_admin.add_field(
                name="`/역할 멤버 <역할명>`",
                value="**설명:** 특정 역할을 가진 멤버 목록을 확인합니다.\n\n"
                      "**파라미터:**\n"
                      "• `역할명` (필수): 확인할 역할 이름\n\n"
                      "**사용법:**\n"
                      "```\n/역할 멤버 21기-기초\n```\n\n"
                      "**예시 출력:**\n"
                      "```\n👥 '21기-기초' 역할 멤버 목록\n총 6명\n\n멤버 목록\n1. 사용자1 (beans3142) - ✅ 서버 내\n2. 사용자2 (whiteys1) - ✅ 서버 내\n3. 사용자3 (karsad7) - ⚠️ 서버 외\n\nDiscord 역할 멤버 수\n6명\n```\n\n"
                      "**표시되는 정보:**\n"
                      "• 멤버 목록 (디스코드 닉네임, BOJ 핸들)\n"
                      "• 서버 내/외 상태 (✅ 서버 내, ⚠️ 서버 외)\n"
                      "• Discord 역할 멤버 수\n\n"
                      "**참고:**\n"
                      "• 최대 25명까지 표시됩니다\n"
                      "• 서버 외 상태는 해당 사용자가 서버를 나간 경우입니다",
                inline=False
            )
            embed_role_admin.add_field(
                name="`/역할 문제풀이현황 <역할명>`",
                value="**설명:** 특정 역할 멤버들의 최근 7일(월요일 00시 ~ 일요일 23:59) 백준 문제풀이 현황을 조회합니다.\n\n"
                      "**파라미터:**\n"
                      "• `역할명` (필수): 확인할 역할 이름\n\n"
                      "**사용법:**\n"
                      "```\n/역할 문제풀이현황 21기-실전\n```\n\n"
                      "**동작 과정:**\n"
                      "1. 역할 멤버 목록 조회\n"
                      "2. 각 멤버의 BOJ 핸들로 백준 status 페이지 크롤링\n"
                      "3. 최근 7일간 해결한 문제 수 및 문제 번호 수집\n"
                      "4. 결과를 문제 수 많은 순으로 정렬하여 표시\n\n"
                      "**예시 출력:**\n"
                      "```\n📊 '21기-실전' 역할 멤버 백준 문제풀이 현황\n기간: 2026-01-12 ~ 2026-01-18 (월~일)\n\n멤버별 문제풀이 현황\n👑 rornfldla - ✅ 4개 [1874, 2493, 12789, 17298]\n🥈 beans3142 - ✅ 2개 [31497, 32979]\n🥉 kwondo1017 - ✅ 1개 [12789]\n4. whiteys1 - ⚠️ 0개\n5. karsad7 - ⚠️ 0개\n\n📈 통계\n총 멤버: 5명\n문제 풀은 멤버: 3명\n총 해결한 문제: 7개\n```\n\n"
                      "**표시되는 정보:**\n"
                      "• 멤버별 문제풀이 현황 (1~3등은 메달 표시: 👑🥈🥉)\n"
                      "• 해결한 문제 번호 목록 (최대 15개, 그 이상은 '... 외 N개' 표시)\n"
                      "• 통계 (총 멤버, 문제 풀은 멤버, 총 해결한 문제)\n\n"
                      "**참고:**\n"
                      "• 기간은 월요일 00:00 ~ 일요일 23:59로 자동 계산됩니다\n"
                      "• BOJ 핸들이 미등록인 멤버는 'BOJ 핸들 미등록'으로 표시됩니다\n"
                      "• 중복된 문제는 한 번만 카운트됩니다",
                inline=False
            )
            pages.append(embed_role_admin)
            
            # 페이지 4: 그룹 관리 (관리자)
            embed_group_admin = discord.Embed(
                title="🤖 알고리즘 동아리 봇 도움말",
                description=f"**페이지 4/{total_pages}** - 📁 그룹 관리 (관리자 전용)",
                color=discord.Color.blue()
            )
            embed_group_admin.add_field(
                name="`/그룹 생성 <이름> <역할>`",
                value="**설명:** 그룹 카테고리와 채널을 자동으로 생성합니다. 지정된 역할만 접근할 수 있습니다.\n\n"
                      "**파라미터:**\n"
                      "• `이름` (필수): 생성할 그룹 이름 (카테고리 이름)\n"
                      "• `역할` (필수): 접근 권한을 부여할 Discord 역할 이름\n\n"
                      "**사용법:**\n"
                      "```\n/그룹 생성 21기-기초 21기-기초\n/그룹 생성 21기-실전 21기-실전\n```\n\n"
                      "**생성되는 채널:**\n"
                      "**텍스트 채널:**\n"
                      "• `#공지` - Announcement 채널 (공지사항 전용)\n"
                      "• `#풀이현황` - 문제풀이 현황 공유 채널\n"
                      "• `#자유` - 자유로운 대화 채널\n"
                      "• `#해설` - 문제 해설 공유 채널\n"
                      "• `#과제제출` - 과제 제출 채널\n\n"
                      "**음성 채널:**\n"
                      "• `🔊 자유1` - 음성 채널 1\n"
                      "• `🔊 자유2` - 음성 채널 2\n\n"
                      "**예시 출력:**\n"
                      "```\n✅ 그룹 '21기-기초' 생성 완료\n역할: @21기-기초\n카테고리: 21기-기초\n\n생성된 텍스트 채널\n• #공지\n• #풀이현황\n• #자유\n• #해설\n• #과제제출\n\n생성된 음성 채널\n• 🔊 자유1\n• 🔊 자유2\n```\n\n"
                      "**주의사항:**\n"
                      "• 같은 이름의 카테고리가 이미 있으면 생성할 수 없습니다\n"
                      "• 지정된 역할만 해당 채널들을 볼 수 있습니다 (@everyone은 접근 불가)\n"
                      "• 역할은 먼저 `/역할 생성`으로 생성되어 있어야 합니다",
                inline=False
            )
            embed_group_admin.add_field(
                name="`/그룹 목록`",
                value="**설명:** 봇에 등록된 모든 그룹 목록을 확인합니다.\n\n"
                      "**사용법:**\n"
                      "```\n/그룹 목록\n```\n\n"
                      "**예시 출력:**\n"
                      "```\n📋 등록된 그룹 목록\n\n📚 21기-기초\n역할: @21기-기초\n과제 수: 0개\n\n📚 21기-실전\n역할: @21기-실전\n과제 수: 0개\n\n📚 21기-심화\n역할: @21기-심화\n과제 수: 0개\n```\n\n"
                      "**표시되는 정보:**\n"
                      "• 그룹 이름\n"
                      "• 연결된 역할 이름\n"
                      "• 과제 수\n\n"
                      "**참고:**\n"
                      "• 등록된 모든 그룹이 표시됩니다\n"
                      "• 그룹 이름은 카테고리 이름과 동일합니다",
                inline=False
            )
            embed_group_admin.add_field(
                name="`/그룹 수정 <역할이름> <새그룹명>`",
                value="**설명:** 그룹의 이름을 수정합니다. 카테고리 이름도 함께 변경됩니다.\n\n"
                      "**파라미터:**\n"
                      "• `역할이름` (필수): 그룹에 연결된 역할 이름\n"
                      "• `새그룹명` (필수): 새로운 그룹 이름\n\n"
                      "**사용법:**\n"
                      "```\n/그룹 수정 21기-기초 22기-기초\n```\n\n"
                      "**동작 과정:**\n"
                      "1. 그룹 정보 확인\n"
                      "2. 카테고리 이름 변경\n"
                      "3. DB에 새 그룹 이름 저장\n\n"
                      "**예시 출력:**\n"
                      "```\n✅ 그룹 이름이 '21기-기초'에서 '22기-기초'으로 변경되었습니다.\n```\n\n"
                      "**참고:**\n"
                      "• 카테고리 이름이 자동으로 변경됩니다\n"
                      "• 채널 이름은 변경되지 않습니다",
                inline=False
            )
            embed_group_admin.add_field(
                name="`/그룹 삭제 <역할이름>`",
                value="**설명:** 그룹 정보를 데이터베이스에서 삭제합니다. 카테고리와 채널은 수동으로 삭제해야 합니다.\n\n"
                      "**파라미터:**\n"
                      "• `역할이름` (필수): 삭제할 그룹의 역할 이름\n\n"
                      "**사용법:**\n"
                      "```\n/그룹 삭제 21기-기초\n```\n\n"
                      "**동작 과정:**\n"
                      "1. 그룹 정보 확인\n"
                      "2. 확인 버튼 클릭 (삭제 확인 필요)\n"
                      "3. DB에서 그룹 정보 삭제\n\n"
                      "**예시 출력:**\n"
                      "```\n✅ 그룹 '21기-기초'의 데이터가 삭제되었습니다.\n카테고리와 채널은 Discord에서 수동으로 삭제해주세요.\n```\n\n"
                      "**주의사항:**\n"
                      "• 카테고리와 채널은 Discord에서 수동으로 삭제해야 합니다\n"
                      "• 삭제 확인 버튼을 클릭해야 실제로 삭제됩니다\n"
                      "• 삭제된 그룹의 과제 정보도 함께 삭제됩니다",
                inline=False
            )
            embed_group_admin.add_field(
                name="`/그룹 제출현황 <역할이름>`",
                value="**설명:** 특정 그룹의 모든 과제에 대한 제출 현황을 확인합니다.\n\n"
                      "**파라미터:**\n"
                      "• `역할이름` (필수): 확인할 그룹의 역할 이름\n\n"
                      "**사용법:**\n"
                      "```\n/그룹 제출현황 21기-기초\n```\n\n"
                      "**예시 출력:**\n"
                      "```\n📊 21기-기초 그룹 제출 현황\n\n사용자1\n과제1: ✅\n과제2: ⚠️ 2/5\n\n사용자2\n과제1: ✅\n과제2: ✅\n```\n\n"
                      "**표시되는 정보:**\n"
                      "• 그룹 내 모든 과제 목록\n"
                      "• 각 과제별 제출자 수 및 제출 현황\n"
                      "• 멤버별 제출 상태 (✅ 완료, ⚠️ 진행중, ❌ 미제출)\n\n"
                      "**참고:**\n"
                      "• 최대 20명까지 표시됩니다\n"
                      "• 과제가 없는 그룹은 표시할 수 없습니다",
                inline=False
            )
            embed_group_admin.add_field(
                name="`/그룹 정보`",
                value="**설명:** 그룹의 상세 정보를 확인합니다.\n\n"
                      "**사용법:**\n"
                      "```\n/그룹 정보\n```\n\n"
                      "**동작 과정:**\n"
                      "1. `/그룹 정보` 실행\n"
                      "2. Select Menu에서 확인할 그룹 선택\n"
                      "3. 상세 정보 확인 (페이징 가능)\n\n"
                      "**표시되는 정보:**\n"
                      "• **소속 인원**: 그룹에 속한 멤버 목록 (디스코드 닉네임 + BOJ 핸들)\n"
                      "• **과제 현황**:\n"
                      "  - 진행중: 현재 진행 중인 과제 목록\n"
                      "  - 시작 전: 아직 시작하지 않은 과제 목록\n"
                      "  - 종료: 마감된 과제 목록\n\n"
                      "**예시 출력:**\n"
                      "```\n📚 21기-기초 그룹 정보\n\n👥 소속 인원\n총 6명\n사용자1 (beans3142)\n사용자2 (whiteys1)\n...\n\n📝 과제 현황\n진행중: 과제1, 과제2\n시작 전: 과제3\n종료: 과제4\n```\n\n"
                      "**참고:**\n"
                      "• 여러 페이지로 나뉘어 표시될 수 있습니다\n"
                      "• 이전/다음 버튼으로 페이지 이동 가능합니다",
                inline=False
            )
            pages.append(embed_group_admin)
            
            # 페이지 5: 문제풀이 현황 (관리자)
            embed_problem_status = discord.Embed(
                title="🤖 알고리즘 동아리 봇 도움말",
                description=f"**페이지 5/{total_pages}** - 📊 문제풀이 현황 (관리자 전용)",
                color=discord.Color.blue()
            )
            embed_problem_status.add_field(
                name="`/그룹 문제풀이현황 <그룹명>`",
                value="**설명:** 특정 그룹 멤버들의 최근 7일(월요일 00시 ~ 일요일 23:59) 백준 문제풀이 현황을 조회합니다.\n\n"
                      "**파라미터:**\n"
                      "• `그룹명` (필수): 확인할 그룹 이름\n\n"
                      "**사용법:**\n"
                      "```\n/그룹 문제풀이현황 21기-실전\n```\n\n"
                      "**동작 과정:**\n"
                      "1. 그룹 이름으로 연결된 역할 찾기\n"
                      "2. 역할 멤버 목록 조회\n"
                      "3. 각 멤버의 BOJ 핸들로 백준 status 페이지 크롤링\n"
                      "4. 최근 7일간 해결한 문제 수 및 문제 번호 수집\n"
                      "5. 결과를 문제 수 많은 순으로 정렬하여 표시\n\n"
                      "**예시 출력:**\n"
                      "```\n🔄 최근 7일간(월~일) 백준 문제풀이 현황을 조회하는 중...\n📅 기간: 2026-01-12 ~ 2026-01-18\n\n📊 '21기-실전' 그룹 백준 문제풀이 현황\n기간: 2026-01-12 ~ 2026-01-18 (월~일)\n\n멤버별 문제풀이 현황\n👑 rornfldla - ✅ 4개 [1874, 2493, 12789, 17298]\n🥈 beans3142 - ✅ 2개 [31497, 32979]\n🥉 kwondo1017 - ✅ 1개 [12789]\n4. whiteys1 - ⚠️ 0개\n\n📈 통계\n총 멤버: 4명\n문제 풀은 멤버: 3명\n총 해결한 문제: 7개\n```\n\n"
                      "**표시되는 정보:**\n"
                      "• 멤버별 문제풀이 현황 (1~3등은 메달 표시: 👑🥈🥉)\n"
                      "• 해결한 문제 번호 목록 (최대 15개, 그 이상은 '... 외 N개' 표시)\n"
                      "• 통계 (총 멤버, 문제 풀은 멤버, 총 해결한 문제)\n\n"
                      "**참고:**\n"
                      "• 기간은 월요일 00:00 ~ 일요일 23:59로 자동 계산됩니다\n"
                      "• BOJ 핸들이 미등록인 멤버는 'BOJ 핸들 미등록'으로 표시됩니다\n"
                      "• 중복된 문제는 한 번만 카운트됩니다\n"
                      "• 같은 BOJ 핸들을 가진 여러 계정이 있으면 중복 표시될 수 있습니다",
                inline=False
            )
            embed_problem_status.add_field(
                name="`/그룹 주간현황설정 <그룹명>`",
                value="**설명:** 해당 채널에 그룹 주간 문제풀이 현황 메시지를 생성합니다. 매시 정각 자동 갱신 및 수동 갱신 버튼이 제공됩니다.\n\n"
                      "**파라미터:**\n"
                      "• `그룹명` (필수): 설정할 그룹 이름\n\n"
                      "**사용법:**\n"
                      "```\n/그룹 주간현황설정 21기-실전\n```\n"
                      "→ `#풀이현황` 채널에서 실행하면 해당 채널에 고정 메시지 생성\n\n"
                      "**동작 과정:**\n"
                      "1. 그룹 이름으로 연결된 역할 찾기\n"
                      "2. 명령어 실행 채널에 고정 메시지 1개 생성\n"
                      "3. 기간 자동 계산: 명령어 실행일이 속한 주의 월요일 00:00 ~ 다음 주 월요일 01:00\n"
                      "4. 즉시 1회 갱신 (현재 멤버들의 문제풀이 현황 조회)\n"
                      "5. DB에 메시지 정보 저장 (자동 갱신용)\n\n"
                      "**예시 출력:**\n"
                      "```\n✅ '21기-실전' 그룹의 주간 문제풀이 현황 메시지가 설정되었습니다.\n📅 매시 정각 자동 갱신, 버튼으로 수동 갱신 가능합니다.\n```\n\n"
                      "**자동 갱신:**\n"
                      "• 매시 정각(0시~23시)에 자동으로 메시지 갱신\n"
                      "• 기간 내에만 갱신 (기간이 지나면 자동 중단)\n"
                      "• 봇 재시작 후에도 계속 동작\n\n"
                      "**수동 갱신:**\n"
                      "• 메시지 하단의 `🔄 갱신` 버튼 클릭\n"
                      "• 기간 내에만 갱신 가능 (기간이 지나면 버튼 비활성화)\n\n"
                      "**주의사항:**\n"
                      "• 여러 채널에서 각각 생성 가능합니다\n"
                      "• 같은 그룹을 여러 채널에 생성해도 각각 독립적으로 동작합니다\n"
                      "• 기간이 지난 메시지는 기록용으로 남고, DB에서만 정리됩니다",
                inline=False
            )
            embed_problem_status.add_field(
                name="`/그룹 주간현황목록`",
                value="**설명:** 생성된 모든 그룹 주간 현황 메시지 목록을 확인합니다.\n\n"
                      "**사용법:**\n"
                      "```\n/그룹 주간현황목록\n```\n\n"
                      "**예시 출력:**\n"
                      "```\n📋 생성된 그룹 주간 현황 목록\n\n**21기-기초**\n채널: #풀이현황\n기간: 2026-01-12 00:00 ~ 2026-01-19 01:00\n상태: 🟢 진행 중\n\n**21기-실전**\n채널: #풀이현황\n기간: 2026-01-12 00:00 ~ 2026-01-19 01:00\n상태: 🟢 진행 중\n\n**21기-심화**\n채널: #풀이현황\n기간: 2026-01-05 00:00 ~ 2026-01-12 01:00\n상태: 🔴 종료됨\n```\n\n"
                      "**표시되는 정보:**\n"
                      "• 그룹 이름\n"
                      "• 채널 위치 (채널 멘션)\n"
                      "• 기간 (시작일 ~ 종료일)\n"
                      "• 상태:\n"
                      "  - 🟢 진행 중: 현재 기간 내에 있어 갱신 중\n"
                      "  - 🔴 종료됨: 기간이 지나서 더 이상 갱신하지 않음\n"
                      "  - ⏳ 시작 전: 아직 시작하지 않음\n\n"
                      "**참고:**\n"
                      "• 모든 채널의 주간 현황 메시지가 표시됩니다\n"
                      "• 종료된 메시지는 기록용으로 채널에 남아있습니다",
                inline=False
            )
            embed_problem_status.add_field(
                name="`/그룹 주간현황삭제 <그룹명>`",
                value="**설명:** 그룹 주간 현황 메시지 정보를 DB에서 삭제합니다. (메시지는 채널에 그대로 남음)\n\n"
                      "**파라미터:**\n"
                      "• `그룹명` (필수): 삭제할 그룹 이름\n\n"
                      "**사용법:**\n"
                      "```\n/그룹 주간현황삭제 21기-실전\n```\n\n"
                      "**동작 과정:**\n"
                      "1. 그룹 주간 현황 정보 확인\n"
                      "2. DB에서 정보 삭제\n"
                      "3. 메시지는 채널에 그대로 남음 (기록용)\n\n"
                      "**예시 출력:**\n"
                      "```\n✅ '21기-실전' 그룹의 주간 현황 메시지 정보가 삭제되었습니다.\n📝 메시지는 #풀이현황에 그대로 남아있습니다.\n```\n\n"
                      "**사용 시나리오:**\n"
                      "• 기간이 지난 주간 현황 메시지 정리 시\n"
                      "• 다음 주에 새로 생성하기 전에 이전 정보 삭제 시\n"
                      "• 잘못 생성된 메시지 정보 삭제 시\n\n"
                      "**참고:**\n"
                      "• 메시지 자체는 삭제되지 않고 채널에 기록용으로 남습니다\n"
                      "• 삭제 후에도 다음 주에 `/그룹 주간현황설정`으로 새로 생성 가능합니다\n"
                      "• 자동 갱신은 즉시 중단됩니다",
                inline=False
            )
            pages.append(embed_problem_status)
        
        # 페이지가 없으면
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

    def _sync_button_state(self) -> None:
        """현재 페이지에 맞게 이전/다음 버튼 disabled 상태를 동기화"""
        self.prev_button.disabled = self.current_page <= 0
        self.next_button.disabled = self.current_page >= (len(self.pages) - 1)

    async def _safe_edit(self, interaction: discord.Interaction) -> None:
        """
        버튼 클릭 인터랙션에 안전하게 응답하며 메시지를 수정.
        - 3초 제한 회피를 위해 먼저 defer 시도
        - 이미 응답된 경우/응답이 늦어진 경우에도 edit_original_response로 처리
        """
        self._sync_button_state()

        # 3초 내 ACK를 최대한 보장
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            # defer 자체가 실패해도 아래 편집을 시도해본다
            pass

        try:
            await interaction.edit_original_response(embed=self.pages[self.current_page], view=self)
        except Exception:
            # (10062) Unknown interaction 등: 이미 만료/삭제된 경우라면 조용히 무시
            pass
    
    @discord.ui.button(label='◀ 이전', style=discord.ButtonStyle.primary, disabled=True)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        if self.current_page > 0:
            self.current_page -= 1

        await self._safe_edit(interaction)
    
    @discord.ui.button(label='다음 ▶', style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ 이 버튼은 명령어를 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
            return
        
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1

        await self._safe_edit(interaction)
    
    async def on_timeout(self):
        """타임아웃 시 버튼 비활성화"""
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except:
                pass
