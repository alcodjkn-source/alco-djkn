# =============================================
# ALCo DJKN – Streamlit App (Versi Lengkap)
# =============================================
import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import plotly.express as px
import json, gspread
from gspread_dataframe import get_as_dataframe
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="ALCo DJKN", layout="wide")
GSHEET_NAME = "ALCo_Data"

# =====================================================
# AUTENTIKASI GOOGLE SHEETS
# =====================================================
st.sidebar.header("Konfigurasi")

service_account_info = None
json_keyfile_path = None

try:
    service_account_info = st.secrets["gcp_service_account"]
    st.sidebar.success("✅ Credentials otomatis terdeteksi dari Streamlit Secrets.")
except Exception:
    st.sidebar.warning("⚠️ Tidak ada credentials di Streamlit Secrets. Upload/paste manual.")
    auth_method = st.sidebar.radio("Auth Google Sheets:", ["Upload JSON", "Paste JSON"])
    if auth_method == "Upload JSON":
        uploaded = st.sidebar.file_uploader("Upload service_account.json", type=["json"])
        if uploaded:
            json_keyfile_path = "service_account.json"
            with open(json_keyfile_path, "wb") as f:
                f.write(uploaded.getbuffer())
    else:
        secret_json = st.sidebar.text_area("Paste JSON credentials", height=200)
        if secret_json:
            service_account_info = json.loads(secret_json)

def gs_connect(service_account_info=None, json_keyfile_path=None):
    """Membuat koneksi ke Google Sheets"""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    if json_keyfile_path:
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_keyfile_path, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    return gspread.authorize(creds)

def open_or_create_worksheet(client, provinsi):
    """Buka worksheet provinsi atau buat baru jika belum ada"""
    sh = client.open(GSHEET_NAME)
    try:
        ws = sh.worksheet(provinsi)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=provinsi, rows=200, cols=20)
        ws.append_row([
            "Timestamp","Provinsi","Tahun","Bulan",
            "TargetBulanan","RealisasiBulanan",
            "TargetTahunan2024","TargetTahunan2025",
            "RealisasiYTD2024","RealisasiYTD2025",
            "Lelang","BMN","Piutang","KNL","Lainnya","Catatan"
        ])
    return ws

# =====================================================
# FUNGSI VALIDASI INPUT
# =====================================================
def parse_num(value, field_name=""):
    """Konversi input ke float jika valid, atau None jika kosong"""
    if value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        st.error(f"❌ Input pada '{field_name}' harus berupa angka. Anda mengisi: '{value}'")
        st.stop()

# =====================================================
# FUNGSI SIMPAN / UPDATE DATA
# =====================================================
def upsert_to_gsheet(client, provinsi, row):
    ws = open_or_create_worksheet(client, provinsi)
    df = get_as_dataframe(ws, evaluate_formulas=True, header=0).dropna(how="all")

    if df.empty:
        ws.clear()
        ws.append_row(list(row.keys()))
        ws.append_row([str(x) if x is not None else "" for x in row.values()])
        st.success(f"✅ Data pertama berhasil ditambahkan ({row['Provinsi']} {row['Bulan']} {row['Tahun']}).")
        return

    mask = (
        (df["Provinsi"] == row["Provinsi"]) &
        (df["Bulan"] == row["Bulan"]) &
        (df["Tahun"] == row["Tahun"])
    )

    if mask.any():
        idx = df.index[mask][0]
        for k, v in row.items():
            if v is not None and v != "":
                df.at[idx, k] = v
        ws.clear()
        ws.append_row(list(df.columns))
        ws.append_rows(df.astype(str).values.tolist())
        st.success(f"✅ Data {row['Provinsi']} bulan {row['Bulan']} {row['Tahun']} berhasil diperbarui.")
    else:
        ws.append_row([str(x) if x is not None else "" for x in row.values()])
        st.success(f"✅ Data baru ditambahkan ({row['Provinsi']} {row['Bulan']} {row['Tahun']}).")

# =====================================================
# FORM INPUT DATA
# =====================================================
st.title("📊 ALCo DJKN – Input & Visualisasi PNBP")

col_p, _ = st.columns([1,2])
with col_p:
    provinsi = st.selectbox("Pilih Provinsi", [
        "DKI Jakarta","Jawa Barat","Jawa Tengah","Jawa Timur","Bali","Sumatera Utara","Lampung"
    ])
    bulan = st.selectbox("Bulan Laporan", 
        ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"],
        index=datetime.datetime.now().month-1)
    tahun = st.number_input("Tahun", min_value=2024, max_value=2100, value=datetime.datetime.now().year)

