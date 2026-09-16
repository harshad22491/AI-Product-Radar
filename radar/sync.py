import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
VAULT_DIRS = ["Items", "Digests", "Repositories", "Reviews", "Experiments", "Dashboard"]
USER_SECTION = "## User notes"
SAFE_SLUG = re.compile(r"[^A-Za-z0-9_-]+")
ID_RE = re.compile(r"^RAD-[0-9a-f]{12}\Z")


class SyncError(ValueError):
    pass


def atomic_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def safe_slug(name: str) -> str:
    slug = SAFE_SLUG.sub("-", name).strip("-.")
    if not slug or slug in {".", ".."}:
        raise SyncError(f"unsafe repository name: {name!r}")
    return slug[:80]


def safe_path(vault: Path, *parts: str) -> Path:
    for part in parts:
        if (not isinstance(part, str) or not part or part in {".", ".."}
                or "/" in part or "\\" in part or ":" in part):
            raise SyncError(f"path traversal rejected: {part!r}")
    target = vault.joinpath(*parts)
    resolved = target.resolve()
    if not str(resolved).startswith(str(vault.resolve()) + os.sep):
        raise SyncError("path traversal rejected")
    return target


def parse_scalar(raw: str):
    """Parse frontmatter value using stdlib JSON-quoted scalar rules."""
    raw = raw.strip()
    if raw.startswith('"') or raw.startswith("[") or raw.startswith("{") or \
       raw.lstrip("-").replace(".", "", 1).isdigit():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise SyncError(f"malformed frontmatter scalar: {raw!r}")
    if raw in ("true", "false", "null"):
        return json.loads(raw)
    return raw


def unquote_fm(v):
    return v if isinstance(v, str) else v


def parse_frontmatter(text: str):
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        raise SyncError("unterminated frontmatter")
    fm_lines = text[4:end].splitlines()
    body = text[end + 4:].lstrip("\r\n")
    fm = {}
    for line in fm_lines:
        if ":" not in line:
            raise SyncError(f"malformed frontmatter line: {line!r}")
        k, v = line.split(":", 1)
        fm[k.strip()] = parse_scalar(v)
    return fm, body


def snapshot_order(snap: dict):
    """Return the cloud ordering key; filenames are only a final tie-breaker."""
    return (snap["state_revision"], _parse_timestamp(snap["updated_at"], "updated_at"))


def _parse_timestamp(raw, field: str):
    if not isinstance(raw, str) or not raw:
        raise SyncError(f"snapshot {field} must be an aware UTC timestamp")
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise SyncError(f"snapshot {field} must be an aware UTC timestamp")
    if value.tzinfo is None:
        raise SyncError(f"snapshot {field} must be an aware UTC timestamp")
    return value.astimezone(timezone.utc)


def render_frontmatter(fm: dict) -> str:
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines)


def split_user_notes(body: str):
    marker = USER_SECTION + "\n"
    idx = body.find("\n" + marker)
    if idx >= 0:
        return body[:idx].lstrip("\n"), (USER_SECTION + "\n" + body[idx + 1 + len(marker):])
    if body.startswith(marker):
        return "", body
    return body, None


def load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise SyncError(f"cannot read {path}: {e}")


