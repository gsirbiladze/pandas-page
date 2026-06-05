import os
import re
import sys
import glob
import time
import argparse
import datetime
import pandas as pd
import duckdb
import altair as alt
import streamlit as st
import streamlit.components.v1 as components

# 1. Parse command line arguments
@st.cache_resource
def parse_cli_args():
    parser = argparse.ArgumentParser(description="DuckDB CSV Explorer")
    parser.add_argument("-d", "--directory", default=".", help="Directory containing CSV files")
    parser.add_argument("-i", "--interval", type=int, default=5, help="Auto-refresh interval in seconds")
    parser.add_argument("-t", "--title", default="Data Explorer", help="Title of the application")
    # Streamlit passes command line args after '--'
    args, unknown = parser.parse_known_args()
    return os.path.abspath(args.directory), args.interval, args.title

# Get the target directory, refresh interval, and application title
TARGET_DIR, REFRESH_SECONDS, APP_TITLE = parse_cli_args()

# 2. Database & State Management
class DBManager:
    def __init__(self, directory):
        self.directory = directory
        # Initialize in-memory DuckDB connection
        self.conn = duckdb.connect(database=':memory:', read_only=False)
        # Dictionary to track loaded files: file_path -> (mtime, size)
        self.loaded_files = {}

    def get_table_name(self, file_path):
        base = os.path.basename(file_path)
        name, _ = os.path.splitext(base)
        # Replace non-alphanumeric characters with underscore
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = "t_" + sanitized
        return sanitized.lower()

    def scan_and_update(self):
        """Scans the directory and updates DuckDB tables. Returns True if database changed."""
        if not os.path.isdir(self.directory):
            return False

        csv_pattern = os.path.join(self.directory, "*.csv")
        csv_files = glob.glob(csv_pattern)
        
        current_files = {}
        for fp in csv_files:
            try:
                stat = os.stat(fp)
                current_files[fp] = (stat.st_mtime, stat.st_size)
            except Exception:
                continue

        changed = False

        # Drop tables for files that have been deleted
        for fp in list(self.loaded_files.keys()):
            if fp not in current_files:
                table_name = self.get_table_name(fp)
                try:
                    self.conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                except Exception as e:
                    print(f"Error dropping table {table_name}: {e}")
                del self.loaded_files[fp]
                changed = True

        # Load or reload new/modified files
        for fp, (mtime, size) in current_files.items():
            if fp not in self.loaded_files or self.loaded_files[fp] != (mtime, size):
                table_name = self.get_table_name(fp)
                try:
                    self.conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                    # Use read_csv_auto to load the file
                    self.conn.execute(f'CREATE TABLE "{table_name}" AS SELECT * FROM read_csv_auto(?)', [fp])
                    self.loaded_files[fp] = (mtime, size)
                    changed = True
                except Exception as e:
                    # Report error via streamlit but don't crash
                    print(f"Error loading CSV {fp}: {e}")

        return changed

# Load/get the cached database manager
@st.cache_resource
def get_db_manager(directory):
    manager = DBManager(directory)
    manager.scan_and_update()
    return manager

db_manager = get_db_manager(TARGET_DIR)

# 3. Helpers for filter generation
def is_numeric(dtype):
    dtype = dtype.upper()
    numeric_types = ["TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", 
                     "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT", 
                     "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL"]
    return any(nt in dtype for nt in numeric_types)

def is_datetime(dtype):
    dtype = dtype.upper()
    dt_types = ["DATE", "TIME", "TIMESTAMP", "TIMESTAMPTZ"]
    return any(dtt in dtype for dtt in dt_types)

# 4. Streamlit UI Setup
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject CSS for premium aesthetics
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

/* Apply modern font */
html, body, [class*="css"], .stApp {
    font-family: 'Outfit', sans-serif;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Outfit', sans-serif;
    font-weight: 600;
}

/* Gradient Header */
.title-gradient {
    background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.8rem;
    font-weight: 800;
    margin-bottom: 0.2rem;
    text-align: left;
}

.subtitle {
    color: #6b7280;
    font-size: 1.1rem;
    margin-bottom: 2rem;
}

/* Table Card Container */
.table-card {
    background: rgba(255, 255, 255, 0.7);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(229, 231, 235, 0.8);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 30px;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.02);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.table-card:hover {
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
    transform: translateY(-2px);
}

