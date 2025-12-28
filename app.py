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

.block-card2 {
  background: var(--card2);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 14px 14px;
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

/* ----------------------------
   Reveal animations
   ---------------------------- */
.reveal-stage {
  width: 100%;
  display: flex;
  justify-content: center;
  margin-top: 6px;
}

.reveal-card {
  width: min(560px, 100%);
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 20px;
  padding: 16px 16px 18px 16px;
}

.reveal-title {
  font-weight: 900;
  font-size: 18px;
  margin-bottom: 10px;
  letter-spacing: -0.02em;
}

.reveal-sub {
  color: rgba(255,255,255,0.70);
  font-size: 13px;
  margin-bottom: 14px;
}

/* container for images */
.reveal-box {
  width: 100%;
  aspect-ratio: 1 / 1;
  max-height: 420px;
  border-radius: 18px;
  border: 1px solid rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.03);
  overflow: hidden;
  position: relative;
}

/* image styling */
.reveal-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  padding: 18px;
  transform: translateZ(0);
}

/* LIE: crossfade + slight pop to real at ~60% into the animation */
@keyframes hideShown {
  0%   { opacity: 1; transform: scale(1); }
  55%  { opacity: 1; transform: scale(1.02); }
  70%  { opacity: 0; transform: scale(0.98); }
  100% { opacity: 0; transform: scale(0.98); }
}
@keyframes showReal {
  0%   { opacity: 0; transform: scale(0.98); }
  60%  { opacity: 0; transform: scale(0.98); }
  75%  { opacity: 1; transform: scale(1.03); }
  100% { opacity: 1; transform: scale(1.00); }
}
.reveal-lie-shown { animation: hideShown 2.8s ease-in-out forwards; }
.reveal-lie-real  { animation: showReal  2.8s ease-in-out forwards; }

