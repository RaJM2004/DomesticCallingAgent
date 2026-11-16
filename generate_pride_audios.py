import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")
VOICE_ID = "39d518b7-fd0b-4676-9b8b-29d64ff31e12"  # Aarav - Old Time Storyteller
MODEL_ID = "sonic-3"
SAMPLE_RATE = 48000
SPEED = 0.65  # Deliberate, relaxed, and clear speed via generation_config

SCRIPTS = {
    # 01 | BCA Internship Program
    "bca_internship_en.wav": {
        "lang": "en",
        "text": "Hello! This is from PRIDE Online Education, Belagavi. Are you a BCA student looking for an internship? We offer internship programs in Python, Java, Artificial Intelligence, Machine Learning, Data Science, and Cyber Security. Both online and offline options are available, along with an internship certificate. Interested in knowing more? Press 1 to receive complete details on WhatsApp. Thank you for your time. Have a great day!"
    },
    "bca_internship_hi.wav": {
        "lang": "hi",
        "text": "नमस्ते! यह प्राइड ऑनलाइन एजुकेशन, बेलगावी से है। क्या आप बीसीए छात्र हैं और इंटर्नशिप की तलाश में हैं? हम पायथन, जावा, आर्टिफिशियल इंटेलिजेंस, मशीन लर्निंग, डेटा साइंस, और साइबर सिक्योरिटी में इंटर्नशिप प्रोग्राम प्रदान करते हैं। ऑनलाइन और ऑफलाइन दोनों विकल्प उपलब्ध हैं, साथ में इंटर्नशिप सर्टिफिकेट भी दिया जाएगा। अधिक जानने के इच्छुक हैं? व्हाट्सएप पर पूरा विवरण प्राप्त करने के लिए 1 दबाएं। आपके समय के लिए धन्यवाद। आपका दिन शुभ हो!"
    },
    "bca_internship_kn.wav": {
        "lang": "kn",
        "text": "ನಮಸ್ಕಾರ! ಇದು ಪ್ರೈಡ್ ಆನ್‌ಲೈನ್ ಎಜುಕೇಶನ್, ಬೆಳಗಾವಿ. ನೀವು ಇಂಟರ್ನ್‌ಶಿಪ್ ಹುಡುಕುತ್ತಿರುವ ಬಿಸಿಎ ವಿದ್ಯಾರ್ಥಿಯಾಗಿದ್ದೀರಾ? ನಾವು ಪೈಥಾನ್, ಜಾವಾ, ಆರ್ಟಿಫಿಶಿಯಲ್ ಇಂಟೆಲಿಜೆನ್ಸ್, ಮೆಷಿನ್ ಲರ್ನಿಂಗ್, ಡೇಟಾ ಸೈನ್ಸ್, ಮತ್ತು ಸೈಬರ್ ಸೆಕ್ಯುರಿಟಿಗಳಲ್ಲಿ ಇಂಟರ್ನ್‌ಶಿಪ್ ಪ್ರೋಗ್ರಾಂಗಳನ್ನು ಒದಗಿಸುತ್ತೇವೆ. ಆನ್‌ಲೈನ್ ಮತ್ತು ಆಫ್‌ಲೈನ್ ಎರಡೂ ಆಯ್ಕೆಗಳು ಲಭ್ಯವಿದ್ದು, ಇಂಟರ್ನ್‌ಶಿಪ್ ಪ್ರಮಾಣಪತ್ರವೂ ಸಿಗಲಿದೆ. ಹೆಚ್ಚಿನ ಮಾಹಿತಿ ತಿಳಿಯಲು ಆಸಕ್ತಿ ಇದೆಯೇ? ವಾಟ್ಸಾಪ್‌ನಲ್ಲಿ ಸಂಪೂರ್ಣ ವಿವರಗಳನ್ನು ಪಡೆಯಲು 1 ಒತ್ತಿ. ನಿಮ್ಮ ಅಮೂಲ್ಯ ಸಮಯಕ್ಕೆ ಧನ್ಯವಾದಗಳು. ಶುಭ ದಿನ!"
    },

    # 02 | Online & Distance Education
    "distance_education_en.wav": {
        "lang": "en",
        "text": "Hello! This is from PRIDE Online Education, Belagavi. Are you planning to continue your education or complete your degree? We offer SSLC and PUC through NIOS, with undergraduate programs like B A, B Com, B B A, B C A, and B S C, as well as postgraduate programs like M A, M Com, M B A, and M C A. You can learn at your own pace with flexible study options, affordable fees, and complete admission guidance. Would you like to know more about the courses? Press 1 to receive details on WhatsApp. Thank you, and have a wonderful day."
    },
    "distance_education_hi.wav": {
        "lang": "hi",
        "text": "नमस्ते! यह प्राइड ऑनलाइन एजुकेशन, बेलगावी से है। क्या आप अपनी शिक्षा जारी रखने, या अपनी डिग्री पूरी करने की योजना बना रहे हैं? हम एन. आई. ओ. एस. के माध्यम से एस. एस. एल. सी. और पी. यू. सी., तथा बी. ए., बी. कॉम, बी. बी. ए., बी. सी. ए., बी. एस. सी., एम. ए., एम. कॉम, एम. बी. ए., और एम. सी. ए. जैसे स्नातक और स्नातकोत्तर पाठ्यक्रम प्रदान करते हैं। आप लचीले अध्ययन विकल्पों, किफायती फीस, और पूर्ण प्रवेश मार्गदर्शन के साथ अपनी गति से सीख सकते हैं। क्या आप कोर्सेस के बारे में अधिक जानना चाहते हैं? व्हाट्सएप पर विवरण प्राप्त करने के लिए 1 दबाएं। धन्यवाद, आपका दिन शुभ हो।"
    },
    "distance_education_kn.wav": {
        "lang": "kn",
        "text": "ನಮಸ್ಕಾರ! ಇದು ಪ್ರೈಡ್ ಆನ್‌ಲೈನ್ ಎಜುಕೇಶನ್, ಬೆಳಗಾವಿ. ನೀವು ನಿಮ್ಮ ಶಿಕ್ಷಣವನ್ನು ಮುಂದುವರಿಸಲು, ಅಥವಾ ನಿಮ್ಮ ಪದವಿಯನ್ನು ಪೂರ್ಣಗೊಳಿಸಲು ಯೋಜಿಸುತ್ತಿದ್ದೀರಾ? ನಾವು ಎನ್ ಐ ಓ ಎಸ್ ಮೂಲಕ ಎಸ್ಸೆಸ್ಸೆಲ್ಸಿ ಮತ್ತು ಪಿಯುಸಿ, ಹಾಗೂ ಬಿ ಎ, ಬಿ ಕಾಮ್, ಬಿ ಬಿ ಎ, ಬಿ ಸಿ ಎ, ಮತ್ತು ಬಿ ಎಸ್ಸಿ; ಹಾಗೆಯೇ ಸ್ನಾತಕೋತ್ತರ ಕೋರ್ಸ್‌ಗಳಾದ ಎಂ ಎ, ಎಂ ಕಾಮ್, ಎಂ ಬಿ ಎ, ಮತ್ತು ಎಂ ಸಿ ಎ ಪದವಿಗಳನ್ನು ಒದಗಿಸುತ್ತೇವೆ. ಕೈಗೆಟುಕುವ ಶುಲ್ಕ ಮತ್ತು ಸಂಪೂರ್ಣ ಪ್ರವೇಶ ಮಾರ್ಗದರ್ಶನದೊಂದಿಗೆ ನೀವು ನಿಮ್ಮದೇ ಆದ ಸಮಯದಲ್ಲಿ ಕಲಿಯಬಹುದು. ಕೋರ್ಸ್‌ಗಳ ಬಗ್ಗೆ ಹೆಚ್ಚಿನ ಮಾಹಿತಿ ತಿಳಿಯಲು ಬಯಸುವಿರಾ? ವಾಟ್ಸಾಪ್‌ನಲ್ಲಿ ವಿವರಗಳನ್ನು ಪಡೆಯಲು 1 ಒತ್ತಿ. ಧನ್ಯವಾದಗಳು, ಶುಭ ದಿನ."
    },

    # 03 | DEEP Courses (Digital Employability Enhancement Program)
    "deep_courses_en.wav": {
        "lang": "en",
        "text": "Hello! This is from PRIDE Online Education, Belagavi. Are you interested to learn advanced computer and professional skills? We offer over 250 plus online courses through DEEP, including Programming, Hardware and Networking, Graphic Designing, and career-oriented training. Learn from home, at your own pace, with affordable fees. Flat 50% off on all courses. Interested in exploring the courses? Press 1 to receive the course list and details on WhatsApp. Thank you for your time. Have a great day!"
    },
    "deep_courses_hi.wav": {
        "lang": "hi",
        "text": "नमस्ते! यह प्राइड ऑनलाइन एजुकेशन, बेलगावी से है। क्या आप एडवांस कंप्यूटर और प्रोफेशनल स्किल्स सीखने में रुचि रखते हैं? हम डीप प्रोग्राम के माध्यम से 250 से अधिक ऑनलाइन कोर्सेस प्रदान करते हैं, जिनमें प्रोग्रामिंग, हार्डवेयर और नेटवर्किंग, ग्राफिक डिजाइनिंग, और करियर-ओरिएंटेड ट्रेनिंग शामिल हैं। घर से, अपनी गति से, किफायती फीस में सीखें। सभी कोर्सेस पर फ्लैट 50% छूट उपलब्ध है। कोर्सेस जानने के इच्छुक हैं? व्हाट्सएप पर कोर्स लिस्ट और विवरण प्राप्त करने के लिए 1 दबाएं। आपके समय के लिए धन्यवाद। आपका दिन शुभ हो!"
    },
    "deep_courses_kn.wav": {
        "lang": "kn",
        "text": "ನಮಸ್ಕಾರ! ಇದು ಪ್ರೈಡ್ ಆನ್‌ಲೈನ್ ಎಜುಕೇಶನ್, ಬೆಳಗಾವಿ. ನೀವು ಸುಧಾರಿತ ಕಂಪ್ಯೂಟರ್ ಮತ್ತು ವೃತ್ತಿಪರ ಕೌಶಲ್ಯಗಳನ್ನು ಕಲಿಯಲು ಆಸಕ್ತಿ ಹೊಂದಿದ್ದೀರಾ? ನಾವು ಡೀಪ್ ಪ್ರೋಗ್ರಾಂ ಮೂಲಕ ಪ್ರೋಗ್ರಾಮಿಂಗ್, ಹಾರ್ಡ್‌ವೇರ್ ಮತ್ತು ನೆಟ್‌ವರ್ಕಿಂಗ್, ಗ್ರಾಫಿಕ್ ಡಿಸೈನಿಂಗ್, ಮತ್ತು ವೃತ್ತಿ ಆಧಾರಿತ ತರಬೇತಿ ಸೇರಿದಂತೆ 250 ಕ್ಕೂ ಹೆಚ್ಚು ಆನ್‌ಲೈನ್ ಕೋರ್ಸ್‌ಗಳನ್ನು ಒದಗಿಸುತ್ತೇವೆ. ಮನೆಯಿಂದಲೇ, ನಿಮ್ಮದೇ ಸಮಯದಲ್ಲಿ, ಕೈಗೆಟುಕುವ ಶುಲ್ಕದಲ್ಲಿ ಕಲಿಯಿರಿ. ಎಲ್ಲಾ ಕೋರ್ಸ್‌ಗಳ ಮೇಲೆ ಫ್ಲಾಟ್ 50% ರಿಯಾಯಿತಿ ಇದೆ. ಕೋರ್ಸ್‌ಗಳನ್ನು ತಿಳಿದುಕೊಳ್ಳಲು ಆಸಕ್ತಿ ಇದೆಯೇ? ವಾಟ್ಸಾಪ್‌ನಲ್ಲಿ ಕೋರ್ಸ್ ಪಟ್ಟಿ ಮತ್ತು ವಿವರಗಳನ್ನು ಪಡೆಯಲು 1 ಒತ್ತಿ. ನಿಮ್ಮ ಅಮೂಲ್ಯ ಸಮಯಕ್ಕೆ ಧನ್ಯವಾದಗಳು. ಶುಭ ದಿನ!"
    },

    # Acknowledgment Audio (When Press 1 is captured)
    "ack_en.wav": {
        "lang": "en",
        "text": "Thank you for showing interest! We have noted your request. Complete details are being sent to your WhatsApp number right away. Have a wonderful day!"
    },
    "ack_hi.wav": {
        "lang": "hi",
        "text": "रुचि दिखाने के लिए धन्यवाद! आपका अनुरोध दर्ज कर लिया गया है। पूरी जानकारी तुरंत आपके व्हाट्सएप नंबर पर भेजी जा रही है। आपका दिन शुभ हो!"
    },
    "ack_kn.wav": {
        "lang": "kn",
        "text": "ಆಸಕ್ತಿ ತೋರಿಸಿದ್ದಕ್ಕಾಗಿ ಧನ್ಯವಾದಗಳು! ನಿಮ್ಮ ಕೋರಿಕೆಯನ್ನು ದಾಖಲಿಸಿಕೊಳ್ಳಲಾಗಿದೆ. ಸಂಪೂರ್ಣ ವಿವರಗಳನ್ನು ತಕ್ಷಣವೇ ನಿಮ್ಮ ವಾಟ್ಸಾಪ್ ಸಂಖ್ಯೆಗೆ ಕಳುಹಿಸಲಾಗುತ್ತಿದೆ. ಶುಭ ದಿನ!"
    },

    # Timeout / Goodbye
    "timeout_en.wav": {
        "lang": "en",
        "text": "Thank you for your time. For more information, please visit PRIDE Online Education, Belagavi. Have a great day!"
    },
    "timeout_hi.wav": {
        "lang": "hi",
        "text": "आपके समय के लिए धन्यवाद। अधिक जानकारी के लिए प्राइड ऑनलाइन एजुकेशन, बेलगावी से संपर्क करें। आपका दिन शुभ हो!"
    },
    "timeout_kn.wav": {
        "lang": "kn",
        "text": "ನಿಮ್ಮ ಸಮಯಕ್ಕೆ ಧನ್ಯವಾದಗಳು. ಹೆಚ್ಚಿನ ಮಾಹಿತಿಗಾಗಿ ಪ್ರೈಡ್ ಆನ್‌ಲೈನ್ ಎಜುಕೇಶನ್, ಬೆಳಗಾವಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ. ಶುಭ ದಿನ!"
    }
}


