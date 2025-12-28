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
  font-weight: 700;
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

.hint-card {
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.03);
  padding: 16px;
  min-height: 160px;
  display:flex;
  flex-direction:column;
  justify-content:center;
  align-items:center;
  text-align:center;
}

.hint-title {
  font-weight: 900;
  letter-spacing: -0.02em;
  font-size: 18px;
  margin-bottom: 8px;
}

.hint-value {
  font-weight: 800;
  font-size: 28px;
  color: rgba(255,255,255,0.92);
}

.hint-sub {
  margin-top: 10px;
  font-size: 12px;
  color: rgba(255,255,255,0.55);
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

MODE_DISGUISE = "Disguise Draft"
MODE_TYPE = "Mystery: Typing"
MODE_HEIGHT = "Mystery: Height"
MODE_WEIGHT = "Mystery: Weight"
MODE_COLOR = "Mystery: Color"

ALL_MODES = [MODE_DISGUISE, MODE_TYPE, MODE_HEIGHT, MODE_WEIGHT, MODE_COLOR]

AUTO_REFRESH_MS = 1200


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
      phase TEXT NOT NULL,                -- private_setup | public_offer | mystery_offer | reveal
      actor_player_id TEXT NOT NULL,
      picker_player_id TEXT NOT NULL,

      real1 TEXT NOT NULL,
      real2 TEXT NOT NULL,
      real3 TEXT NOT NULL,

      -- In Disguise mode, shown1-3 are pokemon names (with one disguised).
      -- In Mystery modes, shown1-3 are the HINT STRINGS for each option.
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
      next_picker_player_id TEXT NOT NULL DEFAULT ''
    )
    """)

    q("""
    CREATE TABLE IF NOT EXISTS feed (
      room_code TEXT NOT NULL,
      at TEXT NOT NULL,
      message TEXT NOT NULL
    )
    """)


def ensure_rooms_mode_column():
    cols = [r["name"] for r in q("PRAGMA table_info(rooms)") or []]
    if "game_mode" not in cols:
        q("ALTER TABLE rooms ADD COLUMN game_mode TEXT NOT NULL DEFAULT 'Disguise Draft'")


init_db()
ensure_rooms_mode_column()


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

    return sorted(set([n for n in names if ok(n)]))


@st.cache_data(ttl=60 * 60)
def pokemon_sprite_url(name: str):
    try:
        r = requests.get(f"{POKEAPI_BASE}/pokemon/{name}", timeout=12)
        if r.status_code != 200:
            return ""
        data = r.json()
        home = data.get("sprites", {}).get("other", {}).get("home", {}).get("front_default")
        if home:
            return home
        art = data.get("sprites", {}).get("other", {}).get("official-artwork", {}).get("front_default")
        if art:
            return art
        return data.get("sprites", {}).get("front_default", "") or ""
    except Exception:
        return ""


@st.cache_data(ttl=60 * 60)
def pokemon_hint(name: str, mode: str) -> str:
    """
    Returns the single "category" string shown for each option in Mystery modes.
    """
    try:
        pr = requests.get(f"{POKEAPI_BASE}/pokemon/{name}", timeout=12)
        if pr.status_code != 200:
            return "Unknown"
        pdata = pr.json()

        if mode == MODE_TYPE:
            types = [t["type"]["name"] for t in pdata.get("types", [])]
            if not types:
                return "Unknown"
            # preserve slot order
            # (already in slot order from API)
            return " / ".join([t.capitalize() for t in types])

        if mode == MODE_HEIGHT:
            # height in decimeters
            dm = pdata.get("height", None)
            if dm is None:
                return "Unknown"
            meters = dm / 10.0
            feet = meters * 3.28084
            return f"{meters:.1f} m ({feet:.1f} ft)"

        if mode == MODE_WEIGHT:
            # weight in hectograms
            hg = pdata.get("weight", None)
            if hg is None:
                return "Unknown"
            kg = hg / 10.0
            lbs = kg * 2.20462
            return f"{kg:.1f} kg ({lbs:.1f} lb)"

        if mode == MODE_COLOR:
            sr = requests.get(f"{POKEAPI_BASE}/pokemon-species/{name}", timeout=12)
            if sr.status_code != 200:
                return "Unknown"
            sdata = sr.json()
            color = (sdata.get("color") or {}).get("name", "Unknown")
            return str(color).capitalize()

        return "Unknown"
    except Exception:
        return "Unknown"


def pretty_name(n: str) -> str:
    parts = n.replace("-", " ").split()
    return " ".join(p.capitalize() for p in parts)


def sample_three_distinct(exclude=set()):
    names = fetch_all_pokemon_names()
    pool = [n for n in names if n not in exclude]
    if len(pool) < 3:
        pool = names[:]
    return random.sample(pool, 3)


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


def set_session_player(room_code: str, player_id: str):
    st.session_state.room_code = room_code
    st.session_state.player_id = player_id


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
        "INSERT INTO rooms(room_code, created_at, status, host_player_id, turn_index, pick_index, game_mode) VALUES(?,?,?,?,0,0,?)",
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


def room_mode(room_code: str) -> str:
    r = get_room(room_code)
    return (r["game_mode"] if r and "game_mode" in r.keys() else MODE_DISGUISE) or MODE_DISGUISE


def set_room_mode(room_code: str, mode: str):
    if mode not in ALL_MODES:
        mode = MODE_DISGUISE
    q("UPDATE rooms SET game_mode=? WHERE room_code=?", (mode, room_code))


def create_private_offer_disguise(room_code: str, actor_pid: str, picker_pid: str):
    players = get_players(room_code)
    if all(roster_count(room_code, p["player_id"]) >= GOAL_PER_PLAYER for p in players):
        q("UPDATE rooms SET status='done' WHERE room_code=?", (room_code,))
        add_feed(room_code, "Draft complete.")
        return

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
      reveal_until='', next_actor_player_id='', next_picker_player_id=''
    """, (
        room_code, "private_setup", actor_pid, picker_pid,
        a, b, c, a, b, c,
        0, "", now_iso(),
        0, "", "", "",
        "", "", ""
    ))


