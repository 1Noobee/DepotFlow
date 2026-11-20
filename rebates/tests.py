from decimal import Decimal
from django.test import SimpleTestCase

from .models import NBCQuarterlyPlacement, MonthlyHealthCheck
from .services import quarter_for_month, classify_product_category


class NBCRuleTests(SimpleTestCase):
    def test_quarterly_placement_boundaries(self):
        self.assertEqual(NBCQuarterlyPlacement.category_for_volume(12000), 'STANDARD')
        self.assertEqual(NBCQuarterlyPlacement.category_for_volume(12000.01), 'MAXI')
        self.assertEqual(NBCQuarterlyPlacement.category_for_volume(40000), 'MAXI')
        self.assertEqual(NBCQuarterlyPlacement.category_for_volume(40000.01), 'MEGA')

    def test_month_to_quarter(self):
        self.assertEqual(quarter_for_month(1), 1)
        self.assertEqual(quarter_for_month(3), 1)
        self.assertEqual(quarter_for_month(4), 2)
        self.assertEqual(quarter_for_month(12), 4)

    def test_categories_go_by_brand_not_packaging(self):
        self.assertEqual(classify_product_category('Energy Drink 44cl Monster Energy Green *24'), 'MONSTER')
        self.assertEqual(classify_product_category('Energy Drink 400 PET X12 PREDATOR MANGO MAYHEM NG'), 'PREDATOR')
        self.assertEqual(classify_product_category('Juice 300 PET X6 F/ALIVE ORNG PULPY NC NG'), 'JUICE')
        self.assertEqual(classify_product_category('Water 750 Pet X12 Eva Water'), 'WATER')
        self.assertEqual(classify_product_category('Carbonated Soft Drink 330 CAN 4X6 COCA COLA NG'), 'SPARKLING')
        self.assertEqual(classify_product_category('Mixer 400 PET X12 SCHWEPPES TONIC NG'), 'SPARKLING')
        self.assertEqual(classify_product_category('Other 600 PET X12 Limca'), 'SPARKLING')
        self.assertIsNone(classify_product_category('Other 500 PET X12 MYSTERY'))


class HealthCheckFormulaTests(SimpleTestCase):
    def test_matches_the_health_check_sheet(self):
        check = MonthlyHealthCheck(
            grand_total_stock_value=Decimal('69082450'),
            cash_at_hand=Decimal('9058880'),
            git_order_released=Decimal('0'),
            credit_exposure_balance=Decimal('-4146062'),
            nbc_credit_limit=Decimal('0'),
            nbc_permanent_credit=Decimal('0'),
        )
        self.assertEqual(check.total_working_capital, Decimal('78141330'))
        self.assertEqual(check.operator_owned_working_capital, Decimal('82287392'))
        self.assertEqual(round(check.operator_equity_percent), 105)
        self.assertIsNone(check.nbc_credit_utilization_percent)


class RebateRolePolicyTests(SimpleTestCase):
    def test_only_commercial_manager_and_super_admin_manage_reinvestment_targets(self):
        from types import SimpleNamespace
        from .views import _can_manage_profitability

        self.assertTrue(_can_manage_profitability(SimpleNamespace(role='TERRITORY_MANAGER', is_staff=False, is_superuser=False)))
        self.assertTrue(_can_manage_profitability(SimpleNamespace(role='SUPER_ADMIN', is_staff=False, is_superuser=False)))
        self.assertFalse(_can_manage_profitability(SimpleNamespace(role='DEPOT_MANAGER', is_staff=True, is_superuser=False)))
        self.assertFalse(_can_manage_profitability(SimpleNamespace(role='DEPOT_OWNER', is_staff=True, is_superuser=False)))
        self.assertFalse(_can_manage_profitability(SimpleNamespace(role='FINANCE_OFFICER', is_staff=True, is_superuser=False)))

    def test_depot_owner_staff_flag_cannot_submit_health_checks(self):
        from types import SimpleNamespace
        from .views import _can_manage

        self.assertFalse(_can_manage(SimpleNamespace(role='DEPOT_OWNER', is_staff=True)))
        self.assertTrue(_can_manage(SimpleNamespace(role='DEPOT_MANAGER', is_staff=False)))
