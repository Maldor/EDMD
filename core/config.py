"""
core/config.py — Configuration loading, defaults, profile resolution,
                 and hot-reload.

Depends only on core.state (for EDMD_DATA_DIR).
Does not import from emit, journal, or gui.
"""

import sys
import tomllib
from pathlib import Path

from core.state import EDMD_DATA_DIR


# ── Minimal terminal colour for pre-emit warnings ────────────────────────────
# emit.py imports config, so we can't import Terminal from there.
# Only _WARNING is needed here; full Terminal lives in core.emit.

class _T:
    WARN = "\x1b[38;5;215m"
    END  = "\x1b[0m"

_WARNING = f"{_T.WARN}Warning:{_T.END}"


# ── Config defaults ───────────────────────────────────────────────────────────

CFG_DEFAULTS_SETTINGS = {
    "JournalFolder":  "",
    "UseUTC":         False,
    "PrimaryInstance": True,   # Set False on remote/secondary instances to suppress data uploads
    "WarnKillRate":   20,
    "WarnNoKills":    20,
    "PirateNames":    False,
    "BountyFaction":  False,
    "BountyValue":    False,
    "ExtendedStats":  False,
    "MinScanLevel":   1,
}

CFG_DEFAULTS_EXTRA = {
    "TruncateNames":      30,
    "WarnNoKillsInitial": 5,
    "WarnCooldown":       15,
    "FullStackSize":      20,
}

CFG_DEFAULTS_GUI = {
    "Enabled": False,
    "Theme":   "default",
}

CFG_DEFAULTS_DISCORD = {
    "WebhookURL":      "",
    "UserID":          0,
    "PrependCmdrName": False,
    "ForumChannel":    False,
    "ThreadCmdrNames": False,
    "Timestamp":       True,
    "Identity":        True,
}

CFG_DEFAULTS_EDDN = {
    "Enabled":    False,
    "UploaderID": "",
    "TestMode":   False,
}

CFG_DEFAULTS_EDSM = {
    "Enabled":       False,
    "CommanderName": "",
    "ApiKey":        "",
}

CFG_DEFAULTS_EDASTRO = {
    "Enabled":             False,
    "UploadCarrierEvents": False,
}

CFG_DEFAULTS_INARA = {
    "Enabled":       False,
    "ApiKey":        "",
    "CommanderName": "",
}

CFG_DEFAULTS_CAPI = {
    "Enabled": False,   # set True automatically after first successful auth
}


CFG_DEFAULTS_NOTIFY = {
    "InboundScan":      1,
    "RewardEvent":      2,
    "FighterDamage":    2,
    "FighterLost":      3,
    "ShieldEvent":      3,
    "HullEvent":        3,
    "Died":             3,
    "CargoLost":        3,
    "LowCargoValue":    2,
    "PoliceScan":       2,
    "PoliceAttack":     3,
    "FuelStatus":       1,
    "FuelWarning":      2,
    "FuelCritical":     3,
    "MissionUpdate":    2,
    "AllMissionsReady": 3,
    "MeritEvent":       0,
    "InactiveAlert":    3,
    "RateAlert":        3,
    "PeriodicKills":    2,
    "PeriodicFaction":  0,
    "PeriodicCredits":  2,
    "PeriodicMerits":   2,
}


# ── Config file resolution ────────────────────────────────────────────────────
# Priority:
#   1. User data dir  (~/.local/share/EDMD/config.toml)
#   2. Repo-adjacent  (same dir as edmd.py)   — dev / legacy fallback
#   3. PyInstaller bundle

