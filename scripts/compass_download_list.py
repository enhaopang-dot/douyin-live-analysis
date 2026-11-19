# -*- coding: utf-8 -*-
# 复用说明：改文件头部的 PROFILE（浏览器 profile）与 BASE/OUT（输出目录）即可。
# 来源：2026-10-26 娅丽达女装实战。
"""罗盘场次清单：用「下载明细」导出近30天自营场次
输出：原始资料/20261026-整合分析/场次清单/下载/
"""
import sys, io, os, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

PROFILE = r'<你的本机路径>'
OUT = r'<你的项目路径> FDE\01-客户项目\20261018-娅丽达女装\原始资料\20261026-整合分析\场次清单\下载'
os.makedirs(OUT, exist_ok=True)

state = {'rows': []}


def on_response(resp):
    try:
        if 'live_room_detail_v2' in resp.url and 'json' in resp.headers.get('content-type', ''):
            b = resp.body()
            if len(b) > 200:
                j = json.loads(b.decode('utf-8'))
                md = (j.get('data') or {}).get('module_data', {}).get('shop_live_list_room_detail', {})
                rows = (md.get('compass_general_table_value') or {}).get('data') or []
                state['rows'].append((resp.url, rows))
    except Exception:
        pass


def logged_in(ctx):
    try:
        for c in ctx.cookies('https://compass.jinritemai.com'):
            if c['name'] in ('sessionid', 'sessionid_ss', 'sid_tt') and c['value']:
                return True
    except Exception:
        pass
    return False


def click_kw(page, kw, wait=4, exact=True):
    try:
        loc = page.get_by_text(kw, exact=exact).first
        if loc.count() and loc.is_visible():
            loc.click(timeout=4000)
            print(f'[点击] {kw}', flush=True)
            time.sleep(wait)
            return True
    except Exception:
        pass
    return False


def total_text(page):
    try:
        return page.locator('.aurora-pagination-total-text').first.inner_text()
    except Exception:
        return '?'


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel='msedge', headless=True,
        viewport={'width': 1920, 'height': 1080}, accept_downloads=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on('response', on_response)

    page.goto('https://compass.jinritemai.com/shop/live-list', wait_until='domcontentloaded', timeout=60000)
    time.sleep(12)
    if not logged_in(ctx):
        print('[未登录]', flush=True)
        ctx.close()
        sys.exit(2)
    print('[总数·初始]', total_text(page), flush=True)

    for trig in ['近30天', '近30日']:
        if click_kw(page, trig, 6):
            break
    print('[总数·近30天]', total_text(page), flush=True)

    if click_kw(page, '全部账号（自营和合作）', 3) or click_kw(page, '请选择账号', 3):
        time.sleep(2)
        # 列下拉选项文本，便于核对
        try:
            opts = page.evaluate("""() => [...document.querySelectorAll('[class*=dropdown] [class*=option], [class*=select] [class*=item]')]
                .map(e => (e.innerText||'').trim()).filter(t => t && t.length < 30).slice(0, 20)""")
            print('[下拉选项]', json.dumps(opts, ensure_ascii=False)[:400], flush=True)
        except Exception:
            pass
        click_kw(page, '自营账号', 6)
    print('[总数·自营]', total_text(page), flush=True)

    # 下载明细
    got = None
    for sel in ['text=下载明细', 'button:has-text("下载明细")']:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                with page.expect_download(timeout=15000) as di:
                    loc.click(timeout=5000)
                d = di.value
                fn = d.suggested_filename or 'live_list.xlsx'
                d.save_as(os.path.join(OUT, fn))
                got = fn
                print('[下载]', fn, flush=True)
                break
        except Exception as e:
            print(f'[下载失败] {sel} {type(e).__name__}: {str(e)[:80]}', flush=True)
            time.sleep(3)

    if not got:
        # 可能在弹窗里二次确认
        for kw in ['确认', '下载', '确定']:
            if click_kw(page, kw, 3):
                break

    # 兜底：把所有捕获的列表行落盘
    allrows = []
    for url, rows in state['rows']:
        for r in rows:
            allrows.append(r)
    (io.open(os.path.join(OUT, '_raw_rows.json'), 'w', encoding='utf-8')).write(
        json.dumps(allrows, ensure_ascii=False))
    print(f'[兜底] 捕获列表行 {len(allrows)} 条，来自 {len(state["rows"])} 次请求', flush=True)

    ctx.close()
