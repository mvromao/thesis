#!/bin/sh
# rebase.sh — rebase main onto develop (fallback to merge -X theirs)

# ANSI colors
RED="$(printf '\033[31m')"
YELLOW="$(printf '\033[33m')"
CYAN="$(printf '\033[36m')"
RESET="$(printf '\033[0m')"

# Default merge message if not provided (mirrors: MERGE_MESSAGE ?= Merged $(VERSION) - $(DATE).)
: "${MERGE_MESSAGE:=Merged ${VERSION} - ${DATE}.}"

printf "%s-------------------------------------------------------------%s\n" "$RED" "$RESET"
printf "🚀 Starting rebase process...\n"
printf "%sVERSION=%s%s%s - DATE=%s%s.%s\n" "$CYAN" "$YELLOW" "${VERSION}" "$CYAN" "$YELLOW" "${DATE}" "$RESET"
printf "%s-------------------------------------------------------------%s\n" "$RED" "$RESET"

# 1) Ensure we are on 'develop'
CURRENT_BRANCH="$(git branch --show-current 2>/dev/null)"
if [ "$CURRENT_BRANCH" != "develop" ]; then
  echo "❌ Error: You must be on the 'develop' branch to run this target"
  exit 1
fi

# 2) Ensure no uncommitted (tracked) changes
if [ -n "$(git status --porcelain 2>/dev/null | grep -Fv '??')" ]; then
  echo "❌ Error: You have uncommitted changes. Please commit or stash them first."
  git status --short
  exit 1
fi

# 3) Checkout main and attempt rebase onto develop; on conflict, abort and merge -X theirs
if ! git checkout main; then
  echo "❌ Failed to checkout main branch"
  exit 1
fi

if ! git rebase develop; then
  echo "⚠️  Rebase encountered conflicts. Resolving automatically using develop version..."
  git rebase --abort 2>/dev/null || true
  if ! git merge develop -X theirs -m "$MERGE_MESSAGE"; then
    echo "❌ Failed to merge with develop version"
    exit 1
  fi
fi

# 4) Switch back to develop
if ! git checkout develop; then
  echo "❌ Failed to checkout develop branch"
  exit 1
fi

printf "🎉 Rebase process completed successfully!\n\n"
