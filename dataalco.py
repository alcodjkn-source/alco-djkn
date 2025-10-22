# app.py (versi tanpa fitur PowerPoint - ALCo DJKN)
import streamlit as st
import pandas as pd
import numpy as np
import io
import datetime
import plotly.graph_objects as go
import plotly.express as px
import requests, re, json
import gspread
from gspread_dataframe import get_as_dataframe
from oauth2client.service_account import ServiceAccountCredentials

# -----------------------
# CONFIGURASI DASAR
# -----------------------
st.set_page_config(page_title="ALCo DJKN", layout="wide")

GSHEET_NAME = "ALCo_Data"

# -----------------------
# AUTH GOOGLE SHEETS
# -----------------------
st.sidebar.header("Konfigurasi")

service_account_info = None
json_keyfile_path = None

# 🔹 Coba baca otomatis dari Streamlit Secrets
try:
    service_account_info = st.secrets["gcp_service_account"]
    st.sidebar.success("✅ Credentials otomatis terdeteksi dari Streamlit Secrets.")
except Exception:
    st.sidebar.warning("⚠️ Tidak ada credentials di Streamlit Secrets. Upload/paste manual jika lokal.")
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
    """
    Connect ke Google Sheets (tanpa caching).
    Aman dari error UnhashableParamError di Streamlit Cloud.
    """
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

def upsert_row_insert_only(worksheet, row):
    """Menambahkan baris baru jika kombinasi Provinsi, Bulan, Tahun belum ada."""
    df = get_as_dataframe(worksheet, evaluate_formulas=True, header=0).dropna(how="all")

    # Pastikan kolom sudah ada
    if df.empty or "Provinsi" not in df.columns:
        worksheet.clear()
        worksheet.append_row(list(row.keys()))
        worksheet.append_row(list(map(str, row.values())))
        st.success(f"✅ Sheet baru dibuat dan data pertama untuk {row['Provinsi']} bulan {row['Bulan']} {row['Tahun']} berhasil disimpan.")
        return df

    # Cek apakah kombinasi Provinsi, Bulan, Tahun sudah ada
    mask = (
        (df["Provinsi"].astype(str) == str(row["Provinsi"])) &
        (df["Bulan"].astype(str) == str(row["Bulan"])) &
        (df["Tahun"].astype(str) == str(row["Tahun"]))
    )

    if mask.any():
        # Jika sudah ada, tampilkan peringatan dan tidak menyimpan ulang
        st.warning(f"⚠️ Data untuk {row['Provinsi']} bulan {row['Bulan']} {row['Tahun']} sudah ada di Google Sheets. Tidak disimpan ulang.")
        return df

    # Jika belum ada, tambahkan data baru
    worksheet.append_row([str(x) if x is not None else "" for x in row.values()])
    st.success(f"✅ Data baru untuk {row['Provinsi']} bulan {row['Bulan']} {row['Tahun']} berhasil ditambahkan.")
    return df


# --- TEST KONEKSI GOOGLE SHEETS ---
if st.sidebar.button("🔍 Tes Koneksi Google Sheets"):
    try:
        # Gunakan kredensial yang sama
        client = gs_connect(service_account_info, json_keyfile_path)

        # Coba buka spreadsheet
        st.write(f"📄 Mencoba membuka spreadsheet: {GSHEET_NAME}")
        sh = client.open(GSHEET_NAME)
        st.success(f"✅ Berhasil terhubung ke spreadsheet: {sh.title}")

        # Tampilkan daftar worksheet
        worksheets = [ws.title for ws in sh.worksheets()]
        st.info(f"Worksheet yang tersedia: {worksheets}")

    except gspread.SpreadsheetNotFound:
        st.error(f"❌ Spreadsheet '{GSHEET_NAME}' tidak ditemukan di Google Drive.")
        st.info("👉 Pastikan nama sheet benar dan sudah di-share ke akun service account.")
    except gspread.exceptions.APIError as e:
        st.error("🚫 Gagal mengakses Google Sheets — kemungkinan besar izin belum diberikan.")
        st.code(str(e))
    except Exception as e:
        st.error("❌ Error lain saat mencoba koneksi:")
        st.code(str(e))

