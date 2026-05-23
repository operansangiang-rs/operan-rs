import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import pytz
import time  # Ditambahkan untuk jeda notifikasi sukses

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
# DB CONNECTION
# =========================
@st.cache_resource
def conn_db():
    conn = sqlite3.connect("operan.db", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

conn = conn_db()
c = conn.cursor()

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

# AUTO MIGRATION: Pengaman Data Lama agar tidak bentrok/crash
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
    "RPU LT 4","RPA LT 5","Hemodialisa","Kamar Operasi",
    "IGD","NICU","PICU"
]

st.sidebar.title("🏥 Pilih Unit")
selected_unit = st.sidebar.selectbox("Unit", unit_list)


# ==========================================
# 🛠️ TOMBOL BACKUP MANUAL 40 HARI (DI SIDEBAR)
# ==========================================
st.sidebar.divider()
st.sidebar.write("🛠️ **Menu Admin / Backup**")

hari_ini = datetime.now(jakarta)
tanggal_40_hari_lalu = (hari_ini - timedelta(days=40)).strftime("%Y-%m-%d") + " 00:00:00"
tanggal_sekarang_str = hari_ini.strftime("%Y-%m-%d") + " 23:59:59"

tgl_file_mulai = (hari_ini - timedelta(days=40)).strftime("%Y-%m-%d")
tgl_file_selesai = hari_ini.strftime("%Y-%m-%d")

try:
    c.execute("""
        SELECT * FROM operan 
        WHERE tanggal BETWEEN ? AND ?
    """, (tanggal_40_hari_lalu, tanggal_sekarang_str))
    backup_rows = c.fetchall()
    
    c.execute("PRAGMA table_info(operan)")
    columns_info = c.fetchall()
    
    if backup_rows:
        temp_filename = "temp_backup.db"
        
        mem_conn = sqlite3.connect(temp_filename)
        mem_c = mem_conn.cursor()
        
        create_table_sql = "CREATE TABLE IF NOT EXISTS operan (" + ", ".join([f"{col[1]} {col[2]}" for col in columns_info]) + ")"
        mem_c.execute(create_table_sql)
        
        mem_c.execute("DELETE FROM operan")
        
        placeholders = ", ".join(["?"] * len(columns_info))
        mem_c.executemany(f"INSERT INTO operan VALUES ({placeholders})", backup_rows)
        mem_conn.commit()
        mem_conn.close()
        
        with open(temp_filename, "rb") as f:
            db_bytes = f.read()
            
        st.sidebar.download_button(
            label="💾 Backup DB (40 Hari Terakhir)",
            data=db_bytes,
            file_name=f"backup_operan_RS_{tgl_file_mulai}_sampai_{tgl_file_selesai}.db",
            mime="application/octet-stream",
            help="Klik untuk mengunduh database seluruh unit khusus 40 hari terakhir saja.",
            use_container_width=True
        )
    else:
        st.sidebar.info("Belum ada data dalam 40 hari terakhir.")
        
except Exception as error_backup:
    st.sidebar.error(f"Gagal menyiapkan backup: {error_backup}")

st.sidebar.divider()

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

