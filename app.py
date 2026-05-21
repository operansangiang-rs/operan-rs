import streamlit as st
import sqlite3
import pandas as pd

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
# DATABASE
# =========================
conn = sqlite3.connect(
    "operan.db",
    check_same_thread=False
)

c = conn.cursor()

# =========================
# OPTIMASI SQLITE
# =========================
c.execute("PRAGMA journal_mode=WAL;")
c.execute("PRAGMA synchronous=NORMAL;")

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
    operan TEXT
)
""")

conn.commit()

# =========================
# AUTO DELETE > 40 HARI
# =========================
try:

    c.execute("""
    DELETE FROM operan
    WHERE date(tanggal) <= date('now', '-40 day')
    """)

    conn.commit()

except Exception as e:

    st.warning(
        f"Auto delete error: {e}"
    )

# =========================
# LIST UNIT
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

# =========================
# SIDEBAR
# =========================
st.sidebar.title("🏥 Pilih Unit")

selected_unit = st.sidebar.selectbox(
    "Unit",
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
# FORM INPUT
# =========================
st.subheader(
    f"📝 Input Operan - {selected_unit}"
)

with st.form("form_operan"):

    col1, col2 = st.columns(2)

    with col1:

        tanggal = st.date_input(
            "Tanggal"
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
# DATA OPERAN PER UNIT
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
    f"Total data {selected_unit}: {len(unit_df)}"
)


# =========================
# ADMIN DATABASE VIEWER
# =========================
st.divider()

with st.expander("🗄️ Lihat Database"):

    all_data = pd.read_sql_query(
        """
        SELECT *
        FROM operan
        ORDER BY id DESC
        """,
        conn
    )

    st.dataframe(
        all_data,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        f"Total seluruh data: {len(all_data)}"
    )

# =========================
# DOWNLOAD DATABASE
# =========================
try:

    with open("operan.db", "rb") as file:

        st.download_button(
            label="⬇️ Download Database",
            data=file,
            file_name="operan.db",
            mime="application/octet-stream"
        )

except Exception as e:

    st.warning(
        f"Gagal download database: {e}"
    )
