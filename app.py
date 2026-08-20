import streamlit as st
import pandas as pd
import random
import math
import os
import requests
import urllib3
import re
from io import StringIO
from bs4 import BeautifulSoup

from config import (
    CSV_FILENAME, EXCEL_FILENAME, TEAMS, DRAFT_ORDER,
    TEAM_NFL_BIASES, MANAGER_TENDENCIES, get_color,
    normalize_name, make_short_name, MANAGER_TARGETS, TARGET_PLAYERS, SLEEPER_PLAYERS
)

st.set_page_config(
    page_title="Slamulator '26",
    page_icon=":pig_nose:",
    layout="wide"
)

st.markdown(
    """
    <style>
    /* 1. Remove excess top page padding completely */
    header { display: none !important; } /* Kills the empty Streamlit header bar */
    .main .block-container {
        padding-top: 0rem !important;
        margin-top: -30px !important;
        padding-bottom: 1rem !important;
    }

    /* 2. Desktop/Mobile Board Visibility */
    .mobile-board-container { display: none !important; }
    .desktop-board-container { display: block !important; }

    /* 3. Center and size the main logo */
    div[data-testid="stImage"] {
        display: flex;
        justify-content: center;
        margin-top: -10px !important;
        margin-bottom: 20px !important;
    }
    div[data-testid="stImage"] img {
        max-width: 450px !important;
    }

    @media (max-width: 767px) {
        .mobile-board-container { display: block !important; }
        .desktop-board-container { display: none !important; }

        div[data-testid="stImage"] img {
            max-width: 320px !important;
        }

        /* 
         * BULLETPROOF MOBILE REORDERING 
         * Uses strict Streamlit DOM targets to force the Draft Board to the top
         */
        div.st-key-main_layout > div > div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: column !important;
        }
        div.st-key-main_layout > div > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(1) { order: 2 !important; }
        div.st-key-main_layout > div > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) { order: 1 !important; }
        div.st-key-main_layout > div > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) { order: 3 !important; }

        /* Compact player list height for mobile screens */
        div.st-key-player_list_container {
            height: 450px !important;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0px !important;
        }
        div.element-container {
            margin-bottom: 0px !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

import streamlit.components.v1 as components

# This hidden script forcefully deletes the default Streamlit iOS icon
# and replaces it with the custom Dickens draft simulator icon.
components.html(
    """
    <script>
    const links = window.parent.document.querySelectorAll('link[rel="apple-touch-icon"]');
    links.forEach(link => link.parentNode.removeChild(link));

    const newLink = window.parent.document.createElement('link');
    newLink.rel = 'apple-touch-icon';
    newLink.href = 'https://slampigskins-draft-simulator.streamlit.app/app/static/apple-touch-icon.png';
    window.parent.document.head.appendChild(newLink);
    </script>
    """,
    height=0,
    width=0,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.markdown(
    """
    <link rel="apple-touch-icon" href="https://raw.githubusercontent.com/YourUsername/dickens-draft-simulator/main/static/apple-touch-icon.png">
    <style>
        @media (max-width: 768px) {
            .main .block-container {
                padding: 0.5rem 0.5rem !important;
            }
            button {
                min-height: 44px !important;
            }
        }
    </style>
    """,
    unsafe_allow_html=True
)

def load_base_excel():
    if os.path.exists(EXCEL_FILENAME):
        try:
            xls = pd.ExcelFile(EXCEL_FILENAME)
            if 'FFC ADP' in xls.sheet_names:
                ffc_df = pd.read_excel(xls, 'FFC ADP', skiprows=7)
                ffc_df = ffc_df.dropna(subset=['Name', 'Position', 'Overall'])
                players = []
                for idx, row in ffc_df.iterrows():
                    players.append({
                        "Rank": int(idx + 1),
                        "Player": str(row['Name']).strip(),
                        "Position": str(row['Position']).strip().upper(),
                        "NFLTeam": str(row['Team']).strip() if 'Team' in ffc_df.columns else "FA",
                        "CBS ADP": float(row['Overall']),
                        "CBS Rank": float(idx + 1),
                        "FFC ADP": float(row['Overall'])
                    })
                df = pd.DataFrame(players)
                df.to_csv(CSV_FILENAME, index=False)
                return df
        except Exception:
            pass
    return generate_fallback_csv()

def generate_fallback_csv():
    fallback_raw = "Jahmyr Gibbs RB DET, Bijan Robinson RB ATL, Puka Nacua WR LAR, Ja'Marr Chase WR CIN, Christian McCaffrey RB SF"
    players = []
    for idx, item in enumerate(fallback_raw.split(','), 1):
        parts = item.strip().rsplit(' ', 2)
        players.append({
            "Rank": idx, 
            "Player": parts[0], 
            "Position": parts[1].strip().upper(), 
            "NFLTeam": parts[2] if len(parts) > 2 else "FA", 
            "CBS ADP": float(idx), 
            "CBS Rank": float(idx), 
            "FFC ADP": float(idx)
        })
    df = pd.DataFrame(players)
    df.to_csv(CSV_FILENAME, index=False)
    return df

def update_live_adps():
    st.info("Fetching live ADP data from FFC and CBS...")
    ffc_url = "https://fantasyfootballcalculator.com/adp/csv/ppr.csv"
    cbs_adp_url = "https://www.cbssports.com/fantasy/football/draft/averages/ppr/both/h2h/all/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    cbs_adp_map = {}
    
    try:
        cbs_resp = requests.get(cbs_adp_url, headers=headers, verify=False, timeout=10)
        cbs_tables = pd.read_html(StringIO(cbs_resp.text), flavor='lxml')
        if cbs_tables:
            for index, row in cbs_tables[0].iterrows():
                adp_val = row.get('Avg Pos', index + 1)
                parts = str(row['Player']).split()
                name = ""
                for i, part in enumerate(parts):
                    if part in ["QB", "RB", "WR", "TE", "K", "DST"]:
                        name = " ".join(parts[:i])
                        break
                if name:
                    cbs_adp_map[normalize_name(name)] = float(adp_val)
    except Exception:
        st.warning("Could not reach CBS ADP live page. Defaulting CBS ADP to FFC ADP where missing.")

    try:
        ffc_resp = requests.get(ffc_url, headers=headers, verify=False, timeout=15)
        if ffc_resp.status_code == 200:
            ffc_df = pd.read_csv(StringIO(ffc_resp.text), skiprows=7)
            
            players = []
            for idx, row in ffc_df.iterrows():
                if pd.isna(row.get('Name')): continue
                ffc_name = str(row['Name']).strip()
                clean_n = normalize_name(ffc_name)
                
                ffc_adp = float(row.get('Overall', idx + 1))
                cbs_adp = cbs_adp_map.get(clean_n, ffc_adp)
                cbs_rank = 999.0 # Default fallback since manual CBS HTML is removed
                
                players.append({
                    "Rank": int(idx + 1),
                    "Player": ffc_name,
                    "Position": str(row['Position']).strip().upper(),
                    "NFLTeam": str(row['Team']).strip() if 'Team' in ffc_df.columns else "FA",
                    "CBS ADP": cbs_adp,
                    "CBS Rank": cbs_rank,
                    "FFC ADP": ffc_adp
                })
            
            master_df = pd.DataFrame(players)
            master_df.to_csv(CSV_FILENAME, index=False)
            st.cache_data.clear()
            return True
    except Exception as e:
        st.error(f"Error updating database: {e}")
        return False

@st.cache_data
def load_data():
    if not os.path.exists(CSV_FILENAME):
        return load_base_excel()
    try:
        df = pd.read_csv(CSV_FILENAME)
    except Exception:
        return load_base_excel()
        
    for col in ['CBS ADP', 'CBS Rank', 'FFC ADP', 'Rank']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(999.0)
            
    if 'Position' in df.columns:
        df['Position'] = df['Position'].astype(str).str.strip().str.upper()
        df['Position'] = df['Position'].replace({'PK': 'K', 'DEF': 'DST', 'D/ST': 'DST'})
            
    return df

# Initialize Session States
if 'draft_history' not in st.session_state:
    st.session_state.draft_history = []
if 'current_pick' not in st.session_state:
    st.session_state.current_pick = 1
if 'available_players' not in st.session_state:
    st.session_state.available_players = load_data()
if 'time_left' not in st.session_state:
    st.session_state.time_left = 120

# Permanent memory for the toggle that survives page reloads
if 'auto_sim_preference' not in st.session_state:
    st.session_state.auto_sim_preference = True

# Permanent memory for CPU Draft Strategy
if 'cpu_draft_strategy' not in st.session_state:
    st.session_state.cpu_draft_strategy = "CBS ADP"

def execute_cpu_pick(team_name, current_pick_num):   
    df_avail = st.session_state.available_players.copy()
 
    # Check for manager-specific target override
    target_info = MANAGER_TARGETS.get(team_name)
    current_round = (current_pick_num - 1) // 12 + 1
    
    if target_info:
        if target_info["min_round"] <= current_round <= target_info["max_round"]:
            if target_info["player"] in df_avail['Player'].values:
                if random.random() < target_info["probability"]:
                    return df_avail[df_avail['Player'] == target_info["player"]].iloc[0]

    team_roster = [p['Position'] for p in st.session_state.draft_history if p['FantasyTeam'] == team_name]
    
    # 1. Base positional needs (K and DST locked to 0.0 in early rounds)
    needs = {"QB": 1.0, "RB": 1.0, "WR": 1.0, "TE": 1.0, "K": 0.0, "DST": 0.0}
    for pos in ["QB", "TE"]:
        if team_roster.count(pos) >= 1: 
            needs[pos] = 0.3
            
    if current_pick_num > 84 and team_roster.count("QB") == 0: 
        needs["QB"] = 1.8
    if team_roster.count("RB") >= 3: 
        needs["RB"] = 0.7
    if team_roster.count("WR") >= 3: 
        needs["WR"] = 0.7
    
    # K and DST become draftable only in late rounds (Picks 145+)
    if current_pick_num > 144:
        needs["K"] = 2.0 if team_roster.count("K") == 0 else 0.1
        needs["DST"] = 2.0 if team_roster.count("DST") == 0 else 0.1
    
    sigma = 1.5 if current_pick_num <= 48 else (3.0 if current_pick_num <= 120 else 5.5)
    pool_size = 4 if current_pick_num <= 48 else (8 if current_pick_num <= 120 else 16)
        
    bias_info = TEAM_NFL_BIASES.get(team_name, {"teams": [], "boost": 1.0})
    favored_nfl_teams = bias_info["teams"]
    nfl_boost_val = bias_info["boost"]
    
    # 2. Establish Effective ADP
    strategy = st.session_state.get("cpu_draft_strategy", "CBS ADP")
    
    def get_effective_value(r):
        if strategy == "CBS Consensus Rankings":
            val = r.get('CBS Rank', 999.0)
            if pd.notna(val) and val < 900:
                return float(val)
            cbs_adp = r.get('CBS ADP', 999.0)
            if pd.notna(cbs_adp) and cbs_adp < 900: 
                return float(cbs_adp)
            ffc_adp = r.get('FFC ADP', 999.0)
            if pd.notna(ffc_adp) and ffc_adp < 900: 
                return float(ffc_adp)
            return 999.0
            
        elif strategy == "FFC ADP":
            val = r.get('FFC ADP', 999.0)
            if pd.notna(val) and val < 900:
                return float(val)
            cbs_adp = r.get('CBS ADP', 999.0)
            if pd.notna(cbs_adp) and cbs_adp < 900: 
                return float(cbs_adp)
            return 999.0
            
        else: # Default to CBS ADP
            val = r.get('CBS ADP', 999.0)
            if pd.notna(val) and val < 900:
                return float(val)
            ffc_adp = r.get('FFC ADP', 999.0)
            if pd.notna(ffc_adp) and ffc_adp < 900: 
                return float(ffc_adp)
            return 999.0

    df_avail['Effective_ADP'] = df_avail.apply(get_effective_value, axis=1)
    df_avail = df_avail.sort_values(by='Effective_ADP').reset_index(drop=True)
    
    top_by_adp = df_avail.head(pool_size)
    fallen_players = df_avail[df_avail['Effective_ADP'] < current_pick_num]
    top_candidates = pd.concat([top_by_adp, fallen_players]).drop_duplicates(subset=['Player']).reset_index(drop=True)
    
    if top_candidates.empty:
        top_candidates = df_avail.head(10)
    
    scores = []
    for _, row in top_candidates.iterrows():
        pos = row['Position']
        nfl_tm = str(row['NFLTeam'])
        raw_bias = MANAGER_TENDENCIES.get(team_name, {}).get(pos, 1.0)
        bias = 1.0 + (raw_bias - 1.0) * 0.3
        need = needs.get(pos, 1.0)
        
        adp = row['Effective_ADP']
        
        if adp >= current_pick_num:
            w_adp = math.exp(-((adp - current_pick_num)**2) / (2 * (sigma**2)))
        else:
            fall_distance = current_pick_num - adp
            w_adp = 1.0 + (fall_distance * 0.1)
            
        nfl_boost = nfl_boost_val if nfl_tm in favored_nfl_teams else 1.0
        
        player_score = w_adp * need * bias * nfl_boost
        
        if team_name == "Leche Brothers (CAFP)":
            if nfl_tm == "CIN":
                player_score *= 1.5  
            if pos == "QB":
                player_score *= 1.2  
                
        scores.append(player_score)
    
    # Fallback to prevent 0-weight issues
    if sum(scores) <= 0:
        valid_pool = top_candidates[~top_candidates['Position'].isin(['K', 'DST'])]
        if not valid_pool.empty:
            return valid_pool.iloc[0]
        return top_candidates.iloc[0]
        
    chosen_index = random.choices(range(len(scores)), weights=scores, k=1)[0]
    return top_candidates.iloc[chosen_index]

# --- CENTRALLY DISPLAY THE LOGO ---
st.image("static/slamulator_logo.jfif")

current_turn_index = st.session_state.current_pick - 1
team_on_clock = DRAFT_ORDER[current_turn_index] if current_turn_index < len(DRAFT_ORDER) else "Draft Complete"

# --- WRAP THE MAIN DRAFT AREA FOR BULLETPROOF MOBILE REORDERING ---
with st.container(key="main_layout"):
    col_left, col_board, col_roster = st.columns([1.4, 3.1, 1.0])

    with col_left:
        st.subheader("Available Players")
        
        pos_filter = st.radio("Position Filter:", ["All", "QB", "RB", "WR", "TE", "K", "DST"], horizontal=True, label_visibility="collapsed")
        search_query = st.text_input("Search player...")
        sort_option = st.selectbox("Sort by:", ["CBS ADP", "CBS Rank", "FFC ADP"])
        
        display_df = st.session_state.available_players.copy()
        
        for col in ['CBS ADP', 'CBS Rank', 'FFC ADP']:
            if col in display_df.columns:
                display_df[col] = pd.to_numeric(display_df[col], errors='coerce').fillna(999.0)
                
        if sort_option == "CBS ADP":
            display_df = display_df.sort_values(by='CBS ADP', ascending=True).reset_index(drop=True)
        elif sort_option == "CBS Rank":
            display_df = display_df.sort_values(by='CBS Rank', ascending=True).reset_index(drop=True)
        elif sort_option == "FFC ADP":
            display_df = display_df.sort_values(by='FFC ADP', ascending=True).reset_index(drop=True)
            
        if pos_filter != "All":
            display_df = display_df[display_df['Position'].str.strip().str.upper() == pos_filter].reset_index(drop=True)
            
        if search_query:
            display_df = display_df[display_df['Player'].str.contains(search_query, case=False, na=False)].reset_index(drop=True)
            
        # Increased to 750px so it perfectly aligns with the bottom of the PC Draft Board!
        with st.container(height=750, key="player_list_container"):
            normalized_targets = [normalize_name(tp) for tp in TARGET_PLAYERS]
            normalized_sleepers = [normalize_name(sp) for sp in SLEEPER_PLAYERS]
            
            for idx, row in display_df.head(50).iterrows():
                active_adp = row['FFC ADP'] if sort_option == "FFC ADP" else row['CBS ADP']
                rd = math.ceil(active_adp / 12) if pd.notna(active_adp) and active_adp < 999 else 1
                pk = int((active_adp - 1) % 12) + 1 if pd.notna(active_adp) and active_adp < 999 else 1
                
                card_color = get_color(row['Position'])
                btn_label = "Draft" if team_on_clock == "Slampigskins" else "Force"
                
                cbs_adp_text = f"<b>CBS ADP:</b> {row.get('CBS ADP', 0.0)}" if sort_option == "CBS ADP" else f"CBS ADP: {row.get('CBS ADP', 0.0)}"
                current_rank_val = int(row.get('CBS Rank', 999)) if sort_option == "CBS Rank" and row.get('CBS Rank', 999) < 900 else int(row.get('Rank', 1))
                rank_text = f"<b>Rank:</b> {current_rank_val}" if sort_option == "CBS Rank" else f"Rank: {current_rank_val}"
                ffc_adp_text = f"<b>FFC ADP:</b> {row.get('FFC ADP', 0.0)}" if sort_option == "FFC ADP" else f"FFC ADP: {row.get('FFC ADP', 0.0)}"

                norm_player = normalize_name(row['Player'])
                is_target = norm_player in normalized_targets
                is_sleeper = norm_player in normalized_sleepers

                icons = ""
                if is_target:
                    icons += " 🎯"
                if is_sleeper:
                    icons += " 😴"

                if is_target and is_sleeper:
                    border_style = "3px solid #9c27b0"
                    box_shadow = "box-shadow: 0px 0px 8px 1px rgba(156, 39, 176, 0.6) !important;"
                elif is_target:
                    border_style = "3px solid #ff3333"
                    box_shadow = "box-shadow: 0px 0px 8px 1px rgba(255, 51, 51, 0.6) !important;"
                elif is_sleeper:
                    border_style = "3px solid #1e88e5"
                    box_shadow = "box-shadow: 0px 0px 8px 1px rgba(30, 136, 229, 0.6) !important;"
                else:
                    border_style = "1px solid #a0aab5"
                    box_shadow = ""

                card_key = f"card_{idx}"
                
                st.markdown(f"""
                <style>
                /* Default Desktop Style */
                div.st-key-{card_key} {{
                    background-color: {card_color} !important;
                    padding: 10px 15px !important;
                    border-radius: 8px !important;
                    border: {border_style} !important;
                    {box_shadow}
                    margin-bottom: 8px !important;
                }}

                /* Mobile Style - Surgical Override for THIS specific card */
                @media (max-width: 767px) {{
                    /* 1. Shrink the box padding */
                    div.st-key-{card_key} {{
                        padding: 4px 6px !important;
                        margin-bottom: 2px !important;
                    }}
                    
                    /* 2. Force text and button to stay side-by-side */
                    div.st-key-{card_key} div[data-testid="stHorizontalBlock"] {{
                        flex-direction: row !important;
                        align-items: center !important;
                    }}
                    
                    /* 3. Give text 70% and the word buttons 30% of the room */
                    div.st-key-{card_key} div[data-testid="stHorizontalBlock"] > div:nth-child(1) {{
                        width: 70% !important;
                        min-width: 70% !important;
                    }}
                    div.st-key-{card_key} div[data-testid="stHorizontalBlock"] > div:nth-child(2) {{
                        width: 30% !important;
                        min-width: 30% !important;
                    }}

                    /* 4. Shrink fonts and let ADP wrap naturally */
                    div.st-key-{card_key} div[style*="font-size: 12px"] {{
                        font-size: 10px !important;
                        line-height: 1.2 !important;
                        white-space: normal !important; 
                    }}
                    div.st-key-{card_key} b {{
                        font-size: 12px !important;
                    }}

                    /* 5. Shrink the button to tightly frame the words */
                    div.st-key-{card_key} button {{
                        min-height: 28px !important;
                        height: 28px !important;
                        padding: 0px 2px !important;
                        font-size: 11px !important;
                    }}
                }}
                </style>
                """, unsafe_allow_html=True)
                
                with st.container(key=card_key):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"""
                        <div style='font-size: 12px; color: #000000; line-height: 1.4; margin-top: 4px;'>
                            <b style='font-size: 14px;'>{row['Player']}{icons}</b> ({row['Position']} - {row['NFLTeam']})<br>
                            {cbs_adp_text} ({rd}.{pk}) | {ffc_adp_text} | {rank_text}
                        </div>
                        """, unsafe_allow_html=True)
                    with c2:
                        if st.button(f"{btn_label}", key=f"btn_{card_key}", use_container_width=True):
                            draft_item = {"Pick": st.session_state.current_pick, "FantasyTeam": team_on_clock, **row.to_dict()}
                            st.session_state.draft_history.append(draft_item)
                            st.session_state.available_players = st.session_state.available_players[st.session_state.available_players['Rank'] != row['Rank']].reset_index(drop=True)
                            st.session_state.current_pick += 1
                            st.session_state.time_left = 120
                            st.rerun()

    with col_board:
        @st.fragment(run_every=1)
        def render_clock(team_name):
            if team_name == "Draft Complete":
                st.subheader("Draft Complete!")
                return

            # ONLY tick the clock down if it is your turn! 
            # (Allows you to stare at the board without the CPU auto-drafting)
            if team_name == "Slampigskins":
                st.session_state.time_left -= 1
                
            mins = max(0, st.session_state.time_left // 60)
            secs = max(0, st.session_state.time_left % 60)
            
            st.subheader(f"On Clock: **{team_name}** | ⏱️ {mins}:{secs:02d}")
            
            if st.session_state.time_left <= 0:
                st.session_state.time_left = 120
                selection = st.session_state.available_players.iloc[0]
                draft_item = {"Pick": st.session_state.current_pick, "FantasyTeam": team_name, **selection.to_dict()}
                st.session_state.draft_history.append(draft_item)
                st.session_state.available_players = st.session_state.available_players[st.session_state.available_players['Rank'] != selection['Rank']].reset_index(drop=True)
                st.session_state.current_pick += 1
                st.rerun()

        # Added 3 columns here to neatly fit the Settings menu!
        col_sim1, col_sim2 = st.columns([1, 1.4])
        with col_sim1:
            render_clock(team_on_clock)
        with col_sim2:
            col_b1, col_b2, col_b3 = st.columns([1, 1, 1], vertical_alignment="center")
            with col_b1:
                if team_on_clock != "Slampigskins" and team_on_clock != "Draft Complete":
                    if st.button("🤖 Sim Pick", use_container_width=True):
                        cpu_selection = execute_cpu_pick(team_on_clock, st.session_state.current_pick)
                        draft_item = {"Pick": st.session_state.current_pick, "FantasyTeam": team_on_clock, **cpu_selection.to_dict()}
                        st.session_state.draft_history.append(draft_item)
                        st.session_state.available_players = st.session_state.available_players[st.session_state.available_players['Rank'] != cpu_selection['Rank']].reset_index(drop=True)
                        st.session_state.current_pick += 1
                        st.session_state.time_left = 120
                        st.rerun()
            with col_b2:
                # Callback function to hard-save your choice the moment you click the toggle
                def update_auto_sim():
                    st.session_state.auto_sim_preference = st.session_state.auto_sim_toggle_widget

                st.toggle(
                    "Auto-Sim", 
                    value=st.session_state.auto_sim_preference, 
                    key="auto_sim_toggle_widget",
                    on_change=update_auto_sim
                )
            
            # The Settings Menu is now nestled perfectly on the right!
            with col_b3:
                with st.popover("⚙️ Settings"):
                    st.markdown("### Draft Controls")
                    st.selectbox(
                        "CPU Draft Board Strategy",
                        options=["CBS ADP", "CBS Consensus Rankings", "FFC ADP"],
                        key="cpu_draft_strategy"
                    )
                    st.write("Wipe the board and start a new mock draft.")
                    if st.button("🧨 Reset Draft", use_container_width=True):
                        st.session_state.draft_history = []
                        st.session_state.current_pick = 1
                        st.session_state.available_players = load_data()
                        st.rerun()

        # --- THE BULLETPROOF AUTO-SIM ENGINE ---
        # Now reads from your ironclad preference state!
        if st.session_state.auto_sim_preference and team_on_clock != "Slampigskins" and team_on_clock != "Draft Complete":
            while st.session_state.current_pick <= len(DRAFT_ORDER) and DRAFT_ORDER[st.session_state.current_pick - 1] != "Slampigskins":
                current_team = DRAFT_ORDER[st.session_state.current_pick - 1]
                cpu_selection = execute_cpu_pick(current_team, st.session_state.current_pick)
                draft_item = {"Pick": st.session_state.current_pick, "FantasyTeam": current_team, **cpu_selection.to_dict()}
                st.session_state.draft_history.append(draft_item)
                st.session_state.available_players = st.session_state.available_players[st.session_state.available_players['Rank'] != cpu_selection['Rank']].reset_index(drop=True)
                st.session_state.current_pick += 1
            st.session_state.time_left = 120
            st.rerun()

        st.markdown("---")

        # --- DUAL BOARD RENDER LOGIC ---

        # Desktop Full Board HTML (Hidden on Mobile via CSS)
        desktop_html = """
        <div class='desktop-board-container' style='width: 100%; border: 1px solid #ccc; border-radius: 4px; margin-bottom: 20px; overflow-x: auto;'>
        <table style='width: 100%; table-layout: fixed; border-collapse: collapse; text-align: center; font-size: 11px; font-family: sans-serif;'>
        """
        desktop_html += "<tr>"
        desktop_html += "<th style='border: 1px solid black; padding: 4px; background-color: #dcdcdc; width: 4%; font-weight: bold;'>Rd</th>"
        for team in TEAMS:
            desktop_html += f"<th style='border: 1px solid black; padding: 4px; background-color: #f0f0f0; width: 8%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;'>{team}</th>"
        desktop_html += "</tr>"

        # Mobile Compact Board HTML (Hidden on Desktop via CSS)
        mobile_html = """
        <div class='mobile-board-container' style='width: 100%; border: 1px solid #ccc; border-radius: 4px; margin-bottom: 20px; overflow-x: auto;'>
        <table style='min-width: max-content; width: 100%; table-layout: fixed; border-collapse: collapse; text-align: center; font-size: 6.5px; font-family: sans-serif;'>
        """
        mobile_html += "<tr><th style='border: 1px solid black; padding: 1px; background-color: #dcdcdc; width: 5%; font-weight: bold;'>Rd</th>"
        for team in TEAMS:
            mobile_html += f"<th style='border: 1px solid black; padding: 1px; background-color: #f0f0f0; overflow: hidden; white-space: nowrap;'>{team[:3]}</th>"
        mobile_html += "</tr>"

        for round_num in range(1, 17):
            desktop_html += "<tr>"
            mobile_html += "<tr>"
            
            desktop_html += f"<td style='border: 1px solid black; background-color: #f0f0f0; font-weight: bold; color: #333333; padding: 2px; height: 45px;'>R{round_num}</td>"
            mobile_html += f"<td style='border: 1px solid black; background-color: #f0f0f0; font-weight: bold; color: #333333; padding: 1px; height: 22px;'>R{round_num}</td>"
            
            for col_idx in range(12):
                actual_pick_num = (round_num - 1) * 12 + col_idx + 1 if round_num % 2 != 0 else (round_num - 1) * 12 + (11 - col_idx) + 1
                pick = next((p for p in st.session_state.draft_history if p['Pick'] == actual_pick_num), None)
                
                if pick:
                    color = get_color(pick['Position'])
                    
                    # Desktop Cell Data
                    desktop_html += f"<td style='border: 1px solid black; background-color: {color}; padding: 3px; line-height: 1.2; height: 45px; overflow: hidden;'><b>{pick['Player']}</b><br>{pick['Position']}</td>"
                    
                    # Mobile Cell Data
                    short_name = make_short_name(pick['Player'])
                    mobile_html += f"<td style='border: 1px solid black; background-color: {color}; padding: 1px; height: 22px; line-height: 1.0; overflow: hidden;'><b>{short_name}</b><br>{pick['Position']}</td>"
                else:
                    # Desktop Empty Cell
                    desktop_html += f"<td style='border: 1px solid black; background-color: #ffffff; color: #a0aab5; padding: 3px; height: 45px;'><i>Pick {actual_pick_num}</i></td>"
                    
                    # Mobile Empty Cell
                    mobile_html += f"<td style='border: 1px solid black; background-color: #ffffff; color: #b0b0b0; padding: 1px; height: 22px; font-size: 6px;'>{actual_pick_num}</td>"
                    
            desktop_html += "</tr>"
            mobile_html += "</tr>"

        desktop_html += "</table></div>"
        mobile_html += "</table></div>"

        # Merge and render both strings. CSS media queries will handle which one is visible!
        st.markdown(desktop_html + mobile_html, unsafe_allow_html=True)


    with col_roster:
        st.subheader("🐽 Slampigskins Roster")
        
        my_picks = [p for p in st.session_state.draft_history if p['FantasyTeam'] == "Slampigskins"]
        for p in my_picks:
            p['Position'] = str(p.get('Position', '')).strip().upper()
        
        qbs = [p for p in my_picks if p['Position'] == "QB"]
        rbs = [p for p in my_picks if p['Position'] == "RB"]
        wrs = [p for p in my_picks if p['Position'] == "WR"]
        tes = [p for p in my_picks if p['Position'] == "TE"]
        ks  = [p for p in my_picks if p['Position'] == "K"]
        dsts = [p for p in my_picks if p['Position'] == "DST"]
        
        starters = {
            "QB": qbs[:1], "RB": rbs[:2], "WR": wrs[:2],
            "TE": tes[:1], "K": ks[:1], "DST": dsts[:1]
        }
        bench = qbs[1:] + rbs[2:] + wrs[2:] + tes[1:] + ks[1:] + dsts[1:]

        st.markdown("**Starting QB**")
        if starters["QB"]: st.info(f"🏈 {starters['QB'][0]['Player']} (Pick {starters['QB'][0]['Pick']})")
        else: st.caption("Empty")

        st.markdown("**Starting RBs (Max 2)**")
        if starters["RB"]:
            for r in starters["RB"]: st.success(f"🏃 {r['Player']} (Pick {r['Pick']})")
        else: st.caption("Empty")

        st.markdown("**Starting WRs (Max 2)**")
        if starters["WR"]:
            for w in starters["WR"]: st.warning(f"🙌 {w['Player']} (Pick {w['Pick']})")
        else: st.caption("Empty")

        st.markdown("**Starting TE**")
        if starters["TE"]: st.error(f"🧱 {starters['TE'][0]['Player']} (Pick {starters['TE'][0]['Pick']})")
        else: st.caption("Empty")
        
        st.markdown("**Starting K**")
        if starters["K"]: st.info(f"🥾 {starters['K'][0]['Player']} (Pick {starters['K'][0]['Pick']})")
        else: st.caption("Empty")
        
        st.markdown("**Starting DST**")
        if starters["DST"]: st.error(f"🛡️ {starters['DST'][0]['Player']} (Pick {starters['DST'][0]['Pick']})")
        else: st.caption("Empty")

        st.markdown("---")
        st.markdown("**Bench / Other**")
        if bench:
            for b in bench: st.caption(f"📌 {b['Player']} ({b['Position']} - Pick {b['Pick']})")
        else: st.caption("No bench players yet")
