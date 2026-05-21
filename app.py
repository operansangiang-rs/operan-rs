import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Operan Shift RS",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 Operan Shift Rumah Sakit")

# =========================
# DATABASE
# =========================
conn = sqlite3.connect(
    "operan.db",
    check_same_thread=False
)

c = conn.cursor()

# =========================
# CREATE TABLE
# =========================
c.execute("""
CREATE TABLE IF NOT EXISTS operan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tanggal TEXT,
    unit TEXT,
    shift TEXT,
    no_rm TEXT,
    nama_pasien TEXT,
    kamar TEXT,
    diagnosa TEXT,
    operan TEXT
)
""")

conn.commit()

# =========================
# AUTO DELETE > 40 HARI
# =========================
c.execute("""
DELETE FROM operan
WHERE created_at <= datetime('now', '-40 day')
""")

conn.commit()

# =========================
# SIDEBAR UNIT
# =========================
unit_list = [
    "ICU",
    "RPU LT 1",
    "RPU LT 2",
    "RPU LT 3",
    "RPU LT 4",
    "RPU LT 5",
    "Hemodialisa",
    "Kamar Operasi",
    "IGD",
    "NICU",
    "PICU"
]

st.sidebar.title("🏥 Unit")

selected_unit = st.sidebar.selectbox(
    "Pilih Unit",
    unit_list
)

# =========================
# SEARCH GLOBAL
# =========================
st.subheader("🔎 Cari Pasien")

search = st.text_input(
    "Cari berdasarkan No RM atau Nama Pasien"
)

if search:

    query = """
    SELECT
        tanggal,
        unit,
        shift,
        no_rm,
        nama_pasien,
        kamar,
        diagnosa,
        operan
    FROM operan
    WHERE no_rm LIKE ?
    OR nama_pasien LIKE ?
    ORDER BY id DESC
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

st.divider()

# =========================
# INPUT OPERAN
# =========================
st.subheader(f"📝 Input Operan - {selected_unit}")

with st.form("form_operan"):

    col1, col2 = st.columns(2)

    with col1:
        tanggal = st.date_input("Tanggal")

        shift = st.selectbox(
            "Shift",
            ["Pagi", "Sore", "Malam"]
        )

        no_rm = st.text_input("No RM")

        nama_pasien = st.text_input("Nama Pasien")

    with col2:
        kamar = st.text_input("Kamar / Bed")

        diagnosa = st.text_input("Diagnosa")

    operan = st.text_area(
        "Operan Shift",
        height=150
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
                operan
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(tanggal),
                selected_unit,
                shift,
                no_rm,
                nama_pasien,
                kamar,
                diagnosa,
                operan
            )
        )

        conn.commit()

        st.success(
            "Operan berhasil disimpan"
        )

        st.rerun()

# =========================
# DATA UNIT
# =========================
st.subheader(
    f"📋 Data Operan - {selected_unit}"
)

query_unit = """
SELECT
    tanggal,
    shift,
    no_rm,
    nama_pasien,
    kamar,
    diagnosa,
    operan
FROM operan
WHERE unit = ?
ORDER BY id DESC
"""

unit_df = pd.read_sql_query(
    query_unit,
    conn,
    params=(selected_unit,)
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
    f"Total data {selected_unit}: {len(unit_df)} pasien"
)