# -----------------------
# FORM INPUT
# -----------------------
st.title("📊 ALCo DJKN – Input & Visualisasi PNBP")

col_p, col_t = st.columns([1,2])
with col_p:
    provinsi = st.selectbox("Pilih Provinsi", [
        "DKI Jakarta","Jawa Barat","Jawa Tengah","Jawa Timur","Bali","Sumatera Utara","Lampung"
    ])
    bulan = st.selectbox("Bulan Laporan", ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"],
                         index=datetime.datetime.now().month-1)
    tahun = st.number_input("Tahun", min_value=2024, max_value=2100, value=datetime.datetime.now().year)
notes = st.text_area("Catatan / penjelasan", "")

st.markdown("### 🧾 Target dan Realisasi PNBP")
c1, c2 = st.columns(2)
with c1:
    target_bln = st.number_input("Target Bulanan", min_value=0.0, step=0.01)
    target_tahun_2024 = st.number_input("Target Tahunan 2024", min_value=0.0, step=0.01)
    target_tahun_2025 = st.number_input("Target Tahunan 2025", min_value=0.0, step=0.01)
with c2:
    realisasi_bln = st.number_input("Realisasi Bulanan", min_value=0.0, step=0.01)
    realisasi_ytd_2024 = st.number_input("Realisasi YTD 2024 s.d. Bulan ini", min_value=0.0, step=0.01)
    realisasi_ytd_2025 = st.number_input("Realisasi YTD 2025 s.d. Bulan ini", min_value=0.0, step=0.01)

st.markdown("### 🧩 Rincian PNBP s.d. Bulan Berjalan")
col_a, col_b = st.columns(2)
with col_a:
    lelang = st.number_input("PNBP Lelang", min_value=0.0, step=0.01)
    bmn = st.number_input("PNBP BMN", min_value=0.0, step=0.01)
with col_b:
    piutang = st.number_input("PNBP Piutang Negara", min_value=0.0, step=0.01)
    knl = st.number_input("PNBP Kekayaan Negara Lain-lain", min_value=0.0, step=0.01)
lainnya = st.number_input("PNBP Lainnya", min_value=0.0, step=0.01)

submit = st.button("💾 Simpan Data & Tampilkan Visualisasi")

# -----------------------
# SIMPAN KE GOOGLE SHEETS
# -----------------------
if submit:
    if not (json_keyfile_path or service_account_info):
        st.error("⚠️ Tidak ada credentials. Pastikan sudah menambahkan `gcp_service_account` di Streamlit Secrets atau upload JSON di sidebar.")
        st.stop()

    client = gs_connect(service_account_info, json_keyfile_path)
    ws = open_or_create_worksheet(client, provinsi)

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
        "Lelang": lelang, "BMN": bmn, "Piutang": piutang, "KNL": knl, "Lainnya": lainnya,
        "Catatan": notes
    }

    df_ws = upsert_row_insert_only(ws, row)
    st.success(f"✅ Data {provinsi} bulan {bulan} {tahun} tersimpan & diperbarui di Google Sheets!")

    # -----------------------
    # HITUNG MoM & YoY OTOMATIS
    # -----------------------
    df_ws = df_ws.sort_values(by=["Tahun", "Bulan"])
    this_idx = df_ws[(df_ws["Tahun"] == tahun) & (df_ws["Bulan"] == bulan)].index
    prev_row = df_ws.iloc[this_idx[0]-1] if len(this_idx)>0 and this_idx[0]>0 else None

    mom = ((realisasi_bln - prev_row["RealisasiBulanan"]) / prev_row["RealisasiBulanan"] * 100) if prev_row is not None and prev_row["RealisasiBulanan"] != 0 else 0
    yoy = ((realisasi_ytd_2025 - realisasi_ytd_2024) / realisasi_ytd_2024 * 100) if realisasi_ytd_2024 else 0

