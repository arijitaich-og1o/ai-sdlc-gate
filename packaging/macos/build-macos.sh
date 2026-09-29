#!/bin/bash
# Build the self-contained macOS installer (.pkg) for AI SDLC Gate.
#   1. freeze the CLI into a single `ai-sdlc-gate` binary (bundled Python) with PyInstaller
#   2. stage the binary + policy (skills, gate.config.yaml) + hooks into a package root
#   3. build a component package (with a postinstall that sets up the logged-in user), then a product .pkg
# Runs on macOS only (Apple pkgbuild/productbuild). Output: dist/ai-sdlc-gate-<version>.pkg
#
#   bash packaging/macos/build-macos.sh 1.0.0
set -euo pipefail
VERSION="${1:-1.0.0}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="$REPO/dist"; mkdir -p "$OUT"

echo "== 1/4 build venv =="
BVENV="$(mktemp -d)/venv"
python3 -m venv "$BVENV"
"$BVENV/bin/pip" install --quiet --upgrade pip wheel
"$BVENV/bin/pip" install --quiet "$REPO/gate" pyinstaller

echo "== 2/4 freeze binary =="
( cd "$HERE" && "$BVENV/bin/pyinstaller" --clean --noconfirm --distpath "$OUT" ai-sdlc-gate-mac.spec )
test -f "$OUT/ai-sdlc-gate" || { echo "PyInstaller did not produce the binary"; exit 1; }

echo "== 3/4 stage package root =="
ROOT="$HERE/pkgroot"; rm -rf "$ROOT"
mkdir -p "$ROOT/usr/local/bin" "$ROOT/usr/local/share/ai-sdlc-gate/repo" "$ROOT/usr/local/share/ai-sdlc-gate/hooks"
cp "$OUT/ai-sdlc-gate" "$ROOT/usr/local/bin/ai-sdlc-gate"; chmod 755 "$ROOT/usr/local/bin/ai-sdlc-gate"
cp -R "$REPO/skills" "$ROOT/usr/local/share/ai-sdlc-gate/repo/skills"
cp "$REPO/gate.config.yaml" "$ROOT/usr/local/share/ai-sdlc-gate/repo/gate.config.yaml"
cp "$REPO/client/hooks/"* "$ROOT/usr/local/share/ai-sdlc-gate/hooks/"
chmod +x "$HERE/scripts/postinstall"

echo "== 4/4 build .pkg =="
COMPONENT="$HERE/ai-sdlc-gate-component.pkg"
pkgbuild --root "$ROOT" --identifier "in.og1o.ai-sdlc-gate" --version "$VERSION" \
         --scripts "$HERE/scripts" --install-location "/" "$COMPONENT"
productbuild --package "$COMPONENT" "$OUT/ai-sdlc-gate-$VERSION.pkg"
rm -f "$COMPONENT"; rm -rf "$ROOT"
echo "Done. Installer: $OUT/ai-sdlc-gate-$VERSION.pkg"
