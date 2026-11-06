# osTicket AI-Powered Help Desk Simulator

An automated IT Help Desk simulation system that bridges an **osTicket** installation with a local LLM (**KoboldCPP**) using a custom **Python intermediary**. 

The system continuously monitors osTicket for new agent replies, fetches thread context dynamically per ticket, generates realistic end-user responses using KoboldCPP, and posts them back into osTicket. It isolates individual ticket threads by `ticket_id` to prevent persona cross-talk across concurrent tickets.

---

## 🏗️ Architecture

```
+------------------+         SQL / REST API          +-----------------------------+         OpenAI API API         +---------------------+
|                  |  <--------------------------->  |                             |  <------------------------->  |                     |
|  osTicket (v1.x) |                                 |  Python Intermediary Script |                               |  KoboldCPP (LLM)    |
|  (XAMPP / MySQL) |  <--------------------------->  |  (Dynamic Multi-Ticket Sync)|  <------------------------->  |  (Local GGUF Model) |
|                  |                                 |                             |                               |                     |
+------------------+                                 +-----------------------------+                               +---------------------+
```

1. **osTicket (Environment/UI):** The ticketing interface where the IT agent views and replies to support tickets.
2. **Python Intermediary (Orchestrator):** Polls the osTicket MySQL database for updates, extracts conversation context per `ticket_id`, formats LLM prompts, and writes AI replies back to osTicket.
3. **KoboldCPP (User Simulation):** The local LLM engine that roleplays as the end-user who opened the specific ticket.

---

## ✨ Features

* **Dynamic Persona & Context Locking:** Queries `ost_user` and `ost_thread_entry` per ticket to ensure the AI roleplays strictly as the user who created that specific ticket.
* **Context Retention:** Reads the initial issue submission from the database so the LLM remembers the original problem throughout multi-turn conversations.
* **Automated Ticket Seeding:** Automatically creates a fresh random test ticket upon launch via osTicket's REST API.
* **Database Thread Injection:** Direct insertion into `ost_thread_entry` for instant response updates in the osTicket web interface.

---

## 📋 Prerequisites

* **Python 3.8+**
* **XAMPP / MySQL** (running osTicket database)
* **osTicket Installation** (with API enabled)
* **KoboldCPP** (or any OpenAI API-compatible local LLM server running on `http://localhost:5001`)

### Python Dependencies

```bash
pip install pymysql
```

---

## ⚙️ Configuration

Set up environment variables or update the configuration section in `main.py`:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `OSTICKET_API_URL` | osTicket API endpoint for creating tickets | `http://127.0.0.1/osticket/api/tickets.json` |
| `OSTICKET_API_KEY` | Your osTicket API key | *Set via Environment Variable* |
| `DB_HOST` | MySQL host address | `localhost` |
| `DB_USER` | MySQL username | `root` |
| `DB_PASSWORD` | MySQL password | *Set via Environment Variable* |
| `DB_NAME` | osTicket MySQL database name | `osticket_db` |
| `KOBOLD_CHAT_URL` | KoboldCPP chat completions endpoint | `http://localhost:5001/v1/chat/completions` |

---

## 🚀 Running the Simulator

1. Ensure **MySQL/XAMPP** and **KoboldCPP** are running.
2. Set your environment variables (optional but recommended):
   ```bash
   export OSTICKET_API_KEY="YOUR_API_KEY"
   export DB_PASSWORD="YOUR_DB_PASSWORD"
   ```
3. Execute the script:
   ```bash
   python main.py
   ```

---

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).
