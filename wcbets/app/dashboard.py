"""Streamlit dashboard: matchup flags, live lineups, squad stats, backlog."""
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

# DB_PATH is the cache key — functions open their own connection so
# Reload (which calls st.cache_data.clear()) always gets fresh data.
_db = str(DB_PATH)


def _conn():
    """Fresh read-only-ish connection; cheap on SQLite."""
    c = repo.connect(DB_PATH)
    repo.init_db(c)
    return c


# One persistent write connection for backlog mutations
@st.cache_resource
def get_write_conn():
    c = repo.connect(DB_PATH)
    repo.init_db(c)
    repo.seed_backlog(c, now="seed")
    return c


@st.cache_data(ttl=3600)
def cached_players_by_country(country: str, _db: str = _db):
    return mq.players_by_country(_conn(), country)


@st.cache_data(ttl=3600)
def cached_peer_dist(position: str, stat: str, _db: str = _db):
    return mq.peer_distribution(_conn(), position, stat)


@st.cache_data(ttl=3600)
def cached_countries(_db: str = _db):
    return mq.list_countries(_conn())


@st.cache_data(ttl=3600)
def prewarm_peers(_db: str = _db):
    for _, def_stat, atk_stat in RULES:
        for pos in ("GK", "DF", "MF", "FW"):
            cached_peer_dist(pos, def_stat)
            cached_peer_dist(pos, atk_stat)


prewarm_peers()
conn = get_write_conn()


col_title, col_reload = st.columns([8, 1])
col_title.title("WC Bets")
if col_reload.button("↺ Reload", help="Reload after scraping new data"):
    st.cache_resource.clear()
    st.cache_data.clear()
    st.rerun()

tab_live, tab_squads_match, tab_squads, tab_backlog = st.tabs(
    ["🔴 Live / Today", "⚽ Squad matchups", "📊 Squad stats", "📋 Backlog"]
)


# ---------------------------------------------------------------------------
# Shared matchup rendering
# ---------------------------------------------------------------------------

def _run_matchups(defenders, attackers, threshold):
    """Score all def×atk pairs, return (flagged, top_rest) sorted lists."""
    def get_peers(pos, stat):
        return cached_peer_dist(pos, stat)

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
    return (
        [m for m in all_matchups if m["flagged"]],
        [m for m in all_matchups if not m["flagged"]][:10],
    )


def _render_matchups(flagged, top_rest, threshold, context=""):
    if flagged:
        st.subheader(
            f"🚩 {len(flagged)} flagged matchup{'s' if len(flagged) != 1 else ''} "
            f"(both ≥ {int(threshold*100)}th pct)  {context}"
        )
        for m in flagged:
            st.warning(
                f"**{m['label']}**  \n"
                f"🛡 **{m['defender']}** — "
                f"{m['def_stat'].replace('_p90','')} {m['def_val']:.1f}/90 · "
                f"**{int(m['def_pct']*100)}th pct**  \n"
                f"⚡ **{m['attacker']}** — "
                f"{m['atk_stat'].replace('_p90','')} {m['atk_val']:.1f}/90 · "
                f"**{int(m['atk_pct']*100)}th pct**"
            )
    else:
        st.info(
            f"No matchups above {int(threshold*100)}th percentile. "
            f"Try lowering the slider. Top matches shown below."
        )

    if top_rest:
        st.subheader("📊 Top matchups" if flagged else "📊 Highest-scoring matchups (below threshold)")
        for m in top_rest:
            st.markdown(
                f"**{m['label']}** · combined {int(m['combined']*100)}th pct  \n"
                f"🛡 {m['defender']} {m['def_val']:.1f}/90 ({int(m['def_pct']*100)}th) · "
                f"⚡ {m['attacker']} {m['atk_val']:.1f}/90 ({int(m['atk_pct']*100)}th)"
            )


# ---------------------------------------------------------------------------
# Tab: Live / Today
# ---------------------------------------------------------------------------

