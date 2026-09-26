import streamlit as st
import pandas as pd
import numpy as np

from pathlib import Path
import json
import os
import re
import tempfile
import time
import shutil
import hashlib
import uuid
import html
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


# Keep the app palette authoritative even when an older Streamlit theme is deployed.
# Streamlit serializes these server theme options for native widgets and tables.
from streamlit import config as _theme_config

_cool_theme = {
    "primaryColor": "#F59AC7", "backgroundColor": "#FFF9FD",
    "secondaryBackgroundColor": "#FFEAF5", "textColor": "#5A3552",
    "borderColor": "#E9BDD2", "dataframeBorderColor": "#E9BDD2",
    "dataframeHeaderBackgroundColor": "#FFE0EE", "codeBackgroundColor": "#FFF0F8",
    "linkColor": "#F07AB2", "codeTextColor": "#8A647F",
    "chartCategoricalColors": ["#F59AC7", "#D9B8FF", "#FFBCD8", "#BFE8FF"],
    "chartSequentialColors": ["#FFF9FD", "#FFF0F8", "#FFE0EE", "#FFBCD8", "#F59AC7", "#D9B8FF"],
    "chartDivergingColors": ["#D9B8FF", "#BFE8FF", "#FFF9FD", "#FFBCD8", "#F59AC7"],
}
for _hue in ("red", "orange", "yellow", "blue", "green", "violet", "gray"):
    _cool_theme.update({_hue + "Color": "#F59AC7", _hue + "BackgroundColor": "#FFEAF5",
                        _hue + "TextColor": "#8A647F"})
_theme_options = _theme_config.get_config_options()
_theme_changed = False
for _scope in ("theme", "theme.sidebar", "theme.light", "theme.light.sidebar", "theme.dark", "theme.dark.sidebar"):
    for _name, _value in _cool_theme.items():
        if _scope + "." + _name in _theme_options:
            _theme_changed |= _theme_config.get_option(_scope + "." + _name) != _value
            _theme_config.set_option(_scope + "." + _name, _value)
_theme_changed |= _theme_config.get_option("theme.base") != "light"
_theme_config.set_option("theme.base", "light")
if _theme_changed:
    # Theme metadata is sent before the script starts; resend it after an override.
    st.rerun()

st.set_page_config(page_title="Femboy Investing", page_icon="🎀", layout="wide")



# =========================================================
# LOCAL / DISK CACHE
# =========================================================
#
# On a normal local computer this survives app restarts.
# On Streamlit Community Cloud the filesystem is temporary, so it normally
# survives reruns while the app instance is alive but can disappear after a
# reboot/redeploy. st.cache_data still gives an additional in-memory layer.
# =========================================================

PRICE_CACHE_TTL = 6 * 60 * 60
FUNDAMENTAL_CACHE_TTL = 12 * 60 * 60
EARNINGS_CACHE_TTL = 6 * 60 * 60
NEWS_CACHE_TTL = 60 * 60
FAST_SCREEN_CACHE_TTL = 30 * 60


def _make_cache_root():
    candidates = [
        Path.cwd() / ".stock_signal_cache_v10",
        Path(tempfile.gettempdir()) / "stock_signal_cache_v10",
    ]

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            return candidate
        except Exception:
            continue

    return Path(tempfile.gettempdir())


LOCAL_CACHE_ROOT = _make_cache_root()

for _folder in ["prices", "json", "screens"]:
    try:
        (LOCAL_CACHE_ROOT / _folder).mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
