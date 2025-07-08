import streamlit as st
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
import random

# --- Google Sheets Setup ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
spreadsheet_url = st.secrets["GSHEET"]
spreadsheet = client.open_by_url(spreadsheet_url)
worksheet = spreadsheet.worksheet("ADMITS")

# --- Streamlit UI ---
st.title("Census Emoji Message Generator")
emoji_style = st.selectbox("Choose Emoji Style", ["circles", "animal1", "animal2", "fruits", "hearts"])
include_orange = st.checkbox("Include Orange 🍊", value=False)
generate = st.button("Generate Message")

# --- Emoji Bank ---
emoji_by_color = {
    "GREEN": {
        "circles": ["🟢"],
        "animal1": ["🐢", "🐸"],
        "animal2": ["🦖", "🦎"],
        "fruits": ["🥝", "🍐"],
        "hearts": ["💚"]
    },
    "RED": {
        "circles": ["🔴"],
        "animal1": ["🦐", "🦀"],
        "animal2": ["🦊"],
        "fruits": ["🍎", "🍒"],
        "hearts": ["❤️"]
    },
    "BLUE": {
        "circles": ["🔵"],
        "animal1": ["🐟", "🐳"],
        "animal2": ["🐬", "🦕"],
        "fruits": ["🫐"],
        "hearts": ["💙"]
    },
    "PURPLE": {
        "circles": ["🟣"],
        "animal1": ["🦄"],
        "animal2": ["👾"],
        "fruits": ["🍇"],
        "hearts": ["💜"]
    },
    "ORANGE": {
        "circles": ["🟠"],
        "animal1": ["🦊"],
        "animal2": ["🦁"],
        "fruits": ["🍊", "🎃"],
        "hearts": ["🧡"]
    }
}

team_order = ["Post", "Short", "Medium", "Lead"]

team_name_map = {
    "post": "Post",
    "short": "Short",
    "med": "Medium",
    "medium": "Medium",
    "lead": "Lead"
}

if generate:
    col_m = worksheet.col_values(13)
    col_n = worksheet.col_values(14)
    col_o = worksheet.col_values(15)
    team_entries = []

    for m, n, o in zip(col_m, col_n, col_o):
        try:
            if ":" not in m:
                continue
            color_part, census_part = m.split(":")
            color = color_part.strip().upper()
            if not o.strip().endswith("CALL") and not (color == "ORANGE" and include_orange):
                continue
            census = int(census_part.strip())
            doctor = n.split("|")[0].strip()
            team = None
            team_parts = o.strip().split()
            if team_parts:
                raw_team = team_parts[0].lower()
                team = team_name_map.get(raw_team, raw_team.capitalize())
            elif color == "ORANGE" and include_orange:
                team = "Orange"
            else:
                continue  # skip if no valid team

            emoji_list = emoji_by_color.get(color, {}).get(emoji_style, [])
            if emoji_list:
                emoji = random.choice(emoji_list)
                team_entries.append({
                    "team": team,
                    "doctor": doctor,
                    "census": census,
                    "emoji": emoji
                })
        except Exception as e:
            st.error(f"Error parsing row: {e}")

    team_entries.sort(
    key=lambda x: team_order.index(x["team"]) if x["team"] in team_order else 99
)

    message = "Good morning! Please confirm census:\n\n"
    for entry in team_entries:
        message += f"{entry['emoji']} {entry['team']}/{entry['doctor']}: {entry['census']}\n"

    # st.text_area("Generated Message", message, height=200)
    # st.download_button("Download Message as TXT", message, file_name="census_message.txt")
    # Editable message box
    # editable_message = st.text_area("Generated Message (Editable)", message, height=200)
    
    # Copyable code block with built-in copy button
    st.markdown("#### Click to copy:")
    st.code(message, language="text")
