"""
백준 웹 크롤링 모듈
백준 프로필 및 문제풀이 정보를 가져옵니다.
"""

import aiohttp
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional

class BaekjoonCrawler:
    """백준 크롤러 클래스"""
    
    @staticmethod
    async def get_user_profile(baekjoon_id: str) -> Optional[Dict]:
        """
        백준 사용자 프로필 정보 가져오기
        
        Args:
            baekjoon_id: 백준 아이디
            
        Returns:
            프로필 정보 딕셔너리 또는 None
        """
        try:
            url = f"https://www.acmicpc.net/user/{baekjoon_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url) as response:
                    if response.status == 404:
                        return None
                    if response.status != 200:
                        return None
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # 해결한 문제 수 추출
                    solved_count = 0
                    solved_elem = soup.find('span', string=re.compile('맞은 문제'))
                    if solved_elem:
                        parent = solved_elem.find_parent()
                        if parent:
                            count_elem = parent.find('span', class_='badge')
                            if count_elem:
                                solved_count = int(count_elem.text.strip())
                    
                    # 시도했지만 맞지 못한 문제 수
                    tried_count = 0
                    tried_elem = soup.find('span', string=re.compile('시도했지만 맞지 못한 문제'))
                    if tried_elem:
                        parent = tried_elem.find_parent()
                        if parent:
                            count_elem = parent.find('span', class_='badge')
                            if count_elem:
                                tried_count = int(count_elem.text.strip())
                    
                    # 등급 정보 (solved.ac 연동)
                    tier = None
                    tier_elem = soup.find('img', {'alt': re.compile('tier')})
                    if tier_elem:
                        tier = tier_elem.get('alt', '').replace('tier ', '')
                    
                    return {
                        'baekjoon_id': baekjoon_id,
                        'solved_count': solved_count,
                        'tried_count': tried_count,
                        'tier': tier,
                        'profile_url': url
                    }
        except Exception as e:
            print(f"백준 프로필 크롤링 오류: {e}")
            return None
    
    @staticmethod
    async def get_solved_problems(baekjoon_id: str, limit: int = 100) -> List[int]:
        """
        해결한 문제 번호 목록 가져오기
        
        Args:
            baekjoon_id: 백준 아이디
            limit: 가져올 최대 문제 수
            
        Returns:
            문제 번호 리스트
        """
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
                    
                    # 해결한 문제 섹션 찾기
                    solved_problems = []
                    
                    # 문제 번호가 있는 링크 찾기
                    problem_links = soup.find_all('a', href=re.compile(r'/problem/\d+'))
                    for link in problem_links:
                        href = link.get('href', '')
                        match = re.search(r'/problem/(\d+)', href)
                        if match:
                            problem_num = int(match.group(1))
                            if problem_num not in solved_problems:
                                solved_problems.append(problem_num)
                            if len(solved_problems) >= limit:
                                break
                    
                    return solved_problems[:limit]
        except Exception as e:
            print(f"백준 문제 목록 크롤링 오류: {e}")
            return []
    
    @staticmethod
    async def verify_user_exists(baekjoon_id: str) -> bool:
        """
        백준 사용자 존재 여부 확인
        
        Args:
            baekjoon_id: 백준 아이디
            
        Returns:
            사용자 존재 여부
        """
        profile = await BaekjoonCrawler.get_user_profile(baekjoon_id)
        return profile is not None
    
    @staticmethod
    async def get_recent_solved(baekjoon_id: str, count: int = 10) -> List[int]:
        """
        최근 해결한 문제 목록 가져오기
        
        Args:
            baekjoon_id: 백준 아이디
            count: 가져올 문제 수
            
        Returns:
            최근 해결한 문제 번호 리스트
        """
        solved = await BaekjoonCrawler.get_solved_problems(baekjoon_id, limit=count)
        return solved[:count]

