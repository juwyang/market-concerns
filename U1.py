# ... (file header and existing code up to parse_date_string_to_timestamp) ...
# File Description:
# This script scrapes news articles from Barchart.com using its API.
# It can fetch news for a specific target date (CDT) or the most recent news items.
# The script now extracts news content directly from HTML, including title, URL, publish time,
# and summary for each article. It specifically filters for Barchart news items and processes
# their metadata and content using BeautifulSoup.
#
# Updates:
# - Added HTML parsing using BeautifulSoup to extract news content
# - Now extracts summaries from story excerpts
# - Improved feed name and publish time parsing
# - Enhanced URL handling and news ID extraction

# Usage: python U1.py --date 20250611


import logging
import requests
import json
import time
import datetime
import re
from dateutil import parser as date_parser # For robust date string parsing
import argparse
import os
from bs4 import BeautifulSoup  # For parsing HTML content

# --- Configuration ---
TARGET_SUBSECTION = "all-commodities"  # or "all-commodities", etc.
NEWS_COUNT_LIMIT = 35  # Max number of news items to fetch if no date limit is set
TARGET_DATE_STR = "20250611" # Example: Fetch news on Jun 9, 2025 (CDT). Format: YYYYMMDD
MAX_API_CALLS = 500 # Safety limit for API calls
API_CALL_DELAY_SECONDS = 1.0 # Delay between API calls
OUTPUT_FILENAME_TEMPLATE = '{date_str}_barchart_{subsection}_news.json'
# --- End Configuration ---

API_URL = "https://www.barchart.com/news/load-more-stories"
BASE_URL = "https://www.barchart.com"
NEWS_PAGE_URL_TEMPLATE = "https://www.barchart.com/news/commodities/{subsection}"

# ... (get_initial_cookies_and_xsrf function remains the same) ...
def get_initial_cookies_and_xsrf(session, subsection):
    # ... existing code ...
    if subsection.lower() == "all-commodities":
        news_page_url = "https://www.barchart.com/news/commodities"
    else:
        news_page_url = NEWS_PAGE_URL_TEMPLATE.format(subsection=subsection)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,de;q=0.7,fr;q=0.6',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
    }
    try:
        print(f"Fetching initial page: {news_page_url}")
        response = session.get(news_page_url, headers=headers, timeout=15)
        response.raise_for_status()
        print(f"Initial page fetched successfully. Status: {response.status_code}")
        xsrf_token_raw = session.cookies.get('XSRF-TOKEN')
        if not xsrf_token_raw:
            print("Error: XSRF-TOKEN not found in cookies after initial GET request.")
            return None
        
        try:
            import urllib.parse
            xsrf_token = urllib.parse.unquote(xsrf_token_raw)
            print(f"Successfully obtained and URL-decoded XSRF-TOKEN: {xsrf_token} (raw: {xsrf_token_raw})")
        except Exception as e:
            print(f"Error URL-decoding XSRF token: {e}. Using raw token: {xsrf_token_raw}")
            xsrf_token = xsrf_token_raw
        return xsrf_token
    except requests.RequestException as e:
        print(f"Error during initial GET request to {news_page_url}: {e}")
        return None

