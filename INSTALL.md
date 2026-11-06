# Installation and usage

Cloud Cost Comparator is a Claude skill. The normal way to run it is through Claude. You can also run the scripts yourself to test them.

## Option 1: Run it through Claude (recommended)

1. Download this repository as a zip (Code > Download ZIP), or zip the repository folder.
2. In Claude, open **Settings > Capabilities > Skills > Upload skill** and choose the zip.
3. Start a chat and attach your HLD, requirements document or discovery notes.
4. Ask, for example: *"Compare AWS, Google Cloud and Azure for this project and give me the cost report."*
5. Claude reads the documents, asks up to 5 sizing questions, fetches prices, and returns the Word report, the infographic and the draw.io diagrams.

For live prices:

* Connect **Claude in Chrome**. The skill uses your browser to call the official pricing APIs (Azure Retail Prices and the AWS price list files need no login).
* Optional: create a free Google Cloud API key with the Cloud Billing API enabled and give it to Claude (or set `GOOGLE_PRICING_API_KEY`). This gives exact Google Cloud prices in any region.
* Without either, the skill marks items it cannot price from an official source as "unpriced" instead of estimating them.

## Option 2: Run the scripts on the included example

Requirements:

* Python 3 with matplotlib: `pip install matplotlib`
* Node.js with the docx package: `npm install docx`

Commands (Windows Command Prompt; on macOS or Linux use `/` instead of `\`):

```
git clone https://github.com/arunrktech/cloud-cost-comparator
cd cloud-cost-comparator
mkdir work

python scripts\cost_model.py assets\example\prices.json --workload assets\example\workload.json --out work\costs.json
python scripts\diagrams.py assets\example\workload.json --out work\diagrams
python scripts\infographic.py assets\example\report.json work\costs.json --out work\diagrams\infographic.png
node scripts\build_report.js assets\example\report.json work\costs.json assets\example\workload.json work\diagrams work\Example_Report.docx
```

This rebuilds the example report in the `work` folder.

To run the tests: `python -m unittest discover tests`

The scripts handle the arithmetic, diagrams and report. Reading the documents, asking sizing questions, mapping services and fetching prices is done by Claude. To run the scripts on your own project without Claude, write `workload.json`, `prices.json` and `report.json` yourself, following `references/workload_schema.md` and `references/report_outline.md`.
