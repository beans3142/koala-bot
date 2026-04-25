"""AtCoder 풀이 확인 — kenkoooo Atcoder Problems API (외부 의존)"""
import aiohttp
from typing import List, Set
from common.logger import get_logger

logger = get_logger()

API_URL = "https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions"


async def get_solved(handle: str, problem_ids: List[str]) -> Set[str]:
    """
    AtCoder 핸들로 AC 받은 task_id set 반환.
    problem_id 형식: task_id (예: "abc100_a")
    kenkoooo API 다운 시 빈 set 반환 (graceful).
    """
    if not handle or not problem_ids:
        return set()

    target = set(problem_ids)

    params = {"user": handle, "from_second": 0}
    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(API_URL, params=params) as r:
                if r.status != 200:
                    logger.warning(f"[oj.atcoder] HTTP {r.status} for {handle}")
                    return set()
                submissions = await r.json()
    except Exception as e:
        logger.warning(f"[oj.atcoder] {handle} fetch 실패: {e}")
        return set()

    solved = set()
    for sub in submissions or []:
        if sub.get("result") != "AC":
            continue
        pid = sub.get("problem_id")
        if pid and pid in target:
            solved.add(pid)
    return solved
