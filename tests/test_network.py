"""Tests for Phase 8: Network allowlist management."""

import pytest

from delegate.network import (
    _validate_domain,
    allow_domain,
    disallow_domain,
    get_allowed_domains,
    is_unrestricted,
    load_config,
    reset_config,
    save_config,
)
from delegate.paths import network_config_path


@pytest.fixture
def tmp_hc(tmp_path):
    """Provide a temporary hc_home with protected/ dir."""
    hc = tmp_path / "hc"
    hc.mkdir()
    (hc / "protected").mkdir()
    return hc


# ---------------------------------------------------------------------------
# Domain validation
# ---------------------------------------------------------------------------

class TestDomainValidation:
    def test_wildcard(self):
        _validate_domain("*")

    def test_simple_domain(self):
        _validate_domain("example.com")

    def test_subdomain(self):
        _validate_domain("api.github.com")

    def test_wildcard_subdomain(self):
        _validate_domain("*.openai.com")

    def test_hyphenated_domain(self):
        _validate_domain("my-service.example.com")

    def test_invalid_domain_rejects_spaces(self):
        with pytest.raises(ValueError, match="Invalid domain pattern"):
            _validate_domain("not a domain")

    def test_invalid_domain_rejects_slashes(self):
        with pytest.raises(ValueError, match="Invalid domain pattern"):
            _validate_domain("http://example.com")

    def test_invalid_domain_rejects_empty(self):
        with pytest.raises(ValueError, match="Invalid domain pattern"):
            _validate_domain("")

    def test_invalid_domain_rejects_port(self):
        with pytest.raises(ValueError, match="Invalid domain pattern"):
            _validate_domain("example.com:8080")


# ---------------------------------------------------------------------------
# Config read/write
# ---------------------------------------------------------------------------

class TestConfig:
    def test_default_when_no_file(self, tmp_hc):
        """Returns default config when file doesn't exist."""
        config = load_config(tmp_hc)
        assert config["allowedDomains"] == ["*"]

    def test_save_and_load(self, tmp_hc):
        """Can save and load a config."""
        save_config(tmp_hc, {"allowedDomains": ["example.com"]})
        config = load_config(tmp_hc)
        assert config["allowedDomains"] == ["example.com"]

    def test_corrupt_file_returns_defaults(self, tmp_hc):
        """Corrupt YAML returns defaults."""
        path = network_config_path(tmp_hc)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{{invalid yaml::")
        config = load_config(tmp_hc)
        assert config["allowedDomains"] == ["*"]


# ---------------------------------------------------------------------------
# Allow / disallow / reset
# ---------------------------------------------------------------------------

class TestAllowDomain:
    def test_allow_replaces_wildcard(self, tmp_hc):
        """Adding a specific domain replaces '*'."""
        result = allow_domain(tmp_hc, "example.com")
        assert result == ["example.com"]
        assert not is_unrestricted(result)

    def test_allow_appends(self, tmp_hc):
        """Adding a second domain appends."""
        allow_domain(tmp_hc, "example.com")
        result = allow_domain(tmp_hc, "api.github.com")
        assert set(result) == {"example.com", "api.github.com"}

    def test_allow_idempotent(self, tmp_hc):
        """Adding same domain twice is a no-op."""
        allow_domain(tmp_hc, "example.com")
        result = allow_domain(tmp_hc, "example.com")
        assert result == ["example.com"]

    def test_allow_wildcard_domain(self, tmp_hc):
        """Can add wildcard subdomain patterns."""
        allow_domain(tmp_hc, "example.com")
        result = allow_domain(tmp_hc, "*.openai.com")
        assert "*.openai.com" in result

    def test_allow_invalid_domain_raises(self, tmp_hc):
        with pytest.raises(ValueError, match="Invalid domain pattern"):
            allow_domain(tmp_hc, "not valid!")


class TestDisallowDomain:
    def test_disallow_removes(self, tmp_hc):
        """Can remove a domain."""
        allow_domain(tmp_hc, "example.com")
        allow_domain(tmp_hc, "api.github.com")
        result = disallow_domain(tmp_hc, "example.com")
        assert result == ["api.github.com"]

    def test_disallow_last_domain_raises(self, tmp_hc):
        """Cannot remove the last domain."""
        allow_domain(tmp_hc, "example.com")
        with pytest.raises(ValueError, match="Cannot remove the last"):
            disallow_domain(tmp_hc, "example.com")

    def test_disallow_nonexistent_raises(self, tmp_hc):
        """Cannot remove a domain not in the list."""
        allow_domain(tmp_hc, "example.com")
        with pytest.raises(ValueError, match="not in the allowlist"):
            disallow_domain(tmp_hc, "other.com")


class TestReset:
    def test_reset_restores_wildcard(self, tmp_hc):
        """Reset restores the wildcard."""
        allow_domain(tmp_hc, "example.com")
        result = reset_config(tmp_hc)
        assert result == ["*"]
        assert is_unrestricted(result)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

class TestIsUnrestricted:
    def test_wildcard_is_unrestricted(self):
        assert is_unrestricted(["*"]) is True

    def test_wildcard_in_list(self):
        assert is_unrestricted(["*", "example.com"]) is True

    def test_specific_is_restricted(self):
        assert is_unrestricted(["example.com"]) is False

    def test_empty_is_restricted(self):
        assert is_unrestricted([]) is False
