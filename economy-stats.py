import sqlite3
import json
import re
import csv
import math
import statistics
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "economy-stats.dht"
TABLE_NAME = "message_embeds"

THEMES = {
    "dark": {
        "APP_BG": "#050505",
        "SIDEBAR_BG": "#000000",
        "SIDEBAR_HOVER": "#18181B",
        "PRIMARY": "#7C3AED",
        "PRIMARY_HOVER": "#8B5CF6",
        "TEXT": "#F8FAFC",
        "MUTED": "#A1A1AA",
        "CARD": "#0D0D0D",
        "BORDER": "#27272A",
        "SOFT_BLUE": "#211A36",
        "SOFT_GREEN": "#052E16",
        "SOFT_AMBER": "#3A2600",
        "GREEN": "#4ADE80",
        "AMBER": "#FBBF24",
        "INFO_BG": "#0A0A0A",
        "SECONDARY_BG": "#18181B",
        "SECONDARY_HOVER": "#27272A",
        "TABLE_HEADER_BG": "#18181B",
        "TABLE_ALT": "#121212",
        "DEEP_BG": "#090909",
        "SIDEBAR_TEXT": "#FFFFFF",
        "ACCENT_TEXT": "#A78BFA",
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

    def connect(self):
        db_path = Path(self.db_path)

        if not db_path.exists():
            raise FileNotFoundError(
                "Database not found.\n\n"
                f"Current database location:\n{db_path}\n\n"
                "Click 'Choose Database' at the top of the program "
                "to select a .dht or SQLite database manually."
            )

        return sqlite3.connect(
            db_path
        )

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

    def get_user_transactions(
        self,
        user_id,
    ):
        return [
            tx
            for tx
            in self.transactions
            if tx["user_id"]
            == user_id
        ]

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
            ("User ID", user_id),
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
        rows = []

        for tx in self.transactions:
            if (
                user_id is not None
                and tx["user_id"]
                != user_id
            ):
                continue

            if (
                game_from_reason(
                    tx[
                        "original_reason"
                    ]
                )
                == game
            ):
                rows.append(
                    tx
                )

        return rows

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

        bets = (
            self.infer_game_bets(
                game,
                txs,
                settings[
                    "current_slot_multiplier"
                ],
            )
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

        inferred_rounds = len(
            bets
        )

        fallback_rounds = sum(
            1
            for tx in txs
            if not tx[
                "is_chicken_purchase"
            ]
        )

        observed_rounds = (
            inferred_rounds
            if inferred_rounds
            else fallback_rounds
        )

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
            purchase_txs = [
                tx
                for tx in txs
                if is_animal_race_purchase(
                    tx["original_reason"]
                )
            ]

            race_txs = [
                tx
                for tx in txs
                if not is_animal_race_purchase(
                    tx["original_reason"]
                )
            ]

            purchase_net = sum(
                tx["total"]
                for tx in purchase_txs
            )

            purchase_earned = sum(
                tx["total"]
                for tx in purchase_txs
                if tx["total"] > 0
            )

            purchase_lost = -sum(
                tx["total"]
                for tx in purchase_txs
                if tx["total"] < 0
            )

            race_net = sum(
                tx["total"]
                for tx in race_txs
            )

            race_earned = sum(
                tx["total"]
                for tx in race_txs
                if tx["total"] > 0
            )

            race_lost = -sum(
                tx["total"]
                for tx in race_txs
                if tx["total"] < 0
            )

            current_avg_bet = (
                sum(bets) / len(bets)
                if bets
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

        mapped_bets = [
            scale_bet(
                bet,
                current["min"],
                current["max"],
                proposed["min"],
                proposed["max"],
            )
            for bet in bets
        ]

        old_stake = sum(
            bets
        )

        new_stake_base = sum(
            mapped_bets
        )

        current_avg_bet = (
            old_stake
            / len(bets)
        )

        proposed_avg_bet = (
            new_stake_base
            / len(
                mapped_bets
            )
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

    def simulation_scope(
        self,
        settings,
        user_id=None,
    ):
        factor24 = self.get_24h_factor()
        game_rows = []
        totals = defaultdict(float)

        for game in GAME_ORDER:
            txs = self.get_game_transactions(
                game,
                user_id=user_id,
            )

            result = self.simulate_game(
                game,
                txs,
                settings,
            )

            totals["observed_net"] += result["observed_net"]
            totals["current_model_net"] += result["current_model_net"]
            totals["current_model_earned"] += result["current_model_earned"]
            totals["current_model_lost"] += result["current_model_lost"]
            totals["proposed_net"] += result["proposed_net"]
            totals["proposed_earned"] += result["proposed_earned"]
            totals["proposed_lost"] += result["proposed_lost"]
            totals["observed_rounds"] += result["observed_rounds"]
            totals["proposed_rounds"] += result["proposed_rounds"]

            row = {
                "Game": GAME_DISPLAY[game],
                "24h Current Games": (
                    result["observed_rounds"]
                    * factor24
                ),
                "24h Proposed Games": (
                    result["proposed_rounds"]
                    * factor24
                ),
                "Current Avg Bet": result["current_avg_bet"],
                "Proposed Avg Bet": result["proposed_avg_bet"],
                "24h Current Net": (
                    result["current_model_net"]
                    * factor24
                ),
                "24h Proposed Net": (
                    result["proposed_net"]
                    * factor24
                ),
                "24h Change": (
                    (
                        result["proposed_net"]
                        - result["current_model_net"]
                    )
                    * factor24
                ),
            }

            if "proposed_probability" in result:
                row["Proposed Win %"] = (
                    result["proposed_probability"]
                    * 100
                )
            else:
                row["Proposed Win %"] = ""

            game_rows.append(row)

        summary = {
            "24h_observed_net": (
                totals["observed_net"]
                * factor24
            ),
            "24h_current_model_net": (
                totals["current_model_net"]
                * factor24
            ),
            "24h_current_model_earned": (
                totals["current_model_earned"]
                * factor24
            ),
            "24h_current_model_lost": (
                totals["current_model_lost"]
                * factor24
            ),
            "24h_proposed_net": (
                totals["proposed_net"]
                * factor24
            ),
            "24h_proposed_earned": (
                totals["proposed_earned"]
                * factor24
            ),
            "24h_proposed_lost": (
                totals["proposed_lost"]
                * factor24
            ),
            "24h_change": (
                (
                    totals["proposed_net"]
                    - totals["current_model_net"]
                )
                * factor24
            ),
            "24h_current_games": (
                totals["observed_rounds"]
                * factor24
            ),
            "24h_proposed_games": (
                totals["proposed_rounds"]
                * factor24
            ),
            "normalization_factor": factor24,
        }

        return (
            game_rows,
            summary,
        )

    def run_simulation(
        self,
        settings,
    ):
        game_rows, summary = self.simulation_scope(
            settings
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
            )

            user_rows.append(
                {
                    "User ID": user_id,
                    "24h Current Net": user_summary[
                        "24h_current_model_net"
                    ],
                    "24h Proposed Net": user_summary[
                        "24h_proposed_net"
                    ],
                    "24h Change": user_summary[
                        "24h_change"
                    ],
                    "24h Current Games": user_summary[
                        "24h_current_games"
                    ],
                    "24h Proposed Games": user_summary[
                        "24h_proposed_games"
                    ],
                }
            )

        user_rows.sort(
            key=lambda row: row[
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
        return (
            self.simulation_scope(
                settings,
                user_id=user_id,
            )
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
        font=(
            "Segoe UI Semibold",
            9,
        ),
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

        self.title_label = tk.Label(
            self.inner,
            text=title,
            bg=INFO_BG,
            fg=TEXT,
            justify=tk.LEFT,
            anchor="w",
            font=(
                "Segoe UI Semibold",
                10,
            ),
        )

        self.title_label.pack(
            fill=tk.X,
            anchor="w",
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
                9,
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
            font=(
                "Segoe UI Semibold",
                9,
            ),
        )

        self.create_text(
            18,
            46,
            anchor="nw",
            text=self.value,
            fill=TEXT,
            font=(
                "Segoe UI Semibold",
                20,
            ),
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
            font=(
                "Segoe UI Semibold",
                8,
            ),
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
            font=(
                "Segoe UI Semibold",
                9,
            ),
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
            font=(
                "Segoe UI Semibold",
                9,
            ),
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
            font=(
                "Segoe UI Semibold",
                9,
            ),
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
            self.apply_filter,
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

        self.count_label = (
            tk.Label(
                toolbar,
                text="",
                bg=CARD,
                fg=MUTED,
                font=(
                    "Segoe UI",
                    9,
                ),
            )
        )

        self.count_label.pack(
            side=tk.RIGHT
        )

        holder = tk.Frame(
            self,
            bg=CARD,
        )

        holder.pack(
            fill=tk.BOTH,
            expand=True,
        )

        holder.rowconfigure(
            0,
            weight=1,
        )

        holder.columnconfigure(
            0,
            weight=1,
        )

        self.tree = ttk.Treeview(
            holder,
            show="headings",
            selectmode="extended",
            height=height,
        )

        y_scroll = ttk.Scrollbar(
            holder,
            orient=tk.VERTICAL,
            command=self.tree.yview,
        )

        x_scroll = ttk.Scrollbar(
            holder,
            orient=tk.HORIZONTAL,
            command=self.tree.xview,
        )

        self.tree.configure(
            yscrollcommand=(
                y_scroll.set
            ),
            xscrollcommand=(
                x_scroll.set
            ),
        )

        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        y_scroll.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        x_scroll.grid(
            row=1,
            column=0,
            sticky="ew",
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
            "User ID",
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

            width = max(
                110,
                min(
                    230,
                    len(column)
                    * 10
                    + 30,
                ),
            )

            if column in {
                "Reason",
                "Original Reason",
                "Top Income Source",
                "Statistic",
            }:
                width = 240

            elif column == "User ID":
                width = 170

            elif column in {
                "Timestamp",
                "First Seen",
                "Last Seen",
                "Hour",
            }:
                width = 165

            elif column == "Value":
                width = 300

            elif column == "Game":
                width = 155

            elif (
                "24h" in column
                or "30d" in column
            ):
                width = 155

            elif column in {
                "Est. Active Min",
                "Est. Active Hrs",
                "Activity %",
                "Tx / Active Hr",
            }:
                width = 135

            self.tree.column(
                column,
                width=width,
                minwidth=75,
                stretch=False,
                anchor=(
                    tk.W
                    if column
                    in text_columns
                    else tk.E
                ),
            )

        self.refresh()

    def refresh(self):
        self.tree.delete(
            *self.tree.get_children()
        )

        for (
            index,
            row,
        ) in enumerate(
            self.filtered_data
        ):
            values = []

            for column in (
                self.columns
            ):
                value = row.get(
                    column,
                    "",
                )

                if isinstance(
                    value,
                    float,
                ):
                    value = (
                        format_number(
                            value
                        )
                    )

                elif isinstance(
                    value,
                    int,
                ):
                    value = (
                        f"{value:,}"
                    )

                values.append(
                    str(value)
                )

            self.tree.insert(
                "",
                tk.END,
                values=values,
                tags=(
                    "even"
                    if index % 2 == 0
                    else "odd",
                ),
            )

        self.count_label.config(
            text=(
                f"{len(self.filtered_data):,} rows"
            )
        )

    def apply_filter(
        self,
        event=None,
    ):
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

        self.last_sim_settings = (
            None
        )

        self.sim_dirty = True

        self.setup_style()
        self.build_layout()

        self.root.after(
            100,
            self.load_database,
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
            rowheight=30,
            borderwidth=0,
            relief=tk.FLAT,
            font=(
                "Segoe UI",
                9,
            ),
        )

        style.configure(
            "Treeview.Heading",
            background=TABLE_HEADER_BG,
            foreground=TEXT,
            borderwidth=0,
            relief=tk.FLAT,
            padding=(8, 8),
            font=(
                "Segoe UI Semibold",
                9,
            ),
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
            font=(
                "Segoe UI Semibold",
                17,
            ),
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
            font=(
                "Segoe UI Semibold",
                10,
            ),
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
            font=(
                "Segoe UI Semibold",
                21,
            ),
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
            font=(
                "Segoe UI Semibold",
                12,
            ),
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
            font=(
                "Segoe UI Semibold",
                8,
            ),
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
            font=(
                "Segoe UI Semibold",
                8,
            ),
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
            font=(
                "Segoe UI Semibold",
                16,
            ),
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
                9,
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
                "Quick comparison of profit, projected profit "
                "and estimated economy activity."
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
            font=(
                "Segoe UI Semibold",
                8,
            ),
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
            font=(
                "Segoe UI Semibold",
                11,
            ),
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
            font=(
                "Segoe UI Semibold",
                11,
            ),
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

    def build_simulator_page(self):
        page = self.new_page()

        self.make_page_header(
            page,
            "Game Simulator",
            (
                "Change game settings and see what they would mean for players during a typical day"
            ),
        )

        self.sim_window_card = self.make_help_card(
            page,
            (
                "Run the simulation and this box will explain the actual results in plain language. "
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
            text="Global game activity",
            bg=CARD,
            fg=TEXT,
            font=(
                "Segoe UI Semibold",
                11,
            ),
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
            text="Current games / 5 min",
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
            text="Proposed games / 5 min",
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
            font=(
                "Segoe UI Semibold",
                11,
            ),
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
                font=(
                    "Segoe UI Semibold",
                    8,
                ),
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
                font=(
                    "Segoe UI Semibold",
                    9,
                ),
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
                    side=tk.LEFT
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
                    side=tk.LEFT
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
            font=(
                "Segoe UI Semibold",
                11,
            ),
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
            font=(
                "Segoe UI Semibold",
                11,
            ),
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
                    9,
                ),
            )
        )

        self.sim_summary_label.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
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
            font=(
                "Segoe UI Semibold",
                11,
            ),
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
            font=(
                "Segoe UI Semibold",
                11,
            ),
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
            font=(
                "Segoe UI Semibold",
                11,
            ),
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
            font=(
                "Segoe UI Semibold",
                11,
            ),
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
            self.analyzer.user_stats
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
            self.analyzer.user_hour_stats
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

                    "User ID":
                        tx["user_id"],

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
                f"The strongest 30-day estimate is user {top_projected['User ID']}, who would gain about {projected:,.0f} if the same pace continued."
            )
        elif projected < 0:
            projected_text = (
                f"Even the strongest 30-day estimate is negative: user {top_projected['User ID']} would lose about {abs(projected):,.0f} if the same pace continued."
            )
        else:
            projected_text = (
                f"The strongest 30-day estimate is around zero for user {top_projected['User ID']}."
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

                f"A useful example of a fairly typical user is {typical['User ID']}, because their result is close to the middle of the group. "
                f"They received {typical['Gross Earned']:,.0f}, spent or lost {typical['Gross Lost']:,.0f}, and {typical_result}. "
                f"If that exact pace continued, their 30-day result would be {typical_month_text}. "
                f"They had {typical['Transactions']:,.0f} balance changes, used the economy for about {typical['Est. Active Hrs']:,.2f} hours, "
                f"were active for about {typical['Activity %']:,.2f}% of the whole selected period, used it on {typical['Active Days']:,.0f} different days, "
                f"and those uses were split into about {typical['Sessions']:,.0f} separate periods of activity. "
                f"Their most profitable source after both gains and losses were counted was '{typical['Top Income Source']}', and their most recent economy use in this selection was {typical['Last Seen']}.\n\n"

                f"The most active person was {most_active['User ID']} with about {most_active['Est. Active Hrs']:,.2f} hours of economy use. "
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
                "When you press Run Simulation, the program uses how often people actually played during that time and turns it into "
                "an easy 'per day' estimate.\n\n"
                "The explanation here will then tell you, in normal language, roughly how many times each game is played in a day, "
                "what people usually bet, how much players currently gain or lose from that game, and how your new settings would change that."
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
                    f"User {row['User ID']} at {row['Hour']} received {row['Gross Earned']:,.0f}, spent or lost {row['Gross Lost']:,.0f}, "
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
                    f"At {to_local_string(tx['timestamp'])}, user {tx['user_id']} had {abs(tx['total']):,.0f} {direction}. "
                    f"The cash part changed by {tx['cash']:+,.0f} and the bank part changed by {tx['bank']:+,.0f}. "
                    f"The program groups the event under '{tx['reason']}'. The original stored reason was '{tx['original_reason']}'."
                )

            transaction_card.set_text(
                (
                    f"This page contains all {len(txs):,} individual balance changes used by the other pages. "
                    "The time tells you when the change happened, User ID tells you who it happened to, Cash and Bank show which part of their balance moved, "
                    "and Total is the combined amount. A positive total means they received money; a negative total means money left their balance.\n\n"
                    f"Largest single addition: {transaction_sentence(largest_gain)}\n\n"
                    f"Largest single removal: {transaction_sentence(largest_loss)}"
                )
            )
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
            str(
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
        user_id = (
            str(
                row.get(
                    "User ID",
                    "",
                )
            )
            .replace(
                ",",
                "",
            )
            .strip()
        )

        if not user_id:
            return

        self.user_dropdown.set(
            user_id
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
        user_id = self.user_dropdown.get()

        if user_id == "No users":
            return

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
                "Current games per 5 min must be above 0."
            )

        if settings["proposed_games_per_5m"] < 0:
            raise ValueError(
                "Proposed games per 5 min cannot be negative."
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
                f"People currently play the included games about {current_games:,.1f} times in a normal day, and your new activity setting leaves that about the same."
            )
        else:
            play_total_text = (
                f"People currently play the included games about {current_games:,.1f} times in a normal day. Your new activity setting changes that to about {proposed_games:,.1f} plays per day."
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
                        f"It is currently played about {current_count:,.1f} times per day and would be played about {proposed_count:,.1f} times per day with your new activity setting."
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
                user_rows
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
        user_id = (
            str(
                row.get(
                    "User ID",
                    "",
                )
            )
            .replace(
                ",",
                "",
            )
            .strip()
        )

        if not user_id:
            return

        self.sim_user_dropdown.set(
            user_id
        )

        self.view_simulator_user()

    def view_simulator_user(self):
        user_id = self.sim_user_dropdown.get()

        if user_id == "No users":
            return

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
                f"{game}: about {current_count:,.1f} plays per day now and {proposed_count:,.1f} with the new activity setting. "
                f"Their average bet is about {current_bet:,.1f} now and would be about {proposed_bet:,.1f}. "
                f"They currently {current_game_words}; with the new settings they would {proposed_game_words}. "
                f"The difference is {difference:+,.0f} per day."
            )

        detailed_text = " " .join(details)

        self.sim_user_summary_label.config(
            text=(
                f"Based on how user {user_id} actually played in the selected history, they currently play about {current_games:,.1f} of these games in a normal day. "
                f"With your new activity setting, that becomes about {proposed_games:,.1f} plays per day. They {current_text}; with the new settings they {proposed_text}. {effect_text} "
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


def main():
    root = tk.Tk()

    EconomyViewer(
        root
    )

    root.mainloop()


if __name__ == "__main__":
    main()
