import os
import sys
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load environment variables
load_dotenv()

AUDIO_DIR = Path(__file__).parent / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

# =====================================================================
# 1. Sarvam AI Text-to-Speech (Kannada & Indian Languages)
# =====================================================================
def generate_sarvam_tts(
    text: str,
    output_filename: str,
    api_key: str = None,
    language_code: str = "kn-IN",  # Kannada (kn-IN)
    speaker: str = "tarun",        # Kannada Counselor Voice (bulbul:v3)
    model: str = "bulbul:v3",
    pace: float = 0.82
) -> Path:
    """
    Generate speech using Sarvam AI TTS (Bulbul v3).
    Supports Kannada (kn-IN) with natural counselors (tarun, anand, gokul, vijay, kavitha).
    """
    api_key = api_key or os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise ValueError("SARVAM_API_KEY is not set. Please set it in .env or pass it as an argument.")

    url = "https://api.sarvam.ai/text-to-speech"
    payload = {
        "text": text,
        "language_code": language_code,
        "speaker": speaker,
        "model": model,
        "pace": pace,
        "speech_sample_rate": 48000  # 48kHz HD Audio for crystal-clear telephony
    }
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }

    print(f"[*] Calling Sarvam AI TTS (Model: {model}, Language: {language_code}, Speaker: {speaker})...")
    response = requests.post(url, json=payload, headers=headers, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Sarvam AI API Error ({response.status_code}): {response.text}")

    data = response.json()
    if "audios" not in data or not data["audios"]:
        raise RuntimeError(f"Unexpected response format from Sarvam AI: {data}")

    audio_base64 = data["audios"][0]
    output_path = AUDIO_DIR / output_filename
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(audio_base64))

    print(f"[+] Audio successfully saved to: {output_path}")
    return output_path


# =====================================================================
# 2. Cartesia Text-to-Speech
# =====================================================================
# Aarav - Old Time Storyteller (Cartesia Voice ID)
AARAV_VOICE_ID = "39d518b7-fd0b-4676-9b8b-29d64ff31e12"

def generate_cartesia_tts(
    text: str,
    output_filename: str,
    api_key: str = None,
    voice_id: str = None,
    model_id: str = "sonic-3",
    sample_rate: int = 48000,
    speed: float = 0.65,
    language: str = "en"
) -> Path:
    """
    Generate speech using Cartesia Sonic-3 with Aarav's voice and controlled slow pacing (speed=0.65).
    """
    api_key = api_key or os.getenv("CARTESIA_API_KEY")
    if not api_key:
        raise ValueError("CARTESIA_API_KEY is not set. Please set it in .env or pass it as an argument.")

    voice_id = voice_id or AARAV_VOICE_ID

    url = "https://api.cartesia.ai/tts/bytes"
    payload = {
        "model_id": model_id,
        "transcript": text,
        "voice": {
            "mode": "id",
            "id": voice_id
        },
        "generation_config": {
            "speed": speed
        },
        "output_format": {
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": sample_rate
        },
        "language": language
    }
    headers = {
        "Cartesia-Version": "2024-06-10",
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    print(f"[*] Calling Cartesia TTS (Model: {model_id}, Voice ID: {voice_id})...")
    response = requests.post(url, json=payload, headers=headers, timeout=30, stream=True)

    if response.status_code != 200:
        raise RuntimeError(f"Cartesia API Error ({response.status_code}): {response.text}")

    output_path = AUDIO_DIR / output_filename
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=4096):
            if chunk:
                f.write(chunk)

    # Fix Cartesia streaming WAV header chunk size
    try:
        with open(output_path, "r+b") as f:
            f.seek(0, 2)
            total_size = f.tell()
            f.seek(12)
            while True:
                sub = f.read(4)
                if not sub or len(sub) < 4:
                    break
                if sub == b"data":
                    actual_data_size = total_size - f.tell() - 4
                    f.write(actual_data_size.to_bytes(4, "little"))
                    break
                else:
                    chunk_len = int.from_bytes(f.read(4), "little")
                    f.seek(chunk_len, 1)
            f.seek(4)
            f.write((total_size - 8).to_bytes(4, "little"))
    except Exception:
        pass

    print(f"[+] Audio successfully saved to: {output_path}")
    return output_path


