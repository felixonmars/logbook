import errno
import os
import sys

import pytest

import logbook

from .utils import capturing_stderr_context


def test_error_flag(logger):
    with capturing_stderr_context() as captured:
        with logbook.Flags(errors="print"):
            with logbook.Flags(errors="silent"):
                logger.warning("Foo {42}", "aha")
        assert captured.getvalue() == ""

        with logbook.Flags(errors="silent"):
            with logbook.Flags(errors="print"):
                logger.warning("Foo {42}", "aha")
        assert captured.getvalue() != ""

        with pytest.raises(Exception) as caught:
            with logbook.Flags(errors="raise"):
                logger.warning("Foo {42}", "aha")
        assert "Could not format message with provided arguments" in str(caught.value)


def test_disable_introspection(logger):
    with logbook.Flags(introspection=False):
        with logbook.TestHandler() as h:
            logger.warning("Testing")
            assert h.records[0].frame is None
            assert h.records[0].calling_frame is None
            assert h.records[0].module is None


def test_file_error_flag_raise(tmp_path, logger, capsys):
    filename = tmp_path / "missing" / "output.log"
    with logbook.FileHandler(filename, delay=True), logbook.Flags(errors="raise"):
        with pytest.raises(FileNotFoundError) as caught:
            logger.warning("Cannot open the log file")

    assert caught.value.filename == str(filename)
    assert capsys.readouterr().err == ""


def test_file_error_flag_print(tmp_path, logger, capsys):
    filename = tmp_path / "missing" / "output.log"
    with logbook.FileHandler(filename, delay=True), logbook.Flags(errors="print"):
        logger.warning("Cannot open the log file")

    stderr = capsys.readouterr().err
    assert "FileNotFoundError" in stderr
    assert "Logged from file" in stderr
    assert repr(os.fspath(filename)) in stderr


def test_file_error_flag_silent(tmp_path, logger, capsys):
    filename = tmp_path / "missing" / "output.log"
    with logbook.FileHandler(filename, delay=True), logbook.Flags(errors="silent"):
        logger.warning("Cannot open the log file")

    assert capsys.readouterr().err == ""


class BrokenStderr:
    """A stderr whose writes fail the way a closed pipe does."""

    def __init__(self, fail_on=None):
        self.fail_on = fail_on
        self.attempted = []
        self.written = []

    def write(self, text):
        self.attempted.append(text)
        if self.fail_on is None or text.startswith(self.fail_on):
            raise OSError(errno.EPIPE, "Broken pipe")
        self.written.append(text)
        return len(text)

    def flush(self):
        pass


def test_file_error_flag_print_broken_stderr(tmp_path, logger, monkeypatch):
    # Reporting the error must not itself raise, or a broken pipe on stderr
    # turns every log call into a crash.
    filename = tmp_path / "missing" / "output.log"
    stderr = BrokenStderr()
    monkeypatch.setattr(sys, "stderr", stderr)

    with logbook.FileHandler(filename, delay=True), logbook.Flags(errors="print"):
        logger.warning("Cannot open the log file")

    assert stderr.attempted, "the error was never reported to stderr"
    assert stderr.written == []


def test_file_error_flag_print_broken_stderr_trailer(tmp_path, logger, monkeypatch):
    # The same protection has to cover the trailing line, which is written
    # separately from the traceback above it.
    filename = tmp_path / "missing" / "output.log"
    stderr = BrokenStderr(fail_on="Logged from file")
    monkeypatch.setattr(sys, "stderr", stderr)

    with logbook.FileHandler(filename, delay=True), logbook.Flags(errors="print"):
        logger.warning("Cannot open the log file")

    assert "FileNotFoundError" in "".join(stderr.written)
    assert any(text.startswith("Logged from file") for text in stderr.attempted)
