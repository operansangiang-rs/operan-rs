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
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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

# Auto Delete data lama (>15 hari)
try:
    c.execute("DELETE FROM operan WHERE julianday('now') - julianday(tanggal) > 15")
    conn.commit()
except Exception as e:
    print("Auto delete error:", e)

# Pembuatan Table
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
# DIALOG UNTUK EDIT DATA (Lebih Aman & Presisi)
# =========================
@st.dialog("✏️ Edit Data Operan")
def edit_dialog(row_data):
    st.write(f"Pasien: **{row_data['nama_pasien']}** ({row_data['no_rm']})")
    new_operan = st.text_area("Isi Operan Baru", value=row_data['operan'], height=150)
    user_edit = st.text_input("Nama Pengedit / PJ Baru", value=row_data['pj_operan'])
    
    if st.button("Simpan Perubahan"):
        if new_operan.strip() and user_edit.strip():
            waktu_sekarang = datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S")
            c.execute("""
                UPDATE operan 
                SET operan = ?, edited_by = ?, edited_at = ?, pj_operan = ? 
                WHERE id = ?
            """, (new_operan, user_edit, waktu_sekarang, user_edit, row_data['id']))
            conn.commit()
            st.success("Data berhasil diperbarui!")
            st.rerun()
        else:
            st.error("Semua kolom harus diisi!")

# =========================
# SEARCH
# =========================
st.subheader("🔎 Cari Pasien (Semua Unit)")
search = st.text_input("Cari No RM / Nama")

if len(search) >= 3:
    df_search = pd.read_sql_query("""
        SELECT tanggal, unit, shift, no_rm, nama_pasien, kamar, diagnosa, operan, pj_operan 
        FROM operan
        WHERE no_rm LIKE ? OR nama_pasien LIKE ?
        ORDER BY id DESC LIMIT 50
    """, conn, params=(f"%{search}%", f"%{search}%"))
    st.dataframe(df_search, use_container_width=True)

st.divider()

