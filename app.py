import os
import json
import time
import random
import string
import threading
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh

# -----------------------------
# Config
# -----------------------------
DATA_DIR = "data"
ROOMS_DIR = os.path.join(DATA_DIR, "rooms")
os.makedirs(ROOMS_DIR, exist_ok=True)

ICONS = ["🟥", "🟦", "🟩", "🟨", "🟪", "🟧", "⬛", "⬜", "⭐", "🔥", "💧", "🌿", "⚡", "👑", "🧠", "🗡️"]

POKEAPI_LIST_URL = "https://pokeapi.co/api/v2/pokemon?limit=2000"

# Simple “no mega” filter: PokeAPI already uses base species names (no "mega-"),
# but we keep this in case you ever swap lists/sources.
def is_allowed_pokemon_name(name: str) -> bool:
    bad_tokens = ["mega", "gmax", "gigantamax"]
    n = name.lower()
    return not any(tok in n for tok in bad_tokens)

STATE_LOCK = threading.Lock()

# -----------------------------
# Utilities: storage
# -----------------------------
def room_path(code: str) -> str:
    return os.path.join(ROOMS_DIR, f"{code}.json")

def load_room(code: str) -> Optional[Dict[str, Any]]:
    path = room_path(code)
    if not os.path.exists(path):
        return None
    with STATE_LOCK:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

def save_room(code: str, state: Dict[str, Any]) -> None:
    path = room_path(code)
    with STATE_LOCK:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

def new_code(n=5) -> str:
    alphabet = string.ascii_uppercase
    return "".join(random.choice(alphabet) for _ in range(n))

def now_ts() -> float:
    return time.time()

def ensure_room_exists(code: str) -> Dict[str, Any]:
    state = load_room(code)
    if state is None:
        raise ValueError("Room does not exist.")
    return state

# -----------------------------
# Pokémon data
# -----------------------------
@st.cache_data(ttl=60 * 60 * 12)
def fetch_pokemon_list() -> Tuple[List[str], Dict[str, int]]:
    """
    Returns:
      names: list of pokemon names (Title Case)
      name_to_id: mapping "Name" -> id
    """
    try:
        r = requests.get(POKEAPI_LIST_URL, timeout=15)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])

        names = []
        name_to_id = {}
        for item in results:
            raw = item["name"]  # e.g. "pikachu"
            if not is_allowed_pokemon_name(raw):
                continue

            # id from URL .../pokemon/25/
            url = item.get("url", "")
            pid = None
            try:
                pid = int(url.rstrip("/").split("/")[-1])
            except Exception:
                pid = None

            name = raw.replace("-", " ").title()
            if pid is not None:
                names.append(name)
                name_to_id[name] = pid

        # Keep only real-ish entries; PokeAPI includes many forms beyond 1025,
        # but names here are generally fine. You can optionally clamp by pid <= 1025.
        # names = [n for n in names if name_to_id[n] <= 1025]

        names.sort()
        return names, name_to_id
    except Exception:
        # Fallback minimal list if API is down
        fallback = ["Bulbasaur", "Charmander", "Squirtle", "Pikachu", "Eevee", "Gengar", "Lucario", "Garchomp"]
        return fallback, {n: i + 1 for i, n in enumerate(fallback)}

def home_sprite_url(pid: int) -> str:
    # Pokémon HOME renders (look 3D)
    return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/{pid}.png"

# -----------------------------
# Game logic
# -----------------------------
def make_empty_room(host_name: str, host_icon: str) -> Dict[str, Any]:
    code = new_code()
    host_id = f"p_{random.randint(100000, 999999)}"
    state = {
        "room_code": code,
        "created_at": now_ts(),
        "status": "lobby",  # lobby | drafting | done
        "host_id": host_id,
        "players": [
            {"player_id": host_id, "name": host_name, "icon": host_icon, "joined_at": now_ts()}
        ],
        "order": [],  # list of player_ids in draft order
        "turn_owner": None,  # player_id who is the "displayer"
        "phase": None,  # "secret" | "pick"
        "visible_to": None,  # player_id allowed to see current selections (secret owner or picker)
        "current_pool": None,  # list of 3 dicts: {"true": name, "shown": name}
        "rosters": {},  # player_id -> list of names
        "log": [],
        "version": 1,
    }
    return state

