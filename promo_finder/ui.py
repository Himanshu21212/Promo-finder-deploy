"""Shared visual components (pure HTML/CSS strings) for the standalone report and the Streamlit app.

Design rules, chosen for readability:
  * one typeface (Inter) with a strict type scale; nothing in the interface is below 12 px
  * light theme by default, text contrast >= 4.5:1 everywhere (dark theme kept as an option)
  * colour carries meaning only: rose = hook, amber = where it cuts, violet = stitched, green = pass
  * progressive disclosure: each promo shows the essentials, and the scores, flags and transcript sit behind "Details"

No inline SVG and no JavaScript, so everything renders inside Streamlit's sanitised `st.html`
as well as in a plain browser. Every class is prefixed `pf-` and every token lives on `.pf`.
"""
from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path

from .candidates import Promo
from .parser import Beat, fmt, speaker_name

FONT_DIR = Path(__file__).resolve().parents[1] / "static" / "fonts"
FONTS = [("Inter", 400, "normal", "inter-latin-400-normal"), ("Inter", 500, "normal", "inter-latin-500-normal"),
         ("Inter", 600, "normal", "inter-latin-600-normal"), ("Inter", 700, "normal", "inter-latin-700-normal"),
         ("JetBrains Mono", 400, "normal", "jetbrains-mono-latin-400-normal"),
         ("JetBrains Mono", 600, "normal", "jetbrains-mono-latin-600-normal")]


@lru_cache(maxsize=2)
def font_faces(mode: str = "embed") -> str:
    """@font-face rules. 'embed' inlines the fonts (standalone files); 'static' uses Streamlit's static server."""
    out = []
    for fam, w, style, name in FONTS:
        f = FONT_DIR / f"{name}.woff2"
        if mode == "static":
            src = f"url('app/static/fonts/{name}.woff2') format('woff2')"
        elif f.exists():
            src = f"url(data:font/woff2;base64,{base64.b64encode(f.read_bytes()).decode()}) format('woff2')"
        else:
            continue
        out.append(f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{w};font-display:swap;src:{src}}}")
    return "".join(out)


