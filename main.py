from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import async_playwright
import uvicorn
import io
import time
import logging

from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)-7s %(asctime)s %(message)s')
logger = logging.getLogger(__name__)

START_TIME = time.time()
render_count = 0
total_execution_time = 0.0

# Global playwright and browser objects
playwright_instance = None
browser_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global playwright_instance, browser_instance
    logger.info("Starting browser...")
    playwright_instance = await async_playwright().start()
    browser_instance = await playwright_instance.chromium.launch()
    yield
    logger.info("Stopping browser...")
    await browser_instance.close()
    await playwright_instance.stop()

app = FastAPI(
    title="HTML to JPG API",
    description="An API to render HTML content as a JPG image using Playwright.",
    version="1.2.1",
    lifespan=lifespan
)

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
async def render_html(request: RenderRequest):
    global render_count, total_execution_time
    start_render = time.time()
    try:
        # Calculate hash of the request
        import hashlib
        import json
        
        req_dict = request.dict()
        # Sort keys to ensure consistent order for hashing
        req_str = json.dumps(req_dict, sort_keys=True)
        req_hash = hashlib.sha256(req_str.encode("utf-8")).hexdigest()
        
        output_dir = "images"
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # Check if caching is enabled (enabled by default)
        cache_enabled = request.cache
        
        filename = f"{req_hash}.jpg"
        file_path = os.path.join(output_dir, filename)
        
        from fastapi.responses import Response

        # Check if file exists in cache
        if cache_enabled and os.path.exists(file_path):
            logger.info(f"Cache hit: {req_hash}")
            with open(file_path, "rb") as f:
                cached_bytes = f.read()
            return Response(content=cached_bytes, media_type="image/jpeg")

        if not browser_instance:
            raise HTTPException(status_code=500, detail="Browser not initialized")

        # Create a new context and page for each request to ensure thread safety (isolation)
        context = await browser_instance.new_context(viewport={"width": request.width, "height": request.height})
        page = await context.new_page()
        try:
            await page.set_content(request.html)

            if ("window.renderReady" in request.html):
                # Wait until widget JS finished rendering
                await page.wait_for_function(
                    "window.renderReady === true",
                    timeout=5000
                )

            screenshot_bytes = await page.screenshot(type="jpeg", quality=90)
            
            # Save to disk if caching is enabled
            if cache_enabled:
                with open(file_path, "wb") as f:
                    f.write(screenshot_bytes)
            
            execution_time = (time.time() - start_render) * 1000
            log_msg = f"Generated in {int(execution_time)} ms"
            if cache_enabled:
                log_msg += f": {req_hash}"
            logger.info(log_msg)
            
            # Update metrics
            render_count += 1
            total_execution_time += execution_time

            return Response(content=screenshot_bytes, media_type="image/jpeg")
        finally:
            # Always close the page and context to free resources
            await context.close()
    except Exception as e:
        logger.error(f"Error rendering HTML: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/status",
    summary="Get service status",
    description="Returns version, service start time, render count, and average render time (ms)."
)
async def get_status():
    status = {
        "version": app.version,
        "start_time": int(START_TIME),
        "render_count": render_count,
        "render_avg": int(total_execution_time / render_count) if render_count > 0 else 0
    }
    logger.info(f"Service status: {status}")
    return status

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
