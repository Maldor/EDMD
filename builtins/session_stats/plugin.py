"""
builtins/session_stats/plugin.py — Kill, credit, merit, and session timing.

Owns: active_session.kills, credit_total, merits, faction_tally,
      kill timing, periodic summary, inactivity/rate alerts.
GUI block: col=8, row=0, width=8, height=5 (default).
"""

import time
from core.plugin_loader import BasePlugin
from core.state import normalise_ship_name
from core.emit import Terminal, fmt_credits, fmt_duration, rate_per_hour, clip_name
from core.state import RECENT_KILL_WINDOW


class SessionStatsPlugin(BasePlugin):
    PLUGIN_NAME    = "session_stats"
    PLUGIN_DISPLAY = "Session Stats"
    PLUGIN_VERSION = "1.0.0"

    SUBSCRIBED_EVENTS = [
        "Bounty", "FactionKillBond",
        "PowerplayMerits",
        "SupercruiseDestinationDrop",
        "ReceiveText",
        "ShipTargeted",
    ]

    DEFAULT_COL    = 8
    DEFAULT_ROW    = 0
    DEFAULT_WIDTH  = 8
    DEFAULT_HEIGHT = 5

    def on_load(self, core) -> None:
        super().on_load(core)
        core.register_block(self, priority=20)

    def on_event(self, event: dict, state) -> None:
        core    = self.core
        ses     = core.active_session
        lt      = core.lifetime
        gq      = core.gui_queue
        notify  = core.notify_levels
        settings = core.app_settings
        ev      = event.get("event")
        logtime = event.get("_logtime")
        max_trunc = settings.get("TruncateNames", 30)

        match ev:

            case "Bounty" | "FactionKillBond":
                state.sessionstart(ses)
                if settings.get("MinScanLevel") == 0:
                    ses.recent_outbound_scans.clear()

                ses.kills   += 1
                lt.kills    += 1
                thiskill     = logtime
                killtime_str = ""
                state.last_rate_check = time.monotonic()
                ses.pending_merit_events += 1

                if ses.last_kill_time:
                    secs = (thiskill - ses.last_kill_time).total_seconds()
                    killtime_str = f" (+{fmt_duration(secs)})"
                    ses.kill_interval_total += secs
                    if len(ses.recent_kill_times) == RECENT_KILL_WINDOW:
                        ses.recent_kill_times.pop(0)
                    ses.recent_kill_times.append(secs)
                    lt.kill_interval_total += secs

                ses.last_kill_time = logtime
                if not state.in_preload:
                    ses.last_kill_mono = time.monotonic()

                if ev == "Bounty":
                    bountyvalue = event["Rewards"][0]["Reward"]
                    ship        = normalise_ship_name(event.get("Target_Localised") or event.get("Target"))
                else:
                    bountyvalue       = event["Reward"]
                    ship              = "Bond"
                    state.reward_type = "bonds"

                pirate_str = (
                    f" [{clip_name(event['PilotName_Localised'], max_trunc)}]"
                    if "PilotName_Localised" in event and settings.get("PirateNames")
                    else ""
                )
                ses.credit_total += bountyvalue
                lt.credit_total  += bountyvalue

                kills_t = f" x{ses.kills}" if settings.get("ExtendedStats") else ""
                kills_d = f"x{ses.kills} " if settings.get("ExtendedStats") else ""
                bv_str  = (
                    f" [{fmt_credits(bountyvalue)} cr]"
                    if settings.get("BountyValue") else ""
                )
                victimfaction = event.get("VictimFaction_Localised") or event.get("VictimFaction", "")
                ses.faction_tally[victimfaction] = ses.faction_tally.get(victimfaction, 0) + 1
                lt.faction_tally[victimfaction]  = lt.faction_tally.get(victimfaction, 0) + 1
                fc_count = (
                    f" x{ses.faction_tally[victimfaction]}"
                    if settings.get("ExtendedStats") else ""
                )
                bf_str = (
                    f" [{clip_name(victimfaction, max_trunc)}{fc_count}]"
                    if settings.get("BountyFaction") else ""
                )
                core.emitter.emit(
                    msg_term=(
                        f"{Terminal.WHITE}Kill{Terminal.END}{kills_t}: "
                        f"{ship}{killtime_str}{pirate_str}{bv_str}{bf_str}"
                    ),
                    msg_discord=(
                        f"{kills_d}**{ship}{killtime_str}**"
                        f"{pirate_str}{bv_str}{bf_str}"
                    ),
                    emoji="💥", sigil="*  KILL",
                    timestamp=logtime, loglevel=notify["RewardEvent"],
                )
                if gq: gq.put(("stats_update", None))

            case "PowerplayMerits":
                if ses.pending_merit_events > 0 and event.get("MeritsGained", 0) < 500:
                    ses.merits  += event["MeritsGained"]
                    lt.merits   += event["MeritsGained"]
                    core.emitter.emit(
                        msg_term=f"Merits: +{event['MeritsGained']:,} ({event.get('Power', '')})",
                        emoji="⭐", sigil="+  MERC",
                        timestamp=logtime, loglevel=notify["MeritEvent"],
                    )
                    ses.pending_merit_events -= 1
                if gq: gq.put(("stats_update", None))

            case "SupercruiseDestinationDrop" if any(
                x in event.get("Type", "") for x in ["$MULTIPLAYER", "$Warzone"]
            ):
                state.sessionstart(ses, True)
                type_local    = event.get("Type_Localised", "[Unknown]")
                state.pilot_body = type_local
                if core.gui_queue: core.gui_queue.put(("cmdr_update", None))
                emoji = "🪐" if "Resource Extraction Site" in type_local else "⚔️"
                core.emitter.emit(
                    msg_term=f"Dropped at {type_local}",
                    emoji=emoji, sigil=">  DROP",
                    timestamp=logtime, loglevel=2,
                )

            case "ReceiveText" if event.get("Channel") == "npc":
                from core.state import PIRATE_NOATTACK_MSGS, LABEL_UNKNOWN
                msg = event.get("Message", "")
                if "$Pirate_OnStartScanCargo" in msg:
                    piratename = event.get("From_Localised", LABEL_UNKNOWN)
                    if piratename not in ses.recent_inbound_scans:
                        ses.inbound_scan_count += 1
                        lt.inbound_scan_count  += 1
                        count_str  = f" (x{ses.inbound_scan_count})" if settings.get("ExtendedStats") else ""
                        pirate_str = f" [{piratename}]" if settings.get("PirateNames") else ""
                        if len(ses.recent_inbound_scans) == 5:
                            ses.recent_inbound_scans.pop(0)
                        ses.recent_inbound_scans.append(piratename)
                        core.emitter.emit(
                            msg_term=f"Cargo scan{count_str}{pirate_str}",
                            msg_discord=f"**Cargo scan{count_str}**{pirate_str}",
                            emoji="📦", sigil="-  SCAN",
                            timestamp=logtime, loglevel=notify["InboundScan"],
                        )
                elif any(x in msg for x in PIRATE_NOATTACK_MSGS):
                    ses.low_cargo_count += 1
                    count_str = f" (x{ses.low_cargo_count})" if settings.get("ExtendedStats") else ""
                    core.emitter.emit(
                        msg_term=(
                            f"{Terminal.WARN}"
                            f'Pirate didn"t engage due to insufficient cargo value'
                            f"{count_str}{Terminal.END}"
                        ),
                        msg_discord=(
                            f'**Pirate didn"t engage due to insufficient cargo value**'
                            f"{count_str}"
                        ),
                        emoji="📦", sigil="-  SCAN",
                        timestamp=logtime, loglevel=notify["LowCargoValue"],
                        event="LowCargoValue",
                    )
                elif "Police_Attack" in msg:
                    core.emitter.emit(
                        msg_term=f"{Terminal.BAD}Under attack by security services!{Terminal.END}",
                        msg_discord="**Under attack by security services!**",
                        emoji="🚨", sigil="!! ATCK",
                        timestamp=logtime, loglevel=notify["PoliceAttack"],
                    )

            case "ShipTargeted" if "Ship" in event:
                ship = normalise_ship_name(event.get("Ship_Localised") or event.get("Ship"))
                rank = "" if "PilotRank" not in event else f" ({event['PilotRank']})"
                if (
                    ship != ses.last_security_ship
                    and "PilotName" in event
                    and "$ShipName_Police" in event["PilotName"]
                ):
                    ses.last_security_ship = ship
                    core.emitter.emit(
                        msg_term=f"{Terminal.WARN}Scanned security{Terminal.END} ({ship})",
                        msg_discord=f"**Scanned security** ({ship})",
                        emoji="🔍", sigil="-  SCAN",
                        timestamp=logtime, loglevel=notify["PoliceScan"],
                    )
                else:
                    state.sessionstart(ses)
                    from core.state import LABEL_UNKNOWN
                    piratename = event.get("PilotName_Localised", LABEL_UNKNOWN)
                    check      = piratename if settings.get("MinScanLevel") != 0 else ship
                    scanstage  = event.get("ScanStage", 0)
                    if (
                        scanstage >= settings.get("MinScanLevel", 1)
                        and check not in ses.recent_outbound_scans
                    ):
                        if len(ses.recent_outbound_scans) == 10:
                            ses.recent_outbound_scans.pop(0)
                        ses.recent_outbound_scans.append(check)
                        pirate_str = (
                            f" [{piratename}]"
                            if settings.get("PirateNames") and piratename != LABEL_UNKNOWN
                            else ""
                        )
                        core.emitter.emit(
                            msg_term=f"{Terminal.WHITE}Scan{Terminal.END}: {ship}{rank}{pirate_str}",
                            msg_discord=f"**{ship}**{rank}{pirate_str}",
                            emoji="🔍", sigil="-  SCAN",
                            timestamp=logtime, loglevel=notify["InboundScan"],
                        )

    def get_summary_line(self) -> str | None:
        """Returns None — emit_summary() builds the full summary block itself."""
        return None
