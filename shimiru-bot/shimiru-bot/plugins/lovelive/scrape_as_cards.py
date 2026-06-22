"""Scrape LoveLive! ALL STARS card lists from llwiki.org and output YAML."""

import re
import sys
from collections import defaultdict

from curl_cffi import requests
import yaml

URLS = [
    ("μ's", "UR", "https://llwiki.org/zh/LoveLive!%E5%AD%A6%E5%9B%AD%E5%81%B6%E5%83%8F%E7%A5%ADALL_STARS%E5%8D%A1%E7%89%8C%E5%88%97%E8%A1%A8/%CE%BC%27s_UR"),
    ("Aqours", "UR", "https://llwiki.org/zh/LoveLive!%E5%AD%A6%E5%9B%AD%E5%81%B6%E5%83%8F%E7%A5%ADALL_STARS%E5%8D%A1%E7%89%8C%E5%88%97%E8%A1%A8/Aqours_UR"),
    ("虹咲", "UR", "https://llwiki.org/zh/LoveLive!%E5%AD%A6%E5%9B%AD%E5%81%B6%E5%83%8F%E7%A5%ADALL_STARS%E5%8D%A1%E7%89%8C%E5%88%97%E8%A1%A8/%E8%99%B9%E5%92%B2%E5%AD%A6%E5%9B%AD%E5%AD%A6%E5%9B%AD%E5%81%B6%E5%83%8F%E5%90%8C%E5%A5%BD%E4%BC%9AUR"),
    ("μ's", "SR", "https://llwiki.org/zh/LoveLive!%E5%AD%A6%E5%9B%AD%E5%81%B6%E5%83%8F%E7%A5%ADALL_STARS%E5%8D%A1%E7%89%8C%E5%88%97%E8%A1%A8/%CE%BC%27s_SR"),
    ("Aqours", "SR", "https://llwiki.org/zh/LoveLive!%E5%AD%A6%E5%9B%AD%E5%81%B6%E5%83%8F%E7%A5%ADALL_STARS%E5%8D%A1%E7%89%8C%E5%88%97%E8%A1%A8/Aqours_SR"),
    ("虹咲", "SR", "https://llwiki.org/zh/LoveLive!%E5%AD%A6%E5%9B%AD%E5%81%B6%E5%83%8F%E7%A5%ADALL_STARS%E5%8D%A1%E7%89%8C%E5%88%97%E8%A1%A8/%E8%99%B9%E5%92%B2%E5%AD%A6%E5%9B%AD%E5%AD%A6%E5%9B%AD%E5%81%B6%E5%83%8F%E5%90%8C%E5%A5%BD%E4%BC%9ASR"),
    ("μ's", "R", "https://llwiki.org/zh/LoveLive!%E5%AD%A6%E5%9B%AD%E5%81%B6%E5%83%8F%E7%A5%ADALL_STARS%E5%8D%A1%E7%89%8C%E5%88%97%E8%A1%A8/%CE%BC%27s_R"),
    ("Aqours", "R", "https://llwiki.org/zh/LoveLive!%E5%AD%A6%E5%9B%AD%E5%81%B6%E5%83%8F%E7%A5%ADALL_STARS%E5%8D%A1%E7%89%8C%E5%88%97%E8%A1%A8/Aqours_R"),
    ("虹咲", "R", "https://llwiki.org/zh/LoveLive!%E5%AD%A6%E5%9B%AD%E5%81%B6%E5%83%8F%E7%A5%ADALL_STARS%E5%8D%A1%E7%89%8C%E5%88%97%E8%A1%A8/%E8%99%B9%E5%92%B2%E5%AD%A6%E5%9B%AD%E5%AD%A6%E5%9B%AD%E5%81%B6%E5%83%8F%E5%90%8C%E5%A5%BD%E4%BC%9AR"),
]

