# -*- coding: utf-8 -*-
"""娅丽达 整合分析 · 数据集构建
1) 罗盘 54 场自营场次（30天）→ 场次级指标 + 退款成熟度归一
2) 订单 5.3 万行 → 退款成熟度曲线 g(n)
3) 千川 11 天直播/商品日数据 → 日级对齐
输出：原始资料/20261026-整合分析/analysis_dataset.json + 打印摘要
"""
import sys, io, json, re, warnings, datetime
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

BASE = r'<你的项目路径> FDE\01-客户项目\20261018-娅丽达女装'
XLSX = BASE + r'\原始资料\20261026-整合分析\场次清单\下载\直播明细_自营账号_20260926_20261025.xlsx'
RID = BASE + r'\原始资料\20261026-整合分析\场次清单\自营场次_带roomid.json'
QC = BASE + r'\原始资料\20261026-整合分析\qianchuan\qc_13d_raw.json'
ORD = BASE + r'\原始资料\20261018-主播分析\订单\解压\1792304698_f3dbf908492bee6ea8257554a78f91aeJWpdlqPW.csv'
OUT = BASE + r'\原始资料\20261026-整合分析\analysis_dataset.json'
TODAY = datetime.datetime(2026, 10, 26)

# ---------- 1) 场次表 ----------
df = pd.read_excel(XLSX)
df.columns = [str(c).strip() for c in df.columns]
df = df[df['直播开始时间'].notna()].copy()
df['t'] = pd.to_datetime(df['直播开始时间'])
df['day'] = df['t'].dt.strftime('%Y-%m-%d')
rid = pd.DataFrame(json.load(open(RID, encoding='utf-8')))
rid['t'] = pd.to_datetime(rid['start'])
df = df.sort_values('t')
# 最近时间对齐（导出表与列表接口秒级不一致，允许 5 分钟）
s = pd.merge_asof(df, rid[['t', 'room_id']].sort_values('t'), on='t',
                  direction='nearest', tolerance=pd.Timedelta('300s'))
s['room_id'] = s['room_id'].fillna('')

def num(x):
    try:
        return float(x)
    except Exception:
        return np.nan

S = []
for _, r in s.iterrows():
    pay = num(r['直播间成交金额'])
    ordn = num(r['直播间成交订单数'])
    watch = num(r['直播间观看人数'])
    cost = num(r['投放消耗(店铺绑定)'])
    refund = num(r['直播间退款金额'])
    age = (TODAY - r['t']).days
    S.append({
        'start': r['t'].strftime('%Y-%m-%d %H:%M'),
        'day': r['day'],
        'room_id': r['room_id'],
        'dur': num(r['直播时长(分钟)']),
        'expo': num(r['直播间曝光人数']),
        'watch': watch,
        'online_avg': num(r['平均在线人数']),
        'online_max': num(r['最高在线人数']),
        'stay_min': num(r['人均观看时长(分钟)']),
        'pay': pay,
        'orders': ordn,
        'buyers': num(r['直播间成交人数']),
        'aov': (pay / ordn) if ordn else np.nan,
        'gpm': (pay / watch * 1000) if watch else np.nan,
        'expo_rate': (watch / num(r['直播间曝光人数'])) if num(r['直播间曝光人数']) else np.nan,
        'ctr': num(r['商品曝光-点击率(人数)']),
        'cvr': num(r['商品点击-成交率(人数)']),
        'watch_cvr': num(r['观看-成交率(人数)']),
        'cost': cost,
        'ad_share': (cost / pay) if pay else np.nan,
        'refund': refund,
        'refund_rate': (refund / pay) if pay else np.nan,
        'net_pay': num(r['净成交金额']),
        'refund_1h_rate': num(r['1小时退款率']),
        'new_fans': num(r['新增粉丝数']),
        'comments': num(r['评论次数']),
        'age_days': age,
        'coupon': num(r['消费券引导支付占比']),
    })
S = pd.DataFrame(S)

