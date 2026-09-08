"""
Role-based navigation visibility.

This intentionally mirrors the role groupings already enforced in
depots/inventory/operations/sales/finance views.py
(_can_manage_depots, _can_manage_inventory, _can_manage_operations,
_can_manage_sales, _can_record_expenses, _can_approve_finance) —
it does not invent new business rules, it just decides which nav
sections are worth showing a given role.

Every list view in the app remains open to any authenticated user
(only mutations are role-checked), so hiding a section from the nav
is a UX choice, not a security boundary — someone can still reach a
URL directly if they know it, and the view-level checks are what
actually stop unauthorized writes. VIEWER sees everything, matching
its role as the read-everything account.
"""


def nav_visibility(request):
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return {}

    role = getattr(user, "role", "")
    is_admin = user.is_staff or role == "SUPER_ADMIN"

    show_depots = is_admin or role in ("TERRITORY_MANAGER", "VIEWER")
    show_inventory = is_admin or role in ("DEPOT_MANAGER", "DEPOT_OFFICER", "VIEWER")
    show_operations = is_admin or role in ("DEPOT_MANAGER", "DEPOT_OFFICER", "VIEWER")
    show_sales = is_admin or role in ("DEPOT_MANAGER", "DEPOT_OFFICER", "SALESMAN", "VIEWER")

    # Finance is split three ways because the underlying permissions
    # already are: DEPOT_OFFICER can record expenses but not approve
    # them or touch supplier payments/rebates/ledger; TERRITORY_MANAGER
    # can't record anything but has an oversight reason to see the
    # ledger. Only one of these three should end up true per user.
    show_finance_full = is_admin or role in ("DEPOT_MANAGER", "FINANCE_OFFICER", "VIEWER")
    show_finance_expenses_only = (not show_finance_full) and role == "DEPOT_OFFICER"
    show_finance_ledger_only = (not show_finance_full) and role == "TERRITORY_MANAGER"

    return {
        "nav_show_depots": show_depots,
        "nav_show_inventory": show_inventory,
        "nav_show_operations": show_operations,
        "nav_show_sales": show_sales,
        "nav_show_finance_full": show_finance_full,
        "nav_show_finance_expenses_only": show_finance_expenses_only,
        "nav_show_finance_ledger_only": show_finance_ledger_only,
        "nav_show_any_finance": show_finance_full or show_finance_expenses_only or show_finance_ledger_only,
        # A role that sees every operational section gets the full
        # numbered workflow on the home page; everyone else gets a
        # shorter, role-tailored set of quick links instead.
        "nav_full_workflow": show_depots and show_inventory and show_operations and show_sales and show_finance_full,
    }
