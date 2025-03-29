import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from config import TOKEN
from datetime import datetime, date
import os

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Створюємо директорію для зберігання даних користувачів, якщо вона не існує
if not os.path.exists("user_data"):
    os.makedirs("user_data")

def get_user_file_path(user_id):
    """Повертає шлях до файлу даних конкретного користувача"""
    return f"user_data/user_{user_id}.txt"

# Словник для зберігання даних користувачів
user_data = {}

# Стан очікування номера для видалення
AWAITING_DELETE_NUMBER = 0
AWAITING_NAME = "AWAITING_NAME"
AWAITING_DATE = "AWAITING_DATE"

# Стани розмови
NAME, DAY, MONTH, YEAR = range(4)

# Оновлюємо кнопки меню
def get_menu_keyboard():
    keyboard = [
        [KeyboardButton("Додати дату")],
        [KeyboardButton("Показати дати")],
        [KeyboardButton("Найближчий день народження")],
        [KeyboardButton("Видалити дату")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Команда старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    # Створення клавіатури меню
    reply_markup = get_menu_keyboard()
    
    await update.message.reply_text(
        f"Привіт, {user.mention_html()}! Використовуйте кнопки меню для взаємодії з ботом.",
        parse_mode="HTML",
        reply_markup=reply_markup
    )

# Обробка повідомлень користувачів
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка текстових повідомлень"""
    message = update.message
    text = message.text

    if text == "Додати дату":
        return await add_birthday_start(update, context)
    elif text == "Показати дати":
        await show_dates(update, context)
    elif text == "Найближчий день народження":
        await get_nearest_birthday(update, context)
    elif text == "Видалити дату":
        return await delete_birthday_start(update, context)
    else:
        await message.reply_text(
            "Будь ласка, використовуйте кнопки меню для взаємодії з ботом.",
            reply_markup=get_menu_keyboard()
        )

# Оновлена функція для пагінації
async def show_dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user_file = get_user_file_path(user_id)
    
    try:
        if not os.path.exists(user_file):
            await update.message.reply_text("У вас поки немає збережених дат.", reply_markup=get_menu_keyboard())
            return

        with open(user_file, "r", encoding="utf-8") as file:
            data = file.readlines()
        
        # Отримуємо поточну сторінку з user_data або встановлюємо 1 за замовчуванням
        current_page = context.user_data.get('current_page', 1)
        
        # Розрахунок індексів для поточної сторінки
        items_per_page = 10
        start_index = (current_page - 1) * items_per_page
        end_index = min(start_index + items_per_page, len(data))
        
        # Отримання даних для поточної сторінки
        page_data = data[start_index:end_index] if data else []
        
        # Форматування даних з HTML тегами
        if page_data:
            numbered_data = '\n'.join([
                f"<b>{start_index + i + 1}.</b> <code>{line.strip()}</code>" 
                for i, line in enumerate(page_data)
            ])
        else:
            numbered_data = "<i>Немає записів на цій сторінці</i>"
        
        # Створення кнопок пагінації (10 сторінок)
        keyboard = []
        row = []
        for page in range(1, 11):
            # Виділяємо поточну сторінку
            text = f"[{page}]" if page == current_page else str(page)
            row.append(InlineKeyboardButton(text, callback_data=f"page_{page}"))
            # Розбиваємо кнопки на ряди по 5
            if len(row) == 5:
                keyboard.append(row)
                row = []
        if row:  # Додаємо останній ряд, якщо він є
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Відправка повідомлення з HTML форматуванням
        message_text = f"📋 <b>Сторінка {current_page}</b>\n\n{numbered_data}"
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
    except FileNotFoundError:
        # Якщо файл не існує, все одно показуємо сторінки
        keyboard = []
        row = []
        current_page = context.user_data.get('current_page', 1)
        for page in range(1, 11):
            text = f"[{page}]" if page == current_page else str(page)
            row.append(InlineKeyboardButton(text, callback_data=f"page_{page}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = f"📋 <b>Немає збережених даних</b>\n\n<i>Сторінка {current_page}</i>"
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    except Exception as e:
        logger.error(f"Помилка при відображенні даних: {str(e)}")
        await update.message.reply_text(
            f"❌ <b>Сталася помилка при відображенні даних:</b>\n<code>{str(e)}</code>",
            parse_mode='HTML'
        )

# Оновлена функція для обробки натискання кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data.startswith("page_"):
            # Отримуємо номер сторінки з callback_data
            page = int(data.split("_")[1])
            context.user_data['current_page'] = page
            
            try:
                user_file = get_user_file_path(user_id)
                with open(user_file, "r", encoding="utf-8") as file:
                    data = file.readlines()
                
                # Розрахунок індексів для поточної сторінки
                items_per_page = 10
                start_index = (page - 1) * items_per_page
                end_index = min(start_index + items_per_page, len(data))
                
                # Отримання даних для поточної сторінки
                page_data = data[start_index:end_index] if data else []
                
                # Форматування даних з HTML тегами
                if page_data:
                    numbered_data = '\n'.join([
                        f"<b>{start_index + i + 1}.</b> <code>{line.strip()}</code>" 
                        for i, line in enumerate(page_data)
                    ])
                else:
                    numbered_data = "<i>Немає записів на цій сторінці</i>"
                
                # Створення кнопок пагінації
                keyboard = []
                row = []
                for p in range(1, 11):
                    text = f"[{p}]" if p == page else str(p)
                    row.append(InlineKeyboardButton(text, callback_data=f"page_{p}"))
                    # Розбиваємо кнопки на ряди по 5
                    if len(row) == 5:
                        keyboard.append(row)
                        row = []
                if row:
                    keyboard.append(row)
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                message_text = f"📋 <b>Сторінка {page}</b>\n\n{numbered_data}"
                
                # Оновлюємо повідомлення з HTML форматуванням
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                
            except FileNotFoundError:
                keyboard = []
                row = []
                for p in range(1, 11):
                    text = f"[{p}]" if p == page else str(p)
                    row.append(InlineKeyboardButton(text, callback_data=f"page_{p}"))
                    if len(row) == 5:
                        keyboard.append(row)
                        row = []
                if row:
                    keyboard.append(row)
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                message_text = f"📋 <b>Немає збережених даних</b>\n\n<i>Сторінка {page}</i>"
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            
    except Exception as e:
        logger.error(f"Помилка в button_handler: {str(e)}")
        await query.message.reply_text(
            f"❌ <b>Сталася помилка при обробці кнопки:</b>\n<code>{str(e)}</code>",
            parse_mode='HTML'
        )

# Функція для розрахунку найближчого дня народження
async def get_nearest_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user_file = get_user_file_path(user_id)
    
    try:
        if not os.path.exists(user_file):
            await update.message.reply_text("У вас поки немає збережених дат.", reply_markup=get_menu_keyboard())
            return

        with open(user_file, "r", encoding="utf-8") as file:
            dates = file.readlines()
        
        if not dates:
            await update.message.reply_text("У вас поки немає збережених дат.", reply_markup=get_menu_keyboard())
            return

        today = date.today()
        min_days = float('inf')
        nearest_birthdays = {}  # словник для зберігання {date: [names]}
        
        month_number = {
            'Січень': 1, 'Лютий': 2, 'Березень': 3, 'Квітень': 4,
            'Травень': 5, 'Червень': 6, 'Липень': 7, 'Серпень': 8,
            'Вересень': 9, 'Жовтень': 10, 'Листопад': 11, 'Грудень': 12
        }

        for line in dates:
            try:
                # Розбираємо рядок у форматі "Ім'я: день місяць рік"
                name, birthday = line.strip().split(': ')
                day, month, year = birthday.strip().split()
                
                # Конвертуємо місяць в число, якщо він текстовий
                if month in month_number:
                    month = month_number[month]
                else:
                    month = int(month)
                
                # Створюємо об'єкт дати
                birthday_date = date(today.year, int(month), int(day))
                
                # Якщо день народження вже пройшов цього року, додаємо рік
                if birthday_date < today:
                    birthday_date = date(today.year + 1, int(month), int(day))
                
                # Розраховуємо кількість днів до дня народження
                days_until = (birthday_date - today).days
                
                if days_until < min_days:
                    min_days = days_until
                    nearest_birthdays.clear()
                    nearest_birthdays[birthday_date] = [name]
                elif days_until == min_days:
                    if birthday_date not in nearest_birthdays:
                        nearest_birthdays[birthday_date] = []
                    nearest_birthdays[birthday_date].append(name)

            except (ValueError, IndexError) as e:
                logger.error(f"Помилка при обробці дати: {line.strip()} - {str(e)}")
                continue
        
        if nearest_birthdays:
            # Беремо першу дату (вони всі однакові, бо мають однакову кількість днів)
            nearest_date = list(nearest_birthdays.keys())[0]
            names = nearest_birthdays[nearest_date]
            
            # Форматуємо місяць для виводу
            month_names = {v: k for k, v in month_number.items()}
            month_name = month_names.get(nearest_date.month, str(nearest_date.month))
            
            # Форматуємо список імен
            if len(names) == 1:
                names_text = names[0]
            elif len(names) == 2:
                names_text = f"{names[0]} та {names[1]}"
            else:
                names_text = ", ".join(names[:-1]) + f" та {names[-1]}"
            
            # Визначаємо текст для днів
            if min_days == 0:
                message = (
                    f"🎉 <b>Сьогодні день народження у {names_text}!</b>\n"
                    f"🎂 Вітаємо з днем народження!"
                )
            elif min_days == 1:
                message = (
                    f"🎂 <b>Завтра день народження:</b>\n"
                    f"👥 {names_text}\n"
                    f"📅 {nearest_date.day} {month_name}"
                )
            else:
                days_word = "день" if min_days % 10 == 1 and min_days != 11 else "дні" if 2 <= min_days % 10 <= 4 and (min_days < 10 or min_days > 20) else "днів"
                message = (
                    f"🎂 <b>Найближчий день народження:</b>\n"
                    f"👥 {names_text}\n"
                    f"📅 {nearest_date.day} {month_name}\n"
                    f"⏰ через {min_days} {days_word}"
                )
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(
                "❌ <b>Не вдалося знайти найближчий день народження.</b>",
                parse_mode='HTML'
            )
            
    except Exception as e:
        logger.error(f"Помилка при пошуку найближчого дня народження: {str(e)}")
        await update.message.reply_text(
            "❌ <b>Сталася помилка при пошуку найближчого дня народження.</b>",
            parse_mode='HTML'
        )

async def add_birthday_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок розмови для додавання дня народження"""
    await update.message.reply_text(
        "👤 Будь ласка, введіть ім'я:",
        parse_mode='HTML'
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримуємо ім'я та запитуємо день"""
    name = update.message.text.strip()
    
    if not name:
        await update.message.reply_text("❌ Ім'я не може бути порожнім. Спробуйте ще раз:")
        return NAME
    
    context.user_data['name'] = name
    await update.message.reply_text(
        "📅 Введіть день (1-31):",
        parse_mode='HTML'
    )
    return DAY

async def get_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримуємо день та показуємо кнопки з місяцями"""
    try:
        day = int(update.message.text)
        if day < 1 or day > 31:
            await update.message.reply_text("❌ День має бути від 1 до 31. Спробуйте ще раз:")
            return DAY
        
        context.user_data['day'] = day
        
        # Створюємо клавіатуру з місяцями
        months = [
            ('Січень', 'Лютий', 'Березень'),
            ('Квітень', 'Травень', 'Червень'),
            ('Липень', 'Серпень', 'Вересень'),
            ('Жовтень', 'Листопад', 'Грудень')
        ]
        
        keyboard = []
        for row in months:
            keyboard_row = []
            for month in row:
                keyboard_row.append(InlineKeyboardButton(month, callback_data=month))
            keyboard.append(keyboard_row)
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📅 Виберіть місяць:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return MONTH
        
    except ValueError:
        await update.message.reply_text("❌ Будь ласка, введіть число від 1 до 31:")
        return DAY

async def get_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримуємо місяць та запитуємо рік"""
    query = update.callback_query
    await query.answer()
    
    month = query.data
    context.user_data['month'] = month
    
    await query.message.reply_text(
        "📅 Введіть рік (4 цифри):",
        parse_mode='HTML'
    )
    return YEAR

async def get_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_file = get_user_file_path(user_id)
    
    try:
        year = int(update.message.text)
        current_year = datetime.now().year
        
        if year < 1900 or year > current_year:
            await update.message.reply_text(
                f"Будь ласка, введіть рік між 1900 та {current_year}",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Скасувати")]], resize_keyboard=True)
            )
            return YEAR

        name = context.user_data['name']
        day = context.user_data['day']
        month = context.user_data['month']
        
        # Зберігаємо дані у файл користувача з пробілами замість крапок
        with open(user_file, "a", encoding="utf-8") as file:
            file.write(f"{name}: {day} {month} {year}\n")
        
        await update.message.reply_text(
            f"✅ День народження додано успішно:\n"
            f"👤 {name}\n"
            f"📅 {day} {month} {year}",
            parse_mode='HTML',
            reply_markup=get_menu_keyboard()
        )
        
        # Очищаємо дані користувача
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Будь ласка, введіть правильний рік (наприклад, 1990)",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Скасувати")]], resize_keyboard=True)
        )
        return YEAR

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасовує розмову"""
    await update.message.reply_text(
        "❌ Додавання дня народження скасовано.",
        parse_mode='HTML'
    )
    context.user_data.clear()
    return ConversationHandler.END

async def delete_birthday_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок процесу видалення дня народження"""
    message = update.message
    
    # Показуємо список дат перед видаленням
    user_id = message.from_user.id
    user_file = get_user_file_path(user_id)
    
    with open(user_file, "r", encoding="utf-8") as file:
        dates = file.readlines()
    
    if not dates:
        await message.reply_text("У вас немає збережених дат.", reply_markup=get_menu_keyboard())
        return ConversationHandler.END
    
    text = "🗑 <b>Виберіть номер дати для видалення:</b>\n\n"
    for i, date in enumerate(dates, 1):
        text += f"{i}. {date.strip()}\n"
    
    await message.reply_text(text, parse_mode='HTML')
    return AWAITING_DELETE_NUMBER