def add_log(state: Dict[str, Any], msg: str) -> None:
    state["log"].append({"t": now_ts(), "msg": msg})
    state["log"] = state["log"][-200:]  # keep it bounded

def join_room(code: str, name: str, icon: str) -> str:
    state = ensure_room_exists(code)
    if state["status"] != "lobby":
        raise ValueError("Game already started.")
    # prevent duplicate names? (optional)
    player_id = f"p_{random.randint(100000, 999999)}"
    state["players"].append({"player_id": player_id, "name": name, "icon": icon, "joined_at": now_ts()})
    add_log(state, f"{icon} {name} joined.")
    save_room(code, state)
    return player_id

def get_player(state: Dict[str, Any], player_id: str) -> Dict[str, Any]:
    for p in state["players"]:
        if p["player_id"] == player_id:
            return p
    raise KeyError("Player not found")

def next_player_id(state: Dict[str, Any], current_pid: str) -> str:
    order = state["order"]
    i = order.index(current_pid)
    return order[(i + 1) % len(order)]

def everyone_has_six(state: Dict[str, Any]) -> bool:
    for pid in state["order"]:
        if len(state["rosters"].get(pid, [])) < 6:
            return False
    return True

def random_three(names: List[str]) -> List[Dict[str, str]]:
    picks = random.sample(names, 3)
    return [{"true": p, "shown": p} for p in picks]

def start_game(code: str) -> None:
    state = ensure_room_exists(code)
    if state["status"] != "lobby":
        return
    if len(state["players"]) < 2:
        raise ValueError("Need at least 2 players.")

    # Draft order random
    pids = [p["player_id"] for p in state["players"]]
    random.shuffle(pids)
    state["order"] = pids

    # Init rosters
    state["rosters"] = {pid: [] for pid in pids}

    # First "displayer" is order[0]
    owner = pids[0]
    state["turn_owner"] = owner
    state["phase"] = "secret"
    state["visible_to"] = owner

    names, _ = fetch_pokemon_list()
    state["current_pool"] = random_three(names)

    state["status"] = "drafting"
    add_log(state, "Game started. Draft order set.")
    save_room(code, state)

def owner_disguise(code: str, owner_id: str, slot: int, replacement_name: str) -> None:
    state = ensure_room_exists(code)
    if state["status"] != "drafting":
        return
    if state["phase"] != "secret":
        return
    if state["turn_owner"] != owner_id or state["visible_to"] != owner_id:
        return

    pool = state["current_pool"]
    if not pool or slot not in [0, 1, 2]:
        return
    pool[slot]["shown"] = replacement_name
    add_log(state, f"{get_player(state, owner_id)['name']} disguised a Pokémon.")
    save_room(code, state)

def owner_display_to_next(code: str, owner_id: str) -> None:
    state = ensure_room_exists(code)
    if state["status"] != "drafting":
        return
    if state["phase"] != "secret":
        return
    if state["turn_owner"] != owner_id or state["visible_to"] != owner_id:
        return

    picker = next_player_id(state, owner_id)
    state["phase"] = "pick"
    state["visible_to"] = picker
    add_log(state, f"Selections displayed to {get_player(state, picker)['name']}.")
    save_room(code, state)

def picker_choose(code: str, picker_id: str, choice_index: int) -> None:
    state = ensure_room_exists(code)
    if state["status"] != "drafting":
        return
    if state["phase"] != "pick":
        return
    if state["visible_to"] != picker_id:
        return

    pool = state["current_pool"] or []
    if choice_index not in [0, 1, 2] or len(pool) != 3:
        return

    chosen_shown = pool[choice_index]["shown"]
    state["rosters"].setdefault(picker_id, []).append(chosen_shown)

    # After picker chooses:
    # picker becomes the new owner and generates a new secret pool
    new_owner = picker_id
    state["turn_owner"] = new_owner
    state["phase"] = "secret"
    state["visible_to"] = new_owner

    names, _ = fetch_pokemon_list()
    state["current_pool"] = random_three(names)

    add_log(state, f"{get_player(state, picker_id)['name']} picked {chosen_shown}.")

    if everyone_has_six(state):
        state["status"] = "done"
        state["phase"] = None
        state["visible_to"] = None
        state["current_pool"] = None
        add_log(state, "Draft complete!")

    save_room(code, state)

