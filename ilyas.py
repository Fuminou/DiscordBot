import discord
from discord.ext import commands
import os
import asyncio
import yt_dlp
import random
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from discord.ui import View, Button
import math

load_dotenv()

# Load the bot token and spotify stuff from the .env file
TOKEN = os.getenv("discord_token")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Initialize Spotify Client
spotify = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

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

### **Helper Functions**
def is_spotify_url(url):
    """Check if the input is a Spotify URL (track, playlist, or album)."""
    return "open.spotify.com" in url

def get_spotify_track_info(url):
    """Retrieve a single track's name and artist from a Spotify track URL."""
    try:
        track_id = url.split("track/")[1].split("?")[0]
        track_info = spotify.track(track_id)
        return f"{track_info['name']} by {track_info['artists'][0]['name']}"
    except Exception as e:
        print(f"Error retrieving Spotify track info: {e}")
        return None

def get_spotify_tracks(url, type):
    """Retrieve all track names from a Spotify playlist or album."""
    try:
        if type == "playlist":
            item_id = url.split("playlist/")[1].split("?")[0]
            items = spotify.playlist_tracks(item_id)['items']
            tracks = [f"{track['track']['name']} by {track['track']['artists'][0]['name']}" for track in items if track.get('track')]

        elif type == "album":
            item_id = url.split("album/")[1].split("?")[0]
            items = spotify.album_tracks(item_id)['items']
            tracks = [f"{track['name']} by {track['artists'][0]['name']}" for track in items]

        return tracks if tracks else None
    except Exception as e:
        print(f"Error retrieving Spotify {type}: {e}")
        return None

async def search_youtube(query):
    """Search YouTube for a song and return the best match URL and title."""
    try:
        search_data = ytdl.extract_info(f"ytsearch:{query}", download=False)
        if search_data['entries']:
            return search_data['entries'][0]['url'], search_data['entries'][0]['title']
    except Exception as e:
        print(f"Error searching YouTube: {e}")
    return None, None

### **Music Commands**
@bot.command()
async def play(ctx, *, query: str):
    """Plays a song from YouTube, a Spotify track, a Spotify playlist, or a Spotify album."""
    guild_id = ctx.guild.id

    # Initialize queue for the guild if not exists
    if guild_id not in queues:
        queues[guild_id] = []

    # Handle Spotify URLs
    if is_spotify_url(query):
        tracks = []

        if "track/" in query:
            track = get_spotify_track_info(query)
            if track:
                tracks.append(track)

        elif "playlist/" in query:
            tracks = get_spotify_tracks(query, "playlist")

        elif "album/" in query:
            tracks = get_spotify_tracks(query, "album")

        if not tracks:
            await ctx.send("Failed to fetch songs from Spotify.")
            return

        await ctx.send(f"Adding {len(tracks)} songs from Spotify to the queue...")

        # Search YouTube & Add Songs to Queue One by One
        for track in tracks:
            await add_to_queue(ctx, guild_id, track)

        return  # Exit function after handling Spotify

    # If not a Spotify URL, assume it's a YouTube search
    await add_to_queue(ctx, guild_id, query)

async def add_to_queue(ctx, guild_id, query):
    """Search YouTube and add the song to the queue."""
    song_url, song_title = await search_youtube(query)
    if not song_url:
        await ctx.send(f"No results found for **{query}** on YouTube.")
        return

    # Add to queue
    song_info = {
        'title': song_title,
        'url': song_url,
        'message_channel': ctx.channel
    }
    queues[guild_id].append(song_info)
    await ctx.send(f"**{song_title}** has been added to the queue!")

    # Connect to voice channel if not connected
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

async def play_next_song(ctx, guild_id):
    """Plays the next song in the queue."""
    if guild_id not in queues or not queues[guild_id]:
        return

    if looping_state.get(guild_id, False):
        song_info = queues[guild_id][0]  # Loop the current song
    else:
        song_info = queues[guild_id].pop(0)  # Get next song

    song_url = song_info['url']
    song_title = song_info['title']

    try:
        loop = asyncio.get_event_loop()
        player = discord.FFmpegPCMAudio(song_url, **ffmpeg_options)
        voice_clients[guild_id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
            play_next_song(ctx, guild_id), loop
        ))
        await ctx.send(f"▶️ Now playing: **{song_title}**")
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
    """Displays the song queue with pagination."""
    guild_id = ctx.guild.id

    if guild_id not in queues or not queues[guild_id]:
        await ctx.send("The queue is empty.")
        return

    queue_list = [f"{idx + 1}. {song['title']}" for idx, song in enumerate(queues[guild_id])]
    per_page = 10  # Number of songs per page
    total_pages = math.ceil(len(queue_list) / per_page)

    # Function to generate the page content
    def get_page(page):
        start = page * per_page
        end = start + per_page
        songs = "\n".join(queue_list[start:end])
        return f"**Current Queue (Page {page + 1}/{total_pages}):**\n{songs}"

    # Create the first embed
    embed = discord.Embed(title="🎶 Music Queue", description=get_page(0), color=discord.Color.blue())
    message = await ctx.send(embed=embed, view=QueuePagination(ctx, get_page, total_pages))

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

class QueuePagination(View):
    def __init__(self, ctx, get_page, total_pages):
        super().__init__()
        self.ctx = ctx
        self.get_page = get_page
        self.total_pages = total_pages
        self.current_page = 0

        # Create buttons
        self.prev_button = Button(label="⬅️ Previous", style=discord.ButtonStyle.grey)
        self.next_button = Button(label="➡️ Next", style=discord.ButtonStyle.grey)

        # Add button callbacks
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page

        # Add buttons to the view
        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.update_buttons()

    def update_buttons(self):
        """Enable or disable buttons based on the current page."""
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.total_pages - 1

    async def prev_page(self, interaction: discord.Interaction):
        """Go to the previous page."""
        self.current_page -= 1
        self.update_buttons()
        embed = discord.Embed(title="🎶 Music Queue", description=self.get_page(self.current_page), color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_page(self, interaction: discord.Interaction):
        """Go to the next page."""
        self.current_page += 1
        self.update_buttons()
        embed = discord.Embed(title="🎶 Music Queue", description=self.get_page(self.current_page), color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=self)



### Run the Bot
bot.run(TOKEN)