def resolve_config_path(script_path: Path) -> Path | None:
    """Return the first existing config.toml candidate, or None."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates = [
            EDMD_DATA_DIR / "config.toml",
            script_path.parents[1] / "config.toml",
        ]
    else:
        candidates = [
            EDMD_DATA_DIR / "config.toml",
            script_path.parent / "config.toml",
        ]
    for p in candidates:
        if p.is_file():
            return p
    return None



# ── Config format migration ───────────────────────────────────────────────────
#
# EDMD originally used [PROFILE.Section] subsection headers for per-profile
# settings.  The current format uses dotted keys under a single [PROFILE] block:
#
#   Old:                         New (identical parsed output):
#   [EDP1.Settings]              [EDP1]
#   JournalFolder = "..."        Settings.JournalFolder = "..."
#
# On first run after upgrade, migrate_config_format() detects old-format headers
# and rewrites the file using a two-pass algorithm that handles any ordering —
# subsections before their parent profile, after it, or interleaved.
# A backup is written to config.toml.bak before any modification.

_GLOBAL_SECTIONS = frozenset({
    "Settings", "Discord", "LogLevels", "GUI",
    "Inara", "EDDN", "EDSM", "EDAstro",
})

_SUBSEC_RE = __import__("re").compile(r"^\[([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\]")
_HEADER_RE = __import__("re").compile(r"^\[([A-Za-z0-9_]+)\]$")


def _needs_migration(text: str) -> bool:
    for line in text.splitlines():
        m = _SUBSEC_RE.match(line.strip())
        if m and m.group(1) not in _GLOBAL_SECTIONS:
            return True
    return False


def _migrate_text(text: str) -> str:
    """Rewrite old [PROFILE.Section] headers to dotted keys under [PROFILE].

    Two-pass algorithm:
      Pass 1 — collect subsection content and record line positions.
      Pass 2 — emit the file, injecting pre-parent subsections at their parent
               header site and suppressing their original content lines.

    Handles all orderings: normal, out-of-order (subsec before parent),
    interleaved (subsecs of different profiles mixed), and orphaned (no parent
    header at all — one is synthesised at the point of emission).
    """
    lines = text.splitlines(keepends=True)

    # ── Pass 1 ────────────────────────────────────────────────────────────────
    subsection_lines: dict = {}   # (profile, section) -> [raw content lines]
    profile_line_idx: dict = {}   # profile_name -> line index of [profile] header
    subsec_line_idx:  dict = {}   # (profile, section) -> line index of header
    current_subsec = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        m = _SUBSEC_RE.match(stripped)
        if m:
            p, s = m.group(1), m.group(2)
            if p not in _GLOBAL_SECTIONS:
                current_subsec = (p, s)
                subsection_lines.setdefault(current_subsec, [])
                subsec_line_idx[current_subsec] = i
                continue
        plain = _HEADER_RE.match(stripped)
        if plain:
            current_subsec = None
            pname = plain.group(1)
            if pname not in _GLOBAL_SECTIONS:
                profile_line_idx[pname] = i
            continue
        if current_subsec is not None:
            subsection_lines[current_subsec].append(line)

    # Subsections whose header appears before their parent profile header (or
    # parent is absent entirely) — these must be injected at the parent, not inline.
    needs_pre: set = {
        (p, s) for (p, s), si in subsec_line_idx.items()
        if profile_line_idx.get(p, 10**9) > si
    }

    # ── Pass 2 ────────────────────────────────────────────────────────────────
    def _emit(p: str, s: str) -> list:
        out = [f"# (migrated from [{p}.{s}])\n"]
        for kl in subsection_lines.get((p, s), []):
            ks = kl.strip()
            out.append(f"{s}.{kl}" if (ks and not ks.startswith("#")) else kl)
        return out

    output: list = []
    current_subsec = None
    emitted: set = set()

    for line in lines:
        stripped = line.strip()

        m = _SUBSEC_RE.match(stripped)
        if m:
            p, s = m.group(1), m.group(2)
            if p not in _GLOBAL_SECTIONS:
                current_subsec = (p, s)
                if (p, s) not in needs_pre and (p, s) not in emitted:
                    # Normal order: emit inline at header position
                    emitted.add((p, s))
                    output.extend(_emit(p, s))
                # Either way, suppress the raw header line
                continue

        plain = _HEADER_RE.match(stripped)
        if plain:
            current_subsec = None
            output.append(line)
            pname = plain.group(1)
            # Inject any pre-parent subsections for this profile
            for (p, s) in sorted(needs_pre):
                if p == pname and (p, s) not in emitted:
                    emitted.add((p, s))
                    output.extend(_emit(p, s))
            continue

        # Skip raw content lines belonging to any already-handled subsection
        if current_subsec is not None and (
            current_subsec in emitted or current_subsec in needs_pre
        ):
            continue

        output.append(line)

    # Orphaned subsections whose parent profile header never appeared — synthesise one
    orphaned = [(p, s) for (p, s) in sorted(needs_pre)
                if (p, s) not in emitted and p not in profile_line_idx]
    if orphaned:
        seen: set = set()
        for (p, s) in orphaned:
            if p not in seen:
                seen.add(p)
                output.append(f"\n[{p}]\n")
            output.extend(_emit(p, s))

    return "".join(output)


def migrate_config_format(config_path: "Path") -> bool:
    """Check config_path for old-format subsection headers and migrate if found.

    Writes a backup to <config_path>.bak before modifying anything.
    Returns True if migration was performed, False if no migration was needed.
    On any error the original file is left untouched and a warning is printed.
    """
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return False

    if not _needs_migration(text):
        return False

    backup = config_path.with_suffix(".toml.bak")
    try:
        backup.write_text(text, encoding="utf-8")
    except OSError as e:
        print(f"Warning: could not write config backup to {backup}: {e}")
        print("  Skipping config migration to avoid data loss.")
        return False

    try:
        migrated = _migrate_text(text)
        import tomllib as _tl
        _tl.loads(migrated)   # verify before writing
    except Exception as e:
        print(f"Warning: config migration produced invalid TOML ({e}); "
              f"original config preserved.")
        return False

    try:
        config_path.write_text(migrated, encoding="utf-8")
    except OSError as e:
        print(f"Warning: could not write migrated config ({e}); "
              f"original config preserved.")
        return False

    print(f"  Config migrated to dotted-key format. Backup saved to {backup.name}")
    return True


def load_config_file(config_path: Path) -> dict:
    """Read and parse a TOML config file.  Calls sys.exit on decode error.

    Runs migrate_config_format() first to silently upgrade old-format
    [PROFILE.Section] headers to the current dotted-key style.
    """
    migrate_config_format(config_path)
    with open(config_path, mode="rb") as f:
        try:
            return tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            print(f"Config decode error: {e}")
            if sys.argv[0].count("\\") > 1:
                input("Press ENTER to exit")
            sys.exit(1)


# ── Setting resolution ────────────────────────────────────────────────────────

def _safe_section(d: dict, key: str) -> dict:
    """Return d[key] if it is a dict, else {}. Prevents crashes when a config
    key exists but holds a scalar value instead of a nested table."""
    v = d.get(key)
    return v if isinstance(v, dict) else {}


def load_setting(
    config: dict,
    config_profile: str | None,
    category: str,
    defaults: dict,
    warn_missing: bool = True,
) -> dict:
    """Resolve a settings block with profile → global → default fallback.

    Resolution order per key:
      1. config[config_profile][category][key]   (if profile active)
      2. config[category][key]
      3. defaults[key]
    """
    settings = {}

    # Pre-extract sections once so the loop is clean and type-safe.
    # _safe_section guards against any level being a non-dict value.
    profile_section: dict = _safe_section(config, config_profile) if config_profile else {}
    profile_cat:     dict = _safe_section(profile_section, category)
    global_cat:      dict = _safe_section(config, category)

    for key in defaults:
        value = None

        if profile_cat.get(key) is not None:
            value = profile_cat[key]
        elif global_cat.get(key) is not None:
            value = global_cat[key]
        else:
            value = defaults[key]
            if warn_missing:
                print(
                    f"{_WARNING} Config '{category}' -> '{key}' not found "
                    f"(using default: {defaults[key]})"
                )

        if type(value) != type(defaults[key]):
            print(
                f"{_WARNING} Config '{category}' -> '{key}' expected type "
                f"{type(defaults[key]).__name__} but got "
                f"{type(value).__name__} "
                f"(using default: {defaults[key]})"
            )
            value = defaults[key]

        settings[key] = value

    return settings


def pcfg(config: dict, config_profile: str | None, key: str, default=False):
    """Read a key from the active profile only, never from global config.

    These keys are profile-gated by design — they are never read from global config.
    """
    if config_profile:
        v = _safe_section(config, config_profile).get(key)
        if v is not None:
            return v
    return default


# ── ConfigManager ─────────────────────────────────────────────────────────────

class ConfigManager:
    """Holds live config state and supports hot-reload.

    Instantiated once in edmd.py after initial load.  Passed into CoreAPI
    so all components access config through a single object.
    """

    def __init__(
        self,
        config: dict,
        config_path: Path,
        config_profile: str | None,
    ):
        self.config         = config
        self.config_path    = config_path
        self.config_profile = config_profile
        self._mtime         = config_path.stat().st_mtime

        # Resolved setting dicts — refreshed on hot-reload
        self.app_settings  = {}
        self.discord_cfg   = {}
        self.notify_levels = {}
        self.gui_cfg       = {}
        self.capi_cfg      = {}
        self._resolve_all(warn=True)

    def _resolve_all(self, warn: bool = False):
        self.app_settings  = self.load_setting("Settings",  CFG_DEFAULTS_SETTINGS, warn)
        self.app_settings.update(
            self.load_setting("Settings", CFG_DEFAULTS_EXTRA, False)
        )
        self.discord_cfg   = self.load_setting("Discord",   CFG_DEFAULTS_DISCORD,  warn)
        self.notify_levels = self.load_setting("LogLevels", CFG_DEFAULTS_NOTIFY,   warn)
        self.gui_cfg       = self.load_setting("GUI",       CFG_DEFAULTS_GUI,      False)
        self.eddn_cfg      = self.load_setting("EDDN",      CFG_DEFAULTS_EDDN,     False)
        self.edsm_cfg      = self.load_setting("EDSM",      CFG_DEFAULTS_EDSM,     False)
        self.edastro_cfg   = self.load_setting("EDAstro",   CFG_DEFAULTS_EDASTRO,  False)
        self.inara_cfg     = self.load_setting("Inara",     CFG_DEFAULTS_INARA,    False)
        self.capi_cfg      = self.load_setting("CAPI",      CFG_DEFAULTS_CAPI,     False)

    def load_setting(
        self,
        category: str,
        defaults: dict,
        warn_missing: bool = True,
    ) -> dict:
        """Convenience wrapper using stored config and profile."""
        return load_setting(
            self.config,
            self.config_profile,
            category,
            defaults,
            warn_missing,
        )

    def pcfg(self, key: str, default=False):
        """Profile-gated key lookup."""
        return pcfg(self.config, self.config_profile, key, default)

    def refresh(self, terminal_print: bool = True) -> bool:
        """Re-read config.toml if modified.  Returns True if reloaded."""
        try:
            new_mtime = self.config_path.stat().st_mtime
        except OSError:
            return False

        if new_mtime <= self._mtime:
            return False

        try:
            self.config = load_config_file(self.config_path)
        except SystemExit:
            return False

        self._mtime = new_mtime
        self._resolve_all(warn=False)

        if terminal_print:
            # Deferred import avoids circular dependency at module load time
            from core.emit import Terminal
            print(f"{Terminal.YELL}Config reloaded.{Terminal.END}")

        return True
