import os
import cv2
import time
import json
import fitz
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from google import genai
from ultralytics import YOLO

from cypy.core.config import (
    GEMINI_API_KEY, MODEL_GEMINI, MODEL_YOLO, FONT_MANGA, ROOT_DIR,
    MAX_TINGGI_MOSAIK, PAD_X_RATIO, PAD_Y_RATIO, MIN_PAD, SKALA_POTONGAN_MOSAIK,
    MARGIN_KIRI_NOMOR, MARGIN_KANAN, JARAK_ANTAR_POTONGAN, LEBAR_MOSAIK_MIN,
    PAKAI_PATCH_UNTUK_BOX_GEPENG, RASIO_BOX_GEPENG, LEBAR_BOX_GEPENG_RATIO, TINGGI_BOX_GEPENG_RATIO,
    MANUAL_TRANSLATION_OVERRIDE
)
from cypy.core.utils import (
    panggil_gemini_dengan_config, bersihkan_json_dari_gemini,
    gabung_kotak_tumpang_tindih, buang_kotak_ngawur, buang_kotak_sfx_dan_gambar,
    buat_crop_lega_tapi_tidak_nyamber, mask_luar_box_utama, tulis_teks_di_balon
)


def terjemahkan_mosaik(gambar_mosaik_pil, max_retry=3):
    """Sends a single mosaic image to Gemini ♪"""
    for percobaan in range(max_retry):
        try:
            if not GEMINI_API_KEY:
                print("\n[!] GEMINI_API_KEY not found in .env")
                return {}

            client = genai.Client(api_key=GEMINI_API_KEY)

            prompt = (
                "You are an accurate, literal Japanese-to-Indonesian manga translator. "
                "The image contains several speech bubbles arranged vertically. "
                "Each bubble is prefixed with a LARGE RED NUMBER on its left as its ID. "

                "MAIN TASK: "
                "Read the Japanese text in each bubble, then translate it into Indonesian, faithfully preserving the original meaning. "

                "VERTICAL READING RULES: "
                "1. Read vertical text from top to bottom. "
                "2. If there are multiple vertical columns, read the rightmost column first, then move left. "
                "3. Do not reverse column orders. "
                "4. Do not mix text between bubbles. "

                "TRANSLATION RULES: "
                "1. Translate literally and accurately. Do not make it overly polite, do not summarize, and do not invent content. "
                "2. Do not add subjects or objects not present in the original Japanese. "
                "3. Do not alter the relationships between characters. "
                "4. If the Japanese text is rude, explicit, teasing, degrading, bashful, or begging, maintain that exact tone. "
                "5. If the Japanese text contains a question, the Indonesian output must also be a question. "
                "6. Do not create new sentences that sound unnatural if they are not in the original text. "
                "7. For long sentences, keep all parts of the meaning. Do not truncate. "
                "8. If unsure about some text, use [?] for that part. "
                "9. If the bubble only contains SFX, scribbles, is empty, or is background art and not a meaningful dialogue, reply with 'SKIP'. "

                "OUTPUT FORMAT: "
                "Provide the response ONLY in valid JSON without markdown formatting. "
                "Keys must be the red ID numbers as strings. "
                "Values must be the Indonesian translation. "
                'Example output: {"1": "Cepat bangun!", "2": "SKIP", "3": "Ibu... tunggu..."}'
            )

            response = panggil_gemini_dengan_config(client, gambar_mosaik_pil, prompt)

            teks_json = bersihkan_json_dari_gemini(response.text)
            hasil = json.loads(teks_json)

            return hasil

        except ValueError as ve:
            if str(ve) == "API_KEY_ERROR":
                print("\n[!] API key is expired or invalid. Please renew your GEMINI_API_KEY in .env")
                return {}
            raise ve
        except Exception as e:
            err_str = str(e).lower()
            if "api key expired" in err_str or "api_key_invalid" in err_str or "api key" in err_str or "api_key" in err_str:
                print("\n[!] API key is expired or invalid. Please renew your GEMINI_API_KEY in .env")
                return {}

            print(f"\n[!] Gemini error (Attempt {percobaan + 1}/{max_retry})~")

            if percobaan < max_retry - 1:
                time.sleep(10)
            else:
                print("  [!] Failed to connect to Gemini.")
                return {}


def perkecil_daftar_potongan_jika_mosaik_terlalu_tinggi(
    daftar_potongan,
    max_tinggi_mosaik=6000,
    jarak_antar_potongan=10,
    padding_atas_bawah=20
):
    """
    Shrinks panels before constructing the mosaic if it exceeds the max height limit.
    Red IDs are drawn post-resize so they remain perfectly clear~ ♪
    """
    if not daftar_potongan:
        return daftar_potongan

    jumlah_potongan = len(daftar_potongan)
    tinggi_gambar_total = sum(p.height for _, p in daftar_potongan)
    tinggi_spasi_total = jumlah_potongan * jarak_antar_potongan + padding_atas_bawah
    tinggi_mosaik_awal = tinggi_gambar_total + tinggi_spasi_total

    if tinggi_mosaik_awal <= max_tinggi_mosaik:
        return daftar_potongan

    tinggi_target_gambar = max(1, max_tinggi_mosaik - tinggi_spasi_total)
    rasio = tinggi_target_gambar / float(tinggi_gambar_total)

    daftar_baru = []

    for nomor, pot in daftar_potongan:
        lebar_baru = max(1, int(pot.width * rasio))
        tinggi_baru = max(1, int(pot.height * rasio))

        pot_baru = pot.resize(
            (lebar_baru, tinggi_baru),
            Image.Resampling.LANCZOS
        )

        daftar_baru.append((nomor, pot_baru))

    return daftar_baru


