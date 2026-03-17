"""
builtins/capi/plugin.py — Frontier CAPI integration for EDMD.

Architecture
------------
This plugin owns all communication with Frontier's Companion API.  Every
other builtin reads CAPI data exclusively through MonitorState — they never
call _http_get themselves.  When CAPI is disabled or unauthenticated, the
same state fields are populated from journal events and companion JSON files.

Raw data storage
----------------
state.capi_raw          dict  {endpoint: full_response_dict}
state.capi_last_poll    dict  {endpoint: unix_timestamp_float}

These are the canonical CAPI data store.  All extraction helpers read from
state.capi_raw, never from the HTTP response directly.  This means any
plugin can read state.capi_raw["profile"] and get the full Frontier response.

Supported endpoints
-------------------
  profile      /profile      — cmdr + current ship + fleet + modules + ranks
  market       /market       — full commodity list with buy/sell/mean prices
  shipyard     /shipyard     — ships available for purchase at current station
  fleetcarrier /fleetcarrier — carrier state, finance, capacity, services

Poll triggers
-------------
- On startup (after preload), after successful auth
- Docked, Undocked, CarrierJump, StoredShips, LoadGame journal events
  → full cycle (profile + carrier; market/shipyard only when docked)
- plugin_call("capi", "request_refresh", endpoint, min_age_s)
  → targeted refresh if endpoint is older than min_age_s seconds

Public plugin_call API
----------------------
  start_auth_flow()                    → "started" | "already_running"
  auth_status()                        → dict
  disconnect()
  manual_poll()
  request_refresh(endpoint, min_age_s) → bool (queued or skipped)
  get_raw(endpoint)                    → dict | None
  last_poll_time(endpoint)             → float  (0.0 if never polled)

GUI queue messages
------------------
  ("capi_updated", endpoint)    after each endpoint completes successfully
  ("plugin_refresh", "assets")  after profile poll
  ("plugin_refresh", "commander") after profile poll

Config [CAPI] in config.toml
-----------------------------
    Enabled = false   # opt-in; set True after authenticating
"""

import base64
import hashlib
import http.server
import json
import os
import queue
import secrets
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from core.plugin_loader import BasePlugin
from core.state import EDMD_DATA_DIR, VERSION

# ── Constants ──────────────────────────────────────────────────────────────────

PLUGIN_NAME    = "capi"
PLUGIN_VERSION = "2.0.0"

CLIENT_ID    = "25ae274d-d16b-45e5-bbf3-d143a401d1a7"
REDIRECT_URI = "https://drworman.github.io/EDMD/auth/callback"
AUTH_BASE    = "https://auth.frontierstore.net"
CAPI_BASE    = "https://companion.orerve.net"
SCOPE        = "auth capi"

AUTH_TIMEOUT_S          = 120
STARTUP_DELAY_S         = 10
TOKEN_REFRESH_MARGIN_S  = 60
HTTP_EXPIRED            = 422
TOKEN_FILE              = "tokens.json"

# Endpoint names
EP_PROFILE       = "profile"
EP_MARKET        = "market"
EP_SHIPYARD      = "shipyard"
EP_FLEETCARRIER  = "fleetcarrier"
EP_COMMUNITYGOALS= "communitygoals"

ALL_ENDPOINTS = [EP_PROFILE, EP_MARKET, EP_SHIPYARD, EP_FLEETCARRIER, EP_COMMUNITYGOALS]

EP_URLS = {
    EP_PROFILE:      f"{CAPI_BASE}/profile",
    EP_MARKET:       f"{CAPI_BASE}/market",
    EP_SHIPYARD:     f"{CAPI_BASE}/shipyard",
    EP_FLEETCARRIER: f"{CAPI_BASE}/fleetcarrier",
    EP_COMMUNITYGOALS: f"{CAPI_BASE}/communitygoals",
}

# Minimum seconds between polls per endpoint (hard rate-limit guard)
EP_COOLDOWN = {
    EP_PROFILE:      30,
    EP_MARKET:       60,
    EP_SHIPYARD:     60,
    EP_FLEETCARRIER: 30,
    EP_COMMUNITYGOALS: 300,   # CGs change slowly, 5-min cooldown
}


# ── PKCE helpers ───────────────────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _make_pkce() -> tuple[str, str]:
    verifier  = _b64url(secrets.token_bytes(64))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


# ── OAuth callback listener ────────────────────────────────────────────────────

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code   = params.get("code",  [None])[0]
        error  = params.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(
            b"Auth code received. You can close this tab." if code
            else b"Authentication failed. You can close this tab."
        )
        self.server._result_q.put(("code", code) if code else ("error", error or "unknown"))

    def log_message(self, fmt, *args):
        pass


