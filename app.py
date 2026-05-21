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
# CONFIG
# =========================
st.set_page_config(
    page_title="SIMRS Operan",
    page_icon="🏥",
    layout="centered"
)

# =========================
# STYLE MOBILE APP
# =========================
st.markdown("""
<style>

.block-container {
    padding: 1rem;
    background: #111827;
    color: white;
}

h1, h2, h3 {
    color: white !important;
}

.card {
    background: #1f2937;
    padding: 12px;
    border-radius: 12px;
    margin-bottom: 10px;
}

.small {
    font-size: 12px;
    color: #9ca3af;
}

.stButton>button {
    width: 100%;
    border-radius: 10px;
    background: #374151;
    color: white;
    padding: 10px;
}

.stButton>button:hover {
    background: #6b7280;
}

</style>
""", unsafe_allow_html=True)

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
# HEADER APP STYLE
# =========================
st.markdown("# 🏥 SIMRS OPERAN")
st.markdown("### Sistem Operan Shift Mobile")

# =========================
# UNIT (FULL WIDTH DROPDOWN)
# =========================
unit_list = ["ICU","IGD","NICU","PICU","RPU LT 1","RPU LT 2","RPU LT 3 GL"]

selected_unit = st.selectbox("🏥 Pilih Unit", unit_list)

st.markdown(f"**Unit Aktif:** {selected_unit}")

# =========================
# SHIFT AUTO
# =========================
hour = datetime.now(jakarta).hour
shift = "Pagi" if hour < 14 else "Sore" if hour < 21 else "Malam"

# =========================
# INPUT CARD
# =========================
st.markdown("## ➕ Input Operan")

with st.container():
    with st.form("form"):
        no_rm = st.text_input("No RM")
        nama = st.text_input("Nama Pasien")
        kamar = st.text_input("Kamar")
        diagnosa = st.text_input("Diagnosa")
        pj = st.text_input("PJ Operan")
        isi = st.text_area("Isi Operan", height=120)

        submitted = st.form_submit_button("💾 SIMPAN OPERAN")

        if submitted:
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
                    selected_unit, shift,
                    no_rm, nama, kamar, diagnosa,
                    isi, pj
                ))
                conn.commit()
                st.success("Tersimpan")
                st.rerun()

# =========================
# DATA CARD LIST (ANDROID STYLE)
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
            <b>📅 {r['tanggal']}</b><br>
            👤 {r['nama_pasien']} ({r['no_rm']})<br>
            🏠 {r['kamar']} | 🧾 {r['diagnosa']}<br>
            👨‍⚕️ PJ: {r['pj_operan']}<br>
            <span class="small">Shift: {r['shift']}</span>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("🔎 Lihat Detail Operan"):
            st.write(r["operan"])

# =========================
# EDIT SIMPLE
# =========================
st.markdown("## ✏️ Edit Operan")

edit_rm = st.text_input("No RM Edit")
edit_text = st.text_area("Operan Baru")

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
        st.success("Update sukses")
        st.rerun()

# =========================
# PDF
# =========================
st.markdown("## 📤 Download")

start = st.date_input("Dari")
end = st.date_input("Sampai")

pdf_df = pd.read_sql_query("""
SELECT * FROM operan
WHERE unit=?
AND date(tanggal) BETWEEN date(?) AND date(?)
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
        "simrs_operan.pdf"
    )
