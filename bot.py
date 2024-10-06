import discord
from discord import app_commands
from discord.ext import commands, tasks
from mcstatus import JavaServer
import os
import json
import asyncio
import time

# Replace with your bot's token
if os.path.exists("token.txt"):
    with open("token.txt", 'r') as f:
        TOKEN = f.readline()
else:
    print("Couldn't find file token.txt")
    TOKEN = input("Please paste your Discord bot's token: ")
    f2 = open("token.txt", "w")
    f2.write(TOKEN)
    f2.close()

# Intents and bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

data_file = 'data.json'

# Load existing data or create an empty dict if file does not exist
if os.path.exists(data_file):
    with open(data_file, 'r') as f:
        data = json.load(f)
else:
    data = {}
    with open(data_file, 'w') as f:
        json.dump(data, f, indent=4)

def save_data():
    with open(data_file, 'w') as f:
        json.dump(data, f, indent=4)

def load_data():
    global data
    with open(data_file, 'r') as f:
        data = json.load(f)

async def delete_message(guild_id: int, channel_id: int, message_id: int):
    guild = bot.get_guild(int(guild_id))  # Fetch the guild
    if guild is None:
        print("Guild not found.")
        return

    channel = guild.get_channel(channel_id)  # Fetch the channel
    if channel is None:
        print("Channel not found.")
        return

    try:
        message = await channel.fetch_message(message_id)  # Fetch the message
        await message.delete()  # Delete the message
        print(f"Message {message_id} deleted successfully.")
    except discord.NotFound:
        print("Message not found.")
    except discord.Forbidden:
        print("You do not have permission to delete this message.")
    except discord.HTTPException as e:
        print(f"Failed to delete message: {e}")


# Define the /config hostname:port slash command with role restriction
@bot.tree.command(name="config", description="Config command")
async def config(interaction: discord.Interaction, hostname: str, port: str):
    role_name = "szyszka"
    is_admin = interaction.user.guild_permissions.administrator
    # Check if user has the required role
    user_roles = [role.name for role in interaction.user.roles]
    if role_name in user_roles or is_admin:
        # Save hostname and port in data.json with guild ID as key
        guild_id = str(interaction.guild.id)
        data[guild_id] = {"hostname": hostname, "port": port}
        
        # Write updated data back to the file
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=4)

        await interaction.response.send_message(f"Server config set to {hostname}:{port} for this guild.", ephemeral=True)
    else:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

@tasks.loop(seconds=15)
async def update_status_message(guild, channel, message_id):
    try:
        guild_id = str(guild.id)
        if guild_id not in data:
            return

        hostname = data[guild_id]["hostname"]
        port = data[guild_id]["port"]

        server = JavaServer.lookup(f"{hostname}:{port}")
        status = server.status()
        response = f"Last update: <t:{int(time.time())}:R>\n```ansi\n[2;40m[0m[0;2m[0;32m[0m[0;2m[0;32m{hostname}[0m:[0;35m{port}[0m"
        response += f"\nThe server has {status.players.online} player(s) online.\n"
        if status.players.sample:
            player_names = ', '.join([player.name for player in status.players.sample])
            response += f"Players online: {player_names}"
        else:
            response += "No player data available."

        #latency = server.ping()
        #response += f"\nLatency: {latency} ms"
        response += f"\n```"

        # Fetch the message and edit it
        channel = bot.get_channel(channel.id)
        message = await channel.fetch_message(message_id)
        await message.edit(content=response)

    except Exception as e:
        print(f"Error updating status message: {str(e)}")


@bot.tree.command(name="createstatusboard", description="Create and update server status board")
async def createstatusboard(interaction: discord.Interaction):
    role_name = "szyszka"
    is_admin = interaction.user.guild_permissions.administrator
    # Check if user has the required role
    user_roles = [role.name for role in interaction.user.roles]
    if role_name in user_roles or is_admin:
        guild_id = str(interaction.guild.id)

        if guild_id not in data:
            await interaction.response.send_message("No server configuration found. Please use the `/config` command to set the server details.", ephemeral=True)
            return
        
        # Stop the current task if it's running
        if update_status_message.is_running():
            await interaction.response.send_message("Status board already exists, remove it first.", ephemeral=False)
            return 0

        hostname = data[guild_id]["hostname"]
        port = data[guild_id]["port"]

        await interaction.response.send_message("Creating status board...", ephemeral=False)

        try:
            server = JavaServer.lookup(f"{hostname}:{port}")
            status = server.status()
            response = f"Last update: <t:{int(time.time())}:R>\n```ansi\n[2;40m[0m[0;2m[0;32m[0m[0;2m[0;32m{hostname}[0m:[0;35m{port}[0m"
            response += f"\nThe server has {status.players.online} player(s) online.\n"
            #response = f"``` The server has {status.players.online} player(s) online and replied in {status.latency} ms\n"
            response += f"\n```"
            message = await interaction.followup.send(response)

            # Save the message ID and guild data
            message_id = message.id
            data[guild_id]["status_message_id"] = message_id
            data[guild_id]["channel_id"] = interaction.channel_id

            # Save data persistently
            save_data()

            # Start the task again
            update_status_message.start(interaction.guild, interaction.channel, message_id)

        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    else:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

