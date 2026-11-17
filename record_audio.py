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
        "default_text": "Hello! This Call is from PRIDE Online Education, Belagavi. Are you a BCA student looking for an internship? In Pride Online Education Belagavi we offer internship programs in Python, Java, Artificial Intelligence, Machine Learning, Data Science, and Cyber Security. Both online and offline options are available, along with an internship certificate. Are you Interested in knowing more? Press 1 to receive complete details on WhatsApp. Thank you for your time. Have a great day!"
    },
    "2": {
        "name": "01 | BCA Internship Program (Hindi / Hinglish)",
        "file": "bca_internship_hi.wav",
        "lang": "hi",
        "default_text": "हेलो! यह कॉल PRIDE Online Education, Belagavi से है। क्या आप एक BCA student हैं और internship ढूंढ रहे हैं? Pride Online Education Belagavi में हम Python, Java, Artificial Intelligence, Machine Learning, Data Science, और Cyber Security में internship programs offer करते हैं। Online और offline दोनों options available हैं, साथ में internship certificate भी मिलेगा। क्या आप और जानना चाहते हैं? WhatsApp पर complete details पाने के लिए 1 दबाएं। Thank you आपके time के लिए. Have a great day!"
    },
    "3": {
        "name": "01 | BCA Internship Program (Kannada / Kanglish)",
        "file": "bca_internship_kn.wav",
        "lang": "kn",
        "default_text": "ಹಲೋ! ಈ call PRIDE Online Education, Belagavi ಇಂದ. ನೀವು internship ಹುಡುಕುತ್ತಿರುವ BCA student ಆಗಿದ್ದೀರಾ? Pride Online Education Belagavi ನಲ್ಲಿ ನಾವು Python, Java, Artificial Intelligence, Machine Learning, Data Science, ಮತ್ತು Cyber Security ನಲ್ಲಿ internship programs offer ಮಾಡ್ತಿದ್ದೇವೆ. Online ಮತ್ತು offline ಎರಡೂ options available ಇವೆ, ಜೊತೆಗೆ internship certificate ಕೂಡ ಸಿಗುತ್ತೆ. ಹೆಚ್ಚು ತಿಳಿಯಲು interested ಇದ್ದೀರಾ? WhatsApp ನಲ್ಲಿ complete details ಪಡೆಯಲು 1 ಒತ್ತಿ. Thank you ನಿಮ್ಮ ಸಮಯಕ್ಕೆ. Have a great day!"
    },
    "4": {
        "name": "02 | Online & Distance Education (English)",
        "file": "distance_education_en.wav",
        "lang": "en",
        "default_text": "Hello! This Call is from PRIDE Online Education, Belagavi. Are you planning to continue your education or complete your degree? In PRIDE Online Education, Belagavi We offer SSLC and PUC through NIOS, with undergraduate programs like B.A, B.S.C, B.B.A, B.Com,and B.C.A , as well as postgraduate programs like M.A, M.Com, M.B.A, and M.C.A. You can learn at your own pace with flexible study options, affordable fees, and complete admission guidance. Would you like to know more about the courses? Press 1 to receive details on WhatsApp. Thank you, and have a wonderful day."
    },
    "5": {
        "name": "02 | Online & Distance Education (Hindi / Hinglish)",
        "file": "distance_education_hi.wav",
        "lang": "hi",
        "default_text": "हेलो! यह कॉल प्राइड ऑनलाइन एजुकेशन, बेलगावी से है। क्या आप अपनी education continue करने या degree complete करने की सोच रहे हैं? प्राइड ऑनलाइन एजुकेशन, बेलगावी में हम NIOS के through SSLC और PUC, undergraduate programs जैसे B.A, B.S.C, B.B.A, B.Com, B.C.A, और postgraduate programs जैसे M.A, M.Com, M.B.A, और M.C.A offer करते हैं। आप flexible study options, affordable fees, और complete admission guidance के साथ अपनी pace पर learn कर सकते हैं। क्या आप courses के बारे में और जानना चाहते हैं? WhatsApp पर details पाने के लिए 1 दबाएं। Thank you, and have a wonderful day!"
    },
    "6": {
        "name": "02 | Online & Distance Education (Kannada / Kanglish)",
        "file": "distance_education_kn.wav",
        "lang": "kn",
        "default_text": "ಹಲೋ! ಈ call PRIDE Online Education, Belagavi ಇಂದ. ನೀವು ನಿಮ್ಮ education continue ಮಾಡಲು ಅಥವಾ degree complete ಮಾಡಲು plan ಮಾಡ್ತಿದ್ದೀರಾ? PRIDE Online Education, Belagavi ನಲ್ಲಿ ನಾವು NIOS ಮೂಲಕ SSLC ಮತ್ತು PUC, undergraduate programs ಆದ B A, B Com, B B A, B C A, B S C, ಹಾಗೆಯೇ postgraduate programs ಆದ M A, M Com, M B A, ಮತ್ತು M C A offer ಮಾಡ್ತಿದ್ದೇವೆ. Flexible study options, affordable fees, ಮತ್ತು complete admission guidance ನೊಂದಿಗೆ ನೀವು ನಿಮ್ಮದೇ speed ನಲ್ಲಿ ಕಲಿಯಬಹುದು. Courses ಬಗ್ಗೆ ಹೆಚ್ಚು ತಿಳಿಯಲು interested ಇದ್ದೀರಾ? WhatsApp ನಲ್ಲಿ details ಪಡೆಯಲು 1 ಒತ್ತಿ. Thank you, and have a wonderful day!"
    },
    "7": {
        "name": "03 | DEEP Courses (English)",
        "file": "deep_courses_en.wav",
        "lang": "en",
        "default_text": "Hello! This Call is from PRIDE Online Education, Belagavi. Are you interested to learn advanced computer and professional skills? In PRIDE Online Education, Belagavi We offer over 250 plus online courses through DEEP, including Programming, Hardware and Networking, Graphic Designing, and career-oriented training. Learn from home, at your own pace, with affordable fees. Flat 50% off on all courses. Interested in exploring the courses? Press 1 to receive the course list and details on WhatsApp. Thank you for your time. Have a great day!"
    },
    "8": {
        "name": "03 | DEEP Courses (Hindi / Hinglish)",
        "file": "deep_courses_hi.wav",
        "lang": "hi",
        "default_text": "हेलो! यह कॉल PRIDE Online Education, Belagavi से है। क्या आप advanced computer और professional skills सीखना चाहते हैं? PRIDE Online Education, Belagavi में हम DEEP के through 250 plus online courses offer करते हैं, जिसमें Programming, Hardware and Networking, Graphic Designing, और career-oriented training शामिल हैं। घर बैठे, अपनी pace पर, affordable fees में सीखें। सभी courses पर flat 50% off है। क्या आप courses explore करना चाहते हैं? WhatsApp पर course list और details पाने के लिए 1 दबाएं। Thank you आपके time के लिए. Have a great day!"
    },
    "9": {
        "name": "03 | DEEP Courses (Kannada / Kanglish)",
        "file": "deep_courses_kn.wav",
        "lang": "kn",
        "default_text": "ಹಲೋ! ಈ call PRIDE Online Education, Belagavi ಇಂದ. ನೀವು advanced computer ಮತ್ತು professional skills ಕಲಿಯಲು interested ಇದ್ದೀರಾ? PRIDE Online Education, Belagavi ನಲ್ಲಿ ನಾವು DEEP ಮೂಲಕ Programming, Hardware and Networking, Graphic Designing, ಮತ್ತು career-oriented training ಸೇರಿದಂತೆ 250 plus online courses offer ಮಾಡ್ತಿದ್ದೇವೆ. ಮನೆಯಿಂದಲೇ, ನಿಮ್ಮದೇ speed ನಲ್ಲಿ, affordable fees ನಲ್ಲಿ ಕಲಿಯಿರಿ. ಎಲ್ಲಾ courses ಮೇಲೆ flat 50% discount ಇದೆ. Courses explore ಮಾಡಲು interested ಇದ್ದೀರಾ? WhatsApp ನಲ್ಲಿ course list ಮತ್ತು details ಪಡೆಯಲು 1 ಒತ್ತಿ. Thank you ನಿಮ್ಮ ಸಮಯಕ್ಕೆ. Have a great day!"
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
