from typing import List
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from app.db import User, ScheduledTask, PriceAlert, AlertType


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Returns the main menu reply keyboard."""
    buttons = [
        [KeyboardButton(text="📊 SMC Analysis"), KeyboardButton(text="📈 Economic Analysis")],
        [KeyboardButton(text="🗓️ Economic Calendar"), KeyboardButton(text="🔔 Price Alerts")],
        [KeyboardButton(text="👤 My Profile"), KeyboardButton(text="💎 Subscriptions")],
        [KeyboardButton(text="💡 Help")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_back_to_main_menu_inline() -> InlineKeyboardMarkup:
    """Returns an InlineKeyboardMarkup for returning to the main menu."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back to Main Menu", callback_data="main_menu")]
    ])

def main_admin_keyboard() -> InlineKeyboardMarkup:
    """Returns the main admin panel keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 General Stats", callback_data="admin:stats")],
        [
            InlineKeyboardButton(text="🔍 Search User", callback_data="admin:search_user_prompt"),
            InlineKeyboardButton(text="📋 Browse Users", callback_data="users:page:1")
        ],
        [InlineKeyboardButton(text="📋 Special Lists", callback_data="admin:special_lists")],
        [InlineKeyboardButton(text="⚙️ System Management", callback_data="admin:system")],
    ])

def system_management_keyboard() -> InlineKeyboardMarkup:
    """Returns the system management keyboard for admins."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Task Management", callback_data="admin:scheduler")],
        [InlineKeyboardButton(text="📢 Broadcast Message", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="📈 Cache Stats", callback_data="admin:cache_stats")],
        [InlineKeyboardButton(text="🧹 Clear Cache", callback_data="admin:cache_clear")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="admin:main")]
    ])

def special_lists_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for viewing special user lists."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 Show VIPs", callback_data="list:vips")],
        [InlineKeyboardButton(text="💎 Show Subscribers (Pro/Standard)", callback_data="list:subscribers")],
        [InlineKeyboardButton(text="⚠️ Show Expired Subscriptions", callback_data="list:expired")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="admin:main")]
    ])

