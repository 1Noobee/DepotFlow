from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from core.scoping import get_visible_depots, get_visible_territories, user_can_access_depot
from .models import Territory, Depot
from .forms import TerritoryForm, DepotForm


def _can_manage_depots(user):
    """
    Only staff or SUPER_ADMIN-role users can create/edit territories
    and depots; everyone else can view whatever core.scoping says
    is visible to them.
    """

    return user.is_staff or getattr(user, "role", "") == "SUPER_ADMIN"


@login_required
def territory_list(request):
    territories = get_visible_territories(request.user).order_by("name")
    return render(request, "depots/territory_list.html", {"territories": territories})


@login_required
def territory_create(request):
    if not _can_manage_depots(request.user):
        messages.error(request, "You do not have permission to create territories.")
        return redirect("depots:territory_list")

    if request.method == "POST":
        form = TerritoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Territory created.")
            return redirect("depots:territory_list")
    else:
        form = TerritoryForm()

    return render(request, "depots/territory_form.html", {"form": form, "title": "New Territory"})


@login_required
def territory_update(request, pk):
    territory = get_object_or_404(Territory, pk=pk)

    if not _can_manage_depots(request.user):
        messages.error(request, "You do not have permission to edit territories.")
        return redirect("depots:territory_list")

    if request.method == "POST":
        form = TerritoryForm(request.POST, instance=territory)
        if form.is_valid():
            form.save()
            messages.success(request, "Territory updated.")
            return redirect("depots:territory_list")
    else:
        form = TerritoryForm(instance=territory)

    return render(request, "depots/territory_form.html", {"form": form, "title": "Edit Territory"})


@login_required
def depot_list(request):
    depots = get_visible_depots(request.user).select_related("territory").order_by("name")
    return render(request, "depots/depot_list.html", {"depots": depots})


@login_required
def depot_detail(request, pk):
    depot = get_object_or_404(Depot.objects.select_related("territory"), pk=pk)

    if not user_can_access_depot(request.user, depot):
        messages.error(request, "You do not have access to that depot.")
        return redirect("depots:depot_list")

    return render(request, "depots/depot_detail.html", {"depot": depot})


@login_required
def depot_create(request):
    if not _can_manage_depots(request.user):
        messages.error(request, "You do not have permission to create depots.")
        return redirect("depots:depot_list")

    if request.method == "POST":
        form = DepotForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Depot created.")
            return redirect("depots:depot_list")
    else:
        form = DepotForm()

    return render(request, "depots/depot_form.html", {"form": form, "title": "New Depot"})


@login_required
def depot_update(request, pk):
    depot = get_object_or_404(Depot, pk=pk)

    if not _can_manage_depots(request.user):
        messages.error(request, "You do not have permission to edit depots.")
        return redirect("depots:depot_list")

    if request.method == "POST":
        form = DepotForm(request.POST, instance=depot)
        if form.is_valid():
            form.save()
            messages.success(request, "Depot updated.")
            return redirect("depots:depot_list")
    else:
        form = DepotForm(instance=depot)

    return render(request, "depots/depot_form.html", {"form": form, "title": "Edit Depot"})