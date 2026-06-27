"""
주간테스트 채점/파싱 standalone 검증 스크립트.

봇 없이 CF API 와 링크 파싱을 직접 확인한다.

사용법:
  python test_weekly_test.py                # 파싱 테스트 + 샘플 채점
  python test_weekly_test.py <handle> <contestId>   # 특정 핸들/대회 채점
  예: python test_weekly_test.py tourist 566

CF API 는 공개라 토큰 불필요. 출력된 풀이 수를
해당 핸들의 CF 프로필(제출 내역)과 대조해 정확성을 검증하면 된다.
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.oj.codeforces import get_contest_solved
from domain.weekly_test import extract_contest_id_from_text, DEFAULT_THRESHOLD


def test_parsing():
    print("=" * 60)
    print("[1] 링크 → contestId 파싱 테스트")
    print("=" * 60)
    cases = [
        ("https://codeforces.com/contest/2000", "2000"),
        ("https://codeforces.com/contests/1899", "1899"),
        ("https://codeforces.com/contest/1234/problem/A", "1234"),
        ("https://codeforces.com/problemset/problem/566/F", "566"),
        ("https://codeforces.com/gym/100001", "100001"),
        ("2000", "2000"),
        ("https://atcoder.jp/contests/abc300", None),
        ("그냥 텍스트", None),
    ]
    ok = True
    for inp, expected in cases:
        got = extract_contest_id_from_text(inp)
        mark = "✅" if got == expected else "❌"
        if got != expected:
            ok = False
        print(f"  {mark} {inp!r:55} → {got!r} (기대: {expected!r})")
    print(f"\n  파싱 결과: {'전부 통과' if ok else '실패 있음'}\n")
    return ok


async def test_scoring(handle: str, contest_id: str):
    print("=" * 60)
    print(f"[2] CF 채점 테스트 — handle={handle}, contest={contest_id}")
    print("=" * 60)

    solved = await get_contest_solved(handle, contest_id)
    if solved is None:
        print("  ❌ CF API 조회 실패 (서버 다운/레이트리밋/잘못된 핸들)")
        return
    cnt = len(solved)
    passed = cnt >= DEFAULT_THRESHOLD
    print(f"  푼 문제 index: {sorted(solved)}")
    print(f"  푼 문제 수: {cnt}")
    print(f"  통과 기준({DEFAULT_THRESHOLD}문제): {'✅ 통과' if passed else '📝 미통과'}")
    print(f"\n  → CF 프로필에서 대회 {contest_id} 제출 내역과 대조해 검증하세요.\n")


async def main():
    test_parsing()

    if len(sys.argv) >= 3:
        handle, contest_id = sys.argv[1], sys.argv[2]
    else:
        # 샘플: tourist 가 contest 566 에서 푼 문제
        handle, contest_id = "tourist", "566"
        print(f"(인자 없음 → 샘플 실행: {handle} / {contest_id})\n")

    await test_scoring(handle, contest_id)


if __name__ == "__main__":
    asyncio.run(main())
