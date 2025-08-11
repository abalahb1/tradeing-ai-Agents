import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from cachetools import TTLCache

from app.db import DB, AlertType
from app.economic_analyzer import EconomicAnalyzer
from app.keyboards import (
    get_main_menu_keyboard, get_analysis_keyboard, get_economic_analysis_keyboard,
    get_upgrade_keyboard, get_manage_alerts_keyboard, get_alert_asset_keyboard,
    get_alert_type_keyboard, get_alert_frequency_keyboard, get_alert_action_keyboard,
    get_back_to_main_menu_inline
)
from app.states import FSM
from app.scheduler import MyfxbookCalendarScraper
from config import NEWS_API_KEY, YOUR_USERNAME, API_ENABLED

if API_ENABLED:
    from app.api_client import GeminiModel, fetch_and_prepare_candles
    gemini_model = GeminiModel()
else:
    gemini_model = None

user_router = Router()

# --- Command and Menu Handlers ---

@user_router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext, analysis_cache: TTLCache):
    """Handles the /start command with special onboarding for new users."""
    await state.clear()
    
    existing_user = await DB.get_user(message.from_user.id)
    
    user = await DB.get_or_update_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name
    )

    # --- Onboarding for New Users ---
    if not existing_user:
        welcome_text = (
            f"Welcome, {message.from_user.full_name}!\n\n"
            "I am your analysis bot, here to help you make better decisions in the market.\n\n"
            "Let me show you what I can do! Here is a complimentary analysis for **Gold (XAUUSD)** to get you started."
        )
        await message.answer(welcome_text, reply_markup=get_main_menu_keyboard())
        
        # Trigger the sample analysis
        await start_analysis_process(message, "XAUUSD", analysis_cache)
        
        # Follow-up message
        await message.answer(
            "You have been given **10 free credits** to perform your own analysis on any of our supported assets.\n\n"
            "Feel free to explore the other features like **Price Alerts** and the **Economic Calendar** using the menu below. 👇"
        )
        return

    # --- Standard Welcome for Existing Users ---
    welcome_text = (
        f"Welcome back, {message.from_user.full_name}!\n\n"
        "Use the menu below to get started. 👇"
    )
    if user.is_vip:
        welcome_text = (
            f"👑 Welcome back, VIP {message.from_user.full_name}!\n\n"
            "I'm ready to provide more advanced analytics. What would you like to do today? 👇"
        )
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard())

@user_router.callback_query(F.data == "main_menu")
async def back_to_main_menu_handler(query: CallbackQuery, state: FSMContext):
    """Handles the 'Back to Main Menu' inline button."""
    await state.clear()
    await query.message.edit_text(
        "You are back in the main menu. Choose an option from the keyboard below.",
        reply_markup=None # Reply keyboard is already shown
    )
    await query.answer()

@user_router.message(F.text == "💡 Help")
@user_router.message(Command("help"))
async def help_handler(message: Message):
    """Provides a help message explaining the bot's features."""
    help_text = (
        "<b>Help Center</b>\n\n"
        "Here is an explanation of the bot's functions:\n\n"
        "<b>📊 SMC Analysis:</b>\n"
        "Start a technical analysis for any financial asset. You can choose from the suggested assets "
        "or enter the asset symbol yourself if you are a subscriber.\n\n"
        "<b>📈 Economic Analysis (Pro):</b>\n"
        "In-depth analysis that links news and economic calendar data to its impact on assets. "
        "Available for the Pro plan only.\n\n"
        "<b>🗓️ Economic Calendar:</b>\n"
        "View the most important scheduled economic events that affect the markets.\n\n"
        "<b>🔔 Price Alerts:</b>\n"
        "Set custom price alerts for assets, and I will notify you as soon as the price reaches your target.\n\n"
        "<b>👤 My Profile:</b>\n"
        "View your account details and subscription type.\n\n"
        "<b>💎 Subscriptions:</b>\n"
        "View details of available subscription plans and how to upgrade.\n\n"
        "For any other inquiries, you can contact the administrator."
    )
    await message.answer(help_text)

