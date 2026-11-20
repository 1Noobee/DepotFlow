from django.core.management.base import BaseCommand
from django.utils import timezone
from finance.models import BankConnection
from finance.banking.sync import sync_mono_connection
from finance.banking.mono import MonoAPIError

class Command(BaseCommand):
    help = "Synchronise active DepotFlow bank connections (schedule periodically in production)."

    def handle(self, *args, **options):
        connections = BankConnection.objects.filter(
            provider=BankConnection.Provider.MONO,
            status__in=[BankConnection.Status.ACTIVE, BankConnection.Status.ERROR],
        ).exclude(provider_account_id="")
        total = 0
        for connection in connections.iterator():
            try:
                count = sync_mono_connection(connection)
                total += count
                self.stdout.write(self.style.SUCCESS(f"Connection {connection.pk}: imported {count} new transactions"))
            except MonoAPIError as exc:
                connection.status = BankConnection.Status.ERROR
                connection.last_sync_error = str(exc)[:500]
                connection.save(update_fields=["status", "last_sync_error", "updated_at"])
                self.stderr.write(self.style.ERROR(f"Connection {connection.pk}: sync failed: {exc}"))
        self.stdout.write(self.style.SUCCESS(f"Sync complete; {total} new transactions imported at {timezone.now().isoformat()}"))
