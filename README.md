# Vobiz DTMF Calling Agent & Audio Recorder

An intelligent telephony calling agent that generates voice prompts using **Sarvam AI** (Hindi/Indian languages) and **Cartesia** (low-latency English/global voices), hosts audio files, and handles **DTMF IVR conditions** (`if DTMF input == 1 -> audio_1.wav`, `elif DTMF input == 2 -> audio_2.wav`) via **Vobiz Telephony**.

---

## 📁 Project Structure

```text
├── audio/                   # Generated/Recorded audio files (WAV 8kHz telephony format)
│   ├── welcome.wav          # Initial prompt ("Press 1 for Sales, 2 for Support")
│   ├── audio_1.wav          # Played when caller presses 1
│   ├── audio_2.wav          # Played when caller presses 2
│   └── timeout.wav          # Fallback when invalid input or timeout occurs
├── record_audio.py          # Interactive script to generate/record audio (Sarvam / Cartesia / Mic)
├── calling_agent.py         # FastAPI webhook server for Vobiz DTMF & audio streaming
├── make_call.py             # Script to trigger outbound calls using Vobiz REST API
├── .env                     # API keys and configuration
├── requirements.txt         # Python dependencies
└── README.md
```

---

## 🚀 Quick Start Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Your `.env` is already pre-configured with:
- **Sarvam AI API Key**
- **Cartesia API Key**
- **Groq & OpenAI Keys**
- **LiveKit & Vobiz SIP Trunking credentials**

> **Note for Vobiz Webhooks:**
> When running locally, expose port 8000 using ngrok:
> ```bash
> ngrok http 8000
> ```
> Then set `SERVER_BASE_URL` in `.env` to your public ngrok URL (e.g. `https://your-domain.ngrok-free.app`).

---

### 3. Generate or Record Audio Files
You can generate audio anytime using:
```bash
python record_audio.py
```
Options available:
1. **Interactive Menu**: Choose default IVR templates or type custom scripts.
2. **Provider Choices**:
   - **Sarvam AI**: `bulbul:v3` for Hindi, Indian English, Marathi, Bengali, etc.
   - **Cartesia**: `sonic-3.6` ultra-realistic voices.
   - **OpenAI TTS**: `tts-1` Alloy/Nova.
   - **Microphone**: Direct live voice recording.

Or generate directly in Python:
```python
from record_audio import generate_sarvam_tts, generate_cartesia_tts

# Generate using Sarvam AI (Hindi)
generate_sarvam_tts(
    text="नमस्ते! सेल्स के लिए 1 दबाएं, सपोर्ट के लिए 2 दबाएं।",
    output_filename="welcome.wav"
)

# Generate using Cartesia (English)
generate_cartesia_tts(
    text="Press 1 for Sales, 2 for Support.",
    output_filename="welcome_en.wav"
)
```

---

### 4. Start the Calling Agent Webhook Server
Run the FastAPI server:
```bash
python calling_agent.py
```
This serves:
- `GET /audio/{filename}`: Directly streams audio files to Vobiz.
- `POST /call/incoming`: Responds with Vobiz XML `<Gather>` to collect DTMF.
- `POST /call/dtmf`: Handles DTMF inputs:
  - **Digit `1`**: Plays `/audio/audio_1.wav`
  - **Digit `2`**: Plays `/audio/audio_2.wav`
  - **Other / Timeout**: Plays `/audio/timeout.wav`

---

### 5. Trigger an Outbound Call
To initiate a phone call via Vobiz that connects to your IVR:
```bash
python make_call.py +91XXXXXXXXXX
```