# -----------------------
# VISUALISASI
# -----------------------
st.markdown("## 📈 Visualisasi")

# ===== Chart 1 - MoM (Month-on-Month) =====
prev_month = prev_row["Bulan"] if prev_row is not None else "–"
months = [prev_month, bulan]
vals_target = [prev_row["TargetBulanan"] if prev_row is not None else 0, target_bln]
vals_realisasi = [prev_row["RealisasiBulanan"] if prev_row is not None else 0, realisasi_bln]

fig1 = go.Figure()
fig1.add_bar(
    x=months,
    y=vals_target,
    name="Target",
    marker_color="#005BAC",
    text=[f"{v:,.0f}" for v in vals_target],
)
fig1.add_bar(
    x=months,
    y=vals_realisasi,
    name="Realisasi",
    marker_color="#76C043",
    text=[f"{v:,.0f}" for v in vals_realisasi],
)
fig1.add_scatter(
    x=months,
    y=vals_realisasi,
    name="Tren Realisasi",
    mode="lines+markers",
    line=dict(color="#76C043", width=3),
)

# Arrow indicator MoM
arrow_symbol = "▲" if mom > 0 else ("▼" if mom < 0 else "➖")
arrow_color = "green" if mom > 0 else ("red" if mom < 0 else "gray")
fig1.add_annotation(
    text=f"{arrow_symbol} {mom:+.1f}% (MoM)",
    x=bulan,
    y=(max(vals_target + vals_realisasi) if (vals_target + vals_realisasi) else 0) * 1.05 + 1,
    showarrow=False,
    font=dict(color=arrow_color, size=14, family="Arial Black"),
)

fig1.update_layout(
    title=f"Target dan Realisasi PNBP Bulan {bulan} {tahun}",
    barmode="group",
    template="simple_white",
    legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
    margin=dict(t=80, b=50, l=40, r=40),
    height=420,
)

# ===== Chart 2 - YoY (Year-on-Year) =====
r2024 = float(realisasi_ytd_2024 or 0)
r2025 = float(realisasi_ytd_2025 or 0)
t2024 = float(target_tahun_2024 or 0)
t2025 = float(target_tahun_2025 or 0)

fig2 = go.Figure()
fig2.add_bar(
    x=["2024", "2025"],
    y=[t2024, t2025],
    name="Target Tahunan",
    marker_color="#005BAC",
    text=[f"{v:,.0f}" for v in [t2024, t2025]],
)
fig2.add_bar(
    x=["2024", "2025"],
    y=[r2024, r2025],
    name="Realisasi YTD",
    marker_color="#76C043",
    text=[f"{v:,.0f}" for v in [r2024, r2025]],
)
fig2.add_scatter(
    x=["2024", "2025"],
    y=[r2024, r2025],
    name="Tren Realisasi",
    line=dict(color="#76C043", width=3),
)

arrow_symbol_yoy = "▲" if yoy > 0 else ("▼" if yoy < 0 else "➖")
arrow_color_yoy = "green" if yoy > 0 else ("red" if yoy < 0 else "gray")
fig2.add_annotation(
    text=f"{arrow_symbol_yoy} {yoy:+.1f}% (YoY)",
    x="2025",
    y=max(t2025, r2025) * 1.05 + 1,
    showarrow=False,
    font=dict(color=arrow_color_yoy, size=14, family="Arial Black"),
)

fig2.update_layout(
    title=f"Target dan Realisasi PNBP s.d. {bulan} {tahun}",
    barmode="group",
    template="simple_white",
    legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
    margin=dict(t=80, b=50, l=40, r=40),
    height=420,
)

# ===== Chart 3 - Breakdown Jenis (horizontal bar) =====
jenis = ["Lelang", "BMN", "Piutang Negara", "Kek. Negara Lain-lain", "Lainnya"]
# Pastikan nilai numerik (fallback 0)
nilai = [
    float(lelang or 0),
    float(bmn or 0),
    float(piutang or 0),
    float(knl or 0),
    float(lainnya or 0)
]
fig3 = px.bar(
    x=nilai,
    y=jenis,
    orientation="h",
    text=[f"{v:,.0f}" for v in nilai],
    title=f"Realisasi PNBP Berdasarkan Jenis s.d. {bulan}",
    template="simple_white",
    labels={"x": "Nilai (juta)", "y": ""}
)
fig3.update_traces(textposition="outside")
fig3.update_layout(
    margin=dict(l=120, r=40, t=60, b=40),
    height=360,
)

