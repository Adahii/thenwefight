import os
import time
import json
import random
import string
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# -----------------------------
# App Config / Theme Helpers
# -----------------------------
st.set_page_config(page_title="ThenWeFight Draft", page_icon="🎮", layout="wide")

APP_TITLE = "ThenWeFight Draft"
DB_PATH = os.environ.get("TWF_DB_PATH", "thenwefight.sqlite")

ICONS = ["🧢", "🔥", "💧", "🌿", "⚡", "🧠", "👻", "🦾", "🐉", "⭐", "🎲", "🗡️", "🛡️", "🧪", "🎯"]


# -----------------------------
# SQLite (WAL for multi-user)
# -----------------------------
def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db():
    conn = db_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        room_code TEXT PRIMARY KEY,
        created_at INTEGER NOT NULL,
        status TEXT NOT NULL,          -- lobby | drafting | finished
        goal_picks INTEGER NOT NULL,
        seed INTEGER NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS players (
        player_id TEXT PRIMARY KEY,
        room_code TEXT NOT NULL,
        name TEXT NOT NULL,
        icon TEXT NOT NULL,
        is_host INTEGER NOT NULL,
        joined_at INTEGER NOT NULL,
        FOREIGN KEY(room_code) REFERENCES rooms(room_code) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS game_state (
        room_code TEXT PRIMARY KEY,
        started_at INTEGER,
        turn_index INTEGER NOT NULL,     -- index into order list
        round_picks INTEGER NOT NULL,    -- total picks made (global)
        order_json TEXT NOT NULL,        -- list of player_ids
        current_offer_id TEXT,           -- current offer primary key
        phase TEXT NOT NULL,             -- private_offer | public_pick | reveal | finished
        last_event_json TEXT,            -- last reveal details
        FOREIGN KEY(room_code) REFERENCES rooms(room_code) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS offers (
        offer_id TEXT PRIMARY KEY,
        room_code TEXT NOT NULL,
        player_id TEXT NOT NULL,         -- whose turn it is
        created_at INTEGER NOT NULL,
        real_json TEXT NOT NULL,         -- 3 real names
        disguise_slot INTEGER NOT NULL,  -- 0-2
        disguise_as TEXT NOT NULL,       -- replacement name (public)
        displayed_json TEXT NOT NULL,    -- 3 displayed names after disguise
        is_displayed INTEGER NOT NULL,   -- 0/1
        picked_slot INTEGER,             -- 0-2
        picked_name TEXT,
        resolved_at INTEGER,
        FOREIGN KEY(room_code) REFERENCES rooms(room_code) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS picks (
        pick_id TEXT PRIMARY KEY,
        room_code TEXT NOT NULL,
        player_id TEXT NOT NULL,
        picked_at INTEGER NOT NULL,
        pokemon_name TEXT NOT NULL,
        offer_id TEXT NOT NULL,
        FOREIGN KEY(room_code) REFERENCES rooms(room_code) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS feed (
        feed_id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_code TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        message TEXT NOT NULL,
        FOREIGN KEY(room_code) REFERENCES rooms(room_code) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()


def now_ts() -> int:
    return int(time.time())


def uid(n=12) -> str:
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n))


def room_code(n=5) -> str:
    return "".join(random.choice(string.ascii_uppercase) for _ in range(n))


def db_one(q: str, params=()) -> Optional[sqlite3.Row]:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(q, params)
    row = cur.fetchone()
    conn.close()
    return row


def db_all(q: str, params=()) -> List[sqlite3.Row]:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def db_exec(q: str, params=()):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(q, params)
    conn.commit()
    conn.close()


def db_execmany(q: str, seq_params: List[tuple]):
    conn = db_conn()
    cur = conn.cursor()
    cur.executemany(q, seq_params)
    conn.commit()
    conn.close()


def add_feed(room: str, msg: str):
    db_exec(
        "INSERT INTO feed(room_code, created_at, message) VALUES (?, ?, ?)",
        (room, now_ts(), msg)
    )


# -----------------------------
# Pokémon data (PokeAPI)
# -----------------------------
POKEAPI_ALL = "https://pokeapi.co/api/v2/pokemon?limit=200000"

# Filters: keep it simple (no megas, no gmax, no totems, etc.)
BAD_SUBSTRINGS = [
    "mega", "gmax", "totem", "cap", "primal", "eternamax",
    "starter", "cosplay", "battle-bond", "ash", "original",
]

# Some forms show up as hyphenated variants; we keep most, but you can tighten later.
def is_allowed_pokemon(name: str) -> bool:
    n = name.lower().strip()
    if any(s in n for s in BAD_SUBSTRINGS):
        return False
    # extremely noisy patterns (optional)
    if n.endswith("-mega") or "-mega-" in n:
        return False
    return True


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def get_all_pokemon_names() -> List[str]:
    r = requests.get(POKEAPI_ALL, timeout=30)
    r.raise_for_status()
    data = r.json()
    names = [x["name"] for x in data["results"]]
    names = [n for n in names if is_allowed_pokemon(n)]
    # Pretty-ish sorting
    names = sorted(set(names))
    return names


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def get_pokemon_sprite_urls(name: str) -> Dict[str, Optional[str]]:
    """
    Returns {'home': url_or_none, 'art': url_or_none}
    """
    url = f"https://pokeapi.co/api/v2/pokemon/{name.lower().strip()}"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return {"home": None, "art": None}
    d = r.json()

    home = (
        d.get("sprites", {})
         .get("other", {})
         .get("home", {})
         .get("front_default")
    )
    art = (
        d.get("sprites", {})
         .get("other", {})
         .get("official-artwork", {})
         .get("front_default")
    )
    return {"home": home, "art": art}


def display_name(n: str) -> str:
    # convert "mr-mime" -> "Mr Mime" etc
    return n.replace("-", " ").title()


def sprite_url_for(name: str) -> Optional[str]:
    u = get_pokemon_sprite_urls(name)
    return u.get("home") or u.get("art")


# -----------------------------
# Room / Player / Game logic
# -----------------------------
def create_room_db(host_name: str, host_icon: str, goal_picks: int = 6) -> Dict[str, str]:
    code = room_code()
    seed = random.randint(1, 2_000_000_000)

    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO rooms(room_code, created_at, status, goal_picks, seed) VALUES (?, ?, ?, ?, ?)",
        (code, now_ts(), "lobby", goal_picks, seed),
    )

    host_id = uid()
    cur.execute(
        "INSERT INTO players(player_id, room_code, name, icon, is_host, joined_at) VALUES (?, ?, ?, ?, ?, ?)",
        (host_id, code, host_name, host_icon, 1, now_ts()),
    )

    # initial game state (order will be written on start)
    cur.execute(
        "INSERT INTO game_state(room_code, started_at, turn_index, round_picks, order_json, current_offer_id, phase, last_event_json) "
        "VALUES (?, NULL, 0, 0, ?, NULL, ?, NULL)",
        (code, json.dumps([]), "private_offer"),
    )

    conn.commit()
    conn.close()

    add_feed(code, f"{host_icon} {host_name} created the room.")
    return {"room_code": code, "player_id": host_id}


def join_room_db(code: str, name: str, icon: str) -> Optional[str]:
    room = db_one("SELECT * FROM rooms WHERE room_code = ?", (code,))
    if not room:
        return None
    if room["status"] != "lobby":
        # allow late joins? for now, block once started
        return None

    pid = uid()
    db_exec(
        "INSERT INTO players(player_id, room_code, name, icon, is_host, joined_at) VALUES (?, ?, ?, ?, ?, ?)",
        (pid, code, name, icon, 0, now_ts()),
    )
    add_feed(code, f"{icon} {name} joined the room.")
    return pid


def list_players(code: str) -> List[sqlite3.Row]:
    return db_all("SELECT * FROM players WHERE room_code = ? ORDER BY joined_at ASC", (code,))


def player_by_id(pid: str) -> Optional[sqlite3.Row]:
    return db_one("SELECT * FROM players WHERE player_id = ?", (pid,))


def get_room(code: str) -> Optional[sqlite3.Row]:
    return db_one("SELECT * FROM rooms WHERE room_code = ?", (code,))


def get_state(code: str) -> Optional[sqlite3.Row]:
    return db_one("SELECT * FROM game_state WHERE room_code = ?", (code,))


def set_state(code: str, **kwargs):
    keys = list(kwargs.keys())
    vals = list(kwargs.values())
    sets = ", ".join([f"{k} = ?" for k in keys])
    db_exec(f"UPDATE game_state SET {sets} WHERE room_code = ?", (*vals, code))


def set_room_status(code: str, status: str):
    db_exec("UPDATE rooms SET status = ? WHERE room_code = ?", (status, code))


def picks_for_player(code: str, pid: str) -> List[sqlite3.Row]:
    return db_all(
        "SELECT * FROM picks WHERE room_code = ? AND player_id = ? ORDER BY picked_at ASC",
        (code, pid),
    )


def all_picks(code: str) -> List[sqlite3.Row]:
    return db_all("SELECT * FROM picks WHERE room_code = ? ORDER BY picked_at ASC", (code,))


def random_real_options(code: str, exclude_names: List[str], k: int = 3) -> List[str]:
    # deterministic-ish per room seed, but still random per offer
    # we just use python random, but avoid duplicates and already picked
    names = get_all_pokemon_names()
    exclude = set(n.lower() for n in exclude_names)
    pool = [n for n in names if n.lower() not in exclude]

    # ensure truly randomized and unique
    if len(pool) < k:
        pool = names[:]  # fallback
    return random.sample(pool, k=k)


def current_turn_player_id(state: sqlite3.Row) -> Optional[str]:
    order = json.loads(state["order_json"] or "[]")
    if not order:
        return None
    idx = int(state["turn_index"])
    return order[idx % len(order)]


def everyone_done(code: str) -> bool:
    room = get_room(code)
    if not room:
        return True
    goal = int(room["goal_picks"])
    players = list_players(code)
    for p in players:
        if len(picks_for_player(code, p["player_id"])) < goal:
            return False
    return True


def start_game(code: str):
    room = get_room(code)
    if not room or room["status"] != "lobby":
        return

    players = list_players(code)
    if len(players) < 2:
        add_feed(code, "Need at least 2 players to start.")
        return

    # random draft order
    pids = [p["player_id"] for p in players]
    random.shuffle(pids)

    set_room_status(code, "drafting")
    set_state(code,
              started_at=now_ts(),
              order_json=json.dumps(pids),
              turn_index=0,
              round_picks=0,
              current_offer_id=None,
              phase="private_offer",
              last_event_json=None)

    add_feed(code, "Game started. Drafting begins!")
    add_feed(code, "Draft order assigned.")

    # create the first offer (private)
    ensure_offer_exists(code)


def ensure_offer_exists(code: str):
    """
    Creates a private offer for the current turn player if none exists,
    or if the previous one was resolved and we moved to next turn.
    """
    state = get_state(code)
    if not state:
        return

    if everyone_done(code):
        set_state(code, phase="finished")
        set_room_status(code, "finished")
        add_feed(code, "Draft finished!")
        return

    offer_id = state["current_offer_id"]
    if offer_id:
        offer = db_one("SELECT * FROM offers WHERE offer_id = ?", (offer_id,))
        if offer and offer["resolved_at"] is None:
            # still active
            return

    # create new offer for current turn player
    turn_pid = current_turn_player_id(state)
    if not turn_pid:
        return

    # exclude already picked pokemon globally so pool stays diverse
    picked = [r["pokemon_name"] for r in all_picks(code)]
    real = random_real_options(code, picked, k=3)

    new_offer_id = uid(14)
    db_exec(
        "INSERT INTO offers(offer_id, room_code, player_id, created_at, real_json, disguise_slot, disguise_as, displayed_json, is_displayed, picked_slot, picked_name, resolved_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)",
        (new_offer_id, code, turn_pid, now_ts(), json.dumps(real), 0, real[0], json.dumps(real), 0),
    )

    set_state(code, current_offer_id=new_offer_id, phase="private_offer", last_event_json=None)


def display_selections(code: str, offer_id: str, disguise_slot: int, disguise_as: str):
    offer = db_one("SELECT * FROM offers WHERE offer_id = ?", (offer_id,))
    if not offer:
        return

    real = json.loads(offer["real_json"])
    ds = int(disguise_slot)
    ds = max(0, min(2, ds))

    # displayed list: one slot becomes disguise_as
    displayed = real[:]
    displayed[ds] = disguise_as

    db_exec(
        "UPDATE offers SET disguise_slot = ?, disguise_as = ?, displayed_json = ?, is_displayed = ? WHERE offer_id = ?",
        (ds, disguise_as, json.dumps(displayed), 1, offer_id),
    )

    set_state(code, phase="public_pick")
    p = player_by_id(offer["player_id"])
    add_feed(code, f"{p['icon']} {p['name']} displayed the selections.")


def lock_pick(code: str, offer_id: str, picked_slot: int):
    offer = db_one("SELECT * FROM offers WHERE offer_id = ?", (offer_id,))
    if not offer or int(offer["is_displayed"]) != 1 or offer["resolved_at"] is not None:
        return

    displayed = json.loads(offer["displayed_json"])
    real = json.loads(offer["real_json"])
    ps = int(picked_slot)
    ps = max(0, min(2, ps))
    picked_name = displayed[ps]

    # record pick
    db_exec(
        "INSERT INTO picks(pick_id, room_code, player_id, picked_at, pokemon_name, offer_id) VALUES (?, ?, ?, ?, ?, ?)",
        (uid(14), code, offer["player_id"], now_ts(), picked_name, offer_id),
    )

    # resolve offer
    db_exec(
        "UPDATE offers SET picked_slot = ?, picked_name = ?, resolved_at = ? WHERE offer_id = ?",
        (ps, picked_name, now_ts(), offer_id),
    )

    # reveal logic
    disguise_slot = int(offer["disguise_slot"])
    disguise_as = offer["disguise_as"]
    was_disguised_pick = (ps == disguise_slot)
    truth = (not was_disguised_pick)
    real_at_slot = real[disguise_slot]

    event = {
        "offer_id": offer_id,
        "picker_id": offer["player_id"],
        "displayed": displayed,
        "real": real,
        "disguise_slot": disguise_slot,
        "disguise_as": disguise_as,
        "real_at_disguise_slot": real_at_slot,
        "picked_slot": ps,
        "picked_name": picked_name,
        "truth": truth,
    }
    set_state(code, phase="reveal", last_event_json=json.dumps(event))

    p = player_by_id(offer["player_id"])
    add_feed(code, f"{p['icon']} {p['name']} picked **{display_name(picked_name)}**. Reveal!")

    # advance turn if that player hasn't finished yet? (we always advance)
    advance_turn(code)


def advance_turn(code: str):
    state = get_state(code)
    if not state:
        return

    order = json.loads(state["order_json"] or "[]")
    if not order:
        return

    # move to next player who still needs picks
    room = get_room(code)
    goal = int(room["goal_picks"]) if room else 6

    start_idx = int(state["turn_index"])
    n = len(order)
    for step in range(1, n + 1):
        idx = (start_idx + step) % n
        pid = order[idx]
        if len(picks_for_player(code, pid)) < goal:
            set_state(code, turn_index=idx, current_offer_id=None, phase="private_offer")
            ensure_offer_exists(code)
            return

    # if nobody needs picks, finish
    set_state(code, phase="finished")
    set_room_status(code, "finished")
    add_feed(code, "Draft finished!")


def get_offer(offer_id: str) -> Optional[sqlite3.Row]:
    return db_one("SELECT * FROM offers WHERE offer_id = ?", (offer_id,))


def get_feed(code: str, limit: int = 50) -> List[sqlite3.Row]:
    return db_all(
        "SELECT * FROM feed WHERE room_code = ? ORDER BY feed_id DESC LIMIT ?",
        (code, limit),
    )


# -----------------------------
# UI helpers
# -----------------------------
def inject_css():
    st.markdown(
        """
        <style>
          .twf-subtitle { opacity: 0.8; margin-top: -6px; }
          .pill {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.04);
            margin-right: 8px;
            font-size: 13px;
          }
          .card {
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            padding: 14px 14px;
          }
          .muted { opacity: 0.72; }
          .offer-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
          }
          .poke-card {
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(255,255,255,0.04);
            border-radius: 18px;
            padding: 12px;
            min-height: 210px;
          }
          .poke-name {
            font-weight: 700;
            font-size: 18px;
            margin-top: 6px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_pokemon_card(name: str, label: str):
    url = sprite_url_for(name)
    st.markdown(f"<div class='poke-card'>", unsafe_allow_html=True)
    st.markdown(f"<div class='muted'>{label}</div>", unsafe_allow_html=True)
    if url:
        st.image(url, use_container_width=True)
    else:
        st.write("🖼️ (sprite missing)")
    st.markdown(f"<div class='poke-name'>{display_name(name)}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# Main App
# -----------------------------
init_db()
inject_css()

# Keep app responsive / synced between players
st_autorefresh(interval=1500, key="tick")  # 1.5s

if "player_id" not in st.session_state:
    st.session_state.player_id = None
if "room_code" not in st.session_state:
    st.session_state.room_code = None

# Header
left, right = st.columns([1.2, 2.4], gap="large")

with left:
    st.markdown(f"## 🎮 {APP_TITLE}")
    st.markdown("<div class='twf-subtitle'>Pure Python · Streamlit · SQLite · <b>No Supabase</b></div>", unsafe_allow_html=True)
    st.write("")

    mode = st.radio("Mode", ["Host", "Join"], horizontal=True)

    if mode == "Host":
        host_name = st.text_input("Your name", value="Host")
        host_icon = st.selectbox("Icon", ICONS, index=0)

        if st.button("Create Room", use_container_width=True):
            info = create_room_db(host_name.strip() or "Host", host_icon)
            st.session_state.room_code = info["room_code"]
            st.session_state.player_id = info["player_id"]
            st.rerun()

    else:
        code = st.text_input("Room code", value=(st.session_state.room_code or "")).strip().upper()
        join_name = st.text_input("Your name", value="Player")
        join_icon = st.selectbox("Icon", ICONS, index=1)

        if st.button("Join Room", use_container_width=True):
            pid = join_room_db(code, join_name.strip() or "Player", join_icon)
            if not pid:
                st.error("Could not join. Check room code, or the game already started.")
            else:
                st.session_state.room_code = code
                st.session_state.player_id = pid
                st.rerun()

    # Room status box
    if st.session_state.room_code and st.session_state.player_id:
        st.write("---")
        st.markdown(f"**Room:** `{st.session_state.room_code}`")
        st.markdown(f"**You:** `{st.session_state.player_id}`")

        room = get_room(st.session_state.room_code)
        if room:
            st.markdown(f"**Status:** `{room['status']}`")


with right:
    code = st.session_state.room_code
    pid = st.session_state.player_id

    if not code or not pid:
        st.info("Create a room or join one to begin.")
        st.stop()

    room = get_room(code)
    state = get_state(code)
    if not room or not state:
        st.error("Room not found (or DB missing state).")
        st.stop()

    players = list_players(code)
    me = player_by_id(pid)
    if not me:
        st.error("Player not found.")
        st.stop()

    goal = int(room["goal_picks"])
    order = json.loads(state["order_json"] or "[]")
    turn_pid = current_turn_player_id(state)
    turn_player = player_by_id(turn_pid) if turn_pid else None

    # Top pills
    pills = []
    if turn_player:
        pills.append(f"Turn: {turn_player['icon']} {turn_player['name']}")
    pills.append(f"Players: {len(players)}")
    pills.append(f"Goal: {goal} each")
    st.markdown(" ".join([f"<span class='pill'>{p}</span>" for p in pills]), unsafe_allow_html=True)

    # Stats
    my_picks = len(picks_for_player(code, pid))
    total_picks = len(all_picks(code))
    need_total = goal * len(players)

    s1, s2 = st.columns(2)
    with s1:
        st.metric("Your picks", my_picks, delta=f"{goal-my_picks} left")
    with s2:
        st.metric("Total picks", total_picks, delta=f"{need_total-total_picks} of {need_total}")

    st.write("---")

    # Lobby / Start button
    if room["status"] == "lobby":
        st.markdown("### 🧩 Lobby")
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        for p in players:
            st.write(f"{p['icon']} **{p['name']}**" + (" *(host)*" if p["is_host"] else ""))
        st.markdown("</div>", unsafe_allow_html=True)

        if me["is_host"]:
            c1, c2 = st.columns([1, 2])
            with c1:
                if st.button("Start Game", use_container_width=True):
                    start_game(code)
                    st.rerun()
            with c2:
                st.caption("Once started, no late joins (for now).")

        st.write("---")

    # Drafting / Finished
    if room["status"] in ("drafting", "finished"):
        ensure_offer_exists(code)  # keep offer populated
        state = get_state(code)    # refresh

        offer_id = state["current_offer_id"]
        offer = get_offer(offer_id) if offer_id else None

        st.markdown("### 🎴 Current Offer")

        if state["phase"] == "finished" or room["status"] == "finished":
            st.success("Draft complete! 🎉")
        elif not offer:
            st.info("Preparing next offer…")
        else:
            is_my_turn = (offer["player_id"] == pid)
            real = json.loads(offer["real_json"])
            displayed = json.loads(offer["displayed_json"])
            is_displayed = int(offer["is_displayed"]) == 1

            # PRIVATE OFFER PHASE (only current player sees real options + disguise controls)
            if not is_displayed and is_my_turn:
                st.info("Only you can see the **real** Pokémon right now. Choose one slot to disguise, then display to everyone.")

                st.markdown("**Real options (private):**")
                st.markdown(f"{display_name(real[0])} · {display_name(real[1])} · {display_name(real[2])}")

                st.write("")
                slot = st.radio(
                    "Which one do you want to disguise?",
                    options=[0, 1, 2],
                    format_func=lambda i: f"Slot {i+1}: {display_name(real[i])}",
                    horizontal=True
                )

                all_names = get_all_pokemon_names()
                disguise_as = st.selectbox(
                    "Disguise it as (autocomplete)",
                    options=all_names,
                    index=0
                )

                if st.button("✅ Display selections to everyone", use_container_width=True):
                    display_selections(code, offer_id, slot, disguise_as)
                    st.rerun()

            elif not is_displayed and not is_my_turn:
                st.warning("Waiting for the current player to prepare and display the selections…")

            # PUBLIC PICK PHASE (everyone sees displayed set; only current player can lock pick)
            if is_displayed:
                st.success("Selections are displayed to everyone:")

                cols = st.columns(3)
                for i in range(3):
                    with cols[i]:
                        render_pokemon_card(displayed[i], f"Slot {i+1}")

                st.write("")
                if is_my_turn:
                    st.markdown("### ✅ Pick Phase (your turn)")
                    ps = st.radio(
                        "Pick one:",
                        options=[0, 1, 2],
                        format_func=lambda i: display_name(displayed[i]),
                        horizontal=True
                    )
                    if st.button("Lock in pick", use_container_width=True):
                        lock_pick(code, offer_id, ps)
                        st.rerun()
                else:
                    st.info("Waiting for the current player to lock in their pick…")

        st.write("---")

        # REVEAL PANEL (everyone sees)
        if state["last_event_json"]:
            event = json.loads(state["last_event_json"])
            picker = player_by_id(event["picker_id"])
            if picker:
                st.markdown("### 🕵️ Reveal")
                st.markdown("<div class='card'>", unsafe_allow_html=True)

                disp = event["displayed"]
                real = event["real"]
                ds = int(event["disguise_slot"])
                picked_slot = int(event["picked_slot"])
                truth = bool(event["truth"])

                st.write(f"Picker: {picker['icon']} **{picker['name']}**")
                st.write(f"Picked: **{display_name(event['picked_name'])}** (Slot {picked_slot+1})")

                if truth:
                    st.success("✅ Truth! They did **not** pick the disguised slot.")
                else:
                    st.error("❌ Lie detected! They picked the **disguised** slot.")

                st.write("")
                cA, cB, cC = st.columns(3)
                for i, c in enumerate([cA, cB, cC]):
                    with c:
                        label = f"Slot {i+1} (displayed)"
                        render_pokemon_card(disp[i], label)
                        if i == ds:
                            st.caption(f"🔎 Real was: {display_name(real[i])}")
                        else:
                            st.caption(f"✅ Real was: {display_name(real[i])}")

                st.markdown("</div>", unsafe_allow_html=True)

        st.write("---")

        # Public Feed + Rosters
        fcol, rcol = st.columns([1.6, 1.0], gap="large")

        with fcol:
            st.markdown("### 📣 Public Feed (everyone sees)")
            feed = get_feed(code, limit=40)
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            if not feed:
                st.write("No events yet.")
            else:
                for row in reversed(feed):
                    st.write("• " + row["message"])
            st.markdown("</div>", unsafe_allow_html=True)

        with rcol:
            st.markdown("### 🧾 Rosters")
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            for p in players:
                roster = [x["pokemon_name"] for x in picks_for_player(code, p["player_id"])]
                st.write(f"{p['icon']} **{p['name']}** ({len(roster)}/{goal})")
                if roster:
                    st.caption(", ".join(display_name(x) for x in roster))
                st.write("")
            st.markdown("</div>", unsafe_allow_html=True)
