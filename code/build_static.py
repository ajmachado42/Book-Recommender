#!/usr/bin/env python3
"""Precompute every show's top recommendation into recommendations.json.

This lets the site run as plain static files (GitHub Pages, WordPress embed)
with no Python server. Re-run after editing the catalog:

    python3 build_static.py
"""
from __future__ import annotations

import json
from pathlib import Path

from book_recommender import BookRecommender

OUT = Path(__file__).resolve().parent / "recommendations.json"


def main() -> None:
    rec = BookRecommender()
    shows: dict[str, dict] = {}
    for title in rec.shows:
        results = rec.recommend(title, n=1)
        if not results:
            continue
        top = results[0]
        shows[title] = {
            "show": top.show.title,
            "title": top.book.title,
            "author": top.book.author,
            "year": top.book.year,
            "goodreads_url": top.book.goodreads_url,
        }
    lookup = {k: v for k, v in rec._lookup.items() if v in shows}
    OUT.write_text(json.dumps({"lookup": lookup, "shows": shows}, ensure_ascii=False, indent=1))
    print(f"Wrote {len(shows)} shows and {len(lookup)} lookup keys to {OUT.name}")


if __name__ == "__main__":
    main()
