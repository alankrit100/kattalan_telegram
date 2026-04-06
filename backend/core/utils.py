import re

_ACTION_KEYWORDS = frozenset({
    "buy", "sell", "long", "short", "ce", "pe", "call", "put",
    "btst", "stbt", "buy above", "sell below", "add more", "avg",
    "eq", "cash", "spot"
})

_INDEX_KEYWORDS = frozenset({
    "nifty", "banknifty", "finnifty", "sensex", "midcpnifty", "bankex",
    "crude", "crudeoil", "gold", "silver", "naturalgas"
})

_PARAM_KEYWORDS = frozenset({
    "sl", "stop", "stoploss", "stop loss", "tgt", "target", "cmp",
    "entry", "above", "below", "tp", "take profit", "slm",
    "book", "trail", "safe", "exit", "b/o", "breakout"
})


def is_potential_trade(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    if not re.search(r'\d', t):
        return False
    if any(kw in t for kw in _ACTION_KEYWORDS | _INDEX_KEYWORDS):
        return True
    if any(kw in t for kw in _PARAM_KEYWORDS):
        return True
    return False