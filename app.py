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
BUILDING_POINTS_CSV = DATA_DIR / "bag_buildings_public_points.csv"
POST65_CSV = DATA_DIR / "post65_nominated_buildings.csv"


@st.cache_data(show_spinner=False)
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as e:
        st.warning(f"Could not read {path.name}: {e}")
        return pd.DataFrame()


def clean_year_count(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    if "year" not in df.columns or "building_count" not in df.columns:
        return pd.DataFrame()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["building_count"] = pd.to_numeric(df["building_count"], errors="coerce").fillna(0)
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    return df


def clean_points(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for col in ["year", "lat", "lon"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    required = [c for c in ["year", "lat", "lon"] if c in df.columns]
    if required:
        df = df.dropna(subset=required)
    if "year" in df.columns:
        df["year"] = df["year"].astype(int)
    return df


def clean_text_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].fillna("").astype(str).str.strip()
    return df


def fmt_int(x):
    if x is None or pd.isna(x):
        return "n/a"
    return f"{int(round(float(x))):,}".replace(",", ".")


def csv_button(df: pd.DataFrame, filename: str, label: str):
    if df.empty:
        return
    st.download_button(
        label=label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )


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


def find_col(df: pd.DataFrame, names):
    lookup = {c.lower().strip(): c for c in df.columns}
    for name in names:
        if name.lower().strip() in lookup:
            return lookup[name.lower().strip()]
    return None


def filter_by_province(df: pd.DataFrame, selected_province: str) -> pd.DataFrame:
    if df.empty or selected_province == "All Netherlands":
        return df
    col = find_col(df, ["province_name", "province", "provincienaam"])
    if not col:
        return df
    return df[df[col].astype(str).str.lower().str.strip() == selected_province.lower().strip()].copy()


# Load data
df_nl = clean_year_count(load_csv(NL_CSV))
df_prov = clean_year_count(load_csv(PROVINCE_CSV))
df_muni = clean_year_count(load_csv(MUNICIPALITY_CSV))
df_mon = clean_text_cols(load_csv(MONUMENTS_CSV))
df_matched = clean_text_cols(load_csv(MATCHED_MONUMENTS_CSV))
df_points = clean_points(load_csv(BUILDING_POINTS_CSV))
df_post65 = clean_text_cols(load_csv(POST65_CSV))

st.title("Post65 Building Stock & Heritage Protection in the Netherlands")
st.caption(
    "BAG provides construction year and building stock. Heritage protection is represented separately through national monuments, Post65 objects, and future municipal heritage data."
)

if df_nl.empty:
    st.error("Missing or invalid data_public/bag_buildings_by_year_nl.csv")
    st.stop()

min_year = int(df_nl["year"].min())
max_year = int(df_nl["year"].max())

with st.sidebar:
    st.header("Filters")
    st.markdown("### Construction year range")
    col_a, col_b = st.columns(2)
    default_start = 1965 if min_year <= 1965 <= max_year else min_year
    default_end = 1990 if min_year <= 1990 <= max_year else max_year
    start_year = col_a.number_input("Start year", min_value=min_year, max_value=max_year, value=default_start, step=1)
    end_year = col_b.number_input("End year", min_value=min_year, max_value=max_year, value=default_end, step=1)
    if start_year > end_year:
        st.error("Start year must be before end year.")
        st.stop()

    province_options = ["All Netherlands"]
    if not df_prov.empty and "province_name" in df_prov.columns:
        province_options += sorted(df_prov["province_name"].dropna().astype(str).unique().tolist())
    selected_province = st.selectbox("Province", province_options)

selected_nl = df_nl[(df_nl["year"] >= start_year) & (df_nl["year"] <= end_year)]
total_buildings_nl = df_nl["building_count"].sum()
selected_buildings_nl = selected_nl["building_count"].sum()
selected_pct_nl = selected_buildings_nl / total_buildings_nl * 100 if total_buildings_nl else 0

filtered_points = df_points.copy()
if not filtered_points.empty and "year" in filtered_points.columns:
    filtered_points = filtered_points[(filtered_points["year"] >= start_year) & (filtered_points["year"] <= end_year)].copy()
filtered_points = filter_by_province(filtered_points, selected_province)

filtered_matched = filter_by_province(df_matched, selected_province)
filtered_post65 = filter_by_province(df_post65, selected_province)

protected_total = None
if not df_mon.empty and "protected_monuments_total" in df_mon.columns:
    protected_total = pd.to_numeric(df_mon["protected_monuments_total"], errors="coerce").iloc[0]

national_count = len(filtered_matched) if not filtered_matched.empty else 0
post65_count = len(filtered_post65) if not filtered_post65.empty else 0
municipal_count = 0

tabs = st.tabs([
    "Overview",
    "Year analysis",
    "Province comparison",
    "Municipality view",
    "Heritage status",
    "Protected monuments",
    "Building locations",
    "Downloads",
    "Method",
])

with tabs[0]:
    st.subheader("National evidence summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total BAG buildings", fmt_int(total_buildings_nl))
    c2.metric(f"Buildings built {start_year}–{end_year}", fmt_int(selected_buildings_nl))
    c3.metric("Share of total BAG stock", f"{selected_pct_nl:.2f}%")
    c4.metric("Protected monuments in dataset", fmt_int(protected_total))

    st.markdown("### Copy-ready evidence sentence")
    sentence = (
        f"According to the BAG building-stock export, {fmt_int(selected_buildings_nl)} buildings "
        f"in the Netherlands were built between {start_year} and {end_year}, representing "
        f"{selected_pct_nl:.2f}% of the current registered building stock. "
        f"Heritage protection is represented separately through national rijksmonumenten, "
        f"Post65 nominated objects, and future municipal heritage records."
    )
    st.text_area("Evidence text", sentence, height=130)

    summary = pd.DataFrame([{
        "start_year": start_year,
        "end_year": end_year,
        "total_bag_buildings": int(total_buildings_nl),
        "selected_period_buildings": int(selected_buildings_nl),
        "selected_period_percentage": selected_pct_nl,
        "protected_monuments_total": protected_total,
        "national_monument_records_loaded": national_count,
        "post65_nominated_objects_loaded": post65_count,
        "municipal_heritage_records_loaded": municipal_count,
    }])
    st.dataframe(summary, width="stretch")
    csv_button(summary, f"post65_summary_{start_year}_{end_year}.csv", "Download current summary CSV")

with tabs[1]:
    st.subheader("Building stock by construction year")
    chart_df = df_nl.copy()
    chart_df["period"] = chart_df["year"].apply(lambda y: f"Selected {start_year}–{end_year}" if start_year <= y <= end_year else "Other years")
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
            prov_summary = prov_summary[prov_summary["province_name"] == selected_province]
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
This tab keeps the heritage layers conceptually separate:

- **BAG** gives building stock, construction year, coordinates, and `pandstatus`.
- **Rijksmonumenten** are national protected monuments.
- **Post65 nominated objects** are a national RCE Post65 selection/candidate layer.
- **Gemeentelijke monumenten** are municipal heritage records and require a separate Kadaster/BRK or municipal source.

Important: BAG `pandstatus` is **not** a heritage-protection status.
"""
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("National rijksmonument records", fmt_int(national_count))
    c2.metric("Post65 nominated objects", fmt_int(post65_count))
    c3.metric("Municipal heritage records", "Not loaded")
    c4.metric("BAG records in selected period", fmt_int(len(filtered_points)))

    status_rows = pd.DataFrame([
        {"layer": "BAG building stock", "available": "Yes", "source/file": "bag_buildings_public_points.csv", "heritage_level": "Not heritage status"},
        {"layer": "Rijksmonumenten", "available": "Yes, if exported", "source/file": "rijksmonumenten_matched.csv", "heritage_level": "National"},
        {"layer": "Post65 nominated objects", "available": "Yes", "source/file": "post65_nominated_buildings.csv", "heritage_level": "National candidate / selection"},
        {"layer": "Gemeentelijke monumenten", "available": "Not loaded yet", "source/file": "Future Kadaster/BRK or municipality source", "heritage_level": "Municipal"},
    ])
    st.dataframe(status_rows, width="stretch")

    st.markdown("### National Post65 nominated objects")
    if filtered_post65.empty:
        st.warning("Missing data_public/post65_nominated_buildings.csv or no records for the selected province.")
    else:
        st.dataframe(filtered_post65, width="stretch")
        csv_button(filtered_post65, "post65_nominated_buildings_filtered.csv", "Download filtered Post65 nominated objects")

        province_col = find_col(filtered_post65, ["province", "province_name", "provincienaam"])
        typology_col = find_col(filtered_post65, ["typology", "type", "typologie"])
        year_col = find_col(filtered_post65, ["year", "bouwjaar"])

        if province_col:
            province_summary = filtered_post65.groupby(province_col, as_index=False).size().rename(columns={"size": "object_count"})
            fig = px.bar(province_summary.sort_values("object_count", ascending=False), x=province_col, y="object_count", title="Post65 objects by province")
            st.plotly_chart(fig, width="stretch")

        if typology_col:
            typology_summary = (
                filtered_post65[filtered_post65[typology_col].astype(str).str.strip() != ""]
                .groupby(typology_col, as_index=False)
                .size()
                .rename(columns={"size": "object_count"})
                .sort_values("object_count", ascending=False)
            )
            if not typology_summary.empty:
                fig = px.bar(typology_summary, x=typology_col, y="object_count", title="Post65 objects by typology")
                st.plotly_chart(fig, width="stretch")

        if year_col:
            tmp = filtered_post65.copy()
            tmp[year_col] = pd.to_numeric(tmp[year_col], errors="coerce")
            year_summary = tmp.dropna(subset=[year_col]).groupby(year_col, as_index=False).size().rename(columns={"size": "object_count"})
            if not year_summary.empty:
                fig = px.bar(year_summary, x=year_col, y="object_count", title="Post65 objects by year")
                st.plotly_chart(fig, width="stretch")

    st.markdown("### Municipal heritage")
    st.info(
        "Municipal heritage is not loaded yet. This layer must come from Kadaster/BRK restrictions or municipal monument datasets. It cannot be derived from BAG."
    )

with tabs[5]:
    st.subheader("Protected monuments dataset")
    if df_mon.empty:
        st.warning("Missing data_public/rijksmonumenten_summary.csv")
    else:
        st.dataframe(df_mon, width="stretch")
    st.markdown("### Matched national monument records")
    if filtered_matched.empty:
        st.info("No matched national monument records found yet.")
    else:
        st.dataframe(filtered_matched, width="stretch")
        csv_button(filtered_matched, "rijksmonumenten_matched_filtered.csv", "Download matched national monuments")

with tabs[6]:
    st.subheader("Building locations")
    if df_points.empty:
        st.warning("Missing data_public/bag_buildings_public_points.csv")
    else:
        st.write(f"Showing BAG building points constructed between {start_year} and {end_year}.")
        st.metric("Buildings in current filter", fmt_int(len(filtered_points)))
        csv_button(filtered_points, f"buildings_{start_year}_{end_year}_{selected_province}.csv".replace(" ", "_"), "Download selected building list as CSV")

        st.warning("Map rendering is intentionally limited to avoid Streamlit Cloud memory resets.")
        max_points = st.slider("Maximum points to show in table/map sample", min_value=100, max_value=10000, value=2000, step=100)
        sample_df = filtered_points.head(max_points)
        if not sample_df.empty and {"lat", "lon"}.issubset(sample_df.columns):
            st.map(sample_df[["lat", "lon"]].copy(), latitude="lat", longitude="lon")

        display_cols = [c for c in ["pand_id", "year", "province_name", "municipality_name", "gemeentecode", "pandstatus", "lat", "lon"] if c in filtered_points.columns]
        st.dataframe(filtered_points[display_cols].head(max_points), width="stretch")

with tabs[7]:
    st.subheader("Download dashboard datasets")
    csv_button(df_nl, "bag_buildings_by_year_nl.csv", "Download national BAG by year")
    csv_button(df_prov, "bag_buildings_by_year_province.csv", "Download BAG by province/year")
    csv_button(df_muni, "bag_buildings_by_year_municipality.csv", "Download BAG by municipality/year")
    csv_button(df_points, "bag_buildings_public_points.csv", "Download BAG public points")
    csv_button(df_mon, "rijksmonumenten_summary.csv", "Download monument summary")
    csv_button(df_matched, "rijksmonumenten_matched.csv", "Download matched national monuments")
    csv_button(df_post65, "post65_nominated_buildings.csv", "Download Post65 nominated objects")

with tabs[8]:
    st.subheader("Method")
    st.markdown(
        """
**Core distinction**

- BAG is used for the denominator: total building stock, construction year, location, and `pandstatus`.
- Rijksmonumenten are used for the national protected heritage layer.
- Post65 nominated objects are loaded as a named national RCE Post65 selection/candidate layer.
- Municipal heritage requires a separate municipal/Kadaster/BRK source and should not be inferred from BAG.

**Main calculation**

```text
Selected-period share = BAG buildings built in selected year range / total BAG buildings
```

**Important limitation**

BAG `pandstatus` is not a monument or heritage-protection status. It only describes the BAG lifecycle/status of a building object.
"""
    )
