from bs4 import BeautifulSoup
import json
import re

HTML_FILE = "page.html"

result = {}

with open(HTML_FILE, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

rows = soup.find_all("tr")

for tr in rows:
    tds = tr.find_all("td")
    if len(tds) < 3:
        continue

    # 第二列：封面
    img_a = tds[1].find("a", class_="mw-file-description")
    if not img_a:
        continue

    href = img_a.get("href", "")

    m = re.search(r"Songs_(.*?)\.jpg", href)
    if not m:
        continue

    resource = m.group(1)

    # 第三列：曲名
    title_a = tds[2].find("a")
    if not title_a:
        continue

    song_name = title_a.get_text(strip=True)

    result[resource] = song_name

# 输出 JSON
with open("songs.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("songs parsed:", len(result))
