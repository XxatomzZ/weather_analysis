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
def get_weather_data(postcode, start_year, end_year, show_trends=False, show_errorbars=False):
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
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)

    # Add number of days in each month (non-leap year assumption)
    days_in_month = {
        'Jan': 31, 'Feb': 28, 'Mar': 31, 'Apr': 30,
        'May': 31, 'Jun': 30, 'Jul': 31, 'Aug': 31,
        'Sep': 30, 'Oct': 31, 'Nov': 30, 'Dec': 31
    }

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

    # Monthly max/min for all variables
    monthly_max_all = data.groupby(data.index.month).max(numeric_only=True)
    monthly_min_all = data.groupby(data.index.month).min(numeric_only=True)

    # Map numeric months to names
    month_map = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct',
                 11: 'Nov', 12: 'Dec'}
    monthly_max_all.index = monthly_max_all.index.map(month_map)
    monthly_min_all.index = monthly_min_all.index.map(month_map)


    # --- Compute monthly extremes for error bars (if requested) ---
    monthly_max = None
    monthly_min = None
    # We'll take tmax/tmin if available (preferred). Otherwise fall back to tavg extremes.
    try:
        if 'tmax' in data.columns and 'tmin' in data.columns:
            monthly_max = data.groupby(data.index.month)['tmax'].max()
            monthly_min = data.groupby(data.index.month)['tmin'].min()
        elif 'tavg' in data.columns:
            # fallback: use daily average max/min
            monthly_max = data.groupby(data.index.month)['tavg'].max()
            monthly_min = data.groupby(data.index.month)['tavg'].min()
        # convert numeric-month index to month names to match monthly_means index
        if monthly_max is not None:
            monthly_max.index = monthly_max.index.map({
                1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
            })
            monthly_min.index = monthly_min.index.map({
                1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
            })
            # align to monthly_means index order and fill missing months with NaN
            monthly_max = monthly_max.reindex(monthly_means.index)
            monthly_min = monthly_min.reindex(monthly_means.index)
    except Exception:
        # If anything goes wrong, ensure them None so later logic can skip error bars
        monthly_max = None
        monthly_min = None


    # --- Compute monthly extremes (max/min) for all variables ---
    monthly_max_all = data.groupby(data.index.month).max(numeric_only=True)
    monthly_min_all = data.groupby(data.index.month).min(numeric_only=True)

    # Convert numeric-month index to month names
    month_map = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
    }
    monthly_max_all.index = monthly_max_all.index.map(month_map)
    monthly_min_all.index = monthly_min_all.index.map(month_map)

    # Compute monthly min/max daily sunshine
    if 'tsun' in monthly_max_all.columns and 'tsun' in monthly_min_all.columns:
        monthly_max_all['tsun_daily'] = monthly_max_all['tsun'] / pd.Series(days_in_month)
        monthly_min_all['tsun_daily'] = monthly_min_all['tsun'] / pd.Series(days_in_month)


    # Calculate average daily sunshine (hours per day)
#    if 'tsun' in monthly_means.columns:
#        monthly_means['tsun_daily'] = [
#            monthly_means.loc[m, 'tsun'] / days_in_month[m] for m in monthly_means.index
#        ]
#    if 'tsun' in monthly_means.columns:
#        monthly_means = monthly_means.drop(columns=['tsun'])

    # --- Create combined and individual interactive plots ---
    plot_vars = {
        'tavg': 'Average Temperature (°C)',
        'tmin': 'Minimum Temperature (°C)',
        'tmax': 'Maximum Temperature (°C)',
        'prcp': 'Precipitation (mm)',
        'tsun': 'Average Daily Sunshine (min/day)',
        'wspd': 'Wind Speed (km/h)'
    }

    # Only include variables that actually exist in the monthly_means DataFrame
    available_vars = {
        k: v for k, v in plot_vars.items()
        if k in monthly_means.columns #and k != 'tsun_daily'
    }

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
        'tsun': 'orange',
        'wspd': 'grey'
    }

    err_dict = {}
    for var in available_vars.keys():
        if var == 'tavg':
            # Existing tavg min/max logic
            if 'tmax' in monthly_max_all.columns and 'tmin' in monthly_min_all.columns:
                err_plus = (monthly_max_all['tmax'] - monthly_means['tavg']).clip(lower=0)
                err_minus = (monthly_means['tavg'] - monthly_min_all['tmin']).clip(lower=0)
                err_dict['tavg'] = (err_plus, err_minus)
