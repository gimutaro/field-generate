"""Game server: image upload, world generation, and game serving."""

import http.server
import json
import os
import subprocess
import sys
import threading
import uuid

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VIEWER_DIR = os.path.join(PROJECT_DIR, "viewer")
WORLDS_DIR = os.path.join(PROJECT_DIR, "worlds")
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
UPLOAD_DIR = os.path.join(PROJECT_DIR, "uploads")

MIME_TYPES = {
    ".spz": "application/octet-stream",
    ".glb": "model/gltf-binary",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".json": "application/json",
    ".html": "text/html",
    ".js": "application/javascript",
    ".css": "text/css",
    ".txt": "text/plain",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}

generations = {}


def run_generation(gen_id, image_path, display_name, text_prompt):
    try:
        cmd = ["python3", "generate-world.py", image_path]
        if display_name:
            cmd.append(display_name)
        if text_prompt:
            cmd.append(text_prompt)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=PROJECT_DIR,
        )

        world_id = None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            generations[gen_id]["last_log"] = line

            if "Step 1" in line or "Step 2" in line:
                generations[gen_id]["status"] = "uploading"
            elif "Step 3" in line:
                generations[gen_id]["status"] = "generating"
            elif "Step 4" in line:
                generations[gen_id]["status"] = "polling"
            elif "Step 5" in line:
                generations[gen_id]["status"] = "downloading"
            elif "World ID:" in line:
                world_id = line.split("World ID:")[1].strip()

        proc.wait()

        if world_id:
            generations[gen_id]["status"] = "done"
            generations[gen_id]["world_id"] = world_id
        else:
            generations[gen_id]["status"] = "error"
            generations[gen_id]["error"] = "World ID not found in output"
    except Exception as e:
        generations[gen_id]["status"] = "error"
        generations[gen_id]["error"] = str(e)


SERVE_DIRS = {
    "/worlds/": WORLDS_DIR,
    "/viewer/": VIEWER_DIR,
    "/assets/": ASSETS_DIR,
}


class GameServerHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/" or path == "/index.html":
            return self._serve_file(os.path.join(VIEWER_DIR, "index.html"))

        for prefix, base_dir in SERVE_DIRS.items():
            if path.startswith(prefix):
                rel = path[len(prefix):]
                return self._serve_file(os.path.join(base_dir, rel))

        if path.startswith("/api/generate/"):
            gen_id = path.split("/api/generate/")[1]
            info = generations.get(gen_id)
            if not info:
                return self._send_json(404, {"error": "Not found"})
            return self._send_json(200, {
                "status": info["status"],
                "world_id": info.get("world_id"),
                "error": info.get("error"),
                "last_log": info.get("last_log", ""),
            })

        if path == "/api/worlds":
            return self._serve_world_list()

        self.send_error(404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        path = self.path

        if path == "/api/upload":
            filename = self.headers.get("X-Filename", "upload.jpg")
            upload_id = str(uuid.uuid4())
            ext = os.path.splitext(filename)[1] or ".jpg"
            save_name = f"{upload_id}{ext}"

            os.makedirs(UPLOAD_DIR, exist_ok=True)
            save_path = os.path.join(UPLOAD_DIR, save_name)
            with open(save_path, "wb") as f:
                f.write(body)

            return self._send_json(200, {"upload_id": upload_id, "ext": ext})

        if path == "/api/generate":
            data = json.loads(body)
            upload_id = data["upload_id"]
            ext = data.get("ext", ".jpg")
            image_path = os.path.join(UPLOAD_DIR, f"{upload_id}{ext}")

            if not os.path.isfile(image_path):
                return self._send_json(404, {"error": "Upload not found"})

            gen_id = str(uuid.uuid4())
            generations[gen_id] = {
                "status": "starting",
                "world_id": None,
                "error": None,
                "last_log": "",
            }

            thread = threading.Thread(
                target=run_generation,
                args=(
                    gen_id,
                    image_path,
                    data.get("display_name", "Generated World"),
                    data.get("text_prompt", ""),
                ),
                daemon=True,
            )
            thread.start()

            return self._send_json(200, {"gen_id": gen_id})

        self.send_error(404)

    def _serve_file(self, file_path):
        file_path = os.path.realpath(file_path)
        allowed = any(
            file_path.startswith(os.path.realpath(d))
            for d in [VIEWER_DIR, WORLDS_DIR, ASSETS_DIR]
        )
        if not allowed:
            return self.send_error(403)
        if not os.path.isfile(file_path):
            return self.send_error(404)

        ext = os.path.splitext(file_path)[1].lower()
        content_type = MIME_TYPES.get(ext, "application/octet-stream")

        with open(file_path, "rb") as f:
            data = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._send_common_headers()
        self.end_headers()
        self.wfile.write(data)

    def _serve_world_list(self):
        worlds = []
        if os.path.isdir(WORLDS_DIR):
            for entry in sorted(os.listdir(WORLDS_DIR), reverse=True):
                meta_path = os.path.join(WORLDS_DIR, entry, "metadata.json")
                if os.path.isfile(meta_path):
                    worlds.append({"id": entry})

        data = json.dumps(worlds).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self._send_common_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status_code, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self._send_common_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_common_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "credentialless")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        self.send_header("Access-Control-Allow-Origin", "*")

    def log_message(self, fmt, *args):
        print(f"  {args[0]}")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = http.server.HTTPServer(("", port), GameServerHandler)
    print(f"Game server running at: http://localhost:{port}/")
    print("Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
