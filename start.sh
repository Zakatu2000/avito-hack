#!/usr/bin/env bash
set -euo pipefail

if ! command -v cygpath >/dev/null || ! command -v powershell.exe >/dev/null; then
    printf '%s\n' 'Run this launcher in Git Bash on Windows, or double-click start.cmd.' >&2
    exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w "$script_dir/start.ps1")" -OpenBrowser "$@"
