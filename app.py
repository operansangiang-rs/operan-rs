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

# Auto Delete data lama (>180 hari / 6 bulan secara bertahap) & Indexing Efisiensi
try:
    c.execute("""
        DELETE FROM operan 
        WHERE julianday('now', 'localtime') - julianday(tanggal) > 180
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_tanggal ON operan(tanggal);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_unit ON operan(unit);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_no_rm ON operan(no_rm);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_nama ON operan(nama_pasien);")
    conn.commit()
except Exception as e:
    print("Auto delete / indexing error:", e)

# Pembuatan Table Awal jika belum ada
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
    edited_at TEXT,
    penjamin TEXT
)
""")
conn.commit()

# 🛠️ AUTO MIGRATION: Pengaman Data Lama Mas Lian agar tidak bentrok/crash
try:
    c.execute("PRAGMA table_info(operan)")
    columns = [column[1] for column in c.fetchall()]
    if "penjamin" not in columns:
        c.execute("ALTER TABLE operan ADD COLUMN penjamin TEXT DEFAULT 'Umum'")
        conn.commit()
except Exception as e:
    print("Migration Error:", e)

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
# DIALOG UNTUK EDIT DATA
# =========================
@st.dialog("✏️ Edit Data Operan")
def edit_dialog(row_data):
    st.write(f"Pasien: **{row_data['nama_pasien']}** ({row_data['no_rm']})")
    
    list_penjamin = ["BPJS", "Umum", "Asuransi Swasta / Perusahaan"]
    current_penjamin = row_data['penjamin'] if pd.notna(row_data['penjamin']) else "Umum"
    default_idx = list_penjamin.index(current_penjamin) if current_penjamin in list_penjamin else 1
    new_penjamin = st.selectbox("Jenis Penjamin", list_penjamin, index=default_idx)
    
    new_kamar = st.text_input("Kamar / Bed", value=row_data['kamar'])
    new_diagnosa = st.text_input("Diagnosa / Spesialis", value=row_data['diagnosa'])
    new_operan = st.text_area("Isi Operan Baru", value=row_data['operan'], height=150)
    user_edit = st.text_input("Nama Pengedit / PJ Baru", value=row_data['pj_operan'])
    
    if st.button("Simpan Perubahan"):
        if new_operan.strip() and user_edit.strip() and new_kamar.strip() and new_diagnosa.strip():
            waktu_sekarang = datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S")
            c.execute("""
                UPDATE operan 
                SET operan = ?, edited_by = ?, edited_at = ?, pj_operan = ?, penjamin = ?, kamar = ?, diagnosa = ?
                WHERE id = ?
            """, (new_operan, user_edit, waktu_sekarang, user_edit, new_penjamin, new_kamar, new_diagnosa, row_data['id']))
            conn.commit()
            st.success("Data berhasil diperbarui!")
            st.rerun()
        else:
            st.error("Semua kolom harus diisi!")

# =========================
# SEARCH (Arsip 6 Bulan Terakhir)
# =========================
st.subheader("🔎 Cari Riwayat Pasien")
search = st.text_input("Masukkan No RM / Nama Pasien", placeholder="Cari data (maksimal riwayat 6 bulan terakhir)...")

if len(search) >= 3:
    df_search = pd.read_sql_query("""
        SELECT tanggal, unit, shift, no_rm, nama_pasien, penjamin, kamar, diagnosa, operan, pj_operan 
        FROM operan
        WHERE no_rm LIKE ? OR nama_pasien LIKE ?
        ORDER BY tanggal DESC LIMIT 50
    """, conn, params=(f"%{search}%", f"%{search}%"))
    if not df_search.empty:
        st.dataframe(df_search, use_container_width=True)
    else:
        st.info("Tidak ditemukan riwayat kunjungan pasien dengan kata kunci tersebut.")

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
        penjamin = st.selectbox("Jenis Penjamin / Pembiayaan", ["BPJS", "Umum", "Asuransi Swasta / Perusahaan"])
        
    with col2:
        kamar = st.text_input("Kamar / Bed")
        diagnosa = st.text_input("Diagnosa Medis / Konsul Spesialis (e.g., Sp.PD / Sp.B)")
        pj_operan = st.text_input("PJ Penyerah Operan")
        
    operan = st.text_area("Isi Instruksi / Catatan Operan", height=130, max_chars=1500)
    submit = st.form_submit_button("Simpan Data")

