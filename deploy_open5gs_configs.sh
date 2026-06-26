#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

# --- Configuration Variables ---
GITHUB_USER="mvromao"
REPO_NAME="thesis"
BRANCH="main"
CONFIG_DIR_IN_REPO="files" # Your target folder in the repo
OPEN5GS_ETC_DIR="/etc/open5gs"

# --- Colors ---
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}[*] Starting Open5GS configuration deployment...${NC}"

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[!] Please run this script as root or with sudo.${NC}"
  exit 1
fi

# Create a temporary directory for git operations
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
cd "$TEMP_DIR"

# --- Sparse Checkout Logic (Credential-Free) ---
echo -e "${BLUE}[*] Performing sparse checkout for: $CONFIG_DIR_IN_REPO...${NC}"

# Using 'git clone --filter=blob:none' with sparse checkout to prevent credential prompts
git clone --depth 1 --branch "$BRANCH" --no-checkout --filter=blob:none "https://github.com/${GITHUB_USER}/${REPO_NAME}.git" .
git config core.sparseCheckout true
echo "$CONFIG_DIR_IN_REPO/*" >> .git/info/sparse-checkout
git checkout "$BRANCH"

# --- Deployment ---
SRC_DIR="$TEMP_DIR/$CONFIG_DIR_IN_REPO"

if [ -d "$OPEN5GS_ETC_DIR" ]; then
    BACKUP_NAME="${OPEN5GS_ETC_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
    echo -e "${BLUE}[*] Backing up existing configs to $BACKUP_NAME...${NC}"
    cp -r "$OPEN5GS_ETC_DIR" "$BACKUP_NAME"
else
    mkdir -p "$OPEN5GS_ETC_DIR"
fi

echo -e "${BLUE}[*] Copying configs to $OPEN5GS_ETC_DIR...${NC}"
cp -r "$SRC_DIR"/* "$OPEN5GS_ETC_DIR/"

echo -e "${BLUE}[*] Setting permissions and restarting Open5GS...${NC}"
chmod 644 "$OPEN5GS_ETC_DIR"/*.yaml
systemctl restart open5gs-*

echo -e "${GREEN}[+] Done! Open5GS is running your updated configs.${NC}"
