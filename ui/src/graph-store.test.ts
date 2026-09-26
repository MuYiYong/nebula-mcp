import { describe, expect, it } from "vitest";

import { mergeGraphElements } from "./graph-store";

const node1 = { data: { id: "demo:1", label: "A" } };
const node2 = { data: { id: "demo:2", label: "B" } };
const node2Updated = { data: { id: "demo:2", label: "B2", score: 2 } };
const node3 = { data: { id: "demo:3", label: "C" } };
const edge12 = { data: { id: "demo:1:E:0:2", source: "demo:1", target: "demo:2" } };
const edge23 = { data: { id: "demo:2:E:0:3", source: "demo:2", target: "demo:3" } };

describe("mergeGraphElements", () => {
  it("deduplicates by stable id and replaces properties with the newest value", () => {
    const merged = mergeGraphElements(
      { nodes: [node1, node2], edges: [edge12] },
      { nodes: [node2Updated, node3], edges: [edge12, edge23] },
    );

    expect(merged).toEqual({
      nodes: [node1, node2Updated, node3],
      edges: [edge12, edge23],
    });
  });

  it("preserves the current graph when an expansion is empty", () => {
    const current = { nodes: [node1, node2], edges: [edge12] };

    expect(mergeGraphElements(current, { nodes: [], edges: [] })).toEqual(current);
    expect(current).toEqual({ nodes: [node1, node2], edges: [edge12] });
  });
});
