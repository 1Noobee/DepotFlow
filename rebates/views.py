from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from core.scoping import get_visible_depots, user_can_access_depot
from depots.models import Depot
from .forms import MonthlyHealthCheckForm, MonthlyProfitabilityForm
from .models import MonthlyHealthCheck, NBCQuarterlyPlacement, MonthlyRebateAccrual, MonthlyProfitability
from .services import calculate_quarterly_placement, calculate_monthly_rebates


def _can_manage(user):
    # Depot Owner restrictions take precedence over Django staff flags.
    if getattr(user, 'role', '') == 'DEPOT_OWNER':
        return False
    return user.is_staff or getattr(user, 'role', '') in ('SUPER_ADMIN', 'DEPOT_MANAGER', 'FINANCE_OFFICER')


def _can_manage_profitability(user):
    # Reinvestment targets are a Commercial Manager control; Super Admin
    # retains unrestricted oversight. Depot Owner/staff flags do not bypass it.
    role = getattr(user, 'role', '')
    return bool(getattr(user, 'is_superuser', False) or role in ('SUPER_ADMIN', 'TERRITORY_MANAGER'))

@login_required
def dashboard(request):
    depots = get_visible_depots(request.user)
    checks = MonthlyHealthCheck.objects.filter(depot__in=depots).select_related('depot')[:24]
    placements = NBCQuarterlyPlacement.objects.filter(depot__in=depots).select_related('depot')[:24]
    accruals = MonthlyRebateAccrual.objects.filter(depot__in=depots).select_related('depot', 'supplier')[:40]
    profitability_records = MonthlyProfitability.objects.filter(depot__in=depots).select_related('depot', 'recorded_by')[:24]
    latest_checks_by_depot = {}
    for check in MonthlyHealthCheck.objects.filter(depot__in=depots).select_related('depot').order_by('depot_id', '-year', '-month'):
        latest_checks_by_depot.setdefault(check.depot_id, check)
    return render(request, 'rebates/dashboard.html', {
        'checks': checks,
        'placements': placements,
        'accruals': accruals,
        'profitability_records': profitability_records,
        'latest_checks_by_depot': latest_checks_by_depot.values(),
        'can_manage': _can_manage(request.user),
        'can_manage_profitability': _can_manage_profitability(request.user),
        'visible_depots': depots,
        'now': timezone.localdate(),
    })

@login_required
def health_check_create(request):
    if not _can_manage(request.user):
        messages.error(request, 'You do not have permission to submit monthly health checks.')
        return redirect('rebates:dashboard')
    if request.method == 'POST':
        form = MonthlyHealthCheckForm(request.POST, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            if not user_can_access_depot(request.user, obj.depot):
                messages.error(request, 'You cannot submit a health check for that depot.')
                return redirect('rebates:dashboard')
            obj.completed_by = request.user
            obj.save()
            messages.success(request, 'Monthly health check saved.')
            return redirect('rebates:dashboard')
    else:
        now = timezone.localdate()
        form = MonthlyHealthCheckForm(initial={'year': now.year, 'month': now.month}, user=request.user)
    return render(request, 'rebates/health_check_form.html', {'form': form})

@login_required
def calculate(request):
    if request.method != 'POST' or not _can_manage(request.user):
        messages.error(request, 'Only authorised managers can calculate rebates.')
        return redirect('rebates:dashboard')
    try:
        depot = Depot.objects.get(pk=request.POST.get('depot'), pk__in=get_visible_depots(request.user).values('pk'))
        year, month = int(request.POST.get('year')), int(request.POST.get('month'))
        if month < 1 or month > 12: raise ValueError('Month must be between 1 and 12.')
        calculate_quarterly_placement(depot, year, ((month - 1) // 3) + 1, request.user)
        calculate_monthly_rebates(depot, year, month, request.user)
        messages.success(request, 'Quarterly placement and monthly rebate estimates have been recalculated from NBC purchase records.')
    except (ValueError, Depot.DoesNotExist) as exc:
        messages.error(request, str(exc) or 'Select an accessible depot and valid period.')
    return redirect('rebates:dashboard')


@login_required
def profitability_update(request):
    # Distribution Manager and every management level above it may set
    # depot reinvestment targets.
    if not _can_manage_profitability(request.user):
        messages.error(request, 'Only the Commercial Manager and Super Admin can manage reinvestment targets.')
        return redirect('rebates:dashboard')

    if request.method == 'POST':
        form = MonthlyProfitabilityForm(request.POST, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            if not user_can_access_depot(request.user, obj.depot):
                messages.error(request, 'You cannot manage profitability for that depot.')
                return redirect('rebates:dashboard')
            existing = MonthlyProfitability.objects.filter(depot=obj.depot, year=obj.year, month=obj.month).first()
            if existing:
                obj.pk = existing.pk
                obj.created_at = existing.created_at
            obj.recorded_by = request.user
            obj.save()
            messages.success(request, 'Monthly profitability target and reinvestment amount saved. Depot status has been recalculated.')
            return redirect('rebates:dashboard')
    else:
        today = timezone.localdate()
        # The previous month is the natural default because this is a month-end review.
        default_year = today.year if today.month > 1 else today.year - 1
        default_month = today.month - 1 if today.month > 1 else 12
        try:
            year = int(request.GET.get('year', default_year))
            month = int(request.GET.get('month', default_month))
            if year < 2000 or year > 2100 or month < 1 or month > 12:
                raise ValueError
        except (TypeError, ValueError):
            year, month = default_year, default_month
        initial = {'year': year, 'month': month}
        depot_id = request.GET.get('depot')
        if depot_id:
            existing = MonthlyProfitability.objects.filter(depot_id=depot_id, depot__in=get_visible_depots(request.user), year=year, month=month).first()
            if existing:
                form = MonthlyProfitabilityForm(instance=existing, user=request.user)
            else:
                initial['depot'] = depot_id
                form = MonthlyProfitabilityForm(initial=initial, user=request.user)
        else:
            form = MonthlyProfitabilityForm(initial=initial, user=request.user)
    return render(request, 'rebates/profitability_form.html', {'form': form})