async def handle_delete_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка номера дати для видалення"""
    message = update.message
    text = message.text
    
    try:
        user_id = message.from_user.id
        user_file = get_user_file_path(user_id)
        
        if not os.path.exists(user_file):
            await update.message.reply_text(
                "У вас немає збережених дат для видалення.",
                reply_markup=get_menu_keyboard()
            )
            return ConversationHandler.END

        with open(user_file, "r", encoding="utf-8") as file:
            lines = file.readlines()
        
        try:
            number = int(update.message.text)
            if number < 1 or number > len(lines):
                await update.message.reply_text(
                    f"Будь ласка, введіть число від 1 до {len(lines)}",
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Скасувати")]], resize_keyboard=True)
                )
                return AWAITING_DELETE_NUMBER

            # Видаляємо вибраний рядок
            deleted_line = lines.pop(number - 1)
            
            # Перезаписуємо файл без видаленого рядка
            with open(user_file, "w", encoding="utf-8") as file:
                file.writelines(lines)
            
            await update.message.reply_text(
                f"✅ <b>Успішно видалено:</b>\n"
                f"<code>{deleted_line.strip()}</code>",
                parse_mode='HTML'
            )
            
            # Показуємо оновлений список
            if lines:
                text = "📅 <b>Оновлений список дат:</b>\n\n"
                for i, date in enumerate(lines, 1):
                    text += f"{i}. {date.strip()}\n"
                await update.message.reply_text(text, parse_mode='HTML')
            else:
                await update.message.reply_text("У вас немає збережених дат.", reply_markup=get_menu_keyboard())
            
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text(
                "Будь ласка, введіть числовий номер дати або натисніть /cancel для скасування.",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Скасувати")]], resize_keyboard=True)
            )
            return AWAITING_DELETE_NUMBER
            
    except Exception as e:
        logger.error(f"Помилка при видаленні даних: {str(e)}")
        await update.message.reply_text(
            f"❌ <b>Сталася помилка при видаленні даних:</b>\n<code>{str(e)}</code>",
            parse_mode='HTML'
        )
        return ConversationHandler.END

async def cancel_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасовує процес видалення"""
    await update.message.reply_text(
        "❌ Видалення скасовано.",
        parse_mode='HTML'
    )
    return ConversationHandler.END

