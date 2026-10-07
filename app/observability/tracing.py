import logging

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import settings

logger = logging.getLogger("prodllm.tracing")
tracer: trace.Tracer = trace.get_tracer("prodllm.gateway")


def setup_tracing(app: FastAPI):
    """
    Initialize OpenTelemetry tracer provider with OTLP / Jaeger exporter
    and instrument FastAPI and HTTPX.
    """
    if not settings.OTEL_ENABLED:
        logger.info("OpenTelemetry tracing is disabled.")
        return

    try:
        resource = Resource.create({
            "service.name": settings.OTEL_SERVICE_NAME,
            "service.environment": settings.APP_ENV,
        })
        provider = TracerProvider(resource=resource)

        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            insecure=True,
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(provider)

        # Instrument FastAPI app and httpx
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        HTTPXClientInstrumentor().instrument(tracer_provider=provider)

        logger.info(
            f"OpenTelemetry tracing initialized with OTLP endpoint: {settings.OTEL_EXPORTER_OTLP_ENDPOINT}"
        )
    except Exception as e:
        logger.warning(f"Failed to initialize OpenTelemetry tracing: {e}")


def get_tracer() -> trace.Tracer:
    return trace.get_tracer("prodllm.gateway")
