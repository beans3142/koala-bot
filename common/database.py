"""
SQLite 데이터베이스 관리 모듈
경량 데이터베이스를 사용하여 효율적인 데이터 저장
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional
import os

DB_FILE = 'bot_data.db'

def get_connection():
    """데이터베이스 연결"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """데이터베이스 초기화"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 사용자 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            boj_handle TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    
    # 역할 토큰 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS role_tokens (
            role_name TEXT PRIMARY KEY,
            token_hash TEXT,
            original_token TEXT,
            created_at TEXT
        )
    ''')
    
    # 사용자 역할 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id TEXT,
            role_name TEXT,
            PRIMARY KEY (user_id, role_name)
        )
    ''')
    
    # 블로그 링크 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blog_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            link TEXT,
            submitted_at TEXT,
            UNIQUE(user_id, link)
        )
    ''')
    
    # 스터디 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS studies (
            study_name TEXT PRIMARY KEY,
            created_at TEXT
        )
    ''')
    
    # 과제 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            assignment_id TEXT PRIMARY KEY,
            study_name TEXT,
            type TEXT,
            name TEXT,
            config TEXT,
            created_at TEXT,
            created_by TEXT,
            FOREIGN KEY (study_name) REFERENCES studies(study_name)
        )
    ''')
    
    # 제출 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            assignment_id TEXT,
            type TEXT,
            content TEXT,
            problem_id INTEGER,
            verified INTEGER DEFAULT 0,
            submitted_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (assignment_id) REFERENCES assignments(assignment_id)
        )
    ''')

    # 주간 현황 메시지 테이블 (역할 기준)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weekly_status_messages (
            role_name TEXT PRIMARY KEY,
            channel_id TEXT,
            message_id TEXT,
            week_start_date TEXT,
            created_at TEXT
        )
    ''')

    # 그룹 주간 현황 메시지 테이블 (그룹 기준)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_weekly_status (
            group_name TEXT PRIMARY KEY,
            role_name TEXT,
            channel_id TEXT,
            message_id TEXT,
            week_start TEXT,
            week_end TEXT,
            last_updated TEXT
        )
    ''')
    
    # 그룹 주간 링크 제출 메시지 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_link_submissions (
            group_name TEXT PRIMARY KEY,
            role_name TEXT,
            channel_id TEXT,
            message_id TEXT,
            week_start TEXT,
            week_end TEXT,
            last_updated TEXT
        )
    ''')
    
    # 그룹 주간 링크 제출 데이터 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS link_submission_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT,
            user_id TEXT,
            week_start TEXT,
            links TEXT,
            submitted_at TEXT,
            updated_at TEXT,
            UNIQUE(group_name, user_id, week_start)
        )
    ''')
    
    conn.commit()
    conn.close()

def reset_database():
    """데이터베이스 초기화 (모든 데이터 삭제)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 모든 테이블 삭제
    cursor.execute('DROP TABLE IF EXISTS weekly_status_messages')
    cursor.execute('DROP TABLE IF EXISTS submissions')
    cursor.execute('DROP TABLE IF EXISTS assignments')
    cursor.execute('DROP TABLE IF EXISTS studies')
    cursor.execute('DROP TABLE IF EXISTS blog_links')
    cursor.execute('DROP TABLE IF EXISTS user_roles')
    cursor.execute('DROP TABLE IF EXISTS role_tokens')
    cursor.execute('DROP TABLE IF EXISTS users')
    
    conn.commit()
    conn.close()
    
    # 테이블 재생성
    init_database()

# ==================== 사용자 관리 ====================

def get_user(user_id: str) -> Optional[Dict]:
    """사용자 정보 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def create_or_update_user(user_id: str, username: str, boj_handle: Optional[str] = None):
    """사용자 생성 또는 업데이트"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    user = get_user(user_id)
    
    if user:
        cursor.execute('''
            UPDATE users SET username = ?, boj_handle = ?, updated_at = ?
            WHERE user_id = ?
        ''', (username, boj_handle, now, user_id))
    else:
        cursor.execute('''
            INSERT INTO users (user_id, username, boj_handle, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, boj_handle, now, now))
    
    conn.commit()
    conn.close()

# -------------------- 사용자 조회/삭제 --------------------

def get_user_by_boj_handle(boj_handle: str) -> Optional[Dict]:
    """BOJ 핸들로 사용자 조회"""
    if not boj_handle:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE boj_handle = ?', (boj_handle,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

# ==================== 역할 관리 ====================
# ==================== 역할 관리 ====================

def get_role_token(role_name: str) -> Optional[Dict]:
    """역할 토큰 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM role_tokens WHERE role_name = ?', (role_name,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def save_role_token(role_name: str, token_hash: str, original_token: str):
    """역할 토큰 저장"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT OR REPLACE INTO role_tokens (role_name, token_hash, original_token, created_at)
        VALUES (?, ?, ?, ?)
    ''', (role_name, token_hash, original_token, now))
    
    conn.commit()
    conn.close()

def get_all_role_tokens() -> Dict[str, Dict]:
    """모든 역할 토큰 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM role_tokens')
    rows = cursor.fetchall()
    conn.close()
    
    return {row['role_name']: dict(row) for row in rows}

