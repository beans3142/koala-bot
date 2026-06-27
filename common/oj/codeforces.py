"""Codeforces 풀이 확인 — 공식 API user.status"""
import aiohttp
from typing import List, Set, Optional, Dict
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


async def get_contest_solved(handle: str, contest_id: str) -> Optional[Set[str]]:
    """
    특정 CF 대회(contest_id)에서 핸들이 AC 받은 문제 index 집합 반환.

    주간테스트용. 참가 유형(가상/연습/실전) 및 제출 시각은 따지지 않는다.
    그 대회의 문제를 verdict==OK 로 푼 것이면 모두 인정.

    반환:
      - set[str]: 푼 문제 index 집합 (예: {"A", "B"}). 0개면 빈 set.
      - None: API 호출 실패(서버 다운/레이트리밋 등) → 호출측에서 ⚠️ 처리
    """
    if not handle or contest_id is None:
        return None

    target_cid = str(contest_id)
    params = {"handle": handle, "from": 1, "count": 10000}
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(API_URL, params=params) as r:
                data = await r.json(content_type=None)
    except Exception as e:
        logger.warning(f"[oj.codeforces] {handle} contest {target_cid} fetch 실패: {e!r}")
        return None

    if data.get("status") != "OK":
        logger.warning(f"[oj.codeforces] user.status API 에러({handle}): {data.get('comment')}")
        return None

    solved: Set[str] = set()
    for sub in data.get("result", []):
        if sub.get("verdict") != "OK":
            continue
        problem = sub.get("problem", {})
        if str(problem.get("contestId")) != target_cid:
            continue
        index = problem.get("index")
        if index:
            solved.add(index.upper())
    return solved
