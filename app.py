from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Post65 Building Stock Dashboard",
    page_icon="🏛️",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data_public"

NL_CSV = DATA_DIR / "bag_buildings_by_year_nl.csv"
PROVINCE_CSV = DATA_DIR / "bag_buildings_by_year_province.csv"
MUNICIPALITY_CSV = DATA_DIR / "bag_buildings_by_year_municipality.csv"
MONUMENTS_CSV = DATA_DIR / "rijksmonumenten_summary.csv"
MATCHED_MONUMENTS_CSV = DATA_DIR / "rijksmonumenten_matched.csv"
POST65_CSV = DATA_DIR / "post65_nominated_buildings.csv"

# Optional. The app does NOT require these to run.
BUILDING_POINTS_CSV = DATA_DIR / "bag_buildings_public_points.csv"


# -----------------------------
# Robust helpers
# -----------------------------
@st.cache_data(show_spinner=False)
def load_csv_auto(path: Path, max_rows=None) -> pd.DataFrame:
    """Safe CSV loader for comma or semicolon CSVs.

    Important: no row-wise string conversion on large files, because that can kill
    Streamlit Cloud health checks on large BAG point exports.
    """
    if not path.exists():
        return pd.DataFrame()

    try:
        sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
        first_line = sample.splitlines()[0] if sample.splitlines() else ""
        sep = ";" if first_line.count(";") > first_line.count(",") else ","

        df = pd.read_csv(
            path,
            sep=sep,
            encoding="utf-8-sig",
            engine="python",
            on_bad_lines="skip",
            nrows=max_rows,
        )
        df.columns = [str(c).strip().replace("\ufeff", "") for c in df.columns]
        df = df.dropna(how="all")

        # Remove separator-only rows such as ;;;;;;;;;;;; without expensive row-wise full conversion on big files.
        if len(df) <= 5000:
            df = df.loc[
                ~df.fillna("").astype(str).apply(
                    lambda row: all(x.strip() == "" for x in row), axis=1
                )
            ]

        return df
    except Exception as e:
        st.error(f"Could not read {path.name}: {e}")
        return pd.DataFrame()


