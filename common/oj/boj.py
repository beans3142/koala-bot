"""BOJ 풀이 확인 — solved.ac API 활용 (기존 boj_utils 재사용)"""
from typing import List, Set
from common.boj_utils import get_user_solved_problems_from_solved_ac


async def get_solved(handle: str, problem_ids: List[str]) -> Set[str]:
    """
    BOJ 핸들로 푼 문제 ID set 반환 (str 타입으로 통일).
    problem_ids는 문자열 (예: ['1000', '1001']) — 내부에서 int 변환.
    """
    if not handle or not problem_ids:
        return set()
    target_ints = []
    for pid in problem_ids:
        try:
            target_ints.append(int(pid))
        except (TypeError, ValueError):
            continue
    if not target_ints:
        return set()
    solved = await get_user_solved_problems_from_solved_ac(handle, target_problems=target_ints)
    # 문자열로 통일
    return {str(s) for s in solved}
