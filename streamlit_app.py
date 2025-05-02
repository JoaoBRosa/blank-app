import streamlit as st
import requests
import difflib
import re
from openai import OpenAI

# --- API KEYS ---
TMDB_API_KEY = st.secrets["api_keys"]["tmdb"]
OPENAI_API_KEY = st.secrets["api_keys"]["openai"]
client = OpenAI(api_key=OPENAI_API_KEY)

# --- AI Movie Selector with Repeat Avoidance ---
def select_single_movie_with_openai(movies, user_preferences, previous_title=None):
    prompt = f"""Given the list of movies and the user's preferences, choose ONE movie that best fits the user's mood, company, with kids, tone, popularity, real or fiction, discussion, and soundtrack preferences.

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
        genres = ', '.join([str(g) for g in movie.get('genre_ids', [])])
        prompt += f"\n- {title} ({year}) | Language: {language} | Genres: {genres}"

    if previous_title:
        prompt += f"\n\nPreviously recommended: {previous_title}. Please pick a different one if possible."

    prompt += "\n\nChoose ONE movie from this list that best matches the user's preferences. Return only the movie title."

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.9
        )
        movie = response.choices[0].message.content.strip()
        return re.sub(r"^[\d\-\*\.\s]+", "", movie)
    except Exception as e:
        st.error(f"❌ OpenAI API error: {e}")
        return None

# --- TMDB Movie Search ---
def search_tmdb_movies(answers):
    genre_map = {
        "Action": 28, "Comedy": 35, "Drama": 18, "Sci-Fi": 878, "Romance": 10749,
        "Thriller": 53, "Horror": 27, "Animation": 16, "Documentary": 99, "Fantasy": 14
    }
    language_map = {
        "English": "en", "French": "fr", "Spanish": "es", "Korean": "ko",
        "Italian": "it", "Portuguese": "pt"
    }
    year_map = {
        "Before 1950": (1900, 1949), "1950-1980": (1950, 1980), "1980-2000": (1980, 2000),
        "2000-2010": (2000, 2010), "2010–2020": (2010, 2020), "2020-2024": (2020, 2024)
    }

    genre_ids = [str(genre_map[g]) for g in answers['genre'] if g in genre_map]
    lang_code = [language_map[l] for l in answers['language'] if l != "No preference" and l in language_map]
    min_y, max_y = year_map.get(answers['release_year'], (None, None))

    duration = answers['duration']
    if duration == "Less than 90 minutes":
        runtime = (0, 89)
    elif duration == "Around 90–120 minutes":
        runtime = (0, 120)
    else:
        runtime = (90, 400)

    results = []
    for page in range(1, 4):
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&sort_by=popularity.desc&page={page}"
        if genre_ids:
            url += f"&with_genres={','.join(genre_ids)}"
        if lang_code:
            url += f"&with_original_language={lang_code[0]}"
        if min_y:
            url += f"&primary_release_date.gte={min_y}-01-01"
        if max_y:
            url += f"&primary_release_date.lte={max_y}-12-31"
        url += f"&with_runtime.gte={runtime[0]}&with_runtime.lte={runtime[1]}"

        response = requests.get(url)
        if response.ok:
            results += response.json().get("results", [])
    return results

# --- Streamlit UI ---
st.title("🎬 AI Movie Recommender")

if "tmdb_results" not in st.session_state:
    st.session_state.tmdb_results = []
if "recommended" not in st.session_state:
    st.session_state.recommended = None

with st.form("preferences_form"):
    st.subheader("1. Basic Questions")
    duration = st.radio("⏱️ How much time do you have?", ["Less than 90 minutes", "Around 90–120 minutes", "More than 2 hours"])
    language = st.multiselect("🌐 Preferred language(s)", ["English", "French", "Spanish", "Korean", "Italian", "Portuguese", "No preference"])
    genre = st.multiselect("🎞️ Genre(s)", ["Action", "Comedy", "Drama", "Sci-Fi", "Romance", "Thriller", "Horror", "Animation", "Documentary", "Fantasy"])
    release_year = st.selectbox("📅 Release year", ["Before 1950", "1950-1980", "1980-2000", "2000-2010", "2010–2020", "2020-2024", "No preference"])
    submit1 = st.form_submit_button("Next")

if submit1 and genre:
    st.session_state.answers = {
        "duration": duration,
        "language": language,
        "genre": genre,
        "release_year": release_year
    }

with st.form("details_form"):
    st.subheader("2. Mood & Preferences")
    mood = st.multiselect("Mood:", ["Happy", "Sad", "Romantic", "Adventurous", "Tense / Anxious", "I don't really know"])
    company = st.selectbox("Watching with:", ["Alone", "Friends", "Family", "Date", "Other"])
    with_kids = st.radio("Are kids watching?", ["Yes", "No"])
    tone = st.radio("Tone?", ["Emotionally deep", "Easygoing"])
    popularity = st.radio("Popularity", ["I prefer well known", "Under the radar", "No preference"])
    real_or_fiction = st.radio("Story Type", ["Real events", "Fictional Narratives", "No preference"])
    discussion = st.radio("Conversation-worthy?", ["Yes", "No", "No preference"])
    soundtrack = st.radio("Strong soundtrack?", ["Yes", "No", "No preference"])
    submit2 = st.form_submit_button("Find Movies")

if submit2:
    answers = st.session_state.answers
    answers.update({
        "mood": mood, "company": company, "with_kids": with_kids, "tone": tone,
        "popularity": popularity, "real_or_fiction": real_or_fiction,
        "discussion": discussion, "soundtrack": soundtrack
    })

    with st.spinner("🔍 Searching TMDb..."):
        st.session_state.tmdb_results = search_tmdb_movies(answers)

    if not st.session_state.tmdb_results:
        st.error("❌ No movies found.")
    else:
        st.success(f"✅ Found {len(st.session_state.tmdb_results)} movies.")
        st.session_state.recommended = select_single_movie_with_openai(
            st.session_state.tmdb_results,
            st.session_state.answers
        )

# --- AI Recommendation Display ---
if st.session_state.recommended:
    st.markdown("### 🌟 AI-Recommended Movie")
    match = difflib.get_close_matches(st.session_state.recommended, [m['title'] for m in st.session_state.tmdb_results], n=1, cutoff=0.7)
    movie_data = next((m for m in st.session_state.tmdb_results if m['title'] == match[0]), None) if match else None

    if movie_data:
        st.markdown(f"#### 🎬 {movie_data['title']} ({movie_data.get('release_date', 'N/A')[:4]})")
        if movie_data.get("poster_path"):
            st.image(f"https://image.tmdb.org/t/p/w500{movie_data['poster_path']}", width=300)
        st.write(movie_data.get("overview", "No synopsis available."))

        if st.button("🔄 Try Another"):
            st.session_state.recommended = select_single_movie_with_openai(
                st.session_state.tmdb_results,
                st.session_state.answers,
                previous_title=st.session_state.recommended
            )
