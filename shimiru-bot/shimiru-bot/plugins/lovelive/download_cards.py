"""Download AS card images from llwiki.org based on card numbers in as_cards.yaml."""

import hashlib
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml
from curl_cffi import requests

YAML_FILE = "as_cards.yaml"
OUT_DIR = "cards"
BASE_URL = "https://llwiki.org/mediawiki/img_auth.php"
MAX_WORKERS = 8


def img_url(card_num: int, suffix: str) -> str:
    """Build the img_auth.php URL for a given card number and a/b suffix."""
    wiki_filename = f"AS_Card_{card_num}_{suffix}.png"
    md5 = hashlib.md5(wiki_filename.encode()).hexdigest()
    return f"{BASE_URL}/{md5[0]}/{md5[:2]}/{wiki_filename}"


def download(src_url: str, dst_path: str) -> bool:
    """Download one image. Returns True on success."""
    try:
        resp = requests.get(src_url, impersonate="chrome131", timeout=30)
        if resp.status_code == 200:
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            with open(dst_path, "wb") as f:
                f.write(resp.content)
            return True
        elif resp.status_code == 404:
            return False
        else:
            print(f"  HTTP {resp.status_code} for {src_url}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        return False


def main() -> None:
    with open(YAML_FILE, encoding="utf-8") as f:
        data: dict[str, list[int]] = yaml.safe_load(f)

    # Collect unique card numbers across all characters
    all_nums: set[int] = set()
    for nums in data.values():
        all_nums.update(nums)

    total_imgs = len(all_nums) * 2
    print(f"Downloading up to {total_imgs} images ({len(all_nums)} cards × 2 versions) to '{OUT_DIR}/' ...")

    success = 0
    skipped = 0

    tasks = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for num in sorted(all_nums):
            for suffix in ("a", "b"):
                url = img_url(num, suffix)
                dst = os.path.join(OUT_DIR, f"{num}_{suffix}.png")
                tasks[pool.submit(download, url, dst)] = dst

        for i, future in enumerate(as_completed(tasks), 1):
            dst = tasks[future]
            if future.result():
                success += 1
            else:
                skipped += 1
            if i % 50 == 0 or i == len(tasks):
                print(f"  {i}/{len(tasks)} done ({success} ok, {skipped} skip)", flush=True)

    print(f"\nDone! {success} downloaded, {skipped} missing -> {OUT_DIR}/")


if __name__ == "__main__":
    main()