def create_mystery_offer(room_code: str, picker_pid: str, mode: str):
    players = get_players(room_code)
    if all(roster_count(room_code, p["player_id"]) >= GOAL_PER_PLAYER for p in players):
        q("UPDATE rooms SET status='done' WHERE room_code=?", (room_code,))
        add_feed(room_code, "Draft complete.")
        return

    a, b, c = sample_three_distinct()
    h1 = pokemon_hint(a, mode)
    h2 = pokemon_hint(b, mode)
    h3 = pokemon_hint(c, mode)

    # In mystery modes: actor = picker (no separate actor step), phase=mystery_offer,
    # shown1-3 store the hint strings.
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
      reveal_until='', next_actor_player_id='', next_picker_player_id=''
    """, (
        room_code, "mystery_offer", picker_pid, picker_pid,
        a, b, c, h1, h2, h3,
        0, "", now_iso(),
        0, "", "", "",
        "", "", ""
    ))


def create_next_offer(room_code: str, new_actor: str, new_picker: str):
    mode = room_mode(room_code)
    if mode == MODE_DISGUISE:
        create_private_offer_disguise(room_code, new_actor, new_picker)
    else:
        # sequential: offer shown only to the picker, who chooses for themselves
        create_mystery_offer(room_code, new_picker, mode)


def get_offer(room_code: str):
    return q("SELECT * FROM offer WHERE room_code=?", (room_code,), one=True)


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
    add_feed(room_code, f"Game started. Mode: **{room_mode(room_code)}**")

    order = get_order(room_code)
    if not order:
        return

    mode = room_mode(room_code)
    if mode == MODE_DISGUISE:
        actor = order[0]
        picker = order[1] if len(order) > 1 else order[0]
        create_private_offer_disguise(room_code, actor, picker)
    else:
        # Mystery modes: first offer goes to order[0]
        create_mystery_offer(room_code, order[0], mode)


def lock_pick_disguise(room_code: str, picker_pid: str, picked_slot: int):
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

    current_count = roster_count(room_code, picker_pid)
    if current_count >= GOAL_PER_PLAYER:
        return "You already have 6 Pokémon."

    slot = current_count + 1
    q("INSERT INTO rosters(room_code, player_id, slot, pokemon) VALUES(?,?,?,?)",
      (room_code, picker_pid, slot, picked_real))

    picker = get_player(picker_pid)
    lied = (picked_real != picked_shown)
    verdict = "✅ TRUTH" if not lied else "🕵️ LIE REVEALED"
    add_feed(room_code, f"{picker['icon']} {picker['name']} picked **{pretty_name(picked_shown)}** — {verdict} (was {pretty_name(picked_real)}).")

    # Next turn logic (picker becomes actor)
    players = get_players(room_code)
    if all(roster_count(room_code, p["player_id"]) >= GOAL_PER_PLAYER for p in players):
        q("UPDATE rooms SET status='done' WHERE room_code=?", (room_code,))
        add_feed(room_code, "Draft complete.")
        reveal_until = (datetime.utcnow() + timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S")
        q("""
        UPDATE offer
        SET phase='reveal',
            picked_slot=?,
            picked_real=?,
            picked_shown=?,
            picked_at=?,
            reveal_until=?,
            next_actor_player_id='',
            next_picker_player_id=''
        WHERE room_code=?
        """, (picked_slot, picked_real, picked_shown, now_iso(), reveal_until, room_code))
        return None

    new_actor = picker_pid
    new_picker = next_in_order(room_code, new_actor)

    safety = 0
    while new_picker and roster_count(room_code, new_picker) >= GOAL_PER_PLAYER and safety < 50:
        new_picker = next_in_order(room_code, new_picker)
        safety += 1

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
    """, (picked_slot, picked_real, picked_shown, now_iso(), reveal_until, new_actor, new_picker, room_code))
    return None


