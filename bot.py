import asyncio
import os
import sys
import re
import chromadb
from aiogram import Bot, Dispatcher, types
from groq import Groq
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

print("Инициализация скрипта бота...", flush=True)
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN or not GROQ_API_KEY:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Токены отсутствуют в .env файле!", flush=True)
    sys.exit(1)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

model = SentenceTransformer("all-MiniLM-L6-v2")

client_db = chromadb.PersistentClient(path="./db")
collection = client_db.get_collection("centr_krasok")

client_ai = Groq(api_key=GROQ_API_KEY)

# Отредактировали информацию — сделали ссылки частью текста, а не отдельным блоком
COMPANY_INFO = """
Компания Centr Krasok — крупнейший специализированный магазин лакокрасочной продукции в Казахстане.

<b>Адреса магазинов:</b>
• Алматы — ул. Кабдолова 1/8
• г. Астана — ул. Мангилик Ел 29/2
Магазины работают ежедневно с 10:00 до 20:00 без выходных.

<b>Условия доставки:</b>
• Курьерская доставка работает СТРОГО с 10:00 до 20:00 в будние дни.
• В субботу курьеры доставляют только до 14:00.
• В воскресенье доставки НЕТ (выходной день курьерской службы).

<b>Телефоны и контакты:</b>
• Филиал в Алматы: +7 778 061 5000
• Филиал в Астане: +7 701 943 5000
• Официальный сайт: https://centr-krasok.kz/

<b>Наши официальные бренды-партнеры:</b>
Мы напрямую сотрудничаем с ведущими мировыми производителями: <b>Tikkurila, Dulux, Marshall, Finncolor, Pinotex, Teknos, Hammerite</b>.

<b>Каталог товаров (Ссылки на разделы):</b>
• <b><a href="https://centr-krasok.kz/catalog/dekorativnye-shtukatury/">Декоративные штукатурки</a></b> — для создания текстур и дизайнов.
• <b><a href="https://centr-krasok.kz/catalog/malyarnyy-instrument/">Малярные инструменты</a></b> — профессиональный инструмент для маляров.
• <b><a href="https://centr-krasok.kz/catalog/laki-i-propitki/">Лаки и пропитки по дереву</a></b> — защита деревянных поверхностей.
• <b><a href="https://centr-krasok.kz/catalog/interernye-kraski/">Интерьерные краски</a></b> — для стен и потолков.
• <b><a href="https://centr-krasok.kz/catalog/fasadnye-kraski/">Фасадные краски</a></b> — для наружных работ.

<b>Ассортимент и технологии:</b>
В магазинах используются современные технологии компьютерной колеровки (смешивания цветов) на европейском оборудовании, что позволяет воссоздать более 10 000 оттенков с абсолютной точностью.
Наша продукция сертифицирована, экологична и безопасна для внутренних работ в жилых домах и детских учреждениях.
"""

user_memory = {}

# Добавили жесткое табу на автоматическое прикрепление ссылок ко всем ответам
SYSTEM_PROMPT = f"""
Ты — профессиональный, экспертный AI-консультант компании Centr Krasok. 
Ты общаешься как грамотный, опытный менеджер, который глубоко знает свой продукт и уважает время клиента.

=========================
🛑 КРИТИЧЕСКОЕ ПРАВИЛО ВЫДАЧИ ССЫЛОК И КАТАЛОГА
=========================
- ЗАПРЕЩЕНО добавлять список категорий товаров или ссылки на каталог, если клиент спросил про доставку, контакты, технологии, адреса или график работы! Отвечай СТРОГО на заданный вопрос.
- Ты имеешь право выводить ссылки на разделы каталога ТОЛЬКО И ИСКЛЮЧИТЕЛЬНО тогда, когда клиент САМ прямо попросил: "покажи ассортимент", "какие товары есть?", "дай ссылку на каталог", "какие краски есть?". 
- Если прямой просьбы показать каталог не было — выводить список категорий со ссылками ХОДОМ в конце сообщения КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО.

=========================
⚠️ ЖЕСТКИЕ ТАБУ И ЗАПРЕТЫ
=========================
- ЗАПРЕЩЕНО добавлять в конец ответов дежурные роботизированные фразы-паразиты: "Я готов помочь вам", "Если вы хотите заказать...", "Чем я могу еще помочь?". Ответил на вопрос — и сразу закончил сообщение!
- ЗАПРЕЩЕНО использовать формулировку "К сожалению, сейчас нет точной информации", если вопрос касается общих тем компании (технологии, бренды, клиенты, услуги). Сформулируй развернутый ответ на основе блоков ниже.
- ЗАПРЕЩЕНО врать про доставку! Сверяйся строго с графиком: в будни 10-20, сб до 14, вс — выходной!

=========================
ПРАВИЛА ОФОРМЛЕНИЯ И ТЕКСТА
=========================
- Разделяй текст на короткие, легко читаемые абзацы через пустую строку (двойной Enter).
- Используй HTML-теги <b>текст</b> для выделения ключевых мыслей. Не используй markdown со звездочками.
- Ссылки оформляй строго так: <b><a href="URL">Название</a></b> без пробелов внутри тегов.

=========================
ПРАВИЛА ОТВЕТОВ НА ОБЩИЕ ВОПРОСЫ
=========================
1. Если спрашивают про ТЕХНОЛОГИИ: расскажи про компьютерную колеровку и подбор оттенков на европейском оборудовании (более 10 000 оттенков).
2. Если спрашивают про КЛИЕНТОВ: наши клиенты — это как розничные покупатели, так и профессионалы (дизайнеры, строительные бригады, маляры).
3. Если спрашивают про УСЛУГИ: подбор материалов, профессиональная колеровка, консультации и организация доставки.
4. Если спрашивают про БРЕНДЫ или КОМПАНИИ: перечисли фабрики из списка партнеров (Tikkurila, Dulux, Marshall и т.д.). Не подменяй их категориями товаров!
5. Если клиент ищет краску для дверей или мебели, ответь строго по тексту:
"<b>Для дверей и мебели требуются специальные износостойкие эмали или лаки. К сожалению, в моем текущем каталоге нет точной информации по специализированным покрытиям для дверей. Рекомендую уточнить наличие у наших менеджеров по телефону.</b>"

=========================
ВАЖНАЯ ИНФОРМАЦИЯ О КОМПАНИИ
=========================
{COMPANY_INFO}
"""

