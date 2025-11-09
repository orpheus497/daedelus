#!/usr/bin/env fish
# Daedalus Fish Shell Integration
# Version: 0.1.0
# Created by: orpheus497
#
# Provides real-time command logging and intelligent suggestions
# for the Daedalus self-learning terminal assistant.

# ============================================
# Configuration
# ============================================

# Socket path for daemon communication
set -g DAEDELUS_SOCKET "$HOME/.local/share/daedelus/runtime/daemon.sock"

# Session ID (generated once per shell session)
set -g DAEDELUS_SESSION_ID "fish-"(random)(date +%s)

# ============================================
# Utility Functions
# ============================================

# Check if daemon is running
function daedelus_is_daemon_running
    test -S "$DAEDELUS_SOCKET"
end

# Send JSON message to daemon
function daedelus_send_message
    set -l message $argv[1]

    if not daedelus_is_daemon_running
        return 1
    end

    # Send via netcat with timeout
    echo "$message" | timeout 1s nc -U "$DAEDELUS_SOCKET" 2>/dev/null
end

# JSON escape function
function daedelus_json_escape
    set -l str $argv[1]
    # Basic escaping for JSON
    string replace -a '\\' '\\\\' -- $str | \
        string replace -a '"' '\\"' | \
        string replace -a (printf '\n') '\\n' | \
        string replace -a (printf '\t') '\\t'
end

# ============================================
# Command Logging
# ============================================

# Post-execution hook (fish_postexec)
function daedelus_postexec --on-event fish_postexec
    set -l cmd $argv[1]
    set -l exit_code $status

    # Skip if empty
    if test -z "$cmd"
        return
    end

    # Skip internal commands
    if string match -q 'daedelus_*' -- $cmd
        return
    end

    # Escape for JSON
    set -l cmd_escaped (daedelus_json_escape "$cmd")
    set -l cwd_escaped (daedelus_json_escape "$PWD")
    set -l session_escaped (daedelus_json_escape "$DAEDELUS_SESSION_ID")

    # Build JSON message
    set -l message "{
    \"type\": \"log_command\",
    \"data\": {
        \"command\": \"$cmd_escaped\",
        \"exit_code\": $exit_code,
        \"duration\": 0.0,
        \"cwd\": \"$cwd_escaped\",
        \"session_id\": \"$session_escaped\"
    }
}"

    # Send asynchronously
    daedelus_send_message "$message" &>/dev/null &
end

# ============================================
# Suggestion Functions
# ============================================

# Get suggestions from daemon
function daedelus_get_suggestions
    set -l partial $argv[1]

    set -l cwd_escaped (daedelus_json_escape "$PWD")
    set -l partial_escaped (daedelus_json_escape "$partial")

    # Get recent history
    set -l history_json "["
    set -l first 1

    for cmd in (history --max 10)
        if test $first -eq 0
            set history_json "$history_json,"
        end
        set -l cmd_escaped (daedelus_json_escape "$cmd")
        set history_json "$history_json\"$cmd_escaped\""
        set first 0
    end

    set history_json "$history_json]"

    # Build request message
    set -l message "{
    \"type\": \"suggest\",
    \"data\": {
        \"partial\": \"$partial_escaped\",
        \"cwd\": \"$cwd_escaped\",
        \"history\": $history_json
    }
}"

    # Send and return response
    daedelus_send_message "$message"
end

# Parse suggestions from JSON
function daedelus_parse_suggestions
    set -l response $argv[1]

    # Use jq if available
    if command -v jq >/dev/null 2>&1
        echo "$response" | jq -r '.suggestions[]? | .command' 2>/dev/null
    else
        # Basic parsing
        echo "$response" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | \
            sed 's/"command"[[:space:]]*:[[:space:]]*"\([^"]*\)"/\1/'
    end
end

# ============================================
# Interactive Suggestion
# ============================================

function daedelus_suggest
    # Check daemon
    if not daedelus_is_daemon_running
        echo "⚠️  Daedelus daemon not running" >&2
        return 1
    end

    # Get current commandline
    set -l buffer (commandline -b)

    # Skip empty
    if test -z "$buffer"
        return
    end

    # Get suggestions
    set -l response (daedelus_get_suggestions "$buffer")

    if test -z "$response"
        echo "No suggestions available" >&2
        return
    end

    # Parse suggestions
    set -l suggestions (daedelus_parse_suggestions "$response")

    if test (count $suggestions) -eq 0
        echo "No suggestions found" >&2
        return
    end

    # Show suggestions
    echo
    echo "Suggestions from Daedelus:"
    set -l i 1
    for suggestion in $suggestions
        echo "  [$i] $suggestion"
        set i (math $i + 1)
    end

    # If only one suggestion, use it
    if test (count $suggestions) -eq 1
        commandline -r "$suggestions[1]"
    end
end

# ============================================
# Keybindings
# ============================================

# Bind Ctrl+Space to suggestions (Fish uses different key notation)
bind \cSpace daedelus_suggest

# ============================================
# Initialization
# ============================================

function daedelus_init
    # Check daemon
    if not daedelus_is_daemon_running
        echo "⚠️  Daedelus daemon not running"
        echo "Start it with: daedelus start"
        return 1
    end

    # Ping daemon
    set -l ping_response (daedelus_send_message '{"type":"ping","data":{}}')

    if test -z "$ping_response"
        echo "⚠️  Cannot communicate with Daedelus daemon"
        return 1
    end

    echo "✅ Daedelus Fish integration loaded (session: "(string sub -l 16 $DAEDELUS_SESSION_ID)"...)"
    echo "   Press Ctrl+Space for suggestions"
end

# Run initialization
daedelus_init

# ============================================
# User Aliases
# ============================================

alias dstatus='daedelus status'
alias dsearch='daedelus search'

# ============================================
# End of Daedelus Fish Integration
# ============================================
