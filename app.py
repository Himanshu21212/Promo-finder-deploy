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
from promo_finder.report import to_csv, to_html, to_json, to_markdown
from promo_finder.usage import SarvamConfig

ROOT = Path(__file__).parent
st.set_page_config(page_title="Promo Finder", page_icon=str(ROOT / "static" / "favicon.png"),
                   layout="wide", initial_sidebar_state="expanded")



st.markdown("""<style>
/* 1. Reduce top padding on results page & enlarge mascot header */
.main .block-container {
    padding-top: 0.5rem !important;
}
.pf-report-head {
    margin-top: -10px !important;
    padding-top: 0 !important;
    align-items: center !important;
}

/* 2. Hide default Streamlit header */
header[data-testid="stHeader"] { display: none !important; }

.pf{--bg:#f6f6f3;--surface:#surface;--surface2:#f4f4f1;
st.markdown("""<style>
.main .block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 1.4rem !important;
}
</style>""", unsafe_allow_html=True)
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
    return f'<div style="display:flex;align-items:center;justify-content:center;width:100%;height:100%">{artwork.get(name, "")}</div>'

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
        if suffix not in {".zip", ".txt"}:
            errors.append(f"{uploaded.name}: only ZIP and TXT files are accepted.")
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
    /* Force Streamlit container to eliminate upper whitespace */
    [data-testid="stAppViewContainer"] .main .block-container {
        padding-top: 0.5rem !important;
    }
    /* Pull the header card up over Streamlit's default container padding */
    .pf-page-head {
        margin-top: -45px !important;
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
  <p>Upload a ZIP of episode .txt files or individual .txt screenplays. Promo Finder reads dialogue, action and source timestamps, and reports files or blocks it cannot parse.</p></article>
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
  <p>Editors inspect the ranked list, top pick, episode library, season map and quality checks. Download HTML, CSV, JSON and Markdown reports to take the cut points into editing.</p></article>
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
                  type="secondary", on_click=new_analysis)

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
        + '<div style="font-size:27px;color:#E11D26;text-align:center;align-self:center">→</div>'
        + process_step(2, "list", "Review the strongest moments",
                       "Ranked 20–60 second cuts, with hooks and cliffhangers.")
        + '<div style="font-size:27px;color:#E11D26;text-align:center;align-self:center">→</div>'
        + process_step(3, "clapper", "Take it to your editor",
                       "Exact cut points, editorial notes and reports to share.")
    )
    st.html(f"""
<div style="display:flex;align-items:center;justify-content:space-between;gap:20px;min-height:158px;margin:0 0 14px">
  <div style="flex:1 1 auto;min-width:0;max-width:820px">
    <div style="font-size:15px;line-height:1.2;font-weight:700;letter-spacing:.5px;color:#E11D26;text-transform:uppercase">PROMO FINDER</div>
    <h1 style="font-family:Inter,system-ui,sans-serif;font-size:56px;line-height:1.04;letter-spacing:-1.8px;font-weight:750;color:#1A1A1C;margin:10px 0 12px">
      Find the moments<br><span style="color:#E11D26">worth promoting</span>
    </h1>
    <p style="font-size:18px;line-height:1.45;color:#5B5B63;margin:0;max-width:820px">
      Find ranked 20–60 second promo cuts, with hooks and cliffhangers ready for your editor.
    </p>
  </div>
  <div style="position:relative;display:flex;align-items:center;justify-content:center;width:230px;min-width:210px;height:160px;overflow:hidden">
    {mascot("pf-mascot-welcome")}
  </div>
</div>
<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));align-items:center;margin:8px 0 24px">
  {features}
</div>
""")

    with st.container(key="home_upload_panel"):
        st.html(
            '<div style="text-align:center;padding:0 0 12px">'
            '<div style="font-size:24px;line-height:1.2;font-weight:700;letter-spacing:-.55px;color:#1A1A1C">'
            'Upload your microdrama scripts</div>'
            '<div style="font-size:14px;color:#5B5B63;margin-top:4px">'
            'Drag & drop a ZIP or TXT file here.</div></div>'
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
            "Upload your microdrama scripts", type=["zip", "txt"], accept_multiple_files=True,
            key=upload_key, on_change=select_uploads, args=(upload_key,),
            label_visibility="collapsed", max_upload_size=50,
        )

        upload_error = st.session_state.get("upload_error", "")
        if upload_error:
            st.html(f'<div style="padding:8px 12px;margin:8px auto;max-width:500px;border:1px solid #F3B7BA;'
                    f'background:#FFF1F1;border-radius:8px;color:#B4232A;font-size:13px;line-height:1.4;text-align:center;">'
                    f'{html_escape(upload_error)}</div>')

        st.html('<div style="height:12px"></div>')
        input_col, button_col = st.columns([2.5, 1.2], gap="small", vertical_alignment="bottom")
        
        with input_col:
            home_title = st.text_input(
                "Show title (optional)",
                key="home_title",
                placeholder="e.g. The Maid Was the Heiress",
                on_change=sync_title,
                args=("home_title", "show_title"),
            )
        with button_col:
            go = st.button("Find Promos", key="find_home", type="primary",
                           use_container_width=True, disabled=not files)
            
        if go:
            title = home_title

    if not go:
        st.html(f'<div style="display:grid;grid-template-columns:minmax(0,1fr) 28px minmax(0,1fr) 28px minmax(0,1fr);'
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
        st.error("No timestamped episodes found. Each script needs blocks like '**SPEAKER:**' followed by "
                 "'Start: (MM:SS.ss) | End: (MM:SS.ss)'.")
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

st.html(f"""<div class="pf"><div class="pf-report-head"><div><div class="pf-label accent">Promo report</div>
<h1 class="pf-h2">{ui.e(res.title)}</h1><div>{badge}</div></div>{mascot("pf-mascot-mobile")}</div>
{ui.run_summary({**s, "ai": {}}, checks)}</div>""")
slug = re.sub(r"\W+", "_", res.title.lower()).strip("_")[:40] or "show"
d1, d2, d3, d4 = st.columns(4)
d1.download_button("Report (HTML)", to_html(res), f"{slug}_promo_report.html", "text/html", width="stretch")
d2.download_button("Ranked list (CSV)", to_csv(res.promos), f"{slug}_promos_ranked.csv", "text/csv", width="stretch")
d3.download_button("Everything (JSON)", to_json(res), f"{slug}_promos.json", "application/json", width="stretch")
d4.download_button("Summary (Markdown)", to_markdown(res), f"{slug}_promos.md", "text/markdown", width="stretch")

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
