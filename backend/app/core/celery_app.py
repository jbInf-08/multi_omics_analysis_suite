"""
Celery Application Configuration
================================

Background task processing with Celery.
"""

from celery import Celery

from backend.app.core.config import settings


# Create Celery application
celery_app = Celery(
    "multi_omics_suite",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "backend.app.tasks.analysis_tasks",
        "backend.app.tasks.ml_tasks",
        "backend.app.tasks.data_tasks",
        "backend.app.tasks.integration_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_max_memory_per_child=512000,  # 512 MB
    
    # Result backend settings
    result_expires=86400,  # 24 hours
    result_extended=True,
    
    # Task routes
    task_routes={
        "backend.app.tasks.analysis_tasks.*": {"queue": "analysis"},
        "backend.app.tasks.ml_tasks.*": {"queue": "ml"},
        "backend.app.tasks.data_tasks.*": {"queue": "data"},
        "backend.app.tasks.integration_tasks.*": {"queue": "integration"},
    },
    
    # Task default rate limit
    task_default_rate_limit="10/m",
    
    # Beat scheduler (for periodic tasks)
    beat_schedule={
        "cleanup-old-results": {
            "task": "backend.app.tasks.data_tasks.cleanup_old_results",
            "schedule": 3600.0,  # Every hour
        },
        "update-data-sources": {
            "task": "backend.app.tasks.data_tasks.update_data_sources",
            "schedule": 86400.0,  # Daily
        },
    },
)


# Task base class with error handling
class OmicsTask(celery_app.Task):
    """Base task class with error handling and logging."""
    
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        print(f"Task {task_id} failed: {exc}")
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        print(f"Task {task_id} completed successfully")
        super().on_success(retval, task_id, args, kwargs)
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        print(f"Task {task_id} retrying: {exc}")
        super().on_retry(exc, task_id, args, kwargs, einfo)