CSS = """
.pf{--bg:#f6f6f3;--surface:#ffffff;--surface2:#f4f4f1;--surface3:#e8e8e3;--line:#e3e3de;--line2:#cfcfc8;
--ink:#121216;--ink2:#34343c;--mute:#55555f;--faint:#6b6b75;
--hook:#d6194a;--hook-bg:#fff0f3;--cliff:#a85400;--cliff-bg:#fff6e8;--stitch:#5b3fd6;--stitch-bg:#f2eeff;
--ok:#137a3d;--ok-bg:#eaf7ef;--warn:#8a5a00;--warn-bg:#fff8e1;--bad:#b42318;--bad-bg:#fdeceb;
--accent:#d6194a;--grad:linear-gradient(135deg,#ff3d6e 0%,#ff7a45 100%);
--shadow:0 1px 2px rgba(18,18,22,.05),0 2px 8px -2px rgba(18,18,22,.06);
--sans:'Inter',ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
--mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased;
font-feature-settings:"cv11","ss01";font-variant-numeric:tabular-nums}
.pf[data-theme=dark]{--bg:#0f0f12;--surface:#17171c;--surface2:#1f1f25;--surface3:#2b2b33;--line:#2b2b33;--line2:#3b3b45;
--ink:#f5f5f6;--ink2:#dcdce0;--mute:#b0b0ba;--faint:#9a9aa5;
--hook:#ff7b98;--hook-bg:rgba(255,123,152,.12);--cliff:#ffc165;--cliff-bg:rgba(255,193,101,.11);--stitch:#b4a3ff;--stitch-bg:rgba(180,163,255,.13);
--ok:#5ee29a;--ok-bg:rgba(94,226,154,.12);--warn:#ffd666;--warn-bg:rgba(255,214,102,.1);--bad:#ff8a80;--bad-bg:rgba(255,138,128,.12);
--accent:#ff7b98;--shadow:none}
.pf *{box-sizing:border-box}
.pf h1,.pf h2,.pf h3,.pf p,.pf ol,.pf ul{margin:0}
.pf ol,.pf ul{padding-left:0!important;margin-left:0!important}.pf li{margin:0!important}
.pf a{color:inherit}
.pf .mono{font-family:var(--mono);font-size:.92em}
/* type scale */
.pf-label{font-size:12px;line-height:1.3;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--faint)}
.pf-label.hook{color:var(--hook)}.pf-label.cliff{color:var(--cliff)}.pf-label.accent{color:var(--accent)}
.pf-h1{font-size:clamp(32px,4.4vw,48px);line-height:1.1;font-weight:700;letter-spacing:-.025em;text-wrap:balance}
.pf-h2{font-size:clamp(24px,2.6vw,30px);line-height:1.2;font-weight:700;letter-spacing:-.02em;margin:6px 0 6px;text-wrap:balance}
.pf-sub{font-size:16px;color:var(--mute);max-width:70ch}
.pf-section{margin:52px 0 0}
.pf-section-head{margin-bottom:20px}
.pf-grad{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
/* brand */
.pf-brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;letter-spacing:-.01em}
.pf-logo{width:28px;height:28px;border-radius:8px;background:#121216;position:relative;flex:none}
.pf-logo i{position:absolute;left:5px;right:5px;top:13px;height:2px;background:rgba(255,255,255,.35);border-radius:1px}
.pf-logo i::before{content:"";position:absolute;left:5px;width:8px;top:-2px;height:6px;background:#ff2d6a;border-radius:1px}
.pf-logo i::after{content:"";position:absolute;left:3px;top:-6px;width:2px;height:14px;background:#fff;border-radius:1px;box-shadow:10px 0 0 #fff}
.pf[data-theme=dark] .pf-logo{background:#26262e;box-shadow:inset 0 0 0 1px #3b3b45}
/* badges */
.pf-badge{display:inline-flex;align-items:center;gap:6px;font-size:13px;line-height:1;font-weight:600;padding:6px 10px;border-radius:8px;
background:var(--surface2);color:var(--ink2);border:1px solid var(--line);white-space:nowrap}
.pf-badge.st{background:var(--stitch-bg);color:var(--stitch);border-color:transparent}
.pf-badge.tA{background:var(--ok-bg);color:var(--ok);border-color:transparent}
.pf-badge.tB{background:var(--warn-bg);color:var(--warn);border-color:transparent}
.pf-badge.tC{background:var(--bad-bg);color:var(--bad);border-color:transparent}
.pf-badge.flag{background:var(--warn-bg);color:var(--warn);border-color:transparent}
.pf-badge.ai{background:var(--hook-bg);color:var(--hook);border-color:transparent}
/* KPIs */
.pf-summary{display:flex;flex-wrap:wrap;gap:6px 22px;font-size:15px;color:var(--ink2);padding:14px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.pf-summary b{color:var(--ink);font-weight:700}
.pf-mode{display:inline-block;font-size:14px;padding:6px 10px;border-radius:8px;background:var(--surface2);color:var(--ink2);border:1px solid var(--line)}
.pf-mode.ai{background:var(--stbg,#f2eeff);color:var(--stitch);border-color:transparent}
.pf-mode.mock{background:var(--warn-bg);color:var(--warn);border-color:transparent;font-weight:600}
.pf-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.pf-kpi{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px 20px;box-shadow:var(--shadow)}
.pf-kpi .v{font-size:32px;line-height:1.1;font-weight:700;letter-spacing:-.025em}
.pf-kpi .l{font-size:15px;font-weight:600;color:var(--ink2);margin-top:6px}
.pf-kpi .c{font-size:13px;color:var(--faint)}
/* promo row (ranked list) */
.pf-list{display:flex;flex-direction:column;gap:12px}
.pf-row{display:grid;grid-template-columns:52px minmax(0,1fr) 270px;gap:0 24px;background:var(--surface);border:1px solid var(--line);
border-radius:16px;padding:20px 22px;box-shadow:var(--shadow);scroll-margin-top:90px}
.pf-row:target{outline:2px solid var(--accent);outline-offset:2px}
.pf-rank{width:40px;height:40px;border-radius:10px;display:grid;place-items:center;font-size:17px;font-weight:700;
background:var(--surface2);color:var(--ink);border:1px solid var(--line)}
.pf-rank.top{background:var(--ink);color:var(--surface);border-color:var(--ink)}
.pf-main{display:flex;flex-direction:column;gap:12px;min-width:0}
.pf-q{font-size:19px;line-height:1.4;font-weight:600;color:var(--ink);letter-spacing:-.01em;margin-top:4px}
.pf-q.act{font-style:italic;font-weight:500;font-size:17px;color:var(--ink2)}
.pf-who{font-size:14px;color:var(--faint);margin-top:2px}
.pf-end{border-left:3px solid var(--cliff);padding:2px 0 2px 12px}
.pf-end p{font-size:16px;line-height:1.5;color:var(--ink2);margin-top:3px}
.pf-end p.act{font-style:italic}
.pf-why{font-size:15px;line-height:1.55;color:var(--ink2)}
.pf-tags{display:flex;flex-wrap:wrap;gap:6px}
.pf-side{display:flex;flex-direction:column;gap:12px;border-left:1px solid var(--line);padding-left:22px}
.pf-len{display:flex;align-items:baseline;justify-content:space-between}
.pf-len b{font-size:24px;font-weight:700;letter-spacing:-.02em}
.pf-len span{font-size:14px;color:var(--mute)}
.pf-score{font-size:14px;color:var(--mute)}.pf-score b{color:var(--ink);font-size:15px}
.pf-cuts{list-style:none;padding:0;display:flex;flex-direction:column;gap:6px}
.pf-cuts li{display:flex;gap:10px;align-items:baseline;font-family:var(--mono);font-size:14px;color:var(--ink2)}
.pf-cuts li span{font-family:var(--sans);font-size:12px;font-weight:600;color:var(--faint);min-width:40px;text-transform:uppercase;letter-spacing:.04em}
.pf-bar{display:flex;gap:3px;height:6px}
.pf-bar i{display:block;height:100%;border-radius:999px;background:var(--stitch)}
.pf-barcap{font-size:13px;color:var(--faint)}
.pf-more{grid-column:2 / -1;margin-top:14px;border-top:1px solid var(--line);padding-top:12px}
.pf-more>summary{cursor:pointer;list-style:none;font-size:14px;font-weight:600;color:var(--mute);display:inline-flex;align-items:center;gap:8px}
.pf-more>summary::-webkit-details-marker{display:none}
.pf-more>summary::before{content:"";width:7px;height:7px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;
transform:rotate(-45deg);transition:transform .15s}
.pf-more[open]>summary::before{transform:rotate(45deg)}
.pf-more>summary:hover{color:var(--ink)}
.pf-detail{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:20px 32px;margin-top:16px}
.pf-detail h4{margin:0 0 8px}
@media (max-width:860px){.pf-row{grid-template-columns:1fr;padding:18px}.pf-row>.pf-rankcell{margin-bottom:10px}
.pf-side{border-left:0;padding-left:0;border-top:1px solid var(--line);padding-top:14px;margin-top:16px}.pf-more{grid-column:1}
.pf-detail{grid-template-columns:1fr}}
/* compact promo rows: one line per promo, click to expand */
.pf-clist{background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--shadow)}
.pf-chead,.pf-crow>summary{display:grid;grid-template-columns:34px minmax(0,1fr) 196px 52px 46px 132px 14px;gap:0 14px;align-items:center;padding:10px 16px}
.pf-chead{font-size:12px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--faint);background:var(--surface2);border-bottom:1px solid var(--line);padding-top:8px;padding-bottom:8px}
.pf-crow{border-bottom:1px solid var(--line);scroll-margin-top:90px}
.pf-crow:last-child{border-bottom:0}
.pf-crow:target{outline:2px solid var(--accent);outline-offset:-2px}
.pf-crow>summary{cursor:pointer;list-style:none}
.pf-crow>summary::-webkit-details-marker{display:none}
.pf-crow>summary:hover{background:var(--surface2)}
.pf-crow[open]>summary{background:var(--surface2)}
.pf-crow .pf-rank{width:30px;height:30px;font-size:14px;border-radius:8px}
.cr-main{min-width:0;display:flex;flex-direction:column;gap:2px}
.cr-main span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cr-hook{font-size:15px;font-weight:600;color:var(--ink)}
.cr-hook.act{font-style:italic;font-weight:500}
.cr-cliff{font-size:14px;color:var(--mute)}
.cr-cliff b{color:var(--cliff);font-weight:600}
.cr-cuts{font-family:var(--mono);font-size:12.5px;line-height:1.5;color:var(--ink2);white-space:nowrap}
.cr-len,.cr-score{font-size:14px;color:var(--ink2);text-align:right;font-variant-numeric:tabular-nums}
.cr-score{font-weight:700;color:var(--ink)}
.cr-tags{display:flex;gap:4px;flex-wrap:wrap}
.cr-tags .pf-badge{font-size:12px;padding:4px 7px}
.cr-chev{width:7px;height:7px;border-right:2px solid var(--faint);border-bottom:2px solid var(--faint);transform:rotate(45deg);margin-top:-4px;transition:transform .15s}
.pf-crow[open] .cr-chev{transform:rotate(-135deg);margin-top:4px}
.cr-body{padding:6px 16px 20px 64px;display:flex;flex-direction:column;gap:16px}
.cr-body .pf-detail{margin-top:0}
.cr-full{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px 32px}
.cr-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pf-chead .r{text-align:right}
@media (max-width:860px){
.pf-chead{display:none}
.pf-crow>summary{grid-template-columns:30px minmax(0,1fr) 14px;grid-template-areas:"r m c" ". x x";gap:6px 12px;padding:12px 14px}
.pf-crow>summary>.pf-rank{grid-area:r}.pf-crow>summary>.cr-main{grid-area:m}.pf-crow>summary>.cr-chev{grid-area:c}
.cr-meta{grid-area:x;display:flex!important;flex-wrap:wrap;gap:4px 12px;align-items:center}
.cr-body{padding:4px 14px 18px}.cr-full{grid-template-columns:1fr}}
.cr-meta{display:contents}
.pf-libtable{table-layout:fixed}
.pf-libtable td{padding:9px 14px!important;line-height:1.4!important;vertical-align:middle!important}
.pf-libtable td.q{min-width:0!important}
.pf-libtable td.q span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* score breakdown */
.pf-why-score{width:100%;border-collapse:collapse;font-size:14px}
.pf-why-score td{padding:6px 0;border-bottom:1px solid var(--line);color:var(--ink2)}
.pf-why-score td.r{text-align:right;font-family:var(--mono);font-size:13px;white-space:nowrap;padding-left:12px}
.pf-why-score tr.tot td{border-bottom:0;font-weight:700;color:var(--ink);padding-top:8px}
.pf-why-score tr.note td{border-bottom:0;font-size:13px;color:var(--faint);padding-top:2px}
.pf-segtable{width:100%;border-collapse:collapse;font-size:14px}
.pf-segtable th{font-size:12px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--faint);text-align:left;padding:0 10px 6px 0}
.pf-segtable td{padding:7px 10px 7px 0;border-top:1px solid var(--line);vertical-align:top;color:var(--ink2)}
.pf-segtable td.m{font-family:var(--mono);font-size:13px;white-space:nowrap}
@media (max-width:600px){.pf-segtable th:nth-child(6),.pf-segtable td:nth-child(6){display:none}.pf-segtable td.m{font-size:12px}}
.pf-spot .detail,.pf-row>*{min-width:0}
.pf-epindex{display:flex;flex-wrap:wrap;gap:4px;margin:0 0 14px}
.pf-epindex a{font-family:var(--mono);font-size:12px;text-decoration:none;padding:3px 6px;border-radius:6px;border:1px solid var(--line);color:var(--ink2);background:var(--surface)}
.pf-epindex a.none{color:var(--faint);border-style:dashed}
/* meters */
.pf-meters{display:flex;flex-direction:column;gap:10px}
.pf-meter .lab{display:flex;justify-content:space-between;font-size:14px;color:var(--ink2)}
.pf-meter .lab b{font-weight:600}
.pf-meter .track{height:6px;border-radius:999px;background:var(--surface3);margin-top:5px;overflow:hidden}
.pf-meter .track i{display:block;height:100%;border-radius:999px;background:var(--ink2)}
/* flags */
.pf-flags{list-style:none;padding:0;display:flex;flex-direction:column;gap:6px}
.pf-flags li{font-size:14px;color:var(--ink2);padding:8px 10px;border-radius:8px;background:var(--warn-bg)}
.pf-flags li::before{content:"⚑";color:var(--warn);margin-right:8px}
/* transcript */
.pf-tx{list-style:none;padding:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;max-height:380px;overflow-y:auto}
.pf-tx li{display:grid;grid-template-columns:54px 1fr;gap:12px;padding:9px 12px;font-size:14px;line-height:1.5;border-top:1px solid var(--line)}
.pf-tx li:first-child{border-top:0}
.pf-tx li.sep{display:block;background:var(--surface2);font-size:12px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--stitch)}
.pf-tx .t{font-family:var(--mono);font-size:13px;color:var(--faint)}
.pf-tx .s{font-weight:600;color:var(--ink)}
.pf-tx .a{color:var(--mute);font-style:italic}
.pf-tx li.hk{background:var(--hook-bg)}.pf-tx li.cf{background:var(--cliff-bg)}
/* phone storyboard */
.pf-phone{width:280px;flex:none;border-radius:44px;padding:10px;background:#1b1b20;
box-shadow:0 0 0 1px rgba(0,0,0,.12),0 30px 60px -30px rgba(18,18,22,.45)}
.pf-screen{position:relative;height:560px;border-radius:35px;overflow:hidden;display:flex;flex-direction:column;padding:50px 20px 20px;color:#fff;
background:#141418}
.pf-notch{position:absolute;top:12px;left:50%;transform:translateX(-50%);width:90px;height:24px;border-radius:999px;background:#000}
.pf-pbar{display:flex;gap:4px}
.pf-pbar span{height:3px;border-radius:999px;background:rgba(255,255,255,.3);overflow:hidden}
.pf-pbar span i{display:block;height:100%;background:#fff}
.pf-ptop{display:flex;justify-content:space-between;margin-top:10px;font-size:12px;font-weight:600;color:rgba(255,255,255,.8)}
.pf-pcap{margin-top:22px}
.pf-pcap .k,.pf-pcliff .k{font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase}
.pf-pcap .k{color:#ff9ab2}
.pf-pcap .q{font-size:24px;line-height:1.25;font-weight:700;margin-top:6px;letter-spacing:-.01em}
.pf-pcap .q.act{font-style:italic;font-weight:600;font-size:19px}
.pf-pmid{margin-top:20px;display:flex;flex-direction:column;gap:10px;font-size:14px;line-height:1.45;color:rgba(255,255,255,.78)}
.pf-pmid b{color:#fff;font-weight:600}
.pf-pmid .more{color:rgba(255,255,255,.55);font-size:13px}
.pf-pcliff{margin-top:auto;border-radius:14px;padding:12px 14px;background:rgba(255,184,77,.16);border:1px solid rgba(255,184,77,.4)}
.pf-pcliff .k{color:#ffcf85}
.pf-pcliff .q{font-size:15px;line-height:1.4;margin-top:4px}
.pf-cta{margin-top:12px;border-radius:12px;padding:11px;text-align:center;font-size:14px;font-weight:600;background:rgba(255,255,255,.14);color:#fff}
/* spotlight */
.pf-spot{display:grid;grid-template-columns:auto minmax(0,1fr);gap:44px;align-items:start;background:var(--surface);border:1px solid var(--line);
border-radius:20px;padding:32px;box-shadow:var(--shadow)}
.pf-spot .detail{display:flex;flex-direction:column;gap:22px;min-width:0}
.pf-spot .big{font-size:clamp(24px,2.6vw,32px);line-height:1.25;font-weight:700;letter-spacing:-.02em;margin-top:6px}
.pf-spot .big.act{font-style:italic;font-weight:600}
.pf-spot .facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:18px 28px}
@media (max-width:860px){.pf-spot{grid-template-columns:1fr;justify-items:center;padding:20px}.pf-spot .detail{width:100%}}
/* season map */
.pf-map{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:22px 22px 16px;box-shadow:var(--shadow)}
.pf-legend{display:flex;flex-wrap:wrap;gap:8px 22px;font-size:14px;color:var(--ink2);margin-bottom:22px}
.pf-legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:8px;vertical-align:-1px}
.pf-mapgrid{display:grid;grid-template-columns:44px 1fr;gap:10px}
.pf-axis{position:relative;font-family:var(--mono);font-size:12px;color:var(--faint)}
.pf-axis span{position:absolute;right:0;transform:translateY(-50%)}
.pf-cols{display:grid;gap:3px}
.pf-col{position:relative}
.pf-col .ep{position:absolute;left:0;right:0;top:0;border-radius:4px;background:var(--surface3)}
.pf-col a.b{position:absolute;left:1px;right:1px;border-radius:3px;background:var(--hook);text-decoration:none}
.pf-col a.b.st{background:var(--stitch)}
.pf-col a.b.lib{background:transparent;border:1.5px dashed var(--faint)}
.pf-col .rk{position:absolute;left:50%;transform:translate(-50%,-125%);min-width:20px;height:20px;padding:0 4px;border-radius:6px;
display:grid;place-items:center;font-size:12px;font-weight:700;background:var(--ink);color:var(--surface);z-index:3}
.pf-xlab{display:grid;gap:3px;margin:10px 0 0 54px;font-family:var(--mono);font-size:12px;color:var(--faint);text-align:center}
/* table */
.pf-tablewrap{background:var(--surface);border:1px solid var(--line);border-radius:16px;overflow:auto;box-shadow:var(--shadow)}
.pf-table{width:100%;border-collapse:collapse;font-size:15px;min-width:820px}
.pf-table th{font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--faint);text-align:left;
padding:12px 16px;background:var(--surface2);border-bottom:1px solid var(--line)}
.pf-table td{padding:14px 16px;border-bottom:1px solid var(--line);vertical-align:top;color:var(--ink2);line-height:1.5}
.pf-table tr:last-child td{border-bottom:0}
.pf-table td.num{font-family:var(--mono);font-size:14px;white-space:nowrap}
.pf-table td.q{min-width:240px}
.pf-table td.q.h{color:var(--ink);font-weight:500}
/* checks */
.pf-checks{display:grid;grid-template-columns:minmax(220px,300px) minmax(0,1fr);gap:16px;align-items:start}
@media (max-width:860px){.pf-checks{grid-template-columns:1fr}}
.pf-pass{background:var(--ok-bg);border-radius:16px;padding:24px}
.pf-pass .v{font-size:44px;line-height:1;font-weight:700;letter-spacing:-.03em;color:var(--ok)}
.pf-pass .v small{font-size:22px;color:var(--ok);opacity:.7}
.pf-pass .l{font-size:16px;font-weight:600;margin-top:10px}.pf-pass .c{font-size:14px;color:var(--ink2);margin-top:6px}
.pf-rules{list-style:none;padding:0;background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow)}
.pf-rules li{display:grid;grid-template-columns:28px 1fr;gap:12px;padding:14px 18px;border-top:1px solid var(--line)}
.pf-rules li:first-child{border-top:0}
.pf-rules .ic{width:24px;height:24px;border-radius:50%;display:grid;place-items:center;font-size:13px;font-weight:700;background:var(--ok-bg);color:var(--ok)}
.pf-rules .ic.warn{background:var(--warn-bg);color:var(--warn)}
.pf-rules b{display:block;font-size:15px;font-weight:600}.pf-rules span{font-size:14px;color:var(--mute)}
/* landing / method */
.pf-steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.pf-step{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px;box-shadow:var(--shadow)}
.pf-step .n{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:8px;background:var(--surface2);font-size:14px;font-weight:700}
.pf-step b{display:block;font-size:17px;margin-top:12px}
.pf-step p{color:var(--mute);font-size:15px;margin-top:4px;line-height:1.55}
.pf-step .tag{display:inline-block;margin-top:12px}
.pf-checklist{list-style:none;padding:0;display:flex;flex-direction:column;gap:8px}
.pf-checklist li{display:flex;gap:10px;align-items:baseline;font-size:16px;color:var(--ink2)}
.pf-checklist li::before{content:"✓";color:var(--ok);font-weight:700}
"""


