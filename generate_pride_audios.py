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
        "text": "Hello! This Call is from PRIDE Online Education, Belagavi. Are you a BCA student looking for an internship? In Pride Online Education Belagavi we offer internship programs in Python, Java, Artificial Intelligence, Machine Learning, Data Science, and Cyber Security. Both online and offline options are available, along with an internship certificate. Are you Interested in knowing more? Press 1 to receive complete details on WhatsApp. Thank you for your time. Have a great day!"
    },
    "bca_internship_hi.wav": {
        "lang": "hi",
        "text": "हेलो! यह कॉल PRIDE Online Education, Belagavi से है। क्या आप एक BCA student हैं और internship ढूंढ रहे हैं? Pride Online Education Belagavi में हम Python, Java, Artificial Intelligence, Machine Learning, Data Science, और Cyber Security में internship programs offer करते हैं। Online और offline दोनों options available हैं, साथ में internship certificate भी मिलेगा। क्या आप और जानना चाहते हैं? WhatsApp पर complete details पाने के लिए 1 दबाएं। Thank you आपके time के लिए. Have a great day!"
    },
    "bca_internship_kn.wav": {
        "lang": "kn",
        "text": "ಹಲೋ! ಈ call PRIDE Online Education, Belagavi ಇಂದ. ನೀವು internship ಹುಡುಕುತ್ತಿರುವ BCA student ಆಗಿದ್ದೀರಾ? Pride Online Education Belagavi ನಲ್ಲಿ ನಾವು Python, Java, Artificial Intelligence, Machine Learning, Data Science, ಮತ್ತು Cyber Security ನಲ್ಲಿ internship programs offer ಮಾಡ್ತಿದ್ದೇವೆ. Online ಮತ್ತು offline ಎರಡೂ options available ಇವೆ, ಜೊತೆಗೆ internship certificate ಕೂಡ ಸಿಗುತ್ತೆ. ಹೆಚ್ಚು ತಿಳಿಯಲು interested ಇದ್ದೀರಾ? WhatsApp ನಲ್ಲಿ complete details ಪಡೆಯಲು 1 ಒತ್ತಿ. Thank you ನಿಮ್ಮ ಸಮಯಕ್ಕೆ. Have a great day!"
    },

    # 02 | Online & Distance Education
    "distance_education_en.wav": {
        "lang": "en",
        "text": "Hello! This Call is from PRIDE Online Education, Belagavi. Are you planning to continue your education or complete your degree? In PRIDE Online Education, Belagavi We offer SSLC and PUC through NIOS, with undergraduate programs like B.A, B.S.C, B.B.A, B.Com,and B.C.A , as well as postgraduate programs like M.A, M.Com, M.B.A, and M.C.A. You can learn at your own pace with flexible study options, affordable fees, and complete admission guidance. Would you like to know more about the courses? Press 1 to receive details on WhatsApp. Thank you, and have a wonderful day."
    },
    "distance_education_hi.wav": {
        "lang": "hi",
        "text": "हेलो! यह कॉल प्राइड ऑनलाइन एजुकेशन, बेलगावी से है। क्या आप अपनी education continue करने या degree complete करने की सोच रहे हैं? प्राइड ऑनलाइन एजुकेशन, बेलगावी में हम NIOS के through SSLC और PUC, undergraduate programs जैसे B.A, B.S.C, B.B.A, B.Com, B.C.A, और postgraduate programs जैसे M.A, M.Com, M.B.A, और M.C.A offer करते हैं। आप flexible study options, affordable fees, और complete admission guidance के साथ अपनी pace पर learn कर सकते हैं। क्या आप courses के बारे में और जानना चाहते हैं? WhatsApp पर details पाने के लिए 1 दबाएं। Thank you, and have a wonderful day!"
    },
    "distance_education_kn.wav": {
        "lang": "kn",
        "text": "ಹಲೋ! ಈ call PRIDE Online Education, Belagavi ಇಂದ. ನೀವು ನಿಮ್ಮ education continue ಮಾಡಲು ಅಥವಾ degree complete ಮಾಡಲು plan ಮಾಡ್ತಿದ್ದೀರಾ? PRIDE Online Education, Belagavi ನಲ್ಲಿ ನಾವು NIOS ಮೂಲಕ SSLC ಮತ್ತು PUC, undergraduate programs ಆದ B A, B Com, B B A, B C A, B S C, ಹಾಗೆಯೇ postgraduate programs ಆದ M A, M Com, M B A, ಮತ್ತು M C A offer ಮಾಡ್ತಿದ್ದೇವೆ. Flexible study options, affordable fees, ಮತ್ತು complete admission guidance ನೊಂದಿಗೆ ನೀವು ನಿಮ್ಮದೇ speed ನಲ್ಲಿ ಕಲಿಯಬಹುದು. Courses ಬಗ್ಗೆ ಹೆಚ್ಚು ತಿಳಿಯಲು interested ಇದ್ದೀರಾ? WhatsApp ನಲ್ಲಿ details ಪಡೆಯಲು 1 ಒತ್ತಿ. Thank you, and have a wonderful day!"
    },

    # 03 | DEEP Courses (Digital Employability Enhancement Program)
    "deep_courses_en.wav": {
        "lang": "en",
        "text": "Hello! This Call is from PRIDE Online Education, Belagavi. Are you interested to learn advanced computer and professional skills? In PRIDE Online Education, Belagavi We offer over 250 plus online courses through DEEP, including Programming, Hardware and Networking, Graphic Designing, and career-oriented training. Learn from home, at your own pace, with affordable fees. Flat 50% off on all courses. Interested in exploring the courses? Press 1 to receive the course list and details on WhatsApp. Thank you for your time. Have a great day!"
    },
    "deep_courses_hi.wav": {
        "lang": "hi",
        "text": "हेलो! यह कॉल PRIDE Online Education, Belagavi से है। क्या आप advanced computer और professional skills सीखना चाहते हैं? PRIDE Online Education, Belagavi में हम DEEP के through 250 plus online courses offer करते हैं, जिसमें Programming, Hardware and Networking, Graphic Designing, और career-oriented training शामिल हैं। घर बैठे, अपनी pace पर, affordable fees में सीखें। सभी courses पर flat 50% off है। क्या आप courses explore करना चाहते हैं? WhatsApp पर course list और details पाने के लिए 1 दबाएं। Thank you आपके time के लिए. Have a great day!"
    },
    "deep_courses_kn.wav": {
        "lang": "kn",
        "text": "ಹಲೋ! ಈ call PRIDE Online Education, Belagavi ಇಂದ. ನೀವು advanced computer ಮತ್ತು professional skills ಕಲಿಯಲು interested ಇದ್ದೀರಾ? PRIDE Online Education, Belagavi ನಲ್ಲಿ ನಾವು DEEP ಮೂಲಕ Programming, Hardware and Networking, Graphic Designing, ಮತ್ತು career-oriented training ಸೇರಿದಂತೆ 250 plus online courses offer ಮಾಡ್ತಿದ್ದೇವೆ. ಮನೆಯಿಂದಲೇ, ನಿಮ್ಮದೇ speed ನಲ್ಲಿ, affordable fees ನಲ್ಲಿ ಕಲಿಯಿರಿ. ಎಲ್ಲಾ courses ಮೇಲೆ flat 50% discount ಇದೆ. Courses explore ಮಾಡಲು interested ಇದ್ದೀರಾ? WhatsApp ನಲ್ಲಿ course list ಮತ್ತು details ಪಡೆಯಲು 1 ಒತ್ತಿ. Thank you ನಿಮ್ಮ ಸಮಯಕ್ಕೆ. Have a great day!"
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

