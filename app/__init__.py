import sys
print(f"Python path: {sys.path}", file=sys.stderr)

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
        from .audit import init_audit_logging

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
                    app.register_blueprint(bp)
                else:
                    app.logger.warning("No blueprint 'bp' found in app.%s.routes", mod, extra={"event_type": "MODULE_REGISTRATION"})
            except Exception as e:
                app.logger.error("Failed to import/register blueprint for %s: %s", mod, e, extra={"event_type": "MODULE_REGISTRATION"})

        # ensure module4 blueprint is registered under /audit
        try:
            module4 = __import__("app.module4.routes", fromlist=["bp"])  # explicit import to ensure registration
            bp4 = getattr(module4, "bp", None)
            if bp4:
                app.register_blueprint(bp4)
        except Exception as e:
            app.logger.error("Failed to import/register module4 routes: %s", e, extra={"event_type": "MODULE_REGISTRATION"})

    return app

app = create_app()
app.logger.info("App created successfully", extra={"event_type": "APP_START"})