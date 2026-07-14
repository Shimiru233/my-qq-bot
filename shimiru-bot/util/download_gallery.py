r"""
从 lsky.mizuki.love 下载指定画廊的所有图片。
用法: python download_gallery.py <gallery_name> [-o <output_dir>]

示例:
  python download_gallery.py mzk
  python download_gallery.py mzk -o D:\pics\mzk
"""

import argparse
import os
import sys
import time
import urllib.request
import json

API_BASE = "https://lsky.mizuki.love/gallery-api/public/gallery"
REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
RETRY_DELAY = 2


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except OSError as e:
            print(f"[!] 请求失败 (attempt {attempt}/{RETRY_COUNT}): {e}")
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_DELAY)
    raise RuntimeError(f"请求失败，已重试 {RETRY_COUNT} 次: {url}")


def download_file(url: str, dest: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = resp.read()
            with open(dest, "wb") as f:
                f.write(data)
            return True
        except OSError as e:
            print(f"  [!] 下载失败 (attempt {attempt}/{RETRY_COUNT}): {e}")
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_DELAY)
    return False


def get_next_index(output_dir: str, prefix: str) -> int:
    """扫描 output_dir，找到 {prefix}N 中最大的 N，返回 N+1。"""
    if not os.path.isdir(output_dir):
        return 1
    max_idx = 0
    for fname in os.listdir(output_dir):
        if fname.startswith(prefix):
            stem, _ = os.path.splitext(fname)
            suffix = stem[len(prefix):]
            if suffix.isdigit():
                max_idx = max(max_idx, int(suffix))
    return max_idx + 1


def main():
    parser = argparse.ArgumentParser(
        description="下载 lsky.mizuki.love 画廊的所有图片"
    )
    parser.add_argument("gallery", help="画廊名称 (例如 mzk)")
    parser.add_argument("-o", "--output", default=None,
                        help="输出目录 (默认: ./<gallery>)")
    parser.add_argument("-n", "--limit", type=int, default=0,
                        help="最多下载 N 张 (0=全部)")
    args = parser.parse_args()

    gallery = args.gallery
    output_dir = args.output or os.getcwd()

    api_url = f"{API_BASE}/{gallery}"
    print(f"[*] 正在获取画廊: {api_url}")
    resp = fetch_json(api_url)

    if not resp.get("ok"):
        print(f"[!] API 返回失败, 响应: {resp}")
        sys.exit(1)

    data = resp.get("data", {})
    images = data.get("images", [])
    pic_count = data.get("pic_count", len(images))

    print(f"[*] 画廊名称: {data.get('name', gallery)}")
    print(f"[*] 图片数量: {pic_count}")
    print(f"[*] 实际返回: {len(images)} 张")
    print(f"[*] 输出目录: {output_dir}")

    if not images:
        print("[!] 没有图片可下载")
        sys.exit(0)

    os.makedirs(output_dir, exist_ok=True)

    # 找到起始编号
    next_idx = get_next_index(output_dir, gallery)
    print(f"[*] 起始编号: {gallery}{next_idx}\n")

    success = 0
    fail = 0

    if args.limit > 0:
        images = images[:args.limit]

    for i, img in enumerate(images, 1):
        url = img.get("url", "")
        pid = img.get("pid", "unknown")

        if not url:
            print(f"[{i:03d}/{len(images)}] ! 跳过 pid={pid}: 无 url")
            continue

        # 根据 URL 推断扩展名，默认 .jpg
        ext = os.path.splitext(url.split("?")[0])[-1]
        if not ext or len(ext) > 5:
            ext = ".jpg"

        filename = f"{gallery}{next_idx}{ext}"
        dest = os.path.join(output_dir, filename)

        print(f"[{i:03d}/{len(images)}] ↓ {filename} ...", end=" ", flush=True)
        if download_file(url, dest):
            size_kb = os.path.getsize(dest) / 1024
            print(f"OK ({size_kb:.1f} KB)")
            success += 1
            next_idx += 1
        else:
            print("FAIL")
            fail += 1

    print(f"\n{'='*50}")
    print(f"[*] 完成! 成功: {success}, 失败: {fail}")
    print(f"[*] 文件保存在: {output_dir}")


if __name__ == "__main__":
    main()
