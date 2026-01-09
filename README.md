# 🎬 DistrictWatch

Real-time movie booking alerts for District.in with dynamic multi-movie and multi-theatre selection.

## ✨ Features

- 🎯 **Dynamic Movie Management** - Add/remove movies via Telegram
- 🎭 **Dynamic Theatre Selection** - Customize theatres per movie
- 📱 **Instant Telegram Alerts** - Get notified when bookings open
- 🔄 **Smart Change Detection** - No duplicate alerts
- 🛡️ **Anti-Detection** - Stealth browser automation
- 💾 **Persistent State** - Survives restarts

## 🚀 Quick Start

### 1. Get Telegram Credentials

1. Create bot at [@BotFather](https://t.me/BotFather) → Get `TELEGRAM_TOKEN`
2. Message [@userinfobot](https://t.me/userinfobot) → Get `TELEGRAM_CHAT_ID`

### 2. Setup

```bash
# Clone repo
git clone https://github.com/yourusername/district-watch.git
cd district-watch

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Configure
cp .env.example .env
# Edit .env with your Telegram credentials

# Run
python main.py
```

### 3. Use Telegram Commands

```
/add https://district.in/movies/leo-... Leo Chennai
/list
/theaters leo_chennai
/addtheater leo_chennai SPI Cinemas
/status
```

## 📱 Commands

| Command | Description |
|---------|-------------|
| `/add <url> <name> [city]` | Add movie to monitor |
| `/remove <id>` | Remove movie |
| `/list` | List all movies |
| `/enable <id>` | Enable monitoring |
| `/disable <id>` | Pause monitoring |
| `/theaters <id>` | Show movie's theatres |
| `/addtheater <id> <name>` | Add theatre to movie |
| `/removetheater <id> <name>` | Remove theatre |
| `/status` | System status |
| `/help` | All commands |

## 🐳 Docker

```bash
# Configure
cp .env.example .env
nano .env

# Run
docker-compose up -d

# View logs
docker-compose logs -f
```

## ⚙️ Configuration

Key `.env` settings:

```env
# Required
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Default theatres for new movies
DEFAULT_THEATERS=Vettri:1:vettri;Rohini:1:rohini;PVR:2:pvr

# Check interval (seconds)
CHECK_INTERVAL=120
```

## 📁 Files

```
district-watch/
├── main.py          # Application entry point
├── config.py        # Configuration management
├── commands.py      # Telegram command handler
├── browser.py       # Playwright automation
├── extractor.py     # Data extraction
├── detector.py      # Change detection
├── notifier.py      # Telegram notifications
├── state.py         # SQLite persistence
├── requirements.txt # Dependencies
├── Dockerfile       # Docker image
├── docker-compose.yml
├── .env.example     # Config template
└── data/
    ├── state.db     # State database
    └── movies.json  # Movie configurations
```

## 🔔 Alert Example

```
🚨 BOOKING ALERT 🚨

✨ New availability detected! ✨

🎬 Leo

1. ⭐ Vettri
   📍 Anna Nagar
   🎬 09:00 AM, 12:30 PM, 03:45 PM

2. ⭐ Rohini Silver Screen
   📍 Koyambedu
   🎬 10:00 AM, 01:00 PM

🔗 Book Now

⏰ 02:35 PM, 09 Jan
```

## 📋 Requirements

- Python 3.11+
- Telegram account
- 500MB disk space

## ⚠️ Disclaimer

For personal use only. Respect District.in's terms of service.

## 📝 License

MIT
