import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from rapidfuzz import fuzz
from dotenv import load_dotenv
import os
import re
import json
from urllib.parse import quote_plus
from google import genai


load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
cache = {}

def get_country_data(country):

    if country.lower() in cache:
        return cache[country.lower()]

    prompt = f"""
        List up to 10 popular e-commerce websites used in {country}, along with their search URL formats, the country's currency symbol, and a list of potential CSS selectors (classes or styles) commonly used for prices on product pages for each website.
        Only return a pure JSON object with the following structure:

        {{
        "currency": "<currency_symbol>",
        "websites": [
            {{
            "name": "<site name>",
            "domain": "<site domain>",
            "search_url_format": "<search URL with {{query}} as placeholder>",
            "price_selectors": ["<selector1>", "<selector2>", ...]
            }}
        ]
        }}

        Here is one example for India:

        {{
        "currency": "₹",
        "websites": [
            {{
            "name": "Flipkart",
            "domain": "flipkart.com",
            "search_url_format": "https://www.flipkart.com/search?q={{query}}",
            "price_selectors": [
                "div._30jeq3",
                "div._1vC4OE",
                "div._3qQ9m1"
            ]
            }},
            {{
            "name": "Amazon India",
            "domain": "amazon.in",
            "search_url_format": "https://www.amazon.in/s?k={{query}}",
            "price_selectors": [
                "span.a-price-whole",
                "span.a-price",
                "span.priceBlockBuyingPriceString"
            ]
            }}
        ]
        }}

        Now do the same for {country}. No backticks, no markdown, no explanation — just clean JSON.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt
    )

    try:
        data = response.text
        parsed_data = eval(data)
        cache[country.lower()] = {
            "currency": parsed_data.get("currency", "$"),
            "websites": parsed_data.get("websites", []),
        }
        return cache[country.lower()]
    except Exception as e:
        raise Exception(f"Failed to parse response from Gemini API: {e}")

def extract_from_schema(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string)
            if isinstance(data, list):
                data = data[0] 
            if data.get("@type") == "Product":
                return {
                    "title": data.get("name"),
                    "price": data.get("offers", {}).get("price"),
                    "currency": data.get("offers", {}).get("priceCurrency")
                }, "schema"
        except:
            continue
    return None, None


def extract_fallback_price(html, currency):
    """
    Extract the first valid price from the HTML using the provided currency symbol.
    """
    soup = BeautifulSoup(html, "html.parser")
    price_tag = soup.find(string=re.compile(rf"{currency}\s*\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?"))
    if price_tag:
        price_match = re.search(rf"{currency}\s*\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?", price_tag)
        if price_match:
            price_text = price_match.group().replace(currency, "").replace(",", "").strip()
            return {"price": float(price_text), "currency": currency}
    return None

def extract_heuristic(html, query, currency):
    """
    Extract prices heuristically using the provided currency symbol.
    """
    soup = BeautifulSoup(html, "html.parser")


    title_tags = soup.find_all(["h1", "h2", "span", "div"], string=True)
    titles = [t.get_text(strip=True) for t in title_tags if len(t.get_text(strip=True)) > 10]
    filtered_titles = [
        title for title in titles if fuzz.partial_ratio(query.lower(), title.lower()) > 50
    ]


    prices = []
    seen_prices = set()
    price_dom_index = 0  
    for symbol_tag in soup.find_all(string=lambda text: currency in text if text else False):
        parent = symbol_tag.find_parent()
        if parent:
            full_text = parent.get_text(strip=True)
            price_match = re.search(rf"{currency}\s*\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?", full_text)
            if price_match and price_match.group() not in seen_prices:
                seen_prices.add(price_match.group())
                font_size = extract_font_size(parent.get("style", ""))
                has_prominent_class = any(cls in str(parent.get('class', [])).lower()
                                         for cls in ['price', 'cost', 'amount', 'main', 'primary'])
                is_standalone = len(full_text.strip()) <= len(price_match.group()) + 10
                price_text = price_match.group().replace(currency, "").replace(",", "").strip()
                is_proper_format = len(price_text) >= 4

                dom_order_score = max(0, 100 - price_dom_index) 

                prominence_score = (font_size if font_size else 0) + \
                                  (30 if has_prominent_class else 0) + \
                                  (20 if is_standalone else 0) + \
                                  (15 if is_proper_format else 0) + \
                                  dom_order_score

                prices.append({
                    "price": price_text,
                    "currency": currency,
                    "parent": parent,
                    "font_size": font_size if font_size is not None else 0,
                })

    return prices

def extract_product_data(html, query):

    result, method = extract_from_schema(html)
    if result:
        return result, method


    result, method = extract_heuristic(html, query)
    if result:
        return result, method


    return None, None

def calculate_dom_proximity(element1, element2):
    """
    Calculate the DOM depth difference between two elements.
    """
    def get_depth(element):
        depth = 0
        while element:
            element = element.parent
            depth += 1
        return depth

    return abs(get_depth(element1) - get_depth(element2))


def extract_font_size(style):
    """
    Extract the font size from an inline style string.
    Example: "font-size: 24px;" -> 24
    """
    match = re.search(r"font-size\s*:\s*(\d+)px", style)
    return int(match.group(1)) if match else None



async def playwright_scrape(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        html = await page.content()
        await browser.close()
    return html



async def scrape_product_page(url, product, currency, selectors=None, use_playwright=False):
    """
    Scrape a product page for price and product details.
    """
    try:
        if not use_playwright:
            response = requests.get(url, headers=HEADERS)
            if response.status_code != 200:
                return None, None
            soup = BeautifulSoup(response.text, "html.parser")
            return extract_product_data(soup.prettify(), product)


        html = await playwright_scrape(url)
        return extract_product_data(html, product)
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None, None

def extract_fallback_price(html, currency):
    """
    Extract the first valid price from the HTML using the provided currency symbol.
    """
    soup = BeautifulSoup(html, "html.parser")
    price_tag = soup.find(string=re.compile(rf"{currency}\s*\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?"))
    if price_tag:
        price_match = re.search(rf"{currency}\s*\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?", price_tag)
        if price_match:
            price_text = price_match.group().replace(currency, "").replace(",", "").strip()
            return {"price": float(price_text), "currency": currency}
    return None

async def get_sorted_prices(country, product):
    """
    Scrape prices for a product in a given country.
    """
    country_data = get_country_data(country)
    websites = country_data["websites"]
    currency = country_data["currency"]

    results = []
    scraped_websites = []  


    for site in websites:
        url = site["search_url_format"].replace("{query}", quote_plus(product))
        selectors = site.get("price_selectors", [])
        product_data, method = await scrape_product_page(url, product, currency, selectors=selectors, use_playwright=False)
        if product_data:
            product_data["link"] = url 
            product_data["website"] = site["name"] 
            product_data["method"] = method 
            results.append(product_data)
            scraped_websites.append(site["name"]) 


    if not results:
        for site in websites:
            url = site["search_url_format"].replace("{query}", quote_plus(product))
            selectors = site.get("price_selectors", [])
            product_data, method = await scrape_product_page(url, product, currency, selectors=selectors, use_playwright=True)
            if product_data:
                product_data["link"] = url
                product_data["website"] = site["name"]
                product_data["method"] = method
                results.append(product_data)
                scraped_websites.append(site["name"])  


    if not results:
        for site in websites:
            url = site["search_url_format"].replace("{query}", quote_plus(product))
            html = await playwright_scrape(url)
            fallback_price = extract_fallback_price(html, currency)
            if fallback_price:
                results.append({
                    "title": product,
                    "price": fallback_price["price"],
                    "currency": fallback_price["currency"],
                    "link": url,
                    "website": site["name"],
                    "method": "fallback"
                })
                scraped_websites.append(site["name"])
                break 

    return {"websites_scraped": scraped_websites, "sorted_prices": sorted(results, key=lambda x: x["price"])}