def css(fonts: str = "embed") -> str:
    return f"<style>{font_faces(fonts)}{CSS}</style>"


def e(s) -> str:
    return html.escape(str(s), quote=True)


def tier(p: Promo) -> str:
    t = p.scores["total"]
    return "A" if t >= 0.85 else "B" if t >= 0.75 else "C"


TIER_TEXT = {"A": "A · strong", "B": "B · usable", "C": "C · weak"}


def logo(name: str = "Promo Finder") -> str:
    return f'<div class="pf-brand"><div class="pf-logo"><i></i></div><span>{e(name)}</span></div>'


def _clean(b: Beat) -> str:
    return b.text.strip().strip('"').strip()


def _short_action(b: Beat, words: int = 16) -> str:
    t = _clean(b).split(". ")[0]
    w = t.split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def who(b: Beat) -> str:
    return speaker_name(b.speaker) if b.kind == "dialogue" else {"action": "On screen", "sfx": "Sound", "camera": "Camera"}[b.kind]


def quote_html(b: Beat, short: bool = False) -> tuple[str, bool]:
    """(escaped text, is_action). Dialogue is quoted; actions are shown as a short italic description."""
    if b.kind == "dialogue":
        t = _clean(b)
        if short and len(t) > 120:
            t = t[:118].rstrip() + "…"
        return f"“{e(t)}”", False
    return e(_short_action(b, 16 if short else 26)), True


