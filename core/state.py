"""
core/state.py — Runtime state containers, constants, and session persistence.

No imports from other EDMD core modules — this is the bottom of the
dependency stack.  Everything else imports from here.
"""

import json
import os
import platform as _pl
import time
from datetime import datetime, timezone
from pathlib import Path


# ── Program identity ──────────────────────────────────────────────────────────

PROGRAM = "Elite Dangerous Monitor Daemon"
DESC    = "Continuous monitoring of Elite Dangerous AFK sessions."
AUTHOR  = "CMDR CALURSUS"
VERSION = "20260319b"
GITHUB_REPO = "drworman/EDMD"
DEBUG_MODE  = False


# ── User data directory ───────────────────────────────────────────────────────
# Linux:   ~/.local/share/EDMD/
# Windows: %APPDATA%\EDMD\
# macOS:   ~/Library/Application Support/EDMD/
# A symlink ~/.config/EDMD → ~/.local/share/EDMD is created on Linux.

def _user_data_dir() -> Path:
    system = _pl.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / "EDMD"
    d.mkdir(parents=True, exist_ok=True)
    if system not in ("Windows", "Darwin"):
        config_link = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "EDMD"
        if not config_link.exists() and not config_link.is_symlink():
            try:
                config_link.symlink_to(d)
            except OSError:
                pass
    return d


EDMD_DATA_DIR: Path = _user_data_dir()
STATE_FILE: Path    = EDMD_DATA_DIR / "session_state.json"


# ── Numeric / display constants ───────────────────────────────────────────────

MAX_DUPLICATES       = 5
FUEL_WARN_THRESHOLD  = 0.2   # 20 %
FUEL_CRIT_THRESHOLD  = 0.1   # 10 %
RECENT_KILL_WINDOW   = 10
SESSION_GAP_MINUTES  = 15    # gap between Shutdown→LoadGame that starts a new session
LABEL_UNKNOWN        = "[Unknown]"
PATTERN_JOURNAL      = r"^Journal\.\d{4}-\d{2}-\d{2}T\d{6}\.\d{2}\.log$"
PATTERN_WEBHOOK      = r"^https:\/\/(?:canary\.|ptb\.)?discord(?:app)?\.com\/api\/webhooks\/\d+\/[A-z0-9_-]+$"

PIRATE_NOATTACK_MSGS = [
    "$Pirate_ThreatTooHigh",
    "$Pirate_NotEnoughCargo",
    "$Pirate_OnNoCargoFound",
]

FIGHTER_TYPE_NAMES = {
    "independent_fighter":   "Taipan",      # Faulcon DeLacy — Independent/Alliance
    "empire_fighter":        "GU-97",        # Gutamaya — Imperial
    "federation_fighter":    "F63 Condor",   # Core Dynamics — Federal
    "gdn_hybrid_fighter_v1": "XG7 Trident",  # Guardian hybrid
    "gdn_hybrid_fighter_v2": "XG8 Javelin",  # Guardian hybrid
    "gdn_hybrid_fighter_v3": "XG9 Lance",    # Guardian hybrid
}

