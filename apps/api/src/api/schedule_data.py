# ruff: noqa: E501
# PyTexas 2026 — Official Conference Schedule
# Source: https://www.pytexas.org/2026/schedule/
# All times in 24-hour format, America/Chicago (CST/CDT)

CONFERENCE_DATA = {
    # ── Friday, April 17 — Tutorial Day ──────────────────────────────────────
    "2026-04-17": {
        "09:00": {
            "title": "Import is Important: The Secret Life of Python Modules and Packages",
            "speaker": "Heather Crawford",
            "desc": "Learn how Python manages modules, how to import from them, and how to debug common issues.",
        },
        "12:00": {
            "title": "Lunch",
            "speaker": "",
            "desc": "Grab some food, meet fellow Pythonistas, and take a breather!",
        },
        "13:30": {
            "title": "Becoming a Better Python Developer with AI",
            "speaker": "Bernat Gabor",
            "desc": "Hands-on workshop on mental models and workflows for using AI assistants effectively.",
        },
        "16:30": {
            "title": "Build Agentic AI with Semantic Kernel (Sponsored)",
            "speaker": "Microsoft",
            "desc": "Build an agent-driven RAG application using Azure Database for PostgreSQL and Semantic Kernel.",
        },
    },
    # ── Saturday, April 18 — Conference Day 1 ────────────────────────────────
    "2026-04-18": {
        "08:00": {
            "title": "Registration Opens & Breakfast",
            "speaker": "",
            "desc": "Pick up your badge, grab breakfast, and get settled in.",
        },
        "09:00": {
            "title": "Day 2 Opening Remarks",
            "speaker": "PyTexas Organizers",
            "desc": "Welcome to PyTexas 2026!",
        },
        "09:20": {
            "title": "Keynote",
            "speaker": "Dawn Wages",
            "desc": "Director of Community at Anaconda. Focuses on inclusive practices and sustainable open source.",
        },
        "10:05": {
            "title": "15 Minute Break",
            "speaker": "",
            "desc": "Short break — grab a coffee!",
        },
        "10:20": {
            "title": "Python as Your DSL",
            "speaker": "Moshe Zadka",
            "desc": "Exploring the art of designing Python Domain-Specific Languages that feel natural.",
        },
        "10:50": {
            "title": "I Built an AI Running Coach",
            "speaker": "Adam Gordon Bell",
            "desc": "How to reverse-engineer APIs and use async patterns to give LLMs memory.",
        },
        "11:20": {"title": "10 Minute Break", "speaker": "", "desc": "Short break."},
        "11:30": {
            "title": "Using MCP to Build Safe AI Systems",
            "speaker": "Maria Silvia Mielniczuk",
            "desc": "Using the Model Context Protocol to design safe, auditable tool interfaces.",
        },
        "12:00": {
            "title": "Data Visualization in Python (Sponsored)",
            "speaker": "Anaconda / Dr. James A. Bednar",
            "desc": "Visualizing data effectively with Python.",
        },
        "12:20": {
            "title": "Lunch",
            "speaker": "",
            "desc": "Enjoy a great lunch and network with fellow Pythonistas!",
        },
        "14:00": {
            "title": "Why Installing Python Packages Is Still a Security Risk",
            "speaker": "Christopher Ariza",
            "desc": "Introduction to installation-time threats and practical defenses for production environments.",
        },
        "14:30": {
            "title": "Behind the Magic: Unlocking Python's Descriptor Protocol",
            "speaker": "Scott Irwin",
            "desc": "Unlocking how Python decides what happens when you access object attributes.",
        },
        "15:00": {"title": "15 Minute Break", "speaker": "", "desc": "Short break."},
        "15:15": {
            "title": "Data Engineer's Survival Guide",
            "speaker": "Indrasena Manga",
            "desc": "Writing resilient pipelines that don't break at 3 AM using Pydantic and pytest.",
        },
        "15:45": {
            "title": "Failed Experiments in Vibe Coding",
            "speaker": "Al Sweigart",
            "desc": "A hilarious exploration of non-developers using AI to vibe code software.",
        },
        "16:15": {"title": "15 Minute Break", "speaker": "", "desc": "Short break."},
        "16:30": {
            "title": "Full-Stack FastAPI App with DocumentDB (Sponsored)",
            "speaker": "Microsoft",
            "desc": "Hands-on lab using FastAPI and Open Source DocumentDB via Docker containers.",
        },
        "18:00": {
            "title": "Lightning Talks",
            "speaker": "",
            "desc": "Five-minute lightning talks from the community.",
        },
        "18:30": {
            "title": "Networking Event Starts",
            "speaker": "",
            "desc": "Meet your fellow Pythonistas at the PyTexas networking event!",
        },
        "21:00": {"title": "Networking Event Ends", "speaker": "", "desc": "See you tomorrow!"},
    },
    # ── Sunday, April 19 — Conference Day 2 ──────────────────────────────────
    "2026-04-19": {
        "08:00": {
            "title": "Registration Opens & Breakfast",
            "speaker": "",
            "desc": "Pick up your badge, grab breakfast, and get settled in for the final day.",
        },
        "09:00": {
            "title": "Day 3 Opening Remarks",
            "speaker": "PyTexas Organizers",
            "desc": "Welcome to Day 3 of PyTexas 2026!",
        },
        "09:20": {
            "title": "Keynote",
            "speaker": "Hynek Schlawack",
            "desc": "Lead infrastructure engineer discussing networks, security, and robust software.",
        },
        "10:05": {
            "title": "15 Minute Break",
            "speaker": "",
            "desc": "Short break — grab a coffee!",
        },
        "10:20": {
            "title": "The Bakery: How PEP810 sped up my bread operations business",
            "speaker": "Jacob Coffee",
            "desc": "How explicit lazy imports can dramatically improve application startup times.",
        },
        "10:50": {
            "title": "Python in the Browser: MkDocs & JupyterLite",
            "speaker": "Kassandra Keeton",
            "desc": "Building interactive documentation with MkDocs and JupyterLite via WebAssembly.",
        },
        "11:20": {"title": "10 Minute Break", "speaker": "", "desc": "Short break."},
        "11:30": {
            "title": "The Hidden Power of Soft Skills",
            "speaker": "Sumaiya Nalukwago",
            "desc": "Mastered dev but still stuck? Why soft skills are the ultimate next level.",
        },
        "12:00": {
            "title": "Events are the Wrong Abstraction (Sponsored)",
            "speaker": "Temporal / Mason Egger",
            "desc": "Rethinking event-driven architecture with durable execution.",
        },
        "12:20": {
            "title": "Lunch",
            "speaker": "",
            "desc": "Enjoy a great lunch and network with fellow Pythonistas!",
        },
        "14:00": {
            "title": "Are API Tests Overrated? Smarter Risk Mitigation",
            "speaker": "Pandy Knight",
            "desc": "Challenging conventional testing strategies in favor of smarter alternatives.",
        },
        "14:30": {
            "title": "Introducing Meow'py",
            "speaker": "Sophia Solomon",
            "desc": "Applying observability (OpenTelemetry) to the Internet of Living Things.",
        },
        "15:00": {"title": "15 Minute Break", "speaker": "", "desc": "Short break."},
        "15:15": {
            "title": "Tying Up Loose Threads: No-GIL Ready",
            "speaker": "Charlie Lin",
            "desc": "Making your project ready for the free-threaded interpreter.",
        },
        "15:45": {
            "title": "Upgrading Python CLIs: From Scripts to Interactive Tools",
            "speaker": "Avik Basu",
            "desc": "Moving from basic scripts to professional TUIs with Textual, Rich, and Typer.",
        },
        "16:15": {
            "title": "Lint Fast, Type Hard",
            "speaker": "Miguel Vargas",
            "desc": "Using modern, ultra-fast tooling like Ruff and Pyrefly to improve code quality.",
        },
        "16:45": {
            "title": "Lightning Talks",
            "speaker": "",
            "desc": "Five-minute lightning talks from the community.",
        },
        "17:25": {
            "title": "Closing Remarks",
            "speaker": "PyTexas Organizers",
            "desc": "Thank you for coming to PyTexas 2026. See you next year!",
        },
    },
}
