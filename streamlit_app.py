import streamlit as st
import requests
import difflib
import re
from openai import OpenAI
import smtplib
from email.message import EmailMessage

# --- Load API keys from secrets.toml ---
TMDB_API_KEY = st.secrets["api_keys"]["tmdb"]
OPENAI_API_KEY = st.secrets["api_keys"]["openai"]

# --- Load Email credentials from secrets.toml ---
SMTP_SERVER = st.secrets["email"]["smtp_server"]
SMTP_PORT   = st.secrets["email"]["smtp_port"]
EMAIL_USER  = st.secrets["email"]["username"]
EMAIL_PASS  = st.secrets["email"]["password"]

# --- Initialize OpenAI client ---
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Helper: send_email via SMTP SSL ---
def send_email(subject: str, body: str, to_email: str):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = EMAIL_USER
    msg["To"]      = to_email
    msg.set_content(body)
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)

# --- Helper: TMDb Search ---
def search_tmdb_movies(answers):
    genre_map = {
        "Action":28, "Comedy":35, "Drama":18, "Sci-Fi":878, "Romance":10749,
        "Thriller":53, "Horror":27, "Animation":16, "Documentary":99, "Fantasy":14
    }
    language_map = {
        "English":"en", "French":"fr", "Spanish":"es", "Korean":"ko",
        "Italian":"it", "Portuguese":"pt"
    }
    year_map = {
        "Before 1950": (1900,1949),
        "1950-1980":  (1950,1980),
        "1980-2000":  (1980,2000),
        "2000-2010":  (2000,2010),
        "2010–2020":  (2010,2020),
        "2020-2024":  (2020,2024)
    }

    genres = [str(genre_map[g]) for g in answers["genre"]]
    langs  = [language_map[l] for l in answers["language"] if l != "No preference"]
    min_y, max_y = year_map.get(answers["release_year"], (None, None))

    dur = answers["duration"]
    if dur == "Less than 90 minutes":
        runtime = (0, 89)
    elif dur == "Around 90–120 minutes":
        runtime = (0, 120)
    else:
        runtime = (90, 400)

    results = []
    for page in range(1, 4):
        url = (
            f"https://api.themoviedb.org/3/discover/movie?"
            f"api_key={TMDB_API_KEY}&sort_by=popularity.desc&page={page}"
            f"&with_runtime.gte={runtime[0]}&with_runtime.lte={runtime[1]}"
        )
        if genres:
            url += "&with_genres=" + ",".join(genres)
        if langs:
            url += "&with_original_language=" + langs[0]
        if min_y:
            url += f"&primary_release_date.gte={min_y}-01-01"
        if max_y:
            url += f"&primary_release_date.lte={max_y}-12-31"

        r = requests.get(url)
        if r.ok:
            for m in r.json().get("results", []):
                if all(int(gid) in m["genre_ids"] for gid in genres):
                    results.append(m)
    return results

# --- Helper: Get Streaming Providers ---
def get_streaming_info(movie_id, country_code="PT"):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers?api_key={TMDB_API_KEY}"
    r = requests.get(url)
    if not r.ok:
        return None
    data = r.json().get("results", {}).get(country_code, {})
    if not data:
        return None
    return {
        "subscription": [p["provider_name"] for p in data.get("flatrate", [])],
        "rent":         [p["provider_name"] for p in data.get("rent", [])],
        "buy":          [p["provider_name"] for p in data.get("buy", [])],
        "link":         data.get("link")
    }

# --- Helper: GPT picks one movie ---
def pick_movie(movies, prefs, prev=None):
    prompt = "🎯 From the list below, pick ONE movie that best fits the user's preferences.\n\n"
    prompt += "📝 Preferences:\n" + "\n".join(f"- {k}: {v}" for k,v in prefs.items()) + "\n\n📽 Movies List:\n"
    for m in movies[:30]:
        prompt += f"- {m['title']} ({m.get('release_date','')[:4]})\n"
    if prev:
        prompt += f"\n⚠️ Previously recommended: {prev}. Choose a different one.\n"
    prompt += "\nReturn ONLY the exact movie title."

    res = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user","content":prompt}],
        max_tokens=50,
        temperature=0.8
    )
    return res.choices[0].message.content.strip()

# --- Helper: Find matched details ---
def find_details(title, pool):
    clean = re.sub(r"\s*\(\d{4}\)$","", title).strip()
    match = difflib.get_close_matches(clean, [m["title"] for m in pool], n=1, cutoff=0.7)
    return next((m for m in pool if m["title"] == match[0]), None) if match else None

# --- UI & Session State Setup ---
st.title("🍿 AI Movie Recommender")

if "tmdb_results" not in st.session_state:
    st.session_state.tmdb_results = []
if "recommendation" not in st.session_state:
    st.session_state.recommendation = None