# ---------- 2) 退款成熟度曲线 ----------
o = pd.read_csv(ORD, usecols=['支付完成时间', '订单应付金额', '订单状态', '售后状态'], low_memory=False)
o = o[o['支付完成时间'].notna()].copy()
o['pt'] = pd.to_datetime(o['支付完成时间'], errors='coerce')
o = o[o['pt'].notna()]
o['paid'] = pd.to_numeric(o['订单应付金额'].astype(str).str.replace(',', ''), errors='coerce')
o['is_refund'] = (o['售后状态'].astype(str).str.contains('退款成功')).astype(int)
o['is_preship'] = (o['is_refund'] == 1) & (o['订单状态'].astype(str).str.contains('已关闭'))
o['is_return'] = (o['is_refund'] == 1) & (~o['订单状态'].astype(str).str.contains('已关闭'))
o['age'] = (pd.Timestamp('2026-10-18') - o['pt']).dt.days  # 订单快照日=2026-10-18
o = o[o['age'] >= 0]
curves = []
for a in range(0, 46):
    sub = o[o['age'] == a]
    if len(sub) < 30:
        continue
    curves.append({
        'age': a, 'n': int(len(sub)),
        'refund_rate': float(sub['is_refund'].mean()),
        'preship_rate': float(sub['is_preship'].mean()),
        'return_rate': float(sub['is_return'].mean()),
    })
C = pd.DataFrame(curves)
# 单调化（累计最大值）：退款只会累积，不会减少
C['refund_rate'] = C['refund_rate'].cummax()
C['preship_rate'] = C['preship_rate'].cummax()
C['return_rate'] = C['return_rate'].cummax()

# 成熟基线（年龄>=30 天的批次平均）
mature = o[o['age'] >= 30]
base = {
    'n': int(len(mature)),
    'refund_rate': float(mature['is_refund'].mean()),
    'preship_rate': float(mature['is_preship'].mean()),
    'return_rate': float(mature['is_return'].mean()),
}

# 曲线截顶：任意年龄的累计退款率不应高于成熟基线（小样本日会把曲线推高）
C['refund_rate'] = C['refund_rate'].clip(upper=base['refund_rate'])

# g(n)：年龄 n 的批次退款率 / 成熟基线 → 观察窗完成度（插值覆盖所有年龄）
_g = C.set_index('age')['refund_rate'] / base['refund_rate'] if base['refund_rate'] else None
_g = _g[~_g.index.duplicated()].sort_index()


def g_of(age):
    if _g is None or len(_g) == 0 or not np.isfinite(age):
        return np.nan
    a = min(int(age), int(_g.index.max()))
    if a in _g.index:
        return float(_g.loc[a])
    lo = _g.index[_g.index <= a].max() if (a >= _g.index.min()) else None
    if lo is None:
        return float(_g.iloc[0])
    return float(_g.loc[lo])


S['refund_completion'] = S['age_days'].map(g_of)
S['refund_rate_norm'] = [ (rr / g_of(a)) if (np.isfinite(rr) and np.isfinite(g_of(a)) and g_of(a) > 0) else np.nan
                          for rr, a in zip(S['refund_rate'], S['age_days']) ]
S['refund_rate_norm'] = S['refund_rate_norm'].clip(upper=1.5)

# ---------- 3) 千川日数据 ----------
qc = json.load(open(QC, encoding='utf-8'))


def qnum(rec, k):
    try:
        return float(rec.get(k) or 0)
    except Exception:
        return 0.0


qlive = {}
for r in qc['live_day']:
    qlive[r['stat_time_day']] = {
        'cost': qnum(r, 'stat_cost'),
        'settle': qnum(r, 'total_order_settle_amount_for_roi2_1h'),
        'orders': qnum(r, 'total_order_settle_count_for_roi2_1h'),
        'pay_orders': qnum(r, 'total_pay_order_count_for_roi2'),
        'pay_roi': qnum(r, 'total_prepay_and_pay_order_roi2'),
        'gross': qnum(r, 'total_pay_order_gmv_include_coupon_for_roi2'),
        'refund_1h': qnum(r, 'total_refund_order_gmv_for_roi2_1h_rate'),
    }
qprod = {}
for r in qc['product_plan']:
    k = r['stat_time_day']
    a = qprod.setdefault(k, {'cost': 0, 'settle': 0, 'orders': 0})
    a['cost'] += qnum(r, 'stat_cost_for_roi2')
    a['settle'] += qnum(r, 'total_order_settle_amount_for_roi2_1h')
    a['orders'] += qnum(r, 'total_order_settle_count_for_roi2_1h')