/* Sidebar Custom Styling */
[data-testid="stSidebar"] {
    background-color: #0f172a;
    border-right: 1px solid #1e293b;
}

[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] span, [data-testid="stSidebar"] p {
    color: #f1f5f9 !important;
}

/* Elegant Secondary Buttons in Sidebar (Enable/Disable All) */
[data-testid="stSidebar"] button[kind="secondary"] {
    color: #f1f5f9 !important;
    background-color: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease-in-out !important;
}

[data-testid="stSidebar"] button[kind="secondary"]:hover {
    background-color: rgba(255, 255, 255, 0.1) !important;
    border-color: rgba(255, 255, 255, 0.3) !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
    transform: translateY(-1px) !important;
}

/* Sidebar Collapse/Retract Button Styling */
[data-testid="stSidebar"] button[kind="headerNoPadding"] {
    background-color: transparent !important;
    border: none !important;
    color: #94a3b8 !important;
    transition: all 0.2s ease-in-out !important;
}

[data-testid="stSidebar"] button[kind="headerNoPadding"]:hover {
    color: #f8fafc !important;
    background-color: rgba(255, 255, 255, 0.08) !important;
}

/* Status Badge styling */
.status-badge {
    padding: 6px 12px;
    border-radius: 9999px;
    font-size: 0.85rem;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.status-active {
    background-color: #dcfce7;
    color: #166534 !important;
    border: 1px solid #bbf7d0;
}

.status-warning {
    background-color: #fef9c3;
    color: #854d0e !important;
    border: 1px solid #fef08a;
}

@media (prefers-color-scheme: dark) {
    .table-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(71, 85, 105, 0.8);
        color: #f1f5f9;
    }
    .status-active {
        background-color: #064e3b;
        color: #6ee7b7 !important;
        border: 1px solid #047857;
    }
}
</style>
""", unsafe_allow_html=True)

# 5. Sidebar Controls & Info
with st.sidebar:
    st.markdown(f"## 📊 {APP_TITLE}")

    st.divider()
    
    # List of tables switches
    st.markdown("### 📂 Toggle Tables to View")
    
    sorted_files = sorted(list(db_manager.loaded_files.keys()))
    toggles = {}
    
    if not sorted_files:
        st.markdown("<span class='status-badge status-warning'>⚠️ No data found</span>", unsafe_allow_html=True)
        st.caption("Please ensure data files are available in the target directory.")
    else:
        col_all_1, col_all_2 = st.columns(2)
        with col_all_1:
            if st.button("Enable All", use_container_width=True):
                for fp in sorted_files:
                    st.session_state[f"toggle_{db_manager.get_table_name(fp)}"] = True
                st.rerun()
        with col_all_2:
            if st.button("Disable All", use_container_width=True):
                for fp in sorted_files:
                    st.session_state[f"toggle_{db_manager.get_table_name(fp)}"] = False
                st.rerun()
        
        st.markdown("")
        
        for fp in sorted_files:
            table_name = db_manager.get_table_name(fp)
            display_name = os.path.splitext(os.path.basename(fp))[0]
            
            # Use session state to persist/control toggle selections
            toggle_key = f"toggle_{table_name}"
            if toggle_key not in st.session_state:
                st.session_state[toggle_key] = False
                
            toggles[table_name] = st.toggle(
                label=display_name,
                key=toggle_key
            )

# 6. Periodic Background Refresh Fragment
if REFRESH_SECONDS > 0:
    @st.fragment(run_every=REFRESH_SECONDS)
    def auto_scan_fragment():
        # Check files modified
        changed = db_manager.scan_and_update()
        if changed:
            st.rerun()
            
    # Run the background checker
    auto_scan_fragment()

# 7. Main Dashboard Interface
st.markdown(f"<h1 class='title-gradient'>{APP_TITLE}</h1>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Real-time interactive dashboard to query, filter, and explore your datasets.</div>", unsafe_allow_html=True)

# Find which tables are selected
active_tables = [t_name for t_name, is_active in toggles.items() if is_active]

if not active_tables:
    # Beautiful Empty State
    st.markdown("""
    <div style='text-align: center; padding: 60px 20px; background: rgba(120, 120, 120, 0.05); border-radius: 16px; border: 2px dashed rgba(120, 120, 120, 0.2);'>
        <h2 style='font-size: 3.5rem; margin-bottom: 10px;'>📂</h2>
        <h3>No Tables Selected</h3>
        <p style='color: #6b7280; max-width: 500px; margin: 0 auto 20px;'>
            Please select one or more datasets in the sidebar toggles to view, query, and filter their data.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Display summary of all discovered files in a nice table
    if sorted_files:
        st.markdown("### 📋 Available Datasets")
        file_summary_data = []
        for fp in sorted_files:
            table_name = db_manager.get_table_name(fp)
            display_name = os.path.splitext(os.path.basename(fp))[0]
            mtime = os.path.getmtime(fp)
            mtime_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            size_kb = round(os.path.getsize(fp) / 1024, 2)
            
            try:
                row_cnt = db_manager.conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
                cols_cnt = len(db_manager.conn.execute(f'PRAGMA table_info("{table_name}")').fetchall())
            except Exception:
                row_cnt, cols_cnt = "Error", "Error"
                
            file_summary_data.append({
                "Name": display_name,
                "Size (KB)": size_kb,
                "Rows": row_cnt,
                "Columns": cols_cnt,
                "Last Updated": mtime_str
            })
            
        st.dataframe(
            pd.DataFrame(file_summary_data),
            use_container_width=True,
            hide_index=True
        )

