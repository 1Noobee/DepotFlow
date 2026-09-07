from decimal import Decimal
from datetime import date
from finance.models import Expense, ExpenseCategory
from depots.models import Depot

depot = Depot.objects.first()
category, _ = ExpenseCategory.objects.get_or_create(name="Test Category")

exp = Expense.objects.create(
    depot=depot,
    category=category,
    expense_date=date.today(),
    description="Test fuel expense",
    amount=Decimal("5000.00"),
    payment_method=Expense.PaymentMethod.CASH,
)
print(exp.reference_number)   # should be auto-generated, e.g. EXP-...

from finance.models import BusinessLedger
print(BusinessLedger.objects.filter(reference=exp.reference_number).count())  # expect 1

# Try to edit a locked field — should raise ValidationError
exp.amount = Decimal("9999.00")
try:
    exp.save()
    print("BUG: locked field was allowed to change")
except Exception as e:
    print("Correctly blocked:", e)

# Reload the real value, then reverse it properly
exp.refresh_from_db()
exp.reverse(reason="Testing reversal")
print(exp.is_reversed)   # expect True

print(BusinessLedger.objects.filter(reference__contains=exp.reference_number).count())  # expect 2 (original + reversal)

# approved (non-locked field) should still be editable
exp.approved = True
exp.save()
print(exp.approved)  # expect True