// ==UserScript==
// @name         KOALA Jungol Crawler
// @namespace    koala-bot
// @version      1.0.0
// @description  정올 페이지에서 AC 사용자 긁어 KOALA 봇으로 전송 (운영자 IP 사용)
// @match        https://jungol.co.kr/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @connect      jungol.co.kr
// @connect      *
// ==/UserScript==

(function () {
    'use strict';

    // ============== 설정 (운영자가 한 번 입력) ==============
    // 봇 서버 주소 (Oracle 인스턴스 IP 또는 도메인)
    const BOT_BASE = GM_getValue('bot_base', 'http://168.107.5.212:8080');
    // 봇 admin 토큰 (서버 .env 의 BOT_ADMIN_TOKEN 과 동일해야 함)
    const ADMIN_TOKEN = GM_getValue('admin_token', '');

    if (!ADMIN_TOKEN) {
        // 처음 사용 시 토큰 입력
        const t = prompt('KOALA 봇 admin 토큰을 입력하세요 (한 번만 필요):', '');
        if (t) {
            GM_setValue('admin_token', t);
            location.reload();
            return;
        }
    }

    // ============== UI: 우측 하단 floating 버튼 ==============
    const wrap = document.createElement('div');
    wrap.style.cssText = `
        position: fixed; right: 20px; bottom: 20px; z-index: 999999;
        background: #52537f; color: white; padding: 12px 16px;
        border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        font-family: -apple-system, sans-serif; font-size: 14px;
        cursor: pointer; user-select: none; display: flex; flex-direction: column;
        gap: 6px; min-width: 200px;`;
    wrap.innerHTML = `
        <div style="font-weight: bold; font-size: 13px;">🐨 KOALA Jungol</div>
        <div id="koala-status" style="font-size: 12px; opacity: 0.9;">활성 문제 가져오기...</div>
        <button id="koala-collect" style="background:#fff;color:#52537f;border:0;padding:6px 10px;border-radius:4px;cursor:pointer;font-weight:bold;font-size:13px;">📥 일괄 수집</button>
        <button id="koala-current" style="background:transparent;color:white;border:1px solid white;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:11px;">이 페이지만 수집</button>
        <div id="koala-log" style="font-size:11px;opacity:0.85;max-height:140px;overflow-y:auto;line-height:1.4;"></div>
    `;
    document.body.appendChild(wrap);

    const $status = wrap.querySelector('#koala-status');
    const $log = wrap.querySelector('#koala-log');
    const $collect = wrap.querySelector('#koala-collect');
    const $current = wrap.querySelector('#koala-current');

    function log(msg) {
        const div = document.createElement('div');
        div.textContent = msg;
        $log.appendChild(div);
        $log.scrollTop = $log.scrollHeight;
    }

    // ============== 페이지에서 AC 사용자 추출 ==============
    function extractAcUsers(doc) {
        const out = new Set();
        const rows = doc.querySelectorAll('table tbody tr');
        for (const row of rows) {
            // 결과 셀에 "정답" 있는지
            let isAC = false;
            for (const c of row.querySelectorAll('td')) {
                const t = (c.innerText || c.textContent || '').trim();
                if (t === '정답' || /^정답\s/.test(t)) { isAC = true; break; }
            }
            if (!isAC) continue;
            // /account/{id} 링크 → innerText 첫 토큰이 username
            const a = row.querySelector('a[href^="/account/"]');
            if (!a) continue;
            const txt = (a.innerText || a.textContent || '').trim();
            const first = txt.split('\n')[0].trim().split(/\s+/)[0];
            if (first) out.add(first);
        }
        return [...out];
    }

    // ============== 한 문제 페이지 fetch + 파싱 ==============
    async function scrapeOne(pid, maxLoadMore = 30) {
        const url = `https://jungol.co.kr/problem/${pid}/submission`;
        try {
            const res = await fetch(url, { credentials: 'include' });
            const html = await res.text();
            const doc = new DOMParser().parseFromString(html, 'text/html');

            // 1차 추출 (SSR 렌더된 부분)
            let users = extractAcUsers(doc);

            // SSR HTML 만으로는 데이터 없을 수 있어, 같은 origin fetch 가 SPA 데이터 endpoint 호출 가능
            // 만약 원본 페이지가 현재 열린 페이지와 같은 problem 이면 DOM 직접 읽기
            const cur = location.pathname.match(/\/problem\/(\d+)/);
            if (cur && cur[1] === String(pid) && /submission/.test(location.pathname)) {
                const dom = extractAcUsers(document);
                if (dom.length > users.length) users = dom;
            }
            return users;
        } catch (e) {
            log(`❌ ${pid}: ${e.message}`);
            return null;
        }
    }

    // ============== 봇으로 POST ==============
    async function postCache(items) {
        try {
            const res = await fetch(`${BOT_BASE}/jungol/cache`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Auth': ADMIN_TOKEN },
                body: JSON.stringify({ items }),
            });
            const text = await res.text();
            if (res.ok) {
                log(`✅ POST OK: ${text.slice(0, 100)}`);
                return true;
            } else {
                log(`❌ POST ${res.status}: ${text.slice(0, 100)}`);
                return false;
            }
        } catch (e) {
            log(`❌ POST 실패: ${e.message}`);
            return false;
        }
    }

    // ============== 활성 문제 ID 목록 가져오기 ==============
    async function fetchActiveProblems() {
        try {
            const res = await fetch(`${BOT_BASE}/jungol/problems`, {
                headers: { 'X-Auth': ADMIN_TOKEN },
            });
            if (!res.ok) {
                $status.textContent = `❌ 봇 응답 ${res.status}`;
                return null;
            }
            const data = await res.json();
            return data.problems || [];
        } catch (e) {
            $status.textContent = `❌ 봇 연결 실패`;
            log(`연결 실패: ${e.message}`);
            return null;
        }
    }

    // ============== 메인: 일괄 수집 ==============
    $collect.onclick = async () => {
        $log.innerHTML = '';
        log('활성 문제 목록 조회 중...');
        const pids = await fetchActiveProblems();
        if (!pids) return;
        if (pids.length === 0) { log('활성 문제 없음 (활성 문제집의 Jungol 문제 0개)'); return; }
        log(`${pids.length}개 문제 수집 시작`);

        const items = [];
        for (const pid of pids) {
            const users = await scrapeOne(pid);
            if (users === null) continue;
            items.push({ problem_id: pid, ac_handles: users });
            log(`  ${pid}: AC ${users.length}명`);
        }

        if (items.length === 0) { log('수집된 데이터 없음'); return; }
        log(`${items.length}/${pids.length} 봇으로 전송 중...`);
        await postCache(items);
        log(`완료 ${new Date().toLocaleTimeString()}`);
    };

    // ============== 현재 페이지만 수집 ==============
    $current.onclick = async () => {
        $log.innerHTML = '';
        const m = location.pathname.match(/\/problem\/(\d+)/);
        if (!m) { log('현재 페이지가 problem 페이지 아님'); return; }
        const pid = m[1];
        log(`현재 페이지 ${pid} 수집...`);
        const users = extractAcUsers(document);
        log(`AC ${users.length}명`);
        if (users.length === 0) { log('AC 0명 — 페이지 데이터 없음'); return; }
        await postCache([{ problem_id: pid, ac_handles: users }]);
    };

    // ============== 활성 문제 수 표시 ==============
    fetchActiveProblems().then(pids => {
        if (pids === null) return;
        $status.textContent = `활성 문제 ${pids.length}개`;
    });
})();