def _listen_for_callback(port: int, result_q: queue.Queue, timeout: int) -> None:
    server = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server._result_q = result_q
    server.timeout   = timeout
    server.handle_request()
    server.server_close()


# ── Token I/O ──────────────────────────────────────────────────────────────────

def _save_tokens(storage, tokens: dict) -> None:
    try: storage.write_json(tokens, TOKEN_FILE)
    except Exception: pass

def _load_tokens(storage) -> dict:
    try:   return storage.read_json(TOKEN_FILE) or {}
    except Exception: return {}


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _http_post(url: str, data: dict, timeout: int = 20) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req  = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", f"EDMD/{VERSION}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _http_get(url: str, token: str, timeout: int = 20) -> dict:
    """GET with Bearer auth that survives redirects (urllib drops the header by default)."""
    class _AuthRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            r = super().redirect_request(req, fp, code, msg, headers, newurl)
            if r:
                r.add_unredirected_header("Authorization", f"Bearer {token}")
                r.add_unredirected_header("User-Agent", f"EDMD/{VERSION}")
            return r

    opener = urllib.request.build_opener(_AuthRedirect)
    req    = urllib.request.Request(url)
    req.add_unredirected_header("Authorization", f"Bearer {token}")
    req.add_unredirected_header("User-Agent", f"EDMD/{VERSION}")
    with opener.open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


# ── Plugin ─────────────────────────────────────────────────────────────────────

