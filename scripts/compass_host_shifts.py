# -*- coding: utf-8 -*-
# 复用说明：改文件头部的 PROFILE（浏览器 profile）与 BASE/OUT（输出目录）即可。
# 来源：2026-10-26 娅丽达女装实战。
"""主播排班批量拉取：复用大屏 anchor_shift_list 接口，逐 room_id 取主播名/头像/时段
先走 page.evaluate 直调（快），失败则逐场 UI 点击兜底
输出：原始资料/20261026-整合分析/anchor_shifts.json
"""
import sys, io, os, json, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

PROFILE = r'<你的本机路径>'
OUT = r'<你的项目路径> FDE\01-客户项目\20261018-娅丽达女装\原始资料\20261026-整合分析\anchor_shifts.json'
ROOMS = [
    ('7696762365035301666', '1015_1329'), ('7696802364753267491', '1015_1605'),
    ('7696852674750532352', '1015_1920'), ('7696886641650109218', '1015_2132'),
    ('7697141430338194216', '1016_1400'), ('7697223276858592000', '1016_1918'),
    ('7697597026950744847', '1017_1928'),
    ('7698238978314537743', '1019_1259'), ('7698346812016560930', '1019_1957'),
    ('7698533785729829672', '1020_0803'), ('7698572130035895090', '1020_1031'),
    ('7698710593800309531', '1020_1929'),
    ('7698904308930546466', '1021_0800'), ('7698982622113893120', '1021_1305'),
    ('7699086960196487951', '1021_1949'),
    ('7699275471560755983', '1022_0801'), ('7699355721938389795', '1022_1312'),
    ('7699391782492293898', '1022_1532'), ('7699455047374768922', '1022_1938'),
    ('7699645612844763938', '1023_0757'), ('7699665393807297331', '1023_0914'),
    ('7699725399135439616', '1023_1307'),
    ('7700017455988558592', '1024_0800'), ('7700187052888886016', '1024_1858'),
    ('7700388329157561123', '1025_0759'), ('7700481431465970447', '1025_1401'),
]

cap = {'url': None}


def on_resp(r):
    try:
        if 'anchor_shift_list' in r.url and cap['url'] is None:
            cap['url'] = r.url
    except Exception:
        pass


def ui_fetch(page, rid):
    page.goto(f'https://compass.jinritemai.com/screen/live/shop?live_room_id={rid}&live_app_id=1128'
              '&source=compass-live-detail&from_page=%2Fshop%2Flive-detail#data',
              wait_until='domcontentloaded', timeout=60000)
    time.sleep(11)
    try:
        loc = page.get_by_text('主播分析', exact=True).first
        if loc.count() and loc.is_visible():
            loc.click(timeout=3000)
            time.sleep(4)
    except Exception:
        pass


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel='msedge', headless=True,
        viewport={'width': 1920, 'height': 1080}, accept_downloads=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on('response', on_resp)

    ui_fetch(page, ROOMS[6][0])  # 用 10-17 场抓一次模板 URL
    base = cap['url']
    print('[模板URL]', '有' if base else '无', (base or '')[:120], flush=True)

    res = {}
    if base:
        for rid, lab in ROOMS:
            u = re.sub(r'room_id=\d+', f'room_id={rid}', base)
            u = re.sub(r'_lid=\d+', f'_lid={int(time.time()) % 10**9}', u)
            try:
                txt = page.evaluate(
                    """async (u) => { const r = await fetch(u, {credentials:'include'}); return await r.text(); }""", u)
                j = json.loads(txt)
                d = j.get('data') or {}
                if d.get('info_list') is not None:
                    res[lab] = {'room_id': rid, 'anchor_cnt': d.get('anchor_cnt'),
                                'shifts': d.get('info_list') or []}
                    names = [s.get('name') for s in (d.get('info_list') or [])]
                    print(f'[直调] {lab} 主播 {names}', flush=True)
                else:
                    print(f'[直调] {lab} 空 st={j.get("st")} {str(j.get("msg"))[:60]}', flush=True)
            except Exception as e:
                print(f'[直调失败] {lab} {type(e).__name__}', flush=True)
            time.sleep(0.4)

    # 兜底：直调没拿到的场次走 UI
    missing = [(r, l) for r, l in ROOMS if l not in res]
    if missing:
        print(f'[UI兜底] {len(missing)} 场', flush=True)
        for rid, lab in missing:
            cap['url'] = None
            ui_fetch(page, rid)
            u = cap['url']
            if not u:
                print(f'[UI] {lab} 无接口', flush=True)
                continue
            try:
                txt = page.evaluate(
                    """async (u) => { const r = await fetch(u, {credentials:'include'}); return await r.text(); }""", u)
                d = (json.loads(txt).get('data') or {})
                res[lab] = {'room_id': rid, 'anchor_cnt': d.get('anchor_cnt'),
                            'shifts': d.get('info_list') or []}
                print(f'[UI] {lab} 主播 {[s.get("name") for s in (d.get("info_list") or [])]}', flush=True)
            except Exception as e:
                print(f'[UI失败] {lab} {type(e).__name__}', flush=True)

    json.dump(res, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n[合计] {len(res)}/{len(ROOMS)} 场拿到排班', flush=True)
    for lab in sorted(res):
        for s in res[lab]['shifts']:
            print(f"  {lab} {s.get('name')} {s.get('live_start_ts')}→{s.get('live_end_ts')}", flush=True)
    ctx.close()