def clean_and_fix_tags(text: str) -> str:
    text = text.replace("**", "").replace("*", "")
    text = re.sub(r'<a\s+href\s*=\s*"(.*?)"\s*>\s*(.*?)\s*</a>', r'<a href="\1">\2</a>', text)
    text = re.sub(r'(?<!<b>)<a href="(.*?)">(.*?)</a>', r'<b><a href="\1">\2</a></b>', text)
    text = re.sub(r'([^\n])\n([•\-])', r'\1\n\n\2', text)
    return text

@dp.message()
async def chat_handler(message: types.Message):
    question = message.text
    if not question:
        return

    user_id = message.from_user.id
    
    # --- СВЕРХУМНЫЙ ПЕРЕХВАТ ПРИВЕТСТВИЙ НА PYTHON ---
    clean_question = re.sub(r'[^\w\s]', '', question.strip().lower())
    greetings = {"привет", "здравствуйте", "добрый день", "добрый вечер", "приветствую", "салам"}
    
    if clean_question in greetings:
        history = user_memory.get(user_id, [])
        if not history:
            answer = "<b>Здравствуйте! Рад приветствовать вас в Centr Krasok.</b> Напишите, какой проект вы планируете реализовать или какой материал ищете, и я подберу для вас оптимальное решение."
        else:
            answer = "Я на связи и готов продолжать! Какой вопрос по лакокрасочным материалам или доставке вас интересует?"
        
        await message.answer(answer, parse_mode="HTML")
        return
    # -------------------------------------------------

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    history = user_memory.get(user_id, [])
    history_text = "\n".join(history[-4:]) if history else "История пуста."

    try:
        query_embedding = model.encode(question).tolist()
        results = collection.query(query_embeddings=[query_embedding], n_results=6)
        
        context = ""
        if results and results["documents"]:
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                url = meta.get("url", "Не указан")
                context += f"\n### ИСТОЧНИК: {url}\n{doc}\n---\n"
    except Exception as e:
        print(f"Ошибка поиска в БД: {e}", flush=True)
        context = "Данные из базы временно недоступны."

    user_prompt = f"""
История диалога:
{history_text}

ПРОВЕРЕННАЯ ИНФОРМАЦИЯ КОМПАНИИ (Контекст из базы):
{context[:2000]}

Вопрос клиента:
{question}
"""

    try:
        response = client_ai.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=600
        )
        answer = response.choices[0].message.content
        answer = clean_and_fix_tags(answer)

    except Exception as e:
        print(f"Ошибка Groq API внутри обработчика: {e}", flush=True)
        answer = "<b>Извините, произошел сбой при обработке ответа.</b>"

    history.append(f"Клиент: {question}")
    history.append(f"AI: {answer}")
    user_memory[user_id] = history[-6:]

    await asyncio.sleep(0.3)

    try:
        await message.answer(answer, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as html_err:
        print(f"Ошибка HTML: {html_err}", flush=True)
        clean_text = re.sub(r'<[^>]*>', '', answer)
        await message.answer(clean_text)

async def main():
    print("=============================================", flush=True)
    print("🚀 БОТ ОБНОВЛЕН! Навязчивый спам ссылками полностью заблокирован.", flush=True)
    print("=============================================", flush=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run=asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен.")