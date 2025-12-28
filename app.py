import json
import random
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import requests
import streamlit as st
from supabase import create_client, Client


# -----------------------------
# Config
# -----------------------------
POKEAPI_SPECIES_LIST = "https://pokeapi.co/api/v2/pokemon-species?limit=20000"
# 3D-ish “HOME” sprites (looks like modern games more than 2D sprites)
POKE_SPRITE_HOME = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/{id}.png"

ICONS = ["⭐", "🔥", "🌊", "🌿", "⚡", "❄️", "👑", "🧠", "🎯", "🦴", "🛡️", "🗡️", "🎲", "🦊", "🐉"]

st.set_page_config(page_title="Poké Draft", page_icon="🎴", layout="wide")


# -----------------------------
# Supabase
# -----------------------------
@st.cache_resource
def sb() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)


# -----------------------------
# Pokémon data
# -----------------------------
@st.cache_data(ttl=60 * 60 * 24)
def load_species_names() -> List[str]:
    """
    Use pokemon-species list to avoid mega forms (megas are forms/varieties,
    species list is the canonical base species list).
    """
    r = requests.get(POKEAPI_SPECIES_LIST, timeout=30)
    r.raise_for_status()
    data = r.json()
    names = [x["name"] for x in data["results"]]

    # Extra guard: remove obvious mega naming if any appear (usually they won't in species)
    banned_substrings = ["mega", "-mega", "mega-", "primal-"]
    cleaned = []
    for n in names:
        low = n.lower()
        if any(b in low for b in banned_substrings):
            continue
        cleaned.append(n)

    # Title-case display later, but keep lowercase IDs for consistency
    return sorted(set(cleaned))


@st.cache_data(ttl=60 * 60 * 24)
def species_name_to_dex_id() -> Dict[str, int]:
    """
    In PokéAPI, pokemon-species IDs align with National Dex for core species.
    We can derive id by fetching species list once and using ordering.
    The list endpoint is paginated; we used limit=20000 so it returns all.
    The results are ordered by id.
    """
    r = requests.get(POKEAPI_SPECIES_LIST, timeout=30)
    r.raise_for_status()
    data = r.json()
    out = {}
    for idx, item in enumerate(data["results"], start=1):
        out[item["name"]] = idx
    return out


def sprite_url_for(name: str) -> Optional[str]:
    dex = species_name_to_dex_id().get(name)
    if not dex:
        return None
    return POKE_SPRITE_HOME.format(id=dex)


def pretty_name(name: str) -> str:
    return name.replace("-", " ").title()


