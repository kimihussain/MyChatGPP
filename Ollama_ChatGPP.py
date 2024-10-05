import os
import streamlit as st
import fitz  # PyMuPDF untuk membaca PDF
import pytesseract
from PIL import Image
import openai
import difflib  # Untuk bandingan persamaan teks

# Tidak perlu tetapkan laluan Tesseract secara eksplisit di pelayan
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# API Key OpenAI
openai.api_key = "sk-proj-a26WXgUOpS_6hjETjqlxKnEGL51trzyYo9Wap3_sNm5rPyp3c2rlet4YM7_nefhGVPXAYBgBCeVEvDJ5_lHTqVUljG3G3iXpLL96IA"  # Gantikan dengan API key OpenAI anda

def tambah_logo_dan_teks_dan_senarai_gpp(lokasi_logo, teks_tambahan, folder_gpp):
    st.sidebar.image(lokasi_logo, width=250)  # Pastikan logo_path betul
    st.sidebar.write(teks_tambahan)
    st.sidebar.write("**Senarai Garis Panduan Perancangan (GPP) dan Panduan Pelaksanaan (PP) yang tersedia di platform MyChatGPP**")
    for pdf_file in os.listdir(folder_gpp):
        if pdf_file.endswith(".pdf"):
            pdf_path = os.path.join(folder_gpp, pdf_file)
            with open(pdf_path, "rb") as file:
                st.sidebar.download_button(label=f"Muat turun {pdf_file}", data=file, file_name=pdf_file)

# Inisialisasi 'st.session_state' untuk mengelakkan AttributeError
if "last_question" not in st.session_state:
    st.session_state.last_question = ""
if "last_answer" not in st.session_state:
    st.session_state.last_answer = ""

# Fungsi untuk membaca dan mengekstrak kandungan dari PDF
def baca_kandungan_pdf(pdf_path):
    kandungan = ""
    try:
        dokumen = fitz.open(pdf_path)
        for halaman in dokumen:
            teks = halaman.get_text()
            if teks.strip():  # Jika ada teks, tambahkan ke kandungan
                kandungan += teks
            else:  # Jika tiada teks, cuba gunakan OCR
                pix = halaman.get_pixmap()
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                teks_ocr = pytesseract.image_to_string(image)
                kandungan += teks_ocr
        dokumen.close()
    except Exception as e:
        st.error(f"Error membaca PDF: {e}")
    return kandungan

# Fungsi untuk memecahkan teks kepada bahagian kecil berdasarkan had token
def pecahkan_kandungan(kandungan, max_tokens=800):  # Hadkan kepada 800 token
    words = kandungan.split()  # Pecahkan teks kepada senarai perkataan
    chunks = []
    chunk = []

    for word in words:
        chunk.append(word)
        if len(chunk) >= max_tokens:
            chunks.append(" ".join(chunk))
            chunk = []
    
    if chunk:  # Tambahkan baki teks yang tidak melebihi had
        chunks.append(" ".join(chunk))
    
    return chunks

# Fungsi untuk menyaring pengulangan dan hanya menyimpan satu jawapan per istilah
def saring_jawapan(jawapan_akhir):
    jawapan_set = set()  # Simpan jawapan unik
    jawapan_bersih = []

    for ayat in jawapan_akhir.split('\n'):
        if ayat.strip() not in jawapan_set and ayat.strip() != "":
            jawapan_bersih.append(ayat.strip())
            jawapan_set.add(ayat.strip())

    return "\n".join(jawapan_bersih)

# Fungsi untuk memastikan setiap ayat berakhir dengan noktah
def pastikan_noktah(jawapan):
    ayat_berformat = []
    for ayat in jawapan.split('\n'):
        ayat = ayat.strip()
        if ayat and not ayat.endswith('.'):  # Tambah noktah jika tiada
            ayat += '.'
        ayat_berformat.append(ayat)
    return "\n".join(ayat_berformat)

# Fungsi untuk menyaring ayat yang berulang atau hampir serupa
def saring_ulang_dengan_similarity(jawapan, threshold=0.85):
    ayat_bersih = []
    ayat_terdahulu = ""

    for ayat in jawapan.split('\n'):
        ayat = ayat.strip()
        if ayat and difflib.SequenceMatcher(None, ayat_terdahulu, ayat).ratio() < threshold:
            ayat_bersih.append(ayat)
            ayat_terdahulu = ayat

    return "\n".join(ayat_bersih)

# Fungsi untuk merumuskan jawapan menggunakan OpenAI API
def ringkaskan_jawapan(jawapan_panjang):
    prompt = f"Ringkaskan jawapan berikut dalam Bahasa Melayu Malaysia dengan tidak lebih daripada 3 ayat penuh:\n\n{jawapan_panjang}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0125",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=200
    )
    return response['choices'][0]['message']['content'].strip()

# Fungsi untuk memadankan soalan dengan GPP/PP yang relevan
def padankan_gpp_dengan_soalan(soalan, folder_gpp):
    dokumen_list = []
    keywords = ['ev', 'evcb', 'kilang tanaman', 'plant factory', 'smart city', 'electric vehicle', 'penilaian impak sosial', 'sia', 'bandar pintar']  # Tambahkan kata kunci yang berkaitan dengan setiap GPP atau PP
    for pdf_file in os.listdir(folder_gpp):
        if pdf_file.endswith(".pdf"):
            # Cari dokumen yang berkaitan dengan soalan atau kata kunci
            if any(keyword in soalan.lower() for keyword in keywords):
                pdf_path = os.path.join(folder_gpp, pdf_file)
                kandungan = baca_kandungan_pdf(pdf_path)
                if kandungan:
                    dokumen_list.append(kandungan)
    return dokumen_list

