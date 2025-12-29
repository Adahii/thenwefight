import sqlite3
import random
import string
import requests
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import streamlit as st

# ----------------------------
# Page + Theme
# ----------------------------
st.set_page_config(
    page_title="ThenWeFight Draft",
    page_icon="🎮",
    layout="wide",
)

CUSTOM_CSS = """
<style>
/* Modern dark look */
:root {
  --bg: #0b1020;
  --card: rgba(255,255,255,0.06);
  --card2: rgba(255,255,255,0.04);
  --border: rgba(255,255,255,0.10);
  --text: rgba(255,255,255,0.90);
  --muted: rgba(255,255,255,0.65);
  --accent: #7c5cff;
  --good: #2ecc71;
  --warn: #f39c12;
  --bad: #e74c3c;
}

html, body, [data-testid="stAppViewContainer"] {
  background: radial-gradient(1200px 800px at 10% 10%, rgba(124,92,255,0.25), rgba(0,0,0,0)) ,
              radial-gradient(900px 700px at 90% 20%, rgba(46,204,113,0.18), rgba(0,0,0,0)) ,
              linear-gradient(180deg, #050816, #060818);
  color: var(--text);
}

h1, h2, h3, h4 { letter-spacing: -0.02em; }

.block-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 16px 16px;
}

.badge {
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding:6px 10px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 999px;
  font-size: 12px;
  color: var(--muted);
  margin-right: 6px;
}

.pill-good { background: rgba(46,204,113,0.18); border-color: rgba(46,204,113,0.35); color: rgba(255,255,255,0.9); }
.pill-warn { background: rgba(243,156,18,0.18); border-color: rgba(243,156,18,0.35); color: rgba(255,255,255,0.9); }
.pill-bad  { background: rgba(231,76,60,0.18); border-color: rgba(231,76,60,0.35); color: rgba(255,255,255,0.9); }

hr { border-color: rgba(255,255,255,0.10) !important; }

.small-muted { color: var(--muted); font-size: 13px; }

.poke-name { font-weight: 700; font-size: 14px; margin-top: 8px; }

.poke-img {
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.03);
  padding: 10px;
}

.feed-item {
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.04);
  margin-bottom: 8px;
}

/* Reveal animations */
.reveal-wrap {
  display:flex;
  justify-content:center;
  align-items:center;
  padding: 14px;
}
.reveal-card {
  width: min(520px, 100%);
  border-radius: 18px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.05);
  padding: 16px;
  text-align:center;
}
.reveal-img {
  width: min(380px, 100%);
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(0,0,0,0.20);
  padding: 10px;
}
.truth-pulse {
  animation: truthPulse 1.8s ease-in-out 0s 1;
}
@keyframes truthPulse {
  0%   { box-shadow: 0 0 0 rgba(46,204,113,0.0); transform: scale(1.0); }
  15%  { box-shadow: 0 0 24px rgba(46,204,113,0.55); transform: scale(1.01); }
  35%  { box-shadow: 0 0 0 rgba(46,204,113,0.0); transform: scale(1.0); }
  55%  { box-shadow: 0 0 24px rgba(46,204,113,0.55); transform: scale(1.01); }
  75%  { box-shadow: 0 0 0 rgba(46,204,113,0.0); transform: scale(1.0); }
  100% { box-shadow: 0 0 0 rgba(46,204,113,0.0); transform: scale(1.0); }
}
.lie-stage {
  position: relative;
  width: min(380px, 100%);
  margin: 0 auto;
}
.lie-stage img {
  width: 100%;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(0,0,0,0.20);
  padding: 10px;
  display:block;
}
.lie-img-shown { position:absolute; top:0; left:0; opacity:1; animation: fadeOut 2.2s ease-in-out 0.6s forwards; }
.lie-img-real  { position:relative; opacity:0; animation: fadeIn 2.2s ease-in-out 0.6s forwards; }
@keyframes fadeOut { to { opacity: 0; transform: scale(0.99); } }
@keyframes fadeIn  { to { opacity: 1; transform: scale(1.01); } }

.pick-flash-green {
  animation: pickFlash 0.9s ease-in-out 0s infinite;
}
@keyframes pickFlash {
  0%   { box-shadow: 0 0 0 rgba(46,204,113,0.0); transform: translateY(0px); }
  50%  { box-shadow: 0 0 26px rgba(46,204,113,0.55); transform: translateY(-1px); }
  100% { box-shadow: 0 0 0 rgba(46,204,113,0.0); transform: translateY(0px); }
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ----------------------------
# Constants
# ----------------------------
ICONS = ["🎩", "🔥", "🧠", "🎮", "⚔️", "🛡️", "🌙", "⚡", "❄️", "🍀", "👑", "🦄"]
POKEAPI_BASE = "https://pokeapi.co/api/v2"
GOAL_PER_PLAYER = 6
AUTO_REFRESH_MS = 1200

# Modes
MODE_DISGUISE = "Disguise Draft"
MYSTERY_MODES = [
    "Mystery: Typing",
    "Mystery: Height",
    "Mystery: Weight",
    "Mystery: Color",
    "Mystery: Pokédex #",
    "Mystery: Base Stat Total",
    "Mystery: Ability",
]
ALL_MODES = [MODE_DISGUISE] + MYSTERY_MODES

# ----------------------------
# DB helpers
# ----------------------------
@st.cache_resource
def db():
    conn = sqlite3.connect("thenwefight.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def q(sql, params=(), one=False):
    cur = db().cursor()
    cur.execute(sql, params)
    db().commit()

    # If the query doesn't return rows (INSERT/UPDATE/etc.)
    if cur.description is None:
        return None

    rows = cur.fetchall()
    # Convert sqlite3.Row -> dict so .get() works everywhere
    rows = [dict(r) for r in rows]

    if one:
        return rows[0] if rows else None
    return rows

def now_iso():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    q("""
    CREATE TABLE IF NOT EXISTS rooms (
      room_code TEXT PRIMARY KEY,
      created_at TEXT NOT NULL,
      status TEXT NOT NULL,              -- lobby | drafting | done
      host_player_id TEXT NOT NULL,
      turn_index INTEGER NOT NULL DEFAULT 0,
      pick_index INTEGER NOT NULL DEFAULT 0
    )
    """)

    q("""
    CREATE TABLE IF NOT EXISTS players (
      player_id TEXT PRIMARY KEY,
      room_code TEXT NOT NULL,
      name TEXT NOT NULL,
      icon TEXT NOT NULL,
      joined_at TEXT NOT NULL,
      is_host INTEGER NOT NULL DEFAULT 0,
      draft_pos INTEGER,
      FOREIGN KEY(room_code) REFERENCES rooms(room_code)
    )
    """)

    q("""
    CREATE TABLE IF NOT EXISTS draft_order (
      room_code TEXT NOT NULL,
      pos INTEGER NOT NULL,
      player_id TEXT NOT NULL,
      PRIMARY KEY (room_code, pos),
      FOREIGN KEY(room_code) REFERENCES rooms(room_code)
    )
    """)

    q("""
    CREATE TABLE IF NOT EXISTS rosters (
      room_code TEXT NOT NULL,
      player_id TEXT NOT NULL,
      slot INTEGER NOT NULL,
      pokemon TEXT NOT NULL,
      PRIMARY KEY (room_code, player_id, slot),
      FOREIGN KEY(room_code) REFERENCES rooms(room_code)
    )
    """)

    q("""
    CREATE TABLE IF NOT EXISTS offer (
      room_code TEXT PRIMARY KEY,
      phase TEXT NOT NULL,                 -- private_setup | public_offer | reveal
      actor_player_id TEXT NOT NULL,
      picker_player_id TEXT NOT NULL,

      real1 TEXT NOT NULL,
      real2 TEXT NOT NULL,
      real3 TEXT NOT NULL,

      shown1 TEXT NOT NULL,
      shown2 TEXT NOT NULL,
      shown3 TEXT NOT NULL,

      disguise_slot INTEGER NOT NULL DEFAULT 0,
      disguise_name TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,

      picked_slot INTEGER NOT NULL DEFAULT 0,
      picked_real TEXT NOT NULL DEFAULT '',
      picked_shown TEXT NOT NULL DEFAULT '',
      picked_at TEXT NOT NULL DEFAULT '',

      reveal_until TEXT NOT NULL DEFAULT '',
      next_actor_player_id TEXT NOT NULL DEFAULT '',
      next_picker_player_id TEXT NOT NULL DEFAULT '',

      ability1 TEXT NOT NULL DEFAULT '',
      ability2 TEXT NOT NULL DEFAULT '',
      ability3 TEXT NOT NULL DEFAULT ''
    )
    """)

    q("""
    CREATE TABLE IF NOT EXISTS feed (
      room_code TEXT NOT NULL,
      at TEXT NOT NULL,
      message TEXT NOT NULL
    )
    """)

def ensure_columns():
    # rooms.mode
    cols = [r["name"] for r in q("PRAGMA table_info(rooms)") or []]
    if "mode" not in cols:
        q("ALTER TABLE rooms ADD COLUMN mode TEXT NOT NULL DEFAULT ''")

    # offer: reveal_until / next_actor / next_picker (if older DB)
    ocols = [r["name"] for r in q("PRAGMA table_info(offer)") or []]
    if "reveal_until" not in ocols:
        q("ALTER TABLE offer ADD COLUMN reveal_until TEXT NOT NULL DEFAULT ''")
    if "next_actor_player_id" not in ocols:
        q("ALTER TABLE offer ADD COLUMN next_actor_player_id TEXT NOT NULL DEFAULT ''")
    if "next_picker_player_id" not in ocols:
        q("ALTER TABLE offer ADD COLUMN next_picker_player_id TEXT NOT NULL DEFAULT ''")
    if "ability1" not in ocols:
        q("ALTER TABLE offer ADD COLUMN ability1 TEXT NOT NULL DEFAULT ''")
    if "ability2" not in ocols:
        q("ALTER TABLE offer ADD COLUMN ability2 TEXT NOT NULL DEFAULT ''")
    if "ability3" not in ocols:
        q("ALTER TABLE offer ADD COLUMN ability3 TEXT NOT NULL DEFAULT ''")

init_db()
ensure_columns()

# ----------------------------
# Auto-refresh
# ----------------------------
def enable_autorefresh():
    if st.session_state.get("room_code") and st.session_state.get("player_id"):
        st_autorefresh(interval=AUTO_REFRESH_MS, key=f"tick_{st.session_state.room_code}")

# ----------------------------
# PokeAPI helpers
# ----------------------------
@st.cache_data(ttl=60 * 60 * 24)
def fetch_all_pokemon_names():
    url = f"{POKEAPI_BASE}/pokemon?limit=5000"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    names = [x["name"] for x in r.json()["results"]]

    def ok(n: str) -> bool:
        bad_substrings = [
            "mega", "gmax", "totem", "primal",
            "-cap", "-starter", "-cosplay",
            "-ash", "-battle-bond",
        ]
        if any(b in n for b in bad_substrings):
            return False
        bad_suffixes = ["-mega-x", "-mega-y"]
        if any(n.endswith(s) for s in bad_suffixes):
            return False
        return True

    filtered = [n for n in names if ok(n)]
    return sorted(set(filtered))

@st.cache_data(ttl=60 * 60)
def pokemon_api(name: str):
    r = requests.get(f"{POKEAPI_BASE}/pokemon/{name}", timeout=12)
    if r.status_code != 200:
        return None
    return r.json()

@st.cache_data(ttl=60 * 60)
def species_api(name: str):
    r = requests.get(f"{POKEAPI_BASE}/pokemon-species/{name}", timeout=12)
    if r.status_code != 200:
        return None
    return r.json()

@st.cache_data(ttl=60 * 60)
def pokemon_sprite_url(name: str):
    data = pokemon_api(name)
    if not data:
        return ""
    home = data.get("sprites", {}).get("other", {}).get("home", {}).get("front_default")
    if home:
        return home
    art = data.get("sprites", {}).get("other", {}).get("official-artwork", {}).get("front_default")
    if art:
        return art
    return data.get("sprites", {}).get("front_default", "") or ""

@st.cache_data(ttl=60 * 60)
def pokemon_info(name: str):
    data = pokemon_api(name)
    if not data:
        return {
            "id": None,
            "types": [],
            "height_dm": None,
            "weight_hg": None,
            "bst": None,
            "abilities": [],
            "color": None,
        }

    pid = data.get("id")
    types = [t["type"]["name"] for t in sorted(data.get("types", []), key=lambda x: x.get("slot", 99))]
    height_dm = data.get("height")
    weight_hg = data.get("weight")
    bst = sum(s["base_stat"] for s in data.get("stats", []) if "base_stat" in s)
    abilities = [a["ability"]["name"] for a in data.get("abilities", []) if a.get("ability", {}).get("name")]

    sp = species_api(name)
    color = None
    if sp and sp.get("color", {}).get("name"):
        color = sp["color"]["name"]

    return {
        "id": pid,
        "types": types,
        "height_dm": height_dm,
        "weight_hg": weight_hg,
        "bst": bst,
        "abilities": abilities,
        "color": color,
    }

def pretty_name(n: str) -> str:
    parts = n.replace("-", " ").split()
    return " ".join(p.capitalize() for p in parts)

def sample_three_distinct(exclude=set()):
    names = fetch_all_pokemon_names()
    pool = [n for n in names if n not in exclude]
    if len(pool) < 3:
        pool = names[:]
    return random.sample(pool, 3)

def mode_is_mystery(mode: str) -> bool:
    return mode in MYSTERY_MODES

def mode_label_for_option(mode: str, real_name: str, forced_ability: str = "") -> str:
    info = pokemon_info(real_name)

    if mode == "Mystery: Typing":
        t = info["types"] or []
        return " / ".join(pretty_name(x) for x in t) if t else "Unknown"

    if mode == "Mystery: Height":
        # PokeAPI height is decimeters
        dm = info["height_dm"]
        if dm is None:
            return "Unknown"
        m = dm / 10.0
        return f"{m:.1f} m"

    if mode == "Mystery: Weight":
        # PokeAPI weight is hectograms
        hg = info["weight_hg"]
        if hg is None:
            return "Unknown"
        kg = hg / 10.0
        return f"{kg:.1f} kg"

    if mode == "Mystery: Color":
        c = info["color"]
        return pretty_name(c) if c else "Unknown"

    if mode == "Mystery: Pokédex #":
        pid = info["id"]
        return f"#{pid}" if pid else "Unknown"

    if mode == "Mystery: Base Stat Total":
        bst = info["bst"]
        return f"{bst}" if bst is not None else "Unknown"

    if mode == "Mystery: Ability":
        # Use forced ability if present so it doesn't change between refreshes
        if forced_ability:
            return pretty_name(forced_ability)
        abilities = info["abilities"] or []
        return pretty_name(abilities[0]) if abilities else "Unknown"

    return "Unknown"

# ----------------------------
# Game logic
# ----------------------------
def gen_id(k=12):
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(k))

def gen_room_code():
    while True:
        code = "".join(random.choice(string.ascii_uppercase) for _ in range(5))
        exists = q("SELECT 1 FROM rooms WHERE room_code=?", (code,), one=True)
        if not exists:
            return code

def add_feed(room_code: str, msg: str):
    q("INSERT INTO feed(room_code, at, message) VALUES(?,?,?)", (room_code, now_iso(), msg))

def get_room(room_code: str):
    return q("SELECT * FROM rooms WHERE room_code=?", (room_code,), one=True)

def get_players(room_code: str):
    return q("SELECT * FROM players WHERE room_code=? ORDER BY joined_at ASC", (room_code,))

def get_player(player_id: str):
    return q("SELECT * FROM players WHERE player_id=?", (player_id,), one=True)

def get_roster(room_code: str, player_id: str):
    return q("SELECT * FROM rosters WHERE room_code=? AND player_id=? ORDER BY slot ASC", (room_code, player_id))

def roster_count(room_code: str, player_id: str):
    r = q("SELECT COUNT(*) AS c FROM rosters WHERE room_code=? AND player_id=?", (room_code, player_id), one=True)
    return int(r["c"]) if r else 0

def total_picks(room_code: str):
    r = q("SELECT COUNT(*) AS c FROM rosters WHERE room_code=?", (room_code,), one=True)
    return int(r["c"]) if r else 0

def ensure_session():
    st.session_state.setdefault("room_code", "")
    st.session_state.setdefault("player_id", "")

def set_session_player(room_code: str, player_id: str):
    st.session_state.room_code = room_code
    st.session_state.player_id = player_id

def create_room(host_name: str, host_icon: str):
    ensure_session()
    if st.session_state.player_id and st.session_state.room_code:
        existing = get_player(st.session_state.player_id)
        if existing:
            return st.session_state.room_code, st.session_state.player_id

    room_code = gen_room_code()
    host_player_id = gen_id()
    q(
        "INSERT INTO rooms(room_code, created_at, status, host_player_id, turn_index, pick_index, mode) VALUES(?,?,?,?,0,0,?)",
        (room_code, now_iso(), "lobby", host_player_id, MODE_DISGUISE),
    )
    q(
        "INSERT INTO players(player_id, room_code, name, icon, joined_at, is_host) VALUES(?,?,?,?,?,1)",
        (host_player_id, room_code, host_name, host_icon, now_iso()),
    )
    add_feed(room_code, f"{host_icon} {host_name} created the room.")
    set_session_player(room_code, host_player_id)
    return room_code, host_player_id

def join_room(room_code: str, name: str, icon: str):
    ensure_session()
    room = get_room(room_code)
    if not room:
        return None, "Room not found."

    if st.session_state.player_id and st.session_state.room_code == room_code:
        pid = st.session_state.player_id
        q("UPDATE players SET name=?, icon=? WHERE player_id=?", (name, icon, pid))
        return pid, None

    if st.session_state.player_id and st.session_state.room_code and st.session_state.room_code != room_code:
        return None, f"You are already in room {st.session_state.room_code}. Refresh the page or clear session to join another."

    player_id = gen_id()
    q(
        "INSERT INTO players(player_id, room_code, name, icon, joined_at, is_host) VALUES(?,?,?,?,?,0)",
        (player_id, room_code, name, icon, now_iso()),
    )
    add_feed(room_code, f"{icon} {name} joined the room.")
    set_session_player(room_code, player_id)
    return player_id, None

def assign_draft_order(room_code: str):
    players = get_players(room_code)
    pids = [p["player_id"] for p in players]
    random.shuffle(pids)
    q("DELETE FROM draft_order WHERE room_code=?", (room_code,))
    for i, pid in enumerate(pids):
        q("INSERT INTO draft_order(room_code, pos, player_id) VALUES(?,?,?)", (room_code, i, pid))
        q("UPDATE players SET draft_pos=? WHERE player_id=?", (i, pid))
    add_feed(room_code, "Draft order assigned.")

def get_order(room_code: str):
    rows = q("SELECT * FROM draft_order WHERE room_code=? ORDER BY pos ASC", (room_code,))
    return [r["player_id"] for r in rows]

def next_in_order(room_code: str, current_pid: str):
    order = get_order(room_code)
    if not order:
        return None
    i = order.index(current_pid)
    return order[(i + 1) % len(order)]

def get_offer(room_code: str):
    return q("SELECT * FROM offer WHERE room_code=?", (room_code,), one=True)

def create_offer(room_code: str, actor_pid: str, picker_pid: str, mode: str):
    # End if all full
    players = get_players(room_code)
    if players and all(roster_count(room_code, p["player_id"]) >= GOAL_PER_PLAYER for p in players):
        q("UPDATE rooms SET status='done' WHERE room_code=?", (room_code,))
        add_feed(room_code, "Draft complete.")
        return

    a, b, c = sample_three_distinct()

    # For ability mode, choose exactly one ability per option and freeze it
    ability1 = ability2 = ability3 = ""
    if mode == "Mystery: Ability":
        for idx, nm in enumerate([a, b, c], start=1):
            abilities = pokemon_info(nm).get("abilities", []) or []
            chosen = random.choice(abilities) if abilities else ""
            if idx == 1:
                ability1 = chosen
            elif idx == 2:
                ability2 = chosen
            else:
                ability3 = chosen

    # Disguise mode starts at private_setup; Mystery modes start at public_offer
    phase = "private_setup" if mode == MODE_DISGUISE else "public_offer"

    q("""
    INSERT INTO offer(room_code, phase, actor_player_id, picker_player_id,
                      real1, real2, real3, shown1, shown2, shown3,
                      disguise_slot, disguise_name, created_at,
                      picked_slot, picked_real, picked_shown, picked_at,
                      reveal_until, next_actor_player_id, next_picker_player_id,
                      ability1, ability2, ability3)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(room_code) DO UPDATE SET
      phase=excluded.phase,
      actor_player_id=excluded.actor_player_id,
      picker_player_id=excluded.picker_player_id,
      real1=excluded.real1, real2=excluded.real2, real3=excluded.real3,
      shown1=excluded.shown1, shown2=excluded.shown2, shown3=excluded.shown3,
      disguise_slot=0, disguise_name='',
      created_at=excluded.created_at,
      picked_slot=0, picked_real='', picked_shown='', picked_at='',
      reveal_until='',
      next_actor_player_id='',
      next_picker_player_id='',
      ability1=excluded.ability1,
      ability2=excluded.ability2,
      ability3=excluded.ability3
    """, (
        room_code, phase, actor_pid, picker_pid,
        a, b, c, a, b, c,
        0, "", now_iso(),
        0, "", "", "",
        "", "", "",
        ability1, ability2, ability3
    ))

def set_public_offer(room_code: str, disguise_slot: int, disguise_name: str):
    off = get_offer(room_code)
    if not off:
        return "No offer exists."
    if disguise_slot not in (1, 2, 3):
        return "Pick a slot to disguise."

    disguise_name = (disguise_name or "").strip().lower()
    if not disguise_name:
        return "Choose a disguise Pokémon."

    shown1, shown2, shown3 = off["real1"], off["real2"], off["real3"]
    if disguise_slot == 1:
        shown1 = disguise_name
    elif disguise_slot == 2:
        shown2 = disguise_name
    else:
        shown3 = disguise_name

    q("""
    UPDATE offer
    SET phase='public_offer',
        disguise_slot=?,
        disguise_name=?,
        shown1=?,
        shown2=?,
        shown3=?
    WHERE room_code=?
    """, (disguise_slot, disguise_name, shown1, shown2, shown3, room_code))

    actor = get_player(off["actor_player_id"])
    add_feed(room_code, f"{actor['icon']} {actor['name']} displayed the selections.")
    return None

def advance_reveal_if_due(room_code: str):
    off = get_offer(room_code)
    if not off or off["phase"] != "reveal":
        return

    until = (off["reveal_until"] or "").strip()
    if not until:
        return

    try:
        reveal_dt = datetime.strptime(until, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return

    if datetime.utcnow() < reveal_dt:
        return

    new_actor = (off["next_actor_player_id"] or "").strip()
    new_picker = (off["next_picker_player_id"] or "").strip()

    # If no next ids, just keep it stable (game ended)
    if not new_actor or not new_picker:
        return

    room = get_room(room_code)
    mode = (room["mode"] or MODE_DISGUISE) if room else MODE_DISGUISE
    create_offer(room_code, new_actor, new_picker, mode)

def start_draft(room_code: str):
    room = get_room(room_code)
    if not room or room["status"] != "lobby":
        return

    players = get_players(room_code)
    if len(players) < 2:
        add_feed(room_code, "Need at least 2 players to start.")
        return

    assign_draft_order(room_code)
    q("UPDATE rooms SET status='drafting', turn_index=0, pick_index=0 WHERE room_code=?", (room_code,))
    add_feed(room_code, "Game started. Drafting begins!")

    order = get_order(room_code)
    mode = (room["mode"] or MODE_DISGUISE)

    if mode == MODE_DISGUISE:
        actor = order[0]
        picker = order[1] if len(order) > 1 else order[0]
        create_offer(room_code, actor, picker, mode)
    else:
        # Mystery modes: each player picks their own offer sequentially
        current = order[0]
        create_offer(room_code, current, current, mode)

def lock_pick(room_code: str, picker_pid: str, picked_slot: int):
    off = get_offer(room_code)
    if not off:
        return "No offer exists."
    if off["phase"] != "public_offer":
        return "Not in pick phase yet."
    if picker_pid != off["picker_player_id"]:
        return "It's not your turn to pick."
    if picked_slot not in (1, 2, 3):
        return "Pick a valid slot."

    real_map = {1: off["real1"], 2: off["real2"], 3: off["real3"]}
    shown_map = {1: off["shown1"], 2: off["shown2"], 3: off["shown3"]}

    picked_real = real_map[picked_slot]
    picked_shown = shown_map[picked_slot]

    # Add to roster
    current_count = roster_count(room_code, picker_pid)
    if current_count >= GOAL_PER_PLAYER:
        return "You already have 6 Pokémon."
    slot = current_count + 1
    q("INSERT INTO rosters(room_code, player_id, slot, pokemon) VALUES(?,?,?,?)",
      (room_code, picker_pid, slot, picked_real))

    room = get_room(room_code)
    mode = (room["mode"] or MODE_DISGUISE) if room else MODE_DISGUISE

    picker = get_player(picker_pid)

    # Decide next turn NOW but don't create next offer until reveal ends
    order = get_order(room_code)
    if not order:
        return None

    # Determine next ids based on mode
    if mode == MODE_DISGUISE:
        new_actor = picker_pid
        new_picker = next_in_order(room_code, new_actor)
        # Skip players already full
        safety = 0
        while new_picker and roster_count(room_code, new_picker) >= GOAL_PER_PLAYER and safety < 50:
            new_picker = next_in_order(room_code, new_picker)
            safety += 1

        # Feed message includes lie/truth (fine since reveal starts immediately)
        lied = (picked_real != picked_shown)
        verdict = "✅ TRUTH" if not lied else "🕵️ LIE REVEALED"
        add_feed(room_code, f"{picker['icon']} {picker['name']} picked **{pretty_name(picked_shown)}** — {verdict} (was {pretty_name(picked_real)}).")

    else:
        # Mystery: the same player is picker; next is next in order (who still needs picks)
        new_actor = next_in_order(room_code, picker_pid)
        new_picker = new_actor
        safety = 0
        while new_picker and roster_count(room_code, new_picker) >= GOAL_PER_PLAYER and safety < 200:
            new_picker = next_in_order(room_code, new_picker)
            new_actor = new_picker
            safety += 1

        # In mystery, "shown" is not a lie; we keep picked_shown = picked_real
        # Feed can reveal during reveal phase window
        add_feed(room_code, f"{picker['icon']} {picker['name']} picked **{pretty_name(picked_real)}**.")

    # End condition (still show reveal for 5s)
    players = get_players(room_code)
    done = players and all(roster_count(room_code, p["player_id"]) >= GOAL_PER_PLAYER for p in players)
    if done:
        q("UPDATE rooms SET status='done' WHERE room_code=?", (room_code,))
        add_feed(room_code, "Draft complete.")
        new_actor = ""
        new_picker = ""

    reveal_until = (datetime.utcnow() + timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S")

    q("""
    UPDATE offer
    SET phase='reveal',
        picked_slot=?,
        picked_real=?,
        picked_shown=?,
        picked_at=?,
        reveal_until=?,
        next_actor_player_id=?,
        next_picker_player_id=?
    WHERE room_code=?
    """, (
        picked_slot, picked_real, picked_shown, now_iso(),
        reveal_until, new_actor, new_picker, room_code
    ))

    return None

# ----------------------------
# UI Helpers
# ----------------------------
def card(title: str, body_html: str):
    st.markdown(f"""
    <div class="block-card">
      <div style="font-weight:800; font-size:18px; margin-bottom:10px;">{title}</div>
      {body_html}
    </div>
    """, unsafe_allow_html=True)

def render_poke_card(name: str, label: str):
    url = pokemon_sprite_url(name)
    disp = pretty_name(name)
    if url:
        st.markdown('<div class="poke-img">', unsafe_allow_html=True)
        st.image(url, use_container_width=True)
        st.markdown(f'<div class="poke-name">{label}: {disp}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="poke-img"><div class="poke-name">{label}: {disp}</div><div class="small-muted">Sprite unavailable</div></div>', unsafe_allow_html=True)

def render_mystery_card(mode: str, real_name: str, forced_ability: str, slot_label: str):
    label = mode_label_for_option(mode, real_name, forced_ability=forced_ability)
    st.markdown('<div class="poke-img">', unsafe_allow_html=True)
    st.markdown(f"<div class='badge pill-warn'>{slot_label}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:28px; font-weight:900; margin-top:10px;'>{label}</div>", unsafe_allow_html=True)
    st.markdown("<div class='small-muted' style='margin-top:6px;'>Pokémon hidden until reveal</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_disguise_reveal(picked_shown: str, picked_real: str):
    shown_url = pokemon_sprite_url(picked_shown)
    real_url = pokemon_sprite_url(picked_real)
    lied = (picked_shown != picked_real)

    if not shown_url:
        shown_url = ""
    if not real_url:
        real_url = ""

    if lied and shown_url and real_url:
        st.markdown(
            f"""
            <div class="reveal-wrap">
              <div class="reveal-card">
                <div class="badge pill-warn">REVEAL</div>
                <div style="margin-top:10px; font-size:18px; font-weight:900;">{pretty_name(picked_shown)}</div>
                <div class="small-muted" style="margin-top:4px;">…was actually…</div>
                <div style="height:16px;"></div>
                <div class="lie-stage">
                  <img class="lie-img-real"  src="{real_url}" />
                  <img class="lie-img-shown" src="{shown_url}" />
                </div>
                <div style="height:10px;"></div>
                <div style="font-size:18px; font-weight:900;">{pretty_name(picked_real)}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        # Truth (or missing images): flash green twice
        url = real_url or shown_url
        st.markdown(
            f"""
            <div class="reveal-wrap">
              <div class="reveal-card">
                <div class="badge pill-good">TRUTH</div>
                <div style="margin-top:10px; font-size:18px; font-weight:900;">{pretty_name(picked_real)}</div>
                <div style="height:14px;"></div>
                <img class="reveal-img truth-pulse" src="{url}" />
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )

def render_mystery_reveal_three(mode: str, off):
    # Reveal all three with selected flashing green
    a, b, c = off["real1"], off["real2"], off["real3"]
    chosen = off["picked_slot"]

    cols = st.columns(3)
    items = [
        (1, a, off.get("ability1", "")),
        (2, b, off.get("ability2", "")),
        (3, c, off.get("ability3", "")),
    ]
    for i, (slot, nm, abil) in enumerate(items):
        with cols[i]:
            url = pokemon_sprite_url(nm)
            disp = pretty_name(nm)
            label = mode_label_for_option(mode, nm, forced_ability=abil)

            cls = "poke-img pick-flash-green" if slot == chosen else "poke-img"
            st.markdown(f"<div class='{cls}'>", unsafe_allow_html=True)

            st.markdown(f"<div class='badge pill-warn'>Slot {slot}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='small-muted' style='margin-top:6px;'>Clue: <b>{label}</b></div>", unsafe_allow_html=True)

            if url:
                st.image(url, use_container_width=True)
            st.markdown(f"<div class='poke-name'>{disp}</div>", unsafe_allow_html=True)

            if slot == chosen:
                st.markdown("<div class='badge pill-good' style='margin-top:8px;'>SELECTED</div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Main App
# ----------------------------
ensure_session()

left, right = st.columns([0.33, 0.67], gap="large")

with left:
    st.markdown("## 🎮 ThenWeFight Draft")
    st.markdown('<div class="small-muted">Pure Python • Streamlit • SQLite • No Supabase</div>', unsafe_allow_html=True)
    st.write("")

    mode_ui = st.radio("Mode", ["Host", "Join"], horizontal=True)

    if st.session_state.room_code and st.session_state.player_id:
        st.markdown(f'<div class="badge pill-good">Room: {st.session_state.room_code}</div>', unsafe_allow_html=True)
        me = get_player(st.session_state.player_id)
        if me:
            st.markdown(f'<div class="badge">You: {me["player_id"]}</div>', unsafe_allow_html=True)
        st.write("")

    if mode_ui == "Host":
        host_name = st.text_input("Your name", value="Host")
        host_icon = st.selectbox("Icon", ICONS, index=0)

        can_create = not (st.session_state.room_code and st.session_state.player_id)
        if st.button("Create Room", use_container_width=True, disabled=not can_create):
            rc, pid = create_room(host_name.strip() or "Host", host_icon)
            st.success(f"Created room: {rc}")
            st.rerun()

        if not can_create:
            st.info("You already joined a room in this session. Refresh the page to start over.")

    else:
        room_code = st.text_input("Room code", value=st.session_state.room_code or "").strip().upper()
        name = st.text_input("Your name", value="Player")
        icon = st.selectbox("Icon", ICONS, index=1)

        disabled_join = bool(st.session_state.room_code and st.session_state.player_id and st.session_state.room_code != room_code and room_code)
        if st.button("Join Room", use_container_width=True, disabled=disabled_join):
            pid, err = join_room(room_code, name.strip() or "Player", icon)
            if err:
                st.error(err)
            else:
                st.success("Joined!")
                st.rerun()

        if disabled_join:
            st.warning(f"You are already in room {st.session_state.room_code} for this session. Refresh page to join another room.")

    st.write("")
    st.markdown("---")

    rc = st.session_state.room_code
    pid = st.session_state.player_id

    if rc and pid:
        room = get_room(rc)
        players = get_players(rc)

        st.markdown("### Room")
        st.markdown(f'<div class="badge pill-good">Room: {rc}</div>', unsafe_allow_html=True)

        me = get_player(pid)

        # Host picks mode BEFORE start (and can change until started)
        if room and me and me["is_host"] == 1 and room["status"] == "lobby":
            cur_mode = room["mode"] or MODE_DISGUISE
            picked_mode = st.selectbox("Game mode", ALL_MODES, index=ALL_MODES.index(cur_mode) if cur_mode in ALL_MODES else 0)
            if picked_mode != cur_mode:
                q("UPDATE rooms SET mode=? WHERE room_code=?", (picked_mode, rc))
                add_feed(rc, f"Host set mode to **{picked_mode}**.")
                st.rerun()

            if st.button("Start Game", use_container_width=True):
                start_draft(rc)
                st.rerun()

        if room and room["mode"]:
            st.markdown(f"<div class='badge'>Mode: <b>{room['mode']}</b></div>", unsafe_allow_html=True)

        st.write("")
        ar = st.toggle("Auto-refresh", value=True)
        if ar:
            enable_autorefresh()

        st.write("")
        st.markdown("### Players")
        for p in players:
            host_tag = " 👑" if p["is_host"] == 1 else ""
            st.markdown(
                f"- {p['icon']} **{p['name']}**{host_tag}  <span class='small-muted'>({roster_count(rc, p['player_id'])}/{GOAL_PER_PLAYER})</span>",
                unsafe_allow_html=True
            )

# Right column = game
with right:
    rc = st.session_state.room_code
    pid = st.session_state.player_id

    if not rc or not pid:
        card("Lobby", "<div class='small-muted'>Create or join a room to begin.</div>")
    else:
        room = get_room(rc)
        players = get_players(rc)

        # advance reveal if due, then re-read offer
        advance_reveal_if_due(rc)
        off = get_offer(rc)

        # Header stats
        total = total_picks(rc)
        max_total = len(players) * GOAL_PER_PLAYER
        my_count = roster_count(rc, pid)
        mode = (room["mode"] or MODE_DISGUISE) if room else MODE_DISGUISE

        c1, c2, c3, c4 = st.columns([0.32, 0.22, 0.23, 0.23])
        with c1:
            st.markdown("## 🧠 Drafting" if room and room["status"] != "lobby" else "## 🧩 Lobby")
        with c2:
            st.markdown(f"<div class='badge'>Players: <b>{len(players)}</b></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='badge pill-good'>Your picks: <b>{my_count}</b> / {GOAL_PER_PLAYER}</div>", unsafe_allow_html=True)
        with c4:
            st.markdown(f"<div class='badge pill-good'>Total picks: <b>{total}</b> / {max_total}</div>", unsafe_allow_html=True)

        st.write("")
        st.markdown("<hr/>", unsafe_allow_html=True)

        if not room or room["status"] == "lobby":
            card("Waiting Room", "<div class='small-muted'>Host can start the game once everyone joins.</div>")

        elif room["status"] == "done":
            card("Draft Complete", "<div class='small-muted'>Everyone finished their 6 picks.</div>")

        else:
            if not off:
                card("Current Offer", "<div class='small-muted'>No offer yet.</div>")
            else:
                actor = get_player(off["actor_player_id"])
                picker = get_player(off["picker_player_id"])

                st.markdown("<div class='block-card'>", unsafe_allow_html=True)
                st.markdown("### 📌 Current Offer")
                st.markdown(
                    f"<div class='badge'>Mode: <b>{mode}</b></div>"
                    f"<div class='badge'>Actor: <b>{actor['icon']} {actor['name']}</b></div>"
                    f"<div class='badge'>Picker: <b>{picker['icon']} {picker['name']}</b></div>",
                    unsafe_allow_html=True
                )
                st.write("")

                # ---- DISGUISE MODE ----
                if mode == MODE_DISGUISE:
                    if off["phase"] == "private_setup":
                        if pid != off["actor_player_id"]:
                            st.info("Waiting for the current actor to prepare and display the selections…")
                        else:
                            st.markdown(
                                "<div class='small-muted'>Only you can see the real Pokémon right now. Choose one slot to disguise, then display to everyone.</div>",
                                unsafe_allow_html=True
                            )
                            st.write("")

                            colA, colB, colC = st.columns(3)
                            with colA:
                                render_poke_card(off["real1"], "Slot 1")
                            with colB:
                                render_poke_card(off["real2"], "Slot 2")
                            with colC:
                                render_poke_card(off["real3"], "Slot 3")

                            st.write("")
                            disguise_slot = st.radio("Which slot do you want to disguise?", [1, 2, 3], horizontal=True)
                            all_names = fetch_all_pokemon_names()
                            disguise_name = st.selectbox(
                                "Disguise it as (autocomplete)",
                                options=all_names,
                                index=all_names.index("pikachu") if "pikachu" in all_names else 0
                            )

                            if st.button("✅ Display selections to everyone", use_container_width=True):
                                err = set_public_offer(rc, disguise_slot, disguise_name)
                                if err:
                                    st.error(err)
                                else:
                                    st.rerun()

                    elif off["phase"] == "public_offer":
                        st.success("Selections are displayed to everyone.")
                        st.write("")

                        colA, colB, colC = st.columns(3)
                        with colA:
                            render_poke_card(off["shown1"], "Slot 1")
                        with colB:
                            render_poke_card(off["shown2"], "Slot 2")
                        with colC:
                            render_poke_card(off["shown3"], "Slot 3")

                        st.write("")
                        st.markdown("#### ✅ Pick Phase")

                        if pid != off["picker_player_id"]:
                            st.info(f"Waiting for {picker['icon']} {picker['name']} to pick…")
                        else:
                            picked_slot = st.radio("Pick one:", [1, 2, 3], horizontal=True)
                            if st.button("Lock in pick", use_container_width=True):
                                err = lock_pick(rc, pid, picked_slot)
                                if err:
                                    st.error(err)
                                else:
                                    st.rerun()

                    elif off["phase"] == "reveal":
                        # ONLY picked image + animation
                        st.warning("🎭 Reveal phase (5 seconds)…")
                        st.write("")
                        render_disguise_reveal(off["picked_shown"], off["picked_real"])

                # ---- MYSTERY MODES ----
                else:
                    if off["phase"] == "public_offer":
                        st.success("Offer is displayed to everyone (mystery clues only).")
                        st.write("")

                        colA, colB, colC = st.columns(3)
                        with colA:
                            render_mystery_card(mode, off["real1"], off.get("ability1", ""), "Slot 1")
                        with colB:
                            render_mystery_card(mode, off["real2"], off.get("ability2", ""), "Slot 2")
                        with colC:
                            render_mystery_card(mode, off["real3"], off.get("ability3", ""), "Slot 3")

                        st.write("")
                        st.markdown("#### ✅ Pick Phase")

                        if pid != off["picker_player_id"]:
                            st.info(f"Waiting for {picker['icon']} {picker['name']} to pick…")
                        else:
                            picked_slot = st.radio("Pick one:", [1, 2, 3], horizontal=True)
                            if st.button("Lock in pick", use_container_width=True):
                                err = lock_pick(rc, pid, picked_slot)
                                if err:
                                    st.error(err)
                                else:
                                    st.rerun()

                    elif off["phase"] == "reveal":
                        st.warning("🎭 Reveal phase (5 seconds)… all 3 are revealed, selected flashes green.")
                        st.write("")
                        render_mystery_reveal_three(mode, off)

                st.markdown("</div>", unsafe_allow_html=True)

        st.write("")
        st.markdown("<hr/>", unsafe_allow_html=True)

        # Feed + Rosters
        fcol, rcol = st.columns([0.60, 0.40], gap="large")

        with fcol:
            st.markdown("### 📣 Public Feed (everyone sees)")
            feed = q("SELECT * FROM feed WHERE room_code=? ORDER BY at DESC LIMIT 30", (rc,))
            if not feed:
                st.markdown("<div class='small-muted'>No events yet.</div>", unsafe_allow_html=True)
            else:
                for item in feed:
                    st.markdown(f"<div class='feed-item'>{item['message']}</div>", unsafe_allow_html=True)

        with rcol:
            st.markdown("### 🧾 Rosters")
            for p in players:
                roster = get_roster(rc, p["player_id"])
                st.markdown(f"**{p['icon']} {p['name']}**  <span class='small-muted'>({len(roster)}/{GOAL_PER_PLAYER})</span>", unsafe_allow_html=True)
                if roster:
                    for rr in roster:
                        st.markdown(f"- {pretty_name(rr['pokemon'])}")
                else:
                    st.markdown("<div class='small-muted'>No picks yet.</div>", unsafe_allow_html=True)
                st.write("")
