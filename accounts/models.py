from django.db import models
from django.contrib.auth.models import AbstractUser
from depots.models import Depot, Territory


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        TERRITORY_MANAGER = "TERRITORY_MANAGER", "Territory Manager"
        DEPOT_MANAGER = "DEPOT_MANAGER", "Depot Manager"
        DEPOT_OFFICER = "DEPOT_OFFICER", "Depot Officer"
        SALESMAN = "SALESMAN", "Salesman"
        FINANCE_OFFICER = "FINANCE_OFFICER", "Finance Officer"
        VIEWER = "VIEWER", "Viewer"

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.DEPOT_OFFICER
    )

    depot = models.ForeignKey(
        Depot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users"
    )

    territory = models.ForeignKey(
        Territory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users"
    )

    phone = models.CharField(
        max_length=20,
        blank=True
    )

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN

    @property
    def is_territory_manager(self):
        return self.role == self.Role.TERRITORY_MANAGER

    @property
    def is_depot_manager(self):
        return self.role == self.Role.DEPOT_MANAGER

    @property
    def is_depot_officer(self):
        return self.role == self.Role.DEPOT_OFFICER

    @property
    def is_salesman(self):
        return self.role == self.Role.SALESMAN

    @property
    def is_finance_officer(self):
        return self.role == self.Role.FINANCE_OFFICER

    @property
    def is_viewer(self):
        return self.role == self.Role.VIEWER