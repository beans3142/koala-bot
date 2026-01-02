"""
봇 설정 파일
"""

# 명령어 접두사
COMMAND_PREFIX = '/'

# 데이터 파일 경로
DATA_FILE = 'data.json'

# 백준 크롤링 설정
BAEKJOON_CRAWL_LIMIT = 100  # 최대 가져올 문제 수

# Tistory 도메인 검증
TISTORY_DOMAINS = ['tistory.com']

# 역할 관리 권한
REQUIRED_PERMISSIONS = {
    'manage_roles': '역할 관리',
    'administrator': '관리자'
}

