"""Tests for Phase 9: Daemon singleton with fcntl.flock()."""

import fcntl
import os

import pytest

from delegate.daemon import _acquire_lock, _release_lock
from delegate.paths import daemon_lock_path


@pytest.fixture
def tmp_hc(tmp_path):
    hc = tmp_path / "hc"
    hc.mkdir()
    (hc / "protected").mkdir()
    return hc


class TestAcquireLock:
    def test_acquires_lock_successfully(self, tmp_hc):
        """First call to _acquire_lock succeeds."""
        fd = _acquire_lock(tmp_hc)
        assert fd >= 0  # valid file descriptor
        # Lock file should exist
        assert daemon_lock_path(tmp_hc).exists()
        _release_lock(fd)

    def test_lock_file_contains_pid(self, tmp_hc):
        """Lock file contains the current PID."""
        fd = _acquire_lock(tmp_hc)
        lock_path = daemon_lock_path(tmp_hc)
        content = lock_path.read_text().strip()
        assert content == str(os.getpid())
        _release_lock(fd)

    def test_second_acquire_raises(self, tmp_hc):
        """Second call to _acquire_lock raises RuntimeError."""
        fd = _acquire_lock(tmp_hc)
        try:
            with pytest.raises(RuntimeError, match="already running"):
                _acquire_lock(tmp_hc)
        finally:
            _release_lock(fd)

    def test_release_allows_reacquire(self, tmp_hc):
        """After releasing, lock can be acquired again."""
        fd1 = _acquire_lock(tmp_hc)
        _release_lock(fd1)

        fd2 = _acquire_lock(tmp_hc)
        assert fd2 >= 0
        _release_lock(fd2)

    def test_lock_survives_close_fd_not_release(self, tmp_hc):
        """Closing the fd releases the lock (OS behaviour).

        This verifies that the OS releases the advisory lock when the
        fd is closed — which is the safety net for process crashes.
        """
        fd = _acquire_lock(tmp_hc)
        # Closing the fd directly releases the flock
        os.close(fd)

        # Should be able to reacquire
        fd2 = _acquire_lock(tmp_hc)
        assert fd2 >= 0
        _release_lock(fd2)


class TestReleaseLock:
    def test_release_is_safe_on_bad_fd(self):
        """Calling _release_lock with a bad fd doesn't crash."""
        _release_lock(-1)

    def test_double_release_is_safe(self, tmp_hc):
        """Double-releasing doesn't crash."""
        fd = _acquire_lock(tmp_hc)
        _release_lock(fd)
        _release_lock(fd)  # should be a no-op
