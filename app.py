import streamlit as st
import json
from kiteconnect import KiteConnect
import time
import pandas as pd
import datetime as dt
from pymongo import MongoClient, DESCENDING
import requests
import plotly.express as px
import urllib

# hide streamlit branding and hamburger menu
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)


def color_survived(val):
    if val > 0:
        color = "#7FFF00"
    elif val < 0:
        color = "#dc143c"
    return f"color: {color}"


st.title("Gapup Strategy Dashboard")

# select the client name
client_name = st.selectbox(
    "Select the Name of the client:", ("prateek", "tanmay", "swati", "raheel", "ankush")
)


# connect to the database
mongo = MongoClient(
    f'mongodb://LearnApp:{urllib.parse.quote("mongodb@1234")}@ac-bkjrzni-shard-00-00.uamkcnq.mongodb.net:27017,ac-bkjrzni-shard-00-01.uamkcnq.mongodb.net:27017,ac-bkjrzni-shard-00-02.uamkcnq.mongodb.net:27017/?ssl=true&replicaSet=atlas-r6l0ow-shard-0&authSource=admin&retryWrites=true&w=majority'
)
mydb = mongo["algo"]
coll = mydb["gapup-" + client_name]

df = pd.DataFrame(list(coll.find()))

# calculate turnover
df["turnover"] = (df["entry_price"] + df["exit_price"]) * df["quantity"]

# calculate charges
df["brokerage"] = (df["turnover"] / 100) * (0.03)
df["brokerage"] = df["brokerage"].apply(lambda x: min(40, x))
df["stt"] = (((df["entry_price"] + df["exit_price"]) / 2) * df["quantity"]) * (
    0.025 / 100
)
df["txn_charges"] = (df["turnover"] * 0.00345) / 100
df["sebi_charges"] = 1.18 * ((df["turnover"] * 10) / 10000000)
df["stamp_duty"] = (df["turnover"] * 0.0015) / 100
df["gst"] = ((df["brokerage"] + df["sebi_charges"] + df["txn_charges"]) * 18) / 100
df["charges"] = (
    df["brokerage"]
    + df["stt"]
    + df["txn_charges"]
    + df["sebi_charges"]
    + df["stamp_duty"]
    + df["gst"]
)
# calculate net pnl
df["net_pnl"] = df["pnl"] - df["charges"]

final_df = (
    df[["trade_date", "pnl", "charges", "net_pnl"]]
    .groupby(["trade_date"], sort=False)
    .sum()
)
final_df.reset_index(inplace=True)

# set inital streak values
final_df["loss_streak"] = 0
final_df["win_streak"] = 0

if final_df["net_pnl"][0] > 0:
    final_df["loss_streak"][0] = 0
    final_df["win_streak"][0] = 1

else:
    final_df["loss_streak"][0] = 1
    final_df["win_streak"][0] = 0

# find winning and losing streaks
for i in range(1, final_df.shape[0]):

    if final_df["net_pnl"][i] > 0:
        final_df["loss_streak"][i] = 0
        final_df["win_streak"][i] = final_df["win_streak"][i - 1] + 1

    else:
        final_df["win_streak"][i] = 0
        final_df["loss_streak"][i] = final_df["loss_streak"][i - 1] + 1


# cumulative PNL
final_df["cum_pnl"] = final_df["net_pnl"].cumsum()

# Create Drawdown column
final_df["drawdown"] = 0
for i in range(0, final_df.shape[0]):

    if i == 0:
        if final_df["pnl"].iloc[i] > 0:
            final_df["drawdown"].iloc[i] = 0
        else:
            final_df["drawdown"].iloc[i] = final_df["pnl"].iloc[i]
    else:
        if final_df["pnl"].iloc[i] + final_df["drawdown"].iloc[i - 1] > 0:
            final_df["drawdown"].iloc[i] = 0
        else:
            final_df["drawdown"].iloc[i] = (
                final_df["pnl"].iloc[i] + final_df["drawdown"].iloc[i - 1]
            )
# create monthly data
final_df["month"] = pd.DatetimeIndex(final_df["trade_date"]).month
final_df["year"] = pd.DatetimeIndex(final_df["trade_date"]).year
final_df["month"] = (
    pd.to_datetime(final_df["month"], format="%m").dt.month_name().str.slice(stop=3)
)
final_df["month_year"] = (
    final_df["month"] + " " + final_df["year"].astype(str)
).str.slice(stop=11)
# Dataframe for monthly returns
final_df_month = final_df.groupby(["month_year"], sort=False).sum()
final_df_month = final_df_month.reset_index()

# Calculate Statistics
total_days = len(final_df)
winning_days = (final_df["net_pnl"] > 0).sum()
losing_days = (final_df["net_pnl"] < 0).sum()

win_ratio = round((winning_days / total_days) * 100, 2)
max_profit = round(final_df["net_pnl"].max(), 2)
max_loss = round(final_df["net_pnl"].min(), 2)
max_drawdown = round(final_df["drawdown"].min(), 2)
max_winning_streak = max(final_df["win_streak"])
max_losing_streak = max(final_df["loss_streak"])
avg_profit_on_win_days = final_df[final_df["net_pnl"] > 0]["net_pnl"].sum() / len(
    final_df[final_df["net_pnl"] > 0]
)
avg_loss_on_loss_days = final_df[final_df["net_pnl"] < 0]["net_pnl"].sum() / len(
    final_df[final_df["net_pnl"] < 0]
)
avg_profit_per_day = final_df["net_pnl"].sum() / len(final_df)
expectancy = round(
    (avg_profit_on_win_days * win_ratio + avg_loss_on_loss_days * (100 - win_ratio))
    * 0.01,
    2,
)
net_profit = round(final_df["cum_pnl"].iloc[-1], 2)
total_charges = round(final_df["charges"].sum())
recent_pnl = round(final_df.iloc[-1]["net_pnl"], 2)

KPI = {
    "Total days": total_days,
    "Winning days": winning_days,
    "Losing days": losing_days,
    "Max Profit": max_profit,
    "Max Loss": max_loss,
    "Max Winning Streak": max_winning_streak,
    "Max Losing Streak": max_losing_streak,
    "Max Drawdown": max_drawdown,
    "Average Profit on win days": avg_profit_on_win_days,
    "Average Loss on loss days": avg_loss_on_loss_days,
    "Total Transaction Cost": total_charges,
}
strategy_stats = pd.DataFrame(KPI.values(), index=KPI.keys(), columns=[" "]).astype(int)


# Show Statistics
st.write("-----")
col1, col2, col3 = st.columns(3)
col1.metric(label="Win %", value=str(win_ratio) + " %")
col2.metric(label="Net Profit", value="₹ " + str(int(net_profit)), delta=recent_pnl)
col3.metric(label="Avg. daily profit", value="₹ " + str(int(avg_profit_per_day)))
st.write("-----")
st.subheader("Strategy Statistics")
st.table(strategy_stats)
st.write("-----")

# Show equity curve
st.subheader("Equity Curve")
fig_pnl = px.line(
    final_df,
    x="trade_date",
    y="cum_pnl",
    width=800,
    height=500,
)
st.plotly_chart(fig_pnl)
st.write("-----")

# show drawdown curve
st.subheader("Drawdown Curve")
fig_dd = px.line(final_df, x="trade_date", y="drawdown", width=800, height=500)
st.plotly_chart(fig_dd)
st.write("-----")

# Month-wise PNL
st.header("Month-wise PNL")
st.table(
    final_df_month[["month_year", "net_pnl"]].style.applymap(
        color_survived, subset=["net_pnl"]
    )
)
