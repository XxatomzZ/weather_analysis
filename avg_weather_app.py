import streamlit as st
#import matplotlib.pyplot as plt
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from datetime import datetime
from meteostat import Point, Daily
import pandas as pd
#import kaleido
import requests
import io
import re


# --- Define Function ---
def get_weather_data(postcode, years, show_trends=False):
    # Fetch coordinates
    res = requests.get(f"https://api.postcodes.io/postcodes/{postcode}")
    if res.status_code != 200 or res.json()['status'] != 200:
        st.error("Invalid postcode. Please try again.")
        return None, None

    pc_data = res.json()
    lat = pc_data['result']['latitude']
    long = pc_data['result']['longitude']
    st.success(f"Coordinates for {postcode}: {lat:.4f}, {long:.4f}")

    # Define location and date range
    loc = Point(lat, long)
    end = datetime.now()
    start = datetime(end.year - years,1, 1)


    # Fetch daily data
    data = Daily(loc, start, end)
    data = data.fetch()

    if data.empty:
        st.error("No weather data available for this postcode.")
        return None, None

    # Process data
    data.index = pd.to_datetime(data.index)
    data['month'] = data.index.month
    monthly_means = data.groupby('month').mean(numeric_only=True)
    monthly_means.index = monthly_means.index.map({
        1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr', 5:'May', 6:'Jun',
        7:'Jul', 8:'Aug', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dec'
    })
    # Add number of days in each month (non-leap year assumption)
    days_in_month = {
        'Jan': 31, 'Feb': 28, 'Mar': 31, 'Apr': 30,
        'May': 31, 'Jun': 30, 'Jul': 31, 'Aug': 31,
        'Sep': 30, 'Oct': 31, 'Nov': 30, 'Dec': 31
    }

    # Calculate average daily sunshine (hours per day)
    if 'tsun' in monthly_means.columns:
        monthly_means['tsun_daily'] = [
            monthly_means.loc[m, 'tsun'] / days_in_month[m] for m in monthly_means.index
        ]
    if 'tsun' in monthly_means.columns:
        monthly_means = monthly_means.drop(columns=['tsun'])

    # --- Create combined and individual interactive plots ---
    plot_vars = {
        'tavg': 'Average Temperature (°C)',
        'tmin': 'Minimum Temperature (°C)',
        'tmax': 'Maximum Temperature (°C)',
        'prcp': 'Precipitation (mm)',
        'tsun_daily': 'Average Daily Sunshine (hr/day)',
        'wspd': 'Wind Speed (km/h)'
    }

    # Filter only available variables
    available_vars = {k: v for k, v in plot_vars.items() if k in monthly_means.columns}

    # Create combined grid layout
    fig = make_subplots(rows=3, cols=2, subplot_titles=list(available_vars.values()))
    row_col_map = {
        0: (1, 1), 1: (1, 2),
        2: (2, 1), 3: (2, 2),
        4: (3, 1), 5: (3, 2)
    }

    # Color map for variables
    color_map = {
        'tavg': 'green',
        'tmax': 'red',
        'tmin': 'lightblue',
        'prcp': 'blue',
        'tsun_daily': 'orange',
        'wspd': 'grey'
    }

    mode_type = "lines+markers" if show_trends else "markers"
    for i, (col, label) in enumerate(available_vars.items()):
        fig.add_trace(
            go.Scatter(
                x=monthly_means.index,
                y=monthly_means[col],
                mode=mode_type,  # ← use show_trends
                name=label,
                line=dict(color=color_map[col]),
                hovertemplate = '%{x}<br>%{y:.2f}'       # <-- rounds y to 2 decimals
            ),
            row=row_col_map[i][0],
            col=row_col_map[i][1]
        )

    fig.update_layout(
        height=800,
        width=1000,
        title_text=f"Average Monthly Weather Overview for {postcode.upper()} ({years} Years)",
        template="plotly_white",
        showlegend=False
    )

    # --- Create individual plots for each variable ---
    individual_figs = {}
    for var, label in available_vars.items():
        individual_figs[var] = px.line(
            monthly_means,
            x=monthly_means.index,
            y=var,
            title=f"{label} ({postcode.upper()})",
            template='plotly_white',
            color_discrete_sequence=[color_map[var]]  # <-- set the color
        )

        # Adjust markers/lines based on show_trends
        if show_trends:
            individual_figs[var].update_traces(
                mode="lines+markers",
                hovertemplate='%{x}<br>%{y:.2f}'  # <-- rounds y to 2 decimals
            )
        else:
            individual_figs[var].update_traces(
                mode="markers",
                hovertemplate = '%{x}<br>%{y:.2f}'  # <-- rounds y to 2 decimals
            )

        if not show_trends:
            individual_figs[var].update_traces(mode="markers")  # override line if needed



    # Return all data and figures
    return monthly_means, fig, plot_vars, individual_figs


