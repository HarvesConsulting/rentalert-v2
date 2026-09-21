"""Локалізація текстів бота (UK + EN).

Використання:
    from rentalert.translations import T
    T("btn_my_cities", "uk")  # → "📍 Мої міста"
    T("main_menu", "en", country="Poland")  # → підстановка
"""

from __future__ import annotations

from typing import Any

TEXTS: dict[str, dict[str, str]] = {
    # ═════════════════════════════════════════════════════════
    # УКРАЇНСЬКА
    # ═════════════════════════════════════════════════════════
    "uk": {
        # ─── Головне меню ───
        "main_menu": "🏠 <b>RentAlert</b>\n\nКраїна: <b>{country}</b>\n\nОберіть дію нижче 👇",
        "btn_my_cities": "📍 Мої міста",
        "btn_add_city": "➕ Додати місто",
        "btn_favorites": "📌 Обране",
        "btn_settings": "⚙️ Налаштування",
        "btn_help": "❓ Довідка",
        # ─── Кнопки ───
        "btn_yes": "Так",
        "btn_no": "Ні",
        "btn_save_categories": "💾 Зберегти",
        "btn_add_favorite": "В обране",
        "btn_remove_favorite": "Видалити з обраного",
        "btn_open": "🔗 Відкрити",
        "btn_ignore": "🚫 Ігнорувати",
        "btn_unignore": "↩️ Повернути",
        "btn_feedback": "💬 Зворотний зв'язок",
        "btn_rate": "⭐ Оцінити бота",
        "btn_country": "🌍 Країна: {country}",
        "btn_sources": "Джерела",
        "btn_types": "🏘 Тип житла",
        "btn_language": "🌍 Мова / Language",
        "btn_clear_cities": "🗑 Очистити всі міста",
        "btn_clear_favorites": "🗑 Очистити обране",
        # ─── Вибір країни ───
        "country_selector_title": "🌍 <b>Оберіть країну</b>\n\nВід цього залежить:\n• Мова інтерфейсу\n• Список локацій\n• Джерела оголошень\n• Валюта цін\n\n<i>Змінити можна в ⚙️ Налаштування.</i>",
        "country_ua": "🇺🇦 Україна",
        "country_pl": "🇵🇱 Польща",
        "country_pt": "🇵🇹 Португалія",
        "country_ro": "🇷🇴 Румунія",
        "country_bg": "🇧🇬 Болгарія",
        "country_de": "🇩🇪 Німеччина",
        "country_es": "🇪🇸 Іспанія",
        "country_hr": "🇭🇷 Хорватія",
        # ─── Мої міста ───
        "my_cities_title": "📍 <b>Мої міста</b> ({count}):",
        "my_cities_empty": "📍 <b>Мої міста</b>\n\nУ вас ще немає доданих міст.\n\nНатисніть <b>➕ Додати місто</b>, щоб почати.",
        # ─── Додавання міста ───
        "add_city_prompt": "🏢 <b>Додати місто</b>\n\nНапишіть назву (наприклад, <code>Київ</code>):\n\n<i>Підказка: можна писати частину назви.</i>",
        "city_search_results": "🔍 Знайдено {count} міст.\n\nНатисніть, щоб додати:",
        "error_short_query": "❓ <b>Занадто короткий запит.</b>\n\nВведіть мінімум 2 символи.",
        "error_city_not_found": "😕 Місто «{query}» не знайдено.\n\nСпробуйте іншу назву або змініть країну в ⚙️ Налаштуваннях.",
        # ─── Обране ───
        "favorites_title": "📌 <b>Обране</b> ({count}):",
        "favorites_empty": "📌 <b>Обране</b>\n\nТут поки що порожньо.\n\nКоли отримаєте оголошення — натисніть ⭐ <b>В обране</b>.",
        # ─── Налаштування ───
        "settings_title": "⚙️ <b>Налаштування</b>\n\nКраїна: <b>{country}</b>\n\nОберіть дію:",
        "language_title": "🌍 <b>Оберіть мову</b>\n\nПоточна: <b>{current}</b>",
        "language_changed": "✅ Мову змінено",
        # ─── Довідка ───
        "help_text": (
            "🏠 <b>RentAlert — бот</b>\n\n"
            "🎯 <b>Що робить бот?</b>\n"
            "Автоматично відстежує <b>нові оголошення</b> про оренду житла "
            "та надсилає їх у Telegram.\n\n"
            "🌍 <b>Країни:</b>\n"
            "• 🇺🇦 Україна (OLX.ua + DIM.RIA)\n"
            "• 🇵🇱 Польща (OLX.pl)\n"
            "• 🇵🇹 Португалія (OLX.pt)\n"
            "• 🇷🇴 Румунія (OLX.ro)\n"
            "• 🇧🇬 Болгарія (OLX.bg)\n"
            "• 🇩🇪 Німеччина (Kleinanzeigen)\n"
            "• 🇪🇸 Іспанія (Habitaclia)\n\n"
            "✅ <b>Переваги:</b>\n"
            "• ⚡ Нові оголошення кожні 2 хвилини\n"
            "• 🔔 Тільки нові — без спаму\n"
            "• 🎯 Фільтри за типом житла\n"
            "• 📱 Все в Telegram\n\n"
            "📋 <b>Як користуватись:</b>\n"
            "1️⃣ ⚙️ Налаштування → оберіть країну\n"
            "2️⃣ ➕ Додати місто → оберіть локацію\n"
            "3️⃣ Отримуйте сповіщення 🎉\n\n"
            "💬 <b>Зворотний зв'язок:</b>\n"
            "Питання, побажання, ідеї? Натисніть кнопку нижче 👇"
        ),
        "unknown_command": "❓ Невідома команда.\n\nОберіть дію нижче 👇",
        # ─── Feedback ───
        "feedback_prompt": "💬 <b>Зворотний зв'язок</b>\n\nНапишіть ваше повідомлення — побажання, питання, скаргу чи ідею.\n\n<i>Я отримаю його особисто та відповім.</i>",
        "feedback_thanks": "✅ <b>Дякую!</b>\n\nВаше повідомлення надіслано розробнику.",
        # ─── Ігноровані ───
        "ignored_title": "🚫 <b>Ігноровані</b> ({count}):",
        "ignored_empty": "🚫 <b>Ігноровані</b>\n\nТут порожньо.\n\nКоли отримаєте оголошення — натисніть <b>🚫 Ігнорувати</b>, і воно більше не приходитиме (навіть якщо продавець перевипустить його з новим ID).",
        "ignored_done": "✅ Більше не показуватиму це оголошення",
        "ignored_removed": "↩️ Оголошення повернено у стрічку",
        "ignored_cleared": "✅ Очищено {count} ігнорованих оголошень",
        "ignored_clear_confirm": "🗑 Очистити всі ігноровані?",
        "btn_clear_ignored": "🗑 Очистити ігноровані",
        "btn_ignored": "🚫 Ігноровані",
        "error_listing_not_found": "😕 Оголошення не знайдено",
        # ─── Сповіщення ───
        "notification_header": "🔔 <b>{city}</b> — нових оголошень: <b>{count}</b>",
        "notification_more": "…та ще <b>{count}</b> оголошень у наступному циклі.",
        # ─── Помилки ───
        "error_generic": "❌ Щось пішло не так. Спробуйте пізніше.",
        "error_max_cities": "⚠️ Достигнуто ліміт міст: {max}.",
    },
    # ═════════════════════════════════════════════════════════
    # ENGLISH
    # ═════════════════════════════════════════════════════════
    "en": {
        # ─── Main menu ───
        "main_menu": "🏠 <b>RentAlert</b>\n\nCountry: <b>{country}</b>\n\nChoose an action below 👇",
        "btn_my_cities": "📍 My Cities",
        "btn_add_city": "➕ Add City",
        "btn_favorites": "📌 Favorites",
        "btn_settings": "⚙️ Settings",
        "btn_help": "❓ Help",
        # ─── Buttons ───
        "btn_yes": "Yes",
        "btn_no": "No",
        "btn_save_categories": "💾 Save",
        "btn_add_favorite": "Add to favorites",
        "btn_remove_favorite": "Remove from favorites",
        "btn_open": "🔗 Open",
        "btn_ignore": "🚫 Ignore",
        "btn_unignore": "↩️ Return",
        "btn_feedback": "💬 Feedback",
        "btn_rate": "⭐ Rate bot",
        "btn_country": "🌍 Country: {country}",
        "btn_sources": "Sources",
        "btn_types": "🏘 Property type",
        "btn_language": "🌍 Language",
        "btn_clear_cities": "🗑 Clear all cities",
        "btn_clear_favorites": "🗑 Clear favorites",
        # ─── Country selector ───
        "country_selector_title": "🌍 <b>Choose a country</b>\n\nThis affects:\n• Interface language\n• Location list\n• Listing sources\n• Price currency\n\n<i>Change anytime in ⚙️ Settings.</i>",
        "country_ua": "🇺🇦 Ukraine",
        "country_pl": "🇵🇱 Poland",
        "country_pt": "🇵🇹 Portugal",
        "country_ro": "🇷🇴 Romania",
        "country_bg": "🇧🇬 Bulgaria",
        "country_de": "🇩🇪 Germany",
        "country_es": "🇪🇸 Spain",
        "country_hr": "🇭🇷 Croatia",
        # ─── My cities ───
        "my_cities_title": "📍 <b>My cities</b> ({count}):",
        "my_cities_empty": "📍 <b>My cities</b>\n\nYou haven't added any cities yet.\n\nTap <b>➕ Add City</b> to start.",
        # ─── Add city ───
        "add_city_prompt": "🏢 <b>Add City</b>\n\nType the name (e.g., <code>Warsaw</code>):\n\n<i>Tip: you can type part of the name.</i>",
        "city_search_results": "🔍 Found {count} cities.\n\nTap to add:",
        "error_short_query": "❓ <b>Query too short.</b>\n\nEnter at least 2 characters.",
        "error_city_not_found": "😕 City «{query}» not found.\n\nTry another name or change country in ⚙️ Settings.",
        # ─── Favorites ───
        "favorites_title": "📌 <b>Favorites</b> ({count}):",
        "favorites_empty": "📌 <b>Favorites</b>\n\nNothing here yet.\n\nWhen you receive listings — tap ⭐ <b>Add to favorites</b>.",
        # ─── Settings ───
        "settings_title": "⚙️ <b>Settings</b>\n\nCountry: <b>{country}</b>\n\nChoose an action:",
        "language_title": "🌍 <b>Choose language</b>\n\nCurrent: <b>{current}</b>",
        "language_changed": "✅ Language changed",
        # ─── Help ───
        "help_text": (
            "🏠 <b>RentAlert — Bot</b>\n\n"
            "🎯 <b>What does the bot do?</b>\n"
            "Automatically tracks <b>new rental listings</b> "
            "and sends them to Telegram.\n\n"
            "🌍 <b>Countries:</b>\n"
            "• 🇺🇦 Ukraine (OLX.ua + DIM.RIA)\n"
            "• 🇵🇱 Poland (OLX.pl)\n"
            "• 🇵🇹 Portugal (OLX.pt)\n"
            "• 🇷🇴 Romania (OLX.ro)\n"
            "• 🇧🇬 Bulgaria (OLX.bg)\n"
            "• 🇩🇪 Germany (Kleinanzeigen)\n"
            "• 🇪🇸 Spain (Habitaclia)\n\n"
            "✅ <b>Benefits:</b>\n"
            "• ⚡ New listings every 2 minutes\n"
            "• 🔔 Only new — no spam\n"
            "• 🎯 Property type filters\n"
            "• 📱 Everything in Telegram\n\n"
            "📋 <b>How to use:</b>\n"
            "1️⃣ ⚙️ Settings → choose country\n"
            "2️⃣ ➕ Add City → choose location\n"
            "3️⃣ Get notifications 🎉\n\n"
            "💬 <b>Feedback:</b>\n"
            "Questions, suggestions, ideas? Tap the button below 👇"
        ),
        "unknown_command": "❓ Unknown command.\n\nChoose an action below 👇",
        # ─── Feedback ───
        "feedback_prompt": "💬 <b>Feedback</b>\n\nType your message — suggestion, question, complaint, or idea.\n\n<i>I'll receive it personally and reply.</i>",
        "feedback_thanks": "✅ <b>Thanks!</b>\n\nYour message has been sent to the developer.",
        # ─── Ignored ───
        "ignored_title": "🚫 <b>Ignored</b> ({count}):",
        "ignored_empty": "🚫 <b>Ignored</b>\n\nNothing here yet.\n\nWhen you receive a listing — tap <b>🚫 Ignore</b> and it won't come back (even if the seller reposts it with a new ID).",
        "ignored_done": "✅ Won't show this listing again",
        "ignored_removed": "↩️ Listing returned to feed",
        "ignored_cleared": "✅ Cleared {count} ignored listings",
        "ignored_clear_confirm": "🗑 Clear all ignored?",
        "btn_clear_ignored": "🗑 Clear ignored",
        "btn_ignored": "🚫 Ignored",
        "error_listing_not_found": "😕 Listing not found",
        # ─── Notifications ───
        "notification_header": "🔔 <b>{city}</b> — new listings: <b>{count}</b>",
        "notification_more": "…and <b>{count}</b> more listings in the next cycle.",
        # ─── Errors ───
        "error_generic": "❌ Something went wrong. Try again later.",
        "error_max_cities": "⚠️ City limit reached: {max}.",
    },
}


def T(key: str, lang: str = "uk", **kwargs: Any) -> str:
    """Повертає локалізований текст за ключем.

    Args:
        key: ключ у TEXTS
        lang: 'uk' або 'en'
        **kwargs: підстановки для {name}

    Returns:
        Локалізований текст або сам ключ, якщо не знайдено.
    """
    texts = TEXTS.get(lang) or TEXTS["uk"]
    template = texts.get(key)

    if template is None:
        # Fallback на UK, потім — сам ключ
        template = TEXTS["uk"].get(key, key)

    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError:
            return template

    return template
