from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
import os
import datetime
import time
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBasic()
templates = Jinja2Templates(directory="templates")


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
                "date": datetime.datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S")
            })

    # Sort by creation date DESC
    files.sort(key=lambda x: x["ctime"], reverse=True)

    # Pagination
    PAGE_SIZE = 300
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    paginated_files = files[start:end]
    has_more = len(files) > end

    return templates.TemplateResponse(
        "cache_manager.html",
        {
            "request": request,
            "images": paginated_files,
            "page": page,
            "has_more": has_more
        }
    )


@router.post("/cache/clear")
async def clear_cache(auth: bool = Depends(check_auth)):
    output_dir = "images"

    if not os.path.exists(output_dir):
        return RedirectResponse(url="/cache", status_code=303)

    for f in os.listdir(output_dir):
        if f.endswith(".jpg"):
            path = os.path.join(output_dir, f)
            try:
                os.remove(path)
                logger.info(f"Deleted from cache: {f}")
            except Exception as e:
                logger.error(f"Error deleting {f}: {e}")

    return RedirectResponse(url="/cache", status_code=303)
