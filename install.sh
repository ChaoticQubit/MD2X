#!/usr/bin/env bash
# install.sh — LOCAL install of every md2x dependency. Nothing global.
#
# After this finishes, the project folder is fully self-contained:
#   .venv/               Python virtualenv (PyYAML for config parsing)
#   node_modules/        local mmdc + bundled Chromium (via puppeteer)
#   .tools/pandoc/       pandoc binary (downloaded release tarball)
#   .tools/tinytex/      TinyTeX (~70 MB) for xelatex
#   .bin/                symlinks: pandoc, xelatex, mmdc, (dot if available)
#
# Activate the environment for ad-hoc use:
#   source .venv/bin/activate
#   export PATH="$PWD/.bin:$PATH"
#
# Or just run ./md2x.py — it auto-detects the local layout.
#
# Requirements on the host: bash, curl, tar, python3 (>= 3.10), uname.
# Internet access to download pandoc + TinyTeX + npm packages.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

OS="$(uname -s)"
ARCH="$(uname -m)"
PANDOC_VERSION="${PANDOC_VERSION:-3.5}"
NODE_VERSION="${NODE_VERSION:-20.18.0}"

TOOLS="$HERE/.tools"
BIN="$HERE/.bin"
VENV="$HERE/.venv"
NODE_DIR="$TOOLS/node"
PANDOC_DIR="$TOOLS/pandoc"
TINYTEX_DIR="$TOOLS/tinytex"

mkdir -p "$TOOLS" "$BIN"

have() { command -v "$1" >/dev/null 2>&1; }

color()  { printf "\033[1;36m%s\033[0m\n" "$*"; }
warn()   { printf "\033[1;33mWARN:\033[0m %s\n" "$*"; }
die()    { printf "\033[1;31mERROR:\033[0m %s\n" "$*"; exit 1; }

# ── platform identifiers used in download URLs ────────────────────────────
case "$OS" in
    Darwin)  PANDOC_OS=macOS ;;
    Linux)   PANDOC_OS=linux ;;
    *)       die "unsupported OS: $OS" ;;
esac
case "$ARCH" in
    x86_64|amd64)   PANDOC_ARCH=x86_64; NODE_ARCH=x64 ;;
    arm64|aarch64)  PANDOC_ARCH=arm64;  NODE_ARCH=arm64 ;;
    *)              die "unsupported arch: $ARCH" ;;
esac

color "==> md2x local installer"
echo "    project root: $HERE"
echo "    OS=$OS arch=$ARCH"
echo "    pandoc=$PANDOC_VERSION node=$NODE_VERSION"
echo

# ──────────────────────────────────────────────────────────────────────────
# 1. Python venv + PyYAML + pytest
# ──────────────────────────────────────────────────────────────────────────
color "==> [1/5] Python venv at .venv"
if [[ ! -d "$VENV" ]]; then
    python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet pyyaml pytest
deactivate
echo "       PyYAML + pytest installed in .venv"

# ──────────────────────────────────────────────────────────────────────────
# 2. Node (local) + mmdc
# ──────────────────────────────────────────────────────────────────────────
color "==> [2/5] Node.js + mmdc (local node_modules)"
if [[ ! -x "$NODE_DIR/bin/node" ]]; then
    case "$OS" in
        Darwin) NODE_TGZ="node-v${NODE_VERSION}-darwin-${NODE_ARCH}.tar.gz" ;;
        Linux)  NODE_TGZ="node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.xz"  ;;
    esac
    URL="https://nodejs.org/dist/v${NODE_VERSION}/${NODE_TGZ}"
    echo "       downloading $URL"
    curl -fL --progress-bar -o "$TOOLS/$NODE_TGZ" "$URL"
    mkdir -p "$NODE_DIR"
    tar -xf "$TOOLS/$NODE_TGZ" -C "$NODE_DIR" --strip-components=1
    rm -f "$TOOLS/$NODE_TGZ"
