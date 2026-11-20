from decimal import Decimal
from unittest import TestCase

from rebates import scheme as s
from inventory.landing_cost import (
    landing_cost_breakdown, parse_bottles_per_case, parse_litres,
)


class PlacementTests(TestCase):
    def test_boundaries(self):
        self.assertEqual(s.placement_for_cases(12000), s.STANDARD)
        self.assertEqual(s.placement_for_cases(12001), s.MAXI)
        self.assertEqual(s.placement_for_cases(40000), s.MAXI)
        self.assertEqual(s.placement_for_cases(40001), s.MEGA)


class RateTests(TestCase):
    def test_standard_sparkling(self):
        r = lambda c: s.get_rate(s.STANDARD, s.SPARKLING, c)
        self.assertEqual(r(0), Decimal("7.5"))
        self.assertEqual(r(2099), Decimal("7.5"))
        self.assertEqual(r(2100), Decimal("8.0"))
        self.assertEqual(r(2700), Decimal("8.0"))
        self.assertEqual(r(2701), Decimal("8.5"))

    def test_other_cells_from_the_table(self):
        self.assertEqual(s.get_rate(s.MAXI, s.WATER, 651), Decimal("9.0"))
        self.assertEqual(s.get_rate(s.MAXI, s.WATER, 1801), Decimal("9.5"))
        self.assertEqual(s.get_rate(s.MEGA, s.WATER, 9001), Decimal("10.0"))
        self.assertEqual(s.get_rate(s.MEGA, s.PREDATOR, 31001), Decimal("6.0"))
        self.assertEqual(s.get_rate(s.MEGA, s.MONSTER, 33), Decimal("4.0"))
        self.assertEqual(s.get_rate(s.MEGA, s.MONSTER, 34), Decimal("4.5"))
        self.assertEqual(s.get_rate(s.STANDARD, s.JUICE, 121), Decimal("6.5"))
        # Decimal case counts (as summed from the database) work too.
        self.assertEqual(s.get_rate(s.STANDARD, s.MONSTER, Decimal("8")), Decimal("3.5"))

    def test_every_tier_has_every_category(self):
        for tier in (s.STANDARD, s.MAXI, s.MEGA):
            for category in s.CATEGORY_ORDER:
                self.assertIn(category, s.SCHEME[tier])


class LandingCostTests(TestCase):
    def test_pack_parsing(self):
        self.assertEqual(parse_bottles_per_case("500 RGB X24 Coca Cola"), 24)
        self.assertEqual(parse_bottles_per_case("330 CAN 4X6 COCA COLA NG"), 24)
        self.assertEqual(parse_bottles_per_case("44cl Monster Energy Green *24"), 24)
        self.assertEqual(parse_bottles_per_case("1.5 Pet X12 Eva Water"), 12)
        self.assertIsNone(parse_bottles_per_case("40cl PET Predator Gold"))
        self.assertEqual(parse_litres("500 RGB X24"), Decimal("0.5"))
        self.assertEqual(parse_litres("330 CAN 4X6"), Decimal("0.33"))
        self.assertEqual(parse_litres("44cl Monster"), Decimal("0.44"))
        self.assertEqual(parse_litres("1.0 PET X12"), Decimal("1.0"))

    def test_workbook_examples(self):
        # price, name -> landing cost, worked out exactly as the workbook does
        cases = [
            (6000, "500 RGB X24 Coca Cola", "5430.00"),
            (10600, "330 CAN 4X6 COCA COLA NG", "9725.80"),
            (3800, "1.5 Pet X12 Eva Water", "3335.00"),
            (21000, "44cl Monster Energy Green *24", "19319.40"),
        ]
        for price, name, expected in cases:
            result = landing_cost_breakdown(price, name)
            self.assertEqual(result["landing_cost"], Decimal(expected), name)
            self.assertTrue(result["excise_known"])

    def test_unreadable_pack_leaves_excise_out_and_flags_it(self):
        result = landing_cost_breakdown(5200, "40cl PET Predator Gold")
        self.assertFalse(result["excise_known"])
        self.assertEqual(result["landing_cost"], Decimal("4810.00"))  # price less VAT only
