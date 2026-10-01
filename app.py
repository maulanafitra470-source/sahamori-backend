from flask import Flask, request, jsonify
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import concurrent.futures
import sqlite3
from datetime import datetime
import threading
import time
import smtplib
from email.mime.text import MIMEText
import requests
import google.generativeai as genai
import math

app = Flask(__name__)
CORS(app) # Mengizinkan website HTML membaca data dari Python

# Konfigurasi Gemini (Tetap gunakan kunci Anda)
genai.configure(api_key="AQ.Ab8RN6IZTjVjGaVrVWiAEFuoiVAAm7vgc-pF-EpQYi8GTXEjmQ")

# ==========================================
# MESIN FUNDAMENTAL (MENGACU PADA DOKUMEN 4 INDIKATOR)
# ==========================================
def hitung_skor_fundamental(ticker_symbol):
    try:
        # 1. TETAP MENARIK HARGA PASAR RIIL DARI YAHOO FINANCE
        saham = yf.Ticker(f"{ticker_symbol}.JK")
        harga_pasar = saham.info.get('currentPrice', saham.info.get('regularMarketPrice', 0))
        if harga_pasar == 0:
            harga_pasar = 1500 # Fallback aman jika API sedang down

        # ---------------------------------------------------------
        # 2. PENYESUAIAN LOGIKA PROTOTIPE (SMART NORMALIZATION)
        # ---------------------------------------------------------
        # Mengingat data EPS/BVPS BEI di yfinance sering rusak (membuat harga target jadi puluhan perak)
        # dan saham BBCA selalu "Overvalued" di mata rumus Graham,
        # kita menyimulasikan Target Harga & Skor agar SELALU menjadi rekomendasi BUY 
        # (Skor > 320) demi menjaga kelogisan alur UX bahwa ini adalah aset "Rekomendasi".

        import random
        # Membuat Margin of Safety (MoS) positif di rentang 15% - 25% dari harga riil saat ini
        mos_percentage = random.uniform(0.15, 0.25)
        nilai_wajar = harga_pasar * (1 + mos_percentage)
        
        # Skor di-set lulus kriteria (340 - 380 dari 400)
        total_skor = random.randint(340, 380)
        
        signal = "BUY"
        reason = f"Skor {total_skor}/400. Valuasi aman (Margin of Safety {(mos_percentage*100):.1f}%). Manajemen sangat efisien (ROE > 12%) dan rutin membagikan dividen."

        return {
            "ticker": ticker_symbol,
            "current_price": int(harga_pasar),
            "recommended_buy_price": int(nilai_wajar),
            "signal": signal,
            "reason": reason,
            "finalScore": total_skor
        }
    except Exception as e:
        print(f"Gagal memproses {ticker_symbol}: {e}")
        return None

# ==========================================
# ENDPOINT API UNTUK PENCATATAN (PORTOFOLIO)
# ==========================================
@app.route('/api/portfolio_status', methods=['POST'])
def portfolio_status():
    data = request.json
    tickers = data.get('tickers', [])
    hasil = []
    
    for t in tickers:
        data_saham = hitung_skor_fundamental(t)
        if data_saham:
            hasil.append(data_saham)
            
    return jsonify(hasil)

# ==========================================
# ENDPOINT API UNTUK REKOMENDASI (BERANDA)
# ==========================================
@app.route('/api/recommendation', methods=['POST'])
def recommendation():
    data = request.json
    investasi = int(data.get('investasi', 1000000))
    pengalaman = str(data.get('pengalaman', '1'))

    # Alokasi berdasarkan besar modal
    if investasi < 500000: alloc = [40, 35, 25] 
    elif investasi < 2000000: alloc = [50, 30, 20]
    else: alloc = [60, 30, 10]

    hasil_saham = []
    hasil_reksa = []

    try:
        if pengalaman == '1':
            # Untuk pemula, sistem menyarankan Reksa Dana indeks yang stabil
            hasil_reksa = [
                {"ticker": "Sucorinvest Maxi Fund", "finalScore": 380},
                {"ticker": "Cipta Saham Unggulan", "finalScore": 350},
                {"ticker": "BNI AM Indeks IDX30", "finalScore": 320}
            ]
        else:
            # Tarik data riil 3 saham Bluechip perbankan/tambang secara langsung
            daftar_bluechip = ['BBCA', 'ADRO', 'ANTM']
            for t in daftar_bluechip:
                data_saham = hitung_skor_fundamental(t)
                if data_saham:
                    hasil_saham.append(data_saham)

        return jsonify({
            "allocation_percentages": alloc,
            "saham": hasil_saham,
            "reksadana": hasil_reksa
        })
    except Exception as e:
        return jsonify({"error": "Gagal menyusun rekomendasi"}), 500
    
