# -*- coding: utf-8 -*-
# 复用说明：改文件头部的 PROFILE（浏览器 profile）与 BASE/OUT（输出目录）即可。
# 来源：2026-10-26 娅丽达女装实战。
"""补抓：渠道结构（大屏·流量分析 tab）+ 每场商品明细 xlsx（直播详情·下载数据）
用法：python 60_backfill_rooms.py 0 10
"""
import sys, io, os, json, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

PROFILE = r'<你的本机路径>'
BASE = r'<你的项目路径> FDE\01-客户项目\20261018-娅丽达女装\原始资料\20261026-整合分析'
ROOMS = [
    ('7698238978314537743', '1019_1259'), ('7698346812016560930', '1019_1957'),
    ('7698533785729829672', '1020_0803'), ('7698572130035895090', '1020_1031'),
    ('7698710593800309531', '1020_1929'), ('7698904308930546466', '1021_0800'),
    ('7698982622113893120', '1021_1305'), ('7699086960196487951', '1021_1949'),
    ('7699275471560755983', '1022_0801'), ('7699355721938389795', '1022_1312'),
    ('7699391782492293898', '1022_1532'), ('7699455047374768922', '1022_1938'),
    ('7699645612844763938', '1023_0757'), ('7699665393807297331', '1023_0914'),
    ('7699725399135439616', '1023_1307'), ('7700017455988558592', '1024_0800'),
    ('7700187052888886016', '1024_1858'), ('7700388329157561123', '1025_0759'),
    ('7700481431465970447', '1025_1401'),
]
A, B = int(sys.argv[1]), int(sys.argv[2])
state = {'d': None, 'n': 0}


def on_response(resp):
    try:
        u = resp.url
        if 'json' not in resp.headers.get('content-type', '') or 'compass' not in u:
            return
        if not re.search(r'live_screen|live_room_detail|channel_flow|flow_', u):
            return
        b = resp.body()
        if len(b) < 80:
            return
        state['n'] += 1
        fn = f"b{state['n']:03d}_" + re.sub(r'[^A-Za-z0-9_.-]', '_', u.split('?')[0].split('//')[-1])[-70:] + '.json'
        open(os.path.join(state['d'], fn), 'wb').write(b)
    except Exception:
        pass


def click_text(page, kw, wait=4):
    for exact in (True, False):
        try:
            loc = page.get_by_text(kw, exact=exact).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=3000)
                time.sleep(wait)
                return True
        except Exception:
            pass
    return False


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel='msedge', headless=True,
        viewport={'width': 1920, 'height': 1080}, accept_downloads=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on('response', on_response)

    for rid, lab in ROOMS[A:B]:
        d = os.path.join(BASE, '大屏api', f'{lab}_{rid[-6:]}')
        os.makedirs(d, exist_ok=True)
        state.update({'d': d, 'n': 0})
        # 1) 渠道结构
        try:
            page.goto(f'https://compass.jinritemai.com/screen/live/shop?live_room_id={rid}&live_app_id=1128'
                      '&source=compass-live-detail&from_page=%2Fshop%2Flive-detail#data',
                      wait_until='domcontentloaded', timeout=60000)
            time.sleep(12)
            hit = False
            for kw in ['流量分析', '流量', '观众来源']:
                if click_text(page, kw, 5):
                    hit = True
                    break
            time.sleep(3)
            for _ in range(2):
                page.mouse.wheel(0, 1200)
                time.sleep(1.5)
            print(f'[渠道] {lab} 点击={hit} api={state["n"]}', flush=True)
        except Exception as e:
            print(f'[渠道异常] {lab} {type(e).__name__}', flush=True)

        # 2) 商品明细 xlsx
        got = False
        try:
            page.goto(f'https://compass.jinritemai.com/shop/live-detail?live_room_id={rid}',
                      wait_until='domcontentloaded', timeout=60000)
            time.sleep(9)
            for sel in ['text=下载数据', 'text=下载明细', 'text=导出数据']:
                try:
                    loc = page.locator(sel).first
                    if loc.count() and loc.is_visible():
                        with page.expect_download(timeout=12000) as di:
                            loc.click(timeout=4000)
                        dl = di.value
                        fn = dl.suggested_filename or f'{lab}.xlsx'
                        dl.save_as(os.path.join(d, fn))
                        got = True
                        print(f'[xlsx] {lab} -> {fn}', flush=True)
                        break
                except Exception:
                    pass
            if not got:
                print(f'[xlsx] {lab} 未触发下载', flush=True)
        except Exception as e:
            print(f'[xlsx异常] {lab} {type(e).__name__}', flush=True)
        time.sleep(1)

    print('[批次完成]', A, B, flush=True)
    ctx.close()
