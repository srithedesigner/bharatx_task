import streamlit as st
import requests

API_URL = "http://localhost:8000/get-prices"  # Change if your FastAPI runs elsewhere

# List of countries
COUNTRIES = [
    "India", "United States", "United Kingdom", "Canada", "Australia", "Germany", "France", "Italy", "Spain",
    "Brazil", "Mexico", "Japan", "China", "Singapore", "South Africa", "UAE", "Saudi Arabia", "Netherlands",
    "Sweden", "Switzerland", "Turkey", "Russia", "Indonesia", "Malaysia", "Thailand", "Vietnam", "Philippines",
    "Argentina", "Chile", "Colombia", "Egypt", "Nigeria", "Kenya", "South Korea", "New Zealand", "Pakistan",
    "Bangladesh", "Poland", "Portugal", "Greece", "Norway", "Denmark", "Finland", "Ireland", "Belgium", "Austria"
]

# Set up the page
st.set_page_config(page_title="🌍 Global Price Finder", layout="wide")
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2e7d32;
        text-align: center;
        margin-bottom: 20px;
    }
    .grid-item {
        border: 1px solid #eee;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 16px;
        background: #fafbfc;
        box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
    }
    .grid-item h4 {
        margin-bottom: 8px;
        color: #1976d2;
    }
    .grid-item .price {
        font-size: 1.5em;
        font-weight: bold;
        color: #2e7d32;
    }
    .grid-item .product-name {
        margin: 8px 0;
        color: #555;
    }
    .grid-item a {
        color: #1976d2;
        text-decoration: none;
    }
    .grid-item a:hover {
        text-decoration: underline;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">🌍 Global Price Finder</div>', unsafe_allow_html=True)

# Input form
with st.form("search_form"):
    col1, col2 = st.columns(2)
    with col1:
        country = st.selectbox("Select Country", COUNTRIES, index=COUNTRIES.index("India"))
    with col2:
        product = st.text_input("Enter Product Name", value="iPhone 16 Pro, 128GB")
    submitted = st.form_submit_button("🔍 Search")

# Handle form submission
if submitted:
    with st.spinner("Fetching prices..."):
        try:
            response = requests.post(API_URL, json={"country": country, "product": product}, timeout=60)
            response.raise_for_status()
            data = response.json()
            items = data.get("sorted_prices", [])
        except Exception as e:
            st.error(f"Failed to fetch prices: {e}")
            items = []

    if items:
        st.success(f"Found {len(items)} results for '{product}' in {country}")
        # Display results in a grid
        cols = st.columns(3)
        for idx, item in enumerate(items):
            with cols[idx % 3]:
                st.markdown(
                    f"""
                    <div class="grid-item">
                        <h4>{item.get('website', 'Unknown')}</h4>
                        <div class="price">{item.get('currency', '₹')}{item.get('price')}</div>
                        <div class="product-name">{item.get('productName', item.get('title', ''))}</div>
                        <a href="{item.get('link', '#')}" target="_blank">View Product</a>
                        <div style="font-size:0.8em; color:#888; margin-top:8px;">Method: {item.get('method', '')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.warning("No prices found. Try a different product or country.")
else:
    st.info("Enter a product and country, then click Search.")