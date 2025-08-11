import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
from pytz import timezone
from sqlalchemy import update, select, distinct

from app.api_client import GeminiModel, fetch_and_prepare_candles
from app.db import DB, PriceAlert, AlertType, async_session
from config import (
    ADMIN_IDS, API_ENABLED, ECONOMIC_CALENDAR_URL,
    ECONOMIC_CALENDAR_HEADERS, PRICE_API_URL
)

if API_ENABLED:
    try:
        gemini_model = GeminiModel()
        logging.info("Successfully initialized GeminiModel for scheduler.")
    except Exception as e:
        logging.error(f"Could not initialize GeminiModel for scheduler: {e}")
        gemini_model = None
else:
    gemini_model = None


class MyfxbookCalendarScraper:
    """
    Scrapes economic calendar data from Myfxbook.
    """
    def __init__(self):
        self.url = ECONOMIC_CALENDAR_URL
        self.headers = ECONOMIC_CALENDAR_HEADERS
        self.target_currencies = ['USD', 'EUR']
        self.acceptable_impacts = ['Medium', 'High']
        self.baghdad_tz = timezone('Asia/Baghdad')

    def _parse_event_datetime(self, date_str: str) -> Optional[datetime]:
        """Parses date and time strings from the Myfxbook calendar."""
        current_year = datetime.now(self.baghdad_tz).year
        parts = date_str.split(',')
        date_part = parts[0].strip()
        time_part = parts[1].strip() if len(parts) > 1 else ""

        try:
            event_date = datetime.strptime(f"{date_part} {current_year}", "%b %d %Y").date()
            final_dt_naive = datetime(current_year, event_date.month, event_date.day)

            if time_part:
                try:
                    event_time = datetime.strptime(time_part.upper(), "%I:%M%p").time()
                except ValueError:
                    event_time = datetime.strptime(time_part, "%H:%M").time()
                final_dt_naive = final_dt_naive.replace(hour=event_time.hour, minute=event_time.minute)

            return self.baghdad_tz.localize(final_dt_naive, is_dst=None)
        except ValueError as ve:
            logging.warning(f"Failed to parse event datetime '{date_str}': {ve}")
            return None

    async def _scrape_calendar(self) -> List[Dict[str, Any]]:
        """Fetches and parses economic calendar data."""
        economic_events = []
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(self.url, timeout=20) as response:
                    response.raise_for_status()
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")

            rows = soup.find_all("tr", class_="economicCalendarRow")
            today_baghdad = datetime.now(self.baghdad_tz).date()
            tomorrow_baghdad = today_baghdad + timedelta(days=1)

            for row in rows:
                try:
                    date_div = row.find("div", {"data-calendardatetd": True})
                    if not date_div: continue
                    date_str = date_div.text.strip()

                    tds = row.find_all("td")
                    if len(tds) < 6: continue

                    currency = tds[3].text.strip()
                    event = tds[4].text.strip()
                    
                    # Updated impact parsing logic
                    impact_div = tds[5].find('div', class_=lambda x: x and x.startswith('impact_'))
                    impact = impact_div.text.strip() if impact_div else "None"

                    if currency not in self.target_currencies or impact not in self.acceptable_impacts:
                        continue

                    event_full_dt = self._parse_event_datetime(date_str)
                    if not event_full_dt or event_full_dt.date() not in [today_baghdad, tomorrow_baghdad]:
                        continue
                    
                    economic_events.append({
                        "datetime_obj": event_full_dt,
                        "currency": currency, "event": event, "impact": impact,
                        "previous": row.find("td", {"data-previous": True}).text.strip() or "N/A",
                        "forecast": row.find("td", {"data-concensus": True}).text.strip() or "N/A",
                        "actual": row.find("td", {"data-actual": True}).text.strip() or "Not released"
                    })
                except Exception as e:
                    logging.error(f"Error parsing calendar row: {e}", exc_info=True)
            
            economic_events.sort(key=lambda x: x['datetime_obj'])
            return economic_events
        except aiohttp.ClientError as e:
            logging.error(f"Network error fetching economic calendar: {e}")
            return []
        except Exception as e:
            logging.error(f"Unexpected error fetching economic calendar: {e}")
            return []

# --- Scheduler Jobs ---

async def scheduled_analysis_job(asset: str, bot: Bot):
    """Scheduled job to perform analysis and send to VIP users."""
    logging.info(f"SCHEDULER: Running analysis for {asset}")
    if not API_ENABLED or not gemini_model:
        logging.warning("SCHEDULER: API is disabled, skipping analysis job.")
        return
    try:
        candles = await fetch_and_prepare_candles(asset)
        recommendation = await gemini_model.analyze_asset(asset, candles)
        vip_users = await DB.get_vip_users()
        if not vip_users:
            logging.warning("SCHEDULER: No VIP users found to send analysis to.")
            return
        
        message_text = f"<b>Automated VIP Analysis for {asset}</b>\n\n{recommendation}"
        logging.info(f"SCHEDULER: Found {len(vip_users)} VIPs. Broadcasting analysis.")
        
        tasks = [bot.send_message(chat_id=user.id, text=message_text) for user in vip_users]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for user, result in zip(vip_users, results):
            if isinstance(result, Exception):
                logging.warning(f"SCHEDULER: Failed to send to {user.id}: {result}")

    except Exception as e:
        logging.error(f"SCHEDULER: Job for {asset} failed: {e}")
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"🚨 Scheduled task for <b>{asset}</b> failed!\n<b>Error:</b> <code>{e}</code>")
            except Exception as admin_e:
                logging.error(f"Failed to notify admin {admin_id}: {admin_e}")