with tab_live:
    from wcbets.scrape.lineups import get_todays_matches, get_lineup, resolve_lineup_to_db, _IMPERSONATE
    from datetime import datetime

    mode = st.radio("Match source", ["Auto (today's list)", "Manual ID"], horizontal=True)

    selected = None

    if mode == "Auto (today's list)":
        if not _IMPERSONATE:
            st.warning("Match listing is blocked on this server. Use Manual ID instead — find the ID on sofascore.com in the match URL.")

        col_r, col_btn = st.columns([1, 1])
        if col_btn.button("🔄 Refresh match list"):
            st.cache_data.clear()
            st.rerun()

        from datetime import date as _date
        _today = _date.today().isoformat()

        @st.cache_data(ttl=120)
        def load_todays_matches(today_str: str):
            return get_todays_matches()

        matches = load_todays_matches(_today)
        st.caption(f"Showing matches for {_today}")

        if not matches:
            st.info("No matches found. Try Manual ID mode.")
        else:
            show_all = st.checkbox("Show club matches too", value=False)
            international_keywords = [
                "international", "friendly", "world cup", "nations league",
                "euro", "copa america", "africa cup", "qualification",
                "olympic", "u21", "u20", "u19", "u18", "u17", "youth",
                "concacaf", "conmebol", "uefa", "caf", "afc", "ofc",
            ]
            filtered = matches if show_all else [
                m for m in matches
                if any(k in (m["tournament"] + " " + m["category"]).lower()
                       for k in international_keywords)
            ]
            if not filtered:
                filtered = matches

            def fmt_match(m):
                ts = m["timestamp"]
                try:
                    t = datetime.fromtimestamp(ts).strftime("%H:%M")
                except Exception:
                    t = "?"
                badge = "🔴 " if m["status_type"] in ("inprogress",) else ""
                return f"{badge}{t}  {m['home']} vs {m['away']}  [{m['tournament']}]  {m['status']}"

            labels = [fmt_match(m) for m in filtered]
            choice = st.selectbox("Pick a match", range(len(labels)),
                                  format_func=lambda i: labels[i])
            selected = filtered[choice]
            st.markdown(
                f"**{selected['home']} vs {selected['away']}**  \n"
                f"{selected['tournament']} · Sofascore ID: `{selected['id']}`"
            )

    else:
        st.caption("Find the match ID in the Sofascore URL, e.g. sofascore.com/football/match/england-germany/**12345678**")
        manual_id = st.text_input("Sofascore match ID", placeholder="e.g. 12345678")
        home_name = st.text_input("Home team name", placeholder="e.g. England")
        away_name = st.text_input("Away team name", placeholder="e.g. Germany")
        if manual_id.strip() and home_name.strip() and away_name.strip():
            selected = {
                "id": int(manual_id.strip()),
                "home": home_name.strip(),
                "away": away_name.strip(),
                "tournament": "Manual",
            }

    if selected:
        threshold_live = st.slider(
            "Min percentile", 50, 95, int(FLAG_PERCENTILE * 100), 5,
            key="threshold_live"
        ) / 100

        home_defends = st.checkbox(f"{selected['home']} defending", value=True)

        if st.button("🔍 Fetch lineup & run matchups", type="primary"):
            with st.spinner("Fetching lineup from Sofascore..."):
                lineup = get_lineup(selected["id"])

            if not lineup["home"] and not lineup["away"]:
                st.warning(
                    "No lineup available yet — Sofascore usually publishes "
                    "confirmed lineups ~60 min before kickoff. "
                    "Try again closer to kick-off, or use the Squad matchups tab."
                )
            else:
                home_players = resolve_lineup_to_db(conn, lineup["home"])
                away_players = resolve_lineup_to_db(conn, lineup["away"])

                confirmed_str = "✅ Confirmed" if lineup["confirmed"] else "⚠️ Unconfirmed"
                st.info(
                    f"Lineup status: {confirmed_str}  \n"
                    f"**{selected['home']}**: {len(home_players)}/11 matched to stats  \n"
                    f"**{selected['away']}**: {len(away_players)}/11 matched to stats"
                )

                if home_defends:
                    defending_players = home_players
                    attacking_players = away_players
                    def_name, atk_name = selected["home"], selected["away"]
                else:
                    defending_players = away_players
                    attacking_players = home_players
                    def_name, atk_name = selected["away"], selected["home"]

                defenders = [p for p in defending_players
                             if (p.get("position") or "").startswith("D")]
                attackers = [p for p in attacking_players
                             if (p.get("position") or "").startswith(("F", "M"))]

                if not defenders and not attackers:
                    st.warning(
                        f"Neither team's lineup players were found in the database. "
                        f"Both squads likely play outside the Big-5 leagues — "
                        f"no stats available to analyse."
                    )
                elif not defenders:
                    st.warning(
                        f"No {def_name} defenders found in database "
                        f"({len(defending_players)}/{len(lineup['home' if home_defends else 'away'])} "
                        f"players matched). These players likely play outside the Big-5."
                    )
                elif not attackers:
                    st.warning(
                        f"No {atk_name} attackers found in database "
                        f"({len(attacking_players)}/{len(lineup['away' if home_defends else 'home'])} "
                        f"players matched). These players likely play outside the Big-5."
                    )
                else:
                    st.success(
                        f"Analysing **{len(defenders)}** {def_name} defenders "
                        f"vs **{len(attackers)}** {atk_name} attackers "
                        f"(starting XI only)"
                    )
                    flagged, top_rest = _run_matchups(defenders, attackers, threshold_live)
                    _render_matchups(flagged, top_rest, threshold_live,
                                     context=f"— {def_name} vs {atk_name}")

                    # Show both starting XIs
                    with st.expander("Starting XIs"):
                        c1, c2 = st.columns(2)
                        c1.markdown(f"**{selected['home']}**")
                        for p in home_players:
                            c1.markdown(f"- {p['name']} ({p.get('position','?')})")
                        c2.markdown(f"**{selected['away']}**")
                        for p in away_players:
                            c2.markdown(f"- {p['name']} ({p.get('position','?')})")


