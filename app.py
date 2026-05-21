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

st.markdown("""
<style>
.block-container {padding-top: 1.5rem;}
div[data-testid="stMetric"]{
    background:white;
    padding:12px;
    border-radius:12px;
    box-shadow:0 2px 10px rgba(0,0,0,0.05);
}
section[data-testid="stSidebar"] {
    background:#f4f6fb;
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
# SIDEBAR UNIT
# =========================
unit_list = [
    "ICU","RPU LT 1","RPU LT 2","RPU LT 3 GL","RPU LT 3 GB",
    "RPU LT 4","RPU LT 5","Hemodialisa","Kamar Operasi",
    "IGD","NICU","PICU"
]

selected_unit = st.sidebar.selectbox("🏥 Pilih Unit", unit_list)

# =========================
# SHIFT AUTO
# =========================
hour = datetime.now(jakarta).hour
auto_shift = "Pagi" if hour < 14 else "Sore" if hour < 21 else "Malam"

# =========================
# METRIC TOP
# =========================
df_count = pd.read_sql_query(
    "SELECT COUNT(*) as total FROM operan WHERE unit=?",
    conn,
    params=(selected_unit,)
)

c1, c2, c3 = st.columns(3)
c1.metric("Total Operan", int(df_count["total"].iloc[0]))
c2.metric("Unit", selected_unit)
c3.metric("Shift Aktif", auto_shift)

st.divider()

# =========================
# FORM INPUT (CLEAN CARD)
# =========================
st.subheader("📝 Input Operan")

with st.container(border=True):

    col1, col2 = st.columns(2)

    with col1:
        st.text_input("Tanggal", value=datetime.now(jakarta).strftime("%Y-%m-%d %H:%M"), disabled=True)
        st.text_input("Shift", value=auto_shift, disabled=True)

    with col2:
        no_rm = st.text_input("No RM", key="no_rm")
        nama_pasien = st.text_input("Nama Pasien", key="nama_pasien")

    col3, col4, col5 = st.columns(3)

    with col3:
        kamar = st.text_input("Kamar", key="kamar")
    with col4:
        diagnosa = st.text_input("Diagnosa", key="diagnosa")
    with col5:
        pj_operan = st.text_input("PJ Operan", key="pj_operan")

    operan = st.text_area("Isi Operan", height=140, key="operan")

    if st.button("💾 Simpan Operan", use_container_width=True):

        if no_rm and nama_pasien:

            c.execute("""
                INSERT INTO operan (
                    tanggal, unit, shift, no_rm, nama_pasien,
                    kamar, diagnosa, operan, pj_operan
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

            # reset input
            for k in ["no_rm","nama_pasien","kamar","diagnosa","pj_operan","operan"]:
                st.session_state[k] = ""

            st.rerun()

st.divider()

# =========================
# DATA LIST (CARD STYLE CLEAN)
# =========================
st.subheader("📋 Data Operan")

df = pd.read_sql_query("""
SELECT * FROM operan
WHERE unit=?
ORDER BY id DESC
LIMIT 50
""", conn, params=(selected_unit,))

for _, r in df.iterrows():

    with st.container(border=True):

        c1, c2, c3, c4 = st.columns([2,1,1,2])

        c1.markdown(f"📅 **{r['tanggal']}**")
        c2.markdown(f"⏱ {r['shift']}")
        c3.markdown(f"🆔 {r['no_rm']}")
        c4.markdown(f"👤 {r['nama_pasien']}")

        st.caption(f"🏠 {r['kamar']} | 🧾 {r['diagnosa']} | 👨‍⚕️ PJ: {r['pj_operan']}")

        with st.expander("📄 Detail Operan"):
            st.write(r["operan"])

            st.caption(f"✏️ Edit: {r['edited_by']} | {r['edited_at']}")

st.divider()

# =========================
# EDIT
# =========================
st.subheader("✏️ Edit Operan Terakhir")

edit_rm = st.text_input("No RM Edit")
edit_by = st.text_input("Nama Editor")
edit_text = st.text_area("Operan Baru")

if st.button("Update Operan"):

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

st.divider()

# =========================
# PDF DOWNLOAD
# =========================
st.subheader("⬇️ Download PDF")

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

    elements = [Paragraph("OPERAN SHIFT", styles["Title"]), Spacer(1, 12)]

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
