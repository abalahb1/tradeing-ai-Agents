import asyncio
from typing import List
from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from cachetools import TTLCache

from app.db import DB, User
from app.keyboards import (
    main_admin_keyboard, system_management_keyboard, special_lists_keyboard,
    paginated_users_keyboard, user_management_keyboard, scheduler_menu_keyboard,
    list_tasks_keyboard
)
from app.states import FSM
from config import ADMIN_IDS

admin_router = Router()
admin_router.message.filter(F.from_user.id.in_(ADMIN_IDS))
admin_router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

# --- Main Admin Handlers ---

@admin_router.message(Command("admin"))
@admin_router.callback_query(F.data == "admin:main")
async def admin_start_handler(event: Message | CallbackQuery, state: FSMContext):
    """Displays the main admin panel."""
    await state.clear()
    text = "👑 <b>Admin Control Panel</b>"
    markup = main_admin_keyboard()
    if isinstance(event, Message):
        await event.answer(text, reply_markup=markup)
    else:
        await event.message.edit_text(text, reply_markup=markup)
        await event.answer()

@admin_router.callback_query(F.data == "admin:stats")
async def admin_stats_handler(query: CallbackQuery):
    """Displays bot statistics."""
    stats = await DB.get_stats()
    text = (
        f"📊 <b>Bot Statistics</b>\n\n"
        f"<b>Total Users:</b> {stats['total_users']}\n"
        f"  - <i>Free:</i> {stats['free_users']}\n"
        f"  - <i>Standard:</i> {stats['standard_users']}\n"
        f"  - <i>Pro:</i> {stats['pro_users']}\n\n"
        f"<b>VIP Members:</b> {stats['vip_users']}\n"
        f"<b>Active Scheduled Tasks:</b> {stats['active_tasks']}\n"
        f"<b>Total Price Alerts:</b> {stats['total_alerts']}"
    )
    await query.message.edit_text(text, reply_markup=main_admin_keyboard())
    await query.answer()

# --- System Management ---

@admin_router.callback_query(F.data == "admin:system")
async def admin_system_menu_handler(query: CallbackQuery):
    """Displays the system management menu."""
    await query.message.edit_text("⚙️ <b>System Management</b>", reply_markup=system_management_keyboard())
    await query.answer()

@admin_router.callback_query(F.data == "admin:cache_stats")
async def admin_cache_stats_handler(query: CallbackQuery, analysis_cache: TTLCache):
    """Shows statistics about the analysis cache."""
    text = f"📈 <b>Cache Status</b>\n\n- Items in cache: {analysis_cache.currsize} / {analysis_cache.maxsize}"
    await query.answer(text, show_alert=True)

@admin_router.callback_query(F.data == "admin:cache_clear")
async def admin_cache_clear_handler(query: CallbackQuery, analysis_cache: TTLCache):
    """Clears the analysis cache."""
    analysis_cache.clear()
    await query.answer("🧹 Cache has been cleared successfully!", show_alert=True)

# --- User Management ---

async def get_user_details_text(user: User) -> str:
    """Formats a user's details into a readable string."""
    expiry = user.subscription_expiry.strftime('%Y-%m-%d %H:%M') if user.subscription_expiry else "N/A"
    return (
        f"👤 <b>User:</b> {user.first_name}\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Username:</b> @{user.username if user.username else 'Not set'}\n\n"
        f"<b>Plan:</b> {user.subscription_tier.capitalize()}\n"
        f"<b>Credits:</b> {user.credits}\n"
        f"<b>Expires on:</b> {expiry}\n"
        f"<b>VIP Member:</b> {'✅ Yes' if user.is_vip else '❌ No'}\n"
        f"<b>Join Date:</b> {user.join_date.strftime('%Y-%m-%d')}"
    )

@admin_router.callback_query(F.data.startswith("users:page:"))
async def admin_browse_users_handler(query: CallbackQuery):
    """Handles pagination for browsing users."""
    page = int(query.data.split(":")[-1])
    users, total = await DB.get_all_users(page=page)
    if not users:
        return await query.message.edit_text("No users found.", reply_markup=main_admin_keyboard())
    
    total_pages = (total + 5 - 1) // 5
    await query.message.edit_text(
        f"👥 <b>All Users</b> (Page {page}/{total_pages})",
        reply_markup=paginated_users_keyboard(users, total, page, 5)
    )
    await query.answer()

@admin_router.callback_query(F.data == "admin:search_user_prompt")
async def admin_search_user_prompt_handler(query: CallbackQuery, state: FSMContext):
    """Prompts the admin to enter a search query for a user."""
    await state.set_state(FSM.admin_search_user)
    await query.message.edit_text("Please send the User ID or username to search for.")
    await query.answer()

