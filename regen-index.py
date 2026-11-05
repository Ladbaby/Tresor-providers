#!/usr/bin/env python3
"""Regenerate index.json from the provider recipes in this directory.

The recipe repository is self-contained: this script needs nothing but Python 3
and the JSON files sitting next to it. It validates every recipe with the same
rules a Tresor daemon applies before installing one, so a recipe that cannot be
installed cannot be published, and then derives every index entry from the parsed
recipe rather than from a second, hand-maintained copy.

Usage:
    ./regen-index.py             validate every recipe and write index.json
    ./regen-index.py --check     exit 1 if index.json is out of date; write nothing
    ./regen-index.py --dry-run   validate and report; write nothing
    ./regen-index.py --base-url URL
                                 prefix for each entry's url

The validation mirrors internal/providers/profile.go in Tresor. If a rule changes
there, change it here too — --check in CI is what catches a recipe that this
script accepts but a daemon would refuse.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.parse import urlparse

SCHEMA = "tresor-provider-v1"
CATALOG_SCHEMA = "tresor-provider-catalog-v1"
DEFAULT_BASE_URL = "https://raw.githubusercontent.com/Ladbaby/Tresor-providers/main/"

# Mirrors forbiddenKeys in profile.go. A published recipe must never carry a
# credential: the user supplies one at install time, and a recipe is public.
FORBIDDEN_KEYS = {
    "api_key", "apikey", "client_secret", "secret", "password", "token",
    "access_token", "refresh_token", "private_key",
}

# Keys each object may carry, mirroring the json tags on the Go structs. Tresor
# parses recipes with DisallowUnknownFields, so a misspelled key is a hard error
# there; without this list it would pass here and fail for the user.
PROFILE_KEYS = {"schema", "id", "version", "name", "icon", "summary", "provider",
                "plugins", "aliases", "requires"}
PROVIDER_KEYS = {"base_url", "api_formats", "format_urls", "format_paths", "auth",
                 "models", "regions"}
REGION_KEYS = {"id", "name", "base_url", "api_formats", "format_urls", "format_paths",
               "models", "unknown_models"}
AUTH_KEYS = {
    "type", "flow", "client_id", "authorization_url", "token_url", "discovery_url",
    "redirect_port", "redirect_path", "device_auth_url", "device_token_url",
    "device_verify_url", "device_redirect_uri", "scopes", "extra_authorize_params",
    "extra_headers", "wire", "allowed_endpoint_hosts", "request_nonce",
    "require_refresh_token", "refresh_on_unknown_expiry", "refresh_skew_secs",
    "default_token_lifetime_secs", "persist_discovered_endpoints",
}
PLUGIN_KEYS = {"id", "version", "config", "url", "sha256"}
ALIAS_KEYS = {"input_model_id", "output_model_id", "is_regex"}
REQUIRES_KEYS = {"features", "min_version"}

SLUG_EXTRA = "-_."
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
NESTED_KEYMAP = {
    "provider": PROVIDER_KEYS,
    "regions": REGION_KEYS,
    "auth": AUTH_KEYS,
    "plugins": PLUGIN_KEYS,
    "aliases": ALIAS_KEYS,
    "requires": REQUIRES_KEYS,
}


class RecipeError(Exception):
    """A recipe a daemon would refuse, so it must not reach index.json."""


def _slug(value: str) -> bool:
    return all(c.isascii() and (c.isalnum() or c in SLUG_EXTRA) for c in value)


def _finding(obj, allowed: set[str], where: str) -> str | None:
    unknown = sorted(set(obj) - allowed)
    if unknown:
        return f"{where}: unknown field {unknown[0]!r} (a daemon parses recipes with DisallowUnknownFields)"
    return None


def find_forbidden_key(value, path="") -> str | None:
    """Return the first credential-shaped key, matching profile.go's recursive scan."""
    if isinstance(value, dict):
        for key in sorted(value):
            if key.lower() in FORBIDDEN_KEYS:
                return key
            found = find_forbidden_key(value[key], f"{path}.{key}" if path else key)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_forbidden_key(item, path)
            if found:
                return found
    return None


def validate_region(region, provider, index: int) -> str | None:
    where = f"provider.regions[{index}]"
    if not isinstance(region, dict):
        return f"{where}: must be an object"
    bad = _finding(region, REGION_KEYS, where)
    if bad:
        return bad

    rid = region.get("id")
    if not isinstance(rid, str) or not rid.strip():
        return f"{where}.id is required"
    if not _slug(rid):
        return f"{where}.id {rid!r} must be a slug (letters, digits, '-', '_', '.')"

    # A region inherits the provider's base_url; one that has neither would
    # install to nowhere.
    if not str(region.get("base_url") or "").strip() and not str(provider.get("base_url") or "").strip():
        return f"region {rid} needs a base_url: the provider declares none to inherit"

    models = region.get("models") or []
    if region.get("unknown_models") and models:
        return f"region {rid} declares both models and unknown_models; keep one"
    return None


