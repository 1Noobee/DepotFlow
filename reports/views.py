"""
Thin JSON views for reports. All calculation logic lives in
services.py -- views here only parse request parameters, fetch the
relevant object, call the matching service function, and return it
as JSON.

Every view requires login for now, as a baseline. Full role-based
scoping (e.g. a Territory Manager only seeing their own territory)
is handled in the broader views/permissions pass, not here.
"""

from datetime import date as date_cls
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from depots.models import Depot, Territory
from operations.models import VehicleSalesman
from . import services


def _parse_date(value):
    if not value:
        return None
    return date_cls.fromisoformat(value)


@login_required
@require_GET
def daily_sales_report(request, depot_id):
    depot = get_object_or_404(Depot, pk=depot_id)
    report_date = _parse_date(request.GET.get("date")) or date_cls.today()
    return JsonResponse(services.get_daily_sales_report(depot, report_date))


@login_required
@require_GET
def daily_stock_movement_report(request, depot_id):
    depot = get_object_or_404(Depot, pk=depot_id)
    report_date = _parse_date(request.GET.get("date")) or date_cls.today()
    return JsonResponse(services.get_daily_stock_movement_report(depot, report_date))


@login_required
@require_GET
def current_inventory_report(request, depot_id):
    depot = get_object_or_404(Depot, pk=depot_id)
    return JsonResponse(services.get_current_inventory_report(depot))


@login_required
@require_GET
def expense_report(request, depot_id):
    depot = get_object_or_404(Depot, pk=depot_id)
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    return JsonResponse(services.get_expense_report(depot, date_from, date_to))


@login_required
@require_GET
def net_profit_report(request, depot_id):
    depot = get_object_or_404(Depot, pk=depot_id)
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    return JsonResponse(services.get_net_profit_report(depot, date_from, date_to))


@login_required
@require_GET
def top_selling_skus_report(request, depot_id):
    depot = get_object_or_404(Depot, pk=depot_id)
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    limit = int(request.GET.get("limit", 10))
    return JsonResponse(
        {"skus": services.get_top_selling_skus(depot, date_from, date_to, limit)}
    )


@login_required
@require_GET
def slow_moving_skus_report(request, depot_id):
    depot = get_object_or_404(Depot, pk=depot_id)
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    limit = int(request.GET.get("limit", 10))
    return JsonResponse(
        {"skus": services.get_slow_moving_skus(depot, date_from, date_to, limit)}
    )


@login_required
@require_GET
def salesman_load_return_report(request, salesman_id):
    salesman = get_object_or_404(VehicleSalesman, pk=salesman_id)
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    return JsonResponse(services.get_salesman_load_return_report(salesman, date_from, date_to))


@login_required
@require_GET
def territory_comparison_report(request, territory_id):
    territory = get_object_or_404(Territory, pk=territory_id)
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    return JsonResponse(services.get_territory_depot_comparison(territory, date_from, date_to))


@login_required
@require_GET
def business_ledger_summary_report(request):
    depot_id = request.GET.get("depot_id")
    territory_id = request.GET.get("territory_id")
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))

    depot = get_object_or_404(Depot, pk=depot_id) if depot_id else None
    territory = get_object_or_404(Territory, pk=territory_id) if territory_id else None

    return JsonResponse(
        services.get_business_ledger_summary(depot, territory, date_from, date_to)
    )


@login_required
def stock_view(request):
    """
    Human-facing "what's actually in stock right now" page — the
    HTML counterpart to current_inventory_report's JSON, with a
    depot switcher instead of requiring a depot_id in the URL.

    Open to any authenticated user (matches every other list view in
    the app): defaults to the user's own depot if they have one,
    otherwise the first depot alphabetically.
    """

    depots = Depot.objects.order_by("name")
    depot_id = request.GET.get("depot")

    if depot_id:
        depot = get_object_or_404(Depot, pk=depot_id)
    elif request.user.depot_id:
        depot = request.user.depot
    else:
        depot = depots.first()

    report = services.get_current_inventory_report(depot) if depot else None
    total_value = sum((row["inventory_value"] for row in report["products"]), Decimal("0.00")) if report else Decimal("0.00")

    return render(request, "reports/stock_view.html", {
        "depots": depots,
        "depot": depot,
        "report": report,
        "total_value": total_value,
    })


@login_required
def dashboard(request):
    """
    Role-specific KPI landing page (spec section 22).

    - Depot Manager / Depot Officer: today's figures for their own
      depot (units sold, revenue, expenses, net position).
    - Territory Manager: month-to-date net-profit ranking across
      every depot in their territory.
    - Super Admin: the same ranking, one table per territory,
      across the whole business.

    A single day of net profit ranks depots almost arbitrarily (a
    depot with zero activity today just sits at the bottom), so the
    ranking views use month-to-date instead of "today" — the Depot
    Manager KPIs stay "today" since that's what the spec asks for
    there specifically.

    Salesman/Finance Officer/Viewer get no KPI cards yet: there's no
    link from a User account to a VehicleSalesman record, so a
    personalized salesman dashboard isn't possible without a schema
    change; Finance Officer/Viewer dashboards weren't specified.
    They still see the existing hub of links below.
    """

    user = request.user
    today = date_cls.today()
    month_start = today.replace(day=1)

    context = {"today": today, "month_start": month_start}

    if user.is_depot_manager or user.is_depot_officer:
        if user.depot_id:
            context["depot_today"] = services.get_daily_sales_report(user.depot, today)
            context["depot_net_profit"] = services.get_net_profit_report(user.depot, today, today)
        else:
            context["no_depot_assigned"] = True

    elif user.is_territory_manager:
        if user.territory_id:
            context["territory_comparison"] = services.get_territory_depot_comparison(
                user.territory, month_start, today
            )
        else:
            context["no_territory_assigned"] = True

    elif user.is_super_admin:
        context["all_territory_comparisons"] = [
            services.get_territory_depot_comparison(territory, month_start, today)
            for territory in Territory.objects.all().order_by("name")
        ]

    return render(request, "reports/dashboard.html", context)