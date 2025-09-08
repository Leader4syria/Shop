import traceback
from telebot import types
from . import bot, user_states
from database import Session, User, Service
from utils import get_or_create_user
from utils import send_message_to_user
from config import START_MESSAGE, ADMIN_IDS, SUPPORT_CHANNEL_LINK
import config
from .keyboards import create_main_menu_inline_keyboard

from config import MANDATORY_CHANNEL_ID

@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        chat_id = message.chat.id
        telegram_id = message.from_user.id

        try:
            member = bot.get_chat_member(MANDATORY_CHANNEL_ID, telegram_id)
            if member.status not in ['creator', 'administrator', 'member']:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("اشتراك في القناة", url=f"https://t.me/{MANDATORY_CHANNEL_ID.lstrip('@')}"))
                markup.add(types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription"))
                bot.send_message(chat_id, "لاستخدام البوت، يرجى الاشتراك في قناتنا أولاً.", reply_markup=markup)
                return
        except Exception as e:
            if 'user not found' in str(e).lower():
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("اشتراك في القناة", url=f"https://t.me/{MANDATORY_CHANNEL_ID.lstrip('@')}"))
                markup.add(types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription"))
                bot.send_message(chat_id, "لم أتمكن من التحقق من اشتراكك. يرجى الاشتراك في القناة ثم الضغط على زر التحقق.", reply_markup=markup)
                return
            else:
                print(f"Error checking subscription for {telegram_id} in {MANDATORY_CHANNEL_ID}: {e}")
                bot.send_message(chat_id, "حدث خطأ أثناء التحقق من اشتراكك. يرجى المحاولة مرة أخرى.")
                return

        username = message.from_user.username
        full_name = message.from_user.full_name

        referrer_id = None
        start_payload = None
        s = Session()
        try:
            if message.text and len(message.text.split()) > 1:
                start_payload = message.text.split()[1]
                if start_payload.startswith('service_'):
                    service_id = int(start_payload.split('_')[1])

                    user, is_new_user = get_or_create_user(telegram_id, username, full_name, session=s)

                    service = s.query(Service).get(service_id)

                    if not service or not service.is_available:
                        bot.send_message(chat_id, "الخدمة المطلوبة غير متاحة حاليًا أو غير موجودة.", parse_mode="HTML")
                        sent_message = bot.send_message(chat_id, f"{START_MESSAGE}\n\n<blockquote><b>معرفك:</b> <code>{user.telegram_id}</code></blockquote>\n<blockquote><b>رصيدك:</b> ${user.balance:.2f}</blockquote>\n<b>اختر من الأزرار :</b>",
                                                        reply_markup=create_main_menu_inline_keyboard(), parse_mode="HTML")
                        user_states[chat_id] = {"main_menu_message_id": sent_message.message_id}
                        s.close()
                        return

                    user_states[chat_id] = {"state": "waiting_quantity", "service_id": service_id, "message_id": message.message_id}

                    service_details_text = (
                        f"<b>تفاصيل الخدمة:</b>\n"
                        f"<blockquote>✨ <b>الاسم:</b> {service.name}</blockquote>\n"
                        f"<blockquote>📝 <b>الوصف:</b> {service.description or 'لا يوجد وصف.'}</blockquote>\n"
                        f"<blockquote>💲 <b>السعر:</b> ${service.base_price:.2f} لكل {service.base_quantity}</blockquote>\n"
                        f"<blockquote>🔢 <b>الحد الأدنى للكمية:</b> {service.min_quantity}</blockquote>\n"
                        f"<blockquote>🔢 <b>الحد الأقصى للكمية:</b> {service.max_quantity}</blockquote>\n\n"
                        f" إدخل الكمية المطلوبة (مثال: {service.base_quantity}):"
                    )

                    back_button_data = f"cat_{service.category_id}"
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 رجوع إلى التصنيف", callback_data=back_button_data))

                    sent_message = bot.send_message(chat_id, service_details_text, reply_markup=markup, parse_mode="HTML")
                    user_states[chat_id]["message_id"] = sent_message.message_id
                    s.close()
                    return

                else:
                    referral_code = start_payload
                    referrer = s.query(User).filter_by(referral_code=referral_code).first()
                    if referrer:
                        referrer_id = referrer.telegram_id

            user, is_new_user = get_or_create_user(telegram_id, username, full_name, referrer_id, session=s)

            welcome_message_text = (
                f"{START_MESSAGE}\n\n"
                f"<blockquote><b>معرفك:</b> <code>{user.telegram_id}</code></blockquote>\n"
                f"<blockquote><b>رصيدك:</b> ${user.balance:.2f}</blockquote>\n"
                f"<b>اختر من الأزرار :</b>"
            )

            sent_message = bot.send_message(chat_id, welcome_message_text,
                                            reply_markup=create_main_menu_inline_keyboard(),
                                            parse_mode="HTML")
            user_states[chat_id] = {"main_menu_message_id": sent_message.message_id}

            if is_new_user:
                admin_message = (
                    f"<blockquote>👤 <b>مستخدم جديد انضم إلى البوت!</b></blockquote>\n\n"
                    f"<blockquote>🆔 <b>المعرف:</b> <code>{user.telegram_id}</code></blockquote>\n"
                    f"<blockquote>👤 <b>الاسم:</b> {user.full_name}</blockquote>\n"
                    f"<blockquote>📌 <b>اليوزر:</b> "
                    f"{'@' + user.username if user.username else 'لا يوجد'}</blockquote>\n"
                    f"<blockquote>📅 <b>تاريخ التسجيل:</b> {user.registered_at.strftime('%Y-%m-%d %H:%M:%S')}</blockquote>\n"
                    f"<blockquote>🔗 <b>كود الإحالة:</b> <code>{user.referral_code}</code></blockquote>"
                )
                for admin_id in ADMIN_IDS:
                    try:
                        send_message_to_user(
                            admin_id,
                            admin_message,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        print(f"فشل إرسال رسالة المستخدم الجديد للمشرف {admin_id}: {e}")

            if user.is_admin:
                admin_markup = types.InlineKeyboardMarkup()
                admin_markup.add(types.InlineKeyboardButton("لوحة تحكم المشرف ⚙️", callback_data="show_admin_panel_info"))
                bot.send_message(chat_id, "لوحة الادمن سيتم اتعديل لاحقا", reply_markup=admin_markup, parse_mode="HTML")
        except Exception as e:
            print(f"خطأ في معالج /start: {e}")
            bot.send_message(chat_id, "حدث خطأ أثناء بدء البوت. يرجى المحاولة مرة أخرى لاحقًا.")
        finally:
            s.close()
    except Exception as e:
        print(f"خطأ في handle_start: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "حدث خطأ أثناء بدء البوت. يرجى المحاولة مرة أخرى.")
