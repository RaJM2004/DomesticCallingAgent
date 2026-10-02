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
    pace: float = 1.0
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
def generate_cartesia_tts(
    text: str,
    output_filename: str,
    api_key: str = None,
    voice_id: str = None,
    model_id: str = "sonic-3",
    sample_rate: int = 48000
) -> Path:
    """
    Generate speech using Cartesia Sonic TTS.
    """
    api_key = api_key or os.getenv("CARTESIA_API_KEY")
    if not api_key:
        raise ValueError("CARTESIA_API_KEY is not set. Please set it in .env or pass it as an argument.")

    voice_id = voice_id or os.getenv("CARTESIA_VOICE_ID", "39d518b7-fd0b-4676-9b8b-29d64ff31e12")

    url = "https://api.cartesia.ai/tts/bytes"
    payload = {
        "model_id": model_id,
        "transcript": text,
        "voice": {
            "mode": "id",
            "id": voice_id
        },
        "output_format": {
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": sample_rate
        }
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
# 3. Pride Online Education - Kannada IVR Presets
# =====================================================================
PRESET_TEMPLATES = {
    "1": {
        "name": "Pride Online Education - Welcome IVR (welcome.wav)",
        "file": "welcome.wav",
        "default_text": "ನಮಸ್ಕಾರ, ಪ್ರೈಡ್ ಆನ್ಲೈನ್ ಎಜುಕೇಶನ್ ಬೆಳಗಾವಿಗೆ ತಮಗೆ ಆತ್ಮೀಯ ಸ್ವಾಗತ. ಯುಜಿಸಿ ಮಾನ್ಯತೆ ಪಡೆದ BA, B.Com, BCA, BBA ಪದವಿಗಳಿಗಾಗಿ 1 ಒತ್ತಿ. ಉದ್ಯೋಗಾಧಾರಿತ Python, Full Stack, Data Science ಐಟಿ ಕೋರ್ಸ್ಗಳಿಗಾಗಿ 2 ಒತ್ತಿ."
    },
    "2": {
        "name": "Option 1 - Online UG & PG Degrees (audio_1.wav)",
        "file": "audio_1.wav",
        "default_text": "ಧನ್ಯವಾದಗಳು. ನಮ್ಮಲ್ಲಿ ಯುಜಿಸಿ ಮಾನ್ಯತೆ ಪಡೆದ BA, B.Com, BCA, BBA, ಹಾಗೂ MBA, MCA ಪದವಿಗಳು ಲಭ್ಯವಿವೆ. ಕೆಲಸ ಮಾಡುತ್ತಿರುವ ಉದ್ಯೋಗಿಗಳಿಗೆ ಆನ್ಲೈನ್ ತರಗತಿಗಳ ಸೌಲಭ್ಯವಿದೆ. ಹೆಚ್ಚಿನ ಮಾಹಿತಿ ಹಾಗೂ ದಾಖಲಾತಿಗಾಗಿ ಬೆಳಗಾವಿ ಕಿರ್ಲೋಸ್ಕರ್ ರಸ್ತೆಯ ಮುಜಾವರ್ ಬಿಲ್ಡಿಂಗ್ನಲ್ಲಿರುವ ನಮ್ಮ ಕಚೇರಿಗೆ ಭೇಟಿ ನೀಡಿ ಅಥವಾ 7760345397 ಸಂಖ್ಯೆಗೆ ಸಂಪರ್ಕಿಸಿ."
    },
    "3": {
        "name": "Option 2 - Job-Oriented IT Courses (audio_2.wav)",
        "file": "audio_2.wav",
        "default_text": "ಧನ್ಯವಾದಗಳು. ನಮ್ಮಲ್ಲಿ ಉದ್ಯೋಗಾಧಾರಿತ Python, Full Stack Development, Data Science, ಹಾಗೂ MKCL ಅಧಿಕೃತ ಕಂಪ್ಯೂಟರ್ ಕೋರ್ಸ್ಗಳು ಲಭ್ಯವಿವೆ. ನುರಿತ ತಜ್ಞರಿಂದ ಪ್ರಾಕ್ಟಿಕಲ್ ತರಬೇತಿ ನೀಡಲಾಗುತ್ತದೆ. ಉಚಿತ ಡೆಮೊ ತರಗತಿ ಹಾಗೂ ದಾಖಲಾತಿಗಾಗಿ ಬೆಳಗಾವಿಯ ನಮ್ಮ ಕಚೇರಿಗೆ ಭೇಟಿ ನೀಡಿ. ಧನ್ಯವಾದಗಳು."
    },
    "4": {
        "name": "Timeout / No Response (timeout.wav)",
        "file": "timeout.wav",
        "default_text": "ಕ್ಷಮಿಸಿ, ನಮಗೆ ಯಾವುದೇ ಪ್ರತಿಕ್ರಿಯೆ ಬಂದಿಲ್ಲ. ವೈಯಕ್ತಿಕ ಶೈಕ್ಷಣಿಕ ಸಮಾಲೋಚನೆಗಾಗಿ ಬೆಳಗಾವಿಯ ನಮ್ಮ ಕಚೇರಿಗೆ 7760345397 ಸಂಖ್ಯೆಗೆ ಕರೆ ಮಾಡಿ. ಧನ್ಯವಾದಗಳು."
    }
}


def batch_generate_pride_education(provider: str = "sarvam"):
    """
    Batch generates all 4 Kannada IVR files for Pride Online Education, Belagavi.
    """
    print("\n" + "=" * 65)
    print("  GENERATING PRIDE ONLINE EDUCATION KANNADA IVR AUDIO FILES  ")
    print("=" * 65)
    for key, item in PRESET_TEMPLATES.items():
        print(f"\n--- Generating {item['file']} ({item['name']}) ---")
        if provider == "sarvam":
            generate_sarvam_tts(
                text=item["default_text"],
                output_filename=item["file"],
                language_code="kn-IN",
                speaker="tarun",
                model="bulbul:v3"
            )
        elif provider == "cartesia":
            generate_cartesia_tts(
                text=item["default_text"],
                output_filename=item["file"],
                voice_id="39d518b7-fd0b-4676-9b8b-29d64ff31e12",
                model_id="sonic-3"
            )
    print("\n[SUCCESS] All 4 Kannada IVR audio files generated in ./audio/")


def main():
    print("=" * 65)
    print("   PRIDE ONLINE EDUCATION, BELAGAVI - VOICE PROMPT GENERATOR   ")
    print("=" * 65)
    print(f"Target folder: {AUDIO_DIR.resolve()}\n")

    print("Select an option:")
    for key, item in PRESET_TEMPLATES.items():
        print(f"  [{key}] {item['name']}")
    print("  [5] Custom Audio File (Enter custom filename & text)")
    print("  [6] Batch Generate All 4 Kannada IVR Prompts (Recommended)")

    choice = input("\nEnter choice (1-6) [default 6]: ").strip() or "6"

    if choice == "6":
        p = input("Select provider ([1] Sarvam AI kn-IN [default], [2] Cartesia sonic-3): ").strip()
        prov = "cartesia" if p == "2" else "sarvam"
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

    p = input("Select provider ([1] Sarvam AI kn-IN [default], [2] Cartesia sonic-3): ").strip()
    prov = "cartesia" if p == "2" else "sarvam"

    if prov == "sarvam":
        generate_sarvam_tts(text_to_speak, filename, language_code="kn-IN", speaker="tarun")
    else:
        generate_cartesia_tts(text_to_speak, filename, voice_id="39d518b7-fd0b-4676-9b8b-29d64ff31e12", model_id="sonic-3")


if __name__ == "__main__":
    main()
