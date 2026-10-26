#!/bin/bash

CYAN='\033[0;96m'
BLUE='\033[0;94m'
GREEN='\033[0;92m'
YELLOW='\033[0;93m'
RED='\033[0;91m'
NC='\033[0m'

URL="https://raw.githubusercontent.com/jyavaz68/teperbk/main/teperbk.py"
INSTALL_DIR="/opt/teperbk"
FILE="$INSTALL_DIR/teperbk.py"
CMD="/usr/local/bin/teperbk"

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

mkdir -p "$INSTALL_DIR"

echo -e "${CYAN}➔ Downloading the script to $INSTALL_DIR ...${NC}"

if curl -fsSL -o "$FILE" "$URL"; then
    chmod +x "$FILE"

    # Short command: runs from /root so backups are saved there
    # (never inside /opt/pasarguard, which is wiped on restore)
    cat > "$CMD" <<'WRAP'
#!/bin/bash
cd /root && exec python3 /opt/teperbk/teperbk.py "$@"
WRAP
    chmod +x "$CMD"

    # If the Telegram bot service is already installed, restart it to load the new version
    if systemctl is-active --quiet teperbk-bot 2>/dev/null; then
        systemctl restart teperbk-bot
        echo -e "${GREEN}✔ Telegram bot service restarted with the new version.${NC}"
    fi

    echo -e "${GREEN}✔ Installed successfully!${NC}"
    echo -e "${CYAN}➔ From now on, just type:  ${GREEN}teperbk${NC}"
    echo -e "${CYAN}➔ Backups are saved in:    ${GREEN}/root${NC}"
    echo ""
    "$CMD"
else
    echo -e "${RED}✖ Download failed. Please check your internet connection or the GitHub repository.${NC}"
    exit 1
fi