def score100(p: Promo) -> int:
    return round(100 * min(1.0, p.scores["total"]))


# ----------------------------------------------------------------- small pieces
def mode_badge(model: str, ai: dict | None = None) -> str:
    ai = ai or {}
    if model == "mock":
        return '<span class="pf-mode mock">MOCK judge: test run only, no real model was called</span>'
    if model == "rules":
        if ai.get("calls"):
            note = f"AI review returned no usable ratings after {ai['calls']} request(s); ranked by rules only"
        elif ai.get("requested"):
            note = "AI review unavailable or no candidates to review; ranked by rules only (no API requests made)"
        else:
            note = "Ranked by rules only: no AI model was called"
        return f'<span class="pf-mode">{note}</span>'
    return (f'<span class="pf-mode ai">Rules + AI judge ({e(model)}): {ai.get("judged", 0)} of '
            f'{ai.get("shortlisted", 0)} shortlisted cuts rated by the model</span>')


def run_summary(stats: dict, checks: dict | None = None) -> str:
    episode_label = "episode" if stats['episodes'] == 1 else "episodes"
    source_label = "episode" if stats['episodes_covered'] == 1 else "episodes"
    promo_label = "promo" if stats['promos'] == 1 else "promos"
    bits = [f"<span><b>{stats['episodes']}</b> {episode_label} ({stats['minutes']} min of script)</span>",
            f"<span><b>{stats['candidates']:,}</b> possible cuts scored</span>",
            f"<span><b>{stats['promos']}</b> {promo_label} ranked, from {stats['episodes_covered']} {source_label}</span>"]
    if checks:
        bits.append(f"<span><b>{checks['passed']}/{checks['checked']}</b> pass the rule checks</span>")
    bits.append(f"<span>Run time <b>{stats['seconds']} s</b></span>")
    ai = stats.get("ai", {})
    if ai.get("usage_calls"):
        bits.append(f"<span>reported API tokens <b>{ai['prompt_tokens']:,} input / "
                    f"{ai['completion_tokens']:,} output</b></span>")
        if "estimated_cost_inr" in ai:
            bits.append(f"<span>estimated model cost <b>₹{ai['estimated_cost_inr']:.4f}</b> (excludes tax)</span>")
    return '<div class="pf-summary">' + "".join(bits) + "</div>"