FIGHTER_LOADOUT_NAMES = {
    # ── Base / stock (Frontier omits Type when only one type stocked) ─────────
    ("independent_fighter",   "zero"):  "Taipan",
    ("federation_fighter",    "zero"):  "F63 Condor",
    ("empire_fighter",        "zero"):  "GU-97",
    ("gdn_hybrid_fighter_v1", "zero"):  "XG7 Trident",
    ("gdn_hybrid_fighter_v2", "zero"):  "XG8 Javelin",
    ("gdn_hybrid_fighter_v3", "zero"):  "XG9 Lance",

    # ── GU-97  (empire_fighter — Gutamaya, Imperial) ──────────────────────────
    # Loadout order: 1=Gelid F, 2=Rogue F, 3=Aegis F, 4=Gelid G, 5=Rogue G
    # F = Fixed weapons, G = Gimballed weapons
    ("empire_fighter", "one"):       "GU-97 (Gelid F)",     # 2× fixed beam laser
    ("empire_fighter", "two"):       "GU-97 (Rogue F)",     # 2× fixed plasma repeater
    ("empire_fighter", "three"):     "GU-97 (Aegis F)",     # 2× fixed pulse laser
    ("empire_fighter", "four"):      "GU-97 (Gelid G)",     # 2× gimballed beam laser
    ("empire_fighter", "five"):      "GU-97 (Rogue G)",     # 2× gimballed pulse laser
    # Grade variants (engineering tier on top of loadout variant)
    ("empire_fighter", "one_g1"):    "GU-97 (Gelid F G1)",
    ("empire_fighter", "one_g2"):    "GU-97 (Gelid F G2)",
    ("empire_fighter", "one_g3"):    "GU-97 (Gelid F G3)",
    ("empire_fighter", "two_g1"):    "GU-97 (Rogue F G1)",
    ("empire_fighter", "two_g2"):    "GU-97 (Rogue F G2)",
    ("empire_fighter", "two_g3"):    "GU-97 (Rogue F G3)",
    ("empire_fighter", "three_g1"):  "GU-97 (Aegis F G1)",
    ("empire_fighter", "three_g2"):  "GU-97 (Aegis F G2)",
    ("empire_fighter", "three_g3"):  "GU-97 (Aegis F G3)",
    ("empire_fighter", "four_g1"):   "GU-97 (Gelid G G1)",
    ("empire_fighter", "four_g2"):   "GU-97 (Gelid G G2)",
    ("empire_fighter", "four_g3"):   "GU-97 (Gelid G G3)",
    ("empire_fighter", "five_g1"):   "GU-97 (Rogue G G1)",
    ("empire_fighter", "five_g2"):   "GU-97 (Rogue G G2)",
    ("empire_fighter", "five_g3"):   "GU-97 (Rogue G G3)",
    # Slot 6 (rare — 8E bay has 6 slots)
    ("empire_fighter", "six"):       "GU-97 (Aegis F)",
    ("empire_fighter", "six_g1"):    "GU-97 (Aegis F G1)",
    ("empire_fighter", "six_g2"):    "GU-97 (Aegis F G2)",
    ("empire_fighter", "six_g3"):    "GU-97 (Aegis F G3)",

    # ── F63 Condor  (federation_fighter — Core Dynamics, Federal) ────────────
    # Loadout order: 1=Gelid F, 2=Rogue F, 3=Aegis F, 4=Gelid G, 5=Rogue G
    # Note: Rogue F on Condor = 2× fixed multi-cannon (unique kinetic weapon)
    #       Aegis F on Condor = 2× fixed plasma repeater (not pulse like GU-97)
    ("federation_fighter", "one"):      "F63 Condor (Gelid F)",    # 2× fixed pulse laser
    ("federation_fighter", "two"):      "F63 Condor (Rogue F)",    # 2× fixed multi-cannon
    ("federation_fighter", "three"):    "F63 Condor (Aegis F)",    # 2× fixed plasma repeater
    ("federation_fighter", "four"):     "F63 Condor (Gelid G)",    # 2× gimballed beam laser
    ("federation_fighter", "five"):     "F63 Condor (Rogue G)",    # 2× gimballed pulse laser
    ("federation_fighter", "df"):       "F63 Condor (Rogue F)",    # legacy key — double-fixed MC
    ("federation_fighter", "at"):       "F63 Condor (Aegis F)",    # legacy key
    ("federation_fighter", "one_g1"):   "F63 Condor (Gelid F G1)",
    ("federation_fighter", "one_g2"):   "F63 Condor (Gelid F G2)",
    ("federation_fighter", "one_g3"):   "F63 Condor (Gelid F G3)",
    ("federation_fighter", "two_g1"):   "F63 Condor (Rogue F G1)",
    ("federation_fighter", "two_g2"):   "F63 Condor (Rogue F G2)",
    ("federation_fighter", "two_g3"):   "F63 Condor (Rogue F G3)",
    ("federation_fighter", "three_g1"): "F63 Condor (Aegis F G1)",
    ("federation_fighter", "three_g2"): "F63 Condor (Aegis F G2)",
    ("federation_fighter", "three_g3"): "F63 Condor (Aegis F G3)",
    ("federation_fighter", "four_g1"):  "F63 Condor (Gelid G G1)",
    ("federation_fighter", "four_g2"):  "F63 Condor (Gelid G G2)",
    ("federation_fighter", "four_g3"):  "F63 Condor (Gelid G G3)",
    ("federation_fighter", "five_g1"):  "F63 Condor (Rogue G G1)",
    ("federation_fighter", "five_g2"):  "F63 Condor (Rogue G G2)",
    ("federation_fighter", "five_g3"):  "F63 Condor (Rogue G G3)",
    ("federation_fighter", "six"):      "F63 Condor (Aegis F)",
    ("federation_fighter", "six_g1"):   "F63 Condor (Aegis F G1)",
    ("federation_fighter", "six_g2"):   "F63 Condor (Aegis F G2)",
    ("federation_fighter", "six_g3"):   "F63 Condor (Aegis F G3)",

    # ── Taipan  (independent_fighter — Faulcon DeLacy, Independent/Alliance) ─
    # Loadout order: 1=Gelid F, 2=Rogue F, 3=Aegis F, 4=Gelid G, 5=Rogue G, at=AX1 F
    # Note: AX1 F is anti-xeno only; ineffective against human ships
    ("independent_fighter", "one"):      "Taipan (Gelid F)",    # 2× fixed beam laser
    ("independent_fighter", "two"):      "Taipan (Rogue F)",    # 2× fixed plasma repeater
    ("independent_fighter", "three"):    "Taipan (Aegis F)",    # 2× fixed pulse laser
    ("independent_fighter", "four"):     "Taipan (Gelid G)",    # 2× gimballed beam laser
    ("independent_fighter", "five"):     "Taipan (Rogue G)",    # 2× gimballed pulse laser
    ("independent_fighter", "at"):       "Taipan (AX1 F)",      # 2× fixed AX multi-cannon
    ("independent_fighter", "df"):       "Taipan (Rogue F)",    # legacy key
    ("independent_fighter", "one_g1"):   "Taipan (Gelid F G1)",
    ("independent_fighter", "one_g2"):   "Taipan (Gelid F G2)",
    ("independent_fighter", "one_g3"):   "Taipan (Gelid F G3)",
    ("independent_fighter", "two_g1"):   "Taipan (Rogue F G1)",
    ("independent_fighter", "two_g2"):   "Taipan (Rogue F G2)",
    ("independent_fighter", "two_g3"):   "Taipan (Rogue F G3)",
    ("independent_fighter", "three_g1"): "Taipan (Aegis F G1)",
    ("independent_fighter", "three_g2"): "Taipan (Aegis F G2)",
    ("independent_fighter", "three_g3"): "Taipan (Aegis F G3)",
    ("independent_fighter", "four_g1"):  "Taipan (Gelid G G1)",
    ("independent_fighter", "four_g2"):  "Taipan (Gelid G G2)",
    ("independent_fighter", "four_g3"):  "Taipan (Gelid G G3)",
    ("independent_fighter", "five_g1"):  "Taipan (Rogue G G1)",
    ("independent_fighter", "five_g2"):  "Taipan (Rogue G G2)",
    ("independent_fighter", "five_g3"):  "Taipan (Rogue G G3)",
    ("independent_fighter", "six"):      "Taipan (Aegis F)",
    ("independent_fighter", "six_g1"):   "Taipan (Aegis F G1)",
    ("independent_fighter", "six_g2"):   "Taipan (Aegis F G2)",
    ("independent_fighter", "six_g3"):   "Taipan (Aegis F G3)",

    # ── Guardian hybrid SLFs (single loadout each, no variants) ───────────────
    ("gdn_hybrid_fighter_v1", "one"):    "XG7 Trident",
    ("gdn_hybrid_fighter_v2", "one"):    "XG8 Javelin",
    ("gdn_hybrid_fighter_v3", "one"):    "XG9 Lance",
}

