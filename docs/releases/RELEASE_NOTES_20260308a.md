# EDMD 20260308a

## What's New

### Kill Counter — Bottleneck Fix

The kill counter was over-counting required kills when missions had already met quota but not yet been turned in (`MissionRedirected`). Those missions were still included in the bottleneck calculation despite requiring no further kills, inflating the displayed total and producing a wrong remaining count.

The counter now correctly excludes redirected missions from the bottleneck sum. Only missions with kills still outstanding contribute to the target total.

---

### Kill Display — Remaining Count Only

The `credited / total` kill display format has been replaced with a single remaining count across all output channels — GUI sidebar, stack-full announcement, periodic summary, and the startup status block. The remaining count is the only number that matters and is now the only number shown.

---

### Not-In-Game Detection

EDMD now detects when the player is not in an active session and alerts on Discord (or terminal) at the highest configured notification level.

Detection uses the `Music: MainMenu` journal event as the primary signal, with a `Shutdown` event and a process check as supporting signals. A **5-minute startup grace** prevents false alerts when EDMD launches before the game client. A **15-minute grace after going to menu** covers brief interruptions without generating noise. Re-alerts hourly while the player remains offline. All periodic output is suppressed while not in game.

---

## Upgrading from 20260308

No config changes required. Run `edmd.py --upgrade` or use the Upgrade button in the GUI sidebar.
