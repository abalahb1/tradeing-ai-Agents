from aiogram.fsm.state import State, StatesGroup

class FSM(StatesGroup):
    # Admin states for adding a scheduled task
    add_task_asset = State()
    add_task_hour = State()
    add_task_minute = State()

    # Admin states for editing a scheduled task
    edit_task_select = State()
    edit_task_hour = State()
    edit_task_minute = State()

    # Admin states for broadcasting a message
    broadcast_message = State()
    broadcast_confirm = State()

    # User state for providing a custom asset for analysis
    custom_asset = State()
    
    # Admin state for searching a user
    admin_search_user = State()

    # User states for setting a price alert
    set_alert_asset = State()
    set_alert_price = State()
    set_alert_type = State()
    set_alert_frequency = State() 
    delete_alert_confirm = State()
