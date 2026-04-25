"""Codeforces 풀이 확인 — 공식 API user.status"""
import aiohttp
from typing import List, Set
from common.logger import get_logger

logger = get_logger()

API_URL = "https://codeforces.com/api/user.status"


async def get_solved(handle: str, problem_ids: List[str]) -> Set[str]:
    """
    Codeforces 핸들로 AC 받은 문제 set 반환.
    problem_id 형식: "{contestId}/{index}" (예: "1234/A") 또는 "gym{contestId}/{index}"
    """
    if not handle or not problem_ids:
        return set()

    target = set(p.upper() for p in problem_ids)

    params = {"handle": handle, "from": 1, "count": 10000}
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(API_URL, params=params) as r:
                data = await r.json()
    except Exception as e:
        logger.warning(f"[oj.codeforces] {handle} fetch 실패: {e}")
        return set()

    if data.get("status") != "OK":
        logger.warning(f"[oj.codeforces] API 에러: {data.get('comment')}")
        return set()

    solved = set()
    for sub in data.get("result", []):
        if sub.get("verdict") != "OK":
            continue
        problem = sub.get("problem", {})
        contest_id = problem.get("contestId")
        index = problem.get("index")
        if contest_id is None or not index:
            continue
        # gym 여부는 problemsetName 또는 contestId 범위로 판단하기 까다로움.
        # 사용자가 등록한 problem_id가 'gym...'이면 gym 비교, 아니면 일반 비교
        candidates = {
            f"{contest_id}/{index.upper()}",
            f"gym{contest_id}/{index.upper()}",
        }
        for cand in candidates:
            if cand in target:
                solved.add(cand)
    return solved
