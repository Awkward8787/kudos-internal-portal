# Kudos internal portal

A small internal-portal feature that lets colleagues give each other kudos, shows a public feed of recent messages, and lets an administrator hide or delete anything that should not stay on that feed.

This is the implementation for Anthony Jones's Datacom Automation AI Accelerator Task 2 (Create a process flow). The approved blueprint is in [SPECIFICATION.md](SPECIFICATION.md). A general-purpose agentic coding assistant drafted that specification from a high-level request; the specification was then refined to add authentication, an administrator moderation story, and the `is_visible`, `moderated_by`, `moderated_at`, and `reason_for_moderation` fields. The application was implemented against the approved document, not by improvising product decisions in the code.

Suggested public repository name: `kudos-internal-portal`.

## Stack

- Python 3.13 and Flask 3
- SQLite 3
- Jinja2 templates and a small amount of JavaScript
- pytest

## Features

- Sign in and sign out, with employee and administrator roles
- Choose a colleague from a dropdown, write a message (max 500 characters), and post it
- Dashboard feed of recent visible kudos, paginated
- Administrators can hide a message (with a required reason), restore it, or delete it
- Duplicate messages within 24 hours and more than 10 posts in an hour are rejected
- Responsive layout for phone and desktop widths

## How to run

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app init-db
flask --app app run
```

Then open http://127.0.0.1:5000 and sign in with one of the demo accounts below. `flask --app app init-db` creates `instance/kudos.db` and seeds those accounts plus a few sample kudos. The database file is not committed.

For anything other than local use, set a real secret:

```bash
export KUDOS_SECRET_KEY="a long random value"
```

## Demo accounts

Every demo account uses the password `kudos-demo`. These are for local evaluation only.

| Username | Display name   | Role      |
|----------|----------------|-----------|
| admin    | Alex Rivera    | admin     |
| jordan   | Jordan Lee     | employee  |
| priya    | Priya Shah     | employee  |
| marcus   | Marcus Chen    | employee  |
| anthony  | Anthony Jones  | employee  |

## How to run the tests

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -v
```

Each test uses its own temporary SQLite database. The suite covers authentication, validation, the feed, duplicates, the rate limit, moderation, and HTML escaping.

## Continuous integration

[![CI](https://github.com/Awkward8787/kudos-internal-portal/actions/workflows/ci.yml/badge.svg)](https://github.com/Awkward8787/kudos-internal-portal/actions/workflows/ci.yml)

The `CI` workflow (`.github/workflows/ci.yml`) runs on every push and pull request to `main`, and it can be started manually with `workflow_dispatch`. The `test` job uses `ubuntu-latest` and a Python matrix of 3.11 and 3.12. It checks out the repository, sets up Python with a pip cache, installs `requirements.txt` (pytest is already pinned there), and runs `python -m pytest -q`.

The workflow sets `APP_ENV` to `ci` and prints that value along with `github.repository`, `github.ref_name`, and `github.sha`. An optional repository variable, `DEPLOY_ENV`, is read when it is set; otherwise the step uses `development`.

## License

Copyright (C) 2026 Anthony Jones.

This program is free software under the GNU Affero General Public License as published by the Free Software Foundation, version 3 of the License. See [LICENSE](LICENSE).
