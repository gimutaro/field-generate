"""Download assets from an already-generated world."""

import json
import os
import urllib.request

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "worlds")

WORLD_ID = "07ff4e3f-c851-458f-a3e6-17ea7d584c37"

ASSETS = {
    "world_500k.spz": "https://cdn.marble.worldlabs.ai/07ff4e3f-c851-458f-a3e6-17ea7d584c37/8c6b5fcc-4905-4704-a305-94e29738d92d_ceramic_500k.spz",
    "world_100k.spz": "https://cdn.marble.worldlabs.ai/07ff4e3f-c851-458f-a3e6-17ea7d584c37/f6bb119a-3f66-4c38-abe5-e6db72946aa9_dust_100k.spz",
    "world_full_res.spz": "https://cdn.marble.worldlabs.ai/07ff4e3f-c851-458f-a3e6-17ea7d584c37/e0f458ef-72d4-4ce5-8608-279287b8e9e8_ceramic.spz",
    "collider.glb": "https://cdn.marble.worldlabs.ai/07ff4e3f-c851-458f-a3e6-17ea7d584c37/1e0c8e28.glb",
    "panorama.png": "https://cdn.marble.worldlabs.ai/07ff4e3f-c851-458f-a3e6-17ea7d584c37/9bafcafe-b343-4aed-94b6-579cc4974c78_panos/rgb_0.png",
    "thumbnail.webp": "https://cdn.marble.worldlabs.ai/07ff4e3f-c851-458f-a3e6-17ea7d584c37/593efb44-0310-4871-8d6d-e50b6ab1b633_dust_mpi/thumbnail.webp",
}

METADATA = {
    "operation_id": "8e7f4e4d-b487-4504-9a05-0e2b8d1e845d",
    "done": True,
    "metadata": {
        "progress": {"status": "SUCCEEDED"},
        "world_id": WORLD_ID,
    },
    "response": {
        "world_id": WORLD_ID,
        "display_name": "Lapland Aurora",
        "assets": {
            "caption": "The scene is a breathtaking depiction of a snowy Lapland landscape under the bright green aurora borealis.",
            "thumbnail_url": ASSETS["thumbnail.webp"],
            "splats": {
                "spz_urls": {
                    "500k": ASSETS["world_500k.spz"],
                    "100k": ASSETS["world_100k.spz"],
                    "full_res": ASSETS["world_full_res.spz"],
                }
            },
            "mesh": {"collider_mesh_url": ASSETS["collider.glb"]},
            "imagery": {"pano_url": ASSETS["panorama.png"]},
        },
        "world_marble_url": f"https://marble.worldlabs.ai/world/{WORLD_ID}",
    },
}


def main():
    world_dir = os.path.join(OUTPUT_DIR, WORLD_ID)
    os.makedirs(world_dir, exist_ok=True)

    # Save metadata
    meta_path = os.path.join(world_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(METADATA, f, indent=2)
    print(f"Saved: {meta_path}")

    # Download assets
    for filename, url in ASSETS.items():
        dest = os.path.join(world_dir, filename)
        if os.path.exists(dest):
            print(f"Skip (exists): {filename}")
            continue
        print(f"Downloading: {filename}...")
        urllib.request.urlretrieve(url, dest)
        size = os.path.getsize(dest)
        print(f"  Saved: {size:,} bytes")

    print(f"\nDone! Assets in: {world_dir}")


if __name__ == "__main__":
    main()
