import functools
import secrets

from flask import abort, g, jsonify, redirect, request, session, url_for

from .db import get_db


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(32)
        session["csrf_token"] = token
    return token


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute(
        "SELECT id, username, display_name, role FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def load_user():
    g.user = current_user()


def _wants_json():
    return request.path.startswith("/api/")


def csrf_protect():
    if request.method in SAFE_METHODS:
        return None
    token = (
        request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token")
        or (request.is_json and isinstance(request.json, dict) and request.json.get("csrf_token"))
    )
    if not token or token != session.get("csrf_token"):
        message = "Missing or invalid CSRF token."
        if _wants_json():
            return jsonify(error="csrf", message=message), 400
        abort(400, description=message)
    return None


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if request.path.startswith("/api/"):
                return jsonify(error="unauthenticated", message="Sign in required."), 401
            return redirect(url_for("pages.login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if request.path.startswith("/api/"):
                return jsonify(error="unauthenticated", message="Sign in required."), 401
            return redirect(url_for("pages.login"))
        if g.user["role"] != "admin":
            if request.path.startswith("/api/"):
                return jsonify(error="forbidden", message="Administrator access required."), 403
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def init_app(app):
    app.before_request(load_user)
    app.before_request(csrf_protect)
    app.context_processor(
        lambda: {"csrf_token": get_csrf_token(), "current_user": g.get("user")}
    )
