<div align="center">
  <img src="https://img.icons8.com/fluency/96/bullish.png" alt="Trading Bot Logo" width="100"/>
  <h1>Telegram Trading Analysis Bot</h1>
  <p>
    A sophisticated, feature-rich Telegram bot for financial market analysis, built with Python and Aiogram.
  </p>
  <p>
    <strong>Developed and maintained by Mohmmaed K. AL-Sudani</strong>
  </p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python Version">
    <img src="https://img.shields.io/badge/Framework-Aiogram%203-green.svg" alt="Framework">
    <img src="https://img.shields.io/badge/License-Proprietary-red.svg" alt="License">
  </p>
</div>

---

## ✨ Features

This bot provides a comprehensive suite of tools for traders and market analysts:

-   **🤖 Smart Money Concepts (SMC) Analysis**: Get AI-powered technical analysis and trade recommendations (Entry, SL, TP) for any financial asset.
-   **🌐 In-Depth Economic Analysis**: A "Pro" feature providing institutional-grade macroeconomic analysis by correlating market news and economic data with asset performance.
-   **🗓️ Interactive Economic Calendar**: View upcoming high-impact economic events with timezone support to stay ahead of market-moving news.
-   **🔔 Advanced Price Alerts**: Set custom alerts not just for price targets, but for technical indicators like RSI, Moving Averages, and more.
-   **💎 Multi-Tier Subscriptions**: A flexible system with Free, Standard, and Pro tiers, offering progressively powerful features.
-   **👑 Full-Featured Admin Panel**: A comprehensive dashboard for managing users, broadcasting messages, viewing bot statistics, and scheduling automated tasks.
-   **👤 User Personalization**: Features like custom favorite assets and notification preferences to tailor the bot experience.
-   **🚀 Interactive Onboarding**: A guided tour for new users that immediately showcases the bot's value.

## 🚀 Getting Started

Follow these instructions to get a local copy up and running.

### Prerequisites

-   Python 3.11+
-   A Telegram Bot Token obtained from [@BotFather](https://t.me/BotFather)
-   API keys for required services (NewsAPI, Google Cloud)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd trading-bot # Or your project directory name
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # For Windows
    python -m venv venv
    venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Configuration

All bot configurations are managed through an environment file.

> [!IMPORTANT]
> **Security Warning**
> Your `.env` file and your `key.json` service account file contain highly sensitive information, including your bot token and cloud credentials.
> -   **NEVER** commit these files to a public repository (e.g., on GitHub). The included `.gitignore` file is configured to prevent this, but you must never remove that configuration.
> -   Keep these files secure and do not share them publicly.

1.  **Create the environment file:**
    Copy the example file to create your own local configuration.
    ```bash
    cp .env.example .env
    ```

2.  **Edit the `.env` file:**
    Open the `.env` file and fill in the values for each variable.

    ```dotenv
    # Telegram Bot Token from BotFather
    BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"

    # List of admin user IDs, comma-separated
    ADMIN_IDS="123456789,987654321"

    # Database file name
    DB_FILE="bot_data.db"

    # Google Cloud Project Details for Gemini API
    PROJECT_ID="YOUR_GOOGLE_CLOUD_PROJECT_ID"
    ENDPOINT_ID="YOUR_VERTEX_AI_ENDPOINT_ID"
    SERVICE_ACCOUNT_FILE="key.json" # Ensure this file is in the root directory

    # Your Telegram username (for contact buttons)
    YOUR_USERNAME="your_telegram_username"

    # NewsAPI.org API Key
    NEWS_API_KEY="YOUR_NEWSAPI_KEY"

    # Real-time price API URL
    PRICE_API_URL="https://abalahb.cfd/forex"
    ```

## ▶️ Usage

Once the configuration is complete, you can start the bot by running the `main.py` script:

```bash
python main.py
```

The bot will initialize, connect to Telegram, and be ready to receive commands.

## 🔌 Data Providers & Collaboration

This bot is designed to be a powerful analytical tool, and the quality of its analysis depends heavily on the quality of the incoming data.

If you are a **real-time data provider** and are interested in integrating your services with this bot, or if you wish to discuss other collaboration opportunities, please feel free to reach out.

**Contact:** Mohmmaed K. AL-Sudani - mohmmaed211@gmail.com

## 📂 Project Structure

The project is organized into a modular `app` structure for maintainability and scalability.

```
.
├── app/
│   ├── api_client.py         # Manages external API calls (Gemini, Prices)
│   ├── db.py                 # SQLAlchemy models and database logic
│   ├── economic_analyzer.py  # Core economic analysis module
│   ├── handlers/             # Command and callback handlers
│   │   ├── admin.py
│   │   └── user.py
│   ├── keyboards.py          # All Telegram keyboard layouts
│   ├── scheduler.py          # APScheduler jobs and logic
│   └── states.py             # FSM states for conversational flows
├── .env.example              # Example environment file
├── .gitignore                # Git ignore configuration
├── config.py                 # Loads and manages environment variables
├── main.py                   # Main entry point to run the bot
├── README.md                 # This file
└── requirements.txt          # Project dependencies
```

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/your-username/your-repo/issues).

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 📄 License

This project is under a proprietary license. See the `LICENSE` file for more details.
All rights are reserved. This software is for personal, non-commercial use only.

---

## ⚠️ Important Notices

-   **Not Financial Advice**: This bot is an analytical tool designed to provide data-driven insights based on technical and macroeconomic indicators. The information and analyses provided do not constitute financial advice.
-   **Risk of Loss**: Trading in financial markets involves substantial risk of loss and is not suitable for every investor. You are solely responsible for your own trading decisions.
-   **No Guarantees**: The analysis provided is based on algorithms and AI models, which are not infallible. There is no guarantee of accuracy or profitability. Always perform your own due diligence.
```