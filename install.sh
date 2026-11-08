#!/usr/bin/env bash
# Install the atlaspedia plugin globally for Claude Code (available in every project
# on this machine).
#
# Usage:
#   ./install.sh              # uses this clone if it holds the marketplace, else GitHub
#   ./install.sh owner/repo   # register the marketplace from a GitHub repo instead
#
# This needs NO account, token or registration — it only registers the plugin
# with the local Claude Code CLI. Requires the `claude` CLI on PATH.
set -euo pipefail

REPO_DEFAULT="voxvanhieu/atlaspedia"
MARKETPLACE="voxvanhieu"
PLUGIN="atlaspedia"

if ! command -v claude >/dev/null 2>&1; then
  echo "error: the Claude Code CLI ('claude') was not found on PATH." >&2
  echo "       install it first:  npm install -g @anthropic-ai/claude-code" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SOURCE="${1:-}"
if [[ -z "$SOURCE" ]]; then
  if [[ -f "$SCRIPT_DIR/.claude-plugin/marketplace.json" ]]; then
    SOURCE="$SCRIPT_DIR"   # running from a clone of this repo
  else
    SOURCE="$REPO_DEFAULT" # standalone script: fall back to GitHub
  fi
fi

echo "==> registering marketplace from: $SOURCE"
claude plugin marketplace add "$SOURCE" || echo "    (already registered — continuing)"

echo "==> installing plugin: $PLUGIN@$MARKETPLACE"
claude plugin install "$PLUGIN@$MARKETPLACE" || claude plugin update "$PLUGIN@$MARKETPLACE"

echo
echo "done — atlaspedia is now available in every Claude Code session on this machine."
echo "try it:   claude   then   /atlaspedia:go <topic>"
echo "update:   claude plugin marketplace update $MARKETPLACE   (in a clone, git pull works too)"
echo "          claude plugin update $PLUGIN@$MARKETPLACE"