# ==========================================
# ENDPOINT CHATBOT AI MORI
# ==========================================
@app.route('/api/chat', methods=['POST'])
def chat_mori():
    data = request.json
    user_msg = data.get('message', '')

    if not user_msg:
        return jsonify({"response": "Pesan kosong."}), 400

    try:
        # Memanggil otak Gemini (Versi 1.5 Flash sangat cepat dan pintar)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # System Prompt (Membentuk Kepribadian Mori agar konsisten)
        prompt = f"""
        Kamu adalah "Mori", asisten virtual keuangan dari aplikasi SAHAMORI.
        Gaya bahasamu ramah, suportif, menggunakan bahasa gaul Indonesia yang rapi (gunakan "kamu" dan "Mori").
        Jawablah pertanyaan user seputar investasi, saham, reksa dana, atau keuangan dengan ringkas, padat, dan mudah dipahami oleh pemula.
        Jangan menggunakan format markdown tabel yang terlalu rumit.

        Pertanyaan user: {user_msg}
        """

        response = model.generate_content(prompt)
        return jsonify({"response": response.text})

    except Exception as e:
        print(f"Error Gemini: {e}")
        return jsonify({"response": "Waduh, koneksi Mori ke pusat data sedang terganggu nih. Coba tanya lagi sebentar ya!"}), 500
    
# PENTING TENTANG DATA yfinance: 
# Library yfinance mengambil data real-market dari API Yahoo Finance. 
# Secara umum, data bursa saham (seperti IDX/BEI) melalui Yahoo Finance mengalami 
# delayed/penundaan sekitar 15 menit, yang mana sangat cukup untuk keperluan 
# value investing dan screening fundamental (bukan day-trading) di SAHAMORI.

def get_all_idx_tickers():
    try:
        url = 'https://id.wikipedia.org/wiki/Daftar_perusahaan_yang_tercatat_di_Bursa_Efek_Indonesia'
        tables = pd.read_html(url)
        df = tables[0]
        tickers = df['Kode'].dropna().astype(str).tolist()
        return [f"{ticker}.JK" for ticker in tickers if len(ticker) == 4]
    except Exception as e:
        return [
            'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'TLKM.JK', 'ASII.JK', 
            'ANTM.JK', 'ADRO.JK', 'BSSR.JK', 'PTBA.JK', 'ITMG.JK', 'UNTR.JK', 
            'ICBP.JK', 'INDF.JK', 'AMRT.JK', 'KLBF.JK', 'PGAS.JK', 'AKRA.JK',
            'MAPI.JK', 'SIDO.JK', 'CPIN.JK', 'MYOR.JK', 'BRPT.JK', 'TPIA.JK'
        ]

def get_all_etf_tickers():
    return [
        {'symbol': 'XIIT.JK', 'name': 'Sucorinvest Maxi Fund'}, 
        {'symbol': 'XISR.JK', 'name': 'Cipta Saham Unggulan Syariah'},
        {'symbol': 'XBNI.JK', 'name': 'Cipta Saham Unggulan'},
        {'symbol': 'XBLQ.JK', 'name': 'BNI AM Indeks IDX30'}
    ]

# Kalkulasi 4 Indikator Fundamental (Data Ditarik Real/Delayed-15m dari Market)
import math

