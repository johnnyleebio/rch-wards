import streamlit as st
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
import random
import pandas as pd
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from rapidfuzz import process, fuzz
import hashlib

# Convert UTC to your local timezone (e.g. America/Los_Angeles)
local_time = datetime.now(ZoneInfo("America/Los_Angeles"))
st.write("Local Time:", local_time)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

PASSWORD_HASH = hash_password(st.secrets["PASSWORD"])

# Session setup 
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Password gate - still needs double tap
if not st.session_state.authenticated:
    with st.form("login_form"):
        st.markdown("### 🔐 RCH - Lead | Login\n‼️ You may need to double tap the login button.")
        password_input = st.text_input("Enter Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            if hash_password(password_input) == PASSWORD_HASH:
                st.session_state.authenticated = True
                st.session_state.trigger_rerun = True
            else:
                st.error("❌ Incorrect password")
    st.stop()

# Safe rerun after login
if "trigger_rerun" not in st.session_state:
    st.session_state.trigger_rerun = False
    st.experimental_rerun()
    
# --- Loading Protocol --- 
if "is_loading" not in st.session_state:
    st.session_state.is_loading = False

# Example: Retry loading worksheet up to 3 times
def safe_open_worksheet(spreadsheet, sheet_name, retries=3, delay=5):
    for attempt in range(retries):
        try:
            return spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.APIError as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                st.error("❌ Google Sheets API failed after too many attempts in a short period.")
                st.warning("Please try again in a few seconds or refresh the page.")
                st.stop()

# --- Google Sheets Setup ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
spreadsheet_url = st.secrets["GSHEET"]
spreadsheet = client.open_by_url(spreadsheet_url)
worksheet = safe_open_worksheet(spreadsheet, "ADMITS")
#spreadsheet_url_beta = st.secrets["GSHEET_BETA"]
#spreadsheet_beta = client.open_by_url(spreadsheet_url_beta)
#directory = safe_open_worksheet(spreadsheet_beta, "Directory")
#schedule = safe_open_worksheet(spreadsheet_beta, "Schedule")
directory = safe_open_worksheet(spreadsheet, "Directory")
schedule = safe_open_worksheet(spreadsheet, "Wards")

# --- Streamlit UI ---
st.title("RCH - Lead")
st.markdown(
    """
    ‼️ Please make sure the following sheets are up to date on the Admit Tracker:  
    • **ADMITS**  
    • **Directory**  
    • **Wards**
    """
)
# Display name to internal key mapping
emoji_style_options = {
    "Circles": "circles",
    "Animal [Set 1]": "animal1",
    "Animal [Set 2]": "animal2",
    "Fruits": "fruits",
    "Hearts": "hearts"
}

# Select with friendly labels
selected_label = st.selectbox("Choose Emoji Style", list(emoji_style_options.keys()))
emoji_style = emoji_style_options[selected_label]  # actual key to use
include_orange = st.checkbox("Include Orange in Round Robin 🍊", value=False)
include_pgy1_interns = st.checkbox("Include Categorical Interns 💪", value=False)
generate = st.button("💬 Generate Message", disabled=st.session_state.is_loading)

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
        "animal1": ["🦐"],
        "animal2": ["🦀"],
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
    "lead": "Lead",
    "long": "Lead",
}

# --- Session state setup for message ---
if "census_message" not in st.session_state:
    st.session_state.census_message = ""
if "message_generated" not in st.session_state:
    st.session_state.message_generated = False

if generate:
    st.session_state.is_loading = True
    with st.spinner("Generating message..."):
        raw_headers = worksheet.row_values(2)
        green_index = None
        
        for idx, val in enumerate(raw_headers):
            if "green" in val.lower():
                green_index = idx + 1  # gspread is 1-based
                break
        
        if green_index is None:
            st.error("❌ No column found with 'green' in the header (row 2).")
            st.stop()
    
        col_m = worksheet.col_values(green_index)        # "Green"
        col_n = worksheet.col_values(green_index + 1)    # next column
        col_o = worksheet.col_values(green_index + 2)    # column after that

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
                    continue

                emoji_list = emoji_by_color.get(color, {}).get(emoji_style, [])
                if emoji_list:
                    emoji = random.choice(emoji_list)
                    team_entries.append({"team": team, "doctor": doctor, "census": census, "emoji": emoji})
            except Exception as e:
                st.error(f"Error parsing row: {e}")

        team_entries.sort(key=lambda x: team_order.index(x["team"]) if x["team"] in team_order else 99)

        message = "Good morning! Please confirm census:\n\n"
        for entry in team_entries:
            message += f"{entry['emoji']} {entry['team']}/{entry['doctor']}: {entry['census']}\n"

        st.session_state.census_message = message
        st.session_state.message_generated = True
    st.session_state.is_loading = False

