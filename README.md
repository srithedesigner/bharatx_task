BharatX task
It is a really interesting and a very challenging problem to solve.

One VibeCoder way of solving this problem is just trust the LLM gods, like this,
1. Ask LLM to give the list of top 50 (atmost) ecommerce websites
2. Now for each website, use playwright ( if dynamically generated website) or beautiful soup and get the DOM html content
3. Now pass the html content and the product to the LLM and get the price

This is something that would work, but only if you are ELON MUSK, it is not at all scalable and very very EXPENSIVE, and slow.

One old school way of solving this would be sit down, and statically write selectors for scrapping.
1. This is very boring, and if you are doing this, then what are you even doing with your life?
2. This is expected to break, as the websites change their format.
3. and it takes very long to manually get this data
4. BUT IT IS BLAZING FAST

Both the ways are two sides of the extremes.

After thinking, looking for loopholes, optimisation, here is a solution that I propose.

1. Get the country top websites from LLM, but not for every request, use a cache with a timeout of about a week, where key is country and values would be currency symbol and top 50 ( atmost ) list of ecommerce websites, and their search query, like what API parameter? q=, or name=. This would run atmost 200 times in a week, as the country once fetched would be cached in the db or memory.
2. Now for each website, we put in the search query and now scrape it, using playwright or beautiful soup depending on if its dynamic or static.
3. Here comes the hardest part, scraping the price from this website containing multiple items, there might be a case price, a offer price, an ad, it is very hard to fetch the price. It is something I am still working on,
	1. we can use common SEO properties used by e-commerce websites and they contain name and price
	2. if the above doesn't work, we can use heuristics to find the price based on the currency symbol,
		1. the one with big font
		2. the one in proximity to the Title
	3. The title div itself would be found using fuzzy search algo, closest to the product name.
4. Based on the scrapped prices, the API would return top k items for each website.

Why this is a good approach
1. It is not relying heavily on LLMs, hence cheap.
2. Its relatively fast, as we can scrap all the websites in parallel using async scraping

Due to my full time job, and in this Task being released on Monday, couldn't work more on the item number 3 of my solution. 
But I am confident and given a bit more time, I will be able to figure this out.

The current version doesn't work well, as the scraping logic is still something I need to work on, 
and the Gemini API I am using is also very slow and rate limited often.
But given some more time, during weekends (my current day job is hectic) I am confident I can work on this.

Thank you.
