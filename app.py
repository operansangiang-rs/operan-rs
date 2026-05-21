import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import pytz
from io import BytesIO

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import landscape, A4

# =========================
# CONFIG UI
# =========================
st.set_page_config(
    page_title="SIMRS Operan Mobile",
    page_icon="🏥",
    layout="centered"
)

st.markdown("""
<style>
.block-container {background:#111827;color:white;padding:1rem;}
h1,h2,h3 {color:white !important;}

.card {
    background:#1f2937;
    padding:12px;
    border-radius:12px;
    margin-bottom:10px;
}

.stButton>button{
    width:100%;
    background:#374151;
    color:white;
    border-radius:10px;
}
</style>
""", unsafe_allow_html=True)

st.title("🏥 SIMRS OPERAN MOBILE")

# =========================
# DB
# =========================
conn = sqlite3.connect("operan.db", check_same_thread=False)
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
    pj_operan TEXT,
    edited_by TEXT,
    edited_at TEXT
)
""")
conn.commit()

jakarta = pytz.timezone("Asia/Jakarta")

# =========================
# UNIT
# =========================
unit_list = ["ICU","IGD","NICU","PICU","RPU LT 1","RPU LT 2","RPU LT 3"]

selected_unit = st.selectbox("🏥 Pilih Unit", unit_list)

st.markdown(f"**Unit Aktif:** {selected_unit}")

# =========================
# SHIFT AUTO
# =========================
hour = datetime.now(jakarta).hour
shift = "Pagi" if hour < 14 else "Sore" if hour < 21 else "Malam"

# =========================
# INPUT FORM
# =========================
st.markdown("## ➕ Input Operan")

with st.form("form_input"):
    no_rm = st.text_input("No RM", key="in_rm")
    nama = st.text_input("Nama Pasien", key="in_nama")
    kamar = st.text_input("Kamar", key="in_kamar")
    diagnosa = st.text_input("Diagnosa", key="in_diag")
    pj = st.text_input("PJ Operan", key="in_pj")
    isi = st.text_area("Isi Operan", key="in_isi")

    submit = st.form_submit_button("💾 SIMPAN")

    if submit:
        if no_rm and nama:
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
                shift,
                no_rm,
                nama,
                kamar,
                diagnosa,
                isi,
                pj
            ))
            conn.commit()
            st.success("Tersimpan")
            st.rerun()

# =========================
# SEARCH RM (FIX YANG KAMU MAU)
# =========================
st.markdown("## 🔎 Cari RM / Nama")

search = st.text_input("Cari Pasien", key="search_box")

if search:

    df_search = pd.read_sql_query("""
    SELECT * FROM operan
    WHERE unit=?
    AND (no_rm LIKE ? OR nama_pasien LIKE ?)
    ORDER BY id DESC
    LIMIT 20
    """, conn, params=(selected_unit, f"%{search}%", f"%{search}%"))

    for _, r in df_search.iterrows():

        st.markdown(f"""
        <div class="card">
            👤 <b>{r['nama_pasien']}</b> ({r['no_rm']})<br>
            🏠 {r['kamar']} | 🧾 {r['diagnosa']}<br>
            📅 {r['tanggal']}
        </div>
        """, unsafe_allow_html=True)

        with st.expander("📄 Detail Operan"):
            st.write(r["operan"])

# =========================
# DATA LIST (MOBILE CARD)
# =========================
st.markdown("## 📋 Data Operan")

df = pd.read_sql_query("""
SELECT * FROM operan
WHERE unit=?
ORDER BY id DESC
LIMIT 30
""", conn, params=(selected_unit,))

for _, r in df.iterrows():

    with st.container():

        st.markdown(f"""
        <div class="card">
        📅 {r['tanggal']}<br>
        👤 {r['nama_pasien']} ({r['no_rm']})<br>
        🏠 {r['kamar']} | 🧾 {r['diagnosa']}<br>
        👨‍⚕️ PJ: {r['pj_operan']}<br>
        <small>Shift: {r['shift']}</small>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("📄 Detail Operan"):
            st.write(r["operan"])

# =========================
# EDIT TERAKHIR
# =========================
st.markdown("## ✏️ Edit Operan")

edit_rm = st.text_input("No RM Edit", key="edit_rm")
edit_text = st.text_area("Operan Baru", key="edit_text")

if st.button("UPDATE"):
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
            SET operan=?, edited_at=?
            WHERE id=?
        """, (edit_text, now, last[0]))

        conn.commit()
        st.success("Updated")
        st.rerun()

# =========================
# PDF DOWNLOAD
# =========================
st.markdown("## 📤 Download PDF")

start = st.date_input("Dari")
end = st.date_input("Sampai")

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

    elements = [Paragraph("SIMRS OPERAN", styles["Title"]), Spacer(1, 10)]

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
        "operan.pdf"
    )
