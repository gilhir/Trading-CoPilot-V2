"""
database.py — גישה ל-SQLite בלבד.
כל פונקציה: שאילתה אחת, מחזירה dict או list[dict].
אין pandas, אין Streamlit, אין rich.
"""
import sqlite3
import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "trading_portfolio.db"


# ─────────────────────────────────────────────
# חיבור + אתחול
# ─────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # גישה לעמודות לפי שם
    return conn


def init_db() -> None:
    """יצירת טבלאות אם אינן קיימות. רץ פעם אחת בהפעלה."""
    with _connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS open_positions (
            symbol              TEXT PRIMARY KEY,
            asset_name          TEXT NOT NULL DEFAULT '',
            quantity            REAL NOT NULL,
            avg_cost_price      REAL NOT NULL,
            current_price       REAL NOT NULL,
            direction           TEXT NOT NULL DEFAULT 'LONG',
            trade_type          TEXT NOT NULL DEFAULT 'LONG_TERM',
            entry_thesis        TEXT NOT NULL DEFAULT '',
            initial_stop_loss   REAL NOT NULL DEFAULT 0.0,
            dynamic_stop_loss   REAL NOT NULL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS watchlist_setups (
            symbol                   TEXT PRIMARY KEY,
            required_setup_conditions TEXT NOT NULL DEFAULT '',
            trigger_price_zone       REAL NOT NULL DEFAULT 0.0,
            current_status           TEXT NOT NULL DEFAULT 'Pending Alert',
            stop_loss                REAL NOT NULL DEFAULT 0.0,
            thesis_summary           TEXT NOT NULL DEFAULT '',
            activation_trigger_price REAL,
            activation_trigger_time  TEXT,
            dismissal_notes          TEXT,
            trade_type               TEXT NOT NULL DEFAULT 'LONG_TERM'
        );

        CREATE TABLE IF NOT EXISTS trade_history_ledger (
            order_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol            TEXT NOT NULL,
            action            TEXT NOT NULL,
            execution_price   REAL NOT NULL,
            executed_quantity REAL NOT NULL,
            exit_reason       TEXT NOT NULL DEFAULT '',
            post_mortem_notes TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS closed_trades (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol              TEXT NOT NULL,
            buy_price           REAL NOT NULL,
            sell_price          REAL NOT NULL,
            close_timestamp     TEXT NOT NULL,
            original_rationale  TEXT,
            post_mortem_notes   TEXT
        );

        CREATE TABLE IF NOT EXISTS portfolio_advice (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            advice_text TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS file_metadata (
            file_name        TEXT,
            export_timestamp TEXT PRIMARY KEY
        );
        """)


# ─────────────────────────────────────────────
# open_positions — קריאה
# ─────────────────────────────────────────────

def get_positions() -> list[dict]:
    """כל הפוזיציות הפתוחות + P&L מחושב."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT symbol, asset_name, quantity, avg_cost_price, current_price,
                   direction, trade_type, entry_thesis, initial_stop_loss, dynamic_stop_loss
            FROM open_positions
            ORDER BY (quantity * current_price) DESC
        """).fetchall()

    result = []
    for r in rows:
        qty   = r["quantity"]
        cost  = r["avg_cost_price"]
        curr  = r["current_price"]
        is_long = r["direction"] == "LONG"

        pnl_amt = (curr - cost) * qty if is_long else (cost - curr) * qty
        pnl_pct = (pnl_amt / (cost * qty) * 100) if cost > 0 else 0.0

        result.append({
            **dict(r),
            "pnl_amount":        round(pnl_amt, 2),
            "pnl_percent":       round(pnl_pct, 2),
            "holding_value":     round(curr * qty, 2),
            "holding_cost":      round(cost * qty, 2),
            "stop_distance_pct": round((curr - r["dynamic_stop_loss"]) / curr * 100, 2)
                                  if r["dynamic_stop_loss"] and curr else None,
        })
    return result


def get_position(symbol: str) -> Optional[dict]:
    """פוזיציה בודדת לפי סימול."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM open_positions WHERE symbol = ?", (symbol.upper(),)
        ).fetchone()
    return dict(row) if row else None


def get_positions_summary() -> dict:
    """4 KPIs לכותרת ה-dashboard."""
    positions = get_positions()
    if not positions:
        return {"book_value": 0, "pnl_amount": 0, "pnl_percent": 0,
                "position_count": 0}

    book   = sum(p["holding_value"] for p in positions)
    cost   = sum(p["holding_cost"]  for p in positions)
    pnl    = sum(p["pnl_amount"]    for p in positions)
    pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0

    return {
        "book_value":      round(book, 2),
        "pnl_amount":      round(pnl, 2),
        "pnl_percent":     round(pnl_pct, 2),
        "position_count":  len(positions),
    }


# ─────────────────────────────────────────────
# open_positions — כתיבה
# ─────────────────────────────────────────────

def upsert_position(
    symbol: str, asset_name: str, quantity: float,
    avg_cost_price: float, current_price: float,
    direction: str = "LONG", trade_type: str = "LONG_TERM",
    entry_thesis: str = "Bank Portfolio Ingestion",
    initial_stop_loss: float = 0.0,
) -> str:
    """
    הוספה או עדכון פוזיציה.
    אם קיימת — מעדכן כמות/עלות/מחיר/סטופ ראשוני בלבד.
    אם חדשה — מוסיף עם כל השדות.
    מחזיר תיאור הפעולה.
    """
    symbol = symbol.upper()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT initial_stop_loss, dynamic_stop_loss FROM open_positions WHERE symbol = ?",
            (symbol,)
        ).fetchone()

        if existing:
            # שומרים סטופ דינמי קיים; מעדכנים סטופ ראשוני רק אם הגיע ערך ממשי
            new_initial = initial_stop_loss if initial_stop_loss > 0 else existing["initial_stop_loss"]
            conn.execute("""
                UPDATE open_positions
                SET asset_name=?, quantity=?, avg_cost_price=?, current_price=?,
                    direction=?, trade_type=?, initial_stop_loss=?
                WHERE symbol=?
            """, (asset_name, quantity, avg_cost_price, current_price,
                  direction, trade_type, new_initial, symbol))
            action = "עדכון פוזיציה"
        else:
            # פוזיציה חדשה — סטופ דינמי = סטופ ראשוני
            conn.execute("""
                INSERT INTO open_positions
                    (symbol, asset_name, quantity, avg_cost_price, current_price,
                     direction, trade_type, entry_thesis, initial_stop_loss, dynamic_stop_loss)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (symbol, asset_name, quantity, avg_cost_price, current_price,
                  direction, trade_type, entry_thesis, initial_stop_loss, initial_stop_loss))
            action = "הוספת פוזיציה"

    return f"{action}: {symbol} | כמות={quantity} | עלות={avg_cost_price} | מחיר={current_price}"


def update_current_price(symbol: str, price: float) -> None:
    """עדכון מחיר נוכחי בלבד (מ-yfinance)."""
    with _connect() as conn:
        conn.execute(
            "UPDATE open_positions SET current_price=? WHERE symbol=?",
            (round(price, 4), symbol.upper())
        )


def update_dynamic_stop(symbol: str, new_stop: float) -> tuple[bool, str]:
    """
    עדכון סטופ דינמי עם Ratchet Guardrail.
    מחזיר (הצלחה, הודעה).
    """
    symbol = symbol.upper()
    with _connect() as conn:
        row = conn.execute(
            "SELECT direction, dynamic_stop_loss FROM open_positions WHERE symbol=?",
            (symbol,)
        ).fetchone()

        if not row:
            return False, f"לא נמצאה פוזיציה: {symbol}"

        direction     = row["direction"]
        current_stop  = row["dynamic_stop_loss"]

        # Ratchet Guardrail — סטופ זז רק לכיוון שמקטין סיכון
        if direction == "LONG" and new_stop <= current_stop:
            return False, (
                f"חסום: לא ניתן להוריד סטופ בעסקת LONG. "
                f"נוכחי={current_stop}, מוצע={new_stop}"
            )
        if direction == "SHORT" and new_stop >= current_stop:
            return False, (
                f"חסום: לא ניתן להעלות סטופ בעסקת SHORT. "
                f"נוכחי={current_stop}, מוצע={new_stop}"
            )

        conn.execute(
            "UPDATE open_positions SET dynamic_stop_loss=? WHERE symbol=?",
            (round(new_stop, 4), symbol)
        )
    return True, f"סטופ דינמי עודכן: {symbol} | {current_stop} → {new_stop}"


def close_position(
    symbol: str, execution_price: float,
    exit_reason: str, post_mortem_notes: str = ""
) -> tuple[bool, str]:
    """סגירת פוזיציה + רישום בלדג'ר."""
    symbol = symbol.upper()
    with _connect() as conn:
        row = conn.execute(
            "SELECT quantity, avg_cost_price, direction, entry_thesis FROM open_positions WHERE symbol=?",
            (symbol,)
        ).fetchone()

        if not row:
            return False, f"לא נמצאה פוזיציה: {symbol}"

        qty, cost, direction, thesis = (
            row["quantity"], row["avg_cost_price"],
            row["direction"], row["entry_thesis"]
        )
        action = "SELL" if direction == "LONG" else "COVER"
        now    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute("DELETE FROM open_positions WHERE symbol=?", (symbol,))
        conn.execute("""
            INSERT INTO trade_history_ledger
                (symbol, action, execution_price, executed_quantity, exit_reason, post_mortem_notes)
            VALUES (?,?,?,?,?,?)
        """, (symbol, action, execution_price, qty, exit_reason, post_mortem_notes))
        conn.execute("""
            INSERT INTO closed_trades
                (symbol, buy_price, sell_price, close_timestamp, original_rationale, post_mortem_notes)
            VALUES (?,?,?,?,?,?)
        """, (symbol, cost, execution_price, now, thesis, post_mortem_notes))

    return True, f"פוזיציה נסגרה: {symbol} | שער={execution_price} | {exit_reason}"


def adjust_for_split(symbol: str, split_ratio: float) -> tuple[bool, str]:
    """התאמה לפיצול מניות."""
    symbol = symbol.upper()
    with _connect() as conn:
        row = conn.execute(
            "SELECT quantity, avg_cost_price, current_price, initial_stop_loss, dynamic_stop_loss "
            "FROM open_positions WHERE symbol=?", (symbol,)
        ).fetchone()
        if not row:
            return False, f"לא נמצאה פוזיציה: {symbol}"

        conn.execute("""
            UPDATE open_positions SET
                quantity          = ?,
                avg_cost_price    = ?,
                current_price     = ?,
                initial_stop_loss = ?,
                dynamic_stop_loss = ?
            WHERE symbol=?
        """, (
            round(row["quantity"]          * split_ratio, 6),
            round(row["avg_cost_price"]    / split_ratio, 4),
            round(row["current_price"]     / split_ratio, 4),
            round(row["initial_stop_loss"] / split_ratio, 4),
            round(row["dynamic_stop_loss"] / split_ratio, 4),
            symbol,
        ))
    return True, f"פיצול מניות {symbol}: יחס {split_ratio}"


# ─────────────────────────────────────────────
# watchlist_setups — קריאה
# ─────────────────────────────────────────────

def get_watchlist() -> list[dict]:
    """כל הרשומות ברשימת המעקב."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM watchlist_setups ORDER BY symbol").fetchall()
    return [dict(r) for r in rows]


def get_watchlist_item(symbol: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM watchlist_setups WHERE symbol=?", (symbol.upper(),)
        ).fetchone()
    return dict(row) if row else None


def get_triggered_alerts() -> list[dict]:
    """רק התראות שהופעלו וממתינות לאישור."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT * FROM watchlist_setups
            WHERE current_status = 'Triggered - Awaiting Confirmation'
            ORDER BY activation_trigger_time DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# watchlist_setups — כתיבה
# ─────────────────────────────────────────────

def add_watchlist_setup(
    symbol: str, trigger_price: float, stop_loss: float,
    thesis_summary: str, required_conditions: str = "",
    trade_type: str = "LONG_TERM"
) -> tuple[bool, str]:
    """הוספת סטאפ לרשימת מעקב. מחזיר (הצלחה, הודעה)."""
    symbol = symbol.upper()
    with _connect() as conn:
        try:
            conn.execute("""
                INSERT INTO watchlist_setups
                    (symbol, required_setup_conditions, trigger_price_zone,
                     current_status, stop_loss, thesis_summary, trade_type)
                VALUES (?,?,?,'Pending Alert',?,?,?)
            """, (symbol, required_conditions, trigger_price, stop_loss, thesis_summary, trade_type))
            return True, f"נוסף למעקב: {symbol} | טריגר={trigger_price} | סטופ={stop_loss}"
        except sqlite3.IntegrityError:
            return False, f"{symbol} כבר קיים ברשימת המעקב"


def update_watchlist_status(symbol: str, new_status: str) -> tuple[bool, str]:
    symbol = symbol.upper()
    with _connect() as conn:
        n = conn.execute(
            "UPDATE watchlist_setups SET current_status=? WHERE symbol=?",
            (new_status, symbol)
        ).rowcount
    if n == 0:
        return False, f"לא נמצא: {symbol}"
    return True, f"סטטוס עודכן: {symbol} → {new_status}"


def remove_from_watchlist(symbol: str) -> tuple[bool, str]:
    symbol = symbol.upper()
    with _connect() as conn:
        n = conn.execute(
            "DELETE FROM watchlist_setups WHERE symbol=?", (symbol,)
        ).rowcount
    return (True, f"הוסר: {symbol}") if n else (False, f"לא נמצא: {symbol}")


def dismiss_alert(symbol: str, notes: str = "") -> tuple[bool, str]:
    """ביטול התראה — החזרה ל-Pending Alert עם הערות."""
    symbol = symbol.upper()
    with _connect() as conn:
        n = conn.execute("""
            UPDATE watchlist_setups
            SET current_status='Pending Alert', dismissal_notes=?,
                activation_trigger_price=NULL, activation_trigger_time=NULL
            WHERE symbol=?
        """, (notes, symbol)).rowcount
    return (True, f"התראה בוטלה: {symbol}") if n else (False, f"לא נמצא: {symbol}")


def process_webhook(symbol: str, price: float, alert_time: str) -> tuple[bool, str]:
    """
    מעבד התראה מ-TradingView.
    אם יש סטאפ ממתין → Triggered.
    אם אין → יוצר רשומה עם אזהרה.
    """
    symbol = symbol.upper()
    with _connect() as conn:
        row = conn.execute(
            "SELECT symbol FROM watchlist_setups WHERE symbol=? AND current_status='Pending Alert'",
            (symbol,)
        ).fetchone()

        if row:
            conn.execute("""
                UPDATE watchlist_setups
                SET current_status='Triggered - Awaiting Confirmation',
                    activation_trigger_price=?,
                    activation_trigger_time=?
                WHERE symbol=?
            """, (price, alert_time, symbol))
            return True, f"התראה הופעלה: {symbol} | שער={price}"
        else:
            # Fallback — שמירת התראה ללא תזה
            try:
                conn.execute("""
                    INSERT INTO watchlist_setups
                        (symbol, required_setup_conditions, trigger_price_zone,
                         current_status, stop_loss, thesis_summary,
                         activation_trigger_price, activation_trigger_time)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (symbol,
                      "⚠️ חסרה תזה — הופעל ישירות מ-TradingView",
                      price, "Triggered - Awaiting Confirmation",
                      0.0, "", price, alert_time))
            except sqlite3.IntegrityError:
                conn.execute("""
                    UPDATE watchlist_setups
                    SET current_status='Triggered - Awaiting Confirmation',
                        activation_trigger_price=?, activation_trigger_time=?
                    WHERE symbol=?
                """, (price, alert_time, symbol))
            return True, f"⚠️ {symbol} הופעל ללא תזה קיימת | שער={price}"


# ─────────────────────────────────────────────
# portfolio_advice
# ─────────────────────────────────────────────

def save_advice(advice_text: str) -> None:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO portfolio_advice (timestamp, advice_text) VALUES (?,?)",
            (now, advice_text)
        )


def get_latest_advice() -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT timestamp, advice_text FROM portfolio_advice ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


# ─────────────────────────────────────────────
# trade_history_ledger + file_metadata
# ─────────────────────────────────────────────

def get_ledger() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM trade_history_ledger ORDER BY order_id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def save_file_metadata(file_name: str, export_timestamp: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO file_metadata (file_name, export_timestamp) VALUES (?,?)",
            (file_name, export_timestamp)
        )


def get_last_file_metadata() -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM file_metadata ORDER BY export_timestamp DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


# ─────────────────────────────────────────────
# כלי עזר לסוכנים
# ─────────────────────────────────────────────

def calculate_atr_stop(entry_price: float, atr: float, direction: str = "LONG") -> float:
    """סטופ = 1.5 × ATR מתחת/מעל נקודת כניסה."""
    if direction.upper() == "LONG":
        return round(entry_price - 1.5 * atr, 4)
    return round(entry_price + 1.5 * atr, 4)


def positions_as_text() -> str:
    """תמצית פוזיציות לסוכן — טקסט קצר."""
    positions = get_positions()
    if not positions:
        return "אין פוזיציות פתוחות."
    lines = ["סימול | כמות | עלות | מחיר | P&L% | סטופ_דינמי"]
    for p in positions:
        lines.append(
            f"{p['symbol']} | {p['quantity']} | {p['avg_cost_price']} | "
            f"{p['current_price']} | {p['pnl_percent']}% | {p['dynamic_stop_loss']}"
        )
    return "\n".join(lines)


def watchlist_as_text() -> str:
    """תמצית watchlist לסוכן."""
    items = get_watchlist()
    if not items:
        return "רשימת המעקב ריקה."
    lines = ["סימול | טריגר | סטופ | סטטוס | תזה"]
    for w in items:
        lines.append(
            f"{w['symbol']} | {w['trigger_price_zone']} | {w['stop_loss']} | "
            f"{w['current_status']} | {w['thesis_summary'][:60]}"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────
# אתחול בטעינה
# ─────────────────────────────────────────────
init_db()
