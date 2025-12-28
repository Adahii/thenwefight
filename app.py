import os
import json
import time
import random
import string
import sqlite3
from dataclasses import dataclass
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ----------------------------
# Config
# ----------------------------
DB_PATH = "game.db"
PICKS_PER_PLAYER = 6
OFFER_SIZE = 3
REFRESH_MS = 1500

ICONS = ["🧢", "🎮", "⚡", "🔥", "🌊", "🌿", "🧠", "👑", "🐉", "🦊", "🐸", "🦁"]

# ----------------------------
# Helpers
# ----------------------------
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            room_code TEXT PRIMARY KEY,
            host_player_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'lobby',          -- lobby | drafting | done
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY,
            room_code TEXT NOT NULL,
            name TEXT NOT NULL,
            icon TEXT NOT NULL,
            joined_at INTEGER NOT NULL,
            is_host INTEGER NOT NULL DEFAULT 0,
            seat INTEGER,                                  -- draft order position 0..n-1
            FOREIGN KEY(room_code) REFERENCES rooms(room_code)
        );

        CREATE TABLE IF NOT EXISTS state (
            room_code TEXT PRIMARY KEY,
            turn_index INTEGER NOT NULL DEFAULT 0,          -- whose turn (seat index)
            round_num INTEGER NOT NULL DEFAULT 1,
            picks_json TEXT NOT NULL DEFAULT '[]',          -- list of {player_id, pokemon_true, pokemon_display, was_lie}
            current_offer_json TEXT,                        -- internal offer: {offer_true:[...], disguise_index:int, disguise_to:str, published:bool}
            offer_published INTEGER NOT NULL DEFAULT 0,      -- 0/1
            updated_at INTEGER NOT NULL,
            FOREIGN KEY(room_code) REFERENCES rooms(room_code)
        );

        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            kind TEXT NOT NULL,                             -- info | pick | reveal
            message TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

def now():
    return int(time.time())

def gen_code(n=5):
    return "".join(random.choice(string.ascii_uppercase) for _ in range(n))

def gen_id(n=12):
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n))

def add_log(room_code, kind, message):
    conn = db()
    conn.execute(
        "INSERT INTO logs(room_code, created_at, kind, message) VALUES(?,?,?,?)",
        (room_code, now(), kind, message),
    )
    conn.commit()
    conn.close()

def get_room(room_code):
    conn = db()
    r = conn.execute("SELECT * FROM rooms WHERE room_code=?", (room_code,)).fetchone()
    conn.close()
    return r

def get_players(room_code):
    conn = db()
    rows = conn.execute(
        "SELECT * FROM players WHERE room_code=? ORDER BY COALESCE(seat, 999), joined_at",
        (room_code,),
    ).fetchall()
    conn.close()
    return rows

def get_state(room_code):
    conn = db()
    row = conn.execute("SELECT * FROM state WHERE room_code=?", (room_code,)).fetchone()
    conn.close()
    return row

def upsert_state(room_code, **kwargs):
    s = get_state(room_code)
    conn = db()
    if s is None:
        # create default
        conn.execute(
            "INSERT INTO state(room_code, turn_index, round_num, picks_json, current_offer_json, offer_published, updated_at) VALUES(?,?,?,?,?,?,?)",
            (room_code, 0, 1, "[]", None, 0, now()),
        )
    # update provided keys
    cols = []
    vals = []
    for k, v in kwargs.items():
        cols.append(f"{k}=?")
        vals.append(v)
    cols.append("updated_at=?")
    vals.append(now())
    vals.append(room_code)
    conn.execute(f"UPDATE state SET {', '.join(cols)} WHERE room_code=?", vals)
    conn.commit()
    conn.close()

