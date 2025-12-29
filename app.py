import sqlite3
import random
import string
import requests
from datetime import datetime, timedelta

import streamlit as st
from streamlit_autorefresh import st_autorefresh

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
}

.pill-good { background: rgba(46,204,113,0.18); border-color: rgba(46,204,113,0.35); color: rgba(255,255,255,0.9); }
.pill-warn { background: rgba(243,156,18,0.18); border-color: rgba(243,156,18,0.35); color: rgba(255,255,255,0.9); }
.pill-bad  { background: rgba(231,76,60,0.18); border-color: rgba(231,76,60,0.35); color: rgba(255,255,255,0.9); }

hr { border-color: rgba(255,255,255,0.10) !important; }

.small-muted { color: var(--muted); font-size: 13px; }

.poke-name {
  font-weight: 800;
  font-size: 14px;
  margin-top: 8px;
}

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
@keyframes flashGreenTwice {
  0%, 100% { box-shadow: 0 0 0 rgba(46,204,113,0.0); border-color: rgba(255,255,255,0.12); }
  10% { box-shadow: 0 0 22px rgba(46,204,113,0.7); border-color: rgba(46,204,113,0.75); }
  25% { box-shadow: 0 0 0 rgba(46,204,113,0.0); border-color: rgba(255,255,255,0.12); }
  35% { box-shadow: 0 0 22px rgba(46,204,113,0.7); border-color: rgba(46,204,113,0.75); }
  55% { box-shadow: 0 0 0 rgba(46,204,113,0.0); border-color: rgba(255,255,255,0.12); }
}

@keyframes glowGreenHold {
  0%, 100% { box-shadow: 0 0 18px rgba(46,204,113,0.75); border-color: rgba(46,204,113,0.85); }
  50% { box-shadow: 0 0 30px rgba(46,204,113,0.9); border-color: rgba(46,204,113,1.0); }
}

@keyframes fadeOut {
  0% { opacity: 1; transform: scale(1); }
  48% { opacity: 1; }
  60% { opacity: 0; transform: scale(0.985); }
  100% { opacity: 0; transform: scale(0.985); }
}

@keyframes fadeIn {
  0% { opacity: 0; transform: scale(1.01); }
  50% { opacity: 0; }
  70% { opacity: 1; transform: scale(1); }
  100% { opacity: 1; transform: scale(1); }
}

.reveal-wrap {
  display:flex;
  justify-content:center;
  align-items:center;
  padding: 10px 0 6px 0;
}

.reveal-card {
  width: 360px;
  max-width: 100%;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 18px;
  padding: 14px;
  position: relative;
}

.reveal-imgbox {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  border-radius: 16px;
  overflow:hidden;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(0,0,0,0.25);
}

.reveal-imgbox img {
  position:absolute;
  inset:0;
  width:100%;
  height:100%;
  object-fit:contain;
  padding: 14px;
}

.reveal-title {
  margin-top:10px;
  font-weight: 900;
  text-align:center;
  font-size: 16px;
}