def generate_audio(filename: str, lang: str, text: str):
    output_path = AUDIO_DIR / filename
    
    # User requirement: English and Hindi set to 0.90, Kannada increased to 0.75
    speed_to_use = 0.75 if lang == "kn" else 0.90
    print(f"[*] Generating {filename} [{lang.upper()}] with Cartesia Aarav (speed={speed_to_use})...")

    headers = {
        "Cartesia-Version": "2024-06-10",
        "X-API-Key": CARTESIA_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "model_id": MODEL_ID,
        "transcript": text,
        "voice": {
            "mode": "id",
            "id": VOICE_ID
        },
        "generation_config": {
            "speed": speed_to_use
        },
        "output_format": {
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": SAMPLE_RATE
        },
        "language": lang
    }

    resp = requests.post("https://api.cartesia.ai/tts/bytes", json=payload, headers=headers, stream=True, timeout=60)
    if resp.status_code != 200:
        print(f"[!] Error generating {filename}: {resp.status_code} - {resp.text}")
        return False

    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=4096):
            if chunk:
                f.write(chunk)

    # Fix Cartesia streaming WAV header chunk size so duration is precise
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

    file_size_kb = output_path.stat().st_size / 1024
    print(f"[✓] Saved {filename} ({file_size_kb:.1f} KB)")
    return True


def main():
    print("=" * 70)
    print(" GENERATING PRIDE ONLINE EDUCATION AUDIO PROMPTS")
    print(f" Voice: Aarav ({VOICE_ID}) | Model: {MODEL_ID}")
    print(" Speed: English & Hindi = 0.90 | Kannada = 0.75")
    print("=" * 70)

    success_count = 0
    for filename, item in SCRIPTS.items():
        ok = generate_audio(filename, item["lang"], item["text"])
        if ok:
            success_count += 1

    print("\n" + "=" * 70)
    print(f"[COMPLETED] {success_count}/{len(SCRIPTS)} audio files regenerated with EN/HI=0.90 and KN=0.75 in ./audio/")
    print("=" * 70)


if __name__ == "__main__":
    main()