# ========================================================
# FUNGSI KELOLA DATA & PROTEKSI 2 HARI (VERSI LIPAT)
# ========================================================
def render_timeline_operan(dataframe, context_key="main"):
    """Fungsi bersama untuk menggambar timeline operan dengan riwayat yang bisa dilipat"""
    waktu_sekarang = datetime.now(jakarta)
    
    # Memakai expander supaya riwayatnya bisa dilipat-buka
    with st.expander("📜 Lihat Detail Riwayat Operan Shift Pasien Ini", expanded=False):
        for _, r in dataframe.iterrows():
            avatar_style = "user" if r['shift'] == "Pagi" else "assistant"
            with st.chat_message(avatar_style):
                st.markdown(f"⏱ **Shift {r['shift']}** | 📅 {r['tanggal']} | 👨‍⚕️ PJ: *{r['pj_operan']}*")
                st.markdown(f"**Unit:** {r['unit']} | 🩺 **Diagnosa/Konsul:** {r['diagnosa']}")
                st.info(f"💬 {r['operan']}")
                
                if r['edited_by']:
                    st.caption(f"✏️ Terakhir diubah oleh: {r['edited_by']} ({r['edited_at']})")
                
                # Cek Masa Kedaluwarsa Edit (Max 2 Hari / 48 Jam)
                try:
                    tgl_input = datetime.strptime(r['tanggal'], "%Y-%m-%d %H:%M:%S")
                    tgl_input = jakarta.localize(tgl_input)
                    bisa_edit = (waktu_sekarang - tgl_input) <= timedelta(days=2)
                except:
                    bisa_edit = False 
                    
                if bisa_edit:
                    cA, cB = st.columns([1, 8])
                    with cA:
                        if st.button("✏️ Edit", key=f"btn_edit_{context_key}_{r['id']}"):
                            edit_dialog(r)
                    with cB:
                        if st.button("🗑 Hapus", key=f"btn_del_{context_key}_{r['id']}"):
                            st.session_state[f"confirm_del_{context_key}_{r['id']}"] = True
                            
                    if st.session_state.get(f"confirm_del_{context_key}_{r['id']}", False):
                        st.error("Apakah Anda yakin ingin menghapus catatan instruksi spesifik ini?")
                        cx, cy = st.columns([1, 10])
                        if cx.button("Ya, Hapus", key=f"yes_del_{context_key}_{r['id']}"):
                            c.execute("DELETE FROM operan WHERE id=?", (r['id'],))
                            conn.commit()
                            del st.session_state[f"confirm_del_{context_key}_{r['id']}"]
                            st.rerun()
                        if cy.button("Batal", key=f"no_del_{context_key}_{r['id']}"):
                            del st.session_state[f"confirm_del_{context_key}_{r['id']}"]
                            st.rerun()
                else:
                    st.caption("🔒 *Catatan ini telah dikunci (Sudah melewati batas waktu toleransi edit 2 hari).*")

# ========================================================
# 🔎 SEARCH OPTIMIZATION & TAMBAH OPERAN INSTAN (FITUR BARU)
# ========================================================
st.subheader("🔎 Cari Pasien / Kamar & Tambah Operan Cepat")
st.markdown("<p style='font-size:14px; color:#555;'>Ketik No RM, Nama Pasien, atau Nomor Kamar untuk melihat riwayat atau <b>menambah operan shift baru tanpa perlu mengetik ulang identitas pasien!</b></p>", unsafe_allow_html=True)

search = st.text_input(
    "Masukkan No RM / Nama Pasien / Nomor Kamar", 
    placeholder="Contoh: 123456, Ahmad, atau Kamar 302..."
)

