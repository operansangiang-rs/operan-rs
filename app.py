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
# TIMEZONE JAKARTA
# =========================
jakarta = pytz.timezone("Asia/Jakarta")

# =========================
# DB CONNECTION (OPTIMIZED)
# =========================
@st.cache_resource
def get_connection():

    conn = sqlite3.connect(
        "operan.db",
        check_same_thread=False
    )

    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA cache_size = 10000;")

    return conn

conn = get_connection()
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

if 7 <= jam < 14:
    auto_shift = "Pagi"
elif 14 <= jam < 21:
    auto_shift = "Sore"
else:
    auto_shift = "Malam"

# =========================
# UNIT
# =========================
unit_list = [
    "ICU","RPU LT 1","RPU LT 2","RPU LT 3 GL","RPU LT 3 GB",
    "RPU LT 4","RPU LT 5","Hemodialisa","Kamar Operasi",
    "IGD","NICU","PICU"
]

st.sidebar.title("🏥 Pilih Unit")
selected_unit = st.sidebar.selectbox("Unit", unit_list)

# =========================
# CACHE UNIT DATA (ANTI LAG UTAMA)
# =========================
@st.cache_data(ttl=15)
def load_unit_data(unit):

    return pd.read_sql_query("""
        SELECT
            id, tanggal, shift, no_rm,
            nama_pasien, kamar, diagnosa,
            operan, pj_operan, edited_by, edited_at
        FROM operan
        WHERE unit = ?
        ORDER BY id DESC
        LIMIT 100
    """, conn, params=(unit,))

# =========================
# CACHE SEARCH
# =========================
@st.cache_data(ttl=10)
def search_pasien(q):

    return pd.read_sql_query("""
        SELECT *
        FROM operan
        WHERE no_rm LIKE ?
        OR nama_pasien LIKE ?
        ORDER BY id DESC
        LIMIT 50
    """, conn, params=(f"%{q}%", f"%{q}%"))

# =========================
# SEARCH
# =========================
st.subheader("🔎 Cari Pasien")

search = st.text_input("Cari No RM / Nama")

if len(search) >= 3:
    df_search = search_pasien(search)

    st.dataframe(
        df_search,
        use_container_width=True,
        height=300
    )

elif search != "":
    st.info("Minimal 3 karakter")

st.divider()

# =========================
# FORM INPUT
# =========================
st.subheader(f"📝 Input Operan - {selected_unit}")

with st.form("form"):

    col1, col2 = st.columns(2)

    with col1:

        tanggal = datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S")

        st.text_input("Tanggal", value=tanggal, disabled=True)

        st.text_input("Shift", value=auto_shift, disabled=True)
        shift = auto_shift

        no_rm = st.text_input("No RM")
        nama_pasien = st.text_input("Nama Pasien")

    with col2:

        kamar = st.text_input("Kamar")
        diagnosa = st.text_input("Diagnosa")
        pj_operan = st.text_input("PJ Operan")

    operan = st.text_area("Operan", max_chars=1500)

    submit = st.form_submit_button("Simpan")

# =========================
# SAVE
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

        load_unit_data.clear()
        search_pasien.clear()

        st.success("Tersimpan")
        st.rerun()

    else:
        st.warning("No RM & Nama wajib")

# =========================
# DATA VIEW (FAST)
# =========================
st.subheader(f"📋 Data - {selected_unit}")

df = load_unit_data(selected_unit)

st.dataframe(df, use_container_width=True, height=400)

st.caption(f"{len(df)} data terbaru")

# =========================
# EDIT
# =========================
st.divider()
st.subheader("✏️ Edit Operan")

edit_no_rm = st.text_input("No RM Edit")
edit_by = st.text_input("Nama Pengedit")
edit_text = st.text_area("Operan Baru")

if st.button("Update"):

    waktu = datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
        UPDATE operan
        SET operan = ?, edited_by = ?, edited_at = ?
        WHERE no_rm = ?
    """, (edit_text, edit_by, waktu, edit_no_rm))

    conn.commit()

    load_unit_data.clear()
    search_pasien.clear()

    st.success("Updated")
    st.rerun()

# =========================
# PDF (LIGHT QUERY)
# =========================
st.divider()
st.subheader("⬇️ PDF")

col1, col2 = st.columns(2)

with col1:
    start = st.date_input("Dari")

with col2:
    end = st.date_input("Sampai")

pdf_df = pd.read_sql_query("""
    SELECT
        tanggal, unit, shift,
        no_rm, nama_pasien,
        kamar, diagnosa, operan, pj_operan
    FROM operan
    WHERE unit = ?
    AND date(tanggal) BETWEEN date(?) AND date(?)
    ORDER BY id DESC
""", conn, params=(selected_unit, str(start), str(end)))


def make_pdf(df):

    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()

    elements = [
        Paragraph(f"Operan - {selected_unit}", styles["Title"]),
        Spacer(1, 10)
    ]

    data = [list(df.columns)] + df.values.tolist()

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTSIZE', (0,0), (-1,-1), 8),
    ]))

    elements.append(table)
    doc.build(elements)

    return buffer.getvalue()


if not pdf_df.empty:
    st.download_button(
        "Download PDF",
        make_pdf(pdf_df),
        f"operan_{selected_unit}.pdf"
    )
else:
    st.info("Tidak ada data")
