import discord
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
import random

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('discord_token')  # Make sure the .env file has the correct token
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    voice_clients = {}
    queues = {}  # A dictionary to store the song queue for each guild
    ytdl_options = {'format': 'bestaudio/best'}
    ytdl = yt_dlp.YoutubeDL(ytdl_options)
    ffmpeg_options = {'options': '-vn'}

    async def play_next_song(guild_id):
        """Plays the next song in the queue."""
        if queues[guild_id]:  # Check if the queue is not empty
            song_info = queues[guild_id].pop(0)  # Get the next song (info dictionary)
            song_url = song_info['url']
            loop = asyncio.get_event_loop()
            player = discord.FFmpegPCMAudio(song_url, **ffmpeg_options)
            voice_clients[guild_id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next_song(guild_id), loop))
            await song_info['message_channel'].send(f"Now playing: **{song_info['title']}**")

    @client.event
    async def on_ready():
        print(f'{client.user} has connected to Discord!')

    @client.event
    async def on_message(message):
        guild_id = message.guild.id

        if message.content.startswith("?play"):
            try:
                url = message.content.split()[1]

                # Initialize queue if it doesn't exist for this guild
                if guild_id not in queues:
                    queues[guild_id] = []

                # Extract song info
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

                # Add song info (title and URL) to the queue
                song_info = {
                    'title': data['title'],  # Extract song title
                    'url': data['url'],      # Extract song URL
                    'message_channel': message.channel  # Store the channel to send messages
                }
                queues[guild_id].append(song_info)

                # Connect to the voice channel if not connected
                if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
                    voice_client = await message.author.voice.channel.connect()
                    voice_clients[guild_id] = voice_client

                # Play the song immediately if nothing is playing
                if not voice_clients[guild_id].is_playing():
                    await play_next_song(guild_id)
                else:
                    await message.channel.send(f"**{song_info['title']}** has been added to the queue!")
            except Exception as e:
                print(f"Error playing audio: {e}")
                await message.channel.send("An error occurred. Please try again.")

        if message.content.startswith("?pause"):  # Pause music
            try:
                voice_clients[guild_id].pause()
            except Exception as e:
                print(f"Error pausing audio: {e}")

        if message.content.startswith("?resume"):  # Resume music
            try:
                voice_clients[guild_id].resume()
            except Exception as e:
                print(f"Error resuming audio: {e}")

        if message.content.startswith("?stop"):  # Stop music
            try:
                voice_clients[guild_id].stop()
                queues[guild_id] = []  # Clear the queue
                await message.channel.send("Stopped music and cleared the queue.")
            except Exception as e:
                print(f"Error stopping audio: {e}")

        if message.content.startswith("?dc"):  # Disconnect bot
            try:
                await voice_clients[guild_id].disconnect()
                del voice_clients[guild_id]
                if guild_id in queues:
                    del queues[guild_id]  # Clear the queue for this guild
            except Exception as e:
                print(f"Error disconnecting: {e}")

        if message.content.startswith("?skip"):  # Skip to the next song
            try:
                if voice_clients[guild_id].is_playing():
                    voice_clients[guild_id].stop()  # Stop the current song to trigger play_next_song
                    await message.channel.send("Skipped to the next song.")
                else:
                    await message.channel.send("No song is currently playing.")
            except Exception as e:
                print(f"Error skipping song: {e}")

        if message.content.startswith("?queue"):  # Show the song queue
            try:
                if guild_id in queues and queues[guild_id]:
                    queue_list = "\n".join([f"{idx+1}. {song['title']}" for idx, song in enumerate(queues[guild_id])])
                    await message.channel.send(f"**Current Queue:**\n{queue_list}")
                else:
                    await message.channel.send("The queue is empty.")
            except Exception as e:
                print(f"Error showing queue: {e}")

        if message.content.startswith("?clear"): # Clear the queue
            try:
                queues[guild_id] = []  # Clear the queue
                await message.channel.send("Cleared the queue.")
            except Exception as e:
                print(f"Error clearing queue: {e}")

        if message.content.startswith("?shuffle"): # Shuffle the queue
            try:
                if guild_id in queues and queues[guild_id]:
                    random.shuffle(queues[guild_id])
                    await message.channel.send("Queue has been shuffled.")
                else:
                    await message.channel.send("The queue is empty.")
            except Exception as e:
                print(f"Error shuffling queue: {e}")

        if message.content.startswith("?help"):  # Help command
            commands = """
        **Music Bot Commands:**
        - `?play <YouTube URL>`: Play music from the given URL.
        - `?pause`: Pause the current track.
        - `?resume`: Resume the paused track.
        - `?stop`: Stop the current track and clear the queue.
        - `?skip`: Skip to the next song in the queue.
        - `?queue`: Display the current song queue.
        - `?dc`: Disconnect the bot from the voice channel.
        **Other Commands:**
        - `?gunblade`: I MISS YOU.
        """
            await message.channel.send(commands)

        if message.content.startswith("?gunblade"):# Gunblade Command
            try:
                image_path = "gunblade.png"  # Path to your local image file
                if os.path.exists(image_path):
                    await message.channel.send(file=discord.File(image_path))
                    await message.channel.send("WE ALL MISS YOU GUNBLADE")
                else:
                    await message.channel.send("The image file could not be found.")
            except Exception as e:
                print(f"Error sending image: {e}")
                await message.channel.send("An error occurred while sending the image.")

    client.run(TOKEN)
