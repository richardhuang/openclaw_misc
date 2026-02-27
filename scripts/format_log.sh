#!/bin/bash

# Script to monitor log file and format output beautifully
# Auto-detects the latest OpenClaw log file

# Find the latest log file in /tmp/openclaw/
find_latest_log() {
    local log_dir="/tmp/openclaw"

    if [ ! -d "$log_dir" ]; then
        echo "Error: Log directory $log_dir does not exist."
        exit 1
    fi

    # Find the latest .log file
    local latest_file=$(ls -t "$log_dir"/*.log 2>/dev/null | head -1)

    if [ -z "$latest_file" ]; then
        echo "Error: No log files found in $log_dir."
        exit 1
    fi

    echo "$latest_file"
}

# Use command line argument if provided, otherwise auto-detect
LOG_FILE="${1:-$(find_latest_log)}"

if [ ! -f "$LOG_FILE" ]; then
    echo "Error: Log file $LOG_FILE does not exist."
    exit 1
fi

echo "Monitoring $LOG_FILE with beautiful formatting..."
echo "Press Ctrl+C to stop"
echo "==========================================="

# Initialize last size
LAST_SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null)

# Function to assign consistent colors to strings
get_color_code() {
    local str="$1"
    # Hash the string to get a consistent color assignment
    local hash=$(echo -n "$str" | md5sum | cut -d' ' -f1 | tr -d '\n')
    local hash_num=$(printf "%d" 0x${hash:0:8})

    # Use modulo to get a color from 0-7 (standard ANSI colors)
    # 30-37: Foreground colors
    # 90-97: Bright foreground colors
    local color_idx=$((hash_num % 8))
    local colors=(31 32 33 34 35 36 91 92)  # Red, Green, Yellow, Blue, Magenta, Cyan, Bright Red, Bright Green
    echo ${colors[$color_idx]}
}

# Function to format and print a log entry
format_log_entry() {
    local line="$1"

    # Try to parse as JSON if it looks like JSON
    if [[ $line =~ ^\{.*\}$ ]]; then
        # Extract timestamp if possible
        local timestamp=$(echo "$line" | grep -o '"time":"[^"]*"' | cut -d'"' -f4)
        local level=$(echo "$line" | grep -o '"logLevelName":"[^"]*"' | cut -d'"' -f4)

        # Extract the message content to find module name
        local raw_message=$(echo "$line" | grep -o '"0":"[^"]*"' | cut -d'"' -f4 | sed 's/\\n/ /g' | sed 's/\\t/    /g' | sed 's/\\"/"/g')

        # Extract module from the message content (e.g., [tools], [api], etc.)
        local module=""
        local message=$raw_message

        # Check if the message starts with [something]
        if [[ $raw_message =~ ^\[([a-zA-Z]+)\][[:space:]]*(.*) ]]; then
            module="${BASH_REMATCH[1]}"
            # Extract the rest of the message after [module]
            message="${BASH_REMATCH[2]}"
        fi

        if [ -n "$timestamp" ] && [ -n "$level" ]; then
            # Convert UTC timestamp to GMT+8 (CST China Standard Time)
            # Parse the ISO 8601 timestamp and add 8 hours
            local formatted_time
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS version: convert UTC to local time and add 8 hours
                local epoch_seconds=$(date -jf '%Y-%m-%dT%H:%M:%S' "${timestamp:0:19}" +%s 2>/dev/null)
                if [ -n "$epoch_seconds" ]; then
                    # Add 8 hours (28800 seconds) for GMT+8
                    local gmt8_epoch=$((epoch_seconds + 28800))
                    formatted_time=$(date -r $gmt8_epoch +"%H:%M:%S" 2>/dev/null)
                else
                    # Fallback if the format doesn't match
                    formatted_time=$(date -jf '%Y-%m-%dT%H:%M:%S' "${timestamp:0:19}" 2>/dev/null | date -v+8H +"%H:%M:%S" 2>/dev/null || echo "XX:XX:XX")
                fi
            else
                # Linux version
                formatted_time=$(date -d "$timestamp +08:00" +"%H:%M:%S" 2>/dev/null)
            fi

            # If date parsing failed, use original timestamp
            if [ -z "$formatted_time" ]; then
                formatted_time=$(date -jf '%Y-%m-%dT%H:%M:%S' "${timestamp:0:19}" 2>/dev/null | date -v+8H +"%H:%M:%S" 2>/dev/null || echo "XX:XX:XX")
            fi

            # Apply color to module
            local color_code=$(get_color_code "$module")
            local colored_module=""
            if [ -n "$module" ]; then
                # Use proper escape sequences for terminal coloring
                colored_module="$(printf '\033[%sm[%s]\033[0m ' $color_code $module)"
            fi

            # Print with properly formatted color codes
            printf "\n\033[36m[%s]\033[0m %s\033[31m%s:\033[0m %s\n" "$formatted_time" "$colored_module" "$level" "$message"
        else
            # If not JSON or unable to parse, just print the raw line with formatting
            echo "📄 $line"
        fi
    else
        # If not JSON, just print with simple formatting
        echo "📄 $line"
    fi
}

# Function to print initial content if file has content
print_initial_content() {
    if [ $LAST_SIZE -gt 0 ]; then
        echo "Displaying existing content:"
        echo "---------------------------"
        tail -n 20 "$LOG_FILE" | while read -r line; do
            format_log_entry "$line"
        done
        echo ""
    fi
}

# Print existing content if any
print_initial_content

# Monitor for new content
tail -n 0 -f "$LOG_FILE" | while read -r line; do
    format_log_entry "$line"
done
