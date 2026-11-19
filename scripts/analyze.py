# -*- coding: utf-8 -*-
"""交叉分析：xlsx 结构化数据 × 分钟级趋势 × 讲解时间轴 × 渠道分布 → analysis_results.json"""
import json, io, os, re, sys
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = r'<你的项目路径> FDE\01-客户项目\20260825-洛阳河景云\直播分析\20260913-运动专营店'
D = os.path.join(BASE, '原始数据')
B = os.path.join(BASE, '_构建脚本')

parsed = json.load(io.open(os.path.join(B, 'parsed_data.json'), encoding='utf-8'))

# ---------- 分钟级趋势 ----------
blend = json.load(io.open(os.path.join(D, 'api',
    '367_compass.jinritemai.com_compass_api_content_live_shop_live_screen_blend_trend_v3.json'), encoding='utf-8'))['data']
pay_series, cost_series = {}, {}
for t in blend['trends']:
    minute = t['horizontal'][-5:]  # HH:MM
    if t['point_name'] == 'new_pay_amt':
        pay_series[minute] = t['vertical']
    elif t['point_name'] == 'stat_cost':
        cost_series[minute] = t['vertical']

# 金额单位判断：与全场 GMV 对比
total_series_pay = sum(pay_series.values())
gmv = parsed['basic']['用户支付金额']
unit_pay = 'yuan' if abs(total_series_pay - gmv) / gmv < 0.2 else ('cent' if abs(total_series_pay/100 - gmv)/gmv < 0.2 else '?')
scale = 1 if unit_pay == 'yuan' else (0.01 if unit_pay == 'cent' else 1)
total_cost = sum(cost_series.values())

# ---------- 讲解时间轴 ----------
jj = json.load(io.open(os.path.join(D, '讲解时间轴.json'), encoding='utf-8'))
def hm_range(s, e):
    """HH:MM:SS -> 分钟列表"""
    def m(x): return int(x[:2])*60 + int(x[3:5])
    return [f'{h:02d}:{mi:02d}' for h in range(24) for mi in range(60)][m(s):m(e)+1]

for seg in jj:
    s, e = seg['开始'], seg['结束']
    seg['时长分钟'] = round((int(e[:2])*3600+int(e[3:5])*60+int(e[6:8]) - (int(s[:2])*3600+int(s[3:5])*60+int(s[6:8]))) / 60, 1)
    mins = hm_range(s, e)
    seg['时段成交'] = round(sum(pay_series.get(m, 0) for m in mins) * scale, 2)
    seg['时段投放'] = round(sum(cost_series.get(m, 0) for m in mins), 2)

# ---------- 20 分钟桶 ----------
buckets = {}
for m, v in pay_series.items():
    h, mi = int(m[:2]), int(m[3:5])
    b = f'{h:02d}:{(mi//20)*20:02d}'
    buckets[b] = buckets.get(b, 0) + v * scale
bucket_cost = {}
for m, v in cost_series.items():
    h, mi = int(m[:2]), int(m[3:5])
    b = f'{h:02d}:{(mi//20)*20:02d}'
    bucket_cost[b] = bucket_cost.get(b, 0) + v

# ---------- 流量趋势（分渠道分钟进入） ----------
ft = json.load(io.open(os.path.join(D, 'api',
    '375_compass.jinritemai.com_compass_api_content_live_shop_live_screen_flow_trend.json'), encoding='utf-8'))['data']
chan_min = {}
for t in ft['trends']:
    chan_min.setdefault(t['display_name'], {})[t['horizontal'][-5:]] = t['vertical']

# ---------- 渠道分布（含 GPM） ----------
fd = json.load(io.open(os.path.join(D, 'api',
    '374_compass.jinritemai.com_compass_api_content_live_shop_live_screen_flow_distribution.json'), encoding='utf-8'))['data']
