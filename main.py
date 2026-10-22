import discord
from discord import app_commands
from dotenv import load_dotenv
import os
import requests
import time
import sqlite3
from datetime import datetime, timedelta, timezone
import json
import asyncio

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

channel = ""

thread = ""

poll_task = None

@client.event
async def on_ready():
    global channel, poll_task

    channel = client.get_channel(1562544963965947986)

    await tree.sync()
    print(f'We have logged in as {client.user}')

    if poll_task is None or poll_task.done():
        poll_task = asyncio.create_task(get_new_problem())

@tree.command(name="resources", description="View helpful LeetCode resources.")
async def resources(interaction: discord.Interaction):
    await interaction.response.send_message("""
📚 Helpful LeetCode Resources 📚

1. [NeetCode](<https://neetcode.io/practice>) - Curated list of problems.
2. [Neetcode Youtube](<https://www.youtube.com/c/neetcode>) - YouTube channel with problem walkthroughs.
3. [LeetCode Patterns](<https://seanprashad.com/leetcode-patterns/>) - Patterns and problem-solving strategies.
4. [Grind 75](<https://www.techinterviewhandbook.org/grind75/>) - Blind 75 with a custom study plan timeframe.
Happy coding! 🚀
    """)

@tree.command(name="help", description="Display the help message.")
async def help(interaction: discord.Interaction):
    await interaction.response.send_message("""
📌 **LeetCode Bot Commands** 📌

🧑‍💻 `/submit` — Submit your solution in a discussion thread.
🔗 `/connect` — Connect your LeetCode account, required to submit!
🏆 `/leaderboard` — Display the top 10 LeetCoders!
📚 `/resources` — View helpful LeetCode resources.
💡 `/help` — Display this help message.

🚀 Every day at midnight UTC, a new LeetCode Daily Challenge is posted in #leetcode-bootcamp!
    """)

