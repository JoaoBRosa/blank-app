import streamlit as st
import requests
import difflib
import re
from openai import OpenAI

# --- API KEYS (Loaded securely from Streamlit Cloud Secrets) ---
TMDB_API_KEY = st.secrets["api_keys"]["tmdb"]
OPENAI_API_KEY = st.secrets["api_keys"]["openai"]

# --- Initialize OpenAI client ---
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Functions ---
def search_tmdb_movies(answers):
    genre_map = {
        "Action": 28, "Comedy": 35, "Drama": 18, "Sci-Fi": 878, "Romance": 10749,
        "Thriller": 53, "Horror": 27, "Animation": 16, "Documentary": 99, "Fantasy": 14
    }
    language_map = {
        "English": "en", "French": "fr", "Spanish": "es", "Korean": "ko", "Italian": "it", "Portuguese": "pt"
    }
    year_range_map = {
        "Before 1950": (1900, 1949), "1950-1980": (1950, 1980), "1980-2000": (1980, 2000),
        "2000-2010": (2000, 2010), "2010–2020": (2010, 2020), "2020-2024": (2020, 2024)
    }

    genre_ids = [str(genre_map[g]) for g in answers.get('genre', []) if g in genre_map]
    language_codes = [language_map[lang] for lang in answers.get('language', []) if lang != "No preference" and lang in language_map]
    selected_range = year_range_map.get(answers.get('release_year'), None)
    min_year, max_year = selected_range if selected_range else (None, None)

    duration_pref = answers.get('duration', 'More than 2 hours')
    if duration_pref == "Less than 90 minutes":
        with_runtime = (0, 89)
    elif duration_pref == "Around 90–120 minutes":
        with_runtime = (0, 120)
    elif duration_pref == "More than 2 hours":
        with_runtime = (120, 400)
    else:
        with_runtime = (0, 400)

    results = []
    for page in range(1, 6):
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=en-US&sort_by=popularity.desc&page={page}"
        if genre_ids:
            url += f"&with_genres={','.join(genre_ids)}"
        if language_codes:
            url += f"&with_original_language={language_codes[0]}"
        if min_year:
            url += f"&primary_release_date.gte={min_year}-01-01"
        if max_year:
            url += f"&primary_release_date.lte={max_year}-12-31"
        url += f"&with_runtime.gte={with_runtime[0]}&with_runtime.lte={with_runtime[1]}"

        response = requests.get(url)
        data = response.json()
        filtered = [
            movie for movie in data.get("results", [])
            if all(int(gid) in movie.get("genre_ids", []) for gid in map(int, genre_ids))
        ]
        results.extend(filtered)
    return results

def select_single_movie_with_openai(movies, user_preferences):
    prompt = f"From the list below, select one movie that best fits the user's preferences.

"
    prompt += "User's Preferences:
"
    for key, val in user_preferences.items():
        prompt += f"- {key}: {val}\n"

    prompt += "\nMovies List:\n"
    for movie in movies[:30]:  # Cap it for token safety
        prompt += f"- {movie.get('title', '')} ({movie.get('release_date', '')[:4]})\n"

    prompt += "\nReturn ONLY the exact title of the best match."

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

def find_movie_details(title, movie_pool):
    clean_title = re.sub(r"\s*\(\d{4}\)$", "", title).strip()
    match = difflib.get_close_matches(clean_title, [m['title'] for m in movie_pool], n=1, cutoff=0.8)
    return next((m for m in movie_pool if m['title'] == match[0]), None) if match else None

# --- UI ---
st.title("🎬 AI Movie Recommender")
if "tmdb_results" not in st.session_state:
    st.session_state.tmdb_results = []
if "recommended" not in st.session_state:
    st.session_state.recommended = None

with st.form("movie_form"):
    st.write("### Your Preferences")
    duration = st.radio("How much time do you have?", ["Less than 90 minutes", "Around 90–120 minutes", "More than 2 hours"])
    language = st.multiselect("Preferred language(s)", ["English", "French", "Spanish", "Korean", "Italian", "Portuguese", "No preference"])
    genre = st.multiselect("Genre(s)", ["Action", "Comedy", "Drama", "Sci-Fi", "Romance", "Thriller", "Horror", "Animation", "Documentary", "Fantasy"])
    release_year = st.selectbox("Release year?", ["Before 1950", "1950-1980", "1980-2000", "2000-2010", "2010–2020", "2020-2024", "No preference"])
    mood = st.multiselect("Mood", ["Happy", "Sad", "Romantic", "Adventurous", "Tense / Anxious", "I don't really know"])
    company = st.selectbox("Watching with", ["Alone", "Friends", "Family", "Date", "Other"])
    with_kids = st.radio("Are kids watching?", ["Yes", "No"])
    tone = st.radio("Tone", ["Emotionally deep", "Easygoing"])
    popularity = st.radio("Popularity", ["I prefer well known", "Under the radar", "No preference"])
    real_or_fiction = st.radio("Story type", ["Real events", "Fictional Narratives", "No preference"])
    discussion = st.radio("Conversation-worthy?", ["Yes", "No", "No preference"])
    soundtrack = st.radio("Strong soundtrack?", ["Yes", "No", "No preference"])
    find_clicked = st.form_submit_button("🎥 Find Movies")

if find_clicked:
    answers = {
        "duration": duration, "language": language, "genre": genre, "release_year": release_year,
        "mood": mood, "company": company, "with_kids": with_kids, "tone": tone,
        "popularity": popularity, "real_or_fiction": real_or_fiction,
        "discussion": discussion, "soundtrack": soundtrack
    }
    with st.spinner("🔍 Searching TMDb..."):
        st.session_state.tmdb_results = search_tmdb_movies(answers)
    st.success(f"✅ Found {len(st.session_state.tmdb_results)} movies.")
    if st.session_state.tmdb_results:
        st.session_state.recommended = select_single_movie_with_openai(st.session_state.tmdb_results, answers)

# --- Display AI Movie ---
if st.session_state.get("recommended"):
    st.markdown("## 🌟 AI-Recommended Movie")
    movie = find_movie_details(st.session_state.recommended, st.session_state.tmdb_results)
    if movie:
        st.markdown(f"### 🎬 {movie['title']} ({movie.get('release_date', '')[:4]})")
        if movie.get("poster_path"):
            st.image(f"https://image.tmdb.org/t/p/w500{movie['poster_path']}", width=300)
        st.write(movie.get("overview", "No synopsis available."))
        if st.button("🔁 Try Another"):
            answers = {
                "duration": duration, "language": language, "genre": genre, "release_year": release_year,
                "mood": mood, "company": company, "with_kids": with_kids, "tone": tone,
                "popularity": popularity, "real_or_fiction": real_or_fiction,
                "discussion": discussion, "soundtrack": soundtrack
            }
            st.session_state.recommended = select_single_movie_with_openai(st.session_state.tmdb_results, answers)
    else:
        st.warning("⚠️ AI suggested a title that wasn't found in the search results.")

