// Minimal stub for error page rendering
export function renderErrorPage(): string {
  return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Server Error</title>
  <style>
    body { font-family: system-ui, sans-serif; text-align: center; padding: 4rem; background: #1a1a2e; color: #fff; }
    h1 { font-size: 7rem; margin: 0; }
    p { font-size: 1.5rem; color: #888; margin-top: 1rem; }
    button { margin-top: 2rem; padding: 0.75rem 1.5rem; font-size: 1rem; background: #6366f1; color: white; border: none; border-radius: 0.5rem; cursor: pointer; }
  </style>
</head>
<body>
  <h1>500</h1>
  <p>Internal Server Error</p>
  <button onclick="location.reload()">Reload</button>
</body>
</html>
`;
}