PARTS = [("Hook strength", "hook", 0.28), ("Cliffhanger", "cliff", 0.24), ("Momentum (no flat stretch)", "body", 0.20),
         ("Makes sense to a new viewer", "standalone", 0.16), ("Length fit (25-45 s is ideal)", "fit", 0.06),
         ("Sells the show's premise", "premise", 0.06)]


def score_breakdown(p: Promo) -> str:
    """Show exactly how the score was built, so an editor can see why a promo ranks where it does."""
    sc = p.scores
    rows = "".join(f'<tr><td>{lab}</td><td class="r">{100 * min(1, sc[k]):.0f} × {int(w * 100)}%</td>'
                   f'<td class="r">{100 * w * min(1, sc[k]):.1f}</td></tr>' for lab, k, w in PARTS)
    if sc.get("stitch_adj"):
        rows += (f'<tr><td>Stitched: cuts share a speaker / extra cut</td><td class="r"></td>'
                 f'<td class="r">{100 * sc["stitch_adj"]:+.1f}</td></tr>')
    rules = sc.get("rules_total", sc["total"])
    rows += f'<tr class="tot"><td>Rules score</td><td></td><td class="r">{100 * rules:.1f}</td></tr>'
    if "llm_total" in sc:
        rows += (f'<tr><td>AI judge score (hook 30%, cliffhanger 25%, new viewer 15%, overall 30%)</td><td></td>'
                 f'<td class="r">{100 * sc["llm_total"]:.1f}</td></tr>'
                 f'<tr class="tot"><td>Final score = half rules, half AI</td><td></td><td class="r">{100 * sc["total"]:.1f}</td></tr>')
    if "funnel" in sc:
        rows += (f'<tr class="note"><td colspan="3">Posting order also adds up to 15 points for early episodes '
                 f'(this one: +{15 * sc["funnel"]:.1f}) and avoids the same episode or story type back to back. '
                 f'Scores rank cuts within this show; they are not a prediction of views.</td></tr>')
    return f'<table class="pf-why-score">{rows}</table>'


def segment_table(p: Promo) -> str:
    rows = []
    for i, s in enumerate(p.segments, 1):
        first = next((b for b in s.beats if b.kind == "dialogue"), None) or next((b for b in s.beats if b.kind != "camera"), None)
        txt = (f"{e(speaker_name(first.speaker))}: “{e(_clean(first)[:80])}”" if first and first.kind == "dialogue"
               else e(_short_action(first, 12)) if first else "")
        rows.append(f'<tr><td>{i}</td><td class="m">Ep {s.ep}</td><td class="m">{fmt(s.start)}</td><td class="m">{fmt(s.end)}</td>'
                    f'<td class="m">{s.dur:.1f} s</td><td>{txt}</td></tr>')
    return ('<table class="pf-segtable"><tr><th>Cut</th><th>Episode</th><th>From</th><th>To</th><th>Length</th>'
            '<th>Starts with</th></tr>' + "".join(rows) + "</table>")


def kpis(items: list[tuple[str, str, str]]) -> str:
    """items: (value, label, caption)"""
    return '<div class="pf-kpis">' + "".join(
        f'<div class="pf-kpi"><div class="v">{v}</div><div class="l">{e(l)}</div><div class="c">{e(c)}</div></div>'
        for v, l, c in items) + "</div>"


def cut_list(p: Promo) -> str:
    return '<ol class="pf-cuts">' + "".join(
        f'<li><span>Ep {s.ep}</span>{fmt(s.start)} → {fmt(s.end)}</li>' for s in p.segments) + "</ol>"


def cut_bar(p: Promo) -> str:
    parts = "".join(f'<i style="flex:{s.dur:.2f}" title="Ep {s.ep} · {s.dur:.1f}s"></i>' for s in p.segments)
    lens = " + ".join(f"{s.dur:.0f} s" for s in p.segments)
    return f'<div><div class="pf-bar">{parts}</div><div class="pf-barcap" style="margin-top:6px">{lens}</div></div>'


