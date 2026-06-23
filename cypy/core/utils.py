import cv2
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from google.genai import types
except Exception:
    types = None

from cypy.core.config import (
    FONT_MANGA, OVERLAP_BATAS_CROP, MASK_AREA_LUAR_BOX, MASK_MARGIN,
    FILTER_SFX_AKTIF, FILTER_SFX_MODE, SIMPAN_DEBUG_FILTER_SFX,
    ROOT_DIR, MODEL_GEMINI
)


def bersihkan_json_dari_gemini(teks_mentah):
    """Cleans Gemini's raw output so it can be parsed by json.loads() ♪"""
    teks = teks_mentah.strip()

    if teks.startswith("```json"):
        teks = teks[7:].strip()

    if teks.startswith("```"):
        teks = teks[3:].strip()

    if teks.endswith("```"):
        teks = teks[:-3].strip()

    awal = teks.find("{")
    akhir = teks.rfind("}")

    if awal != -1 and akhir != -1 and akhir > awal:
        teks = teks[awal:akhir + 1]

    return teks.strip()


def panggil_gemini_dengan_config(client, gambar_mosaik_pil, prompt):
    """
    Calls Gemini with low temperature to keep it accurate~ 
    Falls back if library version doesn't support configs ♪
    """
    def check_and_raise_api_error(err):
        err_str = str(err).lower()
        if "api key expired" in err_str or "api_key_invalid" in err_str or "api key" in err_str or "api_key" in err_str:
            raise ValueError("API_KEY_ERROR")

    if types is not None:
        try:
            return client.models.generate_content(
                model=MODEL_GEMINI,
                contents=[gambar_mosaik_pil, prompt],
                config=types.GenerateContentConfig(
                    temperature=0,
                    top_p=0.1,
                    top_k=1,
                    response_mime_type="application/json"
                )
            )
        except Exception as e:
            check_and_raise_api_error(e)

            try:
                return client.models.generate_content(
                    model=MODEL_GEMINI,
                    contents=[gambar_mosaik_pil, prompt],
                    config=types.GenerateContentConfig(
                        temperature=0,
                        top_p=0.1,
                        top_k=1
                    )
                )
            except Exception as e2:
                check_and_raise_api_error(e2)

    try:
        return client.models.generate_content(
            model=MODEL_GEMINI,
            contents=[gambar_mosaik_pil, prompt],
            config={
                "temperature": 0,
                "top_p": 0.1,
                "top_k": 1,
                "response_mime_type": "application/json"
            }
        )
    except Exception as e:
        check_and_raise_api_error(e)

        try:
            return client.models.generate_content(
                model=MODEL_GEMINI,
                contents=[gambar_mosaik_pil, prompt]
            )
        except Exception as final_err:
            check_and_raise_api_error(final_err)
            raise final_err


def pecah_kata_hyphen_jika_panjang(draw, word, font, max_w):
    """
    Splits hyphenated words if they are too long. 
    Normal words without hyphens remain untouched~
    """
    word = str(word)

    bbox = draw.textbbox((0, 0), word, font=font)
    word_w = bbox[2] - bbox[0]

    if word_w <= max_w:
        return [word]

    if "-" not in word:
        return [word]

    parts = word.split("-")
    tokens = []

    for i, part in enumerate(parts):
        if part == "":
            continue

        if i < len(parts) - 1:
            tokens.append(part + "-")
        else:
            tokens.append(part)

    return tokens if tokens else [word]


def bungkus_teks_per_kata(draw, text, font, max_w):
    """
    Wraps text based on word widths. 
    Hyphenated words may be split at hyphens to allow larger font sizes~ ♪
    """
    raw_words = str(text).split()

    if not raw_words:
        return ""

    words = []
    for word in raw_words:
        words.extend(pecah_kata_hyphen_jika_panjang(draw, word, font, max_w))

    lines = []
    current = ""

    for word in words:
        candidate = word if current == "" else current + " " + word
        bbox = draw.textbbox((0, 0), candidate, font=font)
        candidate_w = bbox[2] - bbox[0]

        if candidate_w <= max_w:
            current = candidate
        else:
            if current:
                lines.append(current)
                current = word
            else:
                # If a single word is extremely long and doesn't have a hyphen,
                # we don't force split. Auto-fit will handle shrinking the font.
                lines.append(word)
                current = ""

    if current:
        lines.append(current)

    return "\n".join(lines)


def hitung_bbox_multiline(draw, text, font, spacing):
    """Calculates multiline text bounding box safely~"""
    return draw.multiline_textbbox(
        (0, 0),
        text,
        font=font,
        align="center",
        spacing=spacing
    )


