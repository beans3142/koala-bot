"""
백준 관련 유틸리티 함수
"""
import aiohttp
from bs4 import BeautifulSoup
import re
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone

# solved.ac tier 매핑 (숫자 -> 이름)
TIER_MAPPING = {
    0: "Unrated",
    1: "Bronze V", 2: "Bronze IV", 3: "Bronze III", 4: "Bronze II", 5: "Bronze I",
    6: "Silver V", 7: "Silver IV", 8: "Silver III", 9: "Silver II", 10: "Silver I",
    11: "Gold V", 12: "Gold IV", 13: "Gold III", 14: "Gold II", 15: "Gold I",
    16: "Platinum V", 17: "Platinum IV", 18: "Platinum III", 19: "Platinum II", 20: "Platinum I",
    21: "Diamond V", 22: "Diamond IV", 23: "Diamond III", 24: "Diamond II", 25: "Diamond I",
    26: "Ruby V", 27: "Ruby IV", 28: "Ruby III", 29: "Ruby II", 30: "Ruby I",
}

def tier_to_number(tier_name: str) -> Optional[int]:
    """티어 이름을 숫자로 변환 (예: "Gold II" -> 14, "G2" -> 14)"""
    # 짧은 형식 처리 (예: "B5", "S1", "G2", "P3", "D4", "R5")
    if len(tier_name) == 2 and tier_name[0].isalpha() and tier_name[1].isdigit():
        tier_letter = tier_name[0].upper()
        level = int(tier_name[1])
        
        # 티어 매핑
        tier_map = {
            'B': 'Bronze',
            'S': 'Silver',
            'G': 'Gold',
            'P': 'Platinum',
            'D': 'Diamond',
            'R': 'Ruby'
        }
        
        if tier_letter in tier_map:
            tier_base = tier_map[tier_letter]
            # 레벨을 로마 숫자로 변환 (5=V, 4=IV, 3=III, 2=II, 1=I)
            level_map = {5: 'V', 4: 'IV', 3: 'III', 2: 'II', 1: 'I'}
            tier_full = f"{tier_base} {level_map.get(level, '')}"
            
            for num, name in TIER_MAPPING.items():
                if name == tier_full:
                    return num
    
    # 기존 형식 처리 (예: "Gold II")
    for num, name in TIER_MAPPING.items():
        if name == tier_name:
            return num
    return None

def number_to_tier(tier_num: int) -> str:
    """숫자를 티어 이름으로 변환 (예: 14 -> "Gold II")"""
    return TIER_MAPPING.get(tier_num, "Unknown")

def number_to_tier_short(tier_num: int) -> str:
    """숫자를 짧은 티어 형식으로 변환 (예: 14 -> "G2", 1 -> "B5")
    
    형식: 티어 앞글자 + 난이도 숫자
    - Bronze V~I -> B5~B1
    - Silver V~I -> S5~S1
    - Gold V~I -> G5~G1
    - Platinum V~I -> P5~P1
    - Diamond V~I -> D5~D1
    - Ruby V~I -> R5~R1
    """
    if tier_num == 0:
        return "Unrated"
    
    tier_name = TIER_MAPPING.get(tier_num, "Unknown")
    if tier_name == "Unknown":
        return "Unknown"
    
    # 티어 앞글자 추출
    tier_letter = tier_name[0]
    
    # 난이도 숫자 계산 (V=5, IV=4, III=3, II=2, I=1)
    if "V" in tier_name:
        level = 5
    elif "IV" in tier_name:
        level = 4
    elif "III" in tier_name:
        level = 3
    elif "II" in tier_name:
        level = 2
    elif "I" in tier_name:
        level = 1
    else:
        return tier_name
    
    return f"{tier_letter}{level}"

async def get_problem_tier(problem_id: int) -> Optional[int]:
    """문제의 티어 정보 가져오기 (solved.ac)"""
    try:
        url = f"https://solved.ac/api/v3/problem/show?problemId={problem_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    level = data.get('level', 0)
                    return level
        return None
    except Exception as e:
        print(f"티어 정보 가져오기 오류: {e}")
        return None

async def get_user_solved_problems(baekjoon_id: str, start_date: datetime = None) -> List[int]:
    """사용자가 해결한 문제 목록 가져오기 (날짜 필터링 가능)"""
    try:
        url = f"https://www.acmicpc.net/user/{baekjoon_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # 해결한 문제 목록 추출
                solved_problems = []
                problem_panels = soup.find_all('div', class_='problem-list')
                
                for panel in problem_panels:
                    problem_links = panel.find_all('a', href=re.compile(r'/problem/\d+'))
                    for link in problem_links:
                        problem_id = int(re.search(r'/problem/(\d+)', link['href']).group(1))
                        solved_problems.append(problem_id)
                
                # 날짜 필터링이 필요한 경우 (추후 구현)
                # 현재는 전체 목록 반환
                return solved_problems
    except Exception as e:
        print(f"해결한 문제 목록 가져오기 오류: {e}")
        return []

async def verify_user_exists(baekjoon_id: str) -> bool:
    """
    백준(BOJ) 사용자 존재 여부 확인

    기존에는 acmicpc.net 프로필 페이지(HTML)를 직접 조회했지만,
    현재 서버 IP가 BOJ 쪽에서 403으로 차단된 상태라 solved.ac API로 대체한다.

    solved.ac 문서 기준:
      - GET /api/v3/user/show?handle={handle}
      - 200: 사용자 존재
      - 404: 사용자 없음
    """
    try:
        url = f"https://solved.ac/api/v3/user/show?handle={baekjoon_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return True
                if response.status == 404:
                    return False
                # 기타 상태코드는 보수적으로 False 처리
                return False
    except Exception as e:
        print(f"solved.ac 사용자 확인 오류: {e}")
        return False

async def check_problem_solved(baekjoon_id: str, problem_id: int) -> bool:
    """특정 문제를 해결했는지 확인 (status 페이지에서 확인)"""
    result = await check_problem_solved_from_status(baekjoon_id, problem_id)
    return result['solved'] if result else False