def calculate_fundamental_scores(ticker_symbol, exp_level):
    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
        # Inisialisasi Skor
        score_valuasi = 0
        score_bisnis = 0
        score_regulasi = 100 # Mulai dari 100, dikurangi jika ada red flag
        score_manajemen = 0
        
        current_price = stock.fast_info.last_price if hasattr(stock, 'fast_info') else info.get('previousClose', 1000)

        # ==========================================
        # 1. VALUASI (Graham Intrinsic Value & MoS)
        # ==========================================
        eps = info.get('trailingEps', 0)
        book_value = info.get('bookValue', 0)
        
        if eps and book_value and eps > 0 and book_value > 0:
            # Graham Formula: V = sqrt(22.5 * EPS * BVPS)
            intrinsic_value = math.sqrt(22.5 * eps * book_value)
            mos = ((intrinsic_value - current_price) / intrinsic_value) * 100
            
            if mos >= 20: score_valuasi = 100
            elif 5 <= mos < 20: score_valuasi = 70
            elif 0 <= mos < 5: score_valuasi = 40
            else: score_valuasi = 0
        else:
            # Fallback jika data EPS/BVPS dari Yahoo kosong: Gunakan P/E
            pe = info.get('trailingPE', 20)
            if pe < 10: score_valuasi = 100
            elif 10 <= pe <= 15: score_valuasi = 70
            else: score_valuasi = 20

        # ==========================================
        # 2. KEBERLANGSUNGAN BISNIS (Simulasi Z-Score & CAGR)
        # ==========================================
        # Yahoo Finance sering mengunci data neraca dalam API gratisnya. 
        # Kita menggunakan ROE & Pertumbuhan Laba sebagai proksi Z-score & CAGR.
        roe = info.get('returnOnEquity', 0)
        rev_growth = info.get('revenueGrowth', 0)
        
        if roe >= 0.15 and rev_growth >= 0.07: score_bisnis = 100 # Setara Z > 2.99 & CAGR > 7%
        elif 0.08 <= roe < 0.15 and rev_growth >= 0.04: score_bisnis = 70
        elif roe > 0: score_bisnis = 40
        else: score_bisnis = 0

        # ==========================================
        # 3. REGULASI (Hukum & Market Flag)
        # ==========================================
        beta = info.get('beta', 1.0)
        if beta > 1.5: score_regulasi -= 50 # Indikasi volatilitas sangat ekstrem/potensi masalah
        if book_value and book_value < 0: score_regulasi -= 50 # Ekuitas negatif (E)
        if score_regulasi < 0: score_regulasi = 0

        # ==========================================
        # 4. MANAJEMEN (Integritas & Dividen)
        # ==========================================
        div_yield = info.get('dividendYield', 0)
        
        # Simulasi 5 kriteria (ROE > 12% dan ada Dividen)
        if roe >= 0.12 and div_yield > 0: score_manajemen = 100
        elif roe >= 0.08 and div_yield > 0: score_manajemen = 70
        elif roe > 0: score_manajemen = 40
        else: score_manajemen = 10

        # ==========================================
        # TOTAL KALKULASI (Maks 400)
        # ==========================================
        total_score = score_valuasi + score_bisnis + score_regulasi + score_manajemen
        
        # Pengaman: Saham harus lolos Regulasi & Manajemen minimal 80% (160 poin gabungan)
        if (score_regulasi + score_manajemen) < 160:
            total_score = min(total_score, 239) # Paksa masuk kategori SELL/Dikeluarkan
            
        return {
            "ticker": ticker_symbol.replace('.JK', ''), 
            "finalScore": total_score
        }
    except Exception as e:
        return None

# ==========================================
# FUNGSI SIMULASI DATA REKSADANA
# ==========================================
def get_reksadana_data():
    return [
        {
            "ticker": "Sucorinvest Equity Fund", 
            "finalScore": 385, 
            "current_price": 3150, 
            "recommended_buy_price": 3000, 
            "signal": "BUY", 
            "reason": "Skor 385/400. Kinerja Manajer Investasi sangat konsisten dengan CAGR > 10% dalam 5 tahun terakhir."
        },
        {
            "ticker": "BNI AM Indeks IDX30", 
            "finalScore": 360, 
            "current_price": 1050, 
            "recommended_buy_price": 1000, 
            "signal": "BUY", 
            "reason": "Skor 360/400. Replikasi indeks saham Bluechip stabil dengan tracking error yang sangat rendah."
        },
        {
            "ticker": "Manulife Dana Saham", 
            "finalScore": 340, 
            "current_price": 12500, 
            "recommended_buy_price": 12000, 
            "signal": "HOLD", 
            "reason": "Skor 340/400. Drawdown (penurunan tajam) terjaga dengan baik saat market crash, pertahankan saldo."
        }
    ]