# ----------------------------
# Pokémon list (simple + no-megas)
# ----------------------------
@st.cache_data(show_spinner=False)
def load_pokemon_list():
    """
    Pure-python list for autocomplete. For real completeness you can swap this
    to a PokeAPI fetch + filter, but this keeps it reliable/offline-ish.
    """
    # Gen 1-9 base species-ish list is long; keeping a compact demo list.
    # Replace with a full list file if you want (still Python-only).
    base = [
        "Bulbasaur","Ivysaur","Venusaur","Charmander","Charmeleon","Charizard",
        "Squirtle","Wartortle","Blastoise","Pikachu","Raichu","Eevee","Vaporeon",
        "Jolteon","Flareon","Espeon","Umbreon","Leafeon","Glaceon","Sylveon",
        "Gengar","Dragonite","Tyranitar","Garchomp","Lucario","Greninja",
        "Scizor","Metagross","Salamence","Snorlax","Gyarados","Mimikyu",
        "Aegislash","Zoroark","Dragapult","Haxorus","Arcanine","Lapras",
        "Cinderace","Inteleon","Rillaboom","Meowscarada","Skeledirge","Quaquaval",
    ]
    # No megas by construction (and you can add more non-mega names as desired)
    return sorted(set(base))

def normalize_name(x: str) -> str:
    return x.strip().title()

# ----------------------------
# Core game logic
# ----------------------------
def create_room(host_name, host_icon):
    room_code = gen_code()
    host_id = gen_id()
    conn = db()
    conn.execute(
        "INSERT INTO rooms(room_code, host_player_id, status, created_at) VALUES(?,?,?,?)",
        (room_code, host_id, "lobby", now()),
    )
    conn.execute(
        "INSERT INTO players(player_id, room_code, name, icon, joined_at, is_host) VALUES(?,?,?,?,?,1)",
        (host_id, room_code, host_name, host_icon, now()),
    )
    conn.commit()
    conn.close()
    upsert_state(room_code)  # create initial state
    add_log(room_code, "info", f"{host_icon} {host_name} created the room.")
    return room_code, host_id

def join_room(room_code, name, icon):
    if not get_room(room_code):
        raise ValueError("Room not found.")
    pid = gen_id()
    conn = db()
    conn.execute(
        "INSERT INTO players(player_id, room_code, name, icon, joined_at, is_host) VALUES(?,?,?,?,?,0)",
        (pid, room_code, name, icon, now()),
    )
    conn.commit()
    conn.close()
    add_log(room_code, "info", f"{icon} {name} joined the room.")
    return pid

def assign_seats(room_code):
    players = get_players(room_code)
    # randomize seat order
    pids = [p["player_id"] for p in players]
    random.shuffle(pids)
    conn = db()
    for i, pid in enumerate(pids):
        conn.execute("UPDATE players SET seat=? WHERE player_id=?", (i, pid))
    conn.commit()
    conn.close()
    add_log(room_code, "info", "Draft order assigned.")
    # reset state
    upsert_state(
        room_code,
        turn_index=0,
        round_num=1,
        picks_json="[]",
        current_offer_json=None,
        offer_published=0,
    )

def current_player(room_code):
    players = get_players(room_code)
    s = get_state(room_code)
    if not players or not s:
        return None
    # seat indexes are 0..n-1
    idx = s["turn_index"] % len(players)
    for p in players:
        if p["seat"] == idx:
            return p
    return None

def picks_for_player(picks, player_id):
    return [x for x in picks if x["player_id"] == player_id]

def game_done(room_code):
    players = get_players(room_code)
    s = get_state(room_code)
    if not players or not s:
        return False
    picks = json.loads(s["picks_json"])
    for p in players:
        if len(picks_for_player(picks, p["player_id"])) < PICKS_PER_PLAYER:
            return False
    return True

def ensure_private_offer(room_code, pokemon_pool):
    """
    If no current offer exists, create one (PRIVATE, not published).
    """
    s = get_state(room_code)
    offer = json.loads(s["current_offer_json"]) if s and s["current_offer_json"] else None
    if offer is None:
        offer_true = random.sample(pokemon_pool, k=OFFER_SIZE)
        offer = {
            "offer_true": offer_true,
            "disguise_index": None,
            "disguise_to": None,
            "published": False,
        }
        upsert_state(room_code, current_offer_json=json.dumps(offer), offer_published=0)
        return offer
    return offer

