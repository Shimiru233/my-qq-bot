from bs4 import BeautifulSoup
import psycopg2
import re

HTML_FILE = "page.html"

# 数据库连接
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="arcaea_assets",
    user="postgres",
    password="root"
)

# 读取 HTML
with open(HTML_FILE, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

tables = soup.find_all("table", class_="wikitable")

with conn.cursor() as cur:
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

            resource_name = m.group(1)

            print("insert:", resource_name)

            cur.execute(
                "INSERT INTO m_song (name) VALUES (%s) ON CONFLICT DO NOTHING",
                (resource_name,)
            )

conn.commit()