def validate_snapshot(snap) -> dict:
    if not isinstance(snap, dict):
        raise SyncError("snapshot not an object")
    if snap.get("schema_version") != SCHEMA_VERSION:
        raise SyncError("snapshot schema_version must be 1")
    items = snap.get("items")
    digests = snap.get("digests", [])
    ratings = snap.get("ratings", {})
    state_revision = snap.get("state_revision")
    if (not isinstance(state_revision, int) or isinstance(state_revision, bool)
            or state_revision < 0):
        raise SyncError("snapshot state_revision must be a non-negative integer")
    _parse_timestamp(snap.get("updated_at"), "updated_at")
    if not isinstance(items, list) or not isinstance(digests, list) or not isinstance(ratings, dict):
        raise SyncError("snapshot items/digests/ratings wrong types")
    seen = set()
    for it in items:
        if not isinstance(it, dict):
            raise SyncError("item not object")
        iid = it.get("item_id")
        if not isinstance(iid, str) or not ID_RE.match(iid):
            raise SyncError(f"bad item_id: {iid!r}")
        if iid in seen:
            raise SyncError(f"duplicate item_id in snapshot: {iid}")
        seen.add(iid)
        if not isinstance(it.get("title"), str) or not it["title"]:
            raise SyncError(f"bad title for {iid}")
        if not isinstance(it.get("source_url"), str) or not it["source_url"].startswith("https://"):
            raise SyncError(f"bad source_url for {iid}")
    for digest in digests:
        if not isinstance(digest, dict) or not isinstance(digest.get("run_id"), str) \
                or not digest["run_id"]:
            raise SyncError("digest must have a non-empty run_id")
    for iid, r in ratings.items():
        if not ID_RE.match(iid):
            raise SyncError(f"bad rating key: {iid}")
        if (not isinstance(r, dict) or not isinstance(r.get("score"), int)
                or isinstance(r.get("score"), bool) or not 1 <= r["score"] <= 5
                or not isinstance(r.get("revision"), int)
                or isinstance(r.get("revision"), bool) or r["revision"] < 0
                or ("reason" in r and not isinstance(r["reason"], str))):
            raise SyncError(f"bad rating for {iid}")
    return snap


def ensure_vault(vault: Path) -> None:
    vault.mkdir(parents=True, exist_ok=True)
    for d in VAULT_DIRS:
        safe_path(vault, d).mkdir(exist_ok=True)
    obs = safe_path(vault, ".obsidian")
    obs.mkdir(exist_ok=True)
    cfg = obs / "app.json"
    if not cfg.exists():
        atomic_write_json(cfg, {"alwaysUpdateLinks": True})
    ws = obs / "workspace.json"
    if not ws.exists():
        atomic_write_json(ws, {})


def item_filename(item_id: str, title: str) -> str:
    return f"{item_id} {safe_slug(title)[:60]}.md"


def _rating_values(rating):
    if not isinstance(rating, dict):
        return None
    return rating.get("score"), rating.get("reason", "")


def _same_rating_values(left, right) -> bool:
    return left is not None and right is not None and _rating_values(left) == _rating_values(right)


def _event_key(item_id: str, score: int, reason: str, base_revision: int) -> str:
    return json.dumps([item_id, score, reason, base_revision], ensure_ascii=False, separators=(",", ":"))


