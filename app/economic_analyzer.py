import asyncio
import json
import logging
import textwrap
from datetime import datetime, timedelta
from typing import Any, Dict, List

import aiohttp
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request as AuthRequest
from google.oauth2 import service_account

from config import (
    NEWS_API_KEY, PROJECT_ID, LOCATION, SERVICE_ACCOUNT_FILE, MODEL_ID_PRO
)


class EconomicAnalyzer:
    """
    Performs economic analysis by fetching news and economic calendar data,
    and then using a generative model to create a recommendation.
    """
    def __init__(self):
        self.news_api_key = NEWS_API_KEY
        self.target_currencies = ['USD', 'EUR', 'GBP']
        self.acceptable_impacts = ['Medium', 'High']
        self.today = datetime.now().date()
        self.tomorrow = self.today + timedelta(days=1)

    async def _fetch_economic_calendar(self) -> List[Dict[str, Any]]:
        """Asynchronously fetches and parses the economic calendar."""
        url = "https://www.myfxbook.com/forex-economic-calendar"
        headers = {"User-Agent": "Mozilla/5.0"}
        economic_events = []
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=20) as response:
                    response.raise_for_status()
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    rows = soup.find_all("tr", class_="economicCalendarRow")

                    for row in rows:
                        try:
                            date_str = row.find("div", {"data-calendardatetd": True}).text.strip()
                            currency = row.find_all("td")[3].text.strip()
                            event = row.find_all("td")[4].text.strip()
                            impact_img = row.find_all("td")[5].find('img', class_='impactIcon')
                            impact = impact_img['title'] if impact_img and 'title' in impact_img.attrs else "Low"
                            
                            if currency not in self.target_currencies or impact not in self.acceptable_impacts:
                                continue

                            # Simple date parsing, can be improved for robustness
                            if ',' in date_str and ':' in date_str:
                                event_dt = datetime.strptime(f"{date_str} {datetime.now().year}", "%b %d, %H:%M %Y")
                                if event_dt.date() not in [self.today, self.tomorrow]:
                                    continue
                            else:
                                continue # Skip events without a specific time

                            economic_events.append({
                                "datetime": date_str,
                                "currency": currency,
                                "event": event,
                                "impact": impact,
                                "previous": row.find("td", {"data-previous": True}).text.strip(),
                                "forecast": row.find("td", {"data-concensus": True}).text.strip(),
                                "actual": row.find("td", {"data-actual": True}).text.strip() or "Not released"
                            })
                        except (IndexError, AttributeError, ValueError) as e:
                            logging.warning(f"Could not parse an economic calendar row: {e}")
                            continue
        except aiohttp.ClientError as e:
            logging.error(f"Error fetching economic calendar: {e}")
        return economic_events

    async def _fetch_market_news(self) -> List[Dict[str, str]]:
        """Asynchronously fetches market news from NewsAPI."""
        url = "https://newsapi.org/v2/everything"
        query = "(iran OR Israel OR war OR USA)"
        params = {
            "qInTitle": query,
            "language": "en",
            "sortBy": "publishedAt",
            "apiKey": self.news_api_key,
            "pageSize": 20,
        }
        market_news = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=15) as response:
                    response.raise_for_status()
                    data = await response.json()
                    articles = data.get("articles", [])
                    for article in articles:
                        market_news.append({
                            "title": article.get("title", "No Title"),
                            "description": article.get("description", "No Description"),
                            "publishedAt": article.get("publishedAt", "No Date")
                        })
        except aiohttp.ClientError as e:
            logging.error(f"Error fetching market news: {e}")
        return market_news

    def _build_prompt(self, target_asset: str, economic_calendar: list, market_news: list) -> str:
        """Builds the prompt for the generative model."""
        simplified_calendar = [
            f"{e['datetime']} {e['currency']} {e['event'].splitlines()[0]} Impact: {e['impact']} "
            f"Previous: {e['previous']} Forecast: {e['forecast']} Actual: {e['actual']}"
            for e in economic_calendar
        ]
        calendar_str = "\n".join(simplified_calendar) if simplified_calendar else "No significant economic events for today or tomorrow."

        simplified_news = [
            f"-• {news.get('title', 'No Title')}. Desc: {textwrap.shorten(news.get('description') or '', 100)}"
            for news in market_news
        ]
        news_str = "\n".join(simplified_news) if simplified_news else "No high-impact market news found."
        
        return textwrap.dedent(f'''
            You are a senior institutional macroeconomic strategist at a global investment firm.
            You have received highly curated data from premium sources.

            --- ECONOMIC CALENDAR ---
            {calendar_str}

            --- POLITICAL & MARKET NEWS ---
            {news_str}

            --- ANALYSIS TARGET ---
            Focus your full analysis on this financial asset: **{target_asset}**

            --- CONTEXT ---
            The year is 2025. Your outlook should focus on the next 24 to 72 hours.

            --- TASK ---
            1. Evaluate the combined impact of the listed economic and geopolitical data on the asset's near-term performance.
            2. Identify the dominant macro narrative influencing investor behavior.
            3. Based on your analysis, write a **professional institutional recommendation** that includes:
               - Market Direction: Buy / Sell / Hold
               - Justification: Economic and geopolitical reasoning
               - Timeframe: 24–72 hours
               - Confidence Level: High / Medium / Low

            ⚠️ Return the response in **English only**.
            The output must read like an official investment memo for executive decision-makers.
            Do not include headers or formatting — just the final written report.
        ''').strip()

    async def _get_gcloud_auth_token(self) -> str:
        """Asynchronously gets Google Cloud authentication token."""
        def get_token_sync():
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
                credentials.refresh(AuthRequest())
                return credentials.token
            except FileNotFoundError:
                logging.error(f"Service account key file not found at: {SERVICE_ACCOUNT_FILE}")
                return None
        return await asyncio.to_thread(get_token_sync)

    async def _call_gemini_api(self, model_id: str, prompt: str, auth_token: str) -> str:
        """Asynchronously calls the Gemini API."""
        api_endpoint = f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/{model_id}:generateContent"
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json; charset=utf-8"}
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.5, "maxOutputTokens": 2048}
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_endpoint, headers=headers, json=payload, timeout=120) as response:
                    response.raise_for_status()
                    response_json = await response.json()
                    return response_json['candidates'][0]['content']['parts'][0]['text']
        except (aiohttp.ClientError, json.JSONDecodeError, KeyError, IndexError) as e:
            logging.error(f"Error calling model {model_id}: {e}")
            body = await response.text()
            logging.error(f"Response body: {body}")
            raise Exception("Failed to get a valid response from the AI model.")

    async def get_analysis(self, target_asset: str) -> str:
        """The main async method to be called from the bot."""
        auth_token, calendar_data, news_data = await asyncio.gather(
            self._get_gcloud_auth_token(),
            self._fetch_economic_calendar(),
            self._fetch_market_news()
        )

        if not auth_token:
            raise Exception("Failed to authenticate with Google Cloud.")
            
        prompt = self._build_prompt(target_asset, calendar_data, news_data)
        
        final_recommendation = await self._call_gemini_api(MODEL_ID_PRO, prompt, auth_token)
        
        return final_recommendation