# -----------------------------
# UI helpers
# -----------------------------
def inject_css():
    st.markdown(
        """
<style>
:root { --card: rgba(255,255,255,0.06); --border: rgba(255,255,255,0.10); }
.block-container { padding-top: 1.2rem; }
.pill {
  display:inline-flex; gap:.5rem; align-items:center;
  padding:.35rem .6rem; border:1px solid var(--border);
  background: var(--card); border-radius: 999px; font-size:.9rem;
}
.card {
  border:1px solid var(--border); background: var(--card);
  border-radius: 18px; padding: 14px 14px; height: 100%;
}
.card h3 { margin: 0 0 .4rem 0; font-size: 1.05rem; }
.small { opacity: .75; font-size: .9rem; }
.offer {
  border:1px solid var(--border); background: rgba(255,255,255,0.04);
  border-radius: 18px; padding: 14px; text-align:center;
}
.offer img { width: 120px; height: 120px; object-fit: contain; image-rendering: auto; }
.badge {
  display:inline-block; padding:.25rem .5rem; border-radius: 10px;
  border:1px solid var(--border); background: rgba(0,0,0,0.25);
  font-size: .85rem;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def pill(text: str):
    st.markdown(f"<span class='pill'>{text}</span>", unsafe_allow_html=True)


# -----------------------------
# Room logic
# -----------------------------
def gen_room_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(5))


def get_room(room_code: str) -> Optional[Dict[str, Any]]:
    res = sb().table("rooms").select("*").eq("room_code", room_code).execute()
    if res.data:
        return res.data[0]
    return None


def list_players(room_code: str) -> List[Dict[str, Any]]:
    res = sb().table("players").select("*").eq("room_code", room_code).order("joined_at").execute()
    return res.data or []


def create_room(host_name: str, host_icon: str):
    room_code = generate_room_code()  # however you do this (e.g., 5 letters)

    # 1) Create the room FIRST
    sb().table("rooms").insert({
        "room_code": room_code,
        "status": "lobby",
        "current_turn": 0
    }).execute()

    # 2) Then create the host player referencing that room_code
    host_res = sb().table("players").insert({
        "room_code": room_code,
        "name": host_name,
        "icon": host_icon,
        "is_host": True,
        "is_ready": True
    }).execute()

    host_id = host_res.data[0]["player_id"]

    return {"room_code": room_code, "player_id": host_id}


def join_room(room_code: str, name: str, icon: str) -> Optional[str]:
    room = get_room(room_code)
    if not room:
        return None
    ins = sb().table("players").insert({
        "room_code": room_code,
        "name": name,
        "icon": icon,
        "is_host": False,
        "is_ready": False
    }).execute()
    return ins.data[0]["player_id"]


def set_ready(player_id: str, ready: bool):
    sb().table("players").update({"is_ready": ready}).eq("player_id", player_id).execute()


def all_ready(players: List[Dict[str, Any]]) -> bool:
    return len(players) >= 2 and all(p["is_ready"] for p in players)


def player_picks(room_code: str, player_id: str) -> List[Dict[str, Any]]:
    res = sb().table("picks").select("*").eq("room_code", room_code).eq("player_id", player_id).order("pick_index").execute()
    return res.data or []


def all_picks(room_code: str) -> List[Dict[str, Any]]:
    res = sb().table("picks").select("*").eq("room_code", room_code).order("pick_index").execute()
    return res.data or []


def start_draft(room_code: str):
    players = list_players(room_code)
    order = [p["player_id"] for p in players]  # joined order; you can randomize here if desired
    random.shuffle(order)  # assigned order (your spec)

    # initialize pool from species
    pool = load_species_names().copy()
    random.shuffle(pool)

    # set first offers
    offers = [{"real": pool.pop(), "shown_as": None},
              {"real": pool.pop(), "shown_as": None},
              {"real": pool.pop(), "shown_as": None}]

    sb().table("rooms").update({
        "phase": "draft",
        "started_at": "now()",
        "turn_index": 0,
        "round_index": 0,
        "draft_order": order,
        "pool": pool,
        "current_offers": offers,
        "offer_disguise_used": False
    }).eq("room_code", room_code).execute()


def current_player_id(room: Dict[str, Any]) -> str:
    order = room["draft_order"]
    return order[room["turn_index"] % len(order)]


def picks_needed(players_count: int) -> int:
    return players_count * 6


def rotate_turn(room_code: str):
    room = get_room(room_code)
    players = list_players(room_code)
    if not room or not players:
        return

    pc = len(players)
    total_needed = picks_needed(pc)
    picks = all_picks(room_code)

    if len(picks) >= total_needed:
        sb().table("rooms").update({"phase": "done"}).eq("room_code", room_code).execute()
        return

    pool = room["pool"]
    if len(pool) < 3:
        # recycle by reloading (rare)
        pool = load_species_names().copy()
        random.shuffle(pool)

    offers = [{"real": pool.pop(), "shown_as": None},
              {"real": pool.pop(), "shown_as": None},
              {"real": pool.pop(), "shown_as": None}]

    sb().table("rooms").update({
        "turn_index": (room["turn_index"] + 1) % pc,
        "round_index": room["round_index"] + 1,
        "pool": pool,
        "current_offers": offers,
        "offer_disguise_used": False
    }).eq("room_code", room_code).execute()


def apply_disguise(room_code: str, offer_idx: int, shown_as: str):
    room = get_room(room_code)
    if not room:
        return
    offers = room["current_offers"]
    if not (0 <= offer_idx < len(offers)):
        return
    offers[offer_idx]["shown_as"] = shown_as
    sb().table("rooms").update({
        "current_offers": offers,
        "offer_disguise_used": True
    }).eq("room_code", room_code).execute()


def take_pick(room_code: str, player_id: str, offer_idx: int):
    room = get_room(room_code)
    if not room:
        return
    offers = room["current_offers"]
    if not (0 <= offer_idx < len(offers)):
        return

    pick_index = len(all_picks(room_code))
    chosen = offers[offer_idx]
    real = chosen["real"]
    shown_as = chosen["shown_as"]

    sb().table("picks").insert({
        "room_code": room_code,
        "player_id": player_id,
        "pick_index": pick_index,
        "pokemon": real,
        "shown_as": shown_as
    }).execute()

    rotate_turn(room_code)


# -----------------------------
# App
# -----------------------------
inject_css()

if "room_code" not in st.session_state:
    st.session_state.room_code = None
if "player_id" not in st.session_state:
    st.session_state.player_id = None

left, right = st.columns([1.2, 2.0], gap="large")

with left:
    st.title("🎴 Poké Draft")
    st.caption("Host a lobby, join friends, draft teams with a disguise twist.")

    if not st.session_state.room_code:
        st.subheader("Create or Join")

        tab1, tab2 = st.tabs(["Host", "Join"])

        with tab1:
            host_name = st.text_input("Your name", value="Host")
            host_icon = st.selectbox("Icon", ICONS, index=0)
            if st.button("Create Room", use_container_width=True):
                info = create_room(host_name.strip() or "Host", host_icon)
                st.session_state.room_code = info["room_code"]
                st.session_state.player_id = info["player_id"]
                st.rerun()

        with tab2:
            room_code = st.text_input("Room code", value="").upper().strip()
            name = st.text_input("Your name ", value="Player")
            icon = st.selectbox("Icon ", ICONS, index=1)
            if st.button("Join Room", use_container_width=True):
                pid = join_room(room_code, name.strip() or "Player", icon)
                if not pid:
                    st.error("Room not found.")
                else:
                    st.session_state.room_code = room_code
                    st.session_state.player_id = pid
                    st.rerun()
    else:
        room_code = st.session_state.room_code
        player_id = st.session_state.player_id
        room = get_room(room_code)

        if not room:
            st.error("Room no longer exists.")
            if st.button("Back"):
                st.session_state.room_code = None
                st.session_state.player_id = None
                st.rerun()
        else:
            pill(f"Room: **{room_code}**")
            phase = room["phase"]
            st.write("")

            if st.button("Leave Room", use_container_width=True):
                # (simple leave) delete player row
                sb().table("players").delete().eq("player_id", player_id).execute()
                st.session_state.room_code = None
                st.session_state.player_id = None
                st.rerun()

            # Poll for updates
            st.caption("Auto-refreshing…")
            st.autorefresh(interval=1200, key="tick")  # ~1.2s

with right:
    if not st.session_state.room_code:
        st.info("Create or join a room to begin.")
    else:
        room_code = st.session_state.room_code
        player_id = st.session_state.player_id
        room = get_room(room_code)
        players = list_players(room_code)

        if not room:
            st.stop()

        phase = room["phase"]
        host_id = room["host_player_id"]
        me = next((p for p in players if p["player_id"] == player_id), None)
        is_host = bool(me and me["is_host"])

        # ---------------- Lobby ----------------
        if phase == "lobby":
            st.header("🧩 Lobby")

            c1, c2 = st.columns([1.2, 1.0], gap="large")
            with c1:
                st.markdown("<div class='card'><h3>Players</h3>", unsafe_allow_html=True)
                for p in players:
                    ready = "✅ Ready" if p["is_ready"] else "⏳ Not ready"
                    tag = " (Host)" if p["is_host"] else ""
                    st.write(f"{p['icon']} **{p['name']}**{tag} — {ready}")
                st.markdown("</div>", unsafe_allow_html=True)

            with c2:
                st.markdown("<div class='card'><h3>Actions</h3>", unsafe_allow_html=True)
                if me:
                    new_ready = st.toggle("Ready", value=me["is_ready"])
                    if new_ready != me["is_ready"]:
                        set_ready(player_id, new_ready)
                        st.rerun()

                if is_host:
                    can_start = all_ready(players)
                    if not can_start:
                        st.caption("Need at least 2 players, and everyone ready.")
                    if st.button("Start Game", disabled=not can_start, use_container_width=True):
                        start_draft(room_code)
                        st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

        # ---------------- Draft ----------------
        elif phase == "draft":
            st.header("🎯 Draft")

            order = room["draft_order"]
            turn_pid = current_player_id(room)
            turn_player = next((p for p in players if p["player_id"] == turn_pid), None)

            total_needed = picks_needed(len(players))
            picks = all_picks(room_code)
            progress = len(picks) / total_needed if total_needed else 0
            st.progress(progress, text=f"Picks: {len(picks)} / {total_needed}")

            top = st.columns([1.4, 1.0, 1.2], gap="large")

            with top[0]:
                st.markdown("<div class='card'><h3>Turn</h3>", unsafe_allow_html=True)
                if turn_player:
                    st.write(f"Current: {turn_player['icon']} **{turn_player['name']}**")
                st.caption("Order:")
                for i, pid in enumerate(order):
                    p = next((x for x in players if x["player_id"] == pid), None)
                    if not p:
                        continue
                    marker = "👉 " if pid == turn_pid else "   "
                    st.write(f"{marker}{i+1}. {p['icon']} {p['name']}")
                st.markdown("</div>", unsafe_allow_html=True)

            with top[1]:
                st.markdown("<div class='card'><h3>Your team</h3>", unsafe_allow_html=True)
                mine = player_picks(room_code, player_id)
                if not mine:
                    st.caption("No picks yet.")
                for pk in mine:
                    shown = pk["shown_as"]
                    label = pretty_name(pk["pokemon"])
                    if shown:
                        label = f"{pretty_name(pk['pokemon'])}  _(shown as {pretty_name(shown)})_"
                    st.write(f"• {label}")
                st.markdown("</div>", unsafe_allow_html=True)

            with top[2]:
                st.markdown("<div class='card'><h3>All picks</h3>", unsafe_allow_html=True)
                if not picks:
                    st.caption("No picks yet.")
                for pk in picks[-10:]:
                    p = next((x for x in players if x["player_id"] == pk["player_id"]), None)
                    who = p["name"] if p else "Player"
                    st.write(f"#{pk['pick_index']+1}: **{who}** → {pretty_name(pk['pokemon'])}")
                st.markdown("</div>", unsafe_allow_html=True)

            st.divider()

            offers = room["current_offers"] or []
            disguise_used = room["offer_disguise_used"]

            st.subheader("🃏 Current Offers")

            # Show offers (as seen)
            cols = st.columns(3, gap="large")
            for i in range(3):
                with cols[i]:
                    if i >= len(offers):
                        continue
                    real = offers[i]["real"]
                    shown_as = offers[i]["shown_as"] or real
                    img = sprite_url_for(shown_as)
                    st.markdown("<div class='offer'>", unsafe_allow_html=True)
                    st.markdown(f"<div class='badge'>Option {i+1}</div>", unsafe_allow_html=True)
                    if img:
                        st.image(img)
                    st.markdown(f"### {pretty_name(shown_as)}", unsafe_allow_html=True)
                    if offers[i]["shown_as"]:
                        st.caption(f"(Disguised from {pretty_name(real)})")
                    else:
                        st.caption(" ")
                    st.markdown("</div>", unsafe_allow_html=True)

            st.write("")

            is_my_turn = (player_id == turn_pid)

            # Disguise UI: only for current player, once per turn
            st.markdown("<div class='card'><h3>Disguise (current player only)</h3><p class='small'>Once per turn, you can pick ONE of the three and change what everyone sees.</p>", unsafe_allow_html=True)

            if is_my_turn:
                if disguise_used:
                    st.success("Disguise already used this turn.")
                else:
                    species = load_species_names()
                    cA, cB, cC = st.columns([0.8, 1.8, 0.8], gap="large")
                    with cA:
                        idx = st.selectbox("Which option to disguise?", [1, 2, 3], index=0)
                    with cB:
                        # Typing in selectbox filters options (autocomplete-like)
                        target = st.selectbox(
                            "Disguise as (type to search)",
                            options=species,
                            format_func=pretty_name
                        )
                    with cC:
                        if st.button("Apply", use_container_width=True):
                            apply_disguise(room_code, idx - 1, target)
                            st.rerun()
            else:
                st.info("Waiting for the current player to optionally disguise an offer…")

            st.markdown("</div>", unsafe_allow_html=True)

            st.write("")
            st.markdown("<div class='card'><h3>Pick (current player after disguise step is done)</h3><p class='small'>Next player chooses one of the three.</p>", unsafe_allow_html=True)

            # Picking: only the *current* player picks now (your spec says next player chooses one; in turn-based flow,
            # it means the current player is the chooser for that step. The disguiser is the same as chooser in same turn.
            # If you truly mean: Player A disguises then Player B picks, tell me and I’ll swap it.)
            if is_my_turn:
                pick_choice = st.radio("Choose one", [1, 2, 3], horizontal=True)
                if st.button("Lock in Pick", type="primary", use_container_width=True):
                    take_pick(room_code, player_id, pick_choice - 1)
                    st.rerun()
            else:
                st.info("Only the current player can pick right now.")

            st.markdown("</div>", unsafe_allow_html=True)

        # ---------------- Done ----------------
        elif phase == "done":
            st.header("🏁 Draft Complete")
            picks = all_picks(room_code)
            by_player = {p["player_id"]: [] for p in players}
            for pk in picks:
                by_player[pk["player_id"]].append(pk)

            grid = st.columns(2, gap="large")
            for i, p in enumerate(players):
                with grid[i % 2]:
                    st.markdown(f"<div class='card'><h3>{p['icon']} {p['name']}</h3>", unsafe_allow_html=True)
                    team = by_player.get(p["player_id"], [])
                    for pk in team:
                        shown = pk["shown_as"]
                        label = pretty_name(pk["pokemon"])
                        if shown:
                            label = f"{pretty_name(pk['pokemon'])}  _(shown as {pretty_name(shown)})_"
                        st.write(f"• {label}")
                    st.markdown("</div>", unsafe_allow_html=True)

        else:
            st.error(f"Unknown phase: {phase}")
