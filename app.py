import streamlit as st
import pandas as pd
import json
from supabase import create_client, Client
import matplotlib.pyplot as plt
import seaborn as sns

# --- Supabase Connection ---
# Use Streamlit's secrets management for security
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    st.error("Please add your Supabase credentials to Streamlit's secrets management.")
    st.stop()


# --- Data Fetching and Caching ---
@st.cache_data(ttl=600)  # Cache data for 10 minutes
def fetch_data():
    try:
        response = supabase.table('Orders').select('*').gte('id', 70).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"An error occurred while fetching data: {e}")
        return pd.DataFrame()

# --- Data Processing Functions ---
def process_data(df):
    # Convert data types and create date column
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['date'] = df['created_at'].dt.date
    df['total_amount'] = pd.to_numeric(df['total_amount'], errors='coerce').fillna(0)
    
    # Fill missing location/user names
    df['name'].fillna('Vasant Kunj', inplace=True)

    # Map users to stores
    sf_staff = ['Isha', 'Kunal', 'Pranav']
    df['store'] = df['name'].apply(lambda x: 'SF' if x in sf_staff else 'VK')

    def extract_items(orders_json):
        try:
            orders_dict = json.loads(orders_json) if isinstance(orders_json, str) else orders_json
            return orders_dict.get('cart', [])
        except (json.JSONDecodeError, TypeError):
            return []

    df['items'] = df['orders'].apply(extract_items)
    
    def calculate_subtotal(items_list):
        if not isinstance(items_list, list): return 0
        subtotal = 0
        for item in items_list:
            price = item.get('price', 0)
            quantity = item.get('quantity', 0)
            cones = item.get('cones', 0)
            subtotal += (price * quantity) + (cones * 20)
        return subtotal

    df['subtotal'] = df['items'].apply(calculate_subtotal)
    df['total_with_gst'] = df['subtotal'] * 1.05
    df['discount'] = (df['total_with_gst'] - df['total_amount']).clip(lower=0)
    df['has_discount'] = df['discount'] > 0.01

    # Explode dataframe for item-level analysis
    df_items = df.explode('items').reset_index(drop=True)
    df_items['item_name'] = df_items['items'].apply(lambda x: x.get('name') if isinstance(x, dict) else None)
    df_items['item_quantity'] = df_items['items'].apply(lambda x: x.get('quantity') if isinstance(x, dict) else 0)
    
    return df, df_items

# --- Main Dashboard UI ---
st.set_page_config(layout="wide")
st.title("🍦 Ice Cream Sales Dashboard")

df_raw = fetch_data()

if df_raw.empty:
    st.warning("No data loaded. Please check your Supabase connection and table name ('Orders').")
    st.stop()

df, df_items = process_data(df_raw.copy())


# --- Dashboard Layout ---
st.sidebar.header("Dashboard Controls")
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.subheader("Key Metrics")
col1, col2, col3, col4 = st.columns(4)
total_sales = df['total_amount'].sum()
total_orders = len(df)
avg_order_value = df['total_amount'].mean() if total_orders > 0 else 0
# total_discounts = df['discount'].sum()

col1.metric("Total Sales", f"₹{total_sales:,.2f}")
col2.metric("Total Orders", f"{total_orders}")
col3.metric("Average Order Value", f"₹{avg_order_value:,.2f}")
# col4.metric("Total Discounts Given", f"₹{total_discounts:,.2f}")

st.markdown("---")


st.subheader("Sales & Operational Analysis")
col1, col2 = st.columns(2)

with col1:
    st.write("#### Total Ice Cream Sell Count")
    ice_cream_sell_count = df_items.groupby('item_name')['item_quantity'].sum().sort_values(ascending=False)
    fig1, ax1 = plt.subplots()
    sns.barplot(x=ice_cream_sell_count.index, y=ice_cream_sell_count.values, ax=ax1, palette='viridis')
    plt.setp(ax1.get_xticklabels(), rotation=45, ha='right')
    st.pyplot(fig1)

with col2:
    st.write("#### Number of Orders Each Hour")
    df['hour'] = df['created_at'].dt.hour
    orders_each_hour = df.groupby('hour')['id'].count()
    fig2, ax2 = plt.subplots()
    sns.barplot(x=orders_each_hour.index, y=orders_each_hour.values, ax=ax2, palette='plasma')
    st.pyplot(fig2)

st.markdown("---")

## --- UPDATED: Staff & Store Performance Section ---
st.subheader("Staff & Store Performance")
col_store1, col_store2, col_store3 = st.columns(3) # Added a third column

with col_store1:
    st.write("#### Total Sales by Store")
    sales_by_store = df.groupby('store')['total_amount'].sum().sort_values(ascending=False)
    fig5, ax5 = plt.subplots()
    sns.barplot(x=sales_by_store.index, y=sales_by_store.values, ax=ax5, palette='Set2')
    ax5.set_xlabel('Store')
    ax5.set_ylabel('Total Sales Amount')
    st.pyplot(fig5)

with col_store2:
    st.write("#### Daily Sales by Store")
    sales_by_store_day = df.groupby(['date', 'store'])['total_amount'].sum().unstack(fill_value=0)
    fig6, ax6 = plt.subplots()
    sales_by_store_day.plot(kind='line', marker='o', ax=ax6, figsize=(10, 6))
    ax6.set_xlabel('Date')
    ax6.set_ylabel('Total Sales Amount')
    ax6.grid(True)
    plt.setp(ax6.get_xticklabels(), rotation=45, ha='right')
    ax6.legend(title='Store')
    st.pyplot(fig6)

with col_store3:
    # --- NEW: Orders by User Chart ---
    st.write("#### Order Count by User")
    orders_by_user = df['name'].value_counts()
    fig7, ax7 = plt.subplots()
    sns.barplot(x=orders_by_user.index, y=orders_by_user.values, ax=ax7, palette='coolwarm')
    ax7.set_xlabel('User Name')
    ax7.set_ylabel('Number of Orders')
    plt.setp(ax7.get_xticklabels(), rotation=45, ha='right')
    st.pyplot(fig7)


# Display raw data in an expandable section
with st.expander("Show Raw Data with Final Calculation"):
    st.dataframe(df[['id', 'name', 'store', 'subtotal', 'total_with_gst', 'total_amount', 'discount']])