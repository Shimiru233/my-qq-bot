from bs4 import BeautifulSoup
import requests
import os
import re
import time
from PIL import Image


def is_valid_image(filepath):
    try:
        with Image.open(filepath) as img:
            img.verify()
        return True
    except Exception:
        return False


HTML_FILE = "page.html"
BASE = "https://wiki.arcaea.cn"

os.makedirs("covers", exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

session = requests.Session()
session.headers.update(headers)

with open(HTML_FILE, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

tables = soup.find_all("table", class_="wikitable")

for table in tables:
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        img_a = tds[1].find("a", class_="mw-file-description")
        if not img_a:
            continue

        href = img_a.get("href", "")
        m = re.search(r"Songs_(.*?)\.jpg", href)
        if not m:
            continue

        resource = m.group(1)
        filename = f"Songs_{resource}.jpg"
        filepath = os.path.join("covers", filename)

        if os.path.exists(filepath):
            if is_valid_image(filepath):
                print(f"skip {filename}")
                continue
            else:
                print(f"re-download {filename} (corrupted)")
                os.remove(filepath)

        img = img_a.find("img")
        url = None
        if img and img.get("srcset"):
            first = img["srcset"].split(",")[0].split()[0]
            if "/thumb/" in first:
                after_thumb = first.split("/thumb/")[1]
                parts = after_thumb.split("/")
                url = f"{BASE}/images/{parts[0]}/{parts[1]}/{parts[2]}"

        if not url:
            print(f"skip {filename} - could not construct URL")
            continue

        print(f"downloading {filename} {url}")
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()

            content_type = r.headers.get("Content-Type", "")
            if content_type.startswith("text/html"):
                print(f"skip {filename} - got HTML, preview: {r.text[:200]}")
                continue

            with open(filepath, "wb") as f:
                f.write(r.content)

            if not is_valid_image(filepath):
                print(f"remove {filename} - not a valid image after download")
                os.remove(filepath)

        except Exception as e:
            print(f"failed {filename} {e}")

        time.sleep(1)