# 日级对齐（罗盘场次汇总 vs 千川）
daily = []
for day, grp in S.groupby('day'):
    q = qlive.get(day, {})
    qp = qprod.get(day, {})
    daily.append({
        'day': day,
        'sessions': int(len(grp)),
        'watch': float(grp['watch'].sum()),
        'pay': float(grp['pay'].sum()),
        'orders': float(grp['orders'].sum()),
        'cost_room': float(grp['cost'].sum()),
        'refund': float(grp['refund'].sum()),
        'aov': float(grp['pay'].sum() / grp['orders'].sum()) if grp['orders'].sum() else np.nan,
        'gpm': float(grp['pay'].sum() / grp['watch'].sum() * 1000) if grp['watch'].sum() else np.nan,
        'qc_cost': q.get('cost', 0),
        'qc_settle': q.get('settle', 0),
        'qc_orders': q.get('orders', 0),
        'qc_pay_orders': q.get('pay_orders', 0),
        'qc_roi': (q.get('settle', 0) / q.get('cost')) if q.get('cost') else np.nan,
        'qc_prod_cost': qp.get('cost', 0),
        'qc_prod_roi': (qp.get('settle') / qp['cost']) if qp.get('cost') else np.nan,
    })
D = pd.DataFrame(daily).sort_values('day')

# ---------- 4) 相关性 ----------
def corr_table(frame, cols, label):
    rows = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            sub = frame[[a, b]].dropna()
            if len(sub) < 8 or sub[a].std() == 0 or sub[b].std() == 0:
                continue
            rows.append({
                'x': a, 'y': b, 'n': int(len(sub)),
                'pearson': round(float(sub[a].corr(sub[b], method='pearson')), 3),
                'spearman': round(float(sub[a].corr(sub[b], method='spearman')), 3),
            })
    return sorted(rows, key=lambda z: -abs(z['pearson']))


SESSION_COLS = ['watch', 'online_avg', 'stay_min', 'expo_rate', 'ctr', 'cvr', 'watch_cvr',
                'aov', 'gpm', 'pay', 'cost', 'ad_share', 'refund_rate_norm', 'new_fans', 'comments', 'dur']
C54 = corr_table(S, SESSION_COLS, 'session')
# 只看转化效率相关（去掉成交额/观看这类必然强相关）
EFF = ['stay_min', 'expo_rate', 'ctr', 'cvr', 'watch_cvr', 'aov', 'gpm', 'ad_share',
       'refund_rate_norm', 'new_fans', 'comments']
C_EFF = corr_table(S, EFF, 'eff')
D_COLS = ['qc_cost', 'pay', 'orders', 'aov', 'gpm', 'qc_roi', 'qc_orders', 'cost_room']
C_DAY = corr_table(D[D['day'] >= '2026-10-15'], D_COLS, 'day')

# ---------- 5) 主播对比（已有归属的 7 场）----------
HOST = {'7697597026950744847': 'A', '7697141430338194216': 'A', '7696886641650109218': 'A',
        '7697223276858592000': 'B', '7696852674750532352': 'B', '7696802364753267491': 'B',
        '7696762365035301666': 'B'}
S['host'] = S['room_id'].map(HOST).fillna('')
host_rows = []
for h in ['A', 'B']:
    g2 = S[S['host'] == h]
    if len(g2) == 0:
        continue
    host_rows.append({
        'host': h, 'sessions': int(len(g2)),
        'watch_avg': round(float(g2['watch'].mean()), 0),
        'online_avg': round(float(g2['online_avg'].mean()), 1),
        'stay_avg': round(float(g2['stay_min'].mean()), 2),
        'pay_avg': round(float(g2['pay'].mean()), 0),
        'gpm_avg': round(float(g2['gpm'].mean()), 0),
        'aov_avg': round(float(g2['aov'].mean()), 1),
        'ctr_avg': round(float(g2['ctr'].mean()), 4),
        'cvr_avg': round(float(g2['cvr'].mean()), 4),
        'watch_cvr_avg': round(float(g2['watch_cvr'].mean()), 5),
        'refund_raw': round(float(g2['refund_rate'].mean()), 4),
        'refund_norm': round(float(g2['refund_rate_norm'].mean()), 4),
        'ad_share': round(float(g2['ad_share'].mean()), 3),
        'new_fans_avg': round(float(g2['new_fans'].mean()), 1),
        'comments_avg': round(float(g2['comments'].mean()), 1),
    })

out = {
    'sessions': S.replace({np.nan: None}).to_dict(orient='records'),
    'daily': D.replace({np.nan: None}).to_dict(orient='records'),
    'refund_curve': C.to_dict(orient='records'),
    'refund_mature_baseline': base,
    'corr_session': C54,
    'corr_eff': C_EFF,
    'corr_daily': C_DAY,
    'host_compare': host_rows,
}
json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)

