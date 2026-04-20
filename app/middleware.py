"""Request middleware utilities (request id, role extraction)."""
from uuid import uuid4
from flask import g, request


def init_request_middleware(app):
    @app.before_request
    def attach_request_id_and_role():
        # Generate a unique request id for every incoming request
        rid = str(uuid4())
        g.request_id = rid

        # Try to extract role from JSON body if present
        try:
            data = request.get_json(silent=True)
            role = data.get('role') if isinstance(data, dict) else None
        except Exception:
            role = None
        g.user_role = role
        g.endpoint = request.path

    @app.after_request
    def add_request_id_header(response):
        # Ensure the response has the X-Request-ID header
        try:
            response.headers['X-Request-ID'] = g.request_id
        except Exception:
            # If no request context, ignore
            pass
        return response
