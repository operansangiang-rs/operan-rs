import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Operan Shift RS",
    layout="wide"
)

st.title("Operan Shift Rumah Sakit")

# =========================
# DATABASE
# =========================
conn = sqlite3.connect("operan.db", check_same_thread=False)
c = conn.cursor()

# =========================
# BUAT TABEL
# =========================
c.execute('''
CREATE TABLE IF NOT EXISTS operan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal TEXT,
    unit TEXT,
    shift TEXT,
    no_rm TEXT,
    nama_pasien TEXT,
    kamar TEXT,
    diagnosa TEXT,
    operan TEXT
)
''')

conn.commit()

# =========================
# AUTO HAPUS >40 HARI
# =========================
limit_date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")

c.execute(
    "DELETE FROM operan WHERE tanggal < ?",
    (limit_date,)
)

conn.commit()

# =========================
# SEARCH GLOBAL
# =========================
st.subheader("Cari Pasien")

search = st.text_input("Cari No RM atau Nama Pasien")

if search:

    query = """
    SELECT * FROM operan
    WHERE no_rm LIKE ?
    OR nama_pasien LIKE ?
    ORDER BY id DESC
    """

    df_search = pd.read_sql_query(
        query,
        conn,
        params=(f"%{search}%", f"%{search}%")
    )

    st.dataframe(
        df_search,
        use_container_width=True,
        hide_index=True
    )

st.divider()

# =========================
# PILIH UNIT
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

selected_unit = st.selectbox(
    "Pilih Unit",
    unit_list
)

# =========================
# FORM INPUT
# =========================
st.subheader(f"Input Operan - {selected_unit}")

with st.form("form_operan"):

    tanggal = st.date_input("Tanggal")

    shift = st.selectbox(
        "Shift",
        ["Pagi", "Sore", "Malam"]
    )

    no_rm = st.text_input("No RM")

    nama_pasien = st.text_input("Nama Pasien")

    kamar = st.text_input("Kamar / Bed")

    diagnosa = st.text_input("Diagnosa")

    operan = st.text_area("Operan Shift")

    submit = st.form_submit_button("Simpan")

# =========================
# SIMPAN DATA
# =========================
if submit:

    c.execute(
        '''
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
        ''',
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

    st.success("Operan berhasil disimpan")

    st.rerun()

# =========================
# TAMPILKAN DATA UNIT
# =========================
st.subheader(f"Data Operan - {selected_unit}")

query_unit = """
SELECT * FROM operan
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