# -----------------------------
# UI helpers
# -----------------------------
def render_rosters(state: Dict[str, Any], name_to_id: Dict[str, int]) -> None:
    st.subheader("Rosters")
    cols = st.columns(len(state["order"]))
    for i, pid in enumerate(state["order"]):
        p = get_player(state, pid)
        roster = state["rosters"].get(pid, [])
        with cols[i]:
            st.markdown(f"### {p['icon']} {p['name']}")
            st.caption(f"{len(roster)}/6")
            for mon in roster:
                pid_num = name_to_id.get(mon)
                if pid_num:
                    st.image(home_sprite_url(pid_num), width=96)
                st.write(mon)

def render_pool(pool: List[Dict[str, str]], name_to_id: Dict[str, int]) -> None:
    c1, c2, c3 = st.columns(3)
    for col, idx in zip([c1, c2, c3], [0, 1, 2]):
        shown = pool[idx]["shown"]
        pid_num = name_to_id.get(shown)
        with col:
            if pid_num:
                st.image(home_sprite_url(pid_num), use_container_width=True)
            st.markdown(f"**{shown}**")

# -----------------------------
# Page styling
# -----------------------------
st.set_page_config(page_title="1.0.0 Then We Fight - Draft", page_icon="⚔️", layout="wide")
st.markdown(
    """
<style>
/* modern-ish look */
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1200px; }
[data-testid="stMetricValue"] { font-size: 1.1rem; }
.small-muted { opacity: 0.75; font-size: 0.95rem; }
.card {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.03);
}
hr { opacity: 0.25; }
</style>
""",
    unsafe_allow_html=True,
)

# Autorefresh tick (fixes your AttributeError issue)
st_autorefresh(interval=2000, key="tick")

# -----------------------------
# Session identity
# -----------------------------
if "room_code" not in st.session_state:
    st.session_state.room_code = ""
if "player_id" not in st.session_state:
    st.session_state.player_id = ""
if "mode" not in st.session_state:
    st.session_state.mode = "home"

pokemon_names, name_to_id = fetch_pokemon_list()

# -----------------------------
# HOME (host/join)
# -----------------------------
st.title("⚔️ Then We Fight — Secret Draft")

with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Host", "Join"])

    with tab1:
        host_name = st.text_input("Your name", value="Host", key="host_name")
        host_icon = st.selectbox("Icon", ICONS, index=0, key="host_icon")
        if st.button("Create Room", use_container_width=True):
            state = make_empty_room(host_name.strip() or "Host", host_icon)
            code = state["room_code"]
            save_room(code, state)
            st.session_state.room_code = code
            st.session_state.player_id = state["host_id"]
            st.session_state.mode = "room"
            st.rerun()

    with tab2:
        code = st.text_input("Room code", value="", key="join_code").strip().upper()
        join_name = st.text_input("Your name", value="Player", key="join_name")
        join_icon = st.selectbox("Icon", ICONS, index=1, key="join_icon")
        if st.button("Join Room", use_container_width=True):
            room = load_room(code)
            if not room:
                st.error("Room not found.")
            else:
                try:
                    pid = join_room(code, join_name.strip() or "Player", join_icon)
                    st.session_state.room_code = code
                    st.session_state.player_id = pid
                    st.session_state.mode = "room"
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# ROOM VIEW
# -----------------------------
code = st.session_state.room_code
pid = st.session_state.player_id

