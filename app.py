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
# AUTO DELETE 15 HARI
# =========================
try:
    c.execute("""
        DELETE FROM operan
        WHERE julianday('now') - julianday(tanggal) > 15
    """)
    conn.commit()
except Exception as e:
    print("Auto delete error:", e)

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

st.sidebar.title("🏥 Pilih Unit")
selected_unit = st.sidebar.selectbox("Unit", unit_list)

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
# INPUT
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

    operan = st.text_area("Operan", height=130, max_chars=1500)

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

        st.success("Tersimpan")
        st.rerun()

# =========================
# STATE
# =========================
if "open_detail" not in st.session_state:
    st.session_state["open_detail"] = None

if "confirm_delete" not in st.session_state:
    st.session_state["confirm_delete"] = None

# =========================
# DATA LIST
# =========================
st.subheader("📋 Data Operan")

df = pd.read_sql_query("""
SELECT *
FROM operan
WHERE unit = ?
AND julianday('now') - julianday(tanggal) <= 7
ORDER BY id DESC
""", conn, params=(selected_unit,))

for _, r in df.iterrows():

    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)

    col1.write(f"📅 {r['tanggal']}")
    col2.write(f"⏱ Shift: {r['shift']}")
    col3.write(f"🏥 No RM: {r['no_rm']}")
    col4.write(f"👤 Pasien: {r['nama_pasien']}")

    st.write(f"🏠 {r['kamar']} | 🧾 {r['diagnosa']} | 👨‍⚕️ {r['pj_operan']}")

    colA, colB = st.columns([1, 1])

    # DETAIL
    if colA.button("📄 Detail", key=f"detail_{r['id']}"):

        if st.session_state["open_detail"] == r["id"]:
            st.session_state["open_detail"] = None
        else:
            st.session_state["open_detail"] = r["id"]

    # DELETE BUTTON
    if colB.button("🗑 Hapus", key=f"del_{r['id']}"):
        st.session_state["confirm_delete"] = r["id"]

    # CONFIRM DELETE
    if st.session_state["confirm_delete"] == r["id"]:

        st.warning(f"⚠️ Yakin ingin menghapus pasien: {r['nama_pasien']} ?")

        col_yes, col_no = st.columns(2)

        with col_yes:
            if st.button("✅ Ya, Hapus", key=f"yes_{r['id']}"):

                c.execute("DELETE FROM operan WHERE id=?", (r["id"],))
                conn.commit()

                st.session_state["confirm_delete"] = None
                st.rerun()

        with col_no:
            if st.button("❌ Batal", key=f"no_{r['id']}"):
                st.session_state["confirm_delete"] = None
                st.rerun()

    # DETAIL SHOW
    if st.session_state["open_detail"] == r["id"]:
        st.info(r["operan"])
        st.caption(f"✏️ Edit: {r['edited_by']} | {r['edited_at']}")

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

    # =========================
    # CEK NO RM ADA ATAU TIDAK
    # =========================
    cek = c.execute("""
        SELECT COUNT(*)
        FROM operan
        WHERE no_rm = ?
    """, (edit_rm,)).fetchone()[0]

    if cek == 0:
        st.error("❌ Tidak ada No RM / pasien yang sesuai")

    else:
        # =========================
        # UPDATE DATA TERAKHIR
        # =========================
        c.execute("""
            UPDATE operan
            SET operan = ?, edited_by = ?, edited_at = ?
            WHERE id = (
                SELECT id FROM operan
                WHERE no_rm = ?
                ORDER BY id DESC
                LIMIT 1
            )
        """, (edit_text, edit_by, waktu, edit_rm))

        conn.commit()

        st.success("✅ Operan berhasil diupdate (data terakhir)")
        st.rerun()

 
# =========================
# PDF EXPORT
# =========================
st.divider()
st.subheader("⬇️ Download PDF")

col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input("Dari")

with col2:
    end_date = st.date_input("Sampai")

pdf_df = pd.read_sql_query("""
SELECT *
FROM operan
WHERE unit = ?
AND julianday('now') - julianday(tanggal) <= 35
AND tanggal BETWEEN ? AND ?
ORDER BY id DESC
""", conn, params=(
    selected_unit,
    f"{start_date} 00:00:00",
    f"{end_date} 23:59:59"
))

def generate_pdf(df):

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Paragraph("Operan Shift", styles["Title"]))
    elements.append(Spacer(1, 12))

    data = [list(df.columns)]

    for r in df.values.tolist():
        data.append(r)

    table = Table(data)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
    ]))

    elements.append(table)
    doc.build(elements)

    return buffer.getvalue()

if not pdf_df.empty:

    st.download_button(
        "Download PDF",
        generate_pdf(pdf_df),
        file_name=f"operan_{selected_unit}.pdf",
        mime="application/pdf"
    )

# =========================
# FOOTER
# =========================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888; font-size: 12px;'>"
    "🏥 Sistem Operan Shift RS Sari Asih Sangiang<br>"
    "Developed by <b>RSD 2026</b> © All Rights Reserved"
    "</div>",
    unsafe_allow_html=True
)
