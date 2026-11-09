"""
3ie Evidence Assistant - project access control for chat, query and chat history.

Public projects are open to everyone; private projects only to their owner.
Supabase is replaced by small fakes, so no network is needed.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import api.routes.dependencies as deps

OWNER = SimpleNamespace(id="owner-1", email="o@example.org", role="authenticated")
OTHER = SimpleNamespace(id="other-2", email="x@example.org", role="authenticated")
PRIVATE = {"id": "11111111-2222-3333-4444-555555555555", "user_id": "owner-1", "is_public": False, "name": "P"}
PUBLIC = {"id": "66666666-7777-8888-9999-000000000000", "user_id": "owner-1", "is_public": True, "name": "Q"}


@pytest.fixture
def projects(monkeypatch):
    table = {PRIVATE["id"]: PRIVATE, PUBLIC["id"]: PUBLIC, "my-slug": PRIVATE}
    monkeypatch.setattr(deps, "resolve_project", lambda ref: table.get(ref))


def test_public_project_open_to_anonymous(projects):
    assert deps.authorize_project(PUBLIC["id"], None)["id"] == PUBLIC["id"]


def test_private_project_open_to_owner(projects):
    assert deps.authorize_project(PRIVATE["id"], OWNER)["id"] == PRIVATE["id"]
    assert deps.authorize_project("my-slug", OWNER)["id"] == PRIVATE["id"]


@pytest.mark.parametrize("user, code", [(None, 401), (OTHER, 403)])
def test_private_project_closed_to_others(projects, user, code):
    with pytest.raises(HTTPException) as exc:
        deps.authorize_project(PRIVATE["id"], user)
    assert exc.value.status_code == code


def test_unknown_project_is_404(projects):
    with pytest.raises(HTTPException) as exc:
        deps.authorize_project("nope", OWNER)
    assert exc.value.status_code == 404


class FakeQuery:
    """Records filters applied to a chat_history query."""

    def __init__(self, log):
        self.log = log

    def __getattr__(self, name):
        def method(*args, **kwargs):
            self.log.append((name, args))
            return self
        return method

    def execute(self):
        self.log.append(("execute", ()))
        return SimpleNamespace(data=[])


@pytest.fixture
def history_env(monkeypatch, projects):
    import api.routes.api as api_module
    import src.auth as auth_module

    log = []
    fake = SimpleNamespace(table=lambda name: FakeQuery(log))
    monkeypatch.setattr(auth_module, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(api_module, "authorize_project", deps.authorize_project)
    return api_module, log


@pytest.mark.asyncio
async def test_history_is_per_user(history_env):
    api_module, log = history_env
    await api_module.get_chat_history(PRIVATE["id"], session_id=None, limit=10, user=OWNER)
    assert ("eq", ("user_id", OWNER.id)) in log


@pytest.mark.asyncio
async def test_anonymous_history_needs_session(history_env):
    api_module, log = history_env
    result = await api_module.get_chat_history(PUBLIC["id"], session_id=None, limit=10, user=None)
    assert result == {"history": []} and ("execute", ()) not in log


@pytest.mark.asyncio
async def test_clear_history_never_clears_everyone(history_env):
    api_module, _ = history_env
    with pytest.raises(HTTPException) as exc:
        await api_module.clear_chat_history(PUBLIC["id"], session_id=None, user=None)
    assert exc.value.status_code == 401


class _ProjectTable:
    """Answers rag_projects lookups by id; raises on anything past the access check."""

    def __init__(self, rows):
        self.rows, self.value = rows, None

    def table(self, name):
        if name != "rag_projects":
            raise RuntimeError("past the access check")
        return self

    def select(self, *a):
        return self

    def eq(self, col, value):
        self.value = value
        return self

    def execute(self):
        return SimpleNamespace(data=[r for r in self.rows if r["id"] == self.value])


@pytest.mark.parametrize("user, code", [(None, 401), (OTHER, 403)])
@pytest.mark.asyncio
async def test_highlighted_pdf_closed_to_others(monkeypatch, user, code):
    import api.routes.rags as rags
    monkeypatch.setattr(rags, "get_supabase_client", lambda: _ProjectTable([PRIVATE]))
    with pytest.raises(HTTPException) as exc:
        await rags.get_highlighted_pdf(PRIVATE["id"], "doc", user=user)
    assert exc.value.status_code == code


@pytest.mark.asyncio
async def test_highlighted_pdf_open_to_owner(monkeypatch):
    """The owner gets past the access check (it used to refuse every private project)."""
    import api.routes.rags as rags
    monkeypatch.setattr(rags, "get_supabase_client", lambda: _ProjectTable([PRIVATE]))
    with pytest.raises(Exception) as exc:
        await rags.get_highlighted_pdf(PRIVATE["id"], "doc", user=OWNER)
    assert not (isinstance(exc.value, HTTPException) and exc.value.status_code in (401, 403))
