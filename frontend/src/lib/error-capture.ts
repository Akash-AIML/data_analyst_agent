// Minimal stub for error capture
let _lastError: Error | null = null;

export function captureError(error: Error) {
  _lastError = error;
  console.error("[Error Capture]", error);
}

export function consumeLastCapturedError(): Error | null {
  const e = _lastError;
  _lastError = null;
  return e;
}