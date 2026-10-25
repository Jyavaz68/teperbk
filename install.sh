#!/bin/bash

CYAN='\033[0;96m'
BLUE='\033[0;94m'
GREEN='\033[0;92m'
YELLOW='\033[0;93m'
RED='\033[0;91m'
NC='\033[0m'

URL="https://raw.githubusercontent.com/jyavaz68/teperbk/main/teperbk.py"
FILE="teperbk.py"

echo -e "${BLUE}==================================================${NC}"
echo -e "${CYAN}      Pasarguard Backup/Restore Utility (teperbk)${NC}"
echo -e "${BLUE}==================================================${NC}"

if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}✖ Please run this installer as root.${NC}"
    exit 1
fi

echo -e "${YELLOW}➔ Installing required system packages (python3, paramiko, unzip, curl)...${NC}"
apt-get update >/dev/null 2>&1
apt-get install -y python3 python3-paramiko unzip curl >/dev/null 2>&1

echo -e "${CYAN}➔ Downloading the script to the current directory...${NC}"

if curl -fsSL -o "$FILE" "$URL"; then
    echo -e "${GREEN}✔ Download successful!${NC}"
    echo -e "${CYAN}➔ Starting the utility...${NC}"
    echo ""
    python3 "$FILE"
else
    echo -e "${RED}✖ Download failed. Please check your internet connection or the GitHub repository.${NC}"
    exit 1
fi
