import os
import io
import re
import discord
import pytesseract

from PIL import Image, ImageOps, ImageEnhance
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def odczytaj_id_pokoju(image_bytes):
    obraz = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    obraz = ImageOps.grayscale(obraz)
    obraz = ImageEnhance.Contrast(obraz).enhance(2)

    tekst = pytesseract.image_to_string(obraz)

    wzory = [
        r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b",
        r"\b[A-Z0-9]{3,5}-[A-Z0-9]{3,5}-[A-Z0-9]{3,5}\b",
    ]

    for wzor in wzory:
        wynik = re.search(wzor, tekst.upper())
        if wynik:
            return wynik.group(0)

    return None


@bot.event
async def on_ready():
    print(f"SRS LOBBY BOT uruchomiony: {bot.user}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    for attachment in message.attachments:
        if not attachment.content_type:
            continue

        if not attachment.content_type.startswith("image/"):
            continue

        try:
            image_bytes = await attachment.read()
            pokoj = odczytaj_id_pokoju(image_bytes)

            if pokoj:
                await message.channel.send(
                    f"🏁 **SRS OPEN LOBBY**\n"
                    f"🆔 **IDENTYFIKATOR POKOJU:** `{pokoj}`"
                )
            else:
                await message.channel.send(
                    "⚠️ Nie udało się odczytać identyfikatora pokoju. "
                    "Sprawdź, czy jest widoczny na zrzucie ekranu."
                )

        except Exception as error:
            print(f"Błąd analizy zdjęcia: {error}")
            await message.channel.send(
                "❌ Wystąpił problem podczas analizy zdjęcia."
            )

    await bot.process_commands(message)


if TOKEN:
    bot.run(TOKEN)
else:
    print("Brak tokenu DISCORD_TOKEN!")
