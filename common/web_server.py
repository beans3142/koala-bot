"""
봇 HTTP 서버 — Jungol 데이터 수집용 admin endpoint.

운영자 브라우저(=한국 IP)가 정올 페이지 fetch 후 결과를 여기로 POST.
서버는 datacenter IP 라 직접 정올 못 긁지만, 운영자 브라우저가 거쳐서 줌.

엔드포인트:
  GET  /jungol/problems   — 현재 활성 문제집의 Jungol 문제 ID 목록 (userscript 가 fetch)
  POST /jungol/cache      — userscript 가 긁은 결과 저장
  GET  /                  — health check
"""
import os
import json
from aiohttp import web
from typing import List

from common.logger import get_logger
from common.database import (
    upsert_jungol_solved,
    record_jungol_problem_fetch,
    get_all_notion_problem_set_status,
)
from common.utils import get_kst_now, ensure_kst
from datetime import datetime, timedelta

logger = get_logger()


def get_admin_token() -> str:
    return os.getenv("BOT_ADMIN_TOKEN", "")


def _check_auth(request) -> bool:
    expected = get_admin_token()
    if not expected:
        return False
    given = request.headers.get("X-Auth") or request.query.get("auth", "")
    return given == expected


async def health(request):
    return web.json_response({"ok": True, "service": "koala-bot"})


async def jungol_problems(request):
    """현재 active status (주차 내) 의 Jungol 문제 ID 목록 반환.
    userscript 가 fetch 해서 어떤 문제들 긁을지 결정."""
    if not _check_auth(request):
        return web.Response(status=403, text="forbidden")
    # 활성 문제집들에서 Jungol problem id 모으기
    try:
        from domain.notion_sync import sync_problem_sets
    except Exception as e:
        return web.json_response({"error": f"notion_sync import: {e}"}, status=500)

    now = get_kst_now()
    statuses = get_all_notion_problem_set_status()
    active_names = set()
    for s in statuses:
        try:
            ws = ensure_kst(datetime.fromisoformat(s['week_start']))
            we = ensure_kst(datetime.fromisoformat(s['week_end']))
        except Exception:
            continue
        if ws <= now <= we:
            active_names.add(s['problem_set_name'])

    if not active_names:
        return web.json_response({"problems": [], "note": "no active problem sets"})

    try:
        all_sets = await sync_problem_sets()
    except Exception as e:
        return web.json_response({"error": f"notion fetch: {e}"}, status=500)

    pids = set()
    for ps in all_sets:
        if ps['name'] not in active_names:
            continue
        for p in ps['problems']:
            if p['oj'] == 'jungol':
                pids.add(str(p['id']))

    return web.json_response({"problems": sorted(pids)})


async def jungol_cache(request):
    """userscript 가 긁은 (problem_id, ac_handles) JSON 받아 캐시에 저장.

    expected body: {"problem_id": "1234", "ac_handles": ["user1","user2",...]}
    또는 bulk:    {"items": [{"problem_id":..., "ac_handles":[...]}, ...]}
    """
    if not _check_auth(request):
        return web.Response(status=403, text="forbidden")
    try:
        data = await request.json()
    except Exception as e:
        return web.json_response({"error": f"invalid json: {e}"}, status=400)

    items = data.get("items") if isinstance(data, dict) else None
    if items is None and isinstance(data, dict) and "problem_id" in data:
        items = [data]
    if not isinstance(items, list) or not items:
        return web.json_response({"error": "no items"}, status=400)

    saved = 0
    errors = []
    for item in items:
        try:
            pid = str(item["problem_id"])
            handles = list(item.get("ac_handles") or [])
            handles = [str(h).strip() for h in handles if h]
            upsert_jungol_solved(pid, handles)
            record_jungol_problem_fetch(pid, success=True, user_count=len(handles))
            saved += 1
            logger.info(f"[jungol cache POST] pid={pid} ac={len(handles)}")
        except Exception as e:
            errors.append({"item": item.get("problem_id"), "error": str(e)})
            logger.error(f"[jungol cache POST] item fail: {e}")

    return web.json_response({"saved": saved, "errors": errors})


async def add_cors_headers(request, response):
    """모든 응답에 CORS 헤더 추가 (브라우저가 jungol.co.kr 에서 POST 가능하도록)"""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Auth"
    response.headers["Access-Control-Max-Age"] = "3600"


async def cors_preflight(request):
    return web.Response(status=204)


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/jungol/problems", jungol_problems)
    app.router.add_post("/jungol/cache", jungol_cache)
    # CORS preflight
    app.router.add_options("/jungol/problems", cors_preflight)
    app.router.add_options("/jungol/cache", cors_preflight)
    app.on_response_prepare.append(add_cors_headers)
    return app


_runner = None


async def start_web_server(host: str = "0.0.0.0", port: int = 8080):
    global _runner
    if _runner is not None:
        return _runner
    if not get_admin_token():
        logger.warning("[web_server] BOT_ADMIN_TOKEN 미설정 — 모든 요청 거부됨")
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    _runner = runner
    logger.info(f"[web_server] 시작: http://{host}:{port}")
    return runner


async def stop_web_server():
    global _runner
    if _runner is not None:
        await _runner.cleanup()
        _runner = None
        logger.info("[web_server] 정지")
