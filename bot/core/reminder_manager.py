import logging
from pathlib import Path
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tinydb import TinyDB, Query

log = logging.getLogger(__name__)

class ReminderManager:
    """Manages scheduled reminders and their persistence."""

    def __init__(self, data_dir: Path, bot_app_context):
        self.data_dir = data_dir
        self.db_path = self.data_dir / "reminders.json"
        self.db = TinyDB(self.db_path)
        self.scheduler = AsyncIOScheduler()
        self.bot_app_context = bot_app_context # To send messages via the bot
        self._load_reminders()
        self.scheduler.start()
        log.info(f"ReminderManager initialized, data stored at {self.db_path}. Scheduler started.")

    def _load_reminders(self):
        """Load reminders from DB and reschedule them."""
        for reminder_data in self.db.all():
            try:
                # Only reschedule if the reminder is in the future
                remind_at_dt = datetime.fromisoformat(reminder_data["remind_at"])
                if remind_at_dt > datetime.now():
                    self._schedule_reminder_job(reminder_data)
                    log.debug(f"Rescheduled reminder: {reminder_data['message']} for {remind_at_dt}")
                else:
                    self.db.update({"status": "past_due"}, doc_ids=[reminder_data.doc_id])
                    log.info(f"Marked past due reminder: {reminder_data['message']}")
            except Exception as e:
                log.error(f"Failed to load or reschedule reminder {reminder_data}: {e}")

    async def add_reminder(self, chat_id: int, message: str, remind_at: datetime) -> dict:
        """Add a new reminder to be scheduled."""
        reminder = {
            "chat_id": chat_id,
            "message": message,
            "remind_at": remind_at.isoformat(), # Store as ISO string
            "created_at": datetime.now().isoformat(),
            "status": "scheduled"
        }
        doc_id = self.db.insert(reminder)
        reminder["doc_id"] = doc_id # Add doc_id for scheduling
        self._schedule_reminder_job(reminder)
        log.info(f"Added reminder for chat {chat_id} at {remind_at}: {message}")
        return reminder

    def _schedule_reminder_job(self, reminder_data: dict):
        """Schedule a job with APScheduler."""
        remind_at_dt = datetime.fromisoformat(reminder_data["remind_at"])
        self.scheduler.add_job(
            self._send_reminder,
            'date',
            run_date=remind_at_dt,
            args=[reminder_data["chat_id"], reminder_data["message"], reminder_data.doc_id],
            id=f"reminder_{reminder_data.doc_id}",
            replace_existing=True
        )
        log.info(f"Scheduled reminder job for {reminder_data['chat_id']} at {remind_at_dt}")

    async def _send_reminder(self, chat_id: int, message: str, doc_id: int):
        """Callback function to send the reminder message."""
        log.info(f"Sending reminder to chat {chat_id}: {message}")
        try:
            await self.bot_app_context.bot.send_message(chat_id=chat_id, text=f"🔔 Reminder: {message}")
            self.db.update({"status": "sent"}, doc_ids=[doc_id])
            log.info(f"Reminder sent and status updated for doc_id {doc_id}.")
        except Exception as e:
            log.error(f"Failed to send reminder for doc_id {doc_id} to chat {chat_id}: {e}")
            self.db.update({"status": "failed"}, doc_ids=[doc_id])