def delete_role_token(role_name: str):
    """역할 토큰 삭제"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM role_tokens WHERE role_name = ?', (role_name,))
    conn.commit()
    conn.close()

# ==================== 사용자 역할 관리 ====================

def add_user_role(user_id: str, role_name: str):
    """사용자에게 역할 추가"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR IGNORE INTO user_roles (user_id, role_name)
        VALUES (?, ?)
    ''', (user_id, role_name))
    
    conn.commit()
    conn.close()

def remove_user_role(user_id: str, role_name: str):
    """사용자에게서 역할 제거"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_roles WHERE user_id = ? AND role_name = ?', (user_id, role_name))
    conn.commit()
    conn.close()

def get_user_roles(user_id: str) -> List[str]:
    """사용자의 역할 목록 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT role_name FROM user_roles WHERE user_id = ?', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [row['role_name'] for row in rows]

def get_role_users(role_name: str) -> List[Dict]:
    """특정 역할을 가진 사용자 목록 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.user_id, u.username, u.boj_handle 
        FROM users u
        JOIN user_roles ur ON u.user_id = ur.user_id
        WHERE ur.role_name = ?
        ORDER BY u.username
    ''', (role_name,))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# ==================== 블로그 링크 관리 ====================

def add_blog_link(user_id: str, link: str):
    """블로그 링크 추가"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT OR IGNORE INTO blog_links (user_id, link, submitted_at)
        VALUES (?, ?, ?)
    ''', (user_id, link, now))
    
    conn.commit()
    conn.close()

def get_user_blog_links(user_id: str) -> List[Dict]:
    """사용자의 블로그 링크 목록 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM blog_links WHERE user_id = ?
        ORDER BY submitted_at DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# ==================== 스터디 관리 ====================

def create_study(study_name: str):
    """스터디 생성"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT OR IGNORE INTO studies (study_name, created_at)
        VALUES (?, ?)
    ''', (study_name, now))
    
    conn.commit()
    conn.close()

def get_study(study_name: str) -> Optional[Dict]:
    """스터디 정보 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM studies WHERE study_name = ?', (study_name,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

# ==================== 과제 관리 ====================

def create_assignment(assignment_id: str, study_name: str, assignment_type: str,
                     name: str, config: Dict, created_by: str):
    """과제 생성"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    config_json = json.dumps(config, ensure_ascii=False)
    
    cursor.execute('''
        INSERT OR REPLACE INTO assignments 
        (assignment_id, study_name, type, name, config, created_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (assignment_id, study_name, assignment_type, name, config_json, now, created_by))
    
    conn.commit()
    conn.close()

def get_assignment(assignment_id: str) -> Optional[Dict]:
    """과제 정보 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM assignments WHERE assignment_id = ?', (assignment_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        result = dict(row)
        result['config'] = json.loads(result['config'])
        return result
    return None

