#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News Briefing Generator using DeepSeek API

This script orchestrates the generation of a daily news briefing by:
1. Reading scraped news data from a JSON file for a given date.
2. Preparing a detailed prompt with the news data.
3. Calling the DeepSeek API (deepseek-reasoner model) to summarize the news.
4. Outputting the generated briefing.

Execution Example:
  python briefing_gen_ds.py --date YYYYMMDD
  Example: python briefing_gen_ds.py --date 20250612 --model deepseek-reasoner
  Example: python briefing_gen_ds.py --date 20250612 --model deepseek-chat

Note: 
- The script expects news JSON files in 'data/news-dataset/' named as 'YYYYMMDD_barchart_all-commodities_news.json'.
- DeepSeek API key needs to be configured in the script or via environment variable.
- Use --model to specify 'deepseek-reasoner' or 'deepseek-chat'.

Modifications:
- Replaced Poe API with DeepSeek API.
- Updated API key handling and request logic for DeepSeek.
- Removed Poe-specific command-line arguments (e.g., --bot_name).
- Added --model argument to choose between 'deepseek-reasoner' and 'deepseek-chat'.
- File description and comments updated to reflect DeepSeek integration and model selection.
"""

import argparse
import subprocess
import json
import os
import sys
from datetime import datetime
import asyncio

# Ensure you have the openai library installed: pip install openai
# DeepSeek API Key. For production, store API keys securely (e.g., environment variables).
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "...")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Attempt to import openai, provide guidance if not found
try:
    from openai import OpenAI
except ImportError:
    print("Error: openai library not found. Please install it by running: pip install openai")
    sys.exit(1)

def read_news_data(json_file_path):
    """Reads news data from the specified JSON file."""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Successfully read news data from {json_file_path}")
        return data
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_file_path}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while reading JSON file: {e}")
        return None

def format_news_for_llm(news_data):
    """Formats the news data into a string suitable for the LLM prompt."""
    if not news_data:
        return "No news data available."

    formatted_articles = []
    for i, article in enumerate(news_data):
        title = article.get('title', 'N/A')
        summary = article.get('summary', 'N/A')
        url = article.get('url', 'N/A') # Get the URL
        products_info = []
        if article.get('products'):
            for prod in article['products']:
                prod_name = prod.get('name', 'N/A')
                prod_symbol = prod.get('symbol', 'N/A')
                prod_value = prod.get('value', 'N/A')
                prod_delta = prod.get('delta', 'N/A')
                products_info.append(f"  - Product: {prod_name} ({prod_symbol}), Value: {prod_value}, Change: {prod_delta}")
        
        article_str = f"Article {i+1}:\nTitle: {title}\nURL: {url}\nSummary: {summary}" # Add URL to the string
        if products_info:
            article_str += "\nRelated Products:\n" + "\n".join(products_info)
        formatted_articles.append(article_str)
    
    return "\n\n---\n\n".join(formatted_articles)


def create_llm_prompt(news_text_formatted, target_date):
    """
    Creates the prompt for the LLM to generate the news briefing.

    This revised prompt provides a much stricter template and clearer instructions
    to ensure the LLM's output consistently matches the desired format,
    as exemplified by the user-provided "20250617_daily_briefing.txt" document.
    """
    # The prompt is rewritten to be more directive and includes a clear template.
    prompt = f"""
    You are a financial analyst AI. Your task is to analyze the provided financial news articles for the date {target_date} and generate a structured, concise daily briefing.

    **CRITICAL INSTRUCTIONS:**
    1.  **STICK TO THE SOURCE:** You MUST NOT use any external knowledge, web searches, or information beyond the provided text. All information in your response must be directly sourced from the "NEWS ARTICLES" section.
    2.  **FOLLOW THE FORMAT:** You MUST generate the output in the exact structure and format specified in the "DESIRED OUTPUT STRUCTURE" template below. Use Markdown for formatting.

    --- BEGIN NEWS ARTICLES ---
    {news_text_formatted}
    --- END NEWS ARTICLES ---

    --- BEGIN TASK & FORMATTING INSTRUCTIONS ---

    **I. Main Briefing Section:**
    For each commodity or financial product, synthesize all related information into a single entry. Organize these products under the following categories in this specific order:
    - Energy
    - Grains
    - Livestock
    - Metals
    - Softs
    - Currencies & Stocks

    Each product entry must contain these four points, using the exact bolded names:
    1.  **Price Movement:** Summarize the price change. Include general price direction for the day(e.g., "Rose significantly", "Declined moderately") and percentages or monetary values if provided in the text.
    2.  **Key Drivers:** List the primary reasons cited for the price movement. Be specific, e.g., "Stronger than expected US jobs report", "Concerns over weather in Brazil affecting supply", "Technical buying after breaking resistance level")
    3.  **Reverse Factors:** Mention any counter-arguments, risks, or factors that could reverse the observed trend, e.g., "Upcoming OPEC+ meeting could alter supply outlook", "High inflation data might lead to hawkish Fed stance", "Profit-taking after recent rally", if not mentioned from the article, point out potential reminder of drawing back of current support factors
    4.  **Classification:** Categorize the primary driver for the day's price movement into ONE of the following, based *only* on the information in the articles:
        *   `Long-term influencer - UP`: Price rose due to fundamental, long-term factors (e.g., structural supply shortages, major policy shifts, long-term demand trends).
        *   `Long-term influencer - DOWN`: Price fell due to fundamental, long-term factors (e.g., persistent oversupply, long-term demand destruction).
        *   `Short-term influencer - UP`: Price rose due to temporary factors (e.g., technical buying, brief supply disruptions, immediate news reactions, weather changes).
        *   `Short-term influencer - DOWN`: Price fell due to temporary factors (e.g., profit-taking, weather relief, short-lived market sentiment).
        *   `Unclear`: The articles provide conflicting information or an unclear driver for the price movement.

    **II. Summary Section:**
    After the main briefing, provide three distinct summary sections using Markdown:
    1.  **Summary & Key Themes:** A bulleted list of the most important overarching themes of the day.
    2.  **Risks Highlighted:** A numbered list of key risks identified in the articles.
    3.  **Watch Next:** A numbered list of upcoming events or market indicators to monitor, as mentioned in the text.

    **III. Classification Table:**
    Finally, create a Markdown table titled "Price Movement Classification Table". The table should have three columns: "Product", "Classification", and "Reason". Include an entry for every product analyzed in the main briefing. The "Reason" should be a very brief summary (2-5 words) of the key driver.

    --- END TASK & FORMATTING INSTRUCTIONS ---

    --- BEGIN DESIRED OUTPUT STRUCTURE ---

    ### Daily Financial Briefing: {target_date}

    #### **Energy**
    1.  **[Product Name]**
        - **Price Movement:** [Details]
        - **Key Drivers:** [Details]
        - **Reverse Factors:** [Details]
        - **Classification:** [Classification Type]

    #### **Grains**
    1.  **[Product Name]**
        - **Price Movement:** [Details]
        - **Key Drivers:** [Details]
        - **Reverse Factors:** [Details]
        - **Classification:** [Classification Type]

    (Continue for all other categories: Livestock, Metals, Softs, Currencies & Stocks)

    ---

    ### **Summary & Key Themes**
    - [Theme 1]
    - [Theme 2]

    ### **Risks Highlighted**
    1. [Risk 1]
    2. [Risk 2]

    ### **Watch Next**
    1. [Item 1 to watch]
    2. [Item 2 to watch]

    ---

    ### **Price Movement Classification Table**
    | Product          | Classification          | Reason                      |
    |------------------|-------------------------|-----------------------------|
    | [Product Name]   | [Classification Type]   | [Brief Reason]              |
    | [Product Name]   | [Classification Type]   | [Brief Reason]              |

    --- END DESIRED OUTPUT STRUCTURE ---

    Now, analyze the provided news articles and generate the briefing.
    """
    return prompt

async def get_briefing_from_deepseek(prompt, model_name="deepseek-reasoner"): # Added model_name parameter
    """Calls the DeepSeek API to get the news briefing. Returns a tuple (response_text, cost_info_text)."""
    if not DEEPSEEK_API_KEY:
        print("Error: DeepSeek API Key is not configured.")
        return "Error: DeepSeek API Key not configured.", "Cost information unavailable (API key not configured)."

    print(f"Sending request to DeepSeek API (Model: {model_name})...")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    messages = [{"role": "user", "content": prompt}]
    cost_info_text = "Cost info: Token usage not explicitly tracked in this version for DeepSeek."
    start_time = datetime.now()
    # mymodel = "deepseek-chat" # Replaced by model_name parameter
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages
        )
        full_response_text = response.choices[0].message.content
        # reasoning_content = response.choices[0].message.reasoning_content # If needed
        # You can inspect response.usage for token counts if available and relevant
        if hasattr(response, 'usage') and response.usage:
            cost_info_text = f"Cost info: Prompt tokens: {response.usage.prompt_tokens}, Completion tokens: {response.usage.completion_tokens}, Total tokens: {response.usage.total_tokens}"
        
        end_time = datetime.now()
        time_taken = end_time - start_time
        print("Received response from DeepSeek API.")
        time_info = f"Model Processing Time: {time_taken.total_seconds():.2f} seconds"
        return full_response_text, f"{cost_info_text}\n{time_info}"
    except Exception as e:
        error_msg = f"An error occurred while communicating with DeepSeek API: {e}"
        print(error_msg)
        return error_msg, f"Cost info: Unavailable due to exception: {e}"

async def main():
    parser = argparse.ArgumentParser(description="Generate a news briefing from Barchart commodity news.")
    # Changed: --date argument in YYYYMMDD format, made it required.
    parser.add_argument("--date", type=str, required=True, help="Target date for the news in YYYYMMDD format (e.g., 20250607).")
    parser.add_argument("--model", type=str, choices=['deepseek-reasoner', 'deepseek-chat'], default='deepseek-reasoner', help="DeepSeek model to use (default: deepseek-chat).")
    args = parser.parse_args()

    target_date_yyyymmdd = args.date
    selected_model = args.model
    # Removed bot_name as it's specific to Poe and we are using DeepSeek's default reasoning model.

    # Validate the target_date_yyyymmdd format
    try:
        # Changed: Validate YYYYMMDD format.
        datetime.strptime(target_date_yyyymmdd, "%Y%m%d")
    except ValueError:
        print(f"Error: Date format for --date must be YYYYMMDD. Received: {target_date_yyyymmdd}")
        sys.exit(1)

    # Ensure news-briefing directories exist
    script_dir = os.path.dirname(__file__)
    
    # Added: news-briefing directory for final output.
    news_briefing_dir = os.path.join(script_dir, "data", "news-briefing") # Adjust as needed
    
    os.makedirs(news_briefing_dir, exist_ok=True) # Create news-briefing directory

    # Construct the JSON file path based on the target_date_yyyymmdd
    # Assumes files are named like YYYYMMDD_barchart_all-commodities_news.json in data/news-dataset
    # Changed: JSON file path construction based on YYYYMMDD and fixed directory.
    json_filename = f"{target_date_yyyymmdd}_barchart_all-commodities_news.json"
    json_file_input_path = os.path.join(script_dir, "data", "news-dataset", json_filename)   #adjust as needed

    news_data = None
    actual_json_file_path = None

    # Changed: Logic to directly use constructed json_file_input_path. Removed scraper call and old --json_file logic.
    if not os.path.exists(json_file_input_path):
        print(f"Error: News JSON file not found at {json_file_input_path} for date {target_date_yyyymmdd}")
        sys.exit(1)
    
    print(f"Using news JSON file: {json_file_input_path}")
    news_data = read_news_data(json_file_input_path)
    actual_json_file_path = json_file_input_path

    # Simplified: Error handling if news_data is still None after trying to read.
    if not news_data:
        print(f"No news data could be read from {json_file_input_path}. Exiting.")
        sys.exit(1)

    # Changed: Handling for no news_data now writes to news-briefing directory with YYYYMMDD format.
    if not news_data: # This check is somewhat redundant due to earlier checks but kept for safety.
        print(f"No news data available from {actual_json_file_path} to process. Exiting.")
        error_briefing_filename = f"{target_date_yyyymmdd}_daily_briefing_no_data_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
        error_briefing_filepath = os.path.join(news_briefing_dir, error_briefing_filename) # Save to news-briefing
        try:
            with open(error_briefing_filepath, 'w', encoding='utf-8') as f_err:
                f_err.write(f"No news data found or processed for {target_date_yyyymmdd} from {actual_json_file_path} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.\n")
            print(f"Empty/error briefing note saved to: {error_briefing_filepath}")
        except Exception as e_save_err:
            print(f"Error saving empty/error briefing note: {e_save_err}")
        sys.exit(1)

    formatted_news = format_news_for_llm(news_data)
    if formatted_news == "No news data available.":
        print("Formatted news is empty. Nothing to send to LLM.")
        sys.exit(1)
    
    # Changed: Pass target_date_yyyymmdd to create_llm_prompt.
    llm_prompt = create_llm_prompt(formatted_news, target_date_yyyymmdd) 

    print(f"Attempting to generate briefing using DeepSeek API (Model: {selected_model})...")
    briefing_text, cost_info = await get_briefing_from_deepseek(llm_prompt, model_name=selected_model)

    print("\n--- Generated Briefing ---")
    print("--- End Generated Briefing ---")

    # Changed: Briefing filename base uses target_date_yyyymmdd.
    # Removed year_str parsing as YYYYMMDD already contains the year.
    briefing_filename_base = f"{target_date_yyyymmdd}_daily_briefing"
    
    if "Error:" in briefing_text or "Poe API Error:" in briefing_text:
        briefing_filename = f"{briefing_filename_base}_error.txt"
    else:
        briefing_filename = f"{briefing_filename_base}.txt"

    # Changed: Output directory for final briefing is news_briefing_dir.
    briefing_filepath = os.path.join(news_briefing_dir, briefing_filename)

    try:
        with open(briefing_filepath, 'w', encoding='utf-8') as f:
            # Changed: Use target_date_yyyymmdd for the briefing header.
            f.write(f"News Briefing for: {target_date_yyyymmdd[:4]}-{target_date_yyyymmdd[4:6]}-{target_date_yyyymmdd[6:]}\n") # Format YYYY-MM-DD for display
            f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"LLM Used: DeepSeek ({selected_model})\n")
            if actual_json_file_path:
                f.write(f"Source JSON: {os.path.basename(actual_json_file_path)}\n")
            if cost_info:
                f.write(f"{cost_info}\n")
            f.write("\n---\n\n")
            f.write(briefing_text)
        print(f"Briefing saved to: {briefing_filepath}")
    except Exception as e:
        print(f"Error saving briefing to file: {e}")

if __name__ == "__main__":
            
    asyncio.run(main())