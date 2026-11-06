import os
import json
import random
import time
import urllib.request
import pymysql

# --- CONFIGURATION (Uses Environment Variables for Security) ---
OSTICKET_API_URL = os.getenv("OSTICKET_API_URL", "http://127.0.0.1/osticket/api/tickets.json")
OSTICKET_API_KEY = os.getenv("OSTICKET_API_KEY", "YOUR_OSTICKET_API_KEY_HERE")

# MySQL Database Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "YOUR_DB_PASSWORD_HERE")
DB_NAME = os.getenv("DB_NAME", "osticket_db")

# KoboldCPP OpenAI-Compatible Local Endpoint
KOBOLD_CHAT_URL = os.getenv("KOBOLD_CHAT_URL", "http://localhost:5001/v1/chat/completions")

# --- RANDOMIZATION POOLS ---
USER_NAMES = [
    "Alex Rivera",
    "Jordan Lee",
    "Morgan Smith",
    "Carlos Vance",
    "Samantha Hayes",
    "David Chen",
    "Elena Rostova",
    "Marcus Vance",
]

PERSONALITIES = [
    "impatient and very anxious about deadlines",
    "extremely polite, patient, and apologetic",
    "non-technical and easily confused by jargon",
    "tech-savvy, direct, and concise",
    "frustrated and slightly sarcastic but willing to cooperate",
    "overly detailed, describing every little step",
]


def get_db_connection():
    """Establishes a connection to the osTicket MySQL database."""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
    )


def generate_random_user():
    """Generates a random persona with a name, email, and personality trait for startup ticket creation."""
    name = random.choice(USER_NAMES)
    email_name = name.lower().replace(" ", ".")
    email = f"{email_name}@domain.com"
    personality = random.choice(PERSONALITIES)
    return {"name": name, "email": email, "personality": personality}


