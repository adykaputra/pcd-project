from flask import Flask

from .logging_config import init_logging
from .middleware import init_request_middleware


def create_app():
    app = Flask(__name__)

    # Initialize structured logging and request middleware
    init_logging(app)
    init_request_middleware(app)

    # Initialize audit logging handler
    try:
        from .audit import get_manager, init_audit_logging

        # Ensure the audit DB/table exists before any request logging.
        get_manager()
        init_audit_logging(app)
    except Exception as e:
        app.logger.error("Failed to initialize audit logging: %s", e, extra={"event_type": "AUDIT_INIT"})

    with app.app_context():
        # Register blueprints from module1..module4 if present
        for mod in ("module1", "module2", "module3", "module4", "auth"):
            try:
                module = __import__(f"app.{mod}.routes", fromlist=["bp"])
                bp = getattr(module, "bp", None)
                if bp:
                    # Be tolerant to import side effects that could pre-register names.
                    if bp.name in app.blueprints:
                        app.logger.warning(
                            "Blueprint '%s' already registered; skipping duplicate registration",
                            bp.name,
                            extra={"event_type": "MODULE_REGISTRATION"},
                        )
                    else:
                        app.register_blueprint(bp)
                else:
                    app.logger.warning("No blueprint 'bp' found in app.%s.routes", mod, extra={"event_type": "MODULE_REGISTRATION"})
            except Exception as e:
                app.logger.error("Failed to import/register blueprint for %s: %s", mod, e, extra={"event_type": "MODULE_REGISTRATION"})

    return app

app = create_app()
app.logger.info("App created successfully", extra={"event_type": "APP_START"})