def publish_offer(room_code, disguise_index, disguise_to):
    s = get_state(room_code)
    offer = json.loads(s["current_offer_json"]) if s["current_offer_json"] else None
    if not offer or offer.get("published"):
        return
    offer["disguise_index"] = disguise_index
    offer["disguise_to"] = disguise_to
    offer["published"] = True
    upsert_state(room_code, current_offer_json=json.dumps(offer), offer_published=1)

    cp = current_player(room_code)
    if cp:
        add_log(room_code, "info", f"{cp['icon']} {cp['name']} displayed the selections.")

def displayed_offer(offer):
    """
    Return list of displayed pokemon names (public view).
    """
    disp = offer["offer_true"][:]
    if offer.get("published") and offer.get("disguise_index") is not None and offer.get("disguise_to"):
        disp[offer["disguise_index"]] = offer["disguise_to"]
    return disp

def make_pick(room_code, picker_player_id, chosen_display_name):
    """
    Next player chooses one of the displayed options.
    We store: true pokemon, display name, reveal whether lie.
    Then advance turn and clear offer to generate the next private offer.
    """
    s = get_state(room_code)
    offer = json.loads(s["current_offer_json"]) if s["current_offer_json"] else None
    if not offer or not offer.get("published"):
        raise ValueError("Offer not published yet.")

    disp = displayed_offer(offer)
    if chosen_display_name not in disp:
        raise ValueError("Invalid selection.")

    chosen_index = disp.index(chosen_display_name)
    true_name = offer["offer_true"][chosen_index]
    was_lie = (chosen_display_name != true_name)

    picks = json.loads(s["picks_json"])
    picks.append({
        "player_id": picker_player_id,
        "pokemon_true": true_name,
        "pokemon_display": chosen_display_name,
        "was_lie": was_lie,
        "ts": now(),
    })

    # public log (everyone sees)
    players = get_players(room_code)
    picker = next((p for p in players if p["player_id"] == picker_player_id), None)
    if picker:
        add_log(room_code, "pick", f"{picker['icon']} {picker['name']} picked **{chosen_display_name}**.")
        if was_lie:
            add_log(room_code, "reveal", f"Reveal: It was a **lie** → actually **{true_name}**.")
        else:
            add_log(room_code, "reveal", f"Reveal: It was **true** → **{true_name}**.")

    # advance turn
    next_turn = (s["turn_index"] + 1)
    # clear current offer (so next current player gets a private offer)
    upsert_state(
        room_code,
        picks_json=json.dumps(picks),
        turn_index=next_turn,
        current_offer_json=None,
        offer_published=0
    )

# ----------------------------
# UI
# ----------------------------
st.set_page_config(page_title="ThenWeFight Draft", page_icon="🎮", layout="wide")
init_db()

pokemon_pool = load_pokemon_list()

# Session identity
if "room_code" not in st.session_state:
    st.session_state.room_code = ""
if "player_id" not in st.session_state:
    st.session_state.player_id = ""

