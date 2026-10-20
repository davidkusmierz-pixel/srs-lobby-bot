import os
import io
import re
import logging

import discord
import pytesseract

from PIL import Image, ImageOps, ImageEnhance, ImageFilter
from discord.ext import commands


# ==========================================
# SRS LOBBY BOT
# ==========================================

TOKEN = os.getenv("DISCORD_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger("SRS_LOBBY_BOT")

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ==========================================
# ODCZYT ID POKOJU GT7
# ==========================================

def odczytaj_id_pokoju(image_bytes):
    try:
        obraz = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        szerokosc, wysokosc = obraz.size

        # Na typowym ekranie GT7 etykieta identyfikatora
        # znajduje się w środkowej części ekranu.
        # Analizujemy ten obszar, pomijając większość pozostałych napisów.
        obszar = obraz.crop((
            0,
            int(wysokosc * 0.18),
            int(szerokosc * 0.82),
            int(wysokosc * 0.58)
        ))

        # Powiększamy fragment.
        obszar = obszar.resize(
            (obszar.width * 4, obszar.height * 4)
        )

        szary = ImageOps.grayscale(obszar)
        szary = ImageEnhance.Contrast(szary).enhance(2.5)
        szary = ImageEnhance.Sharpness(szary).enhance(2.0)
        szary = szary.filter(ImageFilter.SHARPEN)

        # Dwa tryby OCR.
        teksty = []

        for konfiguracja in ("--psm 6", "--psm 11"):
            try:
                tekst = pytesseract.image_to_string(
                    szary,
                    config=konfiguracja,
                    timeout=5
                )
                teksty.append(tekst)

            except RuntimeError as error:
                logger.warning("OCR timeout: %s", error)

        tekst = "\n".join(teksty)

        logger.info("Tekst z obszaru ID:\n%s", tekst)

        # Szukamy etykiety oraz kodu znajdującego się po niej.
        wzory = [
            r"identyfikator\s+pokoju\s*[:\-]?\s*([a-z0-9]{5,10})",
            r"identyfikator\s*pokoju.{0,25}?([a-z0-9]{5,10})",
        ]

        for wzor in wzory:
            wynik = re.search(
                wzor,
                tekst,
                re.IGNORECASE | re.DOTALL
            )

            if wynik:
                kod = wynik.group(1).lower()

                if kod not in {"identyfikator", "pokoju"}:
                    logger.info("Kandydat na ID pokoju: %s", kod)
                    return kod

        # Nie wybieramy przypadkowego ciągu z całego zdjęcia.
        # Jeśli nie ma wiarygodnego wyniku, prosimy o ponowny zrzut.
        logger.warning("Nie udało się pewnie odczytać ID pokoju.")
        return None

    except Exception:
        logger.exception("Błąd podczas analizy zdjęcia.")
        return None


# ==========================================
# POŁĄCZENIE Z DISCORDEM
# ==========================================

@bot.event
async def on_ready():
    logger.info("SRS LOBBY BOT uruchomiony: %s", bot.user)


# ==========================================
# OBSŁUGA ZDJĘĆ
# ==========================================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    for attachment in message.attachments:
        nazwa = attachment.filename.lower()

        czy_obraz = (
            attachment.content_type is not None
            and attachment.content_type.startswith("image/")
        ) or nazwa.endswith((".png", ".jpg", ".jpeg", ".webp"))

        if not czy_obraz:
            continue

        try:
            logger.info("Otrzymano zdjęcie: %s", attachment.filename)

            image_bytes = await attachment.read()
            identyfikator = odczytaj_id_pokoju(image_bytes)

            if identyfikator:
                await message.channel.send(
                    "🏁 **SRS OPEN LOBBY**\n\n"
                    "🆔 **IDENTYFIKATOR POKOJU:**\n"
                    f"```{identyfikator}```\n"
                    "🏎️ Dołącz do lobby w Gran Turismo 7!"
                )
            else:
                await message.channel.send(
                    "⚠️ Nie udało się pewnie odczytać identyfikatora.\n"
                    "Wyślij wyraźniejszy zrzut ekranu, na którym "
                    "widać cały napis „Identyfikator pokoju”."
                )

        except Exception:
            logger.exception("Błąd obsługi zdjęcia.")

            await message.channel.send(
                "❌ Wystąpił błąd podczas analizy zdjęcia."
            )

    await bot.process_commands(message)


# ==========================================
# START BOTA
# ==========================================

if __name__ == "__main__":
    if not TOKEN:
        logger.error("Brak tokenu DISCORD_TOKEN w GitHub Secrets!")
    else:
        bot.run(TOKEN)
