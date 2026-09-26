"""Structured contracts shared by nebula-mcp components."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PolicyIssue(BaseModel):
    """One static validation finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


StatementKind = Literal["query", "catalog", "procedure", "mutation", "unknown"]


class PolicyDecision(BaseModel):
    """Server-side execution decision for one GQL statement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement_kind: StatementKind
    allowed: bool
    read_only: bool
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class ValidationEvidence(BaseModel):
    """Static evidence about a generated GQL candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    valid: bool
    detected_dialect: Literal["gql", "cypher", "ngql", "unknown"]
    statement_kind: StatementKind
    issues: tuple[PolicyIssue, ...] = ()
    warnings: tuple[PolicyIssue, ...] = ()
    explain_checked: bool = False
    executed: bool = False
    placeholders: tuple[str, ...] = Field(default_factory=tuple)


class ResultLimits(BaseModel):
    """Hard bounds applied while consuming a query result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rows: int = Field(ge=1)
    nodes: int = Field(ge=1)
    edges: int = Field(ge=1)
    bytes: int = Field(ge=1)


class QueryStatus(BaseModel):
    """Database status returned alongside a parsed result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    code: str
    message: str
    latency_us: int | None = None
    extra_info: dict[str, Any] = Field(default_factory=dict)


class TableResult(BaseModel):
    """Bounded row-oriented view of the result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    columns: list[str]
    rows: list[dict[str, Any]]
    returned_row_count: int
    result_row_count: int | None = None
    truncated: bool = False


class GraphNode(BaseModel):
    """Normalized graph node extracted from a result value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    graph: str | None
    raw_id: Any
    type_name: str | None = None
    labels: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    placeholder: bool = False


class GraphEdge(BaseModel):
    """Normalized graph edge extracted from a result value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    graph: str | None
    src_id: Any
    dst_id: Any
    rank: Any = 0
    edge_type: str | None = None
    labels: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    direction: str | None = None


class GraphPath(BaseModel):
    """Path metadata with the SDK length kept separate from graph hop count."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sdk_length: int | None = None
    hop_count: int
    node_keys: list[str] = Field(default_factory=list)
    edge_keys: list[str] = Field(default_factory=list)
    string_representation: str | None = None


class ParsedGraph(BaseModel):
    """Graph entities discovered while walking returned rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    graph: str | None
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    paths: list[GraphPath] = Field(default_factory=list)


class TruncationInfo(BaseModel):
    """Exact server-side result limits that affected the response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    truncated: bool = False
    reasons: tuple[str, ...] = ()


class ParsedResult(BaseModel):
    """Typed, bounded representation shared by output renderers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: QueryStatus
    table: TableResult
    graph: ParsedGraph
    truncation: TruncationInfo


class CytoscapeElement(BaseModel):
    """One Cytoscape element with an extensible data payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data: dict[str, Any]


class CytoscapeElements(BaseModel):
    """Cytoscape node and edge collections."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    nodes: list[CytoscapeElement] = Field(default_factory=list)
    edges: list[CytoscapeElement] = Field(default_factory=list)


class GraphSpec(BaseModel):
    """Portable graph artifact returned to an MCP client."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal["cytoscape-elements-v1"] = "cytoscape-elements-v1"
    graph: str | None
    elements: CytoscapeElements
    paths: list[dict[str, Any]] = Field(default_factory=list)
    truncated: bool = False


class TopValue(BaseModel):
    """One deterministic categorical frequency entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: Any
    count: int


ColumnKind = Literal["numeric", "temporal", "categorical", "empty", "unsupported"]


class ColumnAnalysis(BaseModel):
    """Facts calculated for one returned column."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ColumnKind
    count: int
    null_count: int
    minimum: int | float | None = None
    maximum: int | float | None = None
    mean: float | None = None
    median: float | None = None
    top_values: list[TopValue] = Field(default_factory=list)


class Analysis(BaseModel):
    """Deterministic statistics scoped only to returned rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Literal["returned_rows"] = "returned_rows"
    complete_result: bool
    row_count: int
    columns: dict[str, ColumnAnalysis]


class ChartSpec(BaseModel):
    """Portable Vega-Lite artifact returned to an MCP client."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal["vega-lite-v5"] = "vega-lite-v5"
    description: str
    spec: dict[str, Any]


class ListGraphsInput(BaseModel):
    """Pagination controls for graph discovery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: str | None = Field(None, alias="schema", min_length=1, max_length=128)
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0, le=100_000)


class GraphSchemaInput(BaseModel):
    """Target Graph Type and optional bounded DDL request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: str = Field(alias="schema", min_length=1, max_length=128)
    graph_type: str = Field(min_length=1, max_length=128)
    include_ddl: bool = False
    max_ddl_bytes: int = Field(65_536, ge=1, le=1_048_576)


