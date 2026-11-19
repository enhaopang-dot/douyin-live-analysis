# -*- coding: utf-8 -*-
"""生成直播复盘分析报告 HTML（数据驱动，图表 SVG 手绘）"""
import json, io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = r'<你的项目路径> FDE\01-客户项目\20260825-洛阳河景云\直播分析\20260913-运动专营店'
B = os.path.join(BASE, '_构建脚本')
r = json.load(io.open(os.path.join(B, 'analysis_results.json'), encoding='utf-8'))
p = json.load(io.open(B + r'\parsed_data.json', encoding='utf-8'))

gmv = p['basic']['用户支付金额']
ov = p['overview']

# ---------- SVG: 分钟成交曲线 + 讲解段 ----------
pay = r['分钟成交序列']
cost = r['分钟投放序列']
mins = sorted(pay.keys())
max_pay = max(pay.values()) or 1
max_cost = max(cost.values()) or 1
W, H = 1080, 260
PAD_L, PAD_B, PAD_T = 50, 34, 16
def xy(i, v, mx):
    x = PAD_L + i * (W - PAD_L - 14) / max(len(mins)-1, 1)
    y = H - PAD_B - v / mx * (H - PAD_B - PAD_T)
    return x, y
line = ' '.join(f'{xy(i, pay[m], max_pay)[0]:.1f},{xy(i, pay[m], max_pay)[1]:.1f}' for i, m in enumerate(mins))
# 讲解段背景带
bands = []
for seg in r['讲解时段']:
    s, e = seg['开始'][:5], seg['结束'][:5]
    if s in mins and e in mins:
        i1, i2 = mins.index(s), mins.index(e)
        x1 = xy(i1, 0, 1)[0]; x2 = xy(i2, 0, 1)[0]
        bands.append(f'<rect x="{x1:.1f}" y="{PAD_T}" width="{max(x2-x1,2):.1f}" height="{H-PAD_B-PAD_T}" fill="#2f6bff" opacity="0.10"/>')
# 投放曲线（归一）
cost_line = ' '.join(f'{xy(i, cost.get(m,0), max_cost)[0]:.1f},{xy(i, cost.get(m,0), max_cost)[1]:.1f}' for i, m in enumerate(mins))
xticks = ''.join(
    f'<text x="{xy(i,0,1)[0]:.0f}" y="{H-14}" font-size="11" fill="#8a8f99" text-anchor="middle">{m}</text>'
    for i, m in enumerate(mins) if m.endswith(':00') or m.endswith(':30'))
svg_trend = f'''<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg">
{''.join(bands)}
<polyline points="{line}" fill="none" stroke="#2f6bff" stroke-width="2"/>
<polyline points="{cost_line}" fill="none" stroke="#f5a623" stroke-width="1.4" stroke-dasharray="4 3" opacity="0.85"/>
{xticks}
<text x="{PAD_L}" y="{PAD_T+4}" font-size="11" fill="#2f6bff">— 分钟成交金额（峰值 ¥{max_pay:,.0f}/分钟）</text>
<text x="{PAD_L+340}" y="{PAD_T+4}" font-size="11" fill="#f5a623">- - 分钟投放消耗（峰值 ¥{max_cost:,.0f}/分钟）</text>
<text x="{PAD_L+700}" y="{PAD_T+4}" font-size="11" fill="#8a8f99">▨ 蓝色底纹 = 讲解时段</text>
</svg>'''

# ---------- SVG: 20分钟桶 ----------
buckets = r['成交20分钟桶']
bk = [k for k in sorted(buckets) if buckets[k] > 0 or '17:00' <= k <= '21:00']
bk = [k for k in sorted(buckets)]
maxb = max(buckets.values())
W2, H2 = 1080, 210
bw = (W2 - PAD_L - 20) / len(bk)
bars = []
for i, k in enumerate(bk):
    v = buckets[k]
    h = v / maxb * (H2 - 60)
    x = PAD_L + i * bw
    color = '#d5434f' if k >= '20:00' else '#2f6bff'
    bars.append(f'<rect x="{x+4:.0f}" y="{H2-30-h:.0f}" width="{bw-8:.0f}" height="{h:.0f}" rx="3" fill="{color}"/>')
    bars.append(f'<text x="{x+bw/2:.0f}" y="{H2-16}" font-size="10.5" fill="#8a8f99" text-anchor="middle">{k}</text>')
    bars.append(f'<text x="{x+bw/2:.0f}" y="{H2-36-h:.0f}" font-size="10.5" fill="#3a3f4a" text-anchor="middle">{v/10000:.1f}万</text>' if v >= 10000 else f'<text x="{x+bw/2:.0f}" y="{H2-36-h:.0f}" font-size="10.5" fill="#3a3f4a" text-anchor="middle">{v:,.0f}</text>')
