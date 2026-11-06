#!/bin/bash
# Exercise the actual DMG contents from a copied, space-containing install path.
set -euo pipefail

fail() {
    printf 'DataDesk macOS verification: %s\n' "$1" >&2
    exit 1
}

if [[ $# -eq 0 || "${1:-}" == --help || "${1:-}" == -h ]]; then
    printf 'Usage: bash packaging/macos/verify.sh FILE.dmg [REPORT.json]\n'
    exit 0
fi
[[ $# -le 2 ]] || fail 'Pass a DMG and an optional smoke-test report path.'
[[ "$(uname -s)" == Darwin ]] || fail 'DMG installation verification requires macOS.'
[[ -f "$1" ]] || fail "Disk image not found: $1"
dmg="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
report="${2:-${dmg%.dmg}-smoke.json}"
mkdir -p "$(dirname "$report")"
report="$(cd "$(dirname "$report")" && pwd)/$(basename "$report")"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/datadesk-install-check.XXXXXX")"
mount_point="$work_dir/mounted"
mkdir "$mount_point"
mounted=0
cleanup() {
    if [[ "$mounted" -eq 1 ]]; then
        /usr/bin/hdiutil detach "$mount_point" >/dev/null 2>&1 || \
            /usr/bin/hdiutil detach -force "$mount_point" >/dev/null 2>&1 || true
    fi
    rm -rf "$work_dir"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

/usr/bin/hdiutil verify "$dmg"
/usr/bin/hdiutil attach "$dmg" -readonly -nobrowse -mountpoint "$mount_point" -plist > "$work_dir/mount.plist"
mounted=1
[[ -L "$mount_point/Applications" ]] || fail 'The disk image has no Applications drag target.'
[[ "$(readlink "$mount_point/Applications")" == /Applications ]] || fail 'The Applications target points to an unexpected directory.'
[[ -f "$mount_point/Önce beni oku.txt" ]] || fail 'The disk image is missing its installation instructions.'
installed_app="$work_dir/Installed DataDesk.app"
/usr/bin/ditto "$mount_point/DataDesk.app" "$installed_app"
/usr/bin/codesign --verify --deep --strict "$installed_app"
binary="$installed_app/Contents/MacOS/DataDesk"
[[ -x "$binary" ]] || fail 'The copied application has no executable.'
QT_QPA_PLATFORM=offscreen "$binary" --smoke-test "$report"
[[ -s "$report" ]] || fail 'The copied application did not create a smoke-test report.'
printf 'Verified a copy installed from the disk image. Report: %s\n' "$report"