# --- Streamlit UI ---
st.set_page_config(
    page_title="UK Weather Analysis",   # Title shown in browser tab
    page_icon="🌦️",                    # Emoji or image path (favicon)
    layout="wide",                      # 'centered' or 'wide'
    initial_sidebar_state="expanded"    # 'expanded' or 'collapsed'
)

st.title("UK Weather Pattern Analysis")
st.subheader("Analyse average monthly weather by postcode")
st.markdown("---")  # Horizontal divider line
st.caption("Data from Meteostat (2005–2025)")

tab1, tab2 = st.tabs(["Charts", "Data Table"])

st.sidebar.header("Settings ⚙️")

postcode = st.sidebar.text_input("Enter a UK Postcode", "---- ---")
if postcode:
    if not re.match(r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$", postcode, re.I):
        st.error("Invalid UK postcode")

years = st.sidebar.slider(
    "Years of historical data to analyse",
    min_value=1,
    max_value=20,
    value=10,
    step=1,
    help="Select how many past years of data to include (1–20 years)"
)

with st.sidebar.expander("Advanced Options"):
    show_trends = st.checkbox("Show trend lines", value=True)


if st.sidebar.button("Run Analysis"):
    st.session_state['run'] = True
    with st.spinner("Fetching and processing weather data..."):
        monthly_means, fig, plot_vars, individual_figs = get_weather_data(postcode, years, show_trends)

    if monthly_means is not None:
        with tab2:
            # Remove unused columns
            columns_to_drop = ['snow', 'wdir', 'wpgt', 'pres']
            monthly_means = monthly_means.drop(columns=[c for c in columns_to_drop if c in monthly_means.columns])

            # Rename table headers before displaying
            readable_columns = {
                'tavg': 'Average Temperature (°C)',
                'tmin': 'Minimum Temperature (°C)',
                'tmax': 'Maximum Temperature (°C)',
                'prcp': 'Precipitation (mm)',
                'tsun_daily': 'Average Daily Sunshine (hr/day)',
                'wspd': 'Wind Speed (km/h)'
            }

            display_df = monthly_means.rename(columns=readable_columns)
            st.dataframe(display_df.round(2))


            # download csv of data
            csv = monthly_means.to_csv().encode('utf-8')
            st.download_button(
                label="Download Monthly Averages as CSV file",
                data=csv,
                file_name=f"weather_summary_{postcode}.csv",
                mime="text/csv"
            )

        with tab1:
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={
                    'displayModeBar': True,
                    'modeBarButtonsToAdd': ['downloadImage'],  # <-- browser-based PNG download
                }
            )
            st.info("You can download the plot as a PNG directly from the chart's toolbar.")

st.markdown(
    """
    <hr>
    <p style='text-align: center; font-size: 14px; color: grey;'>
    © 2025 | Data sourced via Meteostat API
    </p>
    """,
    unsafe_allow_html=True
)


#   cd /Users/cam/Documents/python/weather_app
#   streamlit run avg_weather_app.py
