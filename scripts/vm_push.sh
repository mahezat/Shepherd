#!/usr/bin/env bash
# Run ON THE EVENT VM after vm_ingest.py. Pushes data/ to GitHub.
# Uses GitHub's device login: it prints a code, you enter it at github.com/login/device.
set -e
cd "$(dirname "$0")/.."
if ! command -v gh >/dev/null 2>&1; then
  echo "Installing the GitHub CLI into ~/bin ..."
  mkdir -p ~/bin && cd /tmp
  curl -sSL -o gh.tgz https://github.com/cli/cli/releases/download/v2.63.2/gh_2.63.2_linux_amd64.tar.gz
  tar xzf gh.tgz && cp gh_2.63.2_linux_amd64/bin/gh ~/bin/gh
  export PATH="$HOME/bin:$PATH"
  cd - >/dev/null
fi
gh auth status >/dev/null 2>&1 || gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
git add data/segments.json data/uploads.json data/raw 2>/dev/null || true
git -c user.name="mahezat" -c user.email="mahezat@users.noreply.github.com" commit -m "Real Cosmos + YOLO output from the event pipeline" || true
git pull --rebase origin main
git push origin HEAD:main
echo "Pushed. Tell Claude."
