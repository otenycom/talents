#!/bin/sh
# install_cli.sh — put the official Basecamp command-line tool on this box.
#
# Downloads the published release for this machine's architecture, verifies it against the
# release's own checksum file, and installs a single binary into ~/.local/bin. Idempotent: on
# a box that already has it, this prints the version and exits 0 without downloading.
#
# The tool is a statically linked Go binary with no shared-library dependencies, which is why
# it runs the same on a packed sandbox as on a dedicated machine.
#
#   sh install_cli.sh            # install if absent
#   sh install_cli.sh --force    # reinstall / upgrade to the latest release
#
# Prints BASECAMP_CLI_INSTALLED <version> on success; a single INSTALL_FAILED line otherwise.
set -eu

REPO="basecamp/basecamp-cli"
BIN_DIR="${BASECAMP_CLI_BIN_DIR:-$HOME/.local/bin}"
BIN="$BIN_DIR/basecamp"
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

fail() { echo "INSTALL_FAILED $1" >&2; exit 1; }

if [ "$FORCE" -eq 0 ] && [ -x "$BIN" ]; then
    ver=$("$BIN" --version 2>/dev/null | head -1 || echo "unknown")
    echo "BASECAMP_CLI_INSTALLED $ver (already present)"
    exit 0
fi

case "$(uname -s)" in
    Linux)  os="linux" ;;
    Darwin) os="darwin" ;;
    *) fail "unsupported operating system $(uname -s)" ;;
esac
case "$(uname -m)" in
    x86_64|amd64)  arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
    *) fail "unsupported architecture $(uname -m)" ;;
esac

command -v curl >/dev/null 2>&1 || fail "curl is not available"
command -v tar  >/dev/null 2>&1 || fail "tar is not available"

tmp=$(mktemp -d) || fail "cannot create a temporary directory"
trap 'rm -rf "$tmp"' EXIT INT TERM

# Resolve the latest release tag from the API (no third-party JSON tool on a cold box, so a
# narrow grep on the tag field is deliberate — it is the only "tag_name" key in the payload).
api="https://api.github.com/repos/$REPO/releases/latest"
tag=$(curl -fsSL --max-time 60 "$api" 2>/dev/null \
      | grep -m1 '"tag_name"' | sed 's/.*"tag_name"[^"]*"\([^"]*\)".*/\1/') \
      || fail "cannot reach the release index"
[ -n "${tag:-}" ] || fail "cannot read the latest release tag"
version=${tag#v}

asset="basecamp_${version}_${os}_${arch}.tar.gz"
base="https://github.com/$REPO/releases/download/$tag"

curl -fsSL --max-time 300 -o "$tmp/$asset" "$base/$asset" || fail "cannot download $asset"
curl -fsSL --max-time 60 -o "$tmp/checksums.txt" "$base/checksums.txt" \
    || fail "cannot download the checksum list"

want=$(grep " $asset\$" "$tmp/checksums.txt" | awk '{print $1}')
[ -n "${want:-}" ] || fail "no published checksum for $asset"

if command -v sha256sum >/dev/null 2>&1; then
    got=$(sha256sum "$tmp/$asset" | awk '{print $1}')
elif command -v shasum >/dev/null 2>&1; then
    got=$(shasum -a 256 "$tmp/$asset" | awk '{print $1}')
else
    fail "no sha256 tool available to verify the download"
fi
[ "$got" = "$want" ] || fail "checksum mismatch for $asset"

tar xzf "$tmp/$asset" -C "$tmp" basecamp || fail "the release archive has no basecamp binary"
mkdir -p "$BIN_DIR"
# Install via a temporary name + mv so a concurrent run never sees a half-written binary.
mv "$tmp/basecamp" "$BIN.new"
chmod 0755 "$BIN.new"
mv "$BIN.new" "$BIN"

ver=$("$BIN" --version 2>/dev/null | head -1 || echo "$tag")
echo "BASECAMP_CLI_INSTALLED $ver"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "NOTE $BIN_DIR is not on PATH — call the tool as $BIN" ;;
esac
