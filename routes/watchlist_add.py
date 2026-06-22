"""
routes/watchlist_add.py — POST /api/watchlist/add
שמירת ניתוח מאושר ל-watchlist_setups.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import database as db

router = APIRouter()


class WatchlistAddBody(BaseModel):
    symbol:                   str
    trigger_price_zone:       float
    stop_loss:                float
    thesis_summary:           str
    required_setup_conditions: Optional[str] = ""
    trade_type:               Optional[str] = "SHORT_TERM"
    # שדות אופציונליים מהניתוח
    asset_name:               Optional[str] = ""
    narrative:                Optional[str] = ""
    high_risk:                Optional[bool] = False


@router.post("/api/watchlist/add")
def add_to_watchlist(body: WatchlistAddBody):
    """שמירת תוצאת ניתוח מאושרת ל-watchlist_setups."""
    ok, msg = db.add_watchlist_setup(
        symbol=body.symbol.upper(),
        trigger_price=body.trigger_price_zone,
        stop_loss=body.stop_loss,
        thesis_summary=body.thesis_summary,
        required_conditions=body.required_setup_conditions or "",
        trade_type=body.trade_type or "SHORT_TERM",
    )
    print(f"[watchlist_add] {body.symbol} | ok={ok} | {msg}")
    return {"ok": ok, "message": msg}
