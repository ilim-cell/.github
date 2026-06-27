# 🔎 My GitHub Profile & xkcd Semantic Vault

Welcome to my personal GitHub profile repository! 🚀 This repository is a fully self-contained, offline-capable, and serverless AI system designed to index, organize, and search the entire catalog of xkcd comics.

🌟 Double Identity: Not only is this a state-of-the-art semantic search repository, but it also doubles as my GitHub Profile README! When visitors land on my profile page, they are greeted with a dynamically updated, OCR-processed dashboard featuring the latest live xkcd release alongside my projects.

By leveraging semantic vector embeddings, this built-in profile search engine looks beyond simple keywords to match comics based on concepts, jokes, storylines, or emotional intent. Whether you are looking for "a mother deleting a school student list" or "why you shouldn't use password rules with numbers", this engine understands the context and serves the exact comic instantly.

## 🚀 Key Features

Dual-Search Platform:

  - Web Application (index.html): A client-side, zero-server search application powered directly in the browser using Hugging Face's Transformers.js (all-MiniLM-L6-v2).

  - GitHub Actions Search (issue-search.yml): An automated search engine that runs entirely on GitHub's free runners. Users open an issue, and our workflow parses the query, finds the best matches, renames the issue, posts dynamic image/text results, and locks the thread.

  - Auto-Updating Profiles: Integrated script (update_xkcd.py) automatically pulls the latest comic, runs OCR on it to parse text, updates your vector matrix, and updates my GitHub profile landing page dynamically!

  - Intelligent Vault Restorer (restore_vault.py): Recreates a local structured archive of every comic in the format number_comicname with image downloads and on-the-fly API transcript recovery running on optimized multi-threaded workers.

## 📁 Repository Structure

```
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── config.yml            # Disables blank issues for clean form-only interface
│   │   └── search.yml            # Custom Issue Form template with query boxes
│   └── workflows/
│       ├── issue-search.yml      # Dynamic Issue Search workflow (post-on-edit, lock & close)
│       └── xkcd.yml              # Chron scheduler to fetch new comics, OCR, and embed them
├── img/
│   └── xkcd.png                  # Image placeholder mirror for profile README
├── xkcd/                         # Organised folder backup (Format: num_slug/text.txt & images)
├── xkcd_embeddings.json          # Master JSON database with 384-dimensional vector coordinate arrays
├── local_backfill.py             # Highly detailed local scraper and indexer with status bar
├── generate_embeddings.py        # Vectorizes raw text strings into neural network dimensions
├── restore_vault.py              # Restores offline assets with smart user-agent headers
└── index.html                    # Single-file HTML/JS client search app
```


## 🛠️ Local Setup & Installation

**1. Prerequisites**

Ensure you have Python 3.8+ installed. Install the required Python packages for crawling and generation:

``` python
pip install requests numpy sentence-transformers tqdm Pillow pytesseract
```

Note: If you plan on using OCR features inside update_xkcd.py locally, make sure you have the Tesseract OCR engine installed on your system.

**2. Fetch the Database Index**


If you don't already have the index, run the backfiller to compile the primary JSON dataset:

``` python
python local_backfill.py
```

**3. Generate Semantic Embeddings**

Run the embedding pipeline to convert the compiled text into a semantic matrix (this will create/update the embedding coordinates inside xkcd_embeddings.json):

``` python
python generate_embeddings.py
```

4. Rebuild the Organized Offline Directory

If you want to create a local, beautifully sorted database of comics and transcripts in numerical order:

``` python
python local_backfill.py
```

This utilizes a 10-worker concurrent thread pool to rebuild text and image configurations smoothly while bypassing strict server CDN blocks.

## 💻 Running the Web Application

Due to standard browser security restrictions (CORS), the browser cannot read the local xkcd_embeddings.json file directly from a file:// URL.

To open and run the client-side neural web app, open your terminal in the repository folder and spin up a lightweight Python web server:

``` python
python -m http.server 8000
```

You can also use a Node.js server (inc. Vite) or any sort of server extension in your IDE.

Then, open your web browser and navigate to:
👉 http://localhost:8000

## 🤖 GitHub Serverless Search Integration

The GitHub Actions search operates in an incredibly neat, serverless cycle:

- User Interaction: A user opens a new Issue using the custom 🔎 Search template.

- Initial feedback: The issue-search.yml workflow triggers, immediately posting a "Search has started..." status comment at the top of the thread.

- Execution: The runner boots a Python environment, loads your xkcd_embeddings.json database, generates a query vector matching the user's intent, and updates the issue title to match their exact query.

- Results Posted: The runner edits the original status comment to show the top 3 best matching comics, along with direct markdown image previews and comic references.

- Locked Thread: The issue conversation is automatically locked to prevent spam, instructing the user to close the issue if they found the correct comic.

## 📝 License & Attributions

Comics by xkcd (Randall Munroe), licensed under CC BY-NC 2.5.

Search algorithms and embedding pipelines powered by Hugging Face Transformers, SentenceTransformers, and Xenova JS.
