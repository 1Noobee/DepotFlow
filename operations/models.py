from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from core.models import TimeStampedModel
from depots.models import Depot
from inventory.models import Product, InventoryTransaction
from inventory.services import (
    get_current_acquisition_cost,
    get_current_selling_price,
    get_stock_balance,
)


class Vehicle(TimeStampedModel):
    """
    Represents a sales/distribution vehicle assigned to a depot.
    """

    depot = models.ForeignKey(
        Depot,
        on_delete=models.PROTECT,
        related_name="vehicles"
    )

    registration_number = models.CharField(
        max_length=30,
        unique=True
    )

    vehicle_name = models.CharField(
        max_length=100
    )

    capacity = models.PositiveIntegerField(
        default=0,
        help_text="Maximum number of units the vehicle can carry."
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["registration_number"]

    def __str__(self):
        return f"{self.registration_number} - {self.vehicle_name}"


class VehicleSalesman(TimeStampedModel):
    """
    Represents a salesman who operates a vehicle from a depot.
    """

    name = models.CharField(
        max_length=150
    )

    employee_id = models.CharField(
        max_length=50,
        unique=True
    )

    phone = models.CharField(
        max_length=20,
        blank=True
    )

    depot = models.ForeignKey(
        Depot,
        on_delete=models.PROTECT,
        related_name="salesmen"
    )

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name="salesmen",
        null=True,
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.employee_id})"


class VehicleLoad(TimeStampedModel):
    """
    Represents products loaded from a depot onto a salesman's vehicle.
    """

    salesman = models.ForeignKey(
        VehicleSalesman,
        on_delete=models.PROTECT,
        related_name="vehicle_loads"
    )

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name="loads"
    )

    depot = models.ForeignKey(
        Depot,
        on_delete=models.PROTECT,
        related_name="vehicle_loads"
    )

    load_number = models.CharField(
        max_length=50,
        unique=True
    )

    load_date = models.DateField(
        default=timezone.now
    )

    is_closed = models.BooleanField(
        default=False
    )

    closed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    notes = models.TextField(
        blank=True
    )

    class Meta:
        ordering = ["-load_date", "-created_at"]

    def __str__(self):
        return f"{self.load_number} - {self.salesman.name}"

    def clean(self):
        if self.salesman.depot_id != self.depot_id:
            raise ValidationError(
                "The salesman does not belong to the selected depot."
            )

        if self.vehicle.depot_id != self.depot_id:
            raise ValidationError(
                "The vehicle does not belong to the selected depot."
            )

        if (
            self.salesman.vehicle_id
            and self.salesman.vehicle_id != self.vehicle_id
        ):
            raise ValidationError(
                "The selected vehicle is not assigned to this salesman."
            )

    def close_load(self):
        """
        Close the load so that it can no longer be modified.
        """

        if self.is_closed:
            raise ValidationError(
                "This vehicle load is already closed."
            )

        self.is_closed = True
        self.closed_at = timezone.now()

        self.save(
            update_fields=[
                "is_closed",
                "closed_at",
                "updated_at"
            ]
        )


