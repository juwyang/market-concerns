import os
import glob
import json
from datetime import datetime

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(SCRIPT_DIR, 'data', 'reports')
INDEX_OUTPUT_PATH = os.path.join(REPORTS_DIR, 'index.html')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Market Concerns Reports</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f4f4f9; }
        h1 { text-align: center; color: #333; }
        .calendar-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .calendar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px; text-align: center; }
        .calendar-day-header { font-weight: bold; color: #666; padding: 10px 0; }
        .calendar-day { padding: 15px; border-radius: 4px; background: #f9f9f9; min-height: 40px; display: flex; align-items: center; justify-content: center; }
        .calendar-day.has-report { background-color: #e3f2fd; cursor: pointer; font-weight: bold; color: #1565c0; transition: background-color 0.2s; }
        .calendar-day.has-report:hover { background-color: #bbdefb; }
        .calendar-day.empty { background: transparent; }
        a { text-decoration: none; color: inherit; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
        .controls button { padding: 5px 10px; cursor: pointer; }
    </style>
</head>
<body>
    <h1>Daily Market Reports</h1>
    <div class="calendar-container">
        <div class="calendar-header">
            <button onclick="changeMonth(-1)">&lt; Prev</button>
            <h2 id="monthYear"></h2>
            <button onclick="changeMonth(1)">Next &gt;</button>
        </div>
        <div class="calendar-grid" id="calendar"></div>
    </div>

    <script>
        // Data injected by Python script
        const reports = __REPORTS_JSON__;

        let currentDate = new Date();

        function renderCalendar() {
            const year = currentDate.getFullYear();
            const month = currentDate.getMonth();
            
            document.getElementById('monthYear').textContent = new Date(year, month).toLocaleString('default', { month: 'long', year: 'numeric' });
            
            const firstDay = new Date(year, month, 1).getDay();
            const daysInMonth = new Date(year, month + 1, 0).getDate();
            
            const calendar = document.getElementById('calendar');
            calendar.innerHTML = '';

            const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
            days.forEach(day => {
                const div = document.createElement('div');
                div.className = 'calendar-day-header';
                div.textContent = day;
                calendar.appendChild(div);
            });

            for (let i = 0; i < firstDay; i++) {
                const div = document.createElement('div');
                div.className = 'calendar-day empty';
                calendar.appendChild(div);
            }

            for (let day = 1; day <= daysInMonth; day++) {
                const div = document.createElement('div');
                div.className = 'calendar-day';
                
                const dateStr = `${year}${String(month + 1).padStart(2, '0')}${String(day).padStart(2, '0')}`;
                
                if (reports[dateStr]) {
                    div.classList.add('has-report');
                    const link = document.createElement('a');
                    link.href = reports[dateStr];
                    link.textContent = day;
                    div.appendChild(link);
                } else {
                    div.textContent = day;
                }
                
                calendar.appendChild(div);
            }
        }

        function changeMonth(delta) {
            currentDate.setMonth(currentDate.getMonth() + delta);
            renderCalendar();
        }

        renderCalendar();
    </script>
</body>
</html>
"""

def main():
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)
        print(f"Created directory: {REPORTS_DIR}")

    # Find all HTML reports
    report_files = glob.glob(os.path.join(REPORTS_DIR, '*_report.html'))
    
    reports_map = {}
    for f in report_files:
        filename = os.path.basename(f)
        # Expected format: YYYYMMDD_report.html
        try:
            date_part = filename.split('_')[0]
            # Validate date
            datetime.strptime(date_part, '%Y%m%d')
            reports_map[date_part] = filename
        except ValueError:
            continue

    # Generate HTML
    reports_json = json.dumps(reports_map)
    html_content = HTML_TEMPLATE.replace('__REPORTS_JSON__', reports_json)

    with open(INDEX_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Generated index at: {INDEX_OUTPUT_PATH}")
    print(f"Found {len(reports_map)} reports.")

if __name__ == "__main__":
    main()
