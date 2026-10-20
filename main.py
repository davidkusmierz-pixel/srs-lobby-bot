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
# ODCZYTYWANIE IDENTYFIKATORA POKOJU GT7
# ==========================================

def odczytaj_id_pokoju(image_bytes):
    """
    Próbuje odczytać identyfikator pokoju GT7,
    np. rwar1i, ze zrzutu ekranu.
    """

    try:
        obraz = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        szerokosc, wysokosc = obraz.size

        # Fragmenty, na których może znajdować się identyfikator.
        fragmenty = [
            obraz,
            obraz.crop((
                0,
                int(wysokosc * 0.15),
                int(szerokosc * 0.90),
                int(wysokosc * 0.75)
            )),
            obraz.crop((
                0,
                int(wysokosc * 0.20),
                int(szerokosc * 0.75),
                int(wysokosc * 0.65)
            )),
        ]

        wszystkie_teksty = []

        for fragment in fragmenty:
            # Ograniczamy rozmiar przed powiększeniem.
            fragment.thumbnail((1200, 900))

            szary = ImageOps.grayscale(fragment)
            szary = ImageEnhance.Contrast(szary).enhance(2.5)
            szary = ImageEnhance.Sharpness(szary).enhance(2.0)

            # Powiększamy obraz, aby ułatwić odczyt małych liter.
            szary = szary.resize(
                (szary.width * 3, szary.height * 3)
            )
            szary = szary.filter(ImageFilter.SHARPEN)

            for konfiguracja in ("--psm 6", "--psm 11"):
                try:
                    tekst = pytesseract.image_to_string(
                        szary,
                        config=konfiguracja,
                        timeout=5
                    )
                    wszystkie_teksty.append(tekst)

                except RuntimeError as error:
                    logger.warning("Przekroczono czas OCR: %s", error)

        tekst = "\n".join(wszystkie_teksty)

        logger.info("Tekst rozpoznany przez OCR:\n%s", tekst)

        # Szukamy kodu bezpośrednio przy etykiecie.
        wzory = [
            r"identyfikator\s+pokoju\s*[:\-]?\s*([a-z0-9]{4,12})",
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

                if kod not in {"identyfikator", "pokoju"}:
                    logger.info("Znaleziono identyfikator: %s", kod)
                    return kod

        # Obsługa identyfikatorów zawierających myślniki.
        wynik = re.search(
            r"\b[a-z0-9]{3,5}(?:-[a-z0-9]{3,5}){1,3}\b",
            tekst,
            re.IGNORECASE
        )

        if wynik:
            kod = wynik.group(0).lower()
            logger.info("Znaleziono identyfikator: %s", kod)
            return kod

        # Awaryjne wyszukiwanie kodu, np. rwar1i.
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
                    "srs2026",
                    "identyfikator",
                }
            ):
                logger.info("Kandydat na identyfikator: %s", kod)
                return kod

        logger.warning("Nie znaleziono identyfikatora pokoju.")
        return None

    except Exception:
        logger.exception("Błąd podczas analizy obrazu.")
        return None


# ==========================================
# URUCHOMIENIE BOTA
# ==========================================

@bot.event
async def on_ready():
    logger.info("SRS LOBBY BOT uruchomiony: %s", bot.user)


# ==========================================
# ODBIERANIE ZDJĘĆ NA DISCORDZIE
# ==========================================

@bot.event
async def on_message(message):
    # Ignorujemy wiadomości wysłane przez boty.
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

            try:
                await message.channel.send(
                    "❌ Wystąpił błąd podczas analizy zdjęcia."
                )
            except discord.HTTPException:
                logger.exception("Nie udało się wysłać komunikatu błędu.")

    await bot.process_commands(message)


# ==========================================
# START BOTA
# ==========================================

if __name__ == "__main__":
    if not TOKEN:
        logger.error("Brak tokenu DISCORD_TOKEN w GitHub Secrets!")
    else:
        bot.run(TOKEN)
        
