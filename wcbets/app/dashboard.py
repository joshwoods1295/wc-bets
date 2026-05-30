"""Streamlit dashboard: pick two countries, see matchup flags; manage backlog."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from wcbets.config import DB_PATH, FLAG_PERCENTILE
from wcbets.db import repository as repo
from wcbets.analysis import matchup_query as mq
from wcbets.analysis.matchup import evaluate_matchup, RULES

st.set_page_config(page_title="WC Bets", layout="wide")
conn = repo.connect(DB_PATH)
repo.init_db(conn)
repo.seed_backlog(conn, now="seed")

st.title("WC Bets — matchup flags")
tab_matchups, tab_backlog = st.tabs(["Matchups", "Backlog"])

with tab_matchups:
    countries = mq.list_countries(conn)
    if not countries:
        st.info("No squads loaded yet. Run the scrapers or import CSVs first.")
    else:
        c1, c2 = st.columns(2)
        home = c1.selectbox("Defending side", countries, key="home")
        away = c2.selectbox("Attacking side", countries,
                            index=min(1, len(countries) - 1), key="away")
        defenders = [p for p in mq.players_by_country(conn, home)
                     if (p["position"] or "").startswith("D")]
        attackers = [p for p in mq.players_by_country(conn, away)
                     if (p["position"] or "").startswith(("F", "M"))]
        any_flag = False
        for d in defenders:
            for a in attackers:
                peers = {}
                for _, def_stat, atk_stat in RULES:
                    peers[f"defender_{def_stat}"] = mq.peer_distribution(
                        conn, d["position"], def_stat)
                    peers[f"attacker_{atk_stat}"] = mq.peer_distribution(
                        conn, a["position"], atk_stat)
                flags = evaluate_matchup(d, a, peers, threshold=FLAG_PERCENTILE)
                for f in flags:
                    any_flag = True
                    st.warning(
                        f"**{f['label']}** — {f['defender']} "
                        f"({f['defender_stat']}={f['defender_value']}, "
                        f"{int(f['defender_pct']*100)}th pct) vs {f['attacker']} "
                        f"({f['attacker_stat']}={f['attacker_value']}, "
                        f"{int(f['attacker_pct']*100)}th pct)")
        if not any_flag:
            st.success("No flagged matchups at the current threshold.")

with tab_backlog:
    st.subheader("Backlog / future work")
    new = st.text_input("Add an item")
    if st.button("Add") and new.strip():
        repo.add_backlog_item(conn, new.strip(), now="ui")
        st.rerun()
    for item in repo.list_backlog(conn):
        done = item["status"] == "done"
        label = f"~~{item['title']}~~" if done else item["title"]
        cols = st.columns([6, 1])
        cols[0].markdown(f"{label}  \n<small>{item['notes']}</small>",
                         unsafe_allow_html=True)
        if not done and cols[1].button("Done", key=f"done{item['id']}"):
            repo.complete_backlog_item(conn, item["id"])
            st.rerun()
