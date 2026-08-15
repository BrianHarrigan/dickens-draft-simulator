import os

CSV_FILENAME = "dickens_adp_2026.csv"
EXCEL_FILENAME = "fantasy-cbs-rankings-adp.xlsx"

TEAMS = [
    "Slampigskins", "Thoughts & Praters", "Beav Juicers", "Macksood's Trinkets",
    "Leche Brothers (CAFP)", "CHUBS", "Straight Cash Homey!", "JUGSmachine",
    "Muffed Cunts", "East Coast Fucks", "It's Always Sonny in Bangkok", "The Right Brothers"
]

DRAFT_ORDER = []
for round_num in range(1, 17):
    if round_num % 2 != 0:
        DRAFT_ORDER.extend(TEAMS)
    else:
        DRAFT_ORDER.extend(reversed(TEAMS))

TEAM_NFL_BIASES = {
    "Leche Brothers": {"teams": ["CIN", "CHI"], "boost": 1.5},
    "Beav Juicers": {"teams": ["CIN"], "boost": 1.35},
    "Thoughts & Praters": {"teams": ["CHI", "MIN"], "boost": 1.20},
    "Macksood's Trinkets": {"teams": ["CLE", "CHI"], "boost": 1.20},
    "It's Always Sonny in Bangkok": {"teams": ["PIT"], "boost": 1.20},
    "The Right Brothers (CAFP)": {"teams": ["CIN"], "boost": 1.20},
    "CHUBS": {"teams": ["CHI"], "boost": 1.10},
    "Straight Cash Homey!": {"teams": ["DET"], "boost": 1.10},
    "JUGSmachine": {"teams": ["PIT"], "boost": 1.10},
    "Muffed Cunts": {"teams": ["CHI"], "boost": 1.10},
    "East Coast Fucks": {"teams": ["NYJ"], "boost": 1.10},
    "Slampigskins": {"teams": [], "boost": 1.0}
}

MANAGER_TENDENCIES = {
    "Thoughts & Praters": {"QB": 1.2, "RB": 1.0, "WR": 1.0, "TE": 0.9, "K": 1.0, "DST": 1.0},
    "Beav Juicers": {"QB": 0.9, "RB": 1.3, "WR": 0.9, "TE": 1.0, "K": 1.0, "DST": 1.0},
    "Macksood's Trinkets": {"QB": 1.0, "RB": 0.8, "WR": 1.4, "TE": 1.0, "K": 1.0, "DST": 1.0},
    "Leche Brothers": {"QB": 1.0, "RB": 1.2, "WR": 0.9, "TE": 1.1, "K": 1.0, "DST": 1.0},
    "CHUBS": {"QB": 1.1, "RB": 1.1, "WR": 1.0, "TE": 0.8, "K": 1.0, "DST": 1.0},
    "Straight Cash Homey!": {"QB": 0.8, "RB": 0.9, "WR": 1.3, "TE": 1.2, "K": 1.0, "DST": 1.0},
    "JUGSmachine": {"QB": 1.3, "RB": 1.0, "WR": 0.9, "TE": 0.9, "K": 1.0, "DST": 1.0},
    "Muffed Cunts": {"QB": 0.9, "RB": 1.2, "WR": 1.1, "TE": 1.0, "K": 1.0, "DST": 1.0},
    "East Coast Fucks": {"QB": 1.0, "RB": 1.0, "WR": 1.0, "TE": 1.4, "K": 1.0, "DST": 1.0},
    "It's Always Sonny in Bangkok": {"QB": 1.1, "RB": 0.9, "WR": 1.1, "TE": 1.0, "K": 1.0, "DST": 1.0},
    "The Right Brothers (CAFP)": {"QB": 1.0, "RB": 1.0, "WR": 1.0, "TE": 1.0, "K": 1.0, "DST": 1.0}
}

MANAGER_TARGETS = {
    "Leche": {
        "player": "Joe Burrow",
        "min_round": 2,
        "max_round": 3,
        "probability": 0.85  # 85% chance to draft him when on the clock in Rd 2-3
    }
}

TARGET_PLAYERS = [
    "George Pickens", 
    "Parker Washington", 
    "Wan'Dale Robinson",
    "De'Zhaun Stribling"
]

SLEEPER_PLAYERS = [
    "Wan'Dale Robinson",
    "Denzel Boston",
    "Ja'Kobi Lane",
    "Zachariah Branch",
    "Malachi Fields",
    "Pat Bryant",
    "De'Zhaun Stribling",
    "Jayden Reed",
    "Romeo Doubs",
    "Tre Tucker",
    "Tyler Shough",
    "Dallas Goedert",
    "Tank Dell"
]

def get_color(pos):
    pos_clean = str(pos).strip().upper()
    colors = {"RB": "#add8e6", "WR": "#90ee90", "QB": "#ffcccb", "TE": "#ffffe0", "K": "#e6e6fa", "DST": "#d3d3d3"}
    return colors.get(pos_clean, "#ffffff")

def normalize_name(name):
    return str(name).replace('.', '').replace("'", '').replace("-", "").replace(" ", "").lower()

def make_short_name(name):
    name_str = str(name).replace('.', '').replace("'", '').replace("-", "")
    parts = [p for p in name_str.split() if p.lower() not in ['jr', 'sr', 'ii', 'iii', 'iv']]
    if len(parts) >= 2:
        return (parts[0][0] + "".join(parts[1:])).lower()
    return "".join(parts).lower()