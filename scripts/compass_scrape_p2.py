# -*- coding: utf-8 -*-
"""罗盘直播大屏深抓 pass2：侧边栏(商品/人群/千川) + 顶部Tab + 讲解列表滚动收集 + 更多操作菜单"""
import sys, io, os, json, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

PROFILE = r'<你的项目路径>'
BASE = r'<你的项目路径> FDE\01-客户项目\20260825-洛阳河景云\直播分析\20260913-运动专营店'
DATA = os.path.join(BASE, '原始数据')
API_DIR = os.path.join(DATA, 'api2')
os.makedirs(API_DIR, exist_ok=True)
TARGET_URL = ('https://compass.jinritemai.com/screen/live/shop'
              '?live_room_id=7684940960790285071&live_app_id=1128'
              '&source=compass-live-detail#data')

video_urls, api_count = [], [0]

def on_response(resp):
    u = resp.url
    try:
        if re.search(r'\.(m3u8)(\?|$)|liveplay|timeshift|/replay/|playback', u, re.I):
            video_urls.append(u)
            print(f'[回放URL] {u[:220]}', flush=True)
        ct = resp.headers.get('content-type', '')
        if 'json' in ct and not re.search(r'\.(js|css|png|jpg|svg|woff)', u):
            api_count[0] += 1
            try:
                body = resp.body()
            except Exception:
                return
            if len(body) < 50:
                return
            fn = re.sub(r'[^A-Za-z0-9_.-]', '_', u.split('?')[0].split('//')[-1])[-120:]
            with open(os.path.join(API_DIR, f'{api_count[0]:03d}_{fn}.json'), 'wb') as f:
                f.write(body)
    except Exception:
        pass

def page_text(page):
    try:
        return '\n'.join(page.locator('body').all_inner_texts())
    except Exception:
        return ''

def snap(page, name):
    page.screenshot(path=os.path.join(DATA, f'_{name}.png'))
    io.open(os.path.join(DATA, f'_{name}.txt'), 'w', encoding='utf-8').write(page_text(page))
    print(f'[快照] {name}', flush=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel='msedge', headless=False,
        viewport={'width': 1920, 'height': 1080}, accept_downloads=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on('response', on_response)
    page.goto(TARGET_URL, wait_until='domcontentloaded', timeout=60000)
    time.sleep(15)
    snap(page, 'p2_data')

    # 1) 滚动收集讲解列表（右侧 marker 面板）
    print('[讲解列表] 开始滚动收集', flush=True)
    seen = set()
    jiangjie = []
    try:
        panel = page.locator('text=讲解成交').first
        # 找可滚动容器：讲解条目所在的滚动父级
        scroll_js = """() => {
            const els = document.querySelectorAll('*');
            let best = null;
            for (const el of els) {
                if (el.scrollHeight > el.clientHeight + 50 && el.clientHeight > 200
                    && el.innerText && el.innerText.includes('讲解成交')) {
                    if (!best || el.clientHeight < best.clientHeight) best = el;
                }
            }
            return best;
        }"""
        handle = page.evaluate_handle(scroll_js)
        el = handle.as_element()
        if el:
            stable = 0
            for step in range(60):
                txt = el.inner_text()
                for m in re.finditer(r'([^\n]{10,80})\n讲解成交\n(¥[\d,.]+)\n(\d{2}:\d{2}:\d{2})～(\d{2}:\d{2}:\d{2})', txt):
                    key = (m.group(3), m.group(4))
                    if key not in seen:
                        seen.add(key)
                        jiangjie.append({'商品': m.group(1), '讲解成交': m.group(2),
                                         '开始': m.group(3), '结束': m.group(4)})
                before = len(seen)
                el.evaluate('e => e.scrollTop += 500')
                time.sleep(1.2)
                if len(seen) == before:
                    stable += 1
                    if stable >= 5:
                        break
                else:
                    stable = 0
        print(f'[讲解列表] 收集 {len(jiangjie)} 段', flush=True)
        io.open(os.path.join(DATA, '讲解时间轴.json'), 'w', encoding='utf-8').write(
            json.dumps(jiangjie, ensure_ascii=False, indent=1))
    except Exception as e:
        print('[讲解列表失败]', type(e).__name__, e, flush=True)

    # 2) 顶部 Tab 逐个点击
    for kw in ['流量分析', '引流短视频', '流量诊断', '主播分析', '违规情况']:
        try:
            loc = page.locator(f'div:text-is("{kw}"), span:text-is("{kw}")').first
            if loc.count() and loc.is_visible():
                loc.click(timeout=4000)
                time.sleep(6)
                snap(page, f'p2_tab_{kw}')
            else:
                print(f'[Tab不可见] {kw}', flush=True)
        except Exception as e:
            print(f'[Tab失败] {kw}: {type(e).__name__}', flush=True)

    # 3) 侧边栏：商品 / 人群 / 千川
    for kw in ['商品', '人群', '千川']:
        try:
            loc = page.locator(f'div:text-is("{kw}")').first
            if loc.count() and loc.is_visible():
                loc.click(timeout=4000)
                time.sleep(7)
                snap(page, f'p2_side_{kw}')
            else:
                print(f'[侧栏不可见] {kw}', flush=True)
        except Exception as e:
            print(f'[侧栏失败] {kw}: {type(e).__name__}', flush=True)

    # 4) 更多操作菜单（找下载/回放入口）
    try:
        page.locator('text=更多操作').first.click(timeout=4000)
        time.sleep(3)
        snap(page, 'p2_more_menu')
        t = page_text(page)
        for kw in ['下载', '回放', '录屏', '导出']:
            if kw in t:
                print(f'[更多操作含] {kw}', flush=True)
    except Exception as e:
        print('[更多操作失败]', type(e).__name__, flush=True)

    io.open(os.path.join(DATA, '_replay_urls.txt'), 'w', encoding='utf-8').write('\n'.join(video_urls))
    print(f'[完成] API {api_count[0]} 个, 回放URL {len(video_urls)} 个', flush=True)
    print('[3 分钟后关闭浏览器]', flush=True)
    time.sleep(180)
    ctx.close()
