import asyncio

from promptwise.core import session_context


def test_get_current_session_id_returns_a_stable_default_value():
    first = session_context.get_current_session_id()
    second = session_context.get_current_session_id()
    assert first == second
    assert isinstance(first, str)
    assert len(first) > 0


def test_set_current_session_id_overrides_within_the_current_context():
    token = session_context.set_current_session_id("explicit-session-id")
    try:
        assert session_context.get_current_session_id() == "explicit-session-id"
    finally:
        session_context.reset_current_session_id(token)


def test_reset_restores_the_prior_value():
    original = session_context.get_current_session_id()
    token = session_context.set_current_session_id("temporary-value")
    session_context.reset_current_session_id(token)
    assert session_context.get_current_session_id() == original


def test_concurrent_async_tasks_do_not_leak_session_id_into_each_other():
    """The actual correctness property this refactor exists for: two
    'concurrent' connections must never see each other's session_id."""
    results: dict[str, str] = {}

    async def _run_as(label: str, session_id: str):
        token = session_context.set_current_session_id(session_id)
        try:
            await asyncio.sleep(0)  # yield control, invite interleaving
            results[label] = session_context.get_current_session_id()
        finally:
            session_context.reset_current_session_id(token)

    async def _main():
        await asyncio.gather(_run_as("a", "session-a"), _run_as("b", "session-b"))

    asyncio.run(_main())
    assert results == {"a": "session-a", "b": "session-b"}


def test_get_current_remote_identity_defaults_to_none():
    assert session_context.get_current_remote_identity() is None


def test_set_current_remote_identity_overrides_within_the_current_context():
    token = session_context.set_current_remote_identity("identity-a")
    try:
        assert session_context.get_current_remote_identity() == "identity-a"
    finally:
        session_context.reset_current_remote_identity(token)


def test_reset_restores_the_prior_remote_identity():
    original = session_context.get_current_remote_identity()
    token = session_context.set_current_remote_identity("temporary-identity")
    session_context.reset_current_remote_identity(token)
    assert session_context.get_current_remote_identity() == original


def test_concurrent_async_tasks_do_not_leak_remote_identity_into_each_other():
    """The same correctness property session_id's concurrency test proves,
    for remote_identity: two 'concurrent' connections authenticated with
    different tokens must never see each other's identity (this is the
    exact race a plain ServerContext.remote_identity field had -- see
    session_context.py's module docstring)."""
    results: dict[str, str] = {}

    async def _run_as(label: str, identity: str):
        token = session_context.set_current_remote_identity(identity)
        try:
            await asyncio.sleep(0)  # yield control, invite interleaving
            results[label] = session_context.get_current_remote_identity()
        finally:
            session_context.reset_current_remote_identity(token)

    async def _main():
        await asyncio.gather(_run_as("a", "identity-a"), _run_as("b", "identity-b"))

    asyncio.run(_main())
    assert results == {"a": "identity-a", "b": "identity-b"}
