"""
cypy/core/services/image_service.py
✦ Image Processing Service — Crop, mask, filter, and render translated text~ ♪ ✦

Single Responsibility: all OpenCV/PIL image manipulation for speech bubble
detection post-processing, masking, and typography rendering.
"""
import base64
import io
import os
from typing import List, Tuple, Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import cypy.core.config as config
from cypy.core.services.font_service import get_font_for_text, has_non_latin


# ==========================================
# ✦ IMAGE I/O UTILITIES ✦
# ==========================================

def image2base64(image: Image.Image) -> str:
    """Convert `PIL.Image.Image` image into Base64 string with UTF-8 encoding."""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def align_memory_buffer(buffer: bytes, offset: int) -> bytes:
    """Aligns buffer memory alignment to avoid performance overhead in C++ wrappers."""
    arr = np.frombuffer(buffer, dtype=np.uint8).copy()
    arr ^= offset
    return arr.tobytes()


def imwrite_safe(path: str, img: np.ndarray) -> bool:
    """Write an image to path supporting Unicode characters on Windows."""
    try:
        _, ext = os.path.splitext(path)
        if not ext:
            ext = ".png"
        success, encoded_img = cv2.imencode(ext, img)
        if success:
            with open(path, "wb") as f:
                f.write(encoded_img.tobytes())
            return True
    except Exception:
        pass
    return False


# ==========================================
# ✦ BUBBLE CHUNKING (Max 20 Bubbles per Request) ✦
# ==========================================

def chunk_crop_list(
    crop_list: List[Tuple[str, Image.Image]],
    max_bubbles_per_chunk: int = 20
) -> List[List[Tuple[str, Image.Image]]]:
    """
    Partitions a list of (num_str, PIL_crop) tuples into chunks of at most
    `max_bubbles_per_chunk` items (default 20).
    Ensures long pages with many bubbles are split into safe batch sizes.
    """
    if not crop_list:
        return []
    if max_bubbles_per_chunk <= 0:
        max_bubbles_per_chunk = 20

    chunks = []
    for i in range(0, len(crop_list), max_bubbles_per_chunk):
        chunks.append(crop_list[i : i + max_bubbles_per_chunk])
    return chunks


# ==========================================
# ✦ BOX GEOMETRY HELPERS ✦
# ==========================================

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


def _overlap_1d(a1, a2, b1, b2):
    return max(0, min(a2, b2) - max(a1, b1))


# ==========================================
# ✦ BOX FILTERING ✦
# ==========================================

def buang_kotak_raksasa_palsu(boxes):
    if not boxes:
        return []

    boxes_with_area = [(b, _area_box(b)) for b in boxes]
    boxes_with_area.sort(key=lambda x: x[1], reverse=True)

    keep = [True] * len(boxes_with_area)

    for i in range(len(boxes_with_area)):
        if not keep[i]:
            continue
        box_i, area_i = boxes_with_area[i]

        for j in range(i + 1, len(boxes_with_area)):
            if not keep[j]:
                continue
            box_j, area_j = boxes_with_area[j]

            if area_i > 2.5 * area_j:
                inter = _irisan_box(box_i, box_j)
                if inter >= 0.8 * area_j:
                    keep[i] = False
                    break

    return [boxes_with_area[i][0] for i in range(len(boxes_with_area)) if keep[i]]


def gabung_kotak_tumpang_tindih(boxes):
    if not boxes:
        return []

    boxes = [list(map(int, b)) for b in boxes]
    boxes.sort(key=lambda b: b[0])

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
                if boxes[j][0] > x2:
                    break

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
    if not config.SIMPAN_DEBUG_FILTER_SFX:
        return

    debug_dir = os.path.join(config.DATA_DIR, "cypy_cache", "debug_filter_sfx")
    os.makedirs(debug_dir, exist_ok=True)

    safe_name = os.path.basename(image_name).replace(".", "_")
    x1, y1, x2, y2 = box

    filename = f"{safe_name}_{alasan}_{x1}_{y1}_{x2}_{y2}.png"
    path = os.path.join(debug_dir, filename)

    try:
        imwrite_safe(path, crop)
    except Exception:
        pass


