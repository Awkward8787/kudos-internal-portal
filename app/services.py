from datetime import datetime, timedelta, timezone

from werkzeug.security import check_password_hash

from .db import get_db, utc_now


class KudosError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def parse_utc(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def user_public(row):
    if row is None:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
    }


def user_full(row):
    data = user_public(row)
    data["role"] = row["role"]
    return data


def find_user_by_username(username):
    return get_db().execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE",
        (username.strip() if username else "",),
    ).fetchone()


def find_user_by_id(user_id):
    return get_db().execute(
        "SELECT id, username, display_name, role FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def authenticate(username, password):
    if not username or not password:
        raise KudosError(401, "invalid_credentials", "Incorrect username or password.")
    user = find_user_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        raise KudosError(401, "invalid_credentials", "Incorrect username or password.")
    return user


def list_colleagues(user_id):
    rows = get_db().execute(
        """
        SELECT id, username, display_name, role
        FROM users
        WHERE id != ?
        ORDER BY display_name COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()
    return [user_public(row) for row in rows]


def _pagination(page, per_page):
    try:
        page = int(page or 1)
        per_page = int(per_page or 20)
    except (TypeError, ValueError) as exc:
        raise KudosError(400, "invalid_pagination", "page and per_page must be integers.") from exc
    if page < 1:
        raise KudosError(400, "invalid_pagination", "page must be 1 or greater.")
    if per_page < 1 or per_page > 50:
        raise KudosError(400, "invalid_pagination", "per_page must be between 1 and 50.")
    return page, per_page


def _fetch_users_by_ids(ids):
    ids = list({i for i in ids if i is not None})
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    rows = get_db().execute(
        f"SELECT id, username, display_name, role FROM users WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    return {row["id"]: row for row in rows}


def _serialize_kudos(row, users, include_moderation=False):
    item = {
        "id": row["id"],
        "from_user": user_public(users.get(row["from_user_id"])),
        "to_user": user_public(users.get(row["to_user_id"])),
        "message": row["message"],
        "created_at": row["created_at"],
        "is_visible": bool(row["is_visible"]),
    }
    if include_moderation:
        moderator = users.get(row["moderated_by"]) if row["moderated_by"] else None
        item["moderated_by"] = user_public(moderator)
        item["moderated_at"] = row["moderated_at"]
        item["reason_for_moderation"] = row["reason_for_moderation"]
    return item


def _paginated_kudos(where_sql, where_args, page, per_page, include_moderation):
    page, per_page = _pagination(page, per_page)
    db = get_db()
    total = db.execute(
        f"SELECT COUNT(*) AS n FROM kudos {where_sql}",
        where_args,
    ).fetchone()["n"]
    offset = (page - 1) * per_page
    rows = db.execute(
        f"""
        SELECT * FROM kudos
        {where_sql}
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (*where_args, per_page, offset),
    ).fetchall()
    users = _fetch_users_by_ids(
        [row["from_user_id"] for row in rows]
        + [row["to_user_id"] for row in rows]
        + [row["moderated_by"] for row in rows]
    )
    items = [_serialize_kudos(row, users, include_moderation=include_moderation) for row in rows]
    total_pages = (total + per_page - 1) // per_page if total else 0
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
    }


def list_public_kudos(page=1, per_page=20):
    return _paginated_kudos("WHERE is_visible = 1", (), page, per_page, include_moderation=False)


def list_admin_kudos(page=1, per_page=20):
    return _paginated_kudos("", (), page, per_page, include_moderation=True)


def get_kudos(kudos_id, include_moderation=False):
    row = get_db().execute("SELECT * FROM kudos WHERE id = ?", (kudos_id,)).fetchone()
    if row is None:
        raise KudosError(404, "not_found", "Kudos not found.")
    users = _fetch_users_by_ids([row["from_user_id"], row["to_user_id"], row["moderated_by"]])
    return _serialize_kudos(row, users, include_moderation=include_moderation)


def _normalize_message(message):
    if message is None:
        return ""
    return message.strip()


