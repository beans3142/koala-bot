"""
Jungol Playwright 스크래퍼.

전략:
- 1GB Oracle Free Tier 환경 → Chromium은 일별 1회만 띄움
- 한 번 띄울 때 모든 활성 Jungol 문제를 순차 처리
- 결과를 jungol_solved 캐시에 저장
- 시간 단위 풀이현황 갱신은 캐시만 읽음 (Chromium 안 띄움)

페이지 구조 (사용자 검증 결과 비로그인 접근 가능):
  https://jungol.co.kr/problem/{pid}/submission
  → "결과: 정답" 인 제출만 추출
  → 사용자 핸들 = 제출자 셀의 텍스트
"""
import asyncio
from typing import List, Set, Optional
from common.logger import get_logger
from common.database import (
    upsert_jungol_solved,
    record_jungol_problem_fetch,
)

logger = get_logger()

# Playwright는 선택적 의존성 — import 실패해도 모듈은 로드되도록
try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None
    PWTimeout = Exception


# Chromium launch options for 1GB RAM constraint
CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-default-apps",
    "--disable-sync",
    "--disable-translate",
    "--disable-features=site-per-process,TranslateUI",
    "--memory-pressure-off",
    "--mute-audio",
]

PROBLEM_URL_TEMPLATE = "https://jungol.co.kr/problem/{pid}/submission"

# Submission 행 셀렉터 후보 (페이지 구조 변경 시 fallback)
SUBMISSION_ROW_SELECTORS = [
    'table tbody tr',          # 일반 테이블 행
    '[role="row"]',            # ARIA role
    '.submission-row',         # custom class
    'a[href*="/account/"]',    # 사용자 링크 포함하는 행
]

# 제출 행 안에서 (결과, 사용자명) 추출하는 JS
EXTRACT_JS = r"""
() => {
    // 정올 submission 행 구조 (확인됨, 2026-04):
    //   <a href="/account/{user_id}">{username [verified] [학교명]}</a>
    //   결과 셀 텍스트 = "정답" 또는 "정답 100점" / "런타임 에러" / "오답" / "컴파일 에러" 등
    const out = new Set();
    const rows = document.querySelectorAll('table tbody tr');
    for (const row of rows) {
        // 결과 셀이 정답인 행만
        let isAC = false;
        for (const c of row.querySelectorAll('td')) {
            const ct = (c.innerText || '').trim();
            if (ct === '정답' || /^정답\s/.test(ct)) { isAC = true; break; }
        }
        if (!isAC) continue;

        // 사용자 링크: /account/{number}
        const userLink = row.querySelector('a[href^="/account/"]');
        if (!userLink) continue;
        const txt = (userLink.innerText || '').trim();
        // 첫 줄, 첫 토큰만 (verified / 학교명 등 라벨 제거)
        const firstLine = txt.split('\n')[0].trim();
        const username = firstLine.split(/\s+/)[0];
        if (username) out.add(username);
    }
    return [...out];
}
"""


