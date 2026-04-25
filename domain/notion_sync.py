"""
노션 → 봇 동기화 (Phase 1: 읽기 전용 코어)

구조:
  L1 KOALA (2cfa738c...)
   └── L2 커리큘럼
        └── L3 문제집 (34da738c... = NOTION_ROOT_PAGE_ID)
             ├── L4 하위 문제집 #1   ← 봇이 읽는 단위
             ├── L4 하위 문제집 #2
             └── ...

L3 페이지의 직접 자식(child_page)들을 문제집으로 간주.
각 자식 페이지 본문에서 URL 추출 → OJ 분류.
"""
import os
import re
import aiohttp
import discord
from discord.ext import commands
from typing import List, Optional, Tuple
from common.logger import get_logger

logger = get_logger()

# 봇이 동기화할 시작점 (L3 "문제집" 페이지 ID, 하드코딩)
NOTION_ROOT_PAGE_ID = "34da738c739d807280d8ec67b8824abb"

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# OJ URL 패턴
OJ_PATTERNS = [
    # BOJ
    ("boj", re.compile(r"acmicpc\.net/problem/(\d+)", re.IGNORECASE),
     lambda m: m.group(1)),
    # Codeforces — problemset 또는 contest 형식 모두 지원
    ("codeforces", re.compile(
        r"codeforces\.com/(?:problemset/problem|contest)/(\d+)/(?:problem/)?([A-Za-z0-9]+)",
        re.IGNORECASE),
     lambda m: f"{m.group(1)}/{m.group(2).upper()}"),
    # Codeforces Gym
    ("codeforces", re.compile(
        r"codeforces\.com/gym/(\d+)/problem/([A-Za-z0-9]+)", re.IGNORECASE),
     lambda m: f"gym{m.group(1)}/{m.group(2).upper()}"),
    # AtCoder
    ("atcoder", re.compile(
        r"atcoder\.jp/contests/([\w-]+)/tasks/([\w-]+)", re.IGNORECASE),
     lambda m: m.group(2)),
    # Jungol
    ("jungol", re.compile(
        r"jungol\.co\.kr/[^\s)]*[?&](?:pid|sProbId)=(\d+)", re.IGNORECASE),
     lambda m: m.group(1)),
    # Jungol path 형식
    ("jungol", re.compile(
        r"jungol\.co\.kr/problem/(\d+)", re.IGNORECASE),
     lambda m: m.group(1)),
]

# URL 추출 (markdown 링크/평문 둘 다)
URL_RE = re.compile(r"https?://[^\s)\]<>]+", re.IGNORECASE)


def get_token() -> Optional[str]:
    return os.getenv("NOTION_ACCESS_TOKEN")


def _headers() -> dict:
    token = get_token()
    if not token:
        raise RuntimeError("NOTION_ACCESS_TOKEN 환경변수가 설정되지 않았습니다.")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


async def _get(session: aiohttp.ClientSession, path: str) -> dict:
    async with session.get(f"{NOTION_API}{path}", headers=_headers()) as r:
        data = await r.json()
        if r.status >= 400:
            raise RuntimeError(
                f"Notion API GET {path} 실패 ({r.status}): {data.get('message', data)}"
            )
        return data


def classify_url(url: str) -> Optional[Tuple[str, str]]:
    """
    URL을 OJ로 분류. 매칭되면 (oj, problem_id) 반환, 아니면 None.
    """
    for oj, pattern, id_fn in OJ_PATTERNS:
        m = pattern.search(url)
        if m:
            try:
                return oj, id_fn(m)
            except Exception:
                continue
    return None


def _rich_text_to_str(rich_text: list) -> str:
    """노션 rich_text 배열에서 plain text + URL을 모두 추출"""
    parts = []
    for rt in rich_text or []:
        plain = rt.get("plain_text", "")
        if plain:
            parts.append(plain)
        href = rt.get("href")
        if href:
            parts.append(href)
    return " ".join(parts)


async def list_child_pages(session: aiohttp.ClientSession, parent_id: str) -> List[dict]:
    """
    parent_id 페이지의 직접 자식 중 child_page 타입만 반환.
    반환: [{"id": "...", "title": "..."}]
    """
    children = []
    cursor = None
    while True:
        path = f"/blocks/{parent_id}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        data = await _get(session, path)
        for blk in data.get("results", []):
            if blk.get("type") == "child_page":
                title = blk.get("child_page", {}).get("title", "(제목 없음)")
                children.append({"id": blk["id"], "title": title})
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return children


async def collect_urls_from_page(session: aiohttp.ClientSession, page_id: str,
                                 max_depth: int = 2) -> List[str]:
    """
    페이지의 모든 블록을 재귀 순회하며 URL 추출.
    bookmark/embed/link_preview의 url 필드 + rich_text 안의 href + plain text 내 URL
    """
    urls: List[str] = []

    async def walk(block_id: str, depth: int):
        if depth > max_depth:
            return
        cursor = None
        while True:
            path = f"/blocks/{block_id}/children?page_size=100"
            if cursor:
                path += f"&start_cursor={cursor}"
            try:
                data = await _get(session, path)
            except Exception as e:
                logger.warning(f"[notion_sync] 블록 자식 조회 실패 ({block_id}): {e}")
                return

            for blk in data.get("results", []):
                btype = blk.get("type")
                if not btype:
                    continue
                body = blk.get(btype) or {}

                # rich_text 가 있는 블록 (paragraph, bullet, heading, todo, toggle 등)
                if isinstance(body, dict) and "rich_text" in body:
                    text = _rich_text_to_str(body["rich_text"])
                    urls.extend(URL_RE.findall(text))

                # bookmark / embed / link_preview / video / file 등 url 필드 직접
                if isinstance(body, dict):
                    u = body.get("url")
                    if isinstance(u, str) and u.startswith(("http://", "https://")):
                        urls.append(u)

                # 자식 페이지는 동기화 단위가 아니므로 깊이 들어가지 않음
                # 단, toggle/quote/bulleted 같은 컨테이너는 재귀
                if blk.get("has_children") and btype != "child_page":
                    await walk(blk["id"], depth + 1)

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

    await walk(page_id, 0)
    return urls