def create_kudos(from_user_id, to_user_id, message, now=None):
    now = now or utc_now()
    message = _normalize_message(message)
    if not message:
        raise KudosError(400, "invalid_message", "A message is required.")
    if len(message) > 500:
        raise KudosError(400, "invalid_message", "The message must be 500 characters or fewer.")

    try:
        to_user_id = int(to_user_id)
    except (TypeError, ValueError) as exc:
        raise KudosError(400, "invalid_recipient", "to_user_id must be an integer.") from exc

    if to_user_id == from_user_id:
        raise KudosError(400, "self_kudos", "You cannot give kudos to yourself.")

    recipient = find_user_by_id(to_user_id)
    if recipient is None:
        raise KudosError(404, "not_found", "Recipient not found.")

    db = get_db()
    window_hours = int(current_window_hours())
    since_duplicate = _shift(now, hours=-window_hours)
    duplicate = db.execute(
        """
        SELECT id FROM kudos
        WHERE from_user_id = ?
          AND to_user_id = ?
          AND LOWER(message) = LOWER(?)
          AND created_at >= ?
        LIMIT 1
        """,
        (from_user_id, to_user_id, message, since_duplicate),
    ).fetchone()
    if duplicate:
        raise KudosError(
            409,
            "duplicate",
            "You already sent this message to that colleague within the last 24 hours.",
        )

    since_rate = _shift(now, hours=-1)
    recent_count = db.execute(
        """
        SELECT COUNT(*) AS n FROM kudos
        WHERE from_user_id = ? AND created_at >= ?
        """,
        (from_user_id, since_rate),
    ).fetchone()["n"]
    limit = current_rate_limit()
    if recent_count >= limit:
        raise KudosError(
            429,
            "rate_limited",
            "You can give at most 10 kudos per hour. Please try again later.",
        )

    cursor = db.execute(
        """
        INSERT INTO kudos (from_user_id, to_user_id, message, created_at, is_visible)
        VALUES (?, ?, ?, ?, 1)
        """,
        (from_user_id, to_user_id, message, now),
    )
    db.commit()
    return get_kudos(cursor.lastrowid, include_moderation=False)


def hide_kudos(kudos_id, admin_id, reason, now=None):
    now = now or utc_now()
    reason = _normalize_message(reason)
    if not reason:
        raise KudosError(400, "invalid_reason", "A reason is required to hide kudos.")
    if len(reason) > 500:
        raise KudosError(400, "invalid_reason", "The reason must be 500 characters or fewer.")
    _require_kudos(kudos_id)
    get_db().execute(
        """
        UPDATE kudos
        SET is_visible = 0,
            moderated_by = ?,
            moderated_at = ?,
            reason_for_moderation = ?
        WHERE id = ?
        """,
        (admin_id, now, reason, kudos_id),
    )
    get_db().commit()
    return get_kudos(kudos_id, include_moderation=True)


def unhide_kudos(kudos_id, admin_id, reason=None, now=None):
    now = now or utc_now()
    _require_kudos(kudos_id)
    reason = _normalize_message(reason) if reason is not None else None
    if reason == "":
        raise KudosError(400, "invalid_reason", "A reason, if provided, cannot be empty.")
    if reason and len(reason) > 500:
        raise KudosError(400, "invalid_reason", "The reason must be 500 characters or fewer.")
    if reason:
        get_db().execute(
            """
            UPDATE kudos
            SET is_visible = 1,
                moderated_by = ?,
                moderated_at = ?,
                reason_for_moderation = ?
            WHERE id = ?
            """,
            (admin_id, now, reason, kudos_id),
        )
    else:
        get_db().execute(
            """
            UPDATE kudos
            SET is_visible = 1,
                moderated_by = ?,
                moderated_at = ?
            WHERE id = ?
            """,
            (admin_id, now, kudos_id),
        )
    get_db().commit()
    return get_kudos(kudos_id, include_moderation=True)


def delete_kudos(kudos_id):
    _require_kudos(kudos_id)
    db = get_db()
    db.execute("DELETE FROM kudos WHERE id = ?", (kudos_id,))
    db.commit()


def _require_kudos(kudos_id):
    row = get_db().execute("SELECT id FROM kudos WHERE id = ?", (kudos_id,)).fetchone()
    if row is None:
        raise KudosError(404, "not_found", "Kudos not found.")
    return row


def current_rate_limit():
    from flask import current_app

    return int(current_app.config["RATE_LIMIT_PER_HOUR"])


def current_window_hours():
    from flask import current_app

    return int(current_app.config["DUPLICATE_WINDOW_HOURS"])


def _shift(iso_now, hours):
    moment = parse_utc(iso_now) + timedelta(hours=hours)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
