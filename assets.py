"""Clasificación de activos y normalización de símbolos cripto, sin red."""

from typing import Dict, Optional

# ETFs líquidos habituales. El quoteType de Yahoo puede afinar el resto en caliente.
KNOWN_ETFS = {
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "VEA", "VWO", "EFA", "EEM",
    "GLD", "SLV", "IAU", "USO", "UNG", "TLT", "IEF", "HYG", "LQD", "AGG", "BND",
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE",
    "ARKK", "ARKW", "SMH", "SOXX", "XBI", "KWEB", "FXI", "EWZ", "EWJ",
    "SCHD", "VIG", "VYM", "JEPI", "JEPQ", "BITO",
}

KNOWN_CRYPTO_BASES = {
    "BTC", "ETH", "SOL", "ADA", "XRP", "DOGE", "DOT", "AVAX", "MATIC", "POL",
    "LINK", "LTC", "BCH", "UNI", "ATOM", "XLM", "ALGO", "ETC", "FIL", "APT",
    "ARB", "OP", "NEAR", "ICP", "AAVE", "MKR", "SHIB", "TRX", "TON", "SUI",
    "BNB", "PEPE", "WIF", "BONK", "RENDER", "INJ", "TIA", "SEI", "HBAR",
    "XMR", "ZEC", "EOS", "SAND", "MANA", "AXS", "GRT", "FTM", "EGLD", "FLOW",
    "CRV", "LDO", "SNX", "COMP", "SUSHI", "YFI", "BAT", "ENJ", "CHZ",
    "RUNE", "THETA", "VET", "XTZ", "NEO", "DASH", "WAVES",
}

# Yahoo usa BASE-USD. Binance spot liquida contra USDT.
_FIAT_QUOTES = {"USD", "USDT", "USDC", "EUR"}
_CCXT_QUOTES = ("USDT", "USDC", "BUSD", "USD", "EUR", "BTC", "ETH")
_USD_TO_USDT = {"USD": "USDT"}

QUOTE_TYPE_MAP = {
    "EQUITY": "stock",
    "ETF": "etf",
    "MUTUALFUND": "etf",
    "CRYPTOCURRENCY": "crypto",
    "FUTURE": "futures",
    "CURRENCY": "forex",
    "INDEX": "index",
}

ASSET_LABELS = {
    "stock": "Acción",
    "etf": "ETF",
    "crypto": "Cripto",
    "futures": "Futuro",
    "forex": "Divisa",
    "index": "Índice",
    "unknown": "Desconocido",
}

# Tipos sin múltiplos contables tipo PER.
NON_FUNDAMENTAL_TYPES = {"crypto", "futures", "forex", "index"}


def classify_asset(ticker: str) -> str:
    """Clasifica por el símbolo, sin consultar la red."""
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return "unknown"
    if symbol.endswith("=F"):
        return "futures"
    if symbol.endswith("=X"):
        return "forex"
    if symbol.startswith("^"):
        return "index"
    if "/" in symbol:
        return "crypto"
    if "-" in symbol:
        base, quote = symbol.split("-", 1)
        # BRK-B es una clase de acción; BTC-USD es cripto en Yahoo.
        if quote in _FIAT_QUOTES and len(base) >= 2:
            return "crypto"
        return "stock"
    if symbol in KNOWN_ETFS:
        return "etf"
    for quote in ("USDT", "USDC", "BUSD", "USD"):
        if symbol.endswith(quote) and len(symbol) > len(quote):
            base = symbol[: -len(quote)]
            if base in KNOWN_CRYPTO_BASES:
                return "crypto"
    return "stock"


def refine_asset_type(asset_type: str, info: Optional[Dict] = None) -> str:
    """Afina con quoteType cuando Yahoo ya respondió. Los sufijos fuertes se mantienen."""
    current = asset_type or "unknown"
    if current in {"futures", "forex", "index"}:
        return current
    quote_type = str((info or {}).get("quoteType") or "").upper()
    mapped = QUOTE_TYPE_MAP.get(quote_type)
    if not mapped:
        return current
    return mapped


def should_request_fundamentals(asset_type: str) -> bool:
    """El PER y el dividendo solo se piden para acciones, ETFs o símbolos aún ambiguos."""
    return (asset_type or "unknown") in {"stock", "etf", "unknown"}


def normalize_crypto_symbol(ticker: str) -> str:
    """BTC-USD, BTC/USD o BTCUSDT → BTC/USDT, el par spot de Binance."""
    symbol = (ticker or "").strip().upper().replace(" ", "")
    if not symbol:
        return ""
    symbol = symbol.replace("-", "/")
    if "/" in symbol:
        base, quote = symbol.split("/", 1)
        quote = _USD_TO_USDT.get(quote, quote)
        return f"{base}/{quote}"
    for quote in _CCXT_QUOTES:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            base = symbol[: -len(quote)]
            quote = _USD_TO_USDT.get(quote, quote)
            return f"{base}/{quote}"
    return f"{symbol}/USDT"


def asset_type_label(asset_type: str) -> str:
    return ASSET_LABELS.get(asset_type or "", asset_type or "Desconocido")
