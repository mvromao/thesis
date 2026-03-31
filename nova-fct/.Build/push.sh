#!/bin/sh
# push.sh — performs safe push for main/develop branches

# ANSI colors (same as Makefile variables)
RED="\033[31m"
YELLOW="\033[33m"
CYAN="\033[36m"
RESET="\033[0m"

echo "${RED}-------------------------------------------------------------${RESET}"
echo "🚀 Starting commit-push process..."
echo "${CYAN}VERSION=${YELLOW}${VERSION}${CYAN} - DATE=${YELLOW}${DATE}${RESET}."
echo "${RED}-------------------------------------------------------------${RESET}"

# 1) Check conditions
# -------------------------------------------------------------

# Ensure we’re in a git repo
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Ensure no uncommitted changes
if [ -n "$(git status --porcelain 2>/dev/null | grep -Fv '??')" ]; then
    echo "❌ Error: You have uncommitted changes. Please commit them first."
    git status --short
    exit 1
fi

# Determine current branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
if [ -z "$CURRENT_BRANCH" ]; then
    echo "❌ Error: Not on a valid branch"
    exit 1
fi

# 2) Pull + Push current branch
# -------------------------------------------------------------
PUSH_REMOTE="${PUSH_REMOTE:-origin}"

echo "🔄 Pulling current branch (${CURRENT_BRANCH})..."
if ! git pull "$PUSH_REMOTE" "$CURRENT_BRANCH"; then
    echo "❌ Failed to pull $CURRENT_BRANCH"
    exit 1
fi

# -------------------------------------------------------------

echo "🔄 Pushing current branch (${CURRENT_BRANCH})..."
if ! git push "$PUSH_REMOTE" "$CURRENT_BRANCH"; then
    echo "❌ Failed to push $CURRENT_BRANCH"
    exit 1
fi

# 3) Push the other branch (main or develop)
# -------------------------------------------------------------
if [ "$CURRENT_BRANCH" = "develop" ]; then
    OTHER_BRANCH="main"
elif [ "$CURRENT_BRANCH" = "main" ]; then
    OTHER_BRANCH="develop"
else
    echo "⚠️  Current branch is neither main nor develop. Only pushed $CURRENT_BRANCH"
    OTHER_BRANCH=""
fi

if [ -n "$OTHER_BRANCH" ]; then
    echo "🔄 Pushing $OTHER_BRANCH branch..."
    if git show-ref --verify --quiet "refs/heads/$OTHER_BRANCH"; then
        if ! git push "$PUSH_REMOTE" "$OTHER_BRANCH"; then
            echo "⚠️  Failed to push $OTHER_BRANCH (branch exists but push failed)"
            echo "   You may need to: git pull $PUSH_REMOTE $OTHER_BRANCH"
        fi
    else
        echo "⚠️  Branch $OTHER_BRANCH does not exist locally. Skipping."
    fi
fi

# 4) Summary
# -------------------------------------------------------------
echo "📋 Push Summary:"
echo "   ✅ Pushed: $CURRENT_BRANCH"
if [ -n "$OTHER_BRANCH" ]; then
    if git show-ref --verify --quiet "refs/heads/$OTHER_BRANCH" 2>/dev/null &&
       git push "$PUSH_REMOTE" "$OTHER_BRANCH" --dry-run 2>&1 | grep -q "up to date"; then
        echo "   ✅ Pushed: $OTHER_BRANCH"
    else
        echo "   ⚠️  Status: $OTHER_BRANCH (see above)"
    fi
fi

echo "🎉 Commit push process completed!"