async def get_weekly_solved_count(baekjoon_id: str, start_date: datetime, end_date: datetime) -> Dict:
    """
    특정 기간 동안 해결한 문제 수 및 문제 목록 가져오기

    기존 구현은 BOJ status 페이지(HTML)를 여러 페이지 크롤링했지만,
    현재 서버 IP가 BOJ에서 403이기 때문에 solved.ac의 user history API로 대체한다.

    solved.ac history API:
      - GET /api/v3/user/history?handle={handle}&topic=solvedCount
      - 응답: 날짜별 누적 solvedCount 목록
        예시: [{ "date": "2025-12-30", "value": 2044 }, ...]

    누적 값이므로,
      기간 [start, end] 에 푼 문제 수 = value(end) - value(start - 1일)
    으로 계산한다.
    """
    try:
        url = f"https://solved.ac/api/v3/user/history?handle={baekjoon_id}&topic=solvedCount"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return {'count': 0, 'problems': []}

                data = await response.json()

        # solved.ac history API 응답 형식:
        # [{"timestamp": "2021-09-12T04:37:27.000Z", "value": 445}, ...]
        # timestamp는 ISO 8601(UTC) 형식이며, 같은 날에 여러 항목이 있을 수 있다.
        # 여기서는 시각 단위 누적값을 그대로 사용해 주어진 시각 범위로 정확히 잘라낸다.
        history = []  # [(dt_utc, value)]
        for entry in data:
            timestamp_str = entry.get('timestamp')
            value = entry.get('value')
            if not timestamp_str or value is None:
                continue
            try:
                # "2021-09-12T04:37:27.000Z" 형식 → UTC naive datetime
                dt = datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                ).replace(tzinfo=None)
                v = int(value)
                history.append((dt, v))
            except Exception:
                continue

        if not history:
            return {'count': 0, 'problems': []}

        # 시각 순 정렬
        history.sort(key=lambda x: x[0])

        # channel.py 에서는 KST(UTC+9) 기준 start/end 를 넘기므로,
        # 비교를 위해 UTC 로 변환해서 사용한다.
        def to_utc(dt: datetime) -> datetime:
            if dt.tzinfo is not None:
                # timezone-aware면 UTC로 변환
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                # timezone-naive면 9시간 빼기 (KST → UTC)
                return dt - timedelta(hours=9)

        start_utc = to_utc(start_date)
        end_utc = to_utc(end_date)

        def cumulative_before(target_dt: datetime, inclusive: bool) -> int:
            """
            target_dt 이전(또는 이하)까지의 누적 solvedCount.
            history 는 시간 증가에 따라 value 가 증가/유지되는 누적값 시계열이라고 가정.
            """
            last_val = 0
            for dt, v in history:
                if dt < target_dt or (inclusive and dt <= target_dt):
                    last_val = v
                else:
                    break
            return last_val

        # 시작 시각 직전까지의 누적과 종료 시각까지의 누적 차이로 기간 내 풀이 수 계산
        total_before = cumulative_before(start_utc, inclusive=False)
        total_end = cumulative_before(end_utc, inclusive=True)

        count = max(0, total_end - total_before)

        # solved.ac history로는 개별 문제 번호까지는 알 수 없으므로,
        # count만 채우고 problems 리스트는 비워둔다.
        return {
            'count': count,
            'problems': []
        }
    except Exception as e:
        print(f"주간 해결한 문제 수 조회 오류(solved.ac): {e}")
        return {'count': 0, 'problems': []}

