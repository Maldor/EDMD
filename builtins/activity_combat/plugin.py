"""
builtins/activity_combat/plugin.py — Combat session tracking.

Tracks kills, bounties, combat bonds, deaths, fighter losses,
and the no-kill inactivity timeout (formerly in mode plugin).

Registers with Session Stats as an activity provider.
Tab title: Combat
"""

import time
from core.plugin_loader import BasePlugin
from core.activity import ActivityProviderMixin
from core.emit import Terminal, fmt_credits, fmt_duration, rate_per_hour, clip_name
from core.state import normalise_ship_name, RECENT_KILL_WINDOW

SUMMARY_INTERVAL_S  = 15 * 60   # emit session summary every 15 minutes


class ActivityCombatPlugin(BasePlugin, ActivityProviderMixin):
    PLUGIN_NAME         = "activity_combat"
    PLUGIN_DISPLAY      = "Combat Activity"
    PLUGIN_VERSION      = "1.0.0"
    PLUGIN_DESCRIPTION  = "Tracks kills, bounties, combat bonds, and deaths."
    ACTIVITY_TAB_TITLE  = "Combat"

    SUBSCRIBED_EVENTS = [
        "Bounty",
        "FactionKillBond",
        "Died",
        "FighterDestroyed",
        "Loadout",           # detect ship swap for no-kill timer reset
        "LoadGame",
        "Shutdown",
        "Music",
    ]

    DEFAULT_COL    = 8
    DEFAULT_ROW    = 0
    DEFAULT_WIDTH  = 8
    DEFAULT_HEIGHT = 5

    def on_load(self, core) -> None:
        super().on_load(core)
        core.register_block(self, priority=20)
        core.register_session_provider(self)
        self._reset_counters()          # also seeds _last_summary_mono etc.
        self._last_kill_mono:         float = 0.0
        self._inactivity_alerted:     bool  = False

    def _reset_counters(self) -> None:
        self.kills:            int   = 0
        self.bounty_total:     int   = 0
        self.bond_total:       int   = 0
        self.deaths:           int   = 0
        self.rebuy_paid:       int   = 0
        self.fighter_losses:   int   = 0
        self.faction_tally:    dict  = {}  # victimfaction → count
        self.ship_tally:       dict  = {}  # ship_name → count
        self.kill_interval_total: float = 0.0
        self.recent_kill_times:   list  = []
        self.last_kill_time         = None
        self.last_kill_mono: float  = 0.0
        self.session_start_time     = None
        self._last_summary_mono        = time.monotonic()  # reset clock on new session
        self._last_inactive_alert_mono = None
        self._last_rate_alert_mono     = None

    def on_session_reset(self) -> None:
        self._reset_counters()
        self._last_kill_mono = 0.0
        self._inactivity_alerted = False

    def on_event(self, event: dict, state) -> None:
        core     = self.core
        gq       = core.gui_queue
        notify   = core.notify_levels
        settings = core.app_settings
        ev       = event.get("event")
        logtime  = event.get("_logtime")
        max_trunc = settings.get("TruncateNames", 30)

        match ev:

            case "Bounty" | "FactionKillBond":
                self.kills += 1
                if self.session_start_time is None:
                    self.session_start_time = logtime

                thiskill = logtime
                if self.last_kill_time:
                    secs = (thiskill - self.last_kill_time).total_seconds()
                    self.kill_interval_total += secs
                    if len(self.recent_kill_times) >= RECENT_KILL_WINDOW:
                        self.recent_kill_times.pop(0)
                    self.recent_kill_times.append(secs)
                self.last_kill_time = thiskill
                if not state.in_preload:
                    self._last_kill_mono = time.monotonic()
                    self._inactivity_alerted = False

                if ev == "Bounty":
                    value = event.get("TotalReward") or event["Rewards"][0]["Reward"]
                    ship  = normalise_ship_name(
                        event.get("Target_Localised") or event.get("Target", "Unknown")
                    )
                    self.bounty_total += value
                    victim = event.get("VictimFaction_Localised") or event.get("VictimFaction", "")
                    reward_type = "bounty"
                else:
                    value = event["Reward"]
                    ship  = "Bond target"
                    self.bond_total += value
                    victim = event.get("Faction", "")
                    reward_type = "bond"

                self.faction_tally[victim] = self.faction_tally.get(victim, 0) + 1
                self.ship_tally[ship]      = self.ship_tally.get(ship, 0) + 1

                # Emit to terminal / Discord
                killtime_str = ""
                if len(self.recent_kill_times) > 0:
                    secs = self.recent_kill_times[-1]
                    killtime_str = f" (+{fmt_duration(secs)})"

                kills_t = f" x{self.kills}" if settings.get("ExtendedStats") else ""
                kills_d = f"x{self.kills} " if settings.get("ExtendedStats") else ""
                bv_str  = f" [{fmt_credits(value)} cr]" if settings.get("BountyValue") else ""
                pirate_str = (
                    f" [{clip_name(event['PilotName_Localised'], max_trunc)}]"
                    if "PilotName_Localised" in event and settings.get("PirateNames")
                    else ""
                )
                bf_str = ""
                if settings.get("BountyFaction") and victim:
                    fc = f" x{self.faction_tally[victim]}" if settings.get("ExtendedStats") else ""
                    bf_str = f" [{clip_name(victim, max_trunc)}{fc}]"

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

            case "Died":
                self.deaths += 1
                rebuy = event.get("Cost", 0)
                self.rebuy_paid += rebuy
                core.emitter.emit(
                    msg_term=f"{Terminal.BAD}Ship destroyed!{Terminal.END}"
                             + (f" (Rebuy: {fmt_credits(rebuy)} cr)" if rebuy else ""),
                    msg_discord="**Ship destroyed!**"
                                + (f" (Rebuy: {fmt_credits(rebuy)} cr)" if rebuy else ""),
                    emoji="💀", sigil="!! DEAD",
                    timestamp=logtime, loglevel=notify["Died"],
                )
                if gq: gq.put(("stats_update", None))

            case "FighterDestroyed":
                self.fighter_losses += 1
                if gq: gq.put(("stats_update", None))

            case "LoadGame":
                self._last_kill_mono = 0.0
                self._inactivity_alerted = False

            case "Shutdown" | "Music" if ev == "Music" and event.get("MusicTrack") == "MainMenu":
                pass  # no-kill timer pauses naturally — monotonic won't advance

    def _emit_summary(self, state) -> None:
        """Emit a 15-minute session summary to terminal and Discord.

        Uses the same data sources as the GUI so output is consistent.
        Duration comes from session_stats._session_start_time (the GUI
        clock). Rates are derived from that duration. Merits come from
        activity_powerplay. No legacy emit_summary() call.
        """
        if self.kills == 0:
            return

        core = self.core

        # Duration — from session_stats plugin (same source as GUI block)
        ss = core._plugins.get("session_stats")
        duration = ss.session_duration_seconds() if ss else 0.0

        # Rates
        credit_total = self.bounty_total + self.bond_total
        merits       = 0
        try:
            pp = core._plugins.get("activity_powerplay")
            if pp: merits = pp.merits_earned
        except Exception:
            pass

        kph = rate_per_hour(duration / self.kills        if self.kills        else 0, 1)
        bph = rate_per_hour(duration / credit_total      if credit_total      else 0, 2)
        mph = rate_per_hour(duration / merits            if merits            else 0, 1)

        dur_str = fmt_duration(int(duration))

        avg_interval = ""
        if self.kills > 1 and self.kill_interval_total > 0:
            avg_secs     = self.kill_interval_total / (self.kills - 1)
            avg_interval = f" | avg {fmt_duration(int(avg_secs))}/kill"

        sep = " | "
        summary_text = (
            f"Session Summary:\n"
            f"- Duration: {dur_str}\n"
            f"- Kills:    {self.kills:,}{sep}{kph:,} /hr{avg_interval}\n"
            f"- Bounties: {fmt_credits(credit_total)}{sep}{fmt_credits(bph)} /hr\n"
        )

        # Mission stack from state (unchanged — still authoritative there)
        if state.stack_value > 0:
            done      = state.missions_complete
            total     = len(state.active_missions)
            remaining = total - done
            complete_str = (
                "all complete — turn in!"
                if remaining == 0
                else f"{done}/{total} complete, {remaining} remaining"
            )
            summary_text += f"- Missions: {fmt_credits(state.stack_value)} stack ({complete_str})\n"

        if merits > 0:
            summary_text += f"- Merits:   {merits:,}{sep}{int(mph):,} /hr"
        else:
            summary_text = summary_text.rstrip("\n")

        core.emitter.emit(
            msg_term=summary_text,
            msg_discord=f"```{summary_text}```",
            emoji="📊",
            sigil="~  SUMM",
            timestamp=state.event_time,
            loglevel=2,
        )

    def tick(self, state) -> None:
        """Called every second. Handles:
        - periodic session summary (every 15 min)
        - inactivity alerts (WarnNoKills config)
        - no-kill timeout flush (QuitOnNoKillsMinutes config)
        """
        if not state.in_game:
            return

        now = time.monotonic()
        core = self.core
        cfg  = core.cfg
        settings = core.app_settings

        # ── Inactivity alert (WarnNoKills) ────────────────────────────────
        notify = core.notify_levels
        warn_no_kills  = settings.get("WarnNoKills",        20)
        warn_initial   = settings.get("WarnNoKillsInitial",  5)
        warn_cooldown  = settings.get("WarnCooldown",        15)
        if (
            notify.get("InactiveAlert", 3) > 0
            and self.session_start_time is not None
            and warn_no_kills > 0
            and not state.in_preload
        ):
            threshold_mins = warn_initial if self.kills == 0 else warn_no_kills
            last_kill_ref  = self._last_kill_mono if self._last_kill_mono > 0.0 \
                             else (self._last_summary_mono or now)
            cooldown_ok = (
                self._last_inactive_alert_mono is None
                or now - self._last_inactive_alert_mono >= warn_cooldown * 60
            )
            if cooldown_ok and now - last_kill_ref >= threshold_mins * 60:
                idle_dur = fmt_duration(int(now - last_kill_ref))
                core.emitter.emit(
                    msg_term=f"No kills in {idle_dur} — session may be inactive",
                    msg_discord=f"⚠️ **No kills in {idle_dur}** — session may be inactive",
                    emoji="⚠️", sigil="!  WARN",
                    timestamp=state.event_time,
                    loglevel=notify.get("InactiveAlert", 3),
                )
                self._last_inactive_alert_mono = now

        # ── Kill rate alert (WarnKillRate) ───────────────────────────────
        warn_rate = settings.get("WarnKillRate", 20)
        if (
            notify.get("RateAlert", 3) > 0
            and warn_rate > 0
            and self.kills >= 3
            and len(self.recent_kill_times) >= 3
        ):
            recent_avg_secs = (
                sum(self.recent_kill_times) / len(self.recent_kill_times)
            )
            recent_rate = 3600 / recent_avg_secs if recent_avg_secs > 0 else 0
            rate_cooldown_ok = (
                self._last_rate_alert_mono is None
                or now - self._last_rate_alert_mono >= warn_cooldown * 60
            )
            if rate_cooldown_ok and recent_rate < warn_rate:
                rate_fmt = f"{recent_rate:.1f}"
                core.emitter.emit(
                    msg_term=f"Kill rate low: {rate_fmt}/hr (threshold: {warn_rate}/hr)",
                    msg_discord=f"📉 **Kill rate low: {rate_fmt}/hr** (threshold: {warn_rate}/hr)",
                    emoji="📉", sigil="!  WARN",
                    timestamp=state.event_time,
                    loglevel=notify.get("RateAlert", 3),
                )
                self._last_rate_alert_mono = now

        # ── No-kill timeout (KSW/session flush) ───────────────────────────
        if self._inactivity_alerted:
            return
        if self._last_kill_mono == 0.0:
            return
        limit_minutes = cfg.pcfg("QuitOnNoKillsMinutes", 0)
        if not limit_minutes:
            return
        elapsed = (now - self._last_kill_mono) / 60
        if elapsed >= limit_minutes:
            self._inactivity_alerted = True
            try:
                core.plugin_call(
                    "session_manager", "flush_session",
                    f"No kills for {elapsed:.0f} min (threshold {limit_minutes} min)"
                )
            except Exception:
                pass

    # ── ActivityProviderMixin ─────────────────────────────────────────────────

    def has_activity(self) -> bool:
        return self.kills > 0 or self.deaths > 0 or self.fighter_losses > 0

    def _duration_seconds(self) -> float:
        if not self.session_start_time:
            return 0.0
        state = self.core.state
        if state.event_time:
            return (state.event_time - self.session_start_time).total_seconds()
        return 0.0

    def get_summary_rows(self) -> list[dict]:
        dur = self._duration_seconds()
        rows = []
        if self.kills > 0 or self.bounty_total > 0 or self.bond_total > 0:
            kills_rate = f"{rate_per_hour(dur / self.kills, 1)} /hr" if self.kills and dur else "—"
            rows.append({"label": "Kills",    "value": str(self.kills),
                         "rate": kills_rate})
            credit_total = self.bounty_total + self.bond_total
            if credit_total > 0:
                cr_rate = (f"{fmt_credits(rate_per_hour(dur / credit_total, 2))} /hr"
                           if dur else "—")
                label = "Bounties" if self.bounty_total >= self.bond_total else "Bonds"
                rows.append({"label": label, "value": fmt_credits(credit_total),
                             "rate": cr_rate})
        if self.deaths > 0:
            rebuy_str = f" ({fmt_credits(self.rebuy_paid)} cr)" if self.rebuy_paid else ""
            rows.append({"label": "Deaths", "value": str(self.deaths) + rebuy_str,
                         "rate": None})
        if self.fighter_losses > 0:
            rows.append({"label": "Fighter losses", "value": str(self.fighter_losses),
                         "rate": None})
        return rows

    def get_tab_rows(self) -> list[dict]:
        dur = self._duration_seconds()
        rows = self.get_summary_rows()
        # Ship kill breakdown
        if self.ship_tally:
            rows.append({"label": "─── Ships destroyed ───", "value": "", "rate": None})
            for ship, count in sorted(self.ship_tally.items(), key=lambda x: -x[1]):
                rows.append({"label": f"  {ship}", "value": str(count), "rate": None})
        # Faction tally
        if self.faction_tally and len(self.faction_tally) > 1:
            rows.append({"label": "─── Victim factions ───", "value": "", "rate": None})
            for faction, count in sorted(self.faction_tally.items(), key=lambda x: -x[1]):
                rows.append({"label": f"  {faction}", "value": str(count), "rate": None})
        return rows