svg_bucket = f'''<svg viewBox="0 0 {W2} {H2}" width="100%" xmlns="http://www.w3.org/2000/svg">{''.join(bars)}</svg>'''

# ---------- SVG: 漏斗 ----------
fun = [('直播间曝光', 395300, '39.53万'), ('进入直播间', 31500, '3.15万（曝光-观看率 7.96%）'),
       ('商品曝光', 20200, '2.02万（观看-商品曝光 64.1%）'), ('商品点击', 5902, '5,902（曝光-点击率 29.2%）'),
       ('成交', 244, '244 人（点击-成交率 4.13%）')]
import math
frows = []
for i, (name, v, label) in enumerate(fun):
    w_pct = max(math.log10(v+1) / math.log10(fun[0][1]) * 100, 8)
    if i == 0:
        label_html = f'<span style="position:absolute;left:10px;top:5px;font-size:12.5px;color:#fff;white-space:nowrap">{label}</span>'
    else:
        label_html = f'<span style="position:absolute;left:calc({w_pct:.1f}% + 8px);top:5px;font-size:12.5px;color:#3a3f4a;white-space:nowrap">{label}</span>'
    frows.append(f'''<div style="display:flex;align-items:center;gap:14px;margin:7px 0">
      <div style="width:110px;text-align:right;font-size:13px;color:#5a6070">{name}</div>
      <div style="flex:1;background:#f2f4f8;border-radius:6px;height:30px;position:relative">
        <div style="width:{w_pct:.1f}%;height:100%;border-radius:6px;background:#2f6bff;opacity:{1-i*0.13}"></div>
        {label_html}
      </div></div>''')
funnel_html = ''.join(frows)

# ---------- 渠道表 ----------
ch_rows = []
for c in p['channels'][1:]:
    if c['观看人数'] < 50 and c['支付金额'] == 0:
        continue
    gpm_match = next((g for g in r['渠道GPM'] if g['渠道'].strip(' └') == c['渠道']), None)
    gpm = f"¥{gpm_match['GPM']:,.0f}" if gpm_match and gpm_match['GPM'] else '—'
    share = c['支付金额']/gmv*100
    ch_rows.append(f'''<tr><td>{c['渠道']}</td><td class="num">{c['观看人数']:,.0f}</td>
    <td class="num">{c['人均观看时长']}</td><td class="num">¥{c['支付金额']:,.0f}</td>
    <td class="num">{share:.1f}%</td><td class="num">{gpm}</td><td class="num">{c['观看成交率']}</td></tr>''')
channels_html = ''.join(ch_rows)

# ---------- 讲解时段表 ----------
jj = sorted(r['讲解时段'], key=lambda x: x['开始'])
jj_rows = []
for s in jj:
    eff = s['时段成交']/s['时长分钟'] if s['时长分钟'] else 0
    hl = ' style="background:#fff5f5"' if s['时段成交'] < 1000 else ''
    jj_rows.append(f'''<tr{hl}><td class="num">{s['开始'][:5]} ~ {s['结束'][:5]}</td>
    <td class="num">{s['时长分钟']:.1f}</td><td class="num">¥{s['时段成交']:,.0f}</td>
    <td class="num">¥{s['时段投放']:.0f}</td><td class="num">¥{eff:,.0f}/分</td></tr>''')
jj_html = ''.join(jj_rows)
talk_total = sum(s['时长分钟'] for s in r['讲解时段'])
talk_pay = sum(s['时段成交'] for s in r['讲解时段'])