channels_gpm = []
for c in fd.get('natural_data', []):
    channels_gpm.append({'渠道': c['channel_name'],
                         '支付金额': c['pay_amt']['value']/100,
                         'GPM': c['gpm']['value']/100,
                         '支付占比': c['pay_ratio']['value'],
                         '观看占比': c.get('watch_ratio', {}).get('value')})
    for sub in c.get('sub_flow', []):
        channels_gpm.append({'渠道': '  └ ' + sub['channel_name'],
                             '支付金额': sub['pay_amt']['value']/100,
                             'GPM': sub['gpm']['value']/100,
                             '支付占比': sub['pay_ratio']['value'],
                             '观看占比': sub.get('watch_ratio', {}).get('value')})

# ---------- 关键计算 ----------
overview = parsed['overview']
refund_rate_amt = overview['退款金额_num'] / gmv
products = parsed['products']
main = products[0]
zero_products = [p for p in products if p['支付金额'] == 0]
zero_exposure = sum(p['曝光人数'] for p in zero_products)
total_exposure = sum(p['曝光人数'] for p in products)

results = {
    '单位换算': {'pay_series单位': unit_pay, '分钟成交合计_换算前': total_series_pay,
                '全场GMV': gmv, '投放消耗合计_原始': total_cost},
    '漏斗': {
        '曝光人数': 395300, '进入人数': 31500, '曝光观看率': 0.0796,
        '商品曝光人数': 20200, '商品点击人数': 5902, '成交人数': 244,
        '观看_商品曝光率': 20200/31500, '商品曝光_点击率': 5902/20200,
        '点击_成交率': 244/5902, '观看_成交率': 244/31500,
        '客单价': overview['客单价_num'], 'GPM': parsed['basic']['千次观看支付金额'],
    },
    '退款': {'退款金额': overview['退款金额_num'], '金额退款率': refund_rate_amt,
            '退款订单': int(overview['退款订单数']), '订单退款率': 84/265,
            '主力款退款金额': main['退款金额'], '主力款金额退款率': main['退款金额']/main['支付金额']},
    '商品结构': {
        '上架商品数': len(products), '有成交商品数': parsed['check']['有成交商品数'],
        '主力款支付占比': main['支付金额']/gmv,
        '主力款': {'名称': main['商品名称'], '支付金额': main['支付金额'],
                  '成交件数': main['成交件数'], '曝光人数': main['曝光人数'],
                  '点击人数': main['点击人数'], '曝光点击率': main['曝光点击率'],
                  '点击成交率': main['点击成交率']},
        '零单款数': len(zero_products), '零单款曝光合计': zero_exposure,
        '零单款曝光占比': zero_exposure/total_exposure if total_exposure else 0,
    },
    '渠道GPM': channels_gpm,
    '讲解时段': jj,
    '成交20分钟桶': {k: round(v, 2) for k, v in sorted(buckets.items())},
    '投放20分钟桶': {k: round(v, 2) for k, v in sorted(bucket_cost.items())},
    '分渠道分钟进入': chan_min,
    '分钟成交序列': {k: round(v*scale, 2) for k, v in sorted(pay_series.items())},
    '分钟投放序列': dict(sorted(cost_series.items())),
}

with io.open(os.path.join(B, 'analysis_results.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=1)

# 打印关键结论
print('金额单位:', unit_pay, '| 分钟成交合计:', round(total_series_pay*scale,0), 'vs GMV', gmv)
print('投放消耗合计(原始单位):', total_cost)
print('金额退款率: %.1f%%' % (refund_rate_amt*100), '| 主力款退款率: %.1f%%' % (main['退款金额']/main['支付金额']*100))
print('主力款占比: %.1f%%' % (main['支付金额']/gmv*100))
print('零单款: %d 个, 曝光占比 %.1f%%' % (len(zero_products), zero_exposure/total_exposure*100))
print('\n20分钟桶成交:')
for k, v in sorted(buckets.items()):
    bar = '█' * int(v/300)
    print(f'  {k}  ¥{v:8.0f} {bar}')
print('\n讲解时段TOP:')
for seg in sorted(jj, key=lambda x: -x['时段成交'])[:8]:
    print(f"  {seg['开始']}-{seg['结束']} {seg['时长分钟']}min 成交¥{seg['时段成交']:.0f} 投放{seg['时段投放']:.0f}")
