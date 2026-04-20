"""Structured JSON logging configuration for the Flask app."""
import json
import logging
from datetime import datetime
from flask import has_request_context, g


class JSONFormatter(logging.Formatter):
    def format(self, record):
        record_message = record.getMessage()

        data = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "message": record_message,
            "logger": record.name,
        }

        # Add extra fields if available on the record
        # event_type can be passed via extra={"event_type": "..."}
        if hasattr(record, "event_type"):
            data["event_type"] = record.event_type

        # Try to include request context info when available
        try:
            if has_request_context():
                data.setdefault("request_id", getattr(g, "request_id", None))
                data.setdefault("user_role", getattr(g, "user_role", None))
                data.setdefault("endpoint", getattr(g, "endpoint", None))
        except Exception:
            # Ignore issues in accessing request context
            pass

        # Include exception info if present
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)

        return json.dumps(data)


def init_logging(app):
    # Remove existing handlers and set our structured handler
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    # Clear default handlers to avoid duplicate logs
    for h in list(app.logger.handlers):
        app.logger.removeHandler(h)

    app.logger.addHandler(handler)
    app.logger.setLevel(app.config.get("LOG_LEVEL", "INFO"))

    # Optionally set werkzeug logger to use JSON too
    logging.getLogger("werkzeug").handlers = [handler]
    logging.getLogger("werkzeug").setLevel(app.logger.level)
