
"""A small collection of Python "best syntax" examples.

This file demonstrates concise, modern, and idiomatic Python patterns:
- type hints
- dataclasses
- context managers
- f-strings
- list/dict comprehensions
- generator expressions
- pathlib and logging
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Iterable, List, Dict
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Person:
	name: str
	age: int

	def greet(self) -> str:
		"""Return a short greeting using an f-string."""
		return f"Hello, my name is {self.name} and I'm {self.age}."


def squares(nums: Iterable[int]) -> List[int]:
	"""Return list of squares using a list comprehension."""
	return [n * n for n in nums]

print()

def index_by_name(people: Iterable[Person]) -> Dict[str, Person]:
	"""Return a dict mapping name -> Person (dict comprehension)."""
	return {p.name: p for p in people}


def first_even(nums: Iterable[int]) -> int | None:
	"""Return the first even number or None (generator expression)."""
	return next((n for n in nums if n % 2 == 0), None)


@contextmanager
def open_text(path: Path) -> Iterator[str]:
	"""Simple context manager wrapper for reading a text file.

	Shows use of pathlib and contextmanager for concise resource handling.
	"""
	with path.open("r", encoding="utf-8") as fh:
		yield fh.read()


def read_lines(path: str) -> List[str]:
	"""Read lines from a file using pathlib and return stripped lines."""
	p = Path(path)
	if not p.exists():
		logger.debug("File does not exist: %s", p)
		return []
	return [line.rstrip("\n") for line in p.read_text(encoding="utf-8").splitlines()]


__all__ = [
	"Person",
	"squares",
	"index_by_name",
	"first_even",
	"open_text",
	"read_lines",
]


from decimal import Decimal
from datetime import date
from inventory.models import Product, Promotion

p = Product.objects.first()
promo = Promotion(
    name="Test 10% Off",
    level=Promotion.Level.DEPOT_TO_CUSTOMER,
    promotion_type=Promotion.PromotionType.PERCENTAGE_DISCOUNT,
    percentage_value=Decimal("10.00"),
    start_date=date.today(),
)
promo.full_clean()   # should NOT raise
promo.save()
promo.products.add(p)

print(promo.is_effective_on(date.today()))          # expect True
print(promo.applies_to_product(p))                   # expect True
print(promo.calculate_discount_per_unit(Decimal("10000")))  # expect 1000.00

from inventory.services import get_applicable_promotions
print(get_applicable_promotions(p, Promotion.Level.DEPOT_TO_CUSTOMER))  # expect [promo]