def generate_random_issue(user_profile):
    """Asks Kobold AI to invent a fresh, random IT support issue tailored to the startup user's personality."""
    topics = [
        "VPN connection drops every 10 minutes",
        "Outlook crashes whenever opening attachments",
        "Company printer is offline and not responding to jobs",
        "Excel keeps freezing on large spreadsheets",
        "Password expired and the self-service portal is throwing a 500 error",
    ]
    chosen_topic = random.choice(topics)

    payload = {
        "model": "local-gguv",
        "messages": [
            {
                "role": "system",
                "content": (
                    f"You are an AI generating a realistic initial help desk ticket message for an employee "
                    f"named {user_profile['name']}. Your personality is: {user_profile['personality']}. "
                    "Write a short, natural 1-2 sentence problem description as the client."
                ),
            },
            {
                "role": "user",
                "content": f"Generate a short initial ticket message about: {chosen_topic}",
            },
        ],
        "temperature": 0.8,
    }

    req = urllib.request.Request(
        KOBOLD_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            message = data["choices"][0]["message"]["content"].strip()
            return chosen_topic, message
    except Exception:
        return (
            chosen_topic,
            f"Hello, I am having trouble with {chosen_topic} today. Can you help?",
        )


def create_initial_ticket(user_profile, subject, message):
    """Creates the starting ticket in osTicket via the REST API."""
    payload = {
        "name": user_profile["name"],
        "email": user_profile["email"],
        "subject": subject,
        "message": message,
        "ip": "127.0.0.1",
    }

    req = urllib.request.Request(
        OSTICKET_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-API-Key": OSTICKET_API_KEY,
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req) as response:
            print(
                f"[+] Initial ticket created for {user_profile['name']} ({user_profile['personality']})!"
            )
    except urllib.error.HTTPError as e:
        print(
            f"[-] Failed to create ticket: {e.code} - {e.read().decode('utf-8')}"
        )


def ask_kobold(conversation_history):
    """Sends conversation history to local KoboldCPP using the OpenAI-compatible endpoint."""
    payload = {
        "model": "local-gguv",
        "messages": conversation_history,
        "temperature": 0.7,
        "max_tokens": 150,
    }

    req = urllib.request.Request(
        KOBOLD_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    print("[*] Bridging: Waiting for LLM client to reply to the IT agent...")
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            reply = data["choices"][0]["message"]["content"]

            reply = reply.replace("```json", "").replace("```", "").strip()
            if "Option 1" in reply:
                reply = reply.split("Option 1")[-1].replace(":", "").strip()

            print("[+] Generated response successfully!")
            return reply
    except Exception as e:
        print(f"[-] Error communicating with KoboldCPP: {e}")
        return "Thank you for the update. Let me test that right now."


def get_all_open_tickets_needing_response():
    """
    Queries MySQL for all open tickets where the last entry in the thread is from an IT agent.
    Joins with ost_user to pull the EXACT user_name tied to each ticket_id.
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query = """
                SELECT 
                    t.ticket_id, 
                    th.id AS thread_id, 
                    max_entry.id AS entry_id, 
                    max_entry.body AS agent_body,
                    u.name AS user_name
                FROM ost_ticket t
                JOIN ost_user u ON u.id = t.user_id
                JOIN ost_thread th ON th.object_id = t.ticket_id AND th.object_type = 'T'
                JOIN (
                    SELECT thread_id, MAX(id) AS max_id 
                    FROM ost_thread_entry 
                    GROUP BY thread_id
                ) latest ON th.id = latest.thread_id
                JOIN ost_thread_entry max_entry ON max_entry.id = latest.max_id
                WHERE max_entry.staff_id > 0 
                  AND t.status_id = 1;
            """
            cursor.execute(query)
            return cursor.fetchall()
    finally:
        connection.close()


def get_full_thread_history(ticket_id, user_name):
    """
    Fetches full thread history for a specific ticket_id.
    Captures the FIRST message (initial ticket submission) from the database to 
    extract the original problem context, ensuring Kobold AI roleplays as that specific user.
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query = """
                SELECT te.body, te.staff_id, te.poster 
                FROM ost_ticket t
                JOIN ost_thread th ON th.object_id = t.ticket_id AND th.object_type = 'T'
                JOIN ost_thread_entry te ON te.thread_id = th.id
                WHERE t.ticket_id = %s
                ORDER BY te.id ASC;
            """
            cursor.execute(query, (ticket_id,))
            entries = cursor.fetchall()

            if not entries:
                return []

            # Extract initial problem statement from the very first thread entry
            initial_issue = (
                entries[0]["body"]
                .replace("<p>", "")
                .replace("</p>", "")
                .strip()
            )

            # Build system prompt dynamically locked to THIS ticket's user name and problem context
            chat_history = [
                {
                    "role": "system",
                    "content": (
                        f"You are roleplaying strictly as the end-user named {user_name}. "
                        f"You opened this support ticket regarding: '{initial_issue}'. "
                        "You are the client/customer seeking help, NOT the IT support agent. "
                        "Reply naturally to the IT agent's latest message, staying in character. "
                        "CRITICAL RULE: Output ONLY your single, direct response line as the client. "
                        "Do NOT output prefixes like 'User:', 'Client:', or extra options."
                    ),
                }
            ]

            for entry in entries:
                clean_body = (
                    entry["body"]
                    .replace("<p>", "")
                    .replace("</p>", "")
                    .strip()
                )
                if entry["staff_id"] and entry["staff_id"] > 0:
                    chat_history.append({"role": "user", "content": clean_body})
                else:
                    chat_history.append(
                        {"role": "assistant", "content": clean_body}
                    )

            return chat_history
    finally:
        connection.close()


def add_user_reply_to_db(ticket_id, poster_name, reply_message):
    """Injects the counter-response directly into the ticket thread with the correct user poster name."""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                    SELECT th.id AS thread_id 
                    FROM ost_ticket t
                    JOIN ost_thread th ON th.object_id = t.ticket_id AND th.object_type = 'T'
                    WHERE t.ticket_id = %s
                """,
                (ticket_id,),
            )
            row = cursor.fetchone()
            if not row:
                return
            thread_id = row["thread_id"]

            insert_query = """
                INSERT INTO ost_thread_entry (thread_id, type, poster, body, source, created, updated)
                VALUES (%s, 'M', %s, %s, 'API', NOW(), NOW())
            """
            cursor.execute(
                insert_query,
                (thread_id, f"{poster_name} (Client)", reply_message),
            )
            connection.commit()
            print(
                f"[+] Reply from {poster_name} successfully injected into Ticket #{ticket_id}!"
            )
    finally:
        connection.close()


# --- MAIN EXECUTION LOOP ---
if __name__ == "__main__":
    print("[*] Starting Dynamic Persona Multi-Ticket AI Simulator...")

    # 1. Create a brand-new random user ticket on startup
    startup_user = generate_random_user()
    print(
        f"[*] Startup Ticket Persona Created: {startup_user['name']} | Personality: {startup_user['personality']}"
    )

    subject, initial_message = generate_random_issue(startup_user)
    print(f"[+] Generated Startup Issue: {subject} -> '{initial_message}'")
    create_initial_ticket(startup_user, subject, initial_message)

    last_seen_entry_per_thread = {}

    print("\n[*] Monitoring osTicket database for agent replies...\n")

    # Initial state sync to ignore already processed historical entries
    try:
        initial_open_tickets = get_all_open_tickets_needing_response()
        for row in initial_open_tickets:
            last_seen_entry_per_thread[row["ticket_id"]] = row["entry_id"]
    except Exception as e:
        print(f"[-] Warning during initial state sync: {e}")

    # 2. Continuous Monitoring Loop
    while True:
        try:
            open_tickets = get_all_open_tickets_needing_response()

            for row in open_tickets:
                ticket_id = row["ticket_id"]
                entry_id = row["entry_id"]
                exact_user_name = row["user_name"]  # Fetched directly from DB for THIS ticket ID

                if last_seen_entry_per_thread.get(ticket_id) != entry_id:
                    last_seen_entry_per_thread[ticket_id] = entry_id

                    cleaned_agent_msg = (
                        row["agent_body"]
                        .replace("<p>", "")
                        .replace("</p>", "")
                        .strip()
                    )
                    print(
                        f"\n[!] Agent replied on Ticket #{ticket_id} ({exact_user_name}): {cleaned_agent_msg}"
                    )

                    # Build context strictly from THIS ticket's thread & user identity
                    chat_history = get_full_thread_history(
                        ticket_id=ticket_id, 
                        user_name=exact_user_name
                    )

                    # Ask Kobold to generate reply matching THIS ticket's owner
                    ai_response = ask_kobold(chat_history)

                    # Post back under THAT specific user's name
                    add_user_reply_to_db(
                        ticket_id=ticket_id, 
                        poster_name=exact_user_name, 
                        reply_message=ai_response
                    )

        except Exception as e:
            print(f"[-] Error in polling loop: {e}")

        time.sleep(5)