@admin_router.message(FSM.admin_search_user)
async def admin_perform_user_search_handler(message: Message, state: FSMContext):
    """Performs the user search and displays the result."""
    await state.clear()
    query = message.text.strip()
    
    user = await DB.search_user(query)
    
    if not user:
        await message.answer(
            f"❌ No user found for query: `{query}`",
            reply_markup=main_admin_keyboard()
        )
        return
        
    text = await get_user_details_text(user)
    await message.answer(text, reply_markup=user_management_keyboard(user))

@admin_router.callback_query(F.data.startswith("user:view:"))
async def admin_view_user_handler(query: CallbackQuery):
    """Displays the management panel for a specific user."""
    user_id = int(query.data.split(":")[-1])
    user = await DB.get_user(user_id)
    if not user:
        return await query.answer("User not found.", show_alert=True)
    
    text = await get_user_details_text(user)
    await query.message.edit_text(text, reply_markup=user_management_keyboard(user))
    await query.answer()

@admin_router.callback_query(F.data.startswith("user:"))
async def manage_user_actions_handler(query: CallbackQuery):
    """Handles actions from the user management panel (tier, credits, VIP)."""
    parts = query.data.split(":")
    action, user_id_str = parts[1], parts[-1]
    user_id = int(user_id_str)

    if action == "set_tier":
        tier = parts[2]
        await DB.update_user_tier(user_id, tier)
        await query.answer(f"User's plan set to {tier}.")
    elif action == "add_credits":
        amount = int(parts[2])
        await DB.change_credits(user_id, amount)
        await query.answer(f"{amount} credits added.")
    elif action == "toggle_vip":
        user = await DB.get_user(user_id)
        new_status = not user.is_vip
        await DB.set_vip_status(user_id, new_status)
        await query.answer(f"User is now {'a VIP' if new_status else 'not a VIP'}.")

    user = await DB.get_user(user_id)
    text = await get_user_details_text(user)
    await query.message.edit_text(text, reply_markup=user_management_keyboard(user))

# --- Special User Lists ---

@admin_router.callback_query(F.data == "admin:special_lists")
async def admin_special_lists_menu_handler(query: CallbackQuery):
    """Displays the menu for special user lists."""
    await query.message.edit_text("📋 <b>Special Lists</b>\n\nChoose a list to view:", reply_markup=special_lists_keyboard())
    await query.answer()

async def send_user_list(query: CallbackQuery, users: List[User], title: str):
    """Helper function to display a list of users."""
    if not users:
        return await query.answer(f"No users found in the '{title}' list.", show_alert=True)
    
    text = f"<b>{title} ({len(users)})</b>\n\n"
    user_lines = [
        f"- {u.first_name} (<code>{u.id}</code>)" +
        (f" - Expires: {u.subscription_expiry.strftime('%Y-%m-%d')}" if u.subscription_expiry else "")
        for u in users
    ]
    text += "\n".join(user_lines)
    await query.message.edit_text(text, reply_markup=special_lists_keyboard())
    await query.answer()

@admin_router.callback_query(F.data.startswith("list:"))
async def admin_show_list_handler(query: CallbackQuery):
    """Shows the selected special user list."""
    list_type = query.data.split(":")[-1]
    if list_type == "vips":
        await send_user_list(query, await DB.get_vip_users(), "👑 VIP Users")
    elif list_type == "subscribers":
        await send_user_list(query, await DB.get_subscribers(), "💎 Subscribers (Standard/Pro)")
    elif list_type == "expired":
        await send_user_list(query, await DB.get_expired_users(), "⚠️ Expired Subscriptions")

# --- Scheduler Management ---

@admin_router.callback_query(F.data == "admin:scheduler")
async def scheduler_menu_handler(query: CallbackQuery):
    """Displays the scheduler management menu."""
    await query.message.edit_text("⏰ **Scheduled Task Management**", reply_markup=scheduler_menu_keyboard())
    await query.answer()

# Add Task
@admin_router.callback_query(F.data == "task:add_prompt")
async def add_task_prompt_handler(query: CallbackQuery, state: FSMContext):
    await state.set_state(FSM.add_task_asset)
    await query.message.edit_text("Please send the asset symbol to schedule analysis for (e.g., XAUUSD).")
    await query.answer()

@admin_router.message(FSM.add_task_asset)
async def add_task_asset_handler(message: Message, state: FSMContext):
    await state.update_data(asset=message.text.upper())
    await state.set_state(FSM.add_task_hour)
    await message.answer("Please send the hour (0-23).")