class ValidateGQLInput(BaseModel):
    """Static validation request with optional EXPLAIN evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str = Field(min_length=1, max_length=1_000_000)
    graph: str | None = Field(None, min_length=1, max_length=128)
    run_explain: bool = False


class QueryInput(BaseModel):
    """Read-only query execution request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str = Field(min_length=1, max_length=1_000_000)
    graph: str | None = Field(None, min_length=1, max_length=128)
    max_rows: int | None = Field(None, ge=1, le=10_000)
    include_graph: bool = True
    include_analysis: bool = True
    include_charts: bool = True
    render_mode: Literal["spec"] = "spec"


class MutationInput(BaseModel):
    """Explicitly confirmed mutation execution request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str = Field(min_length=1, max_length=1_000_000)
    graph: str | None = Field(None, min_length=1, max_length=128)
    confirm_mutation: bool = False


class ConnectionOutput(BaseModel):
    """Redacted connectivity evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connected: bool
    version: str
    config: dict[str, Any]


class GraphSummary(BaseModel):
    """One graph returned by show_graphs()."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: str | None = Field(None, alias="schema")
    name: str
    graph_type: str | None = None
    owner: str | None = None
    extra: Any = None


class GraphListOutput(BaseModel):
    """Typed page of available graphs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: QueryStatus
    graphs: list[GraphSummary]
    limit: int
    offset: int
    returned_count: int


class GraphSchemaEntity(BaseModel):
    """One row from DESCRIBE GRAPH TYPE."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: str | None = None
    type_name: str | None = None
    type_pattern: Any = None
    labels: Any = None
    primary_key_or_multiedge_key: Any = None
    properties: Any = None


class GraphSchemaOutput(BaseModel):
    """Structured Graph Type schema with optional bounded DDL."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: QueryStatus
    schema_name: str = Field(alias="schema")
    graph_type: str
    entities: list[GraphSchemaEntity]
    ddl: str | None = None
    ddl_truncated: bool = False


class ValidationOutput(BaseModel):
    """Static policy evidence and optional non-executing EXPLAIN result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence: ValidationEvidence
    policy: PolicyDecision
    explain: ParsedResult | None = None


class QueryMetadata(BaseModel):
    """Execution context recorded with a query result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str
    executed_statement: str
    display_statement: str | None = None
    environment: str | None = None
    connection_id: str | None = None
    graph: str | None
    read_only: bool = True
    validation: ValidationEvidence


class ExplanationContext(BaseModel):
    """Auditable facts for the MCP client to explain in natural language."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    facts: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    empty_result: bool
    validation_evidence: ValidationEvidence
    suggested_focus: list[str] = Field(default_factory=list)


class ProfileOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    latency_us: int | None = None
    operators: list[dict[str, Any]] = Field(default_factory=list)
    truncated: bool = False


class QueryOutput(BaseModel):
    """Unified read-only query output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: QueryStatus
    query: QueryMetadata
    profile: ProfileOutput | None = None
    table: TableResult
    graph: GraphSpec | None = Field(
        None,
        description=(
            "Render this Cytoscape graph when enabled and its elements contain nodes or edges."
        ),
    )
    analysis: Analysis | None = Field(
        None,
        description="Deterministic facts about the bounded returned rows when enabled.",
    )
    charts: list[ChartSpec] = Field(
        default_factory=list,
        description=(
            "Render every Vega-Lite chart in this list when charts are enabled and the list "
            "is non-empty; a table is not a chart replacement."
        ),
    )
    explanation_context: ExplanationContext = Field(
        description=(
            "Use this evidence to write a human-readable explanation for every successful query."
        )
    )
    truncation: TruncationInfo


class QueryPresentation(BaseModel):
    """Any query result and client-authored explanation for the MCP App."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    result: QueryOutput
    explanation: str = Field(
        min_length=1, max_length=100_000,
        description="Explain result meaning and insights with concrete entities, directions, values "
        "and comparisons. Distinguish facts from hypotheses and state sampling/missing-data limits. "
        "Do not merely repeat row or path counts.",
    )


class GraphSelectionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    graph: str
    session_statement: str
    result: QueryOutput | None = None


class GraphPresentation(QueryPresentation):
    """Non-empty graph result and client-authored explanation for the MCP App."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    result: QueryOutput
    explanation: str = Field(
        min_length=1, max_length=100_000,
        description="Explain result meaning and insights with concrete entities, directions, values "
        "and comparisons. Distinguish facts from hypotheses and state sampling/missing-data limits. "
        "Do not merely repeat row or path counts.",
    )

    @model_validator(mode="after")
    def require_non_empty_graph(self) -> GraphPresentation:
        graph = self.result.graph
        if graph is None or not (graph.elements.nodes or graph.elements.edges):
            raise ValueError("nebula_render_graph requires a non-empty graph")
        return self


class MutationOutput(BaseModel):
    """Mutation status without query visualization artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: QueryStatus
    affected_nodes: int
    affected_edges: int
    warnings: tuple[str, ...] = ()


class EnvironmentsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    active: str | None
    environments: list[str]