/* TRUTH: flash green border twice */
@keyframes truthFlash {
  0%   { box-shadow: 0 0 0 rgba(46,204,113,0.0), inset 0 0 0 rgba(46,204,113,0.0); }
  15%  { box-shadow: 0 0 0 6px rgba(46,204,113,0.35), inset 0 0 0 2px rgba(46,204,113,0.25); }
  30%  { box-shadow: 0 0 0 rgba(46,204,113,0.0), inset 0 0 0 rgba(46,204,113,0.0); }
  45%  { box-shadow: 0 0 0 6px rgba(46,204,113,0.35), inset 0 0 0 2px rgba(46,204,113,0.25); }
  60%  { box-shadow: 0 0 0 rgba(46,204,113,0.0), inset 0 0 0 rgba(46,204,113,0.0); }
  100% { box-shadow: 0 0 0 rgba(46,204,113,0.0), inset 0 0 0 rgba(46,204,113,0.0); }
}
.reveal-truth-box { animation: truthFlash 1.6s ease-in-out forwards; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ----------------------------
# Constants
# ----------------------------
ICONS = ["🎩", "🔥", "🧠", "🎮", "⚔️", "🛡️", "🌙", "⚡", "❄️", "🍀", "👑", "🦄"]
POKEAPI_BASE = "https://pokeapi.co/api/v2"
GOAL_PER_PLAYER = 6

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
      turn_index INTEGER NOT NULL DEFAULT 0,   -- index into draft_order
      pick_index INTEGER NOT NULL DEFAULT 0    -- counts total picks made
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
      phase TEXT NOT NULL,
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

def ensure_offer_reveal_columns():
    cols = [r["name"] for r in q("PRAGMA table_info(offer)") or []]
    if "reveal_until" not in cols:
        q("ALTER TABLE offer ADD COLUMN reveal_until TEXT NOT NULL DEFAULT ''")
    if "next_actor_player_id" not in cols:
        q("ALTER TABLE offer ADD COLUMN next_actor_player_id TEXT NOT NULL DEFAULT ''")
    if "next_picker_player_id" not in cols:
        q("ALTER TABLE offer ADD COLUMN next_picker_player_id TEXT NOT NULL DEFAULT ''")

def get_offer(room_code: str):
    return q("SELECT * FROM offer WHERE room_code=?", (room_code,), one=True)

def advance_reveal_if_due(room_code: str):
    """If we're in reveal phase and the 5s timer expired, advance to next private offer."""
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
    if not new_actor or not new_picker:
        return

    create_private_offer(room_code, new_actor, new_picker)

init_db()
ensure_offer_reveal_columns()

# ----------------------------
# PokeAPI helpers (names + sprites)
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

AUTO_REFRESH_MS = 1200

def enable_autorefresh():
    if st.session_state.get("room_code") and st.session_state.get("player_id"):
        st_autorefresh(interval=AUTO_REFRESH_MS, key=f"tick_{st.session_state.room_code}")

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
        "INSERT INTO rooms(room_code, created_at, status, host_player_id, turn_index, pick_index) VALUES(?,?,?,?,0,0)",
        (room_code, now_iso(), "lobby", host_player_id),
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

def next_picker(room_code: str, current_actor_pid: str):
    order = get_order(room_code)
    if not order:
        return None
    i = order.index(current_actor_pid)
    return order[(i + 1) % len(order)]

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
    actor = order[0]
    picker = order[1] if len(order) > 1 else order[0]
    create_private_offer(room_code, actor, picker)

def create_private_offer(room_code: str, actor_pid: str, picker_pid: str):
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

    current_count = roster_count(room_code, picker_pid)
    if current_count >= GOAL_PER_PLAYER:
        return "You already have 6 Pokémon."

    slot = current_count + 1
    q(
        "INSERT INTO rosters(room_code, player_id, slot, pokemon) VALUES(?,?,?,?)",
        (room_code, picker_pid, slot, picked_real)
    )

    picker = get_player(picker_pid)
    lied = (picked_real != picked_shown)
    verdict = "✅ TRUTH" if not lied else "🕵️ LIE REVEALED"
    add_feed(room_code, f"{picker['icon']} {picker['name']} picked **{pretty_name(picked_shown)}** — {verdict} (was {pretty_name(picked_real)}).")

    order = get_order(room_code)
    if not order:
        return None

    new_actor = picker_pid
    new_picker = next_picker(room_code, new_actor)

    players = get_players(room_code)
    done = all(roster_count(room_code, p["player_id"]) >= GOAL_PER_PLAYER for p in players)

    if not done:
        safety = 0
        while new_picker and roster_count(room_code, new_picker) >= GOAL_PER_PLAYER and safety < 50:
            new_picker = next_picker(room_code, new_picker)
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
    """, (
        picked_slot, picked_real, picked_shown, now_iso(),
        reveal_until,
        "" if done else new_actor,
        "" if done else (new_picker or ""),
        room_code
    ))

    if done:
        q("UPDATE rooms SET status='done' WHERE room_code=?", (room_code,))
        add_feed(room_code, "Draft complete.")

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
        st.markdown(f'<div class="poke-img">', unsafe_allow_html=True)
        st.image(url, use_container_width=True)
        st.markdown(f'<div class="poke-name">{label}: {disp}</div>', unsafe_allow_html=True)
        st.markdown(f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="poke-img"><div class="poke-name">{label}: {disp}</div><div class="small-muted">Sprite unavailable</div></div>', unsafe_allow_html=True)

def render_reveal_only(picked_shown: str, picked_real: str):
    """During reveal: show ONLY the picked image. If lie, animate to real. If truth, flash green twice."""
    shown_url = pokemon_sprite_url(picked_shown)
    real_url = pokemon_sprite_url(picked_real)
    lied = (picked_shown != picked_real)

    title = "🎭 Reveal"
    sub = "Everyone can see the pick for a few seconds…"

    if not shown_url:
        # fallback: if sprite missing, just show text
        st.markdown(
            f"<div class='reveal-stage'><div class='reveal-card'>"
            f"<div class='reveal-title'>{title}</div>"
            f"<div class='reveal-sub'>{sub}</div>"
            f"<div class='small-muted'>Sprite unavailable for {pretty_name(picked_shown)}.</div>"
            f"</div></div>",
            unsafe_allow_html=True
        )
        return

    if lied and not real_url:
        # lie but no real sprite; still show shown and then text
        st.markdown(
            f"<div class='reveal-stage'><div class='reveal-card'>"
            f"<div class='reveal-title'>{title}</div>"
            f"<div class='reveal-sub'>{sub}</div>"
            f"<div class='reveal-box'>"
            f"  <img class='reveal-img' src='{shown_url}'/>"
            f"</div>"
            f"<div style='margin-top:10px;' class='badge pill-bad'>🕵️ LIE — actually {pretty_name(picked_real)}</div>"
            f"</div></div>",
            unsafe_allow_html=True
        )
        return

    if lied:
        # Crossfade from shown to real
        st.markdown(
            f"<div class='reveal-stage'><div class='reveal-card'>"
            f"<div class='reveal-title'>{title}</div>"
            f"<div class='reveal-sub'>{sub}</div>"
            f"<div class='reveal-box'>"
            f"  <img class='reveal-img reveal-lie-shown' src='{shown_url}'/>"
            f"  <img class='reveal-img reveal-lie-real'  src='{real_url}'/>"
            f"</div>"
            f"<div style='margin-top:10px;' class='badge pill-bad'>🕵️ LIE REVEALED</div>"
            f"</div></div>",
            unsafe_allow_html=True
        )
    else:
        # Truth: flash green border twice
        st.markdown(
            f"<div class='reveal-stage'><div class='reveal-card'>"
            f"<div class='reveal-title'>{title}</div>"
            f"<div class='reveal-sub'>{sub}</div>"
            f"<div class='reveal-box reveal-truth-box'>"
            f"  <img class='reveal-img' src='{shown_url}'/>"
            f"</div>"
            f"<div style='margin-top:10px;' class='badge pill-good'>✅ TRUTH</div>"
            f"</div></div>",
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
            rc, _pid = create_room(host_name.strip() or "Host", host_icon)
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
            _pid, err = join_room(room_code, name.strip() or "Player", icon)
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
        if room and me and me["is_host"] == 1 and room["status"] == "lobby":
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

        # IMPORTANT: advance reveal BEFORE reading off again
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
                    # ✅ Your requested behavior:
                    # show ONLY the picked image, then animate to the real (if lie) or flash green (if truth)
                    picked_shown = (off["picked_shown"] or "").strip()
                    picked_real = (off["picked_real"] or "").strip()
                    render_reveal_only(picked_shown, picked_real)

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
