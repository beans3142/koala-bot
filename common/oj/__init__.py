"""
OJ별 풀이 확인 통합 인터페이스.

각 OJ는 동일한 인터페이스를 제공:
    async def get_solved(handle: str, problem_ids: list[str]) -> set[str]
"""
from typing import List, Set, Optional, Dict
from common.logger import get_logger

from . import boj, codeforces, atcoder, jungol

logger = get_logger()


SOLVERS = {
    'boj': boj.get_solved,
    'codeforces': codeforces.get_solved,
    'atcoder': atcoder.get_solved,
    'jungol': jungol.get_solved,
}


async def get_solved_for_oj(oj: str, handle: Optional[str], problem_ids: List[str]) -> Set[str]:
    """OJ 이름과 핸들로 푼 문제 set 반환. 핸들이 없거나 OJ 미지원이면 빈 set."""
    if not handle or not problem_ids:
        return set()
    fn = SOLVERS.get(oj)
    if not fn:
        return set()
    try:
        return await fn(handle, problem_ids)
    except Exception as e:
        logger.warning(f"[oj.{oj}] {handle} 풀이 조회 실패: {e}")
        return set()


def is_supported(oj: str) -> bool:
    """해당 OJ가 풀이 자동 확인을 지원하는지.
    Jungol은 캐시 기반(일별 Playwright 갱신) — 캐시가 비어있으면 0/n으로 표시되지만
    OJ 자체는 supported로 취급."""
    return oj in {'boj', 'codeforces', 'atcoder', 'jungol'}
