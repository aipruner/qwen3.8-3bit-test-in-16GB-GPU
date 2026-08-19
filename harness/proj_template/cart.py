"""Shopping cart total calculation."""
from discount import rate_for


class Cart:
    def __init__(self):
        self.items = []

    def add(self, name, unit_price, qty):
        self.items.append({"name": name, "unit_price": unit_price, "qty": qty})

    def subtotal(self):
        return sum(i["unit_price"] * i["qty"] for i in self.items)

    def total(self):
        s = self.subtotal()
        rate = rate_for(s)
        return round(s - (s * rate), 2)
