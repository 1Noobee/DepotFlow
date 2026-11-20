"""
Two costs per case on an NBC purchase (from NBC's sub-dealer rebate workbook):

  * Total cost         - NBC's invoice price per case (StockReceiptItem.cost_price).
                         This is also the selling-price basis and it already
                         contains VAT and excise tax.
  * Rebate-based cost  - the "landing cost": total cost with the tax taken out.
                         NBC's rebate is a percentage of THIS, never of the
                         tax-inclusive price.

Workbook formula, per case:
    VAT          = 7.5% of the price
    Excise       = litres per bottle x bottles per case x N10
    Landing cost = price - VAT - excise

Pure Python (no Django) so it can be tested on its own. To change a tax
rate, edit the two constants below.
"""

import re
from decimal import Decimal, ROUND_HALF_UP

VAT_RATE = Decimal("0.075")
EXCISE_PER_LITRE = Decimal("10")

_TWO_PLACES = Decimal("0.01")


def _money(value):
    return Decimal(value).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def parse_litres(name):
    """Litres per bottle from the leading size in a product name, or None."""
    match = re.match(r"\s*(\d+(?:\.\d+)?)\s*(CL|ML|L)?\b", (name or "").upper())
    if not match:
        return None
    amount = Decimal(match.group(1))
    unit = match.group(2)
    if unit == "CL":
        return amount / 100
    if unit == "ML":
        return amount / 1000
    if unit == "L":
        return amount
    # No unit written: small numbers are litres (1.0, 1.5), big ones are ml (500, 330).
    return amount if amount < 10 else amount / 1000


def parse_bottles_per_case(name):
    """Bottles/cans per case: '4X6' -> 24, 'X12' -> 12, '*24' -> 24, else None."""
    text = (name or "").upper()
    grid = re.search(r"(\d+)\s*X\s*(\d+)", text)
    if grid:
        return int(grid.group(1)) * int(grid.group(2))
    star = re.search(r"\*\s*(\d+)", text)
    if star:
        return int(star.group(1))
    single = re.search(r"\bX\s*(\d+)", text)
    if single:
        return int(single.group(1))
    return None


def landing_cost_breakdown(price, product_name):
    """
    Returns the price, VAT, excise and landing cost for one case.
    excise_known is False when the pack size could not be read from the
    product name; excise is then left out and the figure should be checked.
    """

    price = Decimal(price)
    vat = price * VAT_RATE

    litres = parse_litres(product_name)
    bottles = parse_bottles_per_case(product_name)
    excise_known = litres is not None and bottles is not None
    excise = litres * bottles * EXCISE_PER_LITRE if excise_known else Decimal("0")

    landing = max(price - vat - excise, Decimal("0"))

    return {
        "price": _money(price),
        "vat": _money(vat),
        "excise": _money(excise),
        "landing_cost": _money(landing),
        "excise_known": excise_known,
    }