# ── Ship name normalisation ───────────────────────────────────────────────────
#
# The game's journal is inconsistent: some ships arrive with correct casing via
# the _Localised field, others arrive lowercase (e.g. "adder", "eagle") or as
# raw internal identifiers (e.g. "CobraMkIII", "Type_9_Military").
#
# normalise_ship_name() is the single point of truth for ship display names.
# Keys are ALWAYS lowercased; values are the canonical display strings drawn
# from Inara (https://inara.cz/elite/ships/) as of March 2026.
#
# Rules:
#   • "Mk II / III / IV / V" — no period after Mk, Roman numerals uppercase
#   • For ships with no rank prefix in the display name (Corsair, Dolphin…)
#     keep it short.  "Imperial" in the display name only for ships that
#     require Imperial rank (Cutter, Clipper, Courier, Eagle).
#   • Every plausible journal emission variant gets its own key so we never
#     fall back to .title() for a known ship.
_SHIP_NAMES: dict[str, str] = {
    # ── Faulcon DeLacy ────────────────────────────────────────────────────────
    "sidewinder":               "Sidewinder Mk I",
    "sidewindermki":            "Sidewinder Mk I",
    "sidewinder mk i":          "Sidewinder Mk I",
    "sidewindermkii":           "Sidewinder Mk II",
    "sidewinder mk ii":         "Sidewinder Mk II",
    "eagle":                    "Eagle Mk II",
    "eaglemkii":                "Eagle Mk II",
    "eagle mk ii":              "Eagle Mk II",
    "cobramkiii":               "Cobra Mk III",
    "cobra mkiii":              "Cobra Mk III",
    "cobra mk iii":             "Cobra Mk III",
    "cobra mk. iii":            "Cobra Mk III",
    "cobramkiv":                "Cobra Mk IV",
    "cobra mkiv":               "Cobra Mk IV",
    "cobra mk iv":              "Cobra Mk IV",
    "cobra mk. iv":             "Cobra Mk IV",
    "cobramkv":                 "Cobra Mk V",
    "cobra mkv":                "Cobra Mk V",
    "cobra mk v":               "Cobra Mk V",
    "cobra mk. v":              "Cobra Mk V",
    "python":                   "Python",
    "pythonmkii":               "Python Mk II",
    "python mkii":              "Python Mk II",
    "python mk ii":             "Python Mk II",
    "python mk. ii":            "Python Mk II",
    "python_nx":                "Python Mk II",    # confirmed journal internal
    "anaconda":                 "Anaconda",
    "mamba":                    "Mamba",
    "combat_multirole":         "Mamba",
    # ── Lakon Spaceways ───────────────────────────────────────────────────────
    "adder":                    "Adder",
    "asp":                      "Asp Explorer",
    "asp explorer":             "Asp Explorer",
    "aspscout":                 "Asp Scout",
    "asp_sa":                   "Asp Scout",
    "asp scout":                "Asp Scout",
    "hauler":                   "Hauler",
    "diamondbackscout":         "Diamondback Scout",
    "diamondback scout":        "Diamondback Scout",
    "diamondbackxl":            "Diamondback Explorer",
    "diamondback explorer":     "Diamondback Explorer",
    "type6":                    "Type-6 Transporter",
    "type6transporter":         "Type-6 Transporter",
    "type-6 transporter":       "Type-6 Transporter",
    "type7":                    "Type-7 Transporter",
    "type7transporter":         "Type-7 Transporter",
    "type-7 transporter":       "Type-7 Transporter",
    "type8":                    "Type-8 Transporter",   # confirmed from journal
    "type8transporter":         "Type-8 Transporter",
    "type-8 transporter":       "Type-8 Transporter",
    "type9":                    "Type-9 Heavy",
    "type9heavy":               "Type-9 Heavy",
    "type-9 heavy":             "Type-9 Heavy",
    "type10":                   "Type-10 Defender",
    "type10defender":           "Type-10 Defender",
    "type-10 defender":         "Type-10 Defender",
    "type9_military":           "Type-10 Defender",    # confirmed from Shipyard.json
    "type_9_military":          "Type-10 Defender",    # defensive variant
    "lakonminer":               "Type-11 Prospector",  # confirmed from Shipyard.json
    "type11":                   "Type-11 Prospector",  # defensive alias
    "type11prospector":         "Type-11 Prospector",
    "type-11 prospector":       "Type-11 Prospector",
    "krait_mkii":               "Krait Mk II",
    "kraitmkii":                "Krait Mk II",
    "krait mkii":               "Krait Mk II",
    "krait mk ii":              "Krait Mk II",
    "krait mk. ii":             "Krait Mk II",
    "krait_light":              "Krait Phantom",
    "krait light":              "Krait Phantom",
    "krait phantom":            "Krait Phantom",
    "mandalay":                 "Mandalay",
    "manowarinterdictor":       "Mandalay",            # legacy internal name
    # ── Saud Kruger ───────────────────────────────────────────────────────────
    "belugaliner":              "Beluga Liner",
    "beluga liner":             "Beluga Liner",
    "beluga":                   "Beluga Liner",
    "dolphin":                  "Dolphin",
    "orca":                     "Orca",
    # ── Core Dynamics ─────────────────────────────────────────────────────────
    "viper":                    "Viper Mk III",
    "vipermkiii":               "Viper Mk III",
    "viper mk iii":             "Viper Mk III",
    "viper mk. iii":            "Viper Mk III",
    "vipermkiv":                "Viper Mk IV",
    "viper mk iv":              "Viper Mk IV",
    "viper mk. iv":             "Viper Mk IV",
    "vulture":                  "Vulture",
    "federation_dropship":      "Federal Dropship",
    "federaldropship":          "Federal Dropship",
    "federal dropship":         "Federal Dropship",
    "federation_dropship_mkii": "Federal Assault Ship",
    "federalassaultship":       "Federal Assault Ship",
    "federal assault ship":     "Federal Assault Ship",
    "federation_gunship":       "Federal Gunship",
    "federalgunship":           "Federal Gunship",
    "federal gunship":          "Federal Gunship",
    "federation_corvette":      "Federal Corvette",
    "federalcorvette":          "Federal Corvette",
    "federal corvette":         "Federal Corvette",
    # ── Kestrel Mk II (Core Dynamics, 2026) ──────────────────────────────────
    "smallcombat01_nx":         "Kestrel Mk II",    # confirmed from Shipyard.json
    "kestrel":                  "Kestrel Mk II",    # defensive alias
    "kestrel_mkii":             "Kestrel Mk II",
    "kestrelmkii":              "Kestrel Mk II",
    "kestrel mkii":             "Kestrel Mk II",
    "kestrel mk ii":            "Kestrel Mk II",
    "kestrel mk. ii":           "Kestrel Mk II",
    # ── Gutamaya ─────────────────────────────────────────────────────────────
    "empire_eagle":             "Imperial Eagle",
    "imperialeagle":            "Imperial Eagle",
    "imperial eagle":           "Imperial Eagle",
    "empire_courier":           "Imperial Courier",
    "imperialcourier":          "Imperial Courier",
    "imperial courier":         "Imperial Courier",
    "empire_trader":            "Imperial Clipper",
    "imperialclipper":          "Imperial Clipper",
    "imperial clipper":         "Imperial Clipper",
    "empire_fighter":           "Imperial Fighter",
    "imperial_fighter":         "Imperial Fighter",
    "imperial fighter":         "Imperial Fighter",
    "cutter":                   "Imperial Cutter",
    "imperialcutter":           "Imperial Cutter",
    "imperial cutter":          "Imperial Cutter",
    # ── Corsair (Gutamaya, 2025) — NOT "Imperial Corsair" ────────────────────
    "empire_corsair":           "Corsair",
    "imperialcorsair":          "Corsair",     # defensive alias
    "imperial corsair":         "Corsair",     # defensive alias
    "corsair":                  "Corsair",
    # ── Alliance / Crusader ───────────────────────────────────────────────────
    "typex":                    "Alliance Chieftain",
    "alliancechieftain":        "Alliance Chieftain",
    "alliance chieftain":       "Alliance Chieftain",
    "typex_2":                  "Alliance Crusader",
    "alliancecrusader":         "Alliance Crusader",
    "alliance crusader":        "Alliance Crusader",
    "typex_3":                  "Alliance Challenger",
    "alliancechallenger":       "Alliance Challenger",
    "alliance challenger":      "Alliance Challenger",
    # ── Zorgon Peterson ───────────────────────────────────────────────────────
    "ferdelance":               "Fer-de-Lance",
    "fer-de-lance":             "Fer-de-Lance",
    "fer de lance":             "Fer-de-Lance",
    "keelback":                 "Keelback",
    "independant_trader":       "Keelback",    # legacy internal name
    # ── Panther Clipper Mk II (Zorgon Peterson, 2025) ─────────────────────────
    "panthermkii":              "Panther Clipper Mk II",   # confirmed from Shipyard.json
    "pantherclippermkii":       "Panther Clipper Mk II",
    "panther_clipper_mkii":     "Panther Clipper Mk II",
    "panther clipper mk ii":    "Panther Clipper Mk II",
    "panther clipper mkii":     "Panther Clipper Mk II",
    "panther clipper mk. ii":   "Panther Clipper Mk II",
    # ── Caspian Explorer (Lakon, 2025) ────────────────────────────────────────
    "caspian":                  "Caspian Explorer",
    "caspianexplorer":          "Caspian Explorer",
    "caspian explorer":         "Caspian Explorer",
    # ── SRV / fighters / misc ─────────────────────────────────────────────────
    "independent_fighter":      "F63 Condor",
    "federation_fighter":       "F/A-26 Strike",
    "gdn_hybrid_fighter_v1":    "Trident",
    "gdn_hybrid_fighter_v2":    "Javelin",
    "gdn_hybrid_fighter_v3":    "Lancer",
    "testbuggy":                "SRV",
    "scarab":                   "SRV",
}

