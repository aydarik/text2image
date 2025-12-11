from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import async_playwright
import uvicorn
import io

app = FastAPI(
    title="HTML to JPG API",
    description="An API to render HTML content as a JPG image using Playwright.",
    version="1.0.0"
)

class RenderRequest(BaseModel):
    html: str
    width: int = 240
    height: int = 240

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
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": request.width, "height": request.height})
            await page.set_content(request.html)
            screenshot_bytes = await page.screenshot(type="jpeg")
            await browser.close()
            
            # Save to disk if flag is enabled
            import uuid
            import os
            
            if os.getenv("SAVE_IMAGES_TO_DISK", "false").lower() == "true":
                output_dir = "/images"
                os.makedirs(output_dir, exist_ok=True)
                
                filename = f"{uuid.uuid4()}.jpg"
                file_path = os.path.join(output_dir, filename)
                
                with open(file_path, "wb") as f:
                    f.write(screenshot_bytes)
            
            from fastapi.responses import Response
            return Response(content=screenshot_bytes, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
