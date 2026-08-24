"""Pytest configuration and async test runner hook."""

import asyncio
import inspect


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test to run with asyncio")


def pytest_pyfunc_call(pyfuncitem):
    """Automatically run async test functions via asyncio.run without external plugins."""
    if inspect.iscoroutinefunction(pyfuncitem.obj):
        testargs = {
            arg: pyfuncitem.funcargs[arg]
            for arg in pyfuncitem._fixtureinfo.argnames
            if arg in pyfuncitem.funcargs
        }
        asyncio.run(pyfuncitem.obj(**testargs))
        return True
    return None