def date_str_to_timestamps_for_day(date_str_yyyymmdd):
    """Converts a YYYYMMDD string (assumed to be CDT) to UTC start and end timestamps for that day."""
    logger = logging.getLogger(__name__)
    try:
        dt_obj_naive = datetime.datetime.strptime(date_str_yyyymmdd, '%Y%m%d')
        cdt_tz = datetime.timezone(datetime.timedelta(hours=-5)) # Standard CDT, non-DST
        dt_obj_cdt_start = dt_obj_naive.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=cdt_tz)
        dt_obj_cdt_end = dt_obj_naive.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=cdt_tz)
        dt_obj_utc_start = dt_obj_cdt_start.astimezone(datetime.timezone.utc)
        dt_obj_utc_end = dt_obj_cdt_end.astimezone(datetime.timezone.utc)
        start_timestamp = int(dt_obj_utc_start.timestamp())
        end_timestamp = int(dt_obj_utc_end.timestamp())
        logger.info(f"Target date (CDT): {dt_obj_naive.strftime('%Y-%m-%d')}")
        logger.info(f"CDT start: {dt_obj_cdt_start.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        logger.info(f"CDT end:   {dt_obj_cdt_end.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        logger.info(f"UTC start: {dt_obj_utc_start.strftime('%Y-%m-%d %H:%M:%S %Z%z')} ({start_timestamp})")
        logger.info(f"UTC end:   {dt_obj_utc_end.strftime('%Y-%m-%d %H:%M:%S %Z%z')} ({end_timestamp})")
        return start_timestamp, end_timestamp
    except ValueError as e:
        logger.error(f"Error parsing date string {date_str_yyyymmdd}: {e}")
        return None, None

def parse_date_string_to_timestamp(date_str):
    """将日期字符串解析为UTC时间戳。
    支持格式:
    1. 'Mon Jun 9, 9:56AM CDT' - 完整时间格式
    2. 'Sat Jun 10, 2023' - 日期格式(将转换为中午12点CDT)
    如果未指定年份,使用当前年份;如果未指定时区,默认为CDT;如果未指定具体时间,默认为当天中午12点CDT
    """
    if not date_str:
        return None

    try:
        # 获取当前年份作为默认值
        current_year = datetime.datetime.now().year
        
        # 创建CDT时区对象
        cdt_tz = datetime.timezone(datetime.timedelta(hours=-5))  # CDT = UTC-5
        
        # 解析日期字符串
        dt_object = date_parser.parse(date_str)
        
        # 如果解析结果没有时区信息
        if dt_object.tzinfo is None:
            # 添加CDT时区
            dt_object = dt_object.replace(tzinfo=cdt_tz)
            
            # 如果原始字符串中没有时间信息,设置为中午12点
            if date_str.lower().find('am') == -1 and date_str.lower().find('pm') == -1:
                dt_object = dt_object.replace(hour=12, minute=0, second=0, microsecond=0)
        
        # 如果年份是1900(dateutil默认值),使用当前年份
        if dt_object.year == 1900:
            dt_object = dt_object.replace(year=current_year)
            
        # 转换为UTC时间
        dt_object_utc = dt_object.astimezone(datetime.timezone.utc)
        
        return int(dt_object_utc.timestamp())
        
    except Exception as e:
        print(f"无法解析日期字符串 '{date_str}': {e}")
        return None


def fetch_barchart_news(subsection, target_date_str=None, news_count_limit=30, initial_xsrf_token=None):
    """Fetches news articles from Barchart for a given subsection and date criteria."""
    all_news_items = []
    target_day_start_ts, target_day_end_ts = None, None

    if target_date_str:
        target_day_start_ts, target_day_end_ts = date_str_to_timestamps_for_day(target_date_str)
        if not (target_day_start_ts and target_day_end_ts):
            print(f"ERROR: Could not determine timestamp range for target date {target_date_str}. Aborting.")
            return []
        print(f"\n=== Target Date: {target_date_str} (CDT) ===")
        # Initial 'before' timestamp is set to the end of the target day (UTC) + 1 sec to ensure all items on that day are included in the first fetch if possible
        current_before_timestamp = target_day_end_ts + 1 
        print(f"UTC Timestamp Range for filtering: {target_day_start_ts} to {target_day_end_ts}")
        print(f"(From {datetime.datetime.fromtimestamp(target_day_start_ts, tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')} to {datetime.datetime.fromtimestamp(target_day_end_ts, tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')})")
        print(f"Initial 'beforeTimestamp' for API calls: {current_before_timestamp} ({datetime.datetime.fromtimestamp(current_before_timestamp, tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')})\n")
    else:
        current_before_timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        print(f"No specific target date. Will fetch up to {news_count_limit} most recent articles.")
        print(f"Starting with 'beforeTimestamp': {current_before_timestamp}")

    with requests.Session() as session:
        xsrf_token = initial_xsrf_token or get_initial_cookies_and_xsrf(session, subsection)
        if not xsrf_token:
            print("Failed to obtain XSRF token. Aborting.")
            return []

        api_headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'origin': BASE_URL,
            'referer': f"{BASE_URL}/news/commodities/{subsection}" if subsection.lower() != "all-commodities" else f"{BASE_URL}/news/commodities",
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'x-xsrf-token': xsrf_token
        }
        payload_template = {
            "section": "market_commentary",
            "subSection": subsection,
            "search": [],
            "useThumbnail": True,
            "symbolType": False
        }

        stop_fetching = False
        processed_news_ids = set()
        api_call_num = 0

        while not stop_fetching and api_call_num < MAX_API_CALLS:
            api_call_num += 1
            payload = payload_template.copy()
            payload["before"] = str(current_before_timestamp) # pay attention, use ['before']

            print(f"\nAPI Call {api_call_num} with beforeTimestamp: {current_before_timestamp} ({datetime.datetime.fromtimestamp(current_before_timestamp, tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')})")
            response_json = None # Initialize to ensure it's defined
            try:
                response = session.post(API_URL, headers=api_headers, json=payload, timeout=20)
                response.raise_for_status()
                response_json = response.json()
            except requests.RequestException as e:
                print(f"  Error during API call: {e}")
                stop_fetching = True 
                continue 
            except json.JSONDecodeError as e:
                print(f"  Error decoding JSON response: {e}")
                stop_fetching = True 
                continue 
            
            if not response_json: # Should not happen if no exception, but as a safeguard
                print("  No JSON response received. Stopping.")
                stop_fetching = True
                continue

            html_content = response_json.get('content')
            timestamp_str = response_json.get('timestamp')

            if not html_content and not timestamp_str:
                print("  No HTML content in this batch and no 'timestamp' for next page. Assuming no more older news.")
                stop_fetching = True

            batch_items_added_count = 0
            earliest_valid_ts_in_batch_for_fallback = None # UTC timestamp of the OLDEST VALID item in this batch
            processed_in_batch_count = 0

            if html_content:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                stories = soup.find_all('div', class_='story clearfix')
                processed_in_batch_count = len(stories)

                for story_div in stories:
                    link_tag = story_div.find('a', class_='story-link', href=True)
                    meta_tag = story_div.find('span', class_='story-meta show-for-small-up')
                    excerpt_tag = story_div.find('p', class_='story-excerpt show-for-medium-up')

                    if not (link_tag and meta_tag):
                        print("    Skipping a story div due to missing link or meta tag.")
                        continue

                    news_url = link_tag['href']
                    if not news_url.startswith('http'):
                        news_url = BASE_URL + news_url
                    
                    title = link_tag.get_text(strip=True)
                    
                    # Extract news ID from URL (e.g., /story/news/NEWS_ID/slug)
                    news_id_match = re.search(r'/news/(\d+)/', news_url)
                    news_id = news_id_match.group(1) if news_id_match else None
                    if not news_id:
                        print(f"    Skipping story (Title: {title[:30]}...) due to missing ID in URL: {news_url}")
                        continue

                    meta_text = meta_tag.get_text(strip=True)
                    # Example: Barchart - Tue Jun 10, 5:00PM CDT
                    # Example: Associated Press - Fri, 07 Jun 2024 19:48
                    feed_name_match = re.match(r'^([^-]+)-', meta_text)
                    feed_name = feed_name_match.group(1).strip() if feed_name_match else "Unknown"
                    
                    published_str_part = meta_text
                    if feed_name_match:
                        published_str_part = meta_text[len(feed_name_match.group(0)):].strip()
                    
                    if feed_name.lower() != "barchart":
                        # print(f"    INFO: Skipping item ID {news_id} (Title: {title[:30].encode('utf-8').decode('utf-8')}...) because feedName is '{feed_name}', not 'Barchart'.")
                        continue

                    current_item_ts_utc = parse_date_string_to_timestamp(published_str_part)

                    if current_item_ts_utc is None:
                        print(f"    Skipping item (ID: {news_id}, Title: {title[:30]}...) due to unparseable date from meta: '{published_str_part}' (original meta: '{meta_text}')")
                        continue

                    if earliest_valid_ts_in_batch_for_fallback is None or current_item_ts_utc < earliest_valid_ts_in_batch_for_fallback:
                        earliest_valid_ts_in_batch_for_fallback = current_item_ts_utc

                    if target_day_start_ts and current_item_ts_utc < target_day_start_ts:
                        print(f"  INFO: News item '{title[:50]}...' published at {published_str_part} (TS: {current_item_ts_utc}) is older than target start (TS: {target_day_start_ts}).")
                        print("         Stopping further API calls.")
                        stop_fetching = True
                        break 

                    if news_id not in processed_news_ids:
                        if not target_date_str or (target_day_start_ts <= current_item_ts_utc <= target_day_end_ts):
                            summary = excerpt_tag.get_text(strip=True) if excerpt_tag else ""
                            
                            all_news_items.append({
                                'id': news_id,
                                'title': title,
                                'url': news_url,
                                'published_str_original': published_str_part, 
                                'published_timestamp_utc': current_item_ts_utc,
                                'summary': summary
                            })
                            processed_news_ids.add(news_id)
                            batch_items_added_count += 1
            
            print(f"  Batch summary: Processed {processed_in_batch_count} story divs, added {batch_items_added_count} new valid items. Total collected: {len(all_news_items)}.")

            if stop_fetching: 
                break 

            # Determine the 'beforeTimestamp' for the next API call
            next_api_page_timestamp_str = response_json.get('timestamp') 
            
            if next_api_page_timestamp_str:
                try:
                    next_api_page_timestamp = int(next_api_page_timestamp_str)
                    # Sanity check: next page timestamp should be older than or equal to the oldest item in the current batch we processed,
                    # or older than the current 'beforeTimestamp' if no items were processed.
                    # It should not be newer than the latest item we just processed, unless it's the same page.
                    if earliest_valid_ts_in_batch_for_fallback and next_api_page_timestamp > earliest_valid_ts_in_batch_for_fallback:
                        if next_api_page_timestamp < current_before_timestamp: # If it's a valid step back but not as far as items suggest
                             print(f"    Warning: API 'timestamp' ({next_api_page_timestamp}) is newer than earliest item in batch ({earliest_valid_ts_in_batch_for_fallback}). Using API's value.")
                        # else: it might be an issue if it's also newer than current_before_timestamp, indicating no progress or wrong direction.
                    
                    # Crucially, the next timestamp must be less than the current one to make progress fetching older items.
                    if next_api_page_timestamp < current_before_timestamp:
                        current_before_timestamp = next_api_page_timestamp
                        print(f"  Next API call will use 'before' from API response: {current_before_timestamp}")
                    else:
                        print(f"    Warning: API 'timestamp' ({next_api_page_timestamp}) is not older than current 'beforeTimestamp' ({current_before_timestamp}). This may indicate end of data or an issue.")
                        # Fall through to try fallback if this happens

                except ValueError:
                    print(f"    Warning: Could not parse 'timestamp' ({next_api_page_timestamp_str}) from API response. Attempting fallback.")
            
            if not target_date_str and len(all_news_items) >= news_count_limit:
                print(f"Reached news_count_limit ({news_count_limit}). Stopping.")
                stop_fetching = True
            
            if not stop_fetching:
                time.sleep(API_CALL_DELAY_SECONDS)
        
        if api_call_num >= MAX_API_CALLS:
            print(f"Reached MAX_API_CALLS ({MAX_API_CALLS}). Stopping.")

    if target_day_start_ts and target_day_end_ts: # Final filter for good measure
        print(f"\nFinal check: Filtering {len(all_news_items)} collected items...")
        final_items_count_before = len(all_news_items)
        all_news_items = [
            item for item in all_news_items
            if target_day_start_ts <= item['published_timestamp_utc'] <= target_day_end_ts
        ]
        print(f"Removed {final_items_count_before - len(all_news_items)} items outside target range during final check.")
    
    print(f"\nTotal news items fetched and filtered: {len(all_news_items)}")
    return all_news_items

# ... (main function remains largely the same, ensure logging is configured) ...

def main():
    """Main function to orchestrate the scraping process."""
    # Configure logging at the beginning of main or at script level
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description='Barchart新闻爬取工具')
    parser.add_argument('--subsection', type=str, default='all-commodities',
                      help='要爬取的新闻子版块 (默认: all-commodities)')
    parser.add_argument('--date', type=str, default='20250611',
                      help='目标日期，格式YYYYMMDD (默认: 20250611)')
    
    args = parser.parse_args()
    
    # 使用命令行参数或默认配置
    subsection_to_fetch = args.subsection
    target_date_input = args.date

    if not subsection_to_fetch:
        logging.error("TARGET_SUBSECTION cannot be empty. Please configure it.")
        return

    date_suffix = target_date_input if target_date_input else datetime.datetime.now().strftime('%Y%m%d')
    output_filename = OUTPUT_FILENAME_TEMPLATE.format(subsection=subsection_to_fetch.replace('/', '-'), date_str=date_suffix)

    logging.info(f"Starting Barchart news scraper for subsection: '{subsection_to_fetch}'")
    fetched_news = []
    if target_date_input:
        logging.info(f"Attempting to fetch news for date: {target_date_input} (CDT assumed)")
        fetched_news = fetch_barchart_news(subsection_to_fetch, target_date_str=target_date_input)
    else:
        logging.info(f"Fetching most recent {NEWS_COUNT_LIMIT} news items (no specific date).")
        fetched_news = fetch_barchart_news(subsection_to_fetch, news_count_limit=NEWS_COUNT_LIMIT)

    if fetched_news:
        fetched_news.sort(key=lambda x: x['id'], reverse=True)
        
        # 确保输出目录存在
        output_dir = os.path.join('data', 'news-dataset')  # Adjust as needed
        os.makedirs(output_dir, exist_ok=True)
        
        # 构建完整的输出文件路径
        output_path = os.path.join(output_dir, output_filename)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(fetched_news, f, indent=4, ensure_ascii=False)
            logging.info(f"Successfully saved {len(fetched_news)} news items to {output_path}")
        except IOError as e:
            logging.error(f"Error writing to file {output_path}: {e}")
    else:
        logging.info(f"No news items were fetched for subsection '{subsection_to_fetch}' with the given criteria.")
if __name__ == "__main__":
    main()