def meters(p: Promo) -> str:
    sc = p.scores
    items = (("Hook strength", "hook"), ("Cliffhanger", "cliff"), ("Momentum (no flat stretch)", "body"),
             ("Makes sense to a new viewer", "standalone"))
    return '<div class="pf-meters">' + "".join(
        f'<div class="pf-meter"><div class="lab"><span>{lab}</span><b>{100 * min(1, sc[k]):.0f}</b></div>'
        f'<div class="track"><i style="width:{100 * min(1, sc[k]):.0f}%"></i></div></div>' for lab, k in items) + "</div>"


def flag_list(p: Promo) -> str:
    if not p.flags:
        return '<p style="font-size:14px;color:var(--mute)">Nothing to check.</p>'
    return '<ul class="pf-flags">' + "".join(f"<li>{e(f)}</li>" for f in p.flags) + "</ul>"


def transcript(p: Promo) -> str:
    lis, off = [], 0.0
    for i, s in enumerate(p.segments):
        if len(p.segments) > 1:
            lis.append(f'<li class="sep">Cut {i + 1} · Episode {s.ep} · {fmt(s.start)}–{fmt(s.end)}</li>')
        for b in s.beats:
            if b.kind == "camera":
                continue
            cls = "hk" if b is p.hook_beat else "cf" if b is p.cliff_beat else ""
            at = off + b.start - s.start
            body = (f'<span><span class="s">{e(speaker_name(b.speaker))}:</span> {e(_clean(b))}</span>' if b.kind == "dialogue"
                    else f'<span class="a">{e(_clean(b))}</span>')
            lis.append(f'<li class="{cls}"><span class="t">{at:.1f}s</span>{body}</li>')
        off += s.dur
    return f'<ol class="pf-tx">{"".join(lis)}</ol>'


def ai_line(p: Promo) -> str:
    if not (p.llm and "overall" in p.llm):
        return ""
    l = p.llm
    return (f'<p style="font-size:14px;color:var(--ink2)"><span class="pf-badge ai">AI judge</span> '
            f'hook {l["hook"]:.0f}/10 · cliffhanger {l["cliffhanger"]:.0f}/10 · new viewer {l["standalone"]:.0f}/10 · '
            f'overall {l["overall"]:.0f}/10</p>')


def _tags(p: Promo) -> str:
    t = tier(p)
    kind = (f'<span class="pf-badge st">Stitched · {len(p.segments)} cuts</span>' if p.kind == "stitched"
            else '<span class="pf-badge">Single clip</span>')
    flags = (f'<span class="pf-badge flag">⚑ {len(p.flags)} to check</span>' if p.flags else "")
    return f'<div class="pf-tags">{kind}<span class="pf-badge t{t}">{TIER_TEXT[t]}</span>{flags}</div>'


# ----------------------------------------------------------------- promo row
def card(p: Promo) -> str:
    """One promo as a readable row: what it says, where it cuts, why it works. Everything else under Details."""
    t = tier(p)
    rank = (f'<span class="pf-rank{" top" if p.rank and p.rank <= 3 else ""}">{p.rank}</span>' if p.rank
            else f'<span class="pf-rank" style="font-size:13px">E{p.episodes[0]}</span>')
    hq, hact = quote_html(p.hook_beat, short=True)
    cq, cact = quote_html(p.cliff_beat, short=True)
    eps = " + ".join(f"Ep {x}" for x in p.episodes)
    return f"""<article class="pf-row" id="{e(p.id)}" data-kind="{p.kind}" data-tier="{t}" data-flag="{'1' if p.flags else '0'}">
<div class="pf-rankcell">{rank}</div>
<div class="pf-main">
<div><div class="pf-label hook">Opens on{f" · hook lands at {p.hook_at:.1f} s" if p.hook_at >= 0.5 else ""}</div><p class="pf-q{' act' if hact else ''}">{hq}</p><div class="pf-who">{e(who(p.hook_beat))} · {eps}</div></div>
<div class="pf-end"><div class="pf-label cliff">Cuts on</div><p class="{'act' if cact else ''}">{cq}</p></div>
<p class="pf-why">{e(p.why)}</p>
{_tags(p)}
</div>
<div class="pf-side">
<div class="pf-len"><b>{p.duration:.1f} s</b><span class="pf-score">Score <b>{score100(p)}</b></span></div>
<div><div class="pf-label" style="margin-bottom:8px">Cut points</div>{cut_list(p)}</div>
{cut_bar(p)}
</div>
<details class="pf-more"><summary>Details: why this score, what to check, the full cut</summary>
{_details_grid(p)}</details>
</article>"""


def _details_grid(p: Promo) -> str:
    """Score breakdown, checks, cut points and transcript: what an editor opens to judge a promo."""
    post = (f'<div><div class="pf-label" style="margin-bottom:6px">Why post it {"first" if p.rank == 1 else "here"}</div>'
            f'<p class="pf-why">{e(p.post_reason)}</p></div>' if p.post_reason else "")
    return f"""<div class="pf-detail">
<div style="display:flex;flex-direction:column;gap:22px">{post}{ai_line(p)}
<div><div class="pf-label" style="margin-bottom:8px">How the score adds up</div>{score_breakdown(p)}</div>
<div><div class="pf-label" style="margin-bottom:8px">For a human to check</div>{flag_list(p)}</div></div>
<div style="display:flex;flex-direction:column;gap:22px">
<div><div class="pf-label" style="margin-bottom:8px">Cuts</div>{segment_table(p)}</div>
<div><div class="pf-label" style="margin-bottom:8px">The cut, line by line</div>{transcript(p)}</div></div>
</div>"""


def cut_text(p: Promo) -> str:
    return "; ".join(f"Ep {s.ep} {fmt(s.start)}-{fmt(s.end)}" for s in p.segments)


