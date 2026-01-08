#!/usr/bin/env python3

import argparse
import csv
import time
import re
import sys
from urllib.parse import quote
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
    "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
    "Nehemiah", "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon",
    "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Haggai", "Zechariah", "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians",
    "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
    "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
    "1 John", "2 John", "3 John", "Jude", "Revelation"
]

VERSION_CODES = {
    "KJV": "KJV",
    "NIV": "NIV",
    "NLT": "NLT",
    "ESV": "ESV",
    "CSB": "CSB", 
    "TLB": "TLB",
    "DRA": "DRA",
    "EXB": "EXB",
    "AMP": "AMP",
    "GNT": "GNT",
    "CEB": "CEB"

}

def parse_reference(ref: str):
    match = re.match(r"^(\d*\s?[A-Za-z\s]+)\s+(\d+):(\d+)$", ref.strip())
    if not match:
        raise ValueError(f"Invalid reference format: {ref}")
    book = match.group(1).strip()
    chapter = int(match.group(2))
    verse = int(match.group(3))
    if book not in BOOKS:
        raise ValueError(f"Unknown book: {book}")
    return book, chapter, verse

def get_verse_text(version: str, book: str, chapter: int, verse: int, session: requests.Session) -> str:
    code = VERSION_CODES.get(version)
    if not code:
        return ""

    book_encoded = quote(book)
    search = f"{book_encoded}%20{chapter}:{verse}"
    url = f"https://www.biblegateway.com/passage/?search={search}&version={code}"

    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            return ""
        soup = BeautifulSoup(response.text, "html.parser")

        # Get the whole passage container
        passage = soup.find("div", class_=re.compile(r"passage-content|passage-text|result-text|text-style"))
        if not passage:
            return ""

        # Remove unwanted elements (footnotes, crossrefs, verse/chapter numbers)
        for elem in passage.find_all(["sup", "a", "span"], class_=re.compile(r"crossreference|footnote|versenum|chapternum")):
            elem.decompose()

        # Get all remaining text
        full_text = passage.get_text(separator=" ", strip=True)
        full_text = re.sub(r"\s{2,}", " ", full_text).strip()

        # Remove trailing "Read full chapter ... in all English translations" and similar phrases
        full_text = re.sub(r"Read full chapter.*?(?:in all English translations)?\s*$", "", full_text, flags=re.IGNORECASE).strip()
        full_text = re.sub(r"in all English translations.*$", "", full_text, flags=re.IGNORECASE).strip()

        return full_text
    except Exception:
        return ""

def advance_reference(book: str, chapter: int, verse: int, session: requests.Session) -> Optional[tuple[str, int, int]]:
    test_verse = verse + 1
    test_chapter = chapter
    test_book = book

    attempts = 0
    max_attempts = 300

    while attempts < max_attempts:
        attempts += 1
        text = get_verse_text("NIV", test_book, test_chapter, test_verse, session)
        if text:
            return test_book, test_chapter, test_verse

        test_verse += 1
        if test_verse > 176:
            test_verse = 1
            test_chapter += 1
            if test_chapter > 150:
                try:
                    idx = BOOKS.index(test_book) + 1
                    if idx < len(BOOKS):
                        test_book = BOOKS[idx]
                        test_chapter = 1
                    else:
                        return None
                except ValueError:
                    return None
    return None

def main():
    parser = argparse.ArgumentParser(description="Export Bible verses from BibleGateway")
    parser.add_argument("--start", required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--translations", default="AKJV,NIV,NRSVCE")
    parser.add_argument("--out", default="output.csv")
    args = parser.parse_args()

    translations = [t.strip() for t in args.translations.split(",")]

    current_book, current_chapter, current_verse = parse_reference(args.start)

    rows = []
    exported = 0
    session = requests.Session()
    session.headers.update({"User-Agent": "BibleExporter/1.0"})

    print("Starting export...")
    while exported < args.count:
        ref = f"{current_book} {current_chapter}:{current_verse}"
        row = {"ref": ref}

        has_text = False
        for trans in translations:
            print(f"Fetching {ref} ({trans})...   ", end="\r")
            text = get_verse_text(trans, current_book, current_chapter, current_verse, session)
            row[trans] = text
            if text:
                has_text = True

        if not has_text:
            print(f"\nNo text for {ref} in any translation. Stopping early.")
            break

        rows.append(row)
        exported += 1

        next_ref = advance_reference(current_book, current_chapter, current_verse, session)
        if next_ref is None:
            print("\nReached end of Bible.")
            break
        current_book, current_chapter, current_verse = next_ref

        time.sleep(1.3)

    print("\nWriting CSV...")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["BOOK CHAPTER:VERSE"] + translations
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            csv_row = {"BOOK CHAPTER:VERSE": row["ref"]}
            for t in translations:
                csv_row[t] = row.get(t, "")
            writer.writerow(csv_row)

    last_ref = rows[-1]["ref"] if rows else args.start
    print(f"Exported {exported} verses, last verse: {last_ref}, to {args.out}")

if __name__ == "__main__":
    main()
