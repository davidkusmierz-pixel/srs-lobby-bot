import os
import io
import re
import logging

import discord
import pytesseract

from PIL import Image, ImageOps, ImageEnhance, ImageFilter
from discord.ext import commands


# ==========================================
# SRS LOBBY BOT — KONFIGURACJA
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
# ODCZYTYWANIE ID POKOJU GT7
# ==========================================

def odczytaj_id_pokoju(image_bytes):
    try:
        obraz = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Ograniczamy rozmiar, aby OCR nie trwał zbyt długo
        obraz.thumbnail((1600, 1600))

        szary = ImageOps.grayscale(obraz)
        szary = ImageEnhance.Contrast(szary).enhance(2.0)
        szary = ImageEnhance.Sharpness(szary).enhance(1.5)
        szary = szary.filter(ImageFilter.SHARPEN)

        warianty = [
            ("--psm 6", szary),
            ("--psm 11", szary),
            ("--psm 12", szary),
        ]

        wszystkie_teksty = []

        for konfiguracja, obraz_ocr in warianty:
            try:
                tekst = pytesseract.image_to_string(
                    obraz_ocr,
                    config=konfiguracja,
                    timeout=5
                )
                wszystkie_teksty.append(tekst)

            except RuntimeError as error:
                logger.warning("Przekroczono czas OCR: %s", error)

        tekst = "\n".join(wszystkie_teksty)

        logger.info("Tekst rozpoznany przez OCR:\n%s", tekst)

        # Szukamy kodu obok etykiety identyfikatora pokoju
        wzory = [
            r"identyfikator\s*pokoju\s*[:\-]?\s*([a-z0-9]{4,12})",
            r"identyfikator\s+pokoju.{0,40}?([a-z0-9]{4,12})",
        ]

        for wzor in wzory:
            wynik = re.search(
                wzor,
                tekst,
                re.IGNORECASE | re.DOTALL
            )

            if wynik:
                kod = wynik.group(1).lower()

                if kod not in ("identyfikator", "pokoju"):
                    logger.info("Znaleziono ID pokoju: %s", kod)
                    return kod

        # Szukamy identyfikatora w formacie z myślnikami
        wynik = re.search(
            r"\b[a-z0-9]{3,5}(?:-[a-z0-9]{3,5}){1,3}\b",
            tekst,
            re.IGNORECASE
        )

        if wynik:
            kod = wynik.group(0).lower()
            logger.info("Znaleziono ID pokoju: %s", kod)
            return kod

        # Awaryjne wyszukiwanie krótkiego kodu, np. rwar1i
        kandydaci = re.findall(
            r"\b[a-z0-9]{5,10}\b",
            tekst,
            re.IGNORECASE
        )

        for kod in kandydaci:
            kod = kod.lower()

            if (
                any(c.isalpha() for c in kod)
                and any(c.isdigit() for c in kod)
                and kod not in {
                    "gran7",
                    "turismo7",
                    "gt7",
                    "srs2026",
                }
            ):
                logger.info("Kandydat na ID pokoju: %s", kod)
                return kod

        logger.warning("Nie znaleziono identyfikatora pokoju.")
        return None

    except Exception:
        logger.exception("Błąd podczas analizy obrazu.")
        return None


# ==========================================
# BOT DISCORD
# ==========================================

@bot.event
async def on_ready():
    logger.info("SRS LOBBY BOT uruchomiony: %s", bot.user)


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

                logger.info("Wysłano identyfikator: %s", identyfikator)

            else:
                await message.channel.send(
                    "⚠️ Nie udało się odczytać identyfikatora pokoju.\n"
                    "Spróbuj wysłać wyraźniejszy zrzut ekranu."
                )

        except Exception:
            logger.exception("Błąd obsługi zdjęcia.")

            await message.channel.send(
                "❌ Wystąpił błąd podczas analizy zdjęcia."
            )

    await bot.process_commands(message)


# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    if not TOKEN:
        logger.error("Brak tokenu DISCORD_TOKEN w GitHub Secrets!")
    else:
        bot.run(TOKEN)
