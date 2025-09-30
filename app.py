import streamlit as st
import pandas as pd
import json
from supabase import create_client, Client
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import combinations
from collections import Counter

# --- Supabase Connection ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    st.error("Please add your Supabase credentials to Streamlit's secrets management.")
    st.stop()


# --- Data Fetching and Caching ---
@st.cache_data(ttl=600)
def fetch_data():
    try:
        response = supabase.table('Orders').select('*').gte('id', 70).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"An error occurred while fetching data: {e}")
        return pd.DataFrame()

# --- Data Processing Functions ---
def process_data(df):
    # Basic data cleaning and type conversion
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['date'] = df['created_at'].dt.date
    df['total_amount'] = pd.to_numeric(df['total_amount'], errors='coerce').fillna(0)
    df['name'].fillna('Vasant Kunj', inplace=True)

    # Store mapping
    sf_staff = ['Isha', 'Kunal', 'Pranav']
    df['store'] = df['name'].apply(lambda x: 'SF' if x in sf_staff else 'VK')

    def extract_items(orders_json):
        try:
            orders_dict = json.loads(orders_json) if isinstance(orders_json, str) else orders_json
            return orders_dict.get('cart', [])
        except (json.JSONDecodeError, TypeError):
            return []

    df['items'] = df['orders'].apply(extract_items)
    
    # Discount calculation
    def calculate_subtotal(items_list):
        if not isinstance(items_list, list): return 0
        return sum((item.get('price', 0) * item.get('quantity', 0)) + (item.get('cones', 0) * 20) for item in items_list)

    df['subtotal'] = df['items'].apply(calculate_subtotal)
    df['total_with_gst'] = df['subtotal'] * 1.05
    df['discount'] = (df['total_with_gst'] - df['total_amount']).clip(lower=0)
    df['has_discount'] = df['discount'] > 0.01

    # Exploded dataframe for item-level analysis
    df_items = df.explode('items').reset_index(drop=True).dropna(subset=['items'])
    df_items['item_name'] = df_items['items'].apply(lambda x: x.get('name'))
    df_items['item_quantity'] = df_items['items'].apply(lambda x: x.get('quantity', 0))
    df_items['item_category'] = df_items['items'].apply(lambda x: x.get('category', 'Unknown'))
    df_items['item_revenue'] = df_items['items'].apply(lambda x: x.get('price', 0) * x.get('quantity', 0))
    
    # --- New Metrics Calculations ---
    
    # 1. Sales by Category
    sales_by_category = df_items.groupby('item_category')['item_revenue'].sum().sort_values(ascending=False)
    
    # 2. Items per Order
    df['items_per_order'] = df['items'].apply(lambda cart: sum(item.get('quantity', 0) for item in cart))
    items_dist = df['items_per_order'].value_counts().sort_index()

    # 3. Most Common Pairings
    order_item_lists = df_items.loc[df_items['item_name'].notna()].groupby('id')['item_name'].apply(lambda x: sorted(list(x)))
    all_pairs = Counter()
    for item_list in order_item_lists:
        if len(item_list) > 1:
            all_pairs.update(combinations(item_list, 2))
    
    top_pairs_df = pd.DataFrame(all_pairs.most_common(10), columns=['pair', 'count'])
    # --- NEW: Calculate total pairings count ---
    total_pair_count = sum(all_pairs.values())

    return df, df_items, sales_by_category, items_dist, top_pairs_df, total_pair_count

# --- Main Dashboard UI ---
st.set_page_config(layout="wide")
st.title("🍦 Ice Cream Sales Dashboard")

df_raw = fetch_data()

if df_raw.empty:
    st.warning("No data loaded. Please check your Supabase connection.")
    st.stop()

# --- UPDATED: Unpack new total_pair_count variable ---
df, df_items, sales_by_category, items_dist, top_pairs_df, total_pair_count = process_data(df_raw.copy())

# --- Sidebar and KPIs ---
st.sidebar.header("Dashboard Controls")
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.subheader("Key Metrics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Sales", f"₹{df['total_amount'].sum():,.2f}")
col2.metric("Total Orders", f"{len(df)}")
col3.metric("Average Order Value", f"₹{df['total_amount'].mean():,.2f}")
# col4.metric("Total Discounts Given", f"₹{df['discount'].sum():,.2f}")
st.markdown("---")

# --- Sales & Ops Analysis ---
st.subheader("Sales & Operational Analysis")
col1, col2 = st.columns(2)
with col1:
    st.write("#### Total Ice Cream Sell Count")
    ice_cream_sell_count = df_items.groupby('item_name')['item_quantity'].sum().sort_values(ascending=False)
    fig, ax = plt.subplots()
    sns.barplot(x=ice_cream_sell_count.index, y=ice_cream_sell_count.values, ax=ax, palette='viridis')
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    st.pyplot(fig)
with col2:
    st.write("#### Number of Orders Each Hour")
    df['hour'] = df['created_at'].dt.hour
    orders_each_hour = df.groupby('hour')['id'].count()
    fig, ax = plt.subplots()
    sns.barplot(x=orders_each_hour.index, y=orders_each_hour.values, ax=ax, palette='plasma')
    st.pyplot(fig)
st.markdown("---")


# --- Product & Customer Behavior Analysis ---
st.subheader("Product & Customer Behavior Analysis")
col_prod1, col_prod2 = st.columns(2)
with col_prod1:
    st.write("#### Sales by Category")
    fig, ax = plt.subplots()
    sns.barplot(x=sales_by_category.index, y=sales_by_category.values, ax=ax, palette='magma')
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    ax.set_xlabel("Category")
    ax.set_ylabel("Total Revenue")
    st.pyplot(fig)
with col_prod2:
    st.write("#### Items per Order")
    fig, ax = plt.subplots()
    sns.barplot(x=items_dist.index, y=items_dist.values, ax=ax, palette='crest')
    ax.set_xlabel("Number of Items in Order")
    ax.set_ylabel("Count of Orders")
    st.pyplot(fig)

st.markdown("---")


# --- Staff & Store Performance ---
st.subheader("Staff & Store Performance")
col_store1, col_store2, col_store3 = st.columns(3)
with col_store1:
    st.write("#### Total Sales by Store")
    sales_by_store = df.groupby('store')['total_amount'].sum().sort_values(ascending=False)
    fig, ax = plt.subplots()
    sns.barplot(x=sales_by_store.index, y=sales_by_store.values, ax=ax, palette='Set2')
    st.pyplot(fig)
with col_store2:
    st.write("#### Daily Sales by Store")
    sales_by_store_day = df.groupby(['date', 'store'])['total_amount'].sum().unstack(fill_value=0)
    fig, ax = plt.subplots()
    sales_by_store_day.plot(kind='line', marker='o', ax=ax, figsize=(10, 6))
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    ax.legend(title='Store')
    st.pyplot(fig)
with col_store3:
    st.write("#### Order Count by User")
    orders_by_user = df['name'].value_counts()
    fig, ax = plt.subplots()
    sns.barplot(x=orders_by_user.index, y=orders_by_user.values, ax=ax, palette='coolwarm')
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    st.pyplot(fig)


# --- Raw Data Expander ---
with st.expander("Show Raw Data"):
    st.dataframe(df[['id', 'name', 'store', 'subtotal', 'total_with_gst', 'total_amount', 'discount']])