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

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ==========================================
# ODCZYTYWANIE IDENTYFIKATORA POKOJU GT7
# ==========================================

def odczytaj_id_pokoju(image_bytes):
    """
    Odczytuje identyfikator pokoju GT7 ze zrzutu ekranu.
    Przykład: rwar1i
    """

    try:
        obraz = Image.open(
            io.BytesIO(image_bytes)
        ).convert("RGB")

        # Powiększenie obrazu
        obraz = obraz.resize(
            (obraz.width * 3, obraz.height * 3)
        )

        # Poprawa kontrastu i ostrości
        obraz = ImageOps.grayscale(obraz)
        obraz = ImageEnhance.Contrast(obraz).enhance(2.5)
        obraz = ImageEnhance.Sharpness(obraz).enhance(2.0)
        obraz = obraz.filter(ImageFilter.SHARPEN)

        # Kilka wariantów OCR zwiększa szansę odczytu
        warianty = [
            "--psm 6",
            "--psm 11",
            "--psm 12"
        ]

        wszystkie_teksty = []

        for konfiguracja in warianty:
            tekst = pytesseract.image_to_string(
                obraz,
                config=konfiguracja
            )

            wszystkie_teksty.append(tekst)

        tekst = "\n".join(wszystkie_teksty)

        logger.info(
            "Tekst odczytany ze zdjęcia:\n%s",
            tekst
        )

        # Normalizacja tekstu
        tekst_normalny = tekst.lower()
        tekst_normalny = tekst_normalny.replace("|", "i")

        # Szukamy identyfikatora w pobliżu etykiety
        wzory_po_etykiecie = [
            r"identyfikator\s*pokoju\s*[:\-]?\s*([a-z0-9]{4,12})",
            r"identyfikator\s+pokoju.{0,30}?([a-z0-9]{4,12})",
        ]

        for wzor in wzory_po_etykiecie:
            wynik = re.search(
                wzor,
                tekst_normalny,
                re.IGNORECASE | re.DOTALL
            )

            if wynik:
                kod = wynik.group(1)

                if kod not in (
                    "identyfikator",
                    "pokoju"
                ):
                    logger.info(
                        "Znaleziony identyfikator: %s",
                        kod
                    )
                    return kod

        # Identyfikatory zapisane z myślnikami
        wzor_z_myslnikami = (
            r"\b[a-z0-9]{3,5}"
            r"(?:-[a-z0-9]{3,5}){1,3}\b"
        )

        wynik = re.search(
            wzor_z_myslnikami,
            tekst_normalny,
            re.IGNORECASE
        )

        if wynik:
            return wynik.group(0)

        # Szukanie krótkich kodów alfanumerycznych
        # Typowy przykład: rwar1i
        kandydaci = re.findall(
            r"\b[a-z0-9]{5,10}\b",
            tekst_normalny,
            re.IGNORECASE
        )

        # Najpierw kody zawierające litery i cyfry
        for kod in kandydaci:
            kod = kod.lower()

            if (
                any(c.isalpha() for c in kod)
                and any(c.isdigit() for c in kod)
                and kod not in (
                    "gran7",
                    "turismo7",
                    "gt7",
                    "srs2026"
                )
            ):
                logger.info(
                    "Znaleziony kandydat na ID pokoju: %s",
                    kod
                )
                return kod

        logger.warning(
            "Nie znaleziono identyfikatora pokoju."
        )

        return None

    except Exception:
        logger.exception(
            "Błąd podczas analizy obrazu."
        )
        return None


# ==========================================
# URUCHOMIENIE BOTA
# ==========================================

@bot.event
async def on_ready():
    logger.info(
        "SRS LOBBY BOT uruchomiony: %s",
        bot.user
    )


# ==========================================
# OBSŁUGA WIADOMOŚCI I ZDJĘĆ
# ==========================================

@bot.event
async def on_message(message):

    # Ignorowanie wiadomości innych botów
    if message.author.bot:
        return

    # Obsługa załączników
    for attachment in message.attachments:

        # Sprawdzenie, czy załącznik jest obrazem
        if attachment.content_type:
            if not attachment.content_type.startswith("image/"):
                continue
        else:
            nazwa = attachment.filename.lower()

            if not nazwa.endswith(
                (".png", ".jpg", ".jpeg", ".webp")
            ):
                continue

        try:
            logger.info(
                "Otrzymano zdjęcie: %s",
                attachment.filename
            )

            image_bytes = await attachment.read()

            identyfikator = odczytaj_id_pokoju(
                image_bytes
            )

            if identyfikator:

                wiadomosc = (
                    "🏁 **SRS OPEN LOBBY**\n\n"
                    "🆔 **IDENTYFIKATOR POKOJU:**\n"
                    f"```{identyfikator}```\n"
                    "🏎️ Dołącz do lobby w Gran Turismo 7!"
                )

                await message.channel.send(wiadomosc)

                logger.info(
                    "Wysłano identyfikator: %s",
                    identyfikator
                )

            else:

                await message.channel.send(
                    "⚠️ Nie udało się odczytać "
                    "identyfikatora pokoju.\n"
                    "Upewnij się, że identyfikator "
                    "jest widoczny na zdjęciu."
                )

        except Exception:
            logger.exception(
                "Błąd podczas przetwarzania zdjęcia."
            )

            await message.channel.send(
                "❌ Wystąpił błąd podczas analizy zdjęcia."
            )

    await bot.process_commands(message)


# ==========================================
# START
# ==========================================

if __name__ == "__main__":

    if not TOKEN:
        logger.error(
            "Brak tokenu DISCORD_TOKEN w GitHub Secrets!"
        )

    else:
        bot.run(TOKEN)
