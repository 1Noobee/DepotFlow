from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from core.scoping import get_visible_depots, user_can_access_depot, is_unrestricted
from .models import BusinessLedger, Expense, SupplierPayment, SupplierRebate
from .forms import ExpenseForm, SupplierPaymentForm, SupplierRebateForm, ReversalForm


def _can_record_expenses(user):
    """
    Staff, SUPER_ADMIN, DEPOT_MANAGER, or DEPOT_OFFICER can record
    expenses (matches the original spec's permission table).
    """

    return user.is_staff or getattr(user, "role", "") in (
        "SUPER_ADMIN", "DEPOT_MANAGER", "DEPOT_OFFICER",
    )


def _can_approve_finance(user):
    """
    Approving, reversing, and recording supplier payments/rebates is
    restricted to SUPER_ADMIN, DEPOT_MANAGER, or FINANCE_OFFICER —
    matches the original spec's Finance role ("manage/verify
    financial records").
    """

    return user.is_staff or getattr(user, "role", "") in (
        "SUPER_ADMIN", "DEPOT_MANAGER", "FINANCE_OFFICER",
    )


# =========================
# EXPENSES
# =========================
@login_required
def expense_list(request):
    expenses = Expense.objects.filter(
        depot__in=get_visible_depots(request.user)
    ).select_related("depot", "category").order_by("-expense_date")
    return render(request, "finance/expense_list.html", {
        "expenses": expenses,
        "can_approve": _can_approve_finance(request.user),
    })


@login_required
def expense_create(request):
    if not _can_record_expenses(request.user):
        messages.error(request, "You do not have permission to record expenses.")
        return redirect("finance:expense_list")

    if request.method == "POST":
        form = ExpenseForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Expense recorded.")
            return redirect("finance:expense_list")
    else:
        form = ExpenseForm(user=request.user)

    return render(request, "finance/expense_form.html", {"form": form, "title": "New Expense"})


@login_required
def expense_approve(request, pk):
    expense = get_object_or_404(Expense, pk=pk)

    if not _can_approve_finance(request.user):
        messages.error(request, "You do not have permission to approve expenses.")
        return redirect("finance:expense_list")

    if not user_can_access_depot(request.user, expense.depot):
        messages.error(request, "You do not have access to that expense.")
        return redirect("finance:expense_list")

    if request.method == "POST":
        expense.approved = True
        expense.save(update_fields=["approved", "updated_at"])
        messages.success(request, "Expense approved.")

    return redirect("finance:expense_list")


@login_required
def expense_reverse(request, pk):
    expense = get_object_or_404(Expense, pk=pk)

    if not _can_approve_finance(request.user):
        messages.error(request, "You do not have permission to reverse expenses.")
        return redirect("finance:expense_list")

    if not user_can_access_depot(request.user, expense.depot):
        messages.error(request, "You do not have access to that expense.")
        return redirect("finance:expense_list")

    if request.method == "POST":
        form = ReversalForm(request.POST)
        if form.is_valid():
            try:
                expense.reverse(user=request.user, reason=form.cleaned_data["reason"])
                messages.success(request, "Expense reversed.")
                return redirect("finance:expense_list")
            except Exception as exc:
                messages.error(request, str(exc))
    else:
        form = ReversalForm()

    return render(request, "finance/reversal_form.html", {
        "form": form,
        "object_repr": f"{expense.reference_number} — {expense.category.name} — \u20a6{expense.amount}",
        "title": f"Reverse Expense {expense.reference_number}",
    })


# =========================
# SUPPLIER PAYMENTS
# =========================
@login_required
def supplier_payment_list(request):
    payments = SupplierPayment.objects.filter(
        depot__in=get_visible_depots(request.user)
    ).select_related("depot", "supplier").order_by("-payment_date")
    return render(request, "finance/supplier_payment_list.html", {
        "payments": payments,
        "can_approve": _can_approve_finance(request.user),
    })


@login_required
def supplier_payment_create(request):
    if not _can_approve_finance(request.user):
        messages.error(request, "You do not have permission to record supplier payments.")
        return redirect("finance:supplier_payment_list")

    if request.method == "POST":
        form = SupplierPaymentForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Supplier payment recorded.")
            return redirect("finance:supplier_payment_list")
    else:
        form = SupplierPaymentForm(user=request.user)

    return render(request, "finance/supplier_payment_form.html", {"form": form, "title": "New Supplier Payment"})


