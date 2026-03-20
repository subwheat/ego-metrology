import asyncio

from ego_metrology import __version__
import server

def test_package_version_is_021():
    assert __version__ == "0.3.0"

def test_server_uses_package_version():
    assert server.app.version == __version__

def test_health_returns_package_version():
    payload = asyncio.run(server.health())
    assert payload["version"] == __version__
