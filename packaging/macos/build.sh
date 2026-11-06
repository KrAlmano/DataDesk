#!/bin/bash
# Build a native DataDesk.app and package it in a drag-to-Applications disk image.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
output_dir="$project_root/dist"
skip_build=0
target_arch="$(uname -m)"

usage() {
    cat <<'USAGE'
Usage: bash packaging/macos/build.sh [options]

  --skip-build          Package an existing OUTPUT/DataDesk.app.
  --output-dir DIR      Application output directory (default: project/dist).
  --arch ARCH           Artifact architecture: arm64 or x86_64 (default: native).
  --help                Show this help.

Optional environment:
  MACOS_SIGN_IDENTITY   Developer ID Application identity used by the shared build.
  APPLE_NOTARY_PROFILE Existing notarytool Keychain profile; requires Developer ID.

Output: OUTPUT/installers/DataDesk-VERSION-macos-ARCH.dmg and .sha256.
USAGE
}

fail() {
    printf 'DataDesk macOS: %s\n' "$1" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-build) skip_build=1; shift ;;
        --output-dir)
            [[ $# -ge 2 && -n "$2" ]] || fail '--output-dir needs a directory.'
            output_dir="$2"; shift 2 ;;
        --arch)
            [[ $# -ge 2 && -n "$2" ]] || fail '--arch needs arm64 or x86_64.'
            target_arch="$2"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) fail "Unknown option: $1" ;;
    esac
done

[[ "$(uname -s)" == Darwin ]] || fail 'Build this installer on macOS; use the Windows installer script on Windows.'
case "$target_arch" in arm64|x86_64) ;; *) fail 'Supported architectures are arm64 and x86_64.' ;; esac
if [[ "$skip_build" -eq 0 && "$target_arch" != "$(uname -m)" ]]; then
    fail 'Build each architecture with a matching macOS/Python environment. Cross-compilation is not enabled.'
fi
if [[ -n "${APPLE_NOTARY_PROFILE:-}" && -z "${MACOS_SIGN_IDENTITY:-}" ]]; then
    fail 'APPLE_NOTARY_PROFILE requires MACOS_SIGN_IDENTITY with a Developer ID Application certificate.'
fi

mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
if [[ "$skip_build" -eq 0 ]]; then
    cd "$project_root"
    if command -v uv >/dev/null 2>&1; then
        uv run --extra build python tools/build_app.py --platform macos --output-dir "$output_dir"
    elif [[ -x "$project_root/.venv/bin/python" ]]; then
        "$project_root/.venv/bin/python" tools/build_app.py --platform macos --output-dir "$output_dir"
    else
        fail 'Install uv or prepare the project .venv with the build dependencies first. See docs/MACOS.md.'
    fi
fi

app="$output_dir/DataDesk.app"
plist="$app/Contents/Info.plist"
binary="$app/Contents/MacOS/DataDesk"
[[ -f "$plist" && -x "$binary" ]] || fail "DataDesk.app is incomplete or missing: $app"
bundle_id="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$plist")"
[[ "$bundle_id" == io.github.KrAlmano.DataDesk ]] || fail "Unexpected bundle identifier: $bundle_id"
app_version="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$plist")"
[[ "$app_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail 'The bundle version must have three numeric components.'
binary_arches="$(/usr/bin/lipo -archs "$binary")"
case " $binary_arches " in
    *" $target_arch "*) ;;
    *) fail "The application architecture ($binary_arches) does not contain the requested $target_arch." ;;
esac
/usr/bin/codesign --verify --deep --strict "$app"
signature_details="$(/usr/bin/codesign --display --verbose=2 "$app" 2>&1)"
developer_signed=0
case "$signature_details" in *'Authority=Developer ID Application:'*) developer_signed=1 ;; esac
if [[ -n "${MACOS_SIGN_IDENTITY:-}" && "$developer_signed" -ne 1 ]]; then
    fail 'MACOS_SIGN_IDENTITY was supplied, but DataDesk.app is not Developer ID signed. Rebuild it with the shared builder.'
fi

installers="$output_dir/installers"
mkdir -p "$installers"
artifact_name="DataDesk-$app_version-macos-$target_arch.dmg"
dmg="$installers/$artifact_name"
staging="$(mktemp -d "${TMPDIR:-/tmp}/datadesk-dmg.XXXXXX")"
cleanup() {
    [[ ! -d "$staging" ]] || rm -rf "$staging"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

notarize() {
    local artifact="$1"
    local response="$2"
    /usr/bin/xcrun notarytool submit "$artifact" \
        --keychain-profile "$APPLE_NOTARY_PROFILE" --wait --output-format json > "$response"
    local status
    status="$(/usr/bin/plutil -extract status raw -o - "$response")"
    [[ "$status" == Accepted ]] || fail "Apple notarization was not accepted. Review $response before distribution."
}

if [[ -n "${APPLE_NOTARY_PROFILE:-}" ]]; then
    # Staple the application before packing it, so the copied app also carries
    # its ticket. The final disk image is independently notarized below.
    notarization_zip="$staging/DataDesk-notarization.zip"
    /usr/bin/ditto -c -k --keepParent "$app" "$notarization_zip"
    notarize "$notarization_zip" "$installers/DataDesk-$app_version-$target_arch-app-notary.json"
    /usr/bin/xcrun stapler staple "$app"
    /usr/bin/xcrun stapler validate "$app"
    /usr/sbin/spctl --assess --type execute --verbose=2 "$app"
fi

/usr/bin/ditto "$app" "$staging/DataDesk.app"
ln -s /Applications "$staging/Applications"
cp "$project_root/packaging/macos/INSTALLATION.txt" "$staging/Önce beni oku.txt"
/usr/bin/hdiutil create -volname "DataDesk $app_version" -srcfolder "$staging" \
    -fs HFS+ -format UDZO -ov "$dmg"
if [[ "$developer_signed" -eq 1 && -n "${MACOS_SIGN_IDENTITY:-}" ]]; then
    /usr/bin/codesign --force --sign "$MACOS_SIGN_IDENTITY" --timestamp "$dmg"
fi
if [[ -n "${APPLE_NOTARY_PROFILE:-}" ]]; then
    notarize "$dmg" "$installers/DataDesk-$app_version-$target_arch-dmg-notary.json"
    /usr/bin/xcrun stapler staple "$dmg"
    /usr/bin/xcrun stapler validate "$dmg"
    /usr/sbin/spctl --assess --type open --context context:primary-signature --verbose=2 "$dmg"
fi
/usr/bin/hdiutil verify "$dmg"
(
    cd "$installers"
    /usr/bin/shasum -a 256 "$artifact_name" > "$artifact_name.sha256"
)
if [[ "$developer_signed" -eq 0 ]]; then
    printf 'Created a locally signed development package; Apple notarization was not performed.\n'
elif [[ -z "${APPLE_NOTARY_PROFILE:-}" ]]; then
    printf 'Created a Developer ID signed package; Apple notarization was not performed.\n'
fi
printf 'macOS installer: %s\n' "$dmg"
