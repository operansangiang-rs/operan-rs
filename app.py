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
# TABLE (ID HIDDEN TAPI ADA)
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
c.execute("""
DELETE FROM operan
WHERE date(tanggal) <= date('now', '-40 day')
""")
conn.commit()

# =========================
# SHIFT AUTO
# =========================
jam = datetime.now(jakarta).hour

if jam < 14:
    auto_shift = "Pagi"
elif jam < 21:
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

selected_unit = st.sidebar.selectbox("🏥 Pilih Unit", unit_list)

# =========================
# INPUT
# =========================
st.subheader("📝 Input Operan")

with st.form("form"):

    tanggal = datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S")

    st.text_input("Shift", auto_shift, disabled=True)

    no_rm = st.text_input("No RM")
    nama_pasien = st.text_input("Nama Pasien")
    kamar = st.text_input("Kamar")
    diagnosa = st.text_input("Diagnosa")
    pj_operan = st.text_input("PJ Operan")
    operan = st.text_area("Operan")

    submit = st.form_submit_button("Simpan")

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
            tanggal, selected_unit, auto_shift,
            no_rm, nama_pasien,
            kamar, diagnosa,
            operan, pj_operan
        ))

        conn.commit()
        st.rerun()

# =========================
# DATA LIST (ID TIDAK DITAMPILKAN)
# =========================
st.subheader("📋 Data Operan")

df = pd.read_sql_query("""
SELECT *
FROM operan
WHERE unit = ?
ORDER BY id DESC
LIMIT 100
""", conn, params=(selected_unit,))

for _, r in df.iterrows():

    with st.container():

        st.markdown("---")

        st.write(f"📅 {r['tanggal']} | ⏱ {r['shift']}")
        st.write(f"🆔 {r['no_rm']} | 👤 {r['nama_pasien']}")
        st.write(f"🏠 {r['kamar']} | 🧾 {r['diagnosa']} | 👨‍⚕️ {r['pj_operan']}")

        with st.expander("📄 Detail Operan"):

            st.write(r["operan"])
            st.caption(f"✏️ Edit: {r['edited_by']} | {r['edited_at']}")

            if st.button("🗑 Hapus", key=f"del_{r['id']}"):
                c.execute("DELETE FROM operan WHERE id=?", (r["id"],))
                conn.commit()
                st.rerun()

# =========================
# EDIT TERAKHIR (PAKAI ID INTERNAL)
# =========================
st.divider()
st.subheader("✏️ Edit Operan Terakhir")

edit_rm = st.text_input("No RM")
edit_by = st.text_input("Nama Editor")
edit_text = st.text_area("Operan Baru")

if st.button("Update"):

    now = datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
        SELECT id
        FROM operan
        WHERE no_rm = ?
        ORDER BY id DESC
        LIMIT 1
    """, (edit_rm,))

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
# PDF EXPORT
# =========================
st.divider()
st.subheader("⬇️ Download PDF")

col1, col2 = st.columns(2)

with col1:
    start = st.date_input("Dari")

with col2:
    end = st.date_input("Sampai")

pdf_df = pd.read_sql_query("""
SELECT *
FROM operan
WHERE unit = ?
AND date(tanggal) BETWEEN date(?) AND date(?)
ORDER BY tanggal DESC
""", conn, params=(selected_unit, str(start), str(end)))

def make_pdf(df):

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    styles = getSampleStyleSheet()

    elements = [
        Paragraph("OPERAN SHIFT RS", styles["Title"]),
        Spacer(1, 10)
    ]

    data = [df.columns.tolist()] + df.values.tolist()

    table = Table(data)

    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.grey),
        ("TEXTCOLOR",(0,0),(-1,0),colors.whitesmoke),
        ("GRID",(0,0),(-1,-1),0.5,colors.black),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),8),
    ]))

    elements.append(table)
    doc.build(elements)

    return buf.getvalue()

if not pdf_df.empty:
    st.download_button(
        "Download PDF",
        make_pdf(pdf_df),
        file_name="operan.pdf",
        mime="application/pdf"
    )