async def fetch_current_price(asset: str) -> Optional[float]:
    """Fetches the current real-time price for a given asset."""
    params = {'asset': asset.upper(), 'frames': '1m:1'}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(PRICE_API_URL, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                if data and "data" in data and "1m" in data["data"] and data["data"]["1m"]:
                    latest_candle = data["data"]["1m"][-1]
                    price = latest_candle.get("current_price") or latest_candle.get("close")
                    return float(price) if price is not None else None
                logging.warning(f"API for {asset} returned invalid data structure: {data}")
                return None
    except aiohttp.ClientError as e:
        logging.error(f"Network error fetching price for {asset}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error fetching price for {asset}: {e}")
        return None

async def check_price_alerts_job(bot: Bot):
    """Scheduled job to check all active price alerts."""
    active_assets = await DB.get_distinct_alert_assets()
    if not active_assets:
        return

    price_tasks = {asset: fetch_current_price(asset) for asset in active_assets}
    price_results = await asyncio.gather(*price_tasks.values(), return_exceptions=True)
    
    asset_prices = {asset: price for asset, price in zip(active_assets, price_results) if isinstance(price, float)}

    if not asset_prices:
        logging.info("SCHEDULER: Could not fetch any prices for active alerts.")
        return

    active_alerts = await DB.get_all_active_price_alerts()
    triggered_one_time_ids = []

    for alert in active_alerts:
        current_price = asset_prices.get(alert.asset)
        if current_price is None:
            continue

        triggered = (alert.alert_type == AlertType.ABOVE and current_price >= alert.target_price) or \
                    (alert.alert_type == AlertType.BELOW and current_price <= alert.target_price)

        if triggered:
            try:
                alert_freq_text = "This was a one-time alert and has been deactivated." if alert.is_one_time else "This is a recurring alert and will trigger again."
                message_text = (
                    f"🔔 **Price Alert!**\n\n"
                    f"The price of **{alert.asset}** has reached `{current_price:.4f}`!\n"
                    f"This matches your alert for a price {'above' if alert.alert_type == AlertType.ABOVE else 'below'} `{alert.target_price}`.\n\n"
                    f"**Note:** {alert_freq_text}"
                )
                await bot.send_message(chat_id=alert.user_id, text=message_text)
                
                if alert.is_one_time:
                    triggered_one_time_ids.append(alert.id)
                logging.info(f"Price alert triggered for user {alert.user_id} on {alert.asset}. One-time: {alert.is_one_time}")
            except Exception as e:
                logging.error(f"SCHEDULER: Failed to send price alert to user {alert.user_id}: {e}")

    if triggered_one_time_ids:
        async with async_session() as s:
            await s.execute(
                update(PriceAlert).where(PriceAlert.id.in_(triggered_one_time_ids)).values(is_active=False, triggered_at=datetime.now())
            )
            await s.commit()
        logging.info(f"SCHEDULER: Deactivated {len(triggered_one_time_ids)} one-time price alerts.")

async def send_daily_economic_calendar_job(bot: Bot):
    """Scheduled job to send the daily economic calendar to all users."""
    logging.info("SCHEDULER: Running daily economic calendar job.")
    scraper = MyfxbookCalendarScraper()
    events = await scraper._scrape_calendar()

    if not events:
        message_text = "🗓️ **Daily Economic Calendar**\n\nNo significant economic events (Medium or High impact) scheduled for today or tomorrow."
    else:
        message_text = "🗓️ **Daily Economic Calendar (Baghdad Time)**\n\nKey events for today and tomorrow:\n"
        today = datetime.now(timezone('Asia/Baghdad')).date()
        current_day_str = ""
        for event in events:
            event_day = event['datetime_obj'].date()
            day_str = "Today" if event_day == today else "Tomorrow"
            if day_str != current_day_str:
                current_day_str = day_str
                message_text += f"\n--- **{current_day_str} - {event_day.strftime('%A, %d %B')}** ---\n"
            
            impact_emoji = "🔴" if event['impact'] == "High" else "🟠"
            message_text += (
                f"\n{impact_emoji} **{event['event']}**\n"
                f"  ⏰ {event['datetime_obj'].strftime('%H:%M')} | Currency: {event['currency']}\n"
                f"  📊 Prev: `{event['previous']}` | Forecast: `{event['forecast']}` | Actual: `{event['actual']}`\n"
            )
    
    all_users = await DB.get_all_active_users()
    if not all_users:
        logging.warning("SCHEDULER: No users to send daily calendar to.")
        return

    tasks = [bot.send_message(user.id, message_text, disable_web_page_preview=True) for user in all_users]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    sent_count = sum(1 for r in results if not isinstance(r, Exception))
    logging.info(f"SCHEDULER: Sent daily calendar to {sent_count}/{len(all_users)} users.")
    if sent_count > 0:
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, f"✅ Daily economic calendar sent to {sent_count} users.")

async def setup_scheduler(bot: Bot, scheduler: AsyncIOScheduler):
    """Adds all jobs to the scheduler."""
    tasks = await DB.get_all_tasks()
    for task in tasks:
        scheduler.add_job(scheduled_analysis_job, 'cron', hour=task.hour, minute=task.minute, id=task.job_id, args=[task.asset, bot], replace_existing=True)
    
    scheduler.add_job(check_price_alerts_job, 'interval', minutes=1, args=[bot], id='price_alert_checker', replace_existing=True)
    
    scheduler.add_job(
        send_daily_economic_calendar_job, 'cron', hour=2, minute=0,
        timezone=timezone('Asia/Baghdad'), args=[bot],
        id='daily_calendar_sender', replace_existing=True
    )
    
    logging.info("All scheduler jobs have been set up.")
