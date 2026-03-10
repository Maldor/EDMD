# EDMD Release Notes

---

## 20260309c

**Elite Dangerous Monitor Daemon — EDMD**

Patch release. All fixes target bugs introduced or exposed in 20260309b.

---

### Bug Fix — Materials Block Always Showing Empty

The Materials block displayed `— none —` in all three sections despite the
player having a full materials inventory.

Root cause: the ED journal startup sequence is `Fileheader → Commander →
Materials → Rank → Progress → LoadGame`. `Materials` (the authoritative full
snapshot) fires **before** `LoadGame`, not after. The plugin was subscribing to
`LoadGame` to pre-clear state ahead of the incoming snapshot — but that clear
executed **after** the only `Materials` event in the file, destroying the data
that had just been written. The block then read empty dicts for the rest of the
session.

Fix: `LoadGame` removed from the materials plugin's subscribed events entirely.
A new journal file (relog / new session) always opens with a fresh `Materials`
event which overwrites the previous data correctly.

---

### Bug Fix — EDAstro and EDSM: JSON Serialisation Failure on Every Send

Every outbound event sent to EDAstro and EDSM failed immediately with:

```
TypeError: Object of type datetime is not JSON serializable
```

The disk-queue fallback also failed with the same error, so no events were
being delivered and nothing was accumulating on disk.

Root cause: `handle_event` in `core/journal.py` injects `_logtime` (a Python
`datetime` object) into every event dict before dispatching to plugins. EDDN
explicitly strips this field when building each schema message — that is why
EDDN was unaffected. EDAstro and EDSM both passed the raw event dict directly
to `json.dumps` without removing it.

Fix: `_logtime` is now stripped at the `push()` call site in both plugins
before the event is handed to the sender thread.

---

### Upgrading from 20260309b

No config changes required. If EDAstro or EDSM were enabled in 20260309b, no
events were successfully delivered during that session. The disk-queue fallback
also failed, so there is nothing to replay. Both services will resume normal
uploads immediately on restart.

---

### Known Limitations (unchanged)

- SLF shield state is not tracked — the game does not expose this via journal
  or `Status.json`
- GTK4 GUI is Linux-only; Windows users have terminal and Discord output
- Inara integration is pending whitelist approval
