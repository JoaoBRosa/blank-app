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

# --- Session State Initialization ---
if 'answers' not in st.session_state:
    st.session_state.answers = {}
if 'tmdb_results' not in st.session_state:
    st.session_state.tmdb_results = []
if 'selected_movies' not in st.session_state:
    st.session_state.selected_movies = []

# --- OpenAI movie selection based on preferences ---
def select_movies_with_openai(movies, user_preferences):
    prompt = f"""Given the list of movies and the user's preferences, choose 5 movies that best fit the user's mood, company, with kids, tone, popularity, real or fiction, discussion, and soundtrack preferences.

User's Preferences:
Mood: {user_preferences['mood']}
Company: {user_preferences['company']}
With Kids: {user_preferences['with_kids']}
Tone: {user_preferences['tone']}
Popularity: {user_preferences['popularity']}
Real or Fiction: {user_preferences['real_or_fiction']}
Discussion: {user_preferences['discussion']}
Soundtrack: {user_preferences['soundtrack']}

Movies List:"""

    for movie in movies:
        title = movie.get('title', 'Unknown Title')
        year = movie.get('release_date', 'N/A')[:4]
        language = movie.get('original_language', 'N/A')
        genres = ', '.join([str(genre) for genre in movie.get('genre_ids', [])])
        prompt += f"\n- {title} ({year}) | Language: {language} | Genres: {genres}"

    prompt += "\n\nNow, select 5 movies from this list that best match the user's preferences. Return only the titles."

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.5
        )
        raw_output = response.choices[0].message.content.strip().split("\n")
        selected = [m.strip("\u2022-1234567890. ").strip() for m in raw_output if m.strip()]
        return selected[:5]
    except Exception as e:
        st.error(f"❌ OpenAI API error: {e}")
        return []

# --- Streamlit UI ---
st.title("🎬 AI Movie Recommender")

with st.form("preferences_form"):
    st.subheader("1. Basic Questions")

    duration = st.radio("1.1 How much time do you have to watch a movie right now?", [
        "Less than 90 minutes", "Around 90–120 minutes", "More than 2 hours"])

    language = st.multiselect("1.2 Preferred language(s):", [
        "English", "French", "Spanish", "Korean", "Italian", "Portuguese", "No preference"])

    genre = st.multiselect("1.3 What type of movie are you in the mood for? (Choose at least one)", [
        "Action", "Comedy", "Drama", "Sci-Fi", "Romance", "Thriller", "Horror",
        "Animation", "Documentary", "Fantasy"])

    release_year = st.selectbox("1.5 Do you have a preference for the release year?", [
        "Before 1950", "1950-1980", "1980-2000", "2000-2010", "2010–2020", "2020-2024", "No preference"])

    submitted = st.form_submit_button("Next")

if submitted:
    if not genre:
        st.warning("⚠️ You must choose at least one genre to continue.")
    else:
        st.session_state.answers['duration'] = duration
        st.session_state.answers['language'] = language
        st.session_state.answers['genre'] = genre
        st.session_state.answers['release_year'] = release_year
        st.success("✅ Preferences collected. Continue to the next section.")

with st.form("mood_preferences"):
    st.subheader("2. Mood & Company")

    mood = st.multiselect("2.1 How are you feeling right now?", [
        "Happy", "Sad", "Romantic", "Adventurous", "Tense / Anxious", "I don't really know"])

    company = st.selectbox("2.2 Who are you watching with today?", [
        "Alone", "Friends", "Family", "Date", "Other"])

    with_kids = st.radio("2.3 Are you watching this film with kids?", ["Yes", "No"])

    tone = st.radio("2.4 Are you in the mood for something emotionally deep or something easygoing?", [
        "Emotionally deep", "Easygoing"])

    st.subheader("3. Popularity & Preferences")

    popularity = st.radio("2.5 Would you prefer a widely known movie or something more under the radar?", [
        "I prefer well known", "Under the radar", "No preference"])

    real_or_fiction = st.radio("2.6 Do you lean toward stories inspired by real events or fictional narratives?", [
        "Real events", "Fictional Narratives", "No preference"])

    discussion = st.radio("2.7 Would you like a movie that sparks conversation afterward?", [
        "Yes", "No", "No preference"])

    soundtrack = st.radio("2.8 Would you like a movie with a standout soundtrack or musical element?", [
        "Yes", "No", "No preference"])

    submitted_2 = st.form_submit_button("Save Preferences")