def export_ratings(vault: Path, exchange: Path, state: dict,
                   state_path: Path | None = None) -> dict:
    """Export changed Obsidian ratings before any import. Returns new last-exported map."""
    exported = dict(state.get("last_exported", {}))
    imported = state.get("last_imported", {})
    if not isinstance(imported, dict):
        imported = {}
    events = []
    raw_pending_event_ids = state.get("pending_event_ids", {})
    pending_event_ids = dict(raw_pending_event_ids) if isinstance(raw_pending_event_ids, dict) else {}
    items_dir = safe_path(vault, "Items")
    if items_dir.exists():
        for p in sorted(items_dir.glob("*.md")):
            p = safe_path(vault, "Items", p.name)
            try:
                text = p.read_text(encoding="utf-8")
                fm, body = parse_frontmatter(text)
            except (OSError, SyncError):
                continue
            iid = fm.get("item_id")
            score = fm.get("rating")
            if not isinstance(iid, str) or not ID_RE.match(iid) or score is None:
                continue
            if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5:
                continue
            reason = fm.get("rating_reason", "")
            if not isinstance(reason, str):
                reason = ""
            base = exported.get(iid, imported.get(iid,
                                                  {"score": None, "reason": "", "revision": 0}))
            if not isinstance(base, dict):
                base = {"score": None, "reason": "", "revision": 0}
            if base.get("score") == score and base.get("reason", "") == reason:
                continue  # unchanged since last export
            try:
                base_revision = int(base.get("revision", 0))
            except (TypeError, ValueError):
                base_revision = 0
            if base_revision < 0:
                base_revision = 0
            event_key = _event_key(iid, score, reason, base_revision)
            event_id = pending_event_ids.get(event_key)
            if not isinstance(event_id, str) or not event_id:
                event_id = str(uuid.uuid4())
                pending_event_ids[event_key] = event_id
            events.append({
                "event_id": event_id,
                "item_id": iid,
                "score": score,
                "reason": reason,
                "origin": "obsidian",
                "base_revision": base_revision,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            prior = exported.get(iid, {})
            exported[iid] = {
                "score": score,
                "reason": reason,
                "revision": base_revision,
                "pending": True,
                "event_key": event_key,
                **({"conflicted": True} if isinstance(prior, dict) and prior.get("conflicted") else {}),
            }
    if events:
        # The identity must survive a crash between event creation and feedback write.
        state["pending_event_ids"] = pending_event_ids
        if state_path is None:
            state_path = safe_path(vault, ".radar-sync-state.json")
        atomic_write_json(state_path, state)
        fb = safe_path(exchange, "feedback")
        fb.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        atomic_write_json(fb / f"obsidian-{ts}-{uuid.uuid4().hex[:8]}.json",
                          {"schema_version": SCHEMA_VERSION, "kind": "ratings", "events": events})
    return exported


def apply_pending(vault: Path, pending: dict, snap: dict) -> dict:
    """Merge new snapshot items into pending imports (to be written after export)."""
    items = {p["item_id"]: p for p in pending.get("items", [])}
    for it in snap.get("items", []):
        items[it["item_id"]] = it
    ratings = dict(pending.get("ratings", {}))
    for iid, r in snap.get("ratings", {}).items():
        ratings[iid] = r
    digests = {}
    for digest in pending.get("digests", []):
        if isinstance(digest, dict) and isinstance(digest.get("run_id"), str):
            digests[digest["run_id"]] = digest
    for digest in snap.get("digests", []):
        digests[digest["run_id"]] = digest
    return {
        "items": sorted(items.values(), key=lambda x: x["item_id"]),
        "digests": sorted(digests.values(), key=lambda x: x["run_id"]),
        "ratings": ratings,
    }


def render_item_note(item: dict, existing: str | None, rating) -> str:
    fm = {
        "item_id": item["item_id"],
        "title": item.get("title", ""),
        "source_url": item.get("source_url", ""),
        "published_at": item.get("published_at", ""),
        "source_type": item.get("source_type", ""),
        "evidence_label": item.get("evidence_label", ""),
        "repository": item.get("repository", ""),
        "topics": item.get("topics", []),
        "user_facing_ai": item.get("user_facing_ai", False),
    }
    if item.get("publication"):
        fm["publication"] = item["publication"]
    if rating:
        fm["rating"] = rating["score"]
        fm["rating_revision"] = rating.get("revision", 0)
        if rating.get("reason"):
            fm["rating_reason"] = rating["reason"]
    lines = [render_frontmatter(fm), ""]
    lines.append(f"# {item.get('title', item['item_id'])}")
    lines.append("")
    lines.append(f"Source: {item.get('source_url', '')}")
    publication = item.get("publication")
    if publication:
        lines.extend(["", f"Publication: [{publication.get('venue', '')}]({publication.get('publication_url', '')})"])
    lines.append("")
    lines.append(str(item.get("summary", "")))
    lines.append("")
    lines.append(str(item.get("why_it_matters", "")))
    if item.get("user_facing_ai"):
        marker = "Proposed paper-backed product" if item.get("publication") else "AI product your users could interact with"
        lines.extend(["", f"**{marker}**"])
    if item.get("application_example"):
        lines.extend(["", "## A practical example (proposed trial)", "", str(item["application_example"])])
    guidance = item.get("guidance", [])
    if isinstance(guidance, list):
        for g in guidance:
            lines.append(f"- {g}")
    base = "\n".join(lines)
    if existing:
        _, user_notes = split_user_notes(parse_frontmatter(existing)[1])
        if user_notes:
            return base + "\n\n" + user_notes
    return base + "\n\n" + USER_SECTION + "\n\n"


def _frontmatter_rating(fm: dict):
    score = fm.get("rating")
    if (not isinstance(score, int) or isinstance(score, bool)
            or not 1 <= score <= 5):
        return None
    revision = fm.get("rating_revision", 0)
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        revision = 0
    reason = fm.get("rating_reason", "")
    if not isinstance(reason, str):
        reason = ""
    return {"score": score, "revision": revision, "reason": reason}


def _same_rating(left, right) -> bool:
    if left is None or right is None:
        return left is right
    return (left.get("score") == right.get("score")
            and left.get("revision", 0) == right.get("revision", 0)
            and left.get("reason", "") == right.get("reason", ""))


def digest_filename(digest: dict) -> str:
    return f"{safe_slug(digest['run_id'])}.md"


def render_digest_note(digest: dict, existing: str | None) -> str:
    item_ids = [it.get("item_id") for it in digest.get("items", [])
                if isinstance(it, dict) and isinstance(it.get("item_id"), str)]
    fm = {
        "run_id": digest["run_id"],
        "edition_date": digest.get("edition_date", ""),
        "generated_at": digest.get("generated_at", ""),
        "producer": digest.get("producer", ""),
        "model_id": digest.get("model_id", ""),
        "kind": digest.get("kind", "digest"),
        "item_ids": item_ids,
    }
    if "newsletter" in digest:
        fm["newsletter"] = digest["newsletter"]
    title = digest.get("title") or (f"AI Research Radar {digest.get('edition_date', digest['run_id'])}" if digest.get("newsletter") == "academic" else f"Radar Digest {digest.get('edition_date', digest['run_id'])}")
    lines = [render_frontmatter(fm), "", f"# {title}", ""]
    if item_ids:
        lines.extend(["## Items", ""])
        for it in digest.get("items", []):
            if isinstance(it, dict) and isinstance(it.get("item_id"), str):
                name = item_filename(it['item_id'], it.get('title', it['item_id']))[:-3]
                lines.append(f"- [[Items/{name}|{it.get('title', it['item_id'])}]]")
        lines.append("")
    lines.extend(["## Findings", ""])
    for item in digest.get("items", []):
        if isinstance(item, dict):
            lines.extend([f"### {item.get('title', '')}", "", item.get('summary', ''), "",
                          item.get('why_it_matters', ''), ""])
            lines.extend("- " + line for line in item.get('guidance', []))
            lines.extend(["", "Source: " + item.get('source_url', ''), ""])
    base = "\n".join(lines)
    if existing:
        try:
            _, user_notes = split_user_notes(parse_frontmatter(existing)[1])
        except SyncError:
            user_notes = None
        if user_notes:
            return base + "\n\n" + user_notes
    return base + "\n\n" + USER_SECTION + "\n\n"


def import_digests(vault: Path, digests: list) -> int:
    written = 0
    for digest in digests:
        target = safe_path(vault, "Digests", digest_filename(digest))
        existing = target.read_text(encoding="utf-8") if target.exists() else None
        rendered = render_digest_note(digest, existing)
        if existing != rendered:
            atomic_write_text(target, rendered)
            written += 1
    return written


def read_local_ratings(vault: Path) -> dict:
    ratings = {}
    items_dir = safe_path(vault, "Items")
    if not items_dir.exists():
        return ratings
    for path in items_dir.glob("*.md"):
        try:
            fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, SyncError):
            continue
        iid = fm.get("item_id")
        rating = _frontmatter_rating(fm)
        if isinstance(iid, str) and ID_RE.match(iid) and rating is not None:
            ratings[iid] = rating
    return ratings


def import_snapshot(vault: Path, snap: dict, previous_ratings=None,
                    imported_ratings=None, preserve_local_ids=None) -> int:
    written = 0
    items_dir = safe_path(vault, "Items")
    previous_ratings = previous_ratings or {}
    preserve_local_ids = preserve_local_ids or set()
    for it in snap.get("items", []):
        iid = it["item_id"]
        fname = item_filename(iid, it.get("title", iid))
        target = safe_path(vault, "Items", fname)
        existing = None
        rating = snap.get("ratings", {}).get(iid)
        if not target.exists():
            # locate by item_id prefix to preserve prior user notes
            for p in items_dir.glob(f"{iid} *.md"):
                target = safe_path(vault, "Items", p.name)
                break
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            try:
                ofm, _ = parse_frontmatter(existing)
            except SyncError:
                ofm = {}
            local_rating = _frontmatter_rating(ofm)
            synced_rating = previous_ratings.get(iid)
            if local_rating is not None:
                if iid in preserve_local_ids:
                    rating = local_rating
                else:
                    local_is_synced = _same_rating_values(local_rating, synced_rating)
                    local_matches_cloud = _same_rating_values(local_rating, rating)
                    if not local_is_synced and not local_matches_cloud:
                        # A score/reason changed since the last imported snapshot is local and wins.
                        rating = local_rating
        rendered = render_item_note(it, existing, rating)
        if existing != rendered:
            atomic_write_text(target, rendered)
            written += 1
        if imported_ratings is not None:
            imported_ratings[iid] = snap.get("ratings", {}).get(iid)
    import_digests(vault, snap.get("digests", []))
    return written


def write_dashboard(vault: Path, snap: dict) -> None:
    lines = ["---", 'title: "Radar Dashboard"', "---", "", "# Radar Dashboard", ""]
    lines.append("## Items")
    lines.append("")
    for it in snap.get("items", []):
        rating = snap.get("ratings", {}).get(it["item_id"], {})
        score = rating.get("score") if isinstance(rating, dict) else None
        suffix = f" (rated {score}/5)" if score else ""
        title = it.get("title", it["item_id"])
        target = safe_path(vault, "Items", item_filename(it["item_id"], title))
        if not target.exists():
            # Import preserves the filename when a title changes.
            for existing in safe_path(vault, "Items").glob(f"{it['item_id']} *.md"):
                target = safe_path(vault, "Items", existing.name)
                break
        lines.append(f"- [[Items/{target.stem}|{title}]]{suffix}")
    lines.extend(["", "## Digests", ""])
    for digest in snap.get("digests", []):
        lines.append(f"- [[Digests/{Path(digest_filename(digest)).stem}|{digest['run_id']}]]")
    target = safe_path(vault, "Dashboard", "Radar Dashboard.md")
    rendered = "\n".join(lines)
    if target.exists():
        try:
            _, user_notes = split_user_notes(parse_frontmatter(target.read_text(encoding="utf-8"))[1])
        except SyncError:
            user_notes = None
        if user_notes:
            rendered += "\n\n" + user_notes
    rendered += "\n"
    if not target.exists() or target.read_text(encoding="utf-8") != rendered:
        atomic_write_text(target, rendered)


def run_sync(exchange: Path, vault: Path) -> dict:
    exchange = exchange.resolve()
    vault = vault.resolve()
    ensure_vault(vault)
    snapshots_dir = safe_path(exchange, "snapshots")
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    safe_path(exchange, "feedback").mkdir(parents=True, exist_ok=True)

    state_path = safe_path(vault, ".radar-sync-state.json")
    if state_path.exists():
        try:
            state = load_json(state_path)
        except SyncError:
            state = {}
    else:
        state = {}
    if not isinstance(state, dict):
        state = {}

    # 1. export changed ratings BEFORE importing
    exported = export_ratings(vault, exchange, state, state_path=state_path)
    if state.get("last_exported") != exported:
        state = dict(state)
        state["last_exported"] = exported
        atomic_write_json(state_path, state)

    # 2. validate ALL snapshots before changing the vault
    snaps = []
    for p in snapshots_dir.glob("snapshot*.json"):
        snap = validate_snapshot(load_json(p))
        snaps.append((snapshot_order(snap), p.name.casefold(), snap))
    snaps.sort(key=lambda entry: (entry[0], entry[1]))

    pending = state.get("pending", {"items": [], "digests": [], "ratings": {}})
    last_order = state.get("last_snapshot_order")
    if (not isinstance(last_order, list) or len(last_order) != 2
            or not isinstance(last_order[0], int) or not isinstance(last_order[1], str)):
        last_order = None
    new_snaps = []
    for order, _, snap in snaps:
        order_value = [order[0], order[1].isoformat()]
        if last_order is not None and tuple(order_value) <= tuple(last_order):
            continue
        pending = apply_pending(vault, pending, snap)
        new_snaps.append(snap)
        last_order = order_value

    # A matching cloud score/reason acknowledges the pending event. A different
    # cloud revision marks it conflicted and keeps its original base revision.
    local_ratings = read_local_ratings(vault)
    raw_pending_event_ids = state.get("pending_event_ids", {})
    pending_event_ids = dict(raw_pending_event_ids) if isinstance(raw_pending_event_ids, dict) else {}
    for snap in new_snaps:
        for iid, cloud_rating in snap.get("ratings", {}).items():
            pending_rating = exported.get(iid)
            if not isinstance(pending_rating, dict):
                continue
            try:
                cloud_revision = int(cloud_rating.get("revision", 0))
                base_revision = int(pending_rating.get("revision", 0))
            except (TypeError, ValueError):
                continue
            is_pending = pending_rating.get("pending", True)
            if not is_pending or cloud_revision <= base_revision:
                continue
            if (_same_rating_values(pending_rating, cloud_rating)
                    and _same_rating_values(local_ratings.get(iid), cloud_rating)
                    and not pending_rating.get("conflicted")):
                event_key = pending_rating.get("event_key")
                if isinstance(event_key, str):
                    pending_event_ids.pop(event_key, None)
                exported[iid] = {
                    "score": cloud_rating["score"],
                    "reason": cloud_rating.get("reason", ""),
                    "revision": cloud_revision,
                    "pending": False,
                }
            elif not _same_rating_values(pending_rating, cloud_rating):
                updated = dict(pending_rating)
                updated["conflicted"] = True
                exported[iid] = updated

    # 3. apply pending atomically to state first, then vault
    new_state = {
        "last_exported": exported,
        "pending_event_ids": pending_event_ids,
        "pending": {"items": [], "digests": [], "ratings": {}},
    }
    if last_order is not None:
        new_state["last_snapshot_order"] = last_order
    imported = 0
    imported_ratings = dict(state.get("last_imported", {}))
    preserve_local_ids = {
        iid for iid, rating in exported.items()
        if isinstance(rating, dict) and rating.get("conflicted")
    }
    if pending["items"] or pending["digests"]:
        pseudo = {
            "items": pending["items"],
            "digests": pending["digests"],
            "ratings": pending["ratings"],
            "schema_version": SCHEMA_VERSION,
        }
        imported = import_snapshot(vault, pseudo, state.get("last_imported", {}),
                                   imported_ratings, preserve_local_ids)
        write_dashboard(vault, pseudo)
    new_state["last_imported"] = imported_ratings
    if state != new_state:
        atomic_write_json(state_path, new_state)
    return {"exported_events": True, "imported": imported}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m radar.sync")
    ap.add_argument("--exchange", required=True)
    ap.add_argument("--vault", required=True)
    args = ap.parse_args(argv)
    try:
        result = run_sync(Path(args.exchange), Path(args.vault))
    except SyncError as e:
        print(f"sync error: {e}", file=sys.stderr)
        return 1
    print(f"synced: exported ratings, imported {result['imported']} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
