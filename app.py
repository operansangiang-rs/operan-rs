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
jakarta = pytz.timezone(
    "Asia/Jakarta"
)

# =========================
# DATABASE
# =========================
@st.cache_resource
def get_connection():

    conn = sqlite3.connect(
        "operan.db",
        check_same_thread=False
    )

    conn.execute(
        "PRAGMA journal_mode=WAL;"
    )

    conn.execute(
        "PRAGMA synchronous=NORMAL;"
    )

    return conn

conn = get_connection()

c = conn.cursor()

# =========================
# CREATE TABLE
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
# UPDATE DATABASE LAMA
# =========================
try:

    c.execute("""
    ALTER TABLE operan
    ADD COLUMN pj_operan TEXT
    """)

    conn.commit()

except:
    pass

try:

    c.execute("""
    ALTER TABLE operan
    ADD COLUMN edited_by TEXT
    """)

    conn.commit()

except:
    pass

try:

    c.execute("""
    ALTER TABLE operan
    ADD COLUMN edited_at TEXT
    """)

    conn.commit()

except:
    pass

# =========================
# AUTO DELETE > 40 HARI
# =========================
try:

    c.execute("""
    DELETE FROM operan
    WHERE datetime(tanggal)
    <= datetime('now', '-40 day')
    """)

    conn.commit()

except Exception as e:

    st.warning(
        f"Auto delete error: {e}"
    )

# =========================
# UNIT LIST
# =========================
unit_list = [
    "ICU",
    "RPU LT 1",
    "RPU LT 2",
    "RPU LT 3 GL",
    "RPU LT 3 GB",
    "RPU LT 4",
    "RPU LT 5",
    "Hemodialisa",
    "Kamar Operasi",
    "IGD",
    "NICU",
    "PICU"
]

# =========================
# SIDEBAR
# =========================
st.sidebar.title("🏥 Pilih Unit")

selected_unit = st.sidebar.selectbox(
    "Unit",
    unit_list
)

# =========================
# CACHE QUERY
# =========================
@st.cache_data(ttl=30)
def load_unit_data(unit):

    query = """
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
        edited_by,
        edited_at
    FROM operan
    WHERE unit = ?
    ORDER BY id DESC
    LIMIT 100
    """

    return pd.read_sql_query(
        query,
        conn,
        params=(unit,)
    )

# =========================
# SEARCH GLOBAL
# =========================
st.subheader("🔎 Cari Pasien")

search = st.text_input(
    "Cari berdasarkan No RM atau Nama Pasien"
)

if len(search) >= 3:

    query = """
    SELECT
        id,
        tanggal,
        unit,
        shift,
        no_rm,
        nama_pasien,
        kamar,
        diagnosa,
        operan,
        pj_operan,
        edited_by,
        edited_at
    FROM operan
    WHERE no_rm LIKE ?
    OR nama_pasien LIKE ?
    ORDER BY id DESC
    LIMIT 50
    """

    df_search = pd.read_sql_query(
        query,
        conn,
        params=(
            f"%{search}%",
            f"%{search}%"
        )
    )

    st.dataframe(
        df_search,
        use_container_width=True,
        hide_index=True
    )

elif search != "":

    st.info(
        "Minimal 3 karakter pencarian"
    )

st.divider()

# =========================
# FORM INPUT
# =========================
st.subheader(
    f"📝 Input Operan - {selected_unit}"
)

