# Telegram Digital Shop Bot

Демонстрационный Telegram-магазин на Python, aiogram и SQLite. Администратор добавляет товары, шаблоны и файлы для выдачи. Покупатель открывает каталог, проходит учебную оплату и получает файл. Отдельный сценарий показывает, как администратор проверяет учебный чек.

## Демо за несколько минут

Нужны Python 3.11+, токен отдельного демо-бота от @BotFather и числовой Telegram ID администратора.

```powershell
git clone https://github.com/crygreen/telegram-digital-shop.git
cd telegram-digital-shop
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
.\.venv\Scripts\python main.py
```

Заполните `BOT_TOKEN` и `ADMIN_ID`, оставьте `STARS_MODE=demo`. Запускайте только один экземпляр на токен.

1. Откройте бота, отправьте `/start`, затем `/admin`. Добавьте товар с учебным фото-превью, ценами и файлом для выдачи. Поддерживаются фото, видео, кружочек и документ. Для готового набора можно приложить один ZIP.
2. Откройте «Каталог», выберите товар, оплату Stars и кнопку имитации оплаты. Бот сохраняет заказ, затем выдаёт файл.
3. Для второго сценария выберите «Демо с чеком» и приложите учебное фото или PDF без личных данных. Администратор увидит заявку в `/admin` → «Заявки на проверку» и сможет одобрить или отклонить её.
4. Проверьте `/price` и `/paysupport`. Администратор может ответить покупателю через «Ответить» на пересланное ботом текстовое сообщение. После ошибки выдачи Stars администратор, сверив доставку, может повторить её командой `/retry_stars <номер_заказа>`.

