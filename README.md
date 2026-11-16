# Vobiz & LiveKit Automated Calling & Multilingual Response Hub

An automated telephony campaign engine and response notation platform built with **FastAPI**, **LiveKit SIP / Vobiz Telecom Trunking**, **Cartesia Sonic-3 TTS**, and **SQLite WAL Mode**.

---

## 🎨 Theme & Palette
- **Primary Accent**: `#db8b70` (Terracotta)
- **Glass / Surface Tint**: `#db8b701a` (10% opacity)
- **Warm Linen / Surface**: `#f7eae3`

---

## ✨ Features

1. **Multilingual Voice Routing (English, Hindi, Kannada)**:
   - Voice generated with **Cartesia Sonic-3** using **Aarav** (`39d518b7-fd0b-4676-9b8b-29d64ff31e12`).
   - Telephony-optimized pacing: `speed: 0.90` for English & Hindi, `speed: 0.70` for Kannada. Deliberate, clear, and easy to follow.
   - Covers 3 distinct programs across all 3 languages:
     - **01 | BCA Internship Program** (`bca_internship_en.wav`, `bca_internship_hi.wav`, `bca_internship_kn.wav`)
     - **02 | Online & Distance Education** (`distance_education_en.wav`, `distance_education_hi.wav`, `distance_education_kn.wav`)
     - **03 | DEEP Courses** (`deep_courses_en.wav`, `deep_courses_hi.wav`, `deep_courses_kn.wav`)

2. **Dashboard Program & Language Dropdowns**:
   - Easily select the **Course / Program** and **Language** from dropdown menus in the portal.
   - The dialer dynamically streams the corresponding audio file based on the campaign selection.

3. **Keypad Response Collection (`Press 1` on Keypad)**:
   - Real-time SIP DTMF digit detection on active calls.
   - When caller presses **1**:
     - Automatically logs: `"Pressed 1: WhatsApp Details Requested (<Course Name>)"`.
     - Plays multilingual confirmation audio: `"Thank you! We have noted your request. Complete details are being sent to your WhatsApp number right away. Have a wonderful day!"` (`ack_en.wav`, `ack_hi.wav`, `ack_kn.wav`).
     - Issues immediate SIP BYE to hang up cleanly.
   - 1-click dashboard filter: **`🟢 Pressed 1 (WhatsApp Leads)`**.

4. **Excel & CSV Sheet Upload (Up to 30,000+ Numbers)**:
   - Bulk upload `.xlsx`, `.xls`, or `.csv` files.
   - Automatically sanitizes numbers, formats with `+91`, and links to the selected program and language.

5. **Token Deduction & Carrier Billing**:
   - **1.0 Token** deducted for answered/connected calls.
   - **0.3 Token** deducted for unanswered, declined, or failed calls.
   - Real-time wholesale carrier cost tracking directly from Vobiz CDR.

6. **Annotated Excel Export (.xlsx)**:
   - Export full response sheets with phone numbers, customer names, program, language, DTMF key pressed, annotated notes, duration, and telecom cost.

---

## 📁 Audio Files (in `./audio/`)

| Script / Session | English | Hindi | Kannada |
| :--- | :--- | :--- | :--- |
| **01 \| BCA Internship** | `bca_internship_en.wav` | `bca_internship_hi.wav` | `bca_internship_kn.wav` |
| **02 \| Distance Education** | `distance_education_en.wav` | `distance_education_hi.wav` | `distance_education_kn.wav` |
| **03 \| DEEP Courses** | `deep_courses_en.wav` | `deep_courses_hi.wav` | `deep_courses_kn.wav` |
| **Acknowledgment (Press 1)** | `ack_en.wav` | `ack_hi.wav` | `ack_kn.wav` |
| **Timeout / Goodbye** | `timeout_en.wav` | `timeout_hi.wav` | `timeout_kn.wav` |

---

## 🚀 Running Locally

1. **Start the Web & Dialing Server**:
   ```bash
   python calling_agent.py
   ```
2. Open your browser at:
   ```text
   http://localhost:8000
   ```
3. Select your desired **Program** and **Language** from the dashboard dropdown, upload your Excel sheet, and click **"Start Auto-Dialing"**!

---

## 📁 Project Structure

```text
├── database.py              # SQLite database models (Account, Campaign, CallRecord)
├── dialer_engine.py         # Thread-safe sequential calling background worker
├── vobiz_service.py         # Vobiz REST API integration (carrier balance & outbound dialing)
├── calling_agent.py         # FastAPI main server & webhook router
├── templates/
│   └── index.html           # Modern dashboard with #db8b70 / #db8b701a / #f7eae3 palette
├── Procfile                 # Railway process launcher
├── railway.json             # Railway deployment configuration
├── requirements.txt         # Python dependencies
├── audio/                   # Telephony WAV prompts (welcome.wav, audio_1.wav, audio_2.wav)
└── sample_numbers_30k_template.xlsx  # Sample test spreadsheet
```

---

## 🚀 Running Locally

1. **Start the Web & Dialing Server**:
   ```bash
   python calling_agent.py
   ```
2. Open your browser at:
   ```text
   http://localhost:8000
   ```
3. Upload `sample_numbers_30k_template.xlsx` or your own sheet and click **"Start Auto-Dialing"**.

---

## 🚂 Deploying to Railway

1. Push this repository to **GitHub**.
2. Go to **[Railway.app](https://railway.app)** and click **"New Project" -> "Deploy from GitHub repo"**.
3. Railway automatically detects `railway.json`, `Procfile`, and `requirements.txt`.
4. In Railway dashboard **Settings -> Variables**, add your `.env` keys:
   - `VOBIZ_AUTH_ID`
   - `VOBIZ_AUTH_TOKEN`
   - `VOBIZ_OUTBOUND_NUMBER`
   - `SERVER_BASE_URL` (set to your generated Railway domain, e.g. `https://your-app.up.railway.app`)
5. Click **Deploy**. Your app will run 24/7 with zero cold start delays!