import re as _re
# Matches Roman numeral tokens after "Mk " that were mangled by .title()
# e.g. "Iv" → "IV", "Iii" → "III", "Xlii" → "XLII"
_MK_ROMAN_RE = _re.compile(
    r'\bMk\s+([IVXivx][IVXivx]*)\b'
)


def normalise_ship_name(raw: str | None) -> str | None:
    """Return the correctly-capitalised display name for a ship type string.

    Accepts both internal journal identifiers (e.g. ``"type8"``, ``"krait_mkii"``)
    and pre-localised strings the game sometimes sends (e.g. ``"Cobra Mk IV"``).

    Falls back to a title-cased string for completely unknown ships, with
    Roman numerals after "Mk" kept properly uppercase.

    Returns ``None`` if *raw* is ``None`` or empty.
    """
    if not raw:
        return None
    key = raw.strip().lower()
    if key in _SHIP_NAMES:
        return _SHIP_NAMES[key]
    # Not in map — clean up and title-case, then fix Roman numerals after "Mk"
    candidate = raw.replace("_", " ").strip().title()
    candidate = _MK_ROMAN_RE.sub(lambda m: "Mk " + m.group(1).upper(), candidate)
    return candidate





def resolve_fighter_name(fighter_type: str, loadout: str) -> str:
    """Return display name for a fighter given type + loadout key.

    Handles engineered grade variants (e.g. "df_g1") gracefully.
    Falls back to stripping grade suffix, then type name, then raw string.
    """
    import re as _re
    ft = (fighter_type or "").lower().strip()
    lo = (loadout or "").lower().strip()
    key = (ft, lo)
    if key in FIGHTER_LOADOUT_NAMES:
        return FIGHTER_LOADOUT_NAMES[key]
    # Try stripping grade suffix: "df_g1" -> ("df", "G1")
    m = _re.match(r"^(.+)_(g\d+)$", lo, _re.IGNORECASE)
    if m:
        base_lo = m.group(1)
        grade   = m.group(2).upper()
        base_key = (ft, base_lo)
        if base_key in FIGHTER_LOADOUT_NAMES:
            return f"{FIGHTER_LOADOUT_NAMES[base_key]} {grade}"
    if ft in FIGHTER_TYPE_NAMES:
        return FIGHTER_TYPE_NAMES[ft]
    return ft.replace("_", " ").title() if ft else "SLF"