# ---------- 有成交商品表 ----------
prod_rows = []
for pr in p['products']:
    if pr['支付金额'] <= 0:
        continue
    ref_r = pr['退款金额']/pr['支付金额']*100 if pr['支付金额'] else 0
    name = pr['商品名称']
    name = name if len(name) <= 30 else name[:29] + '…'
    prod_rows.append(f'''<tr><td>{name}</td><td class="num">¥{pr['支付金额']:,.0f}</td>
    <td class="num">{pr['支付金额']/gmv*100:.1f}%</td><td class="num">{pr['成交件数']}</td>
    <td class="num">{pr['曝光人数']:,.0f}</td><td class="num">{pr['点击人数']:,.0f}</td>
    <td class="num">{pr['曝光点击率']}</td><td class="num">{pr['点击成交率']}</td>
    <td class="num" style="color:{'#d5434f' if ref_r>25 else '#3a3f4a'}">{ref_r:.0f}%</td></tr>''')
prod_html = ''.join(prod_rows)

html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>河景云运动专营店 9·13 直播复盘分析</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box }}
  body {{ font-family:"Microsoft YaHei","PingFang SC",sans-serif; color:#23262e; background:#fff;
         width: 1100px; margin:0 auto; padding: 40px 30px; font-size:14px; line-height:1.75 }}
  h1 {{ font-size:26px; color:#1a1e28; margin-bottom:6px }}
  .sub {{ color:#8a8f99; font-size:13px; margin-bottom:28px }}
  h2 {{ font-size:19px; color:#1a1e28; margin:38px 0 14px; padding-left:12px; border-left:4px solid #2f6bff }}
  h3 {{ font-size:15.5px; color:#2f6bff; margin:22px 0 8px }}
  .card-row {{ display:flex; gap:12px; flex-wrap:wrap; margin:16px 0 }}
  .card {{ flex:1; min-width:150px; background:#f7f9ff; border:1px solid #e3e9fb; border-radius:10px; padding:14px 16px }}
  .card .v {{ font-size:22px; font-weight:700; color:#1a1e28 }}
  .card .k {{ font-size:12px; color:#8a8f99; margin-top:2px }}
  .card.warn {{ background:#fff7f7; border-color:#fbe3e3 }}
  .card.warn .v {{ color:#d5434f }}
  table {{ width:100%; border-collapse:collapse; margin:12px 0; font-size:12.8px }}
  th {{ background:#f2f4f8; color:#5a6070; font-weight:600; padding:8px 10px; text-align:left; display:table-cell }}
  td {{ padding:7px 10px; border-bottom:1px solid #eef0f4 }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums }}
  thead {{ display:table-header-group }}
  tr {{ break-inside:avoid }}
  .callout {{ background:#f7f9ff; border-left:4px solid #2f6bff; border-radius:0 8px 8px 0;
              padding:12px 16px; margin:14px 0; font-size:13.5px }}
  .callout.red {{ background:#fff7f7; border-left-color:#d5434f }}
  .callout.amber {{ background:#fffcf3; border-left-color:#f5a623 }}
  ul {{ padding-left:22px }} li {{ margin:5px 0 }}
  .p0 {{ display:inline-block; background:#d5434f; color:#fff; font-size:11px; border-radius:4px; padding:1px 7px; margin-right:8px }}
  .p1 {{ display:inline-block; background:#f5a623; color:#fff; font-size:11px; border-radius:4px; padding:1px 7px; margin-right:8px }}
  .p2 {{ display:inline-block; background:#8a8f99; color:#fff; font-size:11px; border-radius:4px; padding:1px 7px; margin-right:8px }}
  .sec {{ break-inside:avoid-page }}
  .footer {{ margin-top:44px; padding-top:14px; border-top:1px solid #eef0f4; color:#8a8f99; font-size:12px }}
</style></head><body>

<h1>河景云运动专营店精选直播间 · 直播复盘分析报告</h1>
<div class="sub">场次：2026-09-13 16:56 ~ 21:01（4小时4分钟）｜平台：抖音｜数据来源：抖音电商罗盘（直播大屏专业版 + 整场数据下载）｜报告日期：2026-09-15</div>

<div class="card-row">
  <div class="card"><div class="v">¥{gmv:,.0f}</div><div class="k">全场成交（用户支付金额）</div></div>
  <div class="card"><div class="v">{ov['直播间观看人数']}</div><div class="k">观看人数</div></div>
  <div class="card"><div class="v">265 单 / 244 人</div><div class="k">成交订单 / 成交人数</div></div>
  <div class="card"><div class="v">¥{ov['客单价_num']:.0f}</div><div class="k">客单价</div></div>
  <div class="card"><div class="v">¥{p['basic']['千次观看支付金额']:,.0f}</div><div class="k">GPM（千次观看支付）</div></div>
</div>
<div class="card-row">
  <div class="card warn"><div class="v">¥{ov['退款金额_num']:,.0f}（31.2%）</div><div class="k">退款金额 / 金额退款率</div></div>
  <div class="card"><div class="v">¥1,891</div><div class="k">千川全域推广消耗</div></div>
  <div class="card"><div class="v">39.1</div><div class="k">全场 GMV/消耗（口径见注）</div></div>
  <div class="card"><div class="v">{ov['新增粉丝数']}</div><div class="k">新增粉丝（观看-关注率 {ov['直播间观看-关注率(人数)']}）</div></div>
  <div class="card"><div class="v">{ov['平均在线人数']} / {ov['最高在线人数']}</div><div class="k">平均 / 最高在线人数</div></div>
</div>

<div class="callout"><b>一句话结论：</b>这是一场「单爆款 + 全域投流」驱动的场次。开局 1.5 小时节奏健康（17:20 桶峰值 ¥1.2 万），20:00 后流量与转化双崩盘（最后一小时仅贡献 5.8% 成交）；讲解效率极高（35% 的讲解时长产出 88.8% 成交），但 65% 的时间无讲解空转；商品结构极度依赖单一爆款（92.2%），且 31.2% 的金额退款率是下一场最先要止血的地方。</div>

<h2>一、成交漏斗：出血层在「停留」，不在「引流」</h2>
{funnel_html}
<ul>
<li><b>引流端合格：</b>曝光-观看率 7.96%，在全域投放场次中属于正常水平；说明素材/直播间画面对目标人群有吸引力（正向因素：门店商场实景背景）。</li>
<li><b>出血层在停留：</b>人均观看时长仅 <b>34 秒</b>，观看-互动率 1.89%、人均评论 0.03 次，互动指标全场最弱。用户进来留不住，后续点击、成交都无从谈起。34 秒意味着大多数人没听完一轮完整的卖点讲解。</li>
<li><b>成交端效率高：</b>商品曝光-点击率 29.2%、点击-成交率 4.13%，在鞋靴类目属中上水平，证明「货」和「价格锚点」没问题，问题在流量质量和承接节奏。</li>
</ul>

<h2>二、成交节奏：17:20 到达峰值，20:00 后双崩盘</h2>
<div class="sec">{svg_trend}</div>
<h3>20 分钟成交分布（红色为 20:00 后断崖段）</h3>
<div class="sec">{svg_bucket}</div>
<ul>
<li><b>上半场（16:56~18:40）：</b>成交密集且稳定，峰值分钟 17:22 与 17:34 均达 ¥2,511/分钟，对应讲解段 17:09 与 17:33 两轮循环放单。</li>
<li><b>断崖段（20:00 后）：</b>成交 ¥2,247 → ¥1,465 → ¥279，最后一小时仅 ¥4,270（占 5.8%）。分渠道分钟数据显示：20 点时段进入人数环比 19 点时段下降 38%（5,340 → 3,304），但每个进入用户的产出从 ¥3.6 跌到 ¥1.2，<b>转化效率下降 66%，比流量下滑更严重</b>。直播到 21 点进入人数只剩 73 人，实际上 20:30 后已是「垃圾时间」。</li>
<li><b>推断：</b>晚间档推流人群泛化 + 主播状态/话术循环进入疲态，同款讲第 20 遍时缺乏新利益点。建议下场把预算和状态集中在 17:00~19:30 黄金段，20 点后要么换品换利益点重启节奏，要么果断下播保权重。</li>
</ul>

<h2>三、讲解节奏：35% 的时间产出 88.8% 的成交</h2>
<div class="card-row">
  <div class="card"><div class="v">20 段 / 同款循环</div><div class="k">讲解次数（全部为主力款）</div></div>
  <div class="card"><div class="v">86 分钟（35%）</div><div class="k">讲解总时长 / 占全场比例</div></div>
  <div class="card"><div class="v">¥763 / 分钟</div><div class="k">讲解时段成交效率（非讲解段 ¥52，差 14.7 倍）</div></div>
  <div class="card"><div class="v">4.3 分钟</div><div class="k">平均段长（处于 4~7 分钟黄金区间）</div></div>
</div>
<table><thead><tr><th>讲解时段</th><th class="num">时长(分)</th><th class="num">时段成交*</th><th class="num">时段投放</th><th class="num">每分钟效率</th></tr></thead>
<tbody>{jj_html}</tbody></table>
<div class="sub">* 口径说明：时段成交 = 该讲解时段内全场成交金额（分钟级趋势推算），非该商品归因成交。红色行 = 时段成交低于 ¥1,000 的低效段。</div>
<ul>
<li><b>讲解密度不足：</b>158 分钟（65%）无讲解空转。从曲线看，无讲解时段成交几乎贴地。这双鞋是「不讲就不卖」的讲解驱动型商品，应把讲解占比提到 50% 以上。</li>
<li><b>单段时长合格：</b>平均 4.3 分钟处于黄金区间，未出现 3 分钟以下浅讲。</li>
<li><b>返场效率递减明显：</b>同款第 17~20 次讲解（19:56 后四段）合计仅 ¥1,395，单段效率从开场 ¥1,800+/分 跌到 ¥300/分 以下。<b>同款返场单场不超过 2 次就应换利益点</b>（从「透气/久站不累」切到「尺码库存告急」「官方正品验货」等新钩子），否则只是重复消耗。</li>
</ul>

<h2>四、商品结构：一双鞋撑起 92%，33 个零单款白吃 58% 曝光</h2>
<table><thead><tr><th>商品</th><th class="num">支付金额</th><th class="num">占比</th><th class="num">件数</th><th class="num">曝光人数</th><th class="num">点击人数</th><th class="num">曝光-点击率</th><th class="num">点击-成交率</th><th class="num">金额退款率</th></tr></thead>
<tbody>{prod_html}</tbody></table>
<ul>
<li><b>单品依赖：</b>主力款「阿迪达斯 2026 新款跑鞋」¥68,261 占 92.2%，点击-成交率 6.9% 全场最高，是当前绝对的流量承接款，继续主推没问题。</li>
<li><b>货架臃肿：</b>40 个上架商品中 33 个零成交，零单款合计曝光约 6.2 万人次、占商品总曝光的 58.3%。用户点进购物车看到大量 0 销量的杂款，反而稀释信任。建议精简到 8~12 个 SKU：1 个主推 + 2 个副推（不同价位带）+ 1 个引流款，其余下架。</li>
<li><b>副推缺位：</b>第 2 名逐风跑鞋（KJ4606）仅 ¥2,484、点击-成交率 0.31%（vs 主力款 6.9%）。同款人群下没有形成「价格阶梯」，高价需求无处释放。建议补一款 ¥400~500 价位带的利润款做对比锚点。</li>
</ul>

<h2>五、渠道结构：推荐 feed 走量，高净值渠道没运营</h2>
<table><thead><tr><th>渠道</th><th class="num">观看人数</th><th class="num">人均时长</th><th class="num">支付金额</th><th class="num">GMV占比</th><th class="num">渠道GPM</th><th class="num">观看-成交率</th></tr></thead>
<tbody>{channels_html}</tbody></table>
<ul>
<li><b>推荐 feed 是基本盘：</b>68.7% 的流量、55.4% 的成交，GPM ¥1,719。全域投放下量级有保障，但人群质量最低。</li>
<li><b>高 GPM 渠道全是「自然动作」能撬动的：</b>个人主页/店铺/橱窗 GPM ¥18,355（6.58% 成交率）、搜索 GPM ¥5,350、抖音商城 GPM ¥5,516。这三个渠道合计贡献 11.5% GMV 却只占 4% 流量。优化方向：直播间标题/封面埋「阿迪达斯跑鞋」关键词吃搜索；下播后店铺橱窗保持主推款置顶吃橱窗流量。</li>
<li><b>短视频引流完全失效：</b>8 条引流视频仅带来 18 人进入、¥0 成交。视频全是 6~7 月的老素材。直播前 2 小时发切片预告（本场高光讲解 + 价格钩子）是低成本补量手段。</li>
<li><b>头条西瓜渠道：</b>2,756 人贡献 ¥9,337（12.6%），GPM ¥2,853 高于推荐 feed，值得在千川侧单独观察 ROI。</li>
</ul>

<h2>六、退款专项：31.2% 金额退款率是最急的一刀</h2>
<div class="callout red"><b>全场退款 ¥23,122（84 单 / 80 人），金额退款率 31.2%，主力款 31.9%（76 人退 ¥21,749）。</b>真实到手 GMV 约 ¥5.1 万。鞋靴类目直播均值约 15~25%，本场显著偏高。</div>
<ul>
<li><b>SKU 全退集中：</b>主力款 72 个 SKU 中 10 个 SKU 全退（14 件），集中在 36/36.5/44.5/46 等极端尺码与「汉玉白 40/40.5」等热门码。<b>热门码全退提示实物与描述/上脚效果存在预期差</b>，需排查是否尺码偏小偏大、色差或品控批次问题。</li>
<li><b>动作建议：</b>① 讲解中增加「尺码对照 + 脚型建议」话术（直播伴侣挂尺码表贴片）；② 评论区置顶「拍前量脚长」；③ 售后主动回访全退 SKU 买家收集退款原因；④ 退款原因标签下场复盘时按「尺码/质量/不想要」拆解跟踪。</li>
</ul>

<h2>七、平台诊断与合规</h2>
<ul>
<li><b>违规情况：</b>本场 0 违规，实时预警为空。</li>
<li><b>流量诊断：</b>系统判定 1 个负面因素「虚拟背景」（抠像场景可能降低信任感），1 个正向因素「门店商场背景」。建议排查开播时段是否混用了虚拟背景片段，统一使用门店实景。</li>
<li><b>投放形态：</b>16:56 开播即开启千川全域推广，全场消耗 ¥1,891，GMV/消耗 39.1（全域口径下流量不区分自然/付费，该比值不等于标准 ROI，仅供场间纵向对比）。投放曲线与成交曲线形态一致，未见空烧段。</li>
<li><b>主播排班未配置：</b>罗盘主播分析页无排班数据，无法分主播归因。建议下场开播前配置主播轮班，才能回答「谁播得好」。</li>
</ul>

<h2>八、下一场行动清单</h2>
<ul>
<li><span class="p0">P0</span><b>退款止血：</b>排查全退 SKU 的尺码/品控问题；讲解加尺码引导话术；目标把金额退款率压到 25% 以下。</li>
<li><span class="p0">P0</span><b>砍掉垃圾时间：</b>20:00 后若无新利益点/换品，直接下播。把人力和投流集中在 17:00~19:30。</li>
<li><span class="p0">P0</span><b>讲解占比提到 50%+：</b>按 4~6 分钟一段循环，两段之间用福袋/尺码答疑过渡，避免长时间无讲解空转。</li>
<li><span class="p1">P1</span><b>货架瘦身：</b>下架 33 个零单款，保留 1 主推 + 2 副推（补 ¥400~500 价位带）+ 1 引流款。</li>
<li><span class="p1">P1</span><b>停留时长专项：</b>34 秒停留是漏斗最大出血层。开场 3 分钟话术脚本重写（痛点前置 + 价格悬念），配福袋拉互动；目标人均观看 45 秒+。</li>
<li><span class="p1">P1</span><b>同款返场换利益点：</b>单场同款讲解不超过 2 次重复同一套话术，准备 3 套利益点轮换（功能/稀缺/售后）。</li>
<li><span class="p2">P2</span><b>短视频预热：</b>开播前 2 小时发本场切片预告，替换 6 月老素材。</li>
<li><span class="p2">P2</span><b>配置主播排班：</b>罗盘内配置轮班，下场起可分主播归因。</li>
<li><span class="p2">P2</span><b>搜索/橱窗运营：</b>直播间标题与店铺橱窗关键词对齐「阿迪达斯跑鞋」，吃高 GPM 长尾流量。</li>
</ul>

<div class="footer">数据口径：GMV/退款/商品明细来自罗盘「整场数据下载」xlsx；分钟成交/投放曲线来自罗盘直播大屏 blend_trend 接口（单位分，已换算）；渠道 GPM 来自大屏流量分析；讲解时间轴来自大屏讲解标记（时段成交为全场口径）。「GMV/消耗」为全场支付金额除以千川消耗，含自然流量贡献，非标准广告 ROI。</div>

</body></html>'''

out = os.path.join(BASE, '河景云运动专营店-0913直播复盘分析.html')
io.open(out, 'w', encoding='utf-8').write(html)
print('HTML written:', out, len(html))
