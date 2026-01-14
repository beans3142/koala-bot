"""
solved.ac 기반 주간 문제풀이 수 테스트 스크립트
서버에서 직접 실행해서 solved.ac API가 제대로 동작하는지 확인
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta

async def test_verify_user():
    """유저 존재 확인 테스트"""
    print("=" * 60)
    print("[1] solved.ac 유저 존재 확인 테스트")
    print("=" * 60)
    
    test_handles = ["beans3142", "definitely_not_exist_12345"]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for handle in test_handles:
            url = f"https://solved.ac/api/v3/user/show?handle={handle}"
            print(f"\n테스트: {handle}")
            print(f"  URL: {url}")
            
            try:
                async with session.get(url) as response:
                    print(f"  상태 코드: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"  ✅ 존재함 - solvedCount: {data.get('solvedCount', 'N/A')}")
                    elif response.status == 404:
                        print(f"  ❌ 존재하지 않음")
                    else:
                        text = await response.text()
                        print(f"  ⚠️ 예상치 못한 상태: {response.status}")
                        print(f"  응답 (처음 200자): {text[:200]}")
            except Exception as e:
                print(f"  ❌ 오류: {e}")

async def test_history_api():
    """history API 응답 형식 확인"""
    print("\n" + "=" * 60)
    print("[2] solved.ac history API 응답 형식 확인")
    print("=" * 60)
    
    handle = "beans3142"
    url = f"https://solved.ac/api/v3/user/history?handle={handle}&topic=solvedCount"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    print(f"\n테스트: {handle}")
    print(f"URL: {url}\n")
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url) as response:
                print(f"상태 코드: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 성공 - 총 {len(data)}개 항목")
                    
                    if data:
                        print(f"\n첫 5개 항목:")
                        for i, entry in enumerate(data[:5], 1):
                            ts = entry.get('timestamp', 'N/A')
                            val = entry.get('value', 'N/A')
                            print(f"  {i}. timestamp={ts}, value={val}")
                        
                        print(f"\n마지막 5개 항목:")
                        for i, entry in enumerate(data[-5:], len(data)-4):
                            ts = entry.get('timestamp', 'N/A')
                            val = entry.get('value', 'N/A')
                            print(f"  {i}. timestamp={ts}, value={val}")
                else:
                    text = await response.text()
                    print(f"❌ 실패: {response.status}")
                    print(f"응답 (처음 500자): {text[:500]}")
        except Exception as e:
            print(f"❌ 오류: {e}")
            import traceback
            traceback.print_exc()

async def test_weekly_count():
    """주간 풀이 수 계산 테스트 (실제 함수 사용)"""
    print("\n" + "=" * 60)
    print("[3] get_weekly_solved_count 함수 테스트")
    print("=" * 60)
    
    # common.boj_utils 모듈 import
    try:
        from common.boj_utils import get_weekly_solved_count
    except ImportError as e:
        print(f"❌ 모듈 import 실패: {e}")
        print("   현재 디렉토리에서 실행했는지 확인하세요.")
        return
    
    handle = "beans3142"
    
    # 이번 주 월요일 00:00 ~ 다음 주 월요일 01:00 구간 계산 (channel.py 로직과 동일)
    today = datetime.now()
    days_since_monday = today.weekday()  # 월요일=0
    week_start = today - timedelta(days=days_since_monday)
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7, hours=1)
    
    print(f"\n테스트 유저: {handle}")
    print(f"기간: {week_start.strftime('%Y-%m-%d %H:%M')} ~ {week_end.strftime('%Y-%m-%d %H:%M')}")
    print(f"(이번 주 월요일 00:00 ~ 다음 주 월요일 01:00)\n")
    
    try:
        result = await get_weekly_solved_count(handle, week_start, week_end)
        print(f"✅ 결과:")
        print(f"  count: {result.get('count', 0)}")
        print(f"  problems: {result.get('problems', [])}")
        
        if result.get('count', 0) == 0:
            print(f"\n⚠️ 주의: count가 0입니다.")
            print(f"  - 이번 주에 문제를 안 풀었거나")
            print(f"  - API 응답 파싱에 문제가 있을 수 있습니다.")
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """전체 테스트 실행"""
    print("\n" + "=" * 60)
    print("solved.ac API 테스트 시작")
    print("=" * 60)
    
    await test_verify_user()
    await test_history_api()
    await test_weekly_count()
    
    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