# Fungsi untuk menjana jawapan menggunakan OpenAI API dengan chat endpoint
def bina_jawapan_openai(soalan, kandungan):
    try:
        jawapan_akhir = ""
        jawapan_ringkas_set = set()

        # Pecahkan kandungan kepada bahagian yang lebih kecil
        kandungan_pecah = pecahkan_kandungan(kandungan)

        # Simpan soalan terakhir
        st.session_state.last_question = soalan

        # Minta hanya satu jawapan ringkas dan padat bagi setiap istilah
        for bahagian in kandungan_pecah:
            prompt = f"Kandungan PDF: {bahagian}\nSoalan: {soalan}\nBerikan jawapan dalam Bahasa Melayu Malaysia yang sangat ringkas dan elakkan pengulangan. Jawapan mesti sekurang-kurangnya 2 ayat penuh."
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo-0125",
                messages=[{"role": "user", "content": prompt}],  # Hanya ambil soalan terkini
                max_tokens=350,  # Tambah lebih banyak token untuk jawapan lebih lengkap
                temperature=0.3,  # Kawal kreatifiti untuk respons yang lebih padat
            )
            jawapan_ringkas = response['choices'][0]['message']['content'].strip()

            # Hanya masukkan jawapan jika tidak None dan tidak berulang
            if jawapan_ringkas and jawapan_ringkas not in jawapan_ringkas_set:
                jawapan_akhir += jawapan_ringkas + "\n"
                jawapan_ringkas_set.add(jawapan_ringkas)
        
        # Bersihkan jawapan daripada pengulangan
        jawapan_akhir_bersih = saring_jawapan(jawapan_akhir)

        # Pastikan semua ayat berakhir dengan noktah
        jawapan_akhir_berformat = pastikan_noktah(jawapan_akhir_bersih)

        # Saring pengulangan ayat dengan similarity check
        jawapan_akhir_disaring = saring_ulang_dengan_similarity(jawapan_akhir_berformat)

        # Ringkaskan jawapan
        jawapan_ringkas_akhir = ringkaskan_jawapan(jawapan_akhir_disaring)

        # Simpan jawapan terakhir
        st.session_state.last_answer = jawapan_ringkas_akhir.strip()

        return jawapan_ringkas_akhir.strip()
    except Exception as e:
        st.error(f"Error semasa menjana jawapan: {e}")

# Antaramuka Streamlit dengan logo, teks panduan, dan senarai GPP di sebelah kiri
def chatbot_interface(nama_chatbot, logo_path, teks_tambahan, caption, folder_gpp):
    # Menambah logo, teks tambahan dan senarai GPP di sidebar
    tambah_logo_dan_teks_dan_senarai_gpp(logo_path, teks_tambahan, folder_gpp)
    
    # Tajuk utama dengan nama baru chatbot
    st.title(f"{nama_chatbot}")

    # Papar caption di bawah tajuk
    st.write(caption)

    # Papar sejarah soalan dan jawapan terakhir
    if st.session_state.last_question and st.session_state.last_answer:
        st.write(f"**Soalan Pengguna:** {st.session_state.last_question}")
        st.write(f"**MyChatGPP:** {st.session_state.last_answer}")

# Input soalan dari pengguna
def input_soalan():
    return st.text_input("Masukkan soalan anda:")

# Proses jika terdapat soalan
def proses_soalan(soalan, folder_gpp):
    if soalan:
        # Padankan GPP/PP berdasarkan soalan
        dokumen_list = padankan_gpp_dengan_soalan(soalan, folder_gpp)
        
        if dokumen_list:
            # Menggabungkan semua kandungan dari dokumen-dokumen yang padan
            kandungan_semua = " ".join(dokumen_list)
            # Menjana jawapan berdasarkan kandungan PDF
            jawapan = bina_jawapan_openai(soalan, kandungan_semua)
            st.write(f"**MyChatGPP:** {jawapan}")
        else:
            st.error("Tiada kandungan dari PDF yang relevan untuk dijadikan rujukan.")

# Tetapkan lokasi logo, nama chatbot, teks tambahan, dan caption
logo_path = "images/planmalaysia_logo.png"  # Tukar dengan laluan sebenar logo anda
nama_chatbot = "MyChatGPP"
teks_tambahan = "Penafian: MyChatGPP adalah platform interaktif AI yang dibangunkan bagi tujuan pembelajaran dan masih BETA Version. Oleh yang demikian, kesilapan chatbot dalam menjawab soalan adalah boleh dijangka. Pengguna diminta untuk merujuk kepada dokumen pdf yang disertakan untuk maklumat yang lebih tepat. Terima kasih di atas kerjasama anda."
caption = "Selamat datang ke MyChatGPP! Anda boleh cuba bertanyakan apa-apa soalan berkaitan GPP atau PP yang tersenarai di sebelah atau sila muat turun GPP atau PP di link yang disediakan."

# Tetapkan lokasi folder GPP PDF
folder_gpp = "GPPpdf"

# Panggil antaramuka chatbot
chatbot_interface(nama_chatbot, logo_path, teks_tambahan, caption, folder_gpp)

# Input soalan dari pengguna
soalan = input_soalan()

# Proses soalan yang dimasukkan
proses_soalan(soalan, folder_gpp)
