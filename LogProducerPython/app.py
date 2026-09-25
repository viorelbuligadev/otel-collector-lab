"""Second log producer: a Python app that sends logs to the OTel Collector over OTLP/gRPC.

The OTLP exporter sends to http://localhost:4317 by default.
Override with the OTEL_EXPORTER_OTLP_ENDPOINT environment variable if needed.
"""

import logging
import random
import time

from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

RUN_DURATION_SECONDS = 2 * 60
EVENT_INTERVAL_SECONDS = 3
LOW_STOCK_THRESHOLD = 5

# Resource attributes identify *who* produced the logs.
# The collector's routing table matches service.name: "python-log-producer" -> index python-log-producer.
resource = Resource.create({
    "service.name": "python-log-producer",
    "service.version": "1.0.0",
    "deployment.environment": "dev",
})

logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
set_logger_provider(logger_provider)

# Console output for everything at INFO and above (including the OTel SDK's own messages).
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s: %(message)s")

# Bridge only the app's logger to OpenTelemetry. Attaching the handler to the root logger would
# also export the OTel SDK's internal logs (e.g. exporter retries), which can loop back on themselves.
logger = logging.getLogger("inventory")
logger.setLevel(logging.DEBUG)
logger.addHandler(LoggingHandler(level=logging.DEBUG, logger_provider=logger_provider))

SKUS = ["SKU-100", "SKU-200", "SKU-300", "SKU-400"]


def main() -> None:
    logger.info("Inventory producer started")

    stop_at = time.monotonic() + RUN_DURATION_SECONDS
    event_id = 0
    while time.monotonic() < stop_at:
        event_id += 1
        sku = random.choice(SKUS)
        quantity = random.randint(1, 20)
        stock_left = random.randint(0, 50)

        # Keys in `extra` become structured attributes on the OTLP log record.
        attrs = {"EventId": event_id, "Sku": sku, "Quantity": quantity, "StockLeft": stock_left}

        logger.info("Reserved %d x %s", quantity, sku, extra=attrs)

        if stock_left < LOW_STOCK_THRESHOLD:
            logger.warning("Stock for %s is low: %d left", sku, stock_left, extra=attrs)

        if event_id % 7 == 0:
            try:
                raise ConnectionError("Warehouse API unavailable")
            except ConnectionError:
                # logger.exception adds exception.type / exception.message / exception.stacktrace.
                logger.exception("Event %d failed for %s", event_id, sku, extra=attrs)

        logger.debug("Event %d done", event_id, extra=attrs)
        time.sleep(EVENT_INTERVAL_SECONDS)

    logger.info("Inventory producer finished")


if __name__ == "__main__":
    try:
        main()
    finally:
        # Flushes batched logs to the collector. Without it, the last batch is lost on exit.
        logger_provider.shutdown()
