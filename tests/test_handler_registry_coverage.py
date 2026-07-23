"""handlers/ package split -- coverage guard. Every *.py file in
handlers/ (except __init__.py) must be listed in server._HANDLER_MODULES,
and every name in _HANDLER_MODULES must correspond to a real file. Catches
the two ways this could silently drift: a new handlers/foo.py added
without registering it (its tools never load, no error), or a stale name
left in _HANDLER_MODULES after a file is renamed/removed (import error at
startup, masked by the fault-isolation mechanism's own logging)."""
from pathlib import Path

import promptwise.server as server


def _handlers_dir() -> Path:
    return Path(server.__file__).resolve().parent / "handlers"


def test_every_handler_file_is_registered():
    files = {
        p.stem for p in _handlers_dir().glob("*.py")
        if p.stem != "__init__"
    }
    registered = set(server._HANDLER_MODULES)
    missing = files - registered
    assert not missing, (
        f"handlers/*.py file(s) not in _HANDLER_MODULES (their tools will "
        f"never load): {sorted(missing)}"
    )


def test_every_registered_name_has_a_file():
    files = {
        p.stem for p in _handlers_dir().glob("*.py")
        if p.stem != "__init__"
    }
    registered = set(server._HANDLER_MODULES)
    stale = registered - files
    assert not stale, (
        f"_HANDLER_MODULES name(s) with no matching handlers/*.py file: "
        f"{sorted(stale)}"
    )