def paginated_users_keyboard(users: List[User], total: int, page: int, per_page: int) -> InlineKeyboardMarkup:
    """Creates a paginated keyboard for browsing users."""
    buttons = [[InlineKeyboardButton(text=f"👤 {user.first_name}", callback_data=f"user:view:{user.id}")] for user in users]
    total_pages = (total + per_page - 1) // per_page
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"users:page:{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"users:page:{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)
    buttons.append([InlineKeyboardButton(text="⬅️ Back to Main Menu", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def user_management_keyboard(user: User) -> InlineKeyboardMarkup:
    """Returns the keyboard for managing a specific user."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Set Standard", callback_data=f"user:set_tier:standard:{user.id}")],
        [InlineKeyboardButton(text="Set Pro", callback_data=f"user:set_tier:pro:{user.id}")],
        [InlineKeyboardButton(text="Set Free", callback_data=f"user:set_tier:free:{user.id}")],
        [InlineKeyboardButton(text="🎁 Add 10 Credits", callback_data=f"user:add_credits:10:{user.id}")],
        [InlineKeyboardButton(
            text="➖ Remove VIP" if user.is_vip else "➕ Add VIP",
            callback_data=f"user:toggle_vip:{user.id}"
        )],
        [InlineKeyboardButton(text="⬅️ Back to User List", callback_data="users:page:1")]
    ])

def get_analysis_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for selecting an asset for technical analysis."""
    assets = {
        "🥇 Gold": "XAUUSD", "🇪🇺 EUR/USD": "EURUSD", "🇺🇸 NASDAQ 100": "US100",
        "🇺🇸 Dow Jones": "US30", "₿ Bitcoin": "BTCUSD", "🇬🇧 GBP/USD": "GBPUSD"
    }
    rows = [[InlineKeyboardButton(text=t, callback_data=f"analyze:{s}") for t, s in list(assets.items())[i:i+2]] for i in range(0, len(assets), 2)]
    rows.append([InlineKeyboardButton(text="📈 Other Asset", callback_data="analyze:other")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_economic_analysis_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for selecting an asset for economic analysis."""
    assets = {"🥇 Gold": "XAUUSD", "🇪🇺 EUR/USD": "EURUSD", "🇺🇸 NASDAQ 100": "US100"}
    rows = [[InlineKeyboardButton(text=t, callback_data=f"eco_analyze:{s}") for t, s in list(assets.items())[i:i+2]] for i in range(0, len(assets), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def scheduler_menu_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for the scheduler management menu."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Task", callback_data="task:add_prompt")],
        [InlineKeyboardButton(text="📋 View / Remove Tasks", callback_data="task:list_prompt")],
        [InlineKeyboardButton(text="✏️ Edit Task", callback_data="task:edit_prompt")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="admin:system")]
    ])

def list_tasks_keyboard(tasks: List[ScheduledTask], for_edit: bool = False) -> InlineKeyboardMarkup:
    """Returns a keyboard listing scheduled tasks for removal or editing."""
    buttons = []
    if tasks:
        for t in tasks:
            action = "edit" if for_edit else "remove"
            text_prefix = "✏️" if for_edit else "❌"
            buttons.append([InlineKeyboardButton(
                text=f"{text_prefix} {t.asset} @ {t.hour:02d}:{t.minute:02d}",
                callback_data=f"task:{action}:{t.job_id}"
            )])
    buttons.append([InlineKeyboardButton(text="⬅️ Back to Task Menu", callback_data="admin:scheduler")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Price Alert Keyboards ---

def get_alert_asset_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for selecting an asset for a price alert."""
    assets = {"🥇 Gold": "XAUUSD", "🇪🇺 EUR/USD": "EURUSD", "₿ Bitcoin": "BTCUSD", "🇬🇧 GBP/USD": "GBPUSD"}
    rows = [[InlineKeyboardButton(text=t, callback_data=f"set_alert:{s}") for t, s in list(assets.items())[i:i+2]] for i in range(0, len(assets), 2)]
    rows.append([InlineKeyboardButton(text="➕ Add Other Asset", callback_data="set_alert:other_asset")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_alert_type_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for selecting the alert trigger type (above/below)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬆️ When price is ABOVE", callback_data="alert_type:above")],
        [InlineKeyboardButton(text="⬇️ When price is BELOW", callback_data="alert_type:below")]
    ])

def get_alert_frequency_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for selecting the alert frequency (one-time/recurring)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="One-Time Alert (deleted after trigger)", callback_data="alert_freq:one_time")],
        [InlineKeyboardButton(text="Recurring Alert (stays active after trigger)", callback_data="alert_freq:recurring")]
    ])

def get_manage_alerts_keyboard(alerts: List[PriceAlert]) -> InlineKeyboardMarkup:
    """Returns a keyboard to manage existing price alerts."""
    buttons = []
    if alerts:
        for alert in alerts:
            status_emoji = "✅" if alert.is_active else "😴"
            alert_type_text = "⬆️ Above" if alert.alert_type == AlertType.ABOVE else "⬇️ Below"
            freq_text = " (one-time)" if alert.is_one_time else " (recurring)"
            buttons.append([InlineKeyboardButton(
                text=f"{status_emoji} {alert.asset} @ {alert.target_price:.2f} ({alert_type_text}){freq_text}",
                callback_data=f"alert_manage:{alert.id}"
            )])
    buttons.append([InlineKeyboardButton(text="➕ Add New Alert", callback_data="alerts:add")])
    buttons.append([InlineKeyboardButton(text="⬅️ Back to Main Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_alert_action_keyboard(alert_id: int) -> InlineKeyboardMarkup:
    """Returns keyboard with actions for a specific alert (e.g., delete)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Delete Alert", callback_data=f"alert_action:delete:{alert_id}")],
        [InlineKeyboardButton(text="⬅️ Back to Alerts List", callback_data="alerts:list")]
    ])

def get_upgrade_keyboard() -> InlineKeyboardMarkup:
    """Returns a keyboard prompting user to upgrade for a feature."""
    from config import YOUR_USERNAME
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Contact Admin to Upgrade", url=f"https://t.me/{YOUR_USERNAME}")]
    ])
