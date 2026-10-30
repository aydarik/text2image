from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright
import uvicorn
import time
import random
import logging
import hashlib
import json
import os
import re
import math

from contextlib import asynccontextmanager
import asyncio
import cache_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)-7s %(asctime)s %(message)s')
logger = logging.getLogger(__name__)

START_TIME = time.time()
render_count = {}  # Maps IP address to count
rate_buckets = {}  # Maps IP address to [tokens, last_refill_monotonic]
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
        browser_instance = await playwright_instance.chromium.launch(args=CHROMIUM_ARGS)

async def stop_browser():
    global playwright_instance, browser_instance
    logger.info("Stopping browser...")
    if browser_instance:
        try:
            await browser_instance.close()
        except Exception:
            pass
        browser_instance = None
    if playwright_instance:
        try:
            await playwright_instance.stop()
        except Exception:
            pass
        playwright_instance = None

# Environment variables
SAVE_IMAGES = os.getenv("SAVE_IMAGES", "false").lower() == "true"
# Token bucket per IP: one token is refilled every RATE_LIMIT_SECONDS, up to RATE_LIMIT_BURST tokens.
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", "0"))
RATE_LIMIT_BURST = max(1, int(os.getenv("RATE_LIMIT_BURST", "1")))
# Jitter spreads out bursts of renders that arrive at the start of each minute (e.g. cron-driven clients).
JITTER_WINDOW_SECONDS = float(os.getenv("JITTER_WINDOW_SECONDS", "5"))
JITTER_MAX_SECONDS = float(os.getenv("JITTER_MAX_SECONDS", "5"))
BUCKET_PRUNE_THRESHOLD = 1000
IP_BLACKLIST = set(filter(None, [ip.strip() for ip in os.getenv("IP_BLACKLIST", "").split(",")]))

# Extra Chromium flags. /dev/shm is only 64MB in Docker by default, which makes Chromium crash on heavy pages.
# Playwright already disables the sandbox and GPU in headless mode, so those flags are not repeated here.
CHROMIUM_ARGS = ["--disable-dev-shm-usage"] + os.getenv("CHROMIUM_EXTRA_ARGS", "").split()

# Locks for shared mutable state
metrics_lock = asyncio.Lock()

@asynccontextmanager
async def lifespan(_app: FastAPI):
    await start_browser()
    yield
    await stop_browser()

app = FastAPI(
    title="HTML to JPG API",
    description="An API to render HTML content as a JPG image using Playwright.",
    version="1.3.13",
    lifespan=lifespan
)

def sanitize_ip(value: str) -> str:
    """Make the client IP safe to use as a directory name (prevents path traversal via spoofed headers)."""
    cleaned = re.sub(r"[^0-9A-Za-z.:_-]", "_", value or "")[:64].strip(".")
    return cleaned or "unknown"