class VehicleLoadItem(TimeStampedModel):
    """
    Individual product loaded onto a salesman's vehicle.

    cost_price and selling_price are a point-in-time snapshot of
    what the effective prices were AT LOAD TIME, kept purely for
    audit/reference — they are NOT used in expected_revenue/cost/
    profit below. This stock has not been sold yet, so expected
    profit tracks CURRENT effective pricing (current PriceHistory
    selling price, current recorded acquisition cost) per the
    finalized pricing decision (section 8: "current expected profit
    uses the current effective selling price against the relevant
    recorded acquisition cost"). When an actual sale transaction is
    recorded in the future, THAT record must snapshot and freeze
    the price actually used — this load item does not.
    """

    vehicle_load = models.ForeignKey(
        VehicleLoad,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="vehicle_load_items"
    )

    quantity = models.PositiveIntegerField()

    # Historical snapshot only.
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    # Historical snapshot only.
    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    # Customer/depot promotion applied to selling price.
    promo_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["vehicle_load", "product"],
                name="unique_product_per_vehicle_load"
            )
        ]

    def __str__(self):
        return f"{self.product.name} ({self.quantity})"

    @property
    def effective_cost_price(self):
        """
        Current acquisition cost for this product at this depot
        (live lookup — see inventory.services.get_current_acquisition_cost).
        This is stock that hasn't been sold yet, so per the
        finalized pricing decision it tracks current values, not
        the load-time snapshot.
        """

        cost = get_current_acquisition_cost(
            self.vehicle_load.depot,
            self.product,
        )

        return max(cost, Decimal("0.00"))

    @property
    def effective_selling_price(self):
        """
        Current effective selling price for this product (live
        lookup from PriceHistory), minus any promo discount applied
        at load time. Tracks current pricing since this stock has
        not yet been sold.
        """

        price = get_current_selling_price(self.product) - self.promo_discount

        return max(price, Decimal("0.00"))

    @property
    def expected_revenue(self):
        return (
            self.effective_selling_price
            * self.quantity
        )

    @property
    def expected_cost(self):
        return (
            self.effective_cost_price
            * self.quantity
        )

    @property
    def expected_profit(self):
        return (
            self.expected_revenue
            - self.expected_cost
        )

    def clean(self):
        if self.vehicle_load.is_closed:
            raise ValidationError(
                "This vehicle load has already been closed "
                "and cannot be modified."
            )

        if self.quantity <= 0:
            raise ValidationError(
                "Quantity must be greater than zero."
            )

        if self.promo_discount < 0:
            raise ValidationError(
                "Promo discount cannot be negative."
            )

        current_selling_price = get_current_selling_price(self.product)

        if self.promo_discount > current_selling_price:
            raise ValidationError(
                "Promo discount cannot be greater than "
                "the current selling price."
            )

        if self.pk is None:
            available_stock = get_stock_balance(
                self.vehicle_load.depot,
                self.product,
            )

            if self.quantity > available_stock:
                raise ValidationError(
                    f"Insufficient stock for {self.product.name}. "
                    f"Available stock: {available_stock}. "
                    f"Requested quantity: {self.quantity}."
                )

    def save(self, *args, **kwargs):
        """
        Save the load item and create the corresponding inventory
        transaction.

        cost_price/selling_price are set here as a point-in-time
        AUDIT snapshot of what the effective prices were at the
        moment of loading. They are stored for reference only — the
        effective_cost_price/effective_selling_price properties
        above do NOT read from them; they look up current values
        live, since this stock has not been sold yet.

        The stock availability check lives in clean() (above), not
        here, so ModelForms/formsets report it as a normal
        validation error instead of raising mid-save.

        No FIFO/batch costing is used.
        """

        self.full_clean()

        is_new = self.pk is None

        with transaction.atomic():

            if is_new:

                # Snapshot the prices actually applicable at load time.
                self.cost_price = get_current_acquisition_cost(
                    self.vehicle_load.depot,
                    self.product,
                )
                self.selling_price = get_current_selling_price(self.product)

            super().save(*args, **kwargs)

            if is_new:
                InventoryTransaction.objects.create(
                    depot=self.vehicle_load.depot,
                    product=self.product,
                    transaction_type=(
                        InventoryTransaction
                        .TransactionType
                        .VEHICLE_LOAD
                    ),
                    quantity=-self.quantity,
                    unit_cost=self.cost_price,
                    reference=self.vehicle_load.load_number,
                    transaction_date=timezone.now(),
                )


