from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import json, os

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "..", "watchlist_data.json")


def _load() -> dict:
    if not os.path.exists(WATCHLIST_FILE):
        return {"items": []}
    with open(WATCHLIST_FILE) as f:
        return json.load(f)


def _save(data: dict):
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(data, f, indent=2)


class WatchlistItem(BaseModel):
    ticker: str
    note: Optional[str] = ""
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None


@router.get("")
def get_watchlist():
    from ..services.stock_data import get_stock_info, get_price_history
    from ..services.cycle_detector import detect_cycle
    data = _load()
    enriched = []
    for item in data["items"]:
        try:
            info = get_stock_info(item["ticker"])
            df = get_price_history(item["ticker"], period="1y")
            cycle = detect_cycle(df) if len(df) > 50 else {}
            enriched.append({**item, "info": info, "cycle": cycle})
        except Exception:
            enriched.append(item)
    return enriched


@router.post("")
def add_to_watchlist(item: WatchlistItem):
    data = _load()
    tickers = [i["ticker"] for i in data["items"]]
    if item.ticker.upper() in tickers:
        raise HTTPException(status_code=400, detail="Already in watchlist")
    data["items"].append({**item.model_dump(), "ticker": item.ticker.upper()})
    _save(data)
    return {"ok": True}


@router.delete("/{ticker}")
def remove_from_watchlist(ticker: str):
    data = _load()
    data["items"] = [i for i in data["items"] if i["ticker"] != ticker.upper()]
    _save(data)
    return {"ok": True}


@router.patch("/{ticker}")
def update_watchlist_item(ticker: str, updates: WatchlistItem):
    data = _load()
    for item in data["items"]:
        if item["ticker"] == ticker.upper():
            item.update({k: v for k, v in updates.model_dump().items() if v is not None})
            _save(data)
            return {"ok": True}
    raise HTTPException(status_code=404, detail="Not found")