# if st.session_state.message_generated and st.button("❌ Clear Message"):
#     st.session_state.census_message = ""
#     st.session_state.message_generated = False

if st.session_state.message_generated and st.session_state.census_message:
    st.markdown("📋 **Tap on the upper right hand corner of the box to copy** ‼️")
    st.code(st.session_state.census_message, language="text")

# --- Pull Attending Names (respects include_orange checkbox) ---
raw_headers = worksheet.row_values(2)
green_index = None

for idx, val in enumerate(raw_headers):
    if "green" in val.lower():
        green_index = idx + 1  # gspread is 1-based
        break

if green_index is None:
    st.error("❌ No column found with 'green' in the header (row 2).")
    st.stop()

col_m = worksheet.col_values(green_index)        # "Green"
col_n = worksheet.col_values(green_index + 1)    # next column
col_o = worksheet.col_values(green_index + 2)    # column after that

attending_names = set()
for m, n, o in zip(col_m, col_n, col_o):
    try:
        if not m.strip() or ":" not in m:
            continue
        color_part, _ = m.split(":")
        color = color_part.strip().upper()
        is_orange = color == "ORANGE"
        is_on_call = o.strip().endswith("CALL")

        # Only include if CALL or (orange and checkbox is checked)
        if not is_on_call and not (include_orange and is_orange):
            continue

        name = n.split("|")[0].strip()
        if name:
            attending_names.add(name)
    except:
        continue

# --- Load Schedule and Directory ---
df_schedule = pd.DataFrame(schedule.get_all_values())
df_dir = pd.DataFrame(directory.get_all_values())
df_dir.columns = df_dir.iloc[0]
df_dir = df_dir.drop(index=0).reset_index(drop=True)
df_dir.columns = [col.strip() for col in df_dir.columns]
df_dir['FullName'] = (df_dir['First'].astype(str).str.strip() + " " + df_dir['Last'].astype(str).str.strip()).str.lower()

# --- Helper to get phone numbers ---
def get_phone_numbers(name_list, df, threshold=90):
    phones = {}
    for name in name_list:
        name_clean = name.strip().lower()
        if name_clean in df['FullName'].values:
            idx = df[df['FullName'] == name_clean].index[0]
            phones[name] = df.loc[idx, 'Phone']
        else:
            best_match = process.extractOne(name_clean, df['FullName'], scorer=fuzz.partial_ratio)
            if best_match and best_match[1] >= threshold:
                idx = df[df['FullName'] == best_match[0]].index[0]
                phones[name] = df.loc[idx, 'Phone']
            else:
                phones[name] = "Not found"
    return phones

# --- Identify Week Block ---
today = local_time.date()
section_starts = []
for i, val in enumerate(df_schedule.iloc[:, 0]):
    try:
        date_val = pd.to_datetime(val, errors='coerce').date()
        if pd.notnull(date_val):
            section_starts.append((i, date_val))
    except:
        continue

target_start_row = None
for i, date_val in section_starts:
    if date_val <= today <= date_val + timedelta(days=6):
        target_start_row = i
        break

# --- Get PGY2/PGY3 Names ---
pgy3_names, pgy2_names = [], []
if target_start_row is not None:
    week_block = df_schedule.iloc[target_start_row:target_start_row + 8]
    pgy3_row = week_block[week_block.iloc[:, 1] == "PGY3"]
    pgy2_row = week_block[week_block.iloc[:, 1] == "PGY2"]
    pgy3_names = pgy3_row.iloc[0, 2:6].dropna().tolist() if not pgy3_row.empty else []
    pgy2_names = pgy2_row.iloc[0, 2:6].dropna().tolist() if not pgy2_row.empty else []
    pgy3_names = [n.strip() for n in pgy3_names if n.strip()]
    pgy2_names = [n.strip() for n in pgy2_names if n.strip()]

