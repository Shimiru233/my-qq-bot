import requests
from bs4 import BeautifulSoup
import os
import time

URL = "https://wiki.arcaea.cn/%E6%9B%B2%E7%9B%AE%E5%88%97%E8%A1%A8"
BASE = "https://wiki.arcaea.cn"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive"
}
session = requests.Session()
session.headers.update(headers)

print("Downloading page...")
r = session.get(URL, timeout=30)
print(r.status_code)
print(r.url)
print(len(r.text))
r.raise_for_status()

soup = BeautifulSoup(r.text, "html.parser")
tables = soup.select("table.wikitable")
os.makedirs("covers", exist_ok=True)

count = 0

for table in tables:
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue

        # 获取曲名
        name = tds[2].get_text(strip=True)

        # 获取缩略图链接
        img_tag = tds[1].find("img")
        if not img_tag:
            continue
        thumb_src = img_tag.get("src", "")
        if not thumb_src:
            continue

        # 转换为原图 URL
        # thumb_src 可能是 /images/thumb/f/fd/xxx.jpg/75px-xxx.jpg
        if "/thumb/" in thumb_src:
            img_url = BASE + thumb_src.split("/thumb/")[1].rsplit("/", 1)[0]
        else:
            img_url = BASE + thumb_src

        filename = os.path.basename(img_url)
        filepath = os.path.join("covers", filename)

        if os.path.exists(filepath):
            continue

        try:
            print(f"Downloading {filename} ...")
            img_resp = session.get(img_url, timeout=30)
            img_resp.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(img_resp.content)
            count += 1
        except Exception as e:
            print(f"Failed {filename}:", e)

        time.sleep(0.5)

print("Downloaded", count, "images")