def compact(p: Promo) -> str:
    """One promo as a single row (opens on → cuts on, cut points, length, score); click to expand the details."""
    t = tier(p)
    rank = (f'<span class="pf-rank{" top" if p.rank and p.rank <= 3 else ""}">{p.rank}</span>' if p.rank
            else f'<span class="pf-rank" style="font-size:12px">E{p.episodes[0]}</span>')
    hq, hact = quote_html(p.hook_beat, short=True)
    cq, _ = quote_html(p.cliff_beat, short=True)
    hq_full, hact_full = quote_html(p.hook_beat)
    cq_full, cact_full = quote_html(p.cliff_beat)
    cuts = "<br>".join(f"Ep {s.ep} {fmt(s.start)}–{fmt(s.end)}" for s in p.segments)
    kind = f'<span class="pf-badge st">{len(p.segments)} cuts</span>' if p.kind == "stitched" else ""
    flags = f'<span class="pf-badge flag" title="{e(" | ".join(p.flags))}">⚑ {len(p.flags)}</span>' if p.flags else ""
    eps = " + ".join(f"Ep {x}" for x in p.episodes)
    return f"""<details class="pf-crow" id="{e(p.id)}" data-kind="{p.kind}" data-tier="{t}" data-flag="{'1' if p.flags else '0'}" data-cut="{e(cut_text(p))}">
<summary>{rank}<span class="cr-main"><span class="cr-hook{' act' if hact else ''}">{hq}</span><span class="cr-cliff"><b>→</b> {cq}</span></span>
<span class="cr-meta"><span class="cr-cuts">{cuts}</span><span class="cr-len">{p.duration:.0f} s</span><span class="cr-score">{score100(p)}</span>
<span class="cr-tags"><span class="pf-badge t{t}">{t}</span>{kind}{flags}</span></span><span class="cr-chev"></span></summary>
<div class="cr-body">
<div class="cr-full"><div><div class="pf-label hook">Opens on{f" · hook lands at {p.hook_at:.1f} s" if p.hook_at >= 0.5 else ""}</div>
<p class="pf-q{' act' if hact_full else ''}" style="font-size:17px">{hq_full}</p><div class="pf-who">{e(who(p.hook_beat))} · {eps}</div></div>
<div class="pf-end"><div class="pf-label cliff">Cuts on</div><p class="{'act' if cact_full else ''}">{cq_full}</p></div></div>
<p class="pf-why">{e(p.why)}</p>
<div class="cr-actions">{_tags(p)}</div>
{_details_grid(p)}
</div></details>"""


def compact_list(promos: list[Promo]) -> str:
    head = ('<div class="pf-chead"><span>#</span><span>Opens on → cuts on</span><span>Cut points</span>'
            '<span class="r">Length</span><span class="r">Score</span><span>Tier · notes</span><span></span></div>')
    return f'<div class="pf-clist">{head}{"".join(compact(p) for p in promos)}</div>'


def promo_list(promos: list[Promo]) -> str:
    return '<div class="pf-list">' + "".join(card(p) for p in promos) + "</div>"


# ----------------------------------------------------------------- phone + spotlight
def phone(p: Promo) -> str:
    """A 9:16 storyboard of the promo as it would play in a feed."""
    tot = max(p.duration, 1e-6)
    bars = "".join(f'<span style="flex:{s.dur:.2f}"><i style="width:{100 if i == 0 else 0}%"></i></span>'
                   for i, s in enumerate(p.segments))
    hq, hact = quote_html(p.hook_beat, short=True)
    cq, _ = quote_html(p.cliff_beat, short=True)
    mids = []
    for s in p.segments:
        for b in s.beats:
            if b.kind == "dialogue" and b is not p.hook_beat and b is not p.cliff_beat:
                t = _clean(b)
                mids.append(f"<div><b>{e(speaker_name(b.speaker))}:</b> {e(t[:70] + ('…' if len(t) > 70 else ''))}</div>")
    shown = mids[:3]
    more = f'<div class="more">+ {len(mids) - len(shown)} more lines</div>' if len(mids) > len(shown) else ""
    return f"""<div class="pf-phone"><div class="pf-screen"><div class="pf-notch"></div>
<div class="pf-pbar">{bars}</div>
<div class="pf-ptop"><span>Episode {p.episodes[0]}</span><span>0:{int(tot):02d}</span></div>
<div class="pf-pcap"><div class="k">First 3 seconds</div><div class="q{' act' if hact else ''}">{hq}</div></div>
<div class="pf-pmid">{''.join(shown)}{more}</div>
<div class="pf-pcliff"><div class="k">Last frame</div><div class="q">{cq}</div></div>
<div class="pf-cta">▶ Watch Episode {p.episodes[0]}</div>
</div></div>"""


def spotlight(p: Promo, eyebrow: str = "Post this one first") -> str:
    hq, hact = quote_html(p.hook_beat)
    cq, cact = quote_html(p.cliff_beat)
    post = (f'<div><div class="pf-label" style="margin-bottom:6px">Why post it {"first" if p.rank == 1 else "here"}</div>'
            f'<p class="pf-why">{e(p.post_reason)}</p></div>' if p.post_reason else "")
    return f"""<div class="pf-spot">{phone(p)}<div class="detail">
<div><div class="pf-label accent">{e(eyebrow)}</div><div class="big{' act' if hact else ''}">{hq}</div>
<div class="pf-who" style="margin-top:6px">{e(who(p.hook_beat))}{f" · hook lands at {p.hook_at:.1f} s" if p.hook_at >= 0.5 else ""}</div></div>
<div class="pf-end"><div class="pf-label cliff">Cuts on</div><p class="{'act' if cact else ''}">{cq}</p></div>
{_tags(p)}
<div><div class="pf-label" style="margin-bottom:8px">Cuts · {p.duration:.1f} s in total</div>{segment_table(p)}</div>
<div><div class="pf-label" style="margin-bottom:6px">Why it works</div><p class="pf-why">{e(p.why)}</p></div>
{post}{ai_line(p)}
<details class="pf-more" style="margin-top:0"><summary>Details: how the score adds up, what to check, the full cut</summary>
<div class="facts" style="margin-top:16px">
<div><div class="pf-label" style="margin-bottom:8px">How the score adds up</div>{score_breakdown(p)}</div>
<div><div class="pf-label" style="margin-bottom:8px">For a human to check</div>{flag_list(p)}</div>
</div><div style="margin-top:18px">{transcript(p)}</div></details>
</div></div>"""


