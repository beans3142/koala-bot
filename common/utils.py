"""
공통 유틸리티 함수
"""
import os
import json
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from typing import Optional

# 데이터 저장 파일
DATA_FILE = 'data.json'
USE_SQLITE = True  # SQLite 사용 여부 (True로 설정하면 database.py 사용)

def load_data():
    """데이터 파일 로드 (SQLite 우선, 없으면 JSON)"""
    if USE_SQLITE:
        try:
            from common import database
            return database.load_data()
        except ImportError:
            print("⚠️ database.py를 찾을 수 없습니다. JSON 방식으로 전환합니다.")
        except Exception as e:
            print(f"⚠️ SQLite 로드 오류: {e}. JSON 방식으로 전환합니다.")
    
    # JSON 방식 (기존)
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'users': {},  # {user_id: {boj_handle, tistory_links, roles, submissions}}
        'submissions': {},  # {user_id: [link1, link2, ...]} (호환성)
        'role_tokens': {},  # {role_name: {'token_hash': hash, 'original_token': token}}
        'studies': {}  # {study_name: {assignments: {assignment_id: {...}}}}
    }

def save_data(data):
    """데이터 파일 저장 (SQLite 우선, 없으면 JSON)"""
    if USE_SQLITE:
        try:
            from common import database
            database.save_data(data)
            return
        except ImportError:
            print("⚠️ database.py를 찾을 수 없습니다. JSON 방식으로 전환합니다.")
        except Exception as e:
            print(f"⚠️ SQLite 저장 오류: {e}. JSON 방식으로 전환합니다.")
    
    # JSON 방식 (기존)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_token():
    """토큰 생성 (32자 랜덤 문자열)"""
    return secrets.token_urlsafe(24)

def hash_token(token):
    """토큰 해시"""
    return hashlib.sha256(token.encode()).hexdigest()

def verify_token(input_token, stored_hash):
    """토큰 검증"""
    return hash_token(input_token) == stored_hash

def parse_datetime(datetime_str: str) -> Optional[datetime]:
    """
    날짜/시간 문자열을 파싱하여 datetime 객체로 변환
    
    지원 형식:
    - 상대 시간: "7일", "1주", "2주", "14일", "3시간", "5시간 후" (현재 시간 기준)
    - 시 단위: "3시", "14시", "23시", "오전 9시", "오후 3시", "오후 11시"
    - 절대 시간: "2024-12-31", "2024-12-31 23:59", "2024/12/31"
    
    Returns:
        datetime 객체 또는 None (파싱 실패 시)
    """
    if not datetime_str:
        return None
    
    datetime_str = datetime_str.strip()
    
    # 상대 시간 파싱 (예: "7일", "1주", "3시간")
    relative_match = re.match(r'^(\d+)(일|주|시간|week|day|days|weeks|hour|hours)$', datetime_str, re.IGNORECASE)
    if relative_match:
        number = int(relative_match.group(1))
        unit = relative_match.group(2).lower()
        
        if unit in ['일', 'day', 'days']:
            return datetime.now() + timedelta(days=number)
        elif unit in ['주', 'week', 'weeks']:
            return datetime.now() + timedelta(weeks=number)
        elif unit in ['시간', 'hour', 'hours']:
            return datetime.now() + timedelta(hours=number)
    
    # "N시간 후" 형식
    hours_after_match = re.match(r'^(\d+)시간\s*후$', datetime_str, re.IGNORECASE)
    if hours_after_match:
        hours = int(hours_after_match.group(1))
        return datetime.now() + timedelta(hours=hours)
    
    # 시 단위 파싱 (예: "3시", "14시", "오전 9시", "오후 3시")
    # "오전/오후 N시" 형식
    ampm_match = re.match(r'^(오전|오후|AM|PM|am|pm)\s*(\d+)시$', datetime_str, re.IGNORECASE)
    if ampm_match:
        ampm = ampm_match.group(1).lower()
        hour = int(ampm_match.group(2))
        
        # 오전/오후 처리
        if ampm in ['오전', 'am']:
            if hour == 12:
                hour = 0  # 오전 12시는 0시
            elif hour > 12:
                return None  # 오전은 12시까지만
        elif ampm in ['오후', 'pm']:
            if hour != 12:
                hour += 12  # 오후는 12를 더함
            if hour >= 24:
                return None  # 24시 이상은 불가능
        
        # 오늘 날짜에 시간 설정
        now = datetime.now()
        return now.replace(hour=hour, minute=0, second=0, microsecond=0)
    
    # "N시" 형식 (24시간 형식)
    hour_only_match = re.match(r'^(\d{1,2})시$', datetime_str)
    if hour_only_match:
        hour = int(hour_only_match.group(1))
        if 0 <= hour <= 23:
            # 오늘 날짜에 시간 설정
            now = datetime.now()
            return now.replace(hour=hour, minute=0, second=0, microsecond=0)
    
    # 절대 시간 파싱
    formats = [
        '%Y-%m-%d %H:%M',      # 2024-12-31 23:59
        '%Y-%m-%d',            # 2024-12-31
        '%Y/%m/%d %H:%M',      # 2024/12/31 23:59
        '%Y/%m/%d',            # 2024/12/31
        '%Y.%m.%d %H:%M',      # 2024.12.31 23:59
        '%Y.%m.%d',            # 2024.12.31
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(datetime_str, fmt)
            # 날짜만 입력된 경우 시간을 00:00으로 설정
            if fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d']:
                dt = dt.replace(hour=0, minute=0)
            return dt
        except ValueError:
            continue
    
    return None

def parse_deadline(deadline_str: str) -> Optional[datetime]:
    """기한 파싱 (parse_datetime의 별칭, 호환성 유지)"""
    return parse_datetime(deadline_str)

