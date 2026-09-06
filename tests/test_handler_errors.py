import re
import sys
from contextlib import redirect_stderr

import pytest

import logbook

from .utils import capturing_stderr_context

__file_without_pyc__ = __file__
if __file_without_pyc__.endswith(".pyc"):
    __file_without_pyc__ = __file_without_pyc__[:-1]


def test_handler_error_without_stderr(logger):
    with logbook.StderrHandler(), logbook.Flags(errors="print"):
        with redirect_stderr(None):
            logger.warning("unavailable stderr")


def test_handler_error_without_stderr_under_raise(logger):
    with logbook.StderrHandler(), logbook.Flags(errors="raise"):
        with redirect_stderr(None):
            with pytest.raises(AttributeError):
                logger.warning("unavailable stderr")


def test_handler_error_with_closed_stderr(tmp_path, logger):
    # A closed stream is truthy, so it passes the guard and its error is left
    # to the caller, which is what CPython does too.
    with (tmp_path / "stderr.log").open("w") as stream:
        pass
    with logbook.StderrHandler(), logbook.Flags(errors="print"):
        with redirect_stderr(stream):
            with pytest.raises(ValueError):
                logger.warning("unavailable stderr")


def test_handler_exception(activation_strategy, logger):
    class ErroringHandler(logbook.TestHandler):
        def emit(self, record):
            raise RuntimeError("something bad happened")

    with capturing_stderr_context() as stderr:
        with activation_strategy(ErroringHandler()):
            logger.warning("I warn you.")
    assert "something bad happened" in stderr.getvalue()
    assert "I warn you" not in stderr.getvalue()


def test_formatting_exception():
    def make_record():
        return logbook.LogRecord(
            "Test Logger",
            logbook.WARNING,
            "Hello {foo:invalid}",
            kwargs={"foo": 42},
            frame=sys._getframe(),
        )

    record = make_record()
    with pytest.raises(TypeError) as caught:
        record.message  # noqa: B018

    errormsg = str(caught.value)
    assert re.search(
        "Could not format message with provided arguments: Invalid "
        "(?:format specifier)|(?:conversion specification)|(?:format spec)",
        errormsg,
        re.M | re.S,
    )
    assert "msg='Hello {foo:invalid}'" in errormsg
    assert "args=()" in errormsg
    assert "kwargs={'foo': 42}" in errormsg
    assert re.search(
        r"Happened in file .*%s, line \d+" % re.escape(__file_without_pyc__),  # noqa: UP031
        errormsg,
        re.M | re.S,
    )