@user_router.message(F.text == "👤 My Profile")
@user_router.message(Command("my_profile"))
async def profile_handler(message: Message):
    """Displays the user's profile information."""
    user = await DB.get_user(message.from_user.id)
    if not user:
        return await message.answer("Please start the bot first using /start.")
    
    expiry = user.subscription_expiry.strftime("%Y-%m-%d") if user.subscription_expiry else "N/A"
    profile_text = (
        f"👤 <b>My Profile</b>\n\n"
        f"- <b>ID:</b> <code>{user.id}</code>\n"
        f"- <b>Username:</b> @{user.username if user.username else 'Not set'}\n"
        f"- <b>Name:</b> {user.first_name}\n"
        f"- <b>Plan:</b> {user.subscription_tier.capitalize()}\n"
        f"- <b>Subscription Expiry:</b> {expiry}\n"
        f"- <b>VIP Member:</b> {'Yes ✅' if user.is_vip else 'No ❌'}\n"
        f"- <b>Remaining Credits:</b> {user.credits}\n"
        f"- <b>Join Date:</b> {user.join_date.strftime('%Y-%m-%d')}"
    )
    await message.answer(profile_text)

@user_router.message(F.text == "💎 Subscriptions")
@user_router.message(Command("subscribe"))
async def subscribe_handler(message: Message):
    """Displays subscription plans."""
    sub_text = (
        "💎 <b>Subscription Plans</b> 💎\n\n"
        "<b>Free Plan:</b>\n"
        "• 10 free technical analyses.\n"
        "• Access to 6 major assets.\n"
        "💰 <i>Price: Free</i>\n\n"
        "<b>Standard Plan:</b>\n"
        "• Unlimited technical analyses.\n"
        "• Analyze any asset by its symbol.\n"
        "💰 <i>Price: $39.99/month – or $399.99/year</i>\n\n"
        "<b>Pro Plan:</b>\n"
        "• All Standard Plan features.\n"
        "• <b>Full access to the Economic Analysis section.</b>\n"
        "• Receive automated VIP analyses.\n"
        "• <b>Unlimited price alerts.</b>\n"
        "• <b>Access to a detailed economic calendar.</b>\n"
        "• <i>Priority support.</i>\n"
        "💰 <i>Price: $89.99/month – or $899.99/year</i>\n\n"
        "To upgrade your subscription, click the button below to contact the admin."
    )
    contact_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Contact Admin to Upgrade", url=f"https://t.me/{YOUR_USERNAME}")]
    ])
    await message.answer(sub_text, reply_markup=contact_keyboard)

# --- Analysis Handlers ---

async def start_analysis_process(message: Message, asset: str, cache: TTLCache):
    """Shared logic to start the analysis process for an asset."""
    if asset in cache:
        await message.answer(f"<b>Analysis for {asset} (from cache)</b>\n\n{cache[asset]}", disable_web_page_preview=True)
        return

    if not API_ENABLED or not gemini_model:
        return await message.answer("The analysis feature is temporarily disabled by the administration.")

    msg = await message.answer(f"⏳ Analyzing **{asset}**... this might take a moment.")
    try:
        candles = await fetch_and_prepare_candles(asset)
        if not candles:
            await msg.edit_text(f"❌ Could not retrieve market data for **{asset}**. Please check the symbol and try again.")
            return
            
        reco = await gemini_model.analyze_asset(asset, candles)
        cache[asset] = reco
        await msg.edit_text(f"<b>Analysis for {asset}</b>\n\n{reco}", disable_web_page_preview=True)
    except Exception as e:
        logging.error(f"Analysis failed for asset {asset}. Error: {e}")
        await msg.edit_text(f"❌ An error occurred while analyzing **{asset}**. The administration has been notified.")

