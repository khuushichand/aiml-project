"""
OpenTelemetry configuration and initialization for unified metrics.

This module provides centralized telemetry configuration supporting:
- Metrics collection and export
- Distributed tracing
- Log correlation
- Multiple export backends (OTLP, Prometheus, Jaeger)
"""

import inspect
import os
import socket
from contextlib import contextmanager
from typing import Any, Optional

from loguru import logger


# Fallback implementations used when telemetry init fails or OTel is missing.
class DummySpan:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def set_attribute(self, key, value):
        pass
    def set_status(self, status):
        pass
    def add_event(self, name, attributes=None):
        pass
    def record_exception(self, exception):
        pass


class DummyTracer:
    def start_span(self, name, **kwargs):
        return DummySpan()
    def start_as_current_span(self, name, **kwargs):
        return DummySpan()


class DummyInstrument:
    def add(self, amount, attributes=None):
        pass
    def record(self, amount, attributes=None):
        pass
    def set(self, amount, attributes=None):
        pass


class DummyMeter:
    def create_counter(self, name, **kwargs):
        return DummyInstrument()
    def create_histogram(self, name, **kwargs):
        return DummyInstrument()
    def create_gauge(self, name, **kwargs):
        return DummyInstrument()
    def create_observable_gauge(self, name, **kwargs):
        return DummyInstrument()
    def create_up_down_counter(self, name, **kwargs):
        return DummyInstrument()


# Try to import core OpenTelemetry components
try:
    from opentelemetry import baggage, metrics, trace
    from opentelemetry.metrics import Meter
    from opentelemetry.sdk.metrics import MeterProvider

    # SDK components
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import Status, StatusCode, Tracer
    # Views for configuring histogram boundaries
    try:
        from opentelemetry.sdk.metrics.view import (
            ExplicitBucketHistogramAggregation,
            InstrumentSelector,
            View,
        )
    except Exception:  # pragma: no cover - optional depending on OTel version
        View = None  # type: ignore
        ExplicitBucketHistogramAggregation = None  # type: ignore
        InstrumentSelector = None  # type: ignore
    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    OTEL_AVAILABLE = True
except ImportError as e:
    # Demote to debug/info to reduce noisy logs during tests; telemetry is optional
    logger.debug(f"OpenTelemetry not fully available: {e}")
    logger.debug("Install with: pip install opentelemetry-distro opentelemetry-exporter-otlp opentelemetry-instrumentation-fastapi")
    OTEL_AVAILABLE = False
    Status = None  # type: ignore
    StatusCode = None  # type: ignore

PrometheusMetricReader = None
OTLPSpanExporter = None
OTLPMetricExporter = None
FastAPIInstrumentor = None
HTTPXClientInstrumentor = None
SQLAlchemyInstrumentor = None
Psycopg2Instrumentor = None
AioHttpClientInstrumentor = None
set_global_textmap = None
TraceContextTextMapPropagator = None

if OTEL_AVAILABLE:
    try:
        from opentelemetry.exporter.prometheus import PrometheusMetricReader
    except Exception as e:  # pragma: no cover - optional exporter
        logger.debug(f"Prometheus exporter not available: {e}")

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    except Exception as e:  # pragma: no cover - optional exporter
        logger.debug(f"OTLP trace exporter not available: {e}")

    try:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    except Exception as e:  # pragma: no cover - optional exporter
        logger.debug(f"OTLP metric exporter not available: {e}")

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except Exception as e:  # pragma: no cover - optional instrumentation
        logger.debug(f"FastAPI instrumentation not available: {e}")

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    except Exception as e:  # pragma: no cover - optional instrumentation
        logger.debug(f"HTTPX instrumentation not available: {e}")

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except Exception as e:  # pragma: no cover - optional instrumentation
        logger.debug(f"SQLAlchemy instrumentation not available: {e}")

    try:
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
    except Exception as e:  # pragma: no cover - optional instrumentation
        logger.debug(f"Psycopg2 instrumentation not available: {e}")

    try:
        from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
    except Exception as e:  # pragma: no cover - optional instrumentation
        logger.debug(f"aiohttp instrumentation not available: {e}")

    try:
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    except Exception as e:  # pragma: no cover - optional propagation
        logger.debug(f"Trace propagation not available: {e}")