def lock_pick_mystery(room_code: str, picker_pid: str, picked_slot: int):
    off = get_offer(room_code)
    if not off:
        return "No offer exists."
    if off["phase"] != "mystery_offer":
        return "Not in mystery offer phase."
    if picker_pid != off["picker_player_id"]:
        return "It's not your turn to pick."
    if picked_slot not in (1, 2, 3):
        return "Pick a valid slot."

    real_map = {1: off["real1"], 2: off["real2"], 3: off["real3"]}
    hint_map = {1: off["shown1"], 2: off["shown2"], 3: off["shown3"]}

    picked_real = real_map[picked_slot]
    picked_hint = hint_map[picked_slot]

    current_count = roster_count(room_code, picker_pid)
    if current_count >= GOAL_PER_PLAYER:
        return "You already have 6 Pokémon."

    slot = current_count + 1
    q("INSERT INTO rosters(room_code, player_id, slot, pokemon) VALUES(?,?,?,?)",
      (room_code, picker_pid, slot, picked_real))

    picker = get_player(picker_pid)
    add_feed(room_code, f"{picker['icon']} {picker['name']} picked an option ({picked_hint}). Reveal incoming…")

    # Next picker is next in order (skip full rosters)
    players = get_players(room_code)
    if all(roster_count(room_code, p["player_id"]) >= GOAL_PER_PLAYER for p in players):
        q("UPDATE rooms SET status='done' WHERE room_code=?", (room_code,))
        add_feed(room_code, "Draft complete.")
        reveal_until = (datetime.utcnow() + timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S")
        q("""
        UPDATE offer
        SET phase='reveal',
            picked_slot=?,
            picked_real=?,
            picked_shown=?,
            picked_at=?,
            reveal_until=?,
            next_actor_player_id='',
            next_picker_player_id=''
        WHERE room_code=?
        """, (picked_slot, picked_real, picked_hint, now_iso(), reveal_until, room_code))
        return None

    new_picker = next_in_order(room_code, picker_pid)
    safety = 0
    while new_picker and roster_count(room_code, new_picker) >= GOAL_PER_PLAYER and safety < 50:
        new_picker = next_in_order(room_code, new_picker)
        safety += 1

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
    """, (picked_slot, picked_real, picked_hint, now_iso(), reveal_until, picker_pid, new_picker, room_code))
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

    # If no next, just stop (end of draft case)
    if not new_picker:
        return

    create_next_offer(room_code, new_actor or new_picker, new_picker)


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
        st.markdown(
            f'<div class="poke-img"><div class="poke-name">{label}: {disp}</div>'
            f'<div class="small-muted">Sprite unavailable</div></div>',
            unsafe_allow_html=True
        )


def render_hint_card(slot_label: str, hint_title: str, hint_value: str):
    st.markdown(
        f"""
        <div class="hint-card">
          <div class="hint-title">{slot_label}</div>
          <div class="hint-value">{hint_value}</div>
          <div class="hint-sub">{hint_title}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


# ----------------------------
# Main App
# ----------------------------
ensure_session()

left, right = st.columns([0.33, 0.67], gap="large")

with left:
    st.markdown("## 🎮 ThenWeFight Draft")
    st.markdown('<div class="small-muted">Pure Python • Streamlit • SQLite • No Supabase</div>', unsafe_allow_html=True)
    st.write("")

    mode = st.radio("Mode", ["Host", "Join"], horizontal=True)

    if st.session_state.room_code and st.session_state.player_id:
        st.markdown(f'<div class="badge pill-good">Room: {st.session_state.room_code}</div>', unsafe_allow_html=True)
        me = get_player(st.session_state.player_id)
        if me:
            st.markdown(f'<div class="badge">You: {me["player_id"]}</div>', unsafe_allow_html=True)
        st.write("")

    if mode == "Host":
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

        # Host picks mode BEFORE starting
        if room and me and me["is_host"] == 1 and room["status"] == "lobby":
            st.write("")
            current = room_mode(rc)
            selected = st.selectbox("Game Mode", ALL_MODES, index=ALL_MODES.index(current) if current in ALL_MODES else 0)
            if selected != current:
                set_room_mode(rc, selected)
                st.rerun()

            st.write("")
            if st.button("Start Game", use_container_width=True):
                start_draft(rc)
                st.rerun()

        # Auto-refresh
        st.write("")
        ar = st.toggle("Auto-refresh", value=True)
        if ar:
            enable_autorefresh()

        st.write("")
        st.markdown("### Players")
        for p in players:
            host_tag = " 👑" if p["is_host"] == 1 else ""
            st.markdown(
                f"- {p['icon']} **{p['name']}**{host_tag}  "
                f"<span class='small-muted'>({roster_count(rc, p['player_id'])}/{GOAL_PER_PLAYER})</span>",
                unsafe_allow_html=True
            )

with right:
    rc = st.session_state.room_code
    pid = st.session_state.player_id

    if not rc or not pid:
        card("Lobby", "<div class='small-muted'>Create or join a room to begin.</div>")
    else:
        room = get_room(rc)
        me = get_player(pid)
        players = get_players(rc)

        # advance reveal if time is due (this is what makes the 5s reveal "auto move on")
        advance_reveal_if_due(rc)
        off = get_offer(rc)

        total = total_picks(rc)
        max_total = len(players) * GOAL_PER_PLAYER
        my_count = roster_count(rc, pid)

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
                game_mode = room_mode(rc)

                actor = get_player(off["actor_player_id"])
                picker = get_player(off["picker_player_id"])

                st.markdown("<div class='block-card'>", unsafe_allow_html=True)
                st.markdown("### 📌 Current Offer")
                st.markdown(
                    f"<div class='badge'>Mode: <b>{game_mode}</b></div> "
                    f"<div class='badge'>Picker: <b>{picker['icon']} {picker['name']}</b></div>",
                    unsafe_allow_html=True
                )
                st.write("")

                # -------- Disguise Draft flow (your original) --------
                if game_mode == MODE_DISGUISE:
                    st.markdown(
                        f"<div class='badge'>Actor: <b>{actor['icon']} {actor['name']}</b></div>",
                        unsafe_allow_html=True
                    )
                    st.write("")

                    if off["phase"] == "private_setup":
                        if pid != off["actor_player_id"]:
                            st.info("Waiting for the current actor to prepare and display the selections…")
                        else:
                            st.markdown(
                                "<div class='small-muted'>Only you can see the real Pokémon right now. "
                                "Choose one slot to disguise, then display to everyone.</div>",
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
                                err = lock_pick_disguise(rc, pid, picked_slot)
                                if err:
                                    st.error(err)
                                else:
                                    st.rerun()

                    elif off["phase"] == "reveal":
                        # Keep your custom reveal animation changes separate;
                        # here we just show the picked shown name + real if lied.
                        st.warning("🎭 Reveal phase (5 seconds)…")
                        st.write("")
                        lied = (off["picked_real"] != off["picked_shown"])
                        picked_to_show = off["picked_shown"] or off["picked_real"]
                        if picked_to_show:
                            render_poke_card(picked_to_show, "Picked")
                        if lied:
                            st.error(f"🕵️ LIE REVEALED — Actually **{pretty_name(off['picked_real'])}**")
                        else:
                            st.success("✅ TRUTH — Display matched the real Pokémon.")

                # -------- Mystery modes flow --------
                else:
                    hint_title = {
                        MODE_TYPE: "Typing",
                        MODE_HEIGHT: "Height",
                        MODE_WEIGHT: "Weight",
                        MODE_COLOR: "Color",
                    }.get(game_mode, "Hint")

                    if off["phase"] == "mystery_offer":
                        if pid != off["picker_player_id"]:
                            st.info(f"Waiting for {picker['icon']} {picker['name']} to pick…")
                        else:
                            st.markdown(
                                "<div class='small-muted'>You can only see the hint category. "
                                "Choose 1 of the 3 options for your roster.</div>",
                                unsafe_allow_html=True
                            )
                            st.write("")

                            colA, colB, colC = st.columns(3)
                            with colA:
                                render_hint_card("Option 1", hint_title, off["shown1"])
                            with colB:
                                render_hint_card("Option 2", hint_title, off["shown2"])
                            with colC:
                                render_hint_card("Option 3", hint_title, off["shown3"])

                            st.write("")
                            picked_slot = st.radio("Pick one:", [1, 2, 3], horizontal=True)
                            if st.button("Lock in pick", use_container_width=True):
                                err = lock_pick_mystery(rc, pid, picked_slot)
                                if err:
                                    st.error(err)
                                else:
                                    st.rerun()

                    elif off["phase"] == "reveal":
                        st.warning("🎭 Reveal phase (5 seconds)…")
                        st.write("")
                        # In mystery modes, picked_shown is the hint string (not a pokemon),
                        # and picked_real is the actual pokemon.
                        if off["picked_real"]:
                            render_poke_card(off["picked_real"], "Picked Pokémon")
                        if off["picked_shown"]:
                            st.markdown(f"<div class='badge'>Hint was: <b>{off['picked_shown']}</b></div>", unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

        st.write("")
        st.markdown("<hr/>", unsafe_allow_html=True)

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
                st.markdown(
                    f"**{p['icon']} {p['name']}**  <span class='small-muted'>({len(roster)}/{GOAL_PER_PLAYER})</span>",
                    unsafe_allow_html=True
                )
                if roster:
                    for rr in roster:
                        st.markdown(f"- {pretty_name(rr['pokemon'])}")
                else:
                    st.markdown("<div class='small-muted'>No picks yet.</div>", unsafe_allow_html=True)
                st.write("")
