"""
One price per case: the price on the stock receipt is the price the depot works with.
The stock view shows it, stock is valued at it, and the rebate cost is always worked out from it.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from depots.models import Depot, Territory
from reports import services

from .forms import StockReceiptItemFormSet
from .landing_cost import landing_cost_breakdown
from .models import Product, StockReceipt, StockReceiptItem, Supplier

R = User.Role
PASSWORD = "S0me-long-pass-123"
D = Decimal


class SinglePriceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.territory = Territory.objects.create(name="North")
        cls.depot = Depot.objects.create(territory=cls.territory, name="Mine", code="MI")
        cls.other_depot = Depot.objects.create(territory=cls.territory, name="Theirs", code="TH")
        cls.nbc = Supplier.objects.create(name="NBC")
        cls.product = Product.objects.create(
            sku="SKU-1", name="Cola 50cl", category="Sparkling",
            package_type="CRATE", volume="50cl", pack_size=24,
        )
        cls.officer = User.objects.create_user("officer", password=PASSWORD, role=R.DEPOT_OFFICER, depot=cls.depot)

    def receive(self, price, quantity, day, depot=None):
        receipt = StockReceipt.objects.create(
            supplier=self.nbc, depot=depot or self.depot, invoice_number=f"INV-{day}-{price}",
            receipt_date=day, total_amount=D(price) * quantity,
        )
        return StockReceiptItem.objects.create(
            stock_receipt=receipt, product=self.product, quantity=quantity, cost_price=D(price))

    # ---- the receipt line -------------------------------------------------
    def test_there_is_no_landing_cost_field_any_more(self):
        names = {f.name for f in StockReceiptItem._meta.get_fields()}
        self.assertNotIn("rebate_landing_cost", names)
        formset = StockReceiptItemFormSet(instance=StockReceipt())
        self.assertEqual(
            [f for f in formset.forms[0].fields if f not in ("id", "stock_receipt", "DELETE")],
            ["product", "quantity", "cost_price"],
        )
        self.assertNotIn("rebate_landing_cost", formset.forms[0].fields)

    def test_the_field_people_see_is_called_current_selling_price(self):
        form = StockReceiptItemFormSet(instance=StockReceipt()).forms[0]
        self.assertEqual(str(form.fields["cost_price"].label), "Current selling price")

    def test_landing_cost_is_always_worked_out_from_the_price(self):
        item = self.receive("6000.00", 10, date(2026, 11, 1))
        breakdown = landing_cost_breakdown(D("6000.00"), self.product)
        self.assertEqual(item.effective_rebate_landing_cost, breakdown["landing_cost"])
        self.assertEqual(item.effective_rebate_landing_cost, D("5430.00"))   # 6,000 - 7.5% VAT - 12 L x N10
        self.assertLess(item.effective_rebate_landing_cost, item.cost_price)
        self.assertFalse(item.rebate_cost_needs_review)

    # ---- the stock view ---------------------------------------------------
    def test_stock_report_has_one_price_taken_from_the_latest_receipt(self):
        self.receive("5000.00", 10, date(2026, 11, 1))
        self.receive("6000.00", 10, date(2026, 11, 10))
        row = services.get_current_inventory_report(self.depot)["products"][0]
        self.assertEqual(row["price"], D("6000.00"))
        self.assertEqual(row["stock_balance"], 20)
        self.assertEqual(row["inventory_value"], D("120000.00"))
        self.assertNotIn("acquisition_cost", row)
        self.assertNotIn("selling_price", row)

    def test_stock_view_page_shows_a_single_price_column(self):
        self.receive("6000.00", 10, date(2026, 11, 1))
        self.client.login(username="officer", password=PASSWORD)
        response = self.client.get(reverse("reports:stock_view"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(">Price</th>", html)
        self.assertNotIn("Acquisition Cost", html)
        self.assertNotIn("Selling Price", html)
        self.assertIn("6000.00", html)

    # ---- recording a receipt ----------------------------------------------
    def post_receipt(self, depot, price="6000.00"):
        return self.client.post(reverse("inventory:stock_receipt_create"), {
            "supplier": self.nbc.pk, "depot": depot.pk, "receipt_date": "2026-11-10",
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
            "items-0-product": self.product.pk, "items-0-quantity": "10", "items-0-cost_price": price,
        })

    def test_recording_a_receipt_needs_only_product_quantity_and_price(self):
        self.client.login(username="officer", password=PASSWORD)
        response = self.post_receipt(self.depot)
        receipt = StockReceipt.objects.get()
        self.assertRedirects(response, reverse("inventory:stock_receipt_detail", args=[receipt.pk]))
        item = receipt.items.get()
        self.assertEqual(item.cost_price, D("6000.00"))
        detail = self.client.get(reverse("inventory:stock_receipt_detail", args=[receipt.pk]))
        self.assertContains(detail, "<span>Price on receipt</span>")
        self.assertNotContains(detail, "Cost Price")

    def test_a_receipt_cannot_be_recorded_into_another_depot(self):
        self.client.login(username="officer", password=PASSWORD)
        response = self.post_receipt(self.other_depot)
        self.assertEqual(response.status_code, 200)               # form shown again with an error
        self.assertEqual(StockReceipt.objects.count(), 0)
        page = self.client.get(reverse("inventory:stock_receipt_create"))
        self.assertNotContains(page, "Theirs")                    # not even offered
