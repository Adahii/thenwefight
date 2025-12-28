import os
import sqlite3
import time
import random
import string
from contextlib import contextmanager
from streamlit_autorefresh import st_autorefresh

import streamlit as st
import requests

# ----------------------------
# Config
# ----------------------------
DB_PATH = "game.db"

ICONS = ["🐉", "⚡", "🔥", "💧", "🌿", "🧊", "👻", "🤖", "🦴", "🧠", "🧿", "⭐"]
POKEAPI_BASE = "https://pokeapi.co/api/v2"
# "3D-ish" modern sprites: PokeAPI sprites repo (home)
SPRITE_HOME_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/{id}.png"

# ----------------------------
# DB helpers
# ----------------------------
@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with db() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_code TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'lobby',   -- lobby | drafting | done
            host_player_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            current_turn_index INTEGER NOT NULL DEFAULT 0,
            seed INTEGER NOT NULL
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY,
            room_code TEXT NOT NULL,
            name TEXT NOT NULL,
            icon TEXT NOT NULL,
            is_host INTEGER NOT NULL DEFAULT 0,
            is_ready INTEGER NOT NULL DEFAULT 0,
            join_order INTEGER,
            created_at REAL NOT NULL,
            UNIQUE(room_code, name)
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            room_code TEXT PRIMARY KEY,
            offer_a TEXT,
            offer_b TEXT,
            offer_c TEXT,
            disguised_index INTEGER,    -- 0/1/2 or NULL
            disguised_as TEXT,          -- pokemon name or NULL
            updated_at REAL NOT NULL
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS picks (
            room_code TEXT NOT NULL,
            player_id TEXT NOT NULL,
            pick_index INTEGER NOT NULL,   -- 1..6
            pokemon TEXT NOT NULL,
            created_at REAL NOT NULL,
            PRIMARY KEY (room_code, player_id, pick_index)
        );
        """)

def gen_code(n=5):
    return "".join(random.choice(string.ascii_uppercase) for _ in range(n))

def gen_id():
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(12))

# ----------------------------
# PokeAPI caching
# ----------------------------
@st.cache_data(ttl=24 * 3600)
def fetch_pokemon_names():
    # Fetch a big list (no megas are separate forms; we can filter out "-mega" etc.)
    # This endpoint returns species-like names; forms can still appear in some places,
    # but /pokemon list is pretty consistent.
    url = f"{POKEAPI_BASE}/pokemon?limit=2000"
    data = requests.get(url, timeout=20).json()
    names = [x["name"] for x in data["results"]]
    # Filter out obvious non-base / mega / special forms by name patterns
    bad_substrings = [
        "-mega", "-gmax", "-totem", "-primal", "-cap", "-cosplay",
        "-starter", "-ash", "-busted", "-crowned", "-eternamax",
    ]
    cleaned = []
    for n in names:
        if any(b in n for b in bad_substrings):
            continue
        cleaned.append(n)
    # Title case display
    return cleaned

@st.cache_data(ttl=24 * 3600)
def pokemon_name_to_id(name: str) -> int | None:
    try:
        r = requests.get(f"{POKEAPI_BASE}/pokemon/{name.lower()}", timeout=20)
        if r.status_code != 200:
            return None
        return r.json()["id"]
    except Exception:
        return None

def sprite_url_for(name: str) -> str | None:
    pid = pokemon_name_to_id(name)
    if not pid:
        return None
    return SPRITE_HOME_URL.format(id=pid)

# ----------------------------
# Game logic
# ----------------------------
def create_room(host_name: str, host_icon: str) -> dict:
    room_code = gen_code()
    host_id = gen_id()
    now = time.time()
    seed = random.randint(1, 10_000_000)

    with db() as conn:
        conn.execute(
            "INSERT INTO rooms(room_code, status, host_player_id, created_at, seed) VALUES(?,?,?,?,?)",
            (room_code, "lobby", host_id, now, seed),
        )
        conn.execute(
            "INSERT INTO players(player_id, room_code, name, icon, is_host, is_ready, created_at) VALUES(?,?,?,?,?,?,?)",
            (host_id, room_code, host_name, host_icon, 1, 1, now),
        )
        conn.execute(
            "INSERT OR REPLACE INTO offers(room_code, updated_at) VALUES(?,?)",
            (room_code, now),
        )

    return {"room_code": room_code, "player_id": host_id}

def join_room(room_code: str, name: str, icon: str) -> str:
    pid = gen_id()
    now = time.time()
    with db() as conn:
        room = conn.execute("SELECT * FROM rooms WHERE room_code=?", (room_code,)).fetchone()
        if not room:
            raise ValueError("Room not found.")

        # Prevent duplicate names in same room
        existing = conn.execute(
            "SELECT 1 FROM players WHERE room_code=? AND name=?",
            (room_code, name),
        ).fetchone()
        if existing:
            raise ValueError("That name is taken in this room.")

        conn.execute(
            "INSERT INTO players(player_id, room_code, name, icon, is_host, is_ready, created_at) VALUES(?,?,?,?,?,?,?)",
            (pid, room_code, name, icon, 0, 0, now),
        )
    return pid

def list_players(room_code: str):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM players WHERE room_code=? ORDER BY created_at ASC",
            (room_code,),
        ).fetchall()

def set_ready(player_id: str, ready: bool):
    with db() as conn:
        conn.execute("UPDATE players SET is_ready=? WHERE player_id=?", (1 if ready else 0, player_id))

def start_game(room_code: str):
    with db() as conn:
        room = conn.execute("SELECT * FROM rooms WHERE room_code=?", (room_code,)).fetchone()
        if not room:
            raise ValueError("Room not found.")

        players = conn.execute(
            "SELECT * FROM players WHERE room_code=? ORDER BY created_at ASC",
            (room_code,),
        ).fetchall()

        if len(players) < 2:
            raise ValueError("Need at least 2 players to start.")

        # Everyone ready? (host auto-ready)
        if any(p["is_ready"] == 0 for p in players):
            raise ValueError("All players must be ready before starting.")

        # Assign randomized order
        seed = room["seed"]
        rng = random.Random(seed)
        order = players[:]
        rng.shuffle(order)

        for idx, p in enumerate(order):
            conn.execute("UPDATE players SET join_order=? WHERE player_id=?", (idx, p["player_id"]))

        conn.execute("UPDATE rooms SET status='drafting', current_turn_index=0 WHERE room_code=?", (room_code,))
        # Create first offer
        make_new_offer(conn, room_code)

def get_current_turn_player(conn, room_code: str):
    room = conn.execute("SELECT * FROM rooms WHERE room_code=?", (room_code,)).fetchone()
    if not room:
        return None, None
    idx = room["current_turn_index"]
    players = conn.execute(
        "SELECT * FROM players WHERE room_code=? ORDER BY join_order ASC",
        (room_code,),
    ).fetchall()
    if not players:
        return room, None
    return room, players[idx % len(players)]

def player_pick_count(conn, room_code: str, player_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM picks WHERE room_code=? AND player_id=?",
        (room_code, player_id),
    ).fetchone()
    return int(row["c"])

def make_new_offer(conn, room_code: str):
    names = fetch_pokemon_names()
    # Randomly pick 3 distinct names
    offer = random.sample(names, 3)
    now = time.time()
    conn.execute(
        "INSERT OR REPLACE INTO offers(room_code, offer_a, offer_b, offer_c, disguised_index, disguised_as, updated_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (room_code, offer[0], offer[1], offer[2], None, None, now),
    )

def advance_turn_if_needed(conn, room_code: str):
    # If game finished (everyone has 6 picks), mark done
    players = conn.execute(
        "SELECT * FROM players WHERE room_code=? ORDER BY join_order ASC",
        (room_code,),
    ).fetchall()
    if players and all(player_pick_count(conn, room_code, p["player_id"]) >= 6 for p in players):
        conn.execute("UPDATE rooms SET status='done' WHERE room_code=?", (room_code,))
        return

    room = conn.execute("SELECT * FROM rooms WHERE room_code=?", (room_code,)).fetchone()
    if not room:
        return

    # Find next player who still needs picks
    cur = room["current_turn_index"]
    n = len(players)
    for step in range(1, n + 1):
        nxt = (cur + step) % n
        if player_pick_count(conn, room_code, players[nxt]["player_id"]) < 6:
            conn.execute("UPDATE rooms SET current_turn_index=? WHERE room_code=?", (nxt, room_code))
            make_new_offer(conn, room_code)
            return

def disguise_offer(room_code: str, player_id: str, which_idx: int, disguised_as: str):
    with db() as conn:
        room, cur_player = get_current_turn_player(conn, room_code)
        if not room or room["status"] != "drafting":
            raise ValueError("Not currently drafting.")
        if not cur_player or cur_player["player_id"] != player_id:
            raise ValueError("It is not your turn.")
        if player_pick_count(conn, room_code, player_id) >= 6:
            raise ValueError("You already have 6 Pokémon.")

        now = time.time()
        conn.execute(
            "UPDATE offers SET disguised_index=?, disguised_as=?, updated_at=? WHERE room_code=?",
            (which_idx, disguised_as, now, room_code),
        )

def take_pick(room_code: str, player_id: str, chosen_name: str):
    with db() as conn:
        room, cur_player = get_current_turn_player(conn, room_code)
        if not room or room["status"] != "drafting":
            raise ValueError("Not currently drafting.")
        if not cur_player or cur_player["player_id"] != player_id:
            raise ValueError("It is not your turn.")
        if player_pick_count(conn, room_code, player_id) >= 6:
            raise ValueError("You already have 6 Pokémon.")

        offer = conn.execute("SELECT * FROM offers WHERE room_code=?", (room_code,)).fetchone()
        if not offer:
            raise ValueError("Offer missing.")

        # Apply disguise if chosen is the disguised "look"
        # For simplicity, we let the chooser pick among displayed cards exactly.
        # We'll compute the displayed list.
        base = [offer["offer_a"], offer["offer_b"], offer["offer_c"]]
        displayed = base[:]
        if offer["disguised_index"] is not None and offer["disguised_as"]:
            displayed[int(offer["disguised_index"])] = offer["disguised_as"]

        if chosen_name not in displayed:
            raise ValueError("Invalid selection.")

        # What do they actually receive?
        # If they chose the disguised card name, they still receive the original base pokemon in that slot.
        received = chosen_name
        if offer["disguised_index"] is not None and offer["disguised_as"]:
            di = int(offer["disguised_index"])
            if chosen_name == offer["disguised_as"]:
                received = base[di]

        pick_num = player_pick_count(conn, room_code, player_id) + 1
        conn.execute(
            "INSERT INTO picks(room_code, player_id, pick_index, pokemon, created_at) VALUES(?,?,?,?,?)",
            (room_code, player_id, pick_num, received, time.time()),
        )

        # Advance turn and create next offer
        advance_turn_if_needed(conn, room_code)

def get_my_picks(room_code: str, player_id: str):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM picks WHERE room_code=? AND player_id=? ORDER BY pick_index ASC",
            (room_code, player_id),
        ).fetchall()

def get_room(room_code: str):
    with db() as conn:
        return conn.execute("SELECT * FROM rooms WHERE room_code=?", (room_code,)).fetchone()

def get_offer(room_code: str):
    with db() as conn:
        return conn.execute("SELECT * FROM offers WHERE room_code=?", (room_code,)).fetchone()

# ----------------------------
# UI helpers
# ----------------------------
def inject_css():
    st.markdown(
        """
        <style>
          .block-container { padding-top: 2rem; max-width: 1100px; }
          .card {
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 18px;
            padding: 16px;
            background: rgba(255,255,255,0.03);
            backdrop-filter: blur(8px);
          }
          .pill {
            display:inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(255,255,255,0.04);
            margin-right: 6px;
          }
          .title { font-size: 28px; font-weight: 800; letter-spacing:-0.5px; }
          .subtle { opacity: 0.75; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def pokemon_card(name: str):
    url = sprite_url_for(name)
    disp = name.replace("-", " ").title()
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    with c1:
        if url:
            st.image(url, use_container_width=True)
        else:
            st.write("No sprite")
    with c2:
        st.markdown(f"### {disp}")
        st.caption(name)
    st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# App
# ----------------------------
st.set_page_config(page_title="Then We Fight — Draft Lobby", page_icon="🎲", layout="wide")
inject_css()
init_db()

# Session init
if "room_code" not in st.session_state:
    st.session_state.room_code = None
if "player_id" not in st.session_state:
    st.session_state.player_id = None

st.markdown('<div class="title">Then We Fight</div>', unsafe_allow_html=True)
st.markdown('<div class="subtle">Host / Join • Lobby • Random 3 • Disguise 1 • Draft to 6 • 1.0.1</div>', unsafe_allow_html=True)
st.write("")

# Auto-refresh for syncing
# Lightweight: rerun every 2 seconds once in-room
if st.session_state.room_code:
    time.sleep(0.2)
    st_autorefresh(interval=2000, key="tick")

# Not in a room: Host / Join
if not st.session_state.room_code:
    tabs = st.tabs(["Host", "Join"])
    with tabs[0]:
        st.subheader("Host a room")
        host_name = st.text_input("Your name", value="Host")
        host_icon = st.selectbox("Icon", ICONS, index=0)
        if st.button("Create Room", use_container_width=True):
            info = create_room(host_name.strip() or "Host", host_icon)
            st.session_state.room_code = info["room_code"]
            st.session_state.player_id = info["player_id"]
            st.rerun()

    with tabs[1]:
        st.subheader("Join a room")
        room_code = st.text_input("Room code", value="").upper().strip()
        name = st.text_input("Your name", value="")
        icon = st.selectbox("Icon", ICONS, index=1)
        if st.button("Join", use_container_width=True):
            try:
                pid = join_room(room_code, name.strip() or "Player", icon)
                st.session_state.room_code = room_code
                st.session_state.player_id = pid
                st.rerun()
            except Exception as e:
                st.error(str(e))

    st.stop()

# In a room
room_code = st.session_state.room_code
player_id = st.session_state.player_id
room = get_room(room_code)
if not room:
    st.error("Room not found (it may have been deleted).")
    if st.button("Back"):
        st.session_state.room_code = None
        st.session_state.player_id = None
        st.rerun()
    st.stop()

players = list_players(room_code)
me = next((p for p in players if p["player_id"] == player_id), None)

top = st.columns([2, 1])
with top[0]:
    st.markdown(f"**Room:** `{room_code}`")
with top[1]:
    if st.button("Leave room", use_container_width=True):
        st.session_state.room_code = None
        st.session_state.player_id = None
        st.rerun()

st.write("")

# Lobby
if room["status"] == "lobby":
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Lobby")
        st.caption("Set your name + icon, then Ready. Host can start once everyone is ready.")

        st.markdown("#### Players")
        for p in players:
            badge = "✅ Ready" if p["is_ready"] else "⏳ Not ready"
            host = " (Host)" if p["is_host"] else ""
            st.markdown(f"- {p['icon']} **{p['name']}**{host} — {badge}")

    with right:
        st.subheader("Your status")
        if me:
            st.markdown(f"<span class='pill'>You: {me['icon']} {me['name']}</span>", unsafe_allow_html=True)
            ready = st.toggle("Ready", value=bool(me["is_ready"]))
            if ready != bool(me["is_ready"]):
                set_ready(player_id, ready)
                st.rerun()

        st.divider()

        is_host = bool(me and me["is_host"])
        if is_host:
            if st.button("Start game", use_container_width=True):
                try:
                    start_game(room_code)
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        else:
            st.info("Waiting for host to start…")

    st.stop()

# Drafting / Done views
with db() as conn:
    room2, cur_player = get_current_turn_player(conn, room_code)

st.subheader("Draft")

# Show current order
order = sorted([p for p in players if p["join_order"] is not None], key=lambda x: x["join_order"])
if order:
    pills = []
    for p in order:
        pills.append(f"<span class='pill'>{p['join_order']+1}. {p['icon']} {p['name']}</span>")
    st.markdown("".join(pills), unsafe_allow_html=True)

if room["status"] == "done":
    st.success("Draft complete!")
    st.markdown("### Your team")
    myp = get_my_picks(room_code, player_id)
    cols = st.columns(3)
    for i, pk in enumerate(myp):
        with cols[i % 3]:
            pokemon_card(pk["pokemon"])
    st.stop()

# Drafting
offer = get_offer(room_code)
my_turn = (cur_player is not None and cur_player["player_id"] == player_id)

st.markdown(f"**Current turn:** {cur_player['icon']} **{cur_player['name']}**" if cur_player else "**Current turn:** (none)")
myp = get_my_picks(room_code, player_id)
st.caption(f"You have {len(myp)}/6 picks.")

# Show my team
with st.expander("My team so far", expanded=False):
    cols = st.columns(3)
    for i, pk in enumerate(myp):
        with cols[i % 3]:
            pokemon_card(pk["pokemon"])

# Offer display
base = [offer["offer_a"], offer["offer_b"], offer["offer_c"]]
displayed = base[:]
if offer["disguised_index"] is not None and offer["disguised_as"]:
    displayed[int(offer["disguised_index"])] = offer["disguised_as"]

st.markdown("### Offer")
cA, cB, cC = st.columns(3)
for col, name in zip([cA, cB, cC], displayed):
    with col:
        pokemon_card(name)

# Turn actions
st.markdown("### Actions")
if not my_turn:
    st.info("Waiting for your turn…")
else:
    st.success("It’s your turn!")

    names = fetch_pokemon_names()

    with st.expander("Disguise one Pokémon (optional)", expanded=True):
        which = st.radio("Which card to disguise?", [0, 1, 2], format_func=lambda i: f"Card {i+1}: {displayed[i].replace('-', ' ').title()}")
        disguised_as = st.selectbox(
            "Disguise as (autocomplete list)",
            options=names,
            index=0,
        )
        if st.button("Apply disguise", use_container_width=True):
            try:
                disguise_offer(room_code, player_id, which, disguised_as)
                st.rerun()
            except Exception as e:
                st.error(str(e))

    st.divider()

    chosen = st.radio("Pick one", displayed, format_func=lambda n: n.replace("-", " ").title())
    if st.button("Take pick", use_container_width=True):
        try:
            take_pick(room_code, player_id, chosen)
            st.rerun()
        except Exception as e:
            st.error(str(e))