async def sync_problem_sets() -> List[dict]:
    """
    NOTION_ROOT_PAGE_ID 의 자식 문제집들을 모두 가져와 파싱.
    반환:
      [
        {
          "name": "<문제집명>",
          "page_id": "<L4 page id>",
          "problems": [{"oj": "boj", "id": "1234", "url": "..."}, ...],
          "unknown_urls": ["...", ...]   # 분류 실패한 URL (디버그용)
        },
        ...
      ]
    """
    if not get_token():
        raise RuntimeError("NOTION_ACCESS_TOKEN 환경변수가 설정되지 않았습니다.")

    result = []
    async with aiohttp.ClientSession() as session:
        children = await list_child_pages(session, NOTION_ROOT_PAGE_ID)
        logger.info(f"[notion_sync] L3에서 {len(children)}개 자식 문제집 발견")

        for ch in children:
            page_id = ch["id"]
            title = ch["title"]
            urls = await collect_urls_from_page(session, page_id)

            problems = []
            unknown_urls = []
            seen = set()
            for u in urls:
                cls = classify_url(u)
                if cls:
                    oj, pid = cls
                    key = (oj, pid)
                    if key in seen:
                        continue
                    seen.add(key)
                    problems.append({"oj": oj, "id": pid, "url": u})
                else:
                    unknown_urls.append(u)

            result.append({
                "name": title,
                "page_id": page_id,
                "problems": problems,
                "unknown_urls": unknown_urls,
            })

    return result


def setup(bot: commands.Bot):
    """봇에 임시 진단 명령어 등록 (Phase 1 검증용)"""

    @bot.command(name="노션테스트")
    @commands.has_permissions(administrator=True)
    async def notion_test(ctx: commands.Context):
        """노션 root 페이지에서 문제집을 가져와 결과를 ephemeral로 출력 (관리자 전용)"""
        if not get_token():
            await ctx.send("❌ NOTION_ACCESS_TOKEN 환경변수가 설정되지 않았습니다.")
            return

        loading = await ctx.send("🔄 노션에서 문제집 동기화 테스트 중...")
        try:
            results = await sync_problem_sets()
        except Exception as e:
            logger.error(f"[/노션테스트] 실패: {e}", exc_info=True)
            await loading.edit(content=f"❌ 동기화 실패: {type(e).__name__}: {e}")
            return

        if not results:
            await loading.edit(
                content=(
                    "⚠️ 자식 문제집 페이지가 없습니다.\n"
                    f"확인할 점:\n"
                    f"- ROOT 페이지 ID: `{NOTION_ROOT_PAGE_ID}`\n"
                    f"- Integration이 KOALA 또는 문제집 페이지에 Connections로 추가되어 있나요?\n"
                    f"- 문제집 페이지 아래에 자식 페이지가 있나요?"
                )
            )
            return

        # 요약
        total_problems = sum(len(r["problems"]) for r in results)
        total_unknown = sum(len(r["unknown_urls"]) for r in results)

        embed = discord.Embed(
            title="📚 노션 동기화 테스트 결과",
            description=(
                f"**ROOT 페이지:** `{NOTION_ROOT_PAGE_ID}`\n"
                f"**자식 문제집:** {len(results)}개\n"
                f"**파싱된 문제 총합:** {total_problems}개\n"
                f"**분류 실패 URL:** {total_unknown}개"
            ),
            color=discord.Color.blue(),
        )

        # OJ별 합계
        oj_count = {}
        for r in results:
            for p in r["problems"]:
                oj_count[p["oj"]] = oj_count.get(p["oj"], 0) + 1
        if oj_count:
            embed.add_field(
                name="OJ별 문제 수",
                value="\n".join(f"• {oj}: {cnt}" for oj, cnt in sorted(oj_count.items())),
                inline=False,
            )

        # 문제집별 상세 (최대 10개만)
        for r in results[:10]:
            oj_summary = {}
            for p in r["problems"]:
                oj_summary[p["oj"]] = oj_summary.get(p["oj"], 0) + 1
            summary_str = ", ".join(f"{oj} {cnt}" for oj, cnt in sorted(oj_summary.items())) \
                          if oj_summary else "(문제 없음)"
            unknown_note = f" / 미분류 {len(r['unknown_urls'])}개" if r["unknown_urls"] else ""
            embed.add_field(
                name=f"📄 {r['name']}",
                value=f"{summary_str}{unknown_note}",
                inline=False,
            )

        if len(results) > 10:
            embed.set_footer(text=f"... 외 {len(results) - 10}개 문제집")

        await loading.edit(content=None, embed=embed)
