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
# DATABASE
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
# AUTO DELETE 40 HARI
# =========================
try:
    c.execute("""
        DELETE FROM operan
        WHERE datetime(tanggal) <= datetime('now', '-40 day')
    """)
    conn.commit()
except:
    pass

# =========================
# UNIT
# =========================
unit_list = [
    "ICU","RPU LT 1","RPU LT 2","RPU LT 3 GL","RPU LT 3 GB",
    "RPU LT 4","RPU LT 5","Hemodialisa","Kamar Operasi",
    "IGD","NICU","PICU"
]

selected_unit = st.sidebar.selectbox("Unit", unit_list)

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
# INPUT FORM
# =========================
st.subheader(f"📝 Input Operan - {selected_unit}")

with st.form("form"):
    tanggal = datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S")

    st.text_input("Tanggal", value=tanggal, disabled=True)
    st.text_input("Shift", value=auto_shift, disabled=True)

    no_rm = st.text_input("No RM")
    nama_pasien = st.text_input("Nama Pasien")

    kamar = st.text_input("Kamar")
    diagnosa = st.text_input("Diagnosa")
    pj_operan = st.text_input("PJ Operan")

    operan = st.text_area("Operan", height=150, max_chars=1500)

    submit = st.form_submit_button("💾 Simpan")

if submit:
    if no_rm and nama_pasien:

        c.execute("""
            INSERT INTO operan (
                tanggal, unit, shift, no_rm, nama_pasien,
                kamar, diagnosa, operan, pj_operan
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tanggal, selected_unit, auto_shift,
            no_rm, nama_pasien, kamar,
            diagnosa, operan, pj_operan
        ))

        conn.commit()
        st.rerun()

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=20)
def load_data(unit):
    return pd.read_sql_query("""
        SELECT * FROM operan
        WHERE unit = ?
        ORDER BY id DESC
        LIMIT 100
    """, conn, params=(unit,))

# =========================
# DATA VIEW + DETAIL BUTTON
# =========================
st.subheader("📋 Data Operan")

df = load_data(selected_unit)

for _, row in df.iterrows():

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

    col5, col6 = st.columns([4,1])

    with col5:
        st.write("🏠 Kamar:", row["kamar"])
        st.write("🧾 Diagnosa:", row["diagnosa"])
        st.write("👨‍⚕️ PJ:", row["pj_operan"])
        st.caption(f"✏️ {row['edited_by']} | {row['edited_at']}")

    with col6:
        show = st.checkbox("📄 Detail", key=f"det_{row['id']}")

    if show:
        st.text_area(
            "Isi Operan",
            value=row["operan"],
            height=200,
            disabled=True,
            key=f"op_{row['id']}"
        )

# =========================
# EDIT (LAST NO RM ONLY)
# =========================
st.divider()
st.subheader("✏️ Edit Operan Terakhir")

edit_no_rm = st.text_input("No RM Edit")
edit_by = st.text_input("Nama Editor")
edit_text = st.text_area("Operan Baru")

if st.button("Update"):
    now = datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
        SELECT id FROM operan
        WHERE no_rm = ?
        ORDER BY id DESC LIMIT 1
    """, (edit_no_rm,))

    last = c.fetchone()

    if last:
        c.execute("""
            UPDATE operan
            SET operan = ?, edited_by = ?, edited_at = ?
            WHERE id = ?
        """, (edit_text, edit_by, now, last[0]))

        conn.commit()
        st.rerun()

# =========================
# PDF DOWNLOAD
# =========================
st.divider()
st.subheader("⬇️ Download PDF")

start = st.date_input("Dari")
end = st.date_input("Sampai")

pdf_df = pd.read_sql_query("""
    SELECT * FROM operan
    WHERE unit = ?
    AND date(tanggal) BETWEEN date(?) AND date(?)
    ORDER BY tanggal DESC
""", conn, params=(selected_unit, str(start), str(end)))

def make_pdf(df):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    styles = getSampleStyleSheet()

    elements = [Paragraph("Operan Shift", styles["Title"]), Spacer(1,12)]

    data = [df.columns.tolist()] + df.values.tolist()

    table = Table(data)
    table.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),1,colors.black),
        ("BACKGROUND",(0,0),(-1,0),colors.grey),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),7),
    ]))

    elements.append(table)
    doc.build(elements)

    return buf.getvalue()

if not pdf_df.empty:
    st.download_button(
        "Download PDF",
        make_pdf(pdf_df),
        "operan.pdf",
        "application/pdf"
    )
