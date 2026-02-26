#!/usr/bin/env python3
"""
Extract token usage from Qwen (Code) local JSONL logs, grouped by date.

Qwen logs location: ~/.qwen/projects/*/chats/*.jsonl

Usage:
    python qwen_tokens_daily.py [--json] [--pretty]
"""

from __future__ import annotations

import argparse
import json
import sys
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def parse_timestamp(ts_str: str | None) -> str:
    """Extract date from ISO timestamp."""
    if not ts_str:
        return "unknown"
    try:
        if ts_str.endswith("Z"):
            if "." in ts_str:
                base, rest = ts_str.rsplit(".", 1)
                ms = rest.rstrip("Z")
                ms = ms[:3].ljust(3, "0")
                dt = datetime.strptime(f"{base}.{ms}Z", "%Y-%m-%dT%H:%M:%S.%fZ")
            else:
                dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")
        else:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return "unknown"


def extract_tokens_from_entry(entry: dict) -> dict:
    """Extract token counts from a Qwen log entry."""
    result = {
        "prompt_tokens": 0,
        "candidates_tokens": 0,
        "thoughts_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
        "model": None,
    }

    # Extract model
    if entry.get("type") == "assistant":
        result["model"] = entry.get("model")

    # Check usageMetadata
    usage = entry.get("usageMetadata", {})
    if isinstance(usage, dict):
        result["prompt_tokens"] = usage.get("promptTokenCount", 0)
        result["candidates_tokens"] = usage.get("candidatesTokenCount", 0)
        result["thoughts_tokens"] = usage.get("thoughtsTokenCount", 0)
        result["cached_tokens"] = usage.get("cachedContentTokenCount", 0)
        result["total_tokens"] = usage.get("totalTokenCount", 0)

    return result


def process_jsonl_file(filepath: Path) -> dict[str, dict]:
    """Process a single JSONL file and return daily token aggregates."""
    daily: dict[str, dict] = defaultdict(lambda: {
        "prompt_tokens": 0,
        "candidates_tokens": 0,
        "thoughts_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
        "models_used": set(),
    })

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if not isinstance(entry, dict):
                    continue

                ts = entry.get("timestamp")
                if not ts:
                    continue

                date_key = parse_timestamp(ts)

                tokens = extract_tokens_from_entry(entry)
                if tokens["total_tokens"] == 0:
                    continue

                daily[date_key]["prompt_tokens"] += tokens["prompt_tokens"]
                daily[date_key]["candidates_tokens"] += tokens["candidates_tokens"]
                daily[date_key]["thoughts_tokens"] += tokens["thoughts_tokens"]
                daily[date_key]["cached_tokens"] += tokens["cached_tokens"]
                daily[date_key]["total_tokens"] += tokens["total_tokens"]

                if tokens["model"]:
                    daily[date_key]["models_used"].add(tokens["model"])

            except (json.JSONDecodeError, KeyError, TypeError):
                continue

    return dict(daily)


def format_tokens(value: int) -> str:
    """Format token count with K/M suffix."""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.2f}K"
    else:
        return f"{value:,}"


def main():
    # Find Qwen project directory
    project_dirs = [
        str(Path.home() / ".qwen" / "projects" / "-Users-rhuang-workspace" / "chats"),
        str(Path.home() / ".qwen" / "projects"),
    ]

    project_dir = None
    for d in project_dirs:
        if Path(d).is_dir():
            project_dir = Path(d)
            break

    if not project_dir:
        print("Error: Cannot find Qwen project/chats directory.", file=sys.stderr)
        print("Expected:", project_dirs[0], file=sys.stderr)
        return 1

    # Find JSONL files
    jsonl_files = list(project_dir.glob("*.jsonl"))
    if not jsonl_files:
        print(f"Error: No .jsonl files found in {project_dir}", file=sys.stderr)
        return 1

    # Aggregate across all files
    aggregated: dict[str, dict] = defaultdict(lambda: {
        "prompt_tokens": 0,
        "candidates_tokens": 0,
        "thoughts_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
        "models_used": set(),
    })

    for f in jsonl_files:
        daily = process_jsonl_file(f)
        for date, stats in daily.items():
            for key in ["prompt_tokens", "candidates_tokens", "thoughts_tokens", "cached_tokens", "total_tokens"]:
                aggregated[date][key] += stats[key]
            aggregated[date]["models_used"].update(stats["models_used"])

    # Sort by date
    sorted_dates = sorted(aggregated.keys())

    if not sorted_dates:
        print("No token usage data found in Qwen logs.", file=sys.stderr)
        return 1

    # Output
    if args.json:
        output = {
            "provider": "qwen",
            "source": "jsonl",
            "dates": [
                {
                    "date": d,
                    "promptTokens": aggregated[d]["prompt_tokens"],
                    "candidatesTokens": aggregated[d]["candidates_tokens"],
                    "thoughtsTokens": aggregated[d]["thoughts_tokens"],
                    "cachedTokens": aggregated[d]["cached_tokens"],
                    "totalTokens": aggregated[d]["total_tokens"],
                    "totalTokensFormatted": format_tokens(aggregated[d]["total_tokens"]),
                    "models": sorted(aggregated[d]["models_used"]),
                }
                for d in sorted_dates
            ],
        }
        indent = 2 if args.pretty else None
        print(json.dumps(output, indent=indent, sort_keys=args.pretty))
    else:
        print("Qwen Token Usage by Date")
        print("=" * 60)
        for d in sorted_dates:
            stats = aggregated[d]
            prompt = stats["prompt_tokens"]
            candidates = stats["candidates_tokens"]
            thoughts = stats["thoughts_tokens"]
            cached = stats["cached_tokens"]
            total = stats["total_tokens"]

            print(f"\n{d}")
            print(f"  Prompt tokens:      {format_tokens(prompt)}")
            print(f"  Candidates tokens:  {format_tokens(candidates)}")
            print(f"  Thoughts tokens:    {format_tokens(thoughts)}")
            print(f"  Cached tokens:      {format_tokens(cached)}")
            print(f"  Total tokens:       {format_tokens(total)}")
            if stats["models_used"]:
                print(f"  Models used:        {', '.join(sorted(stats['models_used']))}")

    # Save to database if requested
    if args.save:
        save_to_database(aggregated)

    return 0


def save_to_database(daily_data: dict) -> None:
    """Save token usage data to SQLite database."""
    import sqlite3

    db_path = os.path.expanduser("~/.ai_token_usage.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure tool_name column exists
    cursor.execute("PRAGMA table_info(daily_usage)")
    columns = [col[1] for col in cursor.fetchall()]
    if "tool_name" not in columns:
        cursor.execute("ALTER TABLE daily_usage ADD COLUMN tool_name TEXT DEFAULT 'unknown'")

    for date, stats in daily_data.items():
        total = stats["total_tokens"]
        if total > 0:
            cursor.execute('''
                INSERT OR REPLACE INTO daily_usage (date, tokens_used, tool_name)
                VALUES (?, ?, ?)
            ''', (date, total, "qwen"))

    conn.commit()
    conn.close()
    print(f"\nSaved {len(daily_data)} days of data to database ({db_path})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract token usage from Qwen local JSONL logs, grouped by date."
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--pretty", action="store_true",
        help="Pretty-print JSON output"
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save data to SQLite database"
    )

    args = parser.parse_args()
    raise SystemExit(main())
