#!/usr/bin/env bash
# slurmtop installer.
#
#   curl -fsSL https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/install.sh | bash
#
# Installs to /usr/local/bin when writable (or via sudo), otherwise to
# ~/.local/bin. Pass a directory as $1 to override.
#
# credited by team-03/Hawks
set -euo pipefail

SRC=${SLURMTOP_SRC:-https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/slurmtop}
DEST=${1:-}

pick_dest() {
  if [[ -n $DEST ]]; then echo "$DEST"; return; fi
  if [[ -w /usr/local/bin ]]; then echo /usr/local/bin; return; fi
  if command -v sudo >/dev/null && sudo -n true 2>/dev/null; then echo /usr/local/bin; return; fi
  echo "$HOME/.local/bin"
}

DEST=$(pick_dest)
TARGET="$DEST/slurmtop"
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

echo "→ downloading slurmtop"
curl -fsSL --retry 3 -o "$TMP" "$SRC"
python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$TMP" \
  || { echo "downloaded file is not valid Python - aborting"; exit 1; }
chmod +x "$TMP"

echo "→ installing to $TARGET"
mkdir -p "$DEST" 2>/dev/null || true
if [[ -w $DEST ]]; then
  mv "$TMP" "$TARGET"
else
  sudo mkdir -p "$DEST"
  sudo cp "$TMP" "$TARGET"
  sudo chmod +x "$TARGET"
fi
trap - EXIT

if ! command -v slurmtop >/dev/null; then
  echo
  echo "  $DEST is not on your PATH. Add it with:"
  echo "    echo 'export PATH=\"$DEST:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
fi

echo
"$TARGET" --version
echo "done - run 'slurmtop' to start"