#        elif var == 'tsun_daily':
#            # Error bars for sunshine
#            err_plus = (monthly_max_all['tsun_daily'] - monthly_means['tsun_daily']).clip(lower=0)
#            err_minus = (monthly_means['tsun_daily'] - monthly_min_all['tsun_daily']).clip(lower=0)
#            err_dict['tsun_daily'] = (err_plus, err_minus)
        else:
            # Other variables
            err_plus = (monthly_max_all[var] - monthly_means[var]).clip(lower=0)
            err_minus = (monthly_means[var] - monthly_min_all[var]).clip(lower=0)
            err_dict[var] = (err_plus, err_minus)


    mode_type = "lines+markers" if show_trends else "markers"

    for i, (col, label) in enumerate(available_vars.items()):
        if col not in monthly_means.columns:
            continue  # skip missing variables
        # Base trace
        trace_kwargs = dict(
            x=monthly_means.index,
            y=monthly_means[col],
            mode=mode_type,
            name=label,
            line=dict(color=color_map.get(col, None)),
            marker=dict(size=8, opacity=0.8)
        )

        # Add error bars if available
        if show_errorbars and col in err_dict:
            err_plus, err_minus = err_dict[col]
            trace_kwargs['error_y'] = dict(
                type='data',
                array=err_plus.values,
                arrayminus=err_minus.values,
                visible=True
            )

            # Add hover showing min/max values
            if col == 'tavg':
                # Existing tavg hover
                trace_kwargs['customdata'] = list(zip(monthly_min_all['tmin'], monthly_max_all['tmax']))
                trace_kwargs['hovertemplate'] = (
                    "<b>%{x}</b><br>"
                    "Avg Temp: %{y:.2f}<br>"
                    "Min Temp: %{customdata[0]:.2f}<br>"
                    "Max Temp: %{customdata[1]:.2f}"
                )
#            elif col == 'tsun_daily':
#                # New hover for sunshine
#               trace_kwargs['customdata'] = list(zip(monthly_min_all['tsun_daily'], monthly_max_all['tsun_daily']))
#                trace_kwargs['hovertemplate'] = (
#                    "<b>%{x}</b><br>"
#                    f"{label}<br>"
#                    "Avg: %{y:.2f}<br>"
#                    "Min: %{customdata[0]:.2f}<br>"
#                    "Max: %{customdata[1]:.2f}"
#                )
            else:
                # Hover for all other variables
                trace_kwargs['customdata'] = list(zip(monthly_min_all[col], monthly_max_all[col]))
                trace_kwargs['hovertemplate'] = (
                    f"<b>%{{x}}</b><br>{label}<br>"
                    "Avg: %{y:.2f}<br>"
                    "Min: %{customdata[0]:.2f}<br>"
                    "Max: %{customdata[1]:.2f}"
                )
        else:
            trace_kwargs['hovertemplate'] = "<b>%{x}</b><br>%{y:.2f}"

        fig.add_trace(
            go.Scatter(**trace_kwargs),
            row=row_col_map[i][0],
            col=row_col_map[i][1]
        )


    fig.update_layout(
        height=800,
        width=1000,
        title_text=f"Average Monthly Weather Overview for {postcode.upper()} ({start_year}-{end_year})",
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
            color_discrete_sequence=[color_map[var]]
        )

        if show_trends:
            individual_figs[var].update_traces(mode="lines+markers")
        else:
            individual_figs[var].update_traces(mode="markers")

        if show_errorbars and var in err_dict:
            err_plus, err_minus = err_dict[var]
            individual_figs[var].update_traces(
                error_y=dict(
                    type='data',
                    array=err_plus.values,
                    arrayminus=err_minus.values,
                    visible=True
                ),
                customdata=list(zip(
                    monthly_min_all['tmin'] if var == 'tavg' else monthly_min_all[var],
                    monthly_max_all['tmax'] if var == 'tavg' else monthly_max_all[var]
                )),
                hovertemplate=(
                    f"<b>%{{x}}</b><br>{label}<br>"
                    "Avg: %{y:.2f}<br>"
                    "Min: %{customdata[0]:.2f}<br>"
                    "Max: %{customdata[1]:.2f}"
                )
            )

            # If this is the average temperature plot and error arrays are available, add error bars
            if var == 'tavg' and err_plus is not None and err_minus is not None:
                individual_figs[var].update_traces(
                    error_y=dict(type='data', array=err_plus, arrayminus=err_minus, visible=True),
                    customdata=list(zip(monthly_min, monthly_max)),
                    hovertemplate=(
                        "<b>%{x}</b><br>"
                        "Avg: %{y:.2f} °C<br>"
                        "Min: %{customdata[0]:.2f} °C<br>"
                        "Max: %{customdata[1]:.2f} °C"
                    )
                )

        if not show_trends:
            individual_figs[var].update_traces(mode="markers")  # override line if needed



    # Return all data and figures
    return data, monthly_means, monthly_min, monthly_max, fig, plot_vars, individual_figs, color_map


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
st.caption("Note: data may be unavailable for some regions/years")

