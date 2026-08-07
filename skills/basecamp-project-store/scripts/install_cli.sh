#!/bin/sh
# install_cli.sh — put the official Basecamp command-line tool, and its own manual, on this box.
#
# Downloads the PINNED release for this machine's architecture, verifies it against the
# release's own checksum file, installs a single binary into ~/.local/bin, and then has the
# tool install its version-matched agent manual into ~/.agents/skills/basecamp/SKILL.md.
#
# Idempotent: on a box that already has the pinned version this prints the version and exits 0
# without downloading.
#
#   sh install_cli.sh            # install if absent or at the wrong version
#   sh install_cli.sh --force    # reinstall
#
# WHY A PIN, NOT "latest". The tool's behaviour moves between releases, and it moves silently:
# on 0.7.x `todos list --status completed` returned the OPEN todos, so a digest built on it
# would have reported every unfinished todo as done. references/cli-reference.md records what
# was verified, and it is only true of one version — so the version is chosen here, not by
# whatever happens to be newest on the day a box is built. Bump this pin only after
# check_upstream.py has been run against the new release and the reference page corrected.
#
# Prints BASECAMP_CLI_INSTALLED <version> on success; a single INSTALL_FAILED line otherwise.
set -eu

REPO="basecamp/basecamp-cli"
PINNED="${BASECAMP_CLI_VERSION:-0.9.0}"
BIN_DIR="${BASECAMP_CLI_BIN_DIR:-$HOME/.local/bin}"
BIN="$BIN_DIR/basecamp"
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

fail() { echo "INSTALL_FAILED $1" >&2; exit 1; }

# The tool ships its own agent manual inside the binary and installs it on request, so the
# manual can never drift from the verbs it documents. BASECAMP_SETUP_AGENT=none keeps it to
# just the manual — this is a Hermes box, there is no coding agent here to wire up.
install_manual() {
    BASECAMP_SETUP_AGENT=none "$BIN" setup agents >/dev/null 2>&1 || true
    if [ -f "$HOME/.agents/skills/basecamp/SKILL.md" ]; then
        echo "BASECAMP_MANUAL $HOME/.agents/skills/basecamp/SKILL.md"
    else
        echo "NOTE the tool did not install its own manual; use --help instead"
    fi
}

if [ "$FORCE" -eq 0 ] && [ -x "$BIN" ]; then
    ver=$("$BIN" --version 2>/dev/null | awk '{print $NF}' || echo "")
    if [ "$ver" = "$PINNED" ]; then
        echo "BASECAMP_CLI_INSTALLED $ver (already present)"
        install_manual
        exit 0
    fi
    echo "NOTE replacing basecamp ${ver:-unknown} with the pinned $PINNED"
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

tag="v$PINNED"
asset="basecamp_${PINNED}_${os}_${arch}.tar.gz"
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

ver=$("$BIN" --version 2>/dev/null | awk '{print $NF}' || echo "$PINNED")
echo "BASECAMP_CLI_INSTALLED $ver"
install_manual
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "NOTE $BIN_DIR is not on PATH — call the tool as $BIN" ;;
esac
