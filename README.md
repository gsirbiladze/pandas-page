# Data Explorer (pandas-page)

An elegant, lightweight interactive dashboard built with **Streamlit** and **DuckDB** to explore, query, and filter local datasets in real-time.

---

## 1. What It Is For
This application provides a zero-setup, self-hosted web interface to immediately visualize and search tabular datasets (CSVs) residing in any local directory. It is designed for developers, data analysts, and business users who need a clean, responsive, and private tool to inspect datasets without loading them into heavy database servers or custom analytics platforms.

---

## 2. What It Does
- **Auto-Discovery**: Instantly scans a target directory at startup and loads all discovered datasets.
- **SQL-Powered Backend**: Uses an in-memory DuckDB connection to query datasets efficiently.
- **Automatic Directory Monitoring**: Periodically scans the folder in the background (using an interval you define) to automatically hot-reload modified files and drop tables for deleted files.
- **Unified Logical Filtering**:
  - All non-date columns are searched simultaneously using the **Filter Expression** search bar.
  - Supports logical expressions using `"AND"`, `"OR"`, `"NOT"`, `"("`, and `")"` blocks (implicit `"OR"` linker if no operator is specified).
  - Supports field query syntax: exact match (`field=value`), numeric ranges (`field>value` or `field<value`), and boolean switches.
  - Automatically falls back to case-insensitive plain text search across all non-date fields.
- **Type-Aware Date Filters**: Dedicated date range pickers are rendered side-by-side with the search widget for date/time columns.
- **Data Distribution Charts**: Renders an interactive, responsive pie chart (using Altair) next to each dataset, showing percentage breakdowns. Group-by columns dynamically sync with visible dataframe columns and default to selecting all columns.
- **Export Filters**: Download buttons are automatically generated to export your filtered query results back as CSV files.

---

## 3. Library Dependencies
The application runs on Python 3.8+ and depends on the following libraries:
- **`streamlit`** (v1.33.0+): For rendering the interactive web UI.
- **`duckdb`** (v0.9.0+): Used as the fast in-memory query engine.
- **`pandas`** (v2.0.0+): For bridging query results from DuckDB to Streamlit.
- **`altair`** (v5.0.0+): For generating clean, interactive data distribution pie charts.

---

## 4. How to Start

### Installation
Ensure you have the required packages installed in your Python environment:
```bash
pip install streamlit duckdb pandas altair
```

### Running the App
Start the dashboard server by pointing it to the folder containing your data files using Streamlit's parameter passing syntax:

```bash
streamlit run app.py -- -d <directory_path> -i <refresh_interval_seconds> -t "<dashboard_title>"
```

### Command-Line Arguments
- `-d`, `--directory`: Path to the directory containing your CSV files (defaults to the current directory `.`).
- `-i`, `--interval`: Background filesystem scan interval in seconds to watch for changes (defaults to `5` seconds; set to `0` to disable).
- `-t`, `--title`: Custom title shown in the browser tab and page header (defaults to `"Data Explorer"`).

### Example Run
To scan a folder called `./data` every `3` seconds with a custom title:
```bash
streamlit run app.py --server.headless true --server.address localhost --server.port 8501 -- -d ./data -i 3 -t "Business Insights Dashboard"
```
Once started, the terminal will provide a local URL (usually `http://localhost:8501`) to open the app in your browser.