async def _scrape_problem(page, pid: str, max_pages: int = 30,
                           target_handles: Optional[Set[str]] = None) -> Set[str]:
    """
    한 문제의 submission 페이지를 열고 AC 한 사용자 핸들 수집.
    target_handles 가 주어지면 모두 발견 시 조기 종료.
    """
    url = PROBLEM_URL_TEMPLATE.format(pid=pid)
    handles: Set[str] = set()
    targets = set(target_handles) if target_handles else None

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
    except PWTimeout:
        logger.warning(f"[jungol] {pid} 페이지 로딩 타임아웃")
        return handles
    except Exception as e:
        logger.warning(f"[jungol] {pid} 페이지 로딩 실패: {e}")
        return handles

    # SPA 데이터 로딩 대기
    found_selector = False
    for sel in SUBMISSION_ROW_SELECTORS:
        try:
            await page.wait_for_selector(sel, timeout=8000)
            found_selector = True
            break
        except PWTimeout:
            continue

    if not found_selector:
        logger.warning(f"[jungol] {pid} submission 행 셀렉터를 찾지 못함")
        return handles

    # "더 불러오기" 반복 클릭 (조기 종료 가능)
    for _ in range(max_pages):
        # 현재 페이지의 AC 사용자 추출
        try:
            users = await page.evaluate(EXTRACT_JS)
            for u in users:
                if u:
                    handles.add(u)
        except Exception as e:
            logger.warning(f"[jungol] {pid} extract JS 실패: {e}")
            break

        # 타겟 모두 발견 시 조기 종료
        if targets and targets.issubset(handles):
            logger.debug(f"[jungol] {pid}: 타겟 {len(targets)}명 모두 발견, 조기 종료")
            break

        # 더 불러오기 버튼
        more_btn = await page.query_selector(
            'button:has-text("더 불러오기"), button:has-text("Load more"), button:has-text("다음")'
        )
        if not more_btn:
            break
        try:
            await more_btn.click(timeout=3000)
            await asyncio.sleep(1.0)
        except Exception:
            break

    return handles


async def scrape_jungol_problems(problem_ids: List[str], headless: bool = True,
                                  target_handles: Optional[Set[str]] = None,
                                  max_pages: int = 30) -> dict:
    """
    여러 Jungol 문제를 순차 스크래핑.
    Chromium은 한 번만 띄움 → 모든 문제 처리 → 닫음.
    각 문제마다 결과를 jungol_solved 캐시에 upsert.

    target_handles: 활성 그룹 멤버의 jungol_handle set. 모두 발견되면 조기 종료.
    max_pages: "더 불러오기" 최대 클릭 수 (1 클릭 ≈ 30~50 사용자 추가).

    반환: {problem_id: count_of_AC_users} (또는 에러 시 0)
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("[jungol] playwright 패키지가 설치되지 않았습니다. `pip install playwright && playwright install chromium`")
        return {}

    if not problem_ids:
        return {}

    results = {}
    logger.info(f"[jungol] 스크래핑 시작 — {len(problem_ids)}개 문제")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless, args=CHROMIUM_ARGS)
        try:
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="ko-KR",
                viewport={"width": 1280, "height": 800},
            )
            # 불필요한 리소스 차단으로 메모리/대역 절약
            await context.route(
                "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,otf}",
                lambda route: route.abort(),
            )
            await context.route(
                "**/{googletagmanager,google-analytics,doubleclick,googlesyndication,recaptcha,turnstile}.*",
                lambda route: route.abort(),
            )

            page = await context.new_page()
            for pid in problem_ids:
                try:
                    handles = await _scrape_problem(
                        page, pid, max_pages=max_pages, target_handles=target_handles
                    )
                    if handles:
                        upsert_jungol_solved(pid, list(handles))
                        record_jungol_problem_fetch(pid, success=True, user_count=len(handles))
                        logger.info(f"[jungol] {pid}: AC {len(handles)}명 캐시 저장")
                    else:
                        record_jungol_problem_fetch(pid, success=False, user_count=0,
                                                    error="No AC users found (page structure may have changed)")
                        logger.warning(f"[jungol] {pid}: AC 사용자 0명 (셀렉터 미스 가능성)")
                    results[pid] = len(handles)
                except Exception as e:
                    logger.error(f"[jungol] {pid} 처리 중 오류: {e}", exc_info=True)
                    record_jungol_problem_fetch(pid, success=False, user_count=0, error=str(e))
                    results[pid] = 0
                # 사이트 부담 줄이려 잠깐 쉬기
                await asyncio.sleep(0.8)

            await context.close()
        finally:
            await browser.close()

    logger.info(f"[jungol] 스크래핑 완료 — {sum(1 for v in results.values() if v > 0)}/{len(problem_ids)} 성공")
    return results
