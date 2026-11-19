# -*- coding: utf-8 -*-
"""解析整场数据下载 xlsx → 结构化 JSON（供报告用）"""
import pandas as pd, json, io, re, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = r'<你的项目路径> FDE\01-客户项目\20260825-洛阳河景云\直播分析\20260913-运动专营店'
XLSX = BASE + r'\原始数据\直播间详情页_河景云运动专营店精选直播间_2026-09-13_16-56-58_整场数据下载.xlsx'

def money(s):
    if s is None: return 0.0
    s = str(s).replace('¥', '').replace(',', '').strip()
    try: return float(s)
    except: return 0.0

def wan(s):
    """'3.1万' -> 31000, '5902' -> 5902"""
    s = str(s).strip()
    m = re.match(r'^([\d.]+)万$', s)
    if m: return float(m.group(1)) * 10000
    try: return float(s.replace(',', ''))
    except: return 0.0

xl = pd.ExcelFile(XLSX)
out = {}

# 基本信息
df = xl.parse('基本信息', header=0)
r = df.iloc[0]
out['basic'] = {
    '达人昵称': r['达人昵称'], '达人等级': int(r['达人等级']),
    '抖音号': str(r['抖音号or火山号']), '达人类型': r['达人类型'],
    '粉丝数_开播前一天': r['开播前一天粉丝数'],
    '直播时间': r['直播时间'], '直播时长': r['直播时长'],
    '用户支付金额': money(r['直播间用户支付金额']),
    '千次观看支付金额': money(r['千次观看用户支付金额']),
}

# 整体看板
df = xl.parse('整体看板', header=0)
r = df.iloc[0]
out['overview'] = {c: (str(r[c]) if not isinstance(r[c], (int, float)) else r[c]) for c in df.columns}
out['overview']['观看人数'] = wan(r['直播间观看人数'])
out['overview']['客单价_num'] = money(r['客单价'])
out['overview']['退款金额_num'] = money(r['退款金额'])

# 流量转化漏斗
df = xl.parse('流量分析-流量转化', header=None)
out['funnel'] = {str(df.iloc[i, 0]): str(df.iloc[i, 1]) for i in range(len(df))}

# 渠道分析
df = xl.parse('流量分析-渠道分析', header=0)
channels = []
for _, r in df.iterrows():
    channels.append({
        '渠道': r['渠道名称'], '人均观看时长': str(r['人均观看时长']),
        '观看人数': wan(r['观看人数']), '观看次数': wan(r['观看次数']),
        '互动率': str(r['直播间观看-互动率(次数)']),
        '支付金额': money(r['用户支付金额']),
        '订单数': int(r['成交订单数']), '笔单价': money(r['笔单价']),
        '观看成交率': str(r['直播间观看-成交率(次数)']),
    })
out['channels'] = channels

# 短视频引流
df = xl.parse('流量分析-短视频引流', header=0)
out['short_video'] = df.to_dict('records')

# 商品明细：按"商品名称"行切块，商品行 + SKU 行
df = xl.parse('商品分析-商品明细', header=None)
products = []
cur = None
for i in range(1, len(df)):
    row = df.iloc[i]
    c0, c1 = row[0], row[1]
    if str(c0) == '商品名称':
        continue
    if str(c0) == '-' and str(c1) == '-':
        continue
    if pd.notna(c1) and str(c1).strip().isdigit() and len(str(c1).strip()) > 10:
        # 商品行
        cur = {
            '商品名称': str(c0), '商品ID': str(c1),
            '支付金额': money(row[3]), '成交件数': int(row[4]),
            '成交人数': int(row[5]), '成交订单数': int(row[6]),
            '曝光人数': wan(row[9]), '点击人数': wan(row[10]),
            '曝光点击率': str(row[11]), '点击成交率': str(row[12]),
            '退款人数': int(row[13]), '退款金额': money(row[14]), '退款订单数': int(row[15]),
            'skus': [],
        }
        products.append(cur)
    elif cur is not None and pd.notna(row[2]) and 'sku' not in str(row[2]):
        sku_name = str(row[2])
        cur['skus'].append({'sku': sku_name, '支付金额': money(row[4]),
                            '成交件数': int(float(row[5])) if pd.notna(row[5]) else 0,
                            '退款金额': money(row[11])})
out['products'] = products

# 汇总校验
total_pay = sum(p['支付金额'] for p in products)
total_refund = sum(p['退款金额'] for p in products)
out['check'] = {'商品支付合计': total_pay, '商品退款合计': total_refund,
                '商品数': len(products), '有成交商品数': sum(1 for p in products if p['支付金额'] > 0)}

with io.open(BASE + r'\_构建脚本\parsed_data.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print('校验:', json.dumps(out['check'], ensure_ascii=False))
print('主力款:', products[0]['商品名称'][:40], products[0]['支付金额'])
for p in products:
    if p['支付金额'] > 0:
        print(f"  有成交: {p['商品名称'][:38]} ¥{p['支付金额']:.0f} {p['成交件数']}件 退款¥{p['退款金额']:.0f}")
