import os
import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"🏁 SRS LOBBY BOT uruchomiony: {bot.user}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("image/"):
                print(f"📸 Otrzymano zdjęcie: {attachment.filename}")
                await message.channel.send(
                    "🏁 Zdjęcie lobby otrzymane! SRS BOT przygotowuje się do analizy."
                )

    await bot.process_commands(message)


if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Brak tokenu DISCORD_TOKEN!")
