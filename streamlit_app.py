import streamlit as st
import requests
import random
from typing import Dict, Any, Optional
import qrcode
from io import BytesIO

# =========================
#  Config
# =========================

OPENLIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
COVERS_BASE_URL = "https://covers.openlibrary.org/b/id/"

# =========================
#  Mappings (questions → tags)
# =========================

GENRE_TO_SUBJECT = {
    "Classics": "classics",
    "Fantasy": "fantasy",
    "Science Fiction": "science_fiction",
    "Romance": "romance",
    "Mystery / Crime": "mystery",
    "Thriller": "thriller",
    "Horror": "horror",
    "Historical": "historical_fiction",
    "Non-fiction": "nonfiction",
    "Young Adult": "young_adult",
    "Children": "children",
    "Poetry": "poetry",
    "Comics / Manga": "comics",
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
    "Before 1950": (None, 1949),
    "1950–1980": (1950, 1980),
    "1980–2000": (1980, 2000),
    "2000–2010": (2000, 2010),
    "2010–2020": (2010, 2020),
    "After 2020": (2021, None),
    "No preference": (None, None),
}

LENGTH_RANGES = {
    "< 200 pages": (0, 199),
    "200–400 pages": (200, 400),
    "> 400 pages": (401, None),
    "No preference": (None, None),
}

MOOD_EXTRA_SUBJECTS = {
    "Cozy": ["cozy", "friendship"],
    "Dark": ["dark", "psychological"],
    "Funny": ["humor"],
    "Romantic": ["love_stories"],
    "Adventure": ["adventure"],
    "Scary": ["horror"],
    "Thought-provoking": ["philosophy"],
}

# =========================
#  QR Code Generator
# =========================

def generate_qr(text: str):
    qr = qrcode.QRCode(
        version=1,
        box_size=8,
        border=4
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

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

st.title("📘 Bookify Reimagined")
st.write("Find the perfect book based on your mood and preferences.")

st.divider()

if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "current_book" not in st.session_state:
    st.session_state.current_book = None

with st.form("quiz"):
    st.subheader("① Genres")
    genres = st.multiselect(
        "Choose up to 3 genres:",
        list(GENRE_TO_SUBJECT.keys()),
        default=["Classics"]
    )

    st.subheader("② Mood")
    mood = st.multiselect("What vibe do you want?", list(MOOD_EXTRA_SUBJECTS.keys()))

    st.subheader("③ Book Specs")
    length = st.radio("Length:", list(LENGTH_RANGES.keys()))
    year_range = st.selectbox("Era:", list(YEAR_RANGES.keys()))

    st.subheader("④ Language & Audience")
    language = st.selectbox("Language:", list(LANGUAGE_TO_CODE.keys()) + ["No preference"])
    audience = st.selectbox("Who is it for?", ["Just me", "Me & kids", "Book club", "School", "Gift"])
    with_kids = "Yes" if audience == "Me & kids" else "No"

    submitted = st.form_submit_button("🔍 Find my book")

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

    with st.spinner("Searching Open Library..."):
        docs = fetch_openlibrary_books(tags)
        docs = filter_books(docs, tags, prefs)

    st.session_state.search_results = docs

    if docs:
        chosen = pick_book(docs)
        st.session_state.current_book = format_book(chosen)
    else:
        st.session_state.current_book = None
        st.error("No matching books found. Try adjusting your answers!")

book = st.session_state.current_book

if book:
    st.subheader("📖 Your Book Match")

    col1, col2 = st.columns([1, 2])

    with col1:
        if book["cover"]:
            st.image(book["cover"], use_container_width=True)
        else:
            st.write("No cover available.")

    with col2:
        st.markdown(f"### {book['title']}")
        st.write(f"**Author:** {book['authors']}")
        st.write(f"**Published:** {book['year']}")
        if book["pages"]:
            st.write(f"**Pages:** {book['pages']}")
        if book["url"]:
            st.markdown(f"[Open Library Page]({book['url']})")

    # QR Code Section
    st.subheader("📱 Save or Share")
    qr_text = f"""
Title: {book['title']}
Author: {book['authors']}
Year: {book['year']}
Link: {book['url']}
"""

    qr_img = generate_qr(qr_text)
    st.image(qr_img, caption="Scan to save this book!", width=200)

    if st.button("🔁 Show me another option"):
        prev = book["raw"].get("key")
        new = pick_book(st.session_state.search_results, prev=prev)
        st.session_state.current_book = format_book(new)

elif submitted:
    st.info("Try relaxing some filters and try again.")
