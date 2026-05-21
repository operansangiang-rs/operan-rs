import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime
import pytz

from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import landscape, A4

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Operan Shift RS Sari Asih Sangiang",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 Operan Shift RS Sari Asih Sangiang")

# =========================
# TIMEZONE
# =========================
jakarta = pytz.timezone("Asia/Jakarta")

# =========================
# DB CONNECTION
# =========================
@st.cache_resource
def get_conn():
    conn = sqlite3.connect("operan.db", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

conn = get_conn()
c = conn.cursor()

# =========================
# TABLE
# =========================
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
    pj_operan TEXT,
    edited_by TEXT,
    edited_at TEXT
)
""")
conn.commit()

# =========================
# AUTO SHIFT
# =========================
jam = datetime.now(jakarta).hour

if jam < 14:
    auto_shift = "Pagi"
elif jam < 21:
    auto_shift = "Sore"
else:
    auto_shift = "Malam"

# =========================
# RESET FORM STATE
# =========================
if "reset_form" not in st.session_state:
    st.session_state.reset_form = False

# =========================
# UNIT LIST
# =========================
unit_list = [
    "ICU","RPU LT 1","RPU LT 2","RPU LT 3 GL","RPU LT 3 GB",
    "RPU LT 4","RPU LT 5","Hemodialisa","Kamar Operasi",
    "IGD","NICU","PICU"
]

st.sidebar.title("🏥 Pilih Unit")
selected_unit = st.sidebar.selectbox("Unit", unit_list)

# =========================
# LOAD DATA (ANTI NAN FIX)
# =========================
@st.cache_data(ttl=10)
def load_data(unit):

    df = pd.read_sql_query("""
        SELECT
            id,
            tanggal,
            shift,
            no_rm,
            nama_pasien,
            kamar,
            diagnosa,
            operan,
            pj_operan,
            COALESCE(edited_by,'-') AS edited_by,
            COALESCE(edited_at,'-') AS edited_at
        FROM operan
        WHERE unit = ?
        ORDER BY id DESC
        LIMIT 100
    """, conn, params=(unit,))

    return df.fillna("-")

# =========================
# SEARCH
# =========================
st.subheader("🔎 Cari Pasien")

search = st.text_input("Cari No RM / Nama")

if len(search) >= 3:

    df_search = pd.read_sql_query("""
        SELECT *
        FROM operan
        WHERE no_rm LIKE ?
        OR nama_pasien LIKE ?
        ORDER BY id DESC
        LIMIT 50
    """, conn, params=(f"%{search}%", f"%{search}%"))

    st.dataframe(df_search, use_container_width=True, height=300)

st.divider()

# =========================
# INPUT FORM
# =========================
st.subheader(f"📝 Input Operan - {selected_unit}")

with st.form("form_operan"):

    col1, col2 = st.columns(2)

    with col1:

        tanggal = datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S")

        st.text_input("Tanggal", value=tanggal, disabled=True)
        st.text_input("Shift", value=auto_shift, disabled=True)

        shift = auto_shift

        no_rm = st.text_input(
            "No RM",
            value="" if st.session_state.reset_form else ""
        )

        nama_pasien = st.text_input(
            "Nama Pasien",
            value="" if st.session_state.reset_form else ""
        )

    with col2:

        kamar = st.text_input("Kamar")
        diagnosa = st.text_input("Diagnosa")

        pj_operan = st.text_input(
            "PJ Operan",
            value="" if st.session_state.reset_form else ""
        )

    operan = st.text_area(
        "Operan",
        height=130,
        max_chars=1500,
        value="" if st.session_state.reset_form else ""
    )

    submit = st.form_submit_button("Simpan")

# =========================
# SAVE DATA
# =========================
if submit:

    if no_rm and nama_pasien:

        c.execute("""
            INSERT INTO operan (
                tanggal, unit, shift,
                no_rm, nama_pasien,
                kamar, diagnosa,
                operan, pj_operan
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tanggal, selected_unit, shift,
            no_rm, nama_pasien,
            kamar, diagnosa,
            operan, pj_operan
        ))

        conn.commit()

        load_data.clear()

        st.session_state.reset_form = True

        st.success("Tersimpan")
        st.rerun()

# =========================
# LIST DATA (CARD VIEW CLEAN)
# =========================
st.subheader(f"📋 Data Operan - {selected_unit}")

df = load_data(selected_unit)

for _, row in df.iterrows():

    with st.container():

        st.markdown("---")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.write("📅", row["tanggal"])

        with col2:
            st.write("⏱", row["shift"])

        with col3:
            st.write("🆔", row["no_rm"])

        with col4:
            st.write("👤", row["nama_pasien"])

        col5, col6 = st.columns([3,1])

        with col5:
            st.write("🏠 Kamar:", row["kamar"])
            st.write("👨‍⚕️ PJ:", row["pj_operan"])
            st.caption(f"✏️ Edit: {row['edited_by']} | {row['edited_at']}")

        with col6:
            if st.button("📄 Detail", key=f"btn_{row['id']}"):

                st.session_state["detail"] = {
                    "nama": row["nama_pasien"],
                    "rm": row["no_rm"],
                    "tanggal": row["tanggal"],
                    "operan": row["operan"],
                    "pj": row["pj_operan"],
                    "edited_by": row["edited_by"],
                    "edited_at": row["edited_at"]
                }

# =========================
# DETAIL VIEW
# =========================
if "detail" in st.session_state:

    data = st.session_state["detail"]

    st.divider()

    st.subheader(f"📄 Detail Operan - {data['nama']}")

    st.caption(f"RM: {data['rm']} | {data['tanggal']}")

    st.write("👨‍⚕️ PJ:", data.get("pj", "-"))

    st.caption(f"✏️ {data.get('edited_by','-')} | {data.get('edited_at','-')}")

    st.info(data["operan"])

# =========================
# EDIT
# =========================
st.divider()
st.subheader("✏️ Edit Operan")

edit_rm = st.text_input("No RM Edit")
edit_by = st.text_input("Nama Pengedit")
edit_text = st.text_area("Operan Baru")

if st.button("Update"):

    waktu = datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
        UPDATE operan
        SET operan = ?, edited_by = ?, edited_at = ?
        WHERE no_rm = ?
    """, (edit_text, edit_by, waktu, edit_rm))

    conn.commit()

    load_data.clear()

    st.success("Updated")
    st.rerun()
