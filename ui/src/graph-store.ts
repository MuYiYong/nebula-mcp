import type { GraphElement, GraphElements } from "./types";

export function mergeGraphElements(
  current: GraphElements,
  incoming: GraphElements,
): GraphElements {
  return {
    nodes: mergeByStableId(current.nodes, incoming.nodes),
    edges: mergeByStableId(current.edges, incoming.edges),
  };
}

function mergeByStableId(
  current: GraphElement[],
  incoming: GraphElement[],
): GraphElement[] {
  const byId = new Map(current.map((element) => [element.data.id, element]));
  for (const element of incoming) {
    byId.set(element.data.id, element);
  }
  return Array.from(byId.values());
}
