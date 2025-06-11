import json
import os
from typing import Dict

from .constants import DEFAULT_COIN_SELECTION

FILE_PATH = os.path.join(os.path.dirname(__file__), 'monitoring_coin.json')
EXCLUDED = set(DEFAULT_COIN_SELECTION.get('excluded_coins', []))


def _load() -> Dict[str, Dict]:
    if os.path.exists(FILE_PATH):
        try:
            with open(FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save(data: Dict[str, Dict]) -> None:
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_trade(market: str, buy_price: float, sell_price: float) -> None:
    """Record buy/sell information for monitoring."""
    data = _load()
    data[market] = {
        'market': market,
        '매수체결가격': buy_price,
        '매도주문가격': sell_price,
    }
    _save(data)


def update_sell_price(market: str, sell_price: float) -> None:
    """Update sell order price for a market."""
    data = _load()
    entry = data.get(market, {'market': market})
    entry['매도주문가격'] = sell_price
    data[market] = entry
    _save(data)


def remove_market(market: str) -> None:
    """Remove a market from monitoring."""
    data = _load()
    if market in data:
        del data[market]
        _save(data)


def get_monitoring_coins() -> Dict[str, Dict]:
    """Return monitoring coins excluding those in the excluded list."""
    data = _load()
    return {m: info for m, info in data.items() if m not in EXCLUDED}

def sync_holdings(holdings: Dict[str, Dict]) -> None:
    """Ensure monitoring file contains all holdings except excluded ones."""
    data = _load()
    changed = False

    # Add missing holdings
    for market in holdings.keys():
        if market in EXCLUDED:
            continue
        if market not in data:
            data[market] = {'market': market}
            changed = True

    # Remove markets no longer held
    for market in list(data.keys()):
        if market not in holdings or market in EXCLUDED:
            del data[market]
            changed = True

    if changed:
        _save(data)