def validate_profile(profile, path: str) -> str | None:
    """Validate one recipe. Returns the first problem, or None when it is installable."""
    if not isinstance(profile, dict):
        return "recipe must be a JSON object"

    # Credentials are checked before anything else, matching Parse in profile.go:
    # a leaked secret is the finding that must never be masked by a structural
    # complaint elsewhere in the same file.
    leaked = find_forbidden_key(profile)
    if leaked:
        return (f'recipe must not contain credentials (found {leaked!r}); '
                f"supply credentials at install time instead")

    bad = _finding(profile, PROFILE_KEYS, "profile")
    if bad:
        return bad

    if profile.get("schema") != SCHEMA:
        return f"unsupported profile schema {profile.get('schema')!r} (want {SCHEMA!r})"

    pid = profile.get("id")
    if not isinstance(pid, str) or not pid.strip():
        return "id is required"
    if any(c in pid for c in " \t\r\n/"):
        return f"id {pid!r} must not contain whitespace or '/'"

    version = profile.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        return f"version must be at least 1"

    if not isinstance(profile.get("name"), str) or not profile.get("name").strip():
        return "name is required"

    provider = profile.get("provider")
    if not isinstance(provider, dict):
        return "provider is required"
    bad = _finding(provider, PROVIDER_KEYS, "provider")
    if bad:
        return bad

    regions = provider.get("regions") or []
    if not isinstance(regions, list):
        return "provider.regions must be a list"
    if not str(provider.get("base_url") or "").strip() and not regions:
        return "provider.base_url or at least one provider.regions entry is required"

    seen = set()
    for i, region in enumerate(regions):
        err = validate_region(region, provider, i)
        if err:
            return err
        if region["id"] in seen:
            return f"region {region['id']!r} is listed twice"
        seen.add(region["id"])

    auth = provider.get("auth") or {}
    if not isinstance(auth, dict):
        return "provider.auth must be an object"
    bad = _finding(auth, AUTH_KEYS, "provider.auth")
    if bad:
        return bad
    auth_type = auth.get("type") or "api_key"
    if auth_type not in ("api_key", "oauth"):
        return f"auth.type {auth_type!r} must be api_key or oauth"
    wire = auth.get("wire") or ""
    if wire and (len(wire) > 64 or not _slug(wire)):
        return f"auth.wire {wire!r} must be a dialect name (letters, digits, '-', '_', '.')"
    if auth_type == "oauth":
        flow = auth.get("flow")
        if flow == "auth_code":
            if not auth.get("discovery_url") and not (auth.get("authorization_url") and auth.get("token_url")):
                return "auth_code flow needs discovery_url or both authorization_url and token_url"
        elif flow == "device":
            if not auth.get("device_auth_url") or not auth.get("device_token_url"):
                return "device flow needs device_auth_url and device_token_url"
        else:
            return f"oauth flow {flow!r} must be auth_code or device"

    seen_plugins = set()
    for i, plugin in enumerate(profile.get("plugins") or []):
        if not isinstance(plugin, dict):
            return f"plugins[{i}] must be an object"
        bad = _finding(plugin, PLUGIN_KEYS, f"plugins[{i}]")
        if bad:
            return bad
        if not str(plugin.get("id") or "").strip():
            return f"plugins[{i}].id is required"
        if plugin["id"] in seen_plugins:
            return f"plugin {plugin['id']!r} is listed twice"
        seen_plugins.add(plugin["id"])
        url = plugin.get("url") or ""
        if url:
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username:
                return f"plugins[{i}].url must be a public HTTPS URL"
        sha = plugin.get("sha256") or ""
        if sha and not HEX_SHA256.match(sha):
            return f"plugins[{i}].sha256 must be a lowercase hex sha256 digest"

    seen_aliases = set()
    for i, alias in enumerate(profile.get("aliases") or []):
        if not isinstance(alias, dict):
            return f"aliases[{i}] must be an object"
        bad = _finding(alias, ALIAS_KEYS, f"aliases[{i}]")
        if bad:
            return bad
        if not str(alias.get("input_model_id") or "").strip() or not str(alias.get("output_model_id") or "").strip():
            return f"aliases[{i}] needs input_model_id and output_model_id"
        if alias["input_model_id"] in seen_aliases:
            return f"alias input {alias['input_model_id']!r} is listed twice"
        seen_aliases.add(alias["input_model_id"])

    requires = profile.get("requires") or {}
    if not isinstance(requires, dict):
        return "requires must be an object"
    bad = _finding(requires, REQUIRES_KEYS, "requires")
    if bad:
        return bad

    return None


