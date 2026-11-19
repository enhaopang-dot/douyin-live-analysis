# -*- coding: utf-8 -*-
"""抖音电商罗盘 直播复盘抓取 v1（探路版）
- 持久化 Edge profile: browser-profiles/edge-douyin-compass
- 未登录则停二维码等用户扫码（飞书通知）
- 拦截全部 JSON API 响应落盘 + 各 Tab 全文快照 + 截图
- 抓回放流地址（m3u8/mp4）
"""
import sys, io, os, json, time, re, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

PROFILE = r'<你的项目路径>'
BASE = r'<你的项目路径> FDE\01-客户项目\20260825-洛阳河景云\直播分析\20260913-运动专营店'
DATA = os.path.join(BASE, '原始数据')
API_DIR = os.path.join(DATA, 'api')
os.makedirs(API_DIR, exist_ok=True)

TARGET_URL = ('https://compass.jinritemai.com/screen/live/shop'
              '?live_room_id=7684940960790285071&live_app_id=1128'
              '&source=compass-live-detail#data')

video_urls = []
api_count = [0]

def on_response(resp):
    u = resp.url
    try:
        if re.search(r'\.(m3u8|mp4|flv)(\?|$)|liveplay|timeshift|replay', u, re.I):
            video_urls.append(u)
            print(f'[视频URL] {u[:220]}', flush=True)
        ct = resp.headers.get('content-type', '')
        if ('json' in ct) and ('compass' in u or 'jinritemai' in u or 'byteoversea' not in u):
            if re.search(r'\.(js|css|png|jpg|svg|woff)', u):
                return
            api_count[0] += 1
            n = api_count[0]
            try:
                body = resp.body()
            except Exception:
                return
            if len(body) < 50:
                return
            fn = re.sub(r'[^A-Za-z0-9_.-]', '_', u.split('?')[0].split('//')[-1])[-120:]
            with open(os.path.join(API_DIR, f'{n:03d}_{fn}.json'), 'wb') as f:
                f.write(body)
    except Exception:
        pass

def logged_in(ctx):
    """通过 sessionid cookie 判定真实登录态"""
    try:
        for c in ctx.cookies('https://compass.jinritemai.com'):
            if c['name'] in ('sessionid', 'sessionid_ss', 'sid_tt') and c['value']:
                return True
    except Exception:
        pass
    return False

def page_text(page):
    try:
        return '\n'.join(page.locator('body').all_inner_texts())
    except Exception:
        return ''

def snap(page, name):
    page.screenshot(path=os.path.join(DATA, f'_{name}.png'), full_page=False)
    io.open(os.path.join(DATA, f'_{name}.txt'), 'w', encoding='utf-8').write(page_text(page))
    print(f'[快照] {name}', flush=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel='msedge', headless=False,
        viewport={'width': 1920, 'height': 1080}, accept_downloads=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on('response', on_response)

    page.goto(TARGET_URL, wait_until='domcontentloaded', timeout=60000)
    time.sleep(8)
    snap(page, 'step1_loaded')
    t = page_text(page)
    print('[页面文本前500]', t[:500].replace('\n', ' | '), flush=True)

    # 登录判定：以 sessionid cookie 为准
    need_login = not logged_in(ctx)
    if need_login:
        # 直接去罗盘首页登录
        page.goto('https://compass.jinritemai.com/', wait_until='domcontentloaded', timeout=60000)
        time.sleep(8)
        for kw in ['登录', '扫码登录']:
            try:
                loc = page.locator(f'button:has-text("{kw}")').first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=4000)
                    print(f'[自动点击] {kw}', flush=True)
                    time.sleep(5)
                    break
            except Exception:
                pass
        snap(page, 'login_qr')
        print('[需要登录] 已停在登录页，等待用户手动登录', flush=True)
        ok = False
        for i in range(180):  # 15 分钟
            time.sleep(5)
            if logged_in(ctx):
                ok = True
                break
            if i % 6 == 0:
                print(f'[等待登录] {i*5}s url={page.url[:80]}', flush=True)
        if not ok:
            print('[失败] 登录超时', flush=True)
            snap(page, 'login_timeout')
            ctx.close(); sys.exit(1)
        print('[登录成功] 回到目标大屏页', flush=True)
        page.goto(TARGET_URL, wait_until='domcontentloaded', timeout=60000)
        time.sleep(15)
        t = page_text(page)
        if '不支持访问' in t:
            print('[警告] 登录后仍提示账号类型不支持直播大屏', flush=True)
    else:
        print('[已登录]', flush=True)

    snap(page, 'step2_data_tab')
    print('[URL]', page.url, flush=True)

    # 若大屏被拦，转去直播详情页（用户上午下 xlsx 的页面）
    t = page_text(page)
    if '不支持访问' in t or len(t) < 100:
        print('[转进] 直播详情页 /shop/live-detail', flush=True)
        page.goto('https://compass.jinritemai.com/shop/live-detail?live_room_id=7684940960790285071',
                  wait_until='domcontentloaded', timeout=60000)
        time.sleep(12)
        snap(page, 'step3_live_detail')
        t = page_text(page)

    # 枚举页面 Tab/按钮关键词
    for kw in ['复盘', '讲解', '回放', '录屏', '下载', '商品', '流量', '观众']:
        print(f'[关键词探测] {kw}: {"有" if kw in t else "无"}', flush=True)

    # 尝试点击可见的 tab 文本
    for kw in ['复盘', '直播回放', '回放', '讲解', '商品分析', '流量分析']:
        try:
            loc = page.locator(f'text={kw}').first
            if loc.count() and loc.is_visible():
                loc.click(timeout=4000)
                print(f'[点击] {kw}', flush=True)
                time.sleep(6)
                snap(page, f'tab_{kw}')
        except Exception as e:
            print(f'[点击失败] {kw}: {type(e).__name__}', flush=True)

    # 汇总
    io.open(os.path.join(DATA, '_video_urls.txt'), 'w', encoding='utf-8').write('\n'.join(video_urls))
    print(f'[完成] API响应 {api_count[0]} 个, 视频URL {len(video_urls)} 个', flush=True)
    print('[浏览器保持打开 5 分钟供人工检查]', flush=True)
    time.sleep(300)
    ctx.close()
