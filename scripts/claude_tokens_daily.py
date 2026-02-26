#!/usr/bin/env python3
"""
Summarize Claude Code token usage from local JSONL logs.

This script extracts token usage directly from Claude Code's local log files
(~/.claude/projects/*/log.jsonl), grouped by date.

It complements `codexbar cost` by providing fine-grained token breakdowns:
- input_tokens: prompt + tool user messages
- output_tokens: assistant responses
- cache_read_tokens: cached prompt tokens reused
- cache_creation_tokens: new cache entries created

Usage:
    python claude_tokens_daily.py [--json] [--pretty]

Output:
    - Text: Human-readable daily summary
    - JSON: Machine-readable format with dates, tokens, models
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
        # Handle 'Z' suffix (UTC)
        if ts_str.endswith("Z"):
            # Python's %f expects 6 digits, but JSONL uses 3 (milliseconds)
            if "." in ts_str:
                base, rest = ts_str.rsplit(".", 1)
                ms = rest.rstrip("Z")
                ms = ms[:3].ljust(3, "0")  # Ensure 3 digits
                dt = datetime.strptime(f"{base}.{ms}Z", "%Y-%m-%dT%H:%M:%S.%fZ")
            else:
                dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")
        else:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return "unknown"


def extract_tokens_from_entry(entry: dict) -> dict:
    """Extract token counts from a Claude Code log entry."""
    result = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "model": None,
    }

    # Extract model
    if entry.get("type") == "assistant":
        msg = entry.get("message", {})
        if isinstance(msg, dict):
            result["model"] = msg.get("model")

    # Check usage in multiple locations
    usage = None

    # 1. Top-level usage (some entries)
    if "usage" in entry:
        usage = entry["usage"]

    # 2. message.usage (more common for assistant messages)
    elif entry.get("type") == "assistant" and "message" in entry:
        msg = entry["message"]
        if isinstance(msg, dict):
            usage = msg.get("usage")

    if usage and isinstance(usage, dict):
        result["input_tokens"] = usage.get("input_tokens", 0)
        result["output_tokens"] = usage.get("output_tokens", 0)
        result["cache_read_tokens"] = usage.get("cache_read_input_tokens", 0)
        result["cache_creation_tokens"] = usage.get("cache_creation_input_tokens", 0)

    return result


def process_jsonl_file(filepath: Path) -> dict[str, dict]:
    """Process a single JSONL file and return daily token aggregates."""
    daily: dict[str, dict] = defaultdict(lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
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

                # Find timestamp
                ts = entry.get("timestamp")
                if not ts:
                    continue

                date_key = parse_timestamp(ts)

                # Extract tokens
                tokens = extract_tokens_from_entry(entry)
                if sum([
                    tokens["input_tokens"],
                    tokens["output_tokens"],
                    tokens["cache_read_tokens"],
                    tokens["cache_creation_tokens"],
                ]) == 0:
                    continue

                # Aggregate
                daily[date_key]["input_tokens"] += tokens["input_tokens"]
                daily[date_key]["output_tokens"] += tokens["output_tokens"]
                daily[date_key]["cache_read_tokens"] += tokens["cache_read_tokens"]
                daily[date_key]["cache_creation_tokens"] += tokens["cache_creation_tokens"]

                if tokens["model"]:
                    daily[date_key]["models_used"].add(tokens["model"])

            except (json.JSONDecodeError, KeyError, TypeError):
                continue

    return dict(daily)


def main():
    # Find Claude project directory
    project_dirs = [
        str(Path.home() / ".claude" / "projects" / "-Users-rhuang-workspace"),
        str(Path.home() / ".config" / "claude" / "projects"),
    ]

    project_dir = None
    for d in project_dirs:
        if Path(d).is_dir():
            project_dir = Path(d)
            break

    if not project_dir:
        print("Error: Cannot find Claude project directory.", file=sys.stderr)
        print("Expected:", project_dirs[0], file=sys.stderr)
        return 1

    # Find JSONL files
    jsonl_files = list(project_dir.glob("*.jsonl"))
    if not jsonl_files:
        print(f"Error: No .jsonl files found in {project_dir}", file=sys.stderr)
        return 1

    # Aggregate across all files
    aggregated: dict[str, dict] = defaultdict(lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "models_used": set(),
    })

    for f in jsonl_files:
        daily = process_jsonl_file(f)
        for date, stats in daily.items():
            for key in ["input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens"]:
                aggregated[date][key] += stats[key]
            aggregated[date]["models_used"].update(stats["models_used"])

    # Sort by date
    sorted_dates = sorted(aggregated.keys())

    if not sorted_dates:
        print("No token usage data found in Claude logs.", file=sys.stderr)
        return 1

    # Output
    if args.json:
        output = {
            "provider": "claude",
            "source": "jsonl",
            "dates": [
                {
                    "date": d,
                    "inputTokens": aggregated[d]["input_tokens"],
                    "outputTokens": aggregated[d]["output_tokens"],
                    "cacheReadTokens": aggregated[d]["cache_read_tokens"],
                    "cacheCreationTokens": aggregated[d]["cache_creation_tokens"],
                    "totalTokens": (
                        aggregated[d]["input_tokens"]
                        + aggregated[d]["output_tokens"]
                        + aggregated[d]["cache_read_tokens"]
                        + aggregated[d]["cache_creation_tokens"]
                    ),
                    "totalTokensFormatted": format_tokens(
                        aggregated[d]["input_tokens"]
                        + aggregated[d]["output_tokens"]
                        + aggregated[d]["cache_read_tokens"]
                        + aggregated[d]["cache_creation_tokens"]
                    ),
                    "models": sorted(aggregated[d]["models_used"]),
                }
                for d in sorted_dates
            ],
        }
        indent = 2 if args.pretty else None
        print(json.dumps(output, indent=indent, sort_keys=args.pretty))
    else:
        print("Claude Code Token Usage by Date")
        print("=" * 60)
        for d in sorted_dates:
            stats = aggregated[d]
            total = (
                stats["input_tokens"]
                + stats["output_tokens"]
                + stats["cache_read_tokens"]
                + stats["cache_creation_tokens"]
            )
            print(f"\n{d}")
            print(f"  Input tokens:        {format_tokens(stats['input_tokens'])}")
            print(f"  Output tokens:       {format_tokens(stats['output_tokens'])}")
            print(f"  Cache read tokens:   {format_tokens(stats['cache_read_tokens'])}")
            print(f"  Cache creation:      {format_tokens(stats['cache_creation_tokens'])}")
            print(f"  Total tokens:        {format_tokens(total)}")
            if stats["models_used"]:
                print(f"  Models used:         {', '.join(sorted(stats['models_used']))}")

    # Save to database if requested
    if args.save:
        save_to_database(aggregated)

    return 0


def format_tokens(value: int) -> str:
    """Format token count with K/M suffix."""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.2f}K"
    else:
        return f"{value:,}"


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
        total = (
            stats["input_tokens"]
            + stats["output_tokens"]
            + stats["cache_read_tokens"]
            + stats["cache_creation_tokens"]
        )
        if total > 0:
            cursor.execute('''
                INSERT OR REPLACE INTO daily_usage (date, tokens_used, tool_name)
                VALUES (?, ?, ?)
            ''', (date, total, "claude"))

    conn.commit()
    conn.close()
    print(f"\nSaved {len(daily_data)} days of data to database ({db_path})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract token usage from Claude Code local JSONL logs, grouped by date."
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