@bot.tree.command(name="rmstatusboard", description="Removes server status board")
async def rmstatusboard(interaction: discord.Interaction):
    role_name = "szyszka"
    is_admin = interaction.user.guild_permissions.administrator
    # Check if user has the required role
    user_roles = [role.name for role in interaction.user.roles]
    if role_name in user_roles or is_admin:
        guild_id = str(interaction.guild.id)

        if guild_id not in data:
            await interaction.response.send_message("No server configuration found. Please use the `/config` command to set the server details.", ephemeral=True)
            return
        
        # Stop the current task if it's running
        if update_status_message.is_running():
            update_status_message.cancel()
            bot.loop.create_task(delete_message(guild_id, data[guild_id]["channel_id"], data[guild_id]["status_message_id"]))
            data[guild_id].pop("channel_id")
            data[guild_id].pop("status_message_id")
            # Save data persistently
            save_data()
            await interaction.response.send_message("Status board has been removed", ephemeral=False)
            return 0

@bot.tree.command(name="status", description="Check the Minecraft server status")
async def status(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)

    # Check if the guild has a config in data.json
    if guild_id not in data:
        await interaction.response.send_message("No server configuration found. Please use the `/config` command to set the server details.", ephemeral=True)
        return

    # Defer the response immediately to avoid the "application did not respond" issue
    await interaction.response.defer()

    # Get the server details from the config
    hostname = data[guild_id]["hostname"]
    port = data[guild_id]["port"]

    try:
        # Use asyncio.to_thread to run the blocking server.status() in a separate thread
        server = JavaServer.lookup(f"{hostname}:{port}")

        # Use asyncio.wait_for with asyncio.to_thread to enforce a 5-second timeout
        status = await asyncio.wait_for(asyncio.to_thread(server.status), timeout=5)

        # Prepare the response based on the server status
        response = (f"The server has {status.players.online} player(s) online and replied in {int(status.latency)} ms\n")

        if status.players.sample:
            player_names = ', '.join([player.name for player in status.players.sample])
            response += f"Players online: {player_names}"
        else:
            response += "No player data available."

        # Optionally include ping (run in a separate thread as well)
        #latency = await asyncio.to_thread(server.ping)
        #response += f"\nLatency: {int(latency)} ms"

        # Send the follow-up response
        await interaction.followup.send(response)

    except asyncio.TimeoutError:
        # Handle case when the status retrieval takes longer than 5 seconds
        await interaction.followup.send("The server is offline or took too long to respond (5-second timeout).")
        
    except (TimeoutError, ConnectionRefusedError):
        # Handle the case when the server is offline or unreachable
        await interaction.followup.send("The server is offline or unreachable. Please check if the server is running.")
        
    except Exception as e:
        # General exception handling
        await interaction.followup.send(f"Failed to retrieve server status: {str(e)}")



# Define the /ping slash command with role restriction
@bot.tree.command(name="ping", description="Ping command")
async def ping(interaction: discord.Interaction):
    role_name = "szyszka"
    
    # Check if user has the required role
    user_roles = [role.name for role in interaction.user.roles]
    if role_name in user_roles:
        await interaction.response.send_message("pong")
    else:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

# Event to resume updating status message on bot restart
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync()  # Sync globally when the bot is ready

    # Resume updating the status message if a message ID is saved
    for guild_id in data:
        guild_data = data[guild_id]
        if "status_message_id" in guild_data and "channel_id" in guild_data:
            guild = bot.get_guild(int(guild_id))
            channel = bot.get_channel(guild_data["channel_id"])
            message_id = guild_data["status_message_id"]

            # Start the update loop for the saved message
            update_status_message.start(guild, channel, message_id)

# Run the bot
bot.run(TOKEN)