st.markdown("### 🧾 Target dan Realisasi PNBP")
col1, col2 = st.columns(2)
with col1:
    target_bln_in = st.text_input("🎯 Target Bulanan", placeholder="Kosongkan jika tidak diubah")
    target_tahun_2024_in = st.text_input("🎯 Target Tahunan 2024", placeholder="Kosongkan jika tidak diubah")
    target_tahun_2025_in = st.text_input("🎯 Target Tahunan 2025", placeholder="Kosongkan jika tidak diubah")
with col2:
    realisasi_bln_in = st.text_input("📊 Realisasi Bulanan", placeholder="Kosongkan jika tidak diubah")
    realisasi_ytd_2024_in = st.text_input("📊 Realisasi YTD 2024 s.d. Bulan ini", placeholder="Kosongkan jika tidak diubah")
    realisasi_ytd_2025_in = st.text_input("📊 Realisasi YTD 2025 s.d. Bulan ini", placeholder="Kosongkan jika tidak diubah")

st.markdown("### 🧩 Rincian PNBP s.d. Bulan Berjalan")
col3, col4 = st.columns(2)
with col3:
    lelang_in = st.text_input("💰 PNBP Lelang", placeholder="Kosongkan jika tidak diubah")
    bmn_in = st.text_input("🏛️ PNBP BMN", placeholder="Kosongkan jika tidak diubah")
with col4:
    piutang_in = st.text_input("📄 PNBP Piutang Negara", placeholder="Kosongkan jika tidak diubah")
    knl_in = st.text_input("🏠 PNBP Kekayaan Negara Lain-lain", placeholder="Kosongkan jika tidak diubah")
lainnya_in = st.text_input("🗂️ PNBP Lainnya", placeholder="Kosongkan jika tidak diubah")

notes = st.text_area("📝 Catatan / penjelasan", "")

# Validasi angka
target_bln = parse_num(target_bln_in, "Target Bulanan")
target_tahun_2024 = parse_num(target_tahun_2024_in, "Target Tahunan 2024")
target_tahun_2025 = parse_num(target_tahun_2025_in, "Target Tahunan 2025")
realisasi_bln = parse_num(realisasi_bln_in, "Realisasi Bulanan")
realisasi_ytd_2024 = parse_num(realisasi_ytd_2024_in, "Realisasi YTD 2024")
realisasi_ytd_2025 = parse_num(realisasi_ytd_2025_in, "Realisasi YTD 2025")
lelang = parse_num(lelang_in, "PNBP Lelang")
bmn = parse_num(bmn_in, "PNBP BMN")
piutang = parse_num(piutang_in, "PNBP Piutang Negara")
knl = parse_num(knl_in, "PNBP Kekayaan Negara Lain-lain")
lainnya = parse_num(lainnya_in, "PNBP Lainnya")

# =====================================================
# SIMPAN / KONFIRMASI UPDATE
# =====================================================
# Tombol simpan
submit = st.button("💾 Simpan Data & Tampilkan Visualisasi")

# Pastikan session_state selalu ada
if "pending_update_row" not in st.session_state:
    st.session_state["pending_update_row"] = None
if "pending_update_provinsi" not in st.session_state:
    st.session_state["pending_update_provinsi"] = None
if "need_confirm_update" not in st.session_state:
    st.session_state["need_confirm_update"] = False

if submit:
    if not (json_keyfile_path or service_account_info):
        st.error("⚠️ Tidak ada credentials. Tambahkan credentials terlebih dahulu.")
        st.stop()

    client = gs_connect(service_account_info, json_keyfile_path)
    ws = open_or_create_worksheet(client, provinsi)
    df = get_as_dataframe(ws, evaluate_formulas=True, header=0).dropna(how="all")

    # Siapkan data input
    row = {
        "Timestamp": datetime.datetime.now().isoformat(),
        "Provinsi": provinsi,
        "Tahun": tahun,
        "Bulan": bulan,
        "TargetBulanan": target_bln,
        "RealisasiBulanan": realisasi_bln,
        "TargetTahunan2024": target_tahun_2024,
        "TargetTahunan2025": target_tahun_2025,
        "RealisasiYTD2024": realisasi_ytd_2024,
        "RealisasiYTD2025": realisasi_ytd_2025,
        "Lelang": lelang,
        "BMN": bmn,
        "Piutang": piutang,
        "KNL": knl,
        "Lainnya": lainnya,
        "Catatan": notes
    }

    # Simpan row & provinsi ke session agar aman setelah rerun
    st.session_state["pending_update_row"] = row
    st.session_state["pending_update_provinsi"] = provinsi

    # Cek apakah data sudah ada
    mask = (df["Provinsi"] == provinsi) & (df["Bulan"] == bulan) & (df["Tahun"] == tahun)

    if mask.any():
        st.warning(f"⚠️ Data untuk {provinsi} bulan {bulan} {tahun} sudah ada di Google Sheets.")
        st.session_state["need_confirm_update"] = True
    else:
        upsert_to_gsheet(client, provinsi, row)
        st.session_state["need_confirm_update"] = False

