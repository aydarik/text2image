from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import os
import datetime
import time
import re
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBasic()

def check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    correct_password = os.getenv("CACHE_PASSWORD")
    if not correct_password:
        return True
    
    if credentials.password != correct_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Cache Manager</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.7);
            --text: #f8fafc;
            --accent: #38bdf8;
            --danger: #ef4444;
            --glass-border: rgba(255, 255, 255, 0.1);
        }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: var(--text);
            margin: 0;
            padding: 2rem;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            padding: 1.5rem;
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: 1rem;
        }
        h1 { margin: 0; font-size: 1.5rem; color: var(--accent); }
        .controls { display: flex; gap: 1rem; align-items: center; }
        select, button {
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            border: 1px solid var(--glass-border);
            background: rgba(255, 255, 255, 0.05);
            color: white;
            cursor: pointer;
            transition: all 0.2s;
        }
        button { background: var(--danger); font-weight: 600; border: none; }
        button:hover { filter: brightness(1.2); transform: translateY(-1px); }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 1.5rem;
        }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--glass-border);
            border-radius: 0.75rem;
            overflow: hidden;
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            backdrop-filter: blur(8px);
        }
        .card:hover { transform: scale(1.05); border-color: var(--accent); }
        .card img { width: 100%; height: 180px; object-fit: cover; border-bottom: 1px solid var(--glass-border); }
        .card-info { padding: 0.75rem; font-size: 0.75rem; color: #94a3b8; }
        .pagination {
            margin-top: 3rem;
            display: flex;
            justify-content: center;
            gap: 1rem;
        }
        .pagination a {
            text-decoration: none;
            color: var(--text);
            padding: 0.5rem 1.5rem;
            background: var(--card-bg);
            border: 1px solid var(--glass-border);
            border-radius: 0.5rem;
            transition: all 0.2s;
        }
        .pagination a:hover { background: rgba(255,255,255,0.1); border-color: var(--accent); }
        .empty { text-align: center; color: #64748b; padding: 4rem; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Image Cache</h1>
            <div class="controls">
                <form action="/cache/clear" method="post" style="display: flex; gap: 0.5rem;">
                    <select name="period">
                        <option value="7d">Older than 7 days</option>
                        <option value="3d">Older than 3 days</option>
                        <option value="1d">Older than 1 day</option>
                        <option value="all">All images</option>
                    </select>
                    <button type="submit">Clear Cache</button>
                </form>
            </div>
        </header>

        {% if not images %}
            <div class="empty">No images found in cache.</div>
        {% else %}
            <div class="grid">
                {% for img in images %}
                    <div class="card">
                        <img src="/images_static/{{ img.name }}" alt="{{ img.name }}" loading="lazy">
                        <div class="card-info">
                            <div>{{ img.name[:16] }}...</div>
                            <div style="margin-top: 4px;">{{ img.date }}</div>
                        </div>
                    </div>
                {% endfor %}
            </div>
        {% endif %}

        <div class="pagination">
            {% if page > 1 %}
                <a href="/cache?page={{ page - 1 }}">Previous</a>
            {% endif %}
            {% if has_more %}
                <a href="/cache?page={{ page + 1 }}">Next</a>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

@router.get("/cache", response_class=HTMLResponse)
async def get_cache_manager(request: Request, page: int = 1, auth: bool = Depends(check_auth)):
    output_dir = "images"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    files = []
    for f in os.listdir(output_dir):
        if f.endswith(".jpg"):
            path = os.path.join(output_dir, f)
            ctime = os.path.getctime(path)
            files.append({
                "name": f,
                "ctime": ctime,
                "date": datetime.datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M")
            })
            
    # Sort by creation date DESC
    files.sort(key=lambda x: x["ctime"], reverse=True)
    
    # Pagination
    PAGE_SIZE = 100
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    paginated_files = files[start:end]
    has_more = len(files) > end
    
    # Render template (manually substituting because Jinja2 is not in requirements)
    content = HTML_TEMPLATE.replace("{% if not images %}", "" if paginated_files else "<!--")
    content = content.replace("{% else %}", "-->" if not paginated_files else "<!--")
    content = content.replace("{% endif %}", "-->")
    
    loop_pattern = re.compile(r"{% for img in images %}(.*?){% endfor %}", re.DOTALL)
    match = loop_pattern.search(content)
    if match:
        loop_content = match.group(1)
        items_html = ""
        for img in paginated_files:
            item = loop_content.replace("{{ img.name }}", img["name"])
            item = item.replace("{{ img.name[:16] }}", img["name"][:16])
            item = item.replace("{{ img.date }}", img["date"])
            items_html += item
        content = loop_pattern.sub(items_html, content)
        
    content = content.replace("{% if page > 1 %}", "" if page > 1 else "<!--")
    content = content.replace("{% if has_more %}", "" if has_more else "<!--")
    # Clean up the end of if blocks if we used <!-- 
    # Actually simple replacement for pagination
    if page > 1:
        content = content.replace("{{ page - 1 }}", str(page - 1))
    if has_more:
        content = content.replace("{{ page + 1 }}", str(page + 1))
    
    return HTMLResponse(content=content)

@router.post("/cache/clear")
async def clear_cache(period: str = Form(...), auth: bool = Depends(check_auth)):
    output_dir = "images"
    
    if not os.path.exists(output_dir):
        return RedirectResponse(url="/cache", status_code=303)
        
    now = time.time()
    seconds_map = {
        "1d": 86400,
        "3d": 259200,
        "7d": 604800,
        "all": 0
    }
    
    threshold = seconds_map.get(period, 0)
    
    for f in os.listdir(output_dir):
        if f.endswith(".jpg"):
            path = os.path.join(output_dir, f)
            ctime = os.path.getctime(path)
            if period == "all" or (now - ctime) > threshold:
                os.remove(path)
                logger.info(f"Deleted from cache: {f}")
                
    return RedirectResponse(url="/cache", status_code=303)
