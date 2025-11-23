import streamlit as st
import requests
import random
from typing import Dict, Any, Optional

# =========================
#  Config
# =========================

OPENLIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
COVERS_BASE_URL = "https://covers.openlibrary.org/b/id/"

# =========================
#  Mappings (questions → tags)
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
#  Fetch work details (summary + ratings)
# =========================

def fetch_work_details(work_key: str):
    base = "https://openlibrary.org"

    # Work details
    work_data = {}
    r = requests.get(f"{base}{work_key}.json")
    if r.ok:
        work_data = r.json()

    # Ratings
    rating_data = {}
    r2 = requests.get(f"{base}{work_key}/ratings.json")
    if r2.ok:
        rating_data = r2.json().get("summary", {})

    # Summary
    description = None
    desc = work_data.get("description")
    if isinstance(desc, dict):
        description = desc.get("value")
    elif isinstance(desc, str):
        description = desc

    return {
        "description": description,
        "rating_avg": rating_data.get("average"),
        "rating_count": rating_data.get("count"),
    }

# =========================
#  Helper functions
# =========================

def build_search_tags(prefs: Dict[str, Any]):
    subjects = [GENRE_TO_SUBJECT[g] for g in prefs["genres"]]

    if prefs["with_kids"] == "Yes":
        subjects.append("children")

    extra_subjects = []
    for m in prefs["mood"]:
        extra_subjects.extend(MOOD_EXTRA_SUBJECTS.get(m, []))

    lang_code = LANGUAGE_TO_CODE.get(prefs["language"])

    year_range = YEAR_RANGES[prefs["year_range"]]
    length_range = LENGTH_RANGES[prefs["length"]]

    return {
        "main_subjects": subjects,
        "extra_subjects": extra_subjects,
        "language_code": lang_code,
        "year_range": year_range,
        "length_range": length_range,
    }


def fetch_openlibrary_books(tags):
    all_docs = {}

    def do_query(subject):
        params = {"limit": 50}

        if subject:
            params["subject"] = subject
        else:
            params["q"] = "books"

        if tags["language_code"]:
            params["language"] = tags["language_code"]

        r = requests.get(OPENLIBRARY_SEARCH_URL, params=params)
        if r.ok:
            for d in r.json().get("docs", []):
                key = d.get("key")
                if key and key not in all_docs:
                    all_docs[key] = d

    # Main subjects first
    for s in tags["main_subjects"]:
        do_query(s)

    # Fallback wide search
    do_query(None)

    # Extra mood subjects
    for s in tags["extra_subjects"]:
        do_query(s)

    return list(all_docs.values())


def passes_range(value, min_v, max_v):
    if value is None:
        return True
    if min_v is not None and value < min_v:
        return False
    if max_v is not None and value > max_v:
        return False
    return True


def filter_books(docs, tags, prefs):
    out = []
    year_min, year_max = tags["year_range"]
    pages_min, pages_max = tags["length_range"]

    for d in docs:
        year = d.get("first_publish_year")
        pages = d.get("number_of_pages_median")

        if not passes_range(year, year_min, year_max):
            continue
        if not passes_range(pages, pages_min, pages_max):
            continue

        out.append(d)
    return out


def score(doc):
    s = doc.get("edition_count", 0) * 2
    year = doc.get("first_publish_year")
    if year:
        if year >= 2015: s += 5
        elif year >= 2000: s += 3
    return s


def pick_book(docs, prev=None):
    pool = [d for d in docs if d.get("key") != prev] or docs
    pool = sorted(pool, key=score, reverse=True)
    top = pool[:10]
    return random.choice(top)


def format_book(d):
    title = d.get("title", "Unknown Title")
    authors = ", ".join(d.get("author_name", [])) or "Unknown Author"
    year = d.get("first_publish_year", "Unknown Year")
    pages = d.get("number_of_pages_median")
    cover = d.get("cover_i")
    cover_url = f"{COVERS_BASE_URL}{cover}-L.jpg" if cover else None
    url = f"https://openlibrary.org{d.get('key')}" if d.get("key") else None

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "pages": pages,
        "cover": cover_url,
        "url": url,
        "raw": d
    }

# =========================
#  UI
# =========================

st.title("📚✨ Bookify – Find Your Perfect Book Match")
st.write("Answer a few questions and let Bookify recommend your next read!")

st.divider()

if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "current_book" not in st.session_state:
    st.session_state.current_book = None

# ---------------------
# QUIZ
# ---------------------
with st.form("quiz"):
    st.subheader("1️⃣ Choose your genres")
    genres = st.multiselect(
        "Pick 1–3 genres:",
        list(GENRE_TO_SUBJECT.keys()),
        default=["Classics 🏛️"]
    )

    st.subheader("2️⃣ What's the vibe?")
    mood = st.multiselect("Choose your mood:", list(MOOD_EXTRA_SUBJECTS.keys()))

    st.subheader("3️⃣ Book details")
    length = st.radio("Length preference:", list(LENGTH_RANGES.keys()))
    year_range = st.selectbox("Preferred era:", list(YEAR_RANGES.keys()))

    st.subheader("4️⃣ Language & audience")
    language = st.selectbox("Language:", list(LANGUAGE_TO_CODE.keys()))
    audience = st.selectbox("Who's reading?", ["Just me", "Me & kids", "Book club", "School", "Gift"])
    with_kids = "Yes" if audience == "Me & kids" else "No"

    submitted = st.form_submit_button("✨ Find my book!")

# ---------------------
# PROCESSING
# ---------------------
if submitted:
    prefs = {
        "genres": genres,
        "mood": mood,
        "length": length,
        "year_range": year_range,
        "language": language,
        "with_kids": with_kids,
    }

    tags = build_search_tags(prefs)

    with st.spinner("🔎 Searching the library..."):
        docs = fetch_openlibrary_books(tags)
        docs = filter_books(docs, tags, prefs)

    st.session_state.search_results = docs

    if docs:
        st.session_state.current_book = format_book(pick_book(docs))
    else:
        st.session_state.current_book = None
        st.error("No books found. Try changing your preferences!")

# ---------------------
# RESULT
# ---------------------
book = st.session_state.current_book

if book:
    st.subheader("💘 Your Book Match")

    col1, col2 = st.columns([1, 2])

    with col1:
        if book["cover"]:
            st.image(book["cover"], use_container_width=True)
        else:
            st.write("📕 No cover available.")

    with col2:
        st.markdown(f"### {book['title']} 📖")
        st.write(f"**Author(s):** {book['authors']}")
        st.write(f"**Published:** {book['year']}")
        if book["pages"]:
            st.write(f"**Length:** {book['pages']} pages")
        if book["url"]:
            st.markdown(f"[🔗 View on Open Library]({book['url']})")

    # Work details: summary + ratings
    details = fetch_work_details(book["raw"].get("key"))

    st.subheader("📝 Summary")
    if details["description"]:
        st.write(details["description"])
    else:
        st.write("No summary available.")

    st.subheader("⭐ Ratings")
    if details["rating_avg"] is not None:
        st.write(f"**Average Rating:** {details['rating_avg']:.1f} ⭐")
        st.write(f"**Total Reviews:** {details['rating_count']}")
    else:
        st.write("No ratings available.")

    if st.button("🔁 Show another suggestion"):
        prev = book["raw"].get("key")
        new = pick_book(st.session_state.search_results, prev)
        st.session_state.current_book = format_book(new)

elif submitted:
    st.info("Try relaxing some filters to get more results 🙂")
