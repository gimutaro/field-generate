import json
import os
import sys
import time
import urllib.request

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(PROJECT_DIR, ".env")
BASE_URL = "https://api.worldlabs.ai/marble/v1"
OUTPUT_DIR = os.path.join(PROJECT_DIR, "worlds")


def load_api_key():
    with open(ENV_PATH) as f:
        for line in f:
            if line.startswith("WLT_API_KEY="):
                return line.strip().split("=", 1)[1]
    raise ValueError("WLT_API_KEY not found in .env")


def api_request(method, url, headers=None, json_data=None, binary_data=None):
    if headers is None:
        headers = {}

    data = None
    if json_data is not None:
        data = json.dumps(json_data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif binary_data is not None:
        data = binary_data

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read()
        return e.code, body


def download_file(url, dest_path):
    print(f"  Downloading: {os.path.basename(dest_path)}")
    urllib.request.urlretrieve(url, dest_path)
    size = os.path.getsize(dest_path)
    print(f"  Saved: {dest_path} ({size:,} bytes)")


def upload_image(api_key, image_path):
    auth_headers = {"WLT-Api-Key": api_key}
    extension = os.path.splitext(image_path)[1].lstrip(".")
    file_name = os.path.basename(image_path)

    # Prepare upload
    print("=== Step 1: Prepare upload ===")
    status, body = api_request(
        "POST",
        f"{BASE_URL}/media-assets:prepare_upload",
        headers={**auth_headers},
        json_data={
            "file_name": file_name,
            "kind": "image",
            "extension": extension,
        },
    )
    prepare_data = json.loads(body)
    upload_url = prepare_data["upload_info"]["upload_url"]
    upload_headers = prepare_data["upload_info"]["required_headers"]
    media_asset_id = prepare_data["media_asset"]["media_asset_id"]
    print(f"  Media Asset ID: {media_asset_id}")

    # Upload
    print("\n=== Step 2: Upload image ===")
    with open(image_path, "rb") as f:
        image_data = f.read()

    print(f"  Image size: {len(image_data):,} bytes")
    status, _ = api_request("PUT", upload_url, headers=upload_headers, binary_data=image_data)
    if status >= 400:
        raise RuntimeError(f"Upload failed with status {status}")
    print("  Upload complete.")

    return media_asset_id


def generate_world(api_key, display_name, media_asset_id, text_prompt):
    auth_headers = {"WLT-Api-Key": api_key}

    print("\n=== Step 3: Generate world ===")
    status, body = api_request(
        "POST",
        f"{BASE_URL}/worlds:generate",
        headers={**auth_headers},
        json_data={
            "display_name": display_name,
            "world_prompt": {
                "type": "image",
                "image_prompt": {
                    "source": "media_asset",
                    "media_asset_id": media_asset_id,
                },
                "text_prompt": text_prompt,
            },
        },
    )
    generate_data = json.loads(body)

    if "operation_id" not in generate_data:
        raise RuntimeError(f"Failed to start generation: {generate_data}")

    operation_id = generate_data["operation_id"]
    print(f"  Operation ID: {operation_id}")
    return operation_id


def poll_operation(api_key, operation_id):
    auth_headers = {"WLT-Api-Key": api_key}

    print("\n=== Step 4: Polling operation status ===")
    while True:
        status, body = api_request(
            "GET",
            f"{BASE_URL}/operations/{operation_id}",
            headers=auth_headers,
        )
        poll_data = json.loads(body)

        done = poll_data.get("done", False)
        metadata = poll_data.get("metadata") or {}
        progress = metadata.get("progress") or {}
        poll_status = progress.get("status", "UNKNOWN")

        timestamp = time.strftime("%H:%M:%S")
        print(f"  {timestamp} - Status: {poll_status}, Done: {done}")

        if done:
            error = poll_data.get("error")
            if error:
                raise RuntimeError(f"Generation failed: {error}")
            return poll_data

        time.sleep(15)


def download_assets(response_data, world_dir):
    os.makedirs(world_dir, exist_ok=True)

    assets = response_data.get("response", {}).get("assets", {})

    # Download SPZ files
    spz_urls = assets.get("splats", {}).get("spz_urls", {})
    for resolution, url in spz_urls.items():
        dest = os.path.join(world_dir, f"world_{resolution}.spz")
        download_file(url, dest)

    # Download collider mesh
    mesh_url = assets.get("mesh", {}).get("collider_mesh_url")
    if mesh_url:
        download_file(mesh_url, os.path.join(world_dir, "collider.glb"))

    # Download panorama
    pano_url = assets.get("imagery", {}).get("pano_url")
    if pano_url:
        download_file(pano_url, os.path.join(world_dir, "panorama.png"))

    # Download thumbnail
    thumb_url = assets.get("thumbnail_url")
    if thumb_url:
        download_file(thumb_url, os.path.join(world_dir, "thumbnail.webp"))

    # Save caption
    caption = assets.get("caption", "")
    if caption:
        with open(os.path.join(world_dir, "caption.txt"), "w") as f:
            f.write(caption)

    # Save metadata
    with open(os.path.join(world_dir, "metadata.json"), "w") as f:
        json.dump(response_data, f, indent=2)

    return world_dir


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate-world.py <image_path> [display_name] [text_prompt]")
        sys.exit(1)

    image_path = os.path.abspath(sys.argv[1])
    display_name = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(os.path.basename(image_path))[0]
    text_prompt = sys.argv[3] if len(sys.argv) > 3 else ""

    if not os.path.exists(image_path):
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)

    api_key = load_api_key()

    # Upload image
    media_asset_id = upload_image(api_key, image_path)

    # Generate world
    operation_id = generate_world(api_key, display_name, media_asset_id, text_prompt)

    # Poll until done
    result = poll_operation(api_key, operation_id)

    # Download assets
    metadata = result.get("metadata") or {}
    world_id = metadata.get("world_id", "unknown")
    world_dir = os.path.join(OUTPUT_DIR, world_id)

    print(f"\n=== Step 5: Downloading assets to {world_dir} ===")
    download_assets(result, world_dir)

    marble_url = result.get("response", {}).get("world_marble_url", "")
    print(f"\n=== Done! ===")
    print(f"  World ID: {world_id}")
    print(f"  Assets:   {world_dir}")
    print(f"  Marble:   {marble_url}")
    print(f"\n  To view locally:")
    print(f"    python serve.py")
    print(f"    Open: http://localhost:8080/?world={world_id}")


if __name__ == "__main__":
    main()