class TelemetryConfig:
    """Configuration for OpenTelemetry setup."""

    def __init__(self):
        """Initialize telemetry configuration from environment variables."""
        # Allow explicit disable in tests/CI without requiring SDK uninstall.
        self.sdk_disabled = os.getenv("OTEL_SDK_DISABLED", "false").lower() == "true"
        # Service identification
        self.service_name = os.getenv("OTEL_SERVICE_NAME", "tldw_server")
        self.service_version = os.getenv("OTEL_SERVICE_VERSION", "1.0.0")
        self.service_namespace = os.getenv("OTEL_SERVICE_NAMESPACE", "production")
        self.deployment_environment = os.getenv("DEPLOYMENT_ENV", "development")

        # OTLP Configuration
        self.otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        self.otlp_protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
        self.otlp_headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
        self.otlp_insecure = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"

        # Exporter selection
        self.metrics_exporters = [
            exporter.strip()
            for exporter in os.getenv("OTEL_METRICS_EXPORTER", "prometheus").split(",")
            if exporter.strip()
        ]
        self.traces_exporters = [
            exporter.strip()
            for exporter in os.getenv("OTEL_TRACES_EXPORTER", "console").split(",")
            if exporter.strip()
        ]

        # Prometheus Configuration
        self.prometheus_port = int(os.getenv("PROMETHEUS_PORT", "9090"))
        self.prometheus_host = os.getenv("PROMETHEUS_HOST", "0.0.0.0")

        # Feature flags
        self.enable_metrics = os.getenv("ENABLE_METRICS", "true").lower() == "true"
        self.enable_tracing = os.getenv("ENABLE_TRACING", "true").lower() == "true"
        self.enable_logging = os.getenv("ENABLE_OTEL_LOGGING", "false").lower() == "true"
        self.enable_console_metrics_exporter = (
            os.getenv("ENABLE_OTEL_CONSOLE_METRICS_EXPORTER", "false").lower() == "true"
        )
        self.enable_profiling = os.getenv("ENABLE_PROFILING", "false").lower() == "true"

        # Performance settings
        self.metrics_export_interval = int(os.getenv("METRICS_EXPORT_INTERVAL_MS", "60000"))
        self.traces_export_batch_size = int(os.getenv("TRACES_EXPORT_BATCH_SIZE", "512"))
        self.traces_export_timeout = int(os.getenv("TRACES_EXPORT_TIMEOUT_MS", "30000"))
        self.sample_rate = float(os.getenv("METRICS_SAMPLE_RATE", "1.0"))

        if self.enable_console_metrics_exporter and "console" not in self.metrics_exporters:
            self.metrics_exporters.append("console")

        if self.sdk_disabled:
            # Force-disable all OTEL work to avoid background threads in tests.
            self.enable_metrics = False
            self.enable_tracing = False
            self.enable_logging = False
            self.enable_console_metrics_exporter = False
            self.metrics_exporters = []
            self.traces_exporters = []

        # Additional metadata
        self.hostname = socket.gethostname()
        self.pod_name = os.getenv("POD_NAME", self.hostname)
        self.pod_namespace = os.getenv("POD_NAMESPACE", "default")

    def get_resource_attributes(self) -> dict[str, Any]:
        """Get resource attributes for telemetry."""
        return {
            SERVICE_NAME: self.service_name,
            SERVICE_VERSION: self.service_version,
            "service.namespace": self.service_namespace,
            "deployment.environment": self.deployment_environment,
            "host.name": self.hostname,
            "k8s.pod.name": self.pod_name,
            "k8s.namespace.name": self.pod_namespace,
        }