@user_router.message(F.text == "📊 SMC Analysis")
@user_router.message(Command("analyze"))
async def menu_analyze_handler(message: Message):
    """Handles the 'SMC Analysis' button and /analyze command."""
    user = await DB.get_user(message.from_user.id) or await DB.get_or_update_user(
        message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    
    if user.subscription_tier in ['standard', 'pro'] and user.subscription_expiry and user.subscription_expiry < datetime.now():
        await DB.update_user_tier(user.id, 'free')
        return await message.answer("Your subscription has expired. Please contact the admin to renew.", reply_markup=get_upgrade_keyboard())
    
    if user.subscription_tier == 'free' and user.credits <= 0:
        return await message.answer("You have run out of free analysis credits. Please upgrade your plan to continue.", reply_markup=get_upgrade_keyboard())
        
    await message.answer("Choose an asset for technical analysis:", reply_markup=get_analysis_keyboard())

@user_router.callback_query(F.data.startswith("analyze:"))
async def analyze_callback_handler(query: CallbackQuery, state: FSMContext, analysis_cache: TTLCache):
    """Handles asset selection from the analysis keyboard."""
    user = await DB.get_user(query.from_user.id)
    action = query.data.split(":")[1]
    
    if action == "other":
        if user.subscription_tier == 'free' and not user.is_vip:
            return await query.answer("This feature is exclusive to subscribers and VIP members.", show_alert=True)
        await state.set_state(FSM.custom_asset)
        await query.message.edit_text("Please send the symbol of the asset you wish to analyze (e.g., AAPL, TSLA).")
    else:
        await query.answer()
        if user.subscription_tier == 'free' and not user.is_vip:
            if user.credits <= 0:
                await query.message.edit_text("You have no analysis credits left.", reply_markup=get_upgrade_keyboard())
                return
            await DB.change_credits(user.id, -1)
        
        await query.message.edit_text(f"Analyzing **{action}**... Please wait.")
        await start_analysis_process(query.message, action, analysis_cache)

@user_router.message(FSM.custom_asset)
async def custom_asset_handler(message: Message, state: FSMContext, analysis_cache: TTLCache):
    """Handles the custom asset symbol provided by the user."""
    await state.clear()
    await start_analysis_process(message, message.text.upper(), analysis_cache)

# --- Economic Analysis Handlers ---

@user_router.message(F.text == "📈 Economic Analysis")
async def menu_economic_analysis_handler(message: Message):
    """Handles the 'Economic Analysis' button."""
    user = await DB.get_user(message.from_user.id) or await DB.get_or_update_user(
        message.from_user.id, message.from_user.username, message.from_user.full_name
    )

    if user.subscription_tier != 'pro':
        return await message.answer(
            "💎 **Exclusive Pro Feature**\n\n"
            "This feature is only available to **Pro plan** subscribers.\n\n"
            "Upgrade your subscription to benefit from in-depth economic analyses prepared by our experts.",
            reply_markup=get_upgrade_keyboard()
        )
    
    await message.answer(
        "Please choose an asset for economic analysis from the menu below.",
        reply_markup=get_economic_analysis_keyboard()
    )

@user_router.callback_query(F.data.startswith("eco_analyze:"))
async def economic_analysis_callback(query: CallbackQuery):
    """Handles the asset selection for economic analysis."""
    user = await DB.get_user(query.from_user.id)
    if not user or user.subscription_tier != 'pro':
        await query.answer("This feature is exclusive to the Pro plan.", show_alert=True)
        await query.message.delete()
        return

    asset = query.data.split(":")[1]
    await query.answer(f"Preparing analysis for {asset}...")
    msg = await query.message.edit_text(
        f"⏳ **Preparing Economic Analysis for {asset}**\n\n"
        "We are now collecting the latest economic data and news for analysis... This process may take a minute or more."
    )

    try:
        analyzer = EconomicAnalyzer()
        final_recommendation = await analyzer.get_analysis(asset)
        response_text = f"<b>📊 Comprehensive Economic Analysis for {asset}</b>\n\n{final_recommendation}"
        await msg.edit_text(response_text)
    except FileNotFoundError:
        logging.error("Economic analysis failed: Service account key not found.")
        await msg.edit_text("❌ A technical error occurred (Key not found). The administration has been notified.")
    except Exception as e:
        logging.error(f"Economic analysis for {asset} failed: {e}")
        await msg.edit_text(f"❌ An error occurred while performing the economic analysis for <b>{asset}</b>. The administration has been notified.")

# --- Economic Calendar Handler ---

@user_router.message(F.text == "🗓️ Economic Calendar")
async def myfxbook_calendar_menu_handler(message: Message):
    """Displays the economic calendar."""
    msg_loading = await message.answer("⏳ Fetching the latest economic calendar data...")
    
    scraper = MyfxbookCalendarScraper()
    events = await scraper._scrape_calendar()

    if not events:
        await msg_loading.edit_text("🗓️ **Economic Calendar**\n\nNo significant economic events (Medium or High impact) are scheduled for today or tomorrow.")
        return

    # Build the message
    message_text = "🗓️ **Economic Calendar (Baghdad Time)**\n\nKey events for today and tomorrow:\n"
    today = datetime.now(scraper.baghdad_tz).date()
    current_day_str = ""
    
    for event in events:
        event_day = event['datetime_obj'].date()
        day_str = "Today" if event_day == today else "Tomorrow"
        
        if day_str != current_day_str:
            current_day_str = day_str
            message_text += f"\n--- **{current_day_str} - {event_day.strftime('%A, %d %B')}** ---\n"
        
        impact_emoji = "🔴" if event['impact'] == "High" else "🟠"
        event_text = (
            f"\n{impact_emoji} **{event['event']}**\n"
            f"  ⏰ {event['datetime_obj'].strftime('%H:%M')} | Currency: {event['currency']}\n"
            f"  📊 Prev: `{event['previous']}` | Forecast: `{event['forecast']}` | Actual: `{event['actual']}`\n"
        )
        
        if len(message_text) + len(event_text) > 4096:
            await message.answer(message_text)
            message_text = ""

        message_text += event_text

    await msg_loading.delete()
    if message_text:
        await message.answer(message_text, disable_web_page_preview=True)


# --- Price Alert Handlers ---

async def show_user_alerts_menu(message: Message | CallbackQuery):
    """Displays the user's price alerts management menu."""
    user_alerts = await DB.get_user_price_alerts(message.from_user.id, active_only=False)
    
    text = "Here are your price alerts. You can add a new one or manage existing ones."
    markup = get_manage_alerts_keyboard(user_alerts)

    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=markup)
        await message.answer()
    else:
        await message.answer(text, reply_markup=markup)

