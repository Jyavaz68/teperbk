# teperbk

Backup, restore & server migration tool for **PasarGuard** and **PG-Node**.
ابزار بکاپ، ریستور و انتقال سرور برای **پاسارگاد** و **PG-Node**.

[English](#-english) | [فارسی](#-فارسی)

---

## 🇬🇧 English

### Features
- Full backup of PasarGuard + PG-Node (config, data, database)
- Supports **TimescaleDB (PostgreSQL)**, **MySQL** and **MariaDB**, and **detects your database automatically** (no questions asked)
- Aborts the backup if the database export fails, so you never end up with an empty backup
- One-step migration to a new server over SSH
- **Telegram bot + daily schedule:** pick how many times per day and at what hours, from the terminal or from the bot. The cron job is created and updated automatically, and only the latest backup is kept on the server
- **Jalali (Shamsi) dates:** plan a one-time backup for an exact Jalali date and time from the bot
- **Files up to 2 GB** (optional local Bot API server) instead of the 50 MB Telegram bot limit
- **One-click update** from GitHub (menu option 5 or `teperbk --update`)
- **Universal Tools (option 6):** all five databases (SQLite, PostgreSQL, TimescaleDB, MySQL, MariaDB), restore of official PasarGuard backups (split backups too), and database engine conversion with the official PasarGuard migration tool
- **Safer scheduled backups:** every backup is verified, the number of kept backups is configurable, optional HTTP/SOCKS5 proxy for Telegram, free-disk check, and automatic retries with growing delay after a failure
- Manual local backup and restore
- **Test / Final backup mode:** choose whether services are stopped during the backup

### Requirements
- Ubuntu / Debian server, run as **root**
- Docker and Docker Compose
- PasarGuard installed in `/opt/pasarguard` (PG-Node in `/opt/pg-node`, optional)
- For migration: PasarGuard installed on the new server, and root password login enabled there

### Install
```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/jyavaz68/teperbk/main/install.sh)"
```

### Run again
After installation, the tool is available as a command from anywhere:
```bash
teperbk
```
- The script is installed in `/opt/teperbk/teperbk.py`.
- Backup ZIP files are saved in `/root` (never inside `/opt/pasarguard`, because a restore wipes that folder).
- To update to the latest version, just run the install command again.

### Menu
| # | Option | Description |
|---|--------|-------------|
| 1 | Auto Backup & Transfer | Backup, optional Telegram send, then restore on a new server via SSH |
| 2 | Manual Backup | Save the backup ZIP in the current directory |
| 3 | Manual Restore | Restore from a local ZIP (wipes the current setup) |
| 4 | **Telegram Bot & Daily Schedule** | Permanent daily backups with cron + a bot you control from Telegram (recommended) |
| 5 | **Update** | Download the latest version from GitHub |
| 6 | **Universal Tools** | All databases, official PasarGuard backups, database conversion |
| 7 | Exit | |

The database type is **detected automatically**: for backups it reads the services in `/opt/pasarguard/docker-compose.yml`, and for restore it reads the content of the ZIP file. Options 1-3 work with TimescaleDB, MySQL and MariaDB. If your panel uses **SQLite or plain PostgreSQL**, they tell you to use option 6 (Universal Tools); the Telegram scheduler (option 4) handles those two automatically.

### Backup mode (options 1 and 2)
The script asks: *Stop Pasarguard & PG-Node during backup?*
- **n (test):** nothing is stopped, zero downtime. Data may change while the backup runs.
- **y (final):** the app and the node are stopped (the database stays up for the dump), so no data changes. You can also choose to keep them stopped after the backup, which is what you want for a migration.

Scheduled Telegram backups (option 4) never stop anything.

### What is inside the backup
`docker-compose.yml`, `.env`, the database dump, `/var/lib/pasarguard`, `/opt/pg-node` and `/var/lib/pg-node`.

---

### Telegram bot & daily scheduled backups (option 4)

This is the "set it and forget it" mode. It takes the same full backup as the migration (same ZIP format, so you can restore it on a new server), sends it to your Telegram, and keeps only the **latest** copy on the server.

#### Setup
1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Open your new bot in Telegram and press **START** (a bot cannot message you before that).
3. Get your numeric ID from [@userinfobot](https://t.me/userinfobot). Use your **own** account ID, not a group.
4. Run `teperbk`, choose **4**, then **1**, and enter the token, your ID, the bot language, your time zone (default `Asia/Tehran`) and the daily times, for example `03:00, 15:00` (two backups per day).

The script then automatically:
- creates the cron job in `/etc/cron.d/teperbk`
- installs and starts a small systemd service (`teperbk-bot`) so you can control everything from Telegram
- sends you a test message with the bot menu

#### Controlling it from Telegram
Only your admin ID can use the bot. Everyone else is ignored.

| Command / button | What it does |
|------------------|--------------|
| `/start` | Open the menu |
| 📦 Backup now (`/backup`) | Take a backup right now and send it |
| 📊 Status (`/status`) | Shows times, last backup, kept file, cron state |
| ⏰ Schedule (`/schedule`) | Presets (1x, 2x, 3x, 4x per day) or custom daily times |
| 📅 One-time backup (`/once 1405/08/29 14:30`) | Backup at an exact **Jalali** (or Gregorian) date and time |
| 🗑 Cancel dated backups | Removes all pending one-time backups |
| `/settz Asia/Tehran` | Change the time zone used for hours and dates |
| `/settimes 03:00 15:30` | Set the daily times directly |
| 🌐 Language | Switch between فارسی and English |

When you change the schedule in the bot (or from the terminal menu), the cron job on the server is rewritten automatically.

#### Extra safety (added in 1.2.0)
- **Verification:** each new backup is read back before it is accepted: archive integrity (CRC), database dump present and not empty, and the dump's end marker. A backup that fails is deleted and **your older backups stay untouched**; you get a message.
- **Keep N backups:** keep the last 1 to 30 backups on the server (`/keep 3` in the bot, or `teperbk` → 4 → 8). Default is 1, like before.
- **Disk check:** the backup is skipped (with a message) if the disk does not have enough free space for the temporary copy and the archive.
- **Retry with growing delay:** after a failure the bot retries after 15 min, 30 min, 1 h ... up to 6 h. You are told about the 1st failure and then every 3rd one, and when backups work again. The bot service must be running for retries.
- **Telegram proxy:** `teperbk` → 4 → 8 → 2 accepts `socks5://host:port`, `socks5://user:pass@host:port` or `http://host:port`. It is used only for the normal Telegram server (not for the local 2 GB server).
- **Backup engine:** `auto` (default) uses the built-in backup for TimescaleDB, MySQL and MariaDB and the **official** `pasarguard backup` for SQLite and PostgreSQL. `official` uses the official backup for every database.

#### How it behaves
- **No downtime:** scheduled backups never stop PasarGuard or PG-Node.
- **Only the latest backup stays on the server** in `/opt/teperbk/backups`. Older ones are deleted only after the new backup was created successfully, so a failed run never leaves you with nothing.
- **Time zone:** all hours and dates use the time zone you chose (default `Asia/Tehran`), even if the server is in another country. The script converts the hours for cron automatically and re-checks them regularly (for example after a daylight-saving change on the server).
- **Jalali dates:** with the Persian bot language, dates in messages are shown in the Jalali calendar. A one-time backup runs only if the bot service was online at that time. If it was offline for more than 30 minutes, the backup is skipped and you get a message.
- **Big backups:** the normal Telegram bot API accepts files up to 50 MB, so bigger backups are sent in 45 MB parts (join them with `cat backup_XXXX.zip.part* > backup_XXXX.zip`). To send a single file up to 2 GB, see *Large files* below.
- **Overlap protection:** if a backup is already running, a second one is skipped.
- **Failures:** if a backup or the upload fails, the bot sends you a message. Details are in `/var/log/teperbk.log` (rotated weekly).
- **Files:** settings (bot token, times) are stored in `/opt/teperbk/config.json` with permission `600`.
- **Remove everything:** `teperbk` → 4 → 7 removes the cron job and stops the bot service.

#### Large files up to 2 GB (optional)
You choose: **without API** (default, nothing to set up, big backups are split into 45 MB parts) or **with API** (single file up to 2 GB). The script asks you during the Telegram setup, and you can switch any time from `teperbk` → **4** → **5**.

Telegram's normal bot API limits uploads to 50 MB. To send up to 2 GB in one file, the script can run the official **Telegram Bot API server** in a Docker container on your server (`aiogram/telegram-bot-api`, listening on `127.0.0.1:8081` only).

1. Get an `api_id` and `api_hash` at [my.telegram.org](https://my.telegram.org) → *API development tools*.
2. Run `teperbk` → **4** → **5** and enter them. The script starts the container, logs your bot out of the normal Telegram server and switches the bot to the local one.
3. To go back: the same menu item switches it off. After that, the bot needs about **10 minutes** before it answers again (a Telegram rule when moving a bot between servers).

Notes: the container image is a third-party image from Docker Hub, and it handles your bot token, so use it only if you trust it. This mode is optional and off by default. If anything fails, normal 50 MB mode with split parts keeps working.

---

### Universal Tools (option 6)

These tools follow the official PasarGuard documentation and tools ([docs.pasarguard.org](https://docs.pasarguard.org)). They do not change how options 1-5 work.

1. **Backup now (official).** Runs `pasarguard backup`, which works for SQLite, PostgreSQL, TimescaleDB, MySQL and MariaDB. The archive is verified and a copy is kept in `/opt/teperbk/backups`. You can send it to your Telegram bot right away.
2. **Restore a PasarGuard backup.** For archives made by `pasarguard backup` or its Telegram backup service, any database, **split (multi-part) backups too**. It lists the archives it finds (`/root`, the current folder, `/opt/pasarguard/backup`, `/opt/teperbk/backups`) or takes a full path, runs `pasarguard restore <file> --check`, and then restores with the official command: normal mode if a panel is already installed here, `--fresh` mode on a clean new server. You must type `RESTORE` to confirm.
3. **Convert the database engine.** For example MariaDB → TimescaleDB or SQLite → PostgreSQL, using the official [db-migrations](https://github.com/PasarGuard/db-migrations) tool. The wizard:
   - takes the data from a backup archive (teperbk or official), a database file or dump, or a live database URL;
   - reads the target from the panel installed on this server (`.env`) or from a URL you type, and checks that the target is reachable;
   - asks you to confirm three times (backup done, same version and tables created, and typing `MIGRATE`);
   - runs the official tool. PostgreSQL dump files must go through the official tool's own menu, so the wizard prints the exact answers to type.

   Official flow, in short: back up the source → install PasarGuard on the **target** database with the **same app version** and start it once (so it creates its tables) → run the conversion → check users and settings in the panel. The target database is erased before the data is copied.
4. **Documentation links.**

Requirements: the official `pasarguard` command (the script offers to install it with `install-script`), and for conversion `git` plus network access (the official tool installs its own dependencies).

---

### Updating
Run `teperbk` → **5** (or `teperbk --update`). The script downloads the latest `teperbk.py` from GitHub, checks that it is valid Python, keeps the old file as `/opt/teperbk/teperbk.py.bak`, installs the new one and restarts the Telegram bot service if it is installed. Your settings are not touched.

---

### Migration guide: old server → new server

Follow the steps in order.

#### Step 0: Before you start
- Lower the **TTL** of your domain's A record to 60-300 seconds (a day earlier if possible). The DNS switch will be much faster.
- Note down: your database type (TimescaleDB, MySQL or MariaDB), your PasarGuard version, and whether you use PG-Node.

#### Step 1: Prepare the NEW server (clean install, no domain)
Install a fresh PasarGuard with the **same database type** as the old server. Don't configure a domain or SSL and don't create an admin. Just install it and let it run on the server IP. Everything gets replaced by the backup anyway.

TimescaleDB:
```bash
curl -fsSL https://github.com/PasarGuard/scripts/raw/main/pasarguard.sh -o /tmp/pg.sh \
  && sudo bash /tmp/pg.sh install --database timescaledb
```
MySQL:
```bash
curl -fsSL https://github.com/PasarGuard/scripts/raw/main/pasarguard.sh -o /tmp/pg.sh \
  && sudo bash /tmp/pg.sh install --database mysql
```
MariaDB:
```bash
curl -fsSL https://github.com/PasarGuard/scripts/raw/main/pasarguard.sh -o /tmp/pg.sh \
  && sudo bash /tmp/pg.sh install --database mariadb
```
If you use PG-Node on this server too, install it as well:
```bash
sudo bash -c "$(curl -fsSL https://github.com/PasarGuard/scripts/raw/main/pg-node.sh)" @ install
```
Check that Docker works:
```bash
docker ps
```

#### Step 2: Allow root login on the NEW server
The script connects with **root + password**. In `/etc/ssh/sshd_config` make sure these are set, then restart SSH:
```
PermitRootLogin yes
PasswordAuthentication yes
```
```bash
systemctl restart ssh
```
You can turn these off again after the migration.

#### Step 3: Do a TEST run first
On the **old** server, install and run the script (see Install above). Then:
1. Choose option **1** (the database is detected automatically).
2. Answer **n** to "Stop Pasarguard & PG-Node during backup?". Nothing goes down.
3. Enter the new server IP, SSH port and root password.

Open the panel on the new server by IP and check that admins, users, inbounds and settings are there. If the test is fine, you are safe to do the real one.

#### Step 4: The FINAL run
Same as the test, but this time:
1. "Stop Pasarguard & PG-Node during backup?" → **y**
2. "Keep them stopped after backup?" → **y**
3. Optionally send a copy to your Telegram bot (extra safety).
4. Enter the new server IP, SSH port and root password.

From this moment the old server is stopped on purpose, so no new data can be created there. Users stay disconnected until the DNS switch, so pick a quiet time. The script uploads the ZIP, restores the database and the files, and starts everything on the new server.

#### Step 5: Check the new server
```bash
docker ps
pasarguard logs
```
Log in to the panel and make sure users, traffic stats and nodes look right.

#### Step 6: Switch the domain
Change the **A record** of your domain to the new server IP. After DNS propagates:
- Users who connect through your **domain** (subscription link, configs) don't need to do anything. Their accounts, traffic and expiry dates live in the database, which was fully restored.
- Users whose configs use the **old IP** directly must update their subscription or config, because the IP changed.
- If you have separate node servers and their firewall only allows the old panel IP, add the **new** panel IP there.
- If the SSL certificate was issued on the old server, check it on the new one. If it doesn't work, reissue it once DNS points to the new server.

#### Step 7: Cleanup
- Delete the backup ZIP from the old server and from the Telegram chat.
- Turn off root password login on the new server and change the root password.
- Keep the old server (stopped) for a few days as a safety net. Don't delete it until everything is stable.

#### If something goes wrong
The old server is untouched, just stopped. Start it again and point the DNS back:
```bash
cd /opt/pasarguard && docker compose up -d
cd /opt/pg-node && docker compose up -d
```

---

### Manual restore (without the script)
Run as root. Replace `backup_XXXX.zip` with your file name.

```bash
# 1. stop everything
cd /opt/pg-node 2>/dev/null && docker compose down
cd /opt/pasarguard && docker compose down

# 2. clean the folders
rm -rf /opt/pasarguard /opt/pg-node /var/lib/pasarguard /var/lib/pg-node
mkdir -p /opt/pasarguard /opt/pg-node /var/lib/pasarguard /var/lib/pg-node

# 3. extract and put files in place
unzip -q -o /root/backup_XXXX.zip -d /opt/pasarguard
cd /opt/pasarguard
cp -a pasarguard_data/. /var/lib/pasarguard/
cp -a pg_node_opt/. /opt/pg-node/
cp -a pg_node_data/. /var/lib/pg-node/
rm -rf pasarguard_data pg_node_opt pg_node_data
```

TimescaleDB:
```bash
cd /opt/pasarguard
docker compose up -d timescaledb
sleep 15
docker compose exec -T timescaledb psql -U pasarguard -d postgres -c "DROP DATABASE IF EXISTS pasarguard WITH (FORCE);"
docker compose exec -T timescaledb psql -U pasarguard -d postgres -c "CREATE DATABASE pasarguard;"
cat pg_dump/globals.sql | docker compose exec -T timescaledb psql -U pasarguard
cat pg_dump/db-001.sql | docker compose exec -T timescaledb psql -U pasarguard -d pasarguard
```

MySQL:
```bash
cd /opt/pasarguard
docker compose up -d mysql
docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS pasarguard; CREATE DATABASE pasarguard;"'
cat pg_dump/db_backup.sql | docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" pasarguard'
```
MariaDB: same as MySQL, but the service is called `mariadb` and the client is `mariadb` (newer images do not have the `mysql` command). If the password variable is empty inside the container, use the value of `MYSQL_ROOT_PASSWORD` (or `MARIADB_ROOT_PASSWORD`) from `.env`:
```bash
cd /opt/pasarguard
docker compose up -d mariadb
docker compose exec -T mariadb sh -c 'mariadb -uroot -p"${MYSQL_ROOT_PASSWORD:-$MARIADB_ROOT_PASSWORD}" -e "DROP DATABASE IF EXISTS pasarguard; CREATE DATABASE pasarguard;"'
cat pg_dump/db_backup.sql | docker compose exec -T mariadb sh -c 'mariadb -uroot -p"${MYSQL_ROOT_PASSWORD:-$MARIADB_ROOT_PASSWORD}" pasarguard'
```

Start everything:
```bash
docker compose up -d
cd /opt/pg-node && docker compose up -d
docker ps
```

---

### ⚠️ Security notes
- The backup contains **sensitive data** (passwords, keys, users). Keep it private and delete it after use.
- Telegram backups are not encrypted. Use only a private bot and a private chat.
- Restore **deletes** the current data on the target server.
- The script does not verify the SSH host key of the new server. Use it only with servers you own.
- Change the root password of the new server after the migration.

---

<div dir="rtl">

## 🇮🇷 فارسی

### امکانات
- بکاپ کامل پاسارگاد و PG-Node (تنظیمات، دیتا و دیتابیس)
- پشتیبانی از **TimescaleDB (PostgreSQL)** و **MySQL** و **MariaDB** و **تشخیص خودکار دیتابیس** (بدون هیچ سؤالی)
- اگر خروجی گرفتن از دیتابیس خطا بدهد، بکاپ متوقف می‌شود تا بکاپ خالی نگیری
- انتقال یک‌مرحله‌ای به سرور جدید از طریق SSH
- **ربات تلگرام + زمان‌بندی روزانه:** انتخاب اینکه روزی چند بار و چه ساعتی بکاپ بفرستد، هم از ترمینال و هم از داخل ربات. کرون‌جاب خودکار ساخته و به‌روز می‌شود و روی سرور فقط آخرین بکاپ می‌ماند
- **تاریخ شمسی:** زمان‌بندی یک بکاپ تک‌باره در تاریخ و ساعت دقیق شمسی از داخل ربات
- **ارسال فایل تا ۲ گیگابایت** (با سرور محلی Bot API، اختیاری) به جای محدودیت ۵۰ مگابایتی ربات‌های تلگرام
- **آپدیت با یک گزینه** از گیتهاب (گزینه ۵ منو یا `teperbk --update`)
- **ابزارهای جامع (گزینه ۶):** هر پنج دیتابیس (SQLite، PostgreSQL، TimescaleDB، MySQL، MariaDB)، ریستور بکاپ‌های رسمی پاسارگاد (حتی تکه‌تکه) و تبدیل نوع دیتابیس با ابزار رسمی مهاجرت پاسارگاد
- **بکاپ زمان‌بندی‌شده امن‌تر:** بررسی هر بکاپ، تعداد قابل‌تنظیم بکاپ نگه‌داشته‌شده، پراکسی اختیاری HTTP/SOCKS5 برای تلگرام، چک فضای دیسک و تلاش مجدد خودکار با فاصله رو به افزایش بعد از خطا
- بکاپ و ریستور دستی (لوکال)
- **حالت تست / نهایی:** انتخاب اینکه سرویس‌ها حین بکاپ خاموش بشن یا نه

### پیش‌نیازها
- سرور Ubuntu / Debian با دسترسی **root**
- Docker و Docker Compose
- پاسارگاد نصب‌شده در `/opt/pasarguard` (و PG-Node در `/opt/pg-node`، اختیاری)
- برای انتقال: پاسارگاد روی سرور جدید نصب باشه و ورود root با پسورد فعال باشه

### نصب
</div>

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/jyavaz68/teperbk/main/install.sh)"
```

<div dir="rtl">

### اجرای مجدد
بعد از نصب، ابزار به‌صورت یک دستور از هر مسیری در دسترس است:
</div>

```bash
teperbk
```

<div dir="rtl">

- اسکریپت در مسیر `/opt/teperbk/teperbk.py` نصب می‌شود.
- فایل‌های زیپ بکاپ در `/root` ذخیره می‌شوند (نه داخل `/opt/pasarguard`، چون ریستور آن پوشه را پاک می‌کند).
- برای آپدیت به آخرین نسخه، فقط دستور نصب را دوباره اجرا کن.


### منو
| # | گزینه | توضیح |
|---|-------|-------|
| ۱ | بکاپ و انتقال خودکار | بکاپ، ارسال اختیاری به تلگرام و ریستور روی سرور جدید با SSH |
| ۲ | بکاپ دستی | ذخیره زیپ بکاپ در پوشه فعلی |
| ۳ | ریستور دستی | ریستور از زیپ لوکال (تنظیمات فعلی پاک می‌شود) |
| ۴ | **ربات تلگرام و زمان‌بندی روزانه** | بکاپ دائمی روزانه با کرون‌جاب + رباتی که از تلگرام کنترلش می‌کنی (پیشنهادی) |
| ۵ | **آپدیت** | دانلود آخرین نسخه از گیتهاب |
| ۶ | **ابزارهای جامع** | همه دیتابیس‌ها، بکاپ‌های رسمی پاسارگاد، تبدیل دیتابیس |
| ۷ | خروج | |

نوع دیتابیس **خودکار تشخیص داده می‌شود**: برای بکاپ از سرویس‌های `/opt/pasarguard/docker-compose.yml` و برای ریستور از محتوای فایل ZIP. گزینه‌های ۱ تا ۳ با TimescaleDB، MySQL و MariaDB کار می‌کنند. اگر پنل تو **SQLite یا PostgreSQL ساده** باشد، می‌گویند از گزینه ۶ (ابزارهای جامع) استفاده کن؛ بکاپ زمان‌بندی‌شده تلگرام (گزینه ۴) این دو را خودکار پوشش می‌دهد.

### حالت بکاپ (گزینه‌های ۱ و ۲)
اسکریپت می‌پرسد: *Stop Pasarguard & PG-Node during backup?*
- **n (تست):** هیچ‌چیز خاموش نمی‌شود و قطعی ندارد. ممکن است داده حین بکاپ تغییر کند.
- **y (نهایی):** اپ و نود خاموش می‌شوند (دیتابیس برای دامپ روشن می‌ماند) تا هیچ داده‌ای تغییر نکند. می‌توانی انتخاب کنی بعد از بکاپ هم خاموش بمانند، که برای انتقال همین را می‌خواهی.

بکاپ زمان‌بندی‌شده تلگرام (گزینه ۴) هیچ‌وقت چیزی را خاموش نمی‌کند.

### داخل بکاپ چیست
`docker-compose.yml`، `.env`، دامپ دیتابیس، `/var/lib/pasarguard`، `/opt/pg-node` و `/var/lib/pg-node`.

---

### ربات تلگرام و بکاپ روزانه زمان‌بندی‌شده (گزینه ۴)

این حالت «یک بار تنظیم کن و فراموشش کن» است. دقیقاً همان بکاپ کامل انتقال را می‌گیرد (همان فرمت زیپ، پس روی سرور جدید هم ریستور می‌شود)، برایت در تلگرام می‌فرستد و روی سرور فقط **آخرین** نسخه را نگه می‌دارد.

#### راه‌اندازی
۱. با [@BotFather](https://t.me/BotFather) یک ربات بساز و توکنش را کپی کن.
۲. ربات جدیدت را در تلگرام باز کن و **START** را بزن (تا این کار را نکنی ربات نمی‌تواند به تو پیام بدهد).
۳. آیدی عددی خودت را از [@userinfobot](https://t.me/userinfobot) بگیر. آیدی **حساب خودت** را بده، نه گروه.
۴. `teperbk` را اجرا کن، گزینه **۴** و بعد **۱** را بزن و توکن، آیدی، زبان ربات، منطقه زمانی (پیش‌فرض `Asia/Tehran`) و ساعت‌های روزانه را وارد کن، مثلاً `03:00, 15:00` (روزی دو بار).

بعد از آن اسکریپت خودش این کارها را انجام می‌دهد:
- ساخت کرون‌جاب در `/etc/cron.d/teperbk`
- نصب و اجرای یک سرویس کوچک systemd (`teperbk-bot`) تا همه‌چیز را از تلگرام کنترل کنی
- ارسال یک پیام تست با منوی ربات برایت

#### کنترل از داخل تلگرام
فقط آیدی ادمین می‌تواند با ربات کار کند. بقیه نادیده گرفته می‌شوند.

| دستور / دکمه | کار |
|--------------|-----|
| `/start` | باز کردن منو |
| 📦 بکاپ همین الان (`/backup`) | همین الان بکاپ می‌گیرد و می‌فرستد |
| 📊 وضعیت (`/status`) | ساعت‌ها، آخرین بکاپ، فایل روی سرور و وضعیت کرون |
| ⏰ زمان‌بندی (`/schedule`) | گزینه‌های آماده (۱، ۲، ۳ یا ۴ بار در روز) یا ساعت‌های روزانه دلخواه |
| 📅 بکاپ در تاریخ مشخص (`/once 1405/08/29 14:30`) | بکاپ در تاریخ و ساعت دقیق **شمسی** (یا میلادی) |
| 🗑 لغو بکاپ‌های تاریخ‌دار | همه بکاپ‌های تک‌باره در انتظار را پاک می‌کند |
| `/settz Asia/Tehran` | تغییر منطقه زمانی ساعت‌ها و تاریخ‌ها |
| `/settimes 03:00 15:30` | تنظیم مستقیم ساعت‌های روزانه |
| 🌐 زبان | تغییر بین فارسی و English |

وقتی زمان‌بندی را در ربات (یا از منوی ترمینال) عوض کنی، کرون‌جاب روی سرور خودکار دوباره نوشته می‌شود.

#### ایمنی بیشتر (از نسخه ۱.۲.۰)
- **بررسی بکاپ:** هر بکاپ جدید قبل از پذیرفتن خوانده و چک می‌شود: سالم بودن آرشیو (CRC)، وجود دامپ دیتابیس و خالی نبودنش، و نشانه پایان دامپ. بکاپی که رد شود پاک می‌شود و **بکاپ‌های قبلی دست‌نخورده می‌مانند**؛ پیام هم می‌گیری.
- **نگه‌داری N بکاپ:** آخرین ۱ تا ۳۰ بکاپ روی سرور می‌ماند (`/keep 3` در ربات یا `teperbk` ← ۴ ← ۸). پیش‌فرض ۱ است، مثل قبل.
- **چک دیسک:** اگر فضای خالی برای کپی موقت و آرشیو کافی نباشد، بکاپ انجام نمی‌شود و پیام می‌گیری.
- **تلاش مجدد با فاصله رو به افزایش:** بعد از خطا بعد از ۱۵ دقیقه، ۳۰ دقیقه، ۱ ساعت ... تا ۶ ساعت دوباره تلاش می‌کند. خطای اول و بعد هر خطای سوم و همین‌طور سالم شدن دوباره به تو اطلاع داده می‌شود. برای تلاش مجدد سرویس ربات باید روشن باشد.
- **پراکسی تلگرام:** `teperbk` ← ۴ ← ۸ ← ۲ آدرس‌هایی مثل `socks5://host:port`، `socks5://user:pass@host:port` یا `http://host:port` را می‌پذیرد. فقط برای سرور معمولی تلگرام استفاده می‌شود (نه سرور محلی ۲ گیگابایتی).
- **موتور بکاپ:** حالت `auto` (پیش‌فرض) برای TimescaleDB، MySQL و MariaDB بکاپ داخلی و برای SQLite و PostgreSQL بکاپ **رسمی** `pasarguard backup` را استفاده می‌کند. حالت `official` برای همه دیتابیس‌ها بکاپ رسمی می‌گیرد.

#### رفتار سیستم
- **بدون قطعی:** بکاپ زمان‌بندی‌شده هیچ‌وقت پاسارگاد و PG-Node را خاموش نمی‌کند.
- **فقط آخرین بکاپ روی سرور می‌ماند** (در `/opt/teperbk/backups`). نسخه‌های قدیمی فقط بعد از ساخته شدن موفق بکاپ جدید پاک می‌شوند، پس اگر یک اجرا خطا بدهد چیزی را از دست نمی‌دهی.
- **منطقه زمانی:** همه ساعت‌ها و تاریخ‌ها بر اساس منطقه زمانی انتخابی تو هستند (پیش‌فرض `Asia/Tehran`)، حتی اگر سرور در کشور دیگری باشد. اسکریپت ساعت‌ها را خودکار برای کرون تبدیل می‌کند و مرتب دوباره چک می‌کند (مثلاً بعد از تغییر ساعت تابستانی سرور).
- **تاریخ شمسی:** وقتی زبان ربات فارسی است، تاریخ‌ها در پیام‌ها شمسی نمایش داده می‌شوند. بکاپ تک‌باره فقط وقتی اجرا می‌شود که سرویس ربات در آن زمان روشن باشد. اگر بیشتر از ۳۰ دقیقه خاموش بوده باشد، آن بکاپ رد می‌شود و پیام می‌گیری.
- **بکاپ حجیم:** ربات معمولی تلگرام فقط تا ۵۰ مگابایت فایل می‌پذیرد، پس بکاپ بزرگ‌تر در بخش‌های ۴۵ مگابایتی ارسال می‌شود (با `cat backup_XXXX.zip.part* > backup_XXXX.zip` به هم وصلشان کن). برای ارسال یک فایل تا ۲ گیگابایت بخش *فایل حجیم* پایین را ببین.
- **جلوگیری از همپوشانی:** اگر بکاپی در حال اجراست، اجرای دوم رد می‌شود.
- **خطاها:** اگر بکاپ یا ارسال خطا بدهد، ربات برایت پیام می‌فرستد. جزئیات در `/var/log/teperbk.log` است (هفتگی چرخش می‌کند).
- **فایل‌ها:** تنظیمات (توکن ربات و ساعت‌ها) در `/opt/teperbk/config.json` با دسترسی `600` ذخیره می‌شود.
- **حذف کامل:** `teperbk` ← ۴ ← ۷، کرون‌جاب را پاک و سرویس ربات را متوقف می‌کند.

#### فایل حجیم تا ۲ گیگابایت (اختیاری)
انتخاب با خودت است: **بدون API** (پیش‌فرض، هیچ تنظیمی لازم نیست و بکاپ بزرگ در بخش‌های ۴۵ مگابایتی ارسال می‌شود) یا **با API** (یک فایل تا ۲ گیگابایت). اسکریپت موقع راه‌اندازی ربات این را از تو می‌پرسد و هر وقت خواستی از `teperbk` ← **۴** ← **۵** عوضش کنی.

ربات معمولی تلگرام فقط تا ۵۰ مگابایت آپلود می‌پذیرد. برای ارسال یک فایل تا ۲ گیگابایت، اسکریپت می‌تواند **سرور رسمی Telegram Bot API** را داخل یک کانتینر Docker روی سرورت اجرا کند (`aiogram/telegram-bot-api` و فقط روی `127.0.0.1:8081` در دسترس).

۱. از [my.telegram.org](https://my.telegram.org) ← *API development tools* یک `api_id` و `api_hash` بگیر.
۲. `teperbk` ← **۴** ← **۵** را بزن و آن‌ها را وارد کن. اسکریپت کانتینر را اجرا می‌کند، ربات را از سرور معمولی تلگرام خارج (logOut) می‌کند و به سرور محلی می‌برد.
۳. برای برگشت: همان گزینه منو آن را خاموش می‌کند. بعد از آن حدود **۱۰ دقیقه** طول می‌کشد تا ربات دوباره جواب بدهد (قانون تلگرام هنگام جابه‌جایی ربات بین سرورها).

نکته: ایمیج کانتینر یک ایمیج شخص ثالث از Docker Hub است و با توکن ربات کار می‌کند، پس فقط اگر اعتماد داری استفاده کن. این حالت اختیاری و پیش‌فرض خاموش است. اگر مشکلی پیش بیاید، حالت عادی ۵۰ مگابایتی با ارسال تکه‌تکه همچنان کار می‌کند.

---

### ابزارهای جامع (گزینه ۶)

این ابزارها از مستندات و ابزارهای رسمی پاسارگاد ([docs.pasarguard.org](https://docs.pasarguard.org)) پیروی می‌کنند و روش کار گزینه‌های ۱ تا ۵ را تغییر نمی‌دهند.

۱. **بکاپ همین الان (رسمی).** دستور `pasarguard backup` را اجرا می‌کند که برای SQLite، PostgreSQL، TimescaleDB، MySQL و MariaDB کار می‌کند. آرشیو بررسی می‌شود و یک کپی در `/opt/teperbk/backups` می‌ماند. می‌توانی همان لحظه برای ربات تلگرامت بفرستی.
۲. **ریستور بکاپ پاسارگاد.** برای آرشیوهایی که با `pasarguard backup` یا سرویس بکاپ تلگرامی خود پاسارگاد ساخته شده‌اند، هر نوع دیتابیس، **حتی بکاپ‌های تکه‌تکه (چندبخشی)**. آرشیوهای پیداشده (`/root`، پوشه فعلی، `/opt/pasarguard/backup` و `/opt/teperbk/backups`) را لیست می‌کند یا مسیر کامل می‌گیرد، `pasarguard restore <file> --check` را اجرا می‌کند و بعد با دستور رسمی ریستور می‌کند: اگر اینجا پنل نصب باشد حالت عادی و روی سرور جدید و تمیز حالت `--fresh`. برای تأیید باید `RESTORE` را تایپ کنی.
۳. **تبدیل نوع دیتابیس.** مثلاً MariaDB به TimescaleDB یا SQLite به PostgreSQL، با ابزار رسمی [db-migrations](https://github.com/PasarGuard/db-migrations). ویزارد:
   - داده را از آرشیو بکاپ (teperbk یا رسمی)، فایل یا دامپ دیتابیس یا آدرس دیتابیس زنده می‌گیرد؛
   - مقصد را از پنل نصب‌شده روی همین سرور (`.env`) یا از آدرسی که تایپ می‌کنی می‌خواند و در دسترس بودنش را چک می‌کند؛
   - سه بار تأیید می‌گیرد (بکاپ گرفته‌ای، نسخه یکی است و جدول‌ها ساخته شده‌اند، و تایپ `MIGRATE`)؛
   - ابزار رسمی را اجرا می‌کند. فایل دامپ PostgreSQL باید از منوی خود ابزار رسمی انتخاب شود، پس ویزارد جواب‌های دقیق را چاپ می‌کند.

   روند رسمی، خلاصه: از مبدأ بکاپ بگیر ← پاسارگاد را روی دیتابیس **مقصد** و با **همان نسخه برنامه** نصب کن و یک بار بالا بیاور (تا جدول‌ها ساخته شوند) ← تبدیل را اجرا کن ← کاربرها و تنظیمات را در پنل چک کن. دیتابیس مقصد قبل از کپی داده پاک می‌شود.
۴. **لینک‌های مستندات.**

پیش‌نیاز: دستور رسمی `pasarguard` (اسکریپت پیشنهاد می‌دهد با `install-script` نصبش کند) و برای تبدیل `git` و دسترسی به اینترنت (ابزار رسمی وابستگی‌هایش را خودش نصب می‌کند).

---

### آپدیت
`teperbk` ← **۵** را بزن (یا `teperbk --update`). اسکریپت آخرین `teperbk.py` را از گیتهاب دانلود می‌کند، معتبر بودنش را چک می‌کند، فایل قبلی را با نام `/opt/teperbk/teperbk.py.bak` نگه می‌دارد، نسخه جدید را نصب می‌کند و اگر سرویس ربات تلگرام نصب باشد ریستارتش می‌کند. تنظیمات تو دست‌نخورده می‌ماند.

---

### آموزش انتقال: از سرور قدیم به سرور جدید

مراحل را به ترتیب انجام بده.

#### مرحله ۰: قبل از شروع
- مقدار **TTL** رکورد A دامنه را روی ۶۰ تا ۳۰۰ ثانیه بگذار (اگر می‌شود یک روز زودتر). عوض کردن DNS بعداً خیلی سریع‌تر انجام می‌شود.
- یادداشت کن: نوع دیتابیس (TimescaleDB، MySQL یا MariaDB)، نسخه پاسارگاد و اینکه PG-Node داری یا نه.

#### مرحله ۱: آماده‌سازی سرور جدید (نصب خام، بدون دامنه)
روی سرور جدید یک پاسارگاد تمیز نصب کن با **همان نوع دیتابیس** سرور قدیم. دامنه و SSL تنظیم نکن و ادمین نساز. فقط نصبش کن و با IP سرور بالا بیاید. همه‌چیز بعداً با بکاپ جایگزین می‌شود.

TimescaleDB:
</div>

```bash
curl -fsSL https://github.com/PasarGuard/scripts/raw/main/pasarguard.sh -o /tmp/pg.sh \
  && sudo bash /tmp/pg.sh install --database timescaledb
```

<div dir="rtl">

MySQL:
</div>

```bash
curl -fsSL https://github.com/PasarGuard/scripts/raw/main/pasarguard.sh -o /tmp/pg.sh \
  && sudo bash /tmp/pg.sh install --database mysql
```

<div dir="rtl">

MariaDB:
</div>

```bash
curl -fsSL https://github.com/PasarGuard/scripts/raw/main/pasarguard.sh -o /tmp/pg.sh \
  && sudo bash /tmp/pg.sh install --database mariadb
```

<div dir="rtl">

اگر PG-Node هم روی همین سرور استفاده می‌کنی، آن را هم نصب کن:
</div>

```bash
sudo bash -c "$(curl -fsSL https://github.com/PasarGuard/scripts/raw/main/pg-node.sh)" @ install
```

<div dir="rtl">

با این دستور چک کن Docker درست کار می‌کند:
</div>

```bash
docker ps
```

<div dir="rtl">

#### مرحله ۲: باز کردن ورود root روی سرور جدید
اسکریپت با **root و پسورد** وصل می‌شود. در فایل `/etc/ssh/sshd_config` این دو مقدار را چک کن و بعد SSH را ری‌استارت کن:
</div>

```
PermitRootLogin yes
PasswordAuthentication yes
```
```bash
systemctl restart ssh
```

<div dir="rtl">

بعد از انتقال می‌توانی دوباره خاموششان کنی.

#### مرحله ۳: اول یک اجرای تست
روی سرور **قدیم** اسکریپت را نصب و اجرا کن (بخش نصب بالا). بعد:
۱. گزینه **۱** را بزن (دیتابیس خودکار تشخیص داده می‌شود).
۲. به سؤال «Stop Pasarguard & PG-Node during backup?» جواب **n** بده. هیچ‌چیز قطع نمی‌شود.
۳. IP سرور جدید، پورت SSH و پسورد root را وارد کن.

پنل سرور جدید را با IP باز کن و چک کن ادمین‌ها، کاربرها، اینباندها و تنظیمات آمده باشد. اگر تست درست بود، می‌توانی با خیال راحت اجرای اصلی را بزنی.

#### مرحله ۴: اجرای نهایی
مثل تست، ولی این بار:
۱. سؤال «Stop Pasarguard & PG-Node during backup?» → **y**
۲. سؤال «Keep them stopped after backup?» → **y**
۳. اگر خواستی یک نسخه هم به ربات تلگرام بفرست (برای اطمینان بیشتر).
۴. IP سرور جدید، پورت SSH و پسورد root را وارد کن.

از این لحظه سرور قدیم عمداً خاموش می‌ماند تا هیچ داده جدیدی آنجا ساخته نشود. تا وقتی DNS عوض نشده کاربرها قطع هستند، پس ساعت خلوت را انتخاب کن. اسکریپت زیپ را آپلود می‌کند، دیتابیس و فایل‌ها را ریستور می‌کند و همه‌چیز را روی سرور جدید بالا می‌آورد.

#### مرحله ۵: چک کردن سرور جدید
</div>

```bash
docker ps
pasarguard logs
```

<div dir="rtl">

وارد پنل شو و مطمئن شو کاربرها، آمار ترافیک و نودها درست هستند.

#### مرحله ۶: انتقال دامنه
**رکورد A** دامنه را روی IP سرور جدید بگذار. بعد از پخش شدن DNS:
- کاربرهایی که با **دامنه** وصل می‌شوند (لینک سابسکریپشن و کانفیگ‌ها) لازم نیست کاری انجام بدهند. اکانت، ترافیک و تاریخ انقضایشان داخل دیتابیس است که کامل ریستور شده.
- کاربرهایی که کانفیگشان مستقیم با **IP قدیم** ساخته شده، باید سابسکریپشن یا کانفیگ را آپدیت کنند، چون IP عوض شده.
- اگر سرورهای نود جدا داری و فایروالشان فقط IP قدیم پنل را قبول می‌کند، IP **جدید** پنل را آنجا اضافه کن.
- اگر SSL دامنه روی سرور قدیم صادر شده بود، روی سرور جدید چکش کن. اگر گواهی کار نکرد، بعد از اینکه DNS به سرور جدید رسید دوباره صادرش کن.

#### مرحله ۷: تمیزکاری
- زیپ بکاپ را از سرور قدیم و چت تلگرام پاک کن.
- ورود root با پسورد را روی سرور جدید ببند و پسورد root را عوض کن.
- سرور قدیم را (خاموش) چند روز نگه دار تا مطمئن شوی همه‌چیز پایدار است. زود حذفش نکن.

#### اگر مشکلی پیش آمد
سرور قدیم دست‌نخورده است و فقط خاموش است. دوباره روشنش کن و DNS را برگردان:
</div>

```bash
cd /opt/pasarguard && docker compose up -d
cd /opt/pg-node && docker compose up -d
```

<div dir="rtl">

---

### ریستور دستی (بدون اسکریپت)
با root اجرا کن. به‌جای `backup_XXXX.zip` اسم فایل خودت را بگذار.
</div>

```bash
# 1. stop everything
cd /opt/pg-node 2>/dev/null && docker compose down
cd /opt/pasarguard && docker compose down

# 2. clean the folders
rm -rf /opt/pasarguard /opt/pg-node /var/lib/pasarguard /var/lib/pg-node
mkdir -p /opt/pasarguard /opt/pg-node /var/lib/pasarguard /var/lib/pg-node

# 3. extract and put files in place
unzip -q -o /root/backup_XXXX.zip -d /opt/pasarguard
cd /opt/pasarguard
cp -a pasarguard_data/. /var/lib/pasarguard/
cp -a pg_node_opt/. /opt/pg-node/
cp -a pg_node_data/. /var/lib/pg-node/
rm -rf pasarguard_data pg_node_opt pg_node_data
```

<div dir="rtl">

TimescaleDB:
</div>

```bash
cd /opt/pasarguard
docker compose up -d timescaledb
sleep 15
docker compose exec -T timescaledb psql -U pasarguard -d postgres -c "DROP DATABASE IF EXISTS pasarguard WITH (FORCE);"
docker compose exec -T timescaledb psql -U pasarguard -d postgres -c "CREATE DATABASE pasarguard;"
cat pg_dump/globals.sql | docker compose exec -T timescaledb psql -U pasarguard
cat pg_dump/db-001.sql | docker compose exec -T timescaledb psql -U pasarguard -d pasarguard
```

<div dir="rtl">

MySQL:
</div>

```bash
cd /opt/pasarguard
docker compose up -d mysql
docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS pasarguard; CREATE DATABASE pasarguard;"'
cat pg_dump/db_backup.sql | docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" pasarguard'
```

<div dir="rtl">

MariaDB (مثل MySQL است، فقط اسم سرویس `mariadb` است و کلاینت `mariadb` است، چون ایمیج‌های جدید دستور `mysql` ندارند):
</div>

```bash
cd /opt/pasarguard
docker compose up -d mariadb
docker compose exec -T mariadb sh -c 'mariadb -uroot -p"${MYSQL_ROOT_PASSWORD:-$MARIADB_ROOT_PASSWORD}" -e "DROP DATABASE IF EXISTS pasarguard; CREATE DATABASE pasarguard;"'
cat pg_dump/db_backup.sql | docker compose exec -T mariadb sh -c 'mariadb -uroot -p"${MYSQL_ROOT_PASSWORD:-$MARIADB_ROOT_PASSWORD}" pasarguard'
```

<div dir="rtl">

بالا آوردن همه‌چیز:
</div>

```bash
docker compose up -d
cd /opt/pg-node && docker compose up -d
docker ps
```

<div dir="rtl">

---

### ⚠️ نکات امنیتی
- بکاپ شامل **اطلاعات حساس** است (رمزها، کلیدها، کاربران). آن را خصوصی نگه دار و بعد از استفاده پاک کن.
- بکاپ‌های تلگرام رمزنگاری نمی‌شوند. فقط از ربات و چت خصوصی استفاده کن.
- ریستور، داده‌های فعلی سرور مقصد را **پاک می‌کند**.
- اسکریپت هویت (host key) سرور جدید را در SSH بررسی نمی‌کند. فقط برای سرورهای خودت استفاده کن.
- بعد از انتقال، پسورد root سرور جدید را عوض کن.

</div>

---

Dev by: [jyavaz](https://github.com/jyavaz68/)
