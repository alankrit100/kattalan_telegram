import re

SIGNAL_KEYWORDS = [
    'BUY', 'SELL', 'SL', 'TGT', 'TARGET',
    'CE', 'PE', 'CALL', 'PUT', 'ABOVE', 'BELOW'
]


def compress_text(text: str) -> str:
    # Remove URLs
    text = re.sub(r'http\S+', '', text)
    # Remove multiple spaces and newlines
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing whitespace
    return text.strip()


def is_potential_signal(text: str) -> bool:
    if not text: return False
    
    text_upper = text.upper()
    
    # 1. Must contain at least one trading keyword
    keywords = ["BUY", "SELL", "CE", "PE", "CALL", "PUT", "LONG", "SHORT"]
    if not any(k in text_upper for k in keywords): return False
    
    # 2. Must contain at least one number (for strike, entry, or SL)
    if not re.search(r'\d', text): return False
    
    # 3. Must contain risk management keywords (Target or SL)
    if not any(k in text_upper for k in ["SL", "STOP", "TGT", "TARGET", "PR", "PAID"]): return False
    
    return True