# ---------------------------------------------------------------------------
# Tab: Squad matchups (full squad, any two countries)
# ---------------------------------------------------------------------------

with tab_squads_match:
    countries = cached_countries()
    if not countries:
        st.info("No squads loaded. Run scrape_data.py then import_squads.py first.")
    else:
        c1, c2, c3 = st.columns([2, 2, 1])
        home = c1.selectbox("Defending side", countries, key="home_sq")
        away = c2.selectbox("Attacking side", countries,
                            index=min(1, len(countries) - 1), key="away_sq")
        threshold_sq = c3.slider(
            "Min percentile", 50, 95, int(FLAG_PERCENTILE * 100), 5,
            key="threshold_sq"
        ) / 100

        defenders = [p for p in cached_players_by_country(home)
                     if (p["position"] or "").startswith("D")]
        attackers = [p for p in cached_players_by_country(away)
                     if (p["position"] or "").startswith(("F", "M"))]

        if not defenders:
            st.warning(f"No defenders found for {home}. Re-run scrape_data.py to fix positions.")
        elif not attackers:
            st.warning(f"No attackers found for {away}. Re-run scrape_data.py to fix positions.")
        else:
            flagged, top_rest = _run_matchups(defenders, attackers, threshold_sq)
            _render_matchups(flagged, top_rest, threshold_sq)


# ---------------------------------------------------------------------------
# Tab: Squad stats
# ---------------------------------------------------------------------------

with tab_squads:
    countries2 = cached_countries()
    if countries2:
        import pandas as pd
        country = st.selectbox("Country", countries2, key="squad_country")
        players = cached_players_by_country(country)
        if players:
            df = pd.DataFrame([{
                "Name": p["name"],
                "Pos": p["position"] or "—",
                "Fouls/90": round(p.get("fouls_p90", 0), 2),
                "FoulsDrawn/90": round(p.get("fouls_drawn_p90", 0), 2),
                "Tackles/90": round(p.get("tackles_p90", 0), 2),
                "Goals/90": round(p.get("goals_p90", 0), 2),
                "Shots/90": round(p.get("shots_p90", 0), 2),
                "Yellows/90": round(p.get("yellows_p90", 0), 2),
                "Saves/90": round(p.get("saves_p90", 0), 2),
                "Minutes": int(p.get("minutes", 0)),
            } for p in players]).sort_values(["Pos", "Fouls/90"], ascending=[True, False])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No players found.")


# ---------------------------------------------------------------------------
# Tab: Backlog
# ---------------------------------------------------------------------------

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
