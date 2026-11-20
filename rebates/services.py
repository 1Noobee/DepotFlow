from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum

from inventory.models import StockReceiptItem, Supplier

from . import scheme
from .models import NBCQuarterlyPlacement, MonthlyRebateAccrual

_TWO_PLACES = Decimal('0.01')


def classify_product_category(value):
    """
    Which rebate category a product belongs to, or None if it is outside
    the scheme. Works on the product category plus name, and goes by brand,
    not packaging words like CAN/PET/RGB (those say nothing about the drink).
    Schweppes counts as sparkling, as in NBC's workbook.
    """

    text = (value or '').strip().upper()
    if 'PREDATOR' in text:
        return scheme.PREDATOR
    if 'MONSTER' in text:
        return scheme.MONSTER
    if any(k in text for k in ('FIVE ALIVE', 'F/ALIVE', 'ALIVE', 'PULPY', 'JUICE')):
        return scheme.JUICE
    if any(k in text for k in ('COCA', 'COKE', 'FANTA', 'SPRITE', 'LIMCA', 'SCHWEPPES', 'SSD', 'SPARKLING', 'CARBONATED')):
        return scheme.SPARKLING
    if 'WATER' in text or 'EVA' in text:
        return scheme.WATER
    return None


def quarter_for_month(month):
    return ((int(month) - 1) // 3) + 1


@transaction.atomic
def calculate_quarterly_placement(depot, year, quarter, user=None):
    """
    Quarterly placement (Standard / Maxi / Mega) from all NBC cases the
    depot received in the quarter, across every category.
    """
    months = list(range((quarter - 1) * 3 + 1, quarter * 3 + 1))
    # Quantity on a receipt line is treated as physical cases.
    rows = StockReceiptItem.objects.filter(
        stock_receipt__depot=depot,
        stock_receipt__supplier__name__iexact='NBC',
        stock_receipt__receipt_date__year=year,
        stock_receipt__receipt_date__month__in=months,
    ).aggregate(total=Sum('quantity'))
    volume = Decimal(rows['total'] or 0)
    category = NBCQuarterlyPlacement.category_for_volume(volume)
    placement, _ = NBCQuarterlyPlacement.objects.update_or_create(
        depot=depot, year=year, quarter=quarter,
        defaults={'qualifying_cases': volume, 'category': category, 'calculated_by': user, 'notes': 'Calculated from NBC stock receipt quantities across all product categories.'},
    )
    return placement


@transaction.atomic
def calculate_monthly_rebates(depot, year, month, user=None):
    """
    Monthly rebate estimate per category.

    The quarter's placement picks the rate table; the category's cases for
    this month pick the rate inside it; the rate is applied to the rebate-based
    (tax-free landing) cost of those cases. Estimates already CONFIRMED or PAID
    are left alone so a recalculation cannot overwrite them.
    """
    quarter = quarter_for_month(month)
    placement = NBCQuarterlyPlacement.objects.filter(depot=depot, year=year, quarter=quarter).first()
    if placement is None:
        placement = calculate_quarterly_placement(depot, year, quarter, user=user)

    items = StockReceiptItem.objects.filter(
        stock_receipt__depot=depot,
        stock_receipt__supplier__name__iexact='NBC',
        stock_receipt__receipt_date__year=year,
        stock_receipt__receipt_date__month=month,
    ).select_related('product', 'stock_receipt')

    grouped = defaultdict(lambda: {'qty': Decimal('0'), 'cost': Decimal('0'), 'review': set()})
    for item in items:
        category = classify_product_category(f'{item.product.category} {item.product.name}')
        if category is None:
            continue
        qty = Decimal(item.quantity or 0)
        grouped[category]['qty'] += qty
        grouped[category]['cost'] += qty * Decimal(item.effective_rebate_landing_cost or 0)
        if item.rebate_cost_needs_review:
            grouped[category]['review'].add(item.product.name)

    supplier = Supplier.objects.filter(name__iexact='NBC').first()
    if supplier is None:
        raise ValueError('Create the NBC supplier record before calculating rebates. Historical suppliers are not deleted.')

    results = []
    for category in scheme.CATEGORY_ORDER:
        values = grouped.get(category)
        if values is None:
            continue
        qty, landing_cost = values['qty'], values['cost']
        rate = scheme.get_rate(placement.category, category, qty)
        amount = (landing_cost * rate / Decimal('100')).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

        note = (
            f"{placement.get_category_display()} placement; {qty} cases this month at {rate}% "
            f"of landing cost (tax removed)."
        )
        if values['review']:
            note += ' Pack size unreadable, excise not deducted for: ' + ', '.join(sorted(values['review'])) + '. Enter the landing cost on the receipt line.'

        existing = MonthlyRebateAccrual.objects.filter(
            depot=depot, year=year, month=month, product_category=category,
        ).first()
        if existing and existing.status in (MonthlyRebateAccrual.Status.CONFIRMED, MonthlyRebateAccrual.Status.PAID):
            results.append(existing)
            continue

        record, _ = MonthlyRebateAccrual.objects.update_or_create(
            depot=depot, year=year, month=month, product_category=category,
            defaults={
                'supplier': supplier,
                'qualifying_cases': qty,
                'landing_cost_total': landing_cost.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP),
                'rebate_rate': rate,
                'estimated_amount': amount,
                'placement': placement,
                'calculation_notes': note,
                'created_by': user,
            },
        )
        results.append(record)
    return results