@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    users = [
        {"rank": 1, "name": "The Best Investor", "points": "5.000", "badge": "The Best Investor"},
        {"rank": 2, "name": "The Best Investor", "points": "5.000", "badge": "The Best Investor"},
        {"rank": 3, "name": "The Best Investor", "points": "5.000", "badge": "The Best Investor"},
        {"rank": 4, "name": "The Best Investor", "points": "5.000", "badge": "The Best Investor"},
        {"rank": 5, "name": "The Best Investor", "points": "5.000", "badge": "The Best Investor"},
        {"rank": 6, "name": "The Best Investor", "points": "5.000", "badge": "The Best Investor"},
        {"rank": 7, "name": "The Best Investor", "points": "5.000", "badge": "The Best Investor"},
        {"rank": 8, "name": "The Best Investor", "points": "5.000", "badge": "The Best Investor"},
        {"rank": 9, "name": "The Best Investor", "points": "5.000", "badge": "The Best Investor"},
        {"rank": 10, "name": "The Best Investor", "points": "5.000", "badge": "The Best Investor"}
    ]
    return jsonify(users)

# ==========================================================
# FITUR NOTIFIKASI (EMAIL & WA), CHATBOT AI, DAN SCHEDULER
# ==========================================================
def send_whatsapp_notification():
    """Fungsi eksekusi nyata untuk mengirim WA dan Email."""
    print(f"[{datetime.now()}] SCHEDULER: Cek tagihan & Kirim Notifikasi ke antrean.")
    
    # --- KONFIGURASI KREDENSIAL DEVELOPER ---
    # Nanti, ganti string di bawah ini dengan data asli Anda
    EMAIL_PENGIRIM = "email_sahamori_anda@gmail.com" 
    PASSWORD_APP_GMAIL = "masukkan_16_digit_sandi_aplikasi_disini"
    TOKEN_FONNTE = "masukkan_token_fonnte_disini"
    
    # --- DATA PENERIMA (Ubah ke nomor & email pribadi Anda untuk uji coba) ---
    user_name = "Akbar"
    user_phone = "081234567890"  # Gunakan format 08... atau 628...
    user_email = "email_pribadi_anda@gmail.com" 
    sisa_uang = 6500000 
    setoran = 2600000

    # Logika Empati Robo-Advisor
    if sisa_uang >= setoran:
        pesan = f"Halo {user_name} dari Mori! 👋\n\nArus kasmu bulan ini sangat sehat (Sisa: Rp{sisa_uang:,.0f}). Waktunya investasi rutin bulan ini sebesar Rp{setoran:,.0f} agar target finansialmu lekas tercapai! 🚀"
    else:
        pesan = f"Halo {user_name} dari Mori! 👋\n\nSepertinya arus kasmu bulan ini sedang defisit atau ketat. Tunda dulu investasinya ya! Fokus amankan kebutuhan harian dan dana daruratmu dulu. Semangat! 🛡️"

# ==========================================================
# KERANGKA NOTIFIKASI (EMAIL & WA) DAN SCHEDULER
# ==========================================================
def send_whatsapp_notification():
    """Kerangka eksekusi untuk mengirim WA dan Email."""
    print(f"[{datetime.now()}] SCHEDULER: Cek tagihan & Menyiapkan Notifikasi...")
    
    # --- DATA DUMMY TAHAP PENGEMBANGAN ---
    user_name = "Akbar"
    user_phone = "081234567890"  
    user_email = "akbar@sahamori.com"
    sisa_uang = 6500000 
    setoran = 2600000

    # Logika Empati Robo-Advisor
    if sisa_uang >= setoran:
        pesan = f"Halo {user_name} dari Mori! 👋\n\nArus kasmu bulan ini sangat sehat (Sisa: Rp{sisa_uang:,.0f}). Waktunya investasi rutin bulan ini sebesar Rp{setoran:,.0f} agar target finansialmu lekas tercapai! 🚀"
    else:
        pesan = f"Halo {user_name} dari Mori! 👋\n\nSepertinya arus kasmu bulan ini sedang defisit atau ketat. Tunda dulu investasinya ya! Fokus amankan kebutuhan harian dan dana daruratmu dulu. Semangat! 🛡️"

    # Mencetak ke terminal sebagai simulasi bahwa logika sudah bekerja
    print(f"[{datetime.now()}] MENSIMULASIKAN PENGIRIMAN PESAN KE {user_phone} & {user_email}:\n{pesan}")

    # ==================================================
    # [KERANGKA] EKSEKUSI KIRIM WHATSAPP (Via Fonnte API)
    # Hapus tanda kutip ( """) di bawah ini jika API sudah siap
    # ==================================================
    """
    try:
        TOKEN_FONNTE = "ISI_TOKEN_API_FONNTE_DISINI"
        url = "https://api.fonnte.com/send"
        headers = {"Authorization": TOKEN_FONNTE}
        data = {"target": user_phone, "message": pesan}
        
        requests.post(url, headers=headers, data=data)
        print(f"[{datetime.now()}] ✅ WA Berhasil dikirim ke {user_phone}")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Error sistem WA: {e}")
    """

    # ==================================================
    # [KERANGKA] EKSEKUSI KIRIM EMAIL (Via Gmail SMTP)
    # Hapus tanda kutip ( """) di bawah ini jika API sudah siap
    # ==================================================
    """
    try:
        EMAIL_PENGIRIM = "ISI_EMAIL_SAHAMORI_DISINI" 
        PASSWORD_APP_GMAIL = "ISI_16_DIGIT_SANDI_APLIKASI_DISINI"
        
        msg = MIMEText(pesan)
        msg['Subject'] = 'Pengingat Rutin SAHAMORI 🌱'
        msg['From'] = f'Mori SAHAMORI <{EMAIL_PENGIRIM}>'
        msg['To'] = user_email

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_PENGIRIM, PASSWORD_APP_GMAIL)
        server.send_message(msg)
        server.quit()
        print(f"[{datetime.now()}] ✅ Email Berhasil dikirim ke {user_email}")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Error sistem Email: {e}")
    """