class VehicleReturn(TimeStampedModel):
    """
    Represents products returned to the depot by a salesman
    after completing a vehicle load.
    """

    vehicle_load = models.ForeignKey(
        VehicleLoad,
        on_delete=models.PROTECT,
        related_name="returns"
    )

    return_number = models.CharField(
        max_length=50,
        unique=True
    )

    return_date = models.DateField(
        default=timezone.now
    )

    notes = models.TextField(
        blank=True
    )

    is_confirmed = models.BooleanField(
        default=False
    )

    confirmed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["-return_date", "-created_at"]

    def __str__(self):
        return (
            f"{self.return_number} - "
            f"{self.vehicle_load.load_number}"
        )

    def clean(self):
        if self.vehicle_load.is_closed and not self.is_confirmed:
            raise ValidationError(
                "The vehicle load is already closed."
            )

    def confirm_return(self):
        """
        Confirm the vehicle return.

        Once confirmed, return items cannot be modified.
        """

        if self.is_confirmed:
            raise ValidationError(
                "This return has already been confirmed."
            )

        self.full_clean()

        with transaction.atomic():
            self.is_confirmed = True
            self.confirmed_at = timezone.now()

            self.save(
                update_fields=[
                    "is_confirmed",
                    "confirmed_at",
                    "updated_at"
                ]
            )

            depot = self.vehicle_load.depot

            # Create inventory transactions for the returned items.
            for item in self.items.all():

                unit_cost = get_current_acquisition_cost(depot, item.product)

                if item.condition == "GOOD":

                    InventoryTransaction.objects.create(
                        depot=depot,
                        product=item.product,
                        transaction_type=(
                            InventoryTransaction
                            .TransactionType
                            .VEHICLE_RETURN
                        ),
                        quantity=item.quantity,
                        unit_cost=unit_cost,
                        reference=self.return_number,
                        transaction_date=timezone.now(),
                    )

                elif item.condition == "DAMAGED":

                    InventoryTransaction.objects.create(
                        depot=depot,
                        product=item.product,
                        transaction_type=(
                            InventoryTransaction
                            .TransactionType
                            .DAMAGE
                        ),
                        quantity=-item.quantity,
                        unit_cost=unit_cost,
                        reference=self.return_number,
                        transaction_date=timezone.now(),
                    )


class VehicleReturnItem(TimeStampedModel):
    """
    Individual products returned from a vehicle.
    """

    vehicle_return = models.ForeignKey(
        VehicleReturn,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="vehicle_return_items"
    )

    quantity = models.PositiveIntegerField()

    condition = models.CharField(
        max_length=20,
        choices=[
            ("GOOD", "Good"),
            ("DAMAGED", "Damaged"),
        ],
        default="GOOD"
    )

    notes = models.TextField(
        blank=True
    )

    def __str__(self):
        return f"{self.product.name} ({self.quantity})"

    def clean(self):
        if self.vehicle_return.is_confirmed:
            raise ValidationError(
                "This vehicle return has already been confirmed "
                "and cannot be modified."
            )

        if self.quantity <= 0:
            raise ValidationError(
                "Quantity must be greater than zero."
            )


def get_current_inventory_value(depot, product):
    """
    Calculate the current value of depot stock using the most
    recently recorded acquisition cost for this product at this
    depot (see inventory.services.get_current_acquisition_cost).

    This deliberately does NOT use FIFO. If a new receipt records a
    different cost, existing stock is valued using that new cost
    going forward — but historical stock RECEIPT transactions and
    stock RECEIPT items retain their own original recorded cost.
    """

    stock_quantity = get_stock_balance(depot, product)

    current_cost = get_current_acquisition_cost(depot, product)

    return Decimal(stock_quantity) * current_cost


def get_expected_profit_for_load(vehicle_load):
    """
    Calculate expected profit for the entire vehicle load using each
    item's current effective prices (this stock has not been sold
    yet, so the figure moves as PriceHistory/acquisition cost move).
    """

    total_profit = Decimal("0.00")

    for item in vehicle_load.items.all():
        total_profit += item.expected_profit

    return total_profit


def get_expected_revenue_for_load(vehicle_load):
    """
    Calculate expected revenue for the entire vehicle load using
    each item's current effective selling price.
    """

    total_revenue = Decimal("0.00")

    for item in vehicle_load.items.all():
        total_revenue += item.expected_revenue

    return total_revenue


def get_expected_cost_for_load(vehicle_load):
    """
    Calculate expected cost for the entire vehicle load using each
    item's current effective acquisition cost.
    """

    total_cost = Decimal("0.00")

    for item in vehicle_load.items.all():
        total_cost += item.expected_cost

    return total_cost