class CAPIPlugin(BasePlugin):
    """Frontier Companion API integration — single source of truth for fleet data."""

    PLUGIN_NAME        = "capi"
    PLUGIN_DISPLAY     = "Frontier CAPI"
    PLUGIN_VERSION     = PLUGIN_VERSION
    PLUGIN_DESCRIPTION = "Authoritative fleet, market, and carrier data from Frontier."
    BLOCK_WIDGET_CLASS = None

    SUBSCRIBED_EVENTS = [
        "Docked", "Undocked", "StoredShips",
        "LoadGame", "CarrierJump",
    ]

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def _trace(self, msg: str) -> None:
        if self.core and getattr(self.core, "trace_mode", False):
            print(f"  [CAPI] {msg}")

    def on_load(self, core) -> None:
        super().on_load(core)
        self.core = core

        self._tokens: dict              = {}
        self._last_refresh: float       = 0.0
        self._poll_queue: queue.Queue   = queue.Queue()
        self._auth_result               = None
        self._lock                      = threading.Lock()
        self._docked: bool              = False   # tracked to gate market/shipyard

        # Initialise state fields
        s = core.state
        if not hasattr(s, "capi_raw"):             s.capi_raw             = {}
        if not hasattr(s, "capi_community_goals"): s.capi_community_goals = []
        if not hasattr(s, "capi_last_poll"):   s.capi_last_poll   = {}   # {endpoint: timestamp}
        if not hasattr(s, "capi_ranks"):       s.capi_ranks       = None
        if not hasattr(s, "capi_progress"):    s.capi_progress    = None
        if not hasattr(s, "capi_reputation"):  s.capi_reputation  = None
        if not hasattr(s, "capi_engineer_ranks"): s.capi_engineer_ranks = None
        if not hasattr(s, "capi_market"):      s.capi_market      = None  # processed commodity list
        if not hasattr(s, "capi_shipyard"):    s.capi_shipyard    = None  # processed ship list
        if not hasattr(s, "capi_ship_health"): s.capi_ship_health = None  # {hull, shields, paintwork}
        if not hasattr(s, "capi_ship_value"):  s.capi_ship_value  = None  # {hull, modules, cargo, total, free}
        if not hasattr(s, "capi_loadout"):     s.capi_loadout     = None  # full fitted modules from CAPI
        if not hasattr(s, "capi_permits"):     s.capi_permits     = []
        if not hasattr(s, "capi_statistics"):  s.capi_statistics  = None  # full Statistics object

        loaded = _load_tokens(self.storage)
        if loaded.get("scope", SCOPE) != SCOPE:
            self._trace("Discarding tokens from old scope — re-authenticate")
            loaded = {}
        self._tokens = loaded

        threading.Thread(target=self._poll_worker, daemon=True, name="capi-poll").start()
        threading.Timer(STARTUP_DELAY_S, self._enqueue, args=(None, False)).start()

    def on_unload(self) -> None:
        self._poll_queue.put(None)

    def on_event(self, event: dict, state) -> None:
        ev = event.get("event")
        if ev == "Docked":
            self._docked = True
            self._enqueue(None, False)
        elif ev in ("Undocked",):
            self._docked = False
            self._enqueue(EP_PROFILE, False)
        elif ev in ("StoredShips", "LoadGame", "CarrierJump"):
            self._enqueue(None, False)

    # ── Public plugin_call API ─────────────────────────────────────────────────

    def start_auth_flow(self) -> str:
        with self._lock:
            if self._auth_result is not None:
                return "already_running"
            self._auth_result = queue.Queue()
        threading.Thread(target=self._run_auth_flow, daemon=True, name="capi-auth").start()
        return "started"

    def auth_status(self) -> dict:
        with self._lock:
            running = self._auth_result is not None
        t = self._tokens
        if running:
            st = "auth_running"
        elif t.get("access_token"):
            st = "connected" if time.time() < t.get("expiry", 0) - TOKEN_REFRESH_MARGIN_S else "expired"
        else:
            st = "none"
        return {
            "state":      st,
            "cmdr":       t.get("cmdr"),
            "expiry":     t.get("expiry"),
            "last_polls": dict(getattr(self.core.state, "capi_last_poll", {})),
        }

    def disconnect(self) -> None:
        self._tokens = {}
        _save_tokens(self.storage, {})

    def manual_poll(self) -> None:
        """Force a full poll cycle immediately, bypassing cooldowns."""
        s = self.core.state
        s.capi_last_poll = {}    # clear timestamps so cooldowns don't block
        self._enqueue(None, True)

    def request_refresh(self, endpoint: str, min_age_s: float = 60) -> bool:
        """
        Request a targeted refresh of one endpoint.  Queued only if the last
        poll for that endpoint is older than min_age_s seconds.
        Returns True if queued, False if skipped (too recent).
        """
        if endpoint not in EP_URLS:
            return False
        last = self.core.state.capi_last_poll.get(endpoint, 0.0)
        if time.time() - last < min_age_s:
            return False
        self._enqueue(endpoint, False)
        return True

    def get_raw(self, endpoint: str) -> dict | None:
        """Return the last raw API response for an endpoint, or None."""
        return self.core.state.capi_raw.get(endpoint)

    def last_poll_time(self, endpoint: str) -> float:
        """Return the unix timestamp of the last successful poll, or 0.0."""
        return self.core.state.capi_last_poll.get(endpoint, 0.0)

    # ── Auth flow ──────────────────────────────────────────────────────────────

    def _run_auth_flow(self) -> None:
        try:
            verifier, challenge = _make_pkce()
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
            nonce = secrets.token_hex(8)
            state = f"{port}:{nonce}"
            auth_url = (
                f"{AUTH_BASE}/auth?response_type=code&client_id={CLIENT_ID}"
                f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
                f"&scope={SCOPE}&code_challenge={challenge}"
                f"&code_challenge_method=S256&state={state}"
            )
            cb_q: queue.Queue = queue.Queue()
            threading.Thread(target=_listen_for_callback,
                             args=(port, cb_q, AUTH_TIMEOUT_S), daemon=True).start()
            webbrowser.open(auth_url)
            try:
                kind, value = cb_q.get(timeout=AUTH_TIMEOUT_S + 5)
            except queue.Empty:
                self._finish_auth("timeout"); return
            if kind == "error" or not value:
                self._finish_auth("error"); return

            resp = _http_post(f"{AUTH_BASE}/token", {
                "grant_type": "authorization_code", "client_id": CLIENT_ID,
                "code": value, "redirect_uri": REDIRECT_URI, "code_verifier": verifier,
            })
            at = resp.get("access_token")
            if not at:
                self._finish_auth("error"); return

            cmdr = None
            try:
                me   = _http_get(f"{AUTH_BASE}/decode", at)
                cmdr = me.get("usr", {}).get("firstname") or me.get("customer_id")
            except Exception:
                pass

            self._tokens = {
                "access_token":  at,
                "refresh_token": resp.get("refresh_token"),
                "expiry":        time.time() + resp.get("expires_in", 7200),
                "cmdr":          cmdr,
                "scope":         SCOPE,
            }
            _save_tokens(self.storage, self._tokens)
            self._finish_auth("ok")
            self.manual_poll()
        except Exception as exc:
            self._trace(f"Auth flow error: {exc}")
            self._finish_auth("error")

    def _finish_auth(self, result: str) -> None:
        with self._lock:
            self._auth_result = None
        gq = self.core.gui_queue if self.core else None
        if gq: gq.put(("plugin_refresh", "capi"))

    # ── Token management ──────────────────────────────────────────────────────

    def _refresh_token(self) -> bool:
        rt = self._tokens.get("refresh_token")
        if not rt:
            return False
        try:
            resp = _http_post(f"{AUTH_BASE}/token", {
                "grant_type": "refresh_token", "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI, "refresh_token": rt,
            })
            at = resp.get("access_token")
            if not at:
                self._trace(f"Refresh gave no access_token: {resp}")
                return False
            self._tokens.update({
                "access_token":  at,
                "refresh_token": resp.get("refresh_token", rt),
                "expiry":        time.time() + resp.get("expires_in", 7200),
            })
            _save_tokens(self.storage, self._tokens)
            self._trace("Token refreshed")
            return True
        except urllib.error.HTTPError as e:
            if e.code in (400, 401):
                self._trace(f"Refresh rejected (HTTP {e.code}) — clearing tokens")
                self._tokens = {}
                _save_tokens(self.storage, {})
            return False
        except Exception as exc:
            self._trace(f"Refresh error: {exc}")
            return False

    def _valid_token(self) -> str | None:
        t  = self._tokens
        at = t.get("access_token")
        if not at:
            return None
        if time.time() > t.get("expiry", 0) - TOKEN_REFRESH_MARGIN_S:
            if not self._refresh_token():
                return None
            at = self._tokens.get("access_token")
        return at

    # ── Poll worker ────────────────────────────────────────────────────────────

    def _enqueue(self, endpoint_or_none, force: bool) -> None:
        try:
            self._poll_queue.put_nowait((endpoint_or_none, force))
        except queue.Full:
            pass

    def _poll_worker(self) -> None:
        while True:
            item = self._poll_queue.get()
            if item is None:
                break
            # Drain duplicates
            pending = [item]
            while True:
                try:
                    pending.append(self._poll_queue.get_nowait())
                except queue.Empty:
                    break
            # Deduplicate: keep last request per endpoint; None = full cycle
            seen = {}
            for req in pending:
                ep, force = req
                seen[ep] = force or seen.get(ep, False)

            token = self._valid_token()
            if not token:
                self._trace("Poll skipped — no valid token")
                continue

            if None in seen:
                # Full cycle
                self._do_full_cycle(token, force=seen[None])
            else:
                for ep, force in seen.items():
                    self._do_single(token, ep, force)

    def _elapsed_ok(self, endpoint: str, force: bool) -> bool:
        if force:
            return True
        last = self.core.state.capi_last_poll.get(endpoint, 0.0)
        return (time.time() - last) >= EP_COOLDOWN[endpoint]

    def _do_full_cycle(self, token: str, force: bool = False) -> None:
        """Poll profile (always) + market/shipyard (docked only) + carrier."""
        self._do_single(token, EP_PROFILE, force)
        if self._docked:
            self._do_single(token, EP_MARKET,   force)
            self._do_single(token, EP_SHIPYARD,  force)
        self._do_single(token, EP_FLEETCARRIER,    force)
        self._do_single(token, EP_COMMUNITYGOALS, force)

    def _do_single(self, token: str, endpoint: str, force: bool = False) -> None:
        """Fetch one endpoint, store raw, extract to state, notify GUI."""
        if not self._elapsed_ok(endpoint, force):
            self._trace(f"Skipping {endpoint} — within cooldown")
            return

        url = EP_URLS[endpoint]
        self._trace(f"Polling {endpoint}")
        try:
            data = _http_get(url, token)
        except urllib.error.HTTPError as e:
            if e.code == 404 and endpoint in (EP_FLEETCARRIER, EP_COMMUNITYGOALS):
                return   # 404 = no carrier / no active CGs — not an error
            if e.code in (HTTP_EXPIRED, 401):
                since = time.time() - self._last_refresh
                if since < 60:
                    self._trace(f"401 on {endpoint}, refreshed {since:.0f}s ago — backing off")
                    return
                self._trace(f"Token expired on {endpoint} — refreshing")
                if self._refresh_token():
                    self._last_refresh = time.time()
                    new_token = self._tokens.get("access_token")
                    if new_token:
                        try:
                            data = _http_get(url, new_token)
                        except Exception as exc2:
                            self._trace(f"{endpoint} failed after refresh: {exc2}")
                            return
                    else:
                        return
                else:
                    gq = self.core.gui_queue
                    if gq: gq.put(("plugin_refresh", "capi"))
                    return
            else:
                self._trace(f"{endpoint} HTTP {e.code}")
                return
        except Exception as exc:
            self._trace(f"{endpoint} error: {exc}")
            return

        if not data:
            return

        # Store raw and timestamp
        s = self.core.state
        s.capi_raw[endpoint]       = data
        s.capi_last_poll[endpoint] = time.time()
        # Persist raw response immediately so it survives restarts
        try:
            self.storage.write_json(data, f"capi_{endpoint}.json")
        except Exception:
            pass
        self._trace(f"{endpoint} stored ({len(str(data))} chars)")

        # Extract to MonitorState
        try:
            extractor = getattr(self, f"_extract_{endpoint.replace('/', '_')}", None)
            if extractor:
                extractor(data, s)
        except Exception as exc:
            self._trace(f"{endpoint} extraction error: {exc}")

        # Notify
        gq = self.core.gui_queue
        if gq:
            gq.put(("capi_updated", endpoint))
            if endpoint == EP_PROFILE:
                gq.put(("plugin_refresh", "assets"))
                gq.put(("plugin_refresh", "commander"))
            elif endpoint in (EP_MARKET, EP_SHIPYARD):
                gq.put(("plugin_refresh", "assets"))
                gq.put(("plugin_refresh", "cargo"))

        # Push authoritative credits to Inara after profile
        if endpoint == EP_COMMUNITYGOALS:
            self._extract_communitygoals(data, s)

        if endpoint == EP_PROFILE:
            bal = getattr(s, "assets_balance", None)
            if bal is not None:
                try:
                    self.core.plugin_call("inara", "push_credits", int(bal))
                except Exception:
                    pass

    # ── Extractors — one per endpoint ─────────────────────────────────────────

    @staticmethod
    def _capi_hull_pct(raw) -> int:
        h = float(raw) if raw is not None else 1000000
        return round(h / 10000) if h > 1.0 else round(h * 100)

    def _extract_profile(self, data: dict, state) -> None:
        from core.state import normalise_ship_name as _norm_ship

        def _make_loadout_list(modules_dict: dict) -> list:
            """Convert CAPI /profile ship modules dict to a display-ready list.

            CAPI structure per slot:
              {"module": {name, locName, health, on, priority, value},
               "engineer": {recipeName, recipeLocName, recipeLevel},
               "WorkInProgress_modifications": {stat: {value, LessIsGood, locName}},
               "specialModifications": {effect_key: effect_key}}
            """
            from builtins.assets.plugin import normalise_module_name as _nmn
            result = []
            for sl, sm in (modules_dict or {}).items():
                mod = sm.get("module") or sm  # handle both nested and flat
                mi   = mod.get("name", "")
                disp = mod.get("locName") or _nmn(mi)
                eng_raw = sm.get("engineer") or {}
                exp_raw = sm.get("specialModifications") or {}
                eng = {}
                if eng_raw.get("recipeName"):
                    eng["BlueprintName"] = eng_raw["recipeName"]
                    eng["Level"]         = int(eng_raw.get("recipeLevel", 0))
                    eng["Quality"]       = 1.0
                    eng["BlueprintLocName"] = eng_raw.get("recipeLocName", "")
                    # Experimental effect: first key of specialModifications
                    if exp_raw:
                        eng["ExperimentalEffect"] = next(iter(exp_raw))
                result.append({
                    "slot":          sl,
                    "name_internal": mi,
                    "name_display":  disp,
                    "on":            bool(mod.get("on", True)),
                    "priority":      int(mod.get("priority", 0)),
                    "value":         int(mod.get("value", 0)),
                    "health":        int(mod.get("health", 1000000)),
                    "engineering":   eng,
                })
            return result

        """Extract /profile → multiple MonitorState fields."""
        cmdr    = data.get("commander") or {}
        ship    = data.get("ship")      or {}
        ships   = data.get("ships")     or {}
        modules = data.get("modules")   or {}

        # ── Credits / wealth ──────────────────────────────────────────────────
        bal = cmdr.get("credits")
        if bal is not None:
            state.assets_balance = float(bal)
        debt = cmdr.get("debt")
        if debt is not None:
            state.capi_debt = float(debt)

        # ── Ranks / progress / reputation / engineers ─────────────────────────
        raw_ranks    = cmdr.get("rank",     {})
        raw_progress = cmdr.get("progress", {})
        raw_rep      = cmdr.get("reputation", {})
        raw_eng      = cmdr.get("engineerProgress", [])
        raw_stats    = cmdr.get("statistics")
        raw_permits  = cmdr.get("permits",  [])

        if raw_ranks:
            state.capi_ranks    = {k: int(v) for k, v in raw_ranks.items()
                                   if isinstance(v, (int, float))}
        if raw_progress:
            state.capi_progress = {k: int(v) for k, v in raw_progress.items()
                                   if isinstance(v, (int, float))}
        if raw_rep:
            state.capi_reputation = {k: float(v) for k, v in raw_rep.items()
                                     if isinstance(v, (int, float))}
        if isinstance(raw_eng, list) and raw_eng:
            state.capi_engineer_ranks = [
                {
                    "name":     e.get("Engineer", ""),
                    "rank":     e.get("Rank"),
                    "progress": e.get("RankProgress"),
                    "unlocked": e.get("Rank") is not None,
                }
                for e in raw_eng if isinstance(e, dict)
            ]
        if raw_stats:
            state.capi_statistics = raw_stats
        if isinstance(raw_permits, list):
            state.capi_permits = raw_permits

        # Squadron data
        sq = data.get("squadron") or {}
        state.pilot_squadron_name = sq.get("name", "")
        state.pilot_squadron_tag  = sq.get("tag", "")
        state.pilot_squadron_rank = sq.get("rank", "")

        # ── Current ship ──────────────────────────────────────────────────────
        if ship:
            ship_type   = ship.get("name",          "")
            ship_type_l = ship.get("nameLocalized")  or ship_type
            health_obj  = ship.get("health",         {})
            value_obj   = ship.get("value",          {})
            location    = ship.get("starsystem",     {})

            state.capi_ship_health = {
                "hull":      health_obj.get("hull",      100.0),   # 0.0–1.0
                "shields":   health_obj.get("shieldup",  True),
                "paintwork": health_obj.get("paintwork", 1.0),
            }
            state.capi_ship_value = {
                "hull":    value_obj.get("hull",    0),
                "modules": value_obj.get("modules", 0),
                "cargo":   value_obj.get("cargo",   0),
                "total":   value_obj.get("total",   0),
                "free":    value_obj.get("free",    0),   # rebuy cost
            }

            # Propagate hull + shield to live state fields so Commander block
            # reflects CAPI values immediately, before journal events arrive.
            hull_raw = health_obj.get("hull")
            if hull_raw is not None:
                # CAPI encodes hull on a 0–1 000 000 integer scale (1 000 000 = 100%).
                # Divide by 10 000 to get percentage. If the value is already ≤ 1.0
                # (some CAPI versions return a float fraction), multiply by 100 instead.
                hf = float(hull_raw)
                state.ship_hull = round(hf / 10000) if hf > 1.0 else round(hf * 100)
            shields_up = health_obj.get("shieldup")
            if shields_up is not None:
                state.ship_shields = bool(shields_up)
                if bool(shields_up):
                    state.ship_shields_recharging = False

            # Full fitted loadout from CAPI (slot → module dict with eng info)
            fitted = ship.get("modules") or {}
            state.capi_loadout = fitted   # raw for third-party plugin access

            state.assets_current_ship = {
                "_key":         "current",
                "current":      True,
                "ship_id":      ship.get("id"),
                "type":         ship_type,
                "type_display": ship_type_l,
                "name":         ship.get("shipName",  ""),
                "ident":        ship.get("shipIdent", ""),
                "system":       (location.get("name") if isinstance(location, dict)
                                 else getattr(state, "pilot_system", None)) or "—",
                "value":        value_obj.get("hull", 0),
                "hull":         (lambda h: round(h / 10000) if h > 1.0 else round(h * 100))
                                (float(health_obj.get("hull", 1000000))),
                "rebuy":        value_obj.get("free", 0),
                "capi":         True,
                "loadout":      _make_loadout_list(fitted),
            }

        # ── Rebuild stored fleet from CAPI ────────────────────────────────────
        # CAPI /profile ships{} is the authoritative source — it has complete
        # module loadouts, hull health, and rebuy costs for every owned ship.
        # We build each ship fully from CAPI, then layer in journal data
        # (StarSystem location, Hot status) which CAPI may not carry.
        current_id = (state.assets_current_ship or {}).get("ship_id")

        # Collect journal location/hot data by ship_id for enrichment
        journal_extra: dict = {}
        for existing_ship in getattr(state, "assets_stored_ships", []):
            sid = existing_ship.get("ship_id")
            if sid is not None:
                journal_extra[sid] = {
                    "system": existing_ship.get("system", "—"),
                    "hot":    existing_ship.get("hot", False),
                }

        # Build new stored fleet from CAPI
        stored = []
        for sid_str, sv in ships.items():
            try:   sid = int(sid_str)
            except Exception: sid = sid_str
            if sid == current_id:
                continue
            val   = sv.get("value") or {}
            sv_h  = sv.get("health") or {}
            sv_hr = float(sv_h.get("hull", 1000000))
            hull_pct = round(sv_hr / 10000) if sv_hr > 1.0 else round(sv_hr * 100)
            loc  = sv.get("starsystem") or {}
            capi_sys = loc.get("name", "—") if isinstance(loc, dict) else "—"
            # Prefer journal system (has exact StarSystem) over CAPI starsystem
            jx  = journal_extra.get(sid, {})
            sys_n = jx.get("system", "—") if jx.get("system", "—") != "—" else capi_sys
            stored.append({
                "_key":         f"ship_{sid}",
                "ship_id":      sid,
                "current":      False,
                "type":         sv.get("name", ""),
                "type_display": sv.get("nameLocalized") or _norm_ship(sv.get("name", "")),
                "name":         sv.get("shipName",  ""),
                "ident":        sv.get("shipIdent", ""),
                "system":       sys_n,
                "value":        val.get("hull", 0),
                "rebuy":        val.get("free", 0),
                "hull":         hull_pct,
                "hot":          jx.get("hot", False),
                "loadout":      _make_loadout_list(sv.get("modules") or {}),
                "capi":         True,
            })
        if stored:
            state.assets_stored_ships = stored

        # Persist fleet to disk so next startup loads it immediately
        # without waiting for CAPI to re-poll (10s delay).
        try:
            cur_snap = state.assets_current_ship
            self.storage.write_json({
                "current_ship":  cur_snap,
                "stored_ships":  stored,
            }, "fleet.json")
        except Exception:
            pass

        # Enrich current ship with CAPI hull/rebuy/loadout/ident
        cur = state.assets_current_ship
        if cur:
            capi_cur = ships.get(str(current_id)) or ships.get(current_id)
            if capi_cur:
                c_val  = capi_cur.get("value") or {}
                c_h    = capi_cur.get("health") or {}
                c_hr   = float(c_h.get("hull", 1000000))
                cur["hull"]    = round(c_hr / 10000) if c_hr > 1.0 else round(c_hr * 100)
                cur["rebuy"]   = c_val.get("free", 0)
                cur["loadout"] = _make_loadout_list(capi_cur.get("modules") or {})
                if not cur.get("ident") and capi_cur.get("shipIdent"):
                    cur["ident"] = capi_cur["shipIdent"]
                if not cur.get("name") and capi_cur.get("shipName"):
                    cur["name"] = capi_cur["shipName"]

        # ── Stored modules (at station) ───────────────────────────────────────
        if isinstance(modules, dict) and modules:
            mods = []
            for i, (slot, m) in enumerate(modules.items()):
                internal = m.get("name",          "")
                disp     = m.get("nameLocalized") or internal
                mods.append({
                    "_key":          f"{i}_{internal}",
                    "name_internal": internal,
                    "name_display":  disp,
                    "slot":          slot,
                    "system":        "—",
                    "mass":          m.get("mass",  0.0),
                    "value":         m.get("value", 0),
                    "hot":           False,
                })
            if mods:
                state.assets_stored_modules = mods

    def _extract_communitygoals(self, data: dict, state) -> None:
        """Extract /communitygoals → state.capi_community_goals."""
        goals = data if isinstance(data, list) else data.get("communityGoals", [])
        state.capi_community_goals = [
            {
                "id":          g.get("id"),
                "title":       g.get("title", ""),
                "expiry":      g.get("expiry", ""),
                "system":      g.get("starsystem", ""),
                "station":     g.get("market", {}).get("name", "") if isinstance(g.get("market"), dict) else "",
                "objective":   g.get("objective", ""),
                "description": g.get("description", ""),
                "target_tier": g.get("targetTier", 0),
                "current_tier":g.get("tierReached", 0),
                "player_contribution": g.get("contribution", 0),
                "player_reward":       g.get("reward", 0),
            }
            for g in (goals if isinstance(goals, list) else [])
        ]

    def _extract_market(self, data: dict, state) -> None:
        """Extract /market → state.capi_market + update cargo mean prices."""
        items = data.get("commodities") or []
        if not isinstance(items, list):
            # Some API versions nest under "items"
            items = data.get("items") or []

        processed = {}
        for c in items:
            key = (c.get("name") or "").lower()
            if not key:
                continue
            processed[key] = {
                "name":          c.get("name",          key),
                "name_local":    c.get("displayName")   or c.get("name", key),
                "buy_price":     int(c.get("buyPrice",  0)),
                "sell_price":    int(c.get("sellPrice", 0)),
                "mean_price":    int(c.get("meanPrice", 0)),
                "stock":         int(c.get("stock",     0)),
                "demand":        int(c.get("demand",    0)),
                "category":      c.get("categoryname", ""),
                "rare":          bool(c.get("rare",     False)),
            }

        state.capi_market = {
            "station_name": data.get("name",      ""),
            "market_id":    data.get("id",          0),
            "star_system":  data.get("starsystem", ""),
            "commodities":  processed,
        }

        # Propagate mean prices to cargo state so value column updates
        mean_prices = {k: v["mean_price"] for k, v in processed.items() if v["mean_price"]}
        if mean_prices:
            state.cargo_mean_prices = mean_prices
        self._trace(f"market: {len(processed)} commodities at {data.get('name', '?')}")

    def _extract_shipyard(self, data: dict, state) -> None:
        """Extract /shipyard → state.capi_shipyard."""
        ships_raw = data.get("ships") or {}
        ships_list = []
        if isinstance(ships_raw, dict):
            for sid, sv in ships_raw.items():
                ships_list.append({
                    "type":      sv.get("name",          ""),
                    "name_local":sv.get("nameLocalized") or sv.get("name", ""),
                    "price":     int(sv.get("basevalue", 0)),
                })
        state.capi_shipyard = {
            "station_name": data.get("name",      ""),
            "market_id":    data.get("id",          0),
            "ships":        ships_list,
        }
        self._trace(f"shipyard: {len(ships_list)} ships at {data.get('name', '?')}")

    def _extract_fleetcarrier(self, data: dict, state) -> None:
        """Extract /fleetcarrier → state.assets_carrier."""

        def _int(v):
            try: return int(v)
            except Exception: return 0

        def _pct(v):
            try: return round(float(v), 1)
            except Exception: return 0.0

        def _decode_vanity(s: str) -> str:
            try:    return bytes.fromhex(s).decode("ascii").strip()
            except Exception: return s

        name_obj   = data.get("name") or {}
        callsign   = name_obj.get("callsign") or data.get("callsign") or "—"
        raw_vanity = name_obj.get("vanityName") or name_obj.get("filteredVanityName") or ""
        carrier_name = _decode_vanity(raw_vanity) if raw_vanity else callsign

        fin     = data.get("finance") or {}
        cap     = data.get("capacity") or {}
        mkt     = data.get("market") or {}
        tax     = fin.get("service_taxation") or {}

        bank_bal  = _int(fin.get("bankBalance",         0))
        bank_res  = _int(fin.get("bankReservedBalance",  0))
        services  = {}
        raw_svcs  = mkt.get("services") or {}
        if isinstance(raw_svcs, dict):
            services = dict(raw_svcs)

        crew_space  = _int(cap.get("crew",           0))
        free_space  = _int(cap.get("freeSpace",      0))
        cargo_sale  = _int(cap.get("cargoForSale",   0))
        cargo_nosale= _int(cap.get("cargoNotForSale", 0))
        cargo_res   = _int(cap.get("cargoSpaceReserved", 0))

        state.assets_carrier = {
            "callsign":        callsign,
            "name":            carrier_name,
            "system":          data.get("currentStarSystem", "—"),
            "theme":           data.get("theme",   "—"),
            "fuel":            _int(data.get("fuel", 0)),
            "carrier_state":   data.get("state",   "—"),
            "docking":         data.get("dockingAccess") or "—",
            "notorious":       bool(data.get("notoriousAccess", False)),
            "balance":         bank_bal,
            "reserve":         bank_res,
            "available":       bank_bal - bank_res,
            "tax_refuel":      _pct(tax.get("refuel",          0)),
            "tax_repair":      _pct(tax.get("repair",          0)),
            "tax_rearm":       _pct(tax.get("rearm",           0)),
            "tax_pioneer":     _pct(tax.get("pioneersupplies", 0)),
            "maintenance":     _int(fin.get("maintenance",       0)),
            "maintenance_wtd": _int(fin.get("maintenanceToDate", 0)),
            "cargo_total":     crew_space + free_space,
            "cargo_crew":      crew_space,
            "cargo_used":      cargo_sale + cargo_nosale + cargo_res,
            "cargo_free":      free_space,
            "ship_packs":      _int(cap.get("shipPacks",   0)),
            "module_packs":    _int(cap.get("modulePacks", 0)),
            "micro_total":     _int(cap.get("microresourceCapacityTotal", 0)),
            "micro_free":      _int(cap.get("microresourceCapacityFree",  0)),
            "micro_used":      _int(cap.get("microresourceCapacityUsed",  0)),
            "services":        services,
            "capi":            True,
        }

        # Write diagnostic dump
        try:
            import builtins as _bi
            dump = EDMD_DATA_DIR / "fleetcarrier_dump.json"
            _bi.open(dump, "w").write(json.dumps(data, indent=2, default=str))
        except Exception:
            pass