def build_entry(profile, base_url: str) -> dict:
    """Derive one index entry. Field order matches CatalogEntry in catalog.go."""
    provider = profile.get("provider") or {}
    requires = profile.get("requires") or {}

    entry = {"id": profile["id"], "name": profile["name"]}
    if profile.get("icon"):
        entry["icon"] = profile["icon"]
    entry["version"] = profile["version"]
    if profile.get("summary"):
        entry["summary"] = profile["summary"]
    entry["url"] = base_url + profile["id"] + ".json"
    if requires.get("features"):
        entry["features"] = requires["features"]
    if requires.get("min_version"):
        entry["min_version"] = requires["min_version"]
    if profile.get("plugins"):
        entry["needs_plugins"] = True
    if provider.get("regions"):
        regions = []
        for region in provider["regions"]:
            published = {"id": region["id"]}
            if region.get("name"):
                published["name"] = region["name"]
            regions.append(published)
        entry["regions"] = regions
    return entry


def generate(directory: str, base_url: str):
    """Validate every recipe and return (entries, failures)."""
    if not base_url.endswith("/"):
        base_url += "/"

    failures, entries, seen_ids = [], [], {}

    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json") or name == "index.json":
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, encoding="utf-8") as handle:
                profile = json.load(handle)
        except json.JSONDecodeError as exc:
            failures.append(f"{name}: not valid JSON: {exc}")
            continue

        error = validate_profile(profile, path)
        if error:
            failures.append(f"{name}: {error}")
            continue

        pid = profile["id"]
        if pid != name[: -len(".json")]:
            failures.append(f'{name}: id {pid!r} does not match the file name')
            continue
        if pid in seen_ids:
            failures.append(f"{name}: id {pid!r} is also used by {seen_ids[pid]}")
            continue
        seen_ids[pid] = name
        entries.append(build_entry(profile, base_url))

    # Alphabetical for the user, with the id breaking ties so the order is total
    # and stable — a regeneration must not reshuffle the file.
    entries.sort(key=lambda e: (e["name"], e["id"]))
    return entries, failures


def compare(current: list, fresh: list) -> list[str]:
    """Describe differences between the published entries and freshly built ones."""
    old = {entry["id"]: entry for entry in current}
    new = {entry["id"]: entry for entry in fresh}
    lines = []
    for pid, entry in new.items():
        if pid not in old:
            lines.append(f"  missing from index.json: {pid}")
        elif json.dumps(old[pid], sort_keys=True) != json.dumps(entry, sort_keys=True):
            lines.append(f"  differs: {pid}")
    for pid in old:
        if pid not in new:
            lines.append(f"  no longer on disk: {pid}")
    if not lines and len(current) != len(fresh):
        lines.append(f"  entry count {len(current)} vs {len(fresh)}")
    return sorted(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the provider catalog's index.json from the recipes beside it.")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if index.json is out of date; write nothing")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate and report; write nothing")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help="prefix for each entry's url")
    args = parser.parse_args(argv)

    if args.check and args.dry_run:
        parser.error("--check and --dry-run are mutually exclusive")

    directory = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(directory, "index.json")

    entries, failures = generate(directory, args.base_url)

    for entry in entries:
        regions = len(entry.get("regions") or [])
        print(f"ok   {entry['id']:<30} v{entry['version']:<3} {entry['name']:<26} regions={regions}")

    if failures:
        print(f"\n{len(failures)} recipe(s) failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        print(f"error: {len(failures)} of {len(entries) + len(failures)} recipes are invalid; "
              f"index.json was not written", file=sys.stderr)
        return 1

    if not entries:
        print(f"error: no recipes found in {directory}", file=sys.stderr)
        return 1

    if args.check:
        try:
            with open(index_path, encoding="utf-8") as handle:
                current = json.load(handle)
        except FileNotFoundError:
            print("error: index.json does not exist; run this script to create it", file=sys.stderr)
            return 1
        except json.JSONDecodeError as exc:
            print(f"error: index.json is not valid JSON: {exc}", file=sys.stderr)
            return 1
        diff = compare(current.get("entries") or [], entries)
        if diff:
            print("\nerror: index.json is out of date:", file=sys.stderr)
            print("\n".join(diff), file=sys.stderr)
            print("run without --check to regenerate it", file=sys.stderr)
            return 1
        print(f"\nindex.json is up to date ({len(entries)} entries)")
        return 0

    if args.dry_run:
        print(f"\n{len(entries)} entries ready; nothing written (drop --dry-run to update index.json)")
        return 0

    updated = _now_utc()
    # Keep the previous timestamp when nothing changed, so re-running does not
    # manufacture a diff that claims the catalog moved.
    try:
        with open(index_path, encoding="utf-8") as handle:
            previous = json.load(handle)
        if not compare(previous.get("entries") or [], entries):
            updated = previous.get("updated") or updated
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    payload = {"schema": CATALOG_SCHEMA, "updated": updated, "entries": entries}
    with open(index_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"\nwrote {index_path} with {len(entries)} entries")
    return 0


def _now_utc() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    sys.exit(main())
