import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime
import pytz

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import landscape, A4

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Operan Shift RS",
    page_icon="🏥",
    layout="wide"
)

# =========================
# DARK GRAY THEME
# =========================
st.markdown("""
<style>

.block-container {
    background: #1f2937;
    padding-top: 1rem;
    color: #e5e7eb;
}

section[data-testid="stSidebar"] {
    background: #111827 !important;
}

section[data-testid="stSidebar"] * {
    color: #e5e7eb !important;
}

div[data-testid="stMetric"]{
    background: #374151;
    padding: 12px;
    border-radius: 12px;
    color: white;
}

.stButton>button {
    background: #6b7280;
    color: white;
    border-radius: 8px;
}

.stButton>button:hover {
    background: #9ca3af;
    color: black;
}

</style>
""", unsafe_allow_html=True)

st.title("🏥 Operan Shift RS Sari Asih Sangiang")

# =========================
# TIMEZONE
# =========================
jakarta = pytz.timezone("Asia/Jakarta")

# =========================
# DB
# =========================
@st.cache_resource
def conn_db():
    conn = sqlite3.connect("operan.db", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

conn = conn_db()
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
# UNIT
# =========================
unit_list = [
    "ICU","RPU LT 1","RPU LT 2","RPU LT 3 GL","RPU LT 3 GB",
    "RPU LT 4","RPU LT 5","Hemodialisa","Kamar Operasi",
    "IGD","NICU","PICU"
]

selected_unit = st.sidebar.selectbox("🏥 Unit", unit_list)

# =========================
# SHIFT AUTO
# =========================
hour = datetime.now(jakarta).hour
auto_shift = "Pagi" if hour < 14 else "Sore" if hour < 21 else "Malam"

# =========================
# INPUT FORM
# =========================
st.subheader("📝 Input Operan")

with st.container():

    col1, col2, col3 = st.columns(3)

    with col1:
        st.text_input(
            "Tanggal",
            datetime.now(jakarta).strftime("%Y-%m-%d %H:%M"),
            disabled=True,
            key="tgl_show"
        )
        st.text_input(
            "Shift",
            auto_shift,
            disabled=True,
            key="shift_show"
        )

    with col2:
        no_rm = st.text_input("No RM", key="no_rm_input")
        nama_pasien = st.text_input("Nama Pasien", key="nama_input")

    with col3:
        kamar = st.text_input("Kamar", key="kamar_input")
        diagnosa = st.text_input("Diagnosa", key="diag_input")
        pj_operan = st.text_input("PJ Operan", key="pj_input")

    operan = st.text_area("Isi Operan", height=140, key="operan_input")

    if st.button("💾 Simpan Operan", use_container_width=True):

        if no_rm and nama_pasien:

            c.execute("""
                INSERT INTO operan (
                    tanggal, unit, shift, no_rm,
                    nama_pasien, kamar, diagnosa,
                    operan, pj_operan
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S"),
                selected_unit,
                auto_shift,
                no_rm,
                nama_pasien,
                kamar,
                diagnosa,
                operan,
                pj_operan
            ))

            conn.commit()

            # reset input aman
            st.rerun()

# =========================
# DATA LIST
# =========================
st.subheader("📋 Data Operan")

df = pd.read_sql_query("""
SELECT * FROM operan
WHERE unit = ?
ORDER BY id DESC
LIMIT 50
""", conn, params=(selected_unit,))

for _, r in df.iterrows():

    with st.container():

        col1, col2, col3, col4 = st.columns(4)

        col1.write(f"📅 {r['tanggal']}")
        col2.write(f"⏱ {r['shift']}")
        col3.write(f"🆔 {r['no_rm']}")
        col4.write(f"👤 {r['nama_pasien']}")

        st.write(f"🏠 {r['kamar']} | 🧾 {r['diagnosa']} | 👨‍⚕️ {r['pj_operan']}")

        with st.expander("📄 Detail Operan"):

            st.write(r["operan"])

            st.caption(f"✏️ Edit: {r['edited_by']} | {r['edited_at']}")

            colA, colB = st.columns(2)

            if st.button("🗑 Hapus", key=f"del_{r['id']}"):
                c.execute("DELETE FROM operan WHERE id=?", (r["id"],))
                conn.commit()
                st.rerun()

# =========================
# EDIT
# =========================
st.divider()
st.subheader("✏️ Edit Operan")

edit_rm = st.text_input("No RM", key="edit_rm")
edit_by = st.text_input("Nama Editor", key="edit_by")
edit_text = st.text_area("Operan Baru", key="edit_text")

if st.button("Update Operan", key="btn_update"):

    now = datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
        SELECT id FROM operan
        WHERE no_rm=?
        ORDER BY id DESC LIMIT 1
    """, (edit_rm,))

    last = c.fetchone()

    if last:
        c.execute("""
            UPDATE operan
            SET operan=?, edited_by=?, edited_at=?
            WHERE id=?
        """, (edit_text, edit_by, now, last[0]))

        conn.commit()
        st.rerun()

# =========================
# PDF
# =========================
st.divider()
st.subheader("⬇️ Download PDF")

start = st.date_input("Dari", key="start_pdf")
end = st.date_input("Sampai", key="end_pdf")

pdf_df = pd.read_sql_query("""
SELECT * FROM operan
WHERE unit=?
AND date(tanggal) BETWEEN date(?) AND date(?)
ORDER BY tanggal DESC
""", conn, params=(selected_unit, str(start), str(end)))

def make_pdf(df):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    styles = getSampleStyleSheet()

    elements = [Paragraph("OPERAN SHIFT RS", styles["Title"]), Spacer(1, 10)]

    data = [df.columns.tolist()] + df.values.tolist()

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.grey),
        ("TEXTCOLOR",(0,0),(-1,0),colors.whitesmoke),
        ("GRID",(0,0),(-1,-1),0.5,colors.black),
        ("FONTSIZE",(0,0),(-1,-1),7),
    ]))

    elements.append(table)
    doc.build(elements)

    return buf.getvalue()

if not pdf_df.empty:
    st.download_button(
        "⬇️ Download PDF",
        make_pdf(pdf_df),
        "operan.pdf",
        "application/pdf",
        use_container_width=True
    )