# --- Preferences Form ---
with st.form("preferences_form"):
    st.header("1️⃣ Tell us about your preferences")
    duration     = st.radio("⏱️ How much time for a movie?", ["Less than 90 minutes","Around 90–120 minutes","More than 2 hours"])
    language     = st.multiselect("🌐 Preferred languages", ["English","French","Spanish","Korean","Italian","Portuguese","No preference"])
    genre        = st.multiselect("🎞️ Genres you like", ["Action","Comedy","Drama","Sci-Fi","Romance","Thriller","Horror","Animation","Documentary","Fantasy"])
    release_year = st.selectbox("📅 Release year preference", ["Before 1950","1950-1980","1980-2000","2000-2010","2010–2020","2020-2024","No preference"])

    st.markdown("---")
    st.header("2️⃣ Mood & Extras")
    mood         = st.multiselect("😊 How are you feeling?", ["Happy","Sad","Romantic","Adventurous","Tense/Anxious","I don't really know"])
    company      = st.selectbox("👥 Who are you watching with?", ["Alone","Friends","Family","Date","Other"])
    with_kids    = st.radio("👶 With kids?", ["Yes","No"])
    tone         = st.radio("💭 Tone preference", ["Emotionally deep","Easygoing"])
    popularity   = st.radio("🔥 Popularity level", ["Well known","Under the radar","No preference"])
    real_or_fic  = st.radio("📖 Story type", ["Real events","Fictional Narratives","No preference"])
    discussion   = st.radio("💬 Conversation-worthy?", ["Yes","No","No preference"])
    soundtrack   = st.radio("🎵 Importance of soundtrack", ["Yes","No","No preference"])

    find_clicked = st.form_submit_button("🔍 Find Movies")

if find_clicked:
    st.session_state.prefs = {
        "duration":       duration,
        "language":       language,
        "genre":          genre,
        "release_year":   release_year,
        "mood":           mood,
        "company":        company,
        "with_kids":      with_kids,
        "tone":           tone,
        "popularity":     popularity,
        "real_or_fiction":real_or_fic,
        "discussion":     discussion,
        "soundtrack":     soundtrack
    }
    with st.spinner("🔎 Searching TMDb..."):
        st.session_state.tmdb_results = search_tmdb_movies(st.session_state.prefs)

    if not st.session_state.tmdb_results:
        st.error("❌ No movies found.")
    else:
        st.success(f"✅ Found {len(st.session_state.tmdb_results)} movies!")
        # initial recommendation
        st.session_state.recommendation = pick_movie(
            st.session_state.tmdb_results,
            st.session_state.prefs
        )

# --- Display Recommendation & Features ---
rec = st.session_state.get("recommendation")
if rec and st.session_state.tmdb_results:
    st.markdown("## 🌟 AI-Recommended Movie")

    detail = find_details(rec, st.session_state.tmdb_results)
    if not detail:
        st.warning("⚠️ Couldn't find details for the AI pick.")
    else:
        title    = detail["title"]
        year     = detail.get("release_date","")[:4]
        overview = detail.get("overview","No synopsis available.")

        # Poster + synopsis
        col1, col2 = st.columns([1,2])
        with col1:
            if detail.get("poster_path"):
                st.image(f"https://image.tmdb.org/t/p/w500{detail['poster_path']}", width=200)
        with col2:
            st.markdown(f"### 🎬 {title} ({year})")
            st.write(overview)

        # 🔁 Try Another
        if st.button("🔁 Try Another", key="try_another"):
            st.session_state.recommendation = pick_movie(
                st.session_state.tmdb_results,
                st.session_state.prefs,
                prev=st.session_state.recommendation
            )

        # 📺 Streaming Options
        providers = get_streaming_info(detail["id"], country_code="PT")
        if providers:
            st.markdown("#### 📺 Where to Watch (Portugal)")
            if providers["subscription"]:
                st.markdown("**Included with subscription:**")
                for p in providers["subscription"]:
                    st.markdown(f"- {p}")
            if providers["rent"]:
                st.markdown("**Available to rent:**")
                for p in providers["rent"]:
                    st.markdown(f"- {p}")
            if providers["buy"]:
                st.markdown("**Available to buy:**")
                for p in providers["buy"]:
                    st.markdown(f"- {p}")
            if providers["link"]:
                st.markdown(f"[See all options]({providers['link']})")
        else:
            st.info("No streaming info found for Portugal.")

        # ➕ Add to my watchlist
        if st.button("➕ Add to my watchlist", key="add_watchlist"):
            subject = f"Watchlist: {title} ({year})"
            body    = f"Don't forget to watch:\n\n{title} ({year})\n\nSynopsis:\n{overview}"
            send_email(subject, body, EMAIL_USER)
            st.success("✅ Added to your watchlist!")

        # 📧 Send to a friend
        friend_email = st.text_input("📧 Friend's email address", key="friend_email")
        if friend_email and st.button("📤 Send to friend", key="send_to_friend"):
            subject = f"I Recommend You Watch: {title} ({year})"
            body    = f"Hey,\n\nI thought you might enjoy this movie:\n\n{title} ({year})\n\n{overview}\n\nEnjoy! 🍿"
            try:
                send_email(subject, body, friend_email)
                st.success(f"🎉 Recommendation sent to {friend_email}!")
            except Exception as e:
                st.error(f"❌ Failed to send: {e}")
