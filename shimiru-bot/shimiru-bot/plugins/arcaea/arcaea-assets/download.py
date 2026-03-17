import requests

URL = "https://wiki.arcaea.cn/曲目列表"

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
}

print("downloading html...")

r = requests.get(URL, headers=headers, timeout=30)
r.raise_for_status()

with open("arcaea.html", "w", encoding="utf-8") as f:
    f.write(r.text)

print("saved arcaea.html")
print("size:", len(r.text))
