// Minimal stub for Lovable error reporting (not available in self-hosted builds)
export function reportLovableError(error: Error, context?: Record<string, unknown>) {
  console.error("[Lovable Error Reporting]", error, context);
}

export function initLovableErrorReporting() {
  // No-op in self-hosted environment
}