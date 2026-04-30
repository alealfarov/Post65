# Post65 Building Stock & Heritage Protection Dashboard

A public Streamlit dashboard to explore how many Dutch buildings were built during the Post65 period (1965–1990) and how many are nationally protected as heritage.

## Run locally

```bash
pip install -r requirements.txt
python scripts/03_create_duckdb.py
streamlit run app.py
```

## Data workflow

1. Place official/raw datasets in `data_raw/`.
2. Process them into clean CSV files in `data_processed/`.
3. Run `scripts/03_create_duckdb.py` to create `dashboard.duckdb`.
4. Run the Streamlit app.


## Method note

Use BAG `panden` for building objects where possible. Do not mix BAG buildings with CBS `woningen` unless this limitation is clearly explained.
