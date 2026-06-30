import json
import threading
import traceback

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import close_old_connections
from django.utils import timezone

from core.management.commands.seed_sample_marketplace import (
    SAMPLE_JOB_PREFIX,
    SAMPLE_PRODUCT_PREFIX,
    SAMPLE_SURVEY_PREFIX,
)
from jobs.models import ChatProfile, Job
from products.models import Product
from support.models import FAQ, PolicyPage
from .models import AuditLog, SiteSetting
from .services import create_audit_log


SEED_STATUS_KEY = "bulk-content-seed-status"
DEFAULT_BULK_SEED_TARGETS = {
    "jobs": 10000,
    "surveys": 10000,
    "products": 10000,
}

_seed_thread = None
_seed_lock = threading.Lock()


def content_seed_counts():
    return {
        "jobs": Job.objects.filter(slug__startswith=SAMPLE_JOB_PREFIX).count(),
        "surveys": Job.objects.filter(slug__startswith=SAMPLE_SURVEY_PREFIX).count(),
        "products": Product.objects.filter(slug__startswith=SAMPLE_PRODUCT_PREFIX).count(),
        "policies": PolicyPage.objects.filter(is_published=True).count(),
        "faqs": FAQ.objects.filter(is_published=True).count(),
        "chat_profiles": ChatProfile.objects.filter(is_active=True).count(),
    }


def seed_status_default():
    return {
        "status": "idle",
        "message": "Content seeding has not been started.",
        "counts": content_seed_counts(),
        "updated_at": None,
    }


def get_seed_status():
    setting = SiteSetting.objects.filter(key=SEED_STATUS_KEY).first()
    if not setting or not setting.value:
        return seed_status_default()
    try:
        data = json.loads(setting.value)
    except json.JSONDecodeError:
        return seed_status_default()
    data.setdefault("counts", content_seed_counts())
    return data


def write_seed_status(*, status, message, actor=None, targets=None, error=""):
    data = {
        "status": status,
        "message": message,
        "targets": targets or DEFAULT_BULK_SEED_TARGETS,
        "counts": content_seed_counts(),
        "error": error,
        "updated_at": timezone.now().isoformat(),
    }
    setting, _ = SiteSetting.objects.update_or_create(
        key=SEED_STATUS_KEY,
        defaults={
            "label": "Bulk content seed status",
            "group": "automation",
            "value_type": SiteSetting.ValueType.JSON,
            "value": json.dumps(data),
            "description": "Tracks the admin-triggered jobs, products, FAQs, policies, and chat profile seeding task.",
            "is_sensitive": False,
            "updated_by": actor,
        },
    )
    return setting


def run_bulk_content_seed(*, jobs=None, surveys=None, products=None, batch_size=1000, reset_marketplace=False, actor_id=None):
    User = get_user_model()
    actor = User.objects.filter(pk=actor_id).first() if actor_id else None
    targets = {
        "jobs": max(int(jobs if jobs is not None else DEFAULT_BULK_SEED_TARGETS["jobs"]), 0),
        "surveys": max(int(surveys if surveys is not None else DEFAULT_BULK_SEED_TARGETS["surveys"]), 0),
        "products": max(int(products if products is not None else DEFAULT_BULK_SEED_TARGETS["products"]), 0),
    }
    write_seed_status(
        status="running",
        message="Adding jobs, surveys, products, policies, FAQs, and chat profiles.",
        actor=actor,
        targets=targets,
    )
    try:
        call_command(
            "seed_sample_marketplace",
            jobs=targets["jobs"],
            surveys=targets["surveys"],
            products=targets["products"],
            batch_size=max(int(batch_size), 1),
            reset=reset_marketplace,
        )
        call_command("seed_support_content", updated_by=actor.username if actor else "")
        call_command("seed_chat_profiles")
        setting = write_seed_status(
            status="completed",
            message="Content seeding completed.",
            actor=actor,
            targets=targets,
        )
        create_audit_log(
            action=AuditLog.Action.SYSTEM,
            actor=actor,
            instance=setting,
            changes={"status": "completed", "targets": targets},
            metadata={"counts": content_seed_counts()},
        )
    except Exception as exc:
        error = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        write_seed_status(
            status="failed",
            message="Content seeding failed. Check application logs before trying again.",
            actor=actor,
            targets=targets,
            error=error,
        )
        raise


def start_bulk_content_seed(*, actor_id, jobs=None, surveys=None, products=None, batch_size=1000):
    global _seed_thread
    if _seed_thread and _seed_thread.is_alive():
        return False

    def worker():
        if not _seed_lock.acquire(blocking=False):
            return
        try:
            close_old_connections()
            run_bulk_content_seed(
                jobs=jobs,
                surveys=surveys,
                products=products,
                batch_size=batch_size,
                actor_id=actor_id,
            )
        finally:
            close_old_connections()
            _seed_lock.release()

    _seed_thread = threading.Thread(target=worker, name="bulk-content-seed", daemon=True)
    _seed_thread.start()
    return True