@admin_router.message(FSM.add_task_hour)
async def add_task_hour_handler(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (0 <= int(message.text) <= 23):
        return await message.answer("Invalid hour. Please enter a value between 0 and 23.")
    await state.update_data(hour=int(message.text))
    await state.set_state(FSM.add_task_minute)
    await message.answer("Please send the minute (0-59).")

@admin_router.message(FSM.add_task_minute)
async def add_task_minute_handler(message: Message, state: FSMContext, scheduler: AsyncIOScheduler, bot: Bot):
    if not message.text.isdigit() or not (0 <= int(message.text) <= 59):
        return await message.answer("Invalid minute. Please enter a value between 0 and 59.")
    
    data = await state.get_data()
    asset, hour, minute = data['asset'], data['hour'], int(message.text)
    job_id = f"task_{asset}_{hour}_{minute}"

    if scheduler.get_job(job_id):
        return await message.answer("A task for this asset and time already exists.", reply_markup=scheduler_menu_keyboard())

    await DB.add_task(job_id, asset, hour, minute)
    # Import here to avoid circular dependency
    from app.scheduler import scheduled_analysis_job
    scheduler.add_job(scheduled_analysis_job, 'cron', hour=hour, minute=minute, id=job_id, args=[asset, bot], replace_existing=True)
    
    await state.clear()
    await message.answer(f"✅ Task scheduled for **{asset}** at {hour:02d}:{minute:02d}!", reply_markup=scheduler_menu_keyboard())

# Remove Task
@admin_router.callback_query(F.data == "task:list_prompt")
async def list_tasks_prompt_handler(query: CallbackQuery):
    tasks = await DB.get_all_tasks()
    if not tasks:
        return await query.message.edit_text("No scheduled tasks found.", reply_markup=scheduler_menu_keyboard())
    await query.message.edit_text("Select a task to remove:", reply_markup=list_tasks_keyboard(tasks, for_edit=False))
    await query.answer()

@admin_router.callback_query(F.data.startswith("task:remove:"))
async def remove_task_handler(query: CallbackQuery, scheduler: AsyncIOScheduler):
    job_id = query.data.split(":", 2)[2]
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    await DB.delete_task(job_id)
    await query.answer(f"✅ Task {job_id} removed successfully.")
    
    tasks = await DB.get_all_tasks()
    if not tasks:
        return await query.message.edit_text("All scheduled tasks have been removed.", reply_markup=scheduler_menu_keyboard())
    await query.message.edit_text("Select another task to remove:", reply_markup=list_tasks_keyboard(tasks, for_edit=False))

# Edit Task
@admin_router.callback_query(F.data == "task:edit_prompt")
async def edit_task_prompt_handler(query: CallbackQuery, state: FSMContext):
    tasks = await DB.get_all_tasks()
    if not tasks:
        return await query.message.edit_text("No scheduled tasks to edit.", reply_markup=scheduler_menu_keyboard())
    await state.set_state(FSM.edit_task_select)
    await query.message.edit_text("Select the task you wish to edit:", reply_markup=list_tasks_keyboard(tasks, for_edit=True))
    await query.answer()

@admin_router.callback_query(F.data.startswith("task:edit:"), StateFilter(FSM.edit_task_select))
async def select_task_to_edit_handler(query: CallbackQuery, state: FSMContext):
    # This handler needs to be implemented fully
    await query.answer("Editing tasks is not fully implemented in this refactor.", show_alert=True)


# --- Broadcast ---

@admin_router.callback_query(F.data == "admin:broadcast")
async def broadcast_start_handler(query: CallbackQuery, state: FSMContext):
    await state.set_state(FSM.broadcast_message)
    try:
        await query.message.edit_text(
            "Please send the message you want to broadcast to all users.",
            reply_markup=system_management_keyboard()
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in e.message:
            raise  # Re-raise exceptions that are not about the message not being modified
    await query.answer()

@admin_router.message(FSM.broadcast_message)
async def get_broadcast_msg_handler(message: Message, state: FSMContext):
    stats = await DB.get_stats()
    await state.update_data(message_text=message.html_text)
    await message.answer(
        f"This message will be sent to **{stats['total_users']}** users. Are you sure?\n\n{message.html_text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm and Send", callback_data="broadcast:send")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin:system")]
        ])
    )
    await state.set_state(FSM.broadcast_confirm)

@admin_router.callback_query(F.data == "broadcast:send", StateFilter(FSM.broadcast_confirm))
async def send_broadcast_confirm_handler(query: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    await query.message.edit_text("📢 Starting broadcast...")
    
    user_ids = await DB.get_all_user_ids()
    sent, failed = 0, 0
    
    tasks = [bot.send_message(user_id, data['message_text']) for user_id in user_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            failed += 1
        else:
            sent += 1

    await query.message.edit_text(
        f"✅ Broadcast complete.\n\n- Sent: {sent}\n- Failed: {failed}",
        reply_markup=system_management_keyboard()
    )
    await query.answer()
