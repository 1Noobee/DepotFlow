from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

_PERMISSION_FIELDS = ["role", "depot_id", "territory_id", "is_active", "is_staff", "is_superuser"]


def _permission_snapshot(instance):
    return {field: str(getattr(instance, field)) for field in _PERMISSION_FIELDS}


@receiver(pre_save, sender=get_user_model())
def capture_user_before_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._pre_save_permission_snapshot = _permission_snapshot(sender.objects.get(pk=instance.pk))
        except sender.DoesNotExist:
            instance._pre_save_permission_snapshot = None
    else:
        instance._pre_save_permission_snapshot = None


@receiver(post_save, sender=get_user_model())
def log_user_permission_change(sender, instance, created, **kwargs):
    if created:
        return

    from core.audit import log_action
    from core.models import AuditLog

    old_snapshot = getattr(instance, "_pre_save_permission_snapshot", None)
    new_snapshot = _permission_snapshot(instance)

    if old_snapshot is not None and old_snapshot != new_snapshot:
        log_action(
            AuditLog.Action.PERMISSION_CHANGE,
            obj=instance,
            old_value=old_snapshot,
            new_value=new_snapshot,
        )