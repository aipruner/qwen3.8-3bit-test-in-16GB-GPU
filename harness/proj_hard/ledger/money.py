"""Money is stored as integer minor units (cents) to avoid float drift."""


def to_minor(amount_str):
    """'12.34' -> 1234.  Accepts 1 or 2 decimal places, or none."""
    if "." not in amount_str:
        return int(amount_str) * 100
    whole, frac = amount_str.split(".")
    frac = (frac + "0")[:2]
    return int(whole) * 100 + int(frac)


def to_str(minor):
    return "%d.%02d" % (minor // 100, minor % 100)