class TelemetryManager:
    """Manages OpenTelemetry initialization and provides access to telemetry components."""

    def __init__(self, config: Optional[TelemetryConfig] = None):
        """
        Initialize the telemetry manager.

        Args:
            config: TelemetryConfig instance or None to use defaults
        """
        self.config = config or TelemetryConfig()
        self.tracer_provider: Optional[TracerProvider] = None
        self.meter_provider: Optional[MeterProvider] = None
        self.tracer: Optional[Tracer] = None
        self.meter: Optional[Meter] = None
        self.initialized = False
        # Hold pending views if provider not yet available
        self._pending_views = []  # list[tuple[str, list[float]]]

        if getattr(self.config, "sdk_disabled", False):
            logger.info("OpenTelemetry SDK disabled via OTEL_SDK_DISABLED")
            self.tracer = DummyTracer()
            self.meter = DummyMeter()
            return

        if not OTEL_AVAILABLE:
            logger.info("OpenTelemetry not available, using fallback implementations")
            self.tracer = DummyTracer()
            self.meter = DummyMeter()
            return

        self._initialize()

    def _initialize(self):
        """Initialize OpenTelemetry providers and exporters."""
        if self.initialized:
            return

        try:
            # Create resource
            resource = Resource.create(self.config.get_resource_attributes())

            # Initialize tracing
            if self.config.enable_tracing:
                self._initialize_tracing(resource)

            # Initialize metrics
            if self.config.enable_metrics:
                self._initialize_metrics(resource)

            # Set up context propagation when available
            if set_global_textmap and TraceContextTextMapPropagator:
                set_global_textmap(TraceContextTextMapPropagator())

            # Auto-instrumentation
            self._setup_auto_instrumentation()

            self.initialized = True
            logger.info(f"Telemetry initialized for service: {self.config.service_name}")

        except Exception as e:
            logger.error(f"Failed to initialize telemetry: {e}")
            # Fall back to dummy implementations
            self.tracer = DummyTracer()
            self.meter = DummyMeter()

    def _initialize_tracing(self, resource: Resource):
        """Initialize tracing with configured exporters."""
        self.tracer_provider = TracerProvider(resource=resource)

        # Add exporters based on configuration
        for exporter_name in self.config.traces_exporters:
            exporter = self._create_trace_exporter(exporter_name)
            if exporter:
                processor_kwargs = {
                    "max_queue_size": 2048,
                    "max_export_batch_size": self.config.traces_export_batch_size,
                }
                try:
                    params = inspect.signature(BatchSpanProcessor.__init__).parameters
                except (TypeError, ValueError):
                    params = {}
                if "export_timeout_millis" in params:
                    processor_kwargs["export_timeout_millis"] = self.config.traces_export_timeout
                elif "max_export_timeout_millis" in params:
                    processor_kwargs["max_export_timeout_millis"] = self.config.traces_export_timeout
                processor = BatchSpanProcessor(exporter, **processor_kwargs)
                self.tracer_provider.add_span_processor(processor)

        # Set as global tracer provider
        trace.set_tracer_provider(self.tracer_provider)
        self.tracer = trace.get_tracer(
            self.config.service_name,
            self.config.service_version
        )

    def _initialize_metrics(self, resource: Resource):
        """Initialize metrics with configured exporters."""
        readers = []

        # Add metric readers based on configuration
        for exporter_name in self.config.metrics_exporters:
            reader = self._create_metric_reader(exporter_name)
            if reader:
                readers.append(reader)

        if readers:
            # If Views are supported, apply after provider construction via register_view
            self.meter_provider = MeterProvider(
                resource=resource,
                metric_readers=readers,
            )

            # Set as global meter provider
            metrics.set_meter_provider(self.meter_provider)
            self.meter = metrics.get_meter(
                self.config.service_name,
                self.config.service_version
            )

            # Apply any views queued prior to initialization
            try:
                if hasattr(self.meter_provider, "register_view") and View and ExplicitBucketHistogramAggregation and InstrumentSelector:
                    for name, boundaries in list(self._pending_views):
                        try:
                            self.meter_provider.register_view(
                                View(
                                    instrument_selector=InstrumentSelector(name=name),
                                    aggregation=ExplicitBucketHistogramAggregation(boundaries=boundaries),
                                )
                            )
                        except Exception:
                            pass
                    self._pending_views.clear()
            except Exception:
                pass

    def _create_trace_exporter(self, exporter_name: str):
        """Create a trace exporter based on name."""
        exporter_name = exporter_name.strip().lower()

        if exporter_name == "console":
            return ConsoleSpanExporter()

        elif exporter_name == "otlp":
            if not self.config.otlp_endpoint:
                logger.warning("OTLP trace exporter requested without endpoint configured")
                return None
            if not OTLPSpanExporter:
                logger.warning("OTLP trace exporter not available")
                return None
            headers = {}
            if self.config.otlp_headers:
                for header in self.config.otlp_headers.split(","):
                    header = header.strip()
                    if not header or "=" not in header:
                        logger.debug(f"Skipping malformed OTLP header: {header}")
                        continue
                    key, value = header.split("=", 1)
                    key = key.strip()
                    if not key:
                        continue
                    headers[key] = value.strip()

            return OTLPSpanExporter(
                endpoint=self.config.otlp_endpoint,
                insecure=self.config.otlp_insecure,
                headers=headers
            )

        elif exporter_name == "jaeger":
            # Jaeger support via OTLP
            if not OTLPSpanExporter:
                logger.warning("OTLP trace exporter not available for Jaeger")
                return None
            jaeger_endpoint = os.getenv("JAEGER_ENDPOINT", "http://localhost:4317")
            return OTLPSpanExporter(
                endpoint=jaeger_endpoint,
                insecure=True
            )

        else:
            logger.warning(f"Unknown trace exporter: {exporter_name}")
            return None

    def _create_metric_reader(self, exporter_name: str):
        """Create a metric reader based on name."""
        exporter_name = exporter_name.strip().lower()

        if exporter_name == "console":
            exporter = ConsoleMetricExporter()
            return PeriodicExportingMetricReader(
                exporter,
                export_interval_millis=self.config.metrics_export_interval
            )

        elif exporter_name == "prometheus":
            # Prometheus pull-based metrics
            if not PrometheusMetricReader:
                logger.warning("Prometheus metric exporter not available")
                return None
            return PrometheusMetricReader(
                host=self.config.prometheus_host,
                port=self.config.prometheus_port
            )

        elif exporter_name == "otlp":
            if not self.config.otlp_endpoint:
                logger.warning("OTLP metric exporter requested without endpoint configured")
                return None
            if not OTLPMetricExporter:
                logger.warning("OTLP metric exporter not available")
                return None
            headers = {}
            if self.config.otlp_headers:
                for header in self.config.otlp_headers.split(","):
                    header = header.strip()
                    if not header or "=" not in header:
                        logger.debug(f"Skipping malformed OTLP header: {header}")
                        continue
                    key, value = header.split("=", 1)
                    key = key.strip()
                    if not key:
                        continue
                    headers[key] = value.strip()

            exporter = OTLPMetricExporter(
                endpoint=self.config.otlp_endpoint,
                insecure=self.config.otlp_insecure,
                headers=headers
            )
            return PeriodicExportingMetricReader(
                exporter,
                export_interval_millis=self.config.metrics_export_interval
            )

        else:
            logger.warning(f"Unknown metric exporter: {exporter_name}")
            return None

    def _setup_auto_instrumentation(self):
        """Set up automatic instrumentation for common libraries."""
        if not OTEL_AVAILABLE:
            return

        # FastAPI instrumentation
        if FastAPIInstrumentor:
            try:
                FastAPIInstrumentor.instrument(
                    tracer_provider=self.tracer_provider,
                    meter_provider=self.meter_provider
                )
            except Exception as e:
                logger.debug(f"Could not instrument FastAPI: {e}")

        # HTTP client instrumentation
        if HTTPXClientInstrumentor:
            try:
                HTTPXClientInstrumentor().instrument(
                    tracer_provider=self.tracer_provider
                )
            except Exception as e:
                logger.debug(f"Could not instrument HTTPX: {e}")

        if AioHttpClientInstrumentor:
            try:
                AioHttpClientInstrumentor().instrument(
                    tracer_provider=self.tracer_provider
                )
            except Exception as e:
                logger.debug(f"Could not instrument aiohttp: {e}")

        # Database instrumentation
        if SQLAlchemyInstrumentor:
            try:
                SQLAlchemyInstrumentor().instrument(
                    tracer_provider=self.tracer_provider
                )
            except Exception as e:
                logger.debug(f"Could not instrument SQLAlchemy: {e}")

        if Psycopg2Instrumentor:
            try:
                Psycopg2Instrumentor().instrument(
                    tracer_provider=self.tracer_provider
                )
            except Exception as e:
                logger.debug(f"Could not instrument psycopg2: {e}")

    def get_tracer(self, name: Optional[str] = None) -> Tracer:
        """
        Get a tracer instance.

        Args:
            name: Optional name for the tracer

        Returns:
            Tracer instance
        """
        if not self.tracer:
            return DummyTracer()

        if name:
            return trace.get_tracer(name, self.config.service_version)
        return self.tracer

    def get_meter(self, name: Optional[str] = None) -> Meter:
        """
        Get a meter instance.

        Args:
            name: Optional name for the meter

        Returns:
            Meter instance
        """
        if not self.meter:
            return DummyMeter()

        if name:
            return metrics.get_meter(name, self.config.service_version)
        return self.meter

    def register_histogram_view(self, instrument_name: str, boundaries: list[float]) -> None:
        """Register a histogram view for custom bucket boundaries.

        If the provider supports dynamic view registration, apply immediately;
        otherwise, queue it to be applied after initialization.
        """
        if not OTEL_AVAILABLE or not instrument_name or not boundaries:
            return
        try:
            if hasattr(self, "meter_provider") and self.meter_provider and hasattr(self.meter_provider, "register_view") \
               and View and ExplicitBucketHistogramAggregation and InstrumentSelector:
                self.meter_provider.register_view(
                    View(
                        instrument_selector=InstrumentSelector(name=instrument_name),
                        aggregation=ExplicitBucketHistogramAggregation(boundaries=boundaries),
                    )
                )
            else:
                # Queue for later application
                self._pending_views.append((instrument_name, list(boundaries)))
        except Exception as e:
            logger.debug(f"Failed to register histogram view for {instrument_name}: {e}")

    @contextmanager
    def trace_context(self, operation_name: str, attributes: Optional[dict[str, Any]] = None):
        """
        Context manager for creating a traced operation.

        Args:
            operation_name: Name of the operation
            attributes: Optional attributes to add to the span

        Yields:
            The span object
        """
        tracer = self.get_tracer()
        with tracer.start_as_current_span(operation_name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)

            try:
                yield span
            except Exception as e:
                span.record_exception(e)
                if OTEL_AVAILABLE and Status and StatusCode:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    def shutdown(self):
        """Shutdown telemetry providers and flush data."""
        if not OTEL_AVAILABLE or not self.initialized:
            return

        try:
            if self.tracer_provider:
                self.tracer_provider.shutdown()

            if self.meter_provider:
                self.meter_provider.shutdown()

            logger.info("Telemetry providers shut down successfully")
        except Exception as e:
            logger.error(f"Error shutting down telemetry: {e}")