fi
export PATH="$NODE_DIR/bin:$PATH"
echo "       node=$(node --version)  npm=$(npm --version)"

color "       npm install (mmdc + puppeteer-bundled Chromium)"
npm install --no-audit --no-fund --prefix "$HERE"
ln -sfn "$HERE/node_modules/.bin/mmdc" "$BIN/mmdc"
echo "       mmdc → $(readlink "$BIN/mmdc")"

# ──────────────────────────────────────────────────────────────────────────
# 3. pandoc (local tarball)
# ──────────────────────────────────────────────────────────────────────────
color "==> [3/5] pandoc $PANDOC_VERSION"
if [[ ! -x "$PANDOC_DIR/bin/pandoc" ]]; then
    if [[ "$OS" == "Darwin" ]]; then
        PANDOC_PKG="pandoc-${PANDOC_VERSION}-${PANDOC_ARCH}-macOS.zip"
    else
        PANDOC_PKG="pandoc-${PANDOC_VERSION}-linux-${PANDOC_ARCH}.tar.gz"
    fi
    URL="https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/${PANDOC_PKG}"
    echo "       downloading $URL"
    curl -fL --progress-bar -o "$TOOLS/$PANDOC_PKG" "$URL"
    mkdir -p "$PANDOC_DIR/bin"
    case "$PANDOC_PKG" in
        *.tar.gz) tar -xzf "$TOOLS/$PANDOC_PKG" -C "$PANDOC_DIR" --strip-components=1 ;;
        *.zip)
            unzip -q -o "$TOOLS/$PANDOC_PKG" -d "$TOOLS/pandoc_extract"
            cp -R "$TOOLS/pandoc_extract/pandoc-${PANDOC_VERSION}-${PANDOC_ARCH}/." "$PANDOC_DIR/"
            rm -rf "$TOOLS/pandoc_extract"
            ;;
    esac
    rm -f "$TOOLS/$PANDOC_PKG"
fi
ln -sfn "$PANDOC_DIR/bin/pandoc" "$BIN/pandoc"
echo "       pandoc=$("$BIN/pandoc" --version | head -1)"

# ──────────────────────────────────────────────────────────────────────────
# 4. TinyTeX (local xelatex)
# ──────────────────────────────────────────────────────────────────────────
color "==> [4/5] TinyTeX (local xelatex, ~70 MB)"
# rstudio/tinytex-releases assets carry the version in the filename
# (e.g. TinyTeX-1-darwin-v2026.06.tar.xz), so the "latest" redirect URL
# does NOT resolve unless we look up the tag dynamically.
if ! find "$TINYTEX_DIR/bin" -maxdepth 2 -type f -name xelatex 2>/dev/null | grep -q .; then
    LATEST_TAG="$(curl -fsSL https://api.github.com/repos/rstudio/tinytex-releases/releases/latest \
                  | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)"
    [[ -z "$LATEST_TAG" ]] && die "could not look up latest TinyTeX tag from GitHub API"
    echo "       latest TinyTeX tag: $LATEST_TAG"

    case "$OS-$ARCH" in
        Darwin-*)                   TINYTEX_ASSET="TinyTeX-1-darwin-${LATEST_TAG}.tar.xz" ;;
        Linux-x86_64|Linux-amd64)   TINYTEX_ASSET="TinyTeX-1-linux-x86_64-${LATEST_TAG}.tar.xz" ;;
        Linux-arm64|Linux-aarch64)  TINYTEX_ASSET="TinyTeX-1-linux-arm64-${LATEST_TAG}.tar.xz" ;;
        *)                          die "no TinyTeX asset for $OS-$ARCH" ;;
    esac
    TINYTEX_URL="https://github.com/rstudio/tinytex-releases/releases/download/${LATEST_TAG}/${TINYTEX_ASSET}"
    TINYTEX_TAR="$TOOLS/tinytex.tar.xz"
    echo "       downloading $TINYTEX_URL"
    curl -fL --progress-bar -o "$TINYTEX_TAR" "$TINYTEX_URL"

    rm -rf "$TINYTEX_DIR"
    mkdir -p "$TOOLS"
    # Tarball contains a top-level .TinyTeX/ directory. -xJf works on both
    # BSD tar (macOS) and GNU tar 1.22+.
    tar -xJf "$TINYTEX_TAR" -C "$TOOLS"
    if [[ -d "$TOOLS/.TinyTeX" ]]; then
        mv "$TOOLS/.TinyTeX" "$TINYTEX_DIR"
    elif [[ -d "$TOOLS/TinyTeX" ]]; then
        mv "$TOOLS/TinyTeX" "$TINYTEX_DIR"
    else
        die "TinyTeX tarball had unexpected layout (expected .TinyTeX/ or TinyTeX/)"
    fi
    rm -f "$TINYTEX_TAR"
