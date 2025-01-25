import discord
from discord.ext import commands
import os
import asyncio
import yt_dlp
import random
from dotenv import load_dotenv

load_dotenv()

# Load the bot token from the .env file
TOKEN = os.getenv("discord_token")

# Initialize the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents)

# Globals for managing music
voice_clients = {}
queues = {}
ytdl_options = {'format': 'bestaudio/best'}
ytdl = yt_dlp.YoutubeDL(ytdl_options)
ffmpeg_options = {'options': '-vn'}
looping_state = {}

### Music Commands
@bot.command()
async def play(ctx, *, query: str):
    """Plays music from a YouTube URL or search query."""
    guild_id = ctx.guild.id

    # Initialize the queue for the guild
    if guild_id not in queues:
        queues[guild_id] = []

    # Search or get song information using yt_dlp
    await ctx.send(f"Searching for: **{query}**")
    try:
        if "youtube.com" in query or "youtu.be" in query:
            data = ytdl.extract_info(query, download=False)
        else:
            search_data = ytdl.extract_info(f"ytsearch:{query}", download=False)
            if not search_data['entries']:
                await ctx.send("No results found. Please try another query.")
                return
            data = search_data['entries'][0]  # Take the first search result

        # Handle playlists or single videos
        if 'entries' in data:
            await ctx.send(f"Adding playlist: **{data['title']}** ({len(data['entries'])} songs)")
            for entry in data['entries']:
                song_info = {
                    'title': entry['title'],
                    'url': entry['url'],
                    'message_channel': ctx.channel
                }
                queues[guild_id].append(song_info)
        else:
            song_info = {
                'title': data['title'],
                'url': data['url'],
                'message_channel': ctx.channel
            }
            queues[guild_id].append(song_info)
            await ctx.send(f"**{data['title']}** has been added to the queue!")

        # Connect to the voice channel if not already connected
        if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
            if ctx.author.voice:
                voice_client = await ctx.author.voice.channel.connect()
                voice_clients[guild_id] = voice_client
            else:
                await ctx.send("You need to be in a voice channel to play music.")
                return

        # Play the song immediately if nothing is playing
        if not voice_clients[guild_id].is_playing():
            await play_next_song(ctx, guild_id)
    except Exception as e:
        print(f"Error playing audio: {e}")
        await ctx.send("An error occurred. Please try again.")

async def play_next_song(ctx, guild_id):
    """Plays the next song in the queue."""
    if guild_id not in queues or not queues[guild_id]:
        return

    if looping_state.get(guild_id, False):
        song_info = queues[guild_id][0]  # Loop the current song
    else:
        song_info = queues[guild_id].pop(0)  # Get the next song

    song_url = song_info['url']
    song_title = song_info['title']

    try:
        loop = asyncio.get_event_loop()
        player = discord.FFmpegPCMAudio(song_url, **ffmpeg_options)
        voice_clients[guild_id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
            play_next_song(ctx, guild_id), loop
        ))
        await ctx.send(f"Now playing: **{song_title}**")
    except Exception as e:
        print(f"Error playing audio: {e}")
        await ctx.send("An error occurred while playing the song.")

@bot.command()
async def pause(ctx):
    """Pauses the current song."""
    guild_id = ctx.guild.id
    if guild_id in voice_clients and voice_clients[guild_id].is_playing():
        voice_clients[guild_id].pause()
        await ctx.send("Paused the music.")
    else:
        await ctx.send("No music is currently playing.")

@bot.command()
async def resume(ctx):
    """Resumes the paused song."""
    guild_id = ctx.guild.id
    if guild_id in voice_clients and voice_clients[guild_id].is_paused():
        voice_clients[guild_id].resume()
        await ctx.send("Resumed the music.")
    else:
        await ctx.send("No music is currently paused.")

@bot.command()
async def stop(ctx):
    """Stops the music and clears the queue."""
    guild_id = ctx.guild.id
    if guild_id in voice_clients:
        voice_clients[guild_id].stop()
        queues[guild_id] = []
        await ctx.send("Stopped the music and cleared the queue.")
    else:
        await ctx.send("The bot is not playing any music.")

@bot.command()
async def skip(ctx):
    """Skips the current song."""
    guild_id = ctx.guild.id
    if guild_id in voice_clients and voice_clients[guild_id].is_playing():
        voice_clients[guild_id].stop()
        await ctx.send("Skipped to the next song.")
    else:
        await ctx.send("No music is currently playing.")

@bot.command()
async def queue(ctx):
    """Displays the current queue."""
    guild_id = ctx.guild.id
    if guild_id in queues and queues[guild_id]:
        queue_list = "\n".join([f"{idx + 1}. {song['title']}" for idx, song in enumerate(queues[guild_id])])
        await ctx.send(f"**Current Queue:**\n{queue_list}")
    else:
        await ctx.send("The queue is empty.")

@bot.command()
async def shuffle(ctx):
    """Shuffles the current queue."""
    guild_id = ctx.guild.id
    if guild_id in queues and queues[guild_id]:
        random.shuffle(queues[guild_id])
        await ctx.send("Shuffled the queue.")
    else:
        await ctx.send("The queue is empty.")

@bot.command()
async def loop(ctx):
    """Toggles looping for the current song."""
    guild_id = ctx.guild.id
    looping_state[guild_id] = not looping_state.get(guild_id, False)
    state = "enabled" if looping_state[guild_id] else "disabled"
    await ctx.send(f"Looping is now {state}.")

@bot.command()
async def dc(ctx):
    """Disconnects the bot from the voice channel."""
    guild_id = ctx.guild.id
    if guild_id in voice_clients:
        await voice_clients[guild_id].disconnect()
        del voice_clients[guild_id]
        queues.pop(guild_id, None)
        await ctx.send("Disconnected from the voice channel.")
    else:
        await ctx.send("The bot is not in a voice channel.")

### Fun Commands
@bot.command()
async def gunblade(ctx):
    """WE MISS YOU GUNBLADE."""
    image_path = "gunblade.png"
    if os.path.exists(image_path):
        await ctx.send(file=discord.File(image_path))
        await ctx.send("WE ALL MISS YOU GUNBLADE")
    else:
        await ctx.send("The image file could not be found.")

@bot.command()
async def heartsteel(ctx):
    """Plays the Heartsteel sound."""
    await play_sound(ctx, "heartsteel.mp3", "PLUS 1 HEARTSTEEL STACK!")

@bot.command()
async def viktor(ctx):
    """Viktor"""
    await play_sound(ctx, "viktor.mp3", "VIK TOR VIKTOOORRRRR")

async def play_sound(ctx, file_path, message):
    """Plays a sound file if available."""
    guild_id = ctx.guild.id
    if not ctx.author.voice:
        await ctx.send("You need to be in a voice channel to use this command.")
        return

    if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
        voice_client = await ctx.author.voice.channel.connect()
        voice_clients[guild_id] = voice_client
    else:
        voice_client = voice_clients[guild_id]

    if voice_client.is_playing():
        await ctx.send("❌ Cannot play sounds while music is playing.")
        return

    if not os.path.exists(file_path):
        await ctx.send(f"❌ The sound file `{file_path}` could not be found.")
        return

    player = discord.FFmpegPCMAudio(file_path)
    voice_client.play(player)
    await ctx.send(message)

### Run the Bot
bot.run(TOKEN)
