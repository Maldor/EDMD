"""
builtins/activity_exobiology/plugin.py — Exobiology session tracking.

Tracks organic samples logged and sold, with estimated and realised values.
ScanOrganic has three stages: Log, Sample, Analyse — Analyse is the completion.

Tab title: Exobiology
"""

from core.plugin_loader import BasePlugin
from core.activity import ActivityProviderMixin
from core.emit import fmt_credits


class ActivityExobiologyPlugin(BasePlugin, ActivityProviderMixin):
    PLUGIN_NAME         = "activity_exobiology"
    PLUGIN_DISPLAY      = "Exobiology Activity"
    PLUGIN_VERSION      = "1.0.0"
    PLUGIN_DESCRIPTION  = "Tracks organic samples and exobiology credits."
    ACTIVITY_TAB_TITLE  = "Exobiology"

    SUBSCRIBED_EVENTS = [
        "ScanOrganic",
        "SellOrganicData",
    ]

    def on_load(self, core) -> None:
        super().on_load(core)
        core.register_session_provider(self)
        self._reset_counters()

    def _reset_counters(self) -> None:
        self.samples_analysed: int  = 0   # completed analyses (stage=Analyse)
        self.credits_earned:   int  = 0   # from SellOrganicData
        self.species_tally:    dict = {}  # species → count
        self.session_start_time = None

    def on_session_reset(self) -> None:
        self._reset_counters()

    def on_event(self, event: dict, state) -> None:
        ev      = event.get("event")
        logtime = event.get("_logtime")
        gq      = self.core.gui_queue

        match ev:

            case "ScanOrganic":
                if event.get("ScanType") == "Analyse":
                    if self.session_start_time is None:
                        self.session_start_time = logtime
                    self.samples_analysed += 1
                    species = (
                        event.get("Species_Localised") or
                        event.get("Species", "Unknown")
                    ).strip()
                    self.species_tally[species] = (
                        self.species_tally.get(species, 0) + 1
                    )
                    if gq: gq.put(("stats_update", None))

            case "SellOrganicData":
                total = sum(
                    item.get("Value", 0)
                    for item in event.get("BioData", [])
                )
                self.credits_earned += total
                if gq: gq.put(("stats_update", None))

    # ── ActivityProviderMixin ─────────────────────────────────────────────────

    def has_activity(self) -> bool:
        return self.samples_analysed > 0

    def get_summary_rows(self) -> list[dict]:
        rows = []
        if self.samples_analysed > 0:
            rows.append({
                "label": "Samples analysed",
                "value": str(self.samples_analysed),
                "rate":  None,
            })
        if self.credits_earned > 0:
            rows.append({
                "label": "Exobio sold",
                "value": fmt_credits(self.credits_earned),
                "rate":  None,
            })
        return rows

    def get_tab_rows(self) -> list[dict]:
        rows = self.get_summary_rows()
        if self.species_tally:
            rows.append({"label": "─── Species ───", "value": "", "rate": None})
            for species, count in sorted(
                self.species_tally.items(), key=lambda x: -x[1]
            ):
                rows.append({
                    "label": f"  {species}",
                    "value": str(count),
                    "rate":  None,
                })
        return rows
