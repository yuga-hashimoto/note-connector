export function parseWidgetData(payload: unknown): Record<string, unknown> {
  if (!payload || typeof payload !== "object") return {};
  const obj = payload as Record<string, unknown>;
  if (typeof obj.result === "string") {
    try {
      const inner = JSON.parse(obj.result) as unknown;
      if (inner && typeof inner === "object") return inner as Record<string, unknown>;
    } catch {
      /* ignore */
    }
  }
  return obj;
}