TEMPLATE_TO_NAME = {
    "honoka": "高坂穗乃果",
    "eli": "绚濑绘里",
    "kotori": "南小鸟",
    "umi": "园田海未",
    "rin": "星空凛",
    "maki": "西木野真姬",
    "nozomi": "东条希",
    "hanayo": "小泉花阳",
    "nico": "矢泽妮可",
    "chika": "高海千歌",
    "riko": "樱内梨子",
    "kanan": "松浦果南",
    "dia": "黑泽黛雅",
    "you": "渡边曜",
    "yoshiko": "津岛善子",
    "hanamaru": "国木田花丸",
    "mari": "小原鞠莉",
    "ruby": "黑泽露比",
    "ayumu": "上原步梦",
    "kasumi": "中须霞",
    "shizuku": "樱坂雫",
    "karin": "朝香果林",
    "ai": "宫下爱",
    "kanata": "近江彼方",
    "setsuna": "优木雪菜",
    "emma": "艾玛·维尔德",
    "rina": "天王寺璃奈",
    "shioriko": "三船栞子",
    "mia": "米娅·泰勒",
    "lanzhu": "钟岚珠",
}


def fetch_raw(url: str) -> str:
    resp = requests.get(
        url + "?action=raw",
        impersonate="chrome131",
        timeout=30,
    )
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def parse_header(header_line: str) -> list[str]:
    """Extract character names from the table header line."""
    templates = re.findall(r"\{\{(\w+)/link\}\}", header_line)
    return [TEMPLATE_TO_NAME.get(t, t) for t in templates]


def parse_table(wiki_text: str) -> dict[str, set[int]]:
    """Parse a MediaWiki table and return char_name -> set of card numbers."""
    results: dict[str, set[int]] = defaultdict(set)

    # Find the header line
    header_match = re.search(r"^!.*$", wiki_text, re.MULTILINE)
    if not header_match:
        print("  Warning: no header found", file=sys.stderr)
        return results

    char_names = parse_header(header_match.group(0))
    num_chars = len(char_names)
    print(f"  Found {num_chars} characters: {', '.join(char_names[:3])}...")

    # Split table content by row separators
    # Remove everything before the first |- and after the last |}
    table_start = wiki_text.find("|-")
    table_end = wiki_text.rfind("|}")
    if table_start == -1:
        return results

    table_body = wiki_text[table_start:table_end]

    # Split into rows
    raw_rows = re.split(r"\n\|-", table_body)

    for raw_row in raw_rows:
        # Collect all cells from this row
        cells: list[str] = []
        for line in raw_row.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("!") or line == "|}":
                continue
            if line.startswith("|"):
                line = line[1:].strip()
            # Split by || (MediaWiki cell separator within a line)
            parts = [p.strip() for p in line.split("||")]
            cells.extend(parts)

        if not cells:
            continue

        # Determine how many leading non-character cells to skip
        # (round number, optional set name, etc.)
        # Character cells come in pairs of 2, so: leading = len(cells) - 2 * num_chars
        expected_char_cells = num_chars * 2
        if len(cells) < expected_char_cells:
            continue

        leading = len(cells) - expected_char_cells
        char_cells = cells[leading:]

        for char_idx in range(num_chars):
            pair_start = char_idx * 2
            if pair_start + 1 >= len(char_cells):
                break

            type_number_cell = char_cells[pair_start + 1]
            no_match = re.search(r"No\.(\d+)", type_number_cell)
            if no_match:
                results[char_names[char_idx]].add(int(no_match.group(1)))

    return results


def main() -> None:
    all_results: dict[str, set[int]] = defaultdict(set)

    for group, rarity, url in URLS:
        print(f"Fetching {group} {rarity}...")
        try:
            wiki_text = fetch_raw(url)
            page_results = parse_table(wiki_text)
            total_cards = sum(len(v) for v in page_results.values())
            print(f"  -> {total_cards} cards scraped")
            for name, numbers in page_results.items():
                all_results[name].update(numbers)
        except Exception as e:
            print(f"  Error fetching: {e}", file=sys.stderr)

    # Build sorted output
    output: dict[str, list[int]] = {}
    for name in sorted(all_results.keys()):
        output[name] = sorted(all_results[name])

    # Write YAML
    out_path = "as_cards.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(
            output,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    total = sum(len(v) for v in output.values())
    print(f"\nDone! {total} cards across {len(output)} characters -> {out_path}")


if __name__ == "__main__":
    main()
