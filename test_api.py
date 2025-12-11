import requests
import sys

def test_render():
    html = """
    <html>
        <body style='background-color: #f0f0f0; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;'>
            <div style='background-color: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center;'>
                <h1 style='color: #333; font-family: sans-serif;'>Hello from API!</h1>
                <p style='color: #666; font-family: sans-serif;'>Rendered via Playwright</p>
                <div style='width: 100px; height: 100px; background: linear-gradient(45deg, #ff6b6b, #4ecdc4); margin: 20px auto; border-radius: 50%;'></div>
            </div>
        </body>
    </html>
    """
    
    url = "http://localhost:8000/render"
    payload = {
        "html": html,
        "width": 800,
        "height": 600
    }
    
    print(f"Sending request to {url}...")
    try:
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            with open("output.jpg", "wb") as f:
                f.write(response.content)
            print("Success! output.jpg created.")
        else:
            print(f"Failed. Status: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Make sure the server is running (either locally or via docker).")

if __name__ == "__main__":
    test_render()