RANK_NAMES = [
    "Harmless", "Mostly Harmless", "Novice", "Competent", "Expert",
    "Master", "Dangerous", "Deadly", "Elite",
    "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V",
]

RANK_NAMES_TRADE = [
    "Penniless", "Mostly Penniless", "Peddler", "Dealer", "Merchant",
    "Broker", "Entrepreneur", "Tycoon", "Elite",
    "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V",
]

RANK_NAMES_EXPLORE = [
    "Aimless", "Mostly Aimless", "Scout", "Surveyor", "Trailblazer",
    "Pathfinder", "Ranger", "Pioneer", "Elite",
    "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V",
]

RANK_NAMES_CQC = [
    "Helpless", "Mostly Helpless", "Amateur", "Semi-Professional",
    "Professional", "Champion", "Hero", "Legend", "Elite",
    "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V",
]

RANK_NAMES_SOLDIER = [   # Mercenary
    "Defenceless", "Mostly Defenceless", "Rookie", "Soldier",
    "Gunslinger", "Warrior", "Gladiator", "Deadeye", "Elite",
    "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V",
]

RANK_NAMES_EXOBIO = [
    "Directionless", "Mostly Directionless", "Compiler", "Collector",
    "Cataloguer", "Taxonomist", "Ecologist", "Geneticist", "Elite",
    "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V",
]

