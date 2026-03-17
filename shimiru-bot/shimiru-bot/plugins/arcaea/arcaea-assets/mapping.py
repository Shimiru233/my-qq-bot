from bs4 import BeautifulSoup
import json
import re

HTML_FILE = "page.html"

with open(HTML_FILE, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

tables = soup.find_all("table", class_="wikitable")

result = {}

for table in tables:
    for tr in table.find_all("tr"):

        tds = tr.find_all("td")
        if len(tds) < 3:
            continue

        # 第三个td = 歌名
        name = tds[2].get_text("\n", strip=True).split("\n")[0]

        # 第二个td = 图片
        img = tds[1].find("img")
        if not img:
            continue

        src = img.get("src", "")

        m = re.search(r"Songs_(.*?)\.jpg", src)
        if not m:
            continue

        resource = m.group(1)

        result[resource] = name

with open("mapping.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("songs:", len(result))