if submit:
    if not (no_rm and nama_pasien and kamar and diagnosa and operan and pj_operan):
        st.error("❌ Gagal menyimpan! Semua kolom wajib diisi demi keselamatan dan ketepatan operan pasien.")
    else:
        c.execute("""
            INSERT INTO operan (tanggal, unit, shift, no_rm, nama_pasien, kamar, diagnosa, operan, pj_operan, penjamin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (waktu_input, selected_unit, auto_shift, no_rm, nama_pasien, kamar, diagnosa, operan, pj_operan, penjamin))
        conn.commit()
        st.success("✅ Data operan berhasil disimpan!")
        st.rerun()

# =========================
# DATA LIST (Tampilan Terkunci 7 Hari & Dikelompokkan per Pasien)
# =========================
st.subheader(f"📋 Data Operan Aktif (7 Hari Terakhir) - {selected_unit}")
df = pd.read_sql_query("""
    SELECT * FROM operan 
    WHERE unit = ? AND julianday('now', 'localtime') - julianday(tanggal) <= 7
    ORDER BY tanggal DESC
""", conn, params=(selected_unit,))

if df.empty:
    st.info("Belum ada data operan aktif untuk unit ini dalam 7 hari terakhir.")
else:
    pasien_unik = df['no_rm'].unique()
    
    for rm in pasien_unik:
        df_pasien = df[df['no_rm'] == rm]
        info_terbaru = df_pasien.iloc[0]
        
        val_penjamin = info_terbaru['penjamin'] if pd.notna(info_terbaru['penjamin']) else "Umum"
        badge_penjamin = "🟢 BPJS" if val_penjamin == "BPJS" else "🔵 " + str(val_penjamin)
        
        with st.container(border=True):
            col_p1, col_p2, col_p3, col_p4 = st.columns([1.2, 2, 1.2, 1])
            col_p1.markdown(f"🏥 **No RM:** {info_terbaru['no_rm']}")
            col_p2.markdown(f"👤 **Nama Pasien:** {info_terbaru['nama_pasien']}")
            col_p3.markdown(f"💳 **Penjamin:** {badge_penjamin}")
            col_p4.markdown(f"🏠 **Kamar:** {info_terbaru['kamar']}")
            
            st.markdown("<p style='margin:2px 0px; color:#777; font-size:13px;'><b>🩺 Timeline Instruksi Medis & Operan Shift:</b></p>", unsafe_allow_html=True)
            
            for _, r in df_pasien.iterrows():
                avatar_style = "user" if r['shift'] == "Pagi" else "assistant"
                with st.chat_message(avatar_style):
                    st.markdown(f"⏱ **Shift {r['shift']}** | 📅 {r['tanggal']} | 👨‍⚕️ PJ: *{r['pj_operan']}*")
                    st.markdown(f"🩺 **Diagnosa/Konsul:** {r['diagnosa']}")
                    st.info(f"💬 {r['operan']}")
                    
                    if r['edited_by']:
                        st.caption(f"✏️ Terakhir diubah oleh: {r['edited_by']} ({r['edited_at']})")
                        
                    cA, cB = st.columns([1, 8])
                    with cA:
                        if st.button("✏️ Edit", key=f"btn_edit_{r['id']}"):
                            edit_dialog(r)
                    with cB:
                        if st.button("🗑 Hapus", key=f"btn_del_{r['id']}"):
                            st.session_state[f"confirm_del_{r['id']}"] = True
                            
                    if st.session_state.get(f"confirm_del_{r['id']}", False):
                        st.error("Apakah Anda yakin ingin menghapus catatan instruksi spesifik ini?")
                        cx, cy = st.columns([1, 10])
                        if cx.button("Ya, Hapus", key=f"yes_del_{r['id']}"):
                            c.execute("DELETE FROM operan WHERE id=?", (r['id'],))
                            conn.commit()
                            del st.session_state[f"confirm_del_{r['id']}"]
                            st.rerun()
                        if cy.button("Batal", key=f"no_del_{r['id']}"):
                            del st.session_state[f"confirm_del_{r['id']}"]
                            st.rerun()

# =========================
# PDF EXPORT & STATISTIK REKAP PERIODE
# =========================
st.divider()
st.subheader("⬇️ Rekap Cetak PDF & Analisis Data Periode")

col_d1, col_d2 = st.columns(2)
with col_d1:
    start_date = st.date_input("Mulai Tanggal")
with col_d2:
    end_date = st.date_input("Sampai Tanggal")

# Ambil data lengkap untuk cetak PDF
pdf_df = pd.read_sql_query("""
    SELECT tanggal, shift, no_rm, nama_pasien, penjamin, kamar, diagnosa, operan, pj_operan
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
    
    cell_style = ParagraphStyle(
        'CellText', parent=styles['Normal'], fontSize=7, leading=9
    )
    header_style = ParagraphStyle(
        'HeaderStyle', parent=styles['Normal'], fontSize=8, textColor=colors.whitesmoke, fontName="Helvetica-Bold"
    )

    elements = []
    elements.append(Paragraph(f"<b>LOG OPERAN SHIFT - RS SARI ASIH SANGIANG</b>", styles["Title"]))
    elements.append(Paragraph(f"Unit: {selected_unit} | Periode: {start_date} s/d {end_date}", styles["Heading3"]))
    elements.append(Spacer(1, 15))

    headers = ["Tanggal", "Shift", "No RM", "Nama Pasien", "Penjamin", "Kamar", "Diagnosa", "Catatan Operan", "PJ"]
    data = [[Paragraph(f"<b>{h}</b>", header_style) for h in headers]]

    for row in dataframe.values.tolist():
        formatted_row = [Paragraph(str(cell), cell_style) for cell in row]
        data.append(formatted_row)

    col_widths = [75, 35, 45, 95, 55, 45, 90, 260, 50]
    
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1A365D")), 
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))

    elements.append(table)
    doc.build(elements)
    return buffer.getvalue()

