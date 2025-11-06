import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime
from meteostat import Point, Daily
import pandas as pd
import requests
import io


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



# --- Streamlit UI ---
st.title("Ten-Year Monthly Weather Averages")
st.markdown("Enter a UK postcode to view the ten-year average weather trends.")

postcode = st.text_input("Enter postcode:", " ")

years = st.selectbox(
    "Select number of years to analyse:",
    options=[5, 10, 15, 20],
    index=1  # default = 10
)


if st.button("Generate Plots"):
    monthly_means, fig, buf = get_weather_data(postcode, years)
    if monthly_means is not None:
        st.subheader("Monthly Averages ({years}-Year Period)")
        st.dataframe(monthly_means.round(2))

        # download csv of data
        csv = monthly_means.to_csv().encode('utf-8')
        st.download_button(
            label="Download Monthly Averages as CSV file",
            data=csv,
            file_name=f"weather_summary_{postcode}.csv",
            mime="text/csv"
        )

        st.pyplot(fig)

        # download png of plots
        st.download_button(
            label="Download Weather Plots as PNG",
            data=buf,
            file_name=f"weather_plots_{postcode}.png",
            mime="image/png"
        )




#   streamlit run avg_weather_app.py
