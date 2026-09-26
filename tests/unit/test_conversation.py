from __future__ import annotations

import pytest

from nebula_mcp.errors import NebulaMCPError
from nebula_mcp.models import QueryInput
from nebula_mcp.service import NebulaService
from tests.unit.test_service import FakeGateway, FakeResult


def missing_graph(code="NS209"):
    result = FakeResult([])
    result.status_code = code
    return result


@pytest.mark.anyio
async def test_missing_graph_retains_query_then_select_resumes_once(settings):
    gateway = FakeGateway([missing_graph(), FakeResult([]), FakeResult([{"n": 1}])])
    service = NebulaService(settings.model_copy(update={"default_graph": None}), gateway)
    with pytest.raises(NebulaMCPError) as caught:
        await service.execute_query(QueryInput(statement="MATCH (n) RETURN n", max_rows=3))
    assert caught.value.code == "GRAPH_SELECTION_REQUIRED"
    output = await service.select_graph("demo")
    assert output.result.table.rows == [{"n": 1}]
    assert output.result.query.graph == "demo"
    assert output.result.query.display_statement == "MATCH (n) RETURN n"
    assert gateway.statements == ["PROFILE MATCH (n) RETURN n", "SESSION SET GRAPH demo", "PROFILE MATCH (n) RETURN n"]
    gateway.results.append(FakeResult([]))
    assert (await service.select_graph("other")).result is None


@pytest.mark.anyio
async def test_selection_failure_preserves_pending_and_previous_graph(settings):
    gateway = FakeGateway([missing_graph(), missing_graph("01G03"), FakeResult([]), FakeResult([])])
    service = NebulaService(settings, gateway)
    with pytest.raises(NebulaMCPError):
        await service.execute_query(QueryInput(statement="MATCH (n) RETURN n"))
    with pytest.raises(NebulaMCPError):
        await service.select_graph("missing")
    assert service.selected_graph is None
    assert (await service.select_graph("demo")).result is not None


@pytest.mark.anyio
async def test_query_error_does_not_become_pending(settings):
    gateway = FakeGateway([missing_graph("NS001"), FakeResult([])])
    service = NebulaService(settings, gateway)
    output = await service.execute_query(QueryInput(statement="RETURN unknown"))
    assert output.status.ok is False
    assert (await service.select_graph("demo")).result is None


@pytest.mark.anyio
async def test_graph_selection_cannot_inject_mutation(settings):
    gateway = FakeGateway()
    service = NebulaService(settings, gateway)
    with pytest.raises(NebulaMCPError):
        await service.select_graph("demo; DROP GRAPH demo")
    assert gateway.statements == []


@pytest.mark.anyio
async def test_selection_replaces_missing_explicit_graph_only(settings):
    gateway = FakeGateway([missing_graph("01G03"), FakeResult([]), FakeResult([])])
    service = NebulaService(settings, gateway)
    with pytest.raises(NebulaMCPError):
        await service.execute_query(QueryInput(statement="USE old MATCH (n) RETURN n"))
    result = (await service.select_graph("new_graph")).result
    assert result.query.display_statement == "USE new_graph MATCH (n) RETURN n"
    assert result.query.graph == "new_graph"


@pytest.mark.anyio
@pytest.mark.parametrize('statement, expected', [
    ('USE old/*comment*/ MATCH (n) RETURN n', 'USE new_graph/*comment*/ MATCH (n) RETURN n'),
    ('USE old//comment\nMATCH (n) RETURN n', 'USE new_graph//comment\nMATCH (n) RETURN n'),
    ('USE `old` MATCH (n) RETURN n', 'USE new_graph MATCH (n) RETURN n'),
    ('EXPLAIN USE old MATCH (n) RETURN n', 'EXPLAIN USE new_graph MATCH (n) RETURN n'),
    ('PROFILE USE /schema/old MATCH (n) RETURN n', 'PROFILE USE new_graph MATCH (n) RETURN n'),
    ('/*before*/ USE /*graph*/ `old` MATCH (n) RETURN n', '/*before*/ USE /*graph*/ new_graph MATCH (n) RETURN n'),
])
async def test_resume_replaces_only_original_graph_token(settings, statement, expected):
    gateway = FakeGateway([missing_graph('01G03'), FakeResult([]), FakeResult([])])
    service = NebulaService(settings, gateway)
    with pytest.raises(NebulaMCPError):
        await service.execute_query(QueryInput(statement=statement))
    result = (await service.select_graph('new_graph')).result
    assert result.query.display_statement == expected
    assert result.query.graph == 'new_graph'


@pytest.mark.anyio
async def test_quoted_graph_metadata_is_not_the_following_keyword(settings):
    service = NebulaService(settings, FakeGateway([FakeResult([])]))
    result = await service.execute_query(QueryInput(statement='USE `demo` MATCH (n) RETURN n'))
    assert result.query.graph == '`demo`'
