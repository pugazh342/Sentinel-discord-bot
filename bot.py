import os
import discord
from discord.ext import commands
import aiohttp
import asyncio

# --- CONFIGURATION ---
DISCORD_BOT_TOKEN = "Place your Discord bot token here"
HF_API_URL = "Endpoint URL of your FastAPI Space (e.g., https://your-space-name.hf.space/run/predict)"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("--------------------------------------------------")
    print(f"SUCCESS: {bot.user.name} is online!")
    print(f"Targeting backend: {HF_API_URL}")
    print("Ready for commands. Type !ask <prompt> in Discord.")
    print("--------------------------------------------------")

def split_response(text, max_length=1900):
    """Splits long text to respect Discord's 2,000 character ceiling."""
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]

async def query_sentinel_engine(payload: dict) -> dict:
    """Sends the HTTP POST request to your FastAPI Space."""
    async with aiohttp.ClientSession() as session:
        try:
            # Extended to 180 seconds to allow the free CPU tier enough processing headroom
            async with session.post(HF_API_URL, json=payload, timeout=180) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 422:
                    return {"error": "HTTP 422: The backend rejected the payload schema structure."}
                else:
                    return {"error": f"HTTP Error {response.status}"}
        except asyncio.TimeoutError:
            return {"error": "Inference timed out. The CPU engine took over 3 minutes to compile a response."}
        except Exception as e:
            return {"error": f"Network exception: {str(e)}"}

@bot.command(name="ask")
async def ask(ctx, *, prompt: str):
    """Triggers the AI model via Discord (!ask <prompt>)"""
    async with ctx.typing():
        
        # Reduced max_tokens to 128 for snappier generation responses on the free CPU instance
        payload = {
            "prompt": prompt,
            "max_tokens": 128,
            "temperature": 0.7
        }
        
        result = await query_sentinel_engine(payload)
        
        # Handle Python errors trapped by the backend Try/Except block
        if isinstance(result, dict) and "error" in result:
            await ctx.send(f"❌ **Engine Failure:** `{result['error']}`")
            return

        # Safely unwrap the generated string
        if isinstance(result, dict) and "generated_text" in result:
            response_text = result["generated_text"].strip()
        else:
            response_text = f"⚠️ Server returned an unparseable response: {result}"

        if not response_text:
            await ctx.send("Received an empty output string from the engine.")
            return

        # Dispatch chunks back to the Discord channel
        for chunk in split_response(response_text):
            await ctx.send(chunk)

bot.run(DISCORD_BOT_TOKEN)