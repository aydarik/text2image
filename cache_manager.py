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
async def get_cache_manager(request: Request, page: int = 1, ip: str = None, ajax: bool = False,
                            auth: bool = Depends(check_auth)):
    output_dir = "images"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    all_ips = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]

    # Calculate total count for the manager page
    total_count = 0
    if not ajax:
        search_dirs = [os.path.join(output_dir, ip)] if ip and ip != "all" \
            else [os.path.join(output_dir, d) for d in all_ips]
        for d in search_dirs:
            if os.path.exists(d):
                total_count += len([f for f in os.listdir(d) if f.endswith(".jpg")])

    if not ajax:
        return templates.TemplateResponse(
            "cache_manager.html",
            {
                "request": request,
                "all_ips": sorted(all_ips),
                "current_ip": ip or "all",
                "total_count": total_count
            }
        )

    files = []
    search_dirs = [os.path.join(output_dir, ip)] if ip and ip != "all" \
        else [os.path.join(output_dir, d) for d in all_ips]

    for d in search_dirs:
        if not os.path.exists(d):
            continue
        ip_name = os.path.basename(d)
        for f in os.listdir(d):
            if f.endswith(".jpg"):
                path = os.path.join(d, f)
                ctime = os.path.getctime(path)
                files.append({
                    "name": f,
                    "ip": ip_name,
                    "ctime": ctime,
                    "date": datetime.datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S")
                })

    # Sort by creation date DESC
    files.sort(key=lambda x: x["ctime"], reverse=True)

    # Pagination
    PAGE_SIZE = 60
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    paginated_files = files[start:end]
    has_more = len(files) > end

    return templates.TemplateResponse(
        "cache_manager_grid.html",
        {
            "request": request,
            "images": paginated_files,
            "page": page,
            "has_more": has_more,
            "current_ip": ip or "all"
        }
    )


@router.post("/cache/clear")
async def clear_cache(ip: str = "all", auth: bool = Depends(check_auth)):
    output_dir = "images"

    if not os.path.exists(output_dir):
        return RedirectResponse(url="/cache", status_code=303)

    search_dirs = [os.path.join(output_dir, ip)] if ip != "all" \
        else [os.path.join(output_dir, d) for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]

    for d in search_dirs:
        if not os.path.exists(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".jpg"):
                path = os.path.join(d, f)
                try:
                    os.remove(path)
                except Exception as e:
                    logger.error(f"Error deleting {f} in {d}: {e}")

    return RedirectResponse(url=f"/cache?ip={ip}", status_code=303)
