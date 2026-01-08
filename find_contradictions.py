#!/usr/bin/env python3
"""
Fetch one Bible verse from https://www.biblegateway.com/verse/en/
Output JSON with requested structure + short contradiction description.
"""

import argparse
import json
import re
import sys
from urllib.parse import quote
from datetime import datetime
from typing import Dict

import requests
from bs4 import BeautifulSoup


def clean_verse_text(text: str) -> str:
    text = re.sub(r'\[\d+\]|\d+\s*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'(Read full chapter|in all English translations).*', '', text, flags=re.I)
    return text.strip()


def get_all_translations(url: str) -> Dict[str, str]:
    headers = {"User-Agent": "BibleJsonExporter/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=12)
        r.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch page: {e}", file=sys.stderr)
        return {}

    soup = BeautifulSoup(r.text, "html.parser")

    translations = {}

    blocks = soup.find_all(["p", "div"], class_=re.compile(r"version|text|result|passage"))

    for block in blocks:
        version_tag = block.find(["strong", "b", "span", "em"], string=re.compile(r'\[.*?\]'))
        version = None
        if version_tag:
            version = version_tag.get_text(strip=True).strip("[]").upper()
            version_tag.decompose()

        text = clean_verse_text(block.get_text(" ", strip=True))
        if text and len(text) > 15:
            if not version:
                text_lower = text.lower()
                for code in ["niv", "nlt", "csb", "net", "kjv", "esv", "nasb", "nrsv", "akjv", "msg", "cev", "cjb"]:
                    if code in text_lower:
                        version = code.upper()
                        break
                if not version:
                    continue
            translations[version] = text

    return translations


def calculate_contradiction_score(variants: Dict[str, str]) -> float:
    if len(variants) < 2:
        return 0.0

    texts = list(variants.values())
    total_diff = 0
    count = 0

    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            words_i = set(texts[i].lower().split())
            words_j = set(texts[j].lower().split())
            diff = len(words_i.symmetric_difference(words_j))
            total_diff += diff
            count += 1

    if count == 0:
        return 0.0

    avg_diff = total_diff / count
    score = min(100.0, avg_diff * 5)  # same scaling as before
    return round(score, 1)


def generate_short_contradiction_desc(variants: Dict[str, str], score: float) -> str:
    """
    Generate a very short (≤25 words) description of the main contradiction.
    Very basic heuristic — can be improved later.
    """
    if len(variants) < 2:
        return "No significant differences detected."

    texts = list(variants.values())
    txt1, txt2 = texts[0].lower(), texts[1].lower()

    # Quick keyword checks for common contradiction types
    if "begotten" in txt1 and ("only" in txt2 or "unique" in txt2):
        return "Only begotten Son vs one and only Son."

    if "perish" in txt1 and "not perish" in txt2:
        return "Eternal life vs perish vs not perish."

    if "god" in txt1 and "he" in txt2:
        return "God manifest vs He who was manifest."

    if "heaven" in txt1 and "heavens" in txt2:
        return "Heaven vs heavens wording difference."

    if score < 20:
        return "Minor wording variation only."

    if score < 50:
        return "Noticeable phrasing differences."

    return "Significant textual variation in meaning."


def main():
    parser = argparse.ArgumentParser(description="Fetch one Bible verse → JSON in requested format")
    parser.add_argument("--verse", required=True, help='Reference, e.g. "Genesis 1:1"')
    parser.add_argument("--out", default="verse.json", help="Output JSON file")
    args = parser.parse_args()

    ref = args.verse.strip()
    match = re.match(r"^([A-Za-z\s]+)\s+(\d+):(\d+)$", ref)
    if not match:
        print("Invalid format. Use e.g. 'Genesis 1:1'", file=sys.stderr)
        sys.exit(1)

    book_name = match.group(1).strip()
    chapter = int(match.group(2))
    verse_num = int(match.group(3))

    book_encoded = quote(book_name)
    cv_encoded = quote(f"{chapter}:{verse_num}")
    url = f"https://www.biblegateway.com/verse/en/{book_encoded}%20{cv_encoded}"

    print(f"Fetching: {url}")

    session = requests.Session()
    session.headers.update({"User-Agent": "BibleJsonExporter/1.0"})

    translations = get_all_translations(url)

    if not translations:
        print("No translations found on the page.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(translations)} translations.")

    contradiction_score = calculate_contradiction_score(translations)
    short_desc = generate_short_contradiction_desc(translations, contradiction_score)

    now_iso = datetime.utcnow().isoformat(timespec='seconds') + "Z"

    output = {
        "book": book_name,
        "chapter": chapter,
        "verse": verse_num,
        "link": url,
        "time": now_iso,
        "data": translations,
        "contradiction_score": contradiction_score,
        "contradiction_desc": short_desc
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Wrote to {args.out}")
    print(f"Translations: {len(translations)}")
    print(f"Score: {contradiction_score}")
    print(f"Short desc: {short_desc}")


if __name__ == "__main__":
    main()