@tree.command(name="leaderboard", description="Display the leaderboard")
async def leaderboard(interaction: discord.Interaction):
    conn = sqlite3.connect('./data/database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT name, problems_solved FROM users")
    all_users = cursor.fetchall()

    conn.close()

    if not all_users:
        await interaction.response.send_message("Get to it! No one has solved anything!")
        return

    sorted_users = sorted(all_users, key=lambda x: x[1], reverse=True)
    
    output = ""

    amount = min(len(sorted_users), 10)

    for i in range(amount):
        user = sorted_users[i]
        if user[1] == 0:
            continue
        elif user[1] == 1:
            output += f"**{i+1}. {user[0]}**\n- {user[1]} problem solved\n"
        else:
            output += f"**{i+1}. {user[0]}**\n- {user[1]} problems solved\n"

    await interaction.response.send_message(output)

@tree.command(name="connect", description="Connect your LeetCode account")
@app_commands.describe(username="Your LeetCode username")
async def connect(interaction: discord.Interaction, username: str):
    user = interaction.user

    user_id = user.id
    name = user.display_name

    conn = sqlite3.connect('./data/database.db')
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO users (id, name, username, problems_solved) 
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            username = excluded.username
        """,
        (user_id, name, username, 0)
    )
    conn.commit()
    conn.close()
    await interaction.response.send_message("Connected!", ephemeral=True)

@tree.command(name="submit", description="Submit a LeetCode solution")
async def submit(interaction: discord.Interaction):
    if not (isinstance(interaction.channel, discord.Thread)):
        await interaction.response.send_message("This command needs to be run in a specific problem thread!", ephemeral=True)
        return

    if interaction.channel.parent_id != channel.id:
        await interaction.response.send_message("This command needs to be run in a specific problem thread!", ephemeral=True)
        return
        
    if interaction.channel.id != thread.id:
        await interaction.response.send_message("Too late! This is not today's problem.", ephemeral=True)
        return

    user = interaction.user
    user_id = user.id

    conn = sqlite3.connect('./data/database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT username, problems_solved FROM users WHERE id = ?"
    cursor.execute(query, (user_id,))

    row = cursor.fetchone()

    query = "SELECT problem_id, users_solved FROM problems WHERE thread_id = ?"
    cursor.execute(query, (thread.id,))

    todays_problem = cursor.fetchone()

    conn.close()

    if row is None:
        await interaction.response.send_message("Use the connect command to connect your LeetCode account", ephemeral=True)
        return

    if todays_problem is None:
        await interaction.response.send_message("Today's problem could not be found!", ephemeral=True)
        return

    elif todays_problem['users_solved'] != None:
        user_list = todays_problem['users_solved'].split(",")
        seen = False
        for user in user_list:
            if user.strip() == str(user_id):
                seen = True
        
        if seen:
            await interaction.response.send_message("Congrats! You've already solved this problem.", ephemeral=True)
            return

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
        response = await asyncio.to_thread(
            requests.post,
            url=url, 
            json=payload, 
            timeout=10
        )

        if response.status_code == 200:
            solved_problems = response.json()
            break
                
        else:
            await asyncio.sleep(3)

    data = solved_problems["data"]["recentAcSubmissionList"]

    challenge_date = daily_problem["data"]["activeDailyCodingChallengeQuestion"]["date"]

    if any(obj.get("titleSlug") == todays_problem['problem_id'] and datetime.fromtimestamp(int(obj["timestamp"]), timezone.utc).date().isoformat() == challenge_date for obj in data):

        users_query = """
        UPDATE users
        SET problems_solved = ?
        WHERE id = ?
        """
        
        problems_query = """
        UPDATE problems
        SET users_solved = ?
        WHERE thread_id = ?
        """
        
        conn = sqlite3.connect('./data/database.db')
        cursor = conn.cursor()

        cursor.execute(users_query, (row['problems_solved']+1, user_id))

        if todays_problem['users_solved'] is None:
            cursor.execute(problems_query, (f"{user_id}, ", thread.id))
        else:
            cursor.execute(problems_query, (f"{todays_problem['users_solved']}{user_id}, ", thread.id))
        
        conn.commit()
        conn.close()

        await interaction.response.send_message("Problem submitted!", ephemeral=True)

    else:
        await interaction.response.send_message("You have not yet solved today's problem. Get to it!", ephemeral=True)

async def send_new_problem(problem):
    global thread

    question_info = problem["data"]["activeDailyCodingChallengeQuestion"]["question"]
    
    message = await channel.send(f"📌 **LeetCode Daily Challenge:** {question_info["questionFrontendId"]}. {question_info["title"]} ({question_info["difficulty"]}) \n🔗 https://leetcode.com/problems/{question_info["titleSlug"]}")
    
    thread = await message.create_thread(name=f"Discussion: {question_info["title"]}")
    
    conn = sqlite3.connect('./data/database.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO problems (thread_id, problem_id, users_solved) VALUES (?, ?, ?)",
        (thread.id, question_info["titleSlug"], None)
    )
    conn.commit()
    conn.close()

    await thread.send("Discuss your solutions here! 🧠💡")

async def poll():
    global daily_problem, thread

    while True:
        response = await asyncio.to_thread(
            requests.post,
            url=url,
            json={"query": body},
            timeout=10
        )

        if response.status_code == 200:
            daily_problem = response.json()

            conn = sqlite3.connect('./data/database.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM problems WHERE problem_id = ? LIMIT 1"
            cursor.execute(query, (daily_problem["data"]["activeDailyCodingChallengeQuestion"]["question"]["titleSlug"],))

            row = cursor.fetchone()

            conn.close()

            if row == None:
                await send_new_problem(daily_problem)
            else:
                thread = await client.fetch_channel(row["thread_id"])
            break
                
        else:
            await asyncio.sleep(3)

async def get_new_problem():
    while True:
        now = datetime.now(timezone.utc)

        target = now.replace(
            hour=0, minute=1, second=0, microsecond=0
        )

        if target <= now:
            target += timedelta(days=1)

        seconds_to_wait = (target - now).total_seconds()

        if daily_problem == "":
            await poll()

        await asyncio.sleep(seconds_to_wait)

        await poll()

client.run(os.getenv('TOKEN'))