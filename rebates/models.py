from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from core.models import TimeStampedModel
from depots.models import Depot
from inventory.models import Product, Supplier
from .scheme import CATEGORY_LABELS


class NBCQuarterlyPlacement(TimeStampedModel):
    class Category(models.TextChoices):
        STANDARD = 'STANDARD', 'Standard'
        MAXI = 'MAXI', 'Maxi'
        MEGA = 'MEGA', 'Mega'

    depot = models.ForeignKey(Depot, on_delete=models.PROTECT, related_name='nbc_placements')
    year = models.PositiveSmallIntegerField()
    quarter = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])
    qualifying_cases = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    category = models.CharField(max_length=12, choices=Category.choices, default=Category.STANDARD)
    calculated_at = models.DateTimeField(default=timezone.now)
    calculated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-year', '-quarter', 'depot__name']
        constraints = [models.UniqueConstraint(fields=['depot', 'year', 'quarter'], name='uniq_nbc_depot_year_quarter')]

    def __str__(self):
        return f'{self.depot} — {self.year} Q{self.quarter}: {self.get_category_display()}'

    @staticmethod
    def category_for_volume(cases):
        cases = Decimal(cases or 0)
        if cases > Decimal('40000'):
            return NBCQuarterlyPlacement.Category.MEGA
        if cases > Decimal('12000'):
            return NBCQuarterlyPlacement.Category.MAXI
        return NBCQuarterlyPlacement.Category.STANDARD


class MonthlyRebateAccrual(TimeStampedModel):
    """Calculated monthly NBC rebate estimate, separated from cash actually received."""
    class Status(models.TextChoices):
        ESTIMATED = 'ESTIMATED', 'Estimated'
        CONFIRMED = 'CONFIRMED', 'Confirmed by NBC'
        PAID = 'PAID', 'Paid'
        VOID = 'VOID', 'Voided'

    depot = models.ForeignKey(Depot, on_delete=models.PROTECT, related_name='monthly_rebate_accruals')
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='monthly_rebate_accruals')
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    product_category = models.CharField(max_length=80)
    qualifying_cases = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    landing_cost_total = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    rebate_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0, help_text='Percentage, e.g. 8.0000 means 8%.')
    estimated_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ESTIMATED)
    placement = models.ForeignKey(NBCQuarterlyPlacement, on_delete=models.PROTECT, null=True, blank=True, related_name='monthly_accruals')
    calculation_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-year', '-month', 'product_category']
        constraints = [models.UniqueConstraint(fields=['depot', 'year', 'month', 'product_category'], name='uniq_monthly_rebate_category')]

    def __str__(self):
        return f'{self.depot} {self.year}-{self.month:02d} {self.product_category}: ₦{self.estimated_amount}'

    @property
    def category_label(self):
        return CATEGORY_LABELS.get(self.product_category, self.product_category)


class MonthlyHealthCheck(TimeStampedModel):
    depot = models.ForeignKey(Depot, on_delete=models.PROTECT, related_name='monthly_health_checks')
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    grand_total_stock_cases = models.DecimalField(max_digits=14, decimal_places=2, default=0, help_text='Stock quantity in cases, as shown beside the stock value on the health-check sheet.')
    grand_total_stock_value = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    cash_at_hand = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    git_order_released = models.DecimalField(max_digits=16, decimal_places=2, default=0, help_text='Goods in transit / order released value.')
    credit_exposure_balance = models.DecimalField(max_digits=16, decimal_places=2, default=0, help_text='Enter exactly as it appears on the health-check sheet (a negative figure is allowed).')
    nbc_credit_limit = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    nbc_permanent_credit = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    operator_equity_contribution_percent = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    empties_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    plastic_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    empties_value = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    bank_balance = models.DecimalField(max_digits=16, decimal_places=2, default=0, help_text='Manually entered from the monthly Distribution Manager health check.')
    notes = models.TextField(blank=True)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    completed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-year', '-month', 'depot__name']
        constraints = [models.UniqueConstraint(fields=['depot', 'year', 'month'], name='uniq_health_check_depot_month')]

    @property
    def expected_nbc_rebate(self):
        """Expected rebate from the existing monthly segment/category calculations."""
        total = MonthlyRebateAccrual.objects.filter(
            depot=self.depot, year=self.year, month=self.month
        ).exclude(status=MonthlyRebateAccrual.Status.VOID).aggregate(
            total=models.Sum('estimated_amount')
        )['total']
        return total or Decimal('0.00')

    @property
    def actual_nbc_rebate(self):
        """Actual NBC rebate cash recorded for the health-check month."""
        from datetime import date
        from finance.models import SupplierRebate
        start = date(self.year, self.month, 1)
        end = date(self.year + (self.month == 12), (self.month % 12) + 1, 1)
        records = SupplierRebate.objects.filter(
            (Q(supplier__name__icontains='NBC') | Q(supplier__name__icontains='Nigerian Bottling Company')),
            depot=self.depot,
            rebate_date__gte=start,
            rebate_date__lt=end,
        )
        # Some project versions expose is_reversed on the ledger record; retain
        # compatibility with versions where reversal is represented elsewhere.
        if any(field.name == 'is_reversed' for field in SupplierRebate._meta.get_fields()):
            records = records.filter(is_reversed=False)
        total = records.aggregate(total=models.Sum('amount'))['total']
        return total or Decimal('0.00')

    @property
    def previous_month_health_check(self):
        """Most recent earlier health check, used as the reinvestment baseline."""
        return MonthlyHealthCheck.objects.filter(
            depot=self.depot,
        ).filter(
            Q(year__lt=self.year) | Q(year=self.year, month__lt=self.month)
        ).order_by('-year', '-month').first()

    @property
    def working_capital_change(self):
        """Change in total working capital versus the preceding saved health check."""
        previous = self.previous_month_health_check
        if previous is None:
            return None
        return self.total_working_capital - previous.total_working_capital

    @property
    def total_working_capital(self):
        # Working capital includes the operator's resources and NBC credit facility.
        return self.grand_total_stock_value + self.cash_at_hand + self.bank_balance + self.git_order_released + self.nbc_permanent_credit

    @property
    def nbc_credit_utilization_percent(self):
        if not self.nbc_credit_limit:
            return None
        return (self.credit_exposure_balance / self.nbc_credit_limit) * Decimal('100')

    @property
    def operator_owned_working_capital(self):
        # Matches the health-check sheet: total working capital less the NBC
        # credit position (permanent credit and the credit exposure balance).
        return self.total_working_capital - self.nbc_permanent_credit - self.credit_exposure_balance

    @property
    def operator_equity_percent(self):
        # Operator-owned working capital as a share of total working capital.
        if not self.total_working_capital:
            return None
        return (self.operator_owned_working_capital / self.total_working_capital) * Decimal('100')