# Global telemetry manager instance
_telemetry_manager: Optional[TelemetryManager] = None


def get_telemetry_manager() -> TelemetryManager:
    """
    Get or create the global telemetry manager.

    Returns:
        TelemetryManager instance
    """
    global _telemetry_manager
    if _telemetry_manager is None:
        _telemetry_manager = TelemetryManager()
    return _telemetry_manager


def instrument_fastapi_app(app: Any, telemetry_manager: Optional[TelemetryManager] = None) -> bool:
    """Instrument a FastAPI app with OpenTelemetry if available."""
    if not OTEL_AVAILABLE or not FastAPIInstrumentor or app is None:
        return False
    try:
        for attr in (
            "_is_instrumented_by_opentelemetry",
            "_instrumented_by_opentelemetry",
            "_tldw_otel_fastapi_instrumented",
        ):
            if getattr(app, attr, False):
                return True
        # Guard against duplicate middleware if auto-instrumentation already ran.
        try:
            for middleware in getattr(app, "user_middleware", []) or []:
                cls = getattr(middleware, "cls", None)
                if not cls:
                    continue
                if cls.__name__ == "OpenTelemetryMiddleware" or cls.__module__.startswith(
                    "opentelemetry.instrumentation"
                ):
                    try:
                        setattr(app, "_tldw_otel_fastapi_instrumented", True)
                    except Exception:
                        pass
                    return True
        except Exception:
            pass
        tm = telemetry_manager or get_telemetry_manager()
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=tm.tracer_provider,
            meter_provider=tm.meter_provider,
        )
        try:
            setattr(app, "_tldw_otel_fastapi_instrumented", True)
        except Exception:
            pass
        return True
    except Exception as e:
        logger.debug(f"Could not instrument FastAPI app: {e}")
        return False


def initialize_telemetry(config: Optional[TelemetryConfig] = None) -> TelemetryManager:
    """
    Initialize telemetry with optional configuration.

    Args:
        config: Optional TelemetryConfig instance

    Returns:
        TelemetryManager instance
    """
    global _telemetry_manager
    _telemetry_manager = TelemetryManager(config)
    return _telemetry_manager


def shutdown_telemetry():
    """Shutdown the global telemetry manager."""
    if _telemetry_manager:
        _telemetry_manager.shutdown()