if submitted_2:
    st.session_state.answers["mood"] = mood
    st.session_state.answers["company"] = company
    st.session_state.answers["with_kids"] = with_kids
    st.session_state.answers["tone"] = tone
    st.session_state.answers["popularity"] = popularity
    st.session_state.answers["real_or_fiction"] = real_or_fiction
    st.session_state.answers["discussion"] = discussion
    st.session_state.answers["soundtrack"] = soundtrack
    st.success("✅ Mood and preferences saved.")

# --- TMDb Search ---
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

    genre_ids = [str(genre_map[g]) for g in answers['genre'] if g in genre_map]
    language_codes = [language_map[lang] for lang in answers['language'] if lang != "No preference" and lang in language_map]
    selected_range = year_range_map.get(answers['release_year'], None)
    min_year, max_year = selected_range if selected_range else (None, None)

    duration_pref = answers['duration']
    if duration_pref == "Less than 90 minutes":
        with_runtime = (0, 89)
    elif duration_pref == "Around 90–120 minutes":
        with_runtime = (0, 120)
    elif duration_pref == "More than 2 hours":
        with_runtime = (120, 400)
    else:
        with_runtime = (0, 400)

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
        url += f"&with_runtime.gte={with_runtime[0]}&with_runtime.lte={with_runtime[1]}"

        response = requests.get(url)
        data = response.json()
        filtered = [movie for movie in data.get("results", []) if all(int(gid) in movie.get("genre_ids", []) for gid in map(int, genre_ids))]
        results.extend(filtered)

    return results

# --- Run TMDb Search ---
if st.session_state.answers and st.button("🎥 Find Movies"):
    with st.spinner("Fetching movies..."):
        st.session_state.tmdb_results = search_tmdb_movies(st.session_state.answers)

    if st.session_state.tmdb_results:
        st.success(f"✅ Found {len(st.session_state.tmdb_results)} movie(s).")
        for movie in st.session_state.tmdb_results[:5]:
            st.markdown(f"**{movie['title']}** ({movie.get('release_date', 'N/A')[:4]})")
    else:
        st.error("❌ No movies found with your preferences.")

# --- Recommend with OpenAI ---
if st.session_state.tmdb_results and st.button("🤖 Recommend Top 5 with AI"):
    with st.spinner("Asking OpenAI..."):
        st.session_state.selected_movies = select_movies_with_openai(st.session_state.tmdb_results, st.session_state.answers)

    if st.session_state.selected_movies:
        st.markdown("### 🌟 AI-Recommended Top 5:")
        for title in st.session_state.selected_movies:
            st.markdown(f"- **{title}**")
    else:
        st.error("❌ GPT did not return recommendations.")

# --- Display AI-recommended Movies with Descriptions and Posters ---
if 'tmdb_results' in locals() and tmdb_results and 'selected_movies' in locals() and selected_movies:
    st.markdown("## 🌟 AI-Recommended Top 5:")

    shown_titles = set()
    tmdb_titles = [movie['title'] for movie in tmdb_results]

    for title in selected_movies:
        clean_title = re.sub(r"\s*\(\d{4}\)$", "", title).strip()
        match = difflib.get_close_matches(clean_title, tmdb_titles, n=1, cutoff=0.8)
        movie_data = next((m for m in tmdb_results if m['title'] == match[0]), None) if match else None

        if movie_data and movie_data['title'] not in shown_titles:
            shown_titles.add(movie_data['title'])

            title = movie_data['title']
            year = movie_data.get('release_date', 'N/A')[:4]
            overview = movie_data.get('overview', 'No description available.')
            poster_path = movie_data.get('poster_path')

            st.markdown(f"### 🎬 {title} ({year})")
            if poster_path:
                st.image(f"https://image.tmdb.org/t/p/w500{poster_path}", width=300)
            st.write(overview)
            st.markdown("---")