# --- Get PGY1 Names (optional interns) ---
pgy1_names = []
if target_start_row is not None:
    week_block = df_schedule.iloc[target_start_row:target_start_row + 8]
    
    # Find the index where "PGY1" is first mentioned in column B
    pgy1_start_idx = None
    for i, val in enumerate(week_block.iloc[:, 1]):
        if val.strip() == "PGY1":
            pgy1_start_idx = i
            break

    if pgy1_start_idx is not None:
        # Take 3 rows: PGY1 label + 2 following
        pgy1_block = week_block.iloc[pgy1_start_idx:pgy1_start_idx + 3]

        for _, row in pgy1_block.iterrows():
            # Use columns C–F (index 2 to 5); skip G/H (6/7)
            for col_index in range(2, 6):
                name = str(row.iloc[col_index]).strip()
                if not name or any(bad in name.lower() for bad in ["ty", "neuro", "anes", "anesthesia"]):
                    continue
                name = name.replace(":", "")
                pgy1_names.append(name)

# --- Include Admins ---
always_include = ['Sahar Eivaz', 'Lawren Green']
for name in always_include:
    if name not in pgy3_names and name not in pgy2_names:
        pgy3_names.append(name)

# --- Phone Number Section Trigger ---
if "contacts_generated" not in st.session_state:
    st.session_state.contacts_generated = False
if "contact_data" not in st.session_state:
    st.session_state.contact_data = {}

contact_btn = st.button("📞 Generate Contact List", disabled=st.session_state.is_loading)

if contact_btn:
    st.session_state.is_loading = True
    with st.spinner("Generating contact list..."):
        # --- Phone Lookups ---
        pgy3_phones = get_phone_numbers(pgy3_names, df_dir, threshold=70)
        pgy2_phones = get_phone_numbers(pgy2_names, df_dir, threshold=70)
        attending_phones = get_phone_numbers(attending_names, df_dir, threshold=70)

        # Optional interns
        intern_phones = {}
        if include_pgy1_interns:
            intern_phones = get_phone_numbers(pgy1_names, df_dir, threshold=70)

        admin_names = {'Sahar Eivaz', 'Lawren Green'}
        seniors = {n: p for n, p in {**pgy3_phones, **pgy2_phones}.items() if n not in admin_names}
        admins = {n: p for n, p in {**pgy3_phones, **pgy2_phones}.items() if n in admin_names}
        attendings = {n: p for n, p in attending_phones.items() if n not in seniors and n not in admins}

        all_numbers = list({
            p for p in list(seniors.values()) +
                          list(admins.values()) +
                          list(attendings.values()) +
                          list(intern_phones.values())
            if p != "Not found"
        })
        joined_numbers = ", ".join(all_numbers)

        st.session_state.contacts_generated = True
        st.session_state.contact_data = {
            "seniors": seniors,
            "admins": admins,
            "attendings": attendings,
            "interns": intern_phones,
            "numbers": joined_numbers
        }
    st.session_state.is_loading = False

# --- Clear Button ---
# if st.session_state.contacts_generated and st.button("❌ Clear Contact List"):
#     st.session_state.contacts_generated = False
#     st.session_state.contact_data = {}

# --- Display Section ---
if st.session_state.contacts_generated:
    today_str = today.strftime("%B %d, %Y")  # use the same `today` from above  # e.g., July 8, 2025
    st.success(f"✅ Contact List Generated! ({today_str})") # date function is broken

    st.subheader("📘 Seniors")
    for name, phone in st.session_state.contact_data["seniors"].items():
        st.write(f"**{name}**: {phone}")

    st.subheader("🧑‍⚕️ Interns (PGY1)")
    for name, phone in st.session_state.contact_data["interns"].items():
        st.write(f"**{name}**: {phone}")

    st.subheader("🏛️ Admin / Operations")
    for name, phone in st.session_state.contact_data["admins"].items():
        st.write(f"**{name}**: {phone}")

    st.subheader("😎 Attendings")
    for name, phone in st.session_state.contact_data["attendings"].items():
        st.write(f"**{name}**: {phone}")

    st.markdown("📋 **Tap on the upper right hand corner of the box to copy** ‼️")
    st.code(st.session_state.contact_data["numbers"], language="text")