# Konfirmasi update jika perlu
if st.session_state["need_confirm_update"]:
    st.warning("⚠️ Data ini sudah ada. Klik tombol di bawah untuk memperbarui data yang sudah ada.")
    if st.button("📝 Ya, perbarui data lama"):
        client = gs_connect(service_account_info, json_keyfile_path)
        upsert_to_gsheet(
            client,
            st.session_state["pending_update_provinsi"],
            st.session_state["pending_update_row"]
        )
        st.success("✅ Data berhasil diperbarui di Google Sheets.")
        st.session_state["need_confirm_update"] = False

# =====================================================
# KONFIRMASI UPDATE DATA (TANPA MODAL)
# =====================================================
if st.session_state.get("need_confirm_update", False):
    st.warning(
        f"⚠️ Data untuk **{st.session_state['pending_update_provinsi']}** bulan **{bulan} {tahun}** sudah ada di Google Sheets."
    )
    st.markdown("Apakah Anda ingin **memperbarui** data yang sudah ada?")

    col_confirm = st.columns(2)
    with col_confirm[0]:
        if st.button("✅ Ya, perbarui data lama", key="confirm_update_yes"):
            client = gs_connect(service_account_info, json_keyfile_path)
            upsert_to_gsheet(
                client,
                st.session_state["pending_update_provinsi"],
                st.session_state["pending_update_row"]
            )
            st.success("✅ Data berhasil diperbarui di Google Sheets.")
            st.session_state["need_confirm_update"] = False

    with col_confirm[1]:
        if st.button("❌ Batal", key="confirm_update_no"):
            st.info("Tidak ada perubahan yang disimpan.")
            st.session_state["need_confirm_update"] = False

# =====================================================
# TABEL REKAP & VISUALISASI PER TAHUN
# =====================================================
st.markdown("---")
st.header("📊 Rekap Data PNBP per Tahun")

if (json_keyfile_path or service_account_info):
    try:
        client = gs_connect(service_account_info, json_keyfile_path)
        ws = open_or_create_worksheet(client, provinsi)
        df_all = get_as_dataframe(ws, evaluate_formulas=True, header=0).dropna(how="all")

        if not df_all.empty:
            for c in ["Tahun","BMN","Lelang","Piutang","KNL","Lainnya"]:
                if c in df_all.columns:
                    df_all[c] = pd.to_numeric(df_all[c], errors="coerce")

            tahun_terpilih = st.selectbox("Pilih Tahun:", sorted(df_all["Tahun"].dropna().unique()))
            df_tahun = df_all[df_all["Tahun"] == tahun_terpilih]

            kolom_jenis = ["BMN","Lelang","Piutang","KNL","Lainnya"]
            df_tabel = df_tahun.groupby("Bulan")[kolom_jenis].sum().reset_index()
            urutan_bulan = ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"]
            df_tabel["Bulan"] = pd.Categorical(df_tabel["Bulan"], categories=urutan_bulan, ordered=True)
            df_tabel = df_tabel.sort_values("Bulan")

            st.dataframe(df_tabel, use_container_width=True, hide_index=True)

            st.markdown("### 📈 Visualisasi Otomatis")
            chart_type = st.radio("Pilih jenis chart:", ["Clustered Column","Stacked Bar"], horizontal=True)
            fig = go.Figure()
            for jenis in kolom_jenis:
                fig.add_bar(x=df_tabel["Bulan"], y=df_tabel[jenis], name=jenis)
            fig.update_layout(
                barmode="group" if chart_type=="Clustered Column" else "stack",
                title=f"PNBP per Jenis – Tahun {tahun_terpilih}",
                template="simple_white",
                height=500,
                legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center")
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Belum ada data tersimpan.")
    except Exception as e:
        st.error(f"Gagal memuat data: {e}")
else:
    st.warning("⚠️ Harap login atau upload credentials terlebih dahulu.")