RANK_NAMES_FEDERATION = [
    "None",
    "Recruit", "Cadet", "Midshipman", "Petty Officer", "Chief Petty Officer",
    "Warrant Officer", "Ensign", "Lieutenant", "Lieutenant Commander",
    "Post Commander", "Post Captain", "Rear Admiral", "Vice Admiral", "Admiral",
]

RANK_NAMES_EMPIRE = [
    "None",
    "Outsider", "Serf", "Master", "Squire", "Knight",
    "Lord", "Baron", "Viscount", "Count", "Earl",
    "Marquis", "Duke", "Prince", "King",
]

# (CAPI key — lowercase as returned by /profile, display label, rank name table)
CAPI_RANK_SKILLS = [
    ("combat",       "Combat",       RANK_NAMES),
    ("explore",      "Explorer",     RANK_NAMES_EXPLORE),
    ("trade",        "Trade",        RANK_NAMES_TRADE),
    ("cqc",          "CQC",          RANK_NAMES_CQC),
    ("soldier",      "Mercenary",    RANK_NAMES_SOLDIER),
    ("exobiologist", "Exobiologist", RANK_NAMES_EXOBIO),
    ("federation",   "Federation",   RANK_NAMES_FEDERATION),
    ("empire",       "Empire",       RANK_NAMES_EMPIRE),
]