if st.session_state.mode == "room" and code and pid:
    state = load_room(code)
    if not state:
        st.error("Room no longer exists.")
        st.stop()

    me = get_player(state, pid)

    top = st.columns([1, 1, 2])
    with top[0]:
        st.metric("Room", state["room_code"])
    with top[1]:
        st.metric("Status", state["status"].title())
    with top[2]:
        st.write(f"**You:** {me['icon']} {me['name']}")

    st.divider()

    # LOBBY
    if state["status"] == "lobby":
        left, right = st.columns([1.2, 1])
        with left:
            st.subheader("Lobby")
            st.write("Share the room code so friends can join.")
            st.markdown("**Players:**")
            for p in sorted(state["players"], key=lambda x: x["joined_at"]):
                host_badge = " (Host)" if p["player_id"] == state["host_id"] else ""
                st.write(f"{p['icon']} {p['name']}{host_badge}")

        with right:
            st.subheader("Controls")
            if pid == state["host_id"]:
                if st.button("Start Game", type="primary", use_container_width=True):
                    try:
                        start_game(code)
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            else:
                st.info("Waiting for host to start…")

    # DRAFTING
    elif state["status"] == "drafting":
        owner = state["turn_owner"]
        phase = state["phase"]
        visible_to = state["visible_to"]
        pool = state["current_pool"] or []
        picker = next_player_id(state, owner) if owner else None

        # Always show order + rosters (public)
        st.subheader("Draft Order")
        order_names = " → ".join([f"{get_player(state, x)['icon']} {get_player(state, x)['name']}" for x in state["order"]])
        st.write(order_names)

        st.divider()
        render_rosters(state, name_to_id)

        st.divider()

        # SECRET / PICK VISIBILITY LOGIC
        is_visible_player = (pid == visible_to)

        if not is_visible_player:
            # Everyone else sees a waiting screen
            if phase == "secret":
                st.info(f"⏳ Waiting… **{get_player(state, owner)['name']}** is preparing the hidden selections.")
            elif phase == "pick":
                st.info(f"⏳ Waiting… **{get_player(state, visible_to)['name']}** is choosing a Pokémon.")
            st.caption("This page auto-updates every ~2 seconds.")
        else:
            # The one player who is allowed to see the pool
            if phase == "secret" and pid == owner:
                st.subheader("Your turn: Prepare 3 Pokémon (only you can see this)")
                render_pool(pool, name_to_id)

                st.markdown("### Disguise one (optional)")
                slot = st.radio("Which slot to disguise?", [1, 2, 3], horizontal=True)
                replacement = st.selectbox(
                    "Replacement Pokémon (type to search)",
                    options=pokemon_names,
                    index=pokemon_names.index(pool[slot - 1]["shown"]) if pool and pool[slot - 1]["shown"] in pokemon_names else 0,
                )

                cA, cB = st.columns(2)
                with cA:
                    if st.button("Apply Disguise", use_container_width=True):
                        owner_disguise(code, pid, slot - 1, replacement)
                        st.rerun()
                with cB:
                    if st.button(f"Display Selections → {get_player(state, picker)['name']}", type="primary", use_container_width=True):
                        owner_display_to_next(code, pid)
                        st.rerun()

                st.caption("When you click **Display Selections**, only the next player will see the 3 options.")

            elif phase == "pick" and pid == visible_to:
                st.subheader("Your turn: Pick 1 Pokémon (only you can see this)")
                render_pool(pool, name_to_id)

                choice = st.radio("Choose one", [1, 2, 3], horizontal=True)
                if st.button("Confirm Pick", type="primary", use_container_width=True):
                    picker_choose(code, pid, choice - 1)
                    st.rerun()

                st.caption("After you pick, you become the next displayer and will secretly prepare the next 3.")

    # DONE
    elif state["status"] == "done":
        st.success("✅ Draft complete!")
        render_rosters(state, name_to_id)

    # LOG
    with st.expander("Room Log", expanded=False):
        for item in state.get("log", [])[-60:]:
            st.write(f"- {item['msg']}")

    st.divider()
    if st.button("Leave Room"):
        st.session_state.room_code = ""
        st.session_state.player_id = ""
        st.session_state.mode = "home"
        st.rerun()
