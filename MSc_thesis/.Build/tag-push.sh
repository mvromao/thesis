#!/bin/sh
# tag-push.sh — push tag to remote
TAG_VERSION="${TAG_VERSION:-${VERSION}}"

echo "🚀 Pushing tag v${TAG_VERSION} to remote..."
if [ -z "$TAG_VERSION" ]; then
  echo "❌ Error: TAG_VERSION is required"
  echo "   Usage: make tag-push TAG_VERSION=x.y.z"
  exit 1
fi

if ! git push origin "v${TAG_VERSION}" -f; then
  echo "❌ Failed to push tag v${TAG_VERSION}"
  exit 1
fi

echo "✅ Tag v${TAG_VERSION} pushed to remote"
