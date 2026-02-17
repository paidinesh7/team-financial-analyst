# Team Financial Analyst

An AI-powered financial analysis workflow built on Claude Code. Drop in financial statements, get an executive briefing in 2 minutes, then go as deep as you need.

## Setup

1. Install [Claude Code](https://docs.anthropic.com/en/docs/claude-code) if you haven't already
2. Clone this repo:
   ```bash
   git clone https://github.com/paidinesh7/team-financial-analyst.git
   ```
3. Open the project folder in Claude Code:
   ```bash
   cd team-financial-analyst
   claude
   ```

## How to use

### 1. Add your files

Drop financial statements into the `statements/` folder — PDFs, spreadsheets, CSVs, images of financial statements, annual reports. Anything you'd normally read during an analysis.

### 2. Ask for an analysis

Open Claude Code in this project folder and say something like:

- "Analyze the financials in the statements folder"
- "What do the numbers look like for this company?"
- "Review the annual report I just added"

### 3. Get the executive briefing

The agent will read everything and produce a quick briefing:

- **Company snapshot** — what the business does, how it makes money
- **Key numbers table** — the metrics that matter most for this specific company
- **Red flags** — the 3-5 most critical issues, ranked by severity, with numbers
- **What looks good** — specific strengths backed by data
- **Questions to dig into** — what the data raises but doesn't answer

This is designed to be absorbed in about 2 minutes.

### 4. Go deeper (optional)

After the briefing, you'll be asked if you want more detail. You can:

- Say **"go deeper"** to get the full analysis (detailed statement walkthrough, ratio analysis, connecting-the-dots narrative, and verdict)
- Ask about a **specific area** — e.g., "tell me more about the debt structure" or "what's going on with cash flow?" — and get just that section expanded
- **Ask follow-up questions** at any point

## What's in this repo

```
├── CLAUDE.md                    # Agent instructions (the analysis framework)
├── Understanding_finance.pdf    # Reference: Merrill Lynch guide to financial reports
├── statements/                  # Drop your financial statements here
└── README.md                    # You're reading this
```

## Tips

- **More files = better analysis.** Multiple years of statements, investor presentations, and MD&A sections give the agent more to work with. A single year's financials never tell the full story.
- **Ask specific follow-ups.** After the briefing, don't just say "go deeper" if you only care about one thing. Ask directly — "is the debt maturity schedule a problem?" gets a better answer than a generic deep dive.
- **Challenge the output.** If something doesn't look right, say so. The agent will re-examine and correct itself.
- **Compare companies.** You can drop statements for multiple companies and ask for a comparison.
