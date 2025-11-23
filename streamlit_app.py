import streamlit as st
import requests
import random

# =========================
#  Config
# =========================

OPENLIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
COVERS_BASE_URL = "https://covers.openlibrary.org/b/id/"

# =========================
#  Mappings
# =========================

GENRE_TO_SUBJECT = {
    "Classics 🏛️": "classics",
    "Fantasy 🐉": "fantasy",
    "Science Fiction 🚀": "science_fiction",
    "Romance ❤️": "romance",
    "Mystery / Crime 🕵️‍♂️": "mystery",
    "Thriller 😱": "thriller",
    "Horror 👻": "horror",
    "Historical 📜": "historical_fiction",
    "Non-fiction 📚": "nonfiction",
    "Young Adult ✨": "young_adult",
    "Children 👧🧒": "children",
    "Poetry ✒️": "poetry",
    "Comics / Manga 💥": "comics",
}

LANGUAGE_TO_CODE = {
    "English 🇬🇧": "eng",
    "Portuguese 🇵🇹": "por",
    "Spanish 🇪🇸": "spa",
    "French 🇫🇷": "fre",
    "German 🇩🇪": "ger",
    "Italian 🇮🇹": "ita",
    "No preference 🤷": None
}

YEAR_RANGES = {
    "📜 Before 1950": (None, 1949),
    "🎞️ 1950–1980": (1950, 1980),
    "💾 1980–2000": (1980, 2000),
    "📘 2000–2010": (2000, 2010),
    "📗 2010–2020": (2010, 2020),
    "🆕 After 2020": (2021, None),
    "🎲 No preference": (None, None),
}

LENGTH_RANGES = {
    "📄 < 200 pages": (0, 199),
    "📘 200–400 pages": (200, 400),
    "📚 > 400 pages": (401, None),
    "🤷 Any length": (None, None),
}

MOOD_EXTRA_SUBJECTS = {
    "Cozy ☕️": ["cozy", "friendship"],
    "Dark 🌑": ["dark", "psychological"],
    "Funny 😂": ["humor"],
    "Romantic 💌": ["love_stories"],
    "Adventure 🗺️": ["adventure"],
    "Scary 👀": ["horror"],
    "Thought-provoking 🤔": ["philosophy"],
}

# =========================
#  Fetch summary + ratings
# =========================

def fetch_work_details(key: str):
    base = "https://openlibrary.org"

    description = None
    rating_avg = None
    rating_count = None

    # Summary
    r = requests.get(f"{base}{key}.json")
    if r.ok:
        data = r.json()
        d = data.get("description")
        if isinstance(d, dict):
            description = d.get("value")
        elif isinstance(d, str):
            description = d

    # Ratings
    r2 = requests.get(f"{base}{key}/ratings.json")
    if r2.ok:
        summary = r2.json().get("summary", {})
        rating_avg = summary.get("average")
        rating_count = summary.get("count")

    return description, rating_avg, rating_count

# =========================
#  Core Logic
# =========================

def build_tags(prefs):
    return {
        "subjects": [GENRE_TO_SUBJECT[g] for g in prefs["genres"]],
        "extra": sum((MOOD_EXTRA_SUBJECTS[m] for m in prefs["mood"]), []),
        "lang": LANGUAGE_TO_CODE[prefs["language"]],
        "year": YEAR_RANGES[prefs["year_range"]],
        "length": LENGTH_RANGES[prefs["length"]],
        "kids": prefs["kids"],
    }

def fetch_books(tags):
    docs = {}

    def query(subject):
        params = {"limit": 50}
        if subject:
            params["subject"] = subject
        else:
            params["q"] = "books"

        if tags["lang"]:
            params["language"] = tags["lang"]

        r = requests.get(OPENLIBRARY_SEARCH_URL, params=params)
        if not r.ok:
            return

        for d in r.json().get("docs", []):
            if d.get("key"):
                docs[d["key"]] = d

    # Main genres
    for s in tags["subjects"]:
        query(s)

    # General search
    query(None)

    # Mood categories
    for s in tags["extra"]:
        query(s)

    return list(docs.values())

def passes_range(v, a, b):
    if v is None:
        return True
    if a is not None and v < a:
        return False
    if b is not None and v > b:
        return False
    return True

def filter_books(docs, tags):
    ya, yb = tags["year"]
    pa, pb = tags["length"]

    out = []
    for d in docs:
        if not passes_range(d.get("first_publish_year"), ya, yb):
            continue
        if not passes_range(d.get("number_of_pages_median"), pa, pb):
            continue
        out.append(d)

    return out

