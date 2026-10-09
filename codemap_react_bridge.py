"""
CodeMap React Visualizer Bridge
Serves the built React + Vite @xyflow/react application on a dedicated port (5273+)
and launches it in the user's browser. Avoids conflicts with other Vite instances on 5173.
"""

import os
import sys
import json
import socket
import threading
import http.server
import socketserver
import webbrowser

SERVER_PORT = 5273
_server_thread = None
_httpd = None
_actual_port = None


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Suppresses log spam in terminal."""
    def log_message(self, format, *args):
        pass

    def end_headers(self):
        # Disable browser caching for active_data.json
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()


def get_visualizer_dist_dir():
    """Returns the absolute path to visualizer-ui/dist directory."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(base_dir, "visualizer-ui", "dist")
    return dist_dir


def is_port_in_use(port):
    """Checks if a port is in use on either IPv4 or IPv6 loopback."""
    for host in ('127.0.0.1', '::1'):
        try:
            fam = socket.AF_INET6 if ':' in host else socket.AF_INET
            with socket.socket(fam, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex((host, port)) == 0:
                    return True
        except Exception:
            pass
    return False


def ensure_server_running(preferred_port=SERVER_PORT):
    """Starts the background HTTP daemon server if not already running."""
    global _server_thread, _httpd, _actual_port

    if _httpd is not None and _actual_port is not None:
        return _actual_port

    dist_dir = get_visualizer_dist_dir()
    if not os.path.exists(dist_dir) or not os.path.exists(os.path.join(dist_dir, "index.html")):
        return None

    handler = lambda *args, **kwargs: QuietHTTPRequestHandler(*args, directory=dist_dir, **kwargs)

    # Search for an available port starting from preferred_port
    for p in range(preferred_port, preferred_port + 25):
        if is_port_in_use(p):
            continue
        try:
            _httpd = socketserver.TCPServer(("", p), handler)
            _actual_port = p
            break
        except OSError:
            continue
    else:
        return None

    def _serve():
        try:
            _httpd.serve_forever()
        except Exception:
            pass

    _server_thread = threading.Thread(target=_serve, daemon=True)
    _server_thread.start()
    return _actual_port


def open_react_visualizer(file_path=None, json_data=None):
    """
    Sets active data and opens the React Visualizer in the user's browser.
    file_path: optional path to a .json file or any text file.
    json_data: optional dictionary or list to display.
    """
    dist_dir = get_visualizer_dist_dir()
    public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "visualizer-ui", "public")

    content_to_write = None

    if json_data is not None:
        content_to_write = json.dumps(json_data, indent=2)
    elif file_path and os.path.isfile(file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
                try:
                    parsed = json.loads(raw)
                    content_to_write = json.dumps(parsed, indent=2)
                except Exception:
                    content_to_write = json.dumps({
                        "file": os.path.basename(file_path),
                        "path": file_path,
                        "raw_content": raw[:2000]
                    }, indent=2)
        except Exception as ex:
            print(f"[ReactBridge] Could not read file {file_path}: {ex}")

    if content_to_write:
        for d in (dist_dir, public_dir):
            if os.path.isdir(d):
                try:
                    with open(os.path.join(d, "active_data.json"), "w", encoding="utf-8") as f:
                        f.write(content_to_write)
                except Exception:
                    pass

    port = ensure_server_running()
    if port:
        url = f"http://localhost:{port}/"
        webbrowser.open(url)
        return True
    else:
        # Fallback to direct file:// protocol
        index_html = os.path.join(dist_dir, "index.html")
        if os.path.exists(index_html):
            webbrowser.open("file://" + index_html)
            return True
    return False


if __name__ == "__main__":
    p = ensure_server_running()
    if p:
        url = f"http://localhost:{p}/"
        print("=" * 65)
        print(f"  CodeMap React Visualizer & JSON Crack Control Center")
        print(f"  Running at: {url}")
        print("=" * 65)
        webbrowser.open(url)
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down server...")
    else:
        print("Error: Could not find built visualizer-ui/dist directory.")
