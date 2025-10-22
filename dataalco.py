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

@st.cache_resource
def gs_connect(service_account_info=None, json_keyfile_path=None):
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
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

def upsert_row(worksheet, row):
    df = get_as_dataframe(worksheet, evaluate_formulas=True, header=0).dropna(how="all")
    mask = (df["Tahun"] == row["Tahun"]) & (df["Bulan"] == row["Bulan"])
    if mask.any():
        idx = df.index[mask][0]
        for k,v in row.items():
            df.at[idx,k] = v
    else:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    worksheet.clear()
    worksheet.append_row(list(df.columns))
    for r in df.to_numpy().tolist():
        worksheet.append_row(r)
    return df

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

    df_ws = upsert_row(ws, row)
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

    # Chart 1 - MoM
    prev_month = prev_row["Bulan"] if prev_row is not None else "–"
    months = [prev_month, bulan]
    vals_target = [prev_row["TargetBulanan"] if prev_row is not None else 0, target_bln]
    vals_realisasi = [prev_row["RealisasiBulanan"] if prev_row is not None else 0, realisasi_bln]

    fig1 = go.Figure()
    fig1.add_bar(x=months, y=vals_target, name="Target", marker_color="#005BAC", text=[f"{v:,.0f}" for v in vals_target])
    fig1.add_bar(x=months, y=vals_realisasi, name="Realisasi", marker_color="#76C043", text=[f"{v:,.0f}" for v in vals_realisasi])
    fig1.add_scatter(x=months, y=vals_realisasi, name="Tren Realisasi", mode="lines+markers", line=dict(color="#76C043", width=3))
    fig1.add_annotation(text=f"{mom:+.1f}% (MoM)", x=bulan, y=max(vals_target)*1.1, showarrow=False, font=dict(color="green", size=16))
    fig1.update_layout(
        title=f"Target dan Realisasi PNBP Bulan {bulan} {tahun}",
        barmode="group",
        template="simple_white",
        legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
    )

    # Chart 2 - YoY
    fig2 = go.Figure()
    fig2.add_bar(x=["2024","2025"], y=[realisasi_ytd_2024,realisasi_ytd_2025], name="Realisasi YTD", marker_color="#76C043")
    fig2.add_bar(x=["2024","2025"], y=[target_tahun_2024,target_tahun_2025], name="Target Tahunan", marker_color="#005BAC")
    fig2.add_scatter(x=["2024","2025"], y=[realisasi_ytd_2024,realisasi_ytd_2025], name="Tren Realisasi", line=dict(color="#76C043", width=3))
    fig2.add_annotation(text=f"{yoy:+.1f}% (YoY)", x="2025", y=max(target_tahun_2025,realisasi_ytd_2025)*1.1, showarrow=False, font=dict(color="green", size=16))
    fig2.update_layout(
        title=f"Target dan Realisasi PNBP s.d. {bulan} {tahun}",
        barmode="group",
        template="simple_white",
        legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
    )

    # Chart 3 - Breakdown Jenis
    jenis = ["Lelang","BMN","Piutang","KNL","Lainnya"]
    nilai = [lelang,bmn,piutang,knl,lainnya]
    fig3 = px.bar(x=nilai, y=jenis, orientation="h", text=[f"{v:,.0f}" for v in nilai],
                  color_discrete_sequence=["#005BAC"], title=f"Realisasi PNBP Berdasarkan Jenis s.d. {bulan}")
    fig3.update_traces(textposition="outside")
    fig3.update_layout(template="simple_white")

    st.plotly_chart(fig1, use_container_width=True)
    st.plotly_chart(fig2, use_container_width=True)
    st.plotly_chart(fig3, use_container_width=True)
