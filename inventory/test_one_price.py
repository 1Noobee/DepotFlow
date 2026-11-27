"""
One price: the price on the stock receipt is what the depot buys at AND sells at.
"""
from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from accounts.models import User
from depots.models import Depot, Territory
from operations.models import Vehicle, VehicleLoad, VehicleLoadItem, VehicleSalesman
from sales.models import Sale, SaleItem

from .api import ProductViewSet
from .models import Product, StockReceipt, StockReceiptItem, Supplier, DepotPriceChange
from .services import (
    get_current_acquisition_cost, get_current_selling_price,
    record_depot_price_changes,
)

R = User.Role
PASSWORD = "S0me-long-pass-123"
D = Decimal


class OnePriceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        territory = Territory.objects.create(name="North")
        cls.depot = Depot.objects.create(territory=territory, name="Mine", code="MI")
        cls.other_depot = Depot.objects.create(territory=territory, name="Theirs", code="TH")
        cls.nbc = Supplier.objects.create(name="NBC")
        cls.product = Product.objects.create(
            sku="SKU-1", name="Cola 50cl", category="Sparkling",
            package_type="CRATE", volume="50cl", pack_size=24,
        )
        cls.manager = User.objects.create_user("dm", password=PASSWORD, role=R.DEPOT_MANAGER, depot=cls.depot)
        cls.vehicle = Vehicle.objects.create(depot=cls.depot, registration_number="V-1", vehicle_name="Van")
        cls.salesman = VehicleSalesman.objects.create(
            name="Sam", employee_id="E-1", depot=cls.depot, vehicle=cls.vehicle)

    def receive(self, price, quantity, day, depot=None):
        receipt = StockReceipt.objects.create(
            supplier=self.nbc, depot=depot or self.depot, invoice_number=f"INV-{day}-{price}",
            receipt_date=day, total_amount=D(price) * quantity)
        return StockReceiptItem.objects.create(
            stock_receipt=receipt, product=self.product, quantity=quantity, cost_price=D(price))

    def load(self, quantity=10, **item_extra):
        load = VehicleLoad.objects.create(
            salesman=self.salesman, vehicle=self.vehicle, depot=self.depot, load_date=date(2026, 11, 20))
        item = VehicleLoadItem.objects.create(
            vehicle_load=load, product=self.product, quantity=quantity, **item_extra)
        return load, item

    # ---- the price lookup --------------------------------------------------
    def test_price_is_the_latest_receipt_price_at_the_depot(self):
        self.receive("5000.00", 10, date(2026, 11, 1))
        self.receive("6000.00", 10, date(2026, 11, 10))
        self.receive("9999.00", 10, date(2026, 11, 12), depot=self.other_depot)
        self.assertEqual(get_current_selling_price(self.product, depot=self.depot), D("6000.00"))
        self.assertEqual(get_current_acquisition_cost(self.depot, self.product), D("6000.00"))

    def test_a_product_never_received_has_no_price(self):
        self.assertEqual(get_current_selling_price(self.product, depot=self.depot), D("0.00"))
        self.assertEqual(get_current_selling_price(self.product), D("0.00"))

    def test_without_a_depot_the_latest_receipt_anywhere_is_used(self):
        self.receive("5000.00", 10, date(2026, 11, 1))
        self.receive("9999.00", 10, date(2026, 11, 12), depot=self.other_depot)
        self.assertEqual(get_current_selling_price(self.product), D("9999.00"))

    # ---- loads and sales ---------------------------------------------------
    def test_a_load_is_priced_at_the_receipt_price(self):
        self.receive("6000.00", 50, date(2026, 11, 1))
        _, item = self.load(quantity=10)
        self.assertEqual(item.cost_price, D("6000.00"))
        self.assertEqual(item.selling_price, D("6000.00"))
        self.assertEqual(item.effective_selling_price, D("6000.00"))
        self.assertEqual(item.expected_revenue, D("60000.00"))
        self.assertEqual(item.expected_profit, D("0.00"))

    def test_a_promo_discount_comes_off_the_receipt_price(self):
        self.receive("6000.00", 50, date(2026, 11, 1))
        _, item = self.load(quantity=10, promo_discount=D("500.00"))
        self.assertEqual(item.effective_selling_price, D("5500.00"))

    def test_a_sale_is_priced_at_the_receipt_price_and_later_receipts_do_not_rewrite_it(self):
        self.receive("6000.00", 50, date(2026, 11, 1))
        load, _ = self.load(quantity=20)
        sale = Sale.objects.create(vehicle_load=load, salesman=self.salesman, sale_date=date(2026, 11, 20))
        first = SaleItem.objects.create(sale=sale, product=self.product, quantity=5)
        self.assertEqual(first.unit_price, D("6000.00"))
        self.assertEqual(first.unit_cost, D("6000.00"))
        self.assertEqual(first.line_profit, D("0.00"))

        self.receive("6500.00", 50, date(2026, 11, 21))              # NBC raises its price
        second_sale = Sale.objects.create(vehicle_load=load, salesman=self.salesman, sale_date=date(2026, 11, 21))
        second = SaleItem.objects.create(sale=second_sale, product=self.product, quantity=5)
        self.assertEqual(second.unit_price, D("6500.00"))            # new sales use the new price
        first.refresh_from_db()
        self.assertEqual(first.unit_price, D("6000.00"))             # the earlier sale keeps its own


    def test_receipt_price_change_is_audited_with_old_new_price_and_user(self):
        self.receive("6000.00", 50, date(2026, 11, 1))
        self.client.login(username="dm", password=PASSWORD)

        receipt = StockReceipt.objects.create(
            supplier=self.nbc, depot=self.depot, invoice_number="INV-PRICE-CHANGE",
            receipt_date=date(2026, 11, 10),
        )
        StockReceiptItem.objects.create(
            stock_receipt=receipt, product=self.product, quantity=25,
            cost_price=D("6500.00"),
        )
        changes = record_depot_price_changes(
            receipt, {self.product.pk: D("6000.00")}, changed_by=self.manager
        )
        self.assertEqual(len(changes), 1)

        change = DepotPriceChange.objects.get(stock_receipt=receipt, product=self.product)
        self.assertEqual(change.previous_price, D("6000.00"))
        self.assertEqual(change.new_price, D("6500.00"))
        self.assertEqual(change.changed_by, self.manager)

    def test_first_receipt_and_unchanged_price_do_not_create_change_records(self):
        first = self.receive("6000.00", 50, date(2026, 11, 1))
        self.assertEqual(DepotPriceChange.objects.count(), 0)

        same_price_receipt = StockReceipt.objects.create(
            supplier=self.nbc, depot=self.depot, invoice_number="INV-SAME-PRICE",
            receipt_date=date(2026, 11, 2),
        )
        StockReceiptItem.objects.create(
            stock_receipt=same_price_receipt, product=self.product, quantity=10,
            cost_price=D("6000.00"),
        )
        self.assertEqual(
            record_depot_price_changes(
                same_price_receipt, {self.product.pk: D("6000.00")},
                changed_by=self.manager,
            ),
            [],
        )
        self.assertEqual(DepotPriceChange.objects.count(), 0)

    def test_product_page_displays_price_change_history(self):
        self.receive("6000.00", 50, date(2026, 11, 1))
        receipt = StockReceipt.objects.create(
            supplier=self.nbc, depot=self.depot, invoice_number="INV-PRICE-HISTORY",
            receipt_date=date(2026, 11, 10),
        )
        StockReceiptItem.objects.create(
            stock_receipt=receipt, product=self.product, quantity=25,
            cost_price=D("6500.00"),
        )
        record_depot_price_changes(
            receipt, {self.product.pk: D("6000.00")}, changed_by=self.manager
        )
        self.client.login(username="dm", password=PASSWORD)
        response = self.client.get(reverse("inventory:product_detail", args=[self.product.pk]))
        self.assertContains(response, "Recent price changes")
        self.assertContains(response, "6000.00")
        self.assertContains(response, "6500.00")
        self.assertContains(response, "INV-PRICE-HISTORY")

    # ---- the old price machinery is gone -----------------------------------
    def test_there_is_no_way_left_to_set_a_separate_price(self):
        with self.assertRaises(NoReverseMatch):
            reverse("inventory:change_price", args=[self.product.pk])
        self.assertFalse(hasattr(ProductViewSet, "change_price"))
        self.assertFalse(hasattr(ProductViewSet, "price_history"))
        self.assertFalse(hasattr(Product, "update_prices"))
        with self.assertRaises(CommandError):
            call_command("update_prices")

    def test_product_page_shows_the_receipt_price_per_depot(self):
        self.receive("6000.00", 10, date(2026, 11, 1))
        self.client.login(username="dm", password=PASSWORD)
        response = self.client.get(reverse("inventory:product_detail", args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mine")
        self.assertContains(response, "6000.00")
        self.assertNotContains(response, "Change Price")
        self.assertNotContains(response, "Price History")
        self.assertNotContains(response, "Cost reference")
        self.assertNotContains(response, "Theirs")                    # the manager cannot see that depot

    def test_product_with_no_receipt_says_so(self):
        self.client.login(username="dm", password=PASSWORD)
        response = self.client.get(reverse("inventory:product_detail", args=[self.product.pk]))
        self.assertContains(response, "has no price")

    def test_product_api_exposes_one_current_price(self):
        from .serializers import ProductSerializer
        self.receive("6000.00", 10, date(2026, 11, 1))
        data = ProductSerializer(self.product).data
        self.assertEqual(D(str(data["current_price"])), D("6000.00"))
        self.assertNotIn("current_selling_price", data)
        self.assertNotIn("current_cost_reference", data)

    def test_sale_and_load_pages_show_no_profit(self):
        self.receive("6000.00", 50, date(2026, 11, 1))
        load, _ = self.load(quantity=20)
        sale = Sale.objects.create(vehicle_load=load, salesman=self.salesman, sale_date=date(2026, 11, 20))
        SaleItem.objects.create(sale=sale, product=self.product, quantity=5)
        self.client.login(username="dm", password=PASSWORD)

        sale_page = self.client.get(reverse("sales:sale_detail", args=[sale.pk]))
        self.assertEqual(sale_page.status_code, 200)
        self.assertNotContains(sale_page, "Profit")
        self.assertContains(sale_page, "30000.00")                    # 5 x 6,000

        load_page = self.client.get(reverse("operations:load_detail", args=[load.pk]))
        self.assertEqual(load_page.status_code, 200)
        self.assertNotContains(load_page, "Expected Profit")
        self.assertNotContains(load_page, "Effective Cost")
        self.assertContains(load_page, "120000.00")                   # 20 x 6,000