.reveal-sub {
  text-align:center;
  color: rgba(255,255,255,0.70);
  font-size: 13px;
  margin-top: 4px;
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

MODES = [
    ("Classic Disguise", "classic"),
    ("Mystery: Typing", "m_type"),
    ("Mystery: Height", "m_height"),
    ("Mystery: Weight", "m_weight"),
    ("Mystery: Color", "m_color"),
    ("Mystery: Pokédex #", "m_dex"),
    ("Mystery: Base Stat Total", "m_bst"),
    ("Mystery: Ability", "m_ability"),
]

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
    if cur.description is None:
        return None
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows

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
      phase TEXT NOT NULL,                 -- classic: private_setup/public_offer/reveal | mystery: mystery_offer/reveal
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
      picked_at TEXT NOT NULL DEFAULT ''
    )
    """)

    q("""
    CREATE TABLE IF NOT EXISTS feed (
      room_code TEXT NOT NULL,
      at TEXT NOT NULL,
      message TEXT NOT NULL
    )
    """)

def ensure_room_mode_column():
    cols = [r["name"] for r in q("PRAGMA table_info(rooms)") or []]
    if "mode" not in cols:
        q("ALTER TABLE rooms ADD COLUMN mode TEXT NOT NULL DEFAULT 'classic'")

def ensure_offer_reveal_columns():
    cols = [r["name"] for r in q("PRAGMA table_info(offer)") or []]
    if "reveal_until" not in cols:
        q("ALTER TABLE offer ADD COLUMN reveal_until TEXT NOT NULL DEFAULT ''")
    if "next_actor_player_id" not in cols:
        q("ALTER TABLE offer ADD COLUMN next_actor_player_id TEXT NOT NULL DEFAULT ''")
    if "next_picker_player_id" not in cols:
        q("ALTER TABLE offer ADD COLUMN next_picker_player_id TEXT NOT NULL DEFAULT ''")

init_db()
ensure_room_mode_column()
ensure_offer_reveal_columns()

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

    return sorted(set([n for n in names if ok(n)]))

@st.cache_data(ttl=60 * 60)
def pokemon_data(name: str):
    r = requests.get(f"{POKEAPI_BASE}/pokemon/{name}", timeout=12)
    if r.status_code != 200:
        return {}
    return r.json()

@st.cache_data(ttl=60 * 60)
def pokemon_species_data(name: str):
    r = requests.get(f"{POKEAPI_BASE}/pokemon-species/{name}", timeout=12)
    if r.status_code != 200:
        return {}
    return r.json()

@st.cache_data(ttl=60 * 60)
def pokemon_sprite_url(name: str):
    try:
        data = pokemon_data(name)
        sprites = data.get("sprites", {})
        home = sprites.get("other", {}).get("home", {}).get("front_default")
        if home:
            return home
        art = sprites.get("other", {}).get("official-artwork", {}).get("front_default")
        if art:
            return art
        return sprites.get("front_default", "") or ""
    except Exception:
        return ""

def pretty_name(n: str) -> str:
    parts = n.replace("-", " ").split()
    return " ".join(p.capitalize() for p in parts)

def sample_three_distinct():
    # fully randomized every time, no reuse constraints unless you add them
    names = fetch_all_pokemon_names()
    return random.sample(names, 3)

def mode_is_mystery(mode_code: str) -> bool:
    return mode_code.startswith("m_")

def pokemon_clue(name: str, mode_code: str) -> str:
    d = pokemon_data(name) or {}
    if not d:
        return "Unknown"

    if mode_code == "m_type":
        types = [t["type"]["name"] for t in d.get("types", [])]
        return " / ".join([pretty_name(x) for x in types]) if types else "Unknown"

    if mode_code == "m_height":
        # decimeters -> meters
        h = d.get("height", 0)
        return f"{h/10:.1f} m" if h else "Unknown"

    if mode_code == "m_weight":
        # hectograms -> kg
        w = d.get("weight", 0)
        return f"{w/10:.1f} kg" if w else "Unknown"

    if mode_code == "m_color":
        s = pokemon_species_data(name) or {}
        c = (s.get("color") or {}).get("name", "")
        return pretty_name(c) if c else "Unknown"

    if mode_code == "m_dex":
        pid = d.get("id", 0)
        return f"#{pid}" if pid else "Unknown"

    if mode_code == "m_bst":
        stats = d.get("stats", []) or []
        total = sum(int(s.get("base_stat", 0)) for s in stats)
        return f"{total}" if total else "Unknown"

    if mode_code == "m_ability":
        # pick one ability (first)
        ab = d.get("abilities", []) or []
        if not ab:
            return "Unknown"
        name0 = ab[0]["ability"]["name"]
        return pretty_name(name0)

    return "Unknown"

# ----------------------------
# Game logic helpers
# ----------------------------
def gen_id(k=12):
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(k))

def gen_room_code():
    while True:
        code = "".join(random.choice(string.ascii_uppercase) for _ in range(5))
        exists = q("SELECT 1 FROM rooms WHERE room_code=?", (code,), one=True)
        if not exists:
            return code

def enable_autorefresh():
    if st.session_state.get("room_code") and st.session_state.get("player_id"):
        st_autorefresh(interval=AUTO_REFRESH_MS, key=f"tick_{st.session_state.room_code}")

def add_feed(room_code: str, msg: str):
    q("INSERT INTO feed(room_code, at, message) VALUES(?,?,?)", (room_code, now_iso(), msg))

def get_room(room_code: str):
    return q("SELECT * FROM rooms WHERE room_code=?", (room_code,), one=True)

def set_room_mode(room_code: str, mode_code: str):
    q("UPDATE rooms SET mode=? WHERE room_code=?", (mode_code, room_code))

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
        (room_code, now_iso(), "lobby", host_player_id, "classic"),
    )
    q(
        "INSERT INTO players(player_id, room_code, name, icon, joined_at, is_host) VALUES(?,?,?,?,?,1)",
        (host_player_id, room_code, host_name, host_icon, now_iso()),
    )
    add_feed(room_code, f"{host_icon} {host_name} created the room.")
    st.session_state.room_code = room_code
    st.session_state.player_id = host_player_id
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
        return None, f"You are already in room {st.session_state.room_code}. Refresh the page (or clear session) to join another."

    player_id = gen_id()
    q(
        "INSERT INTO players(player_id, room_code, name, icon, joined_at, is_host) VALUES(?,?,?,?,?,0)",
        (player_id, room_code, name, icon, now_iso()),
    )
    add_feed(room_code, f"{icon} {name} joined the room.")
    st.session_state.room_code = room_code
    st.session_state.player_id = player_id
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

def create_classic_private_offer(room_code: str, actor_pid: str, picker_pid: str):
    a, b, c = sample_three_distinct()
    q("""
    INSERT INTO offer(room_code, phase, actor_player_id, picker_player_id,
                      real1, real2, real3, shown1, shown2, shown3,
                      disguise_slot, disguise_name, created_at,
                      picked_slot, picked_real, picked_shown, picked_at,
                      reveal_until, next_actor_player_id, next_picker_player_id)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
      next_picker_player_id=''
    """, (
        room_code, "private_setup", actor_pid, picker_pid,
        a, b, c, a, b, c,
        0, "", now_iso(),
        0, "", "", "",
        "", "", ""
    ))

def create_mystery_offer(room_code: str, picker_pid: str):
    a, b, c = sample_three_distinct()
    # In mystery mode, actor == picker (they're choosing for themselves)
    q("""
    INSERT INTO offer(room_code, phase, actor_player_id, picker_player_id,
                      real1, real2, real3, shown1, shown2, shown3,
                      disguise_slot, disguise_name, created_at,
                      picked_slot, picked_real, picked_shown, picked_at,
                      reveal_until, next_actor_player_id, next_picker_player_id)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
      next_picker_player_id=''
    """, (
        room_code, "mystery_offer", picker_pid, picker_pid,
        a, b, c, a, b, c,
        0, "", now_iso(),
        0, "", "", "",
        "", "", ""
    ))

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

    mode = room["mode"] if "mode" in room.keys() else "classic"
    order = get_order(room_code)
    if not order:
        return

    if mode_is_mystery(mode):
        first_picker = order[0]
        create_mystery_offer(room_code, first_picker)
    else:
        actor = order[0]
        picker = order[1] if len(order) > 1 else order[0]
        create_classic_private_offer(room_code, actor, picker)

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

    room = get_room(room_code)
    if not room:
        return

    mode = room["mode"] if "mode" in room.keys() else "classic"

    # If draft complete, keep done.
    players = get_players(room_code)
    if all(roster_count(room_code, p["player_id"]) >= GOAL_PER_PLAYER for p in players):
        q("UPDATE rooms SET status='done' WHERE room_code=?", (room_code,))
        add_feed(room_code, "Draft complete.")
        return

    new_actor = (off["next_actor_player_id"] or "").strip()
    new_picker = (off["next_picker_player_id"] or "").strip()

    if mode_is_mystery(mode):
        if not new_picker:
            return
        create_mystery_offer(room_code, new_picker)
    else:
        if not new_actor or not new_picker:
            return
        create_classic_private_offer(room_code, new_actor, new_picker)

def lock_pick(room_code: str, picker_pid: str, picked_slot: int):
    off = get_offer(room_code)
    if not off:
        return "No offer exists."

    room = get_room(room_code)
    mode = room["mode"] if room and "mode" in room.keys() else "classic"

    # Validate phases for each mode
    if mode_is_mystery(mode):
        if off["phase"] != "mystery_offer":
            return "Not in pick phase."
    else:
        if off["phase"] != "public_offer":
            return "Not in pick phase yet."

    if picker_pid != off["picker_player_id"]:
        return "It's not your turn to pick."
    if picked_slot not in (1, 2, 3):
        return "Pick a valid slot."

    real_map = {1: off["real1"], 2: off["real2"], 3: off["real3"]}
    shown_map = {1: off["shown1"], 2: off["shown2"], 3: off["shown3"]}

    picked_real = real_map[picked_slot]
    picked_shown = shown_map[picked_slot]  # in mystery, shown==real (we just don't display it yet)

    # Add to roster
    current_count = roster_count(room_code, picker_pid)
    if current_count >= GOAL_PER_PLAYER:
        return "You already have 6 Pokémon."
    slot = current_count + 1
    q("INSERT INTO rosters(room_code, player_id, slot, pokemon) VALUES(?,?,?,?)",
      (room_code, picker_pid, slot, picked_real))

    picker = get_player(picker_pid)

    # Feed message
    if mode_is_mystery(mode):
        add_feed(room_code, f"{picker['icon']} {picker['name']} made a mystery pick.")
    else:
        lied = (picked_real != picked_shown)
        verdict = "✅ TRUTH" if not lied else "🕵️ LIE REVEALED"
        add_feed(room_code, f"{picker['icon']} {picker['name']} picked **{pretty_name(picked_shown)}** — {verdict} (was {pretty_name(picked_real)}).")

    # Compute next turn (but only after reveal ends)
    order = get_order(room_code)
    if not order:
        return None

    if mode_is_mystery(mode):
        new_picker = next_in_order(room_code, picker_pid)
        # Skip players already full
        safety = 0
        while new_picker and roster_count(room_code, new_picker) >= GOAL_PER_PLAYER and safety < 50:
            new_picker = next_in_order(room_code, new_picker)
            safety += 1
        new_actor = new_picker  # unused, but keep fields filled
    else:
        new_actor = picker_pid
        new_picker = next_in_order(room_code, new_actor)
        safety = 0
        while new_picker and roster_count(room_code, new_picker) >= GOAL_PER_PLAYER and safety < 50:
            new_picker = next_in_order(room_code, new_picker)
            safety += 1

    # If everyone complete, still show reveal then end
    players = get_players(room_code)
    done_after = all(roster_count(room_code, p["player_id"]) >= GOAL_PER_PLAYER for p in players)

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
        picked_slot,
        picked_real,
        picked_shown,
        now_iso(),
        reveal_until,
        "" if done_after else (new_actor or ""),
        "" if done_after else (new_picker or ""),
        room_code
    ))

    if done_after:
        q("UPDATE rooms SET status='done' WHERE room_code=?", (room_code,))

    return None

# ----------------------------
# UI helpers
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
        st.markdown(f'<div class="poke-img">', unsafe_allow_html=True)
        st.image(url, use_container_width=True)
        st.markdown(f'<div class="poke-name">{label}: {disp}</div>', unsafe_allow_html=True)
        st.markdown(f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="poke-img"><div class="poke-name">{label}: {disp}</div><div class="small-muted">Sprite unavailable</div></div>',
            unsafe_allow_html=True
        )

def render_reveal_classic(picked_shown: str, picked_real: str):
    shown_url = pokemon_sprite_url(picked_shown)
    real_url = pokemon_sprite_url(picked_real)
    lied = (picked_real != picked_shown)

    if not shown_url:
        shown_url = ""
    if not real_url:
        real_url = ""

    if not lied:
        # Only the picked image, flashing green twice
        html = f"""
        <div class="reveal-wrap">
          <div class="reveal-card">
            <div class="reveal-imgbox" style="animation: flashGreenTwice 1.5s ease-in-out 1;">
              <img src="{shown_url}" />
            </div>
            <div class="reveal-title">{pretty_name(picked_shown)}</div>
            <div class="reveal-sub">✅ Truth</div>
          </div>
        </div>
        """
        st.components.v1.html(html, height=460)
        return

    # Lie: show picked image, then crossfade to real (still only one "picked" slot shown to viewers)
    html = f"""
    <div class="reveal-wrap">
      <div class="reveal-card">
        <div class="reveal-imgbox">
          <img src="{shown_url}" style="animation: fadeOut 5s ease-in-out 1 forwards;" />
          <img src="{real_url}" style="animation: fadeIn 5s ease-in-out 1 forwards;" />
        </div>
        <div class="reveal-title">{pretty_name(picked_shown)} ➜ {pretty_name(picked_real)}</div>
        <div class="reveal-sub">🕵️ Lie revealed</div>
      </div>
    </div>
    """
    st.components.v1.html(html, height=460)

def render_reveal_mystery_all_three(off, mode_code: str):
    # Reveal all 3 real options; chosen flashes green for whole reveal phase
    picked_slot = int(off["picked_slot"])
    trip = [(1, off["real1"]), (2, off["real2"]), (3, off["real3"])]

    cols = st.columns(3)
    for (slot, mon), col in zip(trip, cols):
        with col:
            url = pokemon_sprite_url(mon)
            chosen = (slot == picked_slot)
            anim = "animation: glowGreenHold 1.2s ease-in-out infinite;" if chosen else ""
            label = "✅ SELECTED" if chosen else "Option"
            st.markdown(
                f"""
                <div class="poke-img" style="{anim}">
                  <div class="badge pill-good" style="margin-bottom:10px;">{label}</div>
                """,
                unsafe_allow_html=True
            )
            if url:
                st.image(url, use_container_width=True)
            st.markdown(f"<div class='poke-name'>{pretty_name(mon)}</div>", unsafe_allow_html=True)

            # show the clue too (since it's a mystery mode)
            clue = pokemon_clue(mon, mode_code)
            st.markdown(f"<div class='small-muted'>Clue: <b>{clue}</b></div>", unsafe_allow_html=True)
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
        me0 = get_player(st.session_state.player_id)
        if me0:
            st.markdown(f'<div class="badge">You: {me0["player_id"]}</div>', unsafe_allow_html=True)
        st.write("")

    if mode_ui == "Host":
        host_name = st.text_input("Your name", value="Host")
        host_icon = st.selectbox("Icon", ICONS, index=0)

        can_create = not (st.session_state.room_code and st.session_state.player_id)
        if st.button("Create Room", use_container_width=True, disabled=not can_create):
            rc_new, pid_new = create_room(host_name.strip() or "Host", host_icon)
            st.success(f"Created room: {rc_new}")
            st.rerun()

        if not can_create:
            st.info("You already joined a room in this session. Refresh the page to start over.")

    else:
        room_code_in = st.text_input("Room code", value=st.session_state.room_code or "").strip().upper()
        name = st.text_input("Your name", value="Player")
        icon = st.selectbox("Icon", ICONS, index=1)

        disabled_join = bool(
            st.session_state.room_code and st.session_state.player_id
            and st.session_state.room_code != room_code_in
            and room_code_in
        )

        if st.button("Join Room", use_container_width=True, disabled=disabled_join):
            pid_new, err = join_room(room_code_in, name.strip() or "Player", icon)
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
        me = get_player(pid)

        st.markdown("### Room")
        st.markdown(f'<div class="badge pill-good">Room: {rc}</div>', unsafe_allow_html=True)

        # Host: choose mode before starting
        if room and me and me["is_host"] == 1 and room["status"] == "lobby":
            current_mode = room["mode"] if "mode" in room.keys() else "classic"
            idx = [m[1] for m in MODES].index(current_mode) if current_mode in [m[1] for m in MODES] else 0
            chosen = st.selectbox(
                "Game Mode",
                options=[m[0] for m in MODES],
                index=idx,
                help="Classic = disguise + public offer. Mystery = each player picks from clues only; reveal shows all options + highlights the chosen."
            )
            chosen_code = dict(MODES)[chosen]
            if chosen_code != current_mode:
                set_room_mode(rc, chosen_code)
                add_feed(rc, f"Host set mode to **{chosen}**.")
                st.rerun()

            if st.button("Start Game", use_container_width=True):
                start_draft(rc)
                st.rerun()

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

with right:
    rc = st.session_state.room_code
    pid = st.session_state.player_id

    if not rc or not pid:
        card("Lobby", "<div class='small-muted'>Create or join a room to begin.</div>")
    else:
        room = get_room(rc)
        players = get_players(rc)
        me = get_player(pid)

        # auto-advance reveal when timer expires (needs auto-refresh ON)
        advance_reveal_if_due(rc)
        off = get_offer(rc)

        # Header stats
        total = total_picks(rc)
        max_total = len(players) * GOAL_PER_PLAYER
        my_count = roster_count(rc, pid)
        mode_code = room["mode"] if room and "mode" in room.keys() else "classic"
        mode_name = [n for (n, c) in MODES if c == mode_code]
        mode_name = mode_name[0] if mode_name else "Classic Disguise"

        c1, c2, c3, c4 = st.columns([0.32, 0.22, 0.23, 0.23])
        with c1:
            st.markdown("## 🧠 Drafting" if room and room["status"] != "lobby" else "## 🧩 Lobby")
        with c2:
            st.markdown(f"<div class='badge'>Mode: <b>{mode_name}</b></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='badge pill-good'>Your picks: <b>{my_count}</b> / {GOAL_PER_PLAYER}</div>", unsafe_allow_html=True)
        with c4:
            st.markdown(f"<div class='badge pill-good'>Total picks: <b>{total}</b> / {max_total}</div>", unsafe_allow_html=True)

        st.write("")
        st.markdown("<hr/>", unsafe_allow_html=True)

        if not room or room["status"] == "lobby":
            card("Waiting Room", "<div class='small-muted'>Host can start the game once everyone joins.</div>")

        elif room["status"] == "done" and (not off or off["phase"] != "reveal"):
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
                    f"<div class='badge'>Actor: <b>{actor['icon']} {actor['name']}</b></div> "
                    f"<div class='badge'>Picker: <b>{picker['icon']} {picker['name']}</b></div>",
                    unsafe_allow_html=True
                )
                st.write("")

                # -------------------- CLASSIC MODE --------------------
                if not mode_is_mystery(mode_code):
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
                            with colA: render_poke_card(off["real1"], "Slot 1")
                            with colB: render_poke_card(off["real2"], "Slot 2")
                            with colC: render_poke_card(off["real3"], "Slot 3")

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
                        with colA: render_poke_card(off["shown1"], "Slot 1")
                        with colB: render_poke_card(off["shown2"], "Slot 2")
                        with colC: render_poke_card(off["shown3"], "Slot 3")

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
                        st.warning("🎭 Reveal phase (5 seconds)…")
                        st.write("")
                        # ONLY show the picked pokemon image with animation
                        render_reveal_classic(off["picked_shown"], off["picked_real"])

                    else:
                        st.info("Waiting…")

                # -------------------- MYSTERY MODES --------------------
                else:
                    if off["phase"] == "mystery_offer":
                        if pid != off["picker_player_id"]:
                            st.info(f"Waiting for {picker['icon']} {picker['name']} to choose from mystery clues…")
                        else:
                            st.markdown(
                                "<div class='small-muted'>You’re choosing for yourself. You only see clues (not the Pokémon).</div>",
                                unsafe_allow_html=True
                            )
                            st.write("")

                            clue1 = pokemon_clue(off["real1"], mode_code)
                            clue2 = pokemon_clue(off["real2"], mode_code)
                            clue3 = pokemon_clue(off["real3"], mode_code)

                            colA, colB, colC = st.columns(3)
                            with colA:
                                card("Slot 1", f"<div class='small-muted'>Clue</div><div style='font-size:20px;font-weight:900;'>{clue1}</div>")
                            with colB:
                                card("Slot 2", f"<div class='small-muted'>Clue</div><div style='font-size:20px;font-weight:900;'>{clue2}</div>")
                            with colC:
                                card("Slot 3", f"<div class='small-muted'>Clue</div><div style='font-size:20px;font-weight:900;'>{clue3}</div>")

                            st.write("")
                            picked_slot = st.radio("Pick one:", [1, 2, 3], horizontal=True)
                            if st.button("Lock in pick", use_container_width=True):
                                err = lock_pick(rc, pid, picked_slot)
                                if err:
                                    st.error(err)
                                else:
                                    st.rerun()

                    elif off["phase"] == "reveal":
                        st.warning("🎭 Reveal phase (5 seconds)… showing ALL options.")
                        st.write("")
                        render_reveal_mystery_all_three(off, mode_code)

                    else:
                        st.info("Waiting…")

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
