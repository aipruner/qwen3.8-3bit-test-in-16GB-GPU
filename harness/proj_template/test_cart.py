import unittest
from cart import Cart


class TestCart(unittest.TestCase):
    def test_no_discount(self):
        c = Cart()
        c.add("pen", 10.0, 5)          # subtotal 50
        self.assertEqual(c.total(), 50.0)

    def test_boundary_exactly_100(self):
        c = Cart()
        c.add("book", 50.0, 2)         # subtotal exactly 100 -> 5% tier applies
        self.assertEqual(c.total(), 95.0)

    def test_boundary_exactly_500(self):
        c = Cart()
        c.add("chair", 250.0, 2)       # subtotal exactly 500 -> 10% tier applies
        self.assertEqual(c.total(), 450.0)

    def test_mid_tier(self):
        c = Cart()
        c.add("desk", 300.0, 2)        # subtotal 600 -> 10%
        self.assertEqual(c.total(), 540.0)

    def test_top_tier(self):
        c = Cart()
        c.add("sofa", 1000.0, 1)       # subtotal exactly 1000 -> 15%
        self.assertEqual(c.total(), 850.0)


if __name__ == "__main__":
    unittest.main()
