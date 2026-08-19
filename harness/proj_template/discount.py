"""Tiered discount rules."""

TIERS = [
    (0,    0.00),
    (100,  0.05),
    (500,  0.10),
    (1000, 0.15),
]


def rate_for(subtotal):
    """Return the discount rate for a given subtotal.

    A tier applies when subtotal is >= the tier threshold.
    """
    rate = 0.0
    for threshold, r in TIERS:
        if subtotal > threshold:
            rate = r
    return rate
