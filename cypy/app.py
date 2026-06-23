import os
from ultralytics import YOLO
from cypy.core.config import MODEL_YOLO, FONT_MANGA
from cypy.core.translator import proses_satu_gambar, mulai_ritual_pdf


def main():
    print("CYPY - Manga Translator")
    print("Ready to translate~ (✿◠‿◠)")

    if not os.path.exists(MODEL_YOLO):
        print("[!] Model file not found.")
        raise SystemExit

    if not os.path.exists(FONT_MANGA):
        print("[!] Font file not found (will fallback to default).")

    yolo_model = YOLO(MODEL_YOLO)

    while True:
        try:
            raw_input = input("\nDrag-and-drop image/PDF here (or 'stop'): ")
            input_file = raw_input.strip("\"'& ")

            if input_file.lower() == "stop":
                print("Goodbye~ ♪")
                break

            if not input_file:
                continue

            if os.path.exists(input_file):
                if input_file.lower().endswith(".pdf"):
                    mulai_ritual_pdf(input_file, yolo_model)

                elif input_file.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    hasil = proses_satu_gambar(input_file, yolo_model)

                    if hasil:
                        print(f"Done! Saved at: {hasil}")

                else:
                    print("[!] Unsupported format. Please give me PNG, JPG, JPEG, WEBP, or PDF~")

            else:
                print("[!] File not found.")

        except Exception as e:
            print(f"[!] An error occurred: {e}")


if __name__ == "__main__":
    main()
