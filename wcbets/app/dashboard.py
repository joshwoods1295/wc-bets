"""Streamlit dashboard: pick two countries, see matchup flags; manage backlog."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from wcbets.config import DB_PATH, FLAG_PERCENTILE
from wcbets.db import repository as repo
from wcbets.analysis import matchup_query as mq
from wcbets.analysis.matchup import RULES
from wcbets.analysis.percentiles import percentile_rank

st.set_page_config(page_title="WC Bets", layout="wide")
conn = repo.connect(DB_PATH)
repo.init_db(conn)
repo.seed_backlog(conn, now="seed")

st.title("WC Bets — matchup flags")
tab_matchups, tab_squads, tab_backlog = st.tabs(["Matchups", "Squad stats", "Backlog"])

with tab_matchups:
    countries = mq.list_countries(conn)
    if not countries:
        st.info("No squads loaded yet. Run scrape_data.py then import_squads.py first.")
    else:
        col1, col2, col3 = st.columns([2, 2, 1])
        home = col1.selectbox("Defending side", countries, key="home")
        away = col2.selectbox("Attacking side", countries,
                              index=min(1, len(countries) - 1), key="away")
        threshold = col3.slider("Min percentile", 50, 95, int(FLAG_PERCENTILE * 100), 5) / 100

        defenders = [p for p in mq.players_by_country(conn, home)
                     if (p["position"] or "").startswith("D")]
        attackers = [p for p in mq.players_by_country(conn, away)
                     if (p["position"] or "").startswith(("F", "M"))]

        if not defenders:
            st.warning(f"No defenders found for {home}. "
                       "Positions may be missing — re-run scrape_data.py.")
        elif not attackers:
            st.warning(f"No attackers found for {away}. "
                       "Positions may be missing — re-run scrape_data.py.")
        else:
            # Precompute peer distributions once per position
            peer_cache = {}
            def get_peers(pos, stat):
                key = (pos, stat)
                if key not in peer_cache:
                    peer_cache[key] = mq.peer_distribution(conn, pos, stat)
                return peer_cache[key]

            # Score every defender-attacker pair for every rule
            all_matchups = []
            for d in defenders:
                for a in attackers:
                    for label, def_stat, atk_stat in RULES:
                        def_val = d.get(def_stat, 0.0)
                        atk_val = a.get(atk_stat, 0.0)
                        def_pct = percentile_rank(def_val, get_peers(d["position"], def_stat))
                        atk_pct = percentile_rank(atk_val, get_peers(a["position"], atk_stat))
                        combined = (def_pct + atk_pct) / 2
                        all_matchups.append({
                            "label": label,
                            "defender": d["name"],
                            "attacker": a["name"],
                            "def_stat": def_stat,
                            "atk_stat": atk_stat,
                            "def_val": def_val,
                            "atk_val": atk_val,
                            "def_pct": def_pct,
                            "atk_pct": atk_pct,
                            "combined": combined,
                            "flagged": def_pct >= threshold and atk_pct >= threshold,
                        })

            all_matchups.sort(key=lambda x: x["combined"], reverse=True)
            flagged = [m for m in all_matchups if m["flagged"]]
            top_rest = [m for m in all_matchups if not m["flagged"]][:10]

            if flagged:
                st.subheader(f"🚩 {len(flagged)} flagged matchup{'s' if len(flagged) != 1 else ''} "
                             f"(both players ≥ {int(threshold*100)}th pct)")
                for m in flagged:
                    st.warning(
                        f"**{m['label']}**  \n"
                        f"🛡 **{m['defender']}** — {m['def_stat'].replace('_p90','')} "
                        f"{m['def_val']:.1f}/90 · **{int(m['def_pct']*100)}th pct**  \n"
                        f"⚡ **{m['attacker']}** — {m['atk_stat'].replace('_p90','')} "
                        f"{m['atk_val']:.1f}/90 · **{int(m['atk_pct']*100)}th pct**"
                    )
            else:
                st.info(f"No matchups where both players are at or above the "
                        f"{int(threshold*100)}th percentile. "
                        f"Try lowering the slider. Top matchups shown below.")

            if top_rest and not flagged:
                st.subheader("📊 Highest-scoring matchups (below threshold)")
            elif top_rest:
                st.subheader("📊 Next best matchups")

            for m in top_rest:
                st.markdown(
                    f"**{m['label']}** · combined {int(m['combined']*100)}th pct  \n"
                    f"🛡 {m['defender']} {m['def_val']:.1f}/90 ({int(m['def_pct']*100)}th) · "
                    f"⚡ {m['attacker']} {m['atk_val']:.1f}/90 ({int(m['atk_pct']*100)}th)"
                )

with tab_squads:
    countries2 = mq.list_countries(conn)
    if countries2:
        country = st.selectbox("Country", countries2, key="squad_country")
        players = mq.players_by_country(conn, country)
        if players:
            import pandas as pd
            df = pd.DataFrame([{
                "Name": p["name"],
                "Pos": p["position"] or "—",
                "Fouls/90": round(p.get("fouls_p90", 0), 2),
                "FoulsDrawn/90": round(p.get("fouls_drawn_p90", 0), 2),
                "Goals/90": round(p.get("goals_p90", 0), 2),
                "Shots/90": round(p.get("shots_p90", 0), 2),
                "Yellows/90": round(p.get("yellows_p90", 0), 2),
                "Saves/90": round(p.get("saves_p90", 0), 2),
                "Minutes": int(p.get("minutes", 0)),
            } for p in players]).sort_values(["Pos", "Fouls/90"], ascending=[True, False])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No players found.")

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
