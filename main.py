import discord
from dotenv import load_dotenv
import os
import requests
import time
import sqlite3
from datetime import datetime, timedelta
import json

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

url = "https://leetcode.com/graphql"

body = """
query getDailyProblem {
  activeDailyCodingChallengeQuestion {
    date
    link
    question {
      questionFrontendId
      title
      titleSlug
      difficulty
    }
  }
}
"""

daily_problem = ""

channel = client.get_channel(1562544963965947986)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    await get_new_problem()

@client.tree.command(name="connect", description="Connect your LeetCode account")
@app_commands.describe(username="Your LeetCode username")
async def connect(interaction: discord.Interaction, username: string):
    await interaction.response.defer(thinking=True)
    user = interaction.user

    user_id = user.id
    name = user.display_name

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (id, name, username) VALUES (?, ?, ?)",
        (user_id, name, username)
    )
    conn.commit()
    conn.close()
    await interaction.response.send_message("Connected!", ephemeral=True)

@client.tree.command(name="submit", description="Submit a LeetCode solution")
async def submit(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    user = interaction.user
    user_id = user.id

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    query = "SELECT username FROM users WHERE id = ?"
    cursor.execute(query, (user_id,))

    row = cursor.fetchone()

    conn.close()

    if row is None:
        await interaction.response.send_message("Use the connect command to connect your LeetCode account", ephemeral=True)
    else:
        leetcode_query = """
        query 
            recentAcSubmissions($username: String!, $limit: Int!) {
                recentAcSubmissionList(username: $username, limit: $limit) {
                id    
                title    
                titleSlug    
                timestamp  
            }
        }
        """

        payload = {
            "query": leetcode_query,
            "variables": {
                "username": row['username'],
                "limit": 25
            }
        }

        while True:
            response = requests.get(url=url, json=payload)

            if response.status_code == 200:
                solved_problems = response.content
                break
                    
            else:
                time.sleep(3)

        if 

        await interaction.response.send_message("Connected!", ephemeral=True)

async def check_submission()

async def send_new_problem(problem):
    await channel.send(problem)

async def poll():
    global daily_problem

    while True:
        response = requests.get(url=url, json={"query": body})

        if response.status_code == 200:
            daily_problem = response.content
            await send_new_problem(daily_problem)
            break
                
        else:
            time.sleep(3)

async def get_new_problem():
    while True:
        now = datetime.now()

        target = now.replace(
            hour=0, minute=1, secound=0, microsecound=0
        )

        if target <= now:
            target += timedelta(days=1)

        secounds_to_wait = (target - now).total_secounds()

        if daily_problem == "":
            poll()

        time.sleep(secounds_to_wait)

        poll()

client.run(os.getenv('TOKEN'))