tab1, tab2, tab3 = st.tabs(["Charts", "Data Table", "Yearly Trends"])

st.sidebar.header("Settings ⚙️")

postcode = st.sidebar.text_input("Enter a UK Postcode", "---- ---")
if postcode:
    if not re.match(r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$", postcode, re.I):
        st.error("Invalid UK postcode")

year_range = st.sidebar.slider(
    "Select range of years to analyse",
    min_value=2005,
    max_value=2025,
    value=(2015, 2025),  # default range
    step=1,
    help="Select start and end year for historical data"
)

start_year, end_year = year_range



yearly_variable = st.sidebar.selectbox(
    "Select variable for yearly trends",
    [
        "Average Temperature (°C)",
        "Minimum Temperature (°C)",
        "Maximum Temperature (°C)",
        "Precipitation (mm)",
        "Average Daily Sunshine (min/day)",
        "Wind Speed (km/h)"
    ]
)

month_names = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

selected_months = st.sidebar.multiselect(
    "Select month(s) to display:",
    options=month_names,
    default=month_names  # default = all months
)


yearly_var_map = {
    "Average Temperature (°C)": "tavg",
    "Minimum Temperature (°C)": "tmin",
    "Maximum Temperature (°C)": "tmax",
    "Precipitation (mm)": "prcp",
    "Average Daily Sunshine (min/day)": "tsun",
    "Wind Speed (km/h)": "wspd"
}


with st.sidebar.expander("Advanced Options"):
    show_trends = st.checkbox("Show trend lines", value=True)
    show_errorbars = st.checkbox("Show monthly min/max as error bars", value=False)


if st.sidebar.button("Run Analysis"):
    st.session_state['run'] = True
    with st.spinner("Fetching and processing weather data..."):
        data, monthly_means, monthly_min, monthly_max, fig, plot_vars, individual_figs, color_map = get_weather_data(postcode, start_year, end_year, show_trends, show_errorbars)

    if monthly_means is not None:
        # ---- Compute yearly averages for each month ----
        data['year'] = data.index.year
        data['month_num'] = data.index.month

        # Prepare dataframe: rows = years, columns = months
        year_month_df = data.groupby(['year', 'month_num']).mean(numeric_only=True)

        # Convert to an easier structure: dict of month → dataframe
        monthly_yearly = {}
        for m in range(1, 12 + 1):
            df_m = year_month_df.xs(m, level='month_num')[yearly_var_map[yearly_variable]].reset_index()
            df_m.columns = ['Year', yearly_variable]
            monthly_yearly[m] = df_m

        selected_var = yearly_var_map[yearly_variable]


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
                'tsun': 'Average Daily Sunshine (min/day)',
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

        with tab3:
            st.subheader("Yearly Trends by Month")

            # Build a mapping: "January" -> 1, etc.
            month_to_num = {name: i + 1 for i, name in enumerate(month_names)}
            # Convert selected month names to numbers
            months_to_plot = [month_to_num[m] for m in selected_months]

            # Only plot selected months
            cols = st.columns(3)
            for i, m in enumerate(months_to_plot):
                with cols[i % 3]:
                    # fetch the dataframe for this month
                    df_m = monthly_yearly[m]

                    # filter by user-selected year range
                    df_m = df_m[(df_m['Year'] >= start_year) & (df_m['Year'] <= end_year)]

                    fig_m = px.line(
                        df_m,
                        x="Year",
                        y=yearly_variable,
                        markers=True,
                        title=month_names[m - 1],
                        template="plotly_white",
                        color_discrete_sequence=[color_map.get(selected_var, "black")]
                    )
                    fig_m.update_traces(
                        hovertemplate=f"(%{{x}}): %{{y:.2f}}"
                    )
                    fig_m.update_layout(height=250)
                    st.plotly_chart(fig_m, use_container_width=True)
            st.info("You can download the plot as a PNG directly from the chart's toolbar.")

        with tab1:
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={
                    'displayModeBar': True,
                    'modeBarButtonsToAdd': ['downloadImage'],  # <-- browser-based PNG download
                }
            )
            st.info("You can download the plot as a PNG directly from the chart's toolbar (top right).")

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

#   streamlit run /Users/cam/Documents/python/weather_app/avg_weather_app.py