def clean_year_count(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    if "year" not in df.columns or "building_count" not in df.columns:
        return pd.DataFrame()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["building_count"] = pd.to_numeric(df["building_count"], errors="coerce").fillna(0)
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    return df


def fmt_int(x):
    try:
        if x is None or pd.isna(x):
            return "n/a"
        return f"{int(round(float(x))):,}".replace(",", ".")
    except Exception:
        return "n/a"


def csv_button(df: pd.DataFrame, filename: str, label: str):
    if df.empty:
        return
    st.download_button(
        label=label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )


def normalize_text_series(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower()


def filter_by_province(df: pd.DataFrame, selected_province: str) -> pd.DataFrame:
    if df.empty or selected_province == "All Netherlands":
        return df
    for col in ["province", "province_name", "provincienaam"]:
        if col in df.columns:
            return df[normalize_text_series(df[col]) == selected_province.strip().lower()].copy()
    return df


def make_period_summary(df: pd.DataFrame, group_cols, start_year: int, end_year: int) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    total = (
        df.groupby(group_cols, as_index=False)["building_count"]
        .sum()
        .rename(columns={"building_count": "total_buildings"})
    )
    selected = (
        df[(df["year"] >= start_year) & (df["year"] <= end_year)]
        .groupby(group_cols, as_index=False)["building_count"]
        .sum()
        .rename(columns={"building_count": "selected_period_buildings"})
    )
    out = total.merge(selected, on=group_cols, how="left")
    out["selected_period_buildings"] = out["selected_period_buildings"].fillna(0)
    out["selected_period_percentage"] = (
        out["selected_period_buildings"] / out["total_buildings"] * 100
    )
    return out


# -----------------------------
# Load lightweight core data
# -----------------------------
df_nl = clean_year_count(load_csv_auto(NL_CSV))
df_prov = clean_year_count(load_csv_auto(PROVINCE_CSV))
df_muni = clean_year_count(load_csv_auto(MUNICIPALITY_CSV))
df_mon = load_csv_auto(MONUMENTS_CSV)
df_matched = load_csv_auto(MATCHED_MONUMENTS_CSV)
df_post65 = load_csv_auto(POST65_CSV)

# Optional point data: load a limited sample only, to avoid Streamlit Cloud memory/health crashes.
df_points_sample = load_csv_auto(BUILDING_POINTS_CSV, max_rows=20000)


st.title("Post65 Building Stock & Heritage Protection in the Netherlands")
st.caption(
    "BAG provides construction year and building stock. Heritage status is shown separately "
    "through national rijksmonumenten, Post65 nominated objects, and a placeholder for municipal heritage."
)

if df_nl.empty:
    st.error("Missing or invalid data_public/bag_buildings_by_year_nl.csv")
    st.stop()

min_year = int(df_nl["year"].min())
max_year = int(df_nl["year"].max())

with st.sidebar:
    st.header("Filters")
    default_start = 1965 if min_year <= 1965 <= max_year else min_year
    default_end = 1990 if min_year <= 1990 <= max_year else max_year

    c1, c2 = st.columns(2)
    start_year = c1.number_input("Start year", min_value=min_year, max_value=max_year, value=default_start, step=1)
    end_year = c2.number_input("End year", min_value=min_year, max_value=max_year, value=default_end, step=1)

    if start_year > end_year:
        st.error("Start year must be before end year.")
        st.stop()

    province_options = ["All Netherlands"]
    if not df_prov.empty and "province_name" in df_prov.columns:
        province_options += sorted(df_prov["province_name"].dropna().astype(str).unique().tolist())
    elif not df_post65.empty and "province" in df_post65.columns:
        province_options += sorted(df_post65["province"].dropna().astype(str).unique().tolist())

    selected_province = st.selectbox("Province", province_options)


selected_nl = df_nl[(df_nl["year"] >= start_year) & (df_nl["year"] <= end_year)]
total_buildings_nl = df_nl["building_count"].sum()
selected_buildings_nl = selected_nl["building_count"].sum()
selected_pct_nl = selected_buildings_nl / total_buildings_nl * 100 if total_buildings_nl else 0

protected_total = None
if not df_mon.empty and "protected_monuments_total" in df_mon.columns:
    protected_total = df_mon["protected_monuments_total"].iloc[0]

filtered_post65 = filter_by_province(df_post65, selected_province)
filtered_matched = filter_by_province(df_matched, selected_province)


# -----------------------------
# Tabs
# -----------------------------
tabs = st.tabs([
    "Overview",
    "Year analysis",
    "Province comparison",
    "Municipality view",
    "Heritage status",
    "Post65 objects",
    "Protected monuments",
    "Downloads",
    "Method",
])

with tabs[0]:
    st.subheader("National evidence summary")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total BAG buildings", fmt_int(total_buildings_nl))
    m2.metric(f"Buildings built {start_year}–{end_year}", fmt_int(selected_buildings_nl))
    m3.metric("Share of total BAG stock", f"{selected_pct_nl:.2f}%")
    m4.metric("Protected monuments in dataset", fmt_int(protected_total))

    sentence = (
        f"According to the BAG building-stock export, {fmt_int(selected_buildings_nl)} buildings "
        f"in the Netherlands were built between {start_year} and {end_year}, representing "
        f"{selected_pct_nl:.2f}% of the current registered building stock. Heritage protection is "
        f"represented separately through rijksmonumenten and Post65 nominated objects."
    )
    st.markdown("### Copy-ready petition sentence")
    st.text_area("Evidence text", sentence, height=130)

    summary = pd.DataFrame([{
        "start_year": start_year,
        "end_year": end_year,
        "total_bag_buildings": int(total_buildings_nl),
        "selected_period_buildings": int(selected_buildings_nl),
        "selected_period_percentage": selected_pct_nl,
        "protected_monuments_total": protected_total,
        "post65_objects_loaded": len(df_post65),
    }])
    csv_button(summary, f"post65_summary_{start_year}_{end_year}.csv", "Download current summary CSV")

with tabs[1]:
    st.subheader("Building stock by construction year")
    chart_df = df_nl.copy()
    chart_df["period"] = chart_df["year"].apply(
        lambda y: f"Selected {start_year}–{end_year}" if start_year <= y <= end_year else "Other years"
    )
    fig = px.bar(
        chart_df,
        x="year",
        y="building_count",
        color="period",
        title=f"National BAG buildings by construction year ({start_year}–{end_year} selected)",
        labels={"year": "Construction year", "building_count": "Number of BAG buildings", "period": "Period"},
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(selected_nl, width="stretch")
    csv_button(selected_nl, f"bag_buildings_nl_{start_year}_{end_year}.csv", "Download selected national years")

with tabs[2]:
    st.subheader("Province comparison")
    if df_prov.empty:
        st.warning("Missing data_public/bag_buildings_by_year_province.csv")
    else:
        prov_summary = make_period_summary(df_prov, ["province_name"], start_year, end_year)
        if selected_province != "All Netherlands":
            prov_summary = filter_by_province(prov_summary, selected_province)
        fig = px.bar(
            prov_summary.sort_values("selected_period_percentage", ascending=False),
            x="province_name",
            y="selected_period_percentage",
            hover_data=["total_buildings", "selected_period_buildings"],
            title=f"Share of buildings built {start_year}–{end_year} by province",
            labels={"province_name": "Province", "selected_period_percentage": "Selected-period share (%)"},
        )
        st.plotly_chart(fig, width="stretch")
        st.dataframe(prov_summary, width="stretch")
        csv_button(prov_summary, f"province_summary_{start_year}_{end_year}.csv", "Download province summary")

with tabs[3]:
    st.subheader("Municipality view")
    if df_muni.empty:
        st.warning("Missing data_public/bag_buildings_by_year_municipality.csv")
    else:
        muni_df = filter_by_province(df_muni, selected_province)
        group_cols = []
        if "province_name" in muni_df.columns:
            group_cols.append("province_name")
        if "municipality_name" in muni_df.columns:
            group_cols.append("municipality_name")
        elif "gemeentecode" in muni_df.columns:
            group_cols.append("gemeentecode")

        if not group_cols:
            st.warning("Municipality CSV needs municipality_name or gemeentecode.")
        else:
            muni_summary = make_period_summary(muni_df, group_cols, start_year, end_year)
            muni_summary = muni_summary.sort_values("selected_period_buildings", ascending=False)
            fig = px.bar(
                muni_summary.head(30),
                x=group_cols[-1],
                y="selected_period_buildings",
                color="selected_period_percentage",
                title=f"Top municipalities: buildings built {start_year}–{end_year}",
                labels={group_cols[-1]: "Municipality", "selected_period_buildings": "Buildings in selected period", "selected_period_percentage": "Share (%)"},
            )
            st.plotly_chart(fig, width="stretch")
            st.dataframe(muni_summary, width="stretch")
            csv_button(muni_summary, f"municipality_summary_{start_year}_{end_year}.csv", "Download municipality summary")

with tabs[4]:
    st.subheader("Heritage status: national vs municipal")
    st.markdown(
        """
This tab separates the semantic layers requested by Ana.

- **BAG building stock**: construction years, counts, and optional building locations.
- **Rijksmonumenten**: nationally protected monuments.
- **Post65 nominated objects**: national RCE Post65 nominated/example layer.
- **Gemeentelijke monumenten**: municipal heritage; not loaded yet and cannot be derived from BAG.

Important: BAG `pandstatus` is **not** a monument or heritage-protection status.
"""
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Rijksmonument records", fmt_int(len(filtered_matched) if not filtered_matched.empty else protected_total))
    c2.metric("Post65 nominated objects", fmt_int(len(filtered_post65)))
    c3.metric("Municipal heritage records", "Not loaded")

    status_rows = pd.DataFrame([
        {"Layer": "BAG building stock", "Available": "Yes", "Meaning": "Denominator: building counts by year", "Heritage level": "Not heritage status"},
        {"Layer": "Rijksmonumenten", "Available": "Yes, if exported", "Meaning": "Nationally protected heritage", "Heritage level": "National"},
        {"Layer": "Post65 nominated objects", "Available": "Yes", "Meaning": "National Post65 candidate/example layer", "Heritage level": "National candidate / nominated"},
        {"Layer": "Gemeentelijke monumenten", "Available": "Not loaded", "Meaning": "Requires Kadaster/BRK or municipal dataset", "Heritage level": "Municipal"},
    ])
    st.dataframe(status_rows, width="stretch")

with tabs[5]:
    st.subheader("Post65 objects — national list")
    if df_post65.empty:
        st.warning("Missing data_public/post65_nominated_buildings.csv")
    else:
        st.markdown("These are shown as a named national Post65 layer. They are not forced to match BAG.")
        c1, c2, c3 = st.columns(3)
        c1.metric("Objects shown", fmt_int(len(filtered_post65)))
        c2.metric("Provinces", fmt_int(filtered_post65["province"].nunique() if "province" in filtered_post65.columns else 0))
        c3.metric("Typologies", fmt_int(filtered_post65["typology"].nunique() if "typology" in filtered_post65.columns else 0))

        if "province" in filtered_post65.columns:
            province_summary = (
                filtered_post65.dropna(subset=["province"])
                .groupby("province", as_index=False)
                .size()
                .rename(columns={"size": "object_count"})
                .sort_values("object_count", ascending=False)
            )
            fig = px.bar(province_summary, x="province", y="object_count", title="Post65 objects by province")
            st.plotly_chart(fig, width="stretch")

        if "typology" in filtered_post65.columns:
            typology_summary = (
                filtered_post65.dropna(subset=["typology"])
                .groupby("typology", as_index=False)
                .size()
                .rename(columns={"size": "object_count"})
                .sort_values("object_count", ascending=False)
            )
            fig = px.bar(typology_summary, x="typology", y="object_count", title="Post65 objects by typology")
            st.plotly_chart(fig, width="stretch")

        st.dataframe(filtered_post65, width="stretch")
        csv_button(filtered_post65, "post65_nominated_buildings_filtered.csv", "Download filtered Post65 objects")

with tabs[6]:
    st.subheader("Protected monuments dataset")
    if df_mon.empty:
        st.warning("Missing data_public/rijksmonumenten_summary.csv")
    else:
        st.dataframe(df_mon, width="stretch")

    st.markdown("### Matched national monument records")
    if filtered_matched.empty:
        st.info("No rijksmonumenten_matched.csv file found or no records for the selected province.")
    else:
        st.dataframe(filtered_matched, width="stretch")
        csv_button(filtered_matched, "rijksmonumenten_matched_filtered.csv", "Download filtered national monuments")

with tabs[7]:
    st.subheader("Download dashboard datasets")
    csv_button(df_nl, "bag_buildings_by_year_nl.csv", "Download national BAG by year")
    csv_button(df_prov, "bag_buildings_by_year_province.csv", "Download BAG by province/year")
    csv_button(df_muni, "bag_buildings_by_year_municipality.csv", "Download BAG by municipality/year")
    csv_button(df_mon, "rijksmonumenten_summary.csv", "Download monument summary")
    csv_button(df_matched, "rijksmonumenten_matched.csv", "Download matched national monuments")
    csv_button(df_post65, "post65_nominated_buildings.csv", "Download Post65 nominated objects")

with tabs[8]:
    st.subheader("Method")
    st.markdown(
        """
**Core distinction**

- BAG is used for the denominator: total building stock and construction-year filtering.
- Rijksmonumenten are used for the national protected heritage layer.
- Post65 nominated objects are a separate national named-object layer.
- Municipal heritage requires a separate Kadaster/BRK or municipal source and should not be inferred from BAG.

**Main calculation**

```text
Selected-period share = BAG buildings built in selected year range / total BAG buildings
```

**Important limitation**

BAG `pandstatus` is not a monument or heritage-protection status. It only describes the BAG lifecycle/status of a building object.
"""
    )
