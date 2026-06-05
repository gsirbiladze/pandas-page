### We are building streamlit based website
- Has to be written in one python file
- At startup should be listing all csv files in the folder passed by -d switch or current folder
- All csv files should be loaded in DuckDB. Each dedicated table for each CSV file.
- Periodically folder should be scanned to refresh DuckDB in case of new files apparence and data changes in the CSV files
- On the webpage will be displayed whole content of DuckDB.
- Left side of the screen will be placed list of table names(CSV file names) as switches to display the corresponding data
- Data should filtarable by every field

