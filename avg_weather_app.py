import streamlit as st
#import matplotlib.pyplot as plt
import plotly.express as px
from datetime import datetime
from meteostat import Point, Daily
import pandas as pd
import kaleido
import requests
import io
import re


# --- Define Function ---
def get_weather_data(postcode, years):
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
    '''
    # Create figure (3x2 grid)
    fig, axes = plt.subplots(3, 2, figsize=(12, 10))
    axes = axes.flatten()

    plot_vars = {
        'tavg': 'Average Temperature (°C)',
        'tmin': 'Minimum Temperature (°C)',
        'tmax': 'Maximum Temperature (°C)',
        'prcp': 'Precipitation (mm)',
        'pres': 'Pressure (hPa)',
        'wspd': 'Wind Speed (km/h)'
    }

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#17becf', '#9467bd', '#8c564b']

    for ax, (col, label), color in zip(axes, plot_vars.items(), colors):
        if col in monthly_means.columns:
            ax.plot(monthly_means.index, monthly_means[col],
                    color=color, marker='o', linestyle='-', linewidth=2)
            ax.set_title(label)
            ax.set_xlabel('Month')
            ax.grid(True, linestyle='--', alpha=0.6)
        else:
            ax.text(0.5, 0.5, f"No data for {label}",
                    ha='center', va='center')
            ax.set_axis_off()

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    return monthly_means, fig, buf
    '''

    # --- Create interactive Plotly figure ---
    plot_vars = {
        'tavg': 'Average Temperature (°C)',
        'tmin': 'Minimum Temperature (°C)',
        'tmax': 'Maximum Temperature (°C)',
        'prcp': 'Precipitation (mm)',
        'pres': 'Pressure (hPa)',
        'wspd': 'Wind Speed (km/h)'
    }

    # Filter available columns only
    available_vars = {k: v for k, v in plot_vars.items() if k in monthly_means.columns}

    # Convert to long format for Plotly
    data_long = monthly_means.reset_index().melt(id_vars='month',
                                             value_vars=list(available_vars.keys()),
                                             var_name='Variable',
                                             value_name='Value')

    # Map friendly labels
    data_long['Variable'] = data_long['Variable'].map(available_vars)

    # Create interactive line plot
    fig = px.line(
        data_long,
        x='month',
        y='Value',
        color='Variable',
        markers=True,
        title=f"Monthly Weather Averages for {postcode.upper()} ({years} Years)",
        template='plotly_white'
    )

    fig.update_layout(
        xaxis_title="Month",
        yaxis_title="Value",
        legend_title="Variable",
        font=dict(size=14),
        hovermode='x unified',
        title_x=0.5
    )

    buf = io.BytesIO()
    fig.write_image(buf, format='png')
    buf.seek(0)
    return monthly_means, fig, buf

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

if st.sidebar.button("Run Analysis"):
    st.session_state['run'] = True
    with st.spinner("Fetching and processing weather data..."):
        monthly_means, fig, buf = get_weather_data(postcode, years)

    if monthly_means is not None:
        with tab2:
            st.dataframe(monthly_means.round(2))

            # download csv of data
            csv = monthly_means.to_csv().encode('utf-8')
            st.download_button(
                label="Download Monthly Averages as CSV file",
                data=csv,
                file_name=f"weather_summary_{postcode}.csv",
                mime="text/csv"
            )

        with tab1:
            st.plotly_chart(fig, use_container_width=True)

            # download png of plots
            st.download_button(
                label="Download Weather Plots as PNG",
                data=buf,
                file_name=f"weather_plots_{postcode}.png",
                mime="image/png"
            )


with st.sidebar.expander("Advanced Options"):
    show_trends = st.checkbox("Show trend lines")

st.markdown(
    """
    <hr>
    <p style='text-align: center; font-size: 14px; color: grey;'>
    © 2025 Climate Analytics Co. | Data sourced via Meteostat API
    </p>
    """,
    unsafe_allow_html=True
)


#   cd /Users/cam/Documents/python/weather_app
#   streamlit run avg_weather_app.py