# ----------------------------------------------------------------- season map
def season_map(episodes, promos: list[Promo], library: list[Promo], link: bool = True) -> str:
    n = len(episodes)
    if not n:
        return ""
    longest = max(ep.duration for ep in episodes)
    height = 220
    ranked_ids = {p.id for p in promos}
    blocks: dict[int, list[str]] = {ep.num: [] for ep in episodes}
    href = (lambda pid: f' href="#{pid}"') if link else (lambda pid: "")
    for p in library:
        if p.id in ranked_ids:
            continue
        s = p.segments[0]
        if s.ep in blocks:
            blocks[s.ep].append(f'<a class="b lib"{href(p.id)} title="Best clip in Ep {s.ep}: {fmt(s.start)}–{fmt(s.end)}" '
                                f'style="top:{100 * s.start / longest:.2f}%;height:{100 * s.dur / longest:.2f}%"></a>')
    for p in promos:
        for i, s in enumerate(p.segments):
            if s.ep not in blocks:
                continue
            cls = "b st" if p.kind == "stitched" else "b"
            blocks[s.ep].append(f'<a class="{cls}"{href(p.id)} title="#{p.rank} · Ep {s.ep} {fmt(s.start)}–{fmt(s.end)}" '
                                f'style="top:{100 * s.start / longest:.2f}%;height:{max(1.6, 100 * s.dur / longest):.2f}%"></a>')
            if p.rank and p.rank <= 5 and i == 0:
                blocks[s.ep].append(f'<span class="rk" style="top:{100 * s.start / longest:.2f}%">{p.rank}</span>')
    cols = "".join(f'<div class="pf-col" style="height:{height}px"><div class="ep" style="height:{100 * ep.duration / longest:.2f}%" '
                   f'title="Episode {ep.num} · {fmt(ep.duration)}"></div>{"".join(blocks[ep.num])}</div>' for ep in episodes)
    ticks = "".join(f'<span style="top:{100 * t / longest:.2f}%">{t // 60}:{t % 60:02d}</span>'
                    for t in range(0, int(longest) + 1, 60))
    xl = "".join(f"<span>{ep.num if (ep.num == 1 or ep.num % 5 == 0) else ''}</span>" for ep in episodes)
    tmpl = f"grid-template-columns:repeat({n},1fr)"
    return f"""<div class="pf-map">
<div class="pf-legend"><span><i style="background:var(--hook)"></i>Single-clip promo</span><span><i style="background:var(--stitch)"></i>Stitched promo</span>
<span><i style="border:1.5px dashed var(--faint)"></i>Best clip in that episode</span><span><i style="background:var(--surface3)"></i>Episode length</span>
<span><i style="background:var(--ink);border-radius:4px"></i>Top-5 rank</span></div>
<div class="pf-mapgrid" style="margin-top:24px"><div class="pf-axis" style="height:{height}px">{ticks}</div><div class="pf-cols" style="{tmpl}">{cols}</div></div>
<div class="pf-xlab" style="{tmpl}">{xl}</div>
<div style="font-size:13px;color:var(--faint);margin-top:10px">Episodes 1–{n} left to right · time runs down</div></div>"""


# ----------------------------------------------------------------- library table
def episode_index(episodes, library: list[Promo]) -> str:
    have = {p.episodes[0] for p in library}
    return '<div class="pf-epindex">' + "".join(
        f'<a href="#ep-{ep.num}">{ep.num}</a>' if ep.num in have else
        f'<a class="none" title="No clip met the rules in this episode">{ep.num}</a>' for ep in episodes) + "</div>"


def library_table(library: list[Promo], ranked_ids: set[str] | None = None, link: bool = True) -> str:
    ranked_ids = ranked_ids or set()
    rows = []
    for p in library:
        s = p.segments[0]
        t = tier(p)
        hq, _ = quote_html(p.hook_beat, short=True)
        cq, _ = quote_html(p.cliff_beat, short=True)
        where = (f'<a href="#{p.id}">#{p.rank}</a>' if link else f"#{p.rank}") if p.id in ranked_ids else "—"
        rows.append(f'<tr id="ep-{s.ep}"><td class="num"><b>{s.ep}</b></td><td class="num">{fmt(s.start)} → {fmt(s.end)} '
                    f'<span style="color:var(--faint)">· {p.duration:.0f} s</span></td>'
                    f'<td><span class="pf-badge t{t}">{t}</span></td><td class="q h"><span title="{hq}">{hq}</span></td>'
                    f'<td class="q"><span title="{cq}">{cq}</span></td>'
                    f'<td class="num">{score100(p)}</td><td class="num">{where}</td></tr>')
    return ('<div class="pf-tablewrap"><table class="pf-table pf-libtable"><colgroup><col style="width:52px"><col style="width:244px">'
            '<col style="width:64px"><col><col><col style="width:70px"><col style="width:78px"></colgroup>'
            '<thead><tr><th>Ep</th><th>Cut</th><th>Tier</th><th>Opens on</th><th>Cuts on</th><th>Score</th><th>Ranked</th></tr></thead>'
            '<tbody>' + "".join(rows) + "</tbody></table></div>")


# ----------------------------------------------------------------- checks
def checks_panel(c: dict) -> str:
    ok = c["passed"] == c["checked"]
    rules = [
        ("Every promo is 20–60 seconds", "Checked on every ranked and library promo."),
        ("The hook lands inside 3 seconds", "Long opening lines are marked down."),
        ("No cut inside a spoken line", "Split lines (“I said…” / “…let her go”) stay together."),
        ("Cuts play in story order", "Stitched segments never overlap or flash forward."),
        ("Every timestamp is real", "Each cut point is copied from the script, never generated."),
    ]
    items = "".join(f'<li><span class="ic">{"✓" if ok else "!"}</span><div><b>{a}</b><span>{b}</span></div></li>' for a, b in rules)
    miss = c["episodes_without"]
    items += (f'<li><span class="ic warn">!</span><div><b>{c["episodes_with_a_promo"]} of {c["episodes_with_a_promo"] + len(miss)} episodes have a usable clip</b>'
              f'<span>{"None found in Ep " + ", ".join(map(str, miss)) + ". " if miss else ""}'
              f'Best clip per episode: {c["library_tiers"]["A"]} tier A, {c["library_tiers"]["B"]} tier B, {c["library_tiers"]["C"]} tier C.</span></div></li>')
    flags = "".join(f'<li>{e(k)}: {v} promo{"s" if v != 1 else ""}</li>'
                    for k, v in list(c["ranked_flag_counts"].items())[:8])
    return f"""<div class="pf-checks"><div class="pf-pass"><div class="v">{c["passed"]}<small> / {c["checked"]}</small></div>
<div class="l">promos pass every hard rule</div><div class="c">Re-checked against the script after every run. These rules live in code, so an AI model can't break them.</div></div>
<ul class="pf-rules">{items}</ul></div>
<div style="margin-top:24px"><div class="pf-label" style="margin-bottom:10px">Flags on the ranked list, for a human to check</div>
<ul class="pf-flags" style="max-width:640px">{flags or '<li>None</li>'}</ul></div>"""