# Tombol Cetak PDF Utama
if not pdf_df.empty:
    st.download_button(
        label="📄 Download Rekap PDF Terfilter",
        data=generate_pdf(pdf_df),
        file_name=f"Operan_{selected_unit}_{start_date}_to_{end_date}.pdf",
        mime="application/pdf"
    )
    
    # 📊 SEKSI TAMBAHAN: MENGGUNAKAN EXPANDER AGAR LAYAR TETAP RAPI (MODEL LIPAT)
    st.write("")
    with st.expander("📊 Lihat Ringkasan Statistik & Grafik Pasien Terfilter", expanded=False):
        
        # Mengisi data penjamin kosong ke 'Umum' demi konsistensi grafik
        pdf_df['penjamin'] = pdf_df['penjamin'].fillna('Umum').replace('', 'Umum')
        
        # Menghitung pasien unik (berdasarkan No RM) untuk akurasi jumlah pasien asli
        df_pasien_unik = pdf_df.drop_duplicates(subset=['no_rm'])
        total_pasien_periode = len(df_pasien_unik)
        
        # Hitung distribusi penjamin dari list pasien unik
        counts = df_pasien_unik['penjamin'].value_counts()
        total_bpjs = counts.get('BPJS', 0)
        total_umum = counts.get('Umum', 0)
        total_asuransi = counts.get('Asuransi Swasta / Perusahaan', 0)
        
        # Tampilan kartu angka (Metric Card)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(label="👥 Total Pasien Unik", value=f"{total_pasien_periode} Orang")
        m2.metric(label="🟢 Total BPJS", value=f"{total_bpjs} Pasien")
        m3.metric(label="🔵 Total Umum", value=f"{total_umum} Pasien")
        m4.metric(label="🟠 Total Asuransi Swasta / Perusahaan", value=f"{total_asuransi} Pasien")
        
        # Tampilan Grafik Visual Berdampingan
        st.write("")
        g1, g2 = st.columns([2, 1])
        
        with g1:
            st.markdown("**Grafik Distribusi Penjamin Pasien (Bar Chart)**")
            chart_data = pd.DataFrame({
                'Jenis Penjamin': counts.index,
                'Jumlah Pasien': counts.values
            }).set_index('Jenis Penjamin')
            
            st.bar_chart(chart_data, color="#1A365D")
            
        with g2:
            st.markdown("**Tabel Rincian Persentase**")
            rekap_tabel = pd.DataFrame({
                'Penjamin': counts.index,
                'Total Pasien': counts.values,
                'Persentase (%)': ((counts.values / total_pasien_periode) * 100).round(1)
            })
            st.dataframe(rekap_tabel, use_container_width=True, hide_index=True)

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
