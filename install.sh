#!/usr/bin/env bash
# =============================================================================
# EDMD — install.sh
# Linux installer for ED Monitor Daemon
# https://github.com/drworman/EDMD
# =============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_MIN="3.11"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YEL='\033[0;33m'; GRN='\033[0;32m'
CYN='\033[0;36m'; WHT='\033[1;37m'; NC='\033[0m'

info()    { echo -e "${CYN}[EDMD]${NC} $*"; }
ok()      { echo -e "${GRN}[  OK  ]${NC} $*"; }
warn()    { echo -e "${YEL}[ WARN ]${NC} $*"; }
fail()    { echo -e "${RED}[ FAIL ]${NC} $*"; exit 1; }
section() { echo -e "\n${WHT}── $* ──${NC}"; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "${CYN}"
echo "  ███████╗██████╗ ███╗   ███╗ ██████╗ ███╗   ██╗██████╗ "
echo "  ██╔════╝██╔══██╗████╗ ████║██╔═══██╗████╗  ██║██╔══██╗"
echo "  █████╗  ██║  ██║██╔████╔██║██║   ██║██╔██╗ ██║██║  ██║"
echo "  ██╔══╝  ██║  ██║██║╚██╔╝██║██║   ██║██║╚██╗██║██║  ██║"
echo "  ███████╗██████╔╝██║ ╚═╝ ██║╚██████╔╝██║ ╚████║██████╔╝"
echo "  ╚══════╝╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═════╝ "
echo -e "${NC}"
echo -e "${WHT}  ED Monitor Daemon — Linux Installer${NC}"
echo    "  https://github.com/drworman/EDMD"
echo

# ── Detect distro ─────────────────────────────────────────────────────────────
section "Detecting system"

DISTRO="unknown"
PKG_MGR="unknown"

if command -v pacman &>/dev/null; then
    DISTRO="arch"
    PKG_MGR="pacman"
    ok "Arch Linux / pacman"
elif command -v apt-get &>/dev/null; then
    DISTRO="debian"
    PKG_MGR="apt"
    ok "Debian / Ubuntu / apt"
elif command -v dnf &>/dev/null; then
    DISTRO="fedora"
    PKG_MGR="dnf"
    ok "Fedora / RHEL / dnf"
elif command -v zypper &>/dev/null; then
    DISTRO="suse"
    PKG_MGR="zypper"
    ok "openSUSE / zypper"
else
    warn "Unknown distro — will attempt pip install for all packages"
    DISTRO="unknown"
fi

# ── Python check ──────────────────────────────────────────────────────────────
section "Checking Python"

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
            PYTHON="$cmd"
            ok "Found $cmd $VER"
            break
        else
            warn "Found $cmd $VER — too old (need $PYTHON_MIN+)"
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python $PYTHON_MIN+ not found. Install it for your distro then re-run this script."
fi

# ── Install system packages ────────────────────────────────────────────────────
section "Installing system packages"

GUI_AVAILABLE=false

case "$DISTRO" in
    arch)
        info "Installing via pacman..."
        sudo pacman -S --needed --noconfirm python-psutil python-gobject gtk4
        GUI_AVAILABLE=true
        ok "python-psutil, python-gobject, gtk4 installed"
        ;;
    debian)
        info "Installing via apt..."
        sudo apt-get update -qq
        sudo apt-get install -y python3-psutil python3-gi python3-gi-cairo \
            gir1.2-gtk-4.0 libgtk-4-dev
        GUI_AVAILABLE=true
        ok "python3-psutil, python3-gi (GTK4 bindings) installed"
        ;;
    fedora)
        info "Installing via dnf..."
        sudo dnf install -y python3-psutil python3-gobject gtk4
        GUI_AVAILABLE=true
        ok "python3-psutil, python3-gobject, gtk4 installed"
        ;;
    suse)
        info "Installing via zypper..."
        sudo zypper install -y python3-psutil python3-gobject typelib-1_0-Gtk-4_0
        GUI_AVAILABLE=true
        ok "python3-psutil, python3-gobject installed"
        ;;
    *)
        warn "Could not install system packages automatically."
        warn "Install psutil and PyGObject via your package manager, then re-run."
        warn "See INSTALL.md for distro-specific instructions."
        ;;
esac

# ── Install pip packages ───────────────────────────────────────────────────────
section "Installing pip packages"

# These packages are not in most distro repos — install via pip
for PKG in "discord-webhook>=1.3.0" "cryptography>=41.0.0"; do
    PKG_NAME=$(echo "$PKG" | cut -d'>' -f1)
    info "Installing ${PKG_NAME}..."
    if $PYTHON -m pip install "$PKG" --quiet 2>/dev/null; then
        ok "${PKG_NAME} installed"
    elif $PYTHON -m pip install "$PKG" --break-system-packages --quiet 2>/dev/null; then
        ok "${PKG_NAME} installed (--break-system-packages)"
    else
        warn "Could not install ${PKG_NAME} automatically."
        warn "Run manually: pip install ${PKG_NAME} --break-system-packages"
    fi
done

# ── Config setup ──────────────────────────────────────────────────────────────
section "Configuration"

if [ ! -f "$REPO_DIR/config.toml" ]; then
    if [ -f "$REPO_DIR/example.config.toml" ]; then
        cp "$REPO_DIR/example.config.toml" "$REPO_DIR/config.toml"
        ok "Created config.toml from example"
    else
        warn "No config.toml or example.config.toml found."
        warn "You will need to create config.toml before running EDMD."
    fi
else
    ok "config.toml already exists — leaving untouched"
fi

# ── Executable bit ────────────────────────────────────────────────────────────
section "Permissions"

chmod +x "$REPO_DIR/edmd.py"
ok "edmd.py is now executable"

# ── Summary ───────────────────────────────────────────────────────────────────
section "Installation complete"

echo
echo -e "  ${GRN}EDMD is ready to run.${NC}"
echo
echo -e "  ${WHT}Terminal mode:${NC}"
echo -e "    ./edmd.py"
echo

if [ "$GUI_AVAILABLE" = true ]; then
    echo -e "  ${WHT}GUI mode:${NC}"
    echo -e "    ./edmd.py --gui"
    echo
else
    warn "GUI mode unavailable — PyGObject was not installed."
    warn "See INSTALL.md for manual GTK4 setup instructions."
    echo
fi

echo -e "  ${WHT}With a config profile:${NC}"
echo -e "    ./edmd.py -p YourProfileName"
echo
echo -e "  ${CYN}Edit config.toml to set your journal folder path before running.${NC}"
echo -e "  ${CYN}See INSTALL.md and README.md for full documentation.${NC}"
echo
