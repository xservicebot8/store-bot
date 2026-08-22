# 🛍️ Advanced Telegram Digital Store Bot

An enterprise-grade Telegram Digital Store Bot built with **Aiogram 3**, **MongoDB Atlas (Motor Async)**, automated **Paytm UPI QR & Webhook Verification**, and **Anti-Fraud Single-Device Referral Points Rewards Shop**.

---

## ✨ Features

- 📁 **3-Tier Product Delivery Engine:**
  - **Batch File Stock (`file_stock`):** Upload 10–50+ individual `.txt` / document files; each buyer gets a unique file delivered automatically.
  - **Line-by-Line Stock (`line_stock`):** Single or bulk lines/keys with atomic claiming and double-spend prevention.
  - **Universal Digital Goods (`static_file` / `static_text`):** Universal download link or code sent to all buyers.
- ⚡ **Automated Paytm UPI Payments:**
  - Real-time dynamic UPI QR generation.
  - 15-second background auto-verifier loop with 12-digit UTR fallback matching.
  - Digital wallet balance top-ups & 1-click wallet payments.
- 🛡️ **Anti-Fraud Device Verification (1 Device / 1 IP = 1 Account):**
  - Telegram WebApp device fingerprinting preventing self-referrals and fake account farming.
  - Enforced verification before generating referral links.
- 💎 **Referral Points & Redeem Shop (`ref_shop`):**
  - +1 Point awarded per verified referral.
  - In-bot Redeem Shop allowing users to exchange points for exclusive items (e.g., 3 Points ➡️ Item X).
- 🎨 **Vibrant UI:**
  - Native Telegram colored inline buttons (`primary`, `success`, `danger`).
  - Custom Telegram Emoji Tags (`<tg-emoji>`) and icon mappings.
- 👑 **Comprehensive Admin Dashboard:**
  - Real-time sales analytics (Today, Yesterday, Month, Top Products).
  - Product creation wizard, instant price adjusting (±₹10, ±₹50), stock ingestion & export.
  - User balance control (Add/Deduct/Ban), Promo Codes / Coupons, Broadcast messaging, and 1-Click MongoDB JSON Backups.

---

## 🚀 Quick Setup

1. **Clone repository:**
   ```bash
   git clone <repository_url>
   cd "store bot - final"
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

4. **Run the Bot:**
   ```bash
   python main.py
   ```

---

## 🔒 Security

- Sensitive credentials (`.env`, cookies, tokens, database dumps) are strictly excluded via `.gitignore`.
- Concurrency locks protect atomic stock claiming and balance updates.
