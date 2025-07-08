import re
import json
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from playwright.sync_api import sync_playwright


def extract_from_schema(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string)
            if isinstance(data, list):
                data = data[0]  # handle array of schemas
            if data.get("@type") == "Product":
                return {
                    "title": data.get("name"),
                    "price": data.get("offers", {}).get("price"),
                    "currency": data.get("offers", {}).get("priceCurrency")
                }, "schema"
        except:
            continue
    return None, None
def extract_heuristic(html, query, currency_symbols=["₹", "$", "KSh", "KES", "EUR", "€"]):
    soup = BeautifulSoup(html, "html.parser")

    # Step 1: Extract potential titles
    title_tags = soup.find_all(["h1", "h2", "span", "div"], string=True)
    titles = [t.get_text(strip=True) for t in title_tags if len(t.get_text(strip=True)) > 10]
    filtered_titles = [
        title for title in titles if fuzz.partial_ratio(query.lower(), title.lower()) > 50
    ]
    print("Filtered Titles:", filtered_titles)  # Debug

    # Step 2: Extract potential prices
    prices = []
    seen_prices = set()
    price_dom_index = 0  # Track order of appearance in DOM
    for symbol in currency_symbols:
        for symbol_tag in soup.find_all(string=lambda text: symbol in text if text else False):
            parent = symbol_tag.find_parent()
            if parent:
                full_text = parent.get_text(strip=True)
                print("Parent Full Text:", full_text)  # Debug

                price_match = re.search(rf"{symbol}\s*\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?", full_text)
                if price_match and price_match.group() not in seen_prices:
                    seen_prices.add(price_match.group())
                    font_size = extract_font_size(parent.get("style", ""))
                    has_prominent_class = any(cls in str(parent.get('class', [])).lower()
                                             for cls in ['price', 'cost', 'amount', 'main', 'primary'])
                    is_standalone = len(full_text.strip()) <= len(price_match.group()) + 10
                    price_text = price_match.group().replace(symbol, "").replace(",", "").strip()
                    is_proper_format = len(price_text) >= 4

                    dom_order_score = max(0, 100 - price_dom_index)  # Earlier = higher score

                    prominence_score = (font_size if font_size else 0) + \
                                      (30 if has_prominent_class else 0) + \
                                      (20 if is_standalone else 0) + \
                                      (15 if is_proper_format else 0) + \
                                      dom_order_score

                    prices.append({
                        "price": price_text,
                        "currency": symbol,
                        "parent": parent,
                        "font_size": font_size if font_size is not None else 0,
                        "prominence_score": prominence_score,
                        "dom_order_score": dom_order_score,
                        "original_text": price_match.group()
                    })
                    price_dom_index += 1
                else:
                    for sibling in parent.find_next_siblings():
                        sibling_text = sibling.get_text(strip=True)
                        price_match = re.search(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?", sibling_text)
                        if price_match and price_match.group() not in seen_prices:
                            seen_prices.add(price_match.group())
                            font_size = extract_font_size(sibling.get("style", ""))
                            has_prominent_class = any(cls in str(sibling.get('class', [])).lower()
                                                     for cls in ['price', 'cost', 'amount', 'main', 'primary'])
                            is_standalone = len(sibling_text.strip()) <= len(price_match.group()) + 10
                            price_text = price_match.group().replace(",", "").strip()
                            is_proper_format = len(price_text) >= 4

                            dom_order_score = max(0, 100 - price_dom_index)

                            prominence_score = (font_size if font_size else 0) + \
                                              (30 if has_prominent_class else 0) + \
                                              (20 if is_standalone else 0) + \
                                              (15 if is_proper_format else 0) + \
                                              dom_order_score

                            prices.append({
                                "price": price_text,
                                "currency": symbol,
                                "parent": sibling,
                                "font_size": font_size if font_size is not None else 0,
                                "prominence_score": prominence_score,
                                "dom_order_score": dom_order_score,
                                "original_text": price_match.group()
                            })
                            price_dom_index += 1
                            break

    print("Extracted Prices:", prices)  # Debug

    # Step 3: Pair titles with prices using weighted scoring
    results = []
    for title in filtered_titles:
        for price_data in prices:
            score = fuzz.token_set_ratio(query.lower(), title.lower())
            if score > 70:
                proximity = calculate_dom_proximity(price_data["parent"], soup.find(string=title))
                # Strong penalty for distance, prominence is the main factor, and boost for early DOM
                weighted_score = price_data["prominence_score"] - (proximity * 10)
                results.append({
                    "title": title,
                    "price": price_data["price"],
                    "currency": price_data["currency"],
                    "score": score,
                    "proximity": proximity,
                    "prominence_score": price_data["prominence_score"],
                    "dom_order_score": price_data["dom_order_score"],
                    "original_text": price_data.get("original_text", ""),
                    "weighted_score": weighted_score
                })

    print("Results Before Sorting:", results)  # Debug

    # Step 4: Sort results by weighted score
    results.sort(key=lambda x: -x["weighted_score"])
    print("Final Results:", results)  # Debug

    return (results[0], "heuristic") if results else (None, None)

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


def extract_product_data(html, query):
    # 1. Try schema.org
    result, method = extract_from_schema(html)
    if result:
        return result, method

    # 2. Try heuristic match
    result, method = extract_heuristic(html, query)
    if result:
        return result, method

    # 3. Fallback: None
    return None, None


def fetch_dynamic_html(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_timeout(5000)  # Wait for dynamic content to load
        html = page.content()
        browser.close()
        return html


if __name__ == "__main__":
    url = "https://www.flipkart.com/search?q=Macbook%20pro%20M4&otracker=search&otracker1=search&marketplace=FLIPKART&as-show=on&as=off"
    html = fetch_dynamic_html(url)
    data, method = extract_product_data(html, "Macbook Pro M4 14 inch")
    print(data, method)