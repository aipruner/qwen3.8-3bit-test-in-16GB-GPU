"""Fixed-rate FX conversion. Rates are quoted as units of TARGET per 1 USD."""

RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "TWD": 31.5,
    "JPY": 155.0,
}


def convert(minor, src, dst):
    """Convert an integer minor-unit amount between currencies."""
    usd = minor / RATES[src]
    return int(usd * RATES[dst])
