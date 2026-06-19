from django.forms.models import model_to_dict

from .models import AuditLog


def snapshot_instance(instance, fields):
    if not instance.pk:
        return {}
    current = instance.__class__.objects.get(pk=instance.pk)
    return model_to_dict(current, fields=fields)


def write_audit_logs(user, instance, before, fields):
    for field in fields:
        old_value = before.get(field)
        new_value = getattr(instance, field)
        if hasattr(new_value, "pk"):
            new_value = new_value.pk
        if str(old_value or "") != str(new_value or ""):
            AuditLog.objects.create(
                user=user,
                model_name=instance.__class__.__name__,
                object_id=str(instance.pk),
                field_name=field,
                old_value=str(old_value or ""),
                new_value=str(new_value or ""),
            )
