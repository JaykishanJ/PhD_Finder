# PhD Vacancy Crawler Pro

A sophisticated, direct-crawling web scraper designed specifically to find PhD positions related to bioinformatics, computational biology, genomics, and multi-omics. 

Instead of relying on Google APIs or generic job boards, this crawler targets university sites, institutional pages, and research feeds, analyzing the raw HTML content, scoring it against a custom set of keywords, and presenting the highest-priority vacancies directly to you.

## Features
- **Intelligent Scoring**: Ranks vacancies based on keywords (e.g. "single-cell", "spatial transcriptomics", "machine learning" score higher than general omics).
- **Automated Extraction**: Pulls deadlines, supervisor names, institutions, and emails from raw page text.
- **Local SQLite Database**: Never lose a vacancy. It keeps track of new vs old postings and prevents duplicates.
- **Modern GUI**: Includes a sleek graphical user interface with live terminal logs.
- **HTML Reporting**: Automatically generates an organized `daily_report.html` summarizing new, urgent, and highly-scored PhD positions.

## Installation & Setup

1. **Install Requirements**: Double-click the `Install_Requirements.bat` file to automatically install all the necessary Python libraries (including `customtkinter`, `pandas`, `beautifulsoup4`, etc.).
2. **Launch the App**: Double-click `Start_PhD_Finder.bat` to launch the modern GUI application without opening a terminal window.

*(You can right-click `Start_PhD_Finder.bat` and select "Send to > Desktop (create shortcut)" for true one-click access from your desktop!)*

## Usage

1. Select your target **Region** from the sidebar dropdown (Europe, USA, Canada, Australia, Asia, India, or All).
2. Check **Quick Run (Test)** if you only want to scrape a tiny subset of the seeds to test if it's working.
3. Check **Generate HTML Report** to automatically create the readable report when it finishes.
4. Click **Start Crawling** and watch the live logs!

Once finished, open `daily_report.html` in any web browser to view your matched vacancies.
