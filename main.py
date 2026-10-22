import discord
from discord import app_commands
from dotenv import load_dotenv
import os
import requests
import time
import sqlite3
from datetime import datetime, timedelta
import json

load_dotenv()

intents = discord.Intents.default()

client = discord.Client(intents=intents)

tree = app_commands.CommandTree(client)

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

thread = ""

@client.event
async def on_ready():
    await tree.sync()
    print(f'We have logged in as {client.user}')
    await get_new_problem()

@tree.command(name="connect", description="Connect your LeetCode account")
@app_commands.describe(username="Your LeetCode username")
async def connect(interaction: discord.Interaction, username: str):
    await interaction.response.defer(thinking=True)
    user = interaction.user

    user_id = user.id
    name = user.display_name

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (id, name, username, problems_solved) VALUES (?, ?, ?, ?)",
        (user_id, name, username, 0)
    )
    conn.commit()
    conn.close()
    await interaction.response.send_message("Connected!", ephemeral=True)

@tree.command(name="submit", description="Submit a LeetCode solution")
async def submit(interaction: discord.Interaction):
    if interaction.channel != channel:
        await interaction.response.send_message("This command needs to be run in a specific problem thread!", ephemeral=True)
        return
    else:
        if not (isinstance(interaction.channel, discord.Thread)):
            await interaction.response.send_message("This command needs to be run in a specific problem thread!", ephemeral=True)
            return
        
        else:
            if interaction.channel.id != thread.id:
                await interaction.response.send_message("Too late! This is not today's problem.", ephemeral=True)
                return

    await interaction.response.defer(thinking=True)
    user = interaction.user
    user_id = user.id

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    query = "SELECT username FROM users WHERE id = ?"
    cursor.execute(query, (user_id,))

    row = cursor.fetchone()

    query = "SELECT thread_id FROM problems WHERE id = ?"
    cursor.execute(query, (thread.id,))

    todays_problem = cursor.fetchone()

    conn.close()

    if row is None:
        await interaction.response.send_message("Use the connect command to connect your LeetCode account", ephemeral=True)
        return
    elif user_id in todays_problem['users_solved']:
        await interaction.response.send_message("Congrats! You've already solved this problem.", ephemeral=True)
        return
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

        problems = solved_problems.data.recentAcSubmissionList

        data = json.loads(problems)

        if any(obj.get("titleSlug") == todays_problem['problem_id'] for obj in data):
            users_query = """
            UPDATE users
            SET problems_solved = ?
            WHERE id = ?
            """
            
            problems_query = """
            UPDATE problems
            SET users_solved = ?
            WHERE id = ?
            """
            
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()

            cursor.execute(users_query, (row['problems_solved']+1, user_id))

            conn.commit()

            if todays_problem['users_solved'] is None:
                cursor.execute(problems_query, (f"{user_id}, ", thread.id))
            else:
                cursor.execute(problems_query, (f"{todays_problem['users_solved']}{user_id}, ", thread.id))

            await interaction.response.send_message("Problem submitted!", ephemeral=True)
        else:
            await interaction.response.send_message("You have not yet solved today's problem. Get to it!", ephemeral=True)

async def send_new_problem(problem):
    global thread

    question_info = problem.data.activeDailyCodingChallengeQuestion.question
    thread = await channel.create_thread(name=(f"Discussion: {question_info.title}"))
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO problems (thread_id, problem_id, users_solved) VALUES (?, ?, ?)",
        (thread.id, question_info.titleSlug, None)
    )
    conn.commit()
    conn.close()

    await thread.send(f"📌 LeetCode Daily Challenge: {question_info.questionFrontendId}. {question_info.title} ({question_info.difficulty}) \n🔗 https://leetcode.com/problems/{question_info.titleSlug}")
    await thread.send("Discuss your solutions here! 🧠💡")

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
            hour=0, minute=1, second=0, microsecond=0
        )

        if target <= now:
            target += timedelta(days=1)

        seconds_to_wait = (target - now).total_seconds()

        if daily_problem == "":
            await poll()

        time.sleep(seconds_to_wait)

        await poll()

client.run(os.getenv('TOKEN'))