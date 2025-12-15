# Text2Image (GeekMagic HTML renderer)

This project provides a simple API to render HTML content into JPG images. It is primarily designed to work with the **[GeekMagic Home Assistant Integration](https://github.com/aydarik/hass-geekmagic)** to verify and generate layouts for GeekMagic.

## Features

-   **HTML to JPG Rendering**: Renders generic HTML/CSS into a 240x240 (default) JPG image.
-   **Playwright Backend**: Uses a headless Chromium browser for accurate rendering.
-   **FastAPI**: Built with FastAPI for high performance.
-   **Caching**: Caches generated images based on request content to speed up subsequent requests.

## Home Assistant Add-on

This project can be installed as a Home Assistant Add-on.

[![Add to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Faydarik%2Ftext2image)

### Installation

1.  Add the repository URL to your Home Assistant Add-on Store repositories:
    `https://github.com/aydarik/text2image`
2.  Install the "GeekMagic Text2Image" add-on.
3.  Start the add-on.

### Configuration

The add-on runs on port `8000` by default. No additional configuration is usually required.

## Docker Usage

You can also run this service standalone using Docker.

### Docker Compose

```yaml
services:
  text2image:
    image: ghcr.io/aydarik/text2image:${ARCH:-amd64}
    container_name: text2image
    ports:
      - "8000:8000"
```

### Manual Run

```bash
docker build -t text2image .
docker run -p 8000:8000 text2image
```

## API Usage

### Endpoint: `/render` [POST]

**Body:**

```json
{
  "html": "<div style='background: red; width: 100%; height: 100%; color: white;'>Hello World</div>",
  "width": 240,
  "height": 240
}
```

**Response:** Returns a `image/jpeg` file.