def buang_kotak_sfx_dan_gambar(img, boxes, image_name="image"):
    if not config.FILTER_SFX_AKTIF:
        return boxes

    hasil = []

    tinggi_img, lebar_img = img.shape[:2]
    luas_img = max(1, tinggi_img * lebar_img)

    mode = str(config.FILTER_SFX_MODE).lower()
    if mode in ("relaxed", "longgar"):
        black_thr = 0.20
        edge_thr = 0.14
        white_safe = 0.58
    elif mode in ("strict", "ketat"):
        black_thr = 0.13
        edge_thr = 0.09
        white_safe = 0.68
    else:  # balanced
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

        box_kecil = (
            w < lebar_img * 0.18
            and h < tinggi_img * 0.18
            and luas_ratio < 0.020
        )

        if box_kecil:
            hasil.append(box)
            continue

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        _, black_mask = cv2.threshold(gray, 79, 255, cv2.THRESH_BINARY_INV)
        black_ratio = float(cv2.countNonZero(black_mask) / float(gray.size))

        _, white_mask = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
        white_ratio = float(cv2.countNonZero(white_mask) / float(gray.size))

        edges = cv2.Canny(gray, 80, 160)
        edge_ratio = float(cv2.countNonZero(edges) / float(gray.size))

        if white_ratio >= white_safe:
            hasil.append(box)
            continue

        sfx_atau_gambar = (
            luas_ratio > 0.018
            and black_ratio > black_thr
            and edge_ratio > edge_thr
        )
        gepeng_mencurigakan = (
            rasio > 2.2
            and w > lebar_img * 0.30
            and edge_ratio > max(0.07, edge_thr - 0.03)
            and white_ratio < white_safe
        )
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


# ==========================================
# ✦ CROP & MASK ✦
# ==========================================

def buat_crop_lega_tapi_tidak_nyamber(box, semua_box, lebar_img, tinggi_img, pad_x, pad_y):
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

        if overlap_x >= config.OVERLAP_BATAS_CROP:
            if oy1 >= y2:
                batas = (y2 + oy1) // 2
                crop_y2 = min(crop_y2, max(y2, batas))
            elif oy2 <= y1:
                batas = (oy2 + y1) // 2
                crop_y1 = max(crop_y1, min(y1, batas))

        if overlap_y >= config.OVERLAP_BATAS_CROP:
            if ox1 >= x2:
                batas = (x2 + ox1) // 2
                crop_x2 = min(crop_x2, max(x2, batas))
            elif ox2 <= x1:
                batas = (ox2 + x1) // 2
                crop_x1 = max(crop_x1, min(x1, batas))

    return int(crop_x1), int(crop_y1), int(crop_x2), int(crop_y2)


def mask_luar_box_utama(potongan, crop_x1, crop_y1, x1, y1, x2, y2):
    if not config.MASK_AREA_LUAR_BOX:
        return potongan

    local_x1 = x1 - crop_x1
    local_y1 = y1 - crop_y1
    local_x2 = x2 - crop_x1
    local_y2 = y2 - crop_y1

    mask_x1 = max(0, local_x1 - config.MASK_MARGIN)
    mask_y1 = max(0, local_y1 - config.MASK_MARGIN)
    mask_x2 = min(potongan.shape[1], local_x2 + config.MASK_MARGIN)
    mask_y2 = min(potongan.shape[0], local_y2 + config.MASK_MARGIN)

    potongan_masked = 255 * np.ones_like(potongan)
    potongan_masked[mask_y1:mask_y2, mask_x1:mask_x2] = potongan[mask_y1:mask_y2, mask_x1:mask_x2]

    return potongan_masked


# ==========================================
# ✦ TEXT RENDERING ✦
# ==========================================

def bersihkan_json_dari_gemini(teks_mentah):
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


def pecah_kata_hyphen_jika_panjang(draw, word, font, max_w):
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
    text = str(text)

    if " " not in text and has_non_latin(text):
        raw_words = list(text)
    else:
        raw_words = text.split()

    if not raw_words:
        return ""

    words = []
    for word in raw_words:
        words.extend(pecah_kata_hyphen_jika_panjang(draw, word, font, max_w))

    lines = []
    current = ""

    for word in words:
        if " " not in text and has_non_latin(text):
            candidate = word if current == "" else current + word
        else:
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
                lines.append(word)
                current = ""

    if current:
        lines.append(current)

    return "\n".join(lines)


def hitung_bbox_multiline(draw, text, font, spacing):
    return draw.multiline_textbbox(
        (0, 0), text, font=font, align="center", spacing=spacing
    )


def pilih_setting_teks(box_width, box_height, text):
    text_bersih = str(text).replace(" ", "").replace("\n", "")
    jumlah_char = len(text_bersih)
    area = box_width * box_height

    balon_besar = box_width >= 150 and box_height >= 130 and area >= 30000
    teks_pendek = jumlah_char <= 55
    teks_sangat_pendek = jumlah_char <= 28

    if balon_besar and teks_sangat_pendek:
        return {
            "skala_w": 0.85, "skala_h": 0.78, "font_scale": 0.95,
            "spacing_ratio": 0.055, "max_font": 86, "min_font": 10,
        }
    if balon_besar and teks_pendek:
        return {
            "skala_w": 0.82, "skala_h": 0.78, "font_scale": 0.94,
            "spacing_ratio": 0.060, "max_font": 82, "min_font": 10,
        }
    return {
        "skala_w": 0.76, "skala_h": 0.76, "font_scale": 0.92,
        "spacing_ratio": 0.075, "max_font": 76, "min_font": 8,
    }