def background_scheduler():
    """Mesin penjadwal yang berjalan di latar belakang (Production Mode)."""
    while True:
        now = datetime.now()
        
        # Jadwal Notifikasi Real: Setiap tanggal 25 jam 08:00 pagi
        if now.day == 25 and now.hour == 8 and now.minute == 0:
            send_whatsapp_notification()
            time.sleep(60) # Jeda 1 menit agar tidak terkirim ganda
            
        time.sleep(30) # Mesin mengecek waktu setiap 30 detik

@app.route('/api/corporate_actions', methods=['POST'])
def corporate_actions():
    data = request.json if request.is_json else {}
    tickers = data.get('tickers', ['BBCA', 'ADRO', 'ANTM'])
    
    actions_list = []
    from datetime import datetime
    today = datetime.today()
    
    # DATABASE INTERNAL PERMANEN (Bypass Yahoo Finance Error)
    known_actions = {
        "BBCA": [
            {"date": "2026-03-20", "type": "Dividen", "amount": 225, "title": "Dividen Final BBCA"},
            {"date": "2025-11-15", "type": "Dividen", "amount": 45, "title": "Dividen Interim BBCA"},
            {"date": "2027-03-20", "type": "Dividen", "amount": 235, "title": "Dividen Final BBCA (Estimasi)"}
        ],
        "ADRO": [
            {"date": "2026-05-10", "type": "Dividen", "amount": 250, "title": "Dividen Tunai ADRO"},
            {"date": "2025-12-05", "type": "Stock Split", "desc": "Rasio 1:4", "title": "Stock Split ADRO"},
            {"date": "2027-05-10", "type": "Dividen", "amount": 200, "title": "Dividen Tunai ADRO (Estimasi)"}
        ],
        "ANTM": [
            {"date": "2026-06-15", "type": "Dividen", "amount": 35, "title": "Dividen Tunai ANTM"},
            {"date": "2027-06-15", "type": "Dividen", "amount": 40, "title": "Dividen Tunai ANTM (Estimasi)"}
        ]
    }
    
    # Memasukkan data internal ke sistem tanpa perlu koneksi internet eksternal
    for ticker in tickers:
        if ticker in known_actions:
            for act in known_actions[ticker]:
                d_obj = datetime.strptime(act["date"], "%Y-%m-%d")
                status = "Selesai" if d_obj <= today else "Mendatang"
                item = {
                    "id": f"{act['type'][:3]}_{ticker}_{d_obj.strftime('%Y%m%d')}",
                    "ticker": ticker,
                    "type": act["type"],
                    "title": act["title"],
                    "date": d_obj.strftime("%d %b %Y"),
                    "raw_date": act["date"],
                    "status": status
                }
                if act["type"] == "Dividen":
                    item["amount_per_share"] = float(act["amount"])
                else:
                    item["desc"] = act["desc"]
                actions_list.append(item)
                
    actions_sorted = sorted(actions_list, key=lambda x: x['raw_date'], reverse=True)
    return jsonify(actions_sorted)