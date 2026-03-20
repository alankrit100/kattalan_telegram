SIGNAL_KEYWORDS = [
    'BUY', 'SELL', 'SL', 'TGT', 'TARGET',
    'CE', 'PE', 'CALL', 'PUT', 'ABOVE', 'BELOW'
]

def is_potential_signal(text: str) -> bool:
    text_upper = text.upper()
    return any(keyword in text_upper for keyword in SIGNAL_KEYWORDS)