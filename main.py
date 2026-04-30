from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from playwright.async_api import async_playwright
import uvicorn
import time
import logging
import hashlib
import json
import os

from contextlib import asynccontextmanager
import asyncio
import cache_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)-7s %(asctime)s %(message)s')
logger = logging.getLogger(__name__)

START_TIME = time.time()
render_count = {}  # Maps IP address to count
last_request_time = {}  # Maps IP address to last request time
total_execution_time = 0.0

# Global playwright and browser objects
playwright_instance = None
browser_instance = None
browser_lock = asyncio.Lock()

async def start_browser():
    global playwright_instance, browser_instance
    async with browser_lock:
        # Check if browser is already running and connected
        if browser_instance and browser_instance.is_connected():
            return

        logger.info("Starting browser...")
        # Clean up existing instances if they exist
        if browser_instance:
            try:
                await browser_instance.close()
            except Exception:
                pass
        if playwright_instance:
            try:
                await playwright_instance.stop()
            except Exception:
                pass

        playwright_instance = await async_playwright().start()
        browser_instance = await playwright_instance.chromium.launch()

async def stop_browser():
    global playwright_instance, browser_instance
    logger.info("Stopping browser...")
    if browser_instance:
        try:
            await browser_instance.close()
        except Exception:
            pass
    if playwright_instance:
        try:
            await playwright_instance.stop()
        except Exception:
            pass

# Environment variables
SAVE_IMAGES = os.getenv("SAVE_IMAGES", "false").lower() == "true"
RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "20"))
IP_BLACKLIST = set(filter(None, [ip.strip() for ip in os.getenv("IP_BLACKLIST", "").split(",")]))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_browser()
    yield
    await stop_browser()

app = FastAPI(
    title="HTML to JPG API",
    description="An API to render HTML content as a JPG image using Playwright.",
    version="1.3.5",
    lifespan=lifespan
)

@app.middleware("http")
async def ip_check_middleware(request: Request, call_next):
    request_ip = (
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0]
        or request.client.host
    )
    request.state.ip = request_ip
    
    if request_ip in IP_BLACKLIST:
        logger.warning(f"Blacklisted IP attempt: {request_ip}")
        return Response(content="Forbidden", status_code=403)
    
    response = await call_next(request)
    return response

# Mount images directory for static access
app.mount("/images_static", StaticFiles(directory="images", html=True), name="images_static")

# Include cache management router
app.include_router(cache_manager.router)

class RenderRequest(BaseModel):
    html: str
    width: int = 240
    height: int = 240
    cache: bool = True

@app.post(
    "/render",
    summary="Render HTML to JPG",
    description="Accepts an HTML string and dimensions, renders it in a headless browser, and returns the screenshot as a JPEG image.",
    responses={
        200: {
            "content": {"image/jpeg": {}},
            "description": "The rendered JPG image."
        }
    }
)
async def render_html(request: RenderRequest, req: Request):
    global render_count, total_execution_time, last_request_time
    
    request_ip = req.state.ip
    
    current_time = time.time()
    if request_ip in last_request_time and current_time - last_request_time[request_ip] < RATE_LIMIT_SECONDS:
        raise HTTPException(
            status_code=429,
            detail=f"Too Many Requests. Only 1 request per {RATE_LIMIT_SECONDS} seconds is allowed."
        )
    last_request_time[request_ip] = current_time

    start_render = time.time()
    try:
        # FastAPI handles the parsing and validation of the request body into 'request'
        
        ip_count = render_count.get(request_ip, 0) + 1

        # Calculate hash of the request
        req_dict = request.dict()
        # Sort keys to ensure consistent order for hashing
        req_str = json.dumps(req_dict, sort_keys=True)
        req_hash = hashlib.sha256(req_str.encode("utf-8")).hexdigest()
        
        # Define output directory based on IP
        output_dir = os.path.join("images", request_ip)
        os.makedirs(output_dir, exist_ok=True)
        
        # Check if caching is enabled (enabled by default)
        cache_enabled = request.cache
        
        filename = f"{req_hash}.jpg"
        file_path = os.path.join(output_dir, filename)
        
        # Check if file exists in cache
        if cache_enabled and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                cached_bytes = f.read()
            return Response(content=cached_bytes, media_type="image/jpeg")

        # Retry loop for browser errors
        for attempt in range(2):
            try:
                if not browser_instance or not browser_instance.is_connected():
                    logger.warning("Browser not initialized or disconnected. Starting...")
                    await start_browser()

                # Create a new context and page for each request to ensure thread safety (isolation)
                context = await browser_instance.new_context(viewport={"width": request.width, "height": request.height})
                try:
                    page = await context.new_page()
                    await page.set_content(request.html)

                    if ("window.renderReady" in request.html):
                        # Wait until widget JS finished rendering
                        await page.wait_for_function(
                            "window.renderReady === true",
                            timeout=5000
                        )

                    screenshot_bytes = await page.screenshot(type="jpeg", quality=90)
                    
                    execution_time = (time.time() - start_render) * 1000
                    
                    # Save to disk if caching is enabled or SAVE_IMAGES is set
                    if cache_enabled or SAVE_IMAGES:
                        with open(file_path, "wb") as f:
                            f.write(screenshot_bytes)
                        if not cache_enabled:
                            log_msg += " (forced save)"
                    
                    logger.info(f"Generated in {int(execution_time)} ms")
                    
                    # Update metrics
                    render_count[request_ip] = ip_count
                    total_execution_time += execution_time

                    return Response(content=screenshot_bytes, media_type="image/jpeg")
                finally:
                    # Always close the page and context to free resources
                    await context.close()
            except Exception as e:
                error_msg = str(e)
                if ("Target page, context or browser has been closed" in error_msg or 
                    "Browser closed" in error_msg) and attempt == 0:
                    logger.warning(f"Browser error detected: {error_msg}. Restarting browser and retrying (attempt {attempt + 1})...")
                    await start_browser()
                    continue
                else:
                    raise e
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error rendering HTML: {error_msg}")
        html_file_path = os.path.join(output_dir, f"{req_hash}.html")
        if not os.path.exists(html_file_path):
            try:
                with open(html_file_path, "w", encoding="utf-8") as f:
                    f.write(request.html)
                logger.info(f"Saved failed HTML to {html_file_path}")
            except Exception as save_error:
                logger.error(f"Failed to save failed HTML: {save_error}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.get(
    "/status",
    summary="Get service status",
    description="Returns version, service start time, render count, and average render time (ms)."
)
async def get_status():
    total_renders = sum(render_count.values())
    status = {
        "version": app.version,
        "start_time": int(START_TIME),
        "render_count": total_renders,
        "render_avg": int(total_execution_time / total_renders) if total_renders > 0 else 0
    }
    return status

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