# ===== Render charts =====
st.plotly_chart(fig1, use_container_width=True)
st.plotly_chart(fig2, use_container_width=True)
st.plotly_chart(fig3, use_container_width=True)

# ==============================================================
# 📅 Halaman Data PNBP per Tahun
# ==============================================================
st.markdown("---")
st.header("📊 Rekap Data PNBP per Tahun")

if not (json_keyfile_path or service_account_info):
    st.warning("⚠️ Tidak ada credentials. Upload/paste JSON credentials di sidebar agar bisa menampilkan data dari Google Sheets.")
else:
    try:
        client = gs_connect(service_account_info, json_keyfile_path)
        ws = open_or_create_worksheet(client, provinsi)
        df_all = get_as_dataframe(ws, evaluate_formulas=True, header=0).dropna(how="all")

        if df_all.empty:
            st.info(f"Belum ada data tersimpan untuk {provinsi}.")
        else:
            # Konversi tipe data
            for c in ["Tahun", "TargetBulanan", "RealisasiBulanan", "BMN", "Lelang", "Piutang", "KNL", "Lainnya"]:
                if c in df_all.columns:
                    df_all[c] = pd.to_numeric(df_all[c], errors="coerce")

            tahun_terpilih = st.selectbox("Pilih Tahun Data:", sorted(df_all["Tahun"].dropna().unique()), index=len(df_all["Tahun"].unique())-1)
            df_tahun = df_all[df_all["Tahun"] == tahun_terpilih]

            # Buat tabel rekap per bulan
            kolom_jenis = ["BMN", "Lelang", "Piutang", "KNL", "Lainnya"]
            df_tabel = df_tahun.groupby("Bulan")[kolom_jenis].sum().reset_index()

            # Urutkan bulan
            urutan_bulan = ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"]
            df_tabel["Bulan"] = pd.Categorical(df_tabel["Bulan"], categories=urutan_bulan, ordered=True)
            df_tabel = df_tabel.sort_values("Bulan")

            st.subheader(f"Tabel PNBP Tahun {tahun_terpilih} — {provinsi}")
            st.dataframe(df_tabel, use_container_width=True, hide_index=True)

            # ==========================================================
            # Visualisasi otomatis dari tabel ini
            # ==========================================================
            st.markdown("### 📈 Visualisasi Otomatis")
            chart_type = st.radio("Pilih jenis visualisasi:", ["Clustered Column", "Stacked Bar"], horizontal=True)

            if chart_type == "Clustered Column":
                fig_tahun = go.Figure()
                for jenis in kolom_jenis:
                    fig_tahun.add_bar(
                        x=df_tabel["Bulan"],
                        y=df_tabel[jenis],
                        name=jenis
                    )
                fig_tahun.update_layout(
                    barmode="group",
                    title=f"Target dan Realisasi PNBP per Jenis — Tahun {tahun_terpilih}",
                    template="simple_white",
                    legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center"),
                    autosize=True,
                    height=500
                )
            else:
                fig_tahun = go.Figure()
                for jenis in kolom_jenis:
                    fig_tahun.add_bar(
                        x=df_tabel["Bulan"],
                        y=df_tabel[jenis],
                        name=jenis
                    )
                fig_tahun.update_layout(
                    barmode="stack",
                    title=f"Komposisi PNBP per Bulan — Tahun {tahun_terpilih}",
                    template="simple_white",
                    legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center"),
                    autosize=True,
                    height=500
                )

            st.plotly_chart(fig_tahun, use_container_width=True)

    except Exception as e:
        st.error(f"Gagal memuat data dari Google Sheets: {e}")
