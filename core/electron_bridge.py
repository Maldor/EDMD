"""
core/electron_bridge.py — WebSocket bridge for the Electron GUI frontend.

Runs a local-only WebSocket server (127.0.0.1, random port) that:
  - Pushes gui_queue messages as JSON to connected Electron renderer clients
  - Accepts command messages from the renderer and dispatches to core
  - Writes the assigned port to EDMD_DATA_DIR/electron.port so Electron
    main.js can find it without any configuration

This module is only imported when edmd.py runs with --mode electron.
It has zero effect on all other modes.

Dependency: websockets>=12.0  (pip install 'websockets>=12.0')
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.core_api import CoreAPI

log = logging.getLogger(__name__)

PORT_FILE_NAME = "electron.port"


def _port_file(core: "CoreAPI") -> Path:
    from core.state import EDMD_DATA_DIR
    return EDMD_DATA_DIR / PORT_FILE_NAME


# ── State serialisers ─────────────────────────────────────────────────────────
# Each returns a JSON-serialisable dict from live core/state data.
# Mirrors what TUI block refresh_data() reads, but returns data instead of
# updating widgets.


def _get_home_display(core) -> dict | None:
    """Return home location display data for the Commander Info tab.
    Returns None only when the commander plugin is not loaded.
    When loaded, always returns a dict so the Home System row is always visible,
    showing 'unknown' when not set.
    """
    cmdr = core._plugins.get("commander")
    if not cmdr:
        return None
    home = cmdr.get_home_location()
    if not home:
        return {"set": False, "display": "unknown"}
    name    = home.get("name", "")
    system  = home.get("system", name)
    is_stn  = home_name != system and bool(system) if (home_name := name) else False
    if is_stn and system and system != name:
        display = f"{name}  ({system})"
    else:
        display = name
    dist = cmdr.home_distance_ly(getattr(core.state, "pilot_star_pos", None))
    if dist is not None:
        display += f"  |  {dist:,.0f} ly away"
    return {"set": True, "display": display, "name": name, "system": system}

def _ser_commander(core: "CoreAPI") -> dict:
    from core.state import CAPI_RANK_SKILLS
    s = core.state

    # CAPI-sourced rank data (None until first CAPI poll)
    capi_ranks = None
    if s.capi_ranks and s.capi_progress:
        capi_ranks = []
        for key, label, names in CAPI_RANK_SKILLS:
            rank_num = s.capi_ranks.get(key)
            prog_num = s.capi_progress.get(key)
            if rank_num is None:
                continue
            name = names[rank_num] if rank_num < len(names) else str(rank_num)
            capi_ranks.append({
                "key":      key,
                "label":    label,
                "rank":     rank_num,
                "name":     name,
                "progress": round(prog_num * 100) if prog_num is not None else None,
            })

    # CAPI reputation
    capi_rep = None
    if s.capi_reputation:
        capi_rep = {k: round(v, 1) for k, v in s.capi_reputation.items()
                    if isinstance(v, (int, float))}

    # Trim body to remove leading system prefix (e.g. "Bhutatani ABC 2 A Ring" -> "ABC 2 A Ring")
    body_local = s.pilot_body or ""
    if s.pilot_system and body_local.startswith(s.pilot_system):
        body_local = body_local[len(s.pilot_system):].lstrip()

    # PP rank progress for the progress bar
    pp_rank_fraction = 0.0
    if s.pp_rank and s.pp_merits_total is not None:
        from core.state import FUEL_CRIT_THRESHOLD, FUEL_WARN_THRESHOLD
        def _merits_for_rank(r):
            if r <= 1:   return 0
            if r == 2:   return 2_000
            if r == 3:   return 5_000
            if r == 4:   return 9_000
            if r == 5:   return 15_000
            if r <= 100: return 15_000 + (r - 5) * 8_000
            return 775_000 + (r - 100) * 8_000
        floor = _merits_for_rank(s.pp_rank)
        ceil  = _merits_for_rank(s.pp_rank + 1)
        span  = ceil - floor
        if span > 0:
            pp_rank_fraction = min(1.0, max(0.0, (s.pp_merits_total - floor) / span))

    return {
        "pilot_name":              s.pilot_name,
        "pilot_ship":              s.pilot_ship,
        "ship_name":               s.ship_name,
        "ship_ident":              s.ship_ident,
        "pilot_rank":              s.pilot_rank,
        "pilot_rank_progress":     s.pilot_rank_progress,
        "pilot_mode":              s.pilot_mode,
        "pilot_system":            s.pilot_system,
        "pilot_body":              s.pilot_body,
        "pilot_body_local":        body_local,
        "ship_hull":               s.ship_hull,
        "ship_shields":            s.ship_shields,
        "ship_shields_recharging": s.ship_shields_recharging,
        "fuel_current":            s.fuel_current,
        "fuel_tank_size":          s.fuel_tank_size,
        "fuel_burn_rate":          s.fuel_burn_rate,
        "pp_power":                s.pp_power,
        "pp_rank":                 s.pp_rank,
        "pp_merits_total":         s.pp_merits_total,
        "pp_rank_fraction":        pp_rank_fraction,
        "pilot_squadron_name":     s.pilot_squadron_name,
        "pilot_squadron_tag":      s.pilot_squadron_tag,
        "pilot_squadron_rank":     s.pilot_squadron_rank,
        "in_game":                 s.in_game,
        "in_supercruise":          s.in_supercruise,
        "vessel_mode":             getattr(s, "vessel_mode",  "ship"),
        "cmdr_in_slf":             getattr(s, "cmdr_in_slf",  False),
        "srv_hull":                getattr(s, "srv_hull",     100),
        "suit_name":               getattr(s, "suit_name",    ""),
        "capi_ranks":              capi_ranks,
        "capi_reputation":         capi_rep,
        # Home location (for display in Info tab)
        "_home": _get_home_display(core),
    }


def _ser_alerts(core: "CoreAPI") -> dict:
    alerts = core.plugin_call("alerts", "get_alerts") or []
    return {
        "alerts": [
            {
                "emoji":     a.get("emoji", ""),
                "text":      a.get("text", ""),
                "mono_time": a.get("mono_time", 0.0),
            }
            for a in alerts
        ]
    }


def _ser_crew(core: "CoreAPI") -> dict:
    s = core.state
    has_crew = bool(s.crew_name) and getattr(s, "crew_active", False)

    hire_time_str = None
    active_str    = None
    hire_time = getattr(s, "crew_hire_time", None)
    if hire_time:
        try:
            hire_time_str = hire_time.strftime("%d %b %Y")
            from datetime import datetime, timezone
            delta = datetime.now(timezone.utc) - hire_time
            days  = delta.days
            hours = delta.seconds // 3600
            mins  = (delta.seconds % 3600) // 60
            if days > 0:
                active_str = f"{days}d {hours}h {mins}m"
            elif hours > 0:
                active_str = f"{hours}h {mins}m"
            else:
                active_str = f"{mins}m"
        except Exception:
            pass

    paid_complete = getattr(s, "crew_paid_complete", False)

    # SLF type split: "GU-97 (Gelid G)" → type="GU-97", variant="Gelid G"
    slf_full    = getattr(s, "slf_type", "") or ""
    slf_type    = slf_full
    slf_variant = ""
    if "(" in slf_full and slf_full.endswith(")"):
        paren       = slf_full.index("(")
        slf_type    = slf_full[:paren].strip()
        slf_variant = slf_full[paren + 1:-1].strip()

    return {
        "has_crew":           has_crew,
        "crew_name":          getattr(s, "crew_name",          None),
        "crew_rank":          getattr(s, "crew_rank",          None),
        "crew_active":        getattr(s, "crew_active",        False),
        "crew_total_paid":    getattr(s, "crew_total_paid",    None),
        "crew_paid_complete": paid_complete,
        "crew_hire_time":     hire_time_str,
        "crew_active_str":    active_str,
        "has_fighter_bay":    s.has_fighter_bay,
        "slf_deployed":       s.slf_deployed,
        "slf_docked":         s.slf_docked,
        "slf_hull":           s.slf_hull,
        "slf_orders":         s.slf_orders,
        "slf_loadout":        s.slf_loadout,
        "slf_type":           slf_type,
        "slf_variant":        slf_variant,
        "slf_stock_total":    getattr(s, "slf_stock_total",    1),
        "slf_destroyed_count":getattr(s, "slf_destroyed_count",0),
        "cmdr_in_slf":        getattr(s, "cmdr_in_slf",        False),
        "pilot_ship":         s.pilot_ship,
    }


def _ser_missions(core: "CoreAPI") -> dict:
    s      = core.state
    detail = getattr(s, "mission_detail_map", {}) or {}

    factions: dict = {}
    total_reward   = 0
    target_factions: list = []
    target_types:    list = []

    for mid, info in detail.items():
        src    = info.get("faction", "Unknown")
        kc     = int(info.get("kill_count", 0))
        reward = int(info.get("reward", 0))
        tgt_f  = info.get("target_faction", "")
        tgt_t  = info.get("target_type",   "")
        sess_k = int(info.get("kills_this_session", 0))

        if src not in factions:
            factions[src] = {"kill_count": 0, "reward": 0, "session_kills": 0}
        factions[src]["kill_count"]    += kc
        factions[src]["reward"]        += reward
        factions[src]["session_kills"] += sess_k
        total_reward += reward
        if tgt_f and tgt_f not in target_factions:
            target_factions.append(tgt_f)
        if tgt_t and tgt_t not in target_types:
            target_types.append(tgt_t)

    heights      = sorted((v["kill_count"] for v in factions.values()), reverse=True)
    stack_height = heights[0] if heights else 0
    n_missions   = len(getattr(s, "active_missions", []) or [])
    done         = getattr(s, "missions_complete", 0)
    full_stack   = core.app_settings.get("FullStackSize", 20)

    faction_rows = [
        {
            "faction":       f,
            "kill_count":    v["kill_count"],
            "reward":        v["reward"],
            "session_kills": v["session_kills"],
        }
        for f, v in sorted(factions.items(), key=lambda x: -x[1]["kill_count"])
    ]

    return {
        "n_missions":      n_missions,
        "full_stack":      full_stack,
        "missions_complete": done,
        "stack_value":     getattr(s, "stack_value", 0),
        "stack_height":    stack_height,
        "total_reward":    total_reward,
        "factions":        faction_rows,
        "target_factions": target_factions,
        "target_types":    target_types,
        "has_detail":      bool(detail),
    }


def _ser_cargo(core: "CoreAPI") -> dict:
    plugin = core._plugins.get("cargo")
    if plugin and hasattr(plugin, "get_electron_data"):
        try:
            return plugin.get_electron_data()
        except Exception:
            pass
    s = core.state
    return {
        "items":    getattr(s, "cargo_items",    {}),
        "capacity": getattr(s, "cargo_capacity", 0),
        "used":     getattr(s, "cargo_used",     0),
        "target_market_name": getattr(s, "cargo_target_market_name", ""),
    }


def _ser_assets(core: "CoreAPI") -> dict:
    s   = core.state
    cur = getattr(s, "assets_current_ship",    None) or {}
    stored_ships   = getattr(s, "assets_stored_ships",   []) or []
    stored_modules = getattr(s, "assets_stored_modules", []) or []
    carrier        = getattr(s, "assets_carrier",         None)

    # Ships total value (all ships including current)
    cur_id    = cur.get("ship_id")
    all_other = [sh for sh in stored_ships if sh.get("ship_id") != cur_id]
    all_ships = ([cur] if cur else []) + all_other
    ships_val = sum(sh.get("value", 0) for sh in all_ships if sh)
    mods_val  = sum(m.get("value", 0) for m in stored_modules)

    # Carrier cargo value
    fc_mats = getattr(s, "assets_fc_materials", []) or []
    carrier_cargo_val = sum(m.get("price", 0) * m.get("stock", 0) for m in fc_mats)

    # At-risk holdings
    bounties = getattr(s, "holdings_bounties",    0)
    bonds    = getattr(s, "holdings_bonds",       0)
    trade    = getattr(s, "holdings_trade",       0)
    carto    = getattr(s, "holdings_cartography", 0)
    exobio   = getattr(s, "holdings_exobiology",  0)
    risk_total = bounties + bonds + trade + carto + exobio

    # Net worth
    bal          = getattr(s, "assets_balance",      None)
    total_wealth = getattr(s, "assets_total_wealth", None)
    cargo_items  = getattr(s, "cargo_items",         {}) or {}
    cargo_val    = sum(
        v.get("sell_price", 0) * v.get("count", 0)
        for v in cargo_items.values() if isinstance(v, dict)
    )
    if carrier:
        ctype = carrier.get("carrier_type", "FleetCarrier")
        carrier_hull_val = 24_850_000_000 if "Squadron" in ctype else 4_850_000_000
    else:
        carrier_hull_val = 0
    if total_wealth is not None:
        nw = int(total_wealth) + cargo_val + carrier_cargo_val + risk_total + carrier_hull_val
    else:
        nw = (bal or 0) + ships_val + mods_val + cargo_val + carrier_cargo_val + carrier_hull_val + risk_total

    def _ser_ship(sh: dict, is_current: bool = False) -> dict:
        """Serialise a ship dict — always prefer localised type_display."""
        loadout = sh.get("loadout") or []
        # Build tooltip string from loadout modules
        mod_lines = []
        for m in loadout:
            mname = m.get("name_display", "")
            if not mname:
                continue
            eng = m.get("engineering") or {}
            bp  = eng.get("BlueprintLocName") or eng.get("BlueprintName", "")
            lvl = eng.get("Level")
            if bp and lvl:
                mname += f"  G{lvl}"
            mod_lines.append(mname)
        return {
            "type":    sh.get("type_display") or sh.get("type") or "Unknown",
            "name":    sh.get("name") or "",
            "ident":   sh.get("ident") or "",
            "system":  sh.get("system") or "—",
            "value":   sh.get("value") or 0,
            "hull":    sh.get("hull"),
            "hot":     sh.get("hot", False),
            "current": is_current,
            "modules": mod_lines,          # for tooltip display
        }

    def _ser_module(m: dict) -> dict:
        """Serialise a stored module with engineering detail."""
        eng  = m.get("engineering") or {}
        bp   = eng.get("BlueprintName", "")
        lvl  = eng.get("Level")
        eng_str = ""
        if bp and lvl:
            import re as _re
            bp_clean = _re.sub(r"(?<=[a-z])(?=[A-Z])", " ", bp)
            eng_str  = f"G{lvl} {bp_clean}"
        return {
            "name":     m.get("name_display") or m.get("name_internal", "Unknown"),
            "slot":     m.get("slot", ""),
            "system":   m.get("system", "—"),
            "value":    m.get("value", 0),
            "mass":     m.get("mass", 0),
            "hot":      m.get("hot", False),
            "eng":      eng_str,
        }

    # Old GTK4-matching slot-based category assignment (from gui/blocks/assets.py)
    _SLOT_CATS = [
        ("TinyHardpoint",          "Utility Mounts"),
        ("HugeHardpoint",          "Hardpoints"),
        ("LargeHardpoint",         "Hardpoints"),
        ("MediumHardpoint",        "Hardpoints"),
        ("SmallHardpoint",         "Hardpoints"),
        ("Hardpoint",              "Hardpoints"),
        ("Armour",                 "Core Internal"),
        ("PowerPlant",             "Core Internal"),
        ("MainEngines",            "Core Internal"),
        ("FrameShiftDrive",        "Core Internal"),
        ("LifeSupport",            "Core Internal"),
        ("PowerDistributor",       "Core Internal"),
        ("Radar",                  "Core Internal"),
        ("FuelTank",               "Core Internal"),
        ("Slot",                   "Optional Internal"),
        ("Military",               "Military"),
        ("PlanetaryApproachSuite", "Optional Internal"),
        ("EngineColour",           "Livery"),
        ("WeaponColour",           "Livery"),
        ("ShipCockpit",            "Livery"),
        ("CargoHatch",             "Optional Internal"),
        ("PaintJob",               "Livery"),
        ("Bobble",                 "Livery"),
        ("Decal",                  "Livery"),
        ("ShipName",               "Livery"),
        ("ShipID",                 "Livery"),
        ("VesselVoice",            "Livery"),
        ("StringLights",           "Livery"),
        ("ShipKitSpoiler",         "Livery"),
        ("ShipKitWings",           "Livery"),
        ("ShipKitTail",            "Livery"),
        ("ShipKitBumper",          "Livery"),
    ]
    _CAT_ORDER = ["Hardpoints", "Core Internal", "Optional Internal",
                  "Military", "Utility Mounts", "Livery", "Other"]

    def _slot_to_cat(slot: str) -> str:
        for prefix, cat in _SLOT_CATS:
            if slot.startswith(prefix):
                return cat
        return "Other"

    grouped_modules: dict = {c: [] for c in _CAT_ORDER}
    for m in sorted(stored_modules, key=lambda x: x.get("name_display", "")):
        cat = _slot_to_cat(m.get("slot", "") or "")
        if cat not in grouped_modules:
            grouped_modules[cat] = []
        grouped_modules[cat].append(_ser_module(m))
    # Remove empty categories to keep JSON clean
    grouped_modules = {k: v for k, v in grouped_modules.items() if v}

    return {
        "balance":      bal,
        "net_worth":    nw if nw else None,
        "ships_value":  ships_val or None,
        "mods_value":   mods_val or None,
        "carrier":  {
            "hull_value":    carrier_hull_val,
            "cargo_value":   carrier_cargo_val,
            "cargo_used":    carrier.get("cargo_used"),
            "cargo_free":    carrier.get("cargo_free"),
            "name":          carrier.get("name"),
            "callsign":      carrier.get("callsign"),
            "system":        carrier.get("system") or carrier.get("currentStarSystem"),
            "fuel":          carrier.get("fuel"),
            "balance":       carrier.get("balance"),
            "reserve":       carrier.get("reserve"),
            "available":     carrier.get("available"),
            "docking":       carrier.get("dockingAccess") or carrier.get("docking"),
            "state":         carrier.get("state"),
        } if carrier else None,
        "risk": {
            "bounties": bounties,
            "bonds":    bonds,
            "trade":    trade,
            "carto":    carto,
            "exobio":   exobio,
            "total":    risk_total,
        },
        "current_ship":  _ser_ship(cur, is_current=True) if cur else None,
        "stored_ships":  [_ser_ship(sh) for sh in all_other],
        "modules":        grouped_modules,   # {category: [{name,slot,system,value,eng}]}
        "module_count":   len(stored_modules),
    }


def _ser_engineering(core: "CoreAPI") -> dict:
    plugin = core._plugins.get("engineering")
    if plugin and hasattr(plugin, "get_electron_data"):
        try:
            return plugin.get_electron_data()
        except Exception:
            pass
    return {"raw": [], "manufactured": [], "encoded": []}


def _ser_career(core: "CoreAPI") -> dict:
    """Serialise career lifetime stats from journal_history plugin results.

    Field names mirror GTK4 gui/blocks/career.py _rows_for() exactly —
    Statistics sub-dicts are the authoritative source for most values.
    """
    hist = core._plugins.get("journal_history")
    if hist is None:
        return {}
    if not hist.scan_done.is_set():
        return {"scanning": True}

    r     = hist.results or {}
    stats = r.get("statistics", {}) or {}

    # Statistics sub-dicts (authoritative game totals from Statistics journal event)
    expl = stats.get("Exploration",  {}) or {}
    exo  = stats.get("Exobiology",   {}) or {}
    bank = stats.get("Bank_Account", {}) or {}
    cmb  = stats.get("Combat",       {}) or {}
    mine = stats.get("Mining",       {}) or {}
    trd  = stats.get("Trading",      {}) or {}

    # journal_history computed dicts (from scanning all journal files)
    combat = r.get("combat",      {}) or {}
    carto  = r.get("cartography", {}) or {}
    exobio = r.get("exobiology",  {}) or {}
    pp     = r.get("powerplay",   {}) or {}
    income = r.get("income",      {}) or {}

    # Live state for PP (more current than scanned history)
    s          = core.state
    pp_total   = getattr(s, "pp_merits_total", None) or pp.get("total_merits", 0)
    pp_power   = getattr(s, "pp_power",        None) or ""
    pp_rank    = getattr(s, "pp_rank",         None)

    return {
        "scanning": False,

        # Summary / time
        "time_played":      expl.get("Time_Played", 0),

        # Combat tab — prefer Statistics (authoritative) over journal scan
        "kills":            cmb.get("Bounties_Claimed",   0) or combat.get("kill_count",      0),
        "bounties":         cmb.get("Bounty_Hunting_Profit", 0) or combat.get("bounties_earned", 0),
        "bonds":            cmb.get("Combat_Bond_Profits", 0) or combat.get("bonds_earned",   0),
        "assassinations":   cmb.get("Assassinations",     0),
        "deaths":           bank.get("Insurance_Claims",  0),
        "rebuy_costs":      bank.get("Spent_On_Insurance", 0),

        # Exploration tab
        "systems_visited":  expl.get("Systems_Visited",              0),
        "hyperspace_jumps": expl.get("Total_Hyperspace_Jumps",       0),
        "distance_ly":      expl.get("Total_Hyperspace_Distance",    0),
        "planets_fss":      expl.get("Planets_Scanned_To_Level_2",   0),
        "planets_dss":      expl.get("Planets_Scanned_To_Level_3",   0),
        "first_footfalls":  expl.get("First_Footfalls",              0),
        "carto_sold":       expl.get("Exploration_Profits",          0) or carto.get("sold_total", 0),
        "carto_highest":    expl.get("Highest_Payout",               0),

        # Exobiology tab
        "exo_samples":      exo.get("Organic_Data",                  0) or exobio.get("sample_count", 0),
        "exo_species":      exo.get("Organic_Species_Encountered",   0),
        "exo_genus":        exo.get("Organic_Genus_Encountered",     0),
        "exo_systems":      exo.get("Organic_Systems",               0),
        "exo_planets":      exo.get("Organic_Planets",               0),
        "exo_sold":         exo.get("Organic_Data_Profits",          0) or exobio.get("sold_total", 0),
        "exo_first_logged": exo.get("First_Logged",                  0),
        "exo_first_profit": exo.get("First_Logged_Profits",          0),

        # Mining tab
        "qty_mined":         mine.get("Quantity_Mined",       0),
        "mining_profit":     mine.get("Mining_Profits",       0),
        "mining_materials":  mine.get("Materials_Collected",  0),

        # Trade tab
        "trade_profit":      trd.get("Market_Profits",        0),
        "trade_markets":     trd.get("Markets_Traded_With",   0),
        "trade_resources":   trd.get("Resources_Traded",      0),
        "mission_income":    income.get("missions",           0),

        # PowerPlay tab
        "pp_power":          pp_power,
        "pp_rank":           pp_rank,
        "pp_merits":         pp_total,
    }


def _ser_session_stats(core: "CoreAPI") -> dict:
    plugin = core._plugins.get("session_stats")
    if plugin is None:
        return {}
    try:
        return plugin.get_electron_data()
    except Exception:
        return {}


def _ser_colonisation(core: "CoreAPI") -> dict:
    plugin = core._plugins.get("colonisation")
    if plugin and hasattr(plugin, "get_electron_data"):
        try:
            return plugin.get_electron_data()
        except Exception:
            pass
    return {"projects": []}


# gui_queue message type → (serialiser | None, renderer event name)
# None serialiser = payload forwarded directly (log lines, notices)
_DISPATCH: dict[str, tuple] = {
    "cmdr_update":         (_ser_commander,    "commander"),
    "vessel_update":       (_ser_commander,    "commander"),
    "location_update":     (_ser_commander,    "commander"),
    "pp_update":           (_ser_commander,    "commander"),
    "capi_updated":        (_ser_commander,    "commander"),
    "alert_update":        (_ser_alerts,       "alerts"),
    "alerts_update":       (_ser_alerts,       "alerts"),
    "crew_update":         (_ser_crew,         "crew"),
    "slf_update":          (_ser_crew,         "crew"),
    "mission_update":      (_ser_missions,     "missions"),
    "cargo_update":        (_ser_cargo,        "cargo"),
    "assets_update":       (_ser_assets,       "assets"),
    "materials_update":    (_ser_engineering,  "engineering"),
    "career_update":       (_ser_career,       "career"),
    "stats_update":        (_ser_session_stats,"session_stats"),
    "colonisation_update": (_ser_colonisation, "colonisation"),
    "log":                 (None,              "log"),
    "update_notice":       (None,              "update_notice"),
    "plugin_refresh":      (None,              "refresh"),  # handled specially in _drain
}


# Maps plugin_refresh payload names → (_DISPATCH key that serialises that block)
# When spansh/cargo/etc calls gq.put(("plugin_refresh", "cargo")), this routes
# it to the correct serialiser so the renderer gets a proper cargo event.
_PLUGIN_REFRESH_MAP: dict[str, str] = {
    "cargo":        "cargo_update",
    "engineering":  "materials_update",
    "assets":       "assets_update",
    "commander":    "cmdr_update",
    "colonisation": "colonisation_update",
    "session_stats":"stats_update",
    "missions":     "mission_update",
    "crew":         "crew_update",
}


# ── Command dispatcher ────────────────────────────────────────────────────────

def _dispatch_command(core: "CoreAPI", cmd: dict) -> dict:
    action = cmd.get("cmd", "")

    if action == "ping":
        return {"pong": True}

    if action == "reset_session":
        try:
            core.plugin_call("session_stats", "on_new_session", 0)
        except Exception as e:
            return {"error": str(e)}
        return {"ok": True}

    if action == "clear_alerts":
        try:
            core.plugin_call("alerts", "clear_alerts")
        except Exception as e:
            return {"error": str(e)}
        return {"ok": True}

    if action == "get_block":
        block = cmd.get("block", "")
        # Try <block>_update first, then bare block name
        entry = _DISPATCH.get(f"{block}_update") or _DISPATCH.get(block)
        if entry and entry[0] is not None:
            try:
                return {"event": entry[1], "data": entry[0](core)}
            except Exception as e:
                return {"error": str(e)}
        return {"error": f"unknown block: {block!r}"}

    if action == "get_all":
        # Full state dump sent on initial renderer connection
        from core.state import VERSION
        result: dict = {}
        seen: set[str] = set()
        for fn, event in _DISPATCH.values():
            if event in seen or fn is None:
                continue
            seen.add(event)
            try:
                result[event] = fn(core)
            except Exception:
                result[event] = {}
        from core.state import PROGRAM
        result["_meta"] = {"version": VERSION, "program": PROGRAM}
        return {"event": "initial_state", "data": result}


    if action == "get_prefs":
        cfg = core.cfg
        # CAPI status
        capi_status = {}
        try:
            dp   = getattr(core, "data", None)
            capi = dp.capi if dp else None
            if capi:
                st = capi.auth_status()
                import datetime, time as _t
                connected = st.get("connected", False)
                cmdr      = st.get("cmdr", "")
                expiry    = st.get("expiry")
                last_ep   = capi.last_poll("profile")
                exp_str   = ""
                last_str  = ""
                if connected and expiry:
                    mins = max(0, int((expiry - _t.time()) / 60))
                    exp_str = f"  (refreshes in {mins}m)"
                if last_ep:
                    t = datetime.datetime.fromtimestamp(last_ep).strftime("%H:%M:%S")
                    last_str = f"  ·  last poll {t}"
                if connected:
                    capi_status = {
                        "state":   f"Connected{(' — CMDR ' + cmdr) if cmdr else ''}{exp_str}{last_str}",
                        "connected": True,
                    }
                else:
                    result = st.get("auth_result", "")
                    capi_status = {
                        "state": "Waiting for browser authentication…" if result == "auth_running" else "Not connected",
                        "connected": False,
                    }
            else:
                capi_status = {"state": "CAPI not available", "connected": False}
        except Exception as exc:
            capi_status = {"state": f"Error: {exc}", "connected": False}

        return {
            "event": "prefs_data",
            "data": {
                "settings":      dict(cfg.app_settings),
                "notify_levels": dict(cfg.notify_levels),
                "ui_cfg":        dict(cfg.ui_cfg),
                "eddn_cfg":      dict(getattr(cfg, "eddn_cfg",    {}) or {}),
                "edsm_cfg":      dict(getattr(cfg, "edsm_cfg",    {}) or {}),
                "inara_cfg":        dict(getattr(cfg, "inara_cfg",        {}) or {}),
                "edastro_cfg":      dict(getattr(cfg, "edastro_cfg",      {}) or {}),
                "colonisation_cfg": dict(getattr(cfg, "colonisation_cfg", {}) or {}),
                "capi_status":      capi_status,
            },
        }

    if action == "save_prefs":
        changes     = cmd.get("changes", [])
        needs_restart = cmd.get("restart", False)
        try:
            cfg = core.cfg
            for ch in changes:
                section = ch.get("section", "settings")
                key     = ch["key"]
                value   = ch["value"]
                if section == "settings":
                    cfg.app_settings[key] = value
                elif section == "eddn":
                    if hasattr(cfg, "eddn_cfg"):
                        cfg.eddn_cfg[key] = value
                elif section == "edsm":
                    if hasattr(cfg, "edsm_cfg"):
                        cfg.edsm_cfg[key] = value
                elif section == "inara":
                    if hasattr(cfg, "inara_cfg"):
                        cfg.inara_cfg[key] = value
                elif section == "colonisation":
                    if hasattr(cfg, "colonisation_cfg"):
                        cfg.colonisation_cfg[key] = value
                        # Push API key change into live plugin without restart
                        if key == "ApiKey":
                            plugin = core._plugins.get("colonisation")
                            if plugin and hasattr(plugin, "set_api_key"):
                                plugin.set_api_key(value)
                elif section == "edastro":
                    if hasattr(cfg, "edastro_cfg"):
                        cfg.edastro_cfg[key] = value
                elif section == "notify_levels":
                    cfg.notify_levels[key] = value
                elif section == "ui":
                    cfg.ui_cfg[key] = value
            cfg.save()
        except Exception as e:
            return {"error": str(e)}
        if needs_restart:
            import os, sys
            try:
                os.execv(sys.executable, [sys.executable] + (
                    getattr(core, "launch_argv", None) or sys.argv
                ))
            except Exception as e:
                return {"error": f"restart failed: {e}"}
        return {"ok": True}

    if action == "run_report":
        from core.reports import REPORT_REGISTRY
        from pathlib import Path as _Path
        report_key = cmd.get("report", "")
        entry = next((r for r in REPORT_REGISTRY if r[0] == report_key), None)
        if entry is None:
            return {"error": f"unknown report: {report_key!r}"}
        _, _label, fn = entry
        try:
            journal_dir = _Path(core.cfg.app_settings.get("JournalFolder", ""))
            result = fn(journal_dir)
            # Flatten ReportResult.sections into a flat row list for the renderer.
            # Each section becomes a header row followed by data rows.
            # ReportSection: heading, columns, rows (list[ReportRow]), prose, note
            # ReportRow: cells (list[str])
            flat: list[dict] = []
            for sec in (result.sections or []):
                # Section heading
                flat.append({"_type": "header", "text": sec.heading})
                # Column headers (if tabular)
                if sec.columns:
                    flat.append({
                        "_type":   "col_headers",
                        "columns": list(sec.columns),
                    })
                # Data rows
                for row in (sec.rows or []):
                    cells = list(row.cells) if hasattr(row, "cells") else [str(row)]
                    # Map cells to label/value/extra based on column count
                    out: dict = {"_type": "data"}
                    if len(cells) == 0:
                        pass
                    elif len(cells) == 1:
                        out["label"] = cells[0]
                    elif len(cells) == 2:
                        out["label"] = cells[0]
                        out["value"] = cells[1]
                    else:
                        out["label"] = cells[0]
                        out["value"] = cells[1]
                        out["extra"] = "  ".join(cells[2:])
                    flat.append(out)
                # Prose block
                if sec.prose:
                    flat.append({"_type": "prose", "text": sec.prose})
                # Note
                if sec.note:
                    flat.append({"_type": "note", "text": sec.note})
                # Separator between sections
                flat.append({"_type": "sep"})
            return {
                "event": "report_data",
                "data": {
                    "key":      report_key,
                    "title":    result.title,
                    "subtitle": result.subtitle,
                    "error":    result.error or "",
                    "rows":     flat,
                },
            }
        except Exception:
            import traceback
            return {"error": traceback.format_exc()}


    if action == "get_home":
        cmdr = core._plugins.get("commander")
        if not cmdr:
            return {"home": None}
        home = cmdr.get_home_location()
        dist = cmdr.home_distance_ly(getattr(core.state, "pilot_star_pos", None))
        if home and dist is not None:
            home = dict(home); home["distance_ly"] = round(dist)
        return {"home": home}

    if action == "set_home":
        cmdr = core._plugins.get("commander")
        if not cmdr:
            return {"error": "commander plugin not loaded"}
        cmdr.set_home_location(
            cmd.get("name", ""),
            cmd.get("system", ""),
            cmd.get("star_pos"),
        )
        return {"ok": True}

    if action == "clear_home":
        cmdr = core._plugins.get("commander")
        if cmdr:
            cmdr.clear_home_location()
        return {"ok": True}

    if action == "search_home":
        import concurrent.futures as _cf
        spansh = core._plugins.get("spansh")
        if not spansh:
            return {"results": [], "error": "spansh not loaded"}
        query = cmd.get("query", "")
        if len(query) < 3:
            return {"results": []}
        try:
            with _cf.ThreadPoolExecutor(max_workers=1) as ex:
                results = ex.submit(spansh.search_home, query).result(timeout=8)
            return {"results": results or []}
        except Exception as e:
            return {"results": [], "error": str(e)}

    if action == "search_market":
        import concurrent.futures as _cf
        spansh = core._plugins.get("spansh")
        if not spansh:
            return {"results": [], "error": "spansh not loaded"}
        query = cmd.get("query", "")
        if len(query) < 3:
            return {"results": []}
        try:
            with _cf.ThreadPoolExecutor(max_workers=1) as ex:
                results = ex.submit(spansh.search, query).result(timeout=8)
            return {"results": results or []}
        except Exception as e:
            return {"results": [], "error": str(e)}

    if action == "set_target_market":
        spansh = core._plugins.get("spansh")
        if not spansh:
            return {"error": "spansh not loaded"}
        record = cmd.get("record")
        if record:
            spansh.set_target(_record=record,
                              station_name=record.get("name", ""),
                              system_name=record.get("system", ""))
        else:
            spansh.set_target(cmd.get("station_name", ""),
                              cmd.get("system_name", ""))
        return {"ok": True}

    if action == "clear_target_market":
        spansh = core._plugins.get("spansh")
        if spansh:
            spansh.clear_target()
        return {"ok": True}


    if action == "capi_connect":
        try:
            dp   = getattr(core, "data", None)
            capi = dp.capi if dp else None
            if capi:
                import threading as _thr
                _thr.Thread(target=capi.authenticate, daemon=True, name="capi-auth").start()
                return {"ok": True, "state": "Authenticating — check your browser"}
            return {"error": "CAPI not available"}
        except Exception as exc:
            return {"error": str(exc)}

    if action == "capi_disconnect":
        try:
            dp   = getattr(core, "data", None)
            capi = dp.capi if dp else None
            if capi:
                capi.revoke()
                return {"ok": True}
            return {"error": "CAPI not available"}
        except Exception as exc:
            return {"error": str(exc)}

    return {"error": f"unknown command: {action!r}"}


# ── Bridge ────────────────────────────────────────────────────────────────────

class ElectronBridge:
    """
    Local WebSocket server (127.0.0.1) bridging edmd.py to Electron.

    Usage::

        bridge = ElectronBridge(core, gui_queue)
        bridge.start()          # background thread; writes port file
        # ... run_monitor() running on another thread ...
        bridge.stop()           # clean shutdown; removes port file
    """

    POLL_HZ = 20   # queue drain frequency

    def __init__(self, core: "CoreAPI", gui_queue: queue.Queue) -> None:
        self._core        = core
        self._q           = gui_queue
        self._clients:   set  = set()
        self._loop:      asyncio.AbstractEventLoop | None = None
        self._thread:    threading.Thread | None = None
        self._port:      int  = 0
        self._port_file: Path = _port_file(core)
        self._ready      = threading.Event()
        self._server:    object = None   # websockets ServerType

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> int:
        """Spawn the server thread. Returns the port once the socket is bound."""
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="electron-bridge",
        )
        self._thread.start()
        self._ready.wait(timeout=8.0)
        return self._port

    def stop(self) -> None:
        """Signal the bridge to shut down and clean up the port file."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        try:
            self._port_file.unlink(missing_ok=True)
        except OSError:
            pass

    # ── Server loop ───────────────────────────────────────────────────────────

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        # Schedule _serve() as a task, then run the loop until stop() is called.
        # Using run_forever() (not run_until_complete) avoids the
        # "Event loop stopped before Future completed" RuntimeError that fires
        # when bridge.stop() calls loop.stop() while a coroutine is pending.
        self._loop.run_until_complete(self._setup_server())
        if self._port == 0:
            # _setup_server signalled failure via _ready — nothing more to do
            return
        try:
            self._loop.run_forever()
        except Exception as exc:
            log.error("electron-bridge loop error: %s", exc)
        finally:
            # Cancel remaining tasks cleanly
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            self._loop.close()

    async def _setup_server(self) -> None:
        """Bind the WebSocket server and start the drain loop as a background task."""
        try:
            import websockets.server
        except ImportError:
            print(
                "\n[electron-bridge] ERROR: websockets package not installed.\n"
                "  pip install \'websockets>=12.0\'\n"
            )
            self._ready.set()
            return

        self._server = await websockets.server.serve(
            self._on_client, "127.0.0.1", 0,
        )
        self._port = self._server.sockets[0].getsockname()[1]
        self._port_file.write_text(str(self._port), encoding="utf-8")
        print(f"[electron-bridge] ws://127.0.0.1:{self._port}")
        self._ready.set()
        # Schedule the queue drain loop as a persistent task
        self._loop.create_task(self._drain_loop())

    async def _drain_loop(self) -> None:
        """Drain gui_queue and push messages to all connected clients at POLL_HZ."""
        interval = 1.0 / self.POLL_HZ
        while True:
            await self._drain()
            await asyncio.sleep(interval)

    # ── Client handler ────────────────────────────────────────────────────────

    async def _on_client(self, ws) -> None:
        self._clients.add(ws)
        log.debug("electron-bridge: client connected (%d)", len(self._clients))
        try:
            # Full state dump on connect
            dump = _dispatch_command(self._core, {"cmd": "get_all"})
            await ws.send(json.dumps(dump))

            async for raw in ws:
                try:
                    cmd    = json.loads(raw)
                    action = cmd.get("cmd", "")
                    # Search commands make blocking HTTP requests — run off the
                    # event loop thread so the drain loop and other clients are
                    # not blocked during the network call.
                    if action in ("search_home", "search_market",
                                  "set_home", "set_target_market",
                                  "clear_target_market", "clear_home"):
                        import asyncio as _aio
                        resp = await _aio.get_event_loop().run_in_executor(
                            None, _dispatch_command, self._core, cmd
                        )
                    else:
                        resp = _dispatch_command(self._core, cmd)
                    await ws.send(json.dumps(resp))
                except (json.JSONDecodeError, Exception) as exc:
                    await ws.send(json.dumps({"error": str(exc)}))
        except Exception:
            pass
        finally:
            self._clients.discard(ws)
            log.debug("electron-bridge: client disconnected (%d)", len(self._clients))

    # ── Queue drain ───────────────────────────────────────────────────────────

    async def _drain(self) -> None:
        messages: list[str] = []
        try:
            while True:
                msg_type, payload = self._q.get_nowait()
                entry = _DISPATCH.get(msg_type)
                if entry is None:
                    continue
                fn, event = entry
                try:
                    if msg_type == "plugin_refresh" and isinstance(payload, str):
                        # Remap to the correct block serialiser
                        dispatch_key = _PLUGIN_REFRESH_MAP.get(payload)
                        if dispatch_key:
                            block_entry = _DISPATCH.get(dispatch_key)
                            if block_entry and block_entry[0] is not None:
                                fn, event = block_entry
                                data = fn(self._core)
                                messages.append(json.dumps({"event": event, "data": data}))
                        continue
                    if fn is None:
                        # log lines and update_notice pass payload directly
                        if event == "log":
                            data: dict = {"line": payload}
                        elif event == "update_notice":
                            if isinstance(payload, tuple):
                                kind, value = payload
                            else:
                                kind, value = "release", payload
                            data = {"kind": kind, "value": str(value)}
                        else:
                            data = {"raw": str(payload)}
                    else:
                        data = fn(self._core)
                    messages.append(json.dumps({"event": event, "data": data}))
                except Exception as exc:
                    log.debug("electron-bridge serialise %s: %s", msg_type, exc)
        except queue.Empty:
            pass

        if not messages or not self._clients:
            return

        dead: set = set()
        for client in self._clients:
            try:
                for msg in messages:
                    await client.send(msg)
            except Exception:
                dead.add(client)
        self._clients -= dead
