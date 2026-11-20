from django.core.management.base import BaseCommand, CommandError
from depots.models import Depot
from rebates.services import calculate_quarterly_placement, calculate_monthly_rebates

class Command(BaseCommand):
    help = 'Calculate NBC quarterly placement and monthly rebate estimates for a depot.'
    def add_arguments(self, parser):
        parser.add_argument('--depot-code', required=True)
        parser.add_argument('--year', type=int, required=True)
        parser.add_argument('--month', type=int, required=True)
    def handle(self, *args, **opts):
        if not 1 <= opts['month'] <= 12:
            raise CommandError('--month must be between 1 and 12')
        try:
            depot = Depot.objects.get(code=opts['depot_code'])
        except Depot.DoesNotExist:
            raise CommandError('No depot found with that code')
        quarter = ((opts['month'] - 1) // 3) + 1
        placement = calculate_quarterly_placement(depot, opts['year'], quarter)
        records = calculate_monthly_rebates(depot, opts['year'], opts['month'])
        self.stdout.write(self.style.SUCCESS(f'{depot.name}: {placement.get_category_display()} placement, {len(records)} monthly category estimate(s).'))