def pilih_setting_teks(box_width, box_height, text):
    """
    Dynamic settings to maximize space in large bubbles with short text, 
    while keeping small/dense bubbles safe~
    """
    text_bersih = str(text).replace(" ", "").replace("\n", "")
    jumlah_char = len(text_bersih)
    area = box_width * box_height

    balon_besar = box_width >= 150 and box_height >= 130 and area >= 30000
    teks_pendek = jumlah_char <= 55
    teks_sangat_pendek = jumlah_char <= 28

    if balon_besar and teks_sangat_pendek:
        return {
            "skala_w": 0.85,
            "skala_h": 0.78,
            "font_scale": 0.95,
            "spacing_ratio": 0.055,
            "max_font": 86,
            "min_font": 7,
        }

    if balon_besar and teks_pendek:
        return {
            "skala_w": 0.82,
            "skala_h": 0.78,
            "font_scale": 0.94,
            "spacing_ratio": 0.060,
            "max_font": 82,
            "min_font": 7,
        }

    return {
        "skala_w": 0.76,
        "skala_h": 0.76,
        "font_scale": 0.92,
        "spacing_ratio": 0.075,
        "max_font": 76,
        "min_font": 6,
    }


def tulis_teks_di_balon(draw, text, x1, y1, x2, y2, background_patch=False):
    """
    Auto-fits Indonesian text into speech bubbles. 
    Wraps words neatly, allows hyphen splits, and maximizes font size~ ♪
    """
    text = str(text).upper().strip()

    box_width = max(1, x2 - x1)
    box_height = max(1, y2 - y1)

    setting = pilih_setting_teks(box_width, box_height, text)

    max_w = box_width * setting["skala_w"]
    max_h = box_height * setting["skala_h"]

    min_font_size = setting["min_font"]
    max_font_size = setting["max_font"]

    best_font_size = min_font_size
    best_wrap = text
    best_spacing = 1
    best_score = -1

    # Looking for the largest font size that fits~
    # Selecting the layout that fills the bubble most beautifully ♪
    for f_size in range(max_font_size, min_font_size - 1, -1):
        try:
            font = ImageFont.truetype(FONT_MANGA, f_size)
        except OSError:
            font = ImageFont.load_default()

        spacing = max(1, int(f_size * setting["spacing_ratio"]))
        wrapped_text = bungkus_teks_per_kata(draw, text, font, max_w)

        bbox = hitung_bbox_multiline(draw, wrapped_text, font, spacing)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        if tw <= max_w and th <= max_h:
            isi_w = tw / max(1, max_w)
            isi_h = th / max(1, max_h)
            score = (f_size * 10) + (isi_w + isi_h)

            if score > best_score:
                best_score = score
                best_font_size = f_size
                best_wrap = wrapped_text
                best_spacing = spacing

            # Since we search largest to smallest, the first match is usually the best~
            break

    # Don't shrink font size too much for big bubbles with short text~
    best_font_size = max(min_font_size, int(best_font_size * setting["font_scale"]))

    try:
        font = ImageFont.truetype(FONT_MANGA, best_font_size)
    except OSError:
        font = ImageFont.load_default()

    best_spacing = max(1, int(best_font_size * setting["spacing_ratio"]))

    # Re-wrapping with the final font size~
    best_wrap = bungkus_teks_per_kata(draw, text, font, max_w)

    bbox = hitung_bbox_multiline(draw, best_wrap, font, best_spacing)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    center_x = x1 + (box_width - text_width) / 2
    center_y = y1 + (box_height - text_height) / 2

    stroke_w = max(1, best_font_size // 11)

    if background_patch:
        pad = max(6, best_font_size // 2)

        patch_box = [
            int(center_x - pad),
            int(center_y - pad),
            int(center_x + text_width + pad),
            int(center_y + text_height + pad)
        ]

        try:
            draw.rounded_rectangle(
                patch_box,
                radius=max(4, best_font_size // 2),
                fill=(255, 255, 255)
            )
        except Exception:
            draw.rectangle(
                patch_box,
                fill=(255, 255, 255)
            )

    draw.multiline_text(
        (center_x, center_y),
        best_wrap,
        fill=(0, 0, 0),
        font=font,
        align="center",
        spacing=best_spacing,
        stroke_width=stroke_w,
        stroke_fill=(255, 255, 255)
    )


def _area_box(box):
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def _irisan_box(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    return max(0, ix2 - ix1) * max(0, iy2 - iy1)


def _perlu_digabung(a, b):
    """
    Checks if two boxes are duplicates or belong to the same bubble. 
    Won't merge if they are just close by~
    """
    area_a = _area_box(a)
    area_b = _area_box(b)

    if area_a == 0 or area_b == 0:
        return False

    inter = _irisan_box(a, b)

    if inter == 0:
        return False

    iou = inter / float(area_a + area_b - inter)
    cover_kotak_kecil = inter / float(min(area_a, area_b))

    if iou >= 0.28:
        return True

    if cover_kotak_kecil >= 0.82:
        return True

    return False


def gabung_kotak_tumpang_tindih(boxes):
    """Merges duplicate YOLO boxes without fusing separate bubbles~ ♪"""
    if not boxes:
        return []

    boxes = [list(map(int, b)) for b in boxes]
    berubah = True

    while berubah:
        berubah = False
        hasil = []
        dipakai = [False] * len(boxes)

        for i in range(len(boxes)):
            if dipakai[i]:
                continue

            x1, y1, x2, y2 = boxes[i]

            for j in range(i + 1, len(boxes)):
                if dipakai[j]:
                    continue

                if _perlu_digabung([x1, y1, x2, y2], boxes[j]):
                    ox1, oy1, ox2, oy2 = boxes[j]

                    x1 = min(x1, ox1)
                    y1 = min(y1, oy1)
                    x2 = max(x2, ox2)
                    y2 = max(y2, oy2)

                    dipakai[j] = True
                    berubah = True

            hasil.append([x1, y1, x2, y2])
            dipakai[i] = True

        boxes = hasil

    return sorted(boxes, key=lambda b: (b[1], b[0]))


def buang_kotak_ngawur(boxes, lebar_img, tinggi_img):
    """
    Discards boxes that are too wide or flat. 
    These are usually false positives from SFX, panels, or lines~ ♪
    """
    hasil = []
    luas_gambar = max(1, lebar_img * tinggi_img)

    for box in boxes:
        x1, y1, x2, y2 = box

        w = max(1, x2 - x1)
        h = max(1, y2 - y1)

        rasio = w / float(h)
        luas_ratio = (w * h) / float(luas_gambar)

        terlalu_lebar = rasio >= 3.2 and w >= lebar_img * 0.35
        terlalu_gepeng_besar = w >= lebar_img * 0.50 and h <= tinggi_img * 0.16
        terlalu_besar_tipis = luas_ratio >= 0.035 and rasio >= 2.8

        if terlalu_lebar or terlalu_gepeng_besar or terlalu_besar_tipis:
            continue

        hasil.append(box)

    return hasil


def simpan_debug_crop_filter(image_name, crop, box, alasan):
    """Saves discarded crops so you can inspect them manually if you wish~ ♪"""
    if not SIMPAN_DEBUG_FILTER_SFX:
        return

    debug_dir = os.path.join(ROOT_DIR, "cypy_cache", "debug_filter_sfx")
    os.makedirs(debug_dir, exist_ok=True)

    safe_name = os.path.basename(image_name).replace(".", "_")
    x1, y1, x2, y2 = box

    filename = f"{safe_name}_{alasan}_{x1}_{y1}_{x2}_{y2}.png"
    path = os.path.join(debug_dir, filename)

    try:
        cv2.imwrite(path, crop)
    except Exception:
        pass


def buang_kotak_sfx_dan_gambar(img, boxes, image_name="image"):
    """
    A safe filter to discard boxes that are likely SFX or background art. 
    Conservative approach:
    - Small boxes are kept.
    - Dominant white boxes are kept.
    - Discards large boxes with dense edges and black lines~
    """
    if not FILTER_SFX_AKTIF:
        return boxes

    hasil = []

    tinggi_img, lebar_img = img.shape[:2]
    luas_img = max(1, tinggi_img * lebar_img)

    if FILTER_SFX_MODE == "longgar":
        black_thr = 0.20
        edge_thr = 0.14
        white_safe = 0.58
    elif FILTER_SFX_MODE == "ketat":
        black_thr = 0.13
        edge_thr = 0.09
        white_safe = 0.68
    else:
        black_thr = 0.16
        edge_thr = 0.11
        white_safe = 0.62

    for box in boxes:
        x1, y1, x2, y2 = map(int, box)

        w = max(1, x2 - x1)
        h = max(1, y2 - y1)
        luas_ratio = (w * h) / float(luas_img)
        rasio = w / float(h)

        crop = img[y1:y2, x1:x2]

        if crop.size == 0:
            continue

        # Main safeguard: keep small boxes safe, as tiny speech bubbles can be small~
        box_kecil = (
            w < lebar_img * 0.18
            and h < tinggi_img * 0.18
            and luas_ratio < 0.020
        )

        if box_kecil:
            hasil.append(box)
            continue

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        black_ratio = float(np.mean(gray < 80))
        white_ratio = float(np.mean(gray > 220))

        edges = cv2.Canny(gray, 80, 160)
        edge_ratio = float(np.mean(edges > 0))

        # If mostly white, it's likely a speech bubble! We'll keep it~
        if white_ratio >= white_safe:
            hasil.append(box)
            continue

        # SFX/background patterns usually have lots of black lines and dense edges~
        sfx_atau_gambar = (
            luas_ratio > 0.018
            and black_ratio > black_thr
            and edge_ratio > edge_thr
        )

        # Wide/flat boxes with dense edges are likely panel borders or SFX~
        gepeng_mencurigakan = (
            rasio > 2.2
            and w > lebar_img * 0.30
            and edge_ratio > max(0.07, edge_thr - 0.03)
            and white_ratio < white_safe
        )

        # Large non-white boxes with dense edges are usually drawings or characters~
        gambar_besar_mencurigakan = (
            luas_ratio > 0.045
            and white_ratio < 0.55
            and edge_ratio > 0.075
        )

        if sfx_atau_gambar or gepeng_mencurigakan or gambar_besar_mencurigakan:
            simpan_debug_crop_filter(
                image_name=image_name,
                crop=crop,
                box=box,
                alasan="sfx"
            )
            continue

        hasil.append(box)

    return hasil


def _overlap_1d(a1, a2, b1, b2):
    return max(0, min(a2, b2) - max(a1, b1))


def buat_crop_lega_tapi_tidak_nyamber(box, semua_box, lebar_img, tinggi_img, pad_x, pad_y):
    """
    Expands crop area slightly so it doesn't get clipped. 
    Limits crop at midpoint if neighbors are aligned~
    """
    x1, y1, x2, y2 = box

    crop_x1 = max(0, x1 - pad_x)
    crop_y1 = max(0, y1 - pad_y)
    crop_x2 = min(lebar_img, x2 + pad_x)
    crop_y2 = min(tinggi_img, y2 + pad_y)

    box_w = max(1, x2 - x1)
    box_h = max(1, y2 - y1)

    for other in semua_box:
        if other == box:
            continue

        ox1, oy1, ox2, oy2 = other

        other_w = max(1, ox2 - ox1)
        other_h = max(1, oy2 - oy1)

        overlap_x = _overlap_1d(x1, x2, ox1, ox2) / float(min(box_w, other_w))
        overlap_y = _overlap_1d(y1, y2, oy1, oy2) / float(min(box_h, other_h))

        if overlap_x >= OVERLAP_BATAS_CROP:
            if oy1 >= y2:
                batas = (y2 + oy1) // 2
                crop_y2 = min(crop_y2, max(y2, batas))

            elif oy2 <= y1:
                batas = (oy2 + y1) // 2
                crop_y1 = max(crop_y1, min(y1, batas))

        if overlap_y >= OVERLAP_BATAS_CROP:
            if ox1 >= x2:
                batas = (x2 + ox1) // 2
                crop_x2 = min(crop_x2, max(x2, batas))

            elif ox2 <= x1:
                batas = (ox2 + x1) // 2
                crop_x1 = max(crop_x1, min(x1, batas))

    return int(crop_x1), int(crop_y1), int(crop_x2), int(crop_y2)


def mask_luar_box_utama(potongan, crop_x1, crop_y1, x1, y1, x2, y2):
    """
    Masks the area outside the YOLO box with white. 
    Keeps external text from confusing Gemini~ ♪
    """
    if not MASK_AREA_LUAR_BOX:
        return potongan

    local_x1 = x1 - crop_x1
    local_y1 = y1 - crop_y1
    local_x2 = x2 - crop_x1
    local_y2 = y2 - crop_y1

    mask_x1 = max(0, local_x1 - MASK_MARGIN)
    mask_y1 = max(0, local_y1 - MASK_MARGIN)
    mask_x2 = min(potongan.shape[1], local_x2 + MASK_MARGIN)
    mask_y2 = min(potongan.shape[0], local_y2 + MASK_MARGIN)

    potongan_masked = 255 * np.ones_like(potongan)
    potongan_masked[mask_y1:mask_y2, mask_x1:mask_x2] = potongan[mask_y1:mask_y2, mask_x1:mask_x2]

    return potongan_masked