@user_router.message(F.text == "🔔 Price Alerts")
async def price_alerts_menu_handler(message: Message):
    """Handles the 'Price Alerts' button."""
    await show_user_alerts_menu(message)

@user_router.callback_query(F.data == "alerts:list")
async def refresh_alerts_list_handler(query: CallbackQuery):
    """Refreshes the alerts list from a callback."""
    await show_user_alerts_menu(query)

@user_router.callback_query(F.data == "alerts:add")
async def start_add_alert_handler(query: CallbackQuery, state: FSMContext):
    """Starts the process of adding a new price alert."""
    user = await DB.get_user(query.from_user.id)
    
    if user.subscription_tier == 'free':
        active_alerts_count = len(await DB.get_user_price_alerts(user.id, active_only=True))
        if active_alerts_count >= 3:
            await query.answer("You have reached the maximum of 3 active alerts for the free plan. Please upgrade to add more.", show_alert=True)
            return

    await state.set_state(FSM.set_alert_asset)
    await query.message.edit_text("Choose the asset you want to set an alert for:", reply_markup=get_alert_asset_keyboard())
    await query.answer()

@user_router.callback_query(F.data.startswith("set_alert:"))
async def select_alert_asset_handler(query: CallbackQuery, state: FSMContext):
    """Handles the asset selection for the new alert."""
    asset_selected = query.data.split(":")[1]
    user = await DB.get_user(query.from_user.id)

    if asset_selected == "other_asset":
        if user.subscription_tier == 'free' and not user.is_vip:
            await query.answer("Adding custom assets is available for subscribers only.", show_alert=True)
            return
        await state.set_state(FSM.set_alert_asset)
        await query.message.edit_text("Please send the symbol for the asset you want to set an alert for (e.g., `GOOGL`, `ETHUSD`).")
    else:
        await state.update_data(alert_asset=asset_selected)
        await state.set_state(FSM.set_alert_price)
        await query.message.edit_text(f"You chose **{asset_selected}**. Now, send the target price for the alert (e.g., `2300.50`).")
    await query.answer()

@user_router.message(FSM.set_alert_asset)
async def handle_custom_alert_asset(message: Message, state: FSMContext):
    """Handles the custom asset symbol for the alert."""
    asset_symbol = message.text.upper().strip()
    if not asset_symbol.isalnum() or not (2 <= len(asset_symbol) <= 10):
        return await message.answer("Invalid asset symbol. It should be 2-10 alphanumeric characters.")

    await state.update_data(alert_asset=asset_symbol)
    await state.set_state(FSM.set_alert_price)
    await message.answer(f"You chose **{asset_symbol}**. Now, send the target price (e.g., `2300.50`).")

