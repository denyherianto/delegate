"""Network allowlist management.

The global network allowlist lives at ``protected/network.yaml`` and
controls which domains agents are permitted to contact.  The file is
outside the agent sandbox so agents cannot tamper with it.

Format::

    allowedDomains:
      - "*"          # default — no restriction
      # or specific domains:
      - "api.github.com"
      - "*.openai.com"

Management is via the ``delegate network`` CLI commands.  The allowlist
is read at Telephone creation time and changes trigger Telephone
recreation (same pattern as repo-list change detection).
"""

import re
import logging
from pathlib import Path
from typing import Any

import yaml

from delegate.paths import network_config_path

logger = logging.getLogger(__name__)

# Default config when no file exists yet
_DEFAULT_CONFIG: dict[str, Any] = {"allowedDomains": ["*"]}

# Domain validation pattern:
#   - "*" (wildcard all)
#   - "*.example.com" (wildcard subdomain)
#   - "example.com" (exact domain)
#   - "sub.example.com" (exact domain with subdomain)
_DOMAIN_PATTERN = re.compile(
    r"^(\*|(\*\.)?[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*)$"
)


def _validate_domain(domain: str) -> None:
    """Raise ValueError if *domain* is not a valid domain pattern."""
    if not _DOMAIN_PATTERN.match(domain):
        raise ValueError(
            f"Invalid domain pattern: '{domain}'. "
            "Must be '*', a domain like 'example.com', "
            "or a wildcard like '*.example.com'."
        )


def load_config(hc_home: Path) -> dict[str, Any]:
    """Load the network config, returning defaults if the file is missing."""
    path = network_config_path(hc_home)
    if not path.exists():
        return dict(_DEFAULT_CONFIG)
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception:
        logger.warning("Corrupt network.yaml — returning defaults")
        return dict(_DEFAULT_CONFIG)
    if "allowedDomains" not in data:
        data["allowedDomains"] = ["*"]
    return data


def save_config(hc_home: Path, config: dict[str, Any]) -> None:
    """Write the network config to disk."""
    path = network_config_path(hc_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(config, default_flow_style=False))


def get_allowed_domains(hc_home: Path) -> list[str]:
    """Return the current domain allowlist."""
    return load_config(hc_home).get("allowedDomains", ["*"])


def allow_domain(hc_home: Path, domain: str) -> list[str]:
    """Add a domain to the allowlist. Returns the updated list."""
    _validate_domain(domain)
    config = load_config(hc_home)
    domains = config.get("allowedDomains", ["*"])

    if domain in domains:
        return domains  # Already present

    # If adding a specific domain and the list is ["*"], replace the wildcard
    if domains == ["*"] and domain != "*":
        domains = [domain]
    else:
        domains.append(domain)

    config["allowedDomains"] = domains
    save_config(hc_home, config)
    return domains


def disallow_domain(hc_home: Path, domain: str) -> list[str]:
    """Remove a domain from the allowlist. Returns the updated list.

    Raises ValueError if removing would leave the list empty.
    """
    _validate_domain(domain)
    config = load_config(hc_home)
    domains = config.get("allowedDomains", ["*"])

    if domain not in domains:
        raise ValueError(f"Domain '{domain}' is not in the allowlist.")

    if len(domains) == 1:
        raise ValueError(
            "Cannot remove the last domain. Use 'delegate network reset' "
            "to restore the default wildcard, or add another domain first."
        )

    domains.remove(domain)
    config["allowedDomains"] = domains
    save_config(hc_home, config)
    return domains


def reset_config(hc_home: Path) -> list[str]:
    """Reset the allowlist to the default wildcard ``["*"]``."""
    config = dict(_DEFAULT_CONFIG)
    save_config(hc_home, config)
    return config["allowedDomains"]


def is_unrestricted(domains: list[str]) -> bool:
    """Return True if the allowlist permits all domains."""
    return domains == ["*"] or "*" in domains