@login_required
def supplier_payment_reverse(request, pk):
    payment = get_object_or_404(SupplierPayment, pk=pk)

    if not _can_approve_finance(request.user):
        messages.error(request, "You do not have permission to reverse supplier payments.")
        return redirect("finance:supplier_payment_list")

    if not user_can_access_depot(request.user, payment.depot):
        messages.error(request, "You do not have access to that supplier payment.")
        return redirect("finance:supplier_payment_list")

    if request.method == "POST":
        form = ReversalForm(request.POST)
        if form.is_valid():
            try:
                payment.reverse(user=request.user, reason=form.cleaned_data["reason"])
                messages.success(request, "Supplier payment reversed.")
                return redirect("finance:supplier_payment_list")
            except Exception as exc:
                messages.error(request, str(exc))
    else:
        form = ReversalForm()

    return render(request, "finance/reversal_form.html", {
        "form": form,
        "object_repr": f"{payment.reference_number} — {payment.supplier.name} — \u20a6{payment.amount}",
        "title": f"Reverse Payment {payment.reference_number}",
    })


# =========================
# SUPPLIER REBATES
# =========================
@login_required
def supplier_rebate_list(request):
    rebates = SupplierRebate.objects.filter(
        depot__in=get_visible_depots(request.user)
    ).select_related("depot", "supplier").order_by("-rebate_date")
    return render(request, "finance/supplier_rebate_list.html", {
        "rebates": rebates,
        "can_approve": _can_approve_finance(request.user),
    })


@login_required
def supplier_rebate_create(request):
    if not _can_approve_finance(request.user):
        messages.error(request, "You do not have permission to record supplier rebates.")
        return redirect("finance:supplier_rebate_list")

    if request.method == "POST":
        form = SupplierRebateForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Supplier rebate recorded.")
            return redirect("finance:supplier_rebate_list")
    else:
        form = SupplierRebateForm(user=request.user)

    return render(request, "finance/supplier_rebate_form.html", {"form": form, "title": "New Supplier Rebate"})


@login_required
def supplier_rebate_reverse(request, pk):
    rebate = get_object_or_404(SupplierRebate, pk=pk)

    if not _can_approve_finance(request.user):
        messages.error(request, "You do not have permission to reverse supplier rebates.")
        return redirect("finance:supplier_rebate_list")

    if not user_can_access_depot(request.user, rebate.depot):
        messages.error(request, "You do not have access to that supplier rebate.")
        return redirect("finance:supplier_rebate_list")

    if request.method == "POST":
        form = ReversalForm(request.POST)
        if form.is_valid():
            try:
                rebate.reverse(user=request.user, reason=form.cleaned_data["reason"])
                messages.success(request, "Supplier rebate reversed.")
                return redirect("finance:supplier_rebate_list")
            except Exception as exc:
                messages.error(request, str(exc))
    else:
        form = ReversalForm()

    return render(request, "finance/reversal_form.html", {
        "form": form,
        "object_repr": f"{rebate.reference_number} — {rebate.supplier.name} — \u20a6{rebate.amount}",
        "title": f"Reverse Rebate {rebate.reference_number}",
    })


# =========================
# BUSINESS LEDGER (read-only)
# =========================
@login_required
def ledger_list(request):
    """
    Business Ledger, scoped for depot confidentiality — this is a
    deliberate exception to the rest of the app's "reads are open to
    anyone" convention, since ledger entries are real financial
    detail for a specific depot:

    - Super Admin (or staff): every depot, switchable.
    - Territory Manager: every depot in their own territory, switchable.
    - Everyone else (Depot Manager, Depot Officer, Finance Officer,
      Salesman, Viewer): only their own assigned depot — no switcher,
      and a ?depot= query param from anyone outside the two groups
      above is ignored rather than honored, so this can't be bypassed
      by editing the URL. No depot on the account means no ledger to
      show at all, rather than falling back to "all of them".
    """

    user = request.user
    can_switch = is_unrestricted(user) or (user.is_territory_manager and user.territory_id)
    depots = get_visible_depots(user).order_by("name")

    depot_id = request.GET.get("depot")

    if depot_id and can_switch:
        depot = get_object_or_404(depots, pk=depot_id)
    else:
        depot = depots.first()

    ledger_entries = (
        BusinessLedger.objects.filter(depot=depot).order_by("-transaction_date", "-created_at")[:200]
        if depot else []
    )

    return render(request, "finance/ledger_list.html", {
        "depots": depots,
        "depot": depot,
        "can_switch": can_switch,
        "ledger_entries": ledger_entries,
    })