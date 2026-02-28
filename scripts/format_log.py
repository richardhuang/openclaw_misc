#!/usr/bin/env python3
"""
OpenClaw Log Formatter - Format and display OpenClaw logs with colors
Auto-detects the latest log file from /tmp/openclaw/
"""

import argparse
import json
import os
import re
import sys
import time
import io
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

# Use unbuffered output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

# Color codes
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Standard ANSI colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


# Level to color mapping
LEVEL_COLORS = {
    "TRACE": Color.BRIGHT_BLACK,
    "DEBUG": Color.BRIGHT_BLUE,
    "INFO": Color.BRIGHT_GREEN,
    "WARN": Color.BRIGHT_YELLOW,
    "ERROR": Color.BRIGHT_RED,
    "FATAL": Color.RED + Color.BOLD,
}

# Module to color mapping (consistent colors based on module name)
_MODULE_COLORS: Dict[str, str] = {}


def get_module_color(module: str) -> str:
    """Get a consistent color for a module name."""
    if module not in _MODULE_COLORS:
        # Hash the module name to pick a color
        hash_val = hash(module)
        colors = [
            Color.BRIGHT_CYAN,
            Color.BRIGHT_MAGENTA,
            Color.BRIGHT_BLUE,
            Color.BRIGHT_YELLOW,
            Color.BRIGHT_GREEN,
            Color.BRIGHT_RED,
        ]
        _MODULE_COLORS[module] = colors[hash_val % len(colors)]
    return _MODULE_COLORS[module]


def convert_to_gmt8(timestamp_str: str) -> str:
    """Convert UTC timestamp to GMT+8 (CST China Standard Time)."""
    try:
        # Parse ISO 8601 timestamp
        # Format: 2026-02-27T16:26:46.306Z
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        # Convert to GMT+8
        gmt8 = dt.astimezone(timezone(timedelta(hours=8)))
        # Only show to seconds, no milliseconds
        return gmt8.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return timestamp_str


def parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a JSON log line and extract relevant fields."""
    line = line.strip()
    if not line:
        return None

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None

    # Extract fields
    timestamp = data.get("time", "")
    level = data.get("_meta", {}).get("logLevelName", "INFO")
    msg_0 = data.get("0", "")
    msg_1 = data.get("1", "")

    # Also include _meta fields for reference
    meta = data.get("_meta", {})

    # Extract module from msg_0 (e.g., {"subsystem":"gateway/canvas"})
    module = ""
    subsystem = ""
    message = ""

    if isinstance(msg_0, str):
        try:
            sub_data = json.loads(msg_0)
            subsystem = sub_data.get("subsystem", "")
        except json.JSONDecodeError:
            # msg_0 is a plain string, could be either a subsystem name or the message itself
            # Try to determine if it looks like a subsystem (starts with { or has "subsystem" key)
            # If it looks like a path like "gateway/canvas", treat as subsystem
            # Otherwise treat as message
            if msg_0.startswith("{"):
                # Try to extract subsystem from malformed JSON
                m = re.search(r'"subsystem"\s*:\s*"([^"]+)"', msg_0)
                if m:
                    subsystem = m.group(1)
            elif msg_0.startswith('"') and msg_0.endswith('"'):
                # Quoted string - try to extract subsystem path
                inner = msg_0[1:-1]  # Remove quotes
                if "/" in inner and not inner.startswith("http") and " " not in inner.split("/")[0]:
                    # Looks like "gateway/canvas" format
                    subsystem = inner
                else:
                    message = inner
            elif "/" in msg_0 and not msg_0.startswith("http"):
                # Check if it's a subsystem path (short, no spaces in first part)
                first_part = msg_0.split("/")[0]
                if " " not in first_part and len(first_part) < 30:
                    subsystem = msg_0
                else:
                    message = msg_0
            else:
                message = msg_0

        # Extract module name from subsystem
        if subsystem:
            if "/" in subsystem:
                module = subsystem.split("/")[0]
            else:
                module = subsystem

    # Message is in msg_1 if available, otherwise we might have it in msg_0
    if msg_1:
        message = msg_1 if isinstance(msg_1, str) else json.dumps(msg_1)
        # Clean up the message - replace \n with space
        message = message.replace("\\n", " ").replace("\n", " ")

    # If still no message, try to get from msg_0
    if not message:
        # message was already set from msg_0 if msg_0 wasn't a JSON object
        # Clean up the message
        message = message.replace("\\n", " ").replace("\n", " ")

    return {
        "time": timestamp,
        "level": level,
        "module": module,
        "message": message,
        "meta": meta,
    }


def format_log_entry(entry: Dict[str, Any], full_meta: bool = False) -> str:
    """Format a log entry with colors."""
    timestamp = entry.get("time", "")
    level = entry.get("level", "INFO")
    module = entry.get("module", "")
    message = entry.get("message", "")
    meta = entry.get("meta", {})

    # Convert timestamp to GMT+8 (only to seconds)
    formatted_time = convert_to_gmt8(timestamp)

    # Get colors
    level_color = LEVEL_COLORS.get(level, Color.WHITE)

    # Build formatted output
    # Time | Module | Level | Message
    output_parts = []

    # Time in cyan (only show time without date for compactness)
    output_parts.append(f"{Color.BRIGHT_CYAN}[{formatted_time}]{Color.RESET}")

    # Module in colored brackets (skip if too long or empty)
    if module and len(module) < 50:
        # Use a consistent color for this module
        if module not in _MODULE_COLORS:
            hash_val = hash(module)
            colors = [
                Color.BRIGHT_CYAN,
                Color.BRIGHT_MAGENTA,
                Color.BRIGHT_BLUE,
                Color.BRIGHT_YELLOW,
                Color.BRIGHT_GREEN,
                Color.BRIGHT_RED,
            ]
            _MODULE_COLORS[module] = colors[hash_val % len(colors)]
        output_parts.append(f"{_MODULE_COLORS[module]}[{module}]{Color.RESET}")

    # Level with color
    output_parts.append(f"{level_color}{level}{Color.RESET}")

    # Message (no extra color, keep original formatting)
    output_parts.append(message)

    # Full meta info if requested
    if full_meta and meta:
        meta_parts = []
        for k, v in meta.items():
            if isinstance(v, dict):
                # Format nested dict
                meta_parts.append(f"{k}={json.dumps(v)}")
            else:
                meta_parts.append(f"{k}={v}")
        output_parts.append(f"{Color.DIM}# {', '.join(meta_parts)}{Color.RESET}")

    return " | ".join(output_parts)


def find_latest_log(log_dir: str = "/tmp/openclaw") -> Optional[str]:
    """Find the latest .log file in the specified directory."""
    path = Path(log_dir)
    if not path.exists():
        return None

    log_files = list(path.glob("*.log"))
    if not log_files:
        return None

    # Sort by modification time, newest first
    log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return str(log_files[0])


def print_header(log_file: str):
    """Print the header with log file info."""
    print()
    print(f"{Color.CYAN}{'=' * 60}{Color.RESET}")
    print(f"{Color.BOLD}OpenClaw Log Monitor{Color.RESET}")
    print(f"{Color.CYAN}{'=' * 60}{Color.RESET}")
    print(f"{Color.WHITE}File: {Color.BRIGHT_CYAN}{log_file}{Color.RESET}")
    print(f"{Color.WHITE}Monitoring for new entries... (Ctrl+C to stop){Color.RESET}")
    print(f"{Color.CYAN}{'=' * 60}{Color.RESET}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Format and display OpenClaw logs")
    parser.add_argument("log_file", nargs="?", help="Log file to display (auto-detects latest if not specified)")
    parser.add_argument("-f", "--follow", action="store_true", help="Follow log file for new entries")
    parser.add_argument("-n", "--lines", type=int, default=20, help="Number of lines to show (default: 20)")
    parser.add_argument("-l", "--full-meta", action="store_true", help="Include full _meta fields in output")
    args = parser.parse_args()

    # Determine log file
    log_file = None

    if args.log_file:
        # Use command line argument
        log_file = args.log_file
        if not os.path.isfile(log_file):
            print(f"{Color.RED}Error: Log file '{log_file}' does not exist.{Color.RESET}")
            sys.exit(1)
    else:
        # Auto-detect
        log_file = find_latest_log("/tmp/openclaw")
        if not log_file:
            print(f"{Color.RED}Error: No log files found in /tmp/openclaw/{Color.RESET}")
            print(f"{Color.YELLOW}Hint: Specify a log file manually{Color.RESET}")
            print(f"  Usage: {sys.argv[0]} /tmp/openclaw/openclaw-2026-02-28.log")
            sys.exit(1)

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

            # Show header only if following or if explicitly requested
            if args.follow:
                print()
                print(f"{Color.CYAN}{'=' * 60}{Color.RESET}")
                print(f"{Color.BOLD}OpenClaw Log Monitor{Color.RESET}")
                print(f"{Color.CYAN}{'=' * 60}{Color.RESET}")
                print(f"{Color.WHITE}File: {Color.BRIGHT_CYAN}{log_file}{Color.RESET}")
                print(f"{Color.CYAN}{'=' * 60}{Color.RESET}")
                print()

            # Show recent logs
            print(f"{Color.BOLD}Recent logs:{Color.RESET}")
            print(f"{Color.DIM}{'-' * 60}{Color.RESET}")

            for line in lines[-args.lines:]:
                entry = parse_log_line(line)
                if entry:
                    print(format_log_entry(entry, args.full_meta))
                elif line.strip():
                    print(f"{Color.BRIGHT_BLACK}└─ {line.rstrip()}{Color.RESET}")

            print()
    except Exception as e:
        print(f"{Color.RED}Error reading log file: {e}{Color.RESET}")

    # Follow mode
    if args.follow:
        print(f"{Color.BOLD}Live monitoring (Ctrl+C to stop):{Color.RESET}")
        print(f"{Color.DIM}{'-' * 60}{Color.RESET}")

        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                f.seek(0, 2)  # Seek to end
                while True:
                    line = f.readline()
                    if line:
                        entry = parse_log_line(line)
                        if entry:
                            print(format_log_entry(entry, args.full_meta))
                        elif line.strip():
                            print(f"{Color.BRIGHT_BLACK}└─ {line.rstrip()}{Color.RESET}")
                    else:
                        time.sleep(0.1)
        except KeyboardInterrupt:
            print(f"\n{Color.YELLOW}Monitoring stopped.{Color.RESET}")
        except Exception as e:
            print(f"\n{Color.RED}Error: {e}{Color.RESET}")
            sys.exit(1)


if __name__ == "__main__":
    main()
