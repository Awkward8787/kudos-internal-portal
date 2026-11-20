import logging

from flask import (
    Blueprint,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .auth import admin_required, get_csrf_token, login_required
from .services import (
    KudosError,
    authenticate,
    create_kudos,
    delete_kudos,
    hide_kudos,
    list_admin_kudos,
    list_colleagues,
    list_public_kudos,
    unhide_kudos,
    user_full,
)

bp = Blueprint("pages", __name__)
logger = logging.getLogger("kudos")


def _json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@bp.errorhandler(KudosError)
def handle_kudos_error(exc):
    if request.path.startswith("/api/"):
        return jsonify(error=exc.code, message=exc.message), exc.status
    flash(exc.message, "error")
    return redirect(request.referrer or url_for("pages.dashboard"))


@bp.get("/api/csrf")
def api_csrf():
    return jsonify(csrf_token=get_csrf_token())


@bp.post("/api/login")
def api_login():
    body = _json_body()
    try:
        user = authenticate(body.get("username"), body.get("password"))
    except KudosError as exc:
        logger.info("login failed")
        return jsonify(error=exc.code, message=exc.message), exc.status
    session["user_id"] = user["id"]
    session.permanent = False
    logger.info("login succeeded user_id=%s", user["id"])
    return jsonify(user_full(user))


@bp.post("/api/logout")
@login_required
def api_logout():
    session.clear()
    return ("", 204)


@bp.get("/api/me")
@login_required
def api_me():
    return jsonify(user_full(g.user))


@bp.get("/api/colleagues")
@login_required
def api_colleagues():
    return jsonify(list_colleagues(g.user["id"]))


@bp.get("/api/kudos")
@login_required
def api_kudos_feed():
    try:
        return jsonify(list_public_kudos(request.args.get("page"), request.args.get("per_page")))
    except KudosError as exc:
        return jsonify(error=exc.code, message=exc.message), exc.status


@bp.post("/api/kudos")
@login_required
def api_create_kudos():
    body = _json_body()
    try:
        item = create_kudos(g.user["id"], body.get("to_user_id"), body.get("message"))
    except KudosError as exc:
        return jsonify(error=exc.code, message=exc.message), exc.status
    logger.info("kudos created id=%s user_id=%s", item["id"], g.user["id"])
    return jsonify(item), 201


@bp.get("/api/admin/kudos")
@admin_required
def api_admin_kudos():
    try:
        return jsonify(list_admin_kudos(request.args.get("page"), request.args.get("per_page")))
    except KudosError as exc:
        return jsonify(error=exc.code, message=exc.message), exc.status


@bp.post("/api/kudos/<int:kudos_id>/hide")
@admin_required
def api_hide_kudos(kudos_id):
    body = _json_body()
    try:
        item = hide_kudos(kudos_id, g.user["id"], body.get("reason"))
    except KudosError as exc:
        return jsonify(error=exc.code, message=exc.message), exc.status
    logger.info("kudos hidden id=%s admin_id=%s", kudos_id, g.user["id"])
    return jsonify(item)


@bp.post("/api/kudos/<int:kudos_id>/unhide")
@admin_required
def api_unhide_kudos(kudos_id):
    body = _json_body()
    try:
        item = unhide_kudos(kudos_id, g.user["id"], body.get("reason"))
    except KudosError as exc:
        return jsonify(error=exc.code, message=exc.message), exc.status
    logger.info("kudos restored id=%s admin_id=%s", kudos_id, g.user["id"])
    return jsonify(item)


@bp.delete("/api/kudos/<int:kudos_id>")
@admin_required
def api_delete_kudos(kudos_id):
    try:
        delete_kudos(kudos_id)
    except KudosError as exc:
        return jsonify(error=exc.code, message=exc.message), exc.status
    logger.info("kudos deleted id=%s admin_id=%s", kudos_id, g.user["id"])
    return ("", 204)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None and request.method == "GET":
        return redirect(url_for("pages.dashboard"))
    if request.method == "POST":
        try:
            user = authenticate(request.form.get("username"), request.form.get("password"))
        except KudosError as exc:
            flash(exc.message, "error")
            return render_template("login.html"), 401
        session["user_id"] = user["id"]
        logger.info("login succeeded user_id=%s", user["id"])
        return redirect(url_for("pages.dashboard"))
    return render_template("login.html")


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("pages.login"))


@bp.get("/")
@login_required
def dashboard():
    feed = list_public_kudos(request.args.get("page"), request.args.get("per_page", 20))
    return render_template("dashboard.html", feed=feed)


@bp.route("/give", methods=["GET", "POST"])
@login_required
def give():
    colleagues = list_colleagues(g.user["id"])
    if request.method == "POST":
        try:
            create_kudos(g.user["id"], request.form.get("to_user_id"), request.form.get("message"))
        except KudosError as exc:
            flash(exc.message, "error")
            return render_template("give.html", colleagues=colleagues), 400
        flash("Your kudos has been posted to the feed.", "success")
        return redirect(url_for("pages.dashboard"))
    return render_template("give.html", colleagues=colleagues)


@bp.get("/admin")
@admin_required
def admin():
    feed = list_admin_kudos(request.args.get("page"), request.args.get("per_page", 20))
    return render_template("admin.html", feed=feed)


@bp.post("/admin/kudos/<int:kudos_id>/hide")
@admin_required
def admin_hide(kudos_id):
    try:
        hide_kudos(kudos_id, g.user["id"], request.form.get("reason"))
    except KudosError as exc:
        flash(exc.message, "error")
        return redirect(url_for("pages.admin"))
    flash("The kudos has been hidden from the public feed.", "success")
    return redirect(url_for("pages.admin"))


@bp.post("/admin/kudos/<int:kudos_id>/unhide")
@admin_required
def admin_unhide(kudos_id):
    try:
        unhide_kudos(kudos_id, g.user["id"], request.form.get("reason"))
    except KudosError as exc:
        flash(exc.message, "error")
        return redirect(url_for("pages.admin"))
    flash("The kudos has been restored to the public feed.", "success")
    return redirect(url_for("pages.admin"))


@bp.post("/admin/kudos/<int:kudos_id>/delete")
@admin_required
def admin_delete(kudos_id):
    try:
        delete_kudos(kudos_id)
    except KudosError as exc:
        flash(exc.message, "error")
        return redirect(url_for("pages.admin"))
    flash("The kudos has been deleted.", "success")
    return redirect(url_for("pages.admin"))


@bp.app_errorhandler(403)
def forbidden(_error):
    if request.path.startswith("/api/"):
        return jsonify(error="forbidden", message="Administrator access required."), 403
    return render_template("forbidden.html"), 403


@bp.app_errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify(error="not_found", message="Not found."), 404
    return render_template("not_found.html"), 404
