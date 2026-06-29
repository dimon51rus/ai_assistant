from calendar_client import YandexCalendar
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from jinja2 import Environment, FileSystemLoader
import requests
import os
import json
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Secretary")
env = Environment(loader=FileSystemLoader("templates"))

# ==================================================
# ========== НАСТРОЙКИ YANDEXGPT ===================
# ==================================================

FOLDER_ID = os.getenv("FOLDER_ID")
API_KEY = os.getenv("API_KEY")
if not FOLDER_ID or not API_KEY:
    raise RuntimeError("FOLDER_ID и API_KEY должны быть заданы в .env")

YANDEXGPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
MODEL_URI = f"gpt://{FOLDER_ID}/yandexgpt-lite"

SYSTEM_PROMPT = """
Ты — профессиональный и вежливый ИИ-секретарь.
Твоя задача — помогать пользователю в работе и личных делах.
Отвечай кратко, ясно и по делу.
Если информации недостаточно — задавай уточняющие вопросы.
Будь дружелюбным, но профессиональным.
Сегодня: {date}
"""

# ==================================================
# ========== РАБОТА С ЗАДАЧАМИ (JSON) =============
# ==================================================

TASKS_FILE = "tasks.json"

def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

def add_task(description, due_date=None):
    tasks = load_tasks()
    task = {
        "id": str(uuid.uuid4()),
        "description": description,
        "due_date": due_date,
        "created_at": datetime.now().isoformat(),
        "completed": False
    }
    tasks.append(task)
    save_tasks(tasks)
    return task

def list_tasks(show_completed=False):
    tasks = load_tasks()
    if not show_completed:
        tasks = [t for t in tasks if not t.get("completed", False)]
    return tasks

def complete_task(task_id):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["completed"] = True
            save_tasks(tasks)
            return task
    return None

def delete_task(task_id):
    tasks = load_tasks()
    new_tasks = [t for t in tasks if t["id"] != task_id]
    if len(new_tasks) == len(tasks):
        return None
    save_tasks(new_tasks)
    return True

# ==================================================
# ========== ИНИЦИАЛИЗАЦИЯ КЛИЕНТА КАЛЕНДАРЯ ======
# ==================================================

calendar_client = YandexCalendar(
    username=os.getenv("YANDEX_USERNAME"),
    password=os.getenv("YANDEX_PASSWORD")
)

# ==================================================
# ========== ОБРАБОТКА КОМАНД =====================
# ==================================================

