#!/usr/bin/env python3
"""
Submit a signed application request to a YAML-configured application API.

Runtime details are loaded from a local YAML file so the public repo can contain
reusable integration code without exposing private application data.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml

DEFAULT_CONFIG_PATH = "application.yaml"


@dataclass(frozen=True)
class ApplicationConfig:
    endpoint: str
    default_secret: str
    secret_env_var: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ApiResult:
    status_code: int
    body: str


def load_config(config_path: Path) -> ApplicationConfig:
    """Load API settings and application payload data from a YAML file."""
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            f"Copy application.example.yaml to {DEFAULT_CONFIG_PATH} and fill in local details."
        )

    with config_path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file)

    if not isinstance(loaded, dict):
        raise ValueError("Config file must contain a YAML object at the top level.")

    api = loaded.get("api")
    if not isinstance(api, dict):
        raise ValueError("Config file must contain an api object.")

    payload = loaded.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Config file must contain a payload object.")

    endpoint = read_required_string(api, "endpoint")
    default_secret = read_required_string(api, "defaultSecret", "default_secret")
    secret_env_var = read_required_string(api, "secretEnvVar", "secret_env_var")

    return ApplicationConfig(
        endpoint=endpoint,
        default_secret=default_secret,
        secret_env_var=secret_env_var,
        payload=dict(payload),
    )


def read_required_string(data: dict[str, Any], *keys: str) -> str:
    """Read a non-empty string from one of the accepted YAML key names."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value

    display_keys = " or ".join(keys)
    raise ValueError(f"api.{display_keys} is required and must be a non-empty string.")


def get_secret(config: ApplicationConfig) -> str:
    """Return the HMAC secret, preferring the configured environment variable."""
    override = os.getenv(config.secret_env_var)
    return override if override is not None else config.default_secret


def canonical_json(payload: dict[str, Any]) -> str:
    """Return deterministic JSON. This exact string is signed and sent."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def sign_body(raw_body: str, secret: str) -> str:
    """Return the hex-encoded HMAC-SHA256 signature for the raw request body."""
    return hmac.new(
        secret.encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_config(config: ApplicationConfig) -> list[str]:
    """Validate API settings from the YAML file."""
    errors: list[str] = []

    if not is_url(config.endpoint):
        errors.append("api.endpoint must be a valid http(s) URL")

    if not config.default_secret:
        errors.append("api.defaultSecret must be a non-empty string")

    if not config.secret_env_var:
        errors.append("api.secretEnvVar must be a non-empty string")

    return errors


def validate_payload(payload: dict[str, Any]) -> list[str]:
    """Validate the payload locally so API mistakes are caught before submission."""
    errors: list[str] = []

    required_string_fields = ["name", "email", "resume", "location", "linkedin", "codeLink"]
    for field in required_string_fields:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} is required and must be a non-empty string")

    for field in ["resume", "linkedin", "codeLink", "repos"]:
        value = payload.get(field)
        if value and (not isinstance(value, str) or not is_url(value)):
            errors.append(f"{field} must be a valid http(s) URL")

    for field in ["notes"]:
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            errors.append(f"{field} must be a string")

    email = payload.get("email")
    if isinstance(email, str) and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors.append("email must look like a valid email address")

    for field in ["yearsPython", "yearsDjango"]:
        value = payload.get(field)
        if value is not None and (type(value) is not int or value < 0):
            errors.append(f"{field} must be a non-negative integer")

    return errors


def post_application(
    endpoint: str,
    raw_body: str,
    signature: str,
    timeout_seconds: int = 30,
) -> ApiResult:
    response = requests.post(
        endpoint,
        data=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-HMAC-Signature": signature,
        },
        timeout=timeout_seconds,
    )
    return ApiResult(status_code=response.status_code, body=response.text)


def print_json(title: str, value: Any) -> None:
    print(f"\n{title}")
    print(json.dumps(value, indent=2, sort_keys=True))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit an application with an HMAC-signed POST request."
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to local YAML application config. Default: {DEFAULT_CONFIG_PATH}",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Actually submit the application. Without this flag, the script performs a dry run.",
    )
    parser.add_argument(
        "--show-raw-body",
        action="store_true",
        help="Print the exact compact JSON body that will be signed and sent.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    config_path = Path(args.config)

    try:
        config = load_config(config_path)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        print(f"Unable to load application config: {exc}")
        return 1

    errors = validate_config(config) + validate_payload(config.payload)
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 2

    raw_body = canonical_json(config.payload)
    signature = sign_body(raw_body, get_secret(config))

    print("Validation passed.")
    print(f"\nEndpoint: {config.endpoint}")
    print_json("Application payload:", config.payload)
    print(f"\nHMAC-SHA256 signature: {signature}")

    if args.show_raw_body:
        print("\nRaw JSON body that will be signed and sent:")
        print(raw_body)

    if not args.submit:
        print("\nDry run complete. Re-run with --submit to send the application.")
        return 0

    print("\nSubmitting application...")
    try:
        result = post_application(config.endpoint, raw_body, signature)
    except requests.RequestException as exc:
        print(f"Submission failed before receiving an API response: {exc}")
        return 3

    print(f"Status code: {result.status_code}")
    try:
        parsed = json.loads(result.body)
        print_json("API response:", parsed)
    except json.JSONDecodeError:
        print("API response body:")
        print(result.body)

    if result.status_code != 201:
        print("Application was not accepted. Review the API response and resubmit after fixing the issue.")
        return 4

    print("Application submitted successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