# =========================
# INPUT FORM
# =========================
st.subheader(f"📝 Input Operan - {selected_unit}")
with st.form("form_input", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        waktu_input = datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S")
        st.text_input("Tanggal", value=waktu_input, disabled=True)
        st.text_input("Shift", value=auto_shift, disabled=True)
        no_rm = st.text_input("No RM")
        nama_pasien = st.text_input("Nama Pasien")
    with col2:
        kamar = st.text_input("Kamar / Bed")
        diagnosa = st.text_input("Diagnosa Medis")
        pj_operan = st.text_input("PJ Penyerah Operan")
        
    operan = st.text_area("Isi Instruksi / Catatan Operan", height=130, max_chars=1500)
    submit = st.form_submit_button("Simpan Data")

if submit:
    # Validasi ketat agar tidak ada data kosong yang krusial
    if not (no_rm and nama_pasien and kamar and diagnosa and operan and pj_operan):
        st.error("❌ Gagal menyimpan! Semua kolom wajib diisi demi keselamatan pasien.")
    else:
        c.execute("""
            INSERT INTO operan (tanggal, unit, shift, no_rm, nama_pasien, kamar, diagnosa, operan, pj_operan)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (waktu_input, selected_unit, auto_shift, no_rm, nama_pasien, kamar, diagnosa, operan, pj_operan))
        conn.commit()
        st.success("✅ Data operan berhasil disimpan!")
        st.rerun()

# =========================
# DATA LIST
# =========================
st.subheader(f"📋 Data Operan Aktif (7 Hari Terakhir) - {selected_unit}")
df = pd.read_sql_query("""
    SELECT * FROM operan 
    WHERE unit = ? AND julianday('now') - julianday(tanggal) <= 7
    ORDER BY id DESC
""", conn, params=(selected_unit,))

if df.empty:
    st.info("Belum ada data operan untuk unit ini dalam 7 hari terakhir.")
else:
    for _, r in df.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"📅 **Tanggal:** {r['tanggal']}")
            c2.markdown(f"⏱ **Shift:** {r['shift']}")
            c3.markdown(f"🏥 **No RM:** {r['no_rm']}")
            c4.markdown(f"👤 **Pasien:** {r['nama_pasien']}")
            
            st.markdown(f"🏠 **Kamar:** {r['kamar']} | 🧾 **Diagnosa:** {r['diagnosa']} | 👨‍⚕️ **PJ:** {r['pj_operan']}")
            
            # Tombol Aksi yang Jauh Lebih Rapi
            cA, cB, cC = st.columns([1, 1, 4])
            
            with cA:
                # Toggle detail langsung memanfaatkan ekspander bawaan agar UI bersih
                with st.expander("📄 Lihat Catatan"):
                    st.info(r['operan'])
                    if r['edited_by']:
                        st.caption(f"✏️ Diubah oleh: {r['edited_by']} ({r['edited_at']})")
            with cB:
                if st.button("✏️ Edit", key=f"btn_edit_{r['id']}"):
                    edit_dialog(r)
            with cC:
                if st.button("🗑 Hapus", key=f"btn_del_{r['id']}"):
                    st.session_state[f"confirm_del_{r['id']}"] = True
            
            # Konfirmasi hapus per baris yang stabil
            if st.session_state.get(f"confirm_del_{r['id']}", False):
                st.error(f"Apakah Anda yakin ingin menghapus data {r['nama_pasien']}?")
                cx, cy = st.columns([1, 5])
                if cx.button("Ya, Hapus", key=f"yes_del_{r['id']}"):
                    c.execute("DELETE FROM operan WHERE id=?", (r['id'],))
                    conn.commit()
                    del st.session_state[f"confirm_del_{r['id']}"]
                    st.rerun()
                if cy.button("Batal", key=f"no_del_{r['id']}"):
                    del st.session_state[f"confirm_del_{r['id']}"]
                    st.rerun()

# =========================
# PDF EXPORT (Perbaikan Wrap Text)
# =========================
st.divider()
st.subheader("⬇️ Rekap Cetak PDF")

col_d1, col_d2 = st.columns(2)
with col_d1:
    start_date = st.date_input("Mulai Tanggal")
with col_d2:
    end_date = st.date_input("Sampai Tanggal")

pdf_df = pd.read_sql_query("""
    SELECT tanggal, shift, no_rm, nama_pasien, kamar, diagnosa, operan, pj_operan
    FROM operan
    WHERE unit = ? AND tanggal BETWEEN ? AND ?
    ORDER BY tanggal ASC
""", conn, params=(selected_unit, f"{start_date} 00:00:00", f"{end_date} 23:59:59"))

def generate_pdf(dataframe):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(A4),
        rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20
    )
    styles = getSampleStyleSheet()
    
    # Custom Style khusus untuk isi tabel agar teks otomatis turun ke bawah (Wrap)
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontSize=7,
        leading=9
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.whitesmoke,
        fontName="Helvetica-Bold"
    )

    elements = []
    elements.append(Paragraph(f"<b>LOG OPERAN SHIFT - RS SARI ASIH SANGIANG</b>", styles["Title"]))
    elements.append(Paragraph(f"Unit: {selected_unit} | Periode: {start_date} s/d {end_date}", styles["Heading3"]))
    elements.append(Spacer(1, 15))

    # Judul Kolom yang Manusiawi
    headers = ["Tanggal", "Shift", "No RM", "Nama Pasien", "Kamar", "Diagnosa", "Catatan Operan", "PJ"]
    data = [[Paragraph(f"<b>{h}</b>", header_style) for h in headers]]

    # Memasukkan data dan membungkusnya dengan Paragraph agar wrap-text berfungsi
    for row in dataframe.values.tolist():
        formatted_row = [Paragraph(str(cell), cell_style) for cell in row]
        data.append(formatted_row)

    # Set proporsi lebar kolom (Total lebar kertas A4 Landscape setelah margin sekitar 792 pt)
    # Kita berikan porsi terbesar untuk kolom Catatan Operan (kolom ke-7)
    col_widths = [75, 35, 45, 95, 45, 95, 320, 50]
    
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1A365D")), # Warna biru gelap medis
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))

    elements.append(table)
    doc.build(elements)
    return buffer.getvalue()

if not pdf_df.empty:
    st.download_button(
        label="Download PDF Terfilter",
        data=generate_pdf(pdf_df),
        file_name=f"Operan_{selected_unit}_{start_date}_to_{end_date}.pdf",
        mime="application/pdf"
    )
else:
    st.warning("Tidak ditemukan data pada rentang tanggal tersebut untuk dicetak.")

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
