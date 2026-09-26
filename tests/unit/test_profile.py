from types import SimpleNamespace

import pytest

from nebula_mcp.models import QueryInput
from nebula_mcp.service import NebulaService
from tests.unit.test_service import FakeGateway, FakeResult


@pytest.mark.anyio
@pytest.mark.parametrize(('statement', 'graph', 'sent'), [
    ('RETURN 1', None, 'PROFILE RETURN 1'),
    ('/* note */ RETURN 1', 'demo', 'PROFILE USE demo\n/* note */ RETURN 1'),
    ('PROFILE RETURN 1', None, 'PROFILE RETURN 1'),
    ('EXPLAIN RETURN 1', None, 'EXPLAIN RETURN 1'),
    ('PROFILE RETURN 1', 'demo', 'PROFILE USE demo\n RETURN 1'),
])
async def test_profile_execution_and_display(settings, statement, graph, sent):
    gateway = FakeGateway([FakeResult([{'n': 1}])])
    output = await NebulaService(settings, gateway).execute_query(
        QueryInput(statement=statement, graph=graph)
    )
    assert gateway.statements == [sent]
    assert output.query.executed_statement == sent
    assert output.query.display_statement == (sent.removeprefix('PROFILE ') if not statement.startswith('PROFILE') else sent)


@pytest.mark.anyio
async def test_profile_captures_sdk_plan_without_consuming_rows_twice(settings):
    raw = FakeResult([{'n': 1}])
    raw.plan_desc = SimpleNamespace(id='0', name='Project', details='n', time_ms=1.2,
        rows=1, memory_kib=2.0, blocked_ms=0.1, children=[])
    output = await NebulaService(settings, FakeGateway([raw])).execute_query(QueryInput(statement='RETURN 1'))
    assert output.profile.operators[0]['name'] == 'Project'
    assert output.profile.operators[0]['rows'] == 1
    assert output.table.rows == [{'n': 1}]


@pytest.mark.anyio
@pytest.mark.parametrize('statement', [
    '/*comment*/ PROFILE RETURN 1',
    'PROFILE /*comment*/ format="verbose" RETURN 1',
    'EXPLAIN RAW RETURN 1',
])
async def test_graph_is_inserted_after_plan_options(settings, statement):
    gateway = FakeGateway([FakeResult([])])
    result = await NebulaService(settings, gateway).execute_query(QueryInput(statement=statement, graph='demo'))
    assert 'USE demo' in result.query.display_statement
    assert not result.query.executed_statement.startswith('PROFILE USE demo\n')
    assert result.query.executed_statement.index('USE demo') > result.query.executed_statement.index('PROFILE' if 'PROFILE' in statement else 'EXPLAIN')
    if 'format=' in statement:
        assert result.query.executed_statement.index('USE demo') > result.query.executed_statement.index('"verbose"')


@pytest.mark.anyio
async def test_verbose_profile_use_conflicts_with_graph_argument(settings):
    from nebula_mcp.errors import NebulaMCPError
    gateway = FakeGateway([])
    with pytest.raises(NebulaMCPError):
        await NebulaService(settings, gateway).execute_query(QueryInput(
            statement='PROFILE format="verbose" USE other RETURN 1', graph='demo',
        ))
    assert gateway.statements == []


@pytest.mark.anyio
async def test_profile_is_bounded_and_uses_real_sdk_fields(settings):
    from nebulagraph_python.data import PlanInfoNode
    from nebulagraph_python.proto.graph_pb2 import PlanInfo
    raw = FakeResult([])
    raw.plan_desc = PlanInfoNode(PlanInfo(name=b'Project', details=b'x' * 3000, rows=1))
    output = await NebulaService(settings.model_copy(update={'max_bytes': 1024}), FakeGateway([raw])).execute_query(QueryInput(statement='RETURN 1'))
    assert output.profile.truncated
    assert output.profile.operators == []