# =====================================================================
# 3. Pride Online Education - Multilingual Scripts (EN, HI, KN)
# =====================================================================
PRESET_TEMPLATES = {
    "1": {
        "name": "01 | BCA Internship Program (English)",
        "file": "bca_internship_en.wav",
        "lang": "en",
        "default_text": "Hello! This is from PRIDE Online Education, Belagavi. Are you a BCA student looking for an internship? We offer internship program in Python, Java, Artificial Intelligence, Machine Learning, Data Science, and Cyber Security. Both online and offline options are available, along with an internship certificate. Interested in knowing more? Press 1 to receive complete details on WhatsApp. Thank you for your time. Have a great day!"
    },
    "2": {
        "name": "01 | BCA Internship Program (Hindi)",
        "file": "bca_internship_hi.wav",
        "lang": "hi",
        "default_text": "नमस्ते! यह प्राइड ऑनलाइन एजुकेशन, बेलगावी से है। क्या आप बीसीए छात्र हैं और इंटर्नशिप की तलाश में हैं? हम पायथन, जावा, आर्टिफिशियल इंटेलिजेंस, मशीन लर्निंग, डेटा साइंस और साइबर सिक्योरिटी में इंटर्नशिप प्रोग्राम प्रदान करते हैं। ऑनलाइन और ऑफलाइन दोनों विकल्प उपलब्ध हैं, साथ में इंटर्नशिप सर्टिफिकेट भी दिया जाएगा। अधिक जानने के इच्छुक हैं? व्हाट्सएप पर पूरा विवरण प्राप्त करने के लिए 1 दबाएं। आपके समय के लिए धन्यवाद। आपका दिन शुभ हो!"
    },
    "3": {
        "name": "01 | BCA Internship Program (Kannada)",
        "file": "bca_internship_kn.wav",
        "lang": "kn",
        "default_text": "ನಮಸ್ಕಾರ! ಇದು ಪ್ರೈಡ್ ಆನ್‌ಲೈನ್ ಎಜುಕೇಶನ್, ಬೆಳಗಾವಿ. ನೀವು ಇಂಟರ್ನ್‌ಶಿಪ್ ಹುಡುಕುತ್ತಿರುವ ಬಿಸಿಎ ವಿದ್ಯಾರ್ಥಿಯಾಗಿದ್ದೀರಾ? ನಾವು ಪೈಥಾನ್, ಜಾವಾ, ಆರ್ಟಿಫಿಶಿಯಲ್ ಇಂಟೆಲಿಜೆನ್ಸ್, ಮೆಷಿನ್ ಲರ್ನಿಂಗ್, ಡೇಟಾ ಸೈನ್ಸ್ ಮತ್ತು ಸೈಬರ್ ಸೆಕ್ಯುರಿಟಿಗಳಲ್ಲಿ ಇಂಟರ್ನ್‌ಶಿಪ್ ಪ್ರೋಗ್ರಾಂಗಳನ್ನು ಒದಗಿಸುತ್ತೇವೆ. ಆನ್‌ಲೈನ್ ಮತ್ತು ಆಫ್‌ಲೈನ್ ಎರಡೂ ಆಯ್ಕೆಗಳು ಲಭ್ಯವಿದ್ದು, ಇಂಟರ್ನ್‌ಶಿಪ್ ಪ್ರಮಾಣಪತ್ರವೂ ಸಿಗಲಿದೆ. ಹೆಚ್ಚಿನ ಮಾಹಿತಿ ತಿಳಿಯಲು ಆಸಕ್ತಿ ಇದೆಯೇ? ವಾಟ್ಸಾಪ್‌ನಲ್ಲಿ ಸಂಪೂರ್ಣ ವಿವರಗಳನ್ನು ಪಡೆಯಲು 1 ಒತ್ತಿ. ನಿಮ್ಮ ಅಮೂಲ್ಯ ಸಮಯಕ್ಕೆ ಧನ್ಯವಾದಗಳು. ಶುಭ ದಿನ!"
    },
    "4": {
        "name": "02 | Online & Distance Education (English)",
        "file": "distance_education_en.wav",
        "lang": "en",
        "default_text": "Hello! This is from PRIDE Online Education, Belagavi. Are you planning to continue your education or complete your degree? We offer S. S. L. C. and P. U. C. through N. I. O. S., along with undergraduate and postgraduate programs such as B. A., B. Com, B. B. A., B. C. A., B. S. C., M. A., M. Com, M. B. A., and M. C. A. You can learn at your own pace with flexible study options, affordable fees, and complete admission guidance. Would you like to know more about the courses? Press 1 to receive details on WhatsApp. Thank you, and have a wonderful day."
    },
    "5": {
        "name": "02 | Online & Distance Education (Hindi)",
        "file": "distance_education_hi.wav",
        "lang": "hi",
        "default_text": "नमस्ते! यह प्राइड ऑनलाइन एजुकेशन, बेलगावी से है। क्या आप अपनी शिक्षा जारी रखने या अपनी डिग्री पूरी करने की योजना बना रहे हैं? हम एन. आई. ओ. एस. के माध्यम से एस. एस. एल. सी. और पी. यू. सी., तथा बी. ए., बी. कॉम, बी. बी. ए., बी. सी. ए., बी. एस. सी., एम. ए., एम. कॉम, एम. बी. ए., और एम. सी. ए. जैसे स्नातक और स्नातकोत्तर पाठ्यक्रम प्रदान करते हैं। आप लचीले अध्ययन विकल्पों, किफायती फीस और पूर्ण प्रवेश मार्गदर्शन के साथ अपनी गति से सीख सकते हैं। क्या आप कोर्सेस के बारे में अधिक जानना चाहते हैं? व्हाट्सएप पर विवरण प्राप्त करने के लिए 1 दबाएं। धन्यवाद, आपका दिन शुभ हो।"
    },
    "6": {
        "name": "02 | Online & Distance Education (Kannada)",
        "file": "distance_education_kn.wav",
        "lang": "kn",
        "default_text": "ನಮಸ್ಕಾರ! ಇದು ಪ್ರೈಡ್ ಆನ್‌ಲೈನ್ ಎಜುಕೇಶನ್, ಬೆಳಗಾವಿ. ನೀವು ನಿಮ್ಮ ಶಿಕ್ಷಣವನ್ನು ಮುಂದುವರಿಸಲು ಅಥವಾ ನಿಮ್ಮ ಪದವಿಯನ್ನು ಪೂರ್ಣಗೊಳಿಸಲು ಯೋಜಿಸುತ್ತಿದ್ದೀರಾ? ನಾವು ಎನ್. ಐ. ಓ. ಎಸ್. ಮೂಲಕ ಎಸ್. ಎಸ್. ಎಲ್. ಸಿ. ಮತ್ತು ಪಿ. ಯು. ಸಿ., ಹಾಗೂ ಬಿ. ಎ., ಬಿ. ಕಾಂ., ಬಿ. ಬಿ. ಎ., ಬಿ. ಸಿ. ಎ., ಬಿ. ಎಸ್. ಸಿ., ಎಂ. ಎ., ಎಂ. ಕಾಂ., ಎಂ. ಬಿ. ಎ., ಮತ್ತು ಎಂ. ಸಿ. ಎ. ಪದವಿ ಮತ್ತು ಸ್ನಾತಕೋತ್ತರ ಕೋರ್ಸ್‌ಗಳನ್ನು ಒದಗಿಸುತ್ತೇವೆ. ಕೈಗೆಟುಕುವ ಶುಲ್ಕ ಮತ್ತು ಸಂಪೂರ್ಣ ಪ್ರವೇಶ ಮಾರ್ಗದರ್ಶನದೊಂದಿಗೆ ನೀವು ನಿಮ್ಮದೇ ಆದ ಸಮಯದಲ್ಲಿ ಕಲಿಯಬಹುದು. ಕೋರ್ಸ್‌ಗಳ ಬಗ್ಗೆ ಹೆಚ್ಚಿನ ಮಾಹಿತಿ ತಿಳಿಯಲು ಬಯಸುವಿರಾ? ವಾಟ್ಸಾಪ್‌ನಲ್ಲಿ ವಿವರಗಳನ್ನು ಪಡೆಯಲು 1 ಒತ್ತಿ. ಧನ್ಯವಾದಗಳು, ಶುಭ ದಿನ."
    },
    "7": {
        "name": "03 | DEEP Courses (English)",
        "file": "deep_courses_en.wav",
        "lang": "en",
        "default_text": "Hello! This is from PRIDE Online Education, Belagavi. Are you interested to learn advance computer and professional skills? We offer over 250 plus online courses through DEEP, including Programming, Hardware and Networking, Graphic Designing, and career-oriented training. Learn from home, at your own pace, with affordable fees. Flat 50% off on all courses. Interested in exploring the courses? Press 1 to receive the course list and details on WhatsApp. Thank you for your time. Have a great day!"
    },
    "8": {
        "name": "03 | DEEP Courses (Hindi)",
        "file": "deep_courses_hi.wav",
        "lang": "hi",
        "default_text": "नमस्ते! यह प्राइड ऑनलाइन एजुकेशन, बेलगावी से है। क्या आप एडवांस कंप्यूटर और प्रोफेशनल स्किल्स सीखने में रुचि रखते हैं? हम डीप प्रोग्राम के माध्यम से 250 से अधिक ऑनलाइन कोर्सेस प्रदान करते हैं, जिनमें प्रोग्रामिंग, हार्डवेयर और नेटवर्किंग, ग्राफिक डिजाइनिंग और करियर-ओरिएंटेड ट्रेनिंग शामिल हैं। घर से, अपनी गति से, किफायती फीस में सीखें। सभी कोर्सेस पर फ्लैट 50% छूट उपलब्ध है। कोर्सेस जानने के इच्छुक हैं? व्हाट्सएप पर कोर्स लिस्ट और विवरण प्राप्त करने के लिए 1 दबाएं। आपके समय के लिए धन्यवाद। आपका दिन शुभ हो!"
    },
    "9": {
        "name": "03 | DEEP Courses (Kannada)",
        "file": "deep_courses_kn.wav",
        "lang": "kn",
        "default_text": "ನಮಸ್ಕಾರ! ಇದು ಪ್ರೈಡ್ ಆನ್‌ಲೈನ್ ಎಜುಕೇಶನ್, ಬೆಳಗಾವಿ. ನೀವು ಸುಧಾರಿತ ಕಂಪ್ಯೂಟರ್ ಮತ್ತು ವೃತ್ತಿಪರ ಕೌಶಲ್ಯಗಳನ್ನು ಕಲಿಯಲು ಆಸಕ್ತಿ ಹೊಂದಿದ್ದೀರಾ? ನಾವು ಡೀಪ್ ಪ್ರೋಗ್ರಾಂ ಮೂಲಕ ಪ್ರೋಗ್ರಾಮಿಂಗ್, ಹಾರ್ಡ್‌ವೇರ್ ಮತ್ತು ನೆಟ್‌ವರ್ಕಿಂಗ್, ಗ್ರಾಫಿಕ್ ಡಿಸೈನಿಂಗ್ ಮತ್ತು ವೃತ್ತಿ ಆಧಾರಿತ ತರಬೇತಿ ಸೇರಿದಂತೆ 250 ಕ್ಕೂ ಹೆಚ್ಚು ಆನ್‌ಲೈನ್ ಕೋರ್ಸ್‌ಗಳನ್ನು ಒದಗಿಸುತ್ತೇವೆ. ಮನೆಯಿಂದಲೇ, ನಿಮ್ಮದೇ ಸಮಯದಲ್ಲಿ, ಕೈಗೆಟುಕುವ ಶುಲ್ಕದಲ್ಲಿ ಕಲಿಯಿರಿ. ಎಲ್ಲಾ ಕೋರ್ಸ್‌ಗಳ ಮೇಲೆ ಫ್ಲಾಟ್ 50% ರಿಯಾಯಿತಿ ಇದೆ. ಕೋರ್ಸ್‌ಗಳನ್ನು ತಿಳಿದುಕೊಳ್ಳಲು ಆಸಕ್ತಿ ಇದೆಯೇ? ವಾಟ್ಸಾಪ್‌ನಲ್ಲಿ ಕೋರ್ಸ್ ಪಟ್ಟಿ ಮತ್ತು ವಿವರಗಳನ್ನು ಪಡೆಯಲು 1 ಒತ್ತಿ. ನಿಮ್ಮ ಅಮೂಲ್ಯ ಸಮಯಕ್ಕೆ ಧನ್ಯವಾದಗಳು. ಶುಭ ದಿನ!"
    },
    "10": {
        "name": "Acknowledgment - Press 1 (English)",
        "file": "ack_en.wav",
        "lang": "en",
        "default_text": "Thank you for showing interest! We have noted your request. Complete details are being sent to your WhatsApp number right away. Have a wonderful day!"
    },
    "11": {
        "name": "Acknowledgment - Press 1 (Hindi)",
        "file": "ack_hi.wav",
        "lang": "hi",
        "default_text": "रुचि दिखाने के लिए धन्यवाद! आपका अनुरोध दर्ज कर लिया गया है। पूरी जानकारी तुरंत आपके व्हाट्सएप नंबर पर भेजी जा रही है। आपका दिन शुभ हो!"
    },
    "12": {
        "name": "Acknowledgment - Press 1 (Kannada)",
        "file": "ack_kn.wav",
        "lang": "kn",
        "default_text": "ಆಸಕ್ತಿ ತೋರಿಸಿದ್ದಕ್ಕಾಗಿ ಧನ್ಯವಾದಗಳು! ನಿಮ್ಮ ಕೋರಿಕೆಯನ್ನು ದಾಖಲಿಸಿಕೊಳ್ಳಲಾಗಿದೆ. ಸಂಪೂರ್ಣ ವಿವರಗಳನ್ನು ತಕ್ಷಣವೇ ನಿಮ್ಮ ವಾಟ್ಸಾಪ್ ಸಂಖ್ಯೆಗೆ ಕಳುಹಿಸಲಾಗುತ್ತಿದೆ. ಶುಭ ದಿನ!"
    }
}


