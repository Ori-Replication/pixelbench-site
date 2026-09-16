#!/usr/bin/env bash
# Publish paper_site/ to GitHub Pages.
#
# The site is a plain static folder, so publishing means: copy it into a repo and
# push.  Two layouts work, and this script handles the first one, which is the one
# that works without a paid GitHub plan:
#
#   A. a separate public repo whose root IS the site
#         -> https://<user>.github.io/<repo>/
#         ./publish_pages.sh git@github.com:Ori-Replication/pixelbench-site.git
#
#   B. a folder inside an existing repo already set up for Pages
#         -> e.g. the pixelbench repo with Pages source = GitHub Actions
#         ./publish_pages.sh git@github.com:Ori-Replication/pixelbench.git --subdir paper_site
#
# The script never touches the repo it copies from: it clones the target into a
# scratch dir, syncs the site into it, and commits only if something changed.
#
# First-time setup for layout A (repo must exist and be public for free accounts):
#   gh repo create Ori-Replication/pixelbench-site --public \
#      --description "PixelBench project page"
# then run this script.
set -euo pipefail

REMOTE="${1:-}"
SUBDIR=""
BRANCH="${PAGES_BRANCH:-main}"

if [[ -z "$REMOTE" ]]; then
  sed -n '2,22p' "$0"
  exit 2
fi

shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --subdir) SUBDIR="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE="$(cd "$HERE/.." && pwd)"          # paper_site/
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

echo "site:   $SITE"
echo "remote: $REMOTE (branch $BRANCH${SUBDIR:+, subdir $SUBDIR})"

git clone --depth 1 --branch "$BRANCH" "$REMOTE" "$SCRATCH/repo" 2>/dev/null \
  || { echo "-> branch '$BRANCH' not found; starting an empty repo"; \
       git init -q "$SCRATCH/repo"; git -C "$SCRATCH/repo" remote add origin "$REMOTE"; }

DEST="$SCRATCH/repo${SUBDIR:+/$SUBDIR}"
mkdir -p "$DEST"

# --delete keeps the published tree an exact mirror of paper_site/
# (exclude .git so a nested repository is never clobbered)
# Mirror paper_site/ into the target, dropping files that no longer exist in the
# source so the published tree never keeps stale frames or images.  Written with
# find/cp rather than rsync, which is not installed everywhere.
if [[ -n "$SUBDIR" ]]; then
  find "$DEST" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
else
  find "$DEST" -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
fi
cp -a "$SITE/." "$DEST/"

# GitHub Pages must serve the files verbatim, not run them through Jekyll
touch "$DEST/.nojekyll"

cd "$SCRATCH/repo"
git add -A
if git diff --cached --quiet; then
  echo "nothing to publish: the remote is already up to date"
  exit 0
fi
git -c user.name="${GIT_AUTHOR_NAME:-pixelbench}" \
    -c user.email="${GIT_AUTHOR_EMAIL:-pixelbench@users.noreply.github.com}" \
    commit -q -m "Publish PixelBench project page ($(date -u +%Y-%m-%dT%H:%MZ), $(find "$DEST" -type f | wc -l) files)"
git push origin "HEAD:$BRANCH"
echo "pushed. Pages URL: https://<owner>.github.io/<repo>/ (enable in Settings -> Pages if this is the first push)"
