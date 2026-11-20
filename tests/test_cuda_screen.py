"""Exercise the sensitivity screen's rounding and input boundaries on any host."""

from dataclasses import replace
import unittest

from pilot.cuda_screen import screen
from pilot.underwriting import Economics


class ScreenChecks(unittest.TestCase):
    def test_matrix_order_and_rounding(self):
        terms = Economics(
            resale_cents=100_001, renovation_cents=1, carrying_cents=1,
            selling_bps=500, stress_price_drop_bps=0, stress_extra_cents=2,
            base_profit_cents=1, stress_profit_cents=3, financing_cap_cents=None,
        )
        # 100,001 at 10% stress floors to 90,000 before the selling fee.
        self.assertEqual(screen(terms, [100_001, 0], [0, 1000, 10_000]),
                         [[94_993, 85_493, -7], [-7, -7, -7]])
        self.assertEqual(
            screen(replace(terms, financing_cap_cents=0), [100_001], [1000]),
            [[85_493]],
        )
        with self.assertRaises(ValueError):
            screen(terms, [100_001], [10_001])