@app.middleware("http")
async def ip_check_middleware(request: Request, call_next):
    request_ip = (
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    request.state.ip = sanitize_ip(request_ip)
    request_ip = request.state.ip
    
    if request_ip in IP_BLACKLIST:
        return Response(content="Forbidden", status_code=403)
    
    response = await call_next(request)
    return response

# Mount images directory for static access
os.makedirs("images", exist_ok=True)
app.mount("/images_static", StaticFiles(directory="images", html=True), name="images_static")

# Include cache management router
app.include_router(cache_manager.router)

def consume_rate_token(ip: str) -> float:
    """Take a token for this IP. Returns 0 if allowed, otherwise seconds until a token is available.

    No awaits inside, so it is atomic within the event loop (no lock needed).
    """
    if RATE_LIMIT_SECONDS <= 0:
        return 0.0
    now = time.monotonic()

    # Drop buckets that have fully refilled; they are equivalent to a fresh bucket
    if len(rate_buckets) > BUCKET_PRUNE_THRESHOLD:
        full_after = RATE_LIMIT_SECONDS * RATE_LIMIT_BURST
        for key in [k for k, (_, ts) in rate_buckets.items() if now - ts >= full_after]:
            del rate_buckets[key]

    tokens, last = rate_buckets.get(ip, (float(RATE_LIMIT_BURST), now))
    tokens = min(float(RATE_LIMIT_BURST), tokens + (now - last) / RATE_LIMIT_SECONDS)
    if tokens < 1.0:
        rate_buckets[ip] = (tokens, now)
        return (1.0 - tokens) * RATE_LIMIT_SECONDS
    rate_buckets[ip] = (tokens - 1.0, now)
    return 0.0

async def apply_jitter(ip: str) -> None:
    """Randomly delay renders arriving near the start of a minute to avoid thundering-herd spikes."""
    if JITTER_MAX_SECONDS > 0 and time.time() % 60 < JITTER_WINDOW_SECONDS:
        jitter = random.uniform(0, JITTER_MAX_SECONDS)
        logger.info(f"Applying {jitter:.2f}s jitter for request from {ip}")
        await asyncio.sleep(jitter)

def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def _write_bytes(directory: str, path: str, data: bytes) -> None:
    os.makedirs(directory, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)  # atomic: concurrent readers never see partial files

class RenderRequest(BaseModel):
    html: str
    width: int = Field(240, ge=1, le=4096)
    height: int = Field(240, ge=1, le=4096)
    cache: bool = True

@app.post(
    "/render",
    summary="Render HTML to JPG",
    description="Accepts an HTML string and dimensions, renders it in a headless browser, and returns the screenshot as a JPEG image.",
    responses={
        201: {
            "content": {"image/jpeg": {}},
            "description": "Rendered JPG image."
        },
        203: {
            "content": {"image/jpeg": {}},
            "description": "Cached JPG image."
        },
        403: {
            "description": "Forbidden."
        },
        429: {
            "description": "Too Many Requests."
        },
        500: {
            "description": "Internal Server Error."
        }
    }
)
async def render_html(request: RenderRequest, req: Request):
    global render_count, total_execution_time
    
    request_ip = req.state.ip

    # Calculate hash of the request for caching
    req_dict = request.model_dump()
    req_str = json.dumps(req_dict, sort_keys=True)
    req_hash = hashlib.sha256(req_str.encode("utf-8")).hexdigest()

    # Define output directory based on IP
    output_dir = os.path.join("images", request_ip)
    filename = f"{req_hash}.jpg"
    file_path = os.path.join(output_dir, filename)

    cache_enabled = request.cache

    # Check if file exists in cache
    if (cache_enabled or SAVE_IMAGES) and os.path.exists(file_path):
        cached_bytes = await asyncio.to_thread(_read_bytes, file_path)
        logger.info(f"Returning cached image to {request_ip}: {req_hash}")
        return Response(content=cached_bytes, media_type="image/jpeg", status_code=203)

    # Only real renders count against the rate limit (cache hits are cheap and free)
    retry_after = consume_rate_token(request_ip)
    if retry_after > 0:
        wait = max(1, math.ceil(retry_after))
        raise HTTPException(
            status_code=429,
            detail=f"Too Many Requests. Limit is 1 render per {RATE_LIMIT_SECONDS:g}s "
                   f"(burst {RATE_LIMIT_BURST}). Retry in {wait}s.",
            headers={"Retry-After": str(wait)}
        )

    await apply_jitter(request_ip)

    start_render = time.time()

    try:
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
                        await asyncio.to_thread(_write_bytes, output_dir, file_path, screenshot_bytes)

                    # Update metrics atomically
                    async with metrics_lock:
                        render_count_val = render_count.get(request_ip, 0) + 1
                        render_count[request_ip] = render_count_val
                        total_execution_time += execution_time
                        logger.info(f"Image {render_count_val} generated in {execution_time:.2f}ms (cache: {cache_enabled}) for {request_ip}: {req_hash}")

                    return Response(content=screenshot_bytes, media_type="image/jpeg", status_code=201)
                finally:
                    # Always close the page and context to free resources
                    await context.close()
            except Exception as e:
                error_msg = str(e)
                is_browser_crash = (
                    "Target page, context or browser has been closed" in error_msg
                    or "Browser closed" in error_msg
                )
                if is_browser_crash and attempt == 0:
                    logger.warning(f"Browser crash detected: {error_msg}. Restarting and retrying...")
                    await start_browser()
                    continue
                raise
    except HTTPException as e:
        error_msg = str(e)
        logger.error(f"HTTP exception for {request_ip}: {error_msg}")
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error rendering for {request_ip}: {error_msg}")
        # Save the failing HTML for post-mortem debugging
        os.makedirs(output_dir, exist_ok=True)
        html_file_path = os.path.join(output_dir, f"{req_hash}.html")
        if not os.path.exists(html_file_path):
            try:
                with open(html_file_path, "w", encoding="utf-8") as f:
                    f.write(request.html)
                logger.info(f"Saved failed HTML: {html_file_path}")
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
