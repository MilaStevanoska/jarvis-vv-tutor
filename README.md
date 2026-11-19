# Jarvis: V&V Tutor Agent

An educational agent for software **Verification and Validation**.
Runs fully on your computer with a free local model (Ollama). Cost: $0.
No Python packages to install: it uses the standard library only.

## Run it (3 steps)

1. Install Ollama from https://ollama.com and open it.
2. Download a model (one time, about 2 GB):

       ollama pull llama3.2

3. In this folder:

       python run.py

   Then open http://127.0.0.1:8000 in your browser.

Needs Python 3.10 or newer. On macOS/Linux use `python3` if `python` is missing.

Other ways to start:

    python run.py --cli               chat in the terminal
    python run.py --model qwen2.5     use another Ollama model
    python run.py --port 9000         use another port
    python run.py --import-book "C:\path\book.pdf"   add the textbook (once)

## The textbook (agentic search)

No book is included in this repository (textbooks are copyrighted).
Import your own course book once (`.pdf`, `.txt` or `.md`), then restart Jarvis:

    python run.py --import-book "C:\path\to\book.pdf"

It is saved as searchable passages in `knowledge/book/`, each labelled with its
page. Jarvis then gets a `search_book` tool and **decides by itself** when to look
something up, what keywords to use and whether to search again, then answers
and names the page. Without a book, Jarvis works as before. Scanned PDFs (images
only) have no text to read and need OCR first. PDF import uses `pypdf`
(`pip install pypdf`); running Jarvis does not need it.

## The two sections

1. **Learn with Jarvis**: ask anything about V&V and Jarvis explains it,
   using the notes in `knowledge/`. Every chat is saved and listed on the
   left; click one to reopen and continue it. "+ New chat" starts a fresh one.
2. **Cheat on your exam**: paste a requirement or activity. Jarvis answers
   **Verification** or **Validation**, says why in one sentence and gives a
   short example. Answers are saved and shown again next time.
   In the terminal (`--cli`), type `/cheat <requirement>`.

### Where things are saved

Everything stays on this computer, in `data/` (one user, no accounts):

    data/chats/<chat id>.json    one file per chat (title, dates, messages)
    data/cheats.json             all "Cheat on your exam" answers

To delete a chat, delete its file. To back everything up, copy `data/`.

Good-agent rules: says "I'm not sure" instead of guessing, stays on V&V,
keeps all data on this computer.

## Make it yours

| I want to...                  | Change this                                   |
|-------------------------------|-----------------------------------------------|
| Add my lecture notes          | Drop `.md` files into `knowledge/` (use `## ` headings) |
| Change the tutor's rules      | `jarvis/agent/prompts.py`                     |
| Change how V/V is decided     | `SYSTEM_PROMPT` and `FEW_SHOT` in `jarvis/services/classifier.py` |
| Change colours                | `:root` block in `jarvis/web/static/style.css`|
| Give the tutor a new tool     | Subclass `Tool` in `jarvis/tools/`, register it in `jarvis/app.py` |
| Use another model provider    | New class with `chat()` + `is_available()`, swap it in `jarvis/app.py` |

## Structure

    run.py                       entry point
    jarvis/
      config.py                  settings (env vars: JARVIS_MODEL, JARVIS_PORT, ...)
      domain.py                  data types, no I/O
      ports.py                   interfaces the agent depends on
      errors.py                  expected errors
      app.py                     composition root: wires everything together
      agent/tutor.py             1. Learn: the agent loop (think -> tools -> answer)
      agent/prompts.py           tutor system prompt
      services/classifier.py     2. Cheat: Verification or Validation
      llm/ollama.py              Ollama adapter
      knowledge/markdown_kb.py   notes and book search (keywords, rare words count more)
      knowledge/importer.py      PDF/txt book -> knowledge/book/*.md
      tools/book_search.py       search_book tool the agent can call
      storage/conversations.py   saved chats (JSON files; in-memory version for tests)
      storage/cheats.py          saved "Cheat on your exam" answers
      tools/                     tool framework
      web/api.py                 use cases for the browser
      web/server.py              HTTP transport
      web/static/                the UI (HTML, CSS, JS)
      cli.py                     terminal chat
    knowledge/                   course notes
    tests/                       test suite (no Ollama needed)

## How SOLID shows up

- **Single responsibility**: each file has one job. The agent loop does not
  know about HTTP, files or Ollama. The classifier only classifies.
- **Open/closed**: new tools and notes are added without editing the agent.
- **Liskov substitution**: the tests swap the real model for a fake one and
  everything still works.
- **Interface segregation**: small interfaces in `ports.py`.
- **Dependency inversion**: the agent and classifier depend on interfaces.
  Concrete classes are chosen in one place, `app.py`.

## Tests

    python -m unittest discover -s tests -v

## Troubleshooting

- **"Cannot reach Ollama"**: open the Ollama app, or run `ollama serve`.
  A very slow model can also show this message when it takes longer than
  `request_timeout` (180 s) in `jarvis/config.py`.
- **"Model ... is not downloaded"**: run `ollama pull llama3.2`.
- **Slow answers**: normal for local models on a laptop. Try a smaller model.
- **Port already in use**: `python run.py --port 9000`.
