import streamlit as st
import requests
import difflib
import re

# ✅ NEW OpenAI SDK v1.x
from openai import OpenAI

# --- SECURE API KEYS ---
TMDB_API_KEY = st.secrets["api_keys"]["tmdb"]
OPENAI_API_KEY = st.secrets["api_keys"]["openai"]
client = OpenAI(api_key=OPENAI_API_KEY)

# --- CONSTANTS ---
GENRE_MAP = {
    "Action": 28, "Comedy": 35, "Drama": 18, "Sci-Fi": 878, "Romance": 10749,
    "Thriller": 53, "Horror": 27, "Animation": 16, "Documentary": 99, "Fantasy": 14
}

LANGUAGE_MAP = {
    "English": "en", "French": "fr", "Spanish": "es", "Korean": "ko", "Italian": "it", "Portuguese": "pt"
}

YEAR_RANGE_MAP = {
    "Before 1950": (1900, 1949), "1950-1980": (1950, 1980), "1980-2000": (1980, 2000),
    "2000-2010": (2000, 2010), "2010–2020": (2010, 2020), "2020-2024": (2020, 2024)
}


# --- TMDB SEARCH FUNCTION ---
def search_tmdb_movies(answers):
    genre_ids = [str(GENRE_MAP[g]) for g in answers['genre']]
    language_codes = [LANGUAGE_MAP[lang] for lang in answers['language'] if lang != "No preference"]
    selected_range = YEAR_RANGE_MAP.get(answers['release_year'], None)
    min_year, max_year = selected_range if selected_range else (None, None)

    duration_map = {
        "Less than 90 minutes": (0, 89),
        "Around 90–120 minutes": (0, 120),
        "More than 2 hours": (120, 400)
    }
    runtime_range = duration_map.get(answers['duration'], (0, 400))

    results = []
    for page in range(1, 3):
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=en-US&sort_by=popularity.desc&page={page}"
        if genre_ids:
            url += f"&with_genres={','.join(genre_ids)}"
        if language_codes:
            url += f"&with_original_language={language_codes[0]}"
        if min_year:
            url += f"&primary_release_date.gte={min_year}-01-01"
        if max_year:
            url += f"&primary_release_date.lte={max_year}-12-31"
        url += f"&with_runtime.gte={runtime_range[0]}&with_runtime.lte={runtime_range[1]}"

        response = requests.get(url)
        data = response.json()
        filtered = [movie for movie in data.get("results", []) if all(int(gid) in movie.get("genre_ids", []) for gid in map(int, genre_ids))]
        results.extend(filtered)

    return results


# --- OPENAI GPT RECOMMENDATION ---
def select_movies_with_openai(movies, prefs):
    prompt = f"""Given the list of movies and the user's preferences, rank the 5 movies that best fit the user's mood, company, with kids, tone, popularity, real or fiction, discussion, and soundtrack preferences.

User's Preferences:
Mood: {prefs['mood']}
Company: {prefs['company']}
With Kids: {prefs['with_kids']}
Tone: {prefs['tone']}
Popularity: {prefs['popularity']}
Real or Fiction: {prefs['real_or_fiction']}
Discussion: {prefs['discussion']}
Soundtrack: {prefs['soundtrack']}

Movies List:"""

    for movie in movies:
        title = movie.get('title', 'Unknown Title')
        year = movie.get('release_date', 'N/A')[:4]
        language = movie.get('original_language', 'N/A')
        genres = ', '.join([str(genre) for genre in movie.get('genre_ids', [])])
        prompt += f"\n- {title} ({year}) | Language: {language} | Genres: {genres}"

    prompt += "\n\nNow, rank the 5 most suitable movies from this list. Return only the titles."

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.5
    )

    selected = response.choices[0].message.content.strip().split('\n')
    return [re.sub(r"^[\d\-\.\*\s]+", "", m).strip() for m in selected][:5]


# --- STREAMLIT UI ---
st.title("🎬 AI Movie Recommender")

with st.form("preferences_form"):
    duration = st.selectbox("⏱️ How much time do you have?", ["Less than 90 minutes", "Around 90–120 minutes", "More than 2 hours"])
    language = st.multiselect("🌐 Preferred language(s)", list(LANGUAGE_MAP.keys()) + ["No preference"])
    genre = st.multiselect("🎞️ Choose genre(s)", list(GENRE_MAP.keys()))
    release_year = st.selectbox("📅 Release year preference", list(YEAR_RANGE_MAP.keys()) + ["No preference"])
    mood = st.multiselect("😊 Your mood", ["Happy", "Sad", "Romantic", "Adventurous", "Tense / Anxious", "I don't really know"])
    company = st.selectbox("👥 Watching with", ["Alone", "Friends", "Family", "Date", "Other"])
    with_kids = st.selectbox("👶 Are kids watching too?", ["Yes", "No"])
    tone = st.selectbox("🧠 Movie tone", ["Emotionally deep", "Easygoing"])
    popularity = st.selectbox("🔥 Popularity", ["I prefer well known", "Under the radar", "No preference"])
    real_or_fiction = st.selectbox("📖 Story type", ["Real events", "Fictional Narratives", "No preference"])
    discussion = st.selectbox("💬 Want something to talk about?", ["Yes", "No", "No preference"])
    soundtrack = st.selectbox("🎵 Want a strong soundtrack?", ["Yes", "No", "No preference"])

    submitted = st.form_submit_button("🎥 Recommend Movies")

if submitted:
    if not genre:
        st.warning("Please select at least one genre.")
    else:
        answers = {
            "duration": duration, "language": language, "genre": genre, "release_year": release_year,
            "mood": mood, "company": company, "with_kids": with_kids, "tone": tone,
            "popularity": popularity, "real_or_fiction": real_or_fiction,
            "discussion": discussion, "soundtrack": soundtrack
        }

        with st.spinner("🔎 Finding the best matches..."):
            tmdb_results = search_tmdb_movies(answers)

        if not tmdb_results:
            st.error("❌ No movies found. Try different filters.")
        else:
            selected = select_movies_with_openai(tmdb_results, answers)
            if selected:
                st.subheader("🎯 Top 5 Movies For You")
                shown_titles = set()
                for title in selected:
                    clean_title = re.sub(r"\s*\(\d{4}\)$", "", title).strip()
                    match = difflib.get_close_matches(
