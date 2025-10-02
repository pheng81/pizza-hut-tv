#!/bin/bash
# 🧹 Pi Complete Cleanup Script
# Run this directly on the Pi to delete all files

echo "🧹 Pi Complete Cleanup - DELETE ALL FILES"
echo "=========================================="

# Colors for Pi terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🏠 Current location: $(pwd)${NC}"
echo -e "${BLUE}👤 Current user: $(whoami)${NC}"
echo -e "${BLUE}📊 Files before cleanup: $(ls -1 2>/dev/null | wc -l)${NC}"

echo ""
echo -e "${YELLOW}🗑️ DELETING ALL FILES IN HOME DIRECTORY...${NC}"

# Stop all running processes
echo -e "${YELLOW}⏹️ Stopping processes...${NC}"
pkill -f pizza 2>/dev/null || true
pkill -f phtv 2>/dev/null || true  
pkill -f webplayer 2>/dev/null || true
pkill -f vlc 2>/dev/null || true
pkill -f client 2>/dev/null || true
pkill -f tv 2>/dev/null || true
sleep 2

# Delete all Python files
echo -e "${RED}🐍 Deleting Python files...${NC}"
rm -f *.py
rm -f *client*.py
rm -f *pizza*.py
rm -f *phtv*.py
rm -f *tv*.py
rm -f *debug*.py
rm -f *test*.py
rm -f *gui*.py
rm -f *webplayer*.py
rm -f *smooth*.py
rm -f *enhanced*.py
rm -f *working*.py
rm -f *fixed*.py
rm -f *final*.py
rm -f *media*.py
rm -f *direct*.py
rm -f *terminal*.py
rm -f *forced*.py
rm -f *headless*.py
rm -f *launcher*.py
rm -f *daemon*.py
rm -f ea_*.py
rm -f pi_*.py
rm -f quick_*.py
rm -f simple_*.py

# Delete all shell scripts
echo -e "${RED}📜 Deleting shell scripts...${NC}"
rm -f *.sh
rm -f start_*
rm -f launch_*
rm -f pizza_*
rm -f ea_*
rm -f run_*
rm -f install_*

# Delete desktop files
echo -e "${RED}🖥️ Deleting desktop files...${NC}"
rm -f Desktop/*.desktop 2>/dev/null || true
rm -f *.desktop

# Delete config and log files
echo -e "${RED}📝 Deleting configs and logs...${NC}"
rm -f *.log
rm -f *.json
rm -f *.txt
rm -f *.conf
rm -f *.config
rm -f *.cfg

# Delete media files
echo -e "${RED}🎬 Deleting media files...${NC}"
rm -f *.mp4
rm -f *.avi
rm -f *.mkv
rm -f *.m3u
rm -f *.playlist

# Delete archive files
echo -e "${RED}📦 Deleting archives...${NC}"
rm -f *.zip
rm -f *.tar.gz
rm -f *.tar
rm -f *.tgz

# Delete directories
echo -e "${RED}📁 Deleting directories...${NC}"
rm -rf pizza-hut-tv* 2>/dev/null || true
rm -rf phtv* 2>/dev/null || true
rm -rf ea-tv* 2>/dev/null || true
rm -rf temp* 2>/dev/null || true
rm -rf test* 2>/dev/null || true
rm -rf debug* 2>/dev/null || true
rm -rf logs* 2>/dev/null || true
rm -rf backup* 2>/dev/null || true
rm -rf client* 2>/dev/null || true

# Delete hidden files (be careful with system files)
echo -e "${RED}👻 Deleting hidden files...${NC}"
rm -f .*pizza* 2>/dev/null || true
rm -f .*phtv* 2>/dev/null || true
rm -f .*tv* 2>/dev/null || true
rm -f .*client* 2>/dev/null || true

# Delete any remaining files (except essential system files)
echo -e "${RED}🧹 Final cleanup...${NC}"
find . -maxdepth 1 -name "*.py" -delete 2>/dev/null || true
find . -maxdepth 1 -name "*.sh" -delete 2>/dev/null || true
find . -maxdepth 1 -name "*.log" -delete 2>/dev/null || true
find . -maxdepth 1 -name "*.json" -delete 2>/dev/null || true
find . -maxdepth 1 -name "*.txt" -delete 2>/dev/null || true

echo ""
echo -e "${GREEN}✅ CLEANUP COMPLETE!${NC}"
echo -e "${BLUE}📊 Files after cleanup: $(ls -1 2>/dev/null | wc -l)${NC}"

echo ""
echo -e "${GREEN}📋 Remaining files:${NC}"
ls -la 2>/dev/null || echo "Directory is completely clean!"

echo ""
echo -e "${GREEN}🎉 Pi is now completely clean!${NC}"
echo -e "${BLUE}💡 Ready for fresh setup${NC}"