# FIX: TRUE RANDOM SELECTION
def pick_random(docs, prev_key=None):
    if not docs:
        return None
    pool = [d for d in docs if d.get("key") != prev_key] or docs
    return random.choice(pool)

def format_book(d):
    return {
        "title": d.get("title", "Unknown Title"),
        "authors": ", ".join(d.get("author_name", []) or []),
        "year": d.get("first_publish_year", "Unknown Year"),
        "pages": d.get("number_of_pages_median"),
        "cover": f"{COVERS_BASE_URL}{d.get('cover_i')}-L.jpg" if d.get("cover_i") else None,
        "key": d.get("key"),
        "url": "https://openlibrary.org" + d.get("key"),
    }

# =========================
#  UI
# =========================

st.title("📚💘 Bookify – Swipe Your Next Read!")

# Initialize session state
if "results" not in st.session_state:
    st.session_state.results = []

if "book" not in st.session_state:
    st.session_state.book = None

if "likes" not in st.session_state:
    st.session_state.likes = []

# Sidebar - Liked books
st.sidebar.header("❤️ Your Liked Books")
if st.session_state.likes:
    for b in st.session_state.likes:
        st.sidebar.markdown(
            f"**{b['title']}**<br>"
            f"{b['authors']}<br>"
            f"<a href='{b['url']}' target='_blank'>Open Library</a>",
            unsafe_allow_html=True
        )
        st.sidebar.write("---")
else:
    st.sidebar.write("No liked books yet.")

# =========================
# Quiz
# =========================

with st.form("quiz"):
    st.subheader("1️⃣ Genres")
    genres = st.multiselect("Pick genres:", list(GENRE_TO_SUBJECT.keys()), ["Classics 🏛️"])

    st.subheader("2️⃣ Mood")
    mood = st.multiselect("Pick mood:", list(MOOD_EXTRA_SUBJECTS.keys()))

    st.subheader("3️⃣ Book Specs")
    length = st.radio("Length:", list(LENGTH_RANGES.keys()))
    year = st.selectbox("Era:", list(YEAR_RANGES.keys()))

    st.subheader("4️⃣ Language & Audience")
    lang = st.selectbox("Language:", list(LANGUAGE_TO_CODE.keys()))
    audience = st.selectbox("Who's reading?", ["Just me", "Me & kids"])
    kids = "Yes" if audience == "Me & kids" else "No"

    go = st.form_submit_button("✨ Find Books")

# =========================
# Fetch results
# =========================

if go:
    prefs = {
        "genres": genres,
        "mood": mood,
        "length": length,
        "year_range": year,
        "language": lang,
        "kids": kids,
    }

    tags = build_tags(prefs)

    with st.spinner("🔎 Searching for books…"):
        docs = fetch_books(tags)
        docs = filter_books(docs, tags)

    if docs:
        st.session_state.results = docs
        st.session_state.book = format_book(pick_random(docs))
    else:
        st.error("No books found. Try adjusting filters!")

# =========================
# Show result + Swipe
# =========================

book = st.session_state.book

if book:
    st.subheader("📖 Your Match")

    col1, col2 = st.columns([1, 2])

    with col1:
        if book["cover"]:
            st.image(book["cover"])
        else:
            st.write("📕 No cover available.")

    with col2:
        st.markdown(f"### {book['title']} 📘")
        st.write(f"**Author:** {book['authors']}")
        st.write(f"**Year:** {book['year']}")
        st.write(f"[🔗 View on Open Library]({book['url']})")

    # Summary & Rating
    desc, avg, count = fetch_work_details(book["key"])

    st.subheader("📝 Summary")
    st.write(desc or "No summary available.")

    st.subheader("⭐ Ratings")
    if avg:
        st.write(f"**{avg:.1f} ⭐** ({count} reviews)")
    else:
        st.write("No rating data available.")

    # Swipe buttons
    st.write("---")
    st.markdown("### ❤️ Swipe")

    c1, c2 = st.columns(2)

    if c1.button("❤️ Like"):
        st.session_state.likes.append(book)
        st.session_state.book = format_book(pick_random(st.session_state.results, book["key"]))
        st.rerun()

    if c2.button("❌ Skip"):
        st.session_state.book = format_book(pick_random(st.session_state.results, book["key"]))
        st.rerun()

elif go:
    st.info("Try relaxing filters.")
