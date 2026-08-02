# OLX Liquidity Tracker

Приватний Telegram Mini App для аналізу ліквідності категорій OLX Ukraine. Інструмент для дослідження перепродажу — показує які категорії товарів найшвидше продаються.

## Можливості

- **Telegram Mini App** — повноцінний UI з вкладками, таблицями та картками (не текстові команди)
- **Щоденний збір даних** о 8:00 за київським часом через Scrapling (обхід captcha)
- **Метрики**: ліквідність %, швидкість продажу (дні), об'єм продажів
- **Фільтри**: період (1/7/30/90 днів), ціновий діапазон (4–20k UAH)
- **Щоденний дайджест** у Telegram: топ-5 категорій, зміни, стрибки продажів

## Стек

- Python 3.11+, FastAPI, python-telegram-bot
- Scrapling (StealthyFetcher) для скрейпінгу OLX
- SQLite, APScheduler
- Deploy: Render.com free tier

## Швидкий старт

```bash
# Клонувати репозиторій
git clone <your-repo-url>
cd Liquidity_bot

# Віртуальне середовище
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Залежності
pip install -r requirements.txt
playwright install chromium

# Налаштування
cp .env.example .env
# Заповнити TELEGRAM_BOT_TOKEN, MY_CHAT_ID, WEBAPP_URL

# Запуск
uvicorn app.main:app --reload --port 8000
```

## Змінні середовища

| Змінна | Опис |
|--------|------|
| `TELEGRAM_BOT_TOKEN` | Токен бота від @BotFather |
| `MY_CHAT_ID` | Ваш Telegram chat ID (приватний доступ) |
| `WEBAPP_URL` | URL WebApp (https://your-app.onrender.com) |
| `DATABASE_PATH` | Шлях до SQLite (за замовч. `./data/liquidity.db`) |
| `SCRAPE_ENABLED` | `true` / `false` |

## Telegram Bot

1. Створіть бота через [@BotFather](https://t.me/BotFather)
2. У BotFather: `/setmenubutton` → URL вашого WebApp
3. Надішліть `/start` — з'явиться кнопка «Відкрити OLX Liquidity»

## Deploy на Render

1. Push на GitHub
2. Render → New → Blueprint → підключити репозиторій
3. Додати env vars: `TELEGRAM_BOT_TOKEN`, `MY_CHAT_ID`, `WEBAPP_URL`
4. Після деплою оновити `WEBAPP_URL` на фактичний URL Render

## Архітектура

```
app/
├── main.py           # FastAPI + bot + scheduler
├── config.py         # Налаштування
├── database.py       # SQLite
├── scraper/          # OLX + Scrapling
├── metrics/          # Розрахунок ліквідності
├── scheduler/        # Cron 8:00 Kyiv
├── bot/              # Telegram bot
└── api/              # REST API для WebApp
webapp/               # Mini App UI (HTML/CSS/JS)
```

## Ліквідність

```
Ліквідність = (продано / всього на ринку) × 100%
```

Продаж визначається порівнянм сьогоднішніх і вчорашніх оголошень: зникло з OLX = продано.

## Безпека

- Доступ лише для `MY_CHAT_ID`
- WebApp перевіряє Telegram `initData`
- Токени тільки в env, не в коді

## Ліцензія

Приватний проєкт. Тільки для особистого використання.
