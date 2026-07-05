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


async def get_contest_result(handle: str, contest_id: str) -> Optional[dict]:
    """
    한 번의 user.status 호출로 두 가지를 계산:
      - 통과용: 대회에서 AC한 distinct 문제 수 (참가유형·시각 무관)
      - 랭킹용: 가상참가(VIRTUAL) 기록 — ICPC 룰(문제수 + 페널티)

    페널티 = Σ (해결문제의 가상시작~AC 경과분) + 20분 × (AC 전 오답 수)
    가상참가 종료 후 제출은 CF가 PRACTICE로 바꾸므로, VIRTUAL 제출만 보면
    자연히 가상 대회 시간 안으로 한정된다. 여러 번 가상참가 시 가장 좋은 회차 채택.

    반환 (None = API 실패):
      {'solved_any': int, 'has_virtual': bool, 'v_solved': int, 'v_penalty': int}
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
        logger.warning(f"[oj.codeforces] {handle} contest {target_cid} result 실패: {e!r}")
        return None
    if data.get("status") != "OK":
        logger.warning(f"[oj.codeforces] user.status API 에러({handle}): {data.get('comment')}")
        return None

    solved_any = set()
    # 가상참가: startTime 별로 {index: [(time, verdict), ...]}
    virt = {}
    for sub in data.get("result", []):
        problem = sub.get("problem", {})
        if str(problem.get("contestId")) != target_cid:
            continue
        index = problem.get("index")
        if not index:
            continue
        index = index.upper()
        verdict = sub.get("verdict")
        if verdict == "OK":
            solved_any.add(index)
        author = sub.get("author", {})
        if author.get("participantType") == "VIRTUAL":
            st = author.get("startTimeSeconds")
            if st is None:
                continue
            virt.setdefault(st, {}).setdefault(index, []).append(
                (sub.get("creationTimeSeconds", 0), verdict))

    best = None  # {'solved','penalty','detail'}
    for st, probs in virt.items():
        v_solved = 0
        v_penalty = 0
        detail = []  # [{'idx','solved','minute','tries'}]
        for idx in sorted(probs):
            subs = sorted(probs[idx], key=lambda x: x[0])
            wrong = 0
            ac_time = None
            for t, v in subs:
                if v == "OK":
                    ac_time = t
                    break
                if v != "COMPILATION_ERROR":
                    wrong += 1
            if ac_time is not None:
                minute = int(max(0, (ac_time - st) // 60))
                v_solved += 1
                v_penalty += minute + 20 * wrong
                detail.append({"idx": idx, "solved": True, "minute": minute, "tries": wrong})
            else:
                detail.append({"idx": idx, "solved": False, "minute": None, "tries": wrong})
        if (best is None or v_solved > best["solved"]
                or (v_solved == best["solved"] and v_penalty < best["penalty"])):
            best = {"solved": v_solved, "penalty": v_penalty, "detail": detail}

    return {
        "solved_any": len(solved_any),
        "has_virtual": best is not None and best["solved"] > 0,
        "v_solved": best["solved"] if best else 0,
        "v_penalty": best["penalty"] if best else 0,
        "v_detail": best["detail"] if best else [],
    }
