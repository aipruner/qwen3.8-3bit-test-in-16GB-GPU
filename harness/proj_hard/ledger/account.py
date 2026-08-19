from ledger.money import to_minor, to_str
from ledger.fx import convert


class Account:
    def __init__(self, currency):
        self.currency = currency
        self.entries = []

    def post(self, amount_str, currency=None):
        """Post an entry. If currency differs, convert into the account currency."""
        minor = to_minor(amount_str)
        if currency and currency != self.currency:
            minor = convert(minor, currency, self.currency)
        self.entries.append(minor)
        return minor

    def balance(self):
        return to_str(sum(self.entries))