class MonthlyProfitability(TimeStampedModel):
    """Month-end reinvestment target for a depot.

    Profit is derived from actual NBC rebates received minus recognised
    business expenses. Reinvestment is inferred from month-to-month working
    capital movement recorded by the monthly health checks.
    """
    depot = models.ForeignKey(Depot, on_delete=models.PROTECT, related_name='monthly_profitability_records')
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    target_reinvestment_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('20.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Minimum percentage of positive monthly net profit to reinvest.'
    )
    amount_reinvested = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text='Amount actually put back into the business during this month.'
    )
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-year', '-month', 'depot__name']
        constraints = [models.UniqueConstraint(fields=['depot', 'year', 'month'], name='uniq_profitability_depot_month')]

    def __str__(self):
        return f'{self.depot} — {self.year}-{self.month:02d} profitability'

    @property
    def nbc_rebates_received(self):
        from finance.models import SupplierRebate
        from datetime import date
        start = date(self.year, self.month, 1)
        end = date(self.year + (self.month == 12), (self.month % 12) + 1, 1)
        records = SupplierRebate.objects.filter(
            (Q(supplier__name__icontains='NBC') | Q(supplier__name__icontains='Nigerian Bottling Company')),
            depot=self.depot,
            rebate_date__gte=start,
            rebate_date__lt=end,
            is_reversed=False,
        )
        total = records.aggregate(total=models.Sum('amount'))['total']
        return total or Decimal('0.00')

    @property
    def expected_nbc_rebate(self):
        total = MonthlyRebateAccrual.objects.filter(
            depot=self.depot, year=self.year, month=self.month
        ).exclude(status=MonthlyRebateAccrual.Status.VOID).aggregate(
            total=models.Sum('estimated_amount')
        )['total']
        return total or Decimal('0.00')

    @property
    def recognised_expenses(self):
        from datetime import date
        from finance.models import Expense
        start = date(self.year, self.month, 1)
        end = date(self.year + (self.month == 12), (self.month % 12) + 1, 1)
        total = Expense.objects.filter(
            depot=self.depot,
            expense_date__gte=start,
            expense_date__lt=end,
            is_reversed=False,
        ).aggregate(total=models.Sum('amount'))['total']
        return total or Decimal('0.00')

    @property
    def net_profit(self):
        """Recognised profit is NBC rebates received less recognised expenses."""
        return self.nbc_rebates_received - self.recognised_expenses

    @property
    def required_reinvestment(self):
        if self.net_profit <= 0:
            return Decimal('0.00')
        return (self.net_profit * self.target_reinvestment_percent / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def health_check(self):
        return MonthlyHealthCheck.objects.filter(
            depot=self.depot, year=self.year, month=self.month
        ).first()

    @property
    def previous_health_check(self):
        return MonthlyHealthCheck.objects.filter(
            depot=self.depot,
        ).filter(
            Q(year__lt=self.year) | Q(year=self.year, month__lt=self.month)
        ).order_by('-year', '-month').first()

    @property
    def working_capital_change(self):
        current = self.health_check
        previous = self.previous_health_check
        if current is None or previous is None:
            return None
        return current.total_working_capital - previous.total_working_capital

    @property
    def observed_reinvestment(self):
        """Proxy for reinvestment: positive increase in working capital at month-end."""
        change = self.working_capital_change
        if change is None:
            return None
        return max(change, Decimal('0.00'))

    @property
    def actual_reinvestment_percent(self):
        if self.net_profit <= 0 or self.observed_reinvestment is None:
            return None
        return (self.observed_reinvestment / self.net_profit * Decimal('100')).quantize(Decimal('0.01'))

    @property
    def has_working_capital_baseline(self):
        return self.working_capital_change is not None

    @property
    def is_flagged(self):
        # Missing month-end baseline is pending, not an automatic failure.
        if not self.has_working_capital_baseline:
            return False
        if self.net_profit <= 0:
            return True
        return self.observed_reinvestment < self.required_reinvestment