Для проверки настоящего протокола Stars используйте [отдельную тестовую среду Telegram](https://core.telegram.org/bots/payments-stars#testing-payments). Создайте бота и получите тестовый токен в ней, укажите тестовый `ADMIN_ID`, задайте `STARS_MODE=telegram_test` и используйте отдельную SQLite через `DB_PATH`. Загрузите учебные файлы заново в тестового бота. Счёт создаётся только в тестовой среде Telegram.

### Свой прайс

Готовый пример — `price-list.example.json`. Скопируйте его в `private/price-list.json`, измените позиции и перезапустите бота. Ключ `type` может быть `from` для стартовой цены или `addon` для доплаты. Через `PRICE_LIST_PATH` можно указать другой локальный JSON. Бот покажет цены в меню «Прайс». Позиции с персональной подготовкой и услуги согласуются через чат. Кнопка покупки появляется в каталоге для товаров, которым администратор назначил файл выдачи.

`private/`, `.env`, SQLite и резервные копии исключены из Git. Docker собирает образ только из разрешённых исходников и обезличенного примера. Перед публичной демонстрацией используйте учебные изображения, документы и цены.

## Запуск на обычном Linux VPS

Подойдёт VPS с SSH, Linux и исходящим доступом к Telegram по HTTPS. Бот получает обновления через polling, поэтому для него не нужны домен, публичный HTTP-порт, отдельный сервер базы данных или веб-сервер. Для малой машины удобен вариант с systemd. Оплачиваемый тариф и доступность Telegram проверьте у хостинга до покупки.

### Вариант 1. Python и systemd

Для Debian 12 или Ubuntu 24.04 подключитесь как пользователь с `sudo`. Скачайте репозиторий и установите зависимости:

```bash
ssh USER@SERVER_IP
sudo apt update
sudo apt install -y git python3 python3-venv sqlite3
sudo useradd --system --user-group --no-create-home --shell /usr/sbin/nologin shopbot
sudo git clone https://github.com/crygreen/telegram-digital-shop.git /opt/shopbot
cd /opt/shopbot
sudo python3 -m venv .venv
sudo .venv/bin/python -m pip install -r requirements.txt
sudo install -o root -g shopbot -m 0640 .env.example .env
sudoedit .env
```

Заполните токен и ID, сохраните `STARS_MODE=demo`. Если нужен собственный каталог, передайте JSON с компьютера, где он хранится:

```powershell
scp private/price-list.json USER@SERVER_IP:price-list.json
```

На VPS разместите полученный файл в читаемой для сервиса папке:

```bash
sudo install -d -o root -g shopbot -m 0750 /opt/shopbot/private
sudo install -o root -g shopbot -m 0640 ~/price-list.json /opt/shopbot/private/price-list.json
```

Запустите службу:

```bash
sudo install -m 0644 deploy/shopbot.service /etc/systemd/system/shopbot.service
sudo systemctl daemon-reload
sudo systemctl enable --now shopbot
sudo systemctl status shopbot --no-pager
sudo journalctl -u shopbot -n 50 --no-pager
```

Откройте `/start` в Telegram. Служба перезапускается после сбоя и включается после перезагрузки VPS. База находится в `/var/lib/shopbot/shop_bot.db`.

Для ручного перезапуска после изменения `.env` или прайса: `sudo systemctl restart shopbot`. Для остановки: `sudo systemctl stop shopbot`.

**Резервная копия и обновление** из `/opt/shopbot`:

```bash
sudo install -d -m 0700 /var/backups/shopbot
sudo sqlite3 /var/lib/shopbot/shop_bot.db ".backup /var/backups/shopbot/shop-$(date +%F-%H%M).db"
sudo git pull --ff-only
sudo .venv/bin/python -m pip install -r requirements.txt
sudo install -m 0644 deploy/shopbot.service /etc/systemd/system/shopbot.service
sudo systemctl daemon-reload
sudo systemctl restart shopbot
sudo journalctl -u shopbot -n 30 --no-pager
```

Чтобы восстановить базу, остановите службу, проверьте копию командой `sqlite3 ПУТЬ_К_КОПИИ 'PRAGMA quick_check;'` (при необходимости через `sudo`), затем восстановите её через `sudo -u shopbot sqlite3 /var/lib/shopbot/shop_bot.db ".restore /ПУТЬ/К/КОПИИ"` из файла, доступного пользователю `shopbot`. Запустите службу. Храните резервные копии и конфигурацию приватно.

### Вариант 2. Docker Compose

Установите [Docker Engine и плагин Compose](https://docs.docker.com/engine/install/ubuntu/#install-using-the-apt-repository). В каталоге клона:

```bash
cp .env.example .env
chmod 600 .env
nano .env
sudo docker compose up -d --build
sudo docker compose logs --tail=50 shopbot
```

Для собственного прайса контейнер читает папку `./private` в режиме только чтения. Можно поставить файл через `sudo install -d -o 10001 -g 10001 -m 0700 private` и `sudo install -o 10001 -g 10001 -m 0600 ~/price-list.json private/price-list.json`, затем перезапустить контейнер. SQLite остаётся в томе `shop-data` при обычном обновлении.

Резервная копия через SQLite Backup API:

```bash
umask 077
mkdir -p backups
sudo docker compose exec -T shopbot python -c 'import sqlite3, sys; from pathlib import Path; src = sqlite3.connect("/data/shop_bot.db"); dst = sqlite3.connect("/tmp/shopbot-backup.db"); src.backup(dst); dst.close(); src.close(); path = Path("/tmp/shopbot-backup.db"); sys.stdout.buffer.write(path.read_bytes()); path.unlink()' > "backups/shop-$(date +%F-%H%M).db"
```

Обновление: `git pull --ff-only`, `sudo docker compose up -d --build`, затем проверьте логи. Для остановки используйте `sudo docker compose down`. Параметр `-v` удаляет том с базой.

## Автоматические проверки

```bash
python -m unittest discover -s tests -v
```

Тесты используют временную SQLite и подменяют запросы Telegram. Проверка через живой тестовый бот описана в разделе «Демо за несколько минут».
