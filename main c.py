import os
from datetime import datetime
from pymongo import MongoClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

BOT_NAME = "MyBot"

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["bot_db"]
users_col = db["users"]
groups_col = db["groups"]

# DM / Private chat start
def start(update: Update, context: CallbackContext):
    user = update.message.from_user

    # Save user info in MongoDB
    users_col.update_one(
        {"user_id": user.id},
        {"$set": {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "chat_type": "private",
            "joined_at": datetime.utcnow()
        }},
        upsert=True
    )

    text = f"Hello {user.first_name}! I am {BOT_NAME} 🤖\nWelcome! I can chat with you and also work in groups."

    keyboard = [
        [InlineKeyboardButton("Update Channel", url="https://t.me/YourUpdateChannel")],
        [InlineKeyboardButton("Support", url="https://t.me/YourSupportChannel")],
        [InlineKeyboardButton("GC / Group", url="https://t.me/YourGroup")],
        [InlineKeyboardButton("Owner ID", callback_data="owner_id")],
        [InlineKeyboardButton("Add to Group", url=f"https://t.me/{BOT_NAME}?startgroup=true")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(text, reply_markup=reply_markup)

# Callback for buttons
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    if query.data == "owner_id":
        owner_id = os.getenv("OWNER_ID", "Not Set")
        query.edit_message_text(text=f"Owner ID: {owner_id}")

# Group message handler
def group_message(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user = update.message.from_user

    # Save group info if new
    groups_col.update_one(
        {"group_id": chat_id},
        {"$set": {"chat_on": True, "group_name": update.message.chat.title}},
        upsert=True
    )

    # Check if chat is on globally and for this group
    group = groups_col.find_one({"group_id": chat_id})
    chat_on_global = os.getenv("CHAT_ON", "true") == "true"
    if group and group.get("chat_on") and chat_on_global:
        # Reply to message (simple echo for now)
        update.message.reply_text(f"{user.first_name}: {update.message.text}")

# Admin commands for group chat toggle
def toggle_chat(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Only allow group admins or owner to toggle
    owner_id = int(os.getenv("OWNER_ID", "0"))
    member = context.bot.get_chat_member(chat_id, user_id)
    if member.status in ["administrator", "creator"] or user_id == owner_id:
        group = groups_col.find_one({"group_id": chat_id})
        new_status = not group.get("chat_on", True)
        groups_col.update_one({"group_id": chat_id}, {"$set": {"chat_on": new_status}})
        status_text = "ON" if new_status else "OFF"
        update.message.reply_text(f"Group chat is now {status_text}")
    else:
        update.message.reply_text("You are not authorized to toggle chat.")

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    # Handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & Filters.chat_type.groups, group_message))
    dp.add_handler(CommandHandler("togglechat", toggle_chat, Filters.chat_type.groups))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()