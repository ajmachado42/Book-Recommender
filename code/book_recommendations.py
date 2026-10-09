#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from book_recommender import BookRecommender  # noqa: E402


def get_top_recommendation(show_query: str, n: int = 1) -> dict[str, str | int]:
    rec = BookRecommender()
    results = rec.recommend(show_query, n=n)
    if not results:
        raise ValueError(f"No recommendation found for '{show_query}'")

    top = results[0]
    return {
        "show": top.show.title,
        "title": top.book.title,
        "author": top.book.author,
        "year": top.book.year,
        "goodreads_url": top.book.goodreads_url,
    }


def send_json(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class RecommendationHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:  # pragma: no cover
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_HEAD(self) -> None:
        self._send_static_or_json_headers()

    def _send_static_or_json_headers(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/recommend":
            query = urllib.parse.parse_qs(parsed.query).get("show", [""])[0].strip()
            if not query:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                return
            try:
                result = get_top_recommendation(query)
            except Exception as exc:  # pragma: no cover
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                return
            body = json.dumps({"result": result}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return

        if path in {"/", "/index.html"}:
            file_path = ROOT / "index.html"
        else:
            file_path = ROOT / path.lstrip("/")

        if file_path.exists() and file_path.is_file():
            mime_type, _ = mimetypes.guess_type(str(file_path))
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/recommend":
            query = urllib.parse.parse_qs(parsed.query).get("show", [""])[0].strip()
            if not query:
                send_json(self, {"error": "Missing show query parameter"}, 400)
                return
            try:
                result = get_top_recommendation(query)
                send_json(self, {"result": result})
            except Exception as exc:  # pragma: no cover
                send_json(self, {"error": str(exc)}, 400)
            return

        if path in {"/", "/index.html"}:
            file_path = ROOT / "index.html"
        else:
            file_path = ROOT / path.lstrip("/")

        if file_path.exists() and file_path.is_file():
            mime_type, _ = mimetypes.guess_type(str(file_path))
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_response(404)
        self.end_headers()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the book recommender and expose a JSON API.")
    parser.add_argument("show", nargs="?", help="Optional show name to recommend immediately")
    parser.add_argument("--port", type=int, default=8000, help="Port for the local server (default: 8000)")
    parser.add_argument("--json", action="store_true", help="Print the recommendation as JSON instead of serving HTTP")
    args = parser.parse_args(argv)

    if args.show:
        try:
            result = get_top_recommendation(args.show)
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps({"result": result}, ensure_ascii=False))
        else:
            print(json.dumps({"result": result}, ensure_ascii=False))
        return 0

    server = ThreadingHTTPServer(("127.0.0.1", args.port), RecommendationHandler)
    print(f"Serving Book Recommender on http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        print("\nStopping server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