def get_study_assignments(study_name: str) -> Dict[str, Dict]:
    """스터디의 모든 과제 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM assignments WHERE study_name = ?', (study_name,))
    rows = cursor.fetchall()
    conn.close()
    
    result = {}
    for row in rows:
        assignment = dict(row)
        assignment['config'] = json.loads(assignment['config'])
        result[assignment['assignment_id']] = assignment
    
    return result

def update_assignment(assignment_id: str, name: Optional[str] = None, config: Optional[Dict] = None):
    """과제 수정"""
    conn = get_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if name:
        updates.append('name = ?')
        params.append(name)
    
    if config:
        updates.append('config = ?')
        params.append(json.dumps(config, ensure_ascii=False))
    
    if updates:
        params.append(assignment_id)
        cursor.execute(f'''
            UPDATE assignments SET {', '.join(updates)}
            WHERE assignment_id = ?
        ''', params)
        conn.commit()
    
    conn.close()

def delete_assignment(assignment_id: str):
    """과제 삭제"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM assignments WHERE assignment_id = ?', (assignment_id,))
    conn.commit()
    conn.close()

# ==================== 제출 관리 ====================

def add_submission(user_id: str, assignment_id: str, submission_type: str,
                  content: Optional[str] = None, problem_id: Optional[int] = None,
                  verified: bool = False):
    """제출 추가 (중복 체크)"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 중복 체크: 같은 user_id, assignment_id, type, content/problem_id가 이미 있는지 확인
        if problem_id is not None:
            # 문제풀이 제출인 경우 problem_id로 중복 체크
            cursor.execute('''
                SELECT id FROM submissions 
                WHERE user_id = ? AND assignment_id = ? AND type = ? AND problem_id = ?
            ''', (user_id, assignment_id, submission_type, problem_id))
        elif content:
            # 블로그/모의테스트 제출인 경우 content로 중복 체크
            cursor.execute('''
                SELECT id FROM submissions 
                WHERE user_id = ? AND assignment_id = ? AND type = ? AND content = ?
            ''', (user_id, assignment_id, submission_type, content))
        else:
            # content와 problem_id가 모두 없는 경우는 그냥 추가
            pass
        
        existing = cursor.fetchone()
        if existing:
            # 이미 존재하는 제출이면 추가하지 않음
            conn.close()
            return
        
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO submissions 
            (user_id, assignment_id, type, content, problem_id, verified, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, assignment_id, submission_type, content, problem_id, 1 if verified else 0, now))
        
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        # 중복 제출은 에러로 처리하지 않음 (이미 존재하는 경우)
        import traceback
        print(f"[add_submission] 오류 (무시 가능): {e}")
        print(traceback.format_exc())
    finally:
        if conn:
            conn.close()

def get_user_submissions(user_id: str, assignment_id: Optional[str] = None) -> List[Dict]:
    """사용자의 제출 목록 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    if assignment_id:
        cursor.execute('''
            SELECT * FROM submissions 
            WHERE user_id = ? AND assignment_id = ?
            ORDER BY submitted_at DESC
        ''', (user_id, assignment_id))
    else:
        cursor.execute('''
            SELECT * FROM submissions 
            WHERE user_id = ?
            ORDER BY submitted_at DESC
        ''', (user_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_study_submissions(study_name: str) -> Dict[str, List[Dict]]:
    """스터디의 모든 제출 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.* FROM submissions s
        JOIN assignments a ON s.assignment_id = a.assignment_id
        WHERE a.study_name = ?
        ORDER BY s.submitted_at DESC
    ''', (study_name,))
    
    rows = cursor.fetchall()
    conn.close()
    
    result = {}
    for row in rows:
        submission = dict(row)
        assignment_id = submission['assignment_id']
        if assignment_id not in result:
            result[assignment_id] = []
        result[assignment_id].append(submission)
    
    return result

# ==================== 주간 현황 메시지 관리 ====================

def save_weekly_status_message(role_name: str, channel_id: str, message_id: str, week_start_date: str):
    """주간 현황 메시지 저장"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT OR REPLACE INTO weekly_status_messages 
        (role_name, channel_id, message_id, week_start_date, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (role_name, channel_id, message_id, week_start_date, now))
    
    conn.commit()
    conn.close()

def save_group_weekly_status(group_name: str, role_name: str, channel_id: str,
                             message_id: str, week_start: str, week_end: str,
                             last_updated: Optional[str] = None):
    """그룹 주간 현황 메시지 저장"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = last_updated or datetime.now().isoformat()
    cursor.execute('''
        INSERT OR REPLACE INTO group_weekly_status
        (group_name, role_name, channel_id, message_id, week_start, week_end, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (group_name, role_name, channel_id, message_id, week_start, week_end, now))
    
    conn.commit()
    conn.close()

def get_group_weekly_status(group_name: str) -> Optional[Dict]:
    """그룹 주간 현황 메시지 가져오기 (그룹 이름 기준)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM group_weekly_status WHERE group_name = ?', (group_name,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def get_group_weekly_status_by_message(channel_id: str, message_id: str) -> Optional[Dict]:
    """채널/메시지 ID로 그룹 주간 현황 메시지 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM group_weekly_status WHERE channel_id = ? AND message_id = ?',
                   (channel_id, message_id))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def get_all_group_weekly_status() -> List[Dict]:
    """모든 그룹 주간 현황 메시지 목록 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM group_weekly_status')
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def delete_group_weekly_status(group_name: str):
    """그룹 주간 현황 메시지 삭제"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM group_weekly_status WHERE group_name = ?', (group_name,))
    conn.commit()
    conn.close()

# ==================== 그룹 주간 링크 제출 관리 ====================

def save_group_link_submission_status(group_name: str, role_name: str, channel_id: str,
                                      message_id: str, week_start: str, week_end: str,
                                      last_updated: Optional[str] = None):
    """그룹 주간 링크 제출 메시지 저장"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = last_updated or datetime.now().isoformat()
    cursor.execute('''
        INSERT OR REPLACE INTO group_link_submissions
        (group_name, role_name, channel_id, message_id, week_start, week_end, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (group_name, role_name, channel_id, message_id, week_start, week_end, now))
    
    conn.commit()
    conn.close()

def get_group_link_submission_status(group_name: str) -> Optional[Dict]:
    """그룹 주간 링크 제출 메시지 가져오기 (그룹 이름 기준)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM group_link_submissions WHERE group_name = ?', (group_name,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def get_group_link_submission_status_by_message(channel_id: str, message_id: str) -> Optional[Dict]:
    """채널/메시지 ID로 그룹 주간 링크 제출 메시지 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM group_link_submissions WHERE channel_id = ? AND message_id = ?',
                   (channel_id, message_id))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def get_all_group_link_submission_status() -> List[Dict]:
    """모든 그룹 주간 링크 제출 메시지 목록 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM group_link_submissions')
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def delete_group_link_submission_status(group_name: str):
    """그룹 주간 링크 제출 메시지 삭제"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM group_link_submissions WHERE group_name = ?', (group_name,))
    conn.commit()
    conn.close()

def save_link_submission(group_name: str, user_id: str, week_start: str, links: List[str]):
    """링크 제출 저장 (업데이트 가능)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    links_json = json.dumps(links, ensure_ascii=False)
    
    cursor.execute('''
        INSERT OR REPLACE INTO link_submission_data
        (group_name, user_id, week_start, links, submitted_at, updated_at)
        VALUES (?, ?, ?, ?, 
                COALESCE((SELECT submitted_at FROM link_submission_data WHERE group_name = ? AND user_id = ? AND week_start = ?), ?),
                ?)
    ''', (group_name, user_id, week_start, links_json, group_name, user_id, week_start, now, now))
    
    conn.commit()
    conn.close()

def get_link_submissions(group_name: str, week_start: str) -> List[Dict]:
    """특정 그룹/주차의 모든 링크 제출 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM link_submission_data
        WHERE group_name = ? AND week_start = ?
        ORDER BY updated_at DESC
    ''', (group_name, week_start))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        data = dict(row)
        data['links'] = json.loads(data['links'])
        result.append(data)
    return result

def get_user_link_submission(group_name: str, user_id: str, week_start: str) -> Optional[Dict]:
    """특정 사용자의 링크 제출 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM link_submission_data
        WHERE group_name = ? AND user_id = ? AND week_start = ?
    ''', (group_name, user_id, week_start))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        data = dict(row)
        data['links'] = json.loads(data['links'])
        return data
    return None

def delete_link_submissions_by_week(group_name: str, week_start: str):
    """특정 그룹/주차의 모든 링크 제출 삭제"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM link_submission_data WHERE group_name = ? AND week_start = ?',
                   (group_name, week_start))
    conn.commit()
    conn.close()

def get_weekly_status_message(role_name: str) -> Optional[Dict]:
    """주간 현황 메시지 가져오기"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM weekly_status_messages WHERE role_name = ?', (role_name,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def delete_weekly_status_message(role_name: str):
    """주간 현황 메시지 삭제"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM weekly_status_messages WHERE role_name = ?', (role_name,))
    conn.commit()
    conn.close()

# ==================== 호환성 함수 (기존 JSON 방식과 호환) ====================

def load_data() -> Dict:
    """기존 JSON 방식과 호환되는 데이터 로드"""
    # SQLite에서 데이터를 읽어서 JSON 형식으로 변환
    users = {}
    conn = get_connection()
    cursor = conn.cursor()
    
    # 사용자 정보
    cursor.execute('SELECT * FROM users')
    for row in cursor.fetchall():
        user_id = row['user_id']
        user_roles = get_user_roles(user_id)
        blog_links = get_user_blog_links(user_id)
        submissions = get_user_submissions(user_id)
        
        # submissions를 assignment_id별로 그룹화
        submissions_dict = {}
        for sub in submissions:
            aid = sub['assignment_id']
            if aid not in submissions_dict:
                submissions_dict[aid] = []
            submissions_dict[aid].append({
                'type': sub['type'],
                'content': sub['content'],
                'problem_id': sub['problem_id'],
                'verified': bool(sub['verified']),
                'submitted_at': sub['submitted_at']
            })
        
        users[user_id] = {
            'username': row['username'],
            'boj_handle': row['boj_handle'],
            'roles': user_roles,
            'tistory_links': [{'link': link['link'], 'submitted_at': link['submitted_at']} for link in blog_links],
            'submissions': submissions_dict
        }
    
    # 역할 토큰
    role_tokens = get_all_role_tokens()
    role_tokens_dict = {}
    for role_name, token_data in role_tokens.items():
        role_tokens_dict[role_name] = {
            'token_hash': token_data['token_hash'],
            'original_token': token_data['original_token']
        }
    
    # 스터디 및 과제
    studies = {}
    cursor.execute('SELECT study_name FROM studies')
    for row in cursor.fetchall():
        study_name = row['study_name']
        assignments = get_study_assignments(study_name)
        studies[study_name] = {'assignments': assignments}
    
    conn.close()
    
    return {
        'users': users,
        'submissions': {},  # 호환성
        'role_tokens': role_tokens_dict,
        'studies': studies
    }

def save_data(data: Dict):
    """기존 JSON 방식과 호환되는 데이터 저장"""
    # JSON 데이터를 SQLite에 저장
    # 사용자 정보
    for user_id, user_data in data.get('users', {}).items():
        create_or_update_user(
            user_id,
            user_data.get('username', ''),
            user_data.get('boj_handle')
        )
        
        # 역할
        for role_name in user_data.get('roles', []):
            add_user_role(user_id, role_name)
        
        # 블로그 링크
        for link_data in user_data.get('tistory_links', []):
            if isinstance(link_data, dict):
                add_blog_link(user_id, link_data['link'])
            else:
                add_blog_link(user_id, link_data)
        
        # 제출 (submissions는 별도로 처리)
        for assignment_id, submissions in user_data.get('submissions', {}).items():
            for sub in submissions:
                add_submission(
                    user_id,
                    assignment_id,
                    sub.get('type', '블로그'),
                    sub.get('content') or sub.get('link'),
                    sub.get('problem_id'),
                    sub.get('verified', False)
                )
    
    # 역할 토큰
    for role_name, token_data in data.get('role_tokens', {}).items():
        save_role_token(
            role_name,
            token_data.get('token_hash', ''),
            token_data.get('original_token', '')
        )
    
    # 스터디 및 과제
    for study_name, study_data in data.get('studies', {}).items():
        create_study(study_name)
        for assignment_id, assignment in study_data.get('assignments', {}).items():
            # 과제가 이미 존재하는지 확인
            existing = get_assignment(assignment_id)
            if existing:
                # 존재하면 업데이트만 수행 (제출은 다시 저장하지 않음)
                update_assignment(
                    assignment_id,
                    name=assignment.get('name', ''),
                    config=assignment.get('config', {})
                )
            else:
                # 존재하지 않으면 생성
                create_assignment(
                    assignment_id,
                    study_name,
                    assignment.get('type', ''),
                    assignment.get('name', ''),
                    assignment.get('config', {}),
                    assignment.get('created_by', '')
                )