def batch_generate_pride_education():
    """
    Batch generates all multilingual IVR files for Pride Online Education using Aarav.
    Pacing: speed=0.90 for English & Hindi, speed=0.70 for Kannada.
    """
    print("\n" + "=" * 65)
    print("  GENERATING PRIDE ONLINE EDUCATION MULTILINGUAL AUDIO (AARAV)  ")
    print("  Speed: 0.90 (English & Hindi) | 0.70 (Kannada)               ")
    print("=" * 65)
    for key, item in PRESET_TEMPLATES.items():
        lang = item.get("lang", "en")
        sp = 0.90 if lang in ["en", "hi"] else 0.70
        print(f"\n--- Generating {item['file']} ({item['name']}) [speed={sp}] ---")
        generate_cartesia_tts(
            text=item["default_text"],
            output_filename=item["file"],
            voice_id=AARAV_VOICE_ID,
            model_id="sonic-3",
            speed=sp,
            language=lang
        )
    print("\n[SUCCESS] All Multilingual IVR audio files generated with Aarav in ./audio/")


def main():
    print("=" * 65)
    print("   PRIDE ONLINE EDUCATION, BELAGAVI - VOICE PROMPT GENERATOR   ")
    print("   VOICE: Aarav - Old Time Storyteller (Cartesia Sonic-3)       ")
    print("=" * 65)
    print(f"Target folder: {AUDIO_DIR.resolve()}\n")

    print("Select an option:")
    for key, item in PRESET_TEMPLATES.items():
        print(f"  [{key}] {item['name']}")
    print("  [6] Custom Audio File (Enter custom filename & text)")
    print("  [7] Batch Generate All 5 Kannada Prompts with Aarav (Recommended)")

    choice = input("\nEnter choice (1-7) [default 7]: ").strip() or "7"

    if choice == "7":
        p = input("Select provider ([1] Cartesia Aarav [default], [2] Sarvam AI): ").strip()
        prov = "sarvam" if p == "2" else "cartesia"
        batch_generate_pride_education(prov)
        return

    if choice in PRESET_TEMPLATES:
        preset = PRESET_TEMPLATES[choice]
        filename = preset["file"]
        print(f"\nDefault text: \"{preset['default_text']}\"")
        custom_text = input("Press ENTER to use default text, or type custom text: ").strip()
        text_to_speak = custom_text if custom_text else preset["default_text"]
    else:
        filename = input("Enter target filename (e.g. custom.wav): ").strip()
        if not filename.endswith(".wav") and not filename.endswith(".mp3"):
            filename += ".wav"
        text_to_speak = input("Enter the Kannada text script: ").strip()

    p = input("Select provider ([1] Cartesia Aarav [default], [2] Sarvam AI): ").strip()
    prov = "sarvam" if p == "2" else "cartesia"

    if prov == "cartesia":
        generate_cartesia_tts(text_to_speak, filename, voice_id=AARAV_VOICE_ID, model_id="sonic-3")
    else:
        generate_sarvam_tts(text_to_speak, filename, language_code="kn-IN", speaker="tarun")


if __name__ == "__main__":
    main()