def proses_satu_gambar(image_path, yolo_model):
    """Processes a single manga page~ ♪"""
    print(f"\nTranslating: {os.path.basename(image_path)}")

    img = cv2.imread(image_path)

    if img is None:
        print("[!] Image file is corrupt or unreadable.")
        return None

    img_pil_utama = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw_utama = ImageDraw.Draw(img_pil_utama)

    tinggi_img, lebar_img = img.shape[:2]

    tahap_prediksi = [
        {"conf": 0.28, "iou": 0.45},
        {"conf": 0.18, "iou": 0.55},
        {"conf": 0.10, "iou": 0.65}
    ]

    kotak_mentah = []

    for tahap in tahap_prediksi:
        temp_results = yolo_model.predict(
            source=img,
            conf=tahap["conf"],
            iou=tahap["iou"],
            verbose=False
        )

        for box in temp_results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            kotak_mentah.append([x1, y1, x2, y2])

    kotak_matang = gabung_kotak_tumpang_tindih(kotak_mentah)
    kotak_matang = buang_kotak_ngawur(kotak_matang, lebar_img, tinggi_img)
    kotak_matang = buang_kotak_sfx_dan_gambar(
        img=img,
        boxes=kotak_matang,
        image_name=image_path
    )

    daftar_potongan = []
    koordinat_jejak = {}

    for urutan, (x1, y1, x2, y2) in enumerate(kotak_matang, start=1):
        box_w = max(1, x2 - x1)
        box_h = max(1, y2 - y1)

        pad_x = max(MIN_PAD, int(box_w * PAD_X_RATIO))
        pad_y = max(MIN_PAD, int(box_h * PAD_Y_RATIO))

        crop_x1, crop_y1, crop_x2, crop_y2 = buat_crop_lega_tapi_tidak_nyamber(
            [x1, y1, x2, y2],
            kotak_matang,
            lebar_img,
            tinggi_img,
            pad_x,
            pad_y
        )

        potongan = img[crop_y1:crop_y2, crop_x1:crop_x2].copy()

        if potongan.size == 0:
            continue

        potongan = mask_luar_box_utama(
            potongan,
            crop_x1,
            crop_y1,
            x1,
            y1,
            x2,
            y2
        )

        potongan_pil = Image.fromarray(cv2.cvtColor(potongan, cv2.COLOR_BGR2RGB))

        if SKALA_POTONGAN_MOSAIK != 1:
            ukuran_baru = (
                max(1, int(potongan_pil.width * SKALA_POTONGAN_MOSAIK)),
                max(1, int(potongan_pil.height * SKALA_POTONGAN_MOSAIK))
            )

            potongan_pil = potongan_pil.resize(
                ukuran_baru,
                Image.Resampling.LANCZOS
            )

        daftar_potongan.append((str(urutan), potongan_pil))
        koordinat_jejak[str(urutan)] = (x1, y1, x2, y2)

    total_balon = len(daftar_potongan)

    if total_balon == 0:
        print("  No text bubbles found~")

        output_path = image_path.rsplit(".", 1)[0] + "_translated.png"
        img_pil_utama.save(output_path)

        return output_path

    print(f"  Found {total_balon} speech bubbles...")

    margin_kiri_nomor = MARGIN_KIRI_NOMOR
    margin_kanan = MARGIN_KANAN
    jarak_antar_potongan = JARAK_ANTAR_POTONGAN

    daftar_potongan = perkecil_daftar_potongan_jika_mosaik_terlalu_tinggi(
        daftar_potongan,
        max_tinggi_mosaik=MAX_TINGGI_MOSAIK,
        jarak_antar_potongan=jarak_antar_potongan,
        padding_atas_bawah=20
    )

    lebar_mosaik = max(
        LEBAR_MOSAIK_MIN,
        max([p.width for _, p in daftar_potongan]) + margin_kiri_nomor + margin_kanan
    )

    tinggi_mosaik = (
        sum([p.height for _, p in daftar_potongan])
        + (total_balon * jarak_antar_potongan)
        + 20
    )

    kanvas_mosaik = Image.new(
        "RGB",
        (lebar_mosaik, tinggi_mosaik),
        color=(255, 255, 255)
    )

    draw_mosaik = ImageDraw.Draw(kanvas_mosaik)

    y_offset = 10

    font_nomor = ImageFont.load_default()

    try:
        font_nomor = ImageFont.truetype(FONT_MANGA, 40)
    except:
        pass

    for nomor, pot in daftar_potongan:
        draw_mosaik.text(
            (5, y_offset + (pot.height // 2) - 20),
            nomor,
            fill=(255, 0, 0),
            font=font_nomor
        )

        kanvas_mosaik.paste(pot, (margin_kiri_nomor, y_offset))

        y_offset += pot.height + jarak_antar_potongan

    temp_mosaik_dir = os.path.join(ROOT_DIR, "cypy_cache")
    os.makedirs(temp_mosaik_dir, exist_ok=True)

    mosaik_path = os.path.join(
        temp_mosaik_dir,
        f"mosaic_preview_{os.path.basename(image_path)}"
    )

    kanvas_mosaik.save(mosaik_path)

    print("  Translating text...")

    hasil_terjemahan = terjemahkan_mosaik(kanvas_mosaik)

    if not hasil_terjemahan:
        print("  [!] Translation failed.")
        return None

    if MANUAL_TRANSLATION_OVERRIDE:
        hasil_terjemahan.update(MANUAL_TRANSLATION_OVERRIDE)

    for nomor, teks in hasil_terjemahan.items():
        if nomor in koordinat_jejak:
            if teks.upper() != "SKIP" and teks.strip() != "":
                x1, y1, x2, y2 = koordinat_jejak[nomor]

                w = max(1, x2 - x1)
                h = max(1, y2 - y1)
                rasio = w / float(h)
                luas_ratio = (w * h) / float(max(1, lebar_img * tinggi_img))

                if rasio >= 3.2 and w >= lebar_img * 0.35:
                    continue

                if luas_ratio >= 0.035 and rasio >= 2.8:
                    continue

                box_gepeng_mencurigakan = (
                    rasio >= RASIO_BOX_GEPENG
                    and w >= lebar_img * LEBAR_BOX_GEPENG_RATIO
                    and h <= tinggi_img * TINGGI_BOX_GEPENG_RATIO
                )

                if PAKAI_PATCH_UNTUK_BOX_GEPENG and box_gepeng_mencurigakan:
                    tulis_teks_di_balon(
                        draw_utama,
                        teks,
                        x1,
                        y1,
                        x2,
                        y2,
                        background_patch=True
                    )

                else:
                    margin_x = int((x2 - x1) * 0.12)
                    margin_y = int((y2 - y1) * 0.12)

                    overlay = Image.new(
                        "RGBA",
                        img_pil_utama.size,
                        (255, 255, 255, 0)
                    )

                    draw_overlay = ImageDraw.Draw(overlay)

                    draw_overlay.ellipse(
                        [
                            x1 + margin_x,
                            y1 + margin_y,
                            x2 - margin_x,
                            y2 - margin_y
                        ],
                        fill=(255, 255, 255, 255)
                    )

                    overlay_blurred = overlay.filter(ImageFilter.GaussianBlur(radius=8))

                    img_pil_utama.paste(overlay_blurred, (0, 0), overlay_blurred)

                    tulis_teks_di_balon(
                        draw_utama,
                        teks,
                        x1,
                        y1,
                        x2,
                        y2,
                        background_patch=False
                    )

    time.sleep(3)

    output_path = image_path.rsplit(".", 1)[0] + "_translated.png"

    img_pil_utama.save(output_path)

    return output_path


def mulai_ritual_pdf(pdf_path, yolo_model):
    """Processes a PDF page-by-page, and binds them back together~ ♪"""
    print(f"\nProcessing PDF: {os.path.basename(pdf_path)}")

    doc = fitz.open(pdf_path)

    temp_dir = os.path.join(ROOT_DIR, "cypy_cache")
    os.makedirs(temp_dir, exist_ok=True)

    translated_images_paths = []

    for page_num in range(len(doc)):
        print(f"Page {page_num + 1}/{len(doc)}...")

        page = doc.load_page(page_num)

        # Increase dpi to 400 if text appears blurry.
        pix = page.get_pixmap(dpi=300)

        img_path = os.path.join(temp_dir, f"page_{page_num}.png")

        pix.save(img_path)

        hasil_path = proses_satu_gambar(img_path, yolo_model)

        if hasil_path:
            translated_images_paths.append(hasil_path)

    if translated_images_paths:
        print("Saving final PDF...")

        images = [
            Image.open(img).convert("RGB")
            for img in translated_images_paths
        ]

        output_pdf_path = pdf_path.rsplit(".", 1)[0] + "_translated.pdf"

        images[0].save(
            output_pdf_path,
            save_all=True,
            append_images=images[1:]
        )

        print(f"Done! Saved at: {output_pdf_path}")

        for path in translated_images_paths:
            if os.path.exists(path):
                os.remove(path)

        for page_num in range(len(doc)):
            img_path = os.path.join(temp_dir, f"page_{page_num}.png")

            if os.path.exists(img_path):
                os.remove(img_path)