# ── Session data (per-session counters, reset on sessionstart) ────────────────

class SessionData:
    def __init__(self):
        self.reset()

    def reset(self):
        self.recent_inbound_scans  = []
        self.recent_outbound_scans = []
        self.last_kill_time        = 0
        self.last_kill_mono        = 0
        self.kill_interval_total   = 0
        self.recent_kill_times     = []
        self.inbound_scan_count    = 0
        self.kills                 = 0
        self.credit_total          = 0
        self.faction_tally         = {}
        self.merits                = 0
        self.last_security_ship    = ""
        self.low_cargo_count       = 0
        self.fuel_check_time       = 0
        self.fuel_check_level      = 0
        self.pending_merit_events  = 0


# ── Monitor state (persistent across the session, reflects game state) ────────

class MonitorState:
    def __init__(self):
        self.session_start_time      = None
        self.alerted_no_kills        = None
        self.alerted_kill_rate       = None
        self.fuel_tank_size          = 64
        self.fuel_current:   "float | None" = None   # FuelMain tons, updated by ReservoirReplenished
        self.fuel_burn_rate: "float | None" = None   # tons/hr rolling estimate; None until 2+ samples
        self.reward_type             = "credit_total"
        self.fighter_integrity       = 0
        self.logged                  = 0
        self.lines                   = 0
        self.missions                = False
        self.active_missions         = []
        self.missions_complete       = 0
        self.prev_event              = None
        self.event_time              = None
        self.last_dup_key            = ""
        self.dup_count               = 1
        self.dup_suppressed          = False
        self.in_preload              = True
        self.pilot_name              = None
        self.pilot_squadron_name     = ""
        self.cargo_target_market     = {}
        self.cargo_target_market_name= ""
        self.cargo_target_market_ts  = 0.0
        self.slf_capi_type           = None  # type from CAPI launchBays
        self.pilot_squadron_tag      = ""
        self.pilot_squadron_rank     = ""
        self.pilot_ship              = None
        self.pilot_rank              = None
        self.pilot_rank_progress     = None
        self.pilot_mode              = None
        self.pilot_location          = None   # compat alias; prefer pilot_system/pilot_body
        self.pilot_system            = None
        self.pilot_body              = None
        self.last_rate_check         = None
        self.last_periodic_summary   = None
        self.last_inactive_alert     = None
        self.last_rate_alert         = None
        self.last_offline_alert      = None
        self.offline_since_mono      = None
        self.in_game                 = False
        self.in_supercruise          = False  # True while in supercruise
        self.last_sc_exit_mono       = None   # monotonic time of last SC exit
        self.last_shutdown_time      = None   # datetime of last Shutdown event
        self.mission_value_map       = {}
        self.stack_value             = 0
        self.has_fighter_bay         = False
        self.mission_target_faction_map = {}

        # SLF state
        self.slf_deployed  = False
        self.slf_docked    = True
        self.slf_hull      = 100
        self.slf_orders    = None
        self.slf_loadout   = None

        # Powerplay state
        self.pp_power        = None
        self.pp_rank         = None
        self.pp_merits_total = None

        # Ship identity (from Loadout)
        self.ship_name  = None
        self.ship_ident = None

        # Ship hull and shields
        self.ship_hull              = 100
        self.ship_shields           = True
        self.ship_shields_recharging = False

        # Commander in SLF
        self.cmdr_in_slf = False

        # NPC Crew state
        self.crew_name         = None
        self.crew_rank         = None
        self.crew_hire_time    = None
        self.crew_total_paid   = None
        self.crew_paid_complete = False
        self.crew_active       = False

        # SLF type and stock
        self.slf_type            = None
        self.slf_stock_total     = 0
        self.slf_destroyed_count = 0

        # CAPI raw store and poll timestamps (managed by DataProvider)
        self.capi_raw:        dict = {}
        self.capi_last_poll:  dict = {}

        # CAPI-derived fields
        self.capi_ranks:           dict | None = None
        self.capi_progress:        dict | None = None
        self.capi_reputation:      dict | None = None
        self.capi_engineer_ranks:  list | None = None
        self.capi_statistics:      dict | None = None
        self.capi_permits:         list | None = None
        self.capi_ship_health:     dict | None = None
        self.capi_ship_value:      dict | None = None
        self.capi_loadout:         dict | None = None
        self.capi_market:          dict | None = None
        self.capi_shipyard:        dict | None = None
        self.capi_community_goals: list | None = None
        self.capi_debt:            float| None = None

        # Assets (fleet, wallet)
        self.assets_balance:       float| None = None
        self.assets_total_wealth:  float| None = None
        self.assets_current_ship:  dict | None = None
        self.assets_stored_ships:  list        = []
        self.assets_stored_modules:list        = []
        self.assets_carrier:       dict | None = None
        self.assets_fc_materials:  list        = []

        # Cargo
        self.cargo_capacity:       int         = 0
        self.cargo_items:          list        = []
        self.cargo_market_info:    dict        = {}
        self.cargo_mean_prices:    dict        = {}

        # Engineering materials
        self.materials_raw:          dict = {}
        self.materials_manufactured: dict = {}
        self.materials_encoded:      dict = {}
        self.engineering_locker:     dict = {}
        self.engineering_backpack:   dict = {}

        # Navigation
        self.nav_route:              list = []

        # Pilot extended
        self.pilot_minor_reputation: dict | None = None
        self.pilot_reputation:       dict | None = None
        self.pilot_engineer_ranks:   list | None = None

    def sessionstart(self, active_session: SessionData, reset: bool = False):
        if not self.session_start_time or reset:
            self.session_start_time = self.event_time
            active_session.reset()
            self.alerted_no_kills      = None
            self.alerted_kill_rate     = None
            self.last_rate_check       = time.monotonic()
            self.last_periodic_summary = time.monotonic()
            self.last_inactive_alert   = None
            self.last_rate_alert       = None
            global _session_start_iso
            _session_start_iso = (
                self.session_start_time.isoformat()
                if self.session_start_time else None
            )

    def sessionend(self):
        if self.session_start_time:
            self.session_start_time = None

    def reset_missions(self):
        """Clear mission state so a new game session bootstraps cleanly.

        Called on LoadGame.  Without this, missions flag and maps carried over
        from a prior session prevent the Missions bulk event and
        bootstrap_missions() from running.
        """
        self.missions                   = False
        self.active_missions            = []
        self.missions_complete          = 0
        self.stack_value                = 0
        self.mission_value_map          = {}
        self.mission_target_faction_map = {}