else:
    # Display the selected tables
    for table_name in active_tables:
        # Match table name back to original file path
        file_path = next(fp for fp in sorted_files if db_manager.get_table_name(fp) == table_name)
        display_name = os.path.splitext(os.path.basename(file_path))[0]
        
        try:
            total_rows = db_manager.conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            columns_info = db_manager.conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        except Exception as e:
            st.error(f"Error querying metadata for table `{table_name}`: {e}")
            continue

        # Render Table Card
        st.markdown(f"""
        <div class='table-card'>
            <div style='display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(120, 120, 120, 0.2); padding-bottom: 10px; margin-bottom: 20px;'>
                <h3 style='margin: 0; font-size: 1.5rem;'>📄 {display_name}</h3>
                <span class='status-badge status-active'>
                    ⚡ <b>{total_rows}</b> rows, <b>{len(columns_info)}</b> columns
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # We wrap the content below the HTML card in a column container to align with card borders
        with st.container():
            # Section 1: Filters Expander
            with st.expander(f"🔍 Filter Controls for {display_name}", expanded=True):
                # We show filters in a dynamic grid of columns (up to 3 columns)
                col_slots = st.columns(3)
                filters_sql = []
                filters_params = []
                
                for idx, (col_id, col_name, col_type, _, _, _) in enumerate(columns_info):
                    slot = col_slots[idx % 3]
                    widget_key = f"filter_{table_name}_{col_name}"
                    
                    with slot:
                        # Case 1: Numeric Filters
                        if is_numeric(col_type):
                            try:
                                min_val, max_val = db_manager.conn.execute(
                                    f'SELECT MIN("{col_name}"), MAX("{col_name}") FROM "{table_name}"'
                                ).fetchone()
                            except Exception:
                                min_val, max_val = None, None
                                
                            if min_val is not None and max_val is not None and min_val < max_val:
                                # Convert to float for slider compatibility
                                min_f = float(min_val)
                                max_f = float(max_val)
                                # Determine range slider value
                                slider_val = st.slider(
                                    label=f"🔢 {col_name} (Range)",
                                    min_value=min_f,
                                    max_value=max_f,
                                    value=(min_f, max_f),
                                    key=widget_key
                                )
                                filters_sql.append(f'"{col_name}" BETWEEN ? AND ?')
                                filters_params.extend([slider_val[0], slider_val[1]])
                            elif min_val is not None:
                                st.info(f"🔢 {col_name} (Constant: {min_val})")
                                
                        # Case 2: Boolean Filters
                        elif col_type.upper() in ["BOOLEAN", "BOOL"]:
                            bool_choice = st.selectbox(
                                label=f"🔘 {col_name}",
                                options=["All", "True", "False"],
                                index=0,
                                key=widget_key
                            )
                            if bool_choice == "True":
                                filters_sql.append(f'"{col_name}" = TRUE')
                            elif bool_choice == "False":
                                filters_sql.append(f'"{col_name}" = FALSE')
                                
                        # Case 3: Datetime / Date Filters
                        elif is_datetime(col_type):
                            try:
                                min_date_val, max_date_val = db_manager.conn.execute(
                                    f'SELECT MIN("{col_name}"), MAX("{col_name}") FROM "{table_name}"'
                                ).fetchone()
                            except Exception:
                                min_date_val, max_date_val = None, None
                            
                            # Handle converting to date
                            if min_date_val is not None and max_date_val is not None:
                                # Standardize date values
                                if isinstance(min_date_val, str):
                                    # Strip time parts if needed
                                    min_date = datetime.datetime.strptime(min_date_val.split()[0], "%Y-%m-%d").date()
                                    max_date = datetime.datetime.strptime(max_date_val.split()[0], "%Y-%m-%d").date()
                                elif isinstance(min_date_val, (datetime.date, datetime.datetime)):
                                    min_date = min_date_val.date() if isinstance(min_date_val, datetime.datetime) else min_date_val
                                    max_date = max_date_val.date() if isinstance(max_date_val, datetime.datetime) else max_date_val
                                else:
                                    min_date, max_date = None, None
                                    
                                if min_date and max_date:
                                    if min_date < max_date:
                                        date_range = st.date_input(
                                            label=f"📅 {col_name} (Range)",
                                            value=(min_date, max_date),
                                            min_value=min_date,
                                            max_value=max_date,
                                            key=widget_key
                                        )
                                        if isinstance(date_range, tuple) and len(date_range) == 2:
                                            filters_sql.append(f'CAST("{col_name}" AS DATE) BETWEEN ? AND ?')
                                            filters_params.extend([date_range[0], date_range[1]])
                                        elif isinstance(date_range, tuple) and len(date_range) == 1:
                                            filters_sql.append(f'CAST("{col_name}" AS DATE) >= ?')
                                            filters_params.append(date_range[0])
                                    else:
                                        st.info(f"📅 {col_name} (Constant: {min_date})")
                            
                        # Case 4: Text or Categorical Select Filters
                        else:
                            # Let's count unique values
                            try:
                                unique_cnt = db_manager.conn.execute(
                                    f'SELECT COUNT(DISTINCT "{col_name}") FROM "{table_name}"'
                                ).fetchone()[0]
                            except Exception:
                                unique_cnt = 999
                                
                            if unique_cnt <= 12:
                                try:
                                    all_vals = [
                                        row[0] for row in db_manager.conn.execute(
                                            f'SELECT DISTINCT "{col_name}" FROM "{table_name}" WHERE "{col_name}" IS NOT NULL ORDER BY "{col_name}"'
                                        ).fetchall()
                                    ]
                                    # Add None if there are nulls
                                    null_cnt = db_manager.conn.execute(
                                        f'SELECT COUNT(*) FROM "{table_name}" WHERE "{col_name}" IS NULL'
                                    ).fetchone()[0]
                                    if null_cnt > 0:
                                        all_vals.append("<Null>")
                                except Exception:
                                    all_vals = []
                                
                                if all_vals:
                                    selected_vals = st.multiselect(
                                        label=f"🗂️ {col_name} (Multi)",
                                        options=all_vals,
                                        default=all_vals,
                                        key=widget_key
                                    )
                                    if len(selected_vals) < len(all_vals):
                                        if not selected_vals:
                                            filters_sql.append("1=0") # No match
                                        else:
                                            has_null = "<Null>" in selected_vals
                                            non_null_vals = [v for v in selected_vals if v != "<Null>"]
                                            
                                            sub_conds = []
                                            if non_null_vals:
                                                placeholders = ", ".join(["?"] * len(non_null_vals))
                                                sub_conds.append(f'"{col_name}" IN ({placeholders})')
                                                filters_params.extend(non_null_vals)
                                            if has_null:
                                                sub_conds.append(f'"{col_name}" IS NULL')
                                                
                                            filters_sql.append(f"({' OR '.join(sub_conds)})")
                            else:
                                text_val = st.text_input(
                                    label=f"🔤 {col_name} (Contains)",
                                    value="",
                                    key=widget_key
                                )
                                if text_val.strip():
                                    filters_sql.append(f'LOWER("{col_name}") LIKE ?')
                                    filters_params.append(f"%{text_val.strip().lower()}%")

            # Section 2: Execute filtered SQL Query
            final_query = f'SELECT * FROM "{table_name}"'
            if filters_sql:
                final_query += " WHERE " + " AND ".join(filters_sql)
                
            try:
                df_filtered = db_manager.conn.execute(final_query, filters_params).df()
            except Exception as e:
                st.error(f"Error querying table data: {e}")
                df_filtered = pd.DataFrame()
            
            # Section 3: Render Dataframe & Download Button
            if not df_filtered.empty:
                col_meta_1, col_meta_2 = st.columns([3, 1])
                with col_meta_1:
                    st.caption(f"Showing **{len(df_filtered)}** of **{total_rows}** rows (Filtered)")
                with col_meta_2:
                    # Download Button
                    csv_bytes = df_filtered.to_csv(index=False).encode('utf-8')
                    st.download_button(
                          label="📥 Download Dataset",
                          data=csv_bytes,
                          file_name=f"filtered_{display_name}.csv",
                          mime="text/csv",
                          key=f"dl_{table_name}",
                          use_container_width=True
                    )
                
                # Split screen layout: Table on Left, Chart on Right
                col_table, col_chart = st.columns([5, 3])
                
                with col_table:
                    # Display dataframe
                    st.dataframe(df_filtered, use_container_width=True)
                    
                with col_chart:
                    st.markdown("<h4 style='margin-top: 0;'>📊 Data Distribution</h4>", unsafe_allow_html=True)
                    # Multiselect for columns
                    cols_list = [col[1] for col in columns_info]
                    # Select default column (first one)
                    default_sel = [cols_list[0]] if cols_list else []
                    selected_chart_cols = st.multiselect(
                        label="Group by Column(s)",
                        options=cols_list,
                        default=default_sel,
                        key=f"chart_cols_sel_{table_name}"
                    )
                    
                    if selected_chart_cols:
                        # Truncation helper
                        def shorten_val(val, max_len=18):
                            if not isinstance(val, str):
                                val = str(val)
                            if len(val) > max_len:
                                return val[:max_len-3] + "..."
                            return val
                        
                        # Concatenate columns
                        if len(selected_chart_cols) == 1:
                            series = df_filtered[selected_chart_cols[0]].astype(str)
                        else:
                            series = df_filtered[selected_chart_cols].astype(str).agg(' - '.join, axis=1)
                        
                        # Shorten the concatenated text
                        series_shortened = series.apply(lambda x: shorten_val(x, 18))
                        
                        # Value counts
                        df_counts = series_shortened.value_counts().reset_index()
                        df_counts.columns = ["Category", "Count"]
                        
                        # Group top categories and map others to "Other"
                        limit_categories = 7
                        if len(df_counts) > limit_categories:
                            # Sort descending
                            df_counts = df_counts.sort_values(by="Count", ascending=False)
                            df_top = df_counts.head(limit_categories - 1).copy()
                            other_count = df_counts.iloc[limit_categories - 1:]["Count"].sum()
                            other_row = pd.DataFrame([{"Category": "Other", "Count": other_count}])
                            df_counts = pd.concat([df_top, other_row], ignore_index=True)
                            
                        # Compute percentage
                        total_cnt = df_counts["Count"].sum()
                        if total_cnt > 0:
                            df_counts["Percentage"] = (df_counts["Count"] / total_cnt * 100).round(1)
                            df_counts["Label"] = df_counts["Category"] + " (" + df_counts["Percentage"].astype(str) + "%)"
                            
                            # Draw Altair arc/pie chart
                            pie_chart = alt.Chart(df_counts).mark_arc(innerRadius=0).encode(
                                theta=alt.Theta(field="Count", type="quantitative"),
                                color=alt.Color(
                                    field="Label", 
                                    type="nominal", 
                                    legend=alt.Legend(title="Category (%)", orient="bottom")
                                ),
                                tooltip=["Category", "Count", "Percentage"]
                            ).properties(
                                height=280
                            ).configure_view(
                                strokeWidth=0
                            )
                            
                            st.altair_chart(pie_chart, use_container_width=True)
                        else:
                            st.info("No data available to plot.")
                    else:
                        st.info("Please select at least one column to display distribution.")
            else:
                st.warning("No rows match the selected filters.")
            
            st.markdown("<br><hr style='border: 0; border-top: 1px solid rgba(120, 120, 120, 0.15);'><br>", unsafe_allow_html=True)
