import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import pytz

# =========================
# CONFIG
# =========================
st.set_page_config("SIMRS Operan", "🏥", layout="wide")

st.title("🏥 SIMRS Operan Shift")

jakarta = pytz.timezone("Asia/Jakarta")

# =========================
# DB
# =========================
@st.cache_resource
def conn_db():
    conn = sqlite3.connect("operan.db", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

conn = conn_db()
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS operan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal TEXT,
    unit TEXT,
    shift TEXT,
    no_rm TEXT,
    nama_pasien TEXT,
    kamar TEXT,
    diagnosa TEXT,
    operan TEXT,
    pj_operan TEXT
)
""")
conn.commit()

# =========================
# SESSION PAGE
# =========================
if "page" not in st.session_state:
    st.session_state["page"] = "dashboard"

# =========================
# AUTO SHIFT
# =========================
jam = datetime.now(jakarta).hour

auto_shift = (
    "Pagi" if jam < 14 else
    "Sore" if jam < 21 else
    "Malam"
)

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=10)
def load(unit):
    return pd.read_sql_query("""
        SELECT * FROM operan
        WHERE unit = ?
        ORDER BY id DESC
        LIMIT 100
    """, conn, params=(unit,))

# =========================
# PAGE: DASHBOARD
# =========================
if st.session_state["page"] == "dashboard":

    unit = st.selectbox("Unit", [
        "ICU","RPU LT 1","RPU LT 2","RPU LT 3 GL","RPU LT 3 GB",
        "RPU LT 4","RPU LT 5","HD","OK","IGD","NICU","PICU"
    ])

    df = load(unit)

    st.subheader("📋 Pasien")

    for _, r in df.iterrows():

        col1, col2, col3, col4 = st.columns([2,2,2,1])

        with col1:
            st.write(r["no_rm"])
        with col2:
            st.write(r["nama_pasien"])
        with col3:
            st.write(r["kamar"])

        with col4:
            if st.button("Open", key=r["id"]):

                st.session_state["selected"] = r.to_dict()
                st.session_state["page"] = "detail"
                st.rerun()

# =========================
# PAGE: DETAIL PASIEN
# =========================
elif st.session_state["page"] == "detail":

    data = st.session_state["selected"]

    st.button("⬅ Kembali", on_click=lambda: st.session_state.update({"page":"dashboard"}))

    st.subheader(f"👤 {data['nama_pasien']}")

    st.write("🆔 RM:", data["no_rm"])
    st.write("🏠 Kamar:", data["kamar"])
    st.write("🩺 Diagnosa:", data["diagnosa"])
    st.write("⏱ Shift:", data["shift"])

    st.divider()

    st.subheader("📄 Operan")
    st.info(data["operan"])

    st.divider()

    if st.button("✏ Edit"):

        st.session_state["edit"] = True

# =========================
# EDIT MODE
# =========================
    if st.session_state.get("edit"):

        new_op = st.text_area("Edit Operan", data["operan"])

        if st.button("Simpan Update"):

            c.execute("""
                UPDATE operan
                SET operan = ?
                WHERE id = ?
            """, (new_op, data["id"]))

            conn.commit()

            st.success("Updated")

            st.session_state["page"] = "dashboard"
            st.session_state["edit"] = False

            st.rerun()

# =========================
# INPUT PAGE (optional simple)
# =========================
st.sidebar.divider()

if st.sidebar.button("➕ Input Operan"):

    st.session_state["page"] = "input"
    st.rerun()