# ── Session state persistence ─────────────────────────────────────────────────
# Thin JSON snapshot written before upgrade-restart and on clean exit.
# Consumed at startup only when it references the same journal file.

# Wall-clock ISO of session start — set after sessionstart() fires.
_session_start_iso: str | None = None


def save_session_state(journal_path: Path, active_session: SessionData) -> None:
    """Write active session counters to STATE_FILE for upgrade-restart recovery."""
    try:
        payload = {
            "journal":             str(journal_path),
            "session_start_time":  _session_start_iso,
            "kills":               active_session.kills,
            "credit_total":        active_session.credit_total,
            "merits":              active_session.merits,
            "faction_tally":       active_session.faction_tally,
            "kill_interval_total": active_session.kill_interval_total,
            "recent_kill_times":   [t.isoformat() for t in active_session.recent_kill_times],
            "inbound_scan_count":  active_session.inbound_scan_count,
            "low_cargo_count":     active_session.low_cargo_count,
        }
        STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_session_state(
    journal_path: Path,
    active_session: SessionData,
) -> None:
    """Restore session counters from STATE_FILE if it matches journal_path.

    Called once during preload.  Consumed immediately — STATE_FILE is deleted
    after a successful load so state is never restored twice.
    """
    global _session_start_iso
    try:
        if not STATE_FILE.exists():
            return
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if payload.get("journal") != str(journal_path):
            return
        active_session.kills               = int(payload.get("kills", 0))
        active_session.credit_total        = int(payload.get("credit_total", 0))
        active_session.merits              = int(payload.get("merits", 0))
        active_session.faction_tally       = dict(payload.get("faction_tally", {}))
        active_session.kill_interval_total = float(payload.get("kill_interval_total", 0))
        active_session.inbound_scan_count  = int(payload.get("inbound_scan_count", 0))
        active_session.low_cargo_count     = int(payload.get("low_cargo_count", 0))
        active_session.recent_kill_times   = [
            datetime.fromisoformat(t)
            for t in payload.get("recent_kill_times", []) if t
        ]
        _session_start_iso = payload.get("session_start_time")
        STATE_FILE.unlink(missing_ok=True)
    except Exception:
        pass