def process_command(user_message: str) -> (bool, str):
    """
    Обрабатывает команды пользователя.
    Возвращает (обработано_ли_команда, ответ_текст)
    """
    msg_lower = user_message.lower().strip()
    tasks = load_tasks()

    # ========== 1. КОМАНДЫ ДЛЯ КАЛЕНДАРЯ ==========
    if any(phrase in msg_lower for phrase in [
        "календарь", "события", "что у меня сегодня", "что у меня завтра",
        "сегодняшние", "завтрашние", "покажи задачи в моем календаре",
        "все задачи в календаре", "покажи календарь", "мои события"
    ]):
        try:
            if "завтра" in msg_lower or "завтрашн" in msg_lower:
                events = calendar_client.get_events_for_tomorrow()
                day_label = "завтра"
            else:
                events = calendar_client.get_events_for_today()
                day_label = "сегодня"

            if not events:
                return True, f"📭 На {day_label} событий не запланировано."

            result = f"📅 Ваши события на {day_label}:\n"
            for event in events:
                event_str = str(event)
                summary = "Без названия"
                if "SUMMARY:" in event_str:
                    summary = event_str.split("SUMMARY:")[1].split("\n")[0].strip()
                result += f"  • {summary}\n"
            return True, result
        except Exception as e:
            return True, f"❌ Ошибка при получении календаря: {e}"

    # ========== 2. КОМАНДЫ ДЛЯ ЗАДАЧ ==========

    # --- Добавить задачу ---
    if any(msg_lower.startswith(prefix) for prefix in ["запланируй", "добавь задачу", "создай задачу", "новая задача"]):
        rest = user_message
        for prefix in ["запланируй", "добавь задачу", "создай задачу", "новая задача"]:
            if msg_lower.startswith(prefix):
                rest = user_message[len(prefix):].strip()
                break

        due_date = None
        if "завтра" in rest:
            due_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            rest = rest.replace("завтра", "").strip()
        elif "сегодня" in rest:
            due_date = datetime.now().strftime("%Y-%m-%d")
            rest = rest.replace("сегодня", "").strip()

        if rest:
            task = add_task(rest, due_date)
            date_str = f" на {due_date}" if due_date else ""
            return True, f"✅ Задача добавлена{date_str}:\n\"{task['description']}\"\nID: {task['id'][:8]}"
        else:
            return True, "❌ Не удалось распознать описание задачи. Укажите, что нужно сделать."

    # --- Показать задачи ---
    if any(msg_lower.startswith(prefix) for prefix in ["покажи задачи", "список задач", "мои задачи", "задачи"]):
        tasks = list_tasks(show_completed=False)
        if not tasks:
            return True, "📭 Нет активных задач."
        result = "📋 Ваши активные задачи:\n"
        for i, task in enumerate(tasks, 1):
            due = f" (срок: {task['due_date']})" if task.get('due_date') else ""
            result += f"{i}. {task['description']}{due}\n   ID: {task['id'][:8]}\n"
        return True, result

    # --- Выполнить задачу ---
    if any(msg_lower.startswith(prefix) for prefix in ["выполни задачу", "заверши задачу", "отметь как выполненную"]):
        words = user_message.split()
        task_id = None
        for word in words:
            if len(word) >= 8:
                task_id = word
                break
        if not task_id:
            return True, "❌ Укажите ID задачи, которую нужно завершить. ID можно увидеть в списке задач."
        tasks_all = load_tasks()
        found_task = None
        for t in tasks_all:
            if t["id"].startswith(task_id):
                found_task = t
                break
        if found_task:
            if found_task.get("completed"):
                return True, f"ℹ️ Задача \"{found_task['description']}\" уже выполнена."
            complete_task(found_task["id"])
            return True, f"✅ Задача \"{found_task['description']}\" отмечена как выполненная."
        else:
            return True, "❌ Задача с таким ID не найдена."

    # --- Удалить задачу ---
    if any(msg_lower.startswith(prefix) for prefix in ["удали задачу", "удалить задачу"]):
        words = user_message.split()
        task_id = None
        for word in words:
            if len(word) >= 8:
                task_id = word
                break
        if not task_id:
            return True, "❌ Укажите ID задачи, которую нужно удалить."
        tasks_all = load_tasks()
        found_task = None
        for t in tasks_all:
            if t["id"].startswith(task_id):
                found_task = t
                break
        if found_task:
            delete_task(found_task["id"])
            return True, f"🗑️ Задача \"{found_task['description']}\" удалена."
        else:
            return True, "❌ Задача с таким ID не найдена."

    # Если ни одна команда не подошла
    return False, ""

# ==================================================
# ========== ХРАНИЛИЩЕ ИСТОРИИ =====================
# ==================================================

chat_history = []

# ==================================================
# ========== МОДЕЛЬ ЗАПРОСА ========================
# ==================================================

class ChatRequest(BaseModel):
    message: str

# ==================================================
# ========== ФУНКЦИЯ ЗАПРОСА К YANDEXGPT ==========
# ==================================================

def ask_yandexgpt(user_message: str, history: list = None) -> str:
    messages = [
        {"role": "system", "text": SYSTEM_PROMPT.format(date=datetime.now().strftime("%d.%m.%Y"))}
    ]
    if history:
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "text": msg["content"]})
    messages.append({"role": "user", "text": user_message})

    payload = {
        "modelUri": MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 1000
        },
        "messages": messages
    }
    headers = {
        "Authorization": f"Api-Key {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(YANDEXGPT_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get("result", {}).get("alternatives"):
            return result["result"]["alternatives"][0]["message"]["text"]
        else:
            return "Извините, не удалось получить ответ от модели."
    except Exception as e:
        return f"Ошибка при обращении к YandexGPT: {e}"

# ==================================================
# ========== ЭНДПОИНТЫ =============================
# ==================================================

@app.get("/", response_class=HTMLResponse)
async def chat_ui():
    template = env.get_template("chat.html")
    html_content = template.render(history=chat_history)
    return HTMLResponse(content=html_content)

@app.post("/chat")
async def chat(request: ChatRequest):
    global chat_history
    user_message = request.message

    is_command, cmd_response = process_command(user_message)
    if is_command:
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": cmd_response})
        return {"response": cmd_response}

    chat_history.append({"role": "user", "content": user_message})
    answer = ask_yandexgpt(user_message, chat_history[:-1])
    chat_history.append({"role": "assistant", "content": answer})
    return {"response": answer}

@app.get("/ping")
def ping():
    return {"status": "ok"}