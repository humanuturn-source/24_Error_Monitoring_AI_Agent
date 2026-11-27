"""
error_demo_app.py
Lightweight local web app (http://localhost:5001) displaying simulated error
states and healthy states on screen for AI error-checking tests.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = "127.0.0.1"
PORT = 5001

ALL_LINKS_HTML = """
<ul>
  <li><a href="/">Healthy Dashboard</a></li>
  <li><a href="/oom">Out of Memory Error</a></li>
  <li><a href="/server-error">500 Server Error</a></li>
  <li><a href="/form-check">Form Validation</a></li>
</ul>
"""


def render_nav(current_path: str) -> str:
    if current_path == "/":
        return '<nav><a href="/">Home</a><a href="/menu">Menu</a></nav>'
    if current_path == "/menu":
        return '<nav><a href="/">Home</a><a href="/menu">Menu</a></nav>'
    # On specific error/test pages, hide other scenario hyperlinks and show Home + Menu
    return '<nav><a href="/">Home</a><a href="/menu">Menu</a></nav>'


def render_page(
    current_path: str,
    title: str,
    status_badge: str,
    badge_color: str,
    body_html: str,
) -> str:
    nav_html = render_nav(current_path)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; background: #f7f8fa; color: #1f2937; }}
    .card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 24px; max-width: 760px; }}
    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 4px; color: #fff; background: {badge_color}; font-weight: bold; }}
    .error-box {{ background: #fef2f2; border-left: 4px solid #dc2626; padding: 14px; margin-top: 16px; font-family: monospace; white-space: pre-wrap; }}
    .ok-box {{ background: #f0fdf4; border-left: 4px solid #16a34a; padding: 14px; margin-top: 16px; }}
    .menu-box {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 14px; margin-top: 16px; }}
    nav {{ margin-bottom: 16px; }}
    nav a {{ margin-right: 14px; }}
    li {{ margin: 8px 0; }}
  </style>
</head>
<body>
  <div class="card">
    {nav_html}
    <h1>{title}</h1>
    <p>Status: <span class="badge" id="status_badge">{status_badge}</span></p>
    {body_html}
  </div>
</body>
</html>"""


class ErrorDemoHandler(BaseHTTPRequestHandler):
    def _send_html(self, html: str, status_code: int = 200) -> None:
        encoded = html.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            html = render_page(
                current_path=path,
                title="Local Telemetry Dashboard",
                status_badge="HEALTHY",
                badge_color="#16a34a",
                body_html=(
                    '<div class="ok-box" id="status_message">'
                    "All local services are operating normally. Memory usage is at 42% (3.3 GB / 8.0 GB). Zero errors detected."
                    "</div>"
                ),
            )
            self._send_html(html, 200)

        elif path == "/menu":
            html = render_page(
                current_path=path,
                title="Test Scenarios Menu",
                status_badge="MENU",
                badge_color="#2563eb",
                body_html=(
                    '<div class="menu-box" id="scenarios_menu">'
                    "<p>Select a page to inspect:</p>"
                    f"{ALL_LINKS_HTML}"
                    "</div>"
                ),
            )
            self._send_html(html, 200)

        elif path == "/oom":
            html = render_page(
                current_path=path,
                title="Worker Node Diagnostics",
                status_badge="CRITICAL ERROR",
                badge_color="#dc2626",
                body_html=(
                    '<div class="error-box" id="error_log">'
                    "FATAL ERROR: Out of memory: Killed process 48192 (worker_inference) total-vm:18432912kB, anon-rss:7912440kB.\n"
                    "Allocation failed while loading local tensor batch. Unable to reserve contiguous memory block."
                    "</div>"
                ),
            )
            self._send_html(html, 200)

        elif path == "/server-error":
            html = render_page(
                current_path=path,
                title="Pipeline Execution View",
                status_badge="500 ERROR",
                badge_color="#dc2626",
                body_html=(
                    '<div class="error-box" id="error_log">'
                    "HTTP 500 Internal Server Error: Unhandled exception in report_renderer.\n"
                    "RuntimeError: Downstream queue connection refused on 127.0.0.1:6379."
                    "</div>"
                ),
            )
            self._send_html(html, 500)

        elif path == "/form-check":
            params = parse_qs(parsed.query)
            threshold = params.get("threshold", [""])[0].strip()
            feedback = ""
            if threshold:
                try:
                    val = int(threshold)
                    if val < 1 or val > 100:
                        feedback = (
                            '<div class="error-box" id="validation_error">'
                            f"Validation Error: Threshold '{val}' is out of range. Must be between 1 and 100."
                            "</div>"
                        )
                    else:
                        feedback = (
                            '<div class="ok-box" id="validation_ok">'
                            f"Configuration applied: Alert threshold set to {val}%."
                            "</div>"
                        )
                except ValueError:
                    feedback = (
                        '<div class="error-box" id="validation_error">'
                        f"Validation Error: Invalid number '{threshold}'. Expected an integer between 1 and 100."
                        "</div>"
                    )

            form_html = f"""
            <form method="GET" action="/form-check">
              <label for="threshold">Alert Threshold (%):</label>
              <input id="threshold" name="threshold" type="text" value="{threshold}" />
              <button id="apply_btn" type="submit">Apply Threshold</button>
            </form>
            {feedback}
            """
            html = render_page(
                current_path=path,
                title="Threshold Configuration",
                status_badge="READY",
                badge_color="#2563eb",
                body_html=form_html,
            )
            self._send_html(html, 200)

        else:
            html = render_page(
                current_path=path,
                title="Page Not Found",
                status_badge="404 NOT FOUND",
                badge_color="#d97706",
                body_html=f'<div class="error-box" id="error_log">Error 404: Requested path "{path}" does not exist.</div>',
            )
            self._send_html(html, 404)

    def log_message(self, format: str, *args) -> None:
        print(f"[DEMO_APP] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), ErrorDemoHandler)
    print(f"Error Demo App running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
