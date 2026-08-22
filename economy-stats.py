import sqlite3
import json
import re
import csv
import math
import statistics
import copy
import random
import os
import sys
import time
import ctypes
from ctypes import wintypes
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from functools import lru_cache

# When running as a normal .py file, use the script's folder.
# When packaged with PyInstaller, __file__ points inside the temporary
# extraction folder for a one-file build, so use the executable's real folder
# instead. This makes a database placed beside EconomyAnalytics.exe work.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(
        sys.executable
    ).resolve().parent
else:
    BASE_DIR = Path(
        __file__
    ).resolve().parent

DB_PATH = BASE_DIR / "economy-stats.dht"
TABLE_NAME = "message_embeds"

THEMES = {
    "dark": {
        # Soft charcoal dark mode. Intentionally avoids pure black so the
        # interface feels dark without looking flat or harsh.
        "APP_BG": "#19191F",
        "SIDEBAR_BG": "#202027",
        "SIDEBAR_HOVER": "#2D2D36",
        "PRIMARY": "#7C3AED",
        "PRIMARY_HOVER": "#8B5CF6",
        "TEXT": "#F4F4F5",
        "MUTED": "#A7A7B3",
        "CARD": "#23232A",
        "BORDER": "#3A3A46",
        "SOFT_BLUE": "#30284A",
        "SOFT_GREEN": "#1D392A",
        "SOFT_AMBER": "#46371E",
        "GREEN": "#4ADE80",
        "AMBER": "#FBBF24",
        "INFO_BG": "#27272F",
        "SECONDARY_BG": "#303039",
        "SECONDARY_HOVER": "#3A3A45",
        "TABLE_HEADER_BG": "#303039",
        "TABLE_ALT": "#292930",
        "DEEP_BG": "#1E1E25",
        "SIDEBAR_TEXT": "#F7F7FA",
        "ACCENT_TEXT": "#B79BFF",
    },
    "light": {
        "APP_BG": "#F5F5F7",
        "SIDEBAR_BG": "#FFFFFF",
        "SIDEBAR_HOVER": "#F0ECFA",
        "PRIMARY": "#7C3AED",
        "PRIMARY_HOVER": "#6D28D9",
        "TEXT": "#111827",
        "MUTED": "#6B7280",
        "CARD": "#FFFFFF",
        "BORDER": "#D8DAE1",
        "SOFT_BLUE": "#EEE7FF",
        "SOFT_GREEN": "#DCFCE7",
        "SOFT_AMBER": "#FEF3C7",
        "GREEN": "#15803D",
        "AMBER": "#B45309",
        "INFO_BG": "#FAFAFC",
        "SECONDARY_BG": "#F1F2F6",
        "SECONDARY_HOVER": "#E4E6EC",
        "TABLE_HEADER_BG": "#F1F2F6",
        "TABLE_ALT": "#F8F8FA",
        "DEEP_BG": "#F3F4F6",
        "SIDEBAR_TEXT": "#111827",
        "ACCENT_TEXT": "#6D28D9",
    },
}

THEME_NAME = "dark"


def apply_theme_globals(theme_name):
    global APP_BG, SIDEBAR_BG, SIDEBAR_HOVER
    global PRIMARY, PRIMARY_HOVER, TEXT, MUTED, CARD, BORDER
    global SOFT_BLUE, SOFT_GREEN, SOFT_AMBER, GREEN, AMBER
    global INFO_BG, SECONDARY_BG, SECONDARY_HOVER
    global TABLE_HEADER_BG, TABLE_ALT, DEEP_BG
    global SIDEBAR_TEXT, ACCENT_TEXT

    palette = THEMES[theme_name]

    APP_BG = palette["APP_BG"]
    SIDEBAR_BG = palette["SIDEBAR_BG"]
    SIDEBAR_HOVER = palette["SIDEBAR_HOVER"]
    PRIMARY = palette["PRIMARY"]
    PRIMARY_HOVER = palette["PRIMARY_HOVER"]
    TEXT = palette["TEXT"]
    MUTED = palette["MUTED"]
    CARD = palette["CARD"]
    BORDER = palette["BORDER"]
    SOFT_BLUE = palette["SOFT_BLUE"]
    SOFT_GREEN = palette["SOFT_GREEN"]
    SOFT_AMBER = palette["SOFT_AMBER"]
    GREEN = palette["GREEN"]
    AMBER = palette["AMBER"]
    INFO_BG = palette["INFO_BG"]
    SECONDARY_BG = palette["SECONDARY_BG"]
    SECONDARY_HOVER = palette["SECONDARY_HOVER"]
    TABLE_HEADER_BG = palette["TABLE_HEADER_BG"]
    TABLE_ALT = palette["TABLE_ALT"]
    DEEP_BG = palette["DEEP_BG"]
    SIDEBAR_TEXT = palette["SIDEBAR_TEXT"]
    ACCENT_TEXT = palette["ACCENT_TEXT"]


apply_theme_globals(THEME_NAME)

USER_RE = re.compile(r"\*\*User:\*\*\s*<@!?(\d+)>", re.IGNORECASE)
CASH_RE = re.compile(r"Cash:\s*`?\s*([+-]?\s*[\d,]+)\s*`?", re.IGNORECASE)
BANK_RE = re.compile(r"Bank:\s*`?\s*([+-]?\s*[\d,]+)\s*`?", re.IGNORECASE)
REASON_RE = re.compile(r"\*\*Reason:\*\*\s*(.*)", re.IGNORECASE | re.DOTALL)
CHANNEL_MENTION_RE = re.compile(r"<#\d+>")
USER_MENTION_RE = re.compile(r"<@!?\d+>")
ROLE_MENTION_RE = re.compile(r"<@&\d+>")
LOCAL_TZ = datetime.now().astimezone().tzinfo

GAME_ORDER = [
    "blackjack",
    "cockfight",
    "roulette",
    "russian roulette",
    "slot machine",
    "higher or lower",
    "animal race",
]

# These games use the normal UnbelievaBoat min/max bet-limit settings.
# Animal Race is intentionally excluded because its allowed bet is tied to
# the selected animal's price rather than a normal global bet-limit setting.
BET_LIMIT_GAMES = [
    "blackjack",
    "cockfight",
    "roulette",
    "russian roulette",
    "slot machine",
    "higher or lower",
]

# The target optimizer should not solve the economy by making one or two games
# absurdly profitable. It softly tries to keep these configurable games
# beneficial and relevant at the same time.
#
# Russian Roulette is intentionally excluded because it is allowed to remain
# a bad/high-risk option. Animal Race is excluded from this balancing objective
# because its normal profitability cannot be directly tuned through the same
# global settings as the games below.
BALANCED_OPTIMIZER_GAMES = [
    "blackjack",
    "cockfight",
    "roulette",
    "slot machine",
    "higher or lower",
]

GAME_DISPLAY = {
    "blackjack": "Blackjack",
    "cockfight": "Cock Fight",
    "roulette": "Roulette",
    "russian roulette": "Russian Roulette",
    "slot machine": "Slot Machine",
    "higher or lower": "Higher or Lower",
    "animal race": "Animal Race",
}

GAME_COMMAND_NAMES = {
    "blackjack": "blackjack",
    "cockfight": "cock-fight",
    "roulette": "roulette",
    "russian roulette": "russian-roulette",
    "slot machine": "slot-machine",
    "higher or lower": "higher-lower",
}

DEFAULT_GAME_LIMITS = {
    "blackjack": {"min": 75, "max": 750},
    "cockfight": {"min": 75, "max": 300},
    "roulette": {"min": 75, "max": 300},
    "russian roulette": {"min": 75, "max": 1000},
    "slot machine": {"min": 75, "max": 200},
    "higher or lower": {"min": 75, "max": 100},
}

DEFAULT_CURRENT_GAMES_PER_5M = 2
DEFAULT_BLACKJACK_DECKS = 2
DEFAULT_SLOT_SYMBOLS = 2
DEFAULT_SLOT_MULTIPLIER = 4.1
DEFAULT_COCKFIGHT_START = 55.0
DEFAULT_COCKFIGHT_MAX = 99.0
DEFAULT_CHICKEN_PRICE = 20.0

ACTIVITY_GROUP_NAMES = [
    "Very Casual",
    "Casual",
    "Regular",
    "Active",
    "Very Active",
]

ACTIVITY_GROUP_BASIS_OPTIONS = [
    "Combined activity",
    "Estimated active hours",
    "Transactions",
]


def parse_number(value):
    if value is None:
        return 0

    value = (
        str(value)
        .replace(",", "")
        .replace(" ", "")
        .replace("`", "")
    )

    try:
        return int(value)
    except ValueError:
        return 0


def parse_float(value):
    value = str(value).strip().replace(",", ".")

    if not value:
        raise ValueError("A numeric field is empty.")

    return float(value)


def parse_int(value):
    return int(round(parse_float(value)))


def parse_timestamp(value):
    if not value:
        return None

    try:
        value = str(value).strip()

        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        return None


def parse_user_datetime(value, end_of_day=False):
    value = value.strip()

    if not value:
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
    ]

    parsed = None

    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
            break
        except ValueError:
            continue

    if parsed is None:
        raise ValueError(
            "Invalid date/time.\n\n"
            "Examples:\n"
            "2026-08-20 08:30\n"
            "2026-08-20\n"
            "20-08-2026 08:30"
        )

    if end_of_day and ":" not in value:
        parsed = parsed.replace(
            hour=23,
            minute=59,
            second=59,
            microsecond=999999,
        )

    parsed = parsed.replace(tzinfo=LOCAL_TZ)

    return parsed.astimezone(timezone.utc)


def to_local_string(dt):
    if dt is None:
        return ""

    return (
        dt.astimezone(LOCAL_TZ)
        .strftime("%Y-%m-%d %H:%M:%S")
    )


def clean_reason(reason):
    reason = str(reason).strip()

    reason = re.sub(
        r"\s+in\s+<#\d+>",
        "",
        reason,
        flags=re.IGNORECASE,
    )

    reason = CHANNEL_MENTION_RE.sub("", reason)
    reason = USER_MENTION_RE.sub("<@user>", reason)
    reason = ROLE_MENTION_RE.sub("<@role>", reason)

    reason = re.sub(
        r"\s+",
        " ",
        reason,
    )

    reason = re.sub(
        r"\s+\bin\b\s*$",
        "",
        reason,
        flags=re.IGNORECASE,
    )

    return reason.strip()


def is_chicken_purchase(reason):
    return bool(
        re.match(
            r"^buy\s+item\s*\(\s*chicken\s*\)",
            clean_reason(reason).lower(),
        )
    )


def is_animal_race_purchase(reason):
    """Return True for animal/provision purchases used by Animal Race."""
    lower = clean_reason(reason).lower()

    return (
        lower.startswith("buy animal")
        or lower.startswith("buy provision")
        or lower.startswith("animals buy")
        or lower.startswith("provisions buy")
    )


def canonical_reason(
    reason,
    chicken_as_cockfight=True,
):
    cleaned = clean_reason(reason)
    lower = cleaned.lower()

    if (
        chicken_as_cockfight
        and is_chicken_purchase(cleaned)
    ):
        return "cockfight"

    if lower.startswith("blackjack"):
        return "blackjack"

    if (
        lower.startswith("slot-machine")
        or lower.startswith("slot machine")
    ):
        return "slot machine"

    if (
        lower.startswith("cockfight")
        or lower.startswith("cock-fight")
        or lower.startswith("chicken-fight")
    ):
        return "cockfight"

    if (
        lower.startswith("higher-lower")
        or lower.startswith("higher lower")
        or lower.startswith("higher or lower")
    ):
        return "higher or lower"

    if (
        lower.startswith("russian-roulette")
        or lower.startswith("russian roulette")
    ):
        return "russian roulette"

    if lower.startswith("roulette"):
        return "roulette"

    if (
        lower.startswith("animal race")
        or lower.startswith("animal-race")
        or is_animal_race_purchase(cleaned)
    ):
        return "animal race"

    if (
        lower.startswith("rob successful")
        or lower.startswith("rob fine")
        or lower == "robbed"
        or lower.startswith("robbed ")
    ):
        return "rob"

    if (
        lower.startswith("buy item")
        or lower.startswith("buy provision")
        or lower.startswith("buy animal")
        or lower.startswith("buy ")
    ):
        return "buy"

    if lower.startswith("chat money"):
        return "chat money"

    if lower.startswith("work command"):
        return "work"

    if lower.startswith("crime command"):
        return "crime"

    if lower.startswith("slut command"):
        return "slut"

    if lower.startswith("add-money command"):
        return "add money"

    if lower.startswith("remove-money command"):
        return "remove money"

    if lower.startswith("role income"):
        return "role income"

    return cleaned


def game_from_reason(reason):
    cleaned = clean_reason(reason)
    lower = cleaned.lower()

    if is_chicken_purchase(cleaned):
        return "cockfight"

    if lower.startswith("blackjack"):
        return "blackjack"

    if (
        lower.startswith("cockfight")
        or lower.startswith("cock-fight")
        or lower.startswith("chicken-fight")
    ):
        return "cockfight"

    if (
        lower.startswith("slot-machine")
        or lower.startswith("slot machine")
    ):
        return "slot machine"

    if (
        lower.startswith("higher-lower")
        or lower.startswith("higher lower")
        or lower.startswith("higher or lower")
    ):
        return "higher or lower"

    if (
        lower.startswith("russian-roulette")
        or lower.startswith("russian roulette")
    ):
        return "russian roulette"

    if lower.startswith("roulette"):
        return "roulette"

    if (
        lower.startswith("animal race")
        or lower.startswith("animal-race")
        or is_animal_race_purchase(cleaned)
    ):
        return "animal race"

    return None


def is_explicit_bet_reason(reason):
    lower = clean_reason(reason).lower()

    if "return bet" in lower:
        return False

    return (
        lower.endswith(" bet")
        or " bet " in lower
    )


def format_number(
    value,
    decimals=2,
):
    if value is None:
        return ""

    if isinstance(value, bool):
        return str(value)

    if isinstance(value, int):
        return f"{value:,}"

    if isinstance(value, float):
        if math.isnan(value):
            return ""

        if math.isinf(value):
            return "INF"

        return f"{value:,.{decimals}f}"

    return str(value)


def format_compact(value):
    try:
        value = float(value)
    except Exception:
        return str(value)

    sign = "-" if value < 0 else ""
    value = abs(value)

    if value >= 1_000_000_000:
        return (
            f"{sign}"
            f"{value / 1_000_000_000:.2f}B"
        )

    if value >= 1_000_000:
        return (
            f"{sign}"
            f"{value / 1_000_000:.2f}M"
        )

    if value >= 1_000:
        return (
            f"{sign}"
            f"{value / 1_000:.2f}K"
        )

    return f"{sign}{value:,.0f}"



DISCORD_SAFE_MESSAGE_LENGTH = 1900

DISCORD_HEADER_NAMES = {
    "Net Profit": "Net",
    "Gross Earned": "Earned",
    "Gross Lost": "Lost",
    "Net / Hour": "Net/h",
    "Transactions": "Tx",
    "Unique Users": "Users",
    "People using economy": "Users",
    "Est. Active Hrs": "Active h",
    "Estimated Active Hours": "Active h",
    "Activity %": "Active %",
    "Economy Activity %": "Active %",
    "Active Days": "Days",
    "Estimated Sessions": "Sessions",
    "Sessions": "Sessions",
    "Top Income Source": "Top Source",
    "Top Loss Source": "Top Loss",
    "30d Net": "30d Net",
    "30d Projected Net": "30d Net",
    "24h Current Games": "Cur Plays",
    "24h Proposed Games": "New Plays",
    "Current Avg Bet": "Cur Bet",
    "Proposed Avg Bet": "New Bet",
    "24h Current Net": "Cur Net",
    "24h Proposed Net": "New Net",
    "24h Change": "Change",
    "Proposed Win %": "Win %",
    "Avg Active Hrs / Day": "Hrs/day",
    "Avg Transactions / Day": "Tx/day",
    "Avg Active Days / 30d": "Days/30d",
    "Avg 24h Net": "24h Net",
    "Avg 30d Net": "30d Net",
    "Users Played": "Players",
    "Participation %": "Play %",
    "Avg Plays / Player / Day": "Plays/p/day",
    "Avg Bet": "Avg Bet",
    "Net / Play": "Net/play",
    "Avg 24h Net / Member": "Net/m/24h",
    "Avg 30d Net / Member": "Net/m/30d",
    "Active Hrs / Day": "Hrs/day",
    "Transactions / Day": "Tx/day",
}


def discord_clean_text(value):
    text = str(value)

    # Prevent pasted data from accidentally terminating a Discord code block.
    text = text.replace("```", "~~~")
    text = text.replace("\t", " ")
    text = text.replace("\r", " ")
    text = text.replace("\n", " ")

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def discord_compact_number(value):
    try:
        number = float(value)
    except Exception:
        return discord_clean_text(value)

    if math.isnan(number):
        return ""

    if math.isinf(number):
        return "INF" if number > 0 else "-INF"

    absolute = abs(number)

    if absolute >= 1_000_000_000:
        result = f"{number / 1_000_000_000:.2f}B"
    elif absolute >= 1_000_000:
        result = f"{number / 1_000_000:.2f}M"
    elif absolute >= 10_000:
        result = f"{number / 1_000:.1f}K"
    elif absolute >= 1_000:
        result = f"{number:,.0f}"
    elif float(number).is_integer():
        result = f"{int(number):,}"
    else:
        result = f"{number:,.2f}"

    return result


def discord_short_value(value, column=""):
    if isinstance(value, bool):
        return str(value)

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return discord_compact_number(
            value
        )

    text = discord_clean_text(
        value
    )

    limits = {
        "Original Reason": 30,
        "Reason": 20,
        "User ID": 20,
        "Username": 24,
        "Timestamp": 19,
        "First Seen": 19,
        "Last Seen": 19,
        "Game Mix": 28,
        "Top Income Source": 18,
        "Top Loss Source": 18,
        "Statistic": 26,
        "Value": 32,
        "Group": 14,
        "Game": 18,
    }

    maximum = limits.get(
        column,
        16,
    )

    if len(text) > maximum:
        text = (
            text[:max(
                1,
                maximum - 1,
            )]
            + "…"
        )

    return text


def discord_trim_message(
    text,
    limit=DISCORD_SAFE_MESSAGE_LENGTH,
):
    text = str(text).strip()

    if len(text) <= limit:
        return text

    suffix = (
        "\n\n*Trimmed to fit in one Discord message.*"
    )

    allowed = max(
        0,
        limit - len(suffix),
    )

    trimmed = text[:allowed].rstrip()

    sentence = max(
        trimmed.rfind(". "),
        trimmed.rfind("\n"),
    )

    if sentence >= int(
        allowed * 0.75
    ):
        trimmed = trimmed[
            :sentence + 1
        ].rstrip()

    return (
        trimmed
        + suffix
    )



def copy_widget_image_to_clipboard(
    widget,
):
    """Copy the exact rendered Tk widget image to the Windows clipboard.

    This uses only the Python standard library and the Windows GDI API. It
    captures the widget's client area, converts it to a device-independent
    bitmap, and puts that image on the clipboard so it can be pasted directly
    into Discord, Paint, image editors, etc.
    """
    if os.name != "nt":
        raise RuntimeError(
            "Copy Plot Image is currently supported on Windows."
        )

    widget.update_idletasks()
    widget.update()

    width = int(
        widget.winfo_width()
    )
    height = int(
        widget.winfo_height()
    )

    if width <= 1 or height <= 1:
        raise RuntimeError(
            "The plot is not large enough to copy yet."
        )

    hwnd = wintypes.HWND(
        widget.winfo_id()
    )

    user32 = ctypes.WinDLL(
        "user32",
        use_last_error=True,
    )
    gdi32 = ctypes.WinDLL(
        "gdi32",
        use_last_error=True,
    )
    kernel32 = ctypes.WinDLL(
        "kernel32",
        use_last_error=True,
    )

    class BITMAPINFOHEADER(
        ctypes.Structure
    ):
        _fields_ = [
            (
                "biSize",
                wintypes.DWORD,
            ),
            (
                "biWidth",
                wintypes.LONG,
            ),
            (
                "biHeight",
                wintypes.LONG,
            ),
            (
                "biPlanes",
                wintypes.WORD,
            ),
            (
                "biBitCount",
                wintypes.WORD,
            ),
            (
                "biCompression",
                wintypes.DWORD,
            ),
            (
                "biSizeImage",
                wintypes.DWORD,
            ),
            (
                "biXPelsPerMeter",
                wintypes.LONG,
            ),
            (
                "biYPelsPerMeter",
                wintypes.LONG,
            ),
            (
                "biClrUsed",
                wintypes.DWORD,
            ),
            (
                "biClrImportant",
                wintypes.DWORD,
            ),
        ]

    class RGBQUAD(
        ctypes.Structure
    ):
        _fields_ = [
            (
                "rgbBlue",
                ctypes.c_ubyte,
            ),
            (
                "rgbGreen",
                ctypes.c_ubyte,
            ),
            (
                "rgbRed",
                ctypes.c_ubyte,
            ),
            (
                "rgbReserved",
                ctypes.c_ubyte,
            ),
        ]

    class BITMAPINFO(
        ctypes.Structure
    ):
        _fields_ = [
            (
                "bmiHeader",
                BITMAPINFOHEADER,
            ),
            (
                "bmiColors",
                RGBQUAD * 1,
            ),
        ]

    # Function signatures matter on 64-bit Windows because handles are pointer
    # sized. Without explicit restypes, ctypes can truncate them.
    user32.GetDC.argtypes = [
        wintypes.HWND,
    ]
    user32.GetDC.restype = wintypes.HDC

    user32.ReleaseDC.argtypes = [
        wintypes.HWND,
        wintypes.HDC,
    ]
    user32.ReleaseDC.restype = ctypes.c_int

    user32.OpenClipboard.argtypes = [
        wintypes.HWND,
    ]
    user32.OpenClipboard.restype = wintypes.BOOL

    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL

    user32.SetClipboardData.argtypes = [
        wintypes.UINT,
        wintypes.HANDLE,
    ]
    user32.SetClipboardData.restype = wintypes.HANDLE

    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL

    gdi32.CreateCompatibleDC.argtypes = [
        wintypes.HDC,
    ]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC

    gdi32.DeleteDC.argtypes = [
        wintypes.HDC,
    ]
    gdi32.DeleteDC.restype = wintypes.BOOL

    gdi32.CreateCompatibleBitmap.argtypes = [
        wintypes.HDC,
        ctypes.c_int,
        ctypes.c_int,
    ]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP

    gdi32.SelectObject.argtypes = [
        wintypes.HDC,
        wintypes.HGDIOBJ,
    ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ

    gdi32.DeleteObject.argtypes = [
        wintypes.HGDIOBJ,
    ]
    gdi32.DeleteObject.restype = wintypes.BOOL

    gdi32.BitBlt.argtypes = [
        wintypes.HDC,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HDC,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.DWORD,
    ]
    gdi32.BitBlt.restype = wintypes.BOOL

    gdi32.GetDIBits.argtypes = [
        wintypes.HDC,
        wintypes.HBITMAP,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        ctypes.POINTER(
            BITMAPINFO
        ),
        wintypes.UINT,
    ]
    gdi32.GetDIBits.restype = ctypes.c_int

    kernel32.GlobalAlloc.argtypes = [
        wintypes.UINT,
        ctypes.c_size_t,
    ]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL

    kernel32.GlobalLock.argtypes = [
        wintypes.HGLOBAL,
    ]
    kernel32.GlobalLock.restype = ctypes.c_void_p

    kernel32.GlobalUnlock.argtypes = [
        wintypes.HGLOBAL,
    ]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    kernel32.GlobalFree.argtypes = [
        wintypes.HGLOBAL,
    ]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL

    SRCCOPY = 0x00CC0020
    DIB_RGB_COLORS = 0
    BI_RGB = 0
    CF_DIB = 8
    GMEM_MOVEABLE = 0x0002

    source_dc = None
    memory_dc = None
    bitmap = None
    old_object = None
    global_memory = None
    clipboard_open = False
    transferred = False

    try:
        source_dc = user32.GetDC(
            hwnd
        )
        if not source_dc:
            raise ctypes.WinError(
                ctypes.get_last_error()
            )

        memory_dc = (
            gdi32.CreateCompatibleDC(
                source_dc
            )
        )
        if not memory_dc:
            raise ctypes.WinError(
                ctypes.get_last_error()
            )

        bitmap = (
            gdi32.CreateCompatibleBitmap(
                source_dc,
                width,
                height,
            )
        )
        if not bitmap:
            raise ctypes.WinError(
                ctypes.get_last_error()
            )

        old_object = gdi32.SelectObject(
            memory_dc,
            bitmap,
        )

        if not gdi32.BitBlt(
            memory_dc,
            0,
            0,
            width,
            height,
            source_dc,
            0,
            0,
            SRCCOPY,
        ):
            raise RuntimeError(
                "Windows could not capture the plot image."
            )

        image_size = (
            width
            * height
            * 4
        )

        bitmap_info = BITMAPINFO()
        bitmap_info.bmiHeader.biSize = (
            ctypes.sizeof(
                BITMAPINFOHEADER
            )
        )
        bitmap_info.bmiHeader.biWidth = (
            width
        )
        bitmap_info.bmiHeader.biHeight = (
            height
        )
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap_info.bmiHeader.biCompression = (
            BI_RGB
        )
        bitmap_info.bmiHeader.biSizeImage = (
            image_size
        )

        pixel_buffer = (
            ctypes.create_string_buffer(
                image_size
            )
        )

        scan_lines = gdi32.GetDIBits(
            memory_dc,
            bitmap,
            0,
            height,
            pixel_buffer,
            ctypes.byref(
                bitmap_info
            ),
            DIB_RGB_COLORS,
        )

        if scan_lines != height:
            raise RuntimeError(
                "Windows could not convert the plot image for the clipboard."
            )

        header_size = ctypes.sizeof(
            BITMAPINFOHEADER
        )
        clipboard_size = (
            header_size
            + image_size
        )

        global_memory = (
            kernel32.GlobalAlloc(
                GMEM_MOVEABLE,
                clipboard_size,
            )
        )
        if not global_memory:
            raise ctypes.WinError(
                ctypes.get_last_error()
            )

        memory_pointer = (
            kernel32.GlobalLock(
                global_memory
            )
        )
        if not memory_pointer:
            raise ctypes.WinError(
                ctypes.get_last_error()
            )

        try:
            ctypes.memmove(
                memory_pointer,
                ctypes.byref(
                    bitmap_info.bmiHeader
                ),
                header_size,
            )
            ctypes.memmove(
                memory_pointer
                + header_size,
                pixel_buffer,
                image_size,
            )
        finally:
            kernel32.GlobalUnlock(
                global_memory
            )

        # The clipboard can temporarily be busy, so retry briefly instead of
        # failing if another app has it open for a few milliseconds.
        for _ in range(12):
            if user32.OpenClipboard(
                hwnd
            ):
                clipboard_open = True
                break
            time.sleep(
                0.04
            )

        if not clipboard_open:
            raise RuntimeError(
                "The Windows clipboard is busy. Try Copy Plot Image again."
            )

        if not user32.EmptyClipboard():
            raise RuntimeError(
                "Windows could not clear the clipboard."
            )

        result = user32.SetClipboardData(
            CF_DIB,
            global_memory,
        )

        if not result:
            raise RuntimeError(
                "Windows could not place the plot image on the clipboard."
            )

        # Ownership of global_memory transfers to Windows after successful
        # SetClipboardData, so it must not be freed by Python.
        transferred = True
        global_memory = None

    finally:
        if clipboard_open:
            user32.CloseClipboard()

        if (
            memory_dc
            and old_object
        ):
            gdi32.SelectObject(
                memory_dc,
                old_object,
            )

        if bitmap:
            gdi32.DeleteObject(
                bitmap
            )

        if memory_dc:
            gdi32.DeleteDC(
                memory_dc
            )

        if source_dc:
            user32.ReleaseDC(
                hwnd,
                source_dc,
            )

        if (
            global_memory
            and not transferred
        ):
            kernel32.GlobalFree(
                global_memory
            )


def safe_median(values):
    return (
        statistics.median(values)
        if values
        else 0
    )


def floor_5_minute(dt):
    return dt.replace(
        minute=dt.minute - dt.minute % 5,
        second=0,
        microsecond=0,
    )


def scale_bet(
    bet,
    current_min,
    current_max,
    proposed_min,
    proposed_max,
):
    bet = float(bet)

    current_min = float(current_min)
    current_max = float(current_max)

    proposed_min = float(proposed_min)
    proposed_max = float(proposed_max)

    if current_max <= current_min:
        return proposed_min

    normalized = (
        bet - current_min
    ) / (
        current_max - current_min
    )

    normalized = max(
        0.0,
        min(
            1.0,
            normalized,
        ),
    )

    return (
        proposed_min
        + normalized
        * (
            proposed_max
            - proposed_min
        )
    )


@lru_cache(maxsize=512)
def effective_cockfight_win_rate(
    start_percent,
    max_percent,
):
    start = max(
        0.0,
        min(
            0.999999,
            start_percent / 100.0,
        ),
    )

    max_p = max(
        start,
        min(
            0.999999,
            max_percent / 100.0,
        ),
    )

    survival = 1.0

    expected_fights = 0.0
    expected_wins = 0.0

    win_index = 0

    for _ in range(100000):
        if survival < 1e-12:
            break

        p = min(
            start
            + win_index * 0.01,
            max_p,
        )

        expected_fights += survival
        expected_wins += survival * p

        survival *= p

        win_index += 1

    if expected_fights <= 0:
        return 0.0

    return (
        expected_wins
        / expected_fights
    )


def draw_round_rect(
    canvas,
    x1,
    y1,
    x2,
    y2,
    radius,
    fill,
    outline=None,
    width=1,
):
    radius = max(
        2,
        min(
            radius,
            (x2 - x1) / 2,
            (y2 - y1) / 2,
        ),
    )

    points = [
        x1 + radius,
        y1,

        x2 - radius,
        y1,

        x2,
        y1,

        x2,
        y1 + radius,

        x2,
        y2 - radius,

        x2,
        y2,

        x2 - radius,
        y2,

        x1 + radius,
        y2,

        x1,
        y2,

        x1,
        y2 - radius,

        x1,
        y1 + radius,

        x1,
        y1,
    ]

    return canvas.create_polygon(
        points,
        smooth=True,
        splinesteps=32,
        fill=fill,
        outline=outline or fill,
        width=width,
    )


class EconomyAnalyzer:
    def __init__(
        self,
        db_path,
    ):
        self.db_path = db_path

        self.all_transactions = []
        self.transactions = []

        self.user_stats = []
        self.reason_stats = []
        self.hourly_stats = []
        self.daily_stats = []
        self.user_hour_stats = []
        self.summary_stats = []

        self.excluded_reasons = set()

        self.chicken_as_cockfight = True

        self.analysis_start = None
        self.analysis_end = None

        self.json_column = None

        # Discord History Tracker stores user records separately from embeds.
        # Keep a best-effort ID -> username lookup so the UI can use readable
        # names while still falling back to the raw Discord ID when a name is
        # unavailable in a particular database.
        self.user_names = {}
        self.user_labels = {}
        self.user_label_to_id = {}
        self.user_name_source = None

        # Fast lookup indexes. These are rebuilt whenever filters are applied,
        # so expensive pages and simulations do not repeatedly scan the entire
        # transaction list.
        self.transactions_by_user = {}
        self.game_transactions = {
            game: []
            for game in GAME_ORDER
        }
        self.user_game_transactions = {}
        self._simulation_base_cache = {}
        self._normalized_bet_cache = {}

    def connect(self):
        db_path = Path(self.db_path)

        if not db_path.exists():
            raise FileNotFoundError(
                "Database not found.\n\n"
                f"Current database location:\n{db_path}\n\n"
                "If you are using the packaged EXE, extract the ZIP first and "
                "place economy-stats.dht in the same folder as the EXE. "
                "Do not run the EXE directly from inside the ZIP.\n\n"
                "You can also click 'Choose Database' at the top of the program "
                "to select a .dht or SQLite database manually."
            )

        return sqlite3.connect(
            db_path
        )

    def load_user_names(
        self,
        connection,
    ):
        """Best-effort username lookup from the DHT SQLite database.

        DHT versions can use slightly different table/column names, so this
        deliberately discovers likely user tables instead of hard-coding one
        schema. Only values that look like Discord snowflake IDs are accepted.
        """
        self.user_names = {}
        self.user_name_source = None

        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                ORDER BY name
                """
            )
            tables = [
                str(row[0])
                for row in cursor.fetchall()
                if row
                and row[0]
            ]
        except sqlite3.Error:
            return

        def normalized_column(
            value,
        ):
            return re.sub(
                r"[^a-z0-9]",
                "",
                str(value).lower(),
            )

        id_priority = {
            "discorduserid": 120,
            "userid": 110,
            "id": 80,
        }

        name_priority = {
            "username": 140,
            "name": 120,
            "globalname": 100,
            "displayname": 90,
            "nickname": 80,
            "nick": 70,
        }

        best = {}

        for table in tables:
            quoted_table = (
                table.replace(
                    '"',
                    '""',
                )
            )

            try:
                cursor.execute(
                    f'PRAGMA table_info("{quoted_table}")'
                )
                info = cursor.fetchall()
            except sqlite3.Error:
                continue

            if not info:
                continue

            columns = [
                str(row[1])
                for row in info
                if len(row) > 1
            ]

            normalized = {
                normalized_column(
                    column
                ):
                    column
                for column in columns
            }

            id_candidates = [
                (
                    score,
                    normalized[key],
                )
                for key, score
                in id_priority.items()
                if key in normalized
            ]

            name_candidates = [
                (
                    score,
                    normalized[key],
                )
                for key, score
                in name_priority.items()
                if key in normalized
            ]

            if (
                not id_candidates
                or not name_candidates
            ):
                continue

            table_normalized = normalized_column(
                table
            )

            userish = (
                "user" in table_normalized
                or any(
                    "user" in normalized_column(
                        column
                    )
                    for column in columns
                )
            )

            if not userish:
                continue

            id_score, id_column = max(
                id_candidates
            )
            name_score, name_column = max(
                name_candidates
            )

            discriminator_column = (
                normalized.get(
                    "discriminator"
                )
            )

            quoted_id = id_column.replace(
                '"',
                '""',
            )
            quoted_name = name_column.replace(
                '"',
                '""',
            )

            select_columns = [
                f'"{quoted_id}"',
                f'"{quoted_name}"',
            ]

            if discriminator_column:
                select_columns.append(
                    '"'
                    + discriminator_column.replace(
                        '"',
                        '""',
                    )
                    + '"'
                )

            try:
                cursor.execute(
                    f"""
                    SELECT {", ".join(select_columns)}
                    FROM "{quoted_table}"
                    WHERE "{quoted_id}" IS NOT NULL
                      AND "{quoted_name}" IS NOT NULL
                    """
                )
                rows = cursor.fetchall()
            except sqlite3.Error:
                continue

            table_score = (
                180
                if "user" in table_normalized
                else 40
            )

            source_score = (
                table_score
                + id_score
                + name_score
            )

            for row in rows:
                if len(row) < 2:
                    continue

                user_id = str(
                    row[0]
                ).strip()
                username = str(
                    row[1]
                ).strip()

                if not re.fullmatch(
                    r"\d{10,25}",
                    user_id,
                ):
                    continue

                if (
                    not username
                    or username.lower()
                    in {
                        "none",
                        "null",
                    }
                ):
                    continue

                if (
                    discriminator_column
                    and len(row) >= 3
                ):
                    discriminator = str(
                        row[2]
                    ).strip()

                    if (
                        discriminator
                        and discriminator != "0"
                        and re.fullmatch(
                            r"\d{4}",
                            discriminator,
                        )
                        and "#"
                        not in username
                    ):
                        username = (
                            f"{username}"
                            f"#{discriminator}"
                        )

                existing = best.get(
                    user_id
                )

                if (
                    existing is None
                    or source_score
                    > existing[0]
                ):
                    best[
                        user_id
                    ] = (
                        source_score,
                        username,
                        table,
                    )

        for user_id, (
            _,
            username,
            source_table,
        ) in best.items():
            self.user_names[
                user_id
            ] = username

            if (
                self.user_name_source
                is None
            ):
                self.user_name_source = (
                    source_table
                )

    def rebuild_user_labels(self):
        all_user_ids = {
            str(
                tx["user_id"]
            )
            for tx
            in self.all_transactions
        }

        all_user_ids.update(
            self.user_names.keys()
        )

        names_to_ids = defaultdict(
            list
        )

        for user_id in all_user_ids:
            username = self.user_names.get(
                user_id
            )

            if username:
                names_to_ids[
                    username.casefold()
                ].append(
                    user_id
                )

        self.user_labels = {}
        self.user_label_to_id = {}

        for user_id in sorted(
            all_user_ids
        ):
            username = self.user_names.get(
                user_id
            )

            if not username:
                label = user_id

            elif len(
                names_to_ids[
                    username.casefold()
                ]
            ) > 1:
                label = (
                    f"{username} "
                    f"({user_id})"
                )

            else:
                label = username

            self.user_labels[
                user_id
            ] = label
            self.user_label_to_id[
                label
            ] = user_id

            self.user_label_to_id[
                user_id
            ] = user_id

    def get_user_label(
        self,
        user_id,
    ):
        user_id = str(
            user_id
        )

        return self.user_labels.get(
            user_id,
            self.user_names.get(
                user_id,
                user_id,
            ),
        )

    def resolve_user_label(
        self,
        value,
    ):
        value = str(
            value
        ).strip()

        if not value:
            return ""

        resolved = (
            self.user_label_to_id.get(
                value
            )
        )

        if resolved:
            return resolved

        match = re.search(
            r"\((\d{10,25})\)\s*$",
            value,
        )

        if match:
            return match.group(1)

        if re.fullmatch(
            r"\d{10,25}",
            value,
        ):
            return value

        matches = [
            user_id
            for user_id, label
            in self.user_labels.items()
            if label.casefold()
            == value.casefold()
        ]

        if len(matches) == 1:
            return matches[0]

        return value

    def user_display_row(
        self,
        row,
    ):
        """Return a user-facing row with Username replacing User ID."""
        if "User ID" not in row:
            return dict(
                row
            )

        display = {
            "Username":
                self.get_user_label(
                    row[
                        "User ID"
                    ]
                )
        }

        for key, value in row.items():
            if key == "User ID":
                continue

            display[
                key
            ] = value

        return display

    def find_json_column(
        self,
        connection,
    ):
        cursor = connection.cursor()

        cursor.execute(
            f'PRAGMA table_info("{TABLE_NAME}")'
        )

        columns = cursor.fetchall()

        if not columns:
            raise RuntimeError(
                f'Table "{TABLE_NAME}" '
                "was not found."
            )

        column_names = [
            row[1]
            for row in columns
        ]

        preferred_names = [
            "json",
            "embed_json",
            "data",
            "embed",
            "value",
            "content",
        ]

        for preferred in preferred_names:
            for column in column_names:
                if (
                    column.lower()
                    == preferred
                ):
                    return column

        for column in column_names:
            try:
                cursor.execute(
                    f'''
                    SELECT "{column}"
                    FROM "{TABLE_NAME}"
                    WHERE "{column}" IS NOT NULL
                    LIMIT 100
                    '''
                )

                for row in cursor.fetchall():
                    value = row[0]

                    if not isinstance(
                        value,
                        str,
                    ):
                        continue

                    try:
                        parsed = json.loads(
                            value
                        )

                        if (
                            isinstance(
                                parsed,
                                dict,
                            )
                            and (
                                "description"
                                in parsed
                                or "timestamp"
                                in parsed
                            )
                        ):
                            return column

                    except Exception:
                        pass

            except sqlite3.Error:
                continue

        raise RuntimeError(
            "Could not automatically "
            "find the JSON column."
        )

    def load_transactions(self):
        self.all_transactions.clear()

        connection = self.connect()

        try:
            self.load_user_names(
                connection
            )

            self.json_column = (
                self.find_json_column(
                    connection
                )
            )

            cursor = connection.cursor()

            cursor.execute(
                f'''
                SELECT "{self.json_column}"
                FROM "{TABLE_NAME}"
                WHERE "{self.json_column}" IS NOT NULL
                '''
            )

            for row in cursor.fetchall():
                raw_json = row[0]

                if not isinstance(
                    raw_json,
                    str,
                ):
                    continue

                try:
                    embed = json.loads(
                        raw_json
                    )

                except Exception:
                    continue

                if not isinstance(
                    embed,
                    dict,
                ):
                    continue

                description = embed.get(
                    "description"
                )

                if not description:
                    continue

                user_match = USER_RE.search(
                    description
                )

                if not user_match:
                    continue

                cash_match = CASH_RE.search(
                    description
                )

                bank_match = BANK_RE.search(
                    description
                )

                if (
                    not cash_match
                    and not bank_match
                ):
                    continue

                cash = (
                    parse_number(
                        cash_match.group(1)
                    )
                    if cash_match
                    else 0
                )

                bank = (
                    parse_number(
                        bank_match.group(1)
                    )
                    if bank_match
                    else 0
                )

                reason_match = REASON_RE.search(
                    description
                )

                original_reason = (
                    reason_match
                    .group(1)
                    .strip()
                    if reason_match
                    else "Unknown"
                )

                if not original_reason:
                    original_reason = (
                        "Unknown"
                    )

                timestamp = parse_timestamp(
                    embed.get(
                        "timestamp"
                    )
                )

                if timestamp is None:
                    continue

                self.all_transactions.append(
                    {
                        "user_id":
                            user_match.group(1),

                        "cash":
                            cash,

                        "bank":
                            bank,

                        "total":
                            cash + bank,

                        "original_reason":
                            clean_reason(
                                original_reason
                            ),

                        "timestamp":
                            timestamp,
                    }
                )

        finally:
            connection.close()

        self.all_transactions.sort(
            key=lambda tx:
            tx["timestamp"]
        )

        self.rebuild_user_labels()

    def get_available_reasons(
        self,
        chicken_as_cockfight=True,
    ):
        reasons = {
            canonical_reason(
                tx["original_reason"],
                chicken_as_cockfight,
            )
            for tx
            in self.all_transactions
        }

        preferred = [
            "blackjack",
            "slot machine",
            "cockfight",
            "higher or lower",
            "roulette",
            "russian roulette",
            "animal race",
            "rob",
            "chat money",
            "work",
            "crime",
            "slut",
            "role income",
            "buy",
            "add money",
            "remove money",
        ]

        ordered = [
            reason
            for reason
            in preferred
            if reason in reasons
        ]

        ordered.extend(
            sorted(
                reasons
                - set(ordered)
            )
        )

        return ordered

    def analyze(
        self,
        excluded_reasons=None,
        chicken_as_cockfight=True,
        start_time=None,
        end_time=None,
    ):
        if not self.all_transactions:
            raise RuntimeError(
                "The database contains "
                "no parsed transactions."
            )

        self.excluded_reasons = set(
            excluded_reasons
            or set()
        )

        self.chicken_as_cockfight = (
            chicken_as_cockfight
        )

        self.analysis_start = (
            start_time
            if start_time is not None
            else self.all_transactions[0][
                "timestamp"
            ]
        )

        self.analysis_end = (
            end_time
            if end_time is not None
            else self.all_transactions[-1][
                "timestamp"
            ]
        )

        if (
            self.analysis_start
            > self.analysis_end
        ):
            raise RuntimeError(
                "Analysis start cannot "
                "be after analysis end."
            )

        filtered = []

        for original_tx in (
            self.all_transactions
        ):
            if (
                original_tx[
                    "timestamp"
                ]
                < self.analysis_start
            ):
                continue

            if (
                original_tx[
                    "timestamp"
                ]
                > self.analysis_end
            ):
                continue

            reason = canonical_reason(
                original_tx[
                    "original_reason"
                ],
                chicken_as_cockfight,
            )

            if (
                reason
                in self.excluded_reasons
            ):
                continue

            tx = dict(
                original_tx
            )

            tx["reason"] = reason

            tx[
                "is_chicken_purchase"
            ] = is_chicken_purchase(
                original_tx[
                    "original_reason"
                ]
            )

            filtered.append(
                tx
            )

        self.transactions = filtered

        if not self.transactions:
            raise RuntimeError(
                "No transactions match "
                "the current filters."
            )

        self.rebuild_indexes()

        self.build_summary()
        self.build_user_stats()
        self.build_reason_stats()
        self.build_hourly_stats()
        self.build_daily_stats()
        self.build_user_hour_stats()

    def get_analysis_hours(self):
        if (
            self.analysis_start is None
            or self.analysis_end is None
        ):
            return 0

        return max(
            (
                self.analysis_end
                - self.analysis_start
            ).total_seconds()
            / 3600,
            1 / 3600,
        )

    def get_analysis_days(self):
        return (
            self.get_analysis_hours()
            / 24
        )

    def get_30_day_factor(self):
        hours = (
            self.get_analysis_hours()
        )

        if hours <= 0:
            return 0

        return (
            720 / hours
        )

    def get_24h_factor(self):
        hours = (
            self.get_analysis_hours()
        )

        if hours <= 0:
            return 0

        return (
            24 / hours
        )

    def rebuild_indexes(self):
        by_user = defaultdict(list)
        by_game = {
            game: []
            for game in GAME_ORDER
        }
        by_user_game = defaultdict(
            lambda: {
                game: []
                for game in GAME_ORDER
            }
        )

        for tx in self.transactions:
            user_id = str(
                tx["user_id"]
            )
            by_user[user_id].append(tx)

            game = game_from_reason(
                tx["original_reason"]
            )
            tx["_game"] = game

            if game in by_game:
                by_game[game].append(tx)
                by_user_game[user_id][game].append(tx)

        self.transactions_by_user = dict(
            by_user
        )
        self.game_transactions = by_game
        self.user_game_transactions = {
            user_id: dict(game_map)
            for user_id, game_map
            in by_user_game.items()
        }

        # Any filter change means cached simulation inputs are no longer valid.
        self._simulation_base_cache.clear()
        self._normalized_bet_cache.clear()

    def get_user_transactions(
        self,
        user_id,
    ):
        return self.transactions_by_user.get(
            str(user_id),
            [],
        )

    def calculate_activity(
        self,
        txs,
    ):
        if not txs:
            return {
                "active_blocks": 0,
                "active_minutes": 0,
                "active_hours": 0,
                "activity_percent": 0,
                "sessions": 0,
                "tx_per_active_hour": 0,
                "active_days": 0,
            }

        blocks = {
            floor_5_minute(
                tx["timestamp"]
                .astimezone(
                    LOCAL_TZ
                )
            )
            for tx in txs
        }

        active_blocks = len(
            blocks
        )

        active_minutes = (
            active_blocks * 5
        )

        total_minutes = (
            self.get_analysis_hours()
            * 60
        )

        activity_percent = (
            active_minutes
            / total_minutes
            * 100
            if total_minutes > 0
            else 0
        )

        activity_percent = min(
            100.0,
            activity_percent,
        )

        sorted_times = sorted(
            tx["timestamp"]
            for tx in txs
        )

        sessions = 0
        previous = None

        for timestamp in sorted_times:
            if (
                previous is None
                or (
                    timestamp
                    - previous
                ).total_seconds()
                > 600
            ):
                sessions += 1

            previous = timestamp

        active_days = len({
            tx["timestamp"]
            .astimezone(
                LOCAL_TZ
            )
            .date()
            for tx in txs
        })

        active_hours = (
            active_minutes
            / 60
        )

        tx_per_active_hour = (
            len(txs)
            / active_hours
            if active_hours > 0
            else 0
        )

        return {
            "active_blocks":
                active_blocks,

            "active_minutes":
                active_minutes,

            "active_hours":
                active_hours,

            "activity_percent":
                activity_percent,

            "sessions":
                sessions,

            "tx_per_active_hour":
                tx_per_active_hour,

            "active_days":
                active_days,
        }

    def get_user_reason_breakdown(
        self,
        user_id,
    ):
        txs = self.get_user_transactions(user_id)

        grouped = defaultdict(list)

        for tx in txs:
            grouped[tx["reason"]].append(tx)

        total_earned = sum(
            tx["total"]
            for tx in txs
            if tx["total"] > 0
        )

        total_lost = -sum(
            tx["total"]
            for tx in txs
            if tx["total"] < 0
        )

        rows = []

        for reason, reason_txs in grouped.items():
            net = sum(
                tx["total"]
                for tx in reason_txs
            )

            earned = sum(
                tx["total"]
                for tx in reason_txs
                if tx["total"] > 0
            )

            lost = -sum(
                tx["total"]
                for tx in reason_txs
                if tx["total"] < 0
            )

            rows.append(
                {
                    "Reason": reason,
                    "Net Profit": net,
                    "Gross Earned": earned,
                    "Gross Lost": lost,
                    "Transactions": len(reason_txs),
                    "Earnings Share %": (
                        earned / total_earned * 100
                        if total_earned
                        else 0
                    ),
                    "Loss Share %": (
                        lost / total_lost * 100
                        if total_lost
                        else 0
                    ),
                }
            )

        rows.sort(
            key=lambda row: row["Net Profit"],
            reverse=True,
        )

        return rows

    def get_user_summary(
        self,
        user_id,
    ):
        txs = self.get_user_transactions(user_id)

        if not txs:
            return []

        net = sum(
            tx["total"]
            for tx in txs
        )

        earned = sum(
            tx["total"]
            for tx in txs
            if tx["total"] > 0
        )

        lost = -sum(
            tx["total"]
            for tx in txs
            if tx["total"] < 0
        )

        activity = self.calculate_activity(txs)
        breakdown = self.get_user_reason_breakdown(user_id)

        net_income_rows = [
            row
            for row in breakdown
            if row["Net Profit"] > 0
        ]

        loss_rows = [
            row
            for row in breakdown
            if row["Gross Lost"] > 0
        ]

        top_income_source = (
            max(
                net_income_rows,
                key=lambda row: row["Net Profit"],
            )["Reason"]
            if net_income_rows
            else "None"
        )

        top_loss_source = (
            max(
                loss_rows,
                key=lambda row: row["Gross Lost"],
            )["Reason"]
            if loss_rows
            else "None"
        )

        factor = self.get_30_day_factor()

        return [
            (
                "Username",
                self.get_user_label(
                    user_id
                ),
            ),
            ("Net Profit", net),
            ("30d Projected Net", net * factor),
            ("Gross Earned", earned),
            ("Gross Lost", lost),
            ("Transactions", len(txs)),
            (
                "Estimated Active Hours",
                activity["active_hours"],
            ),
            (
                "Economy Activity %",
                activity["activity_percent"],
            ),
            (
                "Estimated Sessions",
                activity["sessions"],
            ),
            (
                "Active Days",
                activity["active_days"],
            ),
            (
                "Top Income Source",
                top_income_source,
            ),
            (
                "Top Loss Source",
                top_loss_source,
            ),
            (
                "Last Transaction",
                to_local_string(
                    max(
                        tx["timestamp"]
                        for tx in txs
                    )
                ),
            ),
        ]

    def build_summary(self):
        txs = self.transactions

        hours = self.get_analysis_hours()
        days = self.get_analysis_days()
        factor = self.get_30_day_factor()

        net = sum(
            tx["total"]
            for tx in txs
        )

        earned = sum(
            tx["total"]
            for tx in txs
            if tx["total"] > 0
        )

        lost = -sum(
            tx["total"]
            for tx in txs
            if tx["total"] < 0
        )

        users = {
            tx["user_id"]
            for tx in txs
        }

        active_blocks = {
            (
                tx["user_id"],
                floor_5_minute(
                    tx["timestamp"].astimezone(
                        LOCAL_TZ
                    )
                ),
            )
            for tx in txs
        }

        self.summary_stats = [
            (
                "Selected period starts",
                to_local_string(
                    self.analysis_start
                ),
            ),
            (
                "Selected period ends",
                to_local_string(
                    self.analysis_end
                ),
            ),
            (
                "Period length",
                f"{days:,.2f} days",
            ),
            (
                "Balance changes",
                len(txs),
            ),
            (
                "People using economy",
                len(users),
            ),
            (
                "Combined time using economy",
                f"{len(active_blocks) * 5 / 60:,.2f} hours",
            ),
            (
                "Overall balance change",
                net,
            ),
            (
                "Money added to users",
                earned,
            ),
            (
                "Money taken from users",
                lost,
            ),
            (
                "Average balance change per hour",
                net / hours,
            ),
            (
                "30-day result at same pace",
                net * factor,
            ),
            (
                "Removed for every 100 added",
                (
                    lost / earned * 100
                    if earned
                    else 0
                ),
            ),
        ]

    def build_user_stats(self):
        grouped = defaultdict(list)

        for tx in self.transactions:
            grouped[tx["user_id"]].append(tx)

        factor = self.get_30_day_factor()
        rows = []

        for user_id, txs in grouped.items():
            net = sum(
                tx["total"]
                for tx in txs
            )

            earned = sum(
                tx["total"]
                for tx in txs
                if tx["total"] > 0
            )

            lost = -sum(
                tx["total"]
                for tx in txs
                if tx["total"] < 0
            )

            activity = self.calculate_activity(txs)
            breakdown = self.get_user_reason_breakdown(user_id)

            net_income_rows = [
                row
                for row in breakdown
                if row["Net Profit"] > 0
            ]

            top_source = (
                max(
                    net_income_rows,
                    key=lambda row: row["Net Profit"],
                )["Reason"]
                if net_income_rows
                else "None"
            )

            rows.append(
                {
                    "User ID": user_id,
                    "Net Profit": net,
                    "30d Net": net * factor,
                    "Gross Earned": earned,
                    "Gross Lost": lost,
                    "Est. Active Hrs": activity["active_hours"],
                    "Activity %": activity["activity_percent"],
                    "Sessions": activity["sessions"],
                    "Active Days": activity["active_days"],
                    "Top Income Source": top_source,
                    "Transactions": len(txs),
                    "Last Seen": to_local_string(
                        max(
                            tx["timestamp"]
                            for tx in txs
                        )
                    ),
                }
            )

        rows.sort(
            key=lambda row: row["30d Net"],
            reverse=True,
        )

        self.user_stats = rows

    def estimate_game_rounds(
        self,
        game,
        txs,
        current_slot_multiplier=DEFAULT_SLOT_MULTIPLIER,
    ):
        bets = self.infer_game_bets(
            game,
            txs,
            current_slot_multiplier,
        )

        if bets:
            return len(bets)

        return sum(
            1
            for tx in txs
            if (
                not tx.get("is_chicken_purchase", False)
                and not (
                    game == "animal race"
                    and is_animal_race_purchase(
                        tx["original_reason"]
                    )
                )
            )
        )

    def get_activity_groups(
        self,
        basis="Combined activity",
    ):
        """Group users by natural activity levels instead of equal-sized bins.

        The old implementation ranked everybody and forced 20% of users into
        each label. That makes the labels misleading when a server has many
        casual users and only a few genuinely heavy economy users.

        This version measures activity as a per-day rate, log-compresses the
        heavy tail, and then performs deterministic one-dimensional k-means.
        The resulting groups are allowed to have very different member counts.
        """
        if basis not in ACTIVITY_GROUP_BASIS_OPTIONS:
            basis = "Combined activity"

        if not self.user_stats:
            return [], {
                name: set()
                for name in ACTIVITY_GROUP_NAMES
            }

        analysis_days = max(
            self.get_analysis_days(),
            1.0 / 24.0,
        )

        records = []

        for row in self.user_stats:
            active_hours = float(
                row["Est. Active Hrs"]
            )
            transactions = int(
                row["Transactions"]
            )

            records.append(
                {
                    "user_id": str(row["User ID"]),
                    "active_hours": active_hours,
                    "transactions": transactions,
                    "active_days": int(row["Active Days"]),
                    "net": float(row["Net Profit"]),
                    "hours_per_day": (
                        active_hours
                        / analysis_days
                    ),
                    "transactions_per_day": (
                        transactions
                        / analysis_days
                    ),
                }
            )

        hour_logs = [
            math.log1p(
                row["hours_per_day"]
            )
            for row in records
        ]
        tx_logs = [
            math.log1p(
                row["transactions_per_day"]
            )
            for row in records
        ]

        def percentile_value(values, fraction):
            if not values:
                return 0.0

            ordered = sorted(values)
            if len(ordered) == 1:
                return ordered[0]

            position = (
                len(ordered) - 1
            ) * fraction
            lower = int(math.floor(position))
            upper = int(math.ceil(position))

            if lower == upper:
                return ordered[lower]

            weight = position - lower
            return (
                ordered[lower]
                * (1.0 - weight)
                + ordered[upper]
                * weight
            )

        # Scale the two combined features by the 90th percentile rather than
        # ranks. This keeps hours and transaction count comparable without
        # forcing the final score itself to be uniformly distributed.
        hour_scale = max(
            1e-9,
            percentile_value(
                hour_logs,
                0.90,
            ),
        )
        tx_scale = max(
            1e-9,
            percentile_value(
                tx_logs,
                0.90,
            ),
        )

        for index, row in enumerate(records):
            if basis == "Estimated active hours":
                score = hour_logs[index]
            elif basis == "Transactions":
                score = tx_logs[index]
            else:
                score = (
                    hour_logs[index]
                    / hour_scale
                    + tx_logs[index]
                    / tx_scale
                ) / 2.0

            row["activity_score"] = float(score)

        def natural_clusters(values, wanted_clusters):
            """Return a cluster id for each 1D value using deterministic k-means."""
            if not values:
                return [], []

            unique_values = sorted(set(values))
            cluster_count = min(
                wanted_clusters,
                len(unique_values),
            )

            if cluster_count <= 1:
                return [0] * len(values), [statistics.mean(values)]

            low = min(values)
            high = max(values)

            if math.isclose(low, high):
                return [0] * len(values), [low]

            # Value-spaced initialization is deliberate. Quantile-spaced
            # centers would tend to recreate the equal-sized groups that this
            # method is replacing.
            centers = [
                low
                + (
                    high - low
                ) * (
                    index
                    / (cluster_count - 1)
                )
                for index in range(cluster_count)
            ]

            assignments = [0] * len(values)

            for _ in range(100):
                new_assignments = []

                for value in values:
                    cluster_index = min(
                        range(cluster_count),
                        key=lambda index: (
                            abs(
                                value
                                - centers[index]
                            ),
                            index,
                        ),
                    )
                    new_assignments.append(
                        cluster_index
                    )

                buckets = [
                    []
                    for _ in range(cluster_count)
                ]

                for value, cluster_index in zip(
                    values,
                    new_assignments,
                ):
                    buckets[cluster_index].append(
                        value
                    )

                new_centers = list(centers)

                for cluster_index, bucket in enumerate(buckets):
                    if bucket:
                        new_centers[cluster_index] = statistics.mean(
                            bucket
                        )
                    else:
                        # Re-seed an empty cluster with the value currently
                        # furthest from every occupied center.
                        occupied = [
                            centers[index]
                            for index, values_in_bucket
                            in enumerate(buckets)
                            if values_in_bucket
                        ]

                        if occupied:
                            candidate = max(
                                values,
                                key=lambda value: min(
                                    abs(value - center)
                                    for center in occupied
                                ),
                            )
                            new_centers[cluster_index] = candidate

                if (
                    new_assignments == assignments
                    and all(
                        math.isclose(
                            new_centers[index],
                            centers[index],
                            rel_tol=1e-10,
                            abs_tol=1e-10,
                        )
                        for index in range(cluster_count)
                    )
                ):
                    assignments = new_assignments
                    centers = new_centers
                    break

                assignments = new_assignments
                centers = new_centers

            # Renumber clusters from least active to most active.
            order = sorted(
                range(cluster_count),
                key=lambda index: centers[index],
            )
            remap = {
                old_index: new_index
                for new_index, old_index
                in enumerate(order)
            }
            ordered_centers = [
                centers[index]
                for index in order
            ]
            assignments = [
                remap[index]
                for index in assignments
            ]

            return assignments, ordered_centers

        scores = [
            row["activity_score"]
            for row in records
        ]
        cluster_ids, centers = natural_clusters(
            scores,
            len(ACTIVITY_GROUP_NAMES),
        )

        cluster_count = len(centers)

        if cluster_count <= 1:
            name_indexes = [0]
        else:
            # If the data genuinely contains fewer than five distinct natural
            # levels, spread those levels across the available names rather
            # than pretending that empty intermediate bands exist.
            name_indexes = [
                int(round(
                    cluster_index
                    * (
                        len(ACTIVITY_GROUP_NAMES) - 1
                    )
                    / (cluster_count - 1)
                ))
                for cluster_index
                in range(cluster_count)
            ]

        members = {
            name: set()
            for name in ACTIVITY_GROUP_NAMES
        }
        record_by_user = {}

        for row, cluster_index in zip(
            records,
            cluster_ids,
        ):
            group_name = ACTIVITY_GROUP_NAMES[
                name_indexes[cluster_index]
            ]
            row["group"] = group_name
            row["cluster_center"] = centers[
                cluster_index
            ]
            members[group_name].add(
                row["user_id"]
            )
            record_by_user[
                row["user_id"]
            ] = row

        factor24 = self.get_24h_factor()
        factor30 = self.get_30_day_factor()
        stats = []

        for group_name in ACTIVITY_GROUP_NAMES:
            group_users = members[group_name]
            group_records = [
                record_by_user[user_id]
                for user_id in group_users
                if user_id in record_by_user
            ]

            if not group_records:
                stats.append(
                    {
                        "Group": group_name,
                        "Members": 0,
                        "Avg Active Hrs / Day": 0,
                        "Avg Transactions / Day": 0,
                        "Avg Active Days / 30d": 0,
                        "Avg 24h Net": 0,
                        "Avg 30d Net": 0,
                    }
                )
                continue

            member_count = len(group_records)
            average_net = statistics.mean(
                row["net"]
                for row in group_records
            )
            average_hours_per_day = statistics.mean(
                row["hours_per_day"]
                for row in group_records
            )
            average_transactions_per_day = statistics.mean(
                row["transactions_per_day"]
                for row in group_records
            )
            average_active_days_per_30d = statistics.mean(
                row["active_days"]
                / analysis_days
                * 30.0
                for row in group_records
            )

            stats.append(
                {
                    "Group": group_name,
                    "Members": member_count,
                    "Avg Active Hrs / Day": average_hours_per_day,
                    "Avg Transactions / Day": average_transactions_per_day,
                    "Avg Active Days / 30d": min(
                        30.0,
                        average_active_days_per_30d,
                    ),
                    "Avg 24h Net": average_net * factor24,
                    "Avg 30d Net": average_net * factor30,
                }
            )

        return stats, members

    def get_activity_group_details(
        self,
        group_name,
        basis="Combined activity",
    ):
        """Return detailed historical averages for one natural activity group.

        These statistics are descriptive history only. They show what users in
        the selected group actually did during the selected database window.
        The Game Simulator still ignores historical game popularity and uses
        the fixed plays-per-five-active-minutes assumption instead.
        """
        group_rows, members = (
            self.get_activity_groups(
                basis
            )
        )

        group_users = set(
            members.get(
                group_name,
                set(),
            )
        )

        group_summary = next(
            (
                row
                for row in group_rows
                if row.get(
                    "Group"
                ) == group_name
            ),
            None,
        )

        if (
            not group_summary
            or not group_users
        ):
            return {
                "group": group_name,
                "members": 0,
                "summary": group_summary,
                "game_rows": [],
                "member_rows": [],
                "avg_game_net_per_member_24h": 0.0,
                "avg_game_net_per_member_30d": 0.0,
            }

        analysis_days = max(
            self.get_analysis_days(),
            1.0 / 24.0,
        )
        factor24 = self.get_24h_factor()
        factor30 = self.get_30_day_factor()
        member_count = len(
            group_users
        )

        total_game_net = 0.0

        game_rows = []

        for game in GAME_ORDER:
            txs = []
            players = set()

            for user_id in group_users:
                game_txs = (
                    self.user_game_transactions
                    .get(
                        str(user_id),
                        {},
                    )
                    .get(
                        game,
                        [],
                    )
                )

                if game_txs:
                    players.add(
                        str(user_id)
                    )
                    txs.extend(
                        game_txs
                    )

            player_count = len(
                players
            )

            net = sum(
                tx["total"]
                for tx in txs
            )
            earned = sum(
                tx["total"]
                for tx in txs
                if tx["total"] > 0
            )
            lost = -sum(
                tx["total"]
                for tx in txs
                if tx["total"] < 0
            )

            rounds = (
                self.estimate_game_rounds(
                    game,
                    txs,
                )
                if txs
                else 0.0
            )

            bets = (
                self.infer_game_bets(
                    game,
                    txs,
                    DEFAULT_SLOT_MULTIPLIER,
                )
                if txs
                else []
            )

            average_bet = (
                statistics.mean(
                    bets
                )
                if bets
                else 0.0
            )

            total_game_net += net

            game_rows.append(
                {
                    "Game":
                        GAME_DISPLAY[
                            game
                        ],
                    "Users Played":
                        player_count,
                    "Participation %":
                        (
                            player_count
                            / member_count
                            * 100.0
                            if member_count
                            else 0.0
                        ),
                    "Avg Plays / Player / Day":
                        (
                            rounds
                            / analysis_days
                            / player_count
                            if player_count
                            else 0.0
                        ),
                    "Avg Bet":
                        average_bet,
                    "Net / Play":
                        (
                            net
                            / rounds
                            if rounds
                            else 0.0
                        ),
                    "Avg 24h Net / Member":
                        (
                            net
                            * factor24
                            / member_count
                            if member_count
                            else 0.0
                        ),
                    "Avg 30d Net / Member":
                        (
                            net
                            * factor30
                            / member_count
                            if member_count
                            else 0.0
                        ),
                }
            )

        game_rows.sort(
            key=lambda row:
                row[
                    "Avg Plays / Player / Day"
                ],
            reverse=True,
        )

        user_stats_by_id = {
            str(row["User ID"]):
                row
            for row in self.user_stats
        }

        member_rows = []

        for user_id in group_users:
            row = user_stats_by_id.get(
                str(user_id)
            )

            if row is None:
                continue

            member_rows.append(
                {
                    "Username":
                        self.get_user_label(
                            user_id
                        ),
                    "Active Hrs / Day":
                        (
                            float(
                                row[
                                    "Est. Active Hrs"
                                ]
                            )
                            / analysis_days
                        ),
                    "Transactions / Day":
                        (
                            float(
                                row[
                                    "Transactions"
                                ]
                            )
                            / analysis_days
                        ),
                    "24h Net":
                        (
                            float(
                                row[
                                    "Net Profit"
                                ]
                            )
                            * factor24
                        ),
                    "30d Net":
                        (
                            float(
                                row[
                                    "Net Profit"
                                ]
                            )
                            * factor30
                        ),
                    "Top Income Source":
                        row.get(
                            "Top Income Source",
                            "None",
                        ),
                    "Sessions":
                        int(
                            row.get(
                                "Sessions",
                                0,
                            )
                        ),
                    "Active Days":
                        int(
                            row.get(
                                "Active Days",
                                0,
                            )
                        ),
                }
            )

        member_rows.sort(
            key=lambda row: (
                row[
                    "Active Hrs / Day"
                ],
                row[
                    "Transactions / Day"
                ],
            ),
            reverse=True,
        )

        return {
            "group":
                group_name,
            "members":
                member_count,
            "summary":
                group_summary,
            "game_rows":
                game_rows,
            "member_rows":
                member_rows,
            "avg_game_net_per_member_24h":
                (
                    total_game_net
                    * factor24
                    / member_count
                    if member_count
                    else 0.0
                ),
            "avg_game_net_per_member_30d":
                (
                    total_game_net
                    * factor30
                    / member_count
                    if member_count
                    else 0.0
                ),
        }

    def prepare_activity_optimizer_context(
        self,
        basis="Combined activity",
    ):
        _, members = self.get_activity_groups(
            basis
        )

        analysis_days = max(
            self.get_analysis_days(),
            1.0 / 24.0,
        )

        user_stats_by_id = {
            str(row["User ID"]): row
            for row in self.user_stats
        }

        group_avg_active_hours_per_day = {}
        group_avg_active_days_per_day = {}

        for group_name in ACTIVITY_GROUP_NAMES:
            rows = [
                user_stats_by_id[user_id]
                for user_id
                in members.get(
                    group_name,
                    set(),
                )
                if user_id in user_stats_by_id
            ]

            if not rows:
                group_avg_active_hours_per_day[
                    group_name
                ] = 0.0
                group_avg_active_days_per_day[
                    group_name
                ] = 0.0
                continue

            group_avg_active_hours_per_day[
                group_name
            ] = statistics.mean(
                float(
                    row["Est. Active Hrs"]
                )
                / analysis_days
                for row in rows
            )

            group_avg_active_days_per_day[
                group_name
            ] = statistics.mean(
                float(
                    row["Active Days"]
                )
                / analysis_days
                for row in rows
            )

        global_game_txs = {
            game:
                self.game_transactions.get(
                    game,
                    [],
                )
            for game in GAME_ORDER
        }

        return {
            "members": members,
            "global_game_txs":
                global_game_txs,
            "group_avg_active_hours_per_day":
                group_avg_active_hours_per_day,
            "group_avg_active_days_per_day":
                group_avg_active_days_per_day,
        }

    def make_current_baseline_settings(
        self,
        settings,
    ):
        """Return settings where every proposed value equals the current value."""
        baseline = copy.deepcopy(settings)

        baseline["proposed_games_per_5m"] = (
            baseline["current_games_per_5m"]
        )
        baseline["proposed_blackjack_decks"] = (
            baseline["current_blackjack_decks"]
        )
        baseline["proposed_slot_symbols"] = (
            baseline["current_slot_symbols"]
        )
        baseline["proposed_slot_multiplier"] = (
            baseline["current_slot_multiplier"]
        )
        baseline["proposed_cockfight_start"] = (
            baseline["current_cockfight_start"]
        )
        baseline["proposed_cockfight_max"] = (
            baseline["current_cockfight_max"]
        )
        baseline["proposed_chicken_price"] = (
            baseline["current_chicken_price"]
        )

        for game in BET_LIMIT_GAMES:
            baseline["games"][game]["proposed"] = dict(
                baseline["games"][game]["current"]
            )

        return baseline

    def evaluate_activity_group_monthly(
        self,
        settings,
        context,
        use_actual_game_mix=False,
    ):
        """Estimate monthly game profit from a fixed play rate.

        Historical game counts and historical game mix are deliberately ignored.
        Every activity group is assumed to play EVERY modeled game the number of
        times entered in the plays-per-five-active-minutes field. Groups differ
        only by their estimated active time.
        """
        predictions = {}

        unit_metrics = (
            self.build_game_unit_metrics(
                settings
            )
        )

        proposed_rate = max(
            0.0,
            float(
                settings[
                    "proposed_games_per_5m"
                ]
            ),
        )

        for group_name in ACTIVITY_GROUP_NAMES:
            member_count = len(
                context["members"].get(
                    group_name,
                    set(),
                )
            )

            if member_count <= 0:
                predictions[group_name] = 0.0
                continue

            active_hours_per_day = float(
                context[
                    "group_avg_active_hours_per_day"
                ].get(
                    group_name,
                    0.0,
                )
            )
            active_days_per_day = float(
                context[
                    "group_avg_active_days_per_day"
                ].get(
                    group_name,
                    0.0,
                )
            )

            plays_per_game_per_day = (
                active_hours_per_day
                * 12.0
                * proposed_rate
            )

            daily_net = 0.0

            for game in GAME_ORDER:
                metrics = unit_metrics.get(
                    game,
                    {},
                )

                daily_net += (
                    plays_per_game_per_day
                    * float(
                        metrics.get(
                            "proposed_net_per_play",
                            0.0,
                        )
                    )
                )

                if game == "animal race":
                    daily_net += (
                        active_days_per_day
                        * float(
                            metrics.get(
                                "fixed_purchase_net_per_active_day",
                                0.0,
                            )
                        )
                    )

            predictions[group_name] = (
                daily_net
                * 30.0
            )

        return predictions

    def optimize_activity_targets(
        self,
        base_settings,
        targets,
        locked_keys,
        basis="Combined activity",
        use_actual_game_mix=False,
    ):
        if not targets:
            raise ValueError(
                "Select at least one activity group and enter a monthly target."
            )

        context = self.prepare_activity_optimizer_context(
            basis
        )

        for group_name in targets:
            if not context["members"].get(group_name):
                raise ValueError(
                    f"{group_name} has no users in the selected data."
                )

        best = copy.deepcopy(base_settings)
        base = copy.deepcopy(base_settings)

        specs = []

        if "proposed_games_per_5m" not in locked_keys:
            specs.append(
                {
                    "key": "proposed_games_per_5m",
                    "kind": "usage",
                    "min": 1.0,
                    "max": 10.0,
                }
            )

        for game in BET_LIMIT_GAMES:
            # Russian Roulette is intentionally left alone by automatic target
            # optimization. It may remain a high-risk / losing game and should
            # never become the optimizer's shortcut for funding every group.
            if game == "russian roulette":
                continue

            # Do not generate meaningless changes for games that nobody played
            # in the selected history. Such settings cannot improve the target.
            if not context["global_game_txs"].get(game):
                continue

            for field in ("min", "max"):
                lock_key = f"{game}:proposed_{field}"
                if lock_key in locked_keys:
                    continue

                base_value = float(
                    base["games"][game][
                        "proposed"
                    ][field]
                )

                # Keep the automatic search in a realistic neighborhood.
                # Manually entered values can still be larger and can be locked.
                automatic_upper = min(
                    10000.0,
                    max(
                        500.0,
                        base_value * 6.0,
                    ),
                )

                specs.append(
                    {
                        "key": lock_key,
                        "kind": "bet",
                        "game": game,
                        "field": field,
                        "min": 1.0,
                        "max": automatic_upper,
                    }
                )

        extra_specs = [
            (
                "proposed_slot_symbols",
                "slots",
                2.0,
                8.0,
            ),
            (
                "proposed_slot_multiplier",
                "multiplier",
                0.1,
                10.0,
            ),
            (
                "proposed_cockfight_start",
                "chance",
                1.0,
                99.0,
            ),
            (
                "proposed_cockfight_max",
                "chance",
                1.0,
                99.0,
            ),
            (
                "proposed_chicken_price",
                "price",
                0.0,
                10000.0,
            ),
        ]

        for key, kind, lower, upper in extra_specs:
            if key in {
                "proposed_slot_symbols",
                "proposed_slot_multiplier",
            } and not context["global_game_txs"].get(
                "slot machine"
            ):
                continue

            if key in {
                "proposed_cockfight_start",
                "proposed_cockfight_max",
                "proposed_chicken_price",
            } and not context["global_game_txs"].get(
                "cockfight"
            ):
                continue

            if key not in locked_keys:
                specs.append(
                    {
                        "key": key,
                        "kind": kind,
                        "min": lower,
                        "max": upper,
                    }
                )

        if not specs:
            raise ValueError(
                "Every value the optimizer can change is locked. Unlock at least one value."
            )

        def get_value(settings, spec):
            if spec["kind"] == "bet":
                return settings["games"][spec["game"]]["proposed"][spec["field"]]
            return settings[spec["key"]]

        def set_value(settings, spec, value):
            value = max(
                spec["min"],
                min(spec["max"], value),
            )

            if spec["kind"] in {"usage", "slots"}:
                value = float(round(value))

            if spec["kind"] == "bet":
                value = float(round(value / 5.0) * 5.0)
                value = max(spec["min"], value)
                settings["games"][spec["game"]]["proposed"][spec["field"]] = value
            elif spec["kind"] == "slots":
                settings[spec["key"]] = int(value)
            elif spec["kind"] == "usage":
                settings[spec["key"]] = float(value)
            else:
                settings[spec["key"]] = float(value)

        def valid(settings):
            for game in BET_LIMIT_GAMES:
                proposed = settings["games"][game]["proposed"]
                if proposed["max"] < proposed["min"]:
                    return False

            if (
                settings["proposed_cockfight_start"]
                > settings["proposed_cockfight_max"]
            ):
                return False

            return True

        prediction_cache = {}
        balance_cache = {}

        def evaluate_game_balance(settings):
            """Keep normal configurable games useful on a per-play basis.

            Historical game popularity is ignored. Russian Roulette is
            intentionally excluded from this balancing goal.
            """
            metrics_by_game = (
                self.build_game_unit_metrics(
                    settings
                )
            )

            game_rows = []

            for game in BALANCED_OPTIMIZER_GAMES:
                metrics = metrics_by_game.get(
                    game,
                    {},
                )

                if not metrics.get(
                    "has_model_data",
                    False,
                ):
                    continue

                current_net = float(
                    metrics.get(
                        "current_net_per_play",
                        0.0,
                    )
                )
                proposed_net = float(
                    metrics.get(
                        "proposed_net_per_play",
                        0.0,
                    )
                )
                proposed_lost = float(
                    metrics.get(
                        "proposed_lost_per_play",
                        0.0,
                    )
                )

                denominator = max(
                    1.0,
                    abs(proposed_lost),
                )
                return_rate = (
                    proposed_net
                    / denominator
                )
                scored_rate = max(
                    -1.0,
                    min(
                        1.0,
                        return_rate,
                    ),
                )

                game_rows.append(
                    {
                        "game": game,
                        "proposed_net": proposed_net,
                        "current_net": current_net,
                        "uplift":
                            proposed_net
                            - current_net,
                        "return_rate":
                            return_rate,
                        "scored_rate":
                            scored_rate,
                    }
                )

            if not game_rows:
                return {
                    "penalty": 0.0,
                    "profitable_games": 0,
                    "game_count": 0,
                    "largest_positive_share": 0.0,
                    "rows": [],
                }

            game_count = len(
                game_rows
            )

            beneficial_penalty = 0.0
            profitable_games = 0

            for row in game_rows:
                rate = row[
                    "scored_rate"
                ]

                if row[
                    "proposed_net"
                ] > 0:
                    profitable_games += 1
                else:
                    beneficial_penalty += (
                        0.18
                        + 0.85
                        * abs(
                            min(
                                0.0,
                                rate,
                            )
                        )
                    )

            beneficial_penalty /= max(
                1,
                game_count,
            )

            rates = [
                row["scored_rate"]
                for row in game_rows
            ]
            median_rate = statistics.median(
                rates
            )

            rate_spread_penalty = (
                sum(
                    (
                        rate
                        - median_rate
                    ) ** 2
                    for rate in rates
                )
                / max(
                    1,
                    len(rates),
                )
            )

            positive_uplifts = [
                max(
                    0.0,
                    row["uplift"],
                )
                for row in game_rows
            ]
            total_positive_uplift = sum(
                positive_uplifts
            )

            concentration_penalty = 0.0
            largest_positive_share = 0.0

            if total_positive_uplift > 0:
                shares = [
                    value
                    / total_positive_uplift
                    for value
                    in positive_uplifts
                ]

                largest_positive_share = max(
                    shares
                )

                equal_share = (
                    1.0
                    / len(shares)
                )

                concentration_penalty += (
                    sum(
                        (
                            share
                            - equal_share
                        ) ** 2
                        for share in shares
                    )
                    * 1.8
                )

                if (
                    largest_positive_share
                    > 0.45
                ):
                    concentration_penalty += (
                        (
                            largest_positive_share
                            - 0.45
                        ) ** 2
                        * 8.0
                    )

                for share in shares:
                    if share < 0.04:
                        concentration_penalty += (
                            (
                                0.04
                                - share
                            ) ** 2
                            * 3.0
                        )

            explosion_penalty = 0.0

            for row in game_rows:
                current_scale = max(
                    1.0,
                    abs(
                        row[
                            "current_net"
                        ]
                    ),
                )

                relative_uplift = (
                    abs(
                        row[
                            "uplift"
                        ]
                    )
                    / current_scale
                )

                if relative_uplift > 4.0:
                    explosion_penalty += min(
                        25.0,
                        (
                            relative_uplift
                            - 4.0
                        ) ** 2
                        * 0.015,
                    )

            explosion_penalty /= max(
                1,
                game_count,
            )

            penalty = (
                beneficial_penalty
                + 0.75
                * rate_spread_penalty
                + concentration_penalty
                + explosion_penalty
            )

            return {
                "penalty": penalty,
                "profitable_games":
                    profitable_games,
                "game_count":
                    game_count,
                "largest_positive_share":
                    largest_positive_share,
                "rows":
                    game_rows,
            }

        def optimizer_key(settings):
            values = [
                float(
                    settings[
                        "proposed_games_per_5m"
                    ]
                ),
                int(
                    settings[
                        "proposed_slot_symbols"
                    ]
                ),
                float(
                    settings[
                        "proposed_slot_multiplier"
                    ]
                ),
                float(
                    settings[
                        "proposed_cockfight_start"
                    ]
                ),
                float(
                    settings[
                        "proposed_cockfight_max"
                    ]
                ),
                float(
                    settings[
                        "proposed_chicken_price"
                    ]
                ),
            ]

            for game in BET_LIMIT_GAMES:
                proposed = settings[
                    "games"
                ][game]["proposed"]
                values.extend(
                    [
                        float(proposed["min"]),
                        float(proposed["max"]),
                    ]
                )

            return tuple(values)

        def predictions_and_score(settings):
            key = optimizer_key(settings)
            predictions = prediction_cache.get(
                key
            )

            if predictions is None:
                predictions = self.evaluate_activity_group_monthly(
                    settings,
                    context,
                    use_actual_game_mix=use_actual_game_mix,
                )
                prediction_cache[key] = predictions

            balance = balance_cache.get(
                key
            )

            if balance is None:
                balance = evaluate_game_balance(
                    settings
                )
                balance_cache[key] = balance

            errors = []
            for group_name, target in targets.items():
                scale = max(
                    1000.0,
                    abs(float(target)),
                )
                errors.append(
                    (
                        (
                            predictions[group_name]
                            - float(target)
                        )
                        / scale
                    ) ** 2
                )

            target_error = (
                sum(errors) / len(errors)
                if errors
                else 0.0
            )

            change_penalty = 0.0
            for spec in specs:
                current_value = get_value(settings, spec)
                base_value = get_value(base, spec)
                scale = max(1.0, abs(base_value))
                change_penalty += (
                    (current_value - base_value) / scale
                ) ** 2

            # When the target is still far away, prioritize actually
            # moving toward it. Once the target is reasonably close, increase
            # the weight on keeping the normal games balanced and relevant.
            if target_error > 0.10:
                balance_weight = 0.06
            elif target_error > 0.02:
                balance_weight = 0.12
            else:
                balance_weight = 0.22

            score = (
                target_error
                + balance_weight
                * balance["penalty"]
                + 0.0005
                * change_penalty
            )

            return (
                predictions,
                score,
            )

        best_predictions, best_score = predictions_and_score(best)
        evaluations = 1

        # Coordinate descent alone can get stuck when several settings need to
        # move together before the target becomes better. Try a deterministic
        # set of joint candidates first, then polish the best one below.
        rng = random.Random(67)

        for iteration in range(700):
            if iteration < 250:
                candidate = copy.deepcopy(base)
                global_strength = 1.0
            else:
                candidate = copy.deepcopy(best)
                progress = (
                    iteration - 250
                ) / 450.0
                global_strength = max(
                    0.08,
                    0.55 * (1.0 - progress),
                )

            for spec in specs:
                if rng.random() > 0.55:
                    continue

                current_value = get_value(
                    candidate,
                    spec,
                )

                if iteration < 250 and rng.random() < 0.45:
                    candidate_value = rng.uniform(
                        spec["min"],
                        spec["max"],
                    )
                else:
                    span = (
                        spec["max"]
                        - spec["min"]
                    )
                    candidate_value = (
                        current_value
                        + rng.uniform(-1.0, 1.0)
                        * span
                        * global_strength
                    )

                set_value(
                    candidate,
                    spec,
                    candidate_value,
                )

            if not valid(candidate):
                continue

            predictions, score = predictions_and_score(
                candidate
            )
            evaluations += 1

            if score + 1e-12 < best_score:
                best = candidate
                best_score = score
                best_predictions = predictions

        phase_fractions = [
            0.50,
            0.25,
            0.10,
            0.05,
            0.02,
        ]

        for phase_index, fraction in enumerate(phase_fractions):
            improved_in_phase = True
            passes = 0

            while improved_in_phase and passes < 2:
                improved_in_phase = False
                passes += 1

                for spec in specs:
                    current_value = get_value(best, spec)

                    if spec["kind"] == "usage":
                        step = 2.0 if phase_index == 0 else 1.0
                    elif spec["kind"] == "slots":
                        step = 1.0
                    elif spec["kind"] == "multiplier":
                        step = max(
                            0.05,
                            [1.0, 0.5, 0.25, 0.10, 0.05][phase_index],
                        )
                    elif spec["kind"] == "chance":
                        step = [10.0, 5.0, 2.0, 1.0, 0.5][phase_index]
                    elif spec["kind"] == "price":
                        step = max(
                            1.0,
                            abs(current_value) * fraction,
                            5.0,
                        )
                    else:
                        step = max(
                            5.0,
                            abs(current_value) * fraction,
                        )

                    candidates = [
                        current_value - step,
                        current_value + step,
                    ]

                    for candidate_value in candidates:
                        candidate = copy.deepcopy(best)
                        set_value(
                            candidate,
                            spec,
                            candidate_value,
                        )

                        if not valid(candidate):
                            continue

                        predictions, score = predictions_and_score(candidate)
                        evaluations += 1

                        if score + 1e-12 < best_score:
                            best = candidate
                            best_score = score
                            best_predictions = predictions
                            improved_in_phase = True

        absolute_misses = [
            abs(
                best_predictions[group_name]
                - float(target)
            )
            for group_name, target in targets.items()
        ]

        final_balance = evaluate_game_balance(
            best
        )

        changed_settings = []
        for spec in specs:
            before = get_value(base, spec)
            after = get_value(best, spec)
            if not math.isclose(
                float(before),
                float(after),
                rel_tol=1e-9,
                abs_tol=1e-9,
            ):
                changed_settings.append(
                    spec["key"]
                )

        relative_misses = [
            abs(
                best_predictions[group_name]
                - float(target)
            )
            / max(
                1000.0,
                abs(float(target)),
            )
            for group_name, target
            in targets.items()
        ]

        return {
            "settings": best,
            "predictions": best_predictions,
            "score": best_score,
            "average_absolute_miss": (
                statistics.mean(absolute_misses)
                if absolute_misses
                else 0.0
            ),
            "evaluations": evaluations,
            "context": context,
            "game_balance": final_balance,
            "changed_settings": changed_settings,
            "max_relative_miss": (
                max(relative_misses)
                if relative_misses
                else 0.0
            ),
        }

    def build_reason_stats(self):
        grouped = defaultdict(list)

        for tx in self.transactions:
            grouped[tx["reason"]].append(tx)

        hours = self.get_analysis_hours()
        rows = []

        for reason, txs in grouped.items():
            net = sum(
                tx["total"]
                for tx in txs
            )

            earned = sum(
                tx["total"]
                for tx in txs
                if tx["total"] > 0
            )

            lost = -sum(
                tx["total"]
                for tx in txs
                if tx["total"] < 0
            )

            users = {
                tx["user_id"]
                for tx in txs
            }

            rows.append(
                {
                    "Reason": reason,
                    "Net Profit": net,
                    "Gross Earned": earned,
                    "Gross Lost": lost,
                    "Net / Hour": net / hours,
                    "Transactions": len(txs),
                    "Unique Users": len(users),
                }
            )

        rows.sort(
            key=lambda row: row["Net Profit"],
            reverse=True,
        )

        self.reason_stats = rows

    def build_hourly_stats(self):
        grouped = defaultdict(list)

        for tx in self.transactions:
            local_dt = tx["timestamp"].astimezone(
                LOCAL_TZ
            )

            hour = local_dt.replace(
                minute=0,
                second=0,
                microsecond=0,
            )

            grouped[hour].append(tx)

        rows = []

        for hour in sorted(grouped):
            txs = grouped[hour]

            net = sum(
                tx["total"]
                for tx in txs
            )

            earned = sum(
                tx["total"]
                for tx in txs
                if tx["total"] > 0
            )

            lost = -sum(
                tx["total"]
                for tx in txs
                if tx["total"] < 0
            )

            users = {
                tx["user_id"]
                for tx in txs
            }

            rows.append(
                {
                    "Hour": hour.strftime(
                        "%Y-%m-%d %H:00"
                    ),
                    "Net Profit": net,
                    "Gross Earned": earned,
                    "Gross Lost": lost,
                    "Transactions": len(txs),
                    "Active Users": len(users),
                }
            )

        self.hourly_stats = rows

    def build_daily_stats(self):
        grouped = defaultdict(list)

        for tx in self.transactions:
            day = (
                tx["timestamp"]
                .astimezone(LOCAL_TZ)
                .date()
            )

            grouped[day].append(tx)

        rows = []

        for day in sorted(grouped):
            txs = grouped[day]

            net = sum(
                tx["total"]
                for tx in txs
            )

            earned = sum(
                tx["total"]
                for tx in txs
                if tx["total"] > 0
            )

            lost = -sum(
                tx["total"]
                for tx in txs
                if tx["total"] < 0
            )

            users = {
                tx["user_id"]
                for tx in txs
            }

            rows.append(
                {
                    "Date": str(day),
                    "Net Profit": net,
                    "Gross Earned": earned,
                    "Gross Lost": lost,
                    "Transactions": len(txs),
                    "Active Users": len(users),
                }
            )

        self.daily_stats = rows

    def build_user_hour_stats(self):
        grouped = defaultdict(
            list
        )

        for tx in self.transactions:
            local_dt = (
                tx["timestamp"]
                .astimezone(
                    LOCAL_TZ
                )
            )

            hour = local_dt.replace(
                minute=0,
                second=0,
                microsecond=0,
            )

            grouped[
                (
                    tx["user_id"],
                    hour,
                )
            ].append(
                tx
            )

        rows = []

        for (
            user_id,
            hour,
        ), txs in grouped.items():

            net = sum(
                tx["total"]
                for tx in txs
            )

            earned = sum(
                tx["total"]
                for tx in txs
                if tx["total"] > 0
            )

            lost = -sum(
                tx["total"]
                for tx in txs
                if tx["total"] < 0
            )

            rows.append(
                {
                    "User ID":
                        user_id,

                    "Hour":
                        hour.strftime(
                            "%Y-%m-%d %H:00"
                        ),

                    "Net Profit":
                        net,

                    "Gross Earned":
                        earned,

                    "Gross Lost":
                        lost,

                    "Transactions":
                        len(txs),
                }
            )

        rows.sort(
            key=lambda row:
            row["Net Profit"],
            reverse=True,
        )

        self.user_hour_stats = rows

    def get_game_transactions(
        self,
        game,
        user_id=None,
    ):
        if user_id is None:
            return self.game_transactions.get(
                game,
                [],
            )

        return (
            self.user_game_transactions
            .get(
                str(user_id),
                {},
            )
            .get(
                game,
                [],
            )
        )

    def infer_game_bets(
        self,
        game,
        txs,
        current_slot_multiplier,
    ):
        bets = []

        if game == "slot machine":
            multiplier = max(
                0.000001,
                current_slot_multiplier,
            )

            for tx in txs:
                if tx[
                    "is_chicken_purchase"
                ]:
                    continue

                amount = tx[
                    "total"
                ]

                lower = (
                    tx[
                        "original_reason"
                    ]
                    .lower()
                )

                if amount < 0:
                    bets.append(
                        abs(
                            amount
                        )
                    )

                elif (
                    amount > 0
                    and (
                        "won" in lower
                        or "win" in lower
                    )
                ):
                    inferred = (
                        amount
                        / multiplier
                    )

                    if inferred > 0:
                        bets.append(
                            inferred
                        )

            return bets

        for tx in txs:
            if tx[
                "is_chicken_purchase"
            ]:
                continue

            if (
                tx["total"] < 0
                and is_explicit_bet_reason(
                    tx[
                        "original_reason"
                    ]
                )
            ):
                bets.append(
                    abs(
                        tx["total"]
                    )
                )

        if bets:
            return bets

        for tx in txs:
            if (
                tx["total"] < 0
                and not tx[
                    "is_chicken_purchase"
                ]
            ):
                bets.append(
                    abs(
                        tx["total"]
                    )
                )

        return bets

    def infer_chicken_price(self):
        prices = [
            abs(
                tx["total"]
            )
            for tx
            in self.transactions
            if (
                tx[
                    "is_chicken_purchase"
                ]
                and tx[
                    "total"
                ] < 0
            )
        ]

        return (
            safe_median(
                prices
            )
            if prices
            else DEFAULT_CHICKEN_PRICE
        )

    def get_simulation_base(
        self,
        game,
        txs,
        current_slot_multiplier,
    ):
        cache_key = (
            game,
            id(txs),
            float(current_slot_multiplier),
        )

        cached = self._simulation_base_cache.get(
            cache_key
        )
        if cached is not None:
            return cached

        bets = self.infer_game_bets(
            game,
            txs,
            current_slot_multiplier,
        )

        observed_net = sum(
            tx["total"]
            for tx in txs
        )
        observed_earned = sum(
            tx["total"]
            for tx in txs
            if tx["total"] > 0
        )
        observed_lost = -sum(
            tx["total"]
            for tx in txs
            if tx["total"] < 0
        )

        inferred_rounds = len(bets)
        fallback_rounds = sum(
            1
            for tx in txs
            if not tx.get(
                "is_chicken_purchase",
                False,
            )
        )
        observed_rounds = (
            inferred_rounds
            if inferred_rounds
            else fallback_rounds
        )

        result = {
            "bets": bets,
            "bet_count": len(bets),
            "old_stake": sum(bets),
            "observed_net": observed_net,
            "observed_earned": observed_earned,
            "observed_lost": observed_lost,
            "observed_rounds": observed_rounds,
        }

        if game == "animal race":
            purchase_net = 0.0
            purchase_earned = 0.0
            purchase_lost = 0.0
            race_net = 0.0
            race_earned = 0.0
            race_lost = 0.0

            for tx in txs:
                amount = tx["total"]

                if is_animal_race_purchase(
                    tx["original_reason"]
                ):
                    purchase_net += amount
                    if amount > 0:
                        purchase_earned += amount
                    elif amount < 0:
                        purchase_lost += -amount
                else:
                    race_net += amount
                    if amount > 0:
                        race_earned += amount
                    elif amount < 0:
                        race_lost += -amount

            result.update(
                {
                    "purchase_net": purchase_net,
                    "purchase_earned": purchase_earned,
                    "purchase_lost": purchase_lost,
                    "race_net": race_net,
                    "race_earned": race_earned,
                    "race_lost": race_lost,
                }
            )

        self._simulation_base_cache[
            cache_key
        ] = result

        return result

    def get_fast_mapped_stake(
        self,
        game,
        txs,
        base,
        current_min,
        current_max,
        proposed_min,
        proposed_max,
        current_slot_multiplier,
    ):
        bet_count = base["bet_count"]

        if bet_count <= 0:
            return 0.0

        normalized_key = (
            game,
            id(txs),
            float(current_slot_multiplier),
            float(current_min),
            float(current_max),
        )

        normalized_sum = self._normalized_bet_cache.get(
            normalized_key
        )

        if normalized_sum is None:
            if current_max <= current_min:
                normalized_sum = 0.0
            else:
                width = current_max - current_min
                total = 0.0

                for bet in base["bets"]:
                    normalized = (
                        float(bet) - current_min
                    ) / width

                    if normalized < 0.0:
                        normalized = 0.0
                    elif normalized > 1.0:
                        normalized = 1.0

                    total += normalized

                normalized_sum = total

            self._normalized_bet_cache[
                normalized_key
            ] = normalized_sum

        return (
            bet_count * proposed_min
            + normalized_sum
            * (
                proposed_max
                - proposed_min
            )
        )

    def simulate_game(
        self,
        game,
        txs,
        settings,
    ):
        current = (
            settings["games"].get(game, {})
            .get("current")
        )

        proposed = (
            settings["games"].get(game, {})
            .get("proposed")
        )

        current_usage = max(
            0.000001,
            settings[
                "current_games_per_5m"
            ],
        )

        proposed_usage = max(
            0.0,
            settings[
                "proposed_games_per_5m"
            ],
        )

        activity_scale = (
            proposed_usage
            / current_usage
        )

        base = self.get_simulation_base(
            game,
            txs,
            settings[
                "current_slot_multiplier"
            ],
        )

        bets = base["bets"]
        observed_net = base["observed_net"]
        observed_earned = base["observed_earned"]
        observed_lost = base["observed_lost"]
        observed_rounds = base["observed_rounds"]

        # Animal Race is handled differently from the other games.
        #
        # Race bets and race winnings scale when the proposed game activity
        # changes. Animal/provision purchases do not. A horse can be reused for
        # many races, so increasing the number of races must not pretend that
        # the user buys the same horse again for every additional race.
        #
        # Purchases remain at the rate actually seen in the selected history.
        # This also avoids inventing a race-to-provision relationship that is
        # not present in the database.
        if game == "animal race":
            purchase_net = base["purchase_net"]
            purchase_earned = base["purchase_earned"]
            purchase_lost = base["purchase_lost"]
            race_net = base["race_net"]
            race_earned = base["race_earned"]
            race_lost = base["race_lost"]

            current_avg_bet = (
                base["old_stake"]
                / base["bet_count"]
                if base["bet_count"]
                else 0
            )

            proposed_rounds = (
                observed_rounds
                * activity_scale
            )

            proposed_net = (
                purchase_net
                + race_net * activity_scale
            )

            proposed_earned = (
                purchase_earned
                + race_earned * activity_scale
            )

            proposed_lost = (
                purchase_lost
                + race_lost * activity_scale
            )

            return {
                "game": game,
                "observed_rounds": observed_rounds,
                "proposed_rounds": proposed_rounds,
                "current_avg_bet": current_avg_bet,
                "proposed_avg_bet": current_avg_bet,
                "observed_net": observed_net,
                "observed_earned": observed_earned,
                "observed_lost": observed_lost,
                "current_model_net": observed_net,
                "current_model_earned": observed_earned,
                "current_model_lost": observed_lost,
                "proposed_net": proposed_net,
                "proposed_earned": proposed_earned,
                "proposed_lost": proposed_lost,
                "activity_scale": activity_scale,
                "fixed_purchase_net": purchase_net,
                "fixed_purchase_earned": purchase_earned,
                "fixed_purchase_lost": purchase_lost,
                "race_net": race_net,
                "race_earned": race_earned,
                "race_lost": race_lost,
            }

        if not bets:
            return {
                "game":
                    game,

                "observed_rounds":
                    observed_rounds,

                "proposed_rounds":
                    (
                        observed_rounds
                        * activity_scale
                    ),

                "current_avg_bet":
                    0,

                "proposed_avg_bet":
                    0,

                "observed_net":
                    observed_net,

                "observed_earned":
                    observed_earned,

                "observed_lost":
                    observed_lost,

                "current_model_net":
                    observed_net,

                "current_model_earned":
                    observed_earned,

                "current_model_lost":
                    observed_lost,

                "proposed_net":
                    (
                        observed_net
                        * activity_scale
                    ),

                "proposed_earned":
                    (
                        observed_earned
                        * activity_scale
                    ),

                "proposed_lost":
                    (
                        observed_lost
                        * activity_scale
                    ),

                "activity_scale":
                    activity_scale,
            }

        old_stake = base["old_stake"]

        new_stake_base = self.get_fast_mapped_stake(
            game,
            txs,
            base,
            float(current["min"]),
            float(current["max"]),
            float(proposed["min"]),
            float(proposed["max"]),
            settings[
                "current_slot_multiplier"
            ],
        )

        current_avg_bet = (
            old_stake
            / base["bet_count"]
        )

        proposed_avg_bet = (
            new_stake_base
            / base["bet_count"]
        )

        proposed_rounds = (
            observed_rounds
            * activity_scale
        )

        if game == "slot machine":
            current_symbols = max(
                1,
                int(
                    settings[
                        "current_slot_symbols"
                    ]
                ),
            )

            proposed_symbols = max(
                1,
                int(
                    settings[
                        "proposed_slot_symbols"
                    ]
                ),
            )

            current_multiplier = max(
                0.0,
                settings[
                    "current_slot_multiplier"
                ],
            )

            proposed_multiplier = max(
                0.0,
                settings[
                    "proposed_slot_multiplier"
                ],
            )

            current_probability = (
                1.0
                / (
                    current_symbols ** 2
                )
            )

            proposed_probability = (
                1.0
                / (
                    proposed_symbols ** 2
                )
            )

            current_model_earned = (
                old_stake
                * current_probability
                * current_multiplier
            )

            current_model_lost = (
                old_stake
            )

            current_model_net = (
                current_model_earned
                - current_model_lost
            )

            proposed_stake = (
                new_stake_base
                * activity_scale
            )

            proposed_earned = (
                proposed_stake
                * proposed_probability
                * proposed_multiplier
            )

            proposed_lost = (
                proposed_stake
            )

            proposed_net = (
                proposed_earned
                - proposed_lost
            )

            return {
                "game":
                    game,

                "observed_rounds":
                    observed_rounds,

                "proposed_rounds":
                    proposed_rounds,

                "current_avg_bet":
                    current_avg_bet,

                "proposed_avg_bet":
                    proposed_avg_bet,

                "observed_net":
                    observed_net,

                "observed_earned":
                    observed_earned,

                "observed_lost":
                    observed_lost,

                "current_model_net":
                    current_model_net,

                "current_model_earned":
                    current_model_earned,

                "current_model_lost":
                    current_model_lost,

                "proposed_net":
                    proposed_net,

                "proposed_earned":
                    proposed_earned,

                "proposed_lost":
                    proposed_lost,

                "activity_scale":
                    activity_scale,

                "current_probability":
                    current_probability,

                "proposed_probability":
                    proposed_probability,
            }

        if game == "cockfight":
            current_win_rate = (
                effective_cockfight_win_rate(
                    settings[
                        "current_cockfight_start"
                    ],
                    settings[
                        "current_cockfight_max"
                    ],
                )
            )

            proposed_win_rate = (
                effective_cockfight_win_rate(
                    settings[
                        "proposed_cockfight_start"
                    ],
                    settings[
                        "proposed_cockfight_max"
                    ],
                )
            )

            current_chicken_price = max(
                0.0,
                settings[
                    "current_chicken_price"
                ],
            )

            proposed_chicken_price = max(
                0.0,
                settings[
                    "proposed_chicken_price"
                ],
            )

            current_model_earned = (
                old_stake
                * current_win_rate
                * 2
            )

            current_chicken_cost = (
                observed_rounds
                * (
                    1
                    - current_win_rate
                )
                * current_chicken_price
            )

            current_model_lost = (
                old_stake
                + current_chicken_cost
            )

            current_model_net = (
                current_model_earned
                - current_model_lost
            )

            proposed_stake = (
                new_stake_base
                * activity_scale
            )

            proposed_chicken_cost = (
                proposed_rounds
                * (
                    1
                    - proposed_win_rate
                )
                * proposed_chicken_price
            )

            proposed_earned = (
                proposed_stake
                * proposed_win_rate
                * 2
            )

            proposed_lost = (
                proposed_stake
                + proposed_chicken_cost
            )

            proposed_net = (
                proposed_earned
                - proposed_lost
            )

            return {
                "game":
                    game,

                "observed_rounds":
                    observed_rounds,

                "proposed_rounds":
                    proposed_rounds,

                "current_avg_bet":
                    current_avg_bet,

                "proposed_avg_bet":
                    proposed_avg_bet,

                "observed_net":
                    observed_net,

                "observed_earned":
                    observed_earned,

                "observed_lost":
                    observed_lost,

                "current_model_net":
                    current_model_net,

                "current_model_earned":
                    current_model_earned,

                "current_model_lost":
                    current_model_lost,

                "proposed_net":
                    proposed_net,

                "proposed_earned":
                    proposed_earned,

                "proposed_lost":
                    proposed_lost,

                "activity_scale":
                    activity_scale,

                "current_probability":
                    current_win_rate,

                "proposed_probability":
                    proposed_win_rate,
            }

        bet_scale = (
            new_stake_base
            / old_stake
            if old_stake > 0
            else 1.0
        )

        current_model_net = (
            observed_net
        )

        current_model_earned = (
            observed_earned
        )

        current_model_lost = (
            observed_lost
        )

        proposed_net = (
            observed_net
            * bet_scale
            * activity_scale
        )

        proposed_earned = (
            observed_earned
            * bet_scale
            * activity_scale
        )

        proposed_lost = (
            observed_lost
            * bet_scale
            * activity_scale
        )

        return {
            "game":
                game,

            "observed_rounds":
                observed_rounds,

            "proposed_rounds":
                proposed_rounds,

            "current_avg_bet":
                current_avg_bet,

            "proposed_avg_bet":
                proposed_avg_bet,

            "observed_net":
                observed_net,

            "observed_earned":
                observed_earned,

            "observed_lost":
                observed_lost,

            "current_model_net":
                current_model_net,

            "current_model_earned":
                current_model_earned,

            "current_model_lost":
                current_model_lost,

            "proposed_net":
                proposed_net,

            "proposed_earned":
                proposed_earned,

            "proposed_lost":
                proposed_lost,

            "activity_scale":
                activity_scale,
        }

    def get_activity_profile_per_day(
        self,
        user_id=None,
    ):
        """Return active hours/day and active days/day.

        Activity history is used only to estimate how much time somebody is
        active. It is NOT used to infer game counts or preferred games.
        """
        analysis_days = max(
            self.get_analysis_days(),
            1.0 / 24.0,
        )

        if user_id is None:
            total_active_hours = sum(
                float(
                    row["Est. Active Hrs"]
                )
                for row in self.user_stats
            )
            total_active_days = sum(
                float(
                    row["Active Days"]
                )
                for row in self.user_stats
            )

            return {
                "active_hours_per_day":
                    total_active_hours
                    / analysis_days,
                "active_days_per_day":
                    total_active_days
                    / analysis_days,
            }

        txs = self.get_user_transactions(
            user_id
        )
        activity = self.calculate_activity(
            txs
        )

        return {
            "active_hours_per_day":
                float(
                    activity[
                        "active_hours"
                    ]
                )
                / analysis_days,
            "active_days_per_day":
                float(
                    activity[
                        "active_days"
                    ]
                )
                / analysis_days,
        }

    def build_game_unit_metrics(
        self,
        settings,
    ):
        """Estimate economics for one play of every modeled game.

        Historical transactions are used to estimate bet behavior and game
        economics, but their historical frequency is ignored.
        """
        model_settings = copy.deepcopy(
            settings
        )

        # Neutralize the old activity multiplier inside simulate_game. The
        # fixed play count is applied later from the user's input.
        model_settings[
            "proposed_games_per_5m"
        ] = model_settings[
            "current_games_per_5m"
        ]

        total_active_days = sum(
            float(
                row["Active Days"]
            )
            for row in self.user_stats
        )

        metrics_by_game = {}

        for game in GAME_ORDER:
            txs = self.get_game_transactions(
                game
            )

            result = self.simulate_game(
                game,
                txs,
                model_settings,
            )

            current_rounds = float(
                result.get(
                    "observed_rounds",
                    0.0,
                )
            )
            proposed_rounds = float(
                result.get(
                    "proposed_rounds",
                    current_rounds,
                )
            )
            has_model_data = (
                current_rounds > 0
            )

            if game == "animal race":
                current_net_source = float(
                    result.get(
                        "race_net",
                        0.0,
                    )
                )
                current_earned_source = float(
                    result.get(
                        "race_earned",
                        0.0,
                    )
                )
                current_lost_source = float(
                    result.get(
                        "race_lost",
                        0.0,
                    )
                )

                proposed_net_source = (
                    current_net_source
                )
                proposed_earned_source = (
                    current_earned_source
                )
                proposed_lost_source = (
                    current_lost_source
                )
            else:
                current_net_source = float(
                    result.get(
                        "current_model_net",
                        0.0,
                    )
                )
                current_earned_source = float(
                    result.get(
                        "current_model_earned",
                        0.0,
                    )
                )
                current_lost_source = float(
                    result.get(
                        "current_model_lost",
                        0.0,
                    )
                )
                proposed_net_source = float(
                    result.get(
                        "proposed_net",
                        0.0,
                    )
                )
                proposed_earned_source = float(
                    result.get(
                        "proposed_earned",
                        0.0,
                    )
                )
                proposed_lost_source = float(
                    result.get(
                        "proposed_lost",
                        0.0,
                    )
                )

            current_denominator = max(
                1.0,
                current_rounds,
            )
            proposed_denominator = max(
                1.0,
                proposed_rounds,
            )

            metrics = {
                "has_model_data":
                    has_model_data,
                "current_net_per_play":
                    (
                        current_net_source
                        / current_denominator
                        if has_model_data
                        else 0.0
                    ),
                "current_earned_per_play":
                    (
                        current_earned_source
                        / current_denominator
                        if has_model_data
                        else 0.0
                    ),
                "current_lost_per_play":
                    (
                        current_lost_source
                        / current_denominator
                        if has_model_data
                        else 0.0
                    ),
                "proposed_net_per_play":
                    (
                        proposed_net_source
                        / proposed_denominator
                        if has_model_data
                        else 0.0
                    ),
                "proposed_earned_per_play":
                    (
                        proposed_earned_source
                        / proposed_denominator
                        if has_model_data
                        else 0.0
                    ),
                "proposed_lost_per_play":
                    (
                        proposed_lost_source
                        / proposed_denominator
                        if has_model_data
                        else 0.0
                    ),
                "current_avg_bet":
                    float(
                        result.get(
                            "current_avg_bet",
                            0.0,
                        )
                    ),
                "proposed_avg_bet":
                    float(
                        result.get(
                            "proposed_avg_bet",
                            0.0,
                        )
                    ),
                "current_probability":
                    result.get(
                        "current_probability"
                    ),
                "proposed_probability":
                    result.get(
                        "proposed_probability"
                    ),
                "fixed_purchase_net_per_active_day":
                    0.0,
                "fixed_purchase_earned_per_active_day":
                    0.0,
                "fixed_purchase_lost_per_active_day":
                    0.0,
            }

            if (
                game == "animal race"
                and total_active_days > 0
            ):
                metrics[
                    "fixed_purchase_net_per_active_day"
                ] = (
                    float(
                        result.get(
                            "fixed_purchase_net",
                            0.0,
                        )
                    )
                    / total_active_days
                )
                metrics[
                    "fixed_purchase_earned_per_active_day"
                ] = (
                    float(
                        result.get(
                            "fixed_purchase_earned",
                            0.0,
                        )
                    )
                    / total_active_days
                )
                metrics[
                    "fixed_purchase_lost_per_active_day"
                ] = (
                    float(
                        result.get(
                            "fixed_purchase_lost",
                            0.0,
                        )
                    )
                    / total_active_days
                )

            metrics_by_game[
                game
            ] = metrics

        return metrics_by_game

    def simulation_scope(
        self,
        settings,
        user_id=None,
        unit_metrics=None,
    ):
        if unit_metrics is None:
            unit_metrics = (
                self.build_game_unit_metrics(
                    settings
                )
            )

        profile = (
            self.get_activity_profile_per_day(
                user_id=user_id
            )
        )

        active_hours_per_day = max(
            0.0,
            float(
                profile[
                    "active_hours_per_day"
                ]
            ),
        )
        active_days_per_day = max(
            0.0,
            float(
                profile[
                    "active_days_per_day"
                ]
            ),
        )

        current_rate = max(
            0.0,
            float(
                settings[
                    "current_games_per_5m"
                ]
            ),
        )
        proposed_rate = max(
            0.0,
            float(
                settings[
                    "proposed_games_per_5m"
                ]
            ),
        )

        current_plays_each_game = (
            active_hours_per_day
            * 12.0
            * current_rate
        )
        proposed_plays_each_game = (
            active_hours_per_day
            * 12.0
            * proposed_rate
        )

        game_rows = []
        totals = defaultdict(float)

        for game in GAME_ORDER:
            metrics = unit_metrics.get(
                game,
                {},
            )

            current_net = (
                current_plays_each_game
                * float(
                    metrics.get(
                        "current_net_per_play",
                        0.0,
                    )
                )
            )
            current_earned = (
                current_plays_each_game
                * float(
                    metrics.get(
                        "current_earned_per_play",
                        0.0,
                    )
                )
            )
            current_lost = (
                current_plays_each_game
                * float(
                    metrics.get(
                        "current_lost_per_play",
                        0.0,
                    )
                )
            )

            proposed_net = (
                proposed_plays_each_game
                * float(
                    metrics.get(
                        "proposed_net_per_play",
                        0.0,
                    )
                )
            )
            proposed_earned = (
                proposed_plays_each_game
                * float(
                    metrics.get(
                        "proposed_earned_per_play",
                        0.0,
                    )
                )
            )
            proposed_lost = (
                proposed_plays_each_game
                * float(
                    metrics.get(
                        "proposed_lost_per_play",
                        0.0,
                    )
                )
            )

            # Animal/provision purchases are a fixed historical rate per active
            # day. They do not multiply just because race count increases.
            if game == "animal race":
                current_net += (
                    active_days_per_day
                    * float(
                        metrics.get(
                            "fixed_purchase_net_per_active_day",
                            0.0,
                        )
                    )
                )
                current_earned += (
                    active_days_per_day
                    * float(
                        metrics.get(
                            "fixed_purchase_earned_per_active_day",
                            0.0,
                        )
                    )
                )
                current_lost += (
                    active_days_per_day
                    * float(
                        metrics.get(
                            "fixed_purchase_lost_per_active_day",
                            0.0,
                        )
                    )
                )

                proposed_net += (
                    active_days_per_day
                    * float(
                        metrics.get(
                            "fixed_purchase_net_per_active_day",
                            0.0,
                        )
                    )
                )
                proposed_earned += (
                    active_days_per_day
                    * float(
                        metrics.get(
                            "fixed_purchase_earned_per_active_day",
                            0.0,
                        )
                    )
                )
                proposed_lost += (
                    active_days_per_day
                    * float(
                        metrics.get(
                            "fixed_purchase_lost_per_active_day",
                            0.0,
                        )
                    )
                )

            totals[
                "current_model_net"
            ] += current_net
            totals[
                "current_model_earned"
            ] += current_earned
            totals[
                "current_model_lost"
            ] += current_lost
            totals[
                "proposed_net"
            ] += proposed_net
            totals[
                "proposed_earned"
            ] += proposed_earned
            totals[
                "proposed_lost"
            ] += proposed_lost
            totals[
                "current_rounds"
            ] += current_plays_each_game
            totals[
                "proposed_rounds"
            ] += proposed_plays_each_game

            row = {
                "Game":
                    GAME_DISPLAY[game],
                "24h Current Games":
                    current_plays_each_game,
                "24h Proposed Games":
                    proposed_plays_each_game,
                "Current Avg Bet":
                    float(
                        metrics.get(
                            "current_avg_bet",
                            0.0,
                        )
                    ),
                "Proposed Avg Bet":
                    float(
                        metrics.get(
                            "proposed_avg_bet",
                            0.0,
                        )
                    ),
                "24h Current Net":
                    current_net,
                "24h Proposed Net":
                    proposed_net,
                "24h Change":
                    proposed_net
                    - current_net,
            }

            proposed_probability = (
                metrics.get(
                    "proposed_probability"
                )
            )

            if proposed_probability is not None:
                row[
                    "Proposed Win %"
                ] = (
                    float(
                        proposed_probability
                    )
                    * 100.0
                )
            else:
                row[
                    "Proposed Win %"
                ] = ""

            game_rows.append(
                row
            )

        summary = {
            "24h_observed_net":
                totals[
                    "current_model_net"
                ],
            "24h_current_model_net":
                totals[
                    "current_model_net"
                ],
            "24h_current_model_earned":
                totals[
                    "current_model_earned"
                ],
            "24h_current_model_lost":
                totals[
                    "current_model_lost"
                ],
            "24h_proposed_net":
                totals[
                    "proposed_net"
                ],
            "24h_proposed_earned":
                totals[
                    "proposed_earned"
                ],
            "24h_proposed_lost":
                totals[
                    "proposed_lost"
                ],
            "24h_change":
                totals[
                    "proposed_net"
                ]
                - totals[
                    "current_model_net"
                ],
            "24h_current_games":
                totals[
                    "current_rounds"
                ],
            "24h_proposed_games":
                totals[
                    "proposed_rounds"
                ],
            "normalization_factor":
                1.0,
            "active_hours_per_day":
                active_hours_per_day,
            "active_days_per_day":
                active_days_per_day,
            "current_plays_each_game_per_5m":
                current_rate,
            "proposed_plays_each_game_per_5m":
                proposed_rate,
        }

        return (
            game_rows,
            summary,
        )

    def run_simulation(
        self,
        settings,
    ):
        unit_metrics = (
            self.build_game_unit_metrics(
                settings
            )
        )

        game_rows, summary = self.simulation_scope(
            settings,
            unit_metrics=unit_metrics,
        )

        users = sorted({
            tx["user_id"]
            for tx in self.transactions
        })

        user_rows = []

        for user_id in users:
            _, user_summary = self.simulation_scope(
                settings,
                user_id=user_id,
                unit_metrics=unit_metrics,
            )

            user_rows.append(
                {
                    "User ID":
                        user_id,
                    "24h Current Net":
                        user_summary[
                            "24h_current_model_net"
                        ],
                    "24h Proposed Net":
                        user_summary[
                            "24h_proposed_net"
                        ],
                    "24h Change":
                        user_summary[
                            "24h_change"
                        ],
                    "24h Current Games":
                        user_summary[
                            "24h_current_games"
                        ],
                    "24h Proposed Games":
                        user_summary[
                            "24h_proposed_games"
                        ],
                }
            )

        user_rows.sort(
            key=lambda row:
                row[
                    "24h Proposed Net"
                ],
            reverse=True,
        )

        return (
            game_rows,
            user_rows,
            summary,
        )

    def run_user_simulation(
        self,
        user_id,
        settings,
    ):
        unit_metrics = (
            self.build_game_unit_metrics(
                settings
            )
        )

        return self.simulation_scope(
            settings,
            user_id=user_id,
            unit_metrics=unit_metrics,
        )

class RoundedButton(
    tk.Canvas
):
    def __init__(
        self,
        parent,
        text,
        command,
        width=120,
        height=38,
        bg=None,
        hover=None,
        fg="#FFFFFF",
        radius=13,
        font=("Bahnschrift", 9, "bold"),
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=parent.cget(
                "bg"
            ),
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
        )

        self.button_text = (
            text
        )

        self.command = (
            command
        )

        self.normal_bg = (
            bg
            if bg is not None
            else PRIMARY
        )

        self.hover_bg = (
            hover
            if hover is not None
            else PRIMARY_HOVER
        )

        self.fg = fg
        self.radius = radius
        self.font = font

        self.bind(
            "<Configure>",
            self._draw,
        )

        self.bind(
            "<Enter>",
            lambda event:
            self._draw(
                fill=self.hover_bg
            ),
        )

        self.bind(
            "<Leave>",
            lambda event:
            self._draw(
                fill=self.normal_bg
            ),
        )

        self.bind(
            "<Button-1>",
            lambda event:
            self.command(),
        )

    def set_text(self, text):
        self.button_text = text
        self._draw()

    def _draw(
        self,
        event=None,
        fill=None,
    ):
        self.delete(
            "all"
        )

        w = max(
            2,
            self.winfo_width(),
        )

        h = max(
            2,
            self.winfo_height(),
        )

        draw_round_rect(
            self,
            1,
            1,
            w - 1,
            h - 1,
            self.radius,
            fill or self.normal_bg,
        )

        self.create_text(
            w / 2,
            h / 2,
            text=self.button_text,
            fill=self.fg,
            font=self.font,
        )


class RoundedEntry(
    tk.Canvas
):
    def __init__(
        self,
        parent,
        textvariable=None,
        width=190,
        height=38,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=parent.cget(
                "bg"
            ),
            highlightthickness=0,
            borderwidth=0,
        )

        self.var = (
            textvariable
            or tk.StringVar()
        )

        self.entry = tk.Entry(
            self,
            textvariable=self.var,
            relief=tk.FLAT,
            bd=0,
            bg=CARD,
            fg=TEXT,
            insertbackground=TEXT,
            font=(
                "Segoe UI",
                9,
            ),
        )

        self.window = (
            self.create_window(
                12,
                height / 2,
                anchor="w",
                window=self.entry,
                height=24,
            )
        )

        self.bind(
            "<Configure>",
            self._draw,
        )

        self._draw()

    def _draw(
        self,
        event=None,
    ):
        self.delete(
            "shape"
        )

        w = max(
            2,
            self.winfo_width(),
        )

        h = max(
            2,
            self.winfo_height(),
        )

        shape = draw_round_rect(
            self,
            1,
            1,
            w - 1,
            h - 1,
            13,
            CARD,
            BORDER,
            1,
        )

        self.addtag_withtag(
            "shape",
            shape,
        )

        self.tag_lower(
            "shape"
        )

        self.itemconfigure(
            self.window,
            width=max(
                20,
                w - 24,
            ),
            height=24,
        )

    def bind_key(
        self,
        sequence,
        callback,
    ):
        self.entry.bind(
            sequence,
            callback,
        )


class RoundedPanel(
    tk.Canvas
):
    def __init__(
        self,
        parent,
        height,
        fill=None,
        radius=20,
        padding=16,
        outline=None,
    ):
        fill = (
            CARD
            if fill is None
            else fill
        )

        outline = (
            BORDER
            if outline is None
            else outline
        )

        super().__init__(
            parent,
            height=height,
            bg=parent.cget(
                "bg"
            ),
            highlightthickness=0,
            borderwidth=0,
        )

        self.panel_fill = (
            fill
        )

        self.radius = (
            radius
        )

        self.padding = (
            padding
        )

        self.outline = (
            outline
        )

        self.inner = tk.Frame(
            self,
            bg=fill,
        )

        self.window = (
            self.create_window(
                padding,
                padding,
                anchor="nw",
                window=self.inner,
            )
        )

        self.bind(
            "<Configure>",
            self._draw,
        )

    def _draw(
        self,
        event=None,
    ):
        self.delete(
            "shape"
        )

        w = max(
            2,
            self.winfo_width(),
        )

        h = max(
            2,
            self.winfo_height(),
        )

        shape = draw_round_rect(
            self,
            1,
            1,
            w - 1,
            h - 1,
            self.radius,
            self.panel_fill,
            self.outline,
            1,
        )

        self.addtag_withtag(
            "shape",
            shape,
        )

        self.tag_lower(
            "shape"
        )

        self.itemconfigure(
            self.window,
            width=max(
                10,
                w
                - self.padding
                * 2,
            ),
            height=max(
                10,
                h
                - self.padding
                * 2,
            ),
        )


class ExplanationCard(
    tk.Canvas
):
    def __init__(
        self,
        parent,
        text="",
        min_height=92,
        title="What this means",
    ):
        super().__init__(
            parent,
            height=min_height,
            bg=parent.cget("bg"),
            highlightthickness=0,
            borderwidth=0,
        )

        self.min_height = min_height

        self.inner = tk.Frame(
            self,
            bg=INFO_BG,
        )

        title_row = tk.Frame(
            self.inner,
            bg=INFO_BG,
        )
        title_row.pack(
            fill=tk.X,
            anchor="w",
        )

        self.title_label = tk.Label(
            title_row,
            text=title,
            bg=INFO_BG,
            fg=TEXT,
            justify=tk.LEFT,
            anchor="w",
            font=("Bahnschrift", 10, "bold"),
        )

        self.title_label.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
            anchor="w",
        )

        self.copy_button = RoundedButton(
            title_row,
            "Copy",
            self.copy_for_discord,
            width=68,
            height=30,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
            radius=10,
            font=(
                "Bahnschrift",
                8,
                "bold",
            ),
        )
        self.copy_button.pack(
            side=tk.RIGHT,
            padx=(10, 0),
        )

        self.body_label = tk.Label(
            self.inner,
            text=text,
            bg=INFO_BG,
            fg=TEXT,
            justify=tk.LEFT,
            anchor="w",
            font=(
                "Segoe UI",
                10,
            ),
        )

        self.body_label.pack(
            fill=tk.X,
            anchor="w",
            pady=(7, 0),
        )

        self.window = self.create_window(
            18,
            16,
            anchor="nw",
            window=self.inner,
        )

        self.bind(
            "<Configure>",
            self._on_configure,
        )

        self.after_idle(
            self._fit_height
        )

    def set_text(self, text):
        self.body_label.config(
            text=text
        )
        self.after_idle(
            self._fit_height
        )

    def copy_for_discord(self):
        title = self.title_label.cget(
            "text"
        ).strip()
        body = self.body_label.cget(
            "text"
        ).strip()

        if not body:
            return

        if title:
            clipboard_text = (
                f"**{title}**\n"
                f"{body}"
            )
        else:
            clipboard_text = body

        clipboard_text = (
            discord_trim_message(
                clipboard_text
            )
        )

        self.clipboard_clear()
        self.clipboard_append(
            clipboard_text
        )
        self.update()

        self.copy_button.set_text(
            "Copied"
        )
        self.after(
            1200,
            lambda:
                self.copy_button.set_text(
                    "Copy"
                ),
        )

    def _on_configure(
        self,
        event=None,
    ):
        width = max(
            100,
            self.winfo_width() - 36,
        )

        self.itemconfigure(
            self.window,
            width=width,
        )

        self.body_label.config(
            wraplength=max(
                80,
                width - 4,
            )
        )

        self._draw()
        self.after_idle(
            self._fit_height
        )

    def _fit_height(self):
        try:
            self.inner.update_idletasks()

            desired = max(
                self.min_height,
                self.inner.winfo_reqheight() + 32,
            )

            if abs(
                self.winfo_height() - desired
            ) > 2:
                self.configure(
                    height=desired
                )

            self._draw()

        except tk.TclError:
            pass

    def _draw(self):
        self.delete(
            "shape"
        )

        width = max(
            2,
            self.winfo_width(),
        )

        height = max(
            2,
            self.winfo_height(),
        )

        shape = draw_round_rect(
            self,
            1,
            1,
            width - 1,
            height - 1,
            18,
            INFO_BG,
            BORDER,
            1,
        )

        self.addtag_withtag(
            "shape",
            shape,
        )

        self.tag_lower(
            "shape"
        )

        self.inner.configure(
            bg=INFO_BG
        )

        self.title_label.configure(
            bg=INFO_BG,
            fg=TEXT,
        )

        self.body_label.configure(
            bg=INFO_BG,
            fg=TEXT,
        )


class KpiCard(
    tk.Canvas
):
    def __init__(
        self,
        parent,
        title,
        subtitle,
    ):
        super().__init__(
            parent,
            height=112,
            bg=parent.cget(
                "bg"
            ),
            highlightthickness=0,
            borderwidth=0,
        )

        self.title = title

        self.subtitle = (
            subtitle
        )

        self.value = "-"

        self.bind(
            "<Configure>",
            self._draw,
        )

    def set_value(
        self,
        value,
    ):
        self.value = value

        self._draw()

    def _draw(
        self,
        event=None,
    ):
        self.delete(
            "all"
        )

        w = max(
            2,
            self.winfo_width(),
        )

        h = max(
            2,
            self.winfo_height(),
        )

        draw_round_rect(
            self,
            1,
            1,
            w - 1,
            h - 1,
            18,
            CARD,
            BORDER,
            1,
        )

        self.create_text(
            18,
            18,
            anchor="nw",
            text=self.title,
            fill=MUTED,
            font=("Bahnschrift", 9, "bold"),
        )

        self.create_text(
            18,
            46,
            anchor="nw",
            text=self.value,
            fill=TEXT,
            font=("Bahnschrift", 20, "bold"),
        )

        self.create_text(
            18,
            84,
            anchor="nw",
            text=self.subtitle,
            fill=MUTED,
            font=(
                "Segoe UI",
                8,
            ),
        )


class StatusPill(
    tk.Canvas
):
    def __init__(
        self,
        parent,
    ):
        super().__init__(
            parent,
            width=124,
            height=30,
            bg=parent.cget(
                "bg"
            ),
            highlightthickness=0,
            borderwidth=0,
        )

        self.text = (
            "Applied"
        )

        self.fill = (
            SOFT_GREEN
        )

        self.fg = GREEN

        self.bind(
            "<Configure>",
            self._draw,
        )

        self._draw()

    def set_applied(self):
        self.text = (
            "Applied"
        )

        self.fill = (
            SOFT_GREEN
        )

        self.fg = GREEN

        self._draw()

    def set_pending(self):
        self.text = (
            "Changes pending"
        )

        self.fill = (
            SOFT_AMBER
        )

        self.fg = AMBER

        self._draw()

    def _draw(
        self,
        event=None,
    ):
        self.delete(
            "all"
        )

        w = max(
            2,
            self.winfo_width(),
        )

        h = max(
            2,
            self.winfo_height(),
        )

        draw_round_rect(
            self,
            1,
            1,
            w - 1,
            h - 1,
            14,
            self.fill,
        )

        self.create_text(
            w / 2,
            h / 2,
            text=self.text,
            fill=self.fg,
            font=("Bahnschrift", 8, "bold"),
        )


class RoundedMenuButton(
    tk.Canvas
):
    def __init__(
        self,
        parent,
        width=210,
        height=38,
        on_change=None,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=parent.cget(
                "bg"
            ),
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
        )

        self.display_text = ""

        self.on_change = (
            on_change
        )

        self.menu = tk.Menu(
            self,
            tearoff=0,
            bg=CARD,
            fg=TEXT,
            activebackground=SOFT_BLUE,
            activeforeground=TEXT,
            relief=tk.FLAT,
            bd=1,
        )

        self.bind(
            "<Configure>",
            self._draw,
        )

        self.bind(
            "<Button-1>",
            self._open_menu,
        )

    def _open_menu(
        self,
        event=None,
    ):
        self.menu.post(
            self.winfo_rootx(),
            self.winfo_rooty()
            + self.winfo_height()
            + 2,
        )

    def _draw(
        self,
        event=None,
    ):
        self.delete(
            "all"
        )

        w = max(
            2,
            self.winfo_width(),
        )

        h = max(
            2,
            self.winfo_height(),
        )

        draw_round_rect(
            self,
            1,
            1,
            w - 1,
            h - 1,
            13,
            CARD,
            BORDER,
            1,
        )

        self.create_text(
            12,
            h / 2,
            anchor="w",
            text=self.display_text,
            fill=TEXT,
            font=(
                "Segoe UI",
                9,
            ),
        )

        self.create_text(
            w - 16,
            h / 2 - 1,
            text="v",
            fill=MUTED,
            font=("Bahnschrift", 9, "bold"),
        )


class MultiSelectMenuButton(
    RoundedMenuButton
):
    def __init__(
        self,
        parent,
        title="Exclude",
        width=235,
        on_change=None,
    ):
        super().__init__(
            parent,
            width=width,
            on_change=on_change,
        )

        self.title = title

        self.variables = {}

        self.options = []

        self.display_text = (
            f"{title}: None"
        )

        self._draw()

    def set_options(
        self,
        options,
        preserve=True,
    ):
        old_selected = (
            self.get_selected()
            if preserve
            else set()
        )

        self.options = list(
            options
        )

        self.variables = {}

        self.menu.delete(
            0,
            tk.END,
        )

        for option in (
            self.options
        ):
            var = tk.BooleanVar(
                value=(
                    option
                    in old_selected
                )
            )

            self.variables[
                option
            ] = var

            self.menu.add_checkbutton(
                label=option,
                variable=var,
                command=self._changed,
            )

        if self.options:
            self.menu.add_separator()

        self.menu.add_command(
            label="Select all",
            command=self.select_all,
        )

        self.menu.add_command(
            label="Clear all",
            command=self.clear_all,
        )

        self._update_label()

    def get_selected(self):
        return {
            option
            for (
                option,
                var,
            )
            in self.variables.items()
            if var.get()
        }

    def select_all(self):
        for var in (
            self.variables.values()
        ):
            var.set(
                True
            )

        self._changed()

    def clear_all(self):
        for var in (
            self.variables.values()
        ):
            var.set(
                False
            )

        self._changed()

    def _changed(self):
        self._update_label()

        if self.on_change:
            self.on_change()

    def _update_label(self):
        selected = sorted(
            self.get_selected()
        )

        if not selected:
            self.display_text = (
                f"{self.title}: None"
            )

        elif len(selected) == 1:
            self.display_text = (
                f"{self.title}: "
                f"{selected[0]}"
            )

        elif len(selected) <= 2:
            self.display_text = (
                f"{self.title}: "
                + ", ".join(
                    selected
                )
            )

        else:
            self.display_text = (
                f"{self.title}: "
                f"{len(selected)} selected"
            )

        self._draw()


class SingleSelectMenuButton(
    RoundedMenuButton
):
    def __init__(
        self,
        parent,
        options,
        value=None,
        width=210,
        on_change=None,
    ):
        super().__init__(
            parent,
            width=width,
            on_change=on_change,
        )

        self.options = list(
            options
        )

        self.var = tk.StringVar(
            value=(
                value
                or self.options[0]
            )
        )

        self.rebuild_menu()

        self.display_text = (
            self.var.get()
        )

        self._draw()

    def rebuild_menu(self):
        self.menu.delete(
            0,
            tk.END,
        )

        for option in (
            self.options
        ):
            self.menu.add_radiobutton(
                label=option,
                variable=self.var,
                value=option,
                command=self._changed,
            )

    def get(self):
        return self.var.get()

    def set(
        self,
        value,
        notify=False,
    ):
        if (
            value
            not in self.options
        ):
            return

        self.var.set(
            value
        )

        self.display_text = (
            value
        )

        self._draw()

        if (
            notify
            and self.on_change
        ):
            self.on_change()

    def set_options(
        self,
        options,
        selected=None,
    ):
        self.options = list(
            options
        )

        self.rebuild_menu()

        if (
            selected
            in self.options
        ):
            self.set(
                selected
            )

        elif self.options:
            self.set(
                self.options[0]
            )

    def _changed(self):
        self.display_text = (
            self.var.get()
        )

        self._draw()

        if self.on_change:
            self.on_change()


class NavButton(
    tk.Canvas
):
    def __init__(
        self,
        parent,
        text,
        command,
        width=184,
        height=42,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=SIDEBAR_BG,
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
        )

        self.text = text

        self.command = (
            command
        )

        self.active = False

        self.hovered = False

        self.bind(
            "<Configure>",
            self._draw,
        )

        self.bind(
            "<Enter>",
            self._enter,
        )

        self.bind(
            "<Leave>",
            self._leave,
        )

        self.bind(
            "<Button-1>",
            lambda event:
            self.command(),
        )

    def set_active(
        self,
        active,
    ):
        self.active = active

        self._draw()

    def _enter(
        self,
        event=None,
    ):
        self.hovered = True

        self._draw()

    def _leave(
        self,
        event=None,
    ):
        self.hovered = False

        self._draw()

    def _draw(
        self,
        event=None,
    ):
        self.delete(
            "all"
        )

        w = max(
            2,
            self.winfo_width(),
        )

        h = max(
            2,
            self.winfo_height(),
        )

        if self.active:
            fill = PRIMARY
            fg = "#FFFFFF"

        elif self.hovered:
            fill = (
                SIDEBAR_HOVER
            )

            fg = "#FFFFFF"

        else:
            fill = SIDEBAR_BG
            fg = MUTED

        draw_round_rect(
            self,
            2,
            2,
            w - 2,
            h - 2,
            14,
            fill,
        )

        self.create_text(
            16,
            h / 2,
            anchor="w",
            text=self.text,
            fill=fg,
            font=("Bahnschrift", 9, "bold"),
        )


class ScrollableArea(
    tk.Frame
):
    def __init__(
        self,
        parent,
    ):
        super().__init__(
            parent,
            bg=APP_BG,
        )

        self.canvas = tk.Canvas(
            self,
            bg=APP_BG,
            highlightthickness=0,
            borderwidth=0,
        )

        self.scrollbar = ttk.Scrollbar(
            self,
            orient=tk.VERTICAL,
            command=self.canvas.yview,
        )

        self.canvas.configure(
            yscrollcommand=(
                self.scrollbar.set
            )
        )

        self.scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y,
        )

        self.canvas.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True,
        )

        self.content = tk.Frame(
            self.canvas,
            bg=APP_BG,
        )

        self.window_id = (
            self.canvas.create_window(
                (0, 0),
                window=self.content,
                anchor="nw",
            )
        )

        self.content.bind(
            "<Configure>",
            self._update_region,
        )

        self.canvas.bind(
            "<Configure>",
            self._resize_content,
        )

        self.canvas.bind_all(
            "<MouseWheel>",
            self._mousewheel,
        )

    def _update_region(
        self,
        event=None,
    ):
        self.canvas.configure(
            scrollregion=(
                self.canvas.bbox(
                    "all"
                )
            )
        )

    def _resize_content(
        self,
        event,
    ):
        self.canvas.itemconfigure(
            self.window_id,
            width=event.width,
        )

    def _mousewheel(
        self,
        event,
    ):
        try:
            widget_class = (
                event.widget
                .winfo_class()
            )

        except Exception:
            widget_class = ""

        if widget_class in {
            "Treeview",
            "Listbox",
            "Text",
        }:
            return

        pointer_x = (
            self.canvas
            .winfo_pointerx()
        )

        pointer_y = (
            self.canvas
            .winfo_pointery()
        )

        left = (
            self.canvas
            .winfo_rootx()
        )

        top = (
            self.canvas
            .winfo_rooty()
        )

        right = (
            left
            + self.canvas.winfo_width()
        )

        bottom = (
            top
            + self.canvas.winfo_height()
        )

        if (
            left
            <= pointer_x
            <= right
            and top
            <= pointer_y
            <= bottom
        ):
            self.canvas.yview_scroll(
                int(
                    -event.delta
                    / 120
                ),
                "units",
            )

    def scroll_to_top(self):
        self.canvas.yview_moveto(
            0
        )


class DataTable(
    tk.Frame
):
    def __init__(
        self,
        parent,
        height=16,
        double_click_callback=None,
    ):
        super().__init__(
            parent,
            bg=CARD,
        )

        self.data = []
        self.filtered_data = []
        self.columns = []

        self.sort_reverse = {}

        # Tables never scroll vertically. Small tables show every row.
        # Large tables use pages, so the user only ever needs the horizontal
        # scrollbar inside the table.
        self.page_size = 20
        self.page_index = 0
        self._filter_after_id = None
        self.natural_column_widths = {}

        # Use the same fonts as the ttk Treeview style so column sizing is
        # based on the actual rendered text instead of rough character counts.
        self.body_measure_font = tkfont.Font(
            family="Segoe UI",
            size=10,
        )
        self.heading_measure_font = tkfont.Font(
            family="Bahnschrift",
            size=10,
            weight="bold",
        )

        self.double_click_callback = (
            double_click_callback
        )

        self.last_click_x = 0
        self.last_click_y = 0

        toolbar = tk.Frame(
            self,
            bg=CARD,
        )

        toolbar.pack(
            fill=tk.X,
            pady=(0, 10),
        )

        tk.Label(
            toolbar,
            text="Search",
            bg=CARD,
            fg=MUTED,
            font=("Bahnschrift", 9, "bold"),
        ).pack(
            side=tk.LEFT
        )

        self.search_var = (
            tk.StringVar()
        )

        self.search_entry = (
            RoundedEntry(
                toolbar,
                textvariable=(
                    self.search_var
                ),
                width=230,
            )
        )

        self.search_entry.pack(
            side=tk.LEFT,
            padx=(8, 8),
        )

        self.search_entry.bind_key(
            "<KeyRelease>",
            self.schedule_filter,
        )

        RoundedButton(
            toolbar,
            "Clear",
            self.clear_search,
            width=72,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.LEFT
        )

        self.discord_copy_button = RoundedButton(
            toolbar,
            "Copy Discord",
            self.copy_discord_page,
            width=112,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        )
        self.discord_copy_button.pack(
            side=tk.LEFT,
            padx=(10, 0),
        )

        self.count_label = (
            tk.Label(
                toolbar,
                text="",
                bg=CARD,
                fg=MUTED,
                font=(
                    "Segoe UI",
                    10,
                ),
            )
        )

        self.count_label.pack(
            side=tk.RIGHT
        )

        RoundedButton(
            toolbar,
            "Next",
            self.next_page,
            width=62,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.RIGHT,
            padx=(6, 0),
        )

        RoundedButton(
            toolbar,
            "Prev",
            self.previous_page,
            width=62,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.RIGHT,
            padx=(10, 0),
        )

        holder = tk.Frame(
            self,
            bg=CARD,
        )

        holder.pack(
            fill=tk.X,
            expand=False,
        )

        holder.rowconfigure(
            0,
            weight=0,
        )

        holder.columnconfigure(
            0,
            weight=1,
        )

        self.table_holder = holder

        self.tree = ttk.Treeview(
            holder,
            show="headings",
            selectmode="extended",
            height=height,
        )

        x_scroll = ttk.Scrollbar(
            holder,
            orient=tk.HORIZONTAL,
            command=self.tree.xview,
        )

        self.tree.configure(
            xscrollcommand=(
                x_scroll.set
            ),
        )

        self.tree.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        x_scroll.grid(
            row=1,
            column=0,
            sticky="ew",
        )

        # Re-fit columns whenever the table area changes width. If all natural
        # content fits, the columns expand to use the full width instead of
        # leaving a large empty block on the right. If they do not fit, the
        # horizontal scrollbar is used.
        holder.bind(
            "<Configure>",
            self.fit_columns_to_viewport,
            add="+",
        )

        self.tree.tag_configure(
            "even",
            background=CARD,
        )

        self.tree.tag_configure(
            "odd",
            background=TABLE_ALT,
        )

        self.tree.bind(
            "<Control-c>",
            self.copy_selected,
        )

        self.tree.bind(
            "<Control-C>",
            self.copy_selected,
        )

        self.tree.bind(
            "<Double-1>",
            self.handle_double_click,
        )

        self.tree.bind(
            "<Button-3>",
            self.show_menu,
        )

        self.menu = tk.Menu(
            self,
            tearoff=0,
            bg=CARD,
            fg=TEXT,
            activebackground=SOFT_BLUE,
            activeforeground=TEXT,
            relief=tk.FLAT,
            bd=1,
        )

        self.menu.add_command(
            label="Copy cell",
            command=self.copy_cell,
        )

        self.menu.add_command(
            label="Copy row",
            command=self.copy_selected,
        )

        self.menu.add_separator()

        self.menu.add_command(
            label="Copy current page for Discord",
            command=self.copy_discord_page,
        )

    def clear_search(self):
        self.search_var.set(
            ""
        )

        self.apply_filter()

    def set_data(
        self,
        data,
    ):
        self.data = list(
            data
        )

        self.filtered_data = list(
            data
        )
        self.page_index = 0

        self.tree.delete(
            *self.tree.get_children()
        )

        if not data:
            self.columns = []

            self.tree[
                "columns"
            ] = []

            self.count_label.config(
                text="0 rows"
            )
            self.tree.configure(
                height=1
            )
            self.after_idle(
                self.fit_parent_panel_to_content
            )

            return

        self.columns = list(
            data[0].keys()
        )

        self.tree[
            "columns"
        ] = self.columns

        text_columns = {
            "Reason",
            "Original Reason",
            "Top Income Source",
            "Group",
            "Most Played Game",
            "Game Mix",
            "User ID",
            "Username",
            "Timestamp",
            "First Seen",
            "Last Seen",
            "Hour",
            "Date",
            "Statistic",
            "Value",
            "Game",
        }

        for column in (
            self.columns
        ):
            self.tree.heading(
                column,
                text=column,
                command=lambda c=column:
                self.sort_by(c),
            )

            width = self.calculate_column_width(
                column
            )
            self.natural_column_widths[
                column
            ] = width

            self.tree.column(
                column,
                width=width,
                minwidth=max(
                    85,
                    self.heading_measure_font.measure(
                        str(column)
                    ) + 24,
                ),
                stretch=False,
                anchor=(
                    tk.W
                    if column
                    in text_columns
                    else tk.E
                ),
            )

        self.after_idle(
            self.fit_columns_to_viewport
        )
        self.refresh()

    def display_value(
        self,
        value,
    ):
        if isinstance(
            value,
            float,
        ):
            return format_number(
                value
            )

        if isinstance(
            value,
            int,
        ):
            return f"{value:,}"

        return str(
            value
        )

    def calculate_column_width(
        self,
        column,
    ):
        """Return the exact content-driven width for a table column.

        There is deliberately no small hard maximum. Long content is allowed
        to make the table wider because every table has a horizontal scrollbar.
        """
        heading_width = (
            self.heading_measure_font.measure(
                str(column)
            )
            + 36
        )

        max_cell_width = 0

        for row in self.data:
            value = self.display_value(
                row.get(
                    column,
                    "",
                )
            )

            measured = (
                self.body_measure_font.measure(
                    value
                )
                + 32
            )

            if measured > max_cell_width:
                max_cell_width = measured

        return int(
            max(
                96,
                heading_width,
                max_cell_width,
            )
        )

    def fit_columns_to_viewport(
        self,
        event=None,
    ):
        """Fill spare horizontal space, otherwise preserve natural widths."""
        if not self.columns:
            return

        try:
            available = (
                event.width
                if event is not None
                else self.table_holder.winfo_width()
            )

            available = max(
                1,
                int(available) - 4,
            )

            natural = [
                int(
                    self.natural_column_widths.get(
                        column,
                        100,
                    )
                )
                for column in self.columns
            ]

            total_natural = sum(
                natural
            )

            if total_natural >= available:
                widths = natural
            else:
                extra = (
                    available
                    - total_natural
                )
                base_extra = (
                    extra
                    // len(self.columns)
                )
                remainder = (
                    extra
                    % len(self.columns)
                )

                widths = [
                    width
                    + base_extra
                    + (
                        1
                        if index < remainder
                        else 0
                    )
                    for index, width
                    in enumerate(natural)
                ]

            for column, width in zip(
                self.columns,
                widths,
            ):
                self.tree.column(
                    column,
                    width=int(width),
                )

        except Exception:
            pass

    def refresh(self):
        self.tree.delete(
            *self.tree.get_children()
        )

        total_rows = len(
            self.filtered_data
        )

        max_page = max(
            0,
            (
                total_rows - 1
            ) // self.page_size
            if total_rows
            else 0,
        )
        self.page_index = min(
            self.page_index,
            max_page,
        )

        start = (
            self.page_index
            * self.page_size
        )
        end = min(
            total_rows,
            start + self.page_size,
        )

        visible_rows = self.filtered_data[
            start:end
        ]

        for (
            local_index,
            row,
        ) in enumerate(
            visible_rows
        ):
            values = []

            for column in (
                self.columns
            ):
                value = row.get(
                    column,
                    "",
                )

                value = self.display_value(
                    value
                )

                values.append(
                    value
                )

            absolute_index = (
                start
                + local_index
            )

            self.tree.insert(
                "",
                tk.END,
                values=values,
                tags=(
                    "even"
                    if absolute_index % 2 == 0
                    else "odd",
                ),
            )

        if total_rows:
            self.count_label.config(
                text=(
                    f"{start + 1:,}-{end:,} of "
                    f"{total_rows:,} rows"
                )
            )
        else:
            self.count_label.config(
                text="0 rows"
            )

        self.auto_fit_height(
            len(visible_rows)
        )

    def auto_fit_height(
        self,
        visible_row_count,
    ):
        """Show every row on the current page with no vertical table scroll."""
        desired_rows = max(
            1,
            int(visible_row_count),
        )

        self.tree.configure(
            height=desired_rows
        )

        self.after_idle(
            self.fit_parent_panel_to_content
        )
        self.after(
            60,
            self.fit_parent_panel_to_content,
        )

    def fit_parent_panel_to_content(
        self,
    ):
        try:
            widget = self.master
            panel = None

            while widget is not None:
                if isinstance(
                    widget,
                    RoundedPanel,
                ):
                    panel = widget
                    break

                widget = getattr(
                    widget,
                    "master",
                    None,
                )

            if panel is None:
                return

            panel.update_idletasks()
            panel.inner.update_idletasks()

            requested_inner_height = (
                panel.inner.winfo_reqheight()
            )

            desired_panel_height = max(
                112,
                requested_inner_height
                + panel.padding * 2
                + 6,
            )

            current_height = int(
                float(
                    panel.cget(
                        "height"
                    )
                )
            )

            if abs(
                current_height
                - desired_panel_height
            ) > 2:
                panel.configure(
                    height=int(
                        desired_panel_height
                    )
                )

        except Exception:
            pass

    def schedule_filter(
        self,
        event=None,
    ):
        if self._filter_after_id is not None:
            try:
                self.after_cancel(
                    self._filter_after_id
                )
            except Exception:
                pass

        self._filter_after_id = self.after(
            250,
            self.apply_filter,
        )

    def previous_page(
        self,
    ):
        if self.page_index > 0:
            self.page_index -= 1
            self.refresh()

    def next_page(
        self,
    ):
        if (
            (self.page_index + 1)
            * self.page_size
            < len(self.filtered_data)
        ):
            self.page_index += 1
            self.refresh()

    def apply_filter(
        self,
        event=None,
    ):
        self._filter_after_id = None
        self.page_index = 0

        text = (
            self.search_var
            .get()
            .lower()
            .strip()
        )

        if not text:
            self.filtered_data = list(
                self.data
            )

        else:
            self.filtered_data = [
                row
                for row in self.data
                if text in " ".join(
                    str(value).lower()
                    for value
                    in row.values()
                )
            ]

        self.refresh()

    def sort_by(
        self,
        column,
    ):
        reverse = (
            self.sort_reverse
            .get(
                column,
                False,
            )
        )

        def key(row):
            value = row.get(
                column
            )

            if value is None:
                return (
                    2,
                    "",
                )

            if isinstance(
                value,
                (
                    int,
                    float,
                ),
            ):
                return (
                    0,
                    value,
                )

            return (
                1,
                str(
                    value
                ).lower(),
            )

        self.filtered_data.sort(
            key=key,
            reverse=reverse,
        )

        self.sort_reverse[
            column
        ] = not reverse

        self.page_index = 0
        self.refresh()

    def get_selected_row(self):
        selected = (
            self.tree.selection()
        )

        if not selected:
            return None

        values = (
            self.tree.item(
                selected[0],
                "values",
            )
        )

        if not values:
            return None

        return dict(
            zip(
                self.columns,
                values,
            )
        )

    def handle_double_click(
        self,
        event,
    ):
        item = (
            self.tree.identify_row(
                event.y
            )
        )

        if item:
            self.tree.selection_set(
                item
            )

        if (
            self.double_click_callback
        ):
            row = (
                self.get_selected_row()
            )

            if row:
                self.double_click_callback(
                    row
                )

            return

        self._copy_clicked_cell(
            event.x,
            event.y,
        )

    def show_menu(
        self,
        event,
    ):
        self.last_click_x = (
            event.x
        )

        self.last_click_y = (
            event.y
        )

        item = (
            self.tree.identify_row(
                event.y
            )
        )

        if item:
            self.tree.selection_set(
                item
            )

        try:
            self.menu.tk_popup(
                event.x_root,
                event.y_root,
            )

        finally:
            self.menu.grab_release()

    def infer_discord_title(
        self,
    ):
        columns = set(
            self.columns
        )

        if {
            "Reason",
            "Net Profit",
            "Unique Users",
        }.issubset(columns):
            return "Income Sources"

        if {
            "Group",
            "Members",
        }.issubset(columns):
            return "Activity Groups"

        if {
            "Game",
            "Users Played",
            "Avg Plays / Player / Day",
        }.issubset(columns):
            return "Activity Group Game Averages"

        if {
            "Game",
            "24h Current Net",
            "24h Proposed Net",
        }.issubset(columns):
            return "Game Simulation"

        if (
            {
                "Timestamp",
                "Original Reason",
            }.issubset(
                columns
            )
            and (
                "Username" in columns
                or "User ID" in columns
            )
        ):
            return "Transactions"

        if (
            "30d Net" in columns
            and (
                "Username" in columns
                or "User ID" in columns
            )
        ):
            return "Users"

        if {
            "Statistic",
            "Value",
        }.issubset(columns):
            return "Summary"

        if "Hour" in columns:
            return "Hourly Results"

        if "Date" in columns:
            return "Daily Results"

        return "Economy Analytics"

    def get_current_page_rows(
        self,
    ):
        total_rows = len(
            self.filtered_data
        )

        start = (
            self.page_index
            * self.page_size
        )

        end = min(
            total_rows,
            start + self.page_size,
        )

        return (
            start,
            end,
            self.filtered_data[
                start:end
            ],
        )

    def build_discord_table(
        self,
    ):
        if (
            not self.columns
            or not self.filtered_data
        ):
            return ""

        start, end, rows = (
            self.get_current_page_rows()
        )

        if not rows:
            return ""

        headers = [
            DISCORD_HEADER_NAMES.get(
                column,
                column,
            )
            for column in self.columns
        ]

        cell_rows = []

        for row in rows:
            cell_rows.append(
                [
                    discord_short_value(
                        row.get(
                            column,
                            "",
                        ),
                        column,
                    )
                    for column
                    in self.columns
                ]
            )

        widths = []

        for column_index, header in enumerate(
            headers
        ):
            maximum = len(
                discord_clean_text(
                    header
                )
            )

            for row in cell_rows:
                maximum = max(
                    maximum,
                    len(
                        row[
                            column_index
                        ]
                    ),
                )

            widths.append(
                maximum
            )

        numeric_columns = []

        for column_name in self.columns:
            raw_values = [
                row.get(
                    column_name,
                    "",
                )
                for row in rows
            ]

            nonempty = [
                raw
                for raw in raw_values
                if raw != ""
            ]

            numeric_columns.append(
                bool(nonempty)
                and all(
                    isinstance(
                        raw,
                        (
                            int,
                            float,
                        ),
                    )
                    for raw in nonempty
                )
            )

        def line_for(
            values,
        ):
            parts = []

            for index, value in enumerate(
                values
            ):
                value = str(
                    value
                )

                if numeric_columns[
                    index
                ]:
                    parts.append(
                        value.rjust(
                            widths[index]
                        )
                    )
                else:
                    parts.append(
                        value.ljust(
                            widths[index]
                        )
                    )

            return "  ".join(
                parts
            ).rstrip()

        header_line = line_for(
            headers
        )

        separator = "  ".join(
            "-" * width
            for width in widths
        )

        data_lines = [
            line_for(
                row
            )
            for row in cell_rows
        ]

        title = self.infer_discord_title()

        total_rows = len(
            self.filtered_data
        )

        page_note = ""

        if total_rows > len(rows):
            page_note = (
                f" | rows "
                f"{start + 1}-{end} "
                f"of {total_rows}"
            )

        prefix = (
            f"**{title}**"
            f"{page_note}\n"
            "```text\n"
        )
        suffix = "\n```"

        kept_lines = []
        trimmed_count = 0

        for data_line in data_lines:
            candidate_lines = [
                header_line,
                separator,
                *kept_lines,
                data_line,
            ]

            candidate = (
                prefix
                + "\n".join(
                    candidate_lines
                )
                + suffix
            )

            if len(
                candidate
            ) <= DISCORD_SAFE_MESSAGE_LENGTH:
                kept_lines.append(
                    data_line
                )
            else:
                trimmed_count += 1

        body_lines = [
            header_line,
            separator,
            *kept_lines,
        ]

        if trimmed_count:
            body_lines.append(
                f"... {trimmed_count} more row"
                f"{'s' if trimmed_count != 1 else ''}"
                " on this page"
            )

        result = (
            prefix
            + "\n".join(
                body_lines
            )
            + suffix
        )

        if len(
            result
        ) > DISCORD_SAFE_MESSAGE_LENGTH:
            first = rows[0]
            compact_lines = []

            for column in self.columns:
                label = DISCORD_HEADER_NAMES.get(
                    column,
                    column,
                )
                value = discord_short_value(
                    first.get(
                        column,
                        "",
                    ),
                    column,
                )

                compact_lines.append(
                    f"{label}: {value}"
                )

            result = (
                f"**{title}**\n"
                "```text\n"
                + "\n".join(
                    compact_lines
                )
                + "\n```"
            )

        return discord_trim_message(
            result
        )

    def copy_discord_page(self):
        clipboard_text = (
            self.build_discord_table()
        )

        if not clipboard_text:
            return

        self.clipboard_clear()
        self.clipboard_append(
            clipboard_text
        )
        self.update()

        self.discord_copy_button.set_text(
            "Copied"
        )

        self.after(
            1200,
            lambda:
                self.discord_copy_button.set_text(
                    "Copy Discord"
                ),
        )

    def copy_selected(
        self,
        event=None,
    ):
        selected = (
            self.tree.selection()
        )

        if not selected:
            return "break"

        rows = []

        for item in selected:
            values = (
                self.tree.item(
                    item,
                    "values",
                )
            )

            rows.append(
                "\t".join(
                    str(value)
                    for value
                    in values
                )
            )

        self.clipboard_clear()

        self.clipboard_append(
            "\n".join(
                rows
            )
        )

        self.update()

        return "break"

    def _copy_clicked_cell(
        self,
        x,
        y,
    ):
        item = (
            self.tree.identify_row(
                y
            )
        )

        column_id = (
            self.tree.identify_column(
                x
            )
        )

        if (
            not item
            or not column_id
        ):
            return

        try:
            index = int(
                column_id.replace(
                    "#",
                    "",
                )
            ) - 1

        except ValueError:
            return

        values = (
            self.tree.item(
                item,
                "values",
            )
        )

        if (
            0
            <= index
            < len(values)
        ):
            self.clipboard_clear()

            self.clipboard_append(
                str(
                    values[index]
                )
            )

            self.update()

    def copy_cell(self):
        self._copy_clicked_cell(
            self.last_click_x,
            self.last_click_y,
        )

    def export_csv(self):
        if not self.filtered_data:
            return

        path = (
            filedialog
            .asksaveasfilename(
                defaultextension=".csv",
                filetypes=[
                    (
                        "CSV files",
                        "*.csv",
                    )
                ],
            )
        )

        if not path:
            return

        with open(
            path,
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=self.columns,
            )

            writer.writeheader()

            writer.writerows(
                self.filtered_data
            )


class PlotCanvas(tk.Frame):
    """Lightweight chart renderer using only Tkinter.

    This keeps the project dependency-free while still supporting useful bar,
    line, scatter and histogram plots inside the desktop app.
    """
    def __init__(
        self,
        parent,
        height=500,
    ):
        super().__init__(
            parent,
            bg=CARD,
        )

        self.default_height = int(
            height
        )
        self.plot_rows = []
        self.chart_type = "Bar"
        self.x_label = ""
        self.y_labels = []
        self.title = ""
        self.message = (
            "Choose what to plot, then press Plot."
        )

        self.canvas = tk.Canvas(
            self,
            bg=CARD,
            highlightthickness=0,
            bd=0,
            height=self.default_height,
        )
        self.canvas.pack(
            fill=tk.BOTH,
            expand=True,
        )
        self.canvas.bind(
            "<Configure>",
            lambda event:
                self.redraw(),
        )

    def set_message(
        self,
        message,
    ):
        self.message = str(
            message
        )
        self.plot_rows = []
        self.redraw()

    def set_plot(
        self,
        rows,
        chart_type,
        x_label,
        y_labels,
        title,
    ):
        self.plot_rows = list(
            rows
        )
        self.chart_type = str(
            chart_type
        )
        self.x_label = str(
            x_label
        )
        self.y_labels = list(
            y_labels
        )
        self.title = str(
            title
        )
        self.message = ""
        self.redraw()

    def compact_number(
        self,
        value,
    ):
        try:
            number = float(
                value
            )
        except Exception:
            return str(
                value
            )

        absolute = abs(
            number
        )

        if absolute >= 1_000_000_000:
            return (
                f"{number / 1_000_000_000:.1f}B"
            )
        if absolute >= 1_000_000:
            return (
                f"{number / 1_000_000:.1f}M"
            )
        if absolute >= 10_000:
            return (
                f"{number / 1_000:.1f}K"
            )
        if absolute >= 1_000:
            return f"{number:,.0f}"
        if absolute >= 100:
            return f"{number:,.1f}"
        return f"{number:,.2f}"

    def _draw_text(
        self,
        x,
        y,
        text,
        **kwargs,
    ):
        defaults = {
            "fill": TEXT,
            "font": (
                "Segoe UI",
                9,
            ),
        }
        defaults.update(
            kwargs
        )
        self.canvas.create_text(
            x,
            y,
            text=text,
            **defaults,
        )

    def _series_colors(self):
        return [
            PRIMARY,
            ACCENT_TEXT,
        ]

    def redraw(self):
        self.canvas.delete(
            "all"
        )

        width = max(
            300,
            self.canvas.winfo_width(),
        )
        height = max(
            260,
            self.canvas.winfo_height(),
        )

        if not self.plot_rows:
            self._draw_text(
                width / 2,
                height / 2,
                self.message
                or "No plot data",
                fill=MUTED,
                font=(
                    "Segoe UI",
                    11,
                ),
                width=max(
                    260,
                    width - 100,
                ),
                justify=tk.CENTER,
            )
            return

        if self.title:
            self._draw_text(
                24,
                18,
                self.title,
                anchor="nw",
                font=(
                    "Bahnschrift",
                    12,
                    "bold",
                ),
            )

        if self.chart_type == "Histogram":
            self._draw_histogram(
                width,
                height,
            )
        elif self.chart_type == "Scatter":
            self._draw_scatter(
                width,
                height,
            )
        elif self.chart_type == "Line":
            self._draw_line(
                width,
                height,
            )
        else:
            self._draw_bar(
                width,
                height,
            )

    def _plot_area(
        self,
        width,
        height,
    ):
        left = 82
        right = 30
        top = 58
        bottom = 100

        return (
            left,
            top,
            max(
                left + 40,
                width - right,
            ),
            max(
                top + 40,
                height - bottom,
            ),
        )

    def _draw_y_axis(
        self,
        x0,
        y0,
        x1,
        y1,
        minimum,
        maximum,
        force_zero=False,
    ):
        if force_zero:
            minimum = min(
                minimum,
                0.0,
            )
            maximum = max(
                maximum,
                0.0,
            )

        if math.isclose(
            minimum,
            maximum,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            pad = max(
                1.0,
                abs(minimum) * 0.1,
            )
            minimum -= pad
            maximum += pad

        span = maximum - minimum
        pad = span * 0.08
        minimum -= pad
        maximum += pad
        span = maximum - minimum

        ticks = 5

        for index in range(
            ticks + 1
        ):
            fraction = (
                index / ticks
            )
            value = (
                maximum
                - fraction * span
            )
            y = (
                y0
                + fraction
                * (y1 - y0)
            )

            self.canvas.create_line(
                x0,
                y,
                x1,
                y,
                fill=BORDER,
                width=1,
            )
            self._draw_text(
                x0 - 10,
                y,
                self.compact_number(
                    value
                ),
                anchor="e",
                fill=MUTED,
                font=(
                    "Segoe UI",
                    8,
                ),
            )

        self.canvas.create_line(
            x0,
            y0,
            x0,
            y1,
            fill=MUTED,
            width=1,
        )
        self.canvas.create_line(
            x0,
            y1,
            x1,
            y1,
            fill=MUTED,
            width=1,
        )

        def y_for(value):
            return (
                y1
                - (
                    (float(value) - minimum)
                    / span
                )
                * (y1 - y0)
            )

        return (
            y_for,
            minimum,
            maximum,
        )

    def _draw_axis_titles(
        self,
        x0,
        y0,
        x1,
        y1,
    ):
        if self.x_label:
            self._draw_text(
                (x0 + x1) / 2,
                y1 + 76,
                self.x_label,
                fill=MUTED,
                font=(
                    "Bahnschrift",
                    9,
                    "bold",
                ),
            )

        if self.y_labels:
            label = " / ".join(
                self.y_labels
            )
            self._draw_text(
                18,
                (y0 + y1) / 2,
                label,
                fill=MUTED,
                font=(
                    "Bahnschrift",
                    9,
                    "bold",
                ),
                angle=90,
            )

    def _draw_legend(
        self,
        width,
    ):
        if len(
            self.y_labels
        ) <= 1:
            return

        colors = self._series_colors()
        x = max(
            120,
            width - 300,
        )
        y = 26

        for index, label in enumerate(
            self.y_labels[:2]
        ):
            color = colors[
                index
            ]
            self.canvas.create_rectangle(
                x,
                y - 6,
                x + 14,
                y + 6,
                fill=color,
                outline="",
            )
            self._draw_text(
                x + 20,
                y,
                label,
                anchor="w",
                fill=MUTED,
                font=(
                    "Segoe UI",
                    8,
                ),
            )
            x += max(
                110,
                len(label) * 7 + 40,
            )

    def _category_label_indices(
        self,
        count,
    ):
        if count <= 12:
            return set(
                range(count)
            )

        step = max(
            1,
            math.ceil(
                count / 12
            ),
        )

        indices = set(
            range(
                0,
                count,
                step,
            )
        )
        indices.add(
            count - 1
        )
        return indices

    def _draw_bar(
        self,
        width,
        height,
    ):
        x0, y0, x1, y1 = (
            self._plot_area(
                width,
                height,
            )
        )

        values = []
        for row in self.plot_rows:
            values.append(
                float(row["y1"])
            )
            if row.get(
                "y2"
            ) is not None:
                values.append(
                    float(row["y2"])
                )

        y_for, minimum, maximum = (
            self._draw_y_axis(
                x0,
                y0,
                x1,
                y1,
                min(values),
                max(values),
                force_zero=True,
            )
        )

        zero_y = y_for(
            0.0
        )
        colors = self._series_colors()
        count = len(
            self.plot_rows
        )
        slot = (
            (x1 - x0)
            / max(
                1,
                count,
            )
        )
        has_second = any(
            row.get(
                "y2"
            ) is not None
            for row in self.plot_rows
        )
        group_width = min(
            slot * 0.76,
            52,
        )
        bar_width = (
            group_width / 2
            if has_second
            else group_width
        )

        label_indices = (
            self._category_label_indices(
                count
            )
        )

        for index, row in enumerate(
            self.plot_rows
        ):
            center = (
                x0
                + slot * (
                    index + 0.5
                )
            )

            series_values = [
                row["y1"]
            ]
            if has_second:
                series_values.append(
                    row.get(
                        "y2",
                        0.0,
                    )
                )

            for series_index, value in enumerate(
                series_values
            ):
                if value is None:
                    continue

                if has_second:
                    left = (
                        center
                        - group_width / 2
                        + series_index
                        * bar_width
                    )
                else:
                    left = (
                        center
                        - bar_width / 2
                    )

                right = (
                    left
                    + max(
                        2,
                        bar_width - 2,
                    )
                )
                value_y = y_for(
                    float(value)
                )

                self.canvas.create_rectangle(
                    left,
                    min(
                        zero_y,
                        value_y,
                    ),
                    right,
                    max(
                        zero_y,
                        value_y,
                    ),
                    fill=colors[
                        min(
                            series_index,
                            len(colors) - 1,
                        )
                    ],
                    outline="",
                )

            if index in label_indices:
                label = str(
                    row["x"]
                )
                if len(label) > 18:
                    label = (
                        label[:17]
                        + "…"
                    )
                self._draw_text(
                    center,
                    y1 + 12,
                    label,
                    anchor="ne",
                    fill=MUTED,
                    font=(
                        "Segoe UI",
                        8,
                    ),
                    angle=45,
                )

        self._draw_axis_titles(
            x0,
            y0,
            x1,
            y1,
        )
        self._draw_legend(
            width
        )

    def _line_x_positions(
        self,
        x0,
        x1,
    ):
        numeric = all(
            isinstance(
                row.get(
                    "x_numeric"
                ),
                (
                    int,
                    float,
                ),
            )
            for row in self.plot_rows
        )

        if numeric:
            values = [
                float(
                    row[
                        "x_numeric"
                    ]
                )
                for row in self.plot_rows
            ]
            minimum = min(
                values
            )
            maximum = max(
                values
            )

            if math.isclose(
                minimum,
                maximum,
            ):
                return [
                    (x0 + x1) / 2
                    for _ in values
                ]

            return [
                x0
                + (
                    value - minimum
                )
                / (
                    maximum - minimum
                )
                * (
                    x1 - x0
                )
                for value in values
            ]

        count = len(
            self.plot_rows
        )
        if count <= 1:
            return [
                (x0 + x1) / 2
            ]

        return [
            x0
            + index
            / (
                count - 1
            )
            * (
                x1 - x0
            )
            for index in range(
                count
            )
        ]

    def _draw_line(
        self,
        width,
        height,
    ):
        x0, y0, x1, y1 = (
            self._plot_area(
                width,
                height,
            )
        )

        values = []
        for row in self.plot_rows:
            values.append(
                float(row["y1"])
            )
            if row.get(
                "y2"
            ) is not None:
                values.append(
                    float(row["y2"])
                )

        y_for, _, _ = (
            self._draw_y_axis(
                x0,
                y0,
                x1,
                y1,
                min(values),
                max(values),
                force_zero=False,
            )
        )
        xs = self._line_x_positions(
            x0,
            x1,
        )
        colors = self._series_colors()
        has_second = any(
            row.get(
                "y2"
            ) is not None
            for row in self.plot_rows
        )

        series_keys = [
            "y1"
        ]
        if has_second:
            series_keys.append(
                "y2"
            )

        for series_index, key in enumerate(
            series_keys
        ):
            points = []

            for index, row in enumerate(
                self.plot_rows
            ):
                value = row.get(
                    key
                )
                if value is None:
                    continue
                points.extend(
                    [
                        xs[index],
                        y_for(
                            float(value)
                        ),
                    ]
                )

            if len(points) >= 4:
                self.canvas.create_line(
                    *points,
                    fill=colors[
                        series_index
                    ],
                    width=2,
                    smooth=False,
                )

            for index, row in enumerate(
                self.plot_rows
            ):
                value = row.get(
                    key
                )
                if value is None:
                    continue
                px = xs[index]
                py = y_for(
                    float(value)
                )
                radius = 3
                self.canvas.create_oval(
                    px - radius,
                    py - radius,
                    px + radius,
                    py + radius,
                    fill=colors[
                        series_index
                    ],
                    outline="",
                )

        label_indices = (
            self._category_label_indices(
                len(self.plot_rows)
            )
        )
        for index, row in enumerate(
            self.plot_rows
        ):
            if index not in label_indices:
                continue
            label = str(
                row["x"]
            )
            if len(label) > 18:
                label = (
                    label[:17]
                    + "…"
                )
            self._draw_text(
                xs[index],
                y1 + 12,
                label,
                anchor="ne",
                fill=MUTED,
                font=(
                    "Segoe UI",
                    8,
                ),
                angle=45,
            )

        self._draw_axis_titles(
            x0,
            y0,
            x1,
            y1,
        )
        self._draw_legend(
            width
        )

    def _draw_scatter(
        self,
        width,
        height,
    ):
        x0, y0, x1, y1 = (
            self._plot_area(
                width,
                height,
            )
        )

        x_values = [
            float(
                row["x_numeric"]
            )
            for row in self.plot_rows
        ]
        y_values = [
            float(
                row["y1"]
            )
            for row in self.plot_rows
        ]

        if any(
            row.get(
                "y2"
            ) is not None
            for row in self.plot_rows
        ):
            y_values.extend(
                float(
                    row["y2"]
                )
                for row in self.plot_rows
                if row.get(
                    "y2"
                ) is not None
            )

        y_for, _, _ = (
            self._draw_y_axis(
                x0,
                y0,
                x1,
                y1,
                min(y_values),
                max(y_values),
                force_zero=False,
            )
        )

        xmin = min(
            x_values
        )
        xmax = max(
            x_values
        )
        if math.isclose(
            xmin,
            xmax,
        ):
            xmin -= 1
            xmax += 1

        xpad = (
            xmax - xmin
        ) * 0.05
        xmin -= xpad
        xmax += xpad

        def x_for(value):
            return (
                x0
                + (
                    float(value) - xmin
                )
                / (
                    xmax - xmin
                )
                * (
                    x1 - x0
                )
            )

        for tick in range(6):
            fraction = tick / 5
            value = (
                xmin
                + fraction
                * (xmax - xmin)
            )
            x = (
                x0
                + fraction
                * (x1 - x0)
            )
            self.canvas.create_line(
                x,
                y0,
                x,
                y1,
                fill=BORDER,
            )
            self._draw_text(
                x,
                y1 + 18,
                self.compact_number(
                    value
                ),
                fill=MUTED,
                font=(
                    "Segoe UI",
                    8,
                ),
            )

        colors = self._series_colors()
        keys = [
            "y1"
        ]
        if any(
            row.get(
                "y2"
            ) is not None
            for row in self.plot_rows
        ):
            keys.append(
                "y2"
            )

        for series_index, key in enumerate(
            keys
        ):
            for row in self.plot_rows:
                value = row.get(
                    key
                )
                if value is None:
                    continue

                px = x_for(
                    row[
                        "x_numeric"
                    ]
                )
                py = y_for(
                    float(value)
                )
                radius = 4
                self.canvas.create_oval(
                    px - radius,
                    py - radius,
                    px + radius,
                    py + radius,
                    fill=colors[
                        series_index
                    ],
                    outline="",
                )

        self._draw_axis_titles(
            x0,
            y0,
            x1,
            y1,
        )
        self._draw_legend(
            width
        )

    def _draw_histogram(
        self,
        width,
        height,
    ):
        x0, y0, x1, y1 = (
            self._plot_area(
                width,
                height,
            )
        )

        values = [
            float(
                row[
                    "x_numeric"
                ]
            )
            for row in self.plot_rows
        ]

        minimum = min(
            values
        )
        maximum = max(
            values
        )

        if math.isclose(
            minimum,
            maximum,
        ):
            minimum -= 0.5
            maximum += 0.5

        bins = min(
            20,
            max(
                5,
                round(
                    math.sqrt(
                        len(values)
                    )
                ),
            ),
        )
        width_value = (
            maximum - minimum
        ) / bins
        counts = [
            0
            for _ in range(
                bins
            )
        ]

        for value in values:
            index = int(
                (value - minimum)
                / width_value
            )
            index = min(
                bins - 1,
                max(
                    0,
                    index,
                ),
            )
            counts[index] += 1

        y_for, _, _ = (
            self._draw_y_axis(
                x0,
                y0,
                x1,
                y1,
                0,
                max(counts),
                force_zero=True,
            )
        )

        slot = (
            (x1 - x0)
            / bins
        )
        zero_y = y_for(
            0
        )

        for index, count in enumerate(
            counts
        ):
            left = (
                x0
                + index * slot
                + 1
            )
            right = (
                x0
                + (index + 1)
                * slot
                - 1
            )
            top = y_for(
                count
            )

            self.canvas.create_rectangle(
                left,
                top,
                right,
                zero_y,
                fill=PRIMARY,
                outline="",
            )

        for tick in range(6):
            fraction = tick / 5
            value = (
                minimum
                + fraction
                * (maximum - minimum)
            )
            x = (
                x0
                + fraction
                * (x1 - x0)
            )
            self._draw_text(
                x,
                y1 + 18,
                self.compact_number(
                    value
                ),
                fill=MUTED,
                font=(
                    "Segoe UI",
                    8,
                ),
            )

        self._draw_text(
            (x0 + x1) / 2,
            y1 + 76,
            self.x_label,
            fill=MUTED,
            font=(
                "Bahnschrift",
                9,
                "bold",
            ),
        )
        self._draw_text(
            18,
            (y0 + y1) / 2,
            "Count",
            fill=MUTED,
            font=(
                "Bahnschrift",
                9,
                "bold",
            ),
            angle=90,
        )


class EconomyViewer:
    def __init__(
        self,
        root,
    ):
        self.root = root

        self.root.title(
            "Economy Analytics"
        )

        self.root.geometry(
            "1600x900"
        )

        self.root.minsize(
            1180,
            700,
        )

        self.root.configure(
            bg=APP_BG
        )

        self.analyzer = (
            EconomyAnalyzer(
                DB_PATH
            )
        )

        self.start_var = (
            tk.StringVar()
        )

        self.end_var = (
            tk.StringVar()
        )

        self.current_page = (
            "overview"
        )

        self.theme_name = THEME_NAME

        self.page_explanation_cards = {}

        self.page_frames = {}

        self.nav_buttons = {}

        self.sim_vars = {}
        self.sim_lock_vars = {}
        self.sim_target_enabled_vars = {}
        self.sim_target_value_vars = {}
        self.sim_target_current_labels = {}
        self.sim_target_result_labels = {}

        self.last_sim_settings = (
            None
        )

        self.sim_dirty = True

        self.setup_style()
        self.build_layout()

        self.root.after(
            100,
            self.load_startup_database,
        )

    def load_startup_database(self):
        """Load a database beside the app, or ask the user to choose one.

        This is deliberately friendly to packaged .exe builds. The preferred
        file is economy-stats.dht beside the executable. If that exact name is
        missing but there is exactly one .dht file in the same folder, use it.
        Otherwise open the normal database picker instead of failing with an
        opaque path error.
        """
        preferred = Path(
            self.analyzer.db_path
        )

        if preferred.exists():
            self.load_database()
            return

        search_directories = [
            BASE_DIR,
        ]

        current_directory = Path.cwd()

        if (
            current_directory.resolve()
            != BASE_DIR.resolve()
        ):
            search_directories.append(
                current_directory
            )

        candidates = []

        for directory in search_directories:
            if not directory.exists():
                continue

            for candidate in directory.glob(
                "*.dht"
            ):
                resolved = candidate.resolve()

                if resolved not in candidates:
                    candidates.append(
                        resolved
                    )

        if len(candidates) == 1:
            self.analyzer.db_path = (
                candidates[0]
            )
            self.load_database()
            return

        self.status_label.config(
            text=(
                "Database not found beside the app. "
                "Choose your .dht database."
            )
        )

        self.dataset_label.config(
            text=(
                "No database selected"
            )
        )

        self.root.after(
            100,
            self.choose_database,
        )

    def toggle_theme(self):
        new_theme = (
            "light"
            if self.theme_name == "dark"
            else "dark"
        )

        self.switch_theme(
            new_theme
        )

    def switch_theme(
        self,
        new_theme,
    ):
        if new_theme == self.theme_name:
            return

        current_page = self.current_page

        start_text = self.start_var.get()
        end_text = self.end_var.get()

        pending_state = (
            getattr(
                self,
                "apply_state",
                None,
            ) is not None
            and self.apply_state.text
            == "Changes pending"
        )

        try:
            quick_value = self.quick_dropdown.get()
        except Exception:
            quick_value = "All time"

        try:
            chicken_value = self.chicken_dropdown.get()
        except Exception:
            chicken_value = "Chicken -> cockfight"

        try:
            excluded = self.exclude_dropdown.get_selected()
        except Exception:
            excluded = set()

        try:
            selected_user = self.user_dropdown.get()
        except Exception:
            selected_user = None

        try:
            selected_sim_user = self.sim_user_dropdown.get()
        except Exception:
            selected_sim_user = None

        sim_values = {
            key: var.get()
            for key, var
            in getattr(
                self,
                "sim_vars",
                {},
            ).items()
        }

        try:
            slot_symbols = self.slot_command_symbols_var.get()
        except Exception:
            slot_symbols = ""

        sim_lock_values = {
            key: var.get()
            for key, var in getattr(
                self,
                "sim_lock_vars",
                {},
            ).items()
        }

        sim_target_enabled_values = {
            key: var.get()
            for key, var in getattr(
                self,
                "sim_target_enabled_vars",
                {},
            ).items()
        }

        sim_target_values = {
            key: var.get()
            for key, var in getattr(
                self,
                "sim_target_value_vars",
                {},
            ).items()
        }

        try:
            optimizer_basis = self.sim_optimizer_basis_dropdown.get()
        except Exception:
            optimizer_basis = "Combined activity"

        try:
            activity_group_basis = self.activity_group_basis_dropdown.get()
        except Exception:
            activity_group_basis = "Combined activity"

        try:
            plot_state = {
                "source": self.plot_source_dropdown.get(),
                "group": self.plot_group_dropdown.get(),
                "x": self.plot_x_dropdown.get(),
                "y": self.plot_y_dropdown.get(),
                "y2": self.plot_y2_dropdown.get(),
                "chart": self.plot_type_dropdown.get(),
                "aggregation": self.plot_aggregation_dropdown.get(),
                "sort": self.plot_sort_dropdown.get(),
                "max_points": self.plot_max_points_var.get(),
                "preset": self.plot_preset_dropdown.get(),
                "rendered": getattr(
                    self,
                    "plot_has_rendered",
                    False,
                ),
            }
        except Exception:
            plot_state = None

        had_simulation = (
            self.last_sim_settings is not None
            and not self.sim_dirty
        )

        self.theme_name = new_theme
        apply_theme_globals(
            new_theme
        )

        for child in self.root.winfo_children():
            child.destroy()

        self.page_frames = {}
        self.nav_buttons = {}
        self.page_explanation_cards = {}
        self.sim_vars = {}
        self.sim_lock_vars = {}
        self.sim_target_enabled_vars = {}
        self.sim_target_value_vars = {}
        self.sim_target_current_labels = {}
        self.sim_target_result_labels = {}
        self.last_sim_settings = None
        self.sim_dirty = True

        self.root.configure(
            bg=APP_BG
        )

        self.setup_style()
        self.build_layout()

        self.start_var.set(
            start_text
        )
        self.end_var.set(
            end_text
        )

        if self.analyzer.all_transactions:
            first = self.analyzer.all_transactions[0][
                "timestamp"
            ]

            last = self.analyzer.all_transactions[-1][
                "timestamp"
            ]

            self.dataset_label.config(
                text=(
                    "Dataset "
                    f"{to_local_string(first)}"
                    " to "
                    f"{to_local_string(last)}"
                )
            )

            self.sidebar_info.config(
                text=(
                    f"{len(self.analyzer.all_transactions):,} parsed\n"
                    f"{to_local_string(first)[:10]}"
                    " to "
                    f"{to_local_string(last)[:10]}"
                )
            )

            self.chicken_dropdown.set(
                chicken_value
            )

            reasons = self.analyzer.get_available_reasons(
                self.pending_chicken_as_cockfight()
            )

            self.exclude_dropdown.set_options(
                reasons,
                preserve=False,
            )

            for reason in excluded:
                if reason in self.exclude_dropdown.variables:
                    self.exclude_dropdown.variables[
                        reason
                    ].set(True)

            self.exclude_dropdown._update_label()

            self.quick_dropdown.set(
                quick_value
            )

            self.populate_all()
            self.update_kpis()
            self.update_user_projection_info()
            self.update_sim_window_info()

            if (
                selected_user
                and selected_user
                in self.user_dropdown.options
            ):
                self.user_dropdown.set(
                    selected_user
                )
                self.view_selected_user(
                    show_message=False
                )

            for key, value in sim_values.items():
                if key in self.sim_vars:
                    self.sim_vars[key].set(
                        value
                    )

            self.slot_command_symbols_var.set(
                slot_symbols
            )

            for key, value in sim_lock_values.items():
                if key in self.sim_lock_vars:
                    self.sim_lock_vars[key].set(value)

            for key, value in sim_target_enabled_values.items():
                if key in self.sim_target_enabled_vars:
                    self.sim_target_enabled_vars[key].set(value)

            for key, value in sim_target_values.items():
                if key in self.sim_target_value_vars:
                    self.sim_target_value_vars[key].set(value)

            try:
                self.sim_optimizer_basis_dropdown.set(
                    optimizer_basis
                )
                self.activity_group_basis_dropdown.set(
                    activity_group_basis
                )
                self.refresh_activity_groups()
                self.refresh_activity_target_rows()
            except Exception:
                pass

            if plot_state is not None:
                try:
                    self.plot_source_dropdown.set(
                        plot_state[
                            "source"
                        ]
                    )
                    self.plot_group_dropdown.set(
                        plot_state[
                            "group"
                        ]
                    )
                    self.refresh_plot_fields()

                    for dropdown, key in [
                        (
                            self.plot_x_dropdown,
                            "x",
                        ),
                        (
                            self.plot_y_dropdown,
                            "y",
                        ),
                        (
                            self.plot_y2_dropdown,
                            "y2",
                        ),
                        (
                            self.plot_type_dropdown,
                            "chart",
                        ),
                        (
                            self.plot_aggregation_dropdown,
                            "aggregation",
                        ),
                        (
                            self.plot_sort_dropdown,
                            "sort",
                        ),
                        (
                            self.plot_preset_dropdown,
                            "preset",
                        ),
                    ]:
                        dropdown.set(
                            plot_state[
                                key
                            ]
                        )

                    self.plot_max_points_var.set(
                        plot_state[
                            "max_points"
                        ]
                    )

                    if plot_state[
                        "rendered"
                    ]:
                        self.render_plot()
                except Exception:
                    pass

            if had_simulation:
                self.run_simulator()

                if (
                    selected_sim_user
                    and selected_sim_user
                    in self.sim_user_dropdown.options
                ):
                    self.sim_user_dropdown.set(
                        selected_sim_user
                    )
                    self.view_simulator_user()

            if pending_state:
                self.apply_state.set_pending()
            else:
                self.apply_state.set_applied()

            self.status_label.config(
                text=(
                    f"{len(self.analyzer.transactions):,} transactions | "
                    f"{self.theme_name.title()} mode"
                )
            )

        self.show_page(
            current_page
            if current_page in self.page_frames
            else "overview"
        )

    def setup_style(self):
        style = ttk.Style()

        try:
            style.theme_use(
                "clam"
            )

        except tk.TclError:
            pass

        style.configure(
            "Treeview",
            background=CARD,
            fieldbackground=CARD,
            foreground=TEXT,
            rowheight=34,
            borderwidth=0,
            relief=tk.FLAT,
            font=(
                "Segoe UI",
                10,
            ),
        )

        style.configure(
            "Treeview.Heading",
            background=TABLE_HEADER_BG,
            foreground=TEXT,
            borderwidth=0,
            relief=tk.FLAT,
            padding=(8, 8),
            font=("Bahnschrift", 9, "bold"),
        )

        style.map(
            "Treeview",
            background=[
                (
                    "selected",
                    PRIMARY,
                )
            ],
            foreground=[
                (
                    "selected",
                    "#FFFFFF",
                )
            ],
        )

        style.configure(
            "TScrollbar",
            background=SECONDARY_BG,
            troughcolor=APP_BG,
            bordercolor=APP_BG,
            arrowcolor=TEXT,
            darkcolor=SECONDARY_BG,
            lightcolor=SECONDARY_BG,
        )

    def build_layout(self):
        sidebar = tk.Frame(
            self.root,
            bg=SIDEBAR_BG,
            width=220,
        )

        sidebar.pack(
            side=tk.LEFT,
            fill=tk.Y,
        )

        sidebar.pack_propagate(
            False
        )

        right = tk.Frame(
            self.root,
            bg=APP_BG,
        )

        right.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True,
        )

        self.build_sidebar(
            sidebar
        )

        self.build_topbar(
            right
        )

        self.scroll_area = (
            ScrollableArea(
                right
            )
        )

        self.scroll_area.pack(
            fill=tk.BOTH,
            expand=True,
        )

        self.build_filter_panel(
            self.scroll_area.content
        )

        self.build_kpi_row(
            self.scroll_area.content
        )

        self.page_host = tk.Frame(
            self.scroll_area.content,
            bg=APP_BG,
        )

        self.page_host.pack(
            fill=tk.X,
            padx=22,
            pady=(0, 24),
        )

        self.build_pages()

        self.show_page(
            "overview"
        )

        status = tk.Frame(
            right,
            bg=DEEP_BG,
            height=28,
        )

        status.pack(
            fill=tk.X
        )

        status.pack_propagate(
            False
        )

        self.status_label = (
            tk.Label(
                status,
                text="Loading database...",
                bg=DEEP_BG,
                fg=MUTED,
                font=(
                    "Segoe UI",
                    8,
                ),
            )
        )

        self.status_label.pack(
            side=tk.LEFT,
            padx=14,
        )

    def build_sidebar(
        self,
        parent,
    ):
        tk.Label(
            parent,
            text="ECONOMY",
            bg=SIDEBAR_BG,
            fg=SIDEBAR_TEXT,
            font=("Bahnschrift", 17, "bold"),
        ).pack(
            anchor="w",
            padx=20,
            pady=(24, 0),
        )

        tk.Label(
            parent,
            text="ANALYTICS",
            bg=SIDEBAR_BG,
            fg=ACCENT_TEXT,
            font=("Bahnschrift", 10, "bold"),
        ).pack(
            anchor="w",
            padx=20,
            pady=(0, 24),
        )

        nav_items = [
            (
                "overview",
                "Overview",
            ),

            (
                "users",
                "Users",
            ),

            (
                "user_breakdown",
                "User Breakdown",
            ),

            (
                "activity_groups",
                "Activity Groups",
            ),

            (
                "sources",
                "Income Sources",
            ),

            (
                "hourly",
                "Hourly",
            ),

            (
                "daily",
                "Daily",
            ),

            (
                "user_hours",
                "User Hours",
            ),

            (
                "transactions",
                "Transactions",
            ),

            (
                "plots",
                "Plots",
            ),

            (
                "simulator",
                "Game Simulator",
            ),
        ]

        for (
            key,
            label,
        ) in nav_items:

            button = NavButton(
                parent,
                label,
                command=(
                    lambda page_key=key:
                    self.show_page(
                        page_key
                    )
                ),
            )

            button.pack(
                padx=18,
                pady=3,
            )

            self.nav_buttons[
                key
            ] = button

        spacer = tk.Frame(
            parent,
            bg=SIDEBAR_BG,
        )

        spacer.pack(
            fill=tk.BOTH,
            expand=True,
        )

        self.sidebar_info = (
            tk.Label(
                parent,
                text=(
                    "Database\n"
                    "not loaded"
                ),
                justify=tk.LEFT,
                bg=SIDEBAR_BG,
                fg=MUTED,
                font=(
                    "Segoe UI",
                    8,
                ),
            )
        )

        self.sidebar_info.pack(
            anchor="w",
            padx=20,
            pady=(0, 18),
        )

    def build_topbar(
        self,
        parent,
    ):
        bar = tk.Frame(
            parent,
            bg=APP_BG,
            height=86,
        )

        bar.pack(
            fill=tk.X
        )

        bar.pack_propagate(
            False
        )

        left = tk.Frame(
            bar,
            bg=APP_BG,
        )

        left.pack(
            side=tk.LEFT,
            padx=24,
            pady=15,
        )

        tk.Label(
            left,
            text="Economy Analytics",
            bg=APP_BG,
            fg=TEXT,
            font=("Bahnschrift", 21, "bold"),
        ).pack(
            anchor="w"
        )

        self.dataset_label = (
            tk.Label(
                left,
                text="Loading dataset",
                bg=APP_BG,
                fg=MUTED,
                font=(
                    "Segoe UI",
                    8,
                ),
            )
        )

        self.dataset_label.pack(
            anchor="w",
            pady=(2, 0),
        )

        right = tk.Frame(
            bar,
            bg=APP_BG,
        )

        right.pack(
            side=tk.RIGHT,
            padx=24,
            pady=20,
        )

        self.apply_state = (
            StatusPill(
                right
            )
        )

        self.apply_state.pack(
            side=tk.LEFT,
            padx=(0, 12),
        )

        self.theme_button = RoundedButton(
            right,
            (
                "Light mode"
                if self.theme_name == "dark"
                else "Dark mode"
            ),
            self.toggle_theme,
            width=104,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        )

        self.theme_button.pack(
            side=tk.LEFT,
            padx=(0, 8),
        )

        RoundedButton(
            right,
            "Choose Database",
            self.choose_database,
            width=128,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )

        RoundedButton(
            right,
            "Reload",
            self.load_database,
            width=92,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )

        RoundedButton(
            right,
            "Export",
            self.export_current_page,
            width=92,
        ).pack(
            side=tk.LEFT
        )

    def build_filter_panel(
        self,
        parent,
    ):
        panel = RoundedPanel(
            parent,
            height=182,
            padding=18,
        )

        panel.pack(
            fill=tk.X,
            padx=22,
            pady=(4, 14),
        )

        inner = panel.inner

        top = tk.Frame(
            inner,
            bg=CARD,
        )

        top.pack(
            fill=tk.X
        )

        tk.Label(
            top,
            text="Analysis filters",
            bg=CARD,
            fg=TEXT,
            font=("Bahnschrift", 12, "bold"),
        ).pack(
            side=tk.LEFT
        )

        tk.Label(
            top,
            text=(
                "Changes only take effect "
                "after Apply"
            ),
            bg=CARD,
            fg=MUTED,
            font=(
                "Segoe UI",
                8,
            ),
        ).pack(
            side=tk.RIGHT
        )

        row1 = tk.Frame(
            inner,
            bg=CARD,
        )

        row1.pack(
            fill=tk.X,
            pady=(14, 8),
        )

        self.exclude_dropdown = (
            MultiSelectMenuButton(
                row1,
                title="Exclude",
                width=250,
                on_change=(
                    self.mark_dirty
                ),
            )
        )

        self.exclude_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        self.chicken_dropdown = (
            SingleSelectMenuButton(
                row1,
                options=[
                    "Chicken -> cockfight",
                    "Chicken -> buy",
                ],
                value=(
                    "Chicken -> cockfight"
                ),
                width=190,
                on_change=(
                    self.on_pending_chicken_change
                ),
            )
        )

        self.chicken_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        self.quick_dropdown = (
            SingleSelectMenuButton(
                row1,
                options=[
                    "All time",
                    "Last 1h",
                    "Last 6h",
                    "Last 12h",
                    "Last 24h",
                    "Last 48h",
                    "Last 7d",
                    "Last 14d",
                    "Last 30d",
                    "Custom",
                ],
                value="All time",
                width=150,
                on_change=(
                    self.on_pending_quick_range
                ),
            )
        )

        self.quick_dropdown.pack(
            side=tk.LEFT
        )

        row2 = tk.Frame(
            inner,
            bg=CARD,
        )

        row2.pack(
            fill=tk.X
        )

        tk.Label(
            row2,
            text="Start",
            bg=CARD,
            fg=MUTED,
            font=("Bahnschrift", 8, "bold"),
        ).pack(
            side=tk.LEFT,
            padx=(0, 6),
        )

        self.start_entry = (
            RoundedEntry(
                row2,
                textvariable=(
                    self.start_var
                ),
                width=190,
            )
        )

        self.start_entry.pack(
            side=tk.LEFT,
            padx=(0, 12),
        )

        self.start_entry.bind_key(
            "<KeyRelease>",
            lambda event:
            self.mark_dirty(),
        )

        self.start_entry.bind_key(
            "<Return>",
            lambda event:
            self.apply_filters(),
        )

        tk.Label(
            row2,
            text="End",
            bg=CARD,
            fg=MUTED,
            font=("Bahnschrift", 8, "bold"),
        ).pack(
            side=tk.LEFT,
            padx=(0, 6),
        )

        self.end_entry = (
            RoundedEntry(
                row2,
                textvariable=(
                    self.end_var
                ),
                width=190,
            )
        )

        self.end_entry.pack(
            side=tk.LEFT,
            padx=(0, 12),
        )

        self.end_entry.bind_key(
            "<KeyRelease>",
            lambda event:
            self.mark_dirty(),
        )

        self.end_entry.bind_key(
            "<Return>",
            lambda event:
            self.apply_filters(),
        )

        RoundedButton(
            row2,
            "Apply",
            self.apply_filters,
            width=92,
        ).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )

        RoundedButton(
            row2,
            "Reset form",
            self.reset_filter_form,
            width=104,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.LEFT
        )

    def build_kpi_row(
        self,
        parent,
    ):
        row = tk.Frame(
            parent,
            bg=APP_BG,
        )

        row.pack(
            fill=tk.X,
            padx=22,
            pady=(0, 14),
        )

        self.kpi_cards = {}

        cards = [
            (
                "net",
                "Overall change",
                "How much richer or poorer users became",
            ),

            (
                "generated",
                "Added to users",
                "All money that entered user balances",
            ),

            (
                "removed",
                "Taken from users",
                "All money spent, lost or removed",
            ),

            (
                "users",
                "Active users",
                "Unique users in range",
            ),

            (
                "rate",
                "Change per hour",
                "Average change in user balances each hour",
            ),
        ]

        for (
            index,
            (
                key,
                title,
                subtitle,
            ),
        ) in enumerate(
            cards
        ):
            row.columnconfigure(
                index,
                weight=1,
            )

            card = KpiCard(
                row,
                title,
                subtitle,
            )

            card.grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(
                    0
                    if index == 0
                    else 5,
                    0
                    if index
                    == len(cards) - 1
                    else 5,
                ),
            )

            self.kpi_cards[
                key
            ] = card

    def make_page_header(
        self,
        parent,
        title,
        subtitle,
    ):
        header = tk.Frame(
            parent,
            bg=APP_BG,
        )

        header.pack(
            fill=tk.X,
            pady=(4, 10),
        )

        tk.Label(
            header,
            text=title,
            bg=APP_BG,
            fg=TEXT,
            font=("Bahnschrift", 16, "bold"),
        ).pack(
            anchor="w"
        )

        tk.Label(
            header,
            text=subtitle,
            bg=APP_BG,
            fg=MUTED,
            font=(
                "Segoe UI",
                10,
            ),
        ).pack(
            anchor="w",
            pady=(2, 0),
        )

    def make_help_card(
        self,
        parent,
        text,
        height=92,
    ):
        card = ExplanationCard(
            parent,
            text=text,
            min_height=height,
        )

        card.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        return card

    def build_pages(self):
        self.page_frames[
            "overview"
        ] = self.build_table_page(
            "Overview",
            "A quick explanation of what happened to player money.",
            "summary_table",
            (
                "This box will tell you how much money users were given, how much they spent or lost, whether users "
                "ended up richer or poorer overall, and what the same pace would look like over a month."
            ),
        )

        self.page_frames[
            "users"
        ] = self.build_users_page()

        self.page_frames[
            "user_breakdown"
        ] = self.build_user_breakdown_page()

        self.page_frames[
            "activity_groups"
        ] = self.build_activity_groups_page()

        self.page_frames[
            "sources"
        ] = self.build_table_page(
            "Income Sources",
            "See which commands and games make users richer or poorer.",
            "sources_table",
            (
                "This box will point out which game or command gave users the most money, which took the most, "
                "how often they were used, and what that means for the economy. Game-related spending is kept with "
                "the game it belongs to: chicken purchases count with Cock Fight, and animal/provision purchases count "
                "with Animal Race instead of being hidden inside a generic Buy total."
            ),
        )

        self.page_frames[
            "hourly"
        ] = self.build_table_page(
            "Hourly Performance",
            "See what users gained or lost during each hour.",
            "hourly_table",
            (
                "This box will tell you which hour was best for users, which was worst, which was busiest, "
                "and how many people were actually using the economy then."
            ),
        )

        self.page_frames[
            "daily"
        ] = self.build_table_page(
            "Daily Performance",
            "See what users gained or lost on each day.",
            "daily_table",
            (
                "This box will tell you which day users gained the most, which day they lost the most, "
                "and which day had the most economy activity."
            ),
        )

        self.page_frames[
            "user_hours"
        ] = self.build_table_page(
            "User Hours",
            "One row for each user and hour in which they used the economy.",
            "user_hours_table",
            (
                "This box will point out the strongest and weakest one-hour stretches for individual users, "
                "so you can spot unusually lucky, unlucky or intense periods of play."
            ),
        )

        self.page_frames[
            "transactions"
        ] = self.build_table_page(
            "Transactions",
            "Every individual time a user gained, spent or lost money.",
            "transactions_table",
            (
                "This box will tell you how many individual money changes happened, the biggest amount someone "
                "received at once, and the biggest amount someone lost or spent at once."
            ),
        )

        self.page_frames[
            "plots"
        ] = self.build_plots_page()

        self.page_frames[
            "simulator"
        ] = self.build_simulator_page()

    def new_page(self):
        return tk.Frame(
            self.page_host,
            bg=APP_BG,
        )

    def build_table_page(
        self,
        title,
        subtitle,
        attribute_name,
        help_text,
    ):
        page = self.new_page()

        self.make_page_header(
            page,
            title,
            subtitle,
        )

        help_card = self.make_help_card(
            page,
            help_text,
        )

        self.page_explanation_cards[
            attribute_name
        ] = help_card

        panel = RoundedPanel(
            page,
            height=610,
            padding=18,
        )

        panel.pack(
            fill=tk.X
        )

        table = DataTable(
            panel.inner,
            height=16,
        )

        table.pack(
            fill=tk.BOTH,
            expand=True,
        )

        setattr(
            self,
            attribute_name,
            table,
        )

        return page

    def build_users_page(self):
        page = self.new_page()

        self.make_page_header(
            page,
            "Users",
            (
                "Quick comparison of profit, projected profit and estimated economy activity. "
                "Usernames are read from the DHT database when available; unresolved users fall back to their Discord ID."
            ),
        )

        self.user_projection_card = self.make_help_card(
            page,
            "Loading user summary...",
            height=110,
        )

        self.page_explanation_cards[
            "users"
        ] = self.user_projection_card

        panel = RoundedPanel(
            page,
            height=640,
            padding=18,
        )

        panel.pack(
            fill=tk.X
        )

        self.users_table = DataTable(
            panel.inner,
            height=17,
            double_click_callback=(
                self.open_user_from_row
            ),
        )

        self.users_table.pack(
            fill=tk.BOTH,
            expand=True,
        )

        return page

    def build_user_breakdown_page(
        self,
    ):
        page = self.new_page()

        self.make_page_header(
            page,
            "User Breakdown",
            (
                "Inspect one user's activity, money sources "
                "and individual transactions."
            ),
        )

        self.user_breakdown_help_card = self.make_help_card(
            page,
            "Select a user to see an explanation of their actual numbers.",
            height=110,
        )

        self.page_explanation_cards[
            "user_breakdown"
        ] = self.user_breakdown_help_card

        selector_panel = RoundedPanel(
            page,
            height=92,
            padding=16,
        )

        selector_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        selector = selector_panel.inner

        tk.Label(
            selector,
            text="User",
            bg=CARD,
            fg=MUTED,
            font=("Bahnschrift", 8, "bold"),
        ).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )

        self.user_dropdown = SingleSelectMenuButton(
            selector,
            options=[
                "No users"
            ],
            value="No users",
            width=220,
        )

        self.user_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        RoundedButton(
            selector,
            "View user",
            self.view_selected_user,
            width=96,
        ).pack(
            side=tk.LEFT
        )

        self.user_breakdown_caption = tk.Label(
            selector,
            text="",
            bg=CARD,
            fg=MUTED,
            font=(
                "Segoe UI",
                9,
            ),
        )

        self.user_breakdown_caption.pack(
            side=tk.LEFT,
            padx=16,
        )

        summary_panel = RoundedPanel(
            page,
            height=430,
            padding=18,
        )

        summary_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        self.user_summary_table = DataTable(
            summary_panel.inner,
            height=11,
        )

        self.user_summary_table.pack(
            fill=tk.BOTH,
            expand=True,
        )

        sources_panel = RoundedPanel(
            page,
            height=510,
            padding=18,
        )

        sources_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        tk.Label(
            sources_panel.inner,
            text="Money sources",
            bg=CARD,
            fg=TEXT,
            font=("Bahnschrift", 11, "bold"),
        ).pack(
            anchor="w",
            pady=(0, 8),
        )

        self.user_sources_table = DataTable(
            sources_panel.inner,
            height=11,
        )

        self.user_sources_table.pack(
            fill=tk.BOTH,
            expand=True,
        )

        tx_panel = RoundedPanel(
            page,
            height=510,
            padding=18,
        )

        tx_panel.pack(
            fill=tk.X
        )

        tk.Label(
            tx_panel.inner,
            text="User transactions",
            bg=CARD,
            fg=TEXT,
            font=("Bahnschrift", 11, "bold"),
        ).pack(
            anchor="w",
            pady=(0, 8),
        )

        self.user_transactions_table = DataTable(
            tx_panel.inner,
            height=11,
        )

        self.user_transactions_table.pack(
            fill=tk.BOTH,
            expand=True,
        )

        return page

    def make_sim_entry(
        self,
        parent,
        value,
        width=76,
    ):
        var = tk.StringVar(
            value=str(
                value
            )
        )

        entry = RoundedEntry(
            parent,
            textvariable=var,
            width=width,
            height=34,
        )

        entry.bind_key(
            "<KeyRelease>",
            lambda event:
            self.mark_sim_dirty(),
        )

        return (
            var,
            entry,
        )

    def build_activity_groups_page(self):
        page = self.new_page()

        self.make_page_header(
            page,
            "Activity Groups",
            "Group users by natural activity levels, then inspect the users and historical game averages inside each group.",
        )

        self.activity_group_help_card = self.make_help_card(
            page,
            (
                "Users are grouped by natural activity levels instead of forcing the same number of people into every group. "
                "Combined activity uses both estimated active hours per day and balance changes per day. You can also group only by active hours or only by transactions. "
                "The detailed section below lets you inspect historical game averages and the individual members inside any group."
            ),
            height=130,
        )

        controls = RoundedPanel(
            page,
            height=100,
            padding=16,
            fill=INFO_BG,
            outline=BORDER,
        )
        controls.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        row = controls.inner

        tk.Label(
            row,
            text="Group users by",
            bg=INFO_BG,
            fg=MUTED,
            font=(
                "Bahnschrift",
                9,
                "bold",
            ),
        ).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )

        self.activity_group_basis_dropdown = SingleSelectMenuButton(
            row,
            options=ACTIVITY_GROUP_BASIS_OPTIONS,
            value="Combined activity",
            width=210,
        )
        self.activity_group_basis_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 12),
        )

        RoundedButton(
            row,
            "Refresh Groups",
            self.refresh_activity_groups,
            width=120,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.LEFT,
        )

        panel = RoundedPanel(
            page,
            height=320,
            padding=18,
        )
        panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        self.activity_group_table = DataTable(
            panel.inner,
            height=8,
            double_click_callback=(
                self.open_activity_group_from_row
            ),
        )
        self.activity_group_table.pack(
            fill=tk.X,
            expand=False,
        )

        detail_controls = RoundedPanel(
            page,
            height=100,
            padding=16,
            fill=INFO_BG,
            outline=BORDER,
        )
        detail_controls.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        detail_row = detail_controls.inner

        tk.Label(
            detail_row,
            text="Detailed group",
            bg=INFO_BG,
            fg=MUTED,
            font=(
                "Bahnschrift",
                9,
                "bold",
            ),
        ).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )

        self.activity_group_detail_dropdown = SingleSelectMenuButton(
            detail_row,
            options=ACTIVITY_GROUP_NAMES,
            value=ACTIVITY_GROUP_NAMES[0],
            width=190,
            on_change=self.view_activity_group_details,
        )
        self.activity_group_detail_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 12),
        )

        RoundedButton(
            detail_row,
            "View Group",
            self.view_activity_group_details,
            width=104,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.LEFT,
        )

        tk.Label(
            detail_row,
            text="You can also double-click a group in the table above.",
            bg=INFO_BG,
            fg=MUTED,
            font=(
                "Segoe UI",
                9,
            ),
        ).pack(
            side=tk.LEFT,
            padx=(14, 0),
        )

        self.activity_group_detail_card = ExplanationCard(
            page,
            title="Selected activity group",
            text=(
                "Select an activity group to see its historical game averages and members."
            ),
            min_height=130,
        )
        self.activity_group_detail_card.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        game_panel = RoundedPanel(
            page,
            height=360,
            padding=18,
        )
        game_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        tk.Label(
            game_panel.inner,
            text="Historical game averages",
            bg=CARD,
            fg=TEXT,
            font=(
                "Bahnschrift",
                12,
                "bold",
            ),
        ).pack(
            anchor="w",
            pady=(0, 10),
        )

        tk.Label(
            game_panel.inner,
            text=(
                "These rows describe what this activity group actually did in the selected history. "
                "They do not control the fixed-frequency Game Simulator."
            ),
            bg=CARD,
            fg=MUTED,
            font=(
                "Segoe UI",
                9,
            ),
            justify=tk.LEFT,
            anchor="w",
        ).pack(
            fill=tk.X,
            anchor="w",
            pady=(0, 10),
        )

        self.activity_group_game_table = DataTable(
            game_panel.inner,
            height=len(
                GAME_ORDER
            ),
        )
        self.activity_group_game_table.pack(
            fill=tk.X,
            expand=False,
        )

        member_panel = RoundedPanel(
            page,
            height=560,
            padding=18,
        )
        member_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        tk.Label(
            member_panel.inner,
            text="Group members",
            bg=CARD,
            fg=TEXT,
            font=(
                "Bahnschrift",
                12,
                "bold",
            ),
        ).pack(
            anchor="w",
            pady=(0, 6),
        )

        tk.Label(
            member_panel.inner,
            text=(
                "Double-click a user to open their full User Breakdown."
            ),
            bg=CARD,
            fg=MUTED,
            font=(
                "Segoe UI",
                9,
            ),
            justify=tk.LEFT,
            anchor="w",
        ).pack(
            fill=tk.X,
            anchor="w",
            pady=(0, 10),
        )

        self.activity_group_member_table = DataTable(
            member_panel.inner,
            height=20,
            double_click_callback=(
                self.open_user_from_row
            ),
        )
        self.activity_group_member_table.pack(
            fill=tk.X,
            expand=False,
        )

        return page

    def refresh_activity_groups(self):
        if not self.analyzer.transactions:
            return

        try:
            basis = (
                self.activity_group_basis_dropdown
                .get()
            )
        except Exception:
            basis = "Combined activity"

        rows, members = (
            self.analyzer.get_activity_groups(
                basis
            )
        )

        self.activity_group_table.set_data(
            rows
        )

        if not rows:
            self.activity_group_help_card.set_text(
                "There are no users in the current selection."
            )
            self.activity_group_detail_dropdown.set_options(
                ACTIVITY_GROUP_NAMES,
                selected=ACTIVITY_GROUP_NAMES[0],
            )
            self.activity_group_game_table.set_data(
                []
            )
            self.activity_group_member_table.set_data(
                []
            )
            return

        nonempty = [
            row
            for row in rows
            if row["Members"] > 0
        ]

        if not nonempty:
            return

        quietest = nonempty[0]
        busiest = nonempty[-1]

        def money_words(value, period):
            if value > 0:
                return (
                    f"gain about {value:,.0f} "
                    f"over {period}"
                )
            if value < 0:
                return (
                    f"lose about {abs(value):,.0f} "
                    f"over {period}"
                )
            return (
                f"finish about even over {period}"
            )

        self.activity_group_help_card.set_text(
            (
                f"The current grouping uses {basis.lower()}. Users are clustered by natural gaps in activity instead of being forced into equal-sized groups. "
                "Some groups can therefore contain many more people than others, and a group can be empty if the data does not contain a distinct activity level for it.\n\n"
                f"A typical {quietest['Group']} member is active for about {quietest['Avg Active Hrs / Day']:,.2f} hours per day and has about {quietest['Avg Transactions / Day']:,.1f} balance changes per day. "
                f"At the same historical pace they would {money_words(quietest['Avg 24h Net'], '24 hours')} and {money_words(quietest['Avg 30d Net'], '30 days')}.\n\n"
                f"A typical {busiest['Group']} member is active for about {busiest['Avg Active Hrs / Day']:,.2f} hours per day and has about {busiest['Avg Transactions / Day']:,.1f} balance changes per day. "
                f"At the same historical pace they would {money_words(busiest['Avg 24h Net'], '24 hours')} and {money_words(busiest['Avg 30d Net'], '30 days')}.\n\n"
                "Double-click any group, or use the Detailed group selector below, to inspect its game-by-game averages and individual members."
            )
        )

        available_groups = [
            row["Group"]
            for row in nonempty
        ]

        previous = (
            self.activity_group_detail_dropdown
            .get()
        )

        selected = (
            previous
            if previous
            in available_groups
            else available_groups[0]
        )

        self.activity_group_detail_dropdown.set_options(
            available_groups,
            selected=selected,
        )

        self.view_activity_group_details()

        try:
            self.refresh_activity_target_rows()
        except Exception:
            pass

    def open_activity_group_from_row(
        self,
        row,
    ):
        group_name = str(
            row.get(
                "Group",
                "",
            )
        ).strip()

        if not group_name:
            return

        self.activity_group_detail_dropdown.set(
            group_name
        )
        self.view_activity_group_details()

    def view_activity_group_details(
        self,
    ):
        if not self.analyzer.transactions:
            return

        try:
            basis = (
                self.activity_group_basis_dropdown
                .get()
            )
        except Exception:
            basis = "Combined activity"

        try:
            group_name = (
                self.activity_group_detail_dropdown
                .get()
            )
        except Exception:
            group_name = ACTIVITY_GROUP_NAMES[0]

        details = (
            self.analyzer
            .get_activity_group_details(
                group_name,
                basis,
            )
        )

        game_rows = details[
            "game_rows"
        ]
        member_rows = details[
            "member_rows"
        ]

        self.activity_group_game_table.set_data(
            game_rows
        )
        self.activity_group_member_table.set_data(
            member_rows
        )

        if not details[
            "members"
        ]:
            self.activity_group_detail_card.set_text(
                (
                    f"{group_name} has no users in the current selection."
                )
            )
            return

        summary = details[
            "summary"
        ]

        active_hours = float(
            summary[
                "Avg Active Hrs / Day"
            ]
        )
        transactions = float(
            summary[
                "Avg Transactions / Day"
            ]
        )
        active_days = float(
            summary[
                "Avg Active Days / 30d"
            ]
        )
        net24 = float(
            summary[
                "Avg 24h Net"
            ]
        )
        net30 = float(
            summary[
                "Avg 30d Net"
            ]
        )

        played_rows = [
            row
            for row in game_rows
            if row[
                "Users Played"
            ] > 0
        ]

        if played_rows:
            most_played = max(
                played_rows,
                key=lambda row:
                    row[
                        "Avg Plays / Player / Day"
                    ],
            )
            best_game = max(
                played_rows,
                key=lambda row:
                    row[
                        "Avg 24h Net / Member"
                    ],
            )
            worst_game = min(
                played_rows,
                key=lambda row:
                    row[
                        "Avg 24h Net / Member"
                    ],
            )

            game_text = (
                f"Among members who actually played each game, {most_played['Game']} had the highest play rate at about {most_played['Avg Plays / Player / Day']:,.2f} plays per player per day. "
                f"The most profitable game for the average group member is {best_game['Game']} at about {best_game['Avg 24h Net / Member']:+,.0f} per day, while {worst_game['Game']} is the weakest at about {worst_game['Avg 24h Net / Member']:+,.0f} per day."
            )
        else:
            game_text = (
                "There is no recorded game activity for this group in the selected history."
            )

        if net24 > 0:
            overall_text = (
                f"the average member finishes about {net24:,.0f} richer per day"
            )
        elif net24 < 0:
            overall_text = (
                f"the average member finishes about {abs(net24):,.0f} poorer per day"
            )
        else:
            overall_text = (
                "the average member finishes about even per day"
            )

        game24 = float(
            details[
                "avg_game_net_per_member_24h"
            ]
        )
        game30 = float(
            details[
                "avg_game_net_per_member_30d"
            ]
        )
        self.activity_group_detail_card.set_text(
            (
                f"{group_name} contains {details['members']:,} users. A typical member is active for about {active_hours:,.2f} hours per day, makes about {transactions:,.1f} balance changes per day, and is active on the equivalent of about {active_days:,.1f} days out of 30. "
                f"Across the whole included economy, {overall_text}; at the same pace that is about {net30:+,.0f} over 30 days.\n\n"
                f"Looking only at historical game activity, the games contributed about {game24:+,.0f} per member per day, or about {game30:+,.0f} over 30 days. "
                f"{game_text}\n\n"
                "'Avg Plays / Player / Day' only averages across members who actually played that game. "
                "The game table is descriptive history, and the fixed-frequency Game Simulator does not use these historical play counts or preferences."
            )
        )

    def build_plots_page(self):
        page = self.new_page()

        self.make_page_header(
            page,
            "Plots",
            "Build useful charts from any of the main analysis tables, including plotting numeric values against each other.",
        )

        self.plot_help_card = self.make_help_card(
            page,
            (
                "Choose a data source, X value and Y value, then pick a chart type. Scatter plots are useful for relationships such as activity versus earnings. "
                "Line plots are best for Hourly or Daily trends. Bar plots are useful for comparing categories such as games, income sources or activity groups. "
                "Histograms show the distribution of one numeric value across users or transactions."
            ),
            height=120,
        )

        controls = RoundedPanel(
            page,
            height=190,
            padding=16,
            fill=INFO_BG,
            outline=BORDER,
        )
        controls.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        row1 = tk.Frame(
            controls.inner,
            bg=INFO_BG,
        )
        row1.pack(
            fill=tk.X,
            pady=(0, 10),
        )

        tk.Label(
            row1,
            text="Quick plot",
            bg=INFO_BG,
            fg=MUTED,
            font=(
                "Bahnschrift",
                9,
                "bold",
            ),
        ).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )

        self.plot_preset_dropdown = SingleSelectMenuButton(
            row1,
            options=[
                "User activity vs 30d result",
                "User transactions vs 30d result",
                "Income source net",
                "Hourly net trend",
                "Daily net trend",
                "Activity group 30d net",
                "Activity group game profit",
                "Simulator current vs proposed",
            ],
            value="User activity vs 30d result",
            width=250,
        )
        self.plot_preset_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        RoundedButton(
            row1,
            "Apply Preset",
            self.apply_plot_preset,
            width=108,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.LEFT,
            padx=(0, 16),
        )

        tk.Label(
            row1,
            text="Source",
            bg=INFO_BG,
            fg=MUTED,
            font=(
                "Bahnschrift",
                9,
                "bold",
            ),
        ).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )

        self.plot_source_dropdown = SingleSelectMenuButton(
            row1,
            options=[
                "Users",
                "Activity Groups",
                "Activity Group Games",
                "Income Sources",
                "Hourly",
                "Daily",
                "User Hours",
                "Transactions",
                "Game Simulation",
            ],
            value="Users",
            width=190,
            on_change=self.refresh_plot_fields,
        )
        self.plot_source_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        tk.Label(
            row1,
            text="Activity group",
            bg=INFO_BG,
            fg=MUTED,
            font=(
                "Bahnschrift",
                9,
                "bold",
            ),
        ).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )

        self.plot_group_dropdown = SingleSelectMenuButton(
            row1,
            options=ACTIVITY_GROUP_NAMES,
            value=ACTIVITY_GROUP_NAMES[0],
            width=150,
            on_change=self.refresh_plot_fields,
        )
        self.plot_group_dropdown.pack(
            side=tk.LEFT,
        )

        row2 = tk.Frame(
            controls.inner,
            bg=INFO_BG,
        )
        row2.pack(
            fill=tk.X,
            pady=(0, 10),
        )

        def control_label(
            parent,
            text_value,
        ):
            tk.Label(
                parent,
                text=text_value,
                bg=INFO_BG,
                fg=MUTED,
                font=(
                    "Bahnschrift",
                    8,
                    "bold",
                ),
            ).pack(
                side=tk.LEFT,
                padx=(0, 6),
            )

        control_label(
            row2,
            "X",
        )
        self.plot_x_dropdown = SingleSelectMenuButton(
            row2,
            options=[
                "None"
            ],
            value="None",
            width=190,
        )
        self.plot_x_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        control_label(
            row2,
            "Y",
        )
        self.plot_y_dropdown = SingleSelectMenuButton(
            row2,
            options=[
                "None"
            ],
            value="None",
            width=190,
        )
        self.plot_y_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        control_label(
            row2,
            "Y2",
        )
        self.plot_y2_dropdown = SingleSelectMenuButton(
            row2,
            options=[
                "None"
            ],
            value="None",
            width=190,
        )
        self.plot_y2_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        control_label(
            row2,
            "Chart",
        )
        self.plot_type_dropdown = SingleSelectMenuButton(
            row2,
            options=[
                "Auto",
                "Bar",
                "Line",
                "Scatter",
                "Histogram",
            ],
            value="Auto",
            width=130,
        )
        self.plot_type_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        row3 = tk.Frame(
            controls.inner,
            bg=INFO_BG,
        )
        row3.pack(
            fill=tk.X,
        )

        control_label(
            row3,
            "Aggregate",
        )
        self.plot_aggregation_dropdown = SingleSelectMenuButton(
            row3,
            options=[
                "None",
                "Sum Y by X",
                "Average Y by X",
            ],
            value="None",
            width=170,
        )
        self.plot_aggregation_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        control_label(
            row3,
            "Sort",
        )
        self.plot_sort_dropdown = SingleSelectMenuButton(
            row3,
            options=[
                "Original order",
                "X ascending",
                "X descending",
                "Y ascending",
                "Y descending",
            ],
            value="Original order",
            width=160,
        )
        self.plot_sort_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        control_label(
            row3,
            "Max points",
        )
        self.plot_max_points_var = tk.StringVar(
            value="30"
        )
        self.plot_max_points_entry = RoundedEntry(
            row3,
            textvariable=self.plot_max_points_var,
            width=90,
        )
        self.plot_max_points_entry.pack(
            side=tk.LEFT,
            padx=(0, 6),
        )

        tk.Label(
            row3,
            text="0 = all",
            bg=INFO_BG,
            fg=MUTED,
            font=(
                "Segoe UI",
                8,
            ),
        ).pack(
            side=tk.LEFT,
            padx=(0, 14),
        )

        RoundedButton(
            row3,
            "Plot",
            self.render_plot,
            width=92,
        ).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )

        self.plot_copy_button = RoundedButton(
            row3,
            "Copy Plot Image",
            self.copy_plot_image,
            width=136,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        )
        self.plot_copy_button.pack(
            side=tk.LEFT,
        )

        chart_panel = RoundedPanel(
            page,
            height=590,
            padding=18,
        )
        chart_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        self.plot_canvas = PlotCanvas(
            chart_panel.inner,
            height=520,
        )
        self.plot_canvas.pack(
            fill=tk.BOTH,
            expand=True,
        )

        self.plot_summary_card = ExplanationCard(
            page,
            title="Plot interpretation",
            text=(
                "Create a plot and this section will summarize the most useful pattern in it."
            ),
            min_height=110,
        )
        self.plot_summary_card.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        self.current_plot_rows = []
        self.current_plot_title = ""
        self.plot_has_rendered = False

        self.refresh_plot_fields()

        return page

    def get_plot_source_rows(
        self,
        source=None,
    ):
        if source is None:
            source = self.plot_source_dropdown.get()

        if source == "Users":
            return [
                self.analyzer.user_display_row(
                    row
                )
                for row
                in self.analyzer.user_stats
            ]

        if source == "Activity Groups":
            try:
                basis = self.activity_group_basis_dropdown.get()
            except Exception:
                basis = "Combined activity"

            rows, _ = self.analyzer.get_activity_groups(
                basis
            )
            return list(
                rows
            )

        if source == "Activity Group Games":
            try:
                basis = self.activity_group_basis_dropdown.get()
            except Exception:
                basis = "Combined activity"

            try:
                group_name = self.plot_group_dropdown.get()
            except Exception:
                group_name = ACTIVITY_GROUP_NAMES[0]

            details = self.analyzer.get_activity_group_details(
                group_name,
                basis,
            )
            return list(
                details[
                    "game_rows"
                ]
            )

        if source == "Income Sources":
            return list(
                self.analyzer.reason_stats
            )

        if source == "Hourly":
            return list(
                self.analyzer.hourly_stats
            )

        if source == "Daily":
            return list(
                self.analyzer.daily_stats
            )

        if source == "User Hours":
            return [
                self.analyzer.user_display_row(
                    row
                )
                for row
                in self.analyzer.user_hour_stats
            ]

        if source == "Transactions":
            return [
                {
                    "Timestamp": to_local_string(
                        tx[
                            "timestamp"
                        ]
                    ),
                    "Username":
                        self.analyzer.get_user_label(
                            tx[
                                "user_id"
                            ]
                        ),
                    "Cash": tx[
                        "cash"
                    ],
                    "Bank": tx[
                        "bank"
                    ],
                    "Total": tx[
                        "total"
                    ],
                    "Reason": tx[
                        "reason"
                    ],
                    "Original Reason": tx[
                        "original_reason"
                    ],
                }
                for tx in self.analyzer.transactions
            ]

        if source == "Game Simulation":
            table = getattr(
                self,
                "sim_game_table",
                None,
            )
            if table is None:
                return []
            return list(
                table.data
            )

        return []

    def plot_column_is_numeric(
        self,
        rows,
        column,
    ):
        values = [
            row.get(
                column
            )
            for row in rows
            if row.get(
                column
            ) not in (
                None,
                "",
            )
        ]

        if not values:
            return False

        for value in values:
            if isinstance(
                value,
                bool,
            ):
                return False

            if isinstance(
                value,
                (
                    int,
                    float,
                ),
            ):
                continue

            try:
                float(
                    str(value)
                    .replace(
                        ",",
                        "",
                    )
                )
            except Exception:
                return False

        return True

    def safe_plot_number(
        self,
        value,
    ):
        if isinstance(
            value,
            bool,
        ):
            raise ValueError(
                "Boolean values cannot be plotted as numbers."
            )

        if isinstance(
            value,
            (
                int,
                float,
            ),
        ):
            number = float(
                value
            )
        else:
            number = float(
                str(value)
                .replace(
                    ",",
                    "",
                )
                .strip()
            )

        if not math.isfinite(
            number
        ):
            raise ValueError(
                "Plot values must be finite numbers."
            )

        return number

    def refresh_plot_fields(
        self,
    ):
        if not hasattr(
            self,
            "plot_source_dropdown",
        ):
            return

        rows = self.get_plot_source_rows()

        previous_x = self.plot_x_dropdown.get()
        previous_y = self.plot_y_dropdown.get()
        previous_y2 = self.plot_y2_dropdown.get()

        if not rows:
            self.plot_x_dropdown.set_options(
                [
                    "None"
                ],
                selected="None",
            )
            self.plot_y_dropdown.set_options(
                [
                    "None"
                ],
                selected="None",
            )
            self.plot_y2_dropdown.set_options(
                [
                    "None"
                ],
                selected="None",
            )
            self.plot_canvas.set_message(
                "This source does not have data yet. If you selected Game Simulation, run the simulator first."
            )
            return

        columns = list(
            rows[0].keys()
        )
        numeric_columns = [
            column
            for column in columns
            if self.plot_column_is_numeric(
                rows,
                column,
            )
        ]

        self.plot_x_dropdown.set_options(
            columns,
            selected=(
                previous_x
                if previous_x in columns
                else columns[0]
            ),
        )

        y_options = (
            numeric_columns
            or [
                "None"
            ]
        )
        self.plot_y_dropdown.set_options(
            y_options,
            selected=(
                previous_y
                if previous_y in y_options
                else y_options[0]
            ),
        )

        y2_options = [
            "None",
            *numeric_columns,
        ]
        self.plot_y2_dropdown.set_options(
            y2_options,
            selected=(
                previous_y2
                if previous_y2
                in y2_options
                else "None"
            ),
        )

    def apply_plot_preset(self):
        preset = self.plot_preset_dropdown.get()

        presets = {
            "User activity vs 30d result": {
                "source": "Users",
                "x": "Est. Active Hrs",
                "y": "30d Net",
                "y2": "None",
                "chart": "Scatter",
                "aggregation": "None",
                "sort": "Original order",
                "max_points": "0",
            },
            "User transactions vs 30d result": {
                "source": "Users",
                "x": "Transactions",
                "y": "30d Net",
                "y2": "None",
                "chart": "Scatter",
                "aggregation": "None",
                "sort": "Original order",
                "max_points": "0",
            },
            "Income source net": {
                "source": "Income Sources",
                "x": "Reason",
                "y": "Net Profit",
                "y2": "None",
                "chart": "Bar",
                "aggregation": "None",
                "sort": "Y descending",
                "max_points": "0",
            },
            "Hourly net trend": {
                "source": "Hourly",
                "x": "Hour",
                "y": "Net Profit",
                "y2": "None",
                "chart": "Line",
                "aggregation": "None",
                "sort": "Original order",
                "max_points": "0",
            },
            "Daily net trend": {
                "source": "Daily",
                "x": "Date",
                "y": "Net Profit",
                "y2": "None",
                "chart": "Line",
                "aggregation": "None",
                "sort": "Original order",
                "max_points": "0",
            },
            "Activity group 30d net": {
                "source": "Activity Groups",
                "x": "Group",
                "y": "Avg 30d Net",
                "y2": "None",
                "chart": "Bar",
                "aggregation": "None",
                "sort": "Original order",
                "max_points": "0",
            },
            "Activity group game profit": {
                "source": "Activity Group Games",
                "x": "Game",
                "y": "Avg 30d Net / Member",
                "y2": "None",
                "chart": "Bar",
                "aggregation": "None",
                "sort": "Y descending",
                "max_points": "0",
            },
            "Simulator current vs proposed": {
                "source": "Game Simulation",
                "x": "Game",
                "y": "24h Current Net",
                "y2": "24h Proposed Net",
                "chart": "Bar",
                "aggregation": "None",
                "sort": "Original order",
                "max_points": "0",
            },
        }

        config = presets.get(
            preset
        )
        if config is None:
            return

        self.plot_source_dropdown.set(
            config[
                "source"
            ]
        )
        self.refresh_plot_fields()

        for dropdown, key in [
            (
                self.plot_x_dropdown,
                "x",
            ),
            (
                self.plot_y_dropdown,
                "y",
            ),
            (
                self.plot_y2_dropdown,
                "y2",
            ),
            (
                self.plot_type_dropdown,
                "chart",
            ),
            (
                self.plot_aggregation_dropdown,
                "aggregation",
            ),
            (
                self.plot_sort_dropdown,
                "sort",
            ),
        ]:
            dropdown.set(
                config[key]
            )

        self.plot_max_points_var.set(
            config[
                "max_points"
            ]
        )
        self.render_plot()

    def infer_plot_type(
        self,
        source,
        x_key,
        rows,
    ):
        if source in {
            "Hourly",
            "Daily",
        }:
            return "Line"

        if self.plot_column_is_numeric(
            rows,
            x_key,
        ):
            return "Scatter"

        return "Bar"

    def prepare_plot_data(
        self,
        rows,
        chart_type,
        x_key,
        y_key,
        y2_key,
        aggregation,
        sort_mode,
        max_points,
    ):
        if chart_type == "Histogram":
            prepared = []
            for row in rows:
                try:
                    x_numeric = self.safe_plot_number(
                        row.get(
                            x_key
                        )
                    )
                except Exception:
                    continue

                prepared.append(
                    {
                        "x": row.get(
                            x_key
                        ),
                        "x_numeric": x_numeric,
                        "y1": 1.0,
                        "y2": None,
                    }
                )

            if sort_mode == "X ascending":
                prepared.sort(
                    key=lambda row:
                        row[
                            "x_numeric"
                        ]
                )
            elif sort_mode == "X descending":
                prepared.sort(
                    key=lambda row:
                        row[
                            "x_numeric"
                        ],
                    reverse=True,
                )

            if max_points > 0:
                prepared = prepared[
                    :max_points
                ]

            return prepared

        raw = []

        for row in rows:
            x_value = row.get(
                x_key
            )

            if x_value in (
                None,
                "",
            ):
                continue

            try:
                y1 = self.safe_plot_number(
                    row.get(
                        y_key
                    )
                )
            except Exception:
                continue

            y2 = None
            if (
                y2_key
                and y2_key != "None"
            ):
                try:
                    y2 = self.safe_plot_number(
                        row.get(
                            y2_key
                        )
                    )
                except Exception:
                    y2 = None

            x_numeric = None
            try:
                x_numeric = self.safe_plot_number(
                    x_value
                )
            except Exception:
                pass

            raw.append(
                {
                    "x": x_value,
                    "x_numeric": x_numeric,
                    "y1": y1,
                    "y2": y2,
                }
            )

        if aggregation != "None":
            grouped = defaultdict(
                list
            )
            for row in raw:
                grouped[
                    str(row[
                        "x"
                    ])
                ].append(
                    row
                )

            prepared = []
            use_average = (
                aggregation
                == "Average Y by X"
            )

            for x_text, grouped_rows in grouped.items():
                y1_values = [
                    row[
                        "y1"
                    ]
                    for row in grouped_rows
                ]
                y2_values = [
                    row[
                        "y2"
                    ]
                    for row in grouped_rows
                    if row[
                        "y2"
                    ] is not None
                ]

                if use_average:
                    y1_value = statistics.mean(
                        y1_values
                    )
                    y2_value = (
                        statistics.mean(
                            y2_values
                        )
                        if y2_values
                        else None
                    )
                else:
                    y1_value = sum(
                        y1_values
                    )
                    y2_value = (
                        sum(
                            y2_values
                        )
                        if y2_values
                        else None
                    )

                prepared.append(
                    {
                        "x": x_text,
                        "x_numeric": None,
                        "y1": y1_value,
                        "y2": y2_value,
                    }
                )
        else:
            prepared = raw

        if chart_type == "Scatter":
            prepared = [
                row
                for row in prepared
                if row[
                    "x_numeric"
                ] is not None
            ]

        if sort_mode == "X ascending":
            prepared.sort(
                key=lambda row: (
                    row[
                        "x_numeric"
                    ]
                    if row[
                        "x_numeric"
                    ] is not None
                    else str(
                        row[
                            "x"
                        ]
                    ).lower()
                )
            )
        elif sort_mode == "X descending":
            prepared.sort(
                key=lambda row: (
                    row[
                        "x_numeric"
                    ]
                    if row[
                        "x_numeric"
                    ] is not None
                    else str(
                        row[
                            "x"
                        ]
                    ).lower()
                ),
                reverse=True,
            )
        elif sort_mode == "Y ascending":
            prepared.sort(
                key=lambda row:
                    row[
                        "y1"
                    ]
            )
        elif sort_mode == "Y descending":
            prepared.sort(
                key=lambda row:
                    row[
                        "y1"
                    ],
                reverse=True,
            )

        if max_points > 0:
            prepared = prepared[
                :max_points
            ]

        return prepared

    def calculate_plot_correlation(
        self,
        rows,
    ):
        pairs = [
            (
                row.get(
                    "x_numeric"
                ),
                row.get(
                    "y1"
                ),
            )
            for row in rows
            if row.get(
                "x_numeric"
            ) is not None
        ]

        if len(
            pairs
        ) < 3:
            return None

        xs = [
            float(pair[0])
            for pair in pairs
        ]
        ys = [
            float(pair[1])
            for pair in pairs
        ]

        x_mean = statistics.mean(
            xs
        )
        y_mean = statistics.mean(
            ys
        )

        numerator = sum(
            (
                x - x_mean
            )
            * (
                y - y_mean
            )
            for x, y in zip(
                xs,
                ys,
            )
        )
        x_sq = sum(
            (
                x - x_mean
            ) ** 2
            for x in xs
        )
        y_sq = sum(
            (
                y - y_mean
            ) ** 2
            for y in ys
        )

        denominator = math.sqrt(
            x_sq * y_sq
        )

        if denominator <= 0:
            return None

        return (
            numerator
            / denominator
        )

    def update_plot_summary(
        self,
        rows,
        chart_type,
        source,
        x_key,
        y_key,
        y2_key,
    ):
        if not rows:
            self.plot_summary_card.set_text(
                "There is no valid data to summarize for this plot."
            )
            return

        if chart_type == "Histogram":
            values = [
                row[
                    "x_numeric"
                ]
                for row in rows
            ]
            self.plot_summary_card.set_text(
                (
                    f"This histogram contains {len(values):,} values from {source}. "
                    f"{x_key} ranges from {min(values):,.2f} to {max(values):,.2f}, with a median of {statistics.median(values):,.2f}. "
                    "Use this to see whether most observations are concentrated in one range or spread widely."
                )
            )
            return

        y_values = [
            row[
                "y1"
            ]
            for row in rows
        ]
        best = max(
            rows,
            key=lambda row:
                row[
                    "y1"
                ],
        )
        worst = min(
            rows,
            key=lambda row:
                row[
                    "y1"
                ],
        )

        if chart_type == "Scatter":
            correlation = self.calculate_plot_correlation(
                rows
            )

            if correlation is None:
                correlation_text = (
                    "There is not enough variation to calculate a useful correlation."
                )
            else:
                absolute = abs(
                    correlation
                )
                if absolute >= 0.7:
                    strength = "strong"
                elif absolute >= 0.4:
                    strength = "moderate"
                elif absolute >= 0.2:
                    strength = "weak"
                else:
                    strength = "very weak"

                direction = (
                    "positive"
                    if correlation > 0
                    else "negative"
                )
                correlation_text = (
                    f"The Pearson correlation is about {correlation:+.3f}, which is a {strength} {direction} relationship in the selected data. "
                    "Correlation describes association only and does not prove that one value causes the other."
                )

            self.plot_summary_card.set_text(
                (
                    f"This scatter plot compares {x_key} against {y_key} across {len(rows):,} observations from {source}. "
                    f"{correlation_text} The highest plotted {y_key} is {best['y1']:+,.2f}, while the lowest is {worst['y1']:+,.2f}."
                )
            )
            return

        extra = ""
        if (
            y2_key
            and y2_key != "None"
        ):
            y2_values = [
                row[
                    "y2"
                ]
                for row in rows
                if row.get(
                    "y2"
                ) is not None
            ]
            if y2_values:
                extra = (
                    f" The average {y_key} is {statistics.mean(y_values):+,.2f}, compared with an average {y2_key} of {statistics.mean(y2_values):+,.2f}."
                )

        self.plot_summary_card.set_text(
            (
                f"This {chart_type.lower()} plot shows {len(rows):,} observations from {source}. "
                f"The highest {y_key} is {best['y1']:+,.2f} at {best['x']}, while the lowest is {worst['y1']:+,.2f} at {worst['x']}."
                f"{extra}"
            )
        )

    def render_plot(self):
        try:
            source = self.plot_source_dropdown.get()
            rows = self.get_plot_source_rows(
                source
            )

            if not rows:
                self.plot_canvas.set_message(
                    "There is no data for this source yet."
                )
                self.plot_summary_card.set_text(
                    "There is no data to plot for the selected source."
                )
                return

            x_key = self.plot_x_dropdown.get()
            y_key = self.plot_y_dropdown.get()
            y2_key = self.plot_y2_dropdown.get()
            chart_type = self.plot_type_dropdown.get()
            aggregation = self.plot_aggregation_dropdown.get()
            sort_mode = self.plot_sort_dropdown.get()

            if x_key == "None":
                raise ValueError(
                    "Choose an X value."
                )

            if chart_type != "Histogram" and y_key == "None":
                raise ValueError(
                    "Choose a numeric Y value."
                )

            if chart_type == "Auto":
                chart_type = self.infer_plot_type(
                    source,
                    x_key,
                    rows,
                )

            try:
                max_points = int(
                    self.plot_max_points_var.get()
                    .strip()
                    or "0"
                )
            except ValueError:
                raise ValueError(
                    "Max points must be a whole number. Use 0 for all points."
                )

            if max_points < 0:
                raise ValueError(
                    "Max points cannot be negative."
                )

            if (
                chart_type == "Scatter"
                and not self.plot_column_is_numeric(
                    rows,
                    x_key,
                )
            ):
                raise ValueError(
                    "Scatter plots require a numeric X value."
                )

            if (
                chart_type == "Histogram"
                and not self.plot_column_is_numeric(
                    rows,
                    x_key,
                )
            ):
                raise ValueError(
                    "Histograms require a numeric X value."
                )

            prepared = self.prepare_plot_data(
                rows,
                chart_type,
                x_key,
                y_key,
                y2_key,
                aggregation,
                sort_mode,
                max_points,
            )

            if not prepared:
                raise ValueError(
                    "No rows contain valid values for the selected plot."
                )

            title = (
                f"{source}: {x_key} vs {y_key}"
                if chart_type != "Histogram"
                else f"{source}: distribution of {x_key}"
            )

            y_labels = []
            if chart_type != "Histogram":
                y_labels.append(
                    y_key
                )
                if (
                    y2_key
                    and y2_key != "None"
                    and any(
                        row.get(
                            "y2"
                        ) is not None
                        for row in prepared
                    )
                ):
                    y_labels.append(
                        y2_key
                    )

            self.plot_canvas.set_plot(
                prepared,
                chart_type,
                x_key,
                y_labels,
                title,
            )

            self.current_plot_rows = prepared
            self.current_plot_title = title
            self.plot_has_rendered = True

            self.update_plot_summary(
                prepared,
                chart_type,
                source,
                x_key,
                y_key,
                y2_key,
            )

        except Exception as error:
            messagebox.showerror(
                "Plot Error",
                str(error),
            )

    def copy_plot_image(self):
        if not getattr(
            self,
            "plot_has_rendered",
            False,
        ):
            messagebox.showinfo(
                "Copy Plot Image",
                "Create a plot first.",
            )
            return

        try:
            # Redraw immediately before capture so the copied bitmap matches
            # exactly what is currently visible in the chart.
            self.plot_canvas.redraw()
            self.root.update_idletasks()

            copy_widget_image_to_clipboard(
                self.plot_canvas.canvas
            )

            self.plot_copy_button.set_text(
                "Copied Image"
            )

            self.root.after(
                1200,
                lambda:
                    self.plot_copy_button.set_text(
                        "Copy Plot Image"
                    ),
            )

        except Exception as error:
            messagebox.showerror(
                "Copy Plot Image Error",
                str(error),
            )

    def build_simulator_page(self):
        page = self.new_page()

        self.make_page_header(
            page,
            "Game Simulator",
            (
                "Assume a fixed number of plays of every game per 5 active minutes and test how settings change earnings"
            ),
        )

        self.sim_window_card = self.make_help_card(
            page,
            (
                "Run the simulation and this box will explain the results in plain language. Historical game counts are not used to decide how much somebody plays. "
                "Animal Race is included automatically, including race bets, winnings, animal purchases and provision purchases. "
                "Its bet amount is kept from the history instead of being shown as a normal configurable bet limit. "
                "Animal and provision purchases are kept at the rate actually seen in the history when you change race activity, "
                "so increasing the number of races does not pretend that someone buys the same horse again for every extra race."
            ),
            height=130,
        )

        self.page_explanation_cards[
            "simulator"
        ] = self.sim_window_card

        global_panel = RoundedPanel(
            page,
            height=130,
            padding=18,
        )

        global_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        global_inner = (
            global_panel.inner
        )

        tk.Label(
            global_inner,
            text="Assumed game frequency",
            bg=CARD,
            fg=TEXT,
            font=("Bahnschrift", 11, "bold"),
        ).pack(
            anchor="w"
        )

        global_row = tk.Frame(
            global_inner,
            bg=CARD,
        )

        global_row.pack(
            anchor="w",
            pady=(12, 0),
        )

        tk.Label(
            global_row,
            text="Current plays of EACH game / 5 active min",
            bg=CARD,
            fg=MUTED,
        ).pack(
            side=tk.LEFT,
            padx=(0, 7),
        )

        (
            self.sim_vars[
                "current_games_per_5m"
            ],
            entry,
        ) = self.make_sim_entry(
            global_row,
            DEFAULT_CURRENT_GAMES_PER_5M,
            78,
        )

        entry.pack(
            side=tk.LEFT,
            padx=(0, 22),
        )

        tk.Label(
            global_row,
            text="Proposed plays of EACH game / 5 active min",
            bg=CARD,
            fg=MUTED,
        ).pack(
            side=tk.LEFT,
            padx=(0, 7),
        )

        (
            self.sim_vars[
                "proposed_games_per_5m"
            ],
            entry,
        ) = self.make_sim_entry(
            global_row,
            DEFAULT_CURRENT_GAMES_PER_5M,
            78,
        )

        entry.pack(
            side=tk.LEFT,
            padx=(0, 14),
        )

        self.sim_lock_vars[
            "proposed_games_per_5m"
        ] = tk.BooleanVar(value=False)

        tk.Checkbutton(
            global_row,
            text="Lock play rate",
            variable=self.sim_lock_vars[
                "proposed_games_per_5m"
            ],
            bg=CARD,
            fg=MUTED,
            selectcolor=DEEP_BG,
            activebackground=CARD,
            activeforeground=TEXT,
            highlightthickness=0,
        ).pack(
            side=tk.LEFT
        )

        settings_panel = RoundedPanel(
            page,
            height=420,
            padding=18,
        )

        settings_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        settings_inner = (
            settings_panel.inner
        )

        tk.Label(
            settings_inner,
            text="Bet limits",
            bg=CARD,
            fg=TEXT,
            font=("Bahnschrift", 11, "bold"),
        ).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 12),
        )

        headings = [
            "Game",
            "Current Min",
            "Current Max",
            "Proposed Min",
            "Proposed Max",
            "Additional configurable settings",
        ]

        for (
            index,
            heading,
        ) in enumerate(
            headings
        ):
            tk.Label(
                settings_inner,
                text=heading,
                bg=CARD,
                fg=MUTED,
                font=("Bahnschrift", 8, "bold"),
            ).grid(
                row=1,
                column=index,
                sticky="w",
                padx=(0, 12),
                pady=(0, 8),
            )

        row_number = 2

        for game in BET_LIMIT_GAMES:
            tk.Label(
                settings_inner,
                text=(
                    GAME_DISPLAY[
                        game
                    ]
                ),
                bg=CARD,
                fg=TEXT,
                font=("Bahnschrift", 9, "bold"),
            ).grid(
                row=row_number,
                column=0,
                sticky="w",
                pady=5,
                padx=(0, 12),
            )

            current_min = (
                DEFAULT_GAME_LIMITS[
                    game
                ]["min"]
            )

            current_max = (
                DEFAULT_GAME_LIMITS[
                    game
                ]["max"]
            )

            field_names = [
                (
                    "current_min",
                    current_min,
                ),

                (
                    "current_max",
                    current_max,
                ),

                (
                    "proposed_min",
                    current_min,
                ),

                (
                    "proposed_max",
                    current_max,
                ),
            ]

            for (
                column_offset,
                (
                    field,
                    value,
                ),
            ) in enumerate(
                field_names,
                start=1,
            ):
                key = (
                    f"{game}:{field}"
                )

                (
                    self.sim_vars[
                        key
                    ],
                    entry,
                ) = self.make_sim_entry(
                    settings_inner,
                    value,
                    78,
                )

                entry.grid(
                    row=row_number,
                    column=column_offset,
                    sticky="w",
                    padx=(0, 12),
                    pady=4,
                )

            extra = tk.Frame(
                settings_inner,
                bg=CARD,
            )

            extra.grid(
                row=row_number,
                column=5,
                sticky="w",
                pady=4,
            )

            lock_box = tk.Frame(
                extra,
                bg=CARD,
            )
            lock_box.pack(
                side=tk.RIGHT,
                padx=(14, 0),
            )

            for lock_field, lock_label in (
                ("min", "Lock min"),
                ("max", "Lock max"),
            ):
                lock_key = f"{game}:proposed_{lock_field}"
                self.sim_lock_vars[lock_key] = tk.BooleanVar(
                    value=False
                )
                tk.Checkbutton(
                    lock_box,
                    text=lock_label,
                    variable=self.sim_lock_vars[lock_key],
                    bg=CARD,
                    fg=MUTED,
                    selectcolor=DEEP_BG,
                    activebackground=CARD,
                    activeforeground=TEXT,
                    highlightthickness=0,
                    font=("Segoe UI", 8),
                ).pack(
                    side=tk.LEFT,
                    padx=(0, 4),
                )

            if game == "blackjack":
                tk.Label(
                    extra,
                    text="Decks",
                    bg=CARD,
                    fg=MUTED,
                ).pack(
                    side=tk.LEFT,
                    padx=(0, 5),
                )

                (
                    self.sim_vars[
                        "current_blackjack_decks"
                    ],
                    entry,
                ) = self.make_sim_entry(
                    extra,
                    DEFAULT_BLACKJACK_DECKS,
                    56,
                )

                entry.pack(
                    side=tk.LEFT
                )

                tk.Label(
                    extra,
                    text="->",
                    bg=CARD,
                    fg=MUTED,
                ).pack(
                    side=tk.LEFT,
                    padx=5,
                )

                (
                    self.sim_vars[
                        "proposed_blackjack_decks"
                    ],
                    entry,
                ) = self.make_sim_entry(
                    extra,
                    DEFAULT_BLACKJACK_DECKS,
                    56,
                )

                entry.pack(
                    side=tk.LEFT
                )

            elif game == "slot machine":
                tk.Label(
                    extra,
                    text="Symbols",
                    bg=CARD,
                    fg=MUTED,
                ).pack(
                    side=tk.LEFT,
                    padx=(0, 5),
                )

                (
                    self.sim_vars[
                        "current_slot_symbols"
                    ],
                    entry,
                ) = self.make_sim_entry(
                    extra,
                    DEFAULT_SLOT_SYMBOLS,
                    50,
                )

                entry.pack(
                    side=tk.LEFT
                )

                tk.Label(
                    extra,
                    text="->",
                    bg=CARD,
                    fg=MUTED,
                ).pack(
                    side=tk.LEFT,
                    padx=4,
                )

                (
                    self.sim_vars[
                        "proposed_slot_symbols"
                    ],
                    entry,
                ) = self.make_sim_entry(
                    extra,
                    DEFAULT_SLOT_SYMBOLS,
                    50,
                )

                entry.pack(
                    side=tk.LEFT,
                    padx=(0, 10),
                )

                tk.Label(
                    extra,
                    text="Multiplier",
                    bg=CARD,
                    fg=MUTED,
                ).pack(
                    side=tk.LEFT,
                    padx=(0, 5),
                )

                (
                    self.sim_vars[
                        "current_slot_multiplier"
                    ],
                    entry,
                ) = self.make_sim_entry(
                    extra,
                    DEFAULT_SLOT_MULTIPLIER,
                    58,
                )

                entry.pack(
                    side=tk.LEFT
                )

                tk.Label(
                    extra,
                    text="->",
                    bg=CARD,
                    fg=MUTED,
                ).pack(
                    side=tk.LEFT,
                    padx=4,
                )

                (
                    self.sim_vars[
                        "proposed_slot_multiplier"
                    ],
                    entry,
                ) = self.make_sim_entry(
                    extra,
                    DEFAULT_SLOT_MULTIPLIER,
                    58,
                )

                entry.pack(
                    side=tk.LEFT,
                    padx=(0, 6),
                )

                for lock_key, lock_label in (
                    ("proposed_slot_symbols", "Lock symbols"),
                    ("proposed_slot_multiplier", "Lock multiplier"),
                ):
                    self.sim_lock_vars[lock_key] = tk.BooleanVar(
                        value=False
                    )
                    tk.Checkbutton(
                        extra,
                        text=lock_label,
                        variable=self.sim_lock_vars[lock_key],
                        bg=CARD,
                        fg=MUTED,
                        selectcolor=DEEP_BG,
                        activebackground=CARD,
                        activeforeground=TEXT,
                        highlightthickness=0,
                        font=("Segoe UI", 8),
                    ).pack(
                        side=tk.LEFT,
                        padx=(0, 4),
                    )

            elif game == "cockfight":
                tk.Label(
                    extra,
                    text="Start %",
                    bg=CARD,
                    fg=MUTED,
                ).pack(
                    side=tk.LEFT,
                    padx=(0, 5),
                )

                (
                    self.sim_vars[
                        "current_cockfight_start"
                    ],
                    entry,
                ) = self.make_sim_entry(
                    extra,
                    DEFAULT_COCKFIGHT_START,
                    55,
                )

                entry.pack(
                    side=tk.LEFT
                )

                tk.Label(
                    extra,
                    text="->",
                    bg=CARD,
                    fg=MUTED,
                ).pack(
                    side=tk.LEFT,
                    padx=4,
                )

                (
                    self.sim_vars[
                        "proposed_cockfight_start"
                    ],
                    entry,
                ) = self.make_sim_entry(
                    extra,
                    DEFAULT_COCKFIGHT_START,
                    55,
                )

                entry.pack(
                    side=tk.LEFT,
                    padx=(0, 8),
                )

                tk.Label(
                    extra,
                    text="Max %",
                    bg=CARD,
                    fg=MUTED,
                ).pack(
                    side=tk.LEFT,
                    padx=(0, 5),
                )

                (
                    self.sim_vars[
                        "current_cockfight_max"
                    ],
                    entry,
                ) = self.make_sim_entry(
                    extra,
                    DEFAULT_COCKFIGHT_MAX,
                    55,
                )

                entry.pack(
                    side=tk.LEFT
                )

                tk.Label(
                    extra,
                    text="->",
                    bg=CARD,
                    fg=MUTED,
                ).pack(
                    side=tk.LEFT,
                    padx=4,
                )

                (
                    self.sim_vars[
                        "proposed_cockfight_max"
                    ],
                    entry,
                ) = self.make_sim_entry(
                    extra,
                    DEFAULT_COCKFIGHT_MAX,
                    55,
                )

                entry.pack(
                    side=tk.LEFT,
                    padx=(0, 6),
                )

                for lock_key, lock_label in (
                    ("proposed_cockfight_start", "Lock start"),
                    ("proposed_cockfight_max", "Lock max %"),
                ):
                    self.sim_lock_vars[lock_key] = tk.BooleanVar(
                        value=False
                    )
                    tk.Checkbutton(
                        extra,
                        text=lock_label,
                        variable=self.sim_lock_vars[lock_key],
                        bg=CARD,
                        fg=MUTED,
                        selectcolor=DEEP_BG,
                        activebackground=CARD,
                        activeforeground=TEXT,
                        highlightthickness=0,
                        font=("Segoe UI", 8),
                    ).pack(
                        side=tk.LEFT,
                        padx=(0, 4),
                    )

            else:
                tk.Label(
                    extra,
                    text=(
                        "Payout rules kept as "
                        "historical/game-defined"
                    ),
                    bg=CARD,
                    fg=MUTED,
                    font=(
                        "Segoe UI",
                        8,
                    ),
                ).pack(
                    side=tk.LEFT
                )

            row_number += 1

        chicken_panel = RoundedPanel(
            page,
            height=115,
            padding=18,
        )

        chicken_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        chicken_inner = (
            chicken_panel.inner
        )

        tk.Label(
            chicken_inner,
            text="Cockfight chicken cost",
            bg=CARD,
            fg=TEXT,
            font=("Bahnschrift", 11, "bold"),
        ).pack(
            anchor="w"
        )

        chicken_row = tk.Frame(
            chicken_inner,
            bg=CARD,
        )

        chicken_row.pack(
            anchor="w",
            pady=(10, 0),
        )

        tk.Label(
            chicken_row,
            text="Current price",
            bg=CARD,
            fg=MUTED,
        ).pack(
            side=tk.LEFT,
            padx=(0, 6),
        )

        (
            self.sim_vars[
                "current_chicken_price"
            ],
            entry,
        ) = self.make_sim_entry(
            chicken_row,
            DEFAULT_CHICKEN_PRICE,
            70,
        )

        entry.pack(
            side=tk.LEFT,
            padx=(0, 15),
        )

        tk.Label(
            chicken_row,
            text="Proposed price",
            bg=CARD,
            fg=MUTED,
        ).pack(
            side=tk.LEFT,
            padx=(0, 6),
        )

        (
            self.sim_vars[
                "proposed_chicken_price"
            ],
            entry,
        ) = self.make_sim_entry(
            chicken_row,
            DEFAULT_CHICKEN_PRICE,
            70,
        )

        entry.pack(
            side=tk.LEFT,
            padx=(0, 12),
        )

        self.sim_lock_vars[
            "proposed_chicken_price"
        ] = tk.BooleanVar(value=False)

        tk.Checkbutton(
            chicken_row,
            text="Lock chicken price",
            variable=self.sim_lock_vars[
                "proposed_chicken_price"
            ],
            bg=CARD,
            fg=MUTED,
            selectcolor=DEEP_BG,
            activebackground=CARD,
            activeforeground=TEXT,
            highlightthickness=0,
        ).pack(
            side=tk.LEFT
        )

        slot_command_panel = RoundedPanel(
            page,
            height=125,
            padding=18,
        )

        slot_command_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        slot_command_inner = slot_command_panel.inner

        tk.Label(
            slot_command_inner,
            text="Slot symbols for commands",
            bg=CARD,
            fg=TEXT,
            font=("Bahnschrift", 11, "bold"),
        ).pack(
            anchor="w"
        )

        slot_command_row = tk.Frame(
            slot_command_inner,
            bg=CARD,
        )

        slot_command_row.pack(
            fill=tk.X,
            pady=(10, 0),
        )

        self.slot_command_symbols_var = tk.StringVar()

        slot_symbol_entry = RoundedEntry(
            slot_command_row,
            textvariable=self.slot_command_symbols_var,
            width=340,
            height=34,
        )

        slot_symbol_entry.pack(
            side=tk.LEFT,
            padx=(0, 14),
        )

        slot_symbol_entry.bind_key(
            "<KeyRelease>",
            lambda event:
            self.mark_sim_dirty(),
        )

        tk.Label(
            slot_command_row,
            text=(
                "Enter the exact slot symbols separated by commas. "
                "Example: <symbol1>, <symbol2>. This only affects generated commands, not the simulation."
            ),
            bg=CARD,
            fg=MUTED,
            justify=tk.LEFT,
            anchor="w",
            wraplength=700,
            font=(
                "Segoe UI",
                8,
            ),
        ).pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )

        optimizer_panel = RoundedPanel(
            page,
            height=650,
            padding=18,
        )
        optimizer_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        optimizer_inner = optimizer_panel.inner

        tk.Label(
            optimizer_inner,
            text="Activity group target optimizer",
            bg=CARD,
            fg=TEXT,
            font=("Bahnschrift", 11, "bold"),
        ).pack(
            anchor="w"
        )

        tk.Label(
            optimizer_inner,
            text=(
                "Choose one or more activity groups, enter how much you want an average member to gain or lose from games over 30 days, then let the program search for nearby settings. "
                "You can select a group by clicking its checkbox or group name. Typing a target automatically selects that group. "
                "Every activity group is assumed to play EVERY modeled game the same number of times per five active minutes, using the play-rate input above. Historical game popularity and historical game mix are ignored. The optimizer also tries to keep Blackjack, Cock Fight, Roulette, Slot Machine and Higher or Lower beneficial and relevant instead of making one game carry the whole economy. "
                "Russian Roulette is intentionally excluded from that balancing goal and is not automatically changed. Locked values are never changed."
            ),
            bg=CARD,
            fg=MUTED,
            justify=tk.LEFT,
            anchor="w",
            wraplength=1250,
            font=(
                "Segoe UI",
                8,
            ),
        ).pack(
            fill=tk.X,
            anchor="w",
            pady=(4, 12),
        )

        optimizer_options = tk.Frame(
            optimizer_inner,
            bg=CARD,
        )
        optimizer_options.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        tk.Label(
            optimizer_options,
            text="Group users by",
            bg=CARD,
            fg=MUTED,
        ).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )

        self.sim_optimizer_basis_dropdown = SingleSelectMenuButton(
            optimizer_options,
            options=ACTIVITY_GROUP_BASIS_OPTIONS,
            value="Combined activity",
            width=210,
        )
        self.sim_optimizer_basis_dropdown.pack(
            side=tk.LEFT,
            padx=(0, 16),
        )

        tk.Label(
            optimizer_options,
            text=(
                "Groups differ only by active time. Every group is assumed to play each game at the fixed plays-per-5-active-minutes rate above."
            ),
            bg=CARD,
            fg=MUTED,
            justify=tk.LEFT,
            anchor="w",
            wraplength=620,
            font=(
                "Segoe UI",
                8,
            ),
        ).pack(
            side=tk.LEFT,
            padx=(0, 12),
        )

        RoundedButton(
            optimizer_options,
            "Refresh Groups",
            self.refresh_activity_target_rows,
            width=116,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.LEFT,
        )

        target_header = tk.Frame(
            optimizer_inner,
            bg=CARD,
        )
        target_header.pack(
            fill=tk.X,
            pady=(0, 4),
        )

        header_items = [
            ("Use", 7),
            ("Activity group", 18),
            ("Current simulated 30d", 22),
            ("Target 30d", 18),
            ("Optimizer result", 22),
        ]
        for label_text, width in header_items:
            tk.Label(
                target_header,
                text=label_text,
                width=width,
                anchor="w",
                bg=CARD,
                fg=MUTED,
                font=("Bahnschrift", 8, "bold"),
            ).pack(
                side=tk.LEFT,
                padx=(0, 8),
            )

        for group_name in ACTIVITY_GROUP_NAMES:
            target_row = tk.Frame(
                optimizer_inner,
                bg=CARD,
            )
            target_row.pack(
                fill=tk.X,
                pady=3,
            )

            enabled_var = tk.BooleanVar(value=False)
            target_var = tk.StringVar(value="")
            self.sim_target_enabled_vars[group_name] = enabled_var
            self.sim_target_value_vars[group_name] = target_var

            group_checkbox = tk.Checkbutton(
                target_row,
                text="Select",
                variable=enabled_var,
                bg=CARD,
                fg=TEXT,
                selectcolor=DEEP_BG,
                activebackground=CARD,
                activeforeground=TEXT,
                highlightthickness=0,
                width=7,
                anchor="w",
                cursor="hand2",
            )
            group_checkbox.pack(
                side=tk.LEFT,
                padx=(0, 8),
            )

            group_label = tk.Label(
                target_row,
                text=group_name,
                width=18,
                anchor="w",
                bg=CARD,
                fg=TEXT,
                cursor="hand2",
                font=("Bahnschrift", 9, "bold"),
            )
            group_label.pack(
                side=tk.LEFT,
                padx=(0, 8),
            )

            # The whole group label is clickable, not just the small checkbox.
            # This makes selecting target groups much easier.
            group_label.bind(
                "<Button-1>",
                lambda event, name=group_name:
                    self.toggle_activity_target_group(name),
            )

            current_label = tk.Label(
                target_row,
                text="Not calculated",
                width=22,
                anchor="w",
                bg=CARD,
                fg=MUTED,
            )
            current_label.pack(
                side=tk.LEFT,
                padx=(0, 8),
            )
            current_label.config(
                cursor="hand2"
            )
            current_label.bind(
                "<Button-1>",
                lambda event, name=group_name:
                    self.toggle_activity_target_group(name),
            )
            self.sim_target_current_labels[group_name] = current_label

            target_entry = RoundedEntry(
                target_row,
                textvariable=target_var,
                width=145,
                height=32,
            )
            target_entry.pack(
                side=tk.LEFT,
                padx=(0, 16),
            )

            # Focusing or typing in a target automatically selects the group.
            target_entry.bind(
                "<Button-1>",
                lambda event, name=group_name:
                    self.enable_activity_target_group(name),
            )
            target_entry.bind(
                "<FocusIn>",
                lambda event, name=group_name:
                    self.enable_activity_target_group(name),
            )
            target_var.trace_add(
                "write",
                lambda *args, name=group_name:
                    self.enable_activity_target_group_if_target(name),
            )

            result_label = tk.Label(
                target_row,
                text="-",
                width=28,
                anchor="w",
                bg=CARD,
                fg=MUTED,
            )
            result_label.pack(
                side=tk.LEFT,
            )
            self.sim_target_result_labels[group_name] = result_label

        optimizer_buttons = tk.Frame(
            optimizer_inner,
            bg=CARD,
        )
        optimizer_buttons.pack(
            fill=tk.X,
            pady=(14, 6),
        )

        RoundedButton(
            optimizer_buttons,
            "Find Settings",
            self.optimize_simulator_targets,
            width=120,
        ).pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        RoundedButton(
            optimizer_buttons,
            "Unlock All",
            lambda: self.set_all_sim_locks(False),
            width=104,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        RoundedButton(
            optimizer_buttons,
            "Lock All",
            lambda: self.set_all_sim_locks(True),
            width=96,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.LEFT,
        )

        optimizer_status_row = tk.Frame(
            optimizer_inner,
            bg=CARD,
        )
        optimizer_status_row.pack(
            fill=tk.X,
            pady=(4, 0),
        )

        self.sim_optimizer_status_label = tk.Label(
            optimizer_status_row,
            text=(
                "The optimizer has not been run. Positive targets mean the average user should gain money. It will also try to keep the normal configurable games broadly useful instead of concentrating all profit into one category. Russian Roulette is excluded."
            ),
            bg=CARD,
            fg=MUTED,
            justify=tk.LEFT,
            anchor="w",
            wraplength=1120,
            font=(
                "Segoe UI",
                8,
            ),
        )
        self.sim_optimizer_status_label.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
            anchor="w",
        )

        self.sim_optimizer_copy_button = RoundedButton(
            optimizer_status_row,
            "Copy",
            lambda: self.copy_label_for_discord(
                self.sim_optimizer_status_label,
                title="Optimizer Result",
                button=self.sim_optimizer_copy_button,
                button_text="Copy",
            ),
            width=68,
            height=30,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        )
        self.sim_optimizer_copy_button.pack(
            side=tk.RIGHT,
            padx=(10, 0),
        )

        action_panel = RoundedPanel(
            page,
            height=98,
            padding=16,
            fill=INFO_BG,
            outline=BORDER,
        )

        action_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        action_row = (
            action_panel.inner
        )

        RoundedButton(
            action_row,
            "Run Simulation",
            self.run_simulator,
            width=130,
        ).pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        RoundedButton(
            action_row,
            "Reset Settings",
            self.reset_simulator,
            width=120,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.LEFT,
            padx=(0, 18),
        )

        self.sim_summary_label = (
            tk.Label(
                action_row,
                text=(
                    "Simulation has not "
                    "been run yet."
                ),
                bg=INFO_BG,
                fg=TEXT,
                justify=tk.LEFT,
                anchor="w",
                wraplength=900,
                font=(
                    "Segoe UI",
                    10,
                ),
            )
        )

        self.sim_summary_label.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )

        self.sim_summary_copy_button = RoundedButton(
            action_row,
            "Copy",
            lambda: self.copy_label_for_discord(
                self.sim_summary_label,
                title="Simulation Summary",
                button=self.sim_summary_copy_button,
                button_text="Copy",
            ),
            width=68,
            height=32,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        )
        self.sim_summary_copy_button.pack(
            side=tk.RIGHT,
            padx=(10, 0),
        )

        game_result_panel = (
            RoundedPanel(
                page,
                height=520,
                padding=18,
            )
        )

        game_result_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        tk.Label(
            game_result_panel.inner,
            text="24 hour game impact",
            bg=CARD,
            fg=TEXT,
            font=("Bahnschrift", 11, "bold"),
        ).pack(
            anchor="w",
            pady=(0, 8),
        )

        self.sim_game_table = (
            DataTable(
                game_result_panel.inner,
                height=11,
            )
        )

        self.sim_game_table.pack(
            fill=tk.BOTH,
            expand=True,
        )

        user_result_panel = (
            RoundedPanel(
                page,
                height=620,
                padding=18,
            )
        )

        user_result_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        tk.Label(
            user_result_panel.inner,
            text=(
                "24 hour projected "
                "user impact"
            ),
            bg=CARD,
            fg=TEXT,
            font=("Bahnschrift", 11, "bold"),
        ).pack(
            anchor="w",
            pady=(0, 8),
        )

        self.sim_user_table = (
            DataTable(
                user_result_panel.inner,
                height=15,
                double_click_callback=(
                    self.open_sim_user_from_row
                ),
            )
        )

        self.sim_user_table.pack(
            fill=tk.BOTH,
            expand=True,
        )

        individual_panel = (
            RoundedPanel(
                page,
                height=650,
                padding=18,
            )
        )

        individual_panel.pack(
            fill=tk.X,
            pady=(0, 12),
        )

        individual_top = tk.Frame(
            individual_panel.inner,
            bg=CARD,
        )

        individual_top.pack(
            fill=tk.X,
            pady=(0, 10),
        )

        tk.Label(
            individual_top,
            text=(
                "Individual user simulation"
            ),
            bg=CARD,
            fg=TEXT,
            font=("Bahnschrift", 11, "bold"),
        ).pack(
            side=tk.LEFT
        )

        self.sim_user_dropdown = (
            SingleSelectMenuButton(
                individual_top,
                options=[
                    "No users"
                ],
                value="No users",
                width=220,
            )
        )

        self.sim_user_dropdown.pack(
            side=tk.LEFT,
            padx=(20, 10),
        )

        RoundedButton(
            individual_top,
            "View User",
            self.view_simulator_user,
            width=96,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.LEFT
        )

        self.sim_user_copy_button = RoundedButton(
            individual_top,
            "Copy Summary",
            lambda: self.copy_label_for_discord(
                self.sim_user_summary_label,
                title="Individual User Simulation",
                button=self.sim_user_copy_button,
                button_text="Copy Summary",
            ),
            width=112,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        )
        self.sim_user_copy_button.pack(
            side=tk.LEFT,
            padx=(10, 0),
        )

        self.sim_user_summary_label = (
            tk.Label(
                individual_panel.inner,
                text=(
                    "Run the simulation, "
                    "then select a user."
                ),
                bg=CARD,
                fg=TEXT,
                justify=tk.LEFT,
                anchor="w",
                wraplength=1200,
                font=(
                    "Segoe UI",
                    9,
                ),
            )
        )

        self.sim_user_summary_label.pack(
            fill=tk.X,
            anchor="w",
            pady=(0, 10),
        )

        def resize_sim_user_summary(
            event,
        ):
            self.sim_user_summary_label.config(
                wraplength=max(
                    300,
                    event.width - 12,
                )
            )

            try:
                self.sim_user_game_table.after_idle(
                    self.sim_user_game_table.fit_parent_panel_to_content
                )
            except Exception:
                pass

        individual_panel.inner.bind(
            "<Configure>",
            resize_sim_user_summary,
            add="+",
        )

        self.sim_user_game_table = (
            DataTable(
                individual_panel.inner,
                height=14,
            )
        )

        self.sim_user_game_table.pack(
            fill=tk.BOTH,
            expand=True,
        )

        command_panel = RoundedPanel(
            page,
            height=360,
            padding=18,
        )

        command_panel.pack(
            fill=tk.X
        )

        command_top = tk.Frame(
            command_panel.inner,
            bg=CARD,
        )

        command_top.pack(
            fill=tk.X,
            pady=(0, 8),
        )

        tk.Label(
            command_top,
            text=(
                "Commands for changed settings only"
            ),
            bg=CARD,
            fg=TEXT,
            font=("Bahnschrift", 11, "bold"),
        ).pack(
            side=tk.LEFT
        )

        RoundedButton(
            command_top,
            "Copy Commands",
            self.copy_simulator_commands,
            width=120,
            bg=SECONDARY_BG,
            hover=SECONDARY_HOVER,
            fg=TEXT,
        ).pack(
            side=tk.RIGHT
        )

        self.sim_command_status_label = tk.Label(
            command_panel.inner,
            text=(
                "Run the simulation to generate commands. "
                "Only settings that changed will appear below."
            ),
            bg=CARD,
            fg=MUTED,
            justify=tk.LEFT,
            anchor="w",
            wraplength=1200,
            font=(
                "Segoe UI",
                8,
            ),
        )

        self.sim_command_status_label.pack(
            fill=tk.X,
            anchor="w",
            pady=(0, 8),
        )

        self.sim_command_text = tk.Text(
            command_panel.inner,
            bg=DEEP_BG,
            fg=TEXT,
            relief=tk.FLAT,
            bd=0,
            font=(
                "Consolas",
                9,
            ),
            height=12,
            wrap=tk.NONE,
        )

        self.sim_command_text.pack(
            fill=tk.BOTH,
            expand=True,
        )

        return page

    def show_page(
        self,
        key,
    ):
        if (
            key
            not in self.page_frames
        ):
            return

        for frame in (
            self.page_frames.values()
        ):
            frame.pack_forget()

        self.page_frames[
            key
        ].pack(
            fill=tk.X
        )

        self.current_page = key

        if key == "plots":
            try:
                self.refresh_plot_fields()
            except Exception:
                pass

        for (
            nav_key,
            button,
        ) in (
            self.nav_buttons.items()
        ):
            button.set_active(
                nav_key == key
            )

        self.scroll_area.scroll_to_top()

    def mark_dirty(self):
        self.apply_state.set_pending()

    def mark_sim_dirty(self):
        self.sim_dirty = True

        if hasattr(
            self,
            "sim_summary_label",
        ):
            self.sim_summary_label.config(
                text=(
                    "Simulator settings changed. "
                    "Run Simulation to update results."
                )
            )

        if hasattr(
            self,
            "sim_command_text",
        ):
            self.sim_command_text.delete(
                "1.0",
                tk.END,
            )

        if hasattr(
            self,
            "sim_command_status_label",
        ):
            self.sim_command_status_label.config(
                text=(
                    "Settings changed. Run Simulation "
                    "to generate fresh copy-paste commands."
                )
            )

    def on_pending_chicken_change(
        self,
    ):
        current_selected = (
            self.exclude_dropdown
            .get_selected()
        )

        reasons = (
            self.analyzer
            .get_available_reasons(
                self.pending_chicken_as_cockfight()
            )
        )

        self.exclude_dropdown.set_options(
            reasons,
            preserve=False,
        )

        for reason in current_selected:
            if (
                reason
                in self.exclude_dropdown.variables
            ):
                self.exclude_dropdown.variables[
                    reason
                ].set(
                    True
                )

        self.exclude_dropdown._update_label()

        self.mark_dirty()

    def on_pending_quick_range(
        self,
    ):
        if not (
            self.analyzer
            .all_transactions
        ):
            self.mark_dirty()
            return

        value = (
            self.quick_dropdown
            .get()
        )

        if value == "Custom":
            self.mark_dirty()
            return

        if value == "All time":
            self.start_var.set("")
            self.end_var.set("")

            self.mark_dirty()

            return

        hour_map = {
            "Last 1h":
                1,

            "Last 6h":
                6,

            "Last 12h":
                12,

            "Last 24h":
                24,

            "Last 48h":
                48,

            "Last 7d":
                24 * 7,

            "Last 14d":
                24 * 14,

            "Last 30d":
                24 * 30,
        }

        hours = (
            hour_map.get(
                value
            )
        )

        if hours is None:
            self.mark_dirty()
            return

        latest = (
            self.analyzer
            .all_transactions[-1][
                "timestamp"
            ]
        )

        start = (
            latest
            - timedelta(
                hours=hours
            )
        )

        self.start_var.set(
            to_local_string(
                start
            )[:-3]
        )

        self.end_var.set(
            to_local_string(
                latest
            )[:-3]
        )

        self.mark_dirty()

    def pending_chicken_as_cockfight(
        self,
    ):
        return (
            self.chicken_dropdown.get()
            == "Chicken -> cockfight"
        )

    def reset_filter_form(self):
        self.quick_dropdown.set(
            "All time"
        )

        self.chicken_dropdown.set(
            "Chicken -> cockfight"
        )

        self.start_var.set("")
        self.end_var.set("")

        reasons = (
            self.analyzer
            .get_available_reasons(
                True
            )
        )

        self.exclude_dropdown.set_options(
            reasons,
            preserve=False,
        )

        self.mark_dirty()

    def get_pending_times(self):
        start_text = (
            self.start_var
            .get()
            .strip()
        )

        end_text = (
            self.end_var
            .get()
            .strip()
        )

        start_time = (
            parse_user_datetime(
                start_text,
                False,
            )
            if start_text
            else None
        )

        end_time = (
            parse_user_datetime(
                end_text,
                True,
            )
            if end_text
            else None
        )

        if (
            start_time is not None
            and end_time is not None
            and start_time > end_time
        ):
            raise ValueError(
                "Start time cannot be "
                "after end time."
            )

        return (
            start_time,
            end_time,
        )

    def choose_database(self):
        current_path = Path(
            self.analyzer.db_path
        )

        if current_path.parent.exists():
            initial_directory = (
                current_path.parent
            )
        else:
            initial_directory = BASE_DIR

        selected_path = (
            filedialog.askopenfilename(
                title="Choose Economy Database",
                initialdir=str(
                    initial_directory
                ),
                filetypes=[
                    (
                        "Discord History Tracker databases",
                        "*.dht",
                    ),
                    (
                        "SQLite databases",
                        "*.db",
                    ),
                    (
                        "SQLite databases",
                        "*.sqlite",
                    ),
                    (
                        "SQLite databases",
                        "*.sqlite3",
                    ),
                    (
                        "All files",
                        "*.*",
                    ),
                ],
            )
        )

        if not selected_path:
            return

        previous_path = (
            self.analyzer.db_path
        )

        self.analyzer.db_path = (
            Path(selected_path)
        )

        if self.load_database():
            return

        # If the selected file could not be loaded, restore the
        # previous database location. If it still exists, reload it so
        # the existing dashboard is not left in a half-loaded state.
        self.analyzer.db_path = (
            previous_path
        )

        previous = Path(
            previous_path
        )

        if previous.exists():
            self.load_database()

    def load_database(self):
        self.status_label.config(
            text="Loading database..."
        )

        self.root.update_idletasks()

        try:
            self.analyzer.load_transactions()

            if (
                self.analyzer
                .all_transactions
            ):
                first = (
                    self.analyzer
                    .all_transactions[0][
                        "timestamp"
                    ]
                )

                last = (
                    self.analyzer
                    .all_transactions[-1][
                        "timestamp"
                    ]
                )

                selected_db = Path(
                    self.analyzer.db_path
                )

                self.dataset_label.config(
                    text=(
                        f"{selected_db.name}  |  "
                        f"{to_local_string(first)}"
                        " to "
                        f"{to_local_string(last)}"
                    )
                )

                self.sidebar_info.config(
                    text=(
                        f"{len(self.analyzer.all_transactions):,} parsed\n"
                        f"{to_local_string(first)[:10]}"
                        " to "
                        f"{to_local_string(last)[:10]}\n"
                        f"{selected_db.name}"
                    )
                )

            reasons = (
                self.analyzer
                .get_available_reasons(
                    True
                )
            )

            self.exclude_dropdown.set_options(
                reasons,
                preserve=False,
            )

            self.quick_dropdown.set(
                "All time"
            )

            self.chicken_dropdown.set(
                "Chicken -> cockfight"
            )

            self.start_var.set("")
            self.end_var.set("")

            self.apply_filters()

            inferred_chicken_price = (
                self.analyzer
                .infer_chicken_price()
            )

            self.sim_vars[
                "current_chicken_price"
            ].set(
                str(
                    round(
                        inferred_chicken_price,
                        2,
                    )
                )
            )

            self.sim_vars[
                "proposed_chicken_price"
            ].set(
                str(
                    round(
                        inferred_chicken_price,
                        2,
                    )
                )
            )

            self.mark_sim_dirty()

            return True

        except Exception as error:
            self.status_label.config(
                text="Database load failed"
            )

            messagebox.showerror(
                "Database Error",
                str(error),
            )

            return False

    def apply_filters(self):
        if not (
            self.analyzer
            .all_transactions
        ):
            return

        try:
            (
                start_time,
                end_time,
            ) = self.get_pending_times()

            excluded = (
                self.exclude_dropdown
                .get_selected()
            )

            chicken_as_cockfight = (
                self.pending_chicken_as_cockfight()
            )

            self.analyzer.analyze(
                excluded_reasons=excluded,
                chicken_as_cockfight=(
                    chicken_as_cockfight
                ),
                start_time=start_time,
                end_time=end_time,
            )

            self.populate_all()
            self.update_kpis()
            self.update_user_projection_info()
            self.update_sim_window_info()

            self.apply_state.set_applied()

            self.mark_sim_dirty()

            filters = [
                (
                    f"{len(excluded)} excluded"
                    if excluded
                    else "nothing excluded"
                )
            ]

            filters.append(
                (
                    "chicken in cockfight"
                    if chicken_as_cockfight
                    else "chicken in buy"
                )
            )

            self.status_label.config(
                text=(
                    f"{len(self.analyzer.transactions):,} "
                    "transactions | "
                    + " | ".join(
                        filters
                    )
                )
            )

            self.scroll_area._update_region()

        except Exception as error:
            messagebox.showerror(
                "Filter Error",
                str(error),
            )

    def populate_all(self):
        self.summary_table.set_data(
            [
                {
                    "Statistic":
                        name,

                    "Value":
                        value,
                }
                for (
                    name,
                    value,
                )
                in self.analyzer.summary_stats
            ]
        )

        self.users_table.set_data(
            [
                self.analyzer.user_display_row(
                    row
                )
                for row
                in self.analyzer.user_stats
            ]
        )

        self.sources_table.set_data(
            self.analyzer.reason_stats
        )

        self.hourly_table.set_data(
            self.analyzer.hourly_stats
        )

        self.daily_table.set_data(
            self.analyzer.daily_stats
        )

        self.user_hours_table.set_data(
            [
                self.analyzer.user_display_row(
                    row
                )
                for row
                in self.analyzer.user_hour_stats
            ]
        )

        transaction_rows = []

        for tx in reversed(
            self.analyzer.transactions
        ):
            transaction_rows.append(
                {
                    "Timestamp":
                        to_local_string(
                            tx["timestamp"]
                        ),

                    "Username":
                        self.analyzer.get_user_label(
                            tx["user_id"]
                        ),

                    "Cash":
                        tx["cash"],

                    "Bank":
                        tx["bank"],

                    "Total":
                        tx["total"],

                    "Reason":
                        tx["reason"],

                    "Original Reason":
                        tx[
                            "original_reason"
                        ],
                }
            )

        self.transactions_table.set_data(
            transaction_rows
        )

        self.refresh_user_dropdowns()
        self.update_page_explanations()

        if hasattr(
            self,
            "plot_source_dropdown",
        ):
            try:
                self.refresh_plot_fields()
                if getattr(
                    self,
                    "plot_has_rendered",
                    False,
                ):
                    self.render_plot()
            except Exception:
                pass

        if (
            self.user_dropdown.get()
            != "No users"
        ):
            self.view_selected_user(
                show_message=False
            )

    def update_user_projection_info(
        self,
    ):
        rows = self.analyzer.user_stats
        hours = self.analyzer.get_analysis_hours()
        days = self.analyzer.get_analysis_days()

        if not rows:
            self.user_projection_card.set_text(
                "There are no users to describe for the time you selected."
            )
            return

        total_users = len(rows)
        total_net = sum(row["Net Profit"] for row in rows)
        total_received = sum(row["Gross Earned"] for row in rows)
        total_lost = sum(row["Gross Lost"] for row in rows)
        total_changes = sum(row["Transactions"] for row in rows)
        total_active_hours = sum(row["Est. Active Hrs"] for row in rows)

        median_net = statistics.median(
            row["Net Profit"] for row in rows
        )

        typical = min(
            rows,
            key=lambda row: abs(row["Net Profit"] - median_net),
        )

        most_active = max(
            rows,
            key=lambda row: row["Est. Active Hrs"],
        )

        top_projected = max(
            rows,
            key=lambda row: row["30d Net"],
        )

        if total_net > 0:
            total_result = (
                f"Across all {total_users:,} users, balances ended {total_net:,.0f} higher than they started."
            )
        elif total_net < 0:
            total_result = (
                f"Across all {total_users:,} users, balances ended {abs(total_net):,.0f} lower than they started."
            )
        else:
            total_result = (
                f"Across all {total_users:,} users, balances ended almost exactly where they started."
            )

        typical_change = typical["Net Profit"]
        if typical_change > 0:
            typical_result = f"finished {typical_change:,.0f} richer"
        elif typical_change < 0:
            typical_result = f"finished {abs(typical_change):,.0f} poorer"
        else:
            typical_result = "finished about even"

        typical_month = typical["30d Net"]
        if typical_month > 0:
            typical_month_text = f"about {typical_month:,.0f} richer after 30 days"
        elif typical_month < 0:
            typical_month_text = f"about {abs(typical_month):,.0f} poorer after 30 days"
        else:
            typical_month_text = "about even after 30 days"

        projected = top_projected["30d Net"]
        if projected > 0:
            projected_text = (
                f"The strongest 30-day estimate is {self.analyzer.get_user_label(top_projected['User ID'])}, who would gain about {projected:,.0f} if the same pace continued."
            )
        elif projected < 0:
            projected_text = (
                f"Even the strongest 30-day estimate is negative: {self.analyzer.get_user_label(top_projected['User ID'])} would lose about {abs(projected):,.0f} if the same pace continued."
            )
        else:
            projected_text = (
                f"The strongest 30-day estimate is around zero for {self.analyzer.get_user_label(top_projected['User ID'])}."
            )

        average_changes_per_user = (
            total_changes / total_users
            if total_users
            else 0
        )

        average_activity_per_user = (
            total_active_hours / total_users
            if total_users
            else 0
        )

        self.user_projection_card.set_text(
            (
                f"This table contains {total_users:,} people from {hours:,.2f} hours of history, which is about {days:,.2f} days. "
                f"Together they had {total_changes:,} balance changes, or about {average_changes_per_user:,.1f} per person. "
                f"They received {total_received:,.0f} and spent or lost {total_lost:,.0f}. {total_result}\n\n"

                f"A useful example of a fairly typical user is {self.analyzer.get_user_label(typical['User ID'])}, because their result is close to the middle of the group. "
                f"They received {typical['Gross Earned']:,.0f}, spent or lost {typical['Gross Lost']:,.0f}, and {typical_result}. "
                f"If that exact pace continued, their 30-day result would be {typical_month_text}. "
                f"They had {typical['Transactions']:,.0f} balance changes, used the economy for about {typical['Est. Active Hrs']:,.2f} hours, "
                f"were active for about {typical['Activity %']:,.2f}% of the whole selected period, used it on {typical['Active Days']:,.0f} different days, "
                f"and those uses were split into about {typical['Sessions']:,.0f} separate periods of activity. "
                f"Their most profitable source after both gains and losses were counted was '{typical['Top Income Source']}', and their most recent economy use in this selection was {typical['Last Seen']}.\n\n"

                f"The most active person was {self.analyzer.get_user_label(most_active['User ID'])} with about {most_active['Est. Active Hrs']:,.2f} hours of economy use. "
                f"Across everyone, the estimated combined time using economy commands was {total_active_hours:,.2f} hours, or about {average_activity_per_user:,.2f} hours per person. "
                "That combined number can be larger than the length of the selected period because several people can be using the economy at the same time. "
                "The activity time is estimated from five-minute blocks: if a person used the economy at least once in a five-minute block, that block counts as five minutes.\n\n"

                f"{projected_text} The 30-day number is not a promise. It simply stretches the selected user's current pace out to 30 days."
            )
        )
    def update_sim_window_info(
        self,
    ):
        hours = self.analyzer.get_analysis_hours()
        days = self.analyzer.get_analysis_days()

        self.sim_window_card.set_text(
            (
                f"You selected {hours:,.2f} hours of history, which is about {days:,.2f} days. "
                "History is used to estimate active time and the economics of each game, but it is NOT used to decide how many games somebody plays. "
                "You choose how many times EACH game is assumed to be played per five active minutes.\n\n"
                "For example, entering 2 means that during every five minutes a person is active, the simulator assumes 2 Blackjack plays, 2 Cock Fight plays, 2 Roulette plays, and so on."
            )
        )
    def update_page_explanations(self):
        txs = self.analyzer.transactions

        if not txs:
            return

        hours = self.analyzer.get_analysis_hours()
        days = self.analyzer.get_analysis_days()
        factor30 = self.analyzer.get_30_day_factor()

        net = sum(tx["total"] for tx in txs)
        earned = sum(
            tx["total"]
            for tx in txs
            if tx["total"] > 0
        )
        lost = -sum(
            tx["total"]
            for tx in txs
            if tx["total"] < 0
        )

        users = {
            tx["user_id"]
            for tx in txs
        }

        positive = sum(
            1
            for tx in txs
            if tx["total"] > 0
        )

        negative = sum(
            1
            for tx in txs
            if tx["total"] < 0
        )

        active_blocks = {
            (
                tx["user_id"],
                floor_5_minute(
                    tx["timestamp"].astimezone(LOCAL_TZ)
                ),
            )
            for tx in txs
        }

        combined_activity_hours = len(active_blocks) * 5 / 60
        changes_per_user = len(txs) / len(users) if users else 0
        activity_per_user = combined_activity_hours / len(users) if users else 0
        per_hour = net / hours if hours else 0
        per_day = net / days if days else 0
        month_result = net * factor30
        removed_per_100 = lost / earned * 100 if earned else 0

        overview = self.page_explanation_cards.get(
            "summary_table"
        )

        if overview:
            if net > 0:
                balance_result = (
                    f"After all additions and removals are combined, users are {net:,.0f} richer than they were at the start."
                )
            elif net < 0:
                balance_result = (
                    f"After all additions and removals are combined, users are {abs(net):,.0f} poorer than they were at the start."
                )
            else:
                balance_result = (
                    "After all additions and removals are combined, users are almost exactly even."
                )

            if per_hour > 0:
                hour_text = (
                    f"On average, user balances are growing by about {per_hour:,.0f} every hour."
                )
            elif per_hour < 0:
                hour_text = (
                    f"On average, user balances are shrinking by about {abs(per_hour):,.0f} every hour."
                )
            else:
                hour_text = (
                    "On average, user balances are not changing much from hour to hour."
                )

            if month_result > 0:
                month_text = (
                    f"If this exact pace continued for 30 days, users would end up about {month_result:,.0f} richer in total."
                )
            elif month_result < 0:
                month_text = (
                    f"If this exact pace continued for 30 days, users would end up about {abs(month_result):,.0f} poorer in total."
                )
            else:
                month_text = (
                    "If this pace continued for 30 days, user balances would stay about even overall."
                )

            if earned > 0:
                if removed_per_100 > 100:
                    removal_text = (
                        f"For every 100 added to user balances, about {removed_per_100:,.2f} is taken back out. "
                        f"That is {removed_per_100 - 100:,.2f} more removed than added for every 100 that enters."
                    )
                elif removed_per_100 < 100:
                    removal_text = (
                        f"For every 100 added to user balances, about {removed_per_100:,.2f} is taken back out. "
                        f"That leaves about {100 - removed_per_100:,.2f} of each 100 still in user balances."
                    )
                else:
                    removal_text = (
                        "For every 100 added to user balances, about 100 is taken back out, so money entering and leaving is almost perfectly balanced."
                    )
            else:
                removal_text = (
                    "No money was added during this selection, so there is no useful added-versus-removed comparison."
                )

            overview.set_text(
                (
                    f"The selected period starts at {to_local_string(self.analyzer.analysis_start)} and ends at {to_local_string(self.analyzer.analysis_end)}. "
                    f"That covers {hours:,.2f} hours, or about {days:,.2f} days.\n\n"

                    f"There are {len(txs):,} balance changes in that time. A balance change is one recorded event where someone's cash or bank amount went up or down. "
                    f"Those changes came from {len(users):,} different people, which works out to about {changes_per_user:,.1f} balance changes per person on average.\n\n"

                    f"The estimated combined time spent using the economy is {combined_activity_hours:,.2f} hours, or about {activity_per_user:,.2f} hours per person. "
                    f"This is not saying the selected period lasted {combined_activity_hours:,.2f} hours. The selected period only lasted {hours:,.2f} hours. "
                    "The larger number adds each person's estimated activity together, so two people using the economy for the same hour count as two user-hours. "
                    "A person's time is estimated from five-minute blocks in which they had at least one economy balance change.\n\n"

                    f"A total of {earned:,.0f} was added to user balances. This happened across {positive:,} separate positive balance changes. "
                    f"A total of {lost:,.0f} was taken from user balances through spending, losses or removals, across {negative:,} negative balance changes. "
                    f"The difference between those two amounts is {abs(net):,.0f}. {balance_result}\n\n"

                    f"The 'average balance change per hour' is {per_hour:+,.2f}. {hour_text} "
                    f"That is the same pace as about {abs(per_day):,.0f} {'gained' if per_day > 0 else 'lost' if per_day < 0 else 'changed'} per day.\n\n"

                    f"The 30-day result shown is {month_result:+,.2f}. {month_text} This assumes the same amount of activity and the same winning, losing and spending pattern continues.\n\n"

                    f"The 'removed for every 100 added' number is {removed_per_100:,.2f}. {removal_text}"
                )
            )

        sources = self.analyzer.reason_stats
        source_card = self.page_explanation_cards.get(
            "sources_table"
        )

        if source_card and sources:
            biggest_gain = max(
                sources,
                key=lambda row: row["Net Profit"],
            )
            biggest_loss = min(
                sources,
                key=lambda row: row["Net Profit"],
            )
            busiest = max(
                sources,
                key=lambda row: row["Transactions"],
            )

            def source_sentence(row):
                result = row["Net Profit"]
                if result > 0:
                    outcome = f"left users {result:,.0f} richer"
                elif result < 0:
                    outcome = f"left users {abs(result):,.0f} poorer"
                else:
                    outcome = "left users about even"

                per_hour_source = row["Net / Hour"]
                if per_hour_source > 0:
                    hourly_words = f"added about {per_hour_source:,.0f} to user balances per hour"
                elif per_hour_source < 0:
                    hourly_words = f"removed about {abs(per_hour_source):,.0f} from user balances per hour"
                else:
                    hourly_words = "changed user balances by almost nothing per hour"

                return (
                    f"'{row['Reason']}' appeared {row['Transactions']:,} times and involved {row['Unique Users']:,} different users. "
                    f"It paid out {row['Gross Earned']:,.0f} and took {row['Gross Lost']:,.0f}. After those are compared, it {outcome}. "
                    f"Spread across the whole selected period, that means it {hourly_words}."
                )

            source_card.set_text(
                (
                    "Each row is one game, command or money source. 'Money paid out' is everything that source added to users. "
                    "'Money taken' is everything it removed. The difference tells you whether that source made users richer or poorer overall.\n\n"
                    f"The most-used source was {busiest['Reason']}. {source_sentence(busiest)}\n\n"
                    f"The source that helped users the most was {biggest_gain['Reason']}. {source_sentence(biggest_gain)}\n\n"
                    f"The source that hurt users the most was {biggest_loss['Reason']}. {source_sentence(biggest_loss)}"
                )
            )

        hourly = self.analyzer.hourly_stats
        hourly_card = self.page_explanation_cards.get(
            "hourly_table"
        )

        if hourly_card and hourly:
            best = max(
                hourly,
                key=lambda row: row["Net Profit"],
            )
            worst = min(
                hourly,
                key=lambda row: row["Net Profit"],
            )
            busiest = max(
                hourly,
                key=lambda row: row["Transactions"],
            )

            def hour_sentence(row):
                result = row["Net Profit"]
                if result > 0:
                    result_words = f"users finished that hour {result:,.0f} richer"
                elif result < 0:
                    result_words = f"users finished that hour {abs(result):,.0f} poorer"
                else:
                    result_words = "users finished that hour about even"

                return (
                    f"At {row['Hour']}, users received {row['Gross Earned']:,.0f} and spent or lost {row['Gross Lost']:,.0f}, so {result_words}. "
                    f"There were {row['Transactions']:,} balance changes from {row['Active Users']:,} different users."
                )

            hourly_card.set_text(
                (
                    "Each row is one clock hour. The money received and money spent/lost numbers show what moved in each direction during that hour. "
                    "The difference tells you whether users as a group ended that hour richer or poorer. The last two numbers tell you how busy that hour was.\n\n"
                    f"Best hour for users: {hour_sentence(best)}\n\n"
                    f"Worst hour for users: {hour_sentence(worst)}\n\n"
                    f"Busiest hour: {hour_sentence(busiest)}"
                )
            )

        daily = self.analyzer.daily_stats
        daily_card = self.page_explanation_cards.get(
            "daily_table"
        )

        if daily_card and daily:
            best = max(
                daily,
                key=lambda row: row["Net Profit"],
            )
            worst = min(
                daily,
                key=lambda row: row["Net Profit"],
            )
            busiest = max(
                daily,
                key=lambda row: row["Transactions"],
            )

            def day_sentence(row):
                result = row["Net Profit"]
                if result > 0:
                    result_words = f"users ended the day {result:,.0f} richer"
                elif result < 0:
                    result_words = f"users ended the day {abs(result):,.0f} poorer"
                else:
                    result_words = "users ended the day about even"

                return (
                    f"On {row['Date']}, users received {row['Gross Earned']:,.0f} and spent or lost {row['Gross Lost']:,.0f}, so {result_words}. "
                    f"There were {row['Transactions']:,} balance changes from {row['Active Users']:,} different users."
                )

            daily_card.set_text(
                (
                    "Each row is one calendar day. The table shows how much money entered user balances, how much left them, the final difference, "
                    "how many balance changes happened, and how many different people used the economy that day.\n\n"
                    f"Best day for users: {day_sentence(best)}\n\n"
                    f"Worst day for users: {day_sentence(worst)}\n\n"
                    f"Busiest day: {day_sentence(busiest)}"
                )
            )

        user_hours = self.analyzer.user_hour_stats
        user_hours_card = self.page_explanation_cards.get(
            "user_hours_table"
        )

        if user_hours_card and user_hours:
            best = max(
                user_hours,
                key=lambda row: row["Net Profit"],
            )
            worst = min(
                user_hours,
                key=lambda row: row["Net Profit"],
            )
            busiest = max(
                user_hours,
                key=lambda row: row["Transactions"],
            )

            def user_hour_sentence(row):
                result = row["Net Profit"]
                if result > 0:
                    result_words = f"finished {result:,.0f} richer"
                elif result < 0:
                    result_words = f"finished {abs(result):,.0f} poorer"
                else:
                    result_words = "finished about even"

                return (
                    f"{self.analyzer.get_user_label(row['User ID'])} at {row['Hour']} received {row['Gross Earned']:,.0f}, spent or lost {row['Gross Lost']:,.0f}, "
                    f"and {result_words} after {row['Transactions']:,} balance changes."
                )

            user_hours_card.set_text(
                (
                    "Each row follows one person for one specific hour. This lets you see short bursts where one person won a lot, lost a lot, or simply used the economy many times.\n\n"
                    f"Strongest one-hour result: {user_hour_sentence(best)}\n\n"
                    f"Weakest one-hour result: {user_hour_sentence(worst)}\n\n"
                    f"Most balance changes by one user in one hour: {user_hour_sentence(busiest)}"
                )
            )

        transaction_card = self.page_explanation_cards.get(
            "transactions_table"
        )

        if transaction_card:
            largest_gain = max(
                txs,
                key=lambda tx: tx["total"],
            )
            largest_loss = min(
                txs,
                key=lambda tx: tx["total"],
            )

            def transaction_sentence(tx):
                direction = "added" if tx["total"] >= 0 else "removed"
                return (
                    f"At {to_local_string(tx['timestamp'])}, {self.analyzer.get_user_label(tx['user_id'])} had {abs(tx['total']):,.0f} {direction}. "
                    f"The cash part changed by {tx['cash']:+,.0f} and the bank part changed by {tx['bank']:+,.0f}. "
                    f"The program groups the event under '{tx['reason']}'. The original stored reason was '{tx['original_reason']}'."
                )

            transaction_card.set_text(
                (
                    f"This page contains all {len(txs):,} individual balance changes used by the other pages. "
                    "The time tells you when the change happened, Username tells you who it happened to, Cash and Bank show which part of their balance moved, "
                    "and Total is the combined amount. A positive total means they received money; a negative total means money left their balance.\n\n"
                    f"Largest single addition: {transaction_sentence(largest_gain)}\n\n"
                    f"Largest single removal: {transaction_sentence(largest_loss)}"
                )
            )
        try:
            self.refresh_activity_groups()
            self.refresh_activity_target_rows()
        except Exception:
            pass

    def update_kpis(self):
        txs = (
            self.analyzer
            .transactions
        )

        if not txs:
            return

        net = sum(
            tx["total"]
            for tx in txs
        )

        generated = sum(
            tx["total"]
            for tx in txs
            if tx["total"] > 0
        )

        removed = -sum(
            tx["total"]
            for tx in txs
            if tx["total"] < 0
        )

        users = len({
            tx["user_id"]
            for tx in txs
        })

        hours = (
            self.analyzer
            .get_analysis_hours()
        )

        self.kpi_cards[
            "net"
        ].set_value(
            format_compact(
                net
            )
        )

        self.kpi_cards[
            "generated"
        ].set_value(
            format_compact(
                generated
            )
        )

        self.kpi_cards[
            "removed"
        ].set_value(
            format_compact(
                removed
            )
        )

        self.kpi_cards[
            "users"
        ].set_value(
            f"{users:,}"
        )

        self.kpi_cards[
            "rate"
        ].set_value(
            format_compact(
                (
                    net / hours
                    if hours
                    else 0
                )
            )
        )

    def refresh_user_dropdowns(self):
        users = [
            self.analyzer.get_user_label(
                row["User ID"]
            )
            for row
            in self.analyzer.user_stats
        ]

        if not users:
            users = [
                "No users"
            ]

        previous_main = (
            self.user_dropdown
            .get()
        )

        self.user_dropdown.set_options(
            users,
            selected=(
                previous_main
                if previous_main
                in users
                else users[0]
            ),
        )

        previous_sim = (
            self.sim_user_dropdown
            .get()
        )

        self.sim_user_dropdown.set_options(
            users,
            selected=(
                previous_sim
                if previous_sim
                in users
                else users[0]
            ),
        )

    def open_user_from_row(
        self,
        row,
    ):
        user_value = (
            str(
                row.get(
                    "Username",
                    row.get(
                        "User ID",
                        "",
                    ),
                )
            )
            .strip()
        )

        if not user_value:
            return

        user_id = (
            self.analyzer.resolve_user_label(
                user_value
            )
        )
        user_label = (
            self.analyzer.get_user_label(
                user_id
            )
        )

        self.user_dropdown.set(
            user_label
        )

        self.view_selected_user(
            show_message=False
        )

        self.show_page(
            "user_breakdown"
        )

    def view_selected_user(
        self,
        show_message=True,
    ):
        user_value = self.user_dropdown.get()

        if user_value == "No users":
            return

        user_id = (
            self.analyzer.resolve_user_label(
                user_value
            )
        )

        txs = self.analyzer.get_user_transactions(
            user_id
        )

        if not txs:
            if show_message:
                messagebox.showinfo(
                    "User Breakdown",
                    (
                        "No transactions for this user in the current filters."
                    ),
                )
            return

        summary = self.analyzer.get_user_summary(
            user_id
        )

        self.user_summary_table.set_data(
            [
                {
                    "Statistic": name,
                    "Value": value,
                }
                for name, value in summary
            ]
        )

        breakdown = self.analyzer.get_user_reason_breakdown(
            user_id
        )

        self.user_sources_table.set_data(
            breakdown
        )

        transaction_rows = []

        for tx in reversed(txs):
            transaction_rows.append(
                {
                    "Timestamp": to_local_string(
                        tx["timestamp"]
                    ),
                    "Cash": tx["cash"],
                    "Bank": tx["bank"],
                    "Total": tx["total"],
                    "Reason": tx["reason"],
                    "Original Reason": tx["original_reason"],
                }
            )

        self.user_transactions_table.set_data(
            transaction_rows
        )

        activity = self.analyzer.calculate_activity(
            txs
        )
        factor = self.analyzer.get_30_day_factor()

        net = sum(tx["total"] for tx in txs)
        earned = sum(
            tx["total"]
            for tx in txs
            if tx["total"] > 0
        )
        lost = -sum(
            tx["total"]
            for tx in txs
            if tx["total"] < 0
        )

        self.user_breakdown_caption.config(
            text=(
                f"{len(txs):,} balance changes | "
                f"about {activity['active_minutes']:,.0f} active minutes | "
                f"30-day result: {net * factor:+,.0f}"
            )
        )

        net_income_rows = [
            row
            for row in breakdown
            if row["Net Profit"] > 0
        ]
        loss_rows = [
            row
            for row in breakdown
            if row["Gross Lost"] > 0
        ]

        top_income = (
            max(
                net_income_rows,
                key=lambda row: row["Net Profit"],
            )
            if net_income_rows
            else None
        )

        top_loss = (
            max(
                loss_rows,
                key=lambda row: row["Gross Lost"],
            )
            if loss_rows
            else None
        )

        if net > 0:
            result_text = (
                f"They finished the selected period {net:,.0f} richer."
            )
        elif net < 0:
            result_text = (
                f"They finished the selected period {abs(net):,.0f} poorer."
            )
        else:
            result_text = (
                "They finished the selected period about even."
            )

        month_value = net * factor
        if month_value > 0:
            month_text = (
                f"If the same pace continued for 30 days, that would be about {month_value:,.0f} gained."
            )
        elif month_value < 0:
            month_text = (
                f"If the same pace continued for 30 days, that would be about {abs(month_value):,.0f} lost."
            )
        else:
            month_text = (
                "If the same pace continued for 30 days, they would still be around even."
            )

        last_transaction = to_local_string(
            max(
                tx["timestamp"]
                for tx in txs
            )
        )

        if top_income:
            income_text = (
                f"Their best money source overall was '{top_income['Reason']}'. After counting both the {top_income['Gross Earned']:,.0f} it gave them "
                f"and the {top_income['Gross Lost']:,.0f} it took from them, they came out {top_income['Net Profit']:,.0f} richer from that source. "
                f"That makes it their top net income source across {top_income['Transactions']:,} recorded uses."
            )
        else:
            income_text = (
                "None of their money sources left them with a positive profit during the selected period."
            )

        if top_loss:
            loss_text = (
                f"Their biggest source of spending or losses was '{top_loss['Reason']}'. It took {top_loss['Gross Lost']:,.0f}, "
                f"which was {top_loss['Loss Share %']:,.1f}% of everything they spent or lost. "
                f"That source also paid them {top_loss['Gross Earned']:,.0f}, so its final effect on their balance was {top_loss['Net Profit']:+,.0f} across {top_loss['Transactions']:,} recorded uses."
            )
        else:
            loss_text = (
                "No source removed money from this user during the selected period."
            )

        self.user_breakdown_help_card.set_text(
            (
                f"User {user_id} had {len(txs):,} balance changes. They received {earned:,.0f} in total and spent or lost {lost:,.0f}. "
                f"The difference between those amounts is {abs(net):,.0f}. {result_text} {month_text}\n\n"

                f"They appear to have spent about {activity['active_hours']:,.2f} hours actually using the economy. "
                f"That is about {activity['activity_percent']:,.2f}% of the entire selected period. Their activity was split into about {activity['sessions']:,.0f} separate periods and spread across {activity['active_days']:,.0f} different days. "
                "This time is estimated from five-minute blocks with at least one economy balance change, so it is an estimate of economy use, not Discord online time.\n\n"

                f"{income_text}\n\n{loss_text}\n\n"

                f"Their most recent balance change in the selected period was {last_transaction}. The money-source table below shows the same story broken down source by source: "
                "money received is what that source paid them, money spent/lost is what it took, the final change is the difference, and the two percentage columns show how much of all their received money or all their lost money came from that source."
            )
        )
    def enable_activity_target_group(
        self,
        group_name,
    ):
        var = self.sim_target_enabled_vars.get(
            group_name
        )
        if var is not None:
            var.set(True)

    def enable_activity_target_group_if_target(
        self,
        group_name,
    ):
        target_var = self.sim_target_value_vars.get(
            group_name
        )
        enabled_var = self.sim_target_enabled_vars.get(
            group_name
        )

        if (
            target_var is not None
            and enabled_var is not None
            and target_var.get().strip()
        ):
            enabled_var.set(True)

    def toggle_activity_target_group(
        self,
        group_name,
    ):
        var = self.sim_target_enabled_vars.get(
            group_name
        )
        if var is not None:
            var.set(
                not bool(var.get())
            )

    def set_all_sim_locks(
        self,
        value,
    ):
        for var in self.sim_lock_vars.values():
            var.set(bool(value))

    def get_locked_simulator_keys(self):
        return {
            key
            for key, var in self.sim_lock_vars.items()
            if var.get()
        }

    def refresh_activity_target_rows(self):
        if not self.analyzer.transactions:
            return

        try:
            settings = self.get_simulator_settings()
        except Exception:
            return

        try:
            basis = self.sim_optimizer_basis_dropdown.get()
        except Exception:
            basis = "Combined activity"

        context = self.analyzer.prepare_activity_optimizer_context(
            basis
        )
        baseline_settings = self.analyzer.make_current_baseline_settings(
            settings
        )
        predictions = self.analyzer.evaluate_activity_group_monthly(
            baseline_settings,
            context,
            use_actual_game_mix=False,
        )

        for group_name in ACTIVITY_GROUP_NAMES:
            member_count = len(
                context["members"].get(
                    group_name,
                    set(),
                )
            )
            value = predictions.get(group_name, 0.0)
            label = self.sim_target_current_labels.get(
                group_name
            )
            if label is not None:
                if member_count > 0:
                    label.config(
                        text=f"{value:+,.0f} ({member_count} users)"
                    )
                else:
                    label.config(
                        text="No users"
                    )

            result_label = self.sim_target_result_labels.get(
                group_name
            )
            if result_label is not None:
                result_label.config(
                    text="-"
                )

    def apply_optimizer_settings_to_ui(
        self,
        settings,
    ):
        self.sim_vars[
            "proposed_games_per_5m"
        ].set(
            f"{settings['proposed_games_per_5m']:g}"
        )

        for game in BET_LIMIT_GAMES:
            proposed = settings["games"][game]["proposed"]
            self.sim_vars[
                f"{game}:proposed_min"
            ].set(
                f"{proposed['min']:g}"
            )
            self.sim_vars[
                f"{game}:proposed_max"
            ].set(
                f"{proposed['max']:g}"
            )

        self.sim_vars[
            "proposed_slot_symbols"
        ].set(
            str(settings["proposed_slot_symbols"])
        )
        self.sim_vars[
            "proposed_slot_multiplier"
        ].set(
            f"{settings['proposed_slot_multiplier']:g}"
        )
        self.sim_vars[
            "proposed_cockfight_start"
        ].set(
            f"{settings['proposed_cockfight_start']:g}"
        )
        self.sim_vars[
            "proposed_cockfight_max"
        ].set(
            f"{settings['proposed_cockfight_max']:g}"
        )
        self.sim_vars[
            "proposed_chicken_price"
        ].set(
            f"{settings['proposed_chicken_price']:g}"
        )

    def optimize_simulator_targets(self):
        if not self.analyzer.transactions:
            return

        try:
            targets = {}

            for group_name in ACTIVITY_GROUP_NAMES:
                enabled = self.sim_target_enabled_vars[
                    group_name
                ].get()
                if not enabled:
                    continue

                raw_value = self.sim_target_value_vars[
                    group_name
                ].get().strip()

                if not raw_value:
                    raise ValueError(
                        f"Enter a 30-day target for {group_name}."
                    )

                targets[group_name] = parse_float(
                    raw_value
                )

            if not targets:
                raise ValueError(
                    "Select at least one activity group and enter a monthly target."
                )

            settings = self.get_simulator_settings()
            basis = self.sim_optimizer_basis_dropdown.get()
            use_actual_mix = False
            locked_keys = self.get_locked_simulator_keys()

            self.sim_optimizer_status_label.config(
                text=(
                    "Searching for settings. This can take a few seconds because the program repeatedly checks the selected activity groups against the history."
                )
            )
            self.root.update_idletasks()

            result = self.analyzer.optimize_activity_targets(
                settings,
                targets,
                locked_keys,
                basis=basis,
                use_actual_game_mix=use_actual_mix,
            )

            self.apply_optimizer_settings_to_ui(
                result["settings"]
            )

            # Run the same simulation that fills the 24-hour game table first.
            # Then recalculate the target rows from the values actually present
            # in the UI. This guarantees that the target result and game table
            # are using the same settings and the same simulation model.
            self.mark_sim_dirty()
            self.run_simulator()

            actual_settings = self.get_simulator_settings()
            actual_context = self.analyzer.prepare_activity_optimizer_context(
                basis
            )
            actual_predictions = self.analyzer.evaluate_activity_group_monthly(
                actual_settings,
                actual_context,
                use_actual_game_mix=False,
            )

            for group_name in ACTIVITY_GROUP_NAMES:
                result_label = self.sim_target_result_labels.get(
                    group_name
                )
                if result_label is None:
                    continue

                if group_name in targets:
                    predicted = actual_predictions[group_name]
                    target = targets[group_name]
                    miss = predicted - target
                    result_label.config(
                        text=(
                            f"{predicted:+,.0f} | target {target:+,.0f} | miss {miss:+,.0f}"
                        ),
                        fg=TEXT,
                    )
                else:
                    result_label.config(
                        text="Not targeted",
                        fg=MUTED,
                    )

            # Keep the returned values aligned with what is actually shown.
            result["predictions"] = actual_predictions

            game_balance = result.get(
                "game_balance",
                {},
            )
            profitable_games = int(
                game_balance.get(
                    "profitable_games",
                    0,
                )
            )
            balanced_game_count = int(
                game_balance.get(
                    "game_count",
                    0,
                )
            )
            largest_share = (
                float(
                    game_balance.get(
                        "largest_positive_share",
                        0.0,
                    )
                )
                * 100.0
            )

            changed_count = len(
                result.get(
                    "changed_settings",
                    [],
                )
            )

            actual_misses = [
                abs(
                    actual_predictions[group_name]
                    - float(target)
                )
                for group_name, target
                in targets.items()
            ]
            actual_average_miss = (
                statistics.mean(actual_misses)
                if actual_misses
                else 0.0
            )
            actual_relative_miss = max(
                (
                    abs(
                        actual_predictions[group_name]
                        - float(target)
                    )
                    / max(
                        1000.0,
                        abs(float(target)),
                    )
                    for group_name, target
                    in targets.items()
                ),
                default=0.0,
            )

            reach_text = (
                "The requested target is still far outside what the optimizer could reach with the unlocked settings and balance rules. "
                if actual_relative_miss > 0.15
                else "The optimized result is reasonably close to the requested target. "
            )

            self.sim_optimizer_status_label.config(
                text=(
                    f"Finished after {result['evaluations']:,} setting checks and changed {changed_count} unlocked setting{'s' if changed_count != 1 else ''}. The actual average miss after re-running the normal simulator is about {actual_average_miss:,.0f} per month. "
                    + reach_text
                    + f"{profitable_games} of {balanced_game_count} normal configurable games finish positive for players in the selected history under these settings. "
                    + (
                        f"The single largest game supplies about {largest_share:,.1f}% of the positive improvement. "
                        if largest_share > 0
                        else ""
                    )
                    + "The optimizer deliberately spreads usefulness across Blackjack, Cock Fight, Roulette, Slot Machine and Higher or Lower instead of letting one category become the only viable option. "
                    "Russian Roulette is intentionally excluded from that goal and is never automatically tuned. "
                    "Locked values were left exactly as entered. The search still prioritizes your selected monthly activity-group targets, so it may not be mathematically possible to make every game positive while also hitting every target exactly. "
                    "Blackjack deck count is not auto-tuned because this program does not claim an exact profit change from deck count alone, and Animal Race has no normal global min/max bet setting to tune."
                )
            )

        except Exception as error:
            messagebox.showerror(
                "Target Optimizer Error",
                str(error),
            )

    def get_simulator_settings(
        self,
    ):
        settings = {
            "current_games_per_5m":
                parse_float(
                    self.sim_vars[
                        "current_games_per_5m"
                    ].get()
                ),

            "proposed_games_per_5m":
                parse_float(
                    self.sim_vars[
                        "proposed_games_per_5m"
                    ].get()
                ),

            "current_blackjack_decks":
                parse_int(
                    self.sim_vars[
                        "current_blackjack_decks"
                    ].get()
                ),

            "proposed_blackjack_decks":
                parse_int(
                    self.sim_vars[
                        "proposed_blackjack_decks"
                    ].get()
                ),

            "current_slot_symbols":
                parse_int(
                    self.sim_vars[
                        "current_slot_symbols"
                    ].get()
                ),

            "proposed_slot_symbols":
                parse_int(
                    self.sim_vars[
                        "proposed_slot_symbols"
                    ].get()
                ),

            "current_slot_multiplier":
                parse_float(
                    self.sim_vars[
                        "current_slot_multiplier"
                    ].get()
                ),

            "proposed_slot_multiplier":
                parse_float(
                    self.sim_vars[
                        "proposed_slot_multiplier"
                    ].get()
                ),

            "current_cockfight_start":
                parse_float(
                    self.sim_vars[
                        "current_cockfight_start"
                    ].get()
                ),

            "proposed_cockfight_start":
                parse_float(
                    self.sim_vars[
                        "proposed_cockfight_start"
                    ].get()
                ),

            "current_cockfight_max":
                parse_float(
                    self.sim_vars[
                        "current_cockfight_max"
                    ].get()
                ),

            "proposed_cockfight_max":
                parse_float(
                    self.sim_vars[
                        "proposed_cockfight_max"
                    ].get()
                ),

            "current_chicken_price":
                parse_float(
                    self.sim_vars[
                        "current_chicken_price"
                    ].get()
                ),

            "proposed_chicken_price":
                parse_float(
                    self.sim_vars[
                        "proposed_chicken_price"
                    ].get()
                ),

            "slot_command_symbols": [
                symbol.strip()
                for symbol
                in self.slot_command_symbols_var.get().split(",")
                if symbol.strip()
            ],

            "games": {},
        }

        if settings["current_games_per_5m"] <= 0:
            raise ValueError(
                "Current plays of each game per 5 active minutes must be above 0."
            )

        if settings["proposed_games_per_5m"] < 0:
            raise ValueError(
                "Proposed plays of each game per 5 active minutes cannot be negative."
            )

        if (
            settings["current_slot_symbols"] < 1
            or settings["proposed_slot_symbols"] < 1
        ):
            raise ValueError(
                "Slot machine must have at least 1 symbol."
            )

        if (
            settings["current_blackjack_decks"] < 1
            or settings["proposed_blackjack_decks"] < 1
        ):
            raise ValueError(
                "Blackjack must have at least 1 deck."
            )

        if (
            settings["proposed_cockfight_start"]
            > settings["proposed_cockfight_max"]
        ):
            raise ValueError(
                "Cockfight starting chance cannot exceed max chance."
            )

        for game in BET_LIMIT_GAMES:
            current_min = parse_float(
                self.sim_vars[
                    f"{game}:current_min"
                ].get()
            )

            current_max = parse_float(
                self.sim_vars[
                    f"{game}:current_max"
                ].get()
            )

            proposed_min = parse_float(
                self.sim_vars[
                    f"{game}:proposed_min"
                ].get()
            )

            proposed_max = parse_float(
                self.sim_vars[
                    f"{game}:proposed_max"
                ].get()
            )

            if current_max < current_min:
                raise ValueError(
                    f"{GAME_DISPLAY[game]} current max "
                    "cannot be below current min."
                )

            if proposed_max < proposed_min:
                raise ValueError(
                    f"{GAME_DISPLAY[game]} proposed max "
                    "cannot be below proposed min."
                )

            settings["games"][game] = {
                "current": {
                    "min": current_min,
                    "max": current_max,
                },
                "proposed": {
                    "min": proposed_min,
                    "max": proposed_max,
                },
            }

        return settings

    def update_simulator_explanation(
        self,
        game_rows,
        summary,
    ):
        hours = self.analyzer.get_analysis_hours()
        days = self.analyzer.get_analysis_days()

        current_result = summary["24h_current_model_net"]
        proposed_result = summary["24h_proposed_net"]
        change = summary["24h_change"]
        current_games = summary["24h_current_games"]
        proposed_games = summary["24h_proposed_games"]

        def result_words(value):
            if value > 0:
                return f"players finish about {value:,.0f} richer"
            if value < 0:
                return f"players finish about {abs(value):,.0f} poorer"
            return "players finish about even"

        if change > 0:
            overall_change = (
                f"Your new settings improve the players' result by about {change:,.0f} each day. In simple terms, players keep that much more money each day."
            )
        elif change < 0:
            overall_change = (
                f"Your new settings worsen the players' result by about {abs(change):,.0f} each day. In simple terms, that much more money leaves player balances each day."
            )
        else:
            overall_change = (
                "Your new settings make almost no difference to how much money players finish with each day."
            )

        if math.isclose(
            current_games,
            proposed_games,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            play_total_text = (
                f"Using your fixed plays-per-five-active-minutes input, the included games add up to about {current_games:,.1f} assumed plays in a normal day, and the proposed play rate leaves that about the same."
            )
        else:
            play_total_text = (
                f"Using your fixed plays-per-five-active-minutes input, the included games add up to about {current_games:,.1f} assumed plays in a normal day. The proposed play rate changes that to about {proposed_games:,.1f} assumed plays per day."
            )

        lines = [
            (
                f"The program looked at {hours:,.2f} hours of real history, or about {days:,.2f} days, and turns that into an estimate of one normal 24-hour day. "
                f"{play_total_text}"
            ),
            (
                f"With the current settings, {result_words(current_result)} from these games during a normal day. "
                f"With your new settings, {result_words(proposed_result)}. {overall_change}"
            ),
        ]

        meaningful_rows = [
            row
            for row in game_rows
            if (
                row["24h Current Games"] > 0
                or row["24h Proposed Games"] > 0
            )
        ]

        if meaningful_rows:
            game_explanations = []

            for row in meaningful_rows:
                game = row["Game"]
                current_count = row["24h Current Games"]
                proposed_count = row["24h Proposed Games"]
                current_bet = row["Current Avg Bet"]
                proposed_bet = row["Proposed Avg Bet"]
                current_game_result = row["24h Current Net"]
                proposed_game_result = row["24h Proposed Net"]
                game_change = row["24h Change"]
                win_percent = row.get("Proposed Win %", "")

                if math.isclose(
                    current_count,
                    proposed_count,
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                ):
                    play_text = (
                        f"It is played about {current_count:,.1f} times per day."
                    )
                else:
                    play_text = (
                        f"The simulator assumes about {current_count:,.1f} plays per day at the current fixed rate and about {proposed_count:,.1f} plays per day at the proposed fixed rate."
                    )

                if current_bet > 0 or proposed_bet > 0:
                    if math.isclose(
                        current_bet,
                        proposed_bet,
                        rel_tol=1e-9,
                        abs_tol=1e-9,
                    ):
                        bet_text = (
                            f"The average bet is about {current_bet:,.1f}."
                        )
                    else:
                        bet_text = (
                            f"People currently bet about {current_bet:,.1f} on average. If they keep the same relative betting habits inside your new minimum and maximum, the average becomes about {proposed_bet:,.1f}."
                        )
                else:
                    bet_text = (
                        "There is not enough information here to work out a useful average bet."
                    )

                if current_game_result > 0:
                    current_text = f"players currently gain about {current_game_result:,.0f} per day"
                elif current_game_result < 0:
                    current_text = f"players currently lose about {abs(current_game_result):,.0f} per day"
                else:
                    current_text = "players currently come out about even each day"

                if proposed_game_result > 0:
                    proposed_text = f"players would gain about {proposed_game_result:,.0f} per day"
                elif proposed_game_result < 0:
                    proposed_text = f"players would lose about {abs(proposed_game_result):,.0f} per day"
                else:
                    proposed_text = "players would come out about even each day"

                if game_change > 0:
                    effect_text = (
                        f"That is about {game_change:,.0f} better for players each day."
                    )
                elif game_change < 0:
                    effect_text = (
                        f"That is about {abs(game_change):,.0f} worse for players each day."
                    )
                else:
                    effect_text = (
                        "That changes the players' daily result by almost nothing."
                    )

                win_text = ""
                if win_percent != "" and win_percent is not None:
                    try:
                        win_value = float(win_percent)
                        win_text = (
                            f" Under your new settings, the estimated chance of winning is about {win_value:,.2f}%, which is roughly {win_value:,.2f} wins for every 100 plays over a very large number of plays."
                        )
                    except Exception:
                        pass

                extra_game_text = ""

                if game == "Animal Race":
                    extra_game_text = (
                        " Horse, animal and provision purchases are not multiplied just because the number of races changes. "
                        "If someone bought one horse and then raced it many times, that horse purchase is still only counted at the purchase rate seen in the history."
                    )

                game_explanations.append(
                    f"{game}: {play_text} {bet_text} With the current settings, {current_text}; with your new settings, {proposed_text}. {effect_text}{win_text}{extra_game_text}"
                )

            lines.append(
                "\n\n".join(game_explanations)
            )

            largest_effect = max(
                meaningful_rows,
                key=lambda row: abs(row["24h Change"]),
            )
            biggest_change = largest_effect["24h Change"]

            if biggest_change > 0:
                biggest_text = (
                    f"The single change that helps players the most is {largest_effect['Game']}. It improves player balances by about {biggest_change:,.0f} per day compared with the current setup."
                )
            elif biggest_change < 0:
                biggest_text = (
                    f"The single change that removes the most extra money is {largest_effect['Game']}. It makes players about {abs(biggest_change):,.0f} worse off per day compared with the current setup."
                )
            else:
                biggest_text = (
                    "None of the changed settings makes a noticeable difference to the players' daily result."
                )

            lines.append(
                biggest_text
            )

        self.sim_window_card.set_text(
            "\n\n".join(lines)
        )
    def run_simulator(self):
        if not self.analyzer.transactions:
            return

        try:
            settings = self.get_simulator_settings()

            (
                game_rows,
                user_rows,
                summary,
            ) = self.analyzer.run_simulation(
                settings
            )

            self.last_sim_settings = settings
            self.sim_dirty = False

            self.sim_game_table.set_data(
                game_rows
            )

            self.sim_user_table.set_data(
                [
                    self.analyzer.user_display_row(
                        row
                    )
                    for row
                    in user_rows
                ]
            )

            self.update_simulator_explanation(
                game_rows,
                summary,
            )

            if summary["24h_change"] > 0:
                short_meaning = (
                    f"Players would keep about {summary['24h_change']:,.0f} more each day."
                )
            elif summary["24h_change"] < 0:
                short_meaning = (
                    f"Players would lose about {abs(summary['24h_change']):,.0f} more each day."
                )
            else:
                short_meaning = (
                    "Players would end up about the same each day."
                )

            self.sim_summary_label.config(
                text=(
                    f"Players currently finish {summary['24h_current_model_net']:+,.0f} per day from these games. "
                    f"With the new settings they finish {summary['24h_proposed_net']:+,.0f} per day. "
                    f"{short_meaning}"
                )
            )

            self.update_command_preview(
                settings
            )

            self.refresh_user_dropdowns()

            if (
                self.sim_user_dropdown.get()
                != "No users"
            ):
                self.view_simulator_user()

            self.scroll_area._update_region()

        except Exception as error:
            messagebox.showerror(
                "Simulation Error",
                str(error),
            )

    def open_sim_user_from_row(
        self,
        row,
    ):
        user_value = (
            str(
                row.get(
                    "Username",
                    row.get(
                        "User ID",
                        "",
                    ),
                )
            )
            .strip()
        )

        if not user_value:
            return

        user_id = (
            self.analyzer.resolve_user_label(
                user_value
            )
        )

        self.sim_user_dropdown.set(
            self.analyzer.get_user_label(
                user_id
            )
        )

        self.view_simulator_user()

    def view_simulator_user(self):
        user_value = self.sim_user_dropdown.get()

        if user_value == "No users":
            return

        user_id = (
            self.analyzer.resolve_user_label(
                user_value
            )
        )

        if (
            self.last_sim_settings is None
            or self.sim_dirty
        ):
            messagebox.showinfo(
                "Simulation",
                (
                    "Run Simulation first so the individual user view matches the current simulator settings."
                ),
            )
            return

        game_rows, summary = self.analyzer.run_user_simulation(
            user_id,
            self.last_sim_settings,
        )

        self.sim_user_game_table.set_data(
            game_rows
        )

        current_result = summary["24h_current_model_net"]
        proposed_result = summary["24h_proposed_net"]
        change = summary["24h_change"]
        current_games = summary["24h_current_games"]
        proposed_games = summary["24h_proposed_games"]

        if current_result > 0:
            current_text = f"currently finishes about {current_result:,.0f} richer per day"
        elif current_result < 0:
            current_text = f"currently finishes about {abs(current_result):,.0f} poorer per day"
        else:
            current_text = "currently finishes about even each day"

        if proposed_result > 0:
            proposed_text = f"would finish about {proposed_result:,.0f} richer per day"
        elif proposed_result < 0:
            proposed_text = f"would finish about {abs(proposed_result):,.0f} poorer per day"
        else:
            proposed_text = "would finish about even each day"

        if change > 0:
            effect_text = f"The new settings are about {change:,.0f} better for this user each day."
        elif change < 0:
            effect_text = f"The new settings are about {abs(change):,.0f} worse for this user each day."
        else:
            effect_text = "The new settings make almost no difference for this user."

        active_game_rows = [
            row
            for row in game_rows
            if (
                row["24h Current Games"] > 0
                or row["24h Proposed Games"] > 0
            )
        ]

        details = []
        for row in active_game_rows:
            game = row["Game"]
            current_count = row["24h Current Games"]
            proposed_count = row["24h Proposed Games"]
            current_bet = row["Current Avg Bet"]
            proposed_bet = row["Proposed Avg Bet"]
            current_game_result = row["24h Current Net"]
            proposed_game_result = row["24h Proposed Net"]
            difference = row["24h Change"]

            if current_game_result > 0:
                current_game_words = f"gains about {current_game_result:,.0f} per day"
            elif current_game_result < 0:
                current_game_words = f"loses about {abs(current_game_result):,.0f} per day"
            else:
                current_game_words = "comes out about even"

            if proposed_game_result > 0:
                proposed_game_words = f"gain about {proposed_game_result:,.0f} per day"
            elif proposed_game_result < 0:
                proposed_game_words = f"lose about {abs(proposed_game_result):,.0f} per day"
            else:
                proposed_game_words = "come out about even"

            details.append(
                f"{game}: the fixed-rate assumption gives about {current_count:,.1f} plays per day now and {proposed_count:,.1f} at the proposed rate. "
                f"Their average bet is about {current_bet:,.1f} now and would be about {proposed_bet:,.1f}. "
                f"They currently {current_game_words}; with the new settings they would {proposed_game_words}. "
                f"The difference is {difference:+,.0f} per day."
            )

        detailed_text = " " .join(details)

        self.sim_user_summary_label.config(
            text=(
                f"User {user_id}'s history is used only to estimate how many hours per day they are active. The simulator does not copy their historical game counts or game choices. "
                f"At the fixed plays-per-five-active-minutes rate, that gives about {current_games:,.1f} total assumed game plays per day now and {proposed_games:,.1f} at the proposed rate. They {current_text}; with the new settings they {proposed_text}. {effect_text} "
                f"{detailed_text}"
            )
        )
    def update_command_preview(
        self,
        settings,
    ):
        commands = []
        warnings = []

        def changed(a, b):
            try:
                return not math.isclose(
                    float(a),
                    float(b),
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                )
            except Exception:
                return a != b

        current_usage = settings[
            "current_games_per_5m"
        ]

        proposed_usage = settings[
            "proposed_games_per_5m"
        ]

        if changed(
            current_usage,
            proposed_usage,
        ):
            if float(
                proposed_usage
            ).is_integer():
                commands.append(
                    "!set-game-cooldown "
                    f"{int(proposed_usage)} 5m"
                )
            else:
                warnings.append(
                    "Game cooldown usages must be a whole number "
                    "before a copy-paste command can be generated."
                )

        for game in BET_LIMIT_GAMES:
            command_name = GAME_COMMAND_NAMES[
                game
            ]

            current = settings[
                "games"
            ][game]["current"]

            proposed = settings[
                "games"
            ][game]["proposed"]

            if changed(
                current["min"],
                proposed["min"],
            ):
                commands.append(
                    "!set-bet-limit "
                    f"{command_name} min "
                    f"{proposed['min']:g}"
                )

            if changed(
                current["max"],
                proposed["max"],
            ):
                commands.append(
                    "!set-bet-limit "
                    f"{command_name} max "
                    f"{proposed['max']:g}"
                )

        if changed(
            settings[
                "current_blackjack_decks"
            ],
            settings[
                "proposed_blackjack_decks"
            ],
        ):
            commands.append(
                "!set-blackjack-decks "
                f"{settings['proposed_blackjack_decks']}"
            )

        if changed(
            settings[
                "current_cockfight_start"
            ],
            settings[
                "proposed_cockfight_start"
            ],
        ):
            commands.append(
                "!cock-fight-win-chance start "
                f"{settings['proposed_cockfight_start']:g}%"
            )

        if changed(
            settings[
                "current_cockfight_max"
            ],
            settings[
                "proposed_cockfight_max"
            ],
        ):
            commands.append(
                "!cock-fight-win-chance max "
                f"{settings['proposed_cockfight_max']:g}%"
            )

        if changed(
            settings[
                "current_chicken_price"
            ],
            settings[
                "proposed_chicken_price"
            ],
        ):
            commands.append(
                "!edit-item price Chicken "
                f"{settings['proposed_chicken_price']:g}"
            )

        slot_changed = (
            changed(
                settings[
                    "current_slot_symbols"
                ],
                settings[
                    "proposed_slot_symbols"
                ],
            )
            or changed(
                settings[
                    "current_slot_multiplier"
                ],
                settings[
                    "proposed_slot_multiplier"
                ],
            )
        )

        if slot_changed:
            symbol_count = int(
                settings[
                    "proposed_slot_symbols"
                ]
            )

            symbols = settings[
                "slot_command_symbols"
            ]

            if len(symbols) == symbol_count:
                commands.append(
                    "!slot-machine-symbol remove all"
                )

                for symbol in symbols:
                    commands.append(
                        "!slot-machine-symbol add "
                        f"{symbol} "
                        f"{settings['proposed_slot_multiplier']:g}"
                    )

            else:
                warnings.append(
                    "Slot settings changed. Enter exactly "
                    f"{symbol_count} slot symbols in the "
                    "'Slot symbols for commands' field."
                )

        self.sim_command_text.delete(
            "1.0",
            tk.END,
        )

        if commands:
            self.sim_command_text.insert(
                "1.0",
                "\n".join(
                    commands
                ),
            )

        if warnings:
            status_text = " ".join(
                warnings
            )

        elif commands:
            status_text = (
                f"{len(commands)} copy-paste command"
                f"{'s' if len(commands) != 1 else ''} ready. "
                "Only changed settings are included."
            )

        else:
            status_text = (
                "No simulator settings have changed."
            )

        self.sim_command_status_label.config(
            text=status_text
        )

    def copy_label_for_discord(
        self,
        label,
        title=None,
        button=None,
        button_text="Copy",
    ):
        if label is None:
            return

        body = str(
            label.cget(
                "text"
            )
        ).strip()

        if not body:
            return

        if title:
            clipboard_text = (
                f"**{title}**\n"
                f"{body}"
            )
        else:
            clipboard_text = body

        clipboard_text = (
            discord_trim_message(
                clipboard_text
            )
        )

        self.root.clipboard_clear()
        self.root.clipboard_append(
            clipboard_text
        )
        self.root.update()

        if button is not None:
            button.set_text(
                "Copied"
            )
            self.root.after(
                1200,
                lambda:
                    button.set_text(
                        button_text
                    ),
            )

    def copy_simulator_commands(
        self,
    ):
        text = (
            self.sim_command_text
            .get(
                "1.0",
                tk.END,
            )
            .strip()
        )

        if not text:
            return

        self.root.clipboard_clear()

        self.root.clipboard_append(
            text
        )

        self.root.update()

    def reset_simulator(self):
        self.sim_vars[
            "current_games_per_5m"
        ].set(
            str(
                DEFAULT_CURRENT_GAMES_PER_5M
            )
        )

        self.sim_vars[
            "proposed_games_per_5m"
        ].set(
            str(
                DEFAULT_CURRENT_GAMES_PER_5M
            )
        )

        for game in BET_LIMIT_GAMES:
            current_min = DEFAULT_GAME_LIMITS[
                game
            ]["min"]

            current_max = DEFAULT_GAME_LIMITS[
                game
            ]["max"]

            self.sim_vars[
                f"{game}:current_min"
            ].set(
                str(
                    current_min
                )
            )

            self.sim_vars[
                f"{game}:current_max"
            ].set(
                str(
                    current_max
                )
            )

            self.sim_vars[
                f"{game}:proposed_min"
            ].set(
                str(
                    current_min
                )
            )

            self.sim_vars[
                f"{game}:proposed_max"
            ].set(
                str(
                    current_max
                )
            )

        self.sim_vars[
            "current_blackjack_decks"
        ].set(
            str(
                DEFAULT_BLACKJACK_DECKS
            )
        )

        self.sim_vars[
            "proposed_blackjack_decks"
        ].set(
            str(
                DEFAULT_BLACKJACK_DECKS
            )
        )

        self.sim_vars[
            "current_slot_symbols"
        ].set(
            str(
                DEFAULT_SLOT_SYMBOLS
            )
        )

        self.sim_vars[
            "proposed_slot_symbols"
        ].set(
            str(
                DEFAULT_SLOT_SYMBOLS
            )
        )

        self.sim_vars[
            "current_slot_multiplier"
        ].set(
            str(
                DEFAULT_SLOT_MULTIPLIER
            )
        )

        self.sim_vars[
            "proposed_slot_multiplier"
        ].set(
            str(
                DEFAULT_SLOT_MULTIPLIER
            )
        )

        self.sim_vars[
            "current_cockfight_start"
        ].set(
            str(
                DEFAULT_COCKFIGHT_START
            )
        )

        self.sim_vars[
            "proposed_cockfight_start"
        ].set(
            str(
                DEFAULT_COCKFIGHT_START
            )
        )

        self.sim_vars[
            "current_cockfight_max"
        ].set(
            str(
                DEFAULT_COCKFIGHT_MAX
            )
        )

        self.sim_vars[
            "proposed_cockfight_max"
        ].set(
            str(
                DEFAULT_COCKFIGHT_MAX
            )
        )

        chicken_price = (
            self.analyzer.infer_chicken_price()
            if self.analyzer.transactions
            else DEFAULT_CHICKEN_PRICE
        )

        self.sim_vars[
            "current_chicken_price"
        ].set(
            str(
                round(
                    chicken_price,
                    2,
                )
            )
        )

        self.sim_vars[
            "proposed_chicken_price"
        ].set(
            str(
                round(
                    chicken_price,
                    2,
                )
            )
        )

        self.slot_command_symbols_var.set("")

        self.sim_game_table.set_data(
            []
        )

        self.sim_user_table.set_data(
            []
        )

        self.sim_user_game_table.set_data(
            []
        )

        self.sim_command_text.delete(
            "1.0",
            tk.END,
        )

        self.sim_summary_label.config(
            text=(
                "Simulation has not "
                "been run yet."
            )
        )

        self.sim_user_summary_label.config(
            text=(
                "Run the simulation, "
                "then select a user."
            )
        )

        self.sim_command_status_label.config(
            text=(
                "Run the simulation to generate commands. "
                "Only settings that changed will appear below."
            )
        )

        self.last_sim_settings = None
        self.sim_dirty = True

    def export_current_page(self):
        export_map = {
            "overview":
                self.summary_table,

            "users":
                self.users_table,

            "user_breakdown":
                self.user_sources_table,

            "sources":
                self.sources_table,

            "hourly":
                self.hourly_table,

            "daily":
                self.daily_table,

            "user_hours":
                self.user_hours_table,

            "transactions":
                self.transactions_table,

            "activity_groups":
                self.activity_group_table,

            "simulator":
                self.sim_user_table,
        }

        table = (
            export_map.get(
                self.current_page
            )
        )

        if table:
            table.export_csv()


if __name__ == "__main__":
    root = tk.Tk()

    icon_path = BASE_DIR / "icon.ico"

    if icon_path.exists():
        try:
            root.iconbitmap(str(icon_path))
        except tk.TclError:
            pass

    root.mainloop()
