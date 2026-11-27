from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("inventory", "0011_single_receipt_price"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stockreceiptitem",
            name="cost_price",
            field=models.DecimalField(
                decimal_places=2,
                help_text=(
                    "Enter the current price per case from the NBC invoice (VAT included). "
                    "This becomes the depot's current selling price. If it differs from "
                    "the previous price, DepotFlow updates the current price and records "
                    "the change in the price history."
                ),
                max_digits=12,
                verbose_name="Current selling price",
            ),
        ),
        migrations.CreateModel(
            name="DepotPriceChange",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("previous_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("new_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("changed_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="depot_price_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "depot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="price_changes",
                        to="depots.depot",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="depot_price_changes",
                        to="inventory.product",
                    ),
                ),
                (
                    "stock_receipt",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="price_changes",
                        to="inventory.stockreceipt",
                    ),
                ),
            ],
            options={
                "verbose_name": "Depot price change",
                "verbose_name_plural": "Depot price changes",
                "ordering": ["-changed_at", "-pk"],
            },
        ),
        migrations.AddConstraint(
            model_name="depotpricechange",
            constraint=models.UniqueConstraint(
                fields=("stock_receipt", "product"),
                name="uniq_depot_price_change_receipt_product",
            ),
        ),
    ]