# autorefresh polling
st_autorefresh(interval=REFRESH_MS, key="tick")

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; }
      .card { padding: 1rem; border: 1px solid rgba(255,255,255,0.12); border-radius: 16px; }
      .muted { opacity: 0.7; }
      .big { font-size: 1.2rem; font-weight: 700; }
      .pill { display:inline-block; padding: 4px 10px; border-radius: 999px; border: 1px solid rgba(255,255,255,0.14); margin-right: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([1, 2], gap="large")

with left:
    st.markdown("### 🎮 ThenWeFight Draft")
    st.markdown("<div class='muted'>Pure Python • Streamlit • SQLite • No Supabase</div>", unsafe_allow_html=True)

    mode = st.radio("Mode", ["Host", "Join"], horizontal=True)

    if mode == "Host":
        name = st.text_input("Your name", value="Host")
        icon = st.selectbox("Icon", ICONS, index=0)
        if st.button("Create Room", use_container_width=True):
            room_code, pid = create_room(name.strip() or "Host", icon)
            st.session_state.room_code = room_code
            st.session_state.player_id = pid
            st.rerun()

    else:
        room_code_in = st.text_input("Room code", value=st.session_state.room_code).strip().upper()
        name = st.text_input("Your name", value="")
        icon = st.selectbox("Icon", ICONS, index=1)
        if st.button("Join Room", use_container_width=True):
            if not room_code_in:
                st.error("Enter a room code.")
            else:
                pid = join_room(room_code_in, name.strip() or "Player", icon)
                st.session_state.room_code = room_code_in
                st.session_state.player_id = pid
                st.rerun()

    st.divider()

    if st.session_state.room_code:
        st.markdown(f"**Room:** `{st.session_state.room_code}`")
        st.markdown(f"**You:** `{st.session_state.player_id}`")

with right:
    room_code = st.session_state.room_code
    player_id = st.session_state.player_id

    if not room_code or not player_id:
        st.info("Host or join a room to begin.")
        st.stop()

    room = get_room(room_code)
    if not room:
        st.error("Room not found.")
        st.stop()

    players = get_players(room_code)
    me = next((p for p in players if p["player_id"] == player_id), None)
    if not me:
        st.error("You are not registered in this room anymore.")
        st.stop()

    state = get_state(room_code)
    status = room["status"]

    # Lobby
    if status == "lobby":
        st.markdown("### 🧩 Lobby")
        c1, c2 = st.columns([2, 1])

        with c1:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("**Players**")
            for p in players:
                host_tag = " 👑" if p["is_host"] else ""
                seat_tag = f" · seat {p['seat']}" if p["seat"] is not None else ""
                st.write(f"{p['icon']} **{p['name']}**{host_tag}{seat_tag}")
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("**Host controls**")
            if me["is_host"]:
                if st.button("Start Game (assign order)", use_container_width=True):
                    assign_seats(room_code)
                    conn = db()
                    conn.execute("UPDATE rooms SET status='drafting' WHERE room_code=?", (room_code,))
                    conn.commit()
                    conn.close()
                    add_log(room_code, "info", "Game started. Drafting begins!")
                    st.rerun()
            else:
                st.info("Waiting for host to start…")
            st.markdown("</div>", unsafe_allow_html=True)

    # Drafting
    elif status == "drafting":
        st.markdown("### 🧠 Drafting")

        cp = current_player(room_code)
        s = get_state(room_code)
        picks = json.loads(s["picks_json"])
        offer = ensure_private_offer(room_code, pokemon_pool)
        published = bool(get_state(room_code)["offer_published"])

        top = st.columns([2, 1, 1])
        with top[0]:
            st.markdown(
                f"<span class='pill'>Turn: {cp['icon']} <b>{cp['name']}</b></span>"
                f"<span class='pill'>Players: <b>{len(players)}</b></span>"
                f"<span class='pill'>Goal: <b>{PICKS_PER_PLAYER}</b> each</span>",
                unsafe_allow_html=True
            )
        with top[1]:
            my_count = len(picks_for_player(picks, player_id))
            st.metric("Your picks", my_count, f"{PICKS_PER_PLAYER - my_count} left")
        with top[2]:
            st.metric("Total picks", len(picks), f"of {len(players)*PICKS_PER_PLAYER}")

        st.divider()

        # Area 1: Offer / turn actions
        st.markdown("#### 🎴 Current Offer")

        if cp["player_id"] == player_id and not published:
            # PRIVATE view only for current player
            st.info("Only you can see the real Pokémon right now. Choose one to disguise, then display to everyone.")

            real = offer["offer_true"]
            st.write("**Real options (private):**")
            st.write(" · ".join([f"**{x}**" for x in real]))

            disguise_index = st.radio(
                "Which one do you want to disguise?",
                options=list(range(OFFER_SIZE)),
                format_func=lambda i: f"Slot {i+1}: {real[i]}",
                horizontal=True,
            )
            disguise_to = st.selectbox(
                "Disguise it as (autocomplete)",
                options=pokemon_pool,
                index=0,
            )

            if st.button("✅ Display selections to everyone", use_container_width=True):
                publish_offer(room_code, disguise_index, normalize_name(disguise_to))
                st.rerun()

        else:
            # PUBLIC or waiting
            if not published:
                st.warning("Waiting for the current player to display selections…")
            else:
                disp = displayed_offer(offer)
                st.success("Selections are displayed to everyone:")
                cols = st.columns(3)
                for i, name in enumerate(disp):
                    with cols[i]:
                        st.markdown("<div class='card'>", unsafe_allow_html=True)
                        st.markdown(f"<div class='big'>Slot {i+1}</div>", unsafe_allow_html=True)
                        st.markdown(f"**{name}**")
                        st.markdown("</div>", unsafe_allow_html=True)

        # Area 2: Picking (only next player in line can pick, but everyone sees results via logs)
        if published:
            # Next picker is seat (turn_index+1) because current player is the "disguiser / shower"
            # BUT your described flow: "player currently selecting the pokemon" is the one who saw & disguised,
            # then NEXT player picks. This matches.
            s2 = get_state(room_code)
            next_seat = (s2["turn_index"] + 1) % len(players)
            next_picker = next((p for p in players if p["seat"] == next_seat), None)

            st.divider()
            st.markdown("#### ✅ Pick Phase")

            if next_picker and next_picker["player_id"] == player_id:
                disp = displayed_offer(offer)
                choice = st.radio("Pick one:", disp, horizontal=True)
                if st.button("Lock in pick", use_container_width=True):
                    make_pick(room_code, player_id, choice)

                    # After a pick, we advanced turn_index and cleared offer.
                    # But we also need to advance one more so the NEXT disguiser becomes current player.
                    # (Current turn_index tracks disguiser seat; after pick we moved it +1 to picker seat.
                    # Now set it to picker seat (current) as next disguiser.)
                    # That is already true after make_pick. Great.

                    # If done, mark done
                    if game_done(room_code):
                        conn = db()
                        conn.execute("UPDATE rooms SET status='done' WHERE room_code=?", (room_code,))
                        conn.commit()
                        conn.close()
                        add_log(room_code, "info", "Draft complete!")
                    st.rerun()
            else:
                if next_picker:
                    st.info(f"Waiting for {next_picker['icon']} {next_picker['name']} to pick…")

        # Area 3: Public log + rosters
        st.divider()
        a, b = st.columns([1, 1], gap="large")

        with a:
            st.markdown("#### 📣 Public Feed (everyone sees)")
            conn = db()
            logs = conn.execute(
                "SELECT * FROM logs WHERE room_code=? ORDER BY id DESC LIMIT 20",
                (room_code,),
            ).fetchall()
            conn.close()
            for row in logs:
                st.write(f"- {row['message']}")

        with b:
            st.markdown("#### 🧾 Rosters")
            for p in players:
                myp = picks_for_player(picks, p["player_id"])
                st.markdown(f"**{p['icon']} {p['name']}** ({len(myp)}/{PICKS_PER_PLAYER})")
                if myp:
                    # show display + reveal outcome
                    for x in myp[-6:]:
                        tag = "🟢 true" if not x["was_lie"] else "🔴 lie"
                        st.write(f"• picked **{x['pokemon_display']}** → **{x['pokemon_true']}** ({tag})")
                st.write("")

    # Done
    else:
        st.markdown("### 🏁 Draft Complete")
        state = get_state(room_code)
        picks = json.loads(state["picks_json"])
        players = get_players(room_code)

        for p in players:
            myp = [x for x in picks if x["player_id"] == p["player_id"]]
            st.markdown(f"#### {p['icon']} {p['name']}")
            for x in myp:
                tag = "🟢 true" if not x["was_lie"] else "🔴 lie"
                st.write(f"- **{x['pokemon_display']}** → **{x['pokemon_true']}** ({tag})")

        st.info("If you want, I can add a 'New Game' button + room cleanup.")