fi

# Discover the actual platform bin dir (universal-darwin / x86_64-linux / aarch64-linux)
TINYTEX_BIN="$(find "$TINYTEX_DIR/bin" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | head -1)"
if [[ -z "$TINYTEX_BIN" || ! -x "$TINYTEX_BIN/xelatex" ]]; then
    die "TinyTeX install failed: xelatex not present under $TINYTEX_DIR/bin/*/. Rerun after \`rm -rf .tools/tinytex\`"
fi
export PATH="$TINYTEX_BIN:$PATH"

# Install the LaTeX packages pandoc + md2x actually need.
# Pandoc's default PDF template pulls in: setspace, ulem, hyperref, xcolor,
# geometry, fancyvrb, microtype, parskip, bookmark, soul, footmisc, etc.
echo "       tlmgr install xetex + recommended fonts + pandoc preamble pkgs"
"$TINYTEX_BIN/tlmgr" option repository ctan >/dev/null 2>&1 || true
"$TINYTEX_BIN/tlmgr" install \
    xetex collection-fontsrecommended \
    geometry hyperref xcolor adjustbox float microtype booktabs \
    fontspec euenc lm-math \
    setspace ulem parskip bookmark soul footmisc \
    fancyvrb framed listings titling caption \
    upquote epstopdf etoolbox || \
    warn "tlmgr install reported issues — re-run install.sh if xelatex later complains about a package"

ln -sfn "$TINYTEX_BIN/xelatex" "$BIN/xelatex"
# tlmgr is a Perl script that resolves @INC relative to its own path —
# symlinks break it. Use a wrapper that execs the real binary.
cat > "$BIN/tlmgr" <<EOF
#!/usr/bin/env bash
exec "$TINYTEX_BIN/tlmgr" "\$@"
EOF
chmod +x "$BIN/tlmgr"
echo "       xelatex=$("$BIN/xelatex" --version | head -1)"

# ──────────────────────────────────────────────────────────────────────────
# 5. graphviz (system-only fallback; optional)
# ──────────────────────────────────────────────────────────────────────────
color "==> [5/5] graphviz dot (optional fallback, system-detected only)"
if have dot; then
    ln -sfn "$(command -v dot)" "$BIN/dot"
    echo "       dot=$(dot -V 2>&1)"
else
    warn "graphviz 'dot' not on PATH — mmdc handles every Mermaid type, so this is optional."
    warn "If you want it: brew install graphviz   (macOS)   /   sudo apt install graphviz   (Linux)"
fi

# ──────────────────────────────────────────────────────────────────────────
# Verify
# ──────────────────────────────────────────────────────────────────────────
echo
color "==> install complete. local binaries:"
ls -1 "$BIN" | sed 's/^/    /'
echo
echo "Run a smoke test:    ./md2x.py examples/sample.md"
echo "Activate for shell:  source .venv/bin/activate && export PATH=\"\$PWD/.bin:\$PATH\""
