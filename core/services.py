from django.forms.models import model_to_dict

from .models import AuditLog, FinanceSettings


def get_client_ip(request):
    if not request:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def create_audit_log(
    *,
    action,
    actor=None,
    instance=None,
    changes=None,
    metadata=None,
    request=None,
):
    model_label = ""
    object_id = ""
    object_repr = ""
    if instance is not None:
        model_label = instance._meta.label
        object_id = str(instance.pk or "")
        object_repr = str(instance)

    return AuditLog.objects.create(
        actor=actor,
        action=action,
        model_label=model_label,
        object_id=object_id,
        object_repr=object_repr,
        changes=changes or {},
        metadata=metadata or {},
        ip_address=get_client_ip(request),
    )


def finance_settings_snapshot(instance):
    data = model_to_dict(instance)
    data.pop("updated_by", None)
    return {key: str(value) for key, value in data.items()}


def get_finance_settings():
    return FinanceSettings.load()