with st.form("form_operan"):

    col1, col2 = st.columns(2)

    with col1:

        tanggal = datetime.now(
            jakarta
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        st.text_input(
            "Tanggal Input",
            value=tanggal,
            disabled=True
        )

        shift = st.selectbox(
            "Shift",
            ["Pagi", "Sore", "Malam"]
        )

        no_rm = st.text_input(
            "No RM"
        )

        nama_pasien = st.text_input(
            "Nama Pasien"
        )

    with col2:

        kamar = st.text_input(
            "Kamar / Bed"
        )

        diagnosa = st.text_input(
            "Diagnosa"
        )

        pj_operan = st.text_input(
            "PJ Operan / Perawat"
        )

    operan = st.text_area(
        "Operan Shift",
        height=150,
        max_chars=1500,
        placeholder="Maksimal 1500 karakter"
    )

    submit = st.form_submit_button(
        "💾 Simpan Operan"
    )

# =========================
# SAVE DATA
# =========================
if submit:

    if no_rm == "" or nama_pasien == "":

        st.warning(
            "No RM dan Nama Pasien wajib diisi"
        )

    else:

        c.execute(
            """
            INSERT INTO operan (
                tanggal,
                unit,
                shift,
                no_rm,
                nama_pasien,
                kamar,
                diagnosa,
                operan,
                pj_operan
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tanggal,
                selected_unit,
                shift,
                no_rm,
                nama_pasien,
                kamar,
                diagnosa,
                operan,
                pj_operan
            )
        )

        conn.commit()

        load_unit_data.clear()

        st.success(
            "Operan berhasil disimpan"
        )

        st.rerun()

# =========================
# DATA OPERAN PER UNIT
# =========================
st.subheader(
    f"📋 Data Operan - {selected_unit}"
)

unit_df = load_unit_data(
    selected_unit
)

st.dataframe(
    unit_df,
    use_container_width=True,
    hide_index=True
)

# =========================
# TOTAL DATA
# =========================
st.caption(
    f"Menampilkan {len(unit_df)} data terbaru"
)

# =========================
# EDIT OPERAN
# =========================
st.divider()

st.subheader("✏️ Edit Operan")

edit_no_rm = st.text_input(
    "Masukkan No RM"
)

edit_nama = st.text_input(
    "Nama Pengedit"
)

edit_operan = st.text_area(
    "Edit Operan Baru"
)

if st.button("💾 Update Operan"):

    waktu_edit = datetime.now(
        jakarta
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    c.execute(
        """
        UPDATE operan
        SET
            operan = ?,
            edited_by = ?,
            edited_at = ?
        WHERE no_rm = ?
        """,
        (
            edit_operan,
            edit_nama,
            waktu_edit,
            edit_no_rm
        )
    )

    conn.commit()

    load_unit_data.clear()

    st.success(
        "Operan berhasil diupdate"
    )

    st.rerun()

# =========================
# FILTER DOWNLOAD PDF
# =========================
st.divider()

st.subheader("⬇️ Download PDF Operan")

col1, col2 = st.columns(2)

with col1:

    start_date = st.date_input(
        "Dari Tanggal"
    )

with col2:

    end_date = st.date_input(
        "Sampai Tanggal"
    )

pdf_query = """
SELECT
    tanggal,
    unit,
    shift,
    no_rm,
    nama_pasien,
    kamar,
    diagnosa,
    operan,
    pj_operan,
    edited_by,
    edited_at
FROM operan
WHERE unit = ?
AND date(tanggal)
BETWEEN date(?) AND date(?)
ORDER BY tanggal DESC
"""

pdf_df = pd.read_sql_query(
    pdf_query,
    conn,
    params=(
        selected_unit,
        str(start_date),
        str(end_date)
    )
)

# =========================
# GENERATE PDF
# =========================
def generate_pdf(dataframe):

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4)
    )

    styles = getSampleStyleSheet()

    elements = []

    title = Paragraph(
        f"Operan Shift - {selected_unit}",
        styles['Title']
    )

    elements.append(title)

    elements.append(
        Spacer(1, 12)
    )

    data = [
        list(dataframe.columns)
    ]

    for row in dataframe.values.tolist():

        data.append(row)

    table = Table(data)

    table.setStyle(TableStyle([
        (
            'BACKGROUND',
            (0, 0),
            (-1, 0),
            colors.grey
        ),
        (
            'TEXTCOLOR',
            (0, 0),
            (-1, 0),
            colors.whitesmoke
        ),
        (
            'GRID',
            (0, 0),
            (-1, -1),
            1,
            colors.black
        ),
        (
            'FONTNAME',
            (0, 0),
            (-1, 0),
            'Helvetica-Bold'
        ),
        (
            'FONTSIZE',
            (0, 0),
            (-1, -1),
            8
        ),
    ]))

    elements.append(table)

    doc.build(elements)

    pdf = buffer.getvalue()

    buffer.close()

    return pdf

# =========================
# DOWNLOAD PDF BUTTON
# =========================
if not pdf_df.empty:

    pdf_file = generate_pdf(
        pdf_df
    )

    st.download_button(
        label="⬇️ Download PDF",
        data=pdf_file,
        file_name=f"operan_{selected_unit}.pdf",
        mime="application/pdf"
    )

else:

    st.info(
        "Tidak ada data pada rentang tanggal tersebut"
    )
