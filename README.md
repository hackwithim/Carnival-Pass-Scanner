# 🎭 Grand Freshers' Carnival 2K26 — Barcode Pass Generator & Access Control Scanner

An event access management suite and barcode verification system built for **Grand Freshers' Carnival 2K26** (Dr. D. Y. Patil Varale Campus).

---

## 🌟 Key Features

### 1. 🎟️ Automated Pass & Barcode Generation
- **College-wise Pass Generation**:
  - **DYPIMED** (150 students): High-resolution festival passes with Code-128 barcodes based on Student ID.
  - **DYPCOEI** (289 students): Verified FE engineering passes with Code-128 barcodes based on Student ID.
  - **DYPTC** (294 students): Engineering passes with Code-128 barcodes based on combined Division + Roll Number (e.g., `A11101`).
- **Multiple Output Formats**:
  - Individual Strip Passes (1 pass per page, 10" × 3" strip).
  - Bulk Printable Sheets on **A4 Portrait** (3 passes per sheet with light cut lines).

### 2. ⚡ Real-Time Scanner Web Application
- **Zero-Latency Barcode Scanner**:
  - **Live Camera Barcode Scanner**: Works in-browser on mobile phone cameras and laptops.
  - **Hardware USB Barcode Gun Support**: Automatically auto-focuses the input field for high-speed continuous check-in.
- **Audio & Visual Feedback**:
  - Synthesized audio tones (chime for admission, harsh buzzer for denial).
  - **Access Granted**: Animated green card showing student details and check-in timestamp.
  - **Second Entry Denied**: High-contrast red security alert displaying the original admission date, time, and volunteer.
- **NoSQL Document Database**:
  - Backed by **TinyDB** document store (`database.json`) storing all 733 students college-wise.
  - Strict atomic transactions preventing duplicate entry.

### 3. 🛡️ Administrator Panel & Live Analytics
- **Live Event Metrics**: Real-time counters of total registered (733), admitted, and pending attendees.
- **College Breakdown**: Live monitoring cards for DYPIMED, DYPCOEI, and DYPTC.
- **Student Verification Directory**: Instant search across all 733 records with filters and manual check-in override.
- **Reset Entries**: Reset attendance records back to `PENDING` (with admin confirmation).
- **One-Click CSV Export**: Download the live attendance log with timestamps and volunteer attribution.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Dependencies:
  ```bash
  pip install flask tinydb openpyxl python-barcode pillow pymupdf
  ```

### Running the Web Application
```bash
python app.py
```
Open your browser at:
- **Local:** [http://127.0.0.1:5000](http://127.0.0.1:5000)
- **Local Network (Wi-Fi):** `http://<your-ip>:5000` *(allows volunteers to scan using mobile phones)*

### Default Login Credentials
| Role | Username / Identifier | Passcode |
|:---|:---|:---|
| **Administrator** | `admin` | `admin123` |
| **Volunteer** | *Any Name / Gate ID* | `pass` |

---

## 🛠️ Regenerating PDF Passes

To generate or refresh the PDF passes from CSV datasets:
```bash
# DYPIMED (150 passes)
python generate_dypimed_passes.py

# DYPCOEI (289 passes)
python generate_dypcoei_passes.py

# DYPTC (294 passes)
python generate_dyptc_passes.py
```

---

## 📁 Repository Structure
```
├── app.py                      # Flask Backend & REST API
├── db_loader.py                # NoSQL Database loader & synchronizer
├── database.json               # TinyDB Document Database
├── data.csv                    # DYPIMED & DYPCOEI student dataset
├── DYPTC.csv                   # DYPTC student dataset
├── generate_dypimed_passes.py  # DYPIMED PDF generator
├── generate_dypcoei_passes.py  # DYPCOEI PDF generator
├── generate_dyptc_passes.py    # DYPTC PDF generator
├── templates/
│   ├── index.html              # Responsive Web Application UI
│   ├── DYPIMED_Template.jpeg   # High-resolution pass template
│   ├── DYPCOEI_Template.jpeg
│   └── DYPTC_Template.jpeg
└── static/
    ├── css/style.css           # Glassmorphism dark aesthetic
    └── js/app.js               # Audio synthesis, camera scanner, API client
```

---

## 📄 License
MIT License. Created for Grand Freshers' Carnival 2K26.