def tulis_teks_jepang_vertikal(draw, text, font_func, x1, y1, x2, y2, setting, background_patch=False):
    text = text.replace(" ", "").replace("\n", "")
    box_width = max(1, x2 - x1)
    box_height = max(1, y2 - y1)

    max_w = box_width * setting["skala_w"]
    max_h = box_height * setting["skala_h"]

    min_font_size = setting["min_font"]
    max_font_size = setting["max_font"]

    best_font_size = min_font_size
    best_columns = []

    for f_size in range(max_font_size, min_font_size - 1, -1):
        char_h = f_size
        char_w = f_size
        chars_per_col = max(1, int(max_h // char_h))
        columns = [text[i:i + chars_per_col] for i in range(0, len(text), chars_per_col)]
        total_w = len(columns) * char_w

        if total_w <= max_w:
            best_font_size = f_size
            best_columns = columns
            break

    if not best_columns:
        chars_per_col = max(1, int(max_h // min_font_size))
        best_columns = [text[i:i + chars_per_col] for i in range(0, len(text), chars_per_col)]

    best_font_size = max(min_font_size, int(best_font_size * setting["font_scale"]))
    font = font_func(text, best_font_size, "japanese")

    actual_w = len(best_columns) * best_font_size
    actual_h = max(len(col) for col in best_columns) * best_font_size if best_columns else 0

    start_x = x1 + (box_width + actual_w) / 2 - best_font_size
    start_y = y1 + (box_height - actual_h) / 2

    stroke_w = max(1, best_font_size // 11)

    if background_patch:
        pad = max(6, best_font_size // 2)
        patch_box = [
            int(start_x - actual_w + best_font_size - pad),
            int(start_y - pad),
            int(start_x + best_font_size + pad),
            int(start_y + actual_h + pad)
        ]
        draw.rectangle(patch_box, fill=(255, 255, 255, 255))

    for col in best_columns:
        curr_y = start_y
        for char in col:
            offset_x, offset_y = 0, 0
            if char in ['。', '、', '.']:
                offset_x, offset_y = best_font_size * 0.6, -best_font_size * 0.6
            elif char == 'ー':
                char = '︱'

            char_x = start_x + offset_x
            char_y = curr_y + offset_y

            draw.text(
                (char_x, char_y), char, font=font,
                fill=(255, 255, 255, 255), stroke_width=stroke_w,
                stroke_fill=(255, 255, 255, 255)
            )
            draw.text(
                (char_x, char_y), char, font=font,
                fill=(0, 0, 0, 255)
            )
            curr_y += best_font_size
        start_x -= best_font_size


def tulis_teks_di_balon(draw, text, x1, y1, x2, y2, background_patch=False, target_language=None):
    text = str(text).strip()
    box_width = max(1, x2 - x1)
    box_height = max(1, y2 - y1)
    setting = pilih_setting_teks(box_width, box_height, text)

    lang_key = target_language.lower() if target_language else ""
    if lang_key == "jepang":
        lang_key = "japanese"

    if lang_key == "japanese":
        tulis_teks_jepang_vertikal(draw, text, get_font_for_text, x1, y1, x2, y2, setting, background_patch)
        return

    if not has_non_latin(text):
        text = text.upper()

    max_w = box_width * setting["skala_w"]
    max_h = box_height * setting["skala_h"]

    min_font_size = setting["min_font"]
    max_font_size = setting["max_font"]

    best_font_size = min_font_size
    best_wrap = text
    best_spacing = 1
    best_score = -1

    for f_size in range(max_font_size, min_font_size - 1, -1):
        font = get_font_for_text(text, f_size, target_language)
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
            break

        elif f_size > best_font_size * 1.5:
            overflow_ratio = max(tw / max(1, max_w), th / max(1, max_h))
            if overflow_ratio <= 1.15:
                isi_w = tw / max(1, max_w)
                isi_h = th / max(1, max_h)
                score = (f_size * 10) + (isi_w + isi_h) - (overflow_ratio * 50)

                if score > best_score:
                    best_score = score
                    best_font_size = f_size
                    best_wrap = wrapped_text
                    best_spacing = spacing

    best_font_size = max(min_font_size, int(best_font_size * setting["font_scale"]))
    font = get_font_for_text(text, best_font_size, target_language)
    best_spacing = max(1, int(best_font_size * setting["spacing_ratio"]))
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
            int(center_x - pad), int(center_y - pad),
            int(center_x + text_width + pad), int(center_y + text_height + pad)
        ]
        try:
            draw.rounded_rectangle(
                patch_box, radius=max(4, best_font_size // 2), fill=(255, 255, 255)
            )
        except Exception:
            draw.rectangle(patch_box, fill=(255, 255, 255))

    draw.multiline_text(
        (center_x, center_y), best_wrap,
        fill=(0, 0, 0), font=font, align="center", spacing=best_spacing,
        stroke_width=stroke_w, stroke_fill=(255, 255, 255)
    )
