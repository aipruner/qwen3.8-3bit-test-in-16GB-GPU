import unittest
from ledger.account import Account
from ledger.money import to_minor, to_str
from ledger.fx import convert


class TestMoney(unittest.TestCase):
    def test_two_decimals(self):
        self.assertEqual(to_minor("12.34"), 1234)

    def test_one_decimal(self):
        self.assertEqual(to_minor("12.3"), 1230)

    def test_no_decimal(self):
        self.assertEqual(to_minor("12"), 1200)

    def test_negative_two_decimals(self):
        self.assertEqual(to_minor("-12.34"), -1234)

    def test_negative_no_decimal(self):
        self.assertEqual(to_minor("-12"), -1200)

    def test_roundtrip_negative(self):
        self.assertEqual(to_str(to_minor("-0.05")), "-0.05")


class TestFX(unittest.TestCase):
    def test_usd_to_twd(self):
        self.assertEqual(convert(10000, "USD", "TWD"), 315000)

    def test_twd_to_usd(self):
        self.assertEqual(convert(315000, "TWD", "USD"), 10000)


class TestAccount(unittest.TestCase):
    def test_same_currency(self):
        a = Account("USD")
        a.post("10.00")
        a.post("5.50")
        self.assertEqual(a.balance(), "15.50")

    def test_refund_makes_negative(self):
        a = Account("USD")
        a.post("10.00")
        a.post("-12.50")
        self.assertEqual(a.balance(), "-2.50")

    def test_cross_currency(self):
        a = Account("USD")
        a.post("315.00", "TWD")
        self.assertEqual(a.balance(), "10.00")


if __name__ == "__main__":
    unittest.main()
