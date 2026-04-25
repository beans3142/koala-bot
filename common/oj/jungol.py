"""Jungol 풀이 확인 — DB 캐시 조회 (Playwright 스크래퍼가 일별 갱신).

풀이현황 시간 갱신 시에는 이 함수만 호출 (DB 읽기 only).
실제 크롤링은 jungol_scraper.scrape_jungol_problems() 가 새벽에 1회 수행.
"""
from typing import List, Set
from common.database import is_handle_solved_jungol


async def get_solved(handle: str, problem_ids: List[str]) -> Set[str]:
    """
    Jungol 핸들로 AC 받은 problem_id set 반환 (캐시 기반).
    캐시는 일별 갱신되므로 최대 24h 지연.
    """
    if not handle or not problem_ids:
        return set()
    return {pid for pid in problem_ids if is_handle_solved_jungol(handle, str(pid))}
