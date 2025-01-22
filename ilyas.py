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

    looping_state = {}  # Dictionary to track looping state for each guild

    async def play_next_song(guild_id):
        """Plays the next song in the queue or loops the current song."""
        if guild_id in looping_state and looping_state[guild_id]:  # Check if looping is enabled
            # If looping is enabled, replay the current song
            if queues[guild_id]:
                song_info = queues[guild_id][0]  # Do not pop, replay the same song
            else:
                return  # No song to loop
        elif queues[guild_id]:  # If not looping, play the next song
            song_info = queues[guild_id].pop(0)  # Get the next song (info dictionary)
        else:  # If the queue is empty and no looping
            return

        song_url = song_info['url']
        song_title = song_info['title']

        try:
            loop = asyncio.get_event_loop()
            player = discord.FFmpegPCMAudio(song_url, **ffmpeg_options)
            voice_clients[guild_id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                play_next_song(guild_id), loop
            ))
            await song_info['message_channel'].send(f"Now playing: **{song_title}**")
        except Exception as e:
            print(f"Error playing audio: {e}")
            await song_info['message_channel'].send("An error occurred while playing the song.")

    @client.event
    async def on_ready():
        print(f'{client.user} has connected to Discord!')

    @client.event
    async def on_message(message):
        guild_id = message.guild.id

        if message.content.startswith("?play"):
            try:
                query = message.content[6:].strip()  # Extract the query (everything after "?play")
                if not query:
                    await message.channel.send("Please provide a song name, YouTube URL, or playlist link.")
                    return

                # Initialize queue if it doesn't exist for this guild
                if guild_id not in queues:
                    queues[guild_id] = []

                # Use yt_dlp to determine if the query is a playlist, single video, or search query
                await message.channel.send(f"Searching for: **{query}**")
                loop = asyncio.get_event_loop()

                if "youtube.com" in query or "youtu.be" in query:
                    # Treat as a YouTube URL or playlist
                    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
                else:
                    # Treat as a search query
                    search_data = await loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch:{query}", download=False))
                    if not search_data['entries']:
                        await message.channel.send("No results found. Please try another query.")
                        return
                    data = search_data['entries'][0]  # Take the first search result

                # Handle playlist or single video
                if 'entries' in data:
                    # Playlist detected
                    await message.channel.send(f"Adding playlist: **{data['title']}** ({len(data['entries'])} songs)")
                    for entry in data['entries']:
                        song_info = {
                            'title': entry['title'],  # Store the title
                            'url': entry['url'],      # Store the streamable URL
                            'message_channel': message.channel
                        }
                        queues[guild_id].append(song_info)
                    await message.channel.send(f"Playlist **{data['title']}** has been added to the queue!")
                else:
                    # Single video
                    song_info = {
                        'title': data['title'],  # Store the title
                        'url': data['url'],      # Store the streamable URL
                        'message_channel': message.channel
                    }
                    queues[guild_id].append(song_info)
                    await message.channel.send(f"**{data['title']}** has been added to the queue!")

                # Connect to the voice channel if not connected
                if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
                    voice_client = await message.author.voice.channel.connect()
                    voice_clients[guild_id] = voice_client

                # Play the song immediately if nothing is playing
                if not voice_clients[guild_id].is_playing():
                    await play_next_song(guild_id)
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

        if message.content.startswith("?loop"):  # Loop the current song

            try:
                # Ensure the queue is initialized for the guild
                if guild_id not in queues:
                    queues[guild_id] = []  # Initialize an empty queue

                # Check if there's a song currently playing or in the queue
                if guild_id in voice_clients and voice_clients[guild_id].is_playing() or queues[guild_id]:
                    if guild_id in looping_state and looping_state[guild_id]:
                        looping_state[guild_id] = False  # Disable looping
                        await message.channel.send("🔁 **Looping disabled for the current song.**")
                        print(f"Queue: {queues[guild_id]}")
                        print(f"Looping state: {looping_state[guild_id]}")
                    else:
                        looping_state[guild_id] = True  # Enable looping
                        await message.channel.send("🔁 **Looping enabled for the current song.**")
                        print(f"Queue: {queues[guild_id]}")
                        print(f"Looping state: {looping_state[guild_id]}")
                else:
                    await message.channel.send("❌ **No song is currently playing or in the queue. Add a song to loop.**")
            except Exception as e:
                print(f"Error toggling looping: {e}")
                await message.channel.send("❌ **An error occurred while toggling looping.**")

        if message.content.startswith("?help"):  # Help command
            commands = """
        **🎵 Music Bot Commands 🎵**
        `?play <YouTube URL>`: Play music from the given URL.
        `?play <Song Name>`: Play music from the given URL.
        `?pause` : Pause the current track.
        `?resume`: Resume the paused track.
        `?stop`  : Stop the current track and clear the queue.
        `?skip`  : Skip to the next song in the queue.
        `?queue` : Display the current song queue.
        `?clear` : Clear the current song queue.
        `?shuffle`: Shuffle the current song queue.
        `?dc`    : Disconnect the bot from the voice channel.

        **🔹 Other Commands 🔹**
        `?gunblade`: I MISS YOU.
        `?heartsteel`: PLUS 1 HEARTSTEEL STACK.
        `?viktor`: VIK TORRRRRRR.
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

        if message.content.startswith("?heartsteel"):  # Play the Heartsteel sound if no song is playing
            try:
                # Ensure the bot is in a voice channel
                if not message.author.voice or not message.author.voice.channel:
                    await message.channel.send("You need to be in a voice channel to use this command.")
                    return

                # Connect to the voice channel if not already connected
                if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
                    voice_client = await message.author.voice.channel.connect()
                    voice_clients[guild_id] = voice_client
                else:
                    voice_client = voice_clients[guild_id]

                # Check if a song is already playing
                if voice_client.is_playing():
                    await message.channel.send("❌ **Cannot play Heartsteel sound while music is playing.**")
                    return

                # Path to the Heartsteel MP3 file
                heartsteel_path = "heartsteel.mp3"
                if not os.path.exists(heartsteel_path):
                    await message.channel.send("❌ **The Heartsteel sound file could not be found.**")
                    return

                # Play the Heartsteel sound
                def after_heartsteel(error):
                    print("Heartsteel sound playback complete.")

                player = discord.FFmpegPCMAudio(heartsteel_path)
                voice_client.play(player, after=after_heartsteel)

                await message.channel.send("🔊 **PLUS 1 HEARTSTEEL STACK!**")

            except Exception as e:
                print(f"Error playing the Heartsteel sound: {e}")
                await message.channel.send("❌ **An error occurred while playing the sound.**")

        if message.content.startswith("?viktor"):  # Play the Viktor sound if no song is playing
            try:
                # Ensure the bot is in a voice channel
                if not message.author.voice or not message.author.voice.channel:
                    await message.channel.send("You need to be in a voice channel to use this command.")
                    return

                # Connect to the voice channel if not already connected
                if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
                    voice_client = await message.author.voice.channel.connect()
                    voice_clients[guild_id] = voice_client
                else:
                    voice_client = voice_clients[guild_id]

                # Check if a song is already playing
                if voice_client.is_playing():
                    await message.channel.send("❌ **Cannot play Viktor sound while music is playing.**")
                    return

                # Path to the Viktor MP3 file
                viktor_path = "viktor.mp3"
                if not os.path.exists(viktor_path):
                    await message.channel.send("❌ **The Viktor sound file could not be found.**")
                    return

                # Play the Viktor sound
                def after_viktor(error):
                    print("Viktor sound playback complete.")

                player = discord.FFmpegPCMAudio(viktor_path)
                voice_client.play(player, after=after_viktor)

                await message.channel.send("VIK TOR VIKTOOORRRRR")

            except Exception as e:
                print(f"Error playing the Viktor sound: {e}")
                await message.channel.send("❌ **An error occurred while playing the sound.**")


    client.run(TOKEN)
