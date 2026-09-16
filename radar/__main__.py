"""Local command line entry points for Radar bundles and review state."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from .domain import validate_bundle
from .github_review import (
    ReviewError,
    apply_review,
    load_json,
    normalize_inventory,
    normalize_state,
    plan_reviews,
    write_json_atomic,
)
from .render import render_html, render_text
from .sync import ensure_vault


_ITEM_ID_RE = re.compile(r"^RAD-[0-9a-f]{12}$")
_RATING_ORIGINS = {"email", "form", "chat", "obsidian"}


def _read_json(path_or_json: str) -> object:
    path = Path(path_or_json)
    if path.is_file():
        return load_json(path)
    try:
        return json.loads(path_or_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"could not read JSON input {path_or_json}: {exc}") from exc


def _load_state(path: Path) -> dict:
    return normalize_state(load_json(path) if path.exists() else {})


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _rating_event(raw: object, *, base_revision: int | None = None) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("rating event must be an object")
    item_id = raw.get("item_id")
    if not isinstance(item_id, str) or not _ITEM_ID_RE.fullmatch(item_id):
        raise ValueError("item_id must be a RAD- identifier")
    score = raw.get("score")
    if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5:
        raise ValueError("score must be an integer from 1 through 5")
    origin = raw.get("origin")
    if origin not in _RATING_ORIGINS:
        raise ValueError("origin must be one of email, form, chat, obsidian")
    supplied_revision = raw.get("base_revision")
    if base_revision is not None:
        if supplied_revision is not None and supplied_revision != base_revision:
            raise ValueError("base_revision argument conflicts with event")
        supplied_revision = base_revision
    if isinstance(supplied_revision, bool) or not isinstance(supplied_revision, int) or supplied_revision < 0:
        raise ValueError("base_revision must be a non-negative integer")
    reason = raw.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise ValueError("reason must be a string or null")
    event_id = raw.get("event_id", str(uuid4()))
    try:
        event_id = str(UUID(event_id))
    except (ValueError, AttributeError) as exc:
        raise ValueError("event_id must be a UUID string") from exc
    created_at = raw.get("created_at", _utc_now_text())
    if not isinstance(created_at, str):
        raise ValueError("created_at must be a UTC ISO timestamp")
    candidate = created_at[:-1] + "+00:00" if created_at.endswith("Z") else created_at
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError("created_at must be a UTC ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("created_at must be a UTC ISO timestamp")
    created_at = parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "event_id": event_id,
        "item_id": item_id,
        "score": score,
        "reason": reason,
        "origin": origin,
        "base_revision": supplied_revision,
        "created_at": created_at,
    }


def _write_immutable(path: Path, data: object) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor = None
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ValueError(f"immutable output already exists: {path}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _cmd_validate(args: argparse.Namespace) -> int:
    normalized = validate_bundle(_read_json(args.bundle))
    json.dump(normalized, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    bundle = validate_bundle(_read_json(args.bundle))
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    format_name = args.format_option or args.format_argument or "html"
    if format_name == "html":
        content = render_html(bundle)
        suffix = ".html"
    elif format_name == "plain":
        content = render_text(bundle)
        suffix = ".txt"
    else:
        content = json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        suffix = ".json"
    target = output_dir / (Path(args.bundle).stem + suffix)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(target)
    return 0


def _cmd_init_vault(args: argparse.Namespace) -> int:
    vault = Path(args.vault)
    ensure_vault(vault)
    print(vault)
    return 0


def _cmd_review_plan(args: argparse.Namespace) -> int:
    inventory = normalize_inventory(load_json(Path(args.inventory)))
    state = _load_state(Path(args.state))
    plan = plan_reviews(inventory, state)
    write_json_atomic(Path(args.out), plan)
    print(args.out)
    return 0


def _cmd_apply_review(args: argparse.Namespace) -> int:
    state_path = Path(args.state)
    state = _load_state(state_path)
    result = load_json(Path(args.result))
    updated = apply_review(state, result)
    write_json_atomic(state_path, updated)
    print(state_path)
    return 0


def _cmd_rating(args: argparse.Namespace) -> int:
    raw = _read_json(args.event)
    event = _rating_event(raw, base_revision=args.base_revision)
    bundle = {"schema_version": 1, "kind": "ratings", "events": [event]}
    _write_immutable(Path(args.out), bundle)
    print(args.out)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m radar")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate a digest bundle")
    validate.add_argument("bundle")
    validate.set_defaults(handler=_cmd_validate)

    render = commands.add_parser("render", help="render a digest bundle")
    render.add_argument("bundle")
    render.add_argument("format_argument", nargs="?", choices=("html", "plain", "json"))
    render.add_argument("--format", "--output-format", dest="format_option", choices=("html", "plain", "json"))
    render.add_argument("--out", required=True, help="output directory")
    render.set_defaults(handler=_cmd_render)

    init_vault = commands.add_parser("init-vault", help="initialize an Obsidian vault")
    init_vault.add_argument("--vault", required=True)
    init_vault.set_defaults(handler=_cmd_init_vault)

    review_plan = commands.add_parser("review-plan", help="plan due repository reviews from local JSON")
    review_plan.add_argument("inventory")
    review_plan.add_argument("--state", required=True)
    review_plan.add_argument("--out", required=True)
    review_plan.set_defaults(handler=_cmd_review_plan)

    apply = commands.add_parser("apply-review", help="apply one explicit review result")
    apply.add_argument("result")
    apply.add_argument("--state", required=True)
    apply.set_defaults(handler=_cmd_apply_review)

    rating = commands.add_parser("rating", help="create an immutable ratings bundle")
    rating.add_argument("event")
    rating.add_argument("--out", required=True)
    rating.add_argument("--base-revision", type=int)
    rating.set_defaults(handler=_cmd_rating)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ReviewError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