# ---------- 打印摘要 ----------
print('=== 场次 ===')
print('总场次', len(S), '｜10-15~10-25 场次', len(S[(S['day'] >= '2026-10-15') & (S['day'] <= '2026-10-25')]))
print('有 room_id 的', (S['room_id'] != '').sum())
print('\n=== 退款成熟度 ===')
print('成熟基线(≥30天): n=%d 退款率 %.1f%% 发前 %.1f%% 退货 %.1f%%' % (
    base['n'], base['refund_rate'] * 100, base['preship_rate'] * 100, base['return_rate'] * 100))
print(C.to_string(index=False))
print('\n=== 场次拒绝退款率（观察窗越短低估越多）===')
tmp = S[['start', 'day', 'age_days', 'refund_rate', 'refund_completion', 'refund_rate_norm', 'pay']].copy()
tmp['start'] = tmp['start'].str[5:]
print(tmp[tmp['day'] >= '2026-10-12'].to_string(index=False, float_format=lambda x: f'{x:.3f}'))
print('\n=== 日级对齐（罗盘 vs 千川）===')
print(D[D['day'] >= '2026-10-15'].to_string(index=False, float_format=lambda x: f'{x:.2f}'))
print('\n=== 主播对比（7场）===')
for h in host_rows:
    print(h)
print('\n=== 相关性 Top（场次 n=%d，效率类）===' % len(S))
for r in C_EFF[:18]:
    print(f"  {r['x']:16s} ~ {r['y']:16s} n={r['n']:3d} pearson={r['pearson']:+.3f} spearman={r['spearman']:+.3f}")
print('\n=== 相关性（日级 n=%d）===' % len(D[D['day'] >= '2026-10-15']))
for r in C_DAY[:15]:
    print(f"  {r['x']:12s} ~ {r['y']:12s} n={r['n']:2d} pearson={r['pearson']:+.3f} spearman={r['spearman']:+.3f}")

print('\n=== 退款曲线前 20 天 ===')
print(C[C['age'] <= 20].to_string(index=False, float_format=lambda x: f'{x:.3f}'))

print('\n=== 指定配对（场次级）===')
PAIRS = [('stay_min', 'gpm'), ('stay_min', 'refund_rate_norm'), ('stay_min', 'aov'),
         ('aov', 'refund_rate_norm'), ('cvr', 'refund_rate_norm'), ('ctr', 'refund_rate_norm'),
         ('ad_share', 'refund_rate_norm'), ('ad_share', 'gpm'), ('cost', 'refund_rate'), ('cost', 'aov'),
         ('watch', 'refund_rate'), ('online_avg', 'gpm'), ('dur', 'gpm'), ('comments', 'refund_rate_norm'),
         ('new_fans', 'refund_rate_norm'), ('pay', 'refund_rate'), ('expo_rate', 'stay_min'),
         ('watch_cvr', 'aov'), ('aov', 'gpm'), ('ctr', 'watch')]
for a, b in PAIRS:
    sub = S[[a, b]].dropna()
    if len(sub) < 8:
        print(f'  {a} ~ {b}: n={len(sub)} 样本不足')
        continue
    print(f"  {a:16s} ~ {b:18s} n={len(sub):3d} pearson={sub[a].corr(sub[b]):+.3f} spearman={sub[a].corr(sub[b],method='spearman'):+.3f}")

print('\n=== 指定配对（日级）===')
for a, b in [('aov', 'qc_roi'), ('qc_cost', 'aov'), ('qc_cost', 'gpm'), ('orders', 'aov'),
             ('day_idx', 'aov')]:
    DD = D[D['day'] >= '2026-10-15'].copy()
    DD['day_idx'] = range(len(DD))
    sub = DD[[a, b]].dropna()
    if len(sub) >= 5:
        print(f"  {a:10s} ~ {b:10s} n={len(sub):2d} pearson={sub[a].corr(sub[b]):+.3f} spearman={sub[a].corr(sub[b],method='spearman'):+.3f}")

print('\n=== 主播覆盖 ===')
print('有 room_id：', int((S['room_id'].astype(str) != '').sum()), '/', len(S))
print('已归属：', int((S['host'] != '').sum()))
print('\n写盘:', OUT)
