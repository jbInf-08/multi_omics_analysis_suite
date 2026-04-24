"""
Structured Logging & Observability
==================================

Centralized logging configuration with structlog, OpenTelemetry integration,
and custom metrics collection.
"""

import logging
import sys
from typing import Any, Dict, Optional
import structlog
from structlog.types import EventDict, Processor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from prometheus_client import Counter, Histogram, Gauge, Info
import time
from functools import wraps
from contextvars import ContextVar

from backend.app.core.config import settings


# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


# =============================================================================
# Prometheus Metrics
# =============================================================================

# Analysis metrics
ANALYSIS_QUEUE_DEPTH = Gauge(
    "omics_analysis_queue_depth",
    "Number of analyses in the queue",
    ["status"]
)

ANALYSIS_DURATION = Histogram(
    "omics_analysis_duration_seconds",
    "Time spent processing analyses",
    ["analysis_type", "omics_type"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
)

ANALYSIS_TOTAL = Counter(
    "omics_analysis_total",
    "Total number of analyses",
    ["analysis_type", "status"]
)

# API metrics
API_REQUEST_DURATION = Histogram(
    "omics_api_request_duration_seconds",
    "API request duration",
    ["method", "endpoint", "status_code"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
)

API_REQUESTS_TOTAL = Counter(
    "omics_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status_code"]
)

# Memory metrics
MEMORY_USAGE = Gauge(
    "omics_memory_usage_bytes",
    "Memory usage in bytes",
    ["component"]
)

# Application info
APP_INFO = Info("omics_app", "Application information")

# Database metrics
DB_CONNECTIONS = Gauge(
    "omics_db_connections",
    "Database connection pool status",
    ["status"]
)

# Celery metrics
CELERY_TASK_DURATION = Histogram(
    "omics_celery_task_duration_seconds",
    "Celery task duration",
    ["task_name", "status"],
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600]
)

CELERY_TASKS_TOTAL = Counter(
    "omics_celery_tasks_total",
    "Total Celery tasks",
    ["task_name", "status"]
)


# =============================================================================
# Structlog Configuration
# =============================================================================

def add_request_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: EventDict
) -> EventDict:
    """Add request context to log entries."""
    request_id = request_id_var.get()
    user_id = user_id_var.get()
    
    if request_id:
        event_dict["request_id"] = request_id
    if user_id:
        event_dict["user_id"] = user_id
    
    return event_dict


def add_trace_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: EventDict
) -> EventDict:
    """Add OpenTelemetry trace context to log entries."""
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def configure_logging(
    log_level: str = "INFO",
    json_logs: bool = True,
    log_file: Optional[str] = None,
) -> None:
    """Configure structured logging with structlog."""
    
    # Shared processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        add_request_context,
        add_trace_context,
    ]
    
    # Development vs Production formatting
    if json_logs:
        # Production: JSON format
        shared_processors.append(structlog.processors.format_exc_info)
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        # Development: Console format with colors
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Configure file logging if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        logging.getLogger().addHandler(file_handler)
    
    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name)


# =============================================================================
# OpenTelemetry Configuration
# =============================================================================

def configure_tracing(
    service_name: str = "multi-omics-suite",
    otlp_endpoint: Optional[str] = None,
) -> None:
    """Configure OpenTelemetry distributed tracing."""
    
    # Create resource with service information
    resource = Resource.create({
        "service.name": service_name,
        "service.version": settings.VERSION if hasattr(settings, 'VERSION') else "1.0.0",
        "deployment.environment": settings.ENVIRONMENT if hasattr(settings, 'ENVIRONMENT') else "development",
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Add OTLP exporter if endpoint is configured
    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # Set global tracer provider
    trace.set_tracer_provider(provider)


def instrument_app(app) -> None:
    """Instrument the FastAPI application with OpenTelemetry."""
    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    
    # Instrument SQLAlchemy (if using)
    try:
        SQLAlchemyInstrumentor().instrument()
    except Exception:
        pass
    
    # Instrument Redis
    try:
        RedisInstrumentor().instrument()
    except Exception:
        pass
    
    # Instrument Celery
    try:
        CeleryInstrumentor().instrument()
    except Exception:
        pass


# =============================================================================
# Metrics Decorators
# =============================================================================

def track_analysis_time(analysis_type: str, omics_type: str = "unknown"):
    """Decorator to track analysis execution time."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                ANALYSIS_DURATION.labels(
                    analysis_type=analysis_type,
                    omics_type=omics_type
                ).observe(duration)
                ANALYSIS_TOTAL.labels(
                    analysis_type=analysis_type,
                    status=status
                ).inc()
        return wrapper
    return decorator


def track_celery_task(task_name: str):
    """Decorator to track Celery task execution."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = func(*args, **kwargs)
                return result
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                CELERY_TASK_DURATION.labels(
                    task_name=task_name,
                    status=status
                ).observe(duration)
                CELERY_TASKS_TOTAL.labels(
                    task_name=task_name,
                    status=status
                ).inc()
        return wrapper
    return decorator


# =============================================================================
# Middleware for Request Tracking
# =============================================================================

class LoggingMiddleware:
    """Middleware for request logging and metrics."""
    
    def __init__(self, app):
        self.app = app
        self.logger = get_logger("api")
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)
        
        start_time = time.time()
        status_code = 500
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start_time
            
            method = scope.get("method", "UNKNOWN")
            path = scope.get("path", "/")
            
            # Record metrics
            API_REQUEST_DURATION.labels(
                method=method,
                endpoint=path,
                status_code=status_code
            ).observe(duration)
            
            API_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=path,
                status_code=status_code
            ).inc()
            
            # Log request
            self.logger.info(
                "request_completed",
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=round(duration * 1000, 2),
            )


# =============================================================================
# Health & Metrics Utilities
# =============================================================================

def update_app_info():
    """Update application info metric."""
    APP_INFO.info({
        "version": settings.VERSION if hasattr(settings, 'VERSION') else "1.0.0",
        "environment": settings.ENVIRONMENT if hasattr(settings, 'ENVIRONMENT') else "development",
    })


def update_memory_metrics():
    """Update memory usage metrics."""
    import psutil
    process = psutil.Process()
    
    MEMORY_USAGE.labels(component="rss").set(process.memory_info().rss)
    MEMORY_USAGE.labels(component="vms").set(process.memory_info().vms)


def update_analysis_queue_metrics(pending: int, running: int, completed: int, failed: int):
    """Update analysis queue depth metrics."""
    ANALYSIS_QUEUE_DEPTH.labels(status="pending").set(pending)
    ANALYSIS_QUEUE_DEPTH.labels(status="running").set(running)
    ANALYSIS_QUEUE_DEPTH.labels(status="completed").set(completed)
    ANALYSIS_QUEUE_DEPTH.labels(status="failed").set(failed)