@user_router.message(FSM.set_alert_price)
async def set_alert_price_handler(message: Message, state: FSMContext):
    """Handles setting the target price for the alert."""
    try:
        price = float(message.text)
        if price <= 0: raise ValueError
    except ValueError:
        return await message.answer("Please enter a valid, positive number for the price.")

    await state.update_data(target_price=price)
    await state.set_state(FSM.set_alert_type)
    await message.answer("When should the alert be triggered?", reply_markup=get_alert_type_keyboard())

@user_router.callback_query(F.data.startswith("alert_type:"), StateFilter(FSM.set_alert_type))
async def set_alert_type_handler(query: CallbackQuery, state: FSMContext):
    """Handles setting the alert type (above/below)."""
    await state.update_data(alert_type=query.data.split(":")[1])
    await state.set_state(FSM.set_alert_frequency)
    await query.message.edit_text("How often should this alert trigger?", reply_markup=get_alert_frequency_keyboard())
    await query.answer()

@user_router.callback_query(F.data.startswith("alert_freq:"), StateFilter(FSM.set_alert_frequency))
async def set_alert_frequency_handler(query: CallbackQuery, state: FSMContext):
    """Handles setting the alert frequency and saves the alert."""
    is_one_time_alert = (query.data.split(":")[1] == 'one_time')
    data = await state.get_data()
    
    try:
        await DB.add_price_alert(
            user_id=query.from_user.id,
            asset=data['alert_asset'],
            target_price=data['target_price'],
            alert_type=AlertType(data['alert_type']),
            is_one_time=is_one_time_alert
        )
        await state.clear()
        
        freq_text = 'one-time' if is_one_time_alert else 'recurring'
        await query.message.edit_text(f"✅ Alert for **{data['alert_asset']}** has been set as a {freq_text} alert.")
        await show_user_alerts_menu(query)
    except Exception as e:
        logging.error(f"Failed to add price alert for user {query.from_user.id}: {e}")
        await query.message.edit_text("❌ An error occurred while adding the alert. Please try again later.")
    await query.answer()

@user_router.callback_query(F.data.startswith("alert_manage:"))
async def manage_specific_alert_handler(query: CallbackQuery):
    """Displays details and actions for a specific alert."""
    alert_id = int(query.data.split(":")[1])
    alert = await DB.get_price_alert_by_id(alert_id) # Assumes a new DB method
    
    if not alert or alert.user_id != query.from_user.id:
        return await query.answer("Alert not found.", show_alert=True)

    alert_type_text = "Above" if alert.alert_type == AlertType.ABOVE else "Below"
    status_text = "Active" if alert.is_active else "Triggered/Inactive"
    frequency_text = "One-time" if alert.is_one_time else "Recurring"
    
    details_text = (
        f"🔔 **Alert Details**\n\n"
        f"**Asset:** {alert.asset}\n"
        f"**Target Price:** `{alert.target_price:.4f}`\n"
        f"**Type:** {alert_type_text}\n"
        f"**Status:** {status_text}\n"
        f"**Frequency:** {frequency_text}\n"
        f"**Created:** {alert.created_at.strftime('%Y-%m-%d %H:%M')}"
    )
    await query.message.edit_text(details_text, reply_markup=get_alert_action_keyboard(alert_id))
    await query.answer()

@user_router.callback_query(F.data.startswith("alert_action:delete:"))
async def confirm_delete_alert_handler(query: CallbackQuery, state: FSMContext):
    """Confirms the deletion of a price alert."""
    alert_id = int(query.data.split(":")[2])
    await state.set_state(FSM.delete_alert_confirm)
    await state.update_data(alert_to_delete=alert_id)
    await query.message.edit_text(
        "Are you sure you want to delete this alert? This action cannot be undone.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Yes, delete", callback_data="alert_delete_confirmed")],
            [InlineKeyboardButton(text="❌ No, cancel", callback_data="alerts:list")]
        ])
    )
    await query.answer()

@user_router.callback_query(F.data == "alert_delete_confirmed", StateFilter(FSM.delete_alert_confirm))
async def delete_alert_handler(query: CallbackQuery, state: FSMContext):
    """Deletes the price alert from the database."""
    data = await state.get_data()
    alert_id = data.get('alert_to_delete')
    if alert_id:
        await DB.delete_price_alert(alert_id)
        await query.answer("✅ Alert deleted successfully.", show_alert=True)
    
    await state.clear()
    await show_user_alerts_menu(query)
