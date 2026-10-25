# teperbk

Backup, restore & server migration tool for **PasarGuard** and **PG-Node**.
ابزار بکاپ، ریستور و انتقال سرور برای **پاسارگاد** و **PG-Node**.

[English](#-english) | [فارسی](#-فارسی)

---

## 🇬🇧 English

### Features
- Full backup of PasarGuard + PG-Node (config, data, database)
- Supports **TimescaleDB (PostgreSQL)** and **MySQL**, and **detects your database automatically** (no questions asked)
- Aborts the backup if the database export fails, so you never end up with an empty backup
- One-step migration to a new server over SSH
- Scheduled automatic backups sent to a Telegram bot
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
```bash
python3 teperbk.py
```

### Menu
| # | Option | Description |
|---|--------|-------------|
| 1 | Auto Backup & Transfer | Backup, optional Telegram send, then restore on a new server via SSH |
| 2 | Auto Backup to Telegram | Scheduled backups every X hours (never stops services) |
| 3 | Manual Backup | Save the backup ZIP in the current directory |
| 4 | Manual Restore | Restore from a local ZIP (wipes the current setup) |
| 5 | Exit | |

The database type is **detected automatically**: for backups it reads the services in `/opt/pasarguard/docker-compose.yml`, and for restore it reads the content of the ZIP file. If your panel uses something else (SQLite, MariaDB, plain PostgreSQL), the script tells you it is unsupported and stops.

### Backup mode (options 1 and 3)
The script asks: *Stop Pasarguard & PG-Node during backup?*
- **n (test):** nothing is stopped, zero downtime. Data may change while the backup runs.
- **y (final):** the app and the node are stopped (the database stays up for the dump), so no data changes. You can also choose to keep them stopped after the backup, which is what you want for a migration.

Option 2 (scheduled Telegram backup) never stops anything.

### What is inside the backup
`docker-compose.yml`, `.env`, the database dump, `/var/lib/pasarguard`, `/opt/pg-node` and `/var/lib/pg-node`.

---

### Migration guide: old server → new server

Follow the steps in order.

#### Step 0: Before you start
- Lower the **TTL** of your domain's A record to 60-300 seconds (a day earlier if possible). The DNS switch will be much faster.
- Note down: your database type (TimescaleDB or MySQL), your PasarGuard version, and whether you use PG-Node.

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
- پشتیبانی از **TimescaleDB (PostgreSQL)** و **MySQL** و **تشخیص خودکار دیتابیس** (بدون هیچ سؤالی)
- اگر خروجی گرفتن از دیتابیس خطا بدهد، بکاپ متوقف می‌شود تا بکاپ خالی نگیری
- انتقال یک‌مرحله‌ای به سرور جدید از طریق SSH
- بکاپ خودکار زمان‌بندی‌شده و ارسال به ربات تلگرام
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
</div>

```bash
python3 teperbk.py
```

<div dir="rtl">

### منو
| # | گزینه | توضیح |
|---|-------|-------|
| ۱ | بکاپ و انتقال خودکار | بکاپ، ارسال اختیاری به تلگرام و ریستور روی سرور جدید با SSH |
| ۲ | بکاپ خودکار به تلگرام | بکاپ هر چند ساعت یک‌بار (هرگز سرویس‌ها را خاموش نمی‌کند) |
| ۳ | بکاپ دستی | ذخیره زیپ بکاپ در پوشه فعلی |
| ۴ | ریستور دستی | ریستور از زیپ لوکال (تنظیمات فعلی پاک می‌شود) |
| ۵ | خروج | |

نوع دیتابیس **خودکار تشخیص داده می‌شود**: برای بکاپ از سرویس‌های `/opt/pasarguard/docker-compose.yml` و برای ریستور از محتوای فایل ZIP. اگر پنل تو از چیز دیگری استفاده می‌کند (SQLite، MariaDB یا PostgreSQL ساده)، اسکریپت می‌گوید پشتیبانی نمی‌شود و متوقف می‌شود.

### حالت بکاپ (گزینه‌های ۱ و ۳)
اسکریپت می‌پرسد: *Stop Pasarguard & PG-Node during backup?*
- **n (تست):** هیچ‌چیز خاموش نمی‌شود و قطعی ندارد. ممکن است داده حین بکاپ تغییر کند.
- **y (نهایی):** اپ و نود خاموش می‌شوند (دیتابیس برای دامپ روشن می‌ماند) تا هیچ داده‌ای تغییر نکند. می‌توانی انتخاب کنی بعد از بکاپ هم خاموش بمانند، که برای انتقال همین را می‌خواهی.

گزینه ۲ (بکاپ زمان‌بندی‌شده تلگرام) هیچ‌وقت چیزی را خاموش نمی‌کند.

### داخل بکاپ چیست
`docker-compose.yml`، `.env`، دامپ دیتابیس، `/var/lib/pasarguard`، `/opt/pg-node` و `/var/lib/pg-node`.

---

### آموزش انتقال: از سرور قدیم به سرور جدید

مراحل را به ترتیب انجام بده.

#### مرحله ۰: قبل از شروع
- مقدار **TTL** رکورد A دامنه را روی ۶۰ تا ۳۰۰ ثانیه بگذار (اگر می‌شود یک روز زودتر). عوض کردن DNS بعداً خیلی سریع‌تر انجام می‌شود.
- یادداشت کن: نوع دیتابیس (TimescaleDB یا MySQL)، نسخه پاسارگاد و اینکه PG-Node داری یا نه.

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