async def get_free_proxies(max_proxies: int = 20) -> List[str]:
    """
    free-proxy-list.net에서 무료 프록시 목록 가져오기
    
    Args:
        max_proxies: 가져올 최대 프록시 수
    
    Returns:
        프록시 URL 리스트 (예: ['http://123.45.67.89:8080', ...])
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        proxies = []
        async with aiohttp.ClientSession(headers=headers) as session:
            # free-proxy-list.net의 프록시 목록 페이지
            url = "https://free-proxy-list.net/"
            
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"[프록시 목록] HTTP {response.status} 에러")
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # 프록시 테이블 찾기
                table = soup.find('table', class_='table table-striped table-bordered')
                if not table:
                    # 다른 가능한 테이블 선택자 시도
                    table = soup.find('table', id='proxylisttable')
                
                if not table:
                    print("[프록시 목록] 프록시 테이블을 찾을 수 없음")
                    return []
                
                tbody = table.find('tbody')
                if not tbody:
                    return []
                
                rows = tbody.find_all('tr')
                for row in rows[:max_proxies]:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        try:
                            ip = cells[0].get_text(strip=True)
                            port = cells[1].get_text(strip=True)
                            
                            # IP와 포트가 유효한지 확인
                            if ip and port and port.isdigit():
                                proxy_url = f"http://{ip}:{port}"
                                proxies.append(proxy_url)
                        except:
                            continue
        
        print(f"[프록시 목록] {len(proxies)}개의 프록시 가져옴")
        return proxies
    except Exception as e:
        print(f"[프록시 목록] 오류: {e}")
        return []

async def test_proxy(proxy_url: str, test_url: str = "https://www.acmicpc.net/", timeout: int = 5) -> bool:
    """
    프록시가 작동하는지 테스트
    
    Args:
        proxy_url: 프록시 URL (예: 'http://123.45.67.89:8080')
        test_url: 테스트할 URL
        timeout: 타임아웃 (초)
    
    Returns:
        프록시가 작동하면 True
    """
    try:
        from aiohttp import ProxyConnector
        import asyncio
        
        connector = ProxyConnector.from_url(proxy_url)
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout_obj) as session:
            async with session.get(test_url) as response:
                if response.status == 200:
                    return True
                return False
    except asyncio.TimeoutError:
        return False
    except Exception as e:
        return False

async def get_weekly_solved_from_boj_status(baekjoon_id: str, start_date: datetime, end_date: datetime) -> Dict:
    """
    백준 status 페이지에서 직접 크롤링하여 특정 기간 동안 해결한 문제 수 및 문제 목록 가져오기
    
    URL 패턴: https://www.acmicpc.net/status?user_id={baekjoon_id}&result_id=4&top={top}
    top 파라미터는 제출 ID를 사용하여 페이지네이션을 수행합니다.
    
    주의: 클라우드 환경에서 403 FORBIDDEN이 발생할 수 있습니다.
    이 경우 solved.ac API로 폴백하거나, 프록시 사용을 고려하세요.
    
    Args:
        baekjoon_id: 백준 아이디
        start_date: 시작 날짜 (datetime)
        end_date: 종료 날짜 (datetime)
    
    Returns:
        {'count': int, 'problems': List[int]}
    """
    try:
        solved_problems = set()
        # 더 정교한 헤더 설정 (403 우회 시도)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Referer': 'https://www.acmicpc.net/',
        }
        
        import asyncio
        
        # 프록시 설정 (환경변수에서 읽기, 없으면 자동 프록시 사용)
        proxy = os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY')
        
        # 백준 크롤링은 항상 자동 프록시 모드 사용 (환경변수 프록시가 없는 경우)
        # 환경변수에 프록시가 없으면 자동으로 무료 프록시 목록에서 가져와서 사용
        if not proxy:
            print("[백준 크롤링] 자동 프록시 모드 활성화 - 프록시 목록 가져오는 중...")
            free_proxies = await get_free_proxies(max_proxies=10)
            
            # 프록시 테스트 및 선택
            working_proxy = None
            for proxy_url in free_proxies:
                print(f"[백준 크롤링] 프록시 테스트 중: {proxy_url}")
                if await test_proxy(proxy_url):
                    working_proxy = proxy_url
                    print(f"[백준 크롤링] ✅ 작동하는 프록시 발견: {working_proxy}")
                    break
                await asyncio.sleep(0.5)  # 테스트 간 딜레이
            
            if working_proxy:
                proxy = working_proxy
            else:
                print("[백준 크롤링] ⚠️ 작동하는 프록시를 찾을 수 없음 - 프록시 없이 시도")
        
        connector = None
        if proxy:
            try:
                from aiohttp import ProxyConnector
                connector = ProxyConnector.from_url(proxy)
                print(f"[백준 크롤링] 프록시 사용: {proxy}")
            except Exception as e:
                print(f"[백준 크롤링] 프록시 설정 오류: {e}")
        
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            # 첫 페이지는 top 파라미터 없이 시작
            top = None
            max_pages = 50  # 최대 50페이지까지 확인 (약 5000개 제출)
            page_count = 0
            
            while page_count < max_pages:
                # result_id=4는 "맞았습니다" 결과
                if top is None:
                    url = f"https://www.acmicpc.net/status?user_id={baekjoon_id}&result_id=4"
                else:
                    url = f"https://www.acmicpc.net/status?user_id={baekjoon_id}&result_id=4&top={top}"
                
                async with session.get(url) as response:
                    # 403 FORBIDDEN 에러 처리
                    if response.status == 403:
                        print(f"[백준 크롤링] 403 FORBIDDEN 에러 발생 - IP 차단 가능성")
                        # 첫 번째 요청에서 403이면 전체 실패로 처리
                        if page_count == 0:
                            print(f"[백준 크롤링] solved.ac API로 폴백 시도...")
                            # solved.ac로 폴백 (문제 번호는 없지만 개수는 알 수 있음)
                            fallback_result = await get_weekly_solved_count(baekjoon_id, start_date, end_date)
                            return fallback_result
                        break
                    
                    if response.status != 200:
                        print(f"[백준 크롤링] HTTP {response.status} 에러")
                        break
                    
                    html = await response.text()
                    
                    # AWS WAF 챌린지 페이지 확인
                    if 'awsWafCookieDomainList' in html or 'gokuProps' in html:
                        print(f"[백준 크롤링] AWS WAF 챌린지 페이지 감지")
                        if page_count == 0:
                            # 첫 페이지에서 WAF 감지되면 폴백
                            print(f"[백준 크롤링] solved.ac API로 폴백 시도...")
                            fallback_result = await get_weekly_solved_count(baekjoon_id, start_date, end_date)
                            return fallback_result
                        await asyncio.sleep(5)  # WAF 챌린지 대기
                        continue
                    
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # status 테이블 찾기
                    status_table = soup.find('table', id='status-table')
                    if not status_table:
                        break
                    
                    tbody = status_table.find('tbody')
                    if not tbody:
                        break
                    
                    rows = tbody.find_all('tr')
                    if not rows:
                        break
                    
                    # 이 페이지의 모든 제출이 기간을 벗어나면 중단
                    page_has_valid = False
                    last_submission_id = None
                    
                    for tr in rows:
                        # 제출 ID 찾기 (다음 페이지를 위한 top 값)
                        # 백준 status 페이지에서 첫 번째 td가 제출 번호입니다
                        tds = tr.find_all('td')
                        if tds and len(tds) > 0:
                            try:
                                # 첫 번째 td의 텍스트가 제출 번호
                                submission_id = int(tds[0].get_text(strip=True))
                                if last_submission_id is None or submission_id < last_submission_id:
                                    last_submission_id = submission_id
                            except:
                                pass
                        
                        # 결과 확인
                        result_td = tr.find('td', class_='result')
                        if not result_td:
                            continue
                        
                        result_text = result_td.get_text(strip=True)
                        if '맞았습니다' not in result_text:
                            continue
                        
                        # 제출 시간 찾기
                        time_td = tr.find('td', class_='real-time-update')
                        if not time_td:
                            time_elem = tr.find('a', class_='real-time-update')
                            if time_elem and time_elem.get('title'):
                                time_str = time_elem.get('title')
                            else:
                                continue
                        else:
                            time_str = time_td.get_text(strip=True)
                        
                        # 시간 파싱
                        try:
                            if '-' in time_str and ':' in time_str:
                                # "2024-01-01 12:34:56" 형식
                                submitted_dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                            else:
                                # 상대 시간인 경우 현재 시간 사용 (정확하지 않을 수 있음)
                                continue
                        except:
                            continue
                        
                        # 기간 확인
                        if start_date <= submitted_dt <= end_date:
                            # 문제 번호 찾기
                            problem_link = tr.find('a', href=re.compile(r'/problem/\d+'))
                            if problem_link:
                                match = re.search(r'/problem/(\d+)', problem_link.get('href', ''))
                                if match:
                                    problem_id = int(match.group(1))
                                    solved_problems.add(problem_id)
                                    page_has_valid = True
                        elif submitted_dt < start_date:
                            # 시작 날짜보다 이전이면 더 이상 확인할 필요 없음
                            # (페이지는 최신순이므로)
                            return {
                                'count': len(solved_problems),
                                'problems': sorted(list(solved_problems))
                            }
                    
                    # 다음 페이지를 위한 top 값 설정
                    if last_submission_id is not None:
                        top = last_submission_id
                    else:
                        # submission_id를 찾을 수 없으면 첫 번째 행의 제출 번호를 사용
                        if rows:
                            first_row = rows[0]
                            first_tds = first_row.find_all('td')
                            if first_tds and len(first_tds) > 0:
                                try:
                                    top = int(first_tds[0].get_text(strip=True))
                                except:
                                    break
                            else:
                                break
                        else:
                            break
                    
                    # 이 페이지에 유효한 제출이 없으면 더 이상 확인하지 않음
                    if not page_has_valid:
                        break
                    
                    # 요청 간 딜레이 추가 (403 우회 및 Rate limiting 방지)
                    await asyncio.sleep(0.5)
                    
                    page_count += 1
        
        return {
            'count': len(solved_problems),
            'problems': sorted(list(solved_problems))
        }
    except Exception as e:
        print(f"백준 status 페이지 크롤링 오류: {e}")
        return {'count': 0, 'problems': []}

async def get_recent_solved_count(baekjoon_id: str, start_date: datetime, end_date: datetime) -> int:
    """
    특정 기간 동안 해결한 문제 수 가져오기
    
    Args:
        baekjoon_id: 백준 아이디
        start_date: 시작 날짜 (datetime)
        end_date: 종료 날짜 (datetime)
    
    Returns:
        해결한 문제 수
    """
    try:
        # 백준 status 페이지에서 최근 제출 내역 확인
        # 여러 페이지를 확인해야 할 수 있으므로 최근 100개 정도 확인
        solved_problems = set()
        page = 1
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            # 최대 10페이지까지 확인 (최근 1000개 제출)
            for page in range(1, 11):
                url = f"https://www.acmicpc.net/status?user_id={baekjoon_id}&result_id=4&page={page}"
                # result_id=4는 "맞았습니다" 결과
                
                async with session.get(url) as response:
                    if response.status != 200:
                        break
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # status 테이블 찾기
                    status_table = soup.find('table', id='status-table')
                    if not status_table:
                        break
                    
                    tbody = status_table.find('tbody')
                    if not tbody:
                        break
                    
                    rows = tbody.find_all('tr')
                    if not rows:
                        break
                    
                    # 이 페이지의 모든 제출이 기간을 벗어나면 중단
                    page_has_valid = False
                    
                    for tr in rows:
                        # 결과 확인
                        result_td = tr.find('td', class_='result')
                        if not result_td:
                            continue
                        
                        result_text = result_td.get_text(strip=True)
                        if '맞았습니다' not in result_text:
                            continue
                        
                        # 제출 시간 찾기
                        time_td = tr.find('td', class_='real-time-update')
                        if not time_td:
                            time_elem = tr.find('a', class_='real-time-update')
                            if time_elem and time_elem.get('title'):
                                time_str = time_elem.get('title')
                            else:
                                continue
                        else:
                            time_str = time_td.get_text(strip=True)
                        
                        # 시간 파싱
                        try:
                            if '-' in time_str and ':' in time_str:
                                # "2024-01-01 12:34:56" 형식
                                submitted_dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                            else:
                                # 상대 시간인 경우 현재 시간 사용 (정확하지 않을 수 있음)
                                continue
                        except:
                            continue
                        
                        # 기간 확인
                        if start_date <= submitted_dt <= end_date:
                            # 문제 번호 찾기
                            problem_link = tr.find('a', href=re.compile(r'/problem/\d+'))
                            if problem_link:
                                match = re.search(r'/problem/(\d+)', problem_link.get('href', ''))
                                if match:
                                    problem_id = int(match.group(1))
                                    solved_problems.add(problem_id)
                                    page_has_valid = True
                    
                    # 이 페이지에 유효한 제출이 없으면 더 이상 확인하지 않음
                    if not page_has_valid:
                        break
        
        return len(solved_problems)
    except Exception as e:
        print(f"최근 해결한 문제 수 조회 오류: {e}")
        return 0

async def check_problem_solved_from_status(baekjoon_id: str, problem_id: int) -> Optional[Dict]:
    """
    BOJ status 페이지에서 문제 해결 여부 및 제출 시간 확인
    
    Returns:
        {
            'solved': bool,
            'submitted_at': str (ISO format) or None,
            'result': str (결과: '맞았습니다!!', '틀렸습니다', etc.)
        } or None (오류 시)
    """
    try:
        # status 페이지 URL: 문제 번호와 사용자 ID로 필터링
        url = f"https://www.acmicpc.net/status?option-status-pid=on&problem_id={problem_id}&user_id={baekjoon_id}&language_id=-1&result_id=-1&from_problem=1"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # status 테이블 찾기
                status_table = soup.find('table', id='status-table')
                if not status_table:
                    return {'solved': False, 'submitted_at': None, 'result': None}
                
                # 테이블 행 찾기 (첫 번째 행이 가장 최근 제출)
                rows = status_table.find('tbody')
                if not rows:
                    return {'solved': False, 'submitted_at': None, 'result': None}
                
                trs = rows.find_all('tr')
                if not trs:
                    return {'solved': False, 'submitted_at': None, 'result': None}
                
                # 각 행을 확인하여 맞은 제출 찾기
                for tr in trs:
                    # 결과 확인 (맞았습니다!!, 맞았습니다, etc.)
                    result_td = tr.find('td', class_='result')
                    if not result_td:
                        continue
                    
                    result_text = result_td.get_text(strip=True)
                    
                    # 맞은 제출인지 확인
                    if '맞았습니다' in result_text or '정답' in result_text:
                        # 제출 시간 찾기
                        time_td = tr.find('td', class_='real-time-update')
                        if not time_td:
                            # 대체 방법: title 속성에서 시간 찾기
                            time_elem = tr.find('a', class_='real-time-update')
                            if time_elem and time_elem.get('title'):
                                time_str = time_elem.get('title')
                            else:
                                time_str = None
                        else:
                            time_str = time_td.get_text(strip=True)
                        
                        # 시간 파싱 (BOJ 형식: "2024-01-01 12:34:56" 또는 상대 시간)
                        submitted_at = None
                        if time_str:
                            try:
                                # 절대 시간 형식인 경우
                                if '-' in time_str and ':' in time_str:
                                    # "2024-01-01 12:34:56" 형식
                                    submitted_at = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S').isoformat()
                                else:
                                    # 상대 시간인 경우 (예: "1분 전") 현재 시간 사용
                                    submitted_at = datetime.now().isoformat()
                            except:
                                submitted_at = datetime.now().isoformat()
                        
                        return {
                            'solved': True,
                            'submitted_at': submitted_at,
                            'result': result_text
                        }
                
                # 맞은 제출이 없으면 해결하지 않음
                return {'solved': False, 'submitted_at': None, 'result': None}
                
    except Exception as e:
        print(f"status 페이지 확인 오류: {e}")
        return None

async def check_problems_solved_with_tier(baekjoon_id: str, problem_ids: List[int], min_tier: int = None) -> Dict[int, bool]:
    """여러 문제의 해결 여부 확인 (난이도 필터링)"""
    solved_problems = await get_user_solved_problems(baekjoon_id)
    result = {}
    
    for problem_id in problem_ids:
        if problem_id in solved_problems:
            if min_tier is not None:
                tier = await get_problem_tier(problem_id)
                if tier is not None and tier >= min_tier:
                    result[problem_id] = True
                else:
                    result[problem_id] = False
            else:
                result[problem_id] = True
        else:
            result[problem_id] = False
    
    return result

# 백준 로그인 정보 (테스트용 하드코딩)
BOJ_USERNAME = "beans3142"
BOJ_PASSWORD = "d3783556"

async def login_boj(session: aiohttp.ClientSession, next_url: str = None) -> bool:
    """
    백준에 로그인
    
    Args:
        session: aiohttp 세션
        next_url: 로그인 후 리다이렉트할 URL (선택사항)
    
    Returns:
        로그인 성공 여부
    """
    try:
        # 세션 쿠키 완전히 제거
        print(f"[BOJ 로그인] 0단계: 세션 쿠키 제거")
        session.cookie_jar.clear()
        
        # 먼저 로그아웃 시도 (기존 세션 제거)
        logout_url = "https://www.acmicpc.net/logout"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.acmicpc.net/',
        }
        
        print(f"[BOJ 로그인] 0-1단계: 로그아웃 시도")
        try:
            async with session.post(logout_url, headers=headers, allow_redirects=True) as response:
                print(f"[BOJ 로그인] 로그아웃 응답: {response.status}")
                # 로그아웃 후 쿠키 다시 제거
                session.cookie_jar.clear()
        except:
            pass  # 로그아웃 실패해도 계속 진행
        
        # 로그인 페이지 접속하여 CSRF 토큰 가져오기
        # next_url이 있으면 해당 URL로 리다이렉트, 없으면 메인 페이지로
        if next_url:
            # URL 인코딩
            from urllib.parse import quote
            encoded_next = quote(next_url.replace('https://www.acmicpc.net', ''), safe='')
            login_url = f"https://www.acmicpc.net/login?next={encoded_next}"
        else:
            login_url = "https://www.acmicpc.net/login?next=%2F"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Referer': 'https://www.acmicpc.net/'
        }
        
        print(f"[BOJ 로그인] 1단계: 로그인 페이지 접속 시도")
        print(f"[BOJ 로그인] URL: {login_url}")
        print(f"[BOJ 로그인] 사용자: {BOJ_USERNAME}")
        
        # AWS WAF 우회를 위해 약간의 딜레이 추가
        import asyncio
        await asyncio.sleep(1)
        
        async with session.get(login_url, headers=headers, allow_redirects=True) as response:
            print(f"[BOJ 로그인] 1단계 응답 상태: {response.status}")
            print(f"[BOJ 로그인] 응답 URL: {str(response.url)}")
            
            html = await response.text()
            
            # AWS WAF 챌린지 페이지 확인
            if response.status == 202 or 'awsWafCookieDomainList' in html or 'gokuProps' in html:
                print("[BOJ 로그인] ⚠️ AWS WAF 챌린지 페이지 감지됨")
                print(f"[BOJ 로그인] 응답 본문 (처음 500자): {html[:500]}")
                # 챌린지 페이지인 경우, 추가 대기 후 재시도
                print("[BOJ 로그인] 5초 대기 후 재시도...")
                await asyncio.sleep(5)
                async with session.get(login_url, headers=headers, allow_redirects=True) as retry_response:
                    print(f"[BOJ 로그인] 재시도 응답 상태: {retry_response.status}")
                    if retry_response.status != 200:
                        print(f"[BOJ 로그인] 로그인 페이지 접속 실패: HTTP {retry_response.status}")
                        retry_html = await retry_response.text()
                        if 'awsWafCookieDomainList' in retry_html or 'gokuProps' in retry_html:
                            print("[BOJ 로그인] ❌ AWS WAF 챌린지 페이지가 계속 반환됨")
                        return False
                    html = await retry_response.text()
                    if 'awsWafCookieDomainList' in html or 'gokuProps' in html:
                        print("[BOJ 로그인] ❌ AWS WAF 챌린지 페이지가 계속 반환됨")
                        return False
            
            if response.status != 200:
                print(f"[BOJ 로그인] 로그인 페이지 접속 실패: HTTP {response.status}")
                try:
                    print(f"[BOJ 로그인] 응답 본문 (처음 500자): {html[:500]}")
                except:
                    pass
                return False
            
            print(f"[BOJ 로그인] HTML 크기: {len(html)} bytes")
            soup = BeautifulSoup(html, 'html.parser')
            
            # 이미 로그인된 상태인지 확인 (로그아웃 링크나 사용자 정보 확인)
            is_already_logged_in = False
            logout_link = soup.find('a', href='/logout')
            logout_form = soup.find('form', {'action': '/logout'})
            
            if logout_link or logout_form:
                print("[BOJ 로그인] ⚠️ 로그아웃 링크/폼 발견 - 이미 로그인된 상태일 수 있음")
                # 실제로 로그인되어 있는지 확인
                if BOJ_USERNAME in html or '로그아웃' in html or 'logout' in html.lower():
                    print("[BOJ 로그인] ✅ 실제로 로그인되어 있음 - 로그인 과정 생략")
                    is_already_logged_in = True
                    # 메인 페이지로 이동하여 최종 확인
                    try:
                        async with session.get("https://www.acmicpc.net/", headers=headers, allow_redirects=True) as test_response:
                            test_html = await test_response.text()
                            if BOJ_USERNAME in test_html or ('로그아웃' in test_html and 'login_user_id' not in test_html):
                                print("[BOJ 로그인] ✅ 메인 페이지에서 로그인 상태 확인됨")
                                return True
                            else:
                                print("[BOJ 로그인] ⚠️ 메인 페이지에서 로그인 상태 확인 실패 - 로그인 시도")
                                is_already_logged_in = False
                    except:
                        print("[BOJ 로그인] ⚠️ 메인 페이지 확인 실패 - 로그인 시도")
                        is_already_logged_in = False
            
            # 로그인 폼 찾기
            login_form = soup.find('form', {'action': '/login'}) or soup.find('form', {'method': 'post'}) or soup.find('form')
            form_action = '/login'  # 기본값
            form_method = 'post'
            
            if not is_already_logged_in:
                if login_form:
                    form_action = login_form.get('action', '/login')
                    form_method = login_form.get('method', 'post').lower()
                    print(f"[BOJ 로그인] 로그인 폼 발견: action={form_action}, method={form_method}")
                    
                    # action이 상대 경로면 절대 경로로 변환
                    if form_action and not form_action.startswith('http'):
                        if form_action.startswith('/'):
                            form_action = f"https://www.acmicpc.net{form_action}"
                        else:
                            form_action = f"https://www.acmicpc.net/login"
                    
                    # action이 /logout이면 로그인 폼이 아님
                    if '/logout' in form_action:
                        print("[BOJ 로그인] ⚠️ 로그인 폼이 아닌 것으로 보임. 기본값 사용: /login")
                        form_action = "https://www.acmicpc.net/login"
                else:
                    print("[BOJ 로그인] ⚠️ 로그인 폼을 찾을 수 없음 - 기본값 사용: /login")
                    form_action = "https://www.acmicpc.net/login"
            
            # CSRF 토큰 찾기 (여러 방법 시도)
            csrf_token = None
            
            # 방법 1: name='csrf_key'인 input 찾기
            csrf_input = soup.find('input', {'name': 'csrf_key'})
            if csrf_input:
                csrf_token = csrf_input.get('value')
                if csrf_token:
                    print(f"[BOJ 로그인] CSRF 토큰 찾음 (방법1): {csrf_token[:30]}... (전체 길이: {len(csrf_token)})")
            
            # 방법 2: name='csrf_token'인 input 찾기
            if not csrf_token:
                csrf_input = soup.find('input', {'name': 'csrf_token'})
                if csrf_input:
                    csrf_token = csrf_input.get('value')
                    if csrf_token:
                        print(f"[BOJ 로그인] CSRF 토큰 찾음 (방법2): {csrf_token[:30]}... (전체 길이: {len(csrf_token)})")
            
            # 방법 3: meta 태그에서 찾기
            if not csrf_token:
                csrf_meta = soup.find('meta', {'name': 'csrf-token'})
                if csrf_meta:
                    csrf_token = csrf_meta.get('content')
                    if csrf_token:
                        print(f"[BOJ 로그인] CSRF 토큰 찾음 (방법3): {csrf_token[:30]}... (전체 길이: {len(csrf_token)})")
            
            # 방법 4: JavaScript에서 찾기 (일부 사이트는 JS로 동적 생성)
            if not csrf_token:
                scripts = soup.find_all('script')
                for script in scripts:
                    script_text = script.string or ''
                    # csrf 관련 변수 찾기
                    import re
                    csrf_match = re.search(r'csrf[_-]?token["\']?\s*[:=]\s*["\']([^"\']+)["\']', script_text, re.IGNORECASE)
                    if csrf_match:
                        csrf_token = csrf_match.group(1)
                        print(f"[BOJ 로그인] CSRF 토큰 찾음 (방법4-JS): {csrf_token[:30]}... (전체 길이: {len(csrf_token)})")
                        break
            
            if not csrf_token:
                print("[BOJ 로그인] ⚠️ CSRF 토큰을 찾을 수 없음 - CSRF 토큰 없이 시도")
                # 모든 input 태그 찾기
                inputs = soup.find_all('input')
                print(f"[BOJ 로그인] 발견된 input 태그 개수: {len(inputs)}")
                for inp in inputs:
                    name = inp.get('name', '')
                    if 'csrf' in name.lower() or 'token' in name.lower():
                        print(f"[BOJ 로그인]   - name={name}, type={inp.get('type')}, value={inp.get('value', '')[:50]}")
                # CSRF 토큰 없이도 시도 (일부 사이트는 선택적일 수 있음)
                csrf_token = ''  # 빈 문자열로 설정
        
        # 이미 로그인되어 있으면 POST 요청 생략
        if 'is_already_logged_in' in locals() and is_already_logged_in:
            print("[BOJ 로그인] ✅ 이미 로그인되어 있음 - POST 요청 생략")
            return True
        
        # 로그인 POST 요청
        # CSRF 토큰이 있으면 포함, 없으면 제외
        if next_url:
            # next_url이 있으면 해당 경로로 리다이렉트
            next_path = next_url.replace('https://www.acmicpc.net', '')
            login_data = {
                'login_user_id': BOJ_USERNAME,
                'login_password': BOJ_PASSWORD,
                'next': next_path
            }
        else:
            login_data = {
                'login_user_id': BOJ_USERNAME,
                'login_password': BOJ_PASSWORD,
                'next': '/'  # 로그인 후 리다이렉트할 경로
            }
        
        if csrf_token:
            login_data['csrf_key'] = csrf_token
        
        print(f"[BOJ 로그인] 2단계: 로그인 POST 요청 시도")
        print(f"[BOJ 로그인] POST 데이터 키: {list(login_data.keys())}")
        print(f"[BOJ 로그인] 사용자 ID 길이: {len(BOJ_USERNAME)}")
        print(f"[BOJ 로그인] 비밀번호 길이: {len(BOJ_PASSWORD)}")
        
        # POST 요청 헤더 추가
        post_headers = headers.copy()
        post_headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': login_url,
            'Origin': 'https://www.acmicpc.net',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin'
        })
        
        # 실제 로그인 POST URL 사용 (폼의 action)
        post_url = form_action if 'form_action' in locals() and form_action else login_url
        print(f"[BOJ 로그인] POST 요청 URL: {post_url}")
        
        async with session.post(post_url, data=login_data, headers=post_headers, allow_redirects=True) as response:
            print(f"[BOJ 로그인] 2단계 응답 상태: {response.status}")
            print(f"[BOJ 로그인] 응답 URL: {str(response.url)}")
            
            # 응답 헤더 확인
            location = response.headers.get('Location', '')
            set_cookie = response.headers.get('Set-Cookie', '')
            if location:
                print(f"[BOJ 로그인] 리다이렉트 위치: {location}")
            if set_cookie:
                print(f"[BOJ 로그인] Set-Cookie 헤더 발견 (길이: {len(set_cookie)})")
            
            # 응답 본문 확인 (에러 메시지가 있을 수 있음)
            response_text = ""
            try:
                response_text = await response.text()
                if len(response_text) < 2000:  # 짧은 응답만 출력
                    print(f"[BOJ 로그인] 응답 본문: {response_text}")
                else:
                    print(f"[BOJ 로그인] 응답 본문 (처음 1000자): {response_text[:1000]}")
                    # 에러 메시지 찾기
                    if 'error' in response_text.lower() or '실패' in response_text or '틀렸' in response_text or '잘못' in response_text:
                        print(f"[BOJ 로그인] ⚠️ 에러 메시지가 응답에 포함되어 있음")
            except Exception as e:
                print(f"[BOJ 로그인] 응답 본문 읽기 실패: {e}")
            
            # 로그인 성공 여부 판단
            # 1. 리다이렉트 확인 (302는 성공)
            # 2. 응답 본문에 로그인 폼이 없으면 성공 (로그인 페이지가 아니면)
            # 3. 쿠키 확인
            # 4. 실제 로그인 확인 (메인 페이지 접속 테스트)
            success = False
            
            if response.status == 302:
                print(f"[BOJ 로그인] ✅ 로그인 성공 (리다이렉트: {response.status})")
                success = True
            elif response.status == 200:
                # 응답 본문 분석
                if response_text:
                    # 로그인 폼이 있으면 실패, 없으면 성공
                    has_login_form = 'login_user_id' in response_text or 'login_password' in response_text or '<title>로그인</title>' in response_text
                    has_logout_form = 'action="/logout"' in response_text or 'action=\'/logout\'' in response_text
                    
                    if has_logout_form and not has_login_form:
                        print(f"[BOJ 로그인] ✅ 로그인 성공 (로그아웃 폼 발견 - 이미 로그인됨)")
                        success = True
                    elif not has_login_form:
                        print(f"[BOJ 로그인] ✅ 로그인 성공 (로그인 폼 없음)")
                        success = True
                    else:
                        print(f"[BOJ 로그인] ❌ 로그인 실패 (로그인 폼이 여전히 있음)")
                        success = False
                else:
                    # 응답 본문이 없으면 상태 코드만으로 판단
                    print(f"[BOJ 로그인] ⚠️ 응답 본문 없음, 상태 코드로만 판단: {response.status}")
                    success = False
            
            # 쿠키 확인
            cookies = session.cookie_jar
            cookie_count = len(list(cookies))
            print(f"[BOJ 로그인] 세션 쿠키 개수: {cookie_count}")
            if cookie_count > 0:
                print(f"[BOJ 로그인] 쿠키가 설정됨 (로그인 성공 가능성 높음)")
            
            # 실제 로그인 확인 (메인 페이지 접속 테스트)
            if success or cookie_count > 0:
                print(f"[BOJ 로그인] 로그인 확인을 위해 메인 페이지 접속 테스트...")
                try:
                    test_headers = headers.copy()
                    test_headers['Referer'] = 'https://www.acmicpc.net/login'
                    async with session.get("https://www.acmicpc.net/", headers=test_headers, allow_redirects=True) as test_response:
                        test_html = await test_response.text()
                        test_url = str(test_response.url)
                        print(f"[BOJ 로그인] 메인 페이지 응답 URL: {test_url}")
                        
                        # 로그인된 상태면 사용자 정보가 있음
                        has_username = BOJ_USERNAME in test_html
                        has_logout = '로그아웃' in test_html or 'logout' in test_html.lower()
                        has_login_form = 'login_user_id' in test_html or '<title>로그인</title>' in test_html
                        
                        print(f"[BOJ 로그인] 메인 페이지 분석: 사용자명={has_username}, 로그아웃={has_logout}, 로그인폼={has_login_form}")
                        
                        if (has_username or has_logout) and not has_login_form:
                            print(f"[BOJ 로그인] ✅ 실제 로그인 확인됨 (메인 페이지에서 사용자 정보 발견)")
                            success = True
                        elif has_login_form:
                            print(f"[BOJ 로그인] ❌ 실제 로그인 실패 (메인 페이지에 로그인 폼 발견)")
                            success = False
                        else:
                            print(f"[BOJ 로그인] ⚠️ 로그인 상태 불명확")
                except Exception as e:
                    print(f"[BOJ 로그인] 로그인 확인 테스트 실패: {e}")
                    import traceback
                    traceback.print_exc()
            
            if success:
                print(f"[BOJ 로그인] ✅ 최종 판단: 로그인 성공")
            else:
                print(f"[BOJ 로그인] ❌ 최종 판단: 로그인 실패")
            return success
    
    except Exception as e:
        print(f"[BOJ 로그인] ❌ 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

async def get_group_practice_ranking(practice_url: str) -> Dict[str, int]:
    """
    그룹 연습 세션 랭킹에서 사용자별 해결한 문제 수 가져오기
    
    Args:
        practice_url: 연습 세션 URL (예: https://www.acmicpc.net/group/practice/view/9883/122)
    
    Returns:
        {사용자ID: 해결한 문제 수} 딕셔너리
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print(f"[랭킹 크롤링] 연습 세션 URL: {practice_url}")
        async with aiohttp.ClientSession(headers=headers) as session:
            # 먼저 연습 세션 페이지로 접속 시도 (로그인이 필요하면 자동으로 리다이렉트됨)
            print(f"[랭킹 크롤링] 연습 세션 페이지로 먼저 접속 시도: {practice_url}")
            async with session.get(practice_url, headers=headers, allow_redirects=True) as initial_response:
                print(f"[랭킹 크롤링] 초기 접속 응답: {initial_response.status}")
                print(f"[랭킹 크롤링] 초기 접속 최종 URL: {str(initial_response.url)}")
                
                initial_html = await initial_response.text()
                
                # 로그인이 필요한지 확인
                if '로그인' in initial_html and 'login_user_id' in initial_html:
                    print("[랭킹 크롤링] 로그인이 필요함 - 로그인 시도...")
                    # 로그인 시 next 파라미터를 연습 세션 URL로 설정
                    login_success = await login_boj(session, next_url=practice_url)
                    if not login_success:
                        print("[랭킹 크롤링] 백준 로그인 실패")
                        return {}
                    print("[랭킹 크롤링] 로그인 성공 - 연습 세션 페이지로 다시 접속")
                else:
                    print("[랭킹 크롤링] 이미 로그인되어 있거나 로그인 불필요")
                    # 이미 접근 가능한 경우
                    if 'contest_scoreboard' in initial_html:
                        print("[랭킹 크롤링] 랭킹 테이블이 이미 로드됨")
                        # 바로 파싱 진행
                        soup = BeautifulSoup(initial_html, 'html.parser')
                        ranking_table = soup.find('table', id='contest_scoreboard')
                        if ranking_table:
                            # 파싱 로직으로 이동 (아래 코드 재사용)
                            pass
                        else:
                            # 로그인 필요할 수 있음
                            print("[랭킹 크롤링] 로그인 시도...")
                            login_success = await login_boj(session, next_url=practice_url)
                            if not login_success:
                                print("[랭킹 크롤링] 백준 로그인 실패")
                                return {}
                            print("[랭킹 크롤링] 로그인 성공")
            
            # 연습 세션 페이지 접속 (로그인 후 자동 리다이렉트됨)
            print(f"[랭킹 크롤링] 연습 세션 페이지 접속 시도: {practice_url}")
            
            page_headers = headers.copy()
            page_headers['Referer'] = 'https://www.acmicpc.net/'
            page_headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
            page_headers['Accept-Language'] = 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
            
            async with session.get(practice_url, headers=page_headers, allow_redirects=True) as response:
                print(f"[랭킹 크롤링] 페이지 응답: {response.status}")
                print(f"[랭킹 크롤링] 응답 URL: {str(response.url)}")
                
                # 리다이렉트 처리
                if response.status in [301, 302, 303, 307, 308]:
                    location = response.headers.get('Location', '')
                    print(f"[랭킹 크롤링] 리다이렉트 감지: {location}")
                    if location and '/login' in location:
                        print("[랭킹 크롤링] ⚠️ 로그인 페이지로 리다이렉트됨 - 권한 문제 또는 쿠키 문제")
                        # 리다이렉트된 페이지 확인
                        if location.startswith('/'):
                            location = f"https://www.acmicpc.net{location}"
                        async with session.get(location, headers=page_headers, allow_redirects=True) as redirect_response:
                            redirect_html = await redirect_response.text()
                            print(f"[랭킹 크롤링] 리다이렉트 후 최종 URL: {str(redirect_response.url)}")
                            if '로그인' in redirect_html and 'login_user_id' in redirect_html:
                                print("[랭킹 크롤링] ❌ 로그인 페이지로 리다이렉트됨 - 쿠키가 전달되지 않았거나 권한이 없음")
                                return {}
                            html = redirect_html
                    else:
                        # 다른 리다이렉트인 경우 따라가기
                        if location.startswith('/'):
                            location = f"https://www.acmicpc.net{location}"
                        async with session.get(location, headers=page_headers, allow_redirects=True) as redirect_response:
                            response = redirect_response
                            html = await response.text()
                else:
                    html = await response.text()
                
                print(f"[랭킹 크롤링] HTML 크기: {len(html)} bytes")
                soup = BeautifulSoup(html, 'html.parser')
                
                # 로그인 필요 여부 확인
                if '로그인' in html and 'login_user_id' in html:
                    print("[랭킹 크롤링] ⚠️ 로그인이 필요한 페이지로 보임 - 쿠키가 전달되지 않았을 수 있음")
                    print(f"[랭킹 크롤링] HTML 일부 (처음 2000자): {html[:2000]}")
                    # 쿠키 재확인
                    cookies_after = list(session.cookie_jar)
                    print(f"[랭킹 크롤링] 요청 후 쿠키 개수: {len(cookies_after)}")
                    return {}
                
                # 랭킹 테이블 찾기 (여러 방법 시도)
                ranking_table = None
                
                # 방법 1: id="contest_scoreboard"로 찾기 (가장 확실한 방법)
                ranking_table = soup.find('table', id='contest_scoreboard')
                if ranking_table:
                    print("[랭킹 크롤링] 랭킹 테이블 찾음 (id=contest_scoreboard)")
                else:
                    # 방법 2: class에 table이 있는 table 태그 찾기
                    ranking_table = soup.find('table', class_=re.compile(r'table', re.I))
                    if ranking_table:
                        print("[랭킹 크롤링] 랭킹 테이블 찾음 (class로)")
                
                if not ranking_table:
                    # 방법 3: 모든 table 태그 찾기
                    tables = soup.find_all('table')
                    print(f"[랭킹 크롤링] 발견된 table 태그 개수: {len(tables)}")
                    
                    for i, table in enumerate(tables):
                        # tbody가 있고, 여러 행이 있는 테이블 찾기
                        tbody = table.find('tbody')
                        if tbody:
                            rows = tbody.find_all('tr')
                            print(f"[랭킹 크롤링] 테이블 {i+1}: tbody 행 개수 = {len(rows)}")
                            if len(rows) > 0:
                                # 첫 번째 행의 열 개수 확인
                                first_row = rows[0]
                                cols = first_row.find_all(['td', 'th'])
                                print(f"[랭킹 크롤링] 테이블 {i+1}: 첫 번째 행 열 개수 = {len(cols)}")
                                if len(cols) >= 2:  # 최소 2개 열 (랭킹, 아이디)
                                    ranking_table = table
                                    print(f"[랭킹 크롤링] 랭킹 테이블 찾음 (테이블 {i+1})")
                                    break
                
                if not ranking_table:
                    print("[랭킹 크롤링] ❌ 랭킹 테이블을 찾을 수 없음")
                    # HTML 구조 확인
                    # contest_scoreboard 검색
                    if 'contest_scoreboard' in html:
                        print("[랭킹 크롤링] ⚠️ 'contest_scoreboard' 문자열은 HTML에 있지만 테이블을 찾지 못함")
                    # table-responsive div 찾기
                    table_responsive = soup.find('div', class_='table-responsive')
                    if table_responsive:
                        print("[랭킹 크롤링] table-responsive div 발견")
                        tables_in_div = table_responsive.find_all('table')
                        print(f"[랭킹 크롤링] table-responsive 내부 테이블 개수: {len(tables_in_div)}")
                        if tables_in_div:
                            ranking_table = tables_in_div[0]
                            print("[랭킹 크롤링] table-responsive 내부의 첫 번째 테이블 사용")
                    
                    if not ranking_table:
                        print(f"[랭킹 크롤링] HTML 일부 (중간 2000자): {html[len(html)//2:len(html)//2+2000]}")
                        # 모든 div 확인
                        divs = soup.find_all('div', class_=re.compile(r'table|rank|list|practice', re.I))
                        print(f"[랭킹 크롤링] 관련 div 개수: {len(divs)}")
                        return {}
                
                print("[랭킹 크롤링] 랭킹 테이블 찾음")
                
                # 테이블 행 파싱
                result = {}
                rows = ranking_table.find('tbody')
                if rows:
                    trs = rows.find_all('tr')
                    print(f"[랭킹 크롤링] 테이블 행 개수: {len(trs)}")
                    for tr in trs:
                        # th와 td 모두 찾기 (백준은 th를 사용함)
                        cells = tr.find_all(['th', 'td'])
                        if len(cells) < 2:
                            continue
                        
                        # 아이디 찾기 (보통 2번째 열, th 태그 사용)
                        user_id = None
                        # 첫 번째 열은 랭킹, 두 번째 열은 아이디
                        if len(cells) >= 2:
                            user_id_cell = cells[1]
                            # 링크가 있으면 링크 텍스트, 없으면 셀 텍스트
                            link = user_id_cell.find('a')
                            if link:
                                user_id = link.get_text(strip=True)
                                # 이미지 태그 제거
                                user_id = re.sub(r'<img[^>]*>', '', user_id).strip()
                            else:
                                user_id = user_id_cell.get_text(strip=True)
                        
                        if not user_id:
                            continue
                        
                        # 해결한 문제 수 계산 (마지막 열의 숫자)
                        # 형식: "2 / 2868" 또는 "2&nbsp;/&nbsp;2868" -> 2를 추출 (총 해결한 문제 수)
                        solved_count = 0
                        
                        # 마지막 열 확인 (th 또는 td)
                        last_cell = cells[-1]
                        last_cell_text = last_cell.get_text(strip=True)
                        # &nbsp; 제거
                        last_cell_text = last_cell_text.replace('\xa0', ' ').replace('&nbsp;', ' ')
                        match = re.match(r'(\d+)\s*/\s*\d+', last_cell_text)
                        if match:
                            solved_count = int(match.group(1))
                        else:
                            print(f"[랭킹 크롤링] ⚠️ 마지막 열 파싱 실패: '{last_cell_text}'")
                        
                        result[user_id] = solved_count
                        print(f"[랭킹 크롤링] 유저 파싱: {user_id} = {solved_count}개")
                
                print(f"[랭킹 크롤링] 총 {len(result)}명의 유저 데이터 파싱 완료")
                return result
    
    except Exception as e:
        print(f"[랭킹 크롤링] 오류: {e}")
        import traceback
        traceback.print_exc()
        return {}

