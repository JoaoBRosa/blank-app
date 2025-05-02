import streamlit as st
import requests
import difflib
import re
from openai import OpenAI

# --- Load API keys from secrets.toml ---
TMDB_API_KEY = st.secrets["api_keys"]["tmdb"]
OPENAI_API_KEY = st.secrets["api_keys"]["openai"]

# --- Initialize OpenAI client ---
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Helper: Search TMDb ---
def search_tmdb_movies(answers):
    genre_map = {"Action":28,"Comedy":35,"Drama":18,"Sci-Fi":878,"Romance":10749,
                 "Thriller":53,"Horror":27,"Animation":16,"Documentary":99,"Fantasy":14}
    language_map = {"English":"en","French":"fr","Spanish":"es","Korean":"ko","Italian":"it","Portuguese":"pt"}
    year_map = {
        "Before 1950": (1900,1949), "1950-1980": (1950,1980), "1980-2000": (1980,2000),
        "2000-2010": (2000,2010), "2010–2020": (2010,2020), "2020-2024": (2020,2024)
    }

    genres = [str(genre_map[g]) for g in answers["genre"]]
    langs  = [language_map[l] for l in answers["language"] if l!="No preference"]
    min_y, max_y = year_map.get(answers["release_year"], (None,None))

    # runtime
    if answers["duration"]=="Less than 90 minutes": runtime=(0,89)
    elif answers["duration"]=="Around 90–120 minutes": runtime=(0,120)
    else: runtime=(90,400)

    results=[]
    for page in range(1,4):
        url = (
            f"https://api.themoviedb.org/3/discover/movie?"
            f"api_key={TMDB_API_KEY}&sort_by=popularity.desc&page={page}"
            f"&with_runtime.gte={runtime[0]}&with_runtime.lte={runtime[1]}"
        )
        if genres:   url += "&with_genres=" + ",".join(genres)
        if langs:    url += "&with_original_language=" + langs[0]
        if min_y:    url += f"&primary_release_date.gte={min_y}-01-01"
        if max_y:    url += f"&primary_release_date.lte={max_y}-12-31"

        resp = requests.get(url)
        if resp.ok:
            for m in resp.json().get("results", []):
                # require all genres
                if all(int(g) in m["genre_ids"] for g in genres):
                    results.append(m)
    return results

# --- Helper: Pick one movie via GPT ---
def pick_movie(gpt_list, prefs, prev=None):
    prompt = "Select ONE movie from the list below that best fits these user preferences.\n\n"
    prompt += "Preferences:\n" + "\n".join(f"- {k}: {v}" for k,v in prefs.items()) + "\n\nMovies:\n"
    for m in gpt_list[:30]:  # cap to 30 for tokens
        prompt += f"- {m['title']} ({m.get('release_date','')[:4]})\n"
    if prev:
        prompt += f"\nPreviously chosen: {prev}. Please choose a different one if possible.\n"
    prompt += "\nReturn ONLY the exact movie title."

    res = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user","content":prompt}],
        max_tokens=50,
        temperature=0.8
    )
    return res.choices[0].message.content.strip()

# --- UI & State ---
st.title("🎬 AI Movie Recommender")

if "tmdb_results" not in st.session_state:
    st.session_state.tmdb_results = []
if "recommendation" not in st.session_state:
    st.session_state.recommendation = None

with st.form("all_prefs"):
    st.subheader("Tell me about your preferences")
    duration     = st.radio("How much time?", ["Less than 90 minutes","Around 90–120 minutes","More than 2 hours"])
    language     = st.multiselect("Preferred language(s)", ["English","French","Spanish","Korean","Italian","Portuguese","No preference"])
    genre        = st.multiselect("Genres", ["Action","Comedy","Drama","Sci-Fi","Romance","Thriller","Horror","Animation","Documentary","Fantasy"])
    release_year = st.selectbox("Release year", ["Before 1950","1950-1980","1980-2000","2000-2010","2010–2020","2020-2024","No preference"])
    mood         = st.multiselect("Mood", ["Happy","Sad","Romantic","Adventurous","Tense/Anxious","I don't really know"])
    company      = st.selectbox("Watching with", ["Alone","Friends","Family","Date","Other"])
    with_kids    = st.radio("With kids?", ["Yes","No"])
    tone         = st.radio("Tone", ["Emotionally deep","Easygoing"])
    popularity   = st.radio("Popularity", ["Well known","Under the radar","No preference"])
    real_or_fic  = st.radio("Story type", ["Real events","Fictional Narratives","No preference"])
    discussion   = st.radio("Conversation-worthy?", ["Yes","No","No preference"])
    soundtrack   = st.radio("Strong soundtrack?", ["Yes","No","No preference"])
    find = st.form_submit_button("🎥 Find Movies")

if find:
    st.session_state.prefs = {
        "duration":duration,"language":language,"genre":genre,"release_year":release_year,
        "mood":mood,"company":company,"with_kids":with_kids,"tone":tone,
        "popularity":popularity,"real_or_fiction":real_or_fic,"discussion":discussion,"soundtrack":soundtrack
    }
    with st.spinner("🔍 Searching TMDb..."):
        st.session_state.tmdb_results = search_tmdb_movies(st.session_state.prefs)
    if not st.session_state.tmdb_results:
        st.error("❌ No movies matched.")
    else:
        st.success(f"✅ Found {len(st.session_state.tmdb_results)} movies.")
        # first recommendation
        st.session_state.recommendation = pick_movie(st.session_state.tmdb_results, st.session_state.prefs)

# Display recommendation
rec = st.session_state.recommendation
if rec and st.session_state.tmdb_results:
    st.markdown("## 🌟 AI-Recommended Movie")
    # lookup details
    titles = [m["title"] for m in st.session_state.tmdb_results]
    match = difflib.get_close_matches(rec, titles, n=1, cutoff=0.7)
    movie = next((m for m in st.session_state.tmdb_results if m["title"]==match[0]), None) if match else None
    if movie:
        st.markdown(f"### {movie['title']} ({movie.get('release_date','')[:4]})")
        if movie.get("poster_path"):
            st.image(f"https://image.tmdb.org/t/p/w500{movie['poster_path']}", width=300)
        st.write(movie.get("overview","No synopsis available."))
        if st.button("🔁 Try Another"):
            st.session_state.recommendation = pick_movie(
                st.session_state.tmdb_results,
                st.session_state.prefs,
                prev=st.session_state.recommendation
            )
    else:
        st.warning("⚠️ Couldn't find details for the AI's pick.")
