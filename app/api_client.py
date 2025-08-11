import json
import asyncio
import logging
from datetime import datetime
from typing import Dict

import aiohttp
import pandas as pd
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest

from config import (
    PROJECT_ID, ENDPOINT_ID, SERVICE_ACCOUNT_FILE, LOCATION, PRICE_API_URL
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


async def fetch_and_prepare_candles(asset: str) -> dict:
    """
    Fetches candle data from the price API and prepares it in a structured format.
    """
    url = f"{PRICE_API_URL}?asset={asset.upper()}&frames=1m:35,5m:70,15m:5,1h:30,4h:25,1d:1"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
        except aiohttp.ClientError as e:
            logging.error(f"❌ Failed to fetch data for {asset}: {e}")
            return {}
        except json.JSONDecodeError as e:
            logging.error(f"❌ Failed to parse JSON for {asset}: {e}")
            return {}

    data = data.get("data", {})
    if not data:
        logging.warning(f"No data found in response for asset: {asset}")
        return {}

    timeframes = {
        "1m": "1M", "5m": "5M", "15m": "15M",
        "1h": "1H", "4h": "4H", "1d": "1D"
    }

    final_candles = {}
    for api_key, tf in timeframes.items():
        if api_key in data and data[api_key]:
            df = pd.DataFrame(data[api_key])
            final_candles[tf.lower()] = []
            for _, row in df.iterrows():
                final_candles[tf.lower()].append({
                    "time": row["time"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"])
                })
    return final_candles


class GeminiModel:
    """
    A client for interacting with the Google Gemini API via Vertex AI.
    """
    def __init__(self):
        self.project_id = PROJECT_ID
        self.endpoint_id = ENDPOINT_ID
        self.service_account_file = SERVICE_ACCOUNT_FILE
        self.location = LOCATION
        self.url = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/projects/{self.project_id}"
            f"/locations/{self.location}/endpoints/{self.endpoint_id}:streamGenerateContent"
        )
        self.credentials = self._load_credentials()
        self.last_token_refresh = datetime.min
        self.token = None

    def _load_credentials(self):
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        try:
            return service_account.Credentials.from_service_account_file(
                self.service_account_file, scopes=scopes
            )
        except FileNotFoundError:
            logging.error(f"Service account file not found at: {self.service_account_file}")
            raise

    def _refresh_token(self):
        logging.info("Refreshing Google Cloud access token.")
        self.credentials.refresh(GoogleAuthRequest())
        self.last_token_refresh = datetime.now()
        return self.credentials.token

    def _get_headers(self) -> Dict[str, str]:
        if not self.credentials.valid or not self.token:
            self.token = self._refresh_token()
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    async def send_prompt(self, prompt: str, temperature: float = 0.9, top_p: float = 0.95) -> str:
        headers = self._get_headers()
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "topP": top_p,
                "maxOutputTokens": 500
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    chunks = await response.json()
        except aiohttp.ClientError as e:
            logging.error(f"❌ Error during Gemini request: {e}")
            raise Exception(f"❌ Error during request to Gemini: {str(e)}")
        except json.JSONDecodeError as e:
            logging.error(f"❌ Error parsing Gemini response JSON: {e}")
            raise Exception(f"❌ Error parsing Gemini response: {str(e)}")
        except Exception as e:
            logging.error(f"❌ An unexpected error occurred with Gemini: {e}")
            raise Exception(f"❌ An unexpected error occurred with Gemini: {str(e)}")

        result = ""
        for chunk in chunks:
            candidates = chunk.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    result += part.get("text", "")
        return result.strip()

    async def analyze_asset(self, asset_name: str, candles_by_timeframe: dict) -> str:
        if not candles_by_timeframe:
            return "No candle data available for analysis."

        prompt_text = ('''
Give me Recommendation
JUST LIKE THIS OUTPUT ONLY
--- OUTPUT FORMAT (MANDATORY) ---
Recommendation:
- Type: Buy or Sell
- Mode: Pending Limit Order (no Stop orders allowed) or Market Execution
- Entry Price:
- Stop Loss:
- Take Profit:

Do not include any explanation or analysis.
Only return one setup that matches this rule.

--- Data Candles ---
''')

        for tf, candles in candles_by_timeframe.items():
            prompt_text += f"\n🕒 Timeframe: {tf.upper()}\n"
            for c in candles:
                prompt_text += f"[{c['time']}] O:{c['open']} H:{c['high']} L:{c['low']} C:{c['close']} V:{c['volume']}\n"

        return await self.send_prompt(prompt_text)

# Example usage for testing
async def main():
    logging.info("Starting main function for asset analysis.")
    try:
        model = GeminiModel()
        logging.info("Fetching candles for XAUUSD...")
        candles = await fetch_and_prepare_candles("xauusd")

        if not candles:
            logging.error("Failed to get candle data. Exiting.")
            return

        logging.info("Analyzing asset with Gemini model...")
        result = await model.analyze_asset("XAUUSD", candles)
        print("\n--- Gemini Analysis Result ---")
        print(result)
        logging.info("Analysis complete.")
    except Exception as e:
        logging.error(f"An error occurred in the main test function: {e}")

if __name__ == "__main__":
    asyncio.run(main())
