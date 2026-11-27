from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Retired: product prices are now updated through stock receipts."

    def handle(self, *args, **options):
        raise CommandError(
            "The update_prices command has been retired. "
            "Record a stock receipt with the new NBC price; DepotFlow will "
            "update the depot's current price and record the price change."
        )