if len(search.strip()) >= 2:
    # Query untuk mencari berdasarkan No RM, Nama, atau Kamar
    df_search = pd.read_sql_query("""
        SELECT * FROM operan
        WHERE no_rm LIKE ? OR nama_pasien LIKE ? OR kamar LIKE ?
        ORDER BY tanggal DESC LIMIT 60
    """, conn, params=(f"%{search}%", f"%{search}%", f"%{search}%"))
    
    if not df_search.empty:
        search_pasien_unik = df_search['no_rm'].unique()
        st.success(f"📌 Ditemukan {len(search_pasien_unik)} pasien yang cocok dengan kata kunci '{search}'.")
        
        for rm in search_pasien_unik:
            df_s_pasien = df_search[df_search['no_rm'] == rm]
            info_terbaru = df_s_pasien.iloc[0]
            val_penjamin = info_terbaru['penjamin'] if pd.notna(info_terbaru['penjamin']) else "Umum"
            badge_penjamin = "🟢 BPJS" if val_penjamin == "BPJS" else "🔵 " + str(val_penjamin)
            
            # Box per pasien
            with st.container(border=True):
                col_s1, col_s2, col_s3, col_s4 = st.columns([1.2, 2, 1.2, 1])
                col_s1.markdown(f"🏥 **No RM:** {info_terbaru['no_rm']}")
                col_s2.markdown(f"👤 **Nama Pasien:** {info_terbaru['nama_pasien']}")
                col_s3.markdown(f"💳 **Penjamin:** {badge_penjamin}")
                col_s4.markdown(f"🏠 **Kamar:** {info_terbaru['kamar']}")
                
                # FORM INSTAN UNTUK MEMASUKKAN OPERAN BARU
                with st.expander(f"➕ **Tambah Catatan Shift Baru untuk {info_terbaru['nama_pasien']}**", expanded=False):
                    with st.form(key=f"quick_form_{info_terbaru['no_rm']}", clear_on_submit=True):
                        st.markdown(f"**Unit Aktif:** {selected_unit} | **Shift Saat Ini:** {auto_shift}")
                        
                        col_f1, col_f2 = st.columns(2)
                        with col_f1:
                            q_kamar = st.text_input("Konfirmasi/Ubah Kamar", value=info_terbaru['kamar'], key=f"q_kmr_{info_terbaru['no_rm']}")
                            q_pj = st.text_input("PJ Penyerah Operan", key=f"q_pj_{info_terbaru['no_rm']}")
                        with col_f2:
                            q_diagnosa = st.text_input("Diagnosa Medis / Konsul Spesialis", value=info_terbaru['diagnosa'], key=f"q_dg_{info_terbaru['no_rm']}")
                        
                        q_operan = st.text_area("Isi Instruksi / Catatan Operan Baru", height=100, key=f"q_op_{info_terbaru['no_rm']}", placeholder="Tulis instruksi kelanjutan di sini...")
                        
                        submit_quick = st.form_submit_button("Simpan Operan Baru")
                        
                        if submit_quick:
                            if not (q_operan.strip() and q_pj.strip() and q_kamar.strip() and q_diagnosa.strip()):
                                st.error("❌ Gagal menyimpan! Catatan Operan, PJ, Kamar, dan Diagnosa wajib diisi.")
                            else:
                                waktu_quick = datetime.now(jakarta).strftime("%Y-%m-%d %H:%M:%S")
                                c.execute("""
                                    INSERT INTO operan (tanggal, unit, shift, no_rm, nama_pasien, kamar, diagnosa, operan, pj_operan, penjamin)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (waktu_quick, selected_unit, auto_shift, info_terbaru['no_rm'], info_terbaru['nama_pasien'], q_kamar.strip(), q_diagnosa.strip(), q_operan.strip(), q_pj.strip(), val_penjamin))
                                conn.commit()
                                
                                # Tampilkan notifikasi sukses yang mantap
                                st.success(f"🎉 Berhasil! Operan baru untuk {info_terbaru['nama_pasien']} telah tersimpan ke database.")
                                st.toast(f"✅ Operan {info_terbaru['nama_pasien']} disimpan!", icon="🟢")
                                
                                time.sleep(1.2)  # Jeda biar perawat sempat baca
                                st.rerun()
                
                # Riwayat operan lama yang sudah bisa dilipat
                render_timeline_operan(df_s_pasien, context_key=f"src_{info_terbaru['no_rm']}")
    else:
        st.info("Tidak ditemukan data pasien atau kamar dengan kata kunci tersebut.")

st.divider()

# =========================
# INPUT FORM (Untuk Pasien Baru)
# =========================
st.subheader(f"📝 Input Operan Pasien Baru - {selected_unit}")
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
        
    operan = st.text_area("Isi Instruksi / Catatan Operan", height=130, max_chars=1500, placeholder="Gunakan format global untuk ICU / HD...")
    submit = st.form_submit_button("Simpan Data")

if submit:
    if not (no_rm.strip() and nama_pasien.strip() and kamar.strip() and diagnosa.strip() and operan.strip() and pj_operan.strip()):
        st.error("❌ Gagal menyimpan! Semua kolom wajib diisi demi keselamatan dan ketepatan operan pasien.")
    else:
        c.execute("""
            INSERT INTO operan (tanggal, unit, shift, no_rm, nama_pasien, kamar, diagnosa, operan, pj_operan, penjamin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (waktu_input, selected_unit, auto_shift, no_rm.strip(), nama_pasien.strip(), kamar.strip(), diagnosa.strip(), operan.strip(), pj_operan.strip(), penjamin))
        conn.commit()
        
        # Notifikasi Sukses Form Manual
        st.success(f"🎉 Pasien Baru Berhasil Ditambahkan! Data operan {nama_pasien.strip()} telah disimpan.")
        st.toast("✅ Data operan berhasil disimpan!", icon="🟢")
        
        time.sleep(1.2)
        st.rerun()

# =========================
# DATA LIST (2 Hari Terakhir)
# =========================
st.subheader(f"📋 Data Operan Aktif (2 Hari Terakhir) - {selected_unit}")
df = pd.read_sql_query("""
    SELECT * FROM operan 
    WHERE unit = ? AND julianday('now', 'localtime') - julianday(tanggal) <= 2
    ORDER BY tanggal DESC
""", conn, params=(selected_unit,))

if df.empty:
    st.info("Belum ada data operan aktif untuk unit ini dalam 2 hari terakhir.")
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
            
            # Memanggil fungsi timeline versi lipat (hanya ambil maks 3 data teratas)
            render_timeline_operan(df_pasien.head(3), context_key="main")

# =========================
# PDF EXPORT & STATISTIK
# =========================
st.divider()
st.subheader("⬇️ Rekap Cetak PDF & Analisis Data Periode")

col_d1, col_d2 = st.columns(2)
with col_d1:
    start_date = st.date_input("Mulai Tanggal")
with col_d2:
    end_date = st.date_input("Sampai Tanggal")

start_str = start_date.strftime("%Y-%m-%d") + " 00:00:00"
end_str = end_date.strftime("%Y-%m-%d") + " 23:59:59"

pdf_df = pd.read_sql_query("""
    SELECT tanggal, shift, no_rm, nama_pasien, penjamin, kamar, diagnosa, operan, pj_operan
    FROM operan
    WHERE unit = ? AND tanggal BETWEEN ? AND ?
    ORDER BY tanggal ASC
""", conn, params=(selected_unit, start_str, end_str))

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

if not pdf_df.empty:
    st.info("""
    ⚠️ **Pemberitahuan Sistem:** Demi keamanan data rekam medis pada server gratisan, Kepala Ruangan / PJ Shift **WAJIB** mengunduh rekap PDF ini **setiap 1 bulan sekali** (di akhir bulan) untuk disimpan sebagai arsip internal unit.
    """)
    
    st.download_button(
        label="📄 Download Rekap PDF Terfilter",
        data=generate_pdf(pdf_df),
        file_name=f"Operan_{selected_unit}_{start_date}_to_{end_date}.pdf",
        mime="application/pdf"
    )
    
    st.write("")
    with st.expander("📊 Lihat Ringkasan Statistik & Grafik Pasien Terfilter", expanded=False):
        pdf_df['penjamin'] = pdf_df['penjamin'].fillna('Umum').replace('', 'Umum')
        df_pasien_unik = pdf_df.drop_duplicates(subset=['no_rm'])
        total_pasien_periode = len(df_pasien_unik)
        
        counts = df_pasien_unik['penjamin'].value_counts()
        total_bpjs = counts.get('BPJS', 0)
        total_umum = counts.get('Umum', 0)
        total_asuransi = counts.get('Asuransi Swasta / Perusahaan', 0)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(label="👥 Total Pasien Unik", value=f"{total_pasien_periode} Orang")
        m2.metric(label="🟢 Total BPJS", value=f"{total_bpjs} Pasien")
        m3.metric(label="🔵 Total Umum", value=f"{total_umum} Pasien")
        m4.metric(label="🟠 Total Asuransi Swasta / Perusahaan", value=f"{total_asuransi} Pasien")
        
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
else:
    st.info("Tidak ada data operan yang terekam pada rentang tanggal terpilih.")

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
