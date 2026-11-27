"""
Inventory & pricing services.

ONE PRICE. The price typed on a stock receipt line (per case, tax included, as on
the NBC invoice) is the price the depot works with: it is what the stock cost, what
the stock is valued at, and the price it is loaded and sold at. There is no separate
selling price and no price-history workflow.

- get_current_acquisition_cost() / get_current_selling_price() both return that one
  price: the price on the most recent StockReceiptItem for the product at the depot.
  (Two names are kept so the many callers do not all change at once.)
- Each sale or load line stores the price it used at that moment, so later receipts
  never rewrite past records.
- There is no InventoryBatch / FIFO layer: when a new receipt records a different
  price, existing stock and later sales use the new price.
- Product.base_cost_price / base_selling_price and the old product-level PriceHistory
  table are retired. DepotPriceChange is the new depot-specific audit trail.
- Current stock balance is computed from the inventory transaction ledger.
"""

from decimal import Decimal

from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone


def get_current_selling_price(product, depot=None):
    """
    The price the depot sells this product at: the price on the latest stock receipt
    for it at `depot`. If no depot is given (for example an API listing of products),
    the latest receipt at any depot is used. Returns 0.00 if it was never received.
    """

    if depot is not None:
        return get_current_acquisition_cost(depot, product)

    from inventory.models import StockReceiptItem

    latest_item = (
        StockReceiptItem.objects
        .filter(product=product)
        .order_by("-stock_receipt__receipt_date", "-created_at")
        .first()
    )

    return latest_item.effective_cost_price if latest_item else Decimal("0.00")


def get_current_acquisition_cost(depot, product):
    """
    Return the price of this product at this depot: the price recorded on
    the most recent StockReceiptItem (per case, tax included). It values
    existing stock and is also the price the product is sold at.

    This deliberately does not use FIFO/batch tracking. If the
    depot has never received this product, returns Decimal("0.00").
    """

    # Imported locally to avoid a circular import at module load time.
    from inventory.models import StockReceiptItem

    latest_item = (
        StockReceiptItem.objects
        .filter(
            stock_receipt__depot=depot,
            product=product,
        )
        .order_by("-stock_receipt__receipt_date", "-created_at")
        .first()
    )

    if not latest_item:
        return Decimal("0.00")

    return latest_item.effective_cost_price



def record_depot_price_changes(receipt, previous_prices, changed_by=None):
    """Persist an immutable audit row for each actual current-price change.

    ``previous_prices`` maps product IDs to the effective depot price before
    the receipt was saved. A first receipt establishes the starting price and
    is not treated as a change. Backdated receipts that do not alter the
    effective current price do not create a change record.
    """
    from inventory.models import DepotPriceChange, StockReceiptItem

    changes = []
    for product_id, previous_price in previous_prices.items():
        if previous_price is None:
            continue

        current_item = (
            StockReceiptItem.objects
            .filter(stock_receipt__depot=receipt.depot, product_id=product_id)
            .select_related("product")
            .order_by("-stock_receipt__receipt_date", "-created_at")
            .first()
        )
        if current_item is None or current_item.cost_price == previous_price:
            continue

        change, created = DepotPriceChange.objects.get_or_create(
            stock_receipt=receipt,
            product=current_item.product,
            defaults={
                "depot": receipt.depot,
                "previous_price": previous_price,
                "new_price": current_item.cost_price,
                "changed_by": changed_by,
            },
        )
        if created:
            changes.append(change)
    return changes

def get_stock_balance(depot, product):
    """
    Return the current physical stock balance for a product at a
    specific depot, derived from the inventory transaction ledger.
    """

    from inventory.models import InventoryTransaction

    balance = (
        InventoryTransaction.objects
        .filter(depot=depot, product=product)
        .aggregate(total=Sum("quantity"))["total"]
    )

    return balance or 0


def get_applicable_promotions(product, level, quantity=1, depot=None, supplier=None, as_of=None):
    """
    Return the list of Promotions that currently apply to a given
    product/quantity/depot/supplier combination, most recently
    started first.
 
    Does not pick a single "winning" promotion or apply anything —
    it's the caller's responsibility to decide how to record the
    resulting discount on the relevant transaction line
    (StockReceiptItem.supplier_discount/supplier_rebate, or
    VehicleLoadItem.promo_discount), so the original price and the
    applied adjustment both stay visible on that record.
    """
 
    from inventory.models import Promotion
 
    as_of = as_of or timezone.now().date()
 
    candidates = Promotion.objects.filter(
        level=level,
        is_active=True,
        start_date__lte=as_of,
    ).filter(
        models.Q(end_date__isnull=True) | models.Q(end_date__gte=as_of)
    )
 
    if depot is not None:
        candidates = candidates.filter(
            models.Q(depot__isnull=True) | models.Q(depot=depot)
        )
 
    if supplier is not None:
        candidates = candidates.filter(
            models.Q(supplier__isnull=True) | models.Q(supplier=supplier)
        )
 
    applicable = [
        promo for promo in candidates
        if promo.applies_to_product(product) and promo.applies_to_quantity(quantity)
    ]
 
    return applicable

def create_adjustment(depot, product, quantity_delta, reason, user=None):
    """
    The sanctioned way to make a manual stock adjustment (stock
    count correction, expiry write-off not already covered by a
    return, etc). Posts an ADJUSTMENT InventoryTransaction and
    records an AuditLog entry — manual adjustments should never be
    made by editing InventoryTransaction rows directly (they're
    locked from editing in admin for exactly this reason).

    quantity_delta: positive to increase stock, negative to
    decrease it. Cannot be zero.
    """

    from inventory.models import InventoryTransaction
    from core.audit import log_action
    from core.models import AuditLog

    if quantity_delta == 0:
        raise ValueError("quantity_delta cannot be zero.")

    if not reason:
        raise ValueError("A reason is required for every inventory adjustment.")

    with transaction.atomic():
        cost_reference = get_current_acquisition_cost(depot, product)

        adjustment = InventoryTransaction.objects.create(
            depot=depot,
            product=product,
            transaction_type=InventoryTransaction.TransactionType.ADJUSTMENT,
            quantity=quantity_delta,
            unit_cost=cost_reference,
            reference=f"ADJ-{depot.code}-{timezone.now():%Y%m%d%H%M%S}",
            transaction_date=timezone.now(),
        )

        log_action(
            AuditLog.Action.INVENTORY_ADJUSTMENT,
            obj=adjustment,
            user=user,
            new_value={
                "depot": depot.code,
                "product": product.sku,
                "quantity_delta": quantity_delta,
            },
            notes=reason,
        )

    return adjustment