# Основна функція для запуску бота
def main() -> None:
    application = Application.builder().token(TOKEN).build()

    # Створюємо обробник розмови для додавання дня народження
    add_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('add', add_birthday_start),
            MessageHandler(filters.Regex('^Додати дату$'), add_birthday_start)
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Показати дати$|^Найближчий день народження$|^Видалити дату$'), get_name)],
            DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Показати дати$|^Найближчий день народження$|^Видалити дату$'), get_day)],
            MONTH: [CallbackQueryHandler(get_month)],
            YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Показати дати$|^Найближчий день народження$|^Видалити дату$'), get_year)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(filters.Regex('^Показати дати$|^Найближчий день народження$|^Видалити дату$'), cancel)
        ],
    )

    # Створюємо обробник розмови для видалення дня народження
    delete_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('delete', delete_birthday_start),
            MessageHandler(filters.Regex('^Видалити дату$'), delete_birthday_start)
        ],
        states={
            AWAITING_DELETE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delete_number)],
        },
        fallbacks=[CommandHandler('cancel', cancel_delete)],
    )

    # Додаємо обробники в правильному порядку
    application.add_handler(CommandHandler("start", start))
    application.add_handler(add_conv_handler)
    application.add_handler(delete_conv_handler)
    
    # Обробка текстових повідомлень, які не є командами
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_message
    ))

    # Обробка натискання кнопок
    application.add_handler(CallbackQueryHandler(button_handler))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
