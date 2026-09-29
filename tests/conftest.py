"""Pytest fixtures and configuration."""

import socket

import pytest


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Ensure no tests make network calls or DNS lookups."""

    def _guarded_connect(self, *args, **kwargs):
        raise RuntimeError(f"Network call blocked during tests: connect{args}")

    def _guarded_getaddrinfo(*args, **kwargs):
        raise RuntimeError(f"DNS lookup blocked during tests: getaddrinfo{args}")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", _guarded_getaddrinfo)
