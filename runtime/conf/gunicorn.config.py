import logging
import os

from gunicorn.arbiter import Arbiter
from gunicorn.workers.gthread import ThreadWorker
from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import (
    LoggerProvider,
    LoggingHandler,
)
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

OTEL_COLLECTOR_HOST = os.environ.get("OTEL_COLLECTOR_HOST")
OTEL_COLLECTOR_PORT = os.environ.get("OTEL_COLLECTOR_PORT")
OTEL_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME")
OTEL_SERVICE_INSTANCE_ID = os.environ.get("OTEL_SERVICE_INSTANCE_ID")

OTEL_TRACE_ENABLED = os.environ.get("OTEL_TRACE_ENABLED", "false").lower() == "true"


def post_fork(server: Arbiter, worker: ThreadWorker) -> None:
    if not OTEL_TRACE_ENABLED:
        return

    server.log.info("Worker spawned (pid: %s)" % (worker.pid))

    resource = Resource.create(
        attributes={
            "service.name": OTEL_SERVICE_NAME,
            "service.instance.id": OTEL_SERVICE_INSTANCE_ID,
            "worker_pid": worker.pid,
        }
    )

    # logs setup
    logger_provider = LoggerProvider(
        resource=resource,
    )
    set_logger_provider(logger_provider)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{OTEL_COLLECTOR_HOST}:{OTEL_COLLECTOR_PORT}", insecure=True))
    )
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
    logging.getLogger().addHandler(handler)

    # traces setup
    trace.set_tracer_provider(TracerProvider(resource=resource))
    span_processor = BatchSpanProcessor(
        OTLPSpanExporter(endpoint=f"{OTEL_COLLECTOR_HOST}:{OTEL_COLLECTOR_PORT}", insecure=True)
    )
    trace.get_tracer_provider().add_span_processor(span_processor)
