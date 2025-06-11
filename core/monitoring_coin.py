import json
import os
from typing import Dict

FILE_PATH = os.path.join(os.path.dirname(__file__), 'monitoring_coin.json')


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


def record_buy(market: str, amount: float, pre_sell: bool = False) -> None:
    """Record buy information for monitoring."""
    data = _load()
    data[market] = {'market': market, 'amount': amount, 'pre_sell': pre_sell}
    _save(data)


def update_pre_sell(market: str, pre_sell: bool = True) -> None:
    """Update pre-sell status for a market."""
    data = _load()
    if market in data:
        data[market]['pre_sell'] = pre_sell
    else:
        data[market] = {'market': market, 'amount': 0.0, 'pre_sell': pre_sell}
    _save(data)


def remove_market(market: str) -> None:
    """Remove a market from monitoring."""
    data = _load()
    if market in data:
        del data[market]
        _save(data)


def get_monitoring_coins(min_value: float = 5000) -> Dict[str, Dict]:
    """Return monitoring coins excluding those below the min_value."""
    data = _load()
    return {
        m: info
        for m, info in data.items()
        if info.get('amount', 0) >= min_value
    }

def sync_holdings(holdings: Dict[str, Dict], min_value: float = 5000) -> None:
    """Ensure monitoring file contains all holdings."""
    data = _load()
    changed = False

    # Add or update current holdings
    for market, info in holdings.items():
        amount = info.get('total_value')
        if amount is None:
            balance = info.get('balance', 0)
            avg_price = info.get('avg_price', 0)
            amount = balance * avg_price

        if amount < min_value:
            if market in data:
                del data[market]
                changed = True
            continue

        entry = data.get(market, {'market': market, 'pre_sell': False})
        if abs(entry.get('amount', 0) - amount) > 1e-8 or market not in data:
            entry['amount'] = amount
            data[market] = entry
            changed = True

    # Remove markets no longer held
    for market in list(data.keys()):
        if market not in holdings and data[market].get('amount', 0) >= min_value:
            del data[market]
            changed = True

    if changed:
        _save(data)

