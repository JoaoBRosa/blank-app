 
Conversas
67% de 15 GB usados
Termos de Utilização · Privacidade · Políticas de programa
Última atividade da conta: há 0 minutos
Esta conta está aberta noutro local · Detalhes
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
    "Mystery / Crime 🕵️": "mystery",
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
    "English": "eng",
    "Portuguese": "por",
    "Spanish": "spa",
    "French": "fre",
    "German": "ger",
    "Italian": "ita"
}

YEAR_RANGES = {
    "Timeless (before 1950)": (None, 1949),
    "Old but gold (1950–1980)": (1950, 1980),
    "90s & 00s nostalgia (1980–2000)": (1980, 2000),
    "Pretty modern (2000–2010)": (2000, 2010),
    "Recent (2010–2020)": (2010, 2020),
    "Very recent (after 2020)": (2021, None),
    "Surprise me! (no preference)": (None, None),
}

LENGTH_RANGES = {
    "Snack size (< 200 pages)": (0, 199),
    "Normal meal (200–400 pages)": (200, 400),
    "Feast (400+ pages)": (401, None),
    "Whatever, I don't mind": (None, None),
}

MOOD_EXTRA_SUBJECTS = {
    "Cute & cozy ☕️": ["cozy", "friendship"],
    "Dark & twisty 🌑": ["dark", "psychological"],
    "I want to laugh 😂": ["humor"],
    "Soft & romantic 💌": ["love_stories"],
    "Epic adventure 🗺️": ["adventure"],
    "Scare me 👀": ["horror"],
    "Make me think 🤔": ["philosophy"],
}

# =========================
#  Helper functions
# =========================

def build_search_tags(prefs: Dict[str, Any]) -> Dict[str, Any]:
    subjects = [GENRE_TO_SUBJECT[g] for g in prefs["genres"]]

    if prefs["with_kids"] == "Yes":
        subjects.append("children")

    extra_subjects = []
    for m in prefs["mood"]:
        extra_subjects.extend(MOOD_EXTRA_SUBJECTS.get(m, []))

    lang_code = None
    if prefs["language"] != "No preference":
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


def fetch_openlibrary_books(tags: Dict[str, Any]):
    all_docs = {}

    def do_query(subject: Optional[str]):
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

    for s in tags["main_subjects"]:
        do_query(s)

    do_query(None)

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
        if year >= 2015:
            s += 5
        elif year >= 2000:
            s += 3
    return s


def pick_book(docs, prev=None):
    if not docs:
        return None

    pool = [d for d in docs if d.get("key") != prev] or docs
    pool = sorted(pool, key=score, reverse=True)
    top = pool[:10] if len(pool) > 10 else pool
    return random.choice(top)


def format_book(d):
    title = d.get("title", "Unknown title")
    authors = ", ".join(d.get("author_name", [])) or "Unknown author"
    year = d.get("first_publish_year", "Unknown year")
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
#  Streamlit UI
# =========================

st.title("📚 Bookify")

st.write(
    """
    Welcome to **Bookify** — *where every reader finds their perfect match!*  
    Take our fun quiz and let us pair you with a book that feels just right.  
    Ready to meet your next favorite story? 
    """
)

if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "current_book" not in st.session_state:
    st.session_state.current_book = None

with st.form("quiz"):
    st.subheader("1️⃣ Pick your genres")
    genres = st.multiselect(
        "Choose 1–3 genres:",
        list(GENRE_TO_SUBJECT.keys()),
        default=["Classics 🏛️"]
    )

    st.subheader("2️⃣ What vibe are you going for?")
    mood = st.multiselect("Choose the vibe:", list(MOOD_EXTRA_SUBJECTS.keys()))

    st.subheader("3️⃣ Book size & era")
    length = st.radio("How long should it be?", list(LENGTH_RANGES.keys()))
    year_range = st.selectbox("Book era:", list(YEAR_RANGES.keys()))

    st.subheader("4️⃣ Language & audience")
    language = st.selectbox("Language:", list(LANGUAGE_TO_CODE.keys()) + ["No preference"])
    audience = st.selectbox("Who is this book for?", ["Just me", "Me & kids", "Book club", "School", "Gift"])
    with_kids = "Yes" if audience == "Me & kids" else "No"

    submitted = st.form_submit_button("✨ Find my book!")

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

    with st.spinner("Searching Open Library…"):
        docs = fetch_openlibrary_books(tags)
        docs = filter_books(docs, tags, prefs)

    st.session_state.search_results = docs

    if docs:
        chosen = pick_book(docs)
        st.session_state.current_book = format_book(chosen)
    else:
        st.session_state.current_book = None
        st.error("No books matched. Try adjusting your answers!")

book = st.session_state.current_book

if book:
    st.markdown("## 💘 Your book match")

    col1, col2 = st.columns([1, 2])

    with col1:
        if book["cover"]:
            st.image(book["cover"], use_container_width=True)
        else:
            st.write("No cover available 😢")

    with col2:
        st.markdown(f"### {book['title']}")
        st.write(f"**Author(s):** {book['authors']}")
        st.write(f"**First published:** {book['year']}")
        if book["pages"]:
            st.write(f"**Length:** {book['pages']} pages")
        if book["url"]:
            st.markdown(f"[📖 View on Open Library]({book['url']})")

    if st.button("🔁 Show me another option"):
        prev = book["raw"].get("key")
        new = pick_book(st.session_state.search_results, prev=prev)
        st.session_state.current_book = format_book(new)

elif submitted:
    st.info("Try relaxing one or two answers and search again 🙂")
