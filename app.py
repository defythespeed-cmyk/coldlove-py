
# --- Supabase Connection ---
# It's highly recommended to use Streamlit's secrets management for these keys.
# For local development, you can temporarily set them here.
# To deploy, use st.secrets["supabase_url"] and st.secrets["supabase_key"]

import streamlit as st
import pandas as pd
import json
from supabase import create_client, Client
import matplotlib.pyplot as plt
import seaborn as sns

# --- Supabase Connection ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Error connecting to Supabase: {e}")
    st.stop()


# --- Data Fetching and Caching ---
@st.cache_data(ttl=600)
def fetch_data():
    try:
        response = supabase.table('Orders').select('*').gte('id', 70).execute()
        data = response.data
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"An error occurred while fetching data: {e}")
        return pd.DataFrame()

# --- Data Processing Functions ---
def process_data(df):
    # Convert 'created_at' to a datetime object
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    # --- THIS IS THE NEW CORRECTED LINE ---
    # Convert 'total_amount' from text to a numeric type, handling potential errors
    df['total_amount'] = pd.to_numeric(df['total_amount'], errors='coerce').fillna(0)
    
    # Fill missing 'name' values (for location) with 'Vasant Kunj'
    df['name'].fillna('Vasant Kunj', inplace=True)

    def extract_items(orders_json):
        try:
            orders_dict = json.loads(orders_json) if isinstance(orders_json, str) else orders_json
            return orders_dict.get('cart', [])
        except (json.JSONDecodeError, TypeError):
            return []

    df['items'] = df['orders'].apply(extract_items)
    df_items = df.explode('items').reset_index(drop=True)

    df_items['item_name'] = df_items['items'].apply(lambda x: x.get('name') if isinstance(x, dict) else None)
    df_items['item_quantity'] = df_items['items'].apply(lambda x: x.get('quantity') if isinstance(x, dict) else 0)
    df_items['item_price'] = df_items['items'].apply(lambda x: x.get('price') if isinstance(x, dict) else 0)
    
    return df, df_items

# --- Main Dashboard UI ---
# (The rest of the file remains the same as the previous version)
st.set_page_config(layout="wide")
st.title("🍦 Ice Cream Sales Dashboard")

df_raw = fetch_data()

if df_raw.empty:
    st.warning("No data loaded. Please check your Supabase connection and table name ('Orders').")
    st.stop()

df, df_items = process_data(df_raw.copy())

# Sidebar, KPI Cards, Charts, etc. remain the same...
st.sidebar.header("Dashboard Controls")
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.subheader("Key Metrics")
col1, col2, col3 = st.columns(3)
total_sales = df['total_amount'].sum()
total_orders = len(df)
avg_order_value = df['total_amount'].mean() if total_orders > 0 else 0

col1.metric("Total Sales", f"₹{total_sales:,.2f}")
col2.metric("Total Orders", f"{total_orders}")
col3.metric("Average Order Value", f"₹{avg_order_value:,.2f}")

st.markdown("---")

st.subheader("Sales Analysis")
col1, col2 = st.columns(2)
# ... (rest of the charting code is unchanged) ...
with col1:
    st.write("#### Total Ice Cream Sell Count")
    ice_cream_sell_count = df_items.groupby('item_name')['item_quantity'].sum().sort_values(ascending=False)
    fig1, ax1 = plt.subplots()
    sns.barplot(x=ice_cream_sell_count.index, y=ice_cream_sell_count.values, ax=ax1, palette='viridis')
    ax1.set_xlabel('Ice Cream Flavor')
    ax1.set_ylabel('Total Quantity Sold')
    plt.xticks(rotation=45, ha='right')
    st.pyplot(fig1)

    st.write("#### Average Order Value by Day")
    df['date'] = df['created_at'].dt.date
    average_order_value_by_day = df.groupby('date')['total_amount'].mean()
    fig3, ax3 = plt.subplots()
    average_order_value_by_day.plot(kind='line', marker='o', ax=ax3)
    ax3.set_xlabel('Date')
    ax3.set_ylabel('Average Order Value')
    ax3.grid(True)
    plt.xticks(rotation=45, ha='right')
    st.pyplot(fig3)

with col2:
    st.write("#### Number of Orders Each Hour")
    df['hour'] = df['created_at'].dt.hour
    orders_each_hour = df.groupby('hour')['id'].count()
    fig2, ax2 = plt.subplots()
    sns.barplot(x=orders_each_hour.index, y=orders_each_hour.values, ax=ax2, palette='plasma')
    ax2.set_xlabel('Hour of the Day')
    ax2.set_ylabel('Number of Orders')
    st.pyplot(fig2)
    
    st.write("#### Ice Cream Sell Count by User/Location")
    ice_cream_count_by_user = df_items.groupby(['name', 'item_name'])['item_quantity'].sum().unstack(fill_value=0)
    fig4, ax4 = plt.subplots()
    ice_cream_count_by_user.plot(kind='bar', stacked=True, ax=ax4, figsize=(10, 6))
    ax4.set_xlabel('User / Location')
    ax4.set_ylabel('Total Quantity Sold')
    plt.xticks(rotation=45, ha='right')
    st.pyplot(fig4)


with st.expander("Show Raw Data"):
    st.dataframe(df_raw)