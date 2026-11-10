"""Promo Finder — Streamlit UI.   Run:  streamlit run app.py"""
from __future__ import annotations

import base64
import io
import os
import re
import zipfile
from html import escape as html_escape
from pathlib import Path

import pandas as pd
import streamlit as st

from promo_finder import ui
from promo_finder.checks import run_checks
from promo_finder.compare import compare, cut_key, to_csv as compare_csv, to_markdown as compare_md
from promo_finder.llm import Judge
from promo_finder.parser import finalize, fmt, load_zip_bytes, parse_text
from promo_finder.pipeline import run
from promo_finder.progress import ReviewProgress
from promo_finder.report import timing_note, to_csv, to_html, to_json, to_pdf
from promo_finder.usage import SarvamConfig

ROOT = Path(__file__).parent
st.set_page_config(page_title="Promo Finder", page_icon=str(ROOT / "static" / "favicon.png"),
                   layout="wide", initial_sidebar_state="expanded")



st.markdown("<style>\n\n.pf{--bg:#f6f6f3;--surface:#ffffff;--surface2:#f4f4f1;--surface3:#e8e8e3;--line:#e3e3de;--line2:#cfcfc8;\n--ink:#121216;--ink2:#34343c;--mute:#55555f;--faint:#6b6b75;\n--hook:#d6194a;--hook-bg:#fff0f3;--cliff:#a85400;--cliff-bg:#fff6e8;--stitch:#5b3fd6;--stitch-bg:#f2eeff;\n--ok:#137a3d;--ok-bg:#eaf7ef;--warn:#8a5a00;--warn-bg:#fff8e1;--bad:#b42318;--bad-bg:#fdeceb;\n--accent:#d6194a;--grad:linear-gradient(135deg,#ff3d6e 0%,#ff7a45 100%);\n--shadow:0 1px 2px rgba(18,18,22,.05),0 2px 8px -2px rgba(18,18,22,.06);\n--sans:'Inter',ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;\n--mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;\ncolor:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased;\nfont-feature-settings:\"cv11\",\"ss01\";font-variant-numeric:tabular-nums}\n.pf[data-theme=dark]{--bg:#0f0f12;--surface:#17171c;--surface2:#1f1f25;--surface3:#2b2b33;--line:#2b2b33;--line2:#3b3b45;\n--ink:#f5f5f6;--ink2:#dcdce0;--mute:#b0b0ba;--faint:#9a9aa5;\n--hook:#ff7b98;--hook-bg:rgba(255,123,152,.12);--cliff:#ffc165;--cliff-bg:rgba(255,193,101,.11);--stitch:#b4a3ff;--stitch-bg:rgba(180,163,255,.13);\n--ok:#5ee29a;--ok-bg:rgba(94,226,154,.12);--warn:#ffd666;--warn-bg:rgba(255,214,102,.1);--bad:#ff8a80;--bad-bg:rgba(255,138,128,.12);\n--accent:#ff7b98;--shadow:none}\n.pf *{box-sizing:border-box}\n.pf h1,.pf h2,.pf h3,.pf p,.pf ol,.pf ul{margin:0}\n.pf ol,.pf ul{padding-left:0!important;margin-left:0!important}.pf li{margin:0!important}\n.pf a{color:inherit}\n.pf .mono{font-family:var(--mono);font-size:.92em}\n/* type scale */\n.pf-label{font-size:12px;line-height:1.3;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--faint)}\n.pf-label.hook{color:var(--hook)}.pf-label.cliff{color:var(--cliff)}.pf-label.accent{color:var(--accent)}\n.pf-h1{font-size:clamp(32px,4.4vw,48px);line-height:1.1;font-weight:700;letter-spacing:-.025em;text-wrap:balance}\n.pf-h2{font-size:clamp(24px,2.6vw,30px);line-height:1.2;font-weight:700;letter-spacing:-.02em;margin:6px 0 6px;text-wrap:balance}\n.pf-sub{font-size:16px;color:var(--mute);max-width:70ch}\n.pf-section{margin:52px 0 0}\n.pf-section-head{margin-bottom:20px}\n.pf-grad{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}\n/* brand */\n.pf-brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;letter-spacing:-.01em}\n.pf-logo{width:28px;height:28px;border-radius:8px;background:#121216;position:relative;flex:none}\n.pf-logo i{position:absolute;left:5px;right:5px;top:13px;height:2px;background:rgba(255,255,255,.35);border-radius:1px}\n.pf-logo i::before{content:\"\";position:absolute;left:5px;width:8px;top:-2px;height:6px;background:#ff2d6a;border-radius:1px}\n.pf-logo i::after{content:\"\";position:absolute;left:3px;top:-6px;width:2px;height:14px;background:#fff;border-radius:1px;box-shadow:10px 0 0 #fff}\n.pf[data-theme=dark] .pf-logo{background:#26262e;box-shadow:inset 0 0 0 1px #3b3b45}\n/* badges */\n.pf-badge{display:inline-flex;align-items:center;gap:6px;font-size:13px;line-height:1;font-weight:600;padding:6px 10px;border-radius:8px;\nbackground:var(--surface2);color:var(--ink2);border:1px solid var(--line);white-space:nowrap}\n.pf-badge.st{background:var(--stitch-bg);color:var(--stitch);border-color:transparent}\n.pf-badge.tA{background:var(--ok-bg);color:var(--ok);border-color:transparent}\n.pf-badge.tB{background:var(--warn-bg);color:var(--warn);border-color:transparent}\n.pf-badge.tC{background:var(--bad-bg);color:var(--bad);border-color:transparent}\n.pf-badge.flag{background:var(--warn-bg);color:var(--warn);border-color:transparent}\n.pf-badge.ai{background:var(--hook-bg);color:var(--hook);border-color:transparent}\n/* KPIs */\n.pf-summary{display:flex;flex-wrap:wrap;gap:6px 22px;font-size:15px;color:var(--ink2);padding:14px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}\n.pf-summary b{color:var(--ink);font-weight:700}\n.pf-mode{display:inline-block;font-size:14px;padding:6px 10px;border-radius:8px;background:var(--surface2);color:var(--ink2);border:1px solid var(--line)}\n.pf-mode.ai{background:var(--stbg,#f2eeff);color:var(--stitch);border-color:transparent}\n.pf-mode.mock{background:var(--warn-bg);color:var(--warn);border-color:transparent;font-weight:600}\n.pf-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}\n.pf-kpi{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px 20px;box-shadow:var(--shadow)}\n.pf-kpi .v{font-size:32px;line-height:1.1;font-weight:700;letter-spacing:-.025em}\n.pf-kpi .l{font-size:15px;font-weight:600;color:var(--ink2);margin-top:6px}\n.pf-kpi .c{font-size:13px;color:var(--faint)}\n/* promo row (ranked list) */\n.pf-list{display:flex;flex-direction:column;gap:12px}\n.pf-row{display:grid;grid-template-columns:52px minmax(0,1fr) 270px;gap:0 24px;background:var(--surface);border:1px solid var(--line);\nborder-radius:16px;padding:20px 22px;box-shadow:var(--shadow);scroll-margin-top:90px}\n.pf-row:target{outline:2px solid var(--accent);outline-offset:2px}\n.pf-rank{width:40px;height:40px;border-radius:10px;display:grid;place-items:center;font-size:17px;font-weight:700;\nbackground:var(--surface2);color:var(--ink);border:1px solid var(--line)}\n.pf-rank.top{background:var(--ink);color:var(--surface);border-color:var(--ink)}\n.pf-main{display:flex;flex-direction:column;gap:12px;min-width:0}\n.pf-q{font-size:19px;line-height:1.4;font-weight:600;color:var(--ink);letter-spacing:-.01em;margin-top:4px}\n.pf-q.act{font-style:italic;font-weight:500;font-size:17px;color:var(--ink2)}\n.pf-who{font-size:14px;color:var(--faint);margin-top:2px}\n.pf-end{border-left:3px solid var(--cliff);padding:2px 0 2px 12px}\n.pf-end p{font-size:16px;line-height:1.5;color:var(--ink2);margin-top:3px}\n.pf-end p.act{font-style:italic}\n.pf-why{font-size:15px;line-height:1.55;color:var(--ink2)}\n.pf-tags{display:flex;flex-wrap:wrap;gap:6px}\n.pf-side{display:flex;flex-direction:column;gap:12px;border-left:1px solid var(--line);padding-left:22px}\n.pf-len{display:flex;align-items:baseline;justify-content:space-between}\n.pf-len b{font-size:24px;font-weight:700;letter-spacing:-.02em}\n.pf-len span{font-size:14px;color:var(--mute)}\n.pf-score{font-size:14px;color:var(--mute)}.pf-score b{color:var(--ink);font-size:15px}\n.pf-cuts{list-style:none;padding:0;display:flex;flex-direction:column;gap:6px}\n.pf-cuts li{display:flex;gap:10px;align-items:baseline;font-family:var(--mono);font-size:14px;color:var(--ink2)}\n.pf-cuts li span{font-family:var(--sans);font-size:12px;font-weight:600;color:var(--faint);min-width:40px;text-transform:uppercase;letter-spacing:.04em}\n.pf-bar{display:flex;gap:3px;height:6px}\n.pf-bar i{display:block;height:100%;border-radius:999px;background:var(--stitch)}\n.pf-barcap{font-size:13px;color:var(--faint)}\n.pf-more{grid-column:2 / -1;margin-top:14px;border-top:1px solid var(--line);padding-top:12px}\n.pf-more>summary{cursor:pointer;list-style:none;font-size:14px;font-weight:600;color:var(--mute);display:inline-flex;align-items:center;gap:8px}\n.pf-more>summary::-webkit-details-marker{display:none}\n.pf-more>summary::before{content:\"\";width:7px;height:7px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;\ntransform:rotate(-45deg);transition:transform .15s}\n.pf-more[open]>summary::before{transform:rotate(45deg)}\n.pf-more>summary:hover{color:var(--ink)}\n.pf-detail{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:20px 32px;margin-top:16px}\n.pf-detail h4{margin:0 0 8px}\n@media (max-width:860px){.pf-row{grid-template-columns:1fr;padding:18px}.pf-row>.pf-rankcell{margin-bottom:10px}\n.pf-side{border-left:0;padding-left:0;border-top:1px solid var(--line);padding-top:14px;margin-top:16px}.pf-more{grid-column:1}\n.pf-detail{grid-template-columns:1fr}}\n/* compact promo rows: one line per promo, click to expand */\n.pf-clist{background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--shadow)}\n.pf-chead,.pf-crow>summary{display:grid;grid-template-columns:34px minmax(0,1fr) 196px 52px 46px 132px 14px;gap:0 14px;align-items:center;padding:10px 16px}\n.pf-chead{font-size:12px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--faint);background:var(--surface2);border-bottom:1px solid var(--line);padding-top:8px;padding-bottom:8px}\n.pf-crow{border-bottom:1px solid var(--line);scroll-margin-top:90px}\n.pf-crow:last-child{border-bottom:0}\n.pf-crow:target{outline:2px solid var(--accent);outline-offset:-2px}\n.pf-crow>summary{cursor:pointer;list-style:none}\n.pf-crow>summary::-webkit-details-marker{display:none}\n.pf-crow>summary:hover{background:var(--surface2)}\n.pf-crow[open]>summary{background:var(--surface2)}\n.pf-crow .pf-rank{width:30px;height:30px;font-size:14px;border-radius:8px}\n.cr-main{min-width:0;display:flex;flex-direction:column;gap:2px}\n.cr-main span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.cr-hook{font-size:15px;font-weight:600;color:var(--ink)}\n.cr-hook.act{font-style:italic;font-weight:500}\n.cr-cliff{font-size:14px;color:var(--mute)}\n.cr-cliff b{color:var(--cliff);font-weight:600}\n.cr-cuts{font-family:var(--mono);font-size:12.5px;line-height:1.5;color:var(--ink2);white-space:nowrap}\n.cr-len,.cr-score{font-size:14px;color:var(--ink2);text-align:right;font-variant-numeric:tabular-nums}\n.cr-score{font-weight:700;color:var(--ink)}\n.cr-tags{display:flex;gap:4px;flex-wrap:wrap}\n.cr-tags .pf-badge{font-size:12px;padding:4px 7px}\n.cr-chev{width:7px;height:7px;border-right:2px solid var(--faint);border-bottom:2px solid var(--faint);transform:rotate(45deg);margin-top:-4px;transition:transform .15s}\n.pf-crow[open] .cr-chev{transform:rotate(-135deg);margin-top:4px}\n.cr-body{padding:6px 16px 20px 64px;display:flex;flex-direction:column;gap:16px}\n.cr-body .pf-detail{margin-top:0}\n.cr-full{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px 32px}\n.cr-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}\n.pf-chead .r{text-align:right}\n@media (max-width:860px){\n.pf-chead{display:none}\n.pf-crow>summary{grid-template-columns:30px minmax(0,1fr) 14px;grid-template-areas:\"r m c\" \". x x\";gap:6px 12px;padding:12px 14px}\n.pf-crow>summary>.pf-rank{grid-area:r}.pf-crow>summary>.cr-main{grid-area:m}.pf-crow>summary>.cr-chev{grid-area:c}\n.cr-meta{grid-area:x;display:flex!important;flex-wrap:wrap;gap:4px 12px;align-items:center}\n.cr-body{padding:4px 14px 18px}.cr-full{grid-template-columns:1fr}}\n.cr-meta{display:contents}\n.pf-libtable{table-layout:fixed}\n.pf-libtable td{padding:9px 14px!important;line-height:1.4!important;vertical-align:middle!important}\n.pf-libtable td.q{min-width:0!important}\n.pf-libtable td.q span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n/* score breakdown */\n.pf-why-score{width:100%;border-collapse:collapse;font-size:14px}\n.pf-why-score td{padding:6px 0;border-bottom:1px solid var(--line);color:var(--ink2)}\n.pf-why-score td.r{text-align:right;font-family:var(--mono);font-size:13px;white-space:nowrap;padding-left:12px}\n.pf-why-score tr.tot td{border-bottom:0;font-weight:700;color:var(--ink);padding-top:8px}\n.pf-why-score tr.note td{border-bottom:0;font-size:13px;color:var(--faint);padding-top:2px}\n.pf-segtable{width:100%;border-collapse:collapse;font-size:14px}\n.pf-segtable th{font-size:12px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--faint);text-align:left;padding:0 10px 6px 0}\n.pf-segtable td{padding:7px 10px 7px 0;border-top:1px solid var(--line);vertical-align:top;color:var(--ink2)}\n.pf-segtable td.m{font-family:var(--mono);font-size:13px;white-space:nowrap}\n@media (max-width:600px){.pf-segtable th:nth-child(6),.pf-segtable td:nth-child(6){display:none}.pf-segtable td.m{font-size:12px}}\n.pf-spot .detail,.pf-row>*{min-width:0}\n.pf-epindex{display:flex;flex-wrap:wrap;gap:4px;margin:0 0 14px}\n.pf-epindex a{font-family:var(--mono);font-size:12px;text-decoration:none;padding:3px 6px;border-radius:6px;border:1px solid var(--line);color:var(--ink2);background:var(--surface)}\n.pf-epindex a.none{color:var(--faint);border-style:dashed}\n/* meters */\n.pf-meters{display:flex;flex-direction:column;gap:10px}\n.pf-meter .lab{display:flex;justify-content:space-between;font-size:14px;color:var(--ink2)}\n.pf-meter .lab b{font-weight:600}\n.pf-meter .track{height:6px;border-radius:999px;background:var(--surface3);margin-top:5px;overflow:hidden}\n.pf-meter .track i{display:block;height:100%;border-radius:999px;background:var(--ink2)}\n/* flags */\n.pf-flags{list-style:none;padding:0;display:flex;flex-direction:column;gap:6px}\n.pf-flags li{font-size:14px;color:var(--ink2);padding:8px 10px;border-radius:8px;background:var(--warn-bg)}\n.pf-flags li::before{content:\"⚑\";color:var(--warn);margin-right:8px}\n/* transcript */\n.pf-tx{list-style:none;padding:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;max-height:380px;overflow-y:auto}\n.pf-tx li{display:grid;grid-template-columns:54px 1fr;gap:12px;padding:9px 12px;font-size:14px;line-height:1.5;border-top:1px solid var(--line)}\n.pf-tx li:first-child{border-top:0}\n.pf-tx li.sep{display:block;background:var(--surface2);font-size:12px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--stitch)}\n.pf-tx .t{font-family:var(--mono);font-size:13px;color:var(--faint)}\n.pf-tx .s{font-weight:600;color:var(--ink)}\n.pf-tx .a{color:var(--mute);font-style:italic}\n.pf-tx li.hk{background:var(--hook-bg)}.pf-tx li.cf{background:var(--cliff-bg)}\n/* phone storyboard */\n.pf-phone{width:280px;flex:none;border-radius:44px;padding:10px;background:#1b1b20;\nbox-shadow:0 0 0 1px rgba(0,0,0,.12),0 30px 60px -30px rgba(18,18,22,.45)}\n.pf-screen{position:relative;height:560px;border-radius:35px;overflow:hidden;display:flex;flex-direction:column;padding:50px 20px 20px;color:#fff;\nbackground:#141418}\n.pf-notch{position:absolute;top:12px;left:50%;transform:translateX(-50%);width:90px;height:24px;border-radius:999px;background:#000}\n.pf-pbar{display:flex;gap:4px}\n.pf-pbar span{height:3px;border-radius:999px;background:rgba(255,255,255,.3);overflow:hidden}\n.pf-pbar span i{display:block;height:100%;background:#fff}\n.pf-ptop{display:flex;justify-content:space-between;margin-top:10px;font-size:12px;font-weight:600;color:rgba(255,255,255,.8)}\n.pf-pcap{margin-top:22px}\n.pf-pcap .k,.pf-pcliff .k{font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase}\n.pf-pcap .k{color:#ff9ab2}\n.pf-pcap .q{font-size:24px;line-height:1.25;font-weight:700;margin-top:6px;letter-spacing:-.01em}\n.pf-pcap .q.act{font-style:italic;font-weight:600;font-size:19px}\n.pf-pmid{margin-top:20px;display:flex;flex-direction:column;gap:10px;font-size:14px;line-height:1.45;color:rgba(255,255,255,.78)}\n.pf-pmid b{color:#fff;font-weight:600}\n.pf-pmid .more{color:rgba(255,255,255,.55);font-size:13px}\n.pf-pcliff{margin-top:auto;border-radius:14px;padding:12px 14px;background:rgba(255,184,77,.16);border:1px solid rgba(255,184,77,.4)}\n.pf-pcliff .k{color:#ffcf85}\n.pf-pcliff .q{font-size:15px;line-height:1.4;margin-top:4px}\n.pf-cta{margin-top:12px;border-radius:12px;padding:11px;text-align:center;font-size:14px;font-weight:600;background:rgba(255,255,255,.14);color:#fff}\n/* spotlight */\n.pf-spot{display:grid;grid-template-columns:auto minmax(0,1fr);gap:44px;align-items:start;background:var(--surface);border:1px solid var(--line);\nborder-radius:20px;padding:32px;box-shadow:var(--shadow)}\n.pf-spot .detail{display:flex;flex-direction:column;gap:22px;min-width:0}\n.pf-spot .big{font-size:clamp(24px,2.6vw,32px);line-height:1.25;font-weight:700;letter-spacing:-.02em;margin-top:6px}\n.pf-spot .big.act{font-style:italic;font-weight:600}\n.pf-spot .facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:18px 28px}\n@media (max-width:860px){.pf-spot{grid-template-columns:1fr;justify-items:center;padding:20px}.pf-spot .detail{width:100%}}\n/* season map */\n.pf-map{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:22px 22px 16px;box-shadow:var(--shadow)}\n.pf-legend{display:flex;flex-wrap:wrap;gap:8px 22px;font-size:14px;color:var(--ink2);margin-bottom:22px}\n.pf-legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:8px;vertical-align:-1px}\n.pf-mapgrid{display:grid;grid-template-columns:44px 1fr;gap:10px}\n.pf-axis{position:relative;font-family:var(--mono);font-size:12px;color:var(--faint)}\n.pf-axis span{position:absolute;right:0;transform:translateY(-50%)}\n.pf-cols{display:grid;gap:3px}\n.pf-col{position:relative}\n.pf-col .ep{position:absolute;left:0;right:0;top:0;border-radius:4px;background:var(--surface3)}\n.pf-col a.b{position:absolute;left:1px;right:1px;border-radius:3px;background:var(--hook);text-decoration:none}\n.pf-col a.b.st{background:var(--stitch)}\n.pf-col a.b.lib{background:transparent;border:1.5px dashed var(--faint)}\n.pf-col .rk{position:absolute;left:50%;transform:translate(-50%,-125%);min-width:20px;height:20px;padding:0 4px;border-radius:6px;\ndisplay:grid;place-items:center;font-size:12px;font-weight:700;background:var(--ink);color:var(--surface);z-index:3}\n.pf-xlab{display:grid;gap:3px;margin:10px 0 0 54px;font-family:var(--mono);font-size:12px;color:var(--faint);text-align:center}\n/* table */\n.pf-tablewrap{background:var(--surface);border:1px solid var(--line);border-radius:16px;overflow:auto;box-shadow:var(--shadow)}\n.pf-table{width:100%;border-collapse:collapse;font-size:15px;min-width:820px}\n.pf-table th{font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--faint);text-align:left;\npadding:12px 16px;background:var(--surface2);border-bottom:1px solid var(--line)}\n.pf-table td{padding:14px 16px;border-bottom:1px solid var(--line);vertical-align:top;color:var(--ink2);line-height:1.5}\n.pf-table tr:last-child td{border-bottom:0}\n.pf-table td.num{font-family:var(--mono);font-size:14px;white-space:nowrap}\n.pf-table td.q{min-width:240px}\n.pf-table td.q.h{color:var(--ink);font-weight:500}\n/* checks */\n.pf-checks{display:grid;grid-template-columns:minmax(220px,300px) minmax(0,1fr);gap:16px;align-items:start}\n@media (max-width:860px){.pf-checks{grid-template-columns:1fr}}\n.pf-pass{background:var(--ok-bg);border-radius:16px;padding:24px}\n.pf-pass .v{font-size:44px;line-height:1;font-weight:700;letter-spacing:-.03em;color:var(--ok)}\n.pf-pass .v small{font-size:22px;color:var(--ok);opacity:.7}\n.pf-pass .l{font-size:16px;font-weight:600;margin-top:10px}.pf-pass .c{font-size:14px;color:var(--ink2);margin-top:6px}\n.pf-rules{list-style:none;padding:0;background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow)}\n.pf-rules li{display:grid;grid-template-columns:28px 1fr;gap:12px;padding:14px 18px;border-top:1px solid var(--line)}\n.pf-rules li:first-child{border-top:0}\n.pf-rules .ic{width:24px;height:24px;border-radius:50%;display:grid;place-items:center;font-size:13px;font-weight:700;background:var(--ok-bg);color:var(--ok)}\n.pf-rules .ic.warn{background:var(--warn-bg);color:var(--warn)}\n.pf-rules b{display:block;font-size:15px;font-weight:600}.pf-rules span{font-size:14px;color:var(--mute)}\n/* landing / method */\n.pf-steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}\n.pf-step{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px;box-shadow:var(--shadow)}\n.pf-step .n{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:8px;background:var(--surface2);font-size:14px;font-weight:700}\n.pf-step b{display:block;font-size:17px;margin-top:12px}\n.pf-step p{color:var(--mute);font-size:15px;margin-top:4px;line-height:1.55}\n.pf-step .tag{display:inline-block;margin-top:12px}\n.pf-checklist{list-style:none;padding:0;display:flex;flex-direction:column;gap:8px}\n.pf-checklist li{display:flex;gap:10px;align-items:baseline;font-size:16px;color:var(--ink2)}\n.pf-checklist li::before{content:\"✓\";color:var(--ok);font-weight:700}\n\n/* Restrained Kuku corporate palette: charcoal, white and signature red. */\nsection[data-testid=\"stSidebar\"]{background:#111113!important;border-right:1px solid #29292d!important}\nsection[data-testid=\"stSidebar\"] [data-testid=\"stMarkdownContainer\"] p,\nsection[data-testid=\"stSidebar\"] label,\nsection[data-testid=\"stSidebar\"] [data-testid=\"stCaptionContainer\"]{color:#e8e8eb!important}\nsection[data-testid=\"stSidebar\"] [data-testid=\"stRadio\"] [role=\"radiogroup\"]{gap:5px}\nsection[data-testid=\"stSidebar\"] [data-testid=\"stRadio\"] [role=\"radiogroup\"] label{border-radius:9px;padding:8px 10px;color:#ededf0!important;background:transparent}\nsection[data-testid=\"stSidebar\"] [data-testid=\"stRadio\"] [role=\"radiogroup\"] label:has(input:checked){background:#321719!important;color:#fff!important;border-left:3px solid #e31e24;padding-left:7px}\nsection[data-testid=\"stSidebar\"] [data-testid=\"stRadio\"] [role=\"radiogroup\"] label p{color:inherit!important;font-weight:600}\nsection[data-testid=\"stSidebar\"] .pf-service{background:#202024;border-color:#38383f;color:#f4f4f5}\nsection[data-testid=\"stSidebar\"] .pf-service .dot{background:#22c55e}\nsection[data-testid=\"stSidebar\"] [data-testid=\"stAlert\"]{background:#202024;color:#eee}\n.pf{--hook:#e31e24;--hook-bg:#fff0f0;--accent:#e31e24;--grad:linear-gradient(135deg,#e31e24 0%,#b71920 100%)}\n[data-testid=\"stBaseButton-primary\"]{background:#e31e24!important;border-color:#e31e24!important}\n[data-testid=\"stBaseButton-primary\"]:hover{background:#bd171d!important;border-color:#bd171d!important}\n.st-key-home_upload_panel [data-testid=\"stFileUploaderDropzone\"] button{background:#e31e24!important;border-color:#e31e24!important}\n.st-key-home_upload_panel [data-testid=\"stFileUploaderDropzone\"] button:hover{background:#bd171d!important;border-color:#bd171d!important}\n.pf-how-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:22px}\n.pf-how-card{background:#fff;border:1px solid #e7e5e7;border-radius:14px;padding:20px 22px;box-shadow:0 2px 10px rgba(18,18,22,.035)}\n.pf-how-card .num{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:8px;background:#fff0f0;color:#e31e24;font-size:13px;font-weight:700;margin-bottom:12px}\n.pf-how-card h3{font-size:16px;line-height:1.35;margin:0 0 6px;color:#171719}\n.pf-how-card p{font-size:14px;line-height:1.65;color:#5b5b63;margin:0}\n.pf-how-note{margin-top:18px;border-left:3px solid #e31e24;background:#fff7f7;padding:15px 18px;border-radius:0 10px 10px 0;color:#414148;font-size:14px;line-height:1.65}\n.pf-page-head{margin:4px 0 22px}\n.pf-page-head h1{font-size:30px;letter-spacing:-.7px;margin:6px 0;color:#171719}\n.pf-page-head p{font-size:15px;color:#666670;margin:0}\n@media(max-width:700px){.pf-how-grid{grid-template-columns:1fr}.pf-page-head h1{font-size:25px}}\n\n/* Home layout: screenshot-matched, restrained Kuku black / white / red. */\nsection[data-testid=\"stSidebar\"]{background:#111113!important}\nsection[data-testid=\"stSidebar\"] [data-testid=\"stRadio\"] label{padding:10px 12px!important;border-radius:10px!important}\nsection[data-testid=\"stSidebar\"] [data-testid=\"stRadio\"] label:has(input:checked){background:linear-gradient(100deg,#e31e24,#9f171c)!important;border-left:0!important}\nsection[data-testid=\"stSidebar\"] [data-testid=\"stRadio\"] label p{font-size:15px!important}\n.pf-home-hero{display:flex;align-items:center;justify-content:space-between;gap:24px;margin:0 0 24px}\n.pf-home-hero h1{font-size:36px;line-height:1.12;letter-spacing:-1.2px;margin:8px 0 10px;color:#171719}\n.pf-home-hero h1 span{color:#e31e24}\n.pf-home-hero p{font-size:16px;color:#62616a;margin:0;line-height:1.6}\n.pf-home-hero .pf-mascot-welcome{width:112px;height:122px}\n.pf-value-row{display:grid;grid-template-columns:repeat(3,1fr);gap:0;margin:16px 0 26px}\n.pf-value{display:flex;align-items:center;gap:12px;padding:7px 20px;border-right:1px solid #e6e3e7}\n.pf-value:first-child{padding-left:0}.pf-value:last-child{border:0}\n.pf-value .ic{width:42px;height:42px;display:grid;place-items:center;border-radius:12px;background:#fff0f0;color:#e31e24;font-size:22px;font-weight:700}\n.pf-value b{display:block;font-size:14px;color:#171719}.pf-value small{display:block;font-size:12px;color:#666670;margin-top:3px}\n.pf-upload-shell{background:#fff;border:1px solid #eee7e9;border-radius:18px;padding:22px 24px 18px;box-shadow:0 7px 26px rgba(30,20,24,.045)}\n.pf-upload-title{text-align:center;font-size:23px;font-weight:700;color:#171719;margin:0 0 3px}\n.pf-upload-sub{text-align:center;color:#666670;font-size:14px;margin:0 0 14px}\n.pf-upload-foot{font-size:12px;color:#777680;text-align:center;margin-top:7px}\n.pf-quickstats{margin-top:22px;padding:16px;border:1px solid #303034;border-radius:14px;background:#1b1b1f}\n.pf-quickstats h4{color:#fff;font-size:14px;margin:0 0 13px}\n.pf-quickstat{display:flex;align-items:center;gap:11px;margin:11px 0;color:#fff}\n.pf-quickstat .ico{width:36px;height:36px;display:grid;place-items:center;border-radius:10px;background:#39191c;color:#ff4449;font-size:17px}\n.pf-quickstat b{display:block;font-size:14px}.pf-quickstat small{display:block;color:#b9b9bf;font-size:12px;margin-top:1px}\n.pf-start-steps{margin-top:22px}\n@media(max-width:850px){.pf-home-hero h1{font-size:29px}.pf-value-row{grid-template-columns:1fr;gap:8px}.pf-value{border:0;padding:6px 0}.pf-home-hero .pf-mascot-welcome{width:78px;height:90px}}\n[data-testid=\"stToolbarActions\"],[data-testid=\"stMainMenu\"],[data-testid=\"stDecoration\"],#MainMenu,footer{display:none!important}\nheader[data-testid=\"stHeader\"]{background:transparent;pointer-events:none}\nheader[data-testid=\"stHeader\"] button{pointer-events:auto}\n[data-testid=\"stExpandSidebarButton\"],[data-testid=\"stSidebarCollapsedControl\"]{visibility:visible!important;opacity:1!important}\n[data-testid=\"stExpandSidebarButton\"]{width:auto!important;height:auto!important;padding:9px 16px 9px 12px!important;border-radius:999px!important;background:#d6194a!important;box-shadow:0 2px 10px rgba(214,25,74,.35)!important;gap:6px!important}\n[data-testid=\"stExpandSidebarButton\"]:hover{background:#b3133d!important}\n[data-testid=\"stExpandSidebarButton\"] span{color:#fff!important}\n[data-testid=\"stExpandSidebarButton\"]::after{content:\"Project\";font:600 14px/1 Inter,sans-serif;color:#fff;white-space:nowrap}\n@media (max-width:860px){.block-container{padding-top:4.6rem!important}}\n.block-container{max-width:1200px;padding-top:2.2rem;padding-bottom:5rem}\nsection[data-testid=\"stSidebar\"]>div{padding-top:.4rem}\n[data-testid=\"stSidebarHeader\"]{height:0!important;min-height:0!important;padding:0!important;margin:0!important;position:relative;z-index:3}\n[data-testid=\"stSidebarCollapseButton\"]{position:absolute!important;top:18px;right:14px;visibility:visible!important;opacity:1!important}\n[data-testid=\"stSidebar\"] button[aria-label=\"Collapse sidebar\"]{visibility:visible!important;opacity:1!important}\n[data-testid=\"stSidebarUserContent\"]{padding-top:20px!important}\n.pf-sbbrand .pf-brand{gap:12px;font-size:20px}\n.pf-sbbrand .pf-logo{transform:scale(1.3);transform-origin:left center;margin-right:9px}\n.pf-sbh{font:600 12px/1 Inter,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:#55555f;margin:22px 0 4px;\ndisplay:flex;gap:8px;align-items:center}\n.pf-sbh b{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:6px;background:#121216;color:#fff;font-size:11px;letter-spacing:0}\n[data-testid=\"stBaseButton-primary\"]{font-weight:600!important}\n[data-testid=\"stBaseButton-secondary\"],[data-testid=\"stDownloadButton\"] button{font-weight:600!important;background:#fff!important}\n[data-testid=\"stFileUploaderDropzone\"]{background:#fafaf8;border-radius:12px}\n.stTabs [data-baseweb=\"tab-list\"]{gap:4px;border-bottom:1px solid #e3e3de}\n.stTabs [data-baseweb=\"tab\"]{font-size:15px;font-weight:600;padding:12px 14px;height:auto}\n.pf-intro{max-width:760px}\n.pf-intro p{font-size:17px;color:var(--ink2);margin:12px 0 0}\n.pf-intro ol{margin:10px 0 0 20px!important;padding:0!important}.pf-intro ol li{margin:0 0 6px!important;font-size:16px;color:var(--ink2)}\n.pf-service{padding:12px 14px;background:#fafaf8;border:1px solid #e3e3de;border-radius:12px;font-size:14px;line-height:1.5}\n.pf-service .dot{display:inline-block;width:7px;height:7px;background:#33845b;border-radius:50%;margin-right:8px}\n.pf-review{max-width:900px;margin:24px auto;padding:30px;background:var(--surface);border:1px solid var(--line2);border-radius:16px}\n.pf-review-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:14px}\n.pf-review-heading h2{font-size:23px;line-height:1.4;font-weight:600;margin:0;display:flex;align-items:center;gap:12px}\n.pf-review-heading>span{font-size:13px;color:var(--mute);white-space:nowrap}\n.pf-review p{font-size:15px;line-height:1.6;color:var(--mute);margin:9px 0 24px}\n.pf-review-dot{width:8px;height:8px;border-radius:50%;background:var(--accent,#d6194a);animation:pf-breathe 1.6s ease-in-out infinite;flex-shrink:0}\n.pf-review-track{height:5px;background:var(--line);border-radius:999px;overflow:hidden}\n.pf-review-fill{height:100%;background:#d6194a;border-radius:999px;transition:width .25s ease}\n.pf-review-pulse{height:100%;width:30%;background:#d6194a;border-radius:999px;animation:pf-sweep 1.8s ease-in-out infinite}\n.pf-review-steps{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:25px}\n.pf-review-step{display:flex;align-items:center;gap:7px;color:var(--mute);font-size:12px;line-height:1.4}\n.pf-review-step span{display:inline-grid;place-items:center;flex-shrink:0;width:21px;height:21px;background:var(--surface2);border-radius:50%;font-size:11px}\n.pf-review-step.active{color:#b3133d;font-weight:600}.pf-review-step.active span{background:#fbe8ed}\n.pf-review-step.done span{color:#33845b;background:#e8f3ec}\n@keyframes pf-sweep{from{transform:translateX(-100%)}to{transform:translateX(430%)}}\n@keyframes pf-breathe{0%,100%{opacity:1}50%{opacity:.3}}\n@media(max-width:600px){.pf-review{padding:23px 20px}.pf-review-heading{align-items:flex-start;flex-direction:column;gap:8px}.pf-review-heading h2{font-size:21px}.pf-review-steps{grid-template-columns:repeat(2,1fr);gap:13px}}\n@media(prefers-reduced-motion:reduce){.pf-review-dot,.pf-review-pulse{animation:none}.pf-review-fill{transition:none}}\n/* Final visual polish: keep the existing controls and report views. */\n.block-container{max-width:1360px;padding-top:3.8rem}\n.pf{--line:#e6e5ea;--line2:#d7d5de;--surface2:#f6f5f8;--surface3:#ebe9ef;--shadow:0 2px 8px rgba(25,18,40,.035)}\n.pf-sbbrand{padding:0 0 17px;border-bottom:1px solid #eceaf0}\n.pf-sbbrand .pf-brand{font-size:21px;letter-spacing:-.6px;gap:11px}\n.pf-mascot{object-fit:contain;flex-shrink:0;display:block}\n.pf-mascot-brand{width:48px;height:54px}\n.pf-sbbrand p{line-height:1.65!important;max-width:240px}\n.pf-sbh{letter-spacing:.065em;font-size:11px;margin-top:25px;color:#60606b}\n.pf-sbh b{background:#f4edf1;color:#9d2347;border:1px solid #ecdde3;border-radius:7px}\n[data-testid=\"stFileUploaderDropzone\"]{border:1px dashed #d8d5df!important;background:#faf9fc!important;border-radius:14px!important;padding:18px 14px!important}\n[data-testid=\"stTextInput\"] input{font-size:14px!important}\n[data-testid=\"stTextInputRootElement\"],[data-baseweb=\"select\"]>div{border-color:#e2dfe8!important;border-radius:10px!important}\n[data-testid=\"stBaseButton-primary\"]{border-radius:10px!important;box-shadow:0 3px 8px rgba(214,25,74,.12);min-height:44px}\n[data-testid=\"stBaseButton-primary\"]:disabled{box-shadow:none}\n[data-testid=\"stBaseButton-secondary\"],[data-testid=\"stDownloadButton\"] button{border-color:#e0dde6!important;border-radius:10px!important;min-height:42px;transition:border-color .15s,box-shadow .15s}\n[data-testid=\"stDownloadButton\"] button:hover{border-color:#d394a7!important;box-shadow:0 2px 7px rgba(40,20,35,.045)}\n.pf-service{background:#fafafc;border-color:#e6e4eb;font-size:13px;padding:11px 13px;border-radius:10px}\n.pf-report-head{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:3px 0 17px}\n.pf-report-head h1{font-size:30px;letter-spacing:-.75px;margin:6px 0 12px}\n.pf-report-head .pf-label{font-size:11px;letter-spacing:.09em}\n.pf-mascot-mobile{display:none}\n.pf-mode{font-size:12px;border-radius:7px;padding:6px 10px}\n.pf-mode.ai{color:#59428a;background:#f1edf8}\n.pf-summary{border:1px solid #e6e4eb;border-radius:12px;background:#fff;padding:15px 18px;margin-bottom:4px;gap:9px 23px;font-size:13px;line-height:1.65}\n.pf-summary b{font-weight:600}\n.stTabs{margin-top:9px}\n.stTabs [data-baseweb=\"tab-list\"]{gap:0;border-bottom-color:#e6e3eb}\n.stTabs [data-baseweb=\"tab\"]{font-size:14px;font-weight:500;padding:12px 13px;white-space:nowrap}\n.pf-clist{border-color:#e4e1e9;border-radius:14px;box-shadow:0 2px 8px rgba(25,18,40,.035)}\n.pf-chead{background:#f8f7fa;font-size:11px;letter-spacing:.055em;padding-top:12px;padding-bottom:12px}\n.pf-crow>summary{padding-top:17px;padding-bottom:17px}\n.cr-hook{font-size:16px;line-height:1.6}\n.cr-cliff{line-height:1.65;font-size:13px}\n.cr-cuts{font-size:12px;color:#64616e}\n.cr-tags .pf-badge{font-size:11px;padding:5px 7px;border-radius:6px}\n.pf-rank.top{background:#24212a;border-color:#24212a}\n.pf-crow>summary:hover,.pf-crow[open]>summary{background:#fcfafd}\n.pf-review{box-shadow:0 3px 14px rgba(25,18,40,.035)}\n.pf-intro h1{letter-spacing:-.9px}\n.pf-intro-top{display:flex;align-items:center;justify-content:space-between;gap:25px;max-width:1000px;margin:0 auto}\n.pf-intro-top .pf-intro{max-width:740px}\n.pf-intro-top .pf-intro p{font-size:15px;line-height:1.75;margin-top:10px}\n.pf-mascot-welcome{width:80px;height:90px}\n@media(max-width:860px){.pf-report-head h1{font-size:26px;overflow-wrap:anywhere}.pf-mascot-mobile{display:block;width:52px;height:62px}.pf-summary{font-size:12px;padding:14px;gap:7px 18px}.stTabs [data-baseweb=\"tab\"]{font-size:13px;padding:11px 12px}.cr-hook{font-size:15px}.pf-mascot-welcome{width:64px;height:74px}.pf-intro-top{gap:15px}}\n@media(prefers-reduced-motion:reduce){[data-testid=\"stBaseButton-secondary\"],[data-testid=\"stDownloadButton\"] button{transition:none}}\n.block-container:has(.st-key-home_upload_panel){padding-top:2.8rem;padding-bottom:2.5rem}\n.st-key-home_upload_panel{max-width:1000px;margin:18px auto 0;background:#fff;border:1px solid #e4e0e9;border-radius:18px;padding:18px 25px;gap:10px!important;box-shadow:0 5px 22px rgba(30,20,40,.035)}\n.st-key-home_upload_panel [data-testid=\"stFileUploaderDropzone\"]{min-height:116px;padding:16px 18px!important;display:flex!important;flex-direction:column!important;align-items:center!important;justify-content:center!important;gap:12px!important;background:linear-gradient(125deg,#fff9fb,#faf8ff)!important;border-color:#d9c7d4!important;transition:border-color .15s,box-shadow .15s}\n.st-key-home_upload_panel [data-testid=\"stFileUploaderDropzone\"]>span{display:flex!important;justify-content:center!important;align-self:center!important;width:auto!important;margin:0!important}\n.st-key-home_upload_panel [data-testid=\"stFileUploaderDropzone\"] [data-testid=\"stFileUploaderDropzoneInstructions\"]{text-align:center!important;align-items:center!important;padding:0!important;width:auto!important}\n.st-key-home_upload_panel [data-testid=\"stFileUploaderDropzone\"] button{min-width:160px;min-height:44px;margin:0!important;background:#d6194a!important;border:1px solid #d6194a!important;color:#fff!important;box-shadow:0 3px 8px rgba(214,25,74,.13);font-size:14px!important}\n.st-key-home_upload_panel [data-testid=\"stFileUploaderDropzone\"] button:hover{background:#b61441!important;border-color:#b61441!important}\n.st-key-home_upload_panel [data-testid=\"stFileUploaderDropzone\"]:focus-within{border-color:#d6194a!important;box-shadow:0 0 0 3px #d6194a13}\n.pf-home-title{text-align:center;font-size:21px;font-weight:600;letter-spacing:-.4px;margin:0 0 5px}\n.pf-home-hint{text-align:center;font-size:13px;color:var(--mute);line-height:1.7;margin-bottom:2px!important}\n.st-key-home_upload_panel .st-key-find_home{max-width:260px;margin:0 auto;width:100%}\n.pf-start-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;max-width:1000px;margin:18px auto 0}\n.pf-start-step{display:grid;grid-template-columns:26px minmax(0,1fr);column-gap:10px;row-gap:4px;border:1px solid var(--line);border-radius:12px;padding:16px;background:var(--surface)}\n.pf-start-step .n{grid-row:1 / 3;display:inline-grid;place-items:center;width:25px;height:25px;border-radius:8px;background:var(--hook-bg);color:var(--hook);font-size:12px;font-weight:600;margin:0}\n.pf-start-step h3{grid-column:2;font-size:13px;font-weight:600;margin:0}.pf-start-step p{grid-column:2;font-size:12px;color:var(--mute);line-height:1.65}\n@media(max-width:600px){.st-key-home_upload_panel{padding:19px 17px;margin-top:19px}.pf-start-steps{grid-template-columns:1fr;gap:9px}.pf-start-step{padding:14px}.pf-home-title{font-size:19px}.st-key-home_upload_panel [data-testid=\"stFileUploaderDropzone\"]{min-height:130px;padding:20px 12px!important}}\n@media(prefers-reduced-motion:reduce){.st-key-home_upload_panel [data-testid=\"stFileUploaderDropzone\"]{transition:none}}\n/* === Approved Kuku Promo Finder reference layout === */\n@media(min-width:861px){\n  section[data-testid=\"stSidebar\"]{width:338px!important;min-width:338px!important;max-width:338px!important}\n  section[data-testid=\"stSidebar\"]>div{width:338px!important}\n  .main .block-container{max-width:none!important;width:100%!important;padding:34px 44px 48px!important}\n}\n.stApp,[data-testid=\"stAppViewContainer\"]{background:#FBF9F9!important}\n[data-testid=\"stAppViewContainer\"]{background-image:radial-gradient(ellipse at 96% 0%,rgba(245,190,196,.13),transparent 34%)!important}\n.pf{--hook:#E11D26;--hook-bg:#FDEBEC;--accent:#E11D26;--grad:linear-gradient(135deg,#D71920 0%,#9E0F15 100%)}\nsection[data-testid=\"stSidebar\"]{position:relative;overflow:hidden!important;background:linear-gradient(180deg,#0D0D0E 0%,#151516 100%)!important;border-right:1px solid #252528!important}\nsection[data-testid=\"stSidebar\"]::after{content:\"\";position:absolute;left:-36px;bottom:-25px;width:390px;height:145px;\n  background:linear-gradient(168deg,rgba(158,15,21,.04) 0%,rgba(215,25,32,.28) 65%,rgba(215,25,32,.16) 100%);\n  border-radius:58% 42% 0 0/48% 38% 0 0;transform:rotate(-4deg);pointer-events:none;z-index:0}\nsection[data-testid=\"stSidebar\"]>div{position:relative;z-index:1;padding:28px 24px 30px!important}\n[data-testid=\"stSidebarUserContent\"]{padding-top:0!important}\nsection[data-testid=\"stSidebar\"] [data-testid=\"stMarkdownContainer\"] p,\nsection[data-testid=\"stSidebar\"] [data-testid=\"stCaptionContainer\"] p{color:#B5B5BC!important}\n.pf-sidebar-brand{display:flex;align-items:center;gap:12px;margin:0 0 6px}\n.pf-sidebar-brand img{width:44px;height:44px;object-fit:contain;display:block;flex:0 0 44px}\n.pf-sidebar-brand b{font-size:24px;line-height:1.1;font-weight:700;letter-spacing:-.6px;color:#fff}\n.pf-sidebar-tagline{font-size:15px;line-height:1.55;color:#B5B5BC;margin:7px 0 26px!important;max-width:250px}\n.pf-sidebar-divider{height:1px;background:#2A2A2D;margin:24px 0}\n.pf-sidebar-nav-icon{width:24px;height:24px;display:flex;align-items:center;justify-content:center;color:#fff}\n.pf-sidebar-nav-icon svg{width:22px;height:22px;display:block}\nsection[data-testid=\"stSidebar\"] [data-testid=\"stHorizontalBlock\"]{gap:10px!important;align-items:center!important}\nsection[data-testid=\"stSidebar\"] .st-key-nav_home,\nsection[data-testid=\"stSidebar\"] .st-key-nav_how{width:100%}\nsection[data-testid=\"stSidebar\"] .st-key-nav_home button,\nsection[data-testid=\"stSidebar\"] .st-key-nav_how button{\n  width:100%!important;height:56px!important;min-height:56px!important;border-radius:12px!important;\n  justify-content:flex-start!important;text-align:left!important;padding:0 16px!important;\n  font-size:16px!important;font-weight:600!important;box-shadow:none!important\n}\nsection[data-testid=\"stSidebar\"] .st-key-nav_home button[kind=\"primary\"],\nsection[data-testid=\"stSidebar\"] .st-key-nav_how button[kind=\"primary\"],\nsection[data-testid=\"stSidebar\"] [data-testid=\"stBaseButton-primary\"]{\n  color:#fff!important;background:linear-gradient(100deg,#D71920 0%,#9E0F15 100%)!important;border:1px solid #D71920!important\n}\nsection[data-testid=\"stSidebar\"] .st-key-nav_home button[kind=\"secondary\"],\nsection[data-testid=\"stSidebar\"] .st-key-nav_how button[kind=\"secondary\"],\nsection[data-testid=\"stSidebar\"] [data-testid=\"stBaseButton-secondary\"]{\n  color:#fff!important;background:transparent!important;border:1px solid transparent!important\n}\nsection[data-testid=\"stSidebar\"] .st-key-nav_home button[kind=\"secondary\"]:hover,\nsection[data-testid=\"stSidebar\"] .st-key-nav_how button[kind=\"secondary\"]:hover{background:#1F1F21!important;border-color:#2A2A2D!important}\n.pf-sidebar-status{display:flex;align-items:center;gap:11px;padding:17px 16px;background:#161618;border:1px solid #232326;\n  border-radius:14px;color:#fff;font-size:16px;font-weight:600;margin:0 0 28px}\n.pf-sidebar-status .dot{width:12px;height:12px;flex:0 0 12px;border-radius:50%;background:#22C55E;\n  box-shadow:0 0 0 4px rgba(34,197,94,.12),0 0 12px rgba(34,197,94,.55)}\n.pf-quickstats{padding:20px;background:#161618;border:1px solid #232326;border-radius:18px;margin:0}\n.pf-quickstats h4{font-size:18px;font-weight:700;color:#fff;margin:0 0 16px}\n.pf-quickstat{display:flex;align-items:center;gap:14px;margin:13px 0 0;color:#fff}\n.pf-quickstat .ico{width:48px;height:48px;min-width:48px;display:grid;place-items:center;border-radius:12px;background:#2A1213;color:#E11D26}\n.pf-quickstat .ico svg{width:24px;height:24px;display:block}\n.pf-quickstat b{display:block;font-size:18px;line-height:1.2;color:#fff;font-weight:700}\n.pf-quickstat small{display:block;font-size:14px;line-height:1.35;color:#B5B5BC;margin-top:3px}\nsection[data-testid=\"stSidebar\"] .pf-service{display:flex;align-items:center;gap:11px;padding:17px 16px;background:#161618;\n  border:1px solid #232326;border-radius:14px;color:#fff;font-size:16px;font-weight:600;margin:0 0 26px}\nsection[data-testid=\"stSidebar\"] .pf-service .dot{width:12px;height:12px;border-radius:50%;background:#22C55E;\n  box-shadow:0 0 0 4px rgba(34,197,94,.12),0 0 12px rgba(34,197,94,.55);margin:0}\nsection[data-testid=\"stSidebar\"] .st-key-sidebar_new_analysis{margin-top:18px}\nsection[data-testid=\"stSidebar\"] .st-key-sidebar_new_analysis button{width:100%;height:46px;border-radius:10px!important;\n  border:1px solid #39393E!important;background:#202024!important;color:#fff!important}\nsection[data-testid=\"stSidebar\"] [data-testid=\"stAlert\"]{background:#1d1d20!important;color:#fff!important;border:1px solid #343439!important}\n.pf-home-hero{position:relative;display:flex;align-items:center;justify-content:space-between;gap:22px;min-height:155px;margin:0 0 12px;overflow:visible}\n.pf-home-hero-copy{position:relative;z-index:2;max-width:810px}\n.pf-home-eyebrow{font-size:15px;line-height:1.2;font-weight:700;letter-spacing:.5px;color:#E11D26;text-transform:uppercase}\n.pf-home-hero h1{font-size:clamp(48px,4.1vw,64px);line-height:1.05;letter-spacing:-1.9px;font-weight:750;color:#1A1A1C;margin:12px 0 13px}\n.pf-home-hero h1 span{display:block;color:#E11D26}\n.pf-home-hero p{font-size:20px;line-height:1.5;color:#5B5B63;margin:0;max-width:810px}\n.pf-home-art{position:relative;width:300px;min-width:250px;height:190px;display:flex;align-items:center;justify-content:center}\n.pf-home-art .pf-mascot-welcome{position:relative;z-index:2;width:188px;height:188px;object-fit:contain;transform:rotate(4deg)}\n.pf-film-ribbon{position:absolute;inset:0;width:100%;height:100%;opacity:.25;pointer-events:none;z-index:1}\n.pf-home-spark{position:absolute;z-index:3;top:14px;right:15px;width:48px;height:48px;color:#E11D26;pointer-events:none}\n.pf-feature-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));margin:8px 0 30px}\n.pf-feature{display:flex;align-items:center;gap:14px;padding:6px 24px;border-right:1px solid #E5E5E8;min-width:0}\n.pf-feature:first-child{padding-left:0}\n.pf-feature:last-child{border:0;padding-right:0}\n.pf-feature-icon{width:48px;height:48px;min-width:48px;display:grid;place-items:center;border-radius:13px;background:#FDEBEC;color:#E11D26}\n.pf-feature-icon svg{width:25px;height:25px;display:block}\n.pf-feature b{display:block;font-size:17px;line-height:1.3;font-weight:650;color:#1A1A1C}\n.pf-feature small{display:block;font-size:15px;line-height:1.4;color:#5B5B63;margin-top:3px}\n.st-key-home_upload_panel{max-width:100%!important;width:100%;margin:0!important;padding:24px!important;background:#fff!important;\n  border:1px solid #F0E6E7!important;border-radius:20px!important;box-shadow:0 8px 24px rgba(20,0,0,.06)!important;gap:0!important}\n.st-key-upload_zone{position:relative!important;width:100%;min-height:250px!important;margin:0 0 16px!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"]{\n  position:relative!important;min-height:250px!important;height:250px!important;width:100%!important;\n  display:flex!important;align-items:center!important;justify-content:center!important;\n  background:#FFF5F5!important;border:1px dashed #F1B7BB!important;border-radius:16px!important;\n  padding:10px!important;overflow:hidden!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"]:hover{border-color:#E11D26!important;background:#FFF3F3!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"]{position:absolute!important;inset:0!important;\n  padding:0!important;color:transparent!important;font-size:0!important;pointer-events:none!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] p{display:none!important}\n.st-key-upload_zone [data-testid=\"stElementContainer\"]:has(.pf-dropzone-overlay){\n  position:absolute!important;inset:0!important;height:250px!important;z-index:3!important;pointer-events:none!important}\n.pf-dropzone-overlay{position:absolute;inset:0;text-align:center;pointer-events:none;color:#1A1A1C}\n.pf-dropzone-overlay .cloud{position:absolute;left:0;right:0;top:10px;display:flex;justify-content:center;color:#E11D26}\n.pf-dropzone-overlay .cloud svg{width:56px;height:56px;display:block}\n.pf-dropzone-overlay h2{position:absolute;left:8px;right:8px;top:69px;font-size:27px;line-height:1.25;font-weight:700;\n  letter-spacing:-.55px;color:#1A1A1C;margin:0}\n.pf-dropzone-overlay p{position:absolute;left:8px;right:8px;top:116px;font-size:16px;line-height:1.4;color:#5B5B63;margin:0}\n.pf-inline-link{color:#E11D26;text-decoration:underline;text-underline-offset:2px;font-weight:600}\n.pf-dropzone-overlay .limit{position:absolute;left:0;right:0;bottom:13px;font-size:15px;line-height:1.2;color:#5B5B63}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] button{\n  opacity:1!important;visibility:visible!important;pointer-events:auto!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"] button{\n  position:absolute!important;left:50%!important;bottom:42px!important;transform:translateX(-50%)!important;\n  width:260px!important;max-width:calc(100% - 32px)!important;height:56px!important;min-height:56px!important;\n  margin:0!important;padding:0 18px!important;border:1px solid #E11D26!important;border-radius:14px!important;\n  background:#E11D26!important;color:#fff!important;font-size:0!important;font-weight:700!important;\n  box-shadow:0 5px 14px rgba(225,29,38,.20)!important;pointer-events:auto!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"] button:hover{background:#C8141D!important;border-color:#C8141D!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"] button::before{\n  content:\"\";display:inline-block;width:21px;height:21px;margin-right:9px;vertical-align:middle;background-repeat:no-repeat;\n  background-position:center;background-size:21px 21px;\n  background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23fff' stroke-width='1.9' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 16V4m-5 5 5-5 5 5'/%3E%3Cpath d='M20 16.5v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2'/%3E%3C/svg%3E\")}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"] button::after{content:\"Choose Files\";font-size:18px;line-height:1}\n.pf-upload-error{display:flex;gap:8px;align-items:flex-start;padding:10px 13px;margin:8px 0 12px;\n  border:1px solid #F3B7BA;background:#FFF1F1;border-radius:10px;color:#B4232A;font-size:13px;line-height:1.5}\n.pf-upload-error svg{flex:0 0 auto;color:#B4232A;margin-top:1px}\n.st-key-upload_zone [data-testid=\"stAlert\"]{border:1px solid #F3B7BA!important;background:#FFF1F1!important;color:#B4232A!important;border-radius:10px!important}\n.st-key-upload_zone [data-testid=\"stAlert\"] p{color:#B4232A!important;font-size:13px!important}\n.pf-ready-files{font-size:13px;color:#4F5964;margin:-5px 0 12px;line-height:1.5}\n.pf-action-row{display:grid;grid-template-columns:116px 1px minmax(180px,1fr) 200px;gap:16px;align-items:center;margin-top:0}\n.pf-action-label{font-size:17px;font-weight:700;color:#1A1A1C;white-space:nowrap}\n.pf-action-divider{height:42px;background:#E5E5E8;width:1px}\n.st-key-home_title input{height:56px!important;min-height:56px!important;border:1px solid #E3E3E7!important;border-radius:14px!important;\n  background-color:#fff!important;background-repeat:no-repeat!important;background-position:15px center!important;background-size:22px 22px!important;\n  padding-left:48px!important;font-size:16px!important;color:#1A1A1C!important}\n.st-key-home_title input{background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%235B5B63' stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 8.5h16v11H4z'/%3E%3Cpath d='M4 8.5 6.5 4H22l-2.5 4.5M8 4l-2 4.5M14 4l-2 4.5m7-4.5-2 4.5'/%3E%3Ccircle cx='9' cy='14' r='1.3'/><path d='m12 18 3-2 2 2'/></svg>\")!important}\n.st-key-home_title [data-testid=\"stTextInputRootElement\"]{border:0!important;box-shadow:none!important}\n.st-key-home_title [data-testid=\"stTextInputRootElement\"] input:focus{border-color:#E11D26!important;box-shadow:0 0 0 3px rgba(225,29,38,.10)!important}\n.st-key-find_home{width:200px}\n.st-key-find_home button{height:56px!important;min-height:56px!important;width:200px!important;border-radius:14px!important;font-size:18px!important;font-weight:700!important}\n.st-key-find_home button::before{content:\"\";display:inline-block;width:19px;height:19px;margin-right:10px;vertical-align:middle;background-repeat:no-repeat;\n  background-position:center;background-size:19px 19px;background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='white'%3E%3Cpath d='m8 5 12 7-12 7z'/%3E%3C/svg%3E\")}\n.st-key-find_home button:disabled{background:#E5E5E8!important;border-color:#E5E5E8!important;color:#8A8A92!important;cursor:not-allowed!important;box-shadow:none!important}\n.st-key-find_home button:disabled::before{opacity:.35}\n.pf-start-steps{display:grid;grid-template-columns:minmax(0,1fr) 28px minmax(0,1fr) 28px minmax(0,1fr);\n  gap:12px;max-width:100%;margin:22px auto 0;align-items:center}\n.pf-start-step{position:relative;display:grid;grid-template-columns:48px minmax(0,1fr);column-gap:14px;row-gap:4px;align-items:center;\n  border:1px solid #F0E6E7;border-radius:16px;padding:18px 17px;background:#fff;min-height:116px;\n  box-shadow:0 5px 16px rgba(20,0,0,.035)}\n.pf-start-step .n{position:absolute;top:12px;left:12px;display:grid;place-items:center;width:25px;height:25px;\n  border-radius:50%;background:#FDEBEC;color:#E11D26;font-size:13px;font-weight:700}\n.pf-start-step .step-icon{grid-row:1 / 3;display:grid;place-items:center;width:48px;height:48px;margin-left:18px;\n  border-radius:12px;background:#FDEBEC;color:#E11D26}\n.pf-start-step .step-icon svg{width:25px;height:25px;display:block}\n.pf-start-step h3{grid-column:2;font-size:16px;font-weight:700;color:#1A1A1C;margin:0}\n.pf-start-step p{grid-column:2;font-size:14px;line-height:1.5;color:#5B5B63;margin:0}\n.pf-step-arrow{font-size:26px;color:#E11D26;text-align:center;font-weight:400}\n.pf-how-grid{grid-template-columns:repeat(2,minmax(0,1fr))}\n@media(max-width:1100px){\n  .pf-home-hero h1{font-size:48px}\n  .pf-home-art{width:220px;min-width:180px}\n  .pf-home-art .pf-mascot-welcome{width:150px;height:150px}\n  .pf-action-row{grid-template-columns:105px 1px minmax(120px,1fr) 180px;gap:10px}\n  .st-key-find_home,.st-key-find_home button{width:180px!important}\n  .pf-start-step{padding:16px 12px;grid-template-columns:42px minmax(0,1fr)}\n}\n@media(max-width:860px){\n  .main .block-container{padding:28px 24px 40px!important}\n  section[data-testid=\"stSidebar\"]{width:300px!important;min-width:300px!important}\n  .pf-home-hero{min-height:0}\n  .pf-home-hero h1{font-size:42px}\n  .pf-home-hero p{font-size:17px}\n  .pf-home-art{width:130px;min-width:110px;height:130px}\n  .pf-home-art .pf-mascot-welcome{width:115px;height:115px}\n  .pf-feature-row{grid-template-columns:1fr;gap:10px;margin-bottom:22px}\n  .pf-feature{padding:4px 0;border:0}\n  .pf-start-steps{grid-template-columns:1fr;gap:8px}\n  .pf-step-arrow{display:none}\n  .pf-action-row{grid-template-columns:1fr;gap:8px}\n  .pf-action-divider{display:none}\n  .pf-action-label{font-size:15px}\n  .st-key-find_home,.st-key-find_home button{width:100%!important}\n}\n@media(max-width:600px){\n  .main .block-container{padding:22px 16px 32px!important}\n  .pf-home-hero h1{font-size:34px;letter-spacing:-1px}\n  .pf-home-hero p{font-size:15px}\n  .pf-home-art{width:84px;min-width:76px;height:90px}\n  .pf-home-art .pf-mascot-welcome{width:86px;height:86px}\n  .st-key-home_upload_panel{padding:16px!important}\n  .pf-dropzone-overlay h2{font-size:21px}\n  .pf-dropzone-overlay p{font-size:13px}\n  .st-key-upload_zone,.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"]{min-height:230px!important;height:230px!important}\n  .pf-dropzone-overlay .limit{bottom:10px}\n  .st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"] button{width:220px!important;height:50px!important;min-height:50px!important;bottom:42px!important}\n}\n\n</style>", unsafe_allow_html=True)
st.html("""<style>
/* Final scoped uploader and viewport sizing overrides. */
.main .block-container{padding-top:1.25rem!important;padding-bottom:1.4rem!important}
.st-key-home_upload_panel{max-width:100%!important;width:100%!important;padding:22px!important;background:#FFFFFF!important;border:1px solid #F0E6E7!important;border-radius:20px!important;box-shadow:0 8px 24px rgba(20,0,0,.06)!important}
.st-key-upload_zone [data-testid="stFileUploaderDropzone"]{min-height:205px!important;height:205px!important;display:flex!important;align-items:center!important;justify-content:center!important;background:#FFF5F5!important;border:1px dashed #F1B7BB!important;border-radius:16px!important;padding:14px!important}
.st-key-upload_zone [data-testid="stFileUploaderDropzoneInstructions"] p,
.st-key-upload_zone [data-testid="stFileUploaderDropzoneInstructions"] span{display:none!important}
.st-key-upload_zone [data-testid="stFileUploaderDropzone"] button{width:250px!important;height:56px!important;min-height:56px!important;border-radius:14px!important;background:#E11D26!important;border:1px solid #E11D26!important;color:transparent!important;font-size:0!important;text-indent:-9999px!important;box-shadow:0 5px 14px rgba(225,29,38,.18)!important;position:relative!important;left:auto!important;bottom:auto!important;transform:none!important;margin:0!important;overflow:hidden!important}
.st-key-upload_zone [data-testid="stFileUploaderDropzone"] button *{display:none!important;visibility:hidden!important;opacity:0!important}
.st-key-upload_zone [data-testid="stFileUploaderDropzone"] button::before{content:"↑";display:block!important;position:absolute;left:42px;top:50%;transform:translateY(-52%);font-size:24px!important;font-weight:500!important;color:#FFFFFF!important;text-indent:0!important}
.st-key-upload_zone [data-testid="stFileUploaderDropzone"] button::after{content:"Choose Files";display:flex!important;position:absolute;inset:0;align-items:center;justify-content:center;text-indent:0!important;color:#FFFFFF!important;font-size:18px!important;font-weight:700!important;padding-left:24px}
.st-key-upload_zone [data-testid="stFileUploaderDropzone"] button:hover{background:#C8141D!important;border-color:#C8141D!important}
.st-key-find_home button{height:56px!important;min-height:56px!important;border-radius:14px!important;background:#E11D26!important;color:#FFFFFF!important;font-size:18px!important;font-weight:700!important}
.st-key-find_home button:disabled{background:#E5E5E8!important;border-color:#E5E5E8!important;color:#8A8A92!important}
.st-key-home_title input{height:56px!important;border:1px solid #E3E3E7!important;border-radius:14px!important;font-size:16px!important}
section[data-testid="stSidebar"] .st-key-nav_home button,
section[data-testid="stSidebar"] .st-key-nav_how button{color:#FFFFFF!important;text-align:left!important;justify-content:flex-start!important;padding-left:18px!important}
@media(max-width:1050px){.main .block-container{padding-left:22px!important;padding-right:22px!important}}
</style>""")


st.markdown("<style>\n/* Final overrides appended after all base styles. */\n@media(min-width:861px){.main .block-container{max-width:1392px!important;padding:28px 54px 38px!important}}\nsection[data-testid=\"stSidebar\"] .st-key-nav_home [data-testid^=\"stBaseButton\"],\nsection[data-testid=\"stSidebar\"] .st-key-nav_how [data-testid^=\"stBaseButton\"]{\n  width:100%!important;height:54px!important;min-height:54px!important;display:flex!important;\n  align-items:center!important;justify-content:flex-start!important;gap:12px!important;\n  text-align:left!important;padding:0 18px!important;border-radius:12px!important;\n  color:#FFFFFF!important;font-family:Inter,system-ui,sans-serif!important;font-size:16px!important;font-weight:600!important;\n  line-height:1.2!important;box-shadow:none!important\n}\nsection[data-testid=\"stSidebar\"] .st-key-nav_home [data-testid=\"stBaseButton-primary\"],\nsection[data-testid=\"stSidebar\"] .st-key-nav_how [data-testid=\"stBaseButton-primary\"]{\n  background:linear-gradient(105deg,#D71920 0%,#9E0F15 100%)!important;border:1px solid #D71920!important;color:#FFFFFF!important\n}\nsection[data-testid=\"stSidebar\"] .st-key-nav_home [data-testid=\"stBaseButton-secondary\"],\nsection[data-testid=\"stSidebar\"] .st-key-nav_how [data-testid=\"stBaseButton-secondary\"]{\n  background:#171719!important;border:1px solid #303034!important;color:#FFFFFF!important\n}\nsection[data-testid=\"stSidebar\"] .st-key-nav_home [data-testid=\"stBaseButton-secondary\"]:hover,\nsection[data-testid=\"stSidebar\"] .st-key-nav_how [data-testid=\"stBaseButton-secondary\"]:hover{\n  background:#242427!important;border-color:#48484D!important\n}\nsection[data-testid=\"stSidebar\"] .st-key-nav_home button span,\nsection[data-testid=\"stSidebar\"] .st-key-nav_how button span{color:#FFFFFF!important}\nsection[data-testid=\"stSidebar\"] .st-key-nav_home button svg,\nsection[data-testid=\"stSidebar\"] .st-key-nav_how button svg{width:20px!important;height:20px!important;min-width:20px!important}\n.pf-feature-row{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;width:100%!important;gap:0!important;margin:7px 0 20px!important}\n.pf-feature{display:flex!important;align-items:center!important;gap:12px!important;min-width:0!important;padding:7px 16px!important}\n.pf-feature-icon{width:46px!important;height:46px!important;min-width:46px!important;flex:0 0 46px!important;display:flex!important;align-items:center!important;justify-content:center!important;background:#FDEBEC!important;border-radius:12px!important;color:#E11D26!important}\n.pf-feature-icon svg{display:block!important;width:24px!important;height:24px!important;stroke:#E11D26!important}\n.pf-feature b{display:block!important;font-size:16px!important;line-height:1.25!important;font-weight:700!important;color:#1A1A1C!important;white-space:normal!important}\n.pf-feature small{display:block!important;font-size:14px!important;line-height:1.35!important;color:#5B5B63!important;white-space:normal!important}\n.st-key-home_upload_panel{padding:20px 22px 17px!important;margin:0!important;gap:0!important}\n.st-key-upload_zone{height:auto!important;min-height:0!important;padding:0!important;margin:0!important}\n.st-key-upload_zone [data-testid=\"stFileUploader\"]{height:auto!important;min-height:0!important;padding:0!important;margin:0!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"]{height:170px!important;min-height:170px!important;max-height:170px!important;margin:0!important;padding:10px!important;box-sizing:border-box!important;display:flex!important;align-items:center!important;justify-content:center!important}\n.st-key-home_upload_panel [data-testid=\"stVerticalBlock\"]{gap:8px!important}\n.st-key-home_upload_panel > div{margin-bottom:0!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"] button{width:230px!important;height:50px!important;min-height:50px!important;margin:0 auto!important;position:relative!important;inset:auto!important;transform:none!important;border-radius:13px!important;background:#E11D26!important;border:1px solid #E11D26!important;color:#FFFFFF!important;box-shadow:0 4px 12px rgba(225,29,38,.16)!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"] button::before{font-size:21px!important;margin-right:9px!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"] button::after{font-size:17px!important}\n.st-key-home_upload_panel .st-key-home_title input{height:54px!important;min-height:54px!important;border:1px solid #E3E3E7!important;border-radius:13px!important}\n.st-key-home_upload_panel .st-key-find_home button{height:54px!important;min-height:54px!important;border-radius:13px!important;background:#E11D26!important;color:#FFFFFF!important;font-size:17px!important;font-weight:700!important}\n.st-key-home_upload_panel .st-key-find_home button:disabled{background:#E5E5E8!important;border-color:#E5E5E8!important;color:#8A8A92!important;box-shadow:none!important}\n@media(max-width:1100px){.pf-feature{padding:6px 9px!important}.pf-feature b{font-size:15px!important}.pf-feature small{font-size:13px!important}}\n@media(max-width:850px){.pf-feature-row{grid-template-columns:1fr!important;gap:7px!important}.pf-feature{border-right:0!important;padding:5px 0!important}}\n</style>", unsafe_allow_html=True)


st.markdown("<style>\n.st-key-upload_zone{position:relative!important;height:190px!important;min-height:190px!important;margin:0!important;padding:0!important}\n.st-key-upload_zone [data-testid=\"stFileUploader\"]{height:190px!important;min-height:190px!important;margin:0!important;padding:0!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"]{height:190px!important;min-height:190px!important;max-height:190px!important;padding-bottom:42px!important}\n.st-key-upload_zone [data-testid=\"stElementContainer\"]:has(.pf-upload-limit){position:absolute!important;left:0!important;right:0!important;bottom:8px!important;z-index:6!important;pointer-events:none!important}\n.pf-upload-limit{font-family:Inter,system-ui,sans-serif!important;font-size:14px!important;line-height:18px!important;text-align:center!important;color:#5B5B63!important;margin:0!important;padding:0!important}\n.st-key-home_upload_panel{padding-bottom:16px!important}\n</style>", unsafe_allow_html=True)


st.markdown("<style>\n/* A single real uploader action button; no pseudo-button duplicates. */\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"] > button,\n.st-key-upload_zone_compact [data-testid=\"stFileUploaderDropzone\"] > button{display:none!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"],\n.st-key-upload_zone_compact [data-testid=\"stFileUploaderDropzoneInstructions\"]{\n  position:static!important;inset:auto!important;display:flex!important;align-items:center!important;\n  justify-content:center!important;width:100%!important;height:100%!important;min-height:0!important;\n  padding:0!important;margin:0!important;opacity:1!important;pointer-events:auto!important;overflow:visible!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] p,\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] span,\n.st-key-upload_zone_compact [data-testid=\"stFileUploaderDropzoneInstructions\"] p,\n.st-key-upload_zone_compact [data-testid=\"stFileUploaderDropzoneInstructions\"] span{display:none!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] button,\n.st-key-upload_zone_compact [data-testid=\"stFileUploaderDropzoneInstructions\"] button{\n  display:flex!important;align-items:center!important;justify-content:center!important;\n  position:relative!important;inset:auto!important;transform:none!important;left:auto!important;bottom:auto!important;\n  width:240px!important;height:54px!important;min-height:54px!important;margin:0 auto!important;padding:0 18px!important;\n  border:1px solid #E11D26!important;border-radius:14px!important;background:#E11D26!important;color:#FFFFFF!important;\n  font-size:17px!important;font-weight:700!important;text-indent:0!important;box-shadow:0 4px 12px rgba(225,29,38,.17)!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] button::before,\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] button::after,\n.st-key-upload_zone_compact [data-testid=\"stFileUploaderDropzoneInstructions\"] button::before,\n.st-key-upload_zone_compact [data-testid=\"stFileUploaderDropzoneInstructions\"] button::after{content:none!important;display:none!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] button:hover,\n.st-key-upload_zone_compact [data-testid=\"stFileUploaderDropzoneInstructions\"] button:hover{background:#C8141D!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"]{\n  min-height:180px!important;height:180px!important;max-height:180px!important;\n  display:flex!important;align-items:center!important;justify-content:center!important;\n  padding:10px!important;background:#FFF5F5!important;border:1px dashed #F1B7BB!important;border-radius:16px!important\n}\n.st-key-upload_zone_compact{min-height:108px!important;padding:12px!important;border:1px dashed #F1B7BB!important;\n  border-radius:16px!important;background:#FFF5F5!important}\n.st-key-upload_zone_compact [data-testid=\"stFileUploaderDropzone\"]{\n  height:78px!important;min-height:78px!important;max-height:78px!important;\n  display:flex!important;align-items:center!important;justify-content:center!important;\n  border:0!important;background:transparent!important;padding:0!important\n}\n.st-key-upload_zone_compact [data-testid=\"stFileUploaderDropzoneInstructions\"] button{width:220px!important;height:52px!important;min-height:52px!important}\n.st-key-upload_zone_compact [data-testid=\"stFileUploaderFile\"],\n.st-key-upload_zone_compact [data-testid=\"stFileUploaderFileName\"],\n.st-key-upload_zone_compact .stFileUploaderFile{display:none!important}\n.st-key-upload_zone_compact [data-testid=\"stFileUploaderDropzoneInstructions\"]{height:auto!important}\n</style>", unsafe_allow_html=True)


st.markdown("<style>\n/* Requested final refinements: visible limit text below one button, and crisp feature icons. */\n.st-key-upload_zone{position:relative!important;height:124px!important;min-height:124px!important;margin:0!important;padding:0!important}\n.st-key-upload_zone [data-testid=\"stFileUploader\"],\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"]{\n  position:relative!important;width:100%!important;height:124px!important;min-height:124px!important;\n  max-height:124px!important;box-sizing:border-box!important;margin:0!important;padding:0!important;\n  background:#FFF5F5!important;border:1px dashed #F1B7BB!important;border-radius:16px!important;\n  display:block!important;overflow:hidden!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"]{\n  position:absolute!important;inset:0!important;width:100%!important;height:124px!important;min-height:124px!important;\n  display:block!important;padding:0!important;margin:0!important;opacity:1!important;pointer-events:auto!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] p,\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] span{display:none!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] button{\n  position:absolute!important;top:18px!important;left:50%!important;right:auto!important;bottom:auto!important;\n  transform:translateX(-50%)!important;width:240px!important;height:52px!important;min-height:52px!important;\n  margin:0!important;padding:0 18px!important;display:flex!important;align-items:center!important;justify-content:center!important;\n  border:1px solid #E11D26!important;border-radius:13px!important;background:#E11D26!important;color:#FFFFFF!important;\n  font-size:17px!important;font-weight:700!important;text-indent:0!important;box-shadow:0 4px 12px rgba(225,29,38,.16)!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] button::before,\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] button::after{content:none!important;display:none!important}\n.st-key-upload_zone [data-testid=\"stElementContainer\"]:has(.pf-upload-limit){\n  position:absolute!important;top:82px!important;left:0!important;right:0!important;bottom:auto!important;\n  width:100%!important;height:20px!important;margin:0!important;padding:0!important;\n  z-index:5!important;pointer-events:none!important\n}\n.pf-upload-limit{\n  display:block!important;width:100%!important;margin:0!important;padding:0!important;\n  text-align:center!important;color:#5B5B63!important;font-family:Inter,system-ui,sans-serif!important;\n  font-size:14px!important;line-height:20px!important;white-space:nowrap!important\n}\n.pf-feature{display:flex!important;align-items:center!important;gap:13px!important;min-width:0!important}\n.pf-feature-icon{\n  width:46px!important;height:46px!important;min-width:46px!important;flex:0 0 46px!important;\n  display:flex!important;align-items:center!important;justify-content:center!important;\n  background:#FDEBEC!important;border-radius:12px!important;color:#E11D26!important\n}\n.pf-feature-icon svg{\n  display:block!important;width:24px!important;height:24px!important;min-width:24px!important;\n  stroke:#E11D26!important;stroke-width:1.9!important;fill:none!important\n}\n.pf-feature b{display:block!important;color:#1A1A1C!important;font-size:16px!important;line-height:1.25!important}\n.pf-feature small{display:block!important;color:#5B5B63!important;font-size:14px!important;line-height:1.35!important}\n</style>", unsafe_allow_html=True)

st.markdown("<style>\n/* Final focused fix: vertically centered file picker, size note immediately below. */\n.st-key-upload_zone{\n  position:relative!important;display:flex!important;flex-direction:column!important;align-items:stretch!important;\n  justify-content:flex-start!important;gap:2px!important;width:100%!important;height:auto!important;min-height:0!important;\n  box-sizing:border-box!important;margin:0!important;padding:9px 14px 8px!important;\n  border:1px dashed #F1B7BB!important;border-radius:16px!important;background:#FFF5F5!important;overflow:visible!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploader\"]{\n  display:block!important;width:100%!important;height:auto!important;min-height:0!important;\n  margin:0!important;padding:0!important;background:transparent!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzone\"]{\n  position:relative!important;display:flex!important;align-items:center!important;justify-content:center!important;\n  width:100%!important;height:64px!important;min-height:64px!important;max-height:64px!important;\n  margin:0!important;padding:0!important;box-sizing:border-box!important;\n  border:0!important;border-radius:0!important;background:transparent!important;overflow:visible!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"]{\n  position:static!important;inset:auto!important;display:flex!important;align-items:center!important;justify-content:center!important;\n  width:100%!important;height:64px!important;min-height:64px!important;margin:0!important;padding:0!important;\n  opacity:1!important;overflow:visible!important;pointer-events:auto!important;background:transparent!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] p,\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] span{display:none!important}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] button{\n  position:relative!important;top:auto!important;right:auto!important;bottom:auto!important;left:auto!important;\n  transform:none!important;display:flex!important;align-items:center!important;justify-content:center!important;\n  width:240px!important;height:50px!important;min-height:50px!important;margin:0 auto!important;padding:0 18px!important;\n  box-sizing:border-box!important;border:1px solid #E11D26!important;border-radius:13px!important;\n  background:#E11D26!important;color:transparent!important;font-size:0!important;text-indent:-9999px!important;\n  box-shadow:0 4px 12px rgba(225,29,38,.16)!important;overflow:hidden!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] button *{\n  display:none!important;visibility:hidden!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] button::before{\n  content:\"↑\";position:absolute!important;left:58px!important;top:50%!important;transform:translateY(-52%)!important;\n  display:block!important;color:#FFFFFF!important;font-size:23px!important;line-height:1!important;text-indent:0!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] button::after{\n  content:\"Choose Files\";position:absolute!important;inset:0!important;display:flex!important;align-items:center!important;\n  justify-content:center!important;padding-left:26px!important;color:#FFFFFF!important;font-size:17px!important;\n  font-weight:700!important;line-height:1!important;text-indent:0!important\n}\n.st-key-upload_zone [data-testid=\"stFileUploaderDropzoneInstructions\"] button:hover{\n  background:#C8141D!important;border-color:#C8141D!important\n}\n.st-key-upload_zone [data-testid=\"stElementContainer\"]:has(.pf-upload-limit){\n  position:static!important;display:block!important;width:100%!important;height:auto!important;min-height:0!important;\n  margin:0!important;padding:0!important;inset:auto!important;z-index:auto!important;pointer-events:none!important\n}\n.pf-upload-limit{\n  display:block!important;position:static!important;width:100%!important;height:auto!important;min-height:18px!important;\n  margin:0!important;padding:0!important;text-align:center!important;white-space:nowrap!important;\n  color:#5B5B63!important;font-family:Inter,system-ui,sans-serif!important;font-size:14px!important;line-height:18px!important\n}\n.pf-feature-icon svg{display:block!important;width:24px!important;height:24px!important;min-width:24px!important}\n</style>", unsafe_allow_html=True)

st.markdown("""<style>
/* ===== HOME SCREEN FIX (scoped to Home only; keep this block LAST) ===== */

/* 1) Remove the blank band above the hero */
[data-testid="stMainBlockContainer"]:has(.st-key-home_upload_panel),
.main .block-container:has(.st-key-home_upload_panel){
  padding-top:14px!important;
}
[data-testid="stMainBlockContainer"]:has(.st-key-home_upload_panel) [data-testid="stElementContainer"]:has(style),
[data-testid="stMainBlockContainer"]:has(.st-key-home_upload_panel) [data-testid="stElementContainer"]:empty,
.block-container:has(.st-key-home_upload_panel) [data-testid="stElementContainer"]:has(style){
  display:none!important;
}

/* 2) Find Promos: fill its column, icon + label centered together */
.st-key-home_upload_panel .st-key-find_home{width:100%!important;max-width:none!important}
.st-key-home_upload_panel .st-key-find_home button{
  width:100%!important;height:56px!important;min-height:56px!important;
  display:inline-flex!important;align-items:center!important;justify-content:center!important;
  gap:10px!important;padding:0 18px!important;border-radius:14px!important;
  font-size:18px!important;font-weight:800!important;letter-spacing:.2px;
  background:linear-gradient(135deg,#F2272F 0%,#C8141D 100%)!important;
  border:0!important;color:#FFFFFF!important;
  box-shadow:0 8px 18px rgba(225,29,38,.32)!important;
  transition:transform .15s,box-shadow .15s,filter .15s;
}
.st-key-home_upload_panel .st-key-find_home button [data-testid="stMarkdownContainer"]{
  width:auto!important;flex:0 0 auto!important;margin:0!important;
}
.st-key-home_upload_panel .st-key-find_home button p{
  margin:0!important;line-height:1!important;color:inherit!important;
}
.st-key-home_upload_panel .st-key-find_home button::before{margin:0!important;flex:0 0 19px}
.st-key-home_upload_panel .st-key-find_home button:hover:not(:disabled){
  transform:translateY(-1px);filter:brightness(1.07);
  box-shadow:0 12px 24px rgba(225,29,38,.40)!important;
}

/* Disabled: still clearly a red button, clearly inactive (readable, not washed out) */
.st-key-home_upload_panel .st-key-find_home button:disabled{
  background:#FDE8EA!important;color:#C0262D!important;
  border:1.5px solid #F2B7BC!important;box-shadow:none!important;
  cursor:not-allowed!important;opacity:1!important;transform:none!important;filter:none!important;
}
.st-key-home_upload_panel .st-key-find_home button:disabled::before{
  opacity:1!important;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='%23C0262D'%3E%3Cpath d='m8 5 12 7-12 7z'/%3E%3C/svg%3E")!important;
}

/* 3) Choose Files: same punchy red gradient + hover */
.st-key-home_upload_panel .st-key-upload_zone [data-testid="stFileUploaderDropzoneInstructions"] button,
.st-key-home_upload_panel .st-key-upload_zone_compact [data-testid="stFileUploaderDropzoneInstructions"] button{
  background:linear-gradient(135deg,#F2272F 0%,#C8141D 100%)!important;
  border:0!important;box-shadow:0 8px 18px rgba(225,29,38,.32)!important;
  transition:filter .15s,box-shadow .15s;
}
.st-key-home_upload_panel .st-key-upload_zone [data-testid="stFileUploaderDropzoneInstructions"] button:hover,
.st-key-home_upload_panel .st-key-upload_zone_compact [data-testid="stFileUploaderDropzoneInstructions"] button:hover{
  filter:brightness(1.07);box-shadow:0 12px 24px rgba(225,29,38,.40)!important;
}

/* 4) Sidebar nav: one consistent, left-aligned style for Home / How it Works.
      Selectors are deliberately more specific than the older nav rules above. */
section[data-testid="stSidebar"] div.st-key-nav_home button[data-testid^="stBaseButton"],
section[data-testid="stSidebar"] div.st-key-nav_how button[data-testid^="stBaseButton"]{
  height:50px!important;min-height:50px!important;padding:0 16px!important;margin:0 0 6px!important;
  border-radius:12px!important;font-size:15.5px!important;font-weight:600!important;
  justify-content:flex-start!important;box-shadow:none!important;transition:background .15s,border-color .15s,color .15s;
}
section[data-testid="stSidebar"] div.st-key-nav_home button[data-testid^="stBaseButton"] > div,
section[data-testid="stSidebar"] div.st-key-nav_how button[data-testid^="stBaseButton"] > div{
  width:100%!important;justify-content:flex-start!important;
}
section[data-testid="stSidebar"] div.st-key-nav_home button[data-testid^="stBaseButton"] > div > span,
section[data-testid="stSidebar"] div.st-key-nav_how button[data-testid^="stBaseButton"] > div > span{
  gap:12px!important;
}
section[data-testid="stSidebar"] div.st-key-nav_home button span[data-testid="stIconMaterial"],
section[data-testid="stSidebar"] div.st-key-nav_how button span[data-testid="stIconMaterial"]{
  font-size:20px!important;width:20px!important;
}
/* Active page */
section[data-testid="stSidebar"] div.st-key-nav_home button[data-testid="stBaseButton-primary"],
section[data-testid="stSidebar"] div.st-key-nav_how button[data-testid="stBaseButton-primary"]{
  background:linear-gradient(135deg,#F2272F 0%,#C8141D 100%)!important;
  border:1px solid #F2272F!important;box-shadow:0 6px 16px rgba(225,29,38,.28)!important;
}
section[data-testid="stSidebar"] div.st-key-nav_home button[data-testid="stBaseButton-primary"] span,
section[data-testid="stSidebar"] div.st-key-nav_how button[data-testid="stBaseButton-primary"] span{
  color:#FFFFFF!important;
}
/* Inactive page */
section[data-testid="stSidebar"] div.st-key-nav_home button[data-testid="stBaseButton-secondary"],
section[data-testid="stSidebar"] div.st-key-nav_how button[data-testid="stBaseButton-secondary"]{
  background:#161618!important;border:1px solid #232326!important;
}
section[data-testid="stSidebar"] div.st-key-nav_home button[data-testid="stBaseButton-secondary"] span,
section[data-testid="stSidebar"] div.st-key-nav_how button[data-testid="stBaseButton-secondary"] span{
  color:#C9C9CF!important;
}
section[data-testid="stSidebar"] div.st-key-nav_home button[data-testid="stBaseButton-secondary"]:hover,
section[data-testid="stSidebar"] div.st-key-nav_how button[data-testid="stBaseButton-secondary"]:hover{
  background:#1F1F22!important;border-color:#3A3A3F!important;
}
section[data-testid="stSidebar"] div.st-key-nav_home button[data-testid="stBaseButton-secondary"]:hover span,
section[data-testid="stSidebar"] div.st-key-nav_how button[data-testid="stBaseButton-secondary"]:hover span{
  color:#FFFFFF!important;
}

/* 5) Uploaded-file state: a clean file card + quiet "Add files" action instead of
      the big red blocks the generic dropzone-button rules produced. */
.st-key-home_upload_panel section[data-testid="stFileUploaderDropzone"]:has([data-testid="stFileChips"]){
  min-height:0!important;padding:18px!important;justify-content:center!important;
}
.st-key-home_upload_panel [data-testid="stFileChips"]{
  display:flex!important;flex-wrap:wrap!important;align-items:center!important;justify-content:center!important;gap:10px!important;
}
.st-key-home_upload_panel [data-testid="stFileChip"]{
  display:flex!important;align-items:center!important;gap:12px!important;
  min-width:280px!important;max-width:420px!important;height:auto!important;
  padding:10px 8px 10px 10px!important;background:#FFFFFF!important;
  border:1px solid #ECE4E5!important;border-radius:12px!important;
  box-shadow:0 2px 8px rgba(20,0,0,.05)!important;
}
.st-key-home_upload_panel [data-testid="stFileChip"] > div:first-child{
  width:36px!important;height:36px!important;min-width:36px!important;border-radius:9px!important;
  background:#FDEBEC!important;color:#E11D26!important;display:flex!important;align-items:center!important;justify-content:center!important;
}
.st-key-home_upload_panel [data-testid="stFileChip"] > div:first-child svg{color:#E11D26!important;fill:currentColor!important}
.st-key-home_upload_panel [data-testid="stFileChip"] > div:nth-child(2){flex:1 1 auto!important;min-width:0!important;text-align:left!important}
.st-key-home_upload_panel [data-testid="stFileChipName"]{font-size:14px!important;font-weight:600!important;color:#1A1A1C!important}
.st-key-home_upload_panel [data-testid="stFileChipName"] + div{font-size:12px!important;color:#7A7A83!important}
.st-key-home_upload_panel [data-testid="stFileChipDeleteBtn"]{margin-left:auto!important;display:flex!important}
.st-key-home_upload_panel section[data-testid="stFileUploaderDropzone"] [data-testid="stFileChipDeleteBtn"] button[data-testid="stBaseButton-minimal"]{
  min-width:30px!important;width:30px!important;height:30px!important;min-height:30px!important;padding:0!important;
  display:flex!important;align-items:center!important;justify-content:center!important;
  background:transparent!important;border:0!important;border-radius:8px!important;box-shadow:none!important;color:#8A8A92!important;
}
.st-key-home_upload_panel section[data-testid="stFileUploaderDropzone"] [data-testid="stFileChipDeleteBtn"] button[data-testid="stBaseButton-minimal"]:hover{
  background:#FDEBEC!important;color:#E11D26!important;
}
.st-key-home_upload_panel section[data-testid="stFileUploaderDropzone"] [data-testid="stFileChipDeleteBtn"] button svg{
  width:16px!important;height:16px!important;color:inherit!important;fill:currentColor!important;
}
.st-key-home_upload_panel section[data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-borderlessIcon"]{
  min-width:0!important;width:auto!important;height:40px!important;min-height:40px!important;padding:0 16px!important;
  display:inline-flex!important;align-items:center!important;gap:6px!important;
  background:#FFFFFF!important;border:1px dashed #F1B7BB!important;border-radius:10px!important;box-shadow:none!important;
  color:#E11D26!important;font-size:14px!important;font-weight:600!important;
}
.st-key-home_upload_panel section[data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-borderlessIcon"]:hover{
  background:#FFF5F5!important;border-style:solid!important;border-color:#E11D26!important;
}
.st-key-home_upload_panel section[data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-borderlessIcon"] *{color:#E11D26!important}
.st-key-home_upload_panel section[data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-borderlessIcon"]::after{
  content:"Add files";font-size:14px;font-weight:600;color:#E11D26;
}

/* 6) Title field + Find Promos: one centered column instead of a right-hand button. */
.st-key-home_upload_panel .st-key-home_actions{
  width:100%!important;max-width:520px!important;margin:16px auto 0!important;gap:12px!important;
}
.st-key-home_upload_panel .st-key-home_actions [data-testid="stWidgetLabel"] p{
  font-size:14px!important;font-weight:600!important;color:#34343C!important;
}
/* The field was 54px inside a 40px wrapper, clipping its top/bottom border. */
.st-key-home_upload_panel .st-key-home_actions [data-testid="stTextInputRootElement"]{
  height:52px!important;min-height:52px!important;overflow:visible!important;
  border:1px solid #E3E3E7!important;border-radius:12px!important;background:#FFFFFF!important;
  transition:border-color .15s,box-shadow .15s;
}
.st-key-home_upload_panel .st-key-home_actions [data-testid="stTextInputRootElement"]:focus-within{
  border-color:#E11D26!important;box-shadow:0 0 0 3px rgba(225,29,38,.12)!important;
}
.st-key-home_upload_panel .st-key-home_actions div.st-key-home_title input[data-testid="stTextInputField"]{
  height:50px!important;min-height:50px!important;border:0!important;box-shadow:none!important;background-color:transparent!important;
}
/* Find Promos: keep the play icon right next to the label, centered as a pair. */
.st-key-home_upload_panel .st-key-home_actions .st-key-find_home button > div{
  width:auto!important;flex:0 0 auto!important;
}
.st-key-home_upload_panel section[data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-borderlessIcon"],
.st-key-home_upload_panel section[data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-borderlessIcon"] > div{
  white-space:nowrap!important;width:auto!important;
}

/* 7) Phones / narrow tablets: stack hero, features and steps (desktop untouched). */
@media (max-width:760px){
  .pf-home-hero{flex-direction:column-reverse!important;align-items:flex-start!important;gap:6px!important;min-height:0!important;margin:0 0 8px!important}
  .pf-home-hero-art{width:96px!important;min-width:0!important;height:auto!important;justify-content:flex-start!important}
  .pf-home-hero-art .pf-mascot{width:96px!important;height:96px!important;max-width:96px!important;max-height:96px!important}
  .pf-home-h1{font-size:36px!important;line-height:1.08!important;letter-spacing:-1px!important;margin:8px 0 10px!important}
  .pf-home-lede{font-size:16px!important}
  .pf-home-features{grid-template-columns:1fr!important;gap:2px!important;margin:4px 0 18px!important}
  .pf-home-features .pf-feature{border-right:0!important;padding:8px 0!important}
  .pf-home-steps{grid-template-columns:1fr!important;gap:8px!important}
  .pf-home-steps .pf-step-arrow{transform:rotate(90deg);font-size:22px!important;line-height:1}
}
@media (min-width:761px) and (max-width:1100px){
  .pf-home-h1{font-size:44px!important}
  .pf-home-features .pf-feature{padding:7px 12px!important}
}

/* 8) Living mascot: pop-in, gentle float, twinkling sparkles, speech bubble, hover reaction. */
.pf-mascot-stage{position:relative;width:140px;height:160px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;cursor:default}
.pf-mascot-bob{position:relative;z-index:2;animation:pf-pop .7s cubic-bezier(.34,1.56,.64,1) both, pf-float 3.4s ease-in-out .7s infinite;transform-origin:50% 90%}
.pf-mascot-bob .pf-mascot{transition:transform .25s ease}
.pf-mascot-shadow{display:block;width:78px;height:10px;margin-top:2px;border-radius:50%;
  background:radial-gradient(ellipse at center,rgba(26,26,28,.22) 0%,rgba(26,26,28,0) 70%);
  animation:pf-shadow 3.4s ease-in-out .7s infinite}
.pf-spark{position:absolute;z-index:1;display:block;background:#E11D26;opacity:0;
  clip-path:polygon(50% 0,61% 39%,100% 50%,61% 61%,50% 100%,39% 61%,0 50%,39% 39%);animation:pf-twinkle 2.6s ease-in-out infinite}
.pf-spark-1{width:16px;height:16px;top:34px;left:-14px;animation-delay:.9s}
.pf-spark-2{width:11px;height:11px;top:96px;right:-12px;background:#F5A3A8;animation-delay:1.6s}
.pf-spark-3{width:9px;height:9px;top:14px;right:8px;animation-delay:2.2s}
.pf-mascot-bubble{position:absolute;z-index:3;top:-10px;right:100%;margin-right:2px;white-space:nowrap;
  padding:7px 12px;border-radius:12px 12px 2px 12px;background:#1A1A1C;color:#FFFFFF;
  font-size:12.5px;font-weight:600;letter-spacing:.1px;box-shadow:0 6px 16px rgba(20,0,0,.16);
  transform-origin:100% 100%;animation:pf-bubble-in .45s cubic-bezier(.34,1.56,.64,1) 1.1s both, pf-bubble-bob 3.4s ease-in-out 1.6s infinite}
.pf-bubble-hover{display:none}
.pf-mascot-stage:hover .pf-bubble-idle{display:none}
.pf-mascot-stage:hover .pf-bubble-hover{display:inline}
.pf-mascot-stage:hover .pf-mascot-bubble{background:#E11D26}
.pf-mascot-stage:hover .pf-mascot-bob{animation:pf-wiggle .6s ease-in-out}
.pf-mascot-stage:hover .pf-spark{animation-duration:1.1s}
@keyframes pf-pop{0%{opacity:0;transform:translateY(16px) scale(.6)}100%{opacity:1;transform:translateY(0) scale(1)}}
@keyframes pf-float{0%,100%{transform:translateY(0) rotate(-2deg)}50%{transform:translateY(-9px) rotate(2deg)}}
@keyframes pf-shadow{0%,100%{transform:scaleX(1);opacity:1}50%{transform:scaleX(.72);opacity:.55}}
@keyframes pf-twinkle{0%,100%{opacity:0;transform:scale(.3) rotate(0)}45%,55%{opacity:1;transform:scale(1) rotate(45deg)}}
@keyframes pf-bubble-in{0%{opacity:0;transform:scale(.4)}100%{opacity:1;transform:scale(1)}}
@keyframes pf-bubble-bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
@keyframes pf-wiggle{0%{transform:translateY(0) rotate(0)}20%{transform:translateY(-12px) rotate(-8deg)}40%{transform:translateY(-12px) rotate(7deg)}60%{transform:translateY(-6px) rotate(-4deg)}80%{transform:translateY(0) rotate(2deg)}100%{transform:translateY(0) rotate(0)}}
@media (max-width:760px){
  .pf-mascot-stage{width:96px;height:110px}
  .pf-mascot-shadow{width:56px;height:8px}
  .pf-mascot-bubble{right:auto;left:100%;margin:0 0 0 2px;top:30px;border-radius:12px 12px 12px 2px;transform-origin:0 100%}
}
@media (prefers-reduced-motion:reduce){
  .pf-mascot-bob,.pf-mascot-shadow,.pf-spark,.pf-mascot-bubble,.pf-mascot-stage:hover .pf-mascot-bob{animation:none!important}
  .pf-spark{opacity:.8}
}

/* 9) Every page: drop empty style-only blocks (each added a 16px gap) and the tall top padding. */
[data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] > style:only-child){
  display:none!important;
}
[data-testid="stMainBlockContainer"]{padding-top:20px!important}

/* 10) Report header mascot: same living mascot as Home, sized for the report. */
.pf-mascot-stage-report{width:118px;height:132px;flex:0 0 118px;margin-right:6px}
.pf-mascot-stage-report .pf-mascot{display:block!important;width:110px!important;height:110px!important;max-width:110px!important;max-height:110px!important}
.pf-mascot-stage-report .pf-mascot-shadow{width:66px}
.pf-mascot-stage-report .pf-mascot-bubble{top:2px}
@media (max-width:860px){
  .pf-mascot-stage-report{width:76px;height:88px;flex-basis:76px}
  .pf-mascot-stage-report .pf-mascot{width:70px!important;height:70px!important;max-width:70px!important;max-height:70px!important}
  .pf-mascot-stage-report .pf-mascot-shadow{width:44px;height:7px}
  .pf-mascot-stage-report .pf-mascot-bubble{display:none}
}

/* 11) Sidebar "New analysis": clearly visible red-outlined action. */
section[data-testid="stSidebar"] div.st-key-sidebar_new_analysis button[data-testid^="stBaseButton"]{
  height:48px!important;min-height:48px!important;border-radius:12px!important;
  background:rgba(225,29,38,.12)!important;border:1px solid rgba(242,39,47,.65)!important;
  box-shadow:none!important;transition:background .15s,border-color .15s,box-shadow .15s;
}
section[data-testid="stSidebar"] div.st-key-sidebar_new_analysis button[data-testid^="stBaseButton"] *{
  color:#FFFFFF!important;font-size:15px!important;font-weight:600!important;
}
section[data-testid="stSidebar"] div.st-key-sidebar_new_analysis button[data-testid^="stBaseButton"] span[data-testid="stIconMaterial"]{
  color:#FF5A61!important;font-size:20px!important;
}
section[data-testid="stSidebar"] div.st-key-sidebar_new_analysis button[data-testid^="stBaseButton"]:hover{
  background:linear-gradient(135deg,#F2272F 0%,#C8141D 100%)!important;border-color:#F2272F!important;
  box-shadow:0 6px 16px rgba(225,29,38,.30)!important;
}
section[data-testid="stSidebar"] div.st-key-sidebar_new_analysis button[data-testid^="stBaseButton"]:hover span[data-testid="stIconMaterial"]{color:#FFFFFF!important}

/* 12) Sidebar re-run form: readable title field and brand-red Find Promos. */
section[data-testid="stSidebar"] div.st-key-show_title [data-testid="stTextInputRootElement"]{
  background:#161618!important;border:1px solid #2E2E33!important;border-radius:10px!important;
}
section[data-testid="stSidebar"] div.st-key-show_title [data-testid="stTextInputRootElement"]:focus-within{border-color:#E11D26!important}
section[data-testid="stSidebar"] div.st-key-show_title input{color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;background:transparent!important}
section[data-testid="stSidebar"] div.st-key-show_title input::placeholder{color:#7A7A83!important;-webkit-text-fill-color:#7A7A83!important}
section[data-testid="stSidebar"] div.st-key-show_title [data-testid="stWidgetLabel"] p{color:#B5B5BC!important}
section[data-testid="stSidebar"] div.stElementContainer:not([class*="st-key-nav_"]) > div[data-testid="stButton"] > button[data-testid="stBaseButton-primary"]{
  background:linear-gradient(135deg,#F2272F 0%,#C8141D 100%)!important;border:1px solid #F2272F!important;border-radius:12px!important;
}

/* 13) Report downloads: icon + label, red accent on hover. */
[data-testid="stMainBlockContainer"] [data-testid="stDownloadButton"] button{
  height:48px!important;border-radius:12px!important;background:#FFFFFF!important;border:1px solid #ECE4E5!important;
  box-shadow:0 2px 6px rgba(20,0,0,.04)!important;transition:border-color .15s,box-shadow .15s,transform .15s;
}
[data-testid="stMainBlockContainer"] [data-testid="stDownloadButton"] button p{font-weight:600!important;color:#1A1A1C!important}
[data-testid="stMainBlockContainer"] [data-testid="stDownloadButton"] button span[data-testid="stIconMaterial"]{color:#E11D26!important}
[data-testid="stMainBlockContainer"] [data-testid="stDownloadButton"] button:hover{
  border-color:#E11D26!important;box-shadow:0 6px 16px rgba(225,29,38,.14)!important;transform:translateY(-1px);
}
[data-testid="stMainBlockContainer"] [data-testid="stDownloadButton"] button:hover p{color:#E11D26!important}
</style>""", unsafe_allow_html=True)

def sb_head(n: str, text: str) -> None:
    st.html(f'<div class="pf-sbh"><b>{n}</b>{text}</div>')


def secret(name: str) -> str:
    try:
        return st.secrets.get(name, "") or os.getenv(name, "")
    except Exception:  # no secrets file configured
        return os.getenv(name, "")


config = SarvamConfig.load(secret)
n_single, n_stitched, llm_top, compare_too = 20, 6, 40, True


def mascot(class_name: str) -> str:
    image = base64.b64encode((ROOT / "static" / "mascot.webp").read_bytes()).decode("ascii")
    dimensions = {
        "pf-mascot-brand": (44, 44),
        "pf-mascot-welcome": (140, 140),
        "pf-mascot-mobile": (110, 110),
    }.get(class_name, (44, 44))
    width, height = dimensions
    return (f'<img class="pf-mascot {class_name}" width="{width}" height="{height}" '
            f'style="width:{width}px;height:{height}px;max-width:{width}px;max-height:{height}px;object-fit:contain;'
            f'display:block;flex:0 0 auto" src="data:image/webp;base64,{image}" '
            f'alt="Promo Finder clapperboard mascot" />')


def svg_icon(name: str, size: int = 24, class_name: str = "") -> str:
    """Inline Lucide-style line icons for the landing screen."""
    paths = {
        "home": '<path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9"/><path d="M9 20v-6h6v6"/>',
        "info": '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
        "bolt": '<path d="m13 2-3 8h7l-6 12 2-9H6l7-11z"/>',
        "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/><path d="m16.5 7.5 4-4"/>',
        "layers": '<path d="m12 3 9 5-9 5-9-5 9-5z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/>',
        "cloud-upload": '<path d="M16 16l-4-4-4 4"/><path d="M12 12v9"/><path d="M20 16.5a4.5 4.5 0 0 0-.7-8.95A7 7 0 0 0 5.2 9.4 4 4 0 0 0 5 17h3"/>',
        "upload": '<path d="M12 16V4m-5 5 5-5 5 5"/><path d="M20 16.5v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2"/>',
        "play": '<path d="m8 5 12 7-12 7z"/>',
        "list": '<path d="M9 6h12M9 12h12M9 18h12"/><path d="M4 6h.01M4 12h.01M4 18h.01"/>',
        "clapper": '<path d="M4 8h16v12H4z"/><path d="m4 8 2-5h16l-2 5"/><path d="M9 3 7 8m7-5-2 5m7-5-2 5"/><circle cx="9" cy="14" r="1"/><path d="m12 18 3-2 2 2"/>',
    }
    return (f'<svg class="{class_name}" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{paths.get(name, "")}</svg>')


def feature_svg_icon(name: str) -> str:
    """Feature icons with explicit SVG colors so they remain visible in every container."""
    artwork = {
        "bolt": (
            '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#E11D26" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>'
        ),
        "target": (
            '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#E11D26" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '<circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>'
        ),
        "layers": (
            '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#E11D26" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>'
            '<polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line>'
            '<line x1="16" y1="17" x2="8" y2="17"></line></svg>'
        ),
    }
    # st.html sanitizes inline <svg> away, so ship each icon as an <img> data URI instead.
    svg = artwork.get(name, "").replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return (f'<img src="data:image/svg+xml;base64,{encoded}" width="22" height="22" alt="" '
            f'style="width:22px;height:22px;display:block" />')

def feature_item(icon: str, title: str, detail: str, bordered: bool = True) -> str:
    border = "border-right:1px solid #E5E5E8;" if bordered else ""
    return (
        f'<div class="pf-feature" style="display:flex;align-items:center;gap:13px;min-width:0;'
        f'box-sizing:border-box;padding:7px 18px;{border}">'
        f'<span class="pf-feature-icon" style="width:40px;height:40px;min-width:40px;flex:0 0 40px;'
        f'display:flex;align-items:center;justify-content:center;border-radius:10px;'
        f'background:#FDEBEC;color:#E11D26">{feature_svg_icon(icon)}</span>'
        f'<span style="display:flex;flex-direction:column;align-items:flex-start;justify-content:center;'
        f'gap:2px;min-width:0;text-align:left">'
        f'<b style="display:block;font-size:15px;line-height:1.2;font-weight:700;color:#1A1A1C;'
        f'white-space:normal">{title}</b>'
        f'<small style="display:block;font-size:13px;line-height:1.3;font-weight:400;color:#5B5B63;'
        f'white-space:normal">{detail}</small>'
        f'</span></div>'
    )

def process_step(number: int, icon: str, title: str, detail: str) -> str:
    symbols = {"upload": "↑", "list": "☷", "clapper": "▤"}
    glyph = symbols.get(icon, "•")
    return (
        f'<div style="position:relative;display:flex;align-items:center;gap:14px;min-height:112px;'
        f'box-sizing:border-box;padding:18px 16px 16px 25px;background:#FFFFFF;border:1px solid #F0E6E7;'
        f'border-radius:16px;box-shadow:0 5px 16px rgba(20,0,0,.035)">'
        f'<span style="position:absolute;top:12px;left:12px;width:25px;height:25px;display:flex;'
        f'align-items:center;justify-content:center;border-radius:50%;background:#FDEBEC;color:#E11D26;'
        f'font-size:13px;font-weight:700">{number}</span>'
        f'<span style="width:48px;height:48px;min-width:48px;margin-left:15px;display:flex;'
        f'align-items:center;justify-content:center;border-radius:12px;background:#FDEBEC;color:#E11D26;'
        f'font-size:27px;font-weight:700">{glyph}</span>'
        f'<span style="display:flex;flex-direction:column;gap:5px;min-width:0">'
        f'<b style="display:block;font-size:16px;line-height:1.3;color:#1A1A1C;font-weight:700">{title}</b>'
        f'<small style="display:block;font-size:14px;line-height:1.45;color:#5B5B63">{detail}</small>'
        f'</span></div>'
    )


def film_ribbon() -> str:
    return """<svg class="pf-film-ribbon" viewBox="0 0 420 190" preserveAspectRatio="none" aria-hidden="true">
<path d="M-20 145 C70 25 128 35 190 110 S310 200 445 55" fill="none" stroke="#F5C5C8" stroke-width="64"/>
<path d="M-20 145 C70 25 128 35 190 110 S310 200 445 55" fill="none" stroke="#FFF" stroke-width="49"/>
<path d="M-20 145 C70 25 128 35 190 110 S310 200 445 55" fill="none" stroke="#F4BFC3" stroke-width="1.5" stroke-dasharray="4 8"/>
<path d="M-20 116 C70 -4 128 6 190 81 S310 171 445 26" fill="none" stroke="#F4BFC3" stroke-width="1.5" stroke-dasharray="4 8"/>
</svg>"""


def feature_hero_art() -> str:
    return film_ribbon() + mascot("pf-mascot-welcome") + (
        '<svg class="pf-home-spark" viewBox="0 0 48 48" fill="none" stroke="#E11D26" '
        'stroke-width="3.2" stroke-linecap="round" aria-hidden="true">'
        '<path d="M23 2 20 13M38 8l-7 9M45 25l-10 1"/>'
        '</svg>')


def guess_title(files) -> str:
    z = next((f for f in files if f.name.lower().endswith(".zip")), None)
    if not z:
        return ""
    try:
        with zipfile.ZipFile(io.BytesIO(z.getvalue())) as zf:
            tops = {n.split("/")[0] for n in zf.namelist() if "/" in n and not n.startswith("__MACOSX")}
    except zipfile.BadZipFile:
        tops = set()
    base = tops.pop() if len(tops) == 1 else re.sub(r"\.zip$", "", z.name, flags=re.I)
    return re.sub(r"[-_ ]?scripts.*$", "", base, flags=re.I).strip()


def clear_report() -> None:
    for name in ("result", "checks", "compare", "kind", "tiers", "kind2", "backup_ranking"):
        st.session_state.pop(name, None)


MAX_FILE_BYTES = 50 * 1024 * 1024


def select_uploads(widget_key: str) -> None:
    """Validate upload choices only; the AI workflow begins only on Find Promos."""
    clear_report()
    incoming = list(st.session_state.get(widget_key) or [])
    valid, errors = [], []
    for uploaded in incoming:
        suffix = Path(uploaded.name).suffix.lower()
        if suffix not in {".zip", ".txt", ".srt", ".vtt"}:
            errors.append(f"{uploaded.name}: only ZIP, TXT, SRT and VTT files are accepted.")
        elif uploaded.size > MAX_FILE_BYTES:
            errors.append(f"{uploaded.name}: exceeds the 50MB per-file limit.")
        else:
            valid.append(uploaded)
    st.session_state.source_files = valid
    st.session_state.upload_error = " ".join(errors)
    suggested = guess_title(valid)
    st.session_state.show_title = suggested
    st.session_state.home_title = suggested
    if errors:
        # Force a fresh uploader widget while retaining any valid files in session state.
        st.session_state.home_upload_version = st.session_state.get("home_upload_version", 0) + 1


def sync_title(source: str, target: str) -> None:
    st.session_state[target] = st.session_state[source]


def new_analysis() -> None:
    clear_report()
    st.session_state.source_files = []
    st.session_state.show_title = ""
    st.session_state.home_title = ""
    st.session_state.upload_error = ""
    st.session_state.active_page = "Home"
    st.session_state.home_upload_version = st.session_state.get("home_upload_version", 0) + 1


def render_how_it_works_page() -> None:
    st.markdown("""
    <style>
    /* Match the Home page: trim top padding and drop the empty style-only
       containers whose 16px flex gaps stacked up into a blank band. */
    [data-testid="stMainBlockContainer"]:has(.pf-page-head),
    .main .block-container:has(.pf-page-head) {
        padding-top: 14px !important;
    }
    [data-testid="stMainBlockContainer"]:has(.pf-page-head) [data-testid="stElementContainer"]:has(style),
    [data-testid="stMainBlockContainer"]:has(.pf-page-head) [data-testid="stElementContainer"]:empty {
        display: none !important;
    }
    .pf-page-head {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    st.html("""
<div class="pf pf-page-head">
<div class="pf-label accent">PRODUCT GUIDE</div><h1 style="margin-top:2px">How Promo Finder works</h1>
<p>From timestamped screenplay files to a ranked, editor-ready promo shortlist.</p>
</div>
<div class="pf pf-how-grid">
  <article class="pf-how-card"><span class="num">01</span><h3>Upload your scripts</h3>
  <p>Upload a ZIP of episode scripts or individual .txt, .srt or .vtt files. Promo Finder reads timestamped scripts, subtitle files and standard screenplays (INT./EXT. layout). Screenplays without timestamps get estimated timing, clearly marked in the report. Files or blocks it cannot parse are reported.</p></article>
  <article class="pf-how-card"><span class="num">02</span><h3>Find hooks and cliffhangers</h3>
  <p>The rules engine scores screenplay beats for hook strength, cliffhanger strength, intensity and dependence on backstory. The show premise is inferred from its title and early episode loglines.</p></article>
  <article class="pf-how-card"><span class="num">03</span><h3>Generate valid promo cuts</h3>
  <p>It builds single-episode and stitched candidates. Each cut must run 20–60 seconds, hook the viewer within the first 3 seconds, use real source timestamps and avoid cutting through a spoken line.</p></article>
  <article class="pf-how-card"><span class="num">04</span><h3>Rank the strongest moments</h3>
  <p>The rules score weighs hook (28%), cliffhanger (24%), momentum (20%), new-viewer clarity (16%), length fit (6%) and premise fit (6%). Selection avoids overlapping cuts and repeated hook or cliffhanger lines.</p></article>
  <article class="pf-how-card"><span class="num">05</span><h3>AI editorial review</h3>
  <p>The configured AI reviewer evaluates a shortlist, returns scores, reasons and risks, and may suggest trims by referring to numbered screenplay beats. Its score is blended with the rules score.</p></article>
  <article class="pf-how-card"><span class="num">06</span><h3>Validate every cut</h3>
  <p>Code checks AI trim suggestions against the original screenplay. It rejects suggestions that break duration, timestamp, hook or spoken-line constraints. Unusable AI replies retain the rules score.</p></article>
  <article class="pf-how-card"><span class="num">07</span><h3>Review and export</h3>
  <p>Editors inspect the ranked list, top pick, episode library, season map and quality checks. Download PDF, HTML, CSV and JSON reports to take the cut points into editing.</p></article>
</div>
<div class="pf pf-how-note"><b>Human approval stays in the loop.</b> Promo Finder analyses screenplay text, not finished footage. Editors should check visual impact, pacing, context and spoiler risk before publishing. AI can only rerank candidates found by the rules pipeline; it cannot recover moments that candidate generation missed.</div>""")
# ---------------------------------------------------------------- sidebar
if "active_page" not in st.session_state:
    st.session_state.active_page = "Home"


def set_active_page(name: str) -> None:
    st.session_state.active_page = name


with st.sidebar:
    st.html(
        f'<div style="display:flex;align-items:center;gap:12px;margin:0 0 7px">'
        f'{mascot("pf-mascot-brand")}'
        '<b style="font-size:24px;line-height:1.1;font-weight:700;letter-spacing:-.6px;color:#FFFFFF">Promo Finder</b>'
        '</div>'
        '<p style="font-size:15px;line-height:1.55;color:#B5B5BC;margin:7px 0 20px;max-width:250px">'
        'Finds promo cuts in microdrama scripts.</p>'
    )
    for label, key, nav_icon in (("Home", "home", ":material/home:"),
                                   ("How it Works", "how", ":material/info:")):
        active = st.session_state.active_page == label
        st.button(label, key=f"nav_{key}", icon=nav_icon,
                  type="primary" if active else "secondary",
                  width="stretch", on_click=set_active_page, args=(label,))

    # Shift "New analysis" button ABOVE the AI Review badge
    if "result" in st.session_state:
        st.html('<div style="height:12px"></div>')
        st.button("New analysis", key="sidebar_new_analysis", width="stretch",
                  type="secondary", on_click=new_analysis, icon=":material/add:")

    st.html('<div style="height:1px;background:#2A2A2D;margin:20px 0"></div>')
    if config.configured:
        st.html('<div style="display:flex;align-items:center;gap:11px;padding:17px 16px;'
                'background:#161618;border:1px solid #232326;border-radius:14px;color:#FFFFFF;'
                'font-size:16px;font-weight:600;margin:0 0 20px">'
                '<span style="width:12px;height:12px;border-radius:50%;background:#22C55E;'
                'box-shadow:0 0 0 4px rgba(34,197,94,.12),0 0 12px rgba(34,197,94,.55)"></span>'
                'AI review enabled</div>')
    else:
        st.html('<div style="display:flex;align-items:center;gap:11px;padding:17px 16px;'
                'background:#161618;border:1px solid #232326;border-radius:14px;color:#FFFFFF;'
                'font-size:16px;font-weight:600;margin:0 0 20px">'
                '<span style="width:12px;height:12px;border-radius:50%;background:#F59E0B"></span>'
                'AI review unavailable</div>')

    st.html(
        '<div style="padding:20px;background:#161618;border:1px solid #232326;border-radius:18px;margin:0">'
        '<div style="font-size:18px;font-weight:700;color:#FFFFFF;margin:0 0 16px">Quick Stats</div>'
        '<div style="display:flex;align-items:center;gap:14px;margin:13px 0 0">'
        '<span style="width:48px;height:48px;min-width:48px;display:flex;align-items:center;justify-content:center;'
        'border-radius:12px;background:#2A1213;color:#E11D26;font-size:25px;font-weight:700">▶</span>'
        '<span style="display:flex;flex-direction:column;gap:3px">'
        '<b style="font-size:18px;line-height:1.2;color:#FFFFFF">20 – 60 sec</b>'
        '<small style="font-size:14px;line-height:1.3;color:#B5B5BC">Promo length</small></span></div>'
        '<div style="display:flex;align-items:center;gap:14px;margin:13px 0 0">'
        '<span style="width:48px;height:48px;min-width:48px;display:flex;align-items:center;justify-content:center;'
        'border-radius:12px;background:#2A1213;color:#E11D26;font-size:24px;font-weight:700">▱</span>'
        '<span style="display:flex;flex-direction:column;gap:3px">'
        '<b style="font-size:18px;line-height:1.2;color:#FFFFFF">4</b>'
        '<small style="font-size:14px;line-height:1.3;color:#B5B5BC">Export formats</small></span></div>'
        '</div>'
    )

    page = st.session_state.active_page
    go = False
    title = st.session_state.get("show_title", "")
    files = list(st.session_state.get("source_files", []))
    if page == "Home" and "result" in st.session_state:
        st.html('<div style="height:1px;background:#2A2A2D;margin:22px 0"></div>')
        title = st.text_input("Show title", key="show_title", placeholder="e.g. The Maid Was the Heiress",
                              on_change=sync_title, args=("show_title", "home_title"),
                              help="The title helps the system understand the show's premise.")
        go = st.button("Find Promos", type="primary", width="stretch",
                       disabled=not files)
# The guide page is independent of the upload and analysis workflow.
if page == "How it Works":
    render_how_it_works_page()
    st.stop()

# Reserve the first main-area slot so progress appears above the upload form.
progress_panel = st.empty()

# ---------------------------------------------------------------- first visit
if page == "Home" and "result" not in st.session_state and not go:
    features = "".join([
        feature_item("bolt", "AI + Rules Engine", "Scores & reranks promos", True),
        feature_item("target", "Script-accurate", "Exact timestamps", True),
        feature_item("layers", "Editor-ready", "Reports, CSV & more", False),
    ])
    steps = (
        process_step(1, "upload", "Upload your story",
                     "One episode or a full season of timestamped screenplays.")
        + '<div class="pf-step-arrow" style="font-size:27px;color:#E11D26;text-align:center;align-self:center">→</div>'
        + process_step(2, "list", "Review the strongest moments",
                       "Ranked 20–60 second cuts, with hooks and cliffhangers.")
        + '<div class="pf-step-arrow" style="font-size:27px;color:#E11D26;text-align:center;align-self:center">→</div>'
        + process_step(3, "clapper", "Take it to your editor",
                       "Exact cut points, editorial notes and reports to share.")
    )
    st.html(f"""
<div class="pf-home-hero" style="display:flex;align-items:center;justify-content:space-between;gap:20px;min-height:158px;margin:0 0 14px">
  <div class="pf-home-hero-text" style="flex:1 1 auto;min-width:0;max-width:820px">
    <div style="font-size:15px;line-height:1.2;font-weight:700;letter-spacing:.5px;color:#E11D26;text-transform:uppercase">PROMO FINDER</div>
    <h1 class="pf-home-h1" style="font-family:Inter,system-ui,sans-serif;font-size:56px;line-height:1.04;letter-spacing:-1.8px;font-weight:750;color:#1A1A1C;margin:10px 0 12px">
      Find the moments<br><span style="color:#E11D26">worth promoting</span>
    </h1>
    <p class="pf-home-lede" style="font-size:18px;line-height:1.45;color:#5B5B63;margin:0;max-width:820px">
      Find ranked 20–60 second promo cuts, with hooks and cliffhangers ready for your editor.
    </p>
  </div>
  <div class="pf-home-hero-art" style="position:relative;display:flex;align-items:center;justify-content:center;width:230px;min-width:210px;height:160px;overflow:visible">
    <div class="pf-mascot-stage">
      <span class="pf-mascot-bubble"><span class="pf-bubble-idle">Let's find a hit!</span><span class="pf-bubble-hover">Drop a script below ↓</span></span>
      <span class="pf-spark pf-spark-1"></span><span class="pf-spark pf-spark-2"></span><span class="pf-spark pf-spark-3"></span>
      <div class="pf-mascot-bob">{mascot("pf-mascot-welcome")}</div>
      <span class="pf-mascot-shadow"></span>
    </div>
  </div>
</div>
<div class="pf-home-features" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));align-items:center;margin:8px 0 24px">
  {features}
</div>
""")

    with st.container(key="home_upload_panel"):
        st.html(
            '<div style="text-align:center;padding:0 0 12px">'
            '<div style="font-size:24px;line-height:1.2;font-weight:700;letter-spacing:-.55px;color:#1A1A1C">'
            'Upload your microdrama scripts</div>'
            '<div style="font-size:14px;color:#5B5B63;margin-top:4px">'
            'Drag & drop a ZIP, TXT, SRT or VTT file here.</div></div>'
        )

        st.markdown("""
        <style>
        /* Glowing Professional "New Analysis" Button */
section[data-testid="stSidebar"] .st-key-sidebar_new_analysis button {
    background: linear-gradient(135deg, #1C191A 0%, #121011 100%) !important;
    color: #FFFFFF !important;
    border: 1px solid #E11D26 !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    letter-spacing: 0.3px !important;
    box-shadow: 0 0 12px rgba(225, 29, 38, 0.35), inset 0 0 8px rgba(225, 29, 38, 0.15) !important;
    transition: all 0.25s ease-in-out !important;
}

section[data-testid="stSidebar"] .st-key-sidebar_new_analysis button:hover {
    background: linear-gradient(135deg, #8E0E12 0%, #5C080B 100%) !important;
    border-color: #FF4D55 !important;
    box-shadow: 0 0 20px rgba(225, 29, 38, 0.6), 0 4px 14px rgba(0, 0, 0, 0.4) !important;
    transform: translateY(-1px) !important;
}
        /* Modernized Upload Zone Styling */
        [data-testid="stFileUploaderDropzone"] {
            background: #FFF5F5 !important;
            border: 1.5px dashed #F1B7BB !important;
            border-radius: 14px !important;
            padding: 24px !important;
            text-align: center !important;
        }
        [data-testid="stFileUploaderDropzone"] button {
            background: linear-gradient(135deg, #8E0E12 0%, #5C080B 100%) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 10px 24px !important;
            font-weight: 700 !important;
            margin: 0 auto !important;
            box-shadow: 0 4px 12px rgba(142, 14, 18, 0.25) !important;
        }
        /* Style uploaded file list item cleanly inside container */
        [data-testid="stFileUploaderFile"] {
            background: #FFFFFF !important;
            border: 1px solid #E5E5E8 !important;
            border-radius: 10px !important;
            margin: 12px auto 0 !important;
            max-width: 480px !important;
        }
        </style>
        """, unsafe_allow_html=True)

        upload_key = f'home_files_{st.session_state.get("home_upload_version", 0)}'

        # Single native Streamlit file uploader (handles uploaded file badges automatically)
        st.file_uploader(
            "Upload your microdrama scripts", type=["zip", "txt", "srt", "vtt"], accept_multiple_files=True,
            key=upload_key, on_change=select_uploads, args=(upload_key,),
            label_visibility="collapsed", max_upload_size=50,
        )

        upload_error = st.session_state.get("upload_error", "")
        if upload_error:
            st.html(f'<div style="padding:8px 12px;margin:8px auto;max-width:500px;border:1px solid #F3B7BA;'
                    f'background:#FFF1F1;border-radius:8px;color:#B4232A;font-size:13px;line-height:1.4;text-align:center;">'
                    f'{html_escape(upload_error)}</div>')

        # Title + primary action stacked in one centered column under the dropzone.
        with st.container(key="home_actions"):
            home_title = st.text_input(
                "Show title (optional)",
                key="home_title",
                placeholder="e.g. The Maid Was the Heiress",
                on_change=sync_title,
                args=("home_title", "show_title"),
            )
            go = st.button("Find Promos", key="find_home", type="primary",
                           use_container_width=True, disabled=not files)

        if go:
            title = home_title

    if not go:
        st.html(f'<div class="pf-home-steps" style="display:grid;grid-template-columns:minmax(0,1fr) 28px minmax(0,1fr) 28px minmax(0,1fr);'
                f'gap:12px;align-items:stretch;margin:18px auto 0">{steps}</div>')
        st.stop()

# ---------------------------------------------------------------- run
if go:
    review = ReviewProgress()
    progress_panel.html(review.html())
    warnings: list[str] = []
    raw = []
    for f in files:
        data = f.getvalue()
        if f.name.lower().endswith(".zip"):
            try:
                raw += load_zip_bytes(data, [])     # finalize() below reports problems once, across all files
            except zipfile.BadZipFile:
                warnings.append(f"{f.name}: not a valid zip file")
        else:
            raw.append(parse_text(data.decode("utf-8", errors="replace"), f.name))
    eps = finalize(raw, warnings)
    for w in warnings:
        st.warning(w)
    if not eps:
        progress_panel.empty()
        st.error("No readable episodes found. Promo Finder reads timestamped scripts (e.g. 'MIA: line' with "
                 "'Start: 00:05 | End: 00:08' or '[00:05 - 00:08] MIA: line'), SRT/VTT subtitle files, and "
                 "standard screenplays (INT./EXT. headings, CHARACTER names on their own line).")
        st.stop()
    review.stage = 1
    progress_panel.html(review.html())
    show_title = title.strip() or (f"Episode {eps[0].num}" if len(eps) == 1 else "Series promo report")
    if not config.configured:
        progress_panel.empty()
        st.error("AI review is unavailable. Contact the app owner.")
        st.stop()
    try:
        judge = Judge(f"sarvam:{config.model}", api_key=config.api_key,
                      base_url=config.base_url, use_cache=False)
    except (ValueError, TypeError) as e:
        progress_panel.empty()
        st.error("AI review is currently unavailable. Please contact the app owner.")
        with st.expander("Run details"):
            st.code(str(e).replace(config.api_key, "[redacted]"), language=None)
        st.stop()

    def show_progress(message: str) -> None:
        before = review.html()
        review.update(message)
        after = review.html()
        if after != before:
            progress_panel.html(after)

    try:
        if compare_too:
            rules_res, res, cmp = compare(eps, show_title, judge, llm_top, progress=show_progress,
                                         n_single=n_single, n_stitched=n_stitched)
            st.session_state.compare = (rules_res, cmp)
        else:
            res = run(eps, show_title, judge, n_single, n_stitched, llm_top,
                      progress=show_progress, warnings=warnings)
            st.session_state.pop("compare", None)
    except Exception as e:
        st.error("We couldn’t finish this review. Please try again.")
        with st.expander("Run details"):
            st.code(str(e).replace(config.api_key, "[redacted]"), language=None)
        st.stop()
    finally:
        progress_panel.empty()
    st.session_state.result = res
    st.session_state.checks = run_checks(res)
    st.rerun()

res = st.session_state.result
checks = st.session_state.get("checks") or run_checks(res)
s = res.stats

ai = s.get("ai", {})
st.caption("Your promo report · Analyse another script whenever you’re ready.")
if not ai.get("judged", 0):
    reason = {
        401: "The AI connection needs attention. Contact the app owner.",
        403: "The AI connection needs attention. Contact the app owner.",
        402: "AI review is paused because the service is out of credits.",
        429: "The AI service is busy. Please try again shortly.",
    }.get(ai.get("last_error_code"), "The AI service did not return a usable review. Please try again.")
    if ai.get("error_kind") == "timeout":
        reason = "The AI service took too long to respond. Please try again."
    st.error(reason)
    st.caption("No AI-ranked report was produced. Your scripts are still uploaded; choose Find promos to retry.")
    with st.expander("Run details"):
        st.code("\n".join(res.log), language=None)
    if not st.checkbox("Show backup ranking", value=False, key="backup_ranking"):
        st.stop()
    badge = '<span class="pf-mode">Backup ranking · AI review unavailable</span>'
else:
    if ai.get("stopped") or ai.get("failed"):
        st.warning(f'AI reviewed {ai["judged"]} of {ai.get("shortlisted", 0)} shortlisted clips. '
                   'The report includes backup scores for the remaining clips.')
    badge = (f'<span class="pf-mode ai">AI reviewed {ai["judged"]} of '
             f'{ai.get("shortlisted", 0)} shortlisted clips</span>')

if (_timing := timing_note(res)):
    st.warning(_timing, icon=":material/schedule:")
_n_promos = len(res.promos)
_bubble_idle = (f"{_n_promos} promo{'s' if _n_promos != 1 else ''} ready!" if _n_promos
                else "Let's try another script")
st.html(f"""<div class="pf"><div class="pf-report-head"><div><div class="pf-label accent">Promo report</div>
<h1 class="pf-h2">{ui.e(res.title)}</h1><div>{badge}</div></div>
<div class="pf-mascot-stage pf-mascot-stage-report">
<span class="pf-mascot-bubble"><span class="pf-bubble-idle">{_bubble_idle}</span><span class="pf-bubble-hover">Take a look below ↓</span></span>
<span class="pf-spark pf-spark-1"></span><span class="pf-spark pf-spark-2"></span><span class="pf-spark pf-spark-3"></span>
<div class="pf-mascot-bob">{mascot("pf-mascot-mobile")}</div><span class="pf-mascot-shadow"></span>
</div></div>
{ui.run_summary({**s, "ai": {}}, checks)}</div>""")
slug = re.sub(r"\W+", "_", res.title.lower()).strip("_")[:40] or "show"
d1, d2, d3, d4 = st.columns(4)
_dl = ":material/download:"
d1.download_button("Report (PDF)", to_pdf(res), f"{slug}_promo_report.pdf", "application/pdf", width="stretch", icon=_dl)
d2.download_button("Report (HTML)", to_html(res), f"{slug}_promo_report.html", "text/html", width="stretch", icon=_dl)
d3.download_button("Ranked list (CSV)", to_csv(res.promos), f"{slug}_promos_ranked.csv", "text/csv", width="stretch", icon=_dl)
d4.download_button("Everything (JSON)", to_json(res), f"{slug}_promos.json", "application/json", width="stretch", icon=_dl)

tabs = ["Ranked promos", "Top pick", "By episode", "Season map", "All candidates", "Checks"]
if "compare" in st.session_state:
    tabs.append("Rules vs AI")
t = st.tabs(tabs)

with t[0]:
    st.html('<p class="pf" style="font-size:15px;color:var(--mute);margin:4px 0 0">In posting order. Click a row to see how its '
            'score adds up, what to check, and the full cut line by line.</p>')
    c1, c2, c3, c4 = st.columns([2.1, 1.7, 1.4, 1.4], vertical_alignment="bottom")
    kind = c1.segmented_control("Type", ["All", "Single clips", "Stitched"], default="All", key="kind")
    tiers = c2.pills("Tier", ["A", "B", "C"], selection_mode="multi", default=["A", "B", "C"], key="tiers",
                     help="A = strong, B = usable, C = weak")
    clean = c3.toggle("Hide flagged", value=False, help="Hide promos that have something for a human to check")
    order = c4.selectbox("Sort by", ["Posting order", "Score", "Episode"])
    shown = [p for p in res.promos
             if (kind in (None, "All") or (kind == "Single clips") == (p.kind == "single"))
             and ui.tier(p) in (tiers or ["A", "B", "C"]) and not (clean and p.flags)]
    if order == "Score":
        shown.sort(key=lambda p: -p.scores["total"])
    elif order == "Episode":
        shown.sort(key=lambda p: (min(p.episodes), p.segments[0].start))
    st.caption(f"Showing {len(shown)} of {len(res.promos)} promos")
    if shown:
        st.html(f'<div class="pf">{ui.compact_list(shown)}</div>')
    else:
        st.info("No promos match these filters.")

with t[1]:
    def _label(p):
        line = p.hook_beat.text.strip().strip('"')
        return f"#{p.rank} · Ep {' + '.join(map(str, p.episodes))} · {line[:70]}"
    labels = {p.id: _label(p) for p in res.promos}
    if labels:
        pick = st.selectbox("Choose a promo", list(labels), format_func=labels.get)
        p = next(x for x in res.promos if x.id == pick)
        st.html(f'<div class="pf">{ui.spotlight(p, eyebrow=f"Ranked #{p.rank} of {len(res.promos)}")}</div>')

with t[2]:
    have = {p.episodes[0]: p for p in res.by_episode}
    ep_nums = [e.num for e in res.episodes]
    c1, c2 = st.columns([1, 3])
    ep = c1.selectbox("Episode", ep_nums, format_func=lambda n: f"Episode {n}" + ("" if n in have else " (no clip)"))
    epi = next(e for e in res.episodes if e.num == ep)
    c2.html(f'<div class="pf" style="font-size:15px;color:var(--ink2);padding-top:30px">{ui.e(epi.logline)}</div>')
    in_ranked = [p for p in res.promos if ep in p.episodes]
    if in_ranked:
        st.caption("In the ranked list: " + ", ".join(f"#{p.rank}" for p in in_ranked))
    if ep in have:
        st.html(f'<div class="pf">{ui.card(have[ep])}</div>')
    else:
        st.info("No cut in this episode passed the rules (no strong opening line followed by an unresolved ending within 20–60 s).")
    ranked_keys = {cut_key(p) for p in res.promos}
    others = sorted((p for p in res.candidates if p.kind == "single" and p.episodes == [ep]),
                    key=lambda p: -p.scores.get("rules_total", p.scores["total"]))[:8]
    if others:
        st.markdown("**Other candidate cuts in this episode**")
        st.dataframe(pd.DataFrame([{
            "Cut": f"{fmt(p.segments[0].start)} → {fmt(p.segments[0].end)}",
            "Length": f"{p.duration:.0f} s", "Opens on": p.hook_beat.short(70), "Cuts on": p.cliff_beat.short(70),
            "Score": round(100 * p.scores.get("rules_total", p.scores["total"])),
            "Ranked": "yes" if cut_key(p) in ranked_keys else "",
            "To check": " | ".join(p.flags)} for p in others]), hide_index=True, width="stretch")
    st.download_button("Download best clip per episode (CSV)", to_csv(res.by_episode), f"{slug}_promos_by_episode.csv", "text/csv")

with t[3]:
    st.html(f'<div class="pf"><p class="pf-sub" style="margin:4px 0 16px">Where each ranked promo is cut from. Hover a block to see its cut points.</p>'
            f'{ui.season_map(res.episodes, res.promos, res.by_episode, link=False)}</div>')

with t[4]:
    allc = pd.read_csv(io.StringIO(to_csv(sorted(res.candidates, key=lambda p: -p.scores["total"])[:3000])), keep_default_na=False)
    st.html('<p class="pf" style="font-size:15px;color:var(--mute);margin:4px 0 0">Every scored cut, best first. '
            'Use this to check why a cut did or didn\'t make the list.</p>')
    c1, c2, c3 = st.columns([2, 1.4, 1.6], vertical_alignment="bottom")
    epf = c1.multiselect("Episodes", sorted({e.num for e in res.episodes}), placeholder="All episodes")
    kind2 = c2.segmented_control("Type", ["single", "stitched"], selection_mode="multi", default=["single", "stitched"],
                                 format_func=lambda k: "Single clips" if k == "single" else "Stitched", key="kind2")
    mins = c3.slider("Minimum score", 0.0, 1.0, 0.7, 0.01)
    view = allc[allc.total >= mins]
    if epf:
        view = view[view.episodes.astype(str).apply(lambda x: any(str(e) in x.split() for e in epf))]
    if kind2:
        view = view[view.kind.isin(kind2)]
    st.caption(f"Showing {len(view):,} of the top {len(allc):,} candidates")
    st.dataframe(
        view[["rank", "segments", "duration_s", "hook", "cliffhanger", "total", "hook_score", "cliff_score", "standalone", "kind", "flags"]],
        hide_index=True, height=560,
        column_config={
            "rank": st.column_config.TextColumn("Rank", width="small"),
            "segments": st.column_config.TextColumn("Cut points", width="medium"),
            "duration_s": st.column_config.NumberColumn("Length", format="%.0f s", width="small"),
            "hook": st.column_config.TextColumn("Opens on", width="large"),
            "cliffhanger": st.column_config.TextColumn("Cuts on", width="large"),
            "total": st.column_config.ProgressColumn("Score", min_value=0, max_value=1, format="%.2f"),
            "hook_score": st.column_config.ProgressColumn("Hook", min_value=0, max_value=1, format="%.2f"),
            "cliff_score": st.column_config.ProgressColumn("Cliffhanger", min_value=0, max_value=1, format="%.2f"),
            "standalone": st.column_config.ProgressColumn("New viewer", min_value=0, max_value=1, format="%.2f"),
            "kind": st.column_config.TextColumn("Type", width="small"),
            "flags": st.column_config.TextColumn("To check", width="medium"),
        })

with t[5]:
    st.html(f'<div class="pf" style="margin-top:4px">{ui.checks_panel(checks)}</div>')
    with st.expander("Run log"):
        st.code("\n".join(res.log), language=None)

if "compare" in st.session_state:
    with t[6]:
        rules_res, cmp = st.session_state.compare
        if cmp["mock"]:
            st.warning("Mock judge: these 'AI' scores are fake test values.")
        st.markdown(compare_md(rules_res, res, cmp))
        st.download_button("Download comparison (CSV)", compare_csv(cmp), f"{slug}_ai_vs_rules.csv", "text/csv")
