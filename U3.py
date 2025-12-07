"""
Generate HTML brief from text file.
"""

import re
import os
import sys
import argparse
from datetime import datetime

class BriefingReportGenerator:
    """
    Parses a daily briefing text file and generates a styled, responsive HTML report.
    """

    def __init__(self, input_txt_path, output_html_path):
        """
        Initializes the generator with input and output file paths.

        Args:
            input_txt_path (str): The path to the source .txt file.
            output_html_path (str): The path where the generated .html file will be saved.
        """
        if not os.path.exists(input_txt_path):
            raise FileNotFoundError(f"The input file was not found at: {input_txt_path}")
        self.input_txt_path = input_txt_path
        self.output_html_path = output_html_path
        self.data = {
            "date": "N/A",
            "commodities": {},
            "summary": {
                "key_themes": [],
                "risks_highlighted": [],
                "watch_next": []
            },
            "classification_table": []
        }

    def parse_file(self):
        """
        Parses the text file and populates the self.data dictionary.
        This method acts as a state machine, moving through the sections of the text file.
        """
        with open(self.input_txt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        current_section = None
        current_category = None
        current_commodity = None
        current_list = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # --- Section Headers (###) ---
            if line.startswith("News Briefing for:"):
                self.data['date'] = line.replace("News Briefing for:", "").strip()
            elif line.startswith("### Daily Financial Briefing"):
                current_section = "commodities"
            elif line.startswith("### **Summary & Key Themes**"):
                current_section = "summary"
                current_list = "key_themes"
            elif line.startswith("### **Risks Highlighted**"):
                current_section = "summary"
                current_list = "risks_highlighted"
            elif line.startswith("### **Watch Next**"):
                current_section = "summary"
                current_list = "watch_next"
            elif line.startswith("### **Price Movement Classification Table**"):
                current_section = "table"
            
            # --- Commodity Categories (####) ---
            elif line.startswith("####"):
                # Extracts category name like "Energy" from "#### **Energy**"
                category_name = line.replace("####", "").replace("**", "").strip()
                if category_name not in self.data["commodities"]:
                    self.data["commodities"][category_name] = []
                current_category = category_name
                current_commodity = None

            # --- Table Parsing ---
            elif current_section == "table" and "|" in line and "---" not in line and "Product" not in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) == 3:
                    self.data["classification_table"].append({
                        "product": parts[0],
                        "classification": parts[1],
                        "reason": parts[2]
                    })

            # --- Commodity Details Parsing ---
            elif current_section == "commodities" and current_category:
                # New commodity item (e.g., "1.  **Crude Oil & RBOB Gasoline**")
                if re.match(r'^\d+\.\s+\*\*', line):
                    commodity_name = re.sub(r'^\d+\.\s+\*\*(.*?)\*\*', r'\1', line).strip()
                    current_commodity = {
                        "name": commodity_name,
                        "price_movement": "",
                        "key_drivers": [],
                        "reverse_factors": [],
                        "classification": ""
                    }
                    self.data["commodities"][current_category].append(current_commodity)
                    current_list = None # Reset list context
                
                elif current_commodity:
                    if line.startswith("- **Price Movement:**"):
                        current_commodity["price_movement"] = line.replace("- **Price Movement:**", "").strip()
                        current_list = None
                    elif line.startswith("- **Key Drivers:**"):
                        current_commodity["key_drivers"].append(line.replace("- **Key Drivers:**", "").strip())
                        current_list = "key_drivers"
                    elif line.startswith("- **Reverse Factors:**"):
                        current_commodity["reverse_factors"].append(line.replace("- **Reverse Factors:**", "").strip())
                        current_list = "reverse_factors"
                    elif line.startswith("- **Classification:**"):
                        current_commodity["classification"] = line.replace("- **Classification:**", "").strip()
                        current_list = None
                    # Handles multi-line list items for drivers/factors
                    elif current_list and (line.startswith("-") or line.startswith("*")):
                         current_commodity[current_list].append(line[1:].strip())


            # --- Summary Lists Parsing ---
            elif current_section == "summary" and current_list:
                if re.match(r'^(?:\d+\.|\-)\s+', line):
                    item_text = re.sub(r'^(?:\d+\.|\-)\s*', '', line)
                    self.data["summary"][current_list].append(item_text)

    def _get_movement_badge(self, classification_str):
        """Helper to generate HTML for the movement status badge."""
        classification_str = classification_str.lower()
        if "up" in classification_str:
            return '<span class="status-badge bg-green">UP</span>'
        elif "down" in classification_str:
            return '<span class="status-badge bg-red">DOWN</span>'
        else:
            return '<span class="status-badge bg-gray">UNCLEAR</span>'

    def _get_classification_color_class(self, classification_str):
        """Helper to get the background color class for a card."""
        classification_str = classification_str.lower()
        if "up" in classification_str:
            return 'bg-green'
        elif "down" in classification_str:
            return 'bg-red'
        else:
            return 'bg-gray'
            
    def _format_price_movement(self, movement_str, classification_str):
        """
        [重写后的函数]
        辅助函数，用于根据所需布局格式化价格变动显示。
        它从 classification_str 获取方向（up/down），并从 movement_str 提取主要数值。
        """
        # 1. 从 classification_str 判断方向，并设置对应的颜色和箭头CSS类
        direction = "neutral"
        if "up" in classification_str.lower():
            direction = "up"
        elif "down" in classification_str.lower():
            direction = "down"

        color_class = ""
        arrow_class = ""
        if direction == "up":
            color_class = "color-green"  # 用于文本颜色
            arrow_class = "arrow-up"     # 用于箭头样式
        elif direction == "down":
            color_class = "color-red"
            arrow_class = "arrow-down"
        else:
            color_class = "color-grey"
            # 中性情况不显示箭头

        # 2. 从 movement_str 提取第一个百分比作为主要数值
        primary_value = ""
        # 使用正则表达式查找格式如: +1.24%, -0.5%, + 2.3% 等
        match = re.search(r'([-+]?\s*\d+\.\d+%)', movement_str)
        if match:
            primary_value = match.group(1).strip()
        else:
            # 如果没有找到匹配的百分比，提供一个备用方案
            primary_value = ""

        # 3. 完整的 movement_str 作为详细描述
        detail_description = movement_str
        
        return f"""
            <div class="price-info">
                <div class="price-movement {color_class}">{primary_value}</div>
                <div class="price-detail">{detail_description}</div>
            </div>
        """

    def generate_html(self):
        """
        Generates the full HTML string using the parsed data.
        """
        # --- Left Column (Market Snapshot) ---
        market_snapshot_rows = ""
        for item in self.data['classification_table']:
            market_snapshot_rows += f"""
                        <tr>
                            <td>{item['product']}</td>
                            <td>{self._get_movement_badge(item['classification'])}</td>
                            <td>{item['reason']}</td>
                        </tr>"""

        # --- Middle Column (Commodity Details) ---
        main_content = ""
        for category, commodities in self.data['commodities'].items():
            main_content += f'<section><h2 class="category-header">{category.upper()}</h2>'
            for commodity in commodities:
                drivers_list = "".join([f"<li>{driver}</li>" for driver in commodity['key_drivers']])
                factors_list = "".join([f"<li>{factor}</li>" for factor in commodity['reverse_factors']])
                
                # 调用方式保持不变
                price_movement_html = self._format_price_movement(commodity['price_movement'], commodity['classification'])
                
                # 注意：这里的HTML结构也根据您的目标示例做了微调
                # 将 price_movement_html 放在了 card-header 下方
                main_content += f"""
                <div class="card commodity-card">
                    <div class="card-header">
                        <h3>{commodity['name']}</h3>
                    </div>
                    {price_movement_html}
                    <div class="drivers-section">
                        <h4>Key Drivers</h4>
                        <ul>{drivers_list}</ul>
                        <h4>Reverse Factors</h4>
                        <ul>{factors_list}</ul>
                    </div>
                    <div class="classification-badge {self._get_classification_color_class(commodity['classification'])}">
                        {commodity['classification']}
                    </div>
                </div>"""
            main_content += '</section>'

        # --- Right Column (Summaries) ---
        key_themes_list = "".join([f"<li>{theme}</li>" for theme in self.data['summary']['key_themes']])
        risks_list = "".join([f"<li>{risk}</li>" for risk in self.data['summary']['risks_highlighted']])
        watch_next_list = "".join([f"<li>{item}</li>" for item in self.data['summary']['watch_next']])

        # --- Final HTML Assembly ---
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Financial Briefing - {self.data['date']}</title>
    <style>
        /* --- General & Reset --- */
        :root {{
            --bg-color: #f0f2f5;
            --card-bg: #ffffff;
            --text-color: #333333;
            --header-color: #1a2c4e;
            --border-color: #e0e0e0;
            --green-color: #28a745;
            --red-color: #dc3545;
            --gray-color: #6c757d;
            --green-bg: #e9f7ec;
            --red-bg: #fdebec;
            --gray-bg: #f8f9fa;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            margin: 0;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
        }}
        * {{
            box-sizing: border-box;
        }}

        /* --- Layout --- */
        .dashboard-container {{
            display: flex;
            flex-wrap: wrap;
            padding: 20px;
            gap: 20px;
        }}
        .column {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        .column-left {{ flex: 1 1 300px; }}
        .column-main {{ flex: 2 1 500px; }}
        .column-right {{ flex: 1 1 300px; }}

        /* --- Cards --- */
        .card {{
            background-color: var(--card-bg);
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            padding: 20px;
            border: 1px solid var(--border-color);
        }}
        .card h2 {{
            margin-top: 0;
            color: var(--header-color);
            font-size: 1.2rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            margin-bottom: 15px;
        }}

        /* --- Left Column: Market Snapshot --- */
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .summary-table th, .summary-table td {{
            text-align: left;
            padding: 10px 8px;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.9rem;
        }}
        .summary-table th {{
            font-weight: 600;
        }}
        .summary-table tr:last-child td {{
            border-bottom: none;
        }}
        .status-badge {{
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: 700;
            font-size: 0.8rem;
            color: var(--card-bg);
            text-transform: uppercase;
        }}

        /* --- Main Column: Commodity Details --- */
        .main-header {{
            text-align: center;
            margin-bottom: 20px;
        }}
        .main-header h1 {{
            color: var(--header-color);
            margin: 0;
        }}
        .main-header p {{
            color: var(--gray-color);
            font-size: 1.1rem;
            margin-top: 5px;
        }}
        .category-header {{
            text-transform: uppercase;
            color: var(--gray-color);
            letter-spacing: 1px;
            margin-top: 20px;
            margin-bottom: 10px;
            font-size: 1rem;
        }}
        .commodity-card .card-header h3 {{
            margin: 0;
            font-size: 1.15rem;
            color: var(--header-color);
        }}
        .price-info {{
            display: flex;
            align-items: baseline;
            gap: 15px;
            margin: 15px 0;
        }}
        .price-movement {{
            font-size: 1.5rem;
            font-weight: 700;
        }}
        .price-detail {{
            font-size: 0.95rem;
            color: var(--gray-color);
        }}
        .arrow-up::before {{ content: '▲'; font-size: 0.6em; }}
        .arrow-down::before {{ content: '▼'; font-size: 0.6em; }}
        .drivers-section h4 {{
            margin-bottom: 5px;
            margin-top: 15px;
            font-size: 0.9rem;
            color: var(--header-color);
        }}
        .drivers-section ul {{
            margin: 0;
            padding-left: 20px;
            font-size: 0.9rem;
        }}
        .classification-badge {{
            margin-top: 15px;
            padding: 5px 12px;
            border-radius: 5px;
            display: inline-block;
            font-size: 0.8rem;
            font-weight: 500;
            color: var(--text-color);
        }}

        /* --- Right Column: Summaries --- */
        .right-column-list {{
            padding-left: 20px;
            margin: 0;
            font-size: 0.9rem;
        }}
        .right-column-list li {{
            margin-bottom: 10px;
        }}

        /* --- Color Utilities --- */
        .bg-green {{ background-color: var(--green-color); }}
        .bg-red {{ background-color: var(--red-color); }}
        .bg-gray {{ background-color: var(--gray-color); }}
        .color-green {{ color: var(--green-color); }}
        .color-red {{ color: var(--red-color); }}
        .classification-badge.bg-green {{ background-color: var(--green-bg); color: var(--green-color); border: 1px solid var(--green-color); }}
        .classification-badge.bg-red {{ background-color: var(--red-bg); color: var(--red-color); border: 1px solid var(--red-color); }}
        .classification-badge.bg-gray {{ background-color: var(--gray-bg); color: var(--gray-color); border: 1px solid #ccc; }}
        
        /* --- Responsive Design --- */
        @media (max-width: 1024px) {{
            .column-left, .column-right {{ flex: 1 1 100%; order: 3; }}
            .column-main {{ flex: 2 1 100%; order: 1; }}
            .main-header {{ order: 0; width: 100%; }}
        }}
        @media (max-width: 768px) {{
            .dashboard-container {{
                flex-direction: column;
                padding: 10px;
                gap: 10px;
            }}
            .column {{
                gap: 10px;
            }}
        }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- ======================= LEFT COLUMN ======================== -->
        <aside class="column column-left">
            <div class="card">
                <h2>Market Snapshot</h2>
                <table class="summary-table">
                    <thead>
                        <tr>
                            <th>Product</th>
                            <th>Movement</th>
                            <th>Reason</th>
                        </tr>
                    </thead>
                    <tbody>
                        {market_snapshot_rows}
                    </tbody>
                </table>
            </div>
        </aside>

        <!-- ======================= MIDDLE COLUMN ======================== -->
        <main class="column column-main">
            <header class="main-header">
                <h1>Daily Financial Briefing</h1>
                <p>Date: {self.data['date']}</p>
            </header>
            {main_content}
        </main>

        <!-- ======================= RIGHT COLUMN ======================== -->
        <aside class="column column-right">
            <div class="card">
                <h2><i class="fa-solid fa-lightbulb"></i>Key Themes</h2>
                <ul class="right-column-list theme-list">
                    {key_themes_list}
                </ul>
            </div>
            <div class="card">
                <h2><i class="fa-solid fa-triangle-exclamation"></i>Risks Highlighted</h2>
                <ul class="right-column-list risk-list">
                    {risks_list}
                </ul>
            </div>
            <div class="card">
                <h2><i class="fa-solid fa-binoculars"></i>Watch Next</h2>
                <ul class="right-column-list watch-list">
                    {watch_next_list}
                </ul>
            </div>
        </aside>
    </div>
</body>
</html>
        """
        return html_template

    def run(self):
        """
        Executes the full process: parse file, generate HTML, and write to output file.
        """
        print("Parsing briefing file...")
        self.parse_file()
        
        print("Generating HTML report...")
        html_content = self.generate_html()
        
        with open(self.output_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"Successfully generated report: {self.output_html_path}")


if __name__ == '__main__':
    # --- Setup Command-Line Argument Parser ---
    parser = argparse.ArgumentParser(
        description="Generate an HTML financial briefing report from a text file.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--date',
        required=True,
        help="The date of the report in YYYYMMDD format (e.g., 20250722)."
    )
    args = parser.parse_args()

    # --- Construct File Paths Based on Date Argument ---
    try:
        # Validate date format
        datetime.strptime(args.date, '%Y%m%d')
        
        script_dir = os.path.dirname(__file__) or '.'
        
        # Input file path: data/news-briefing/YYYYMMDD_daily_briefing.txt
        input_filename = f"{args.date}_daily_briefing.txt"
        input_path = os.path.join(script_dir, "data", "news-briefing", input_filename)
        
        # Output file path: data/reports/YYYYMMDD_report.html
        output_filename = f"{args.date}_report.html"
        output_path = os.path.join(script_dir, "data", "reports", output_filename)
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Create and run the generator
        generator = BriefingReportGenerator(input_txt_path=input_path, output_html_path=output_path)
        generator.run()

    except FileNotFoundError as e:
        print(f"\nError: Input file not found.")
        print(f"Looked for: {e.filename}")
        print("Please ensure the file exists and the path is correct relative to the script.")
    except ValueError:
        print(f"\nError: Invalid date format for --date argument.")
        print("Please use YYYYMMDD format (e.g., 20250722).")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")