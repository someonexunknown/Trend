import os
import time
import json
from flask import Flask, request, jsonify
from google import genai
from dotenv import load_dotenv
from pytrends.request import TrendReq

# Initialize Flask
app = Flask(__name__)

# 1. Load Environment Variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

def generate_inventory_trends(user_input):
    """Generates 10 trending products for store owners."""
    prompt = (
        "Act as a Retail Inventory Strategist and SEO expert. "
        "Based on the occasion provided, identify 10 trending products that a store owner "
        "should stock to maximize sales. "
        "CRITICAL RULES:\n"
        "1. Use ONLY high-volume, general search terms for physical products (e.g., 'Crop Top', 'Wide Leg Jeans').\n"
        "2. Do NOT use adjectives, brand names, or colors.\n"
        "3. Focus on items that indicate a shift in inventory trends.\n"
        "4. Use only 1-2 words per item. English alphabet only.\n"
        "5. Return ONLY a single comma-separated line with no extra text or formatting.\n\n"
        f"\n\nOccasion: {user_input.strip()}"
    )
    try:
        response = client.models.generate_content(
            model="gemma-3-1b-it",
            contents=prompt,
            config={"temperature": 0.1, "max_output_tokens": 100}
        )
        raw_text = response.text.strip().replace("*", "").replace("\n", "")
        return [k.strip() for k in raw_text.split(",") if k.strip()]
    except Exception:
        return []

def get_trends_data(keywords: list):
    """Fetches trend data with fixed compatibility for modern urllib3 versions."""
    if not keywords:
        return {"error": "No keywords provided"}

    batches = [keywords[i:i + 5] for i in range(0, len(keywords), 5)]
    
    # FIX: Initialize without 'backoff_factor' here to avoid the method_whitelist error.
    # We will handle the "politeness" and retries manually in our loop.
    pytrends = TrendReq(hl='en-IN', tz=330) 
    
    all_results = {}

    for i, batch in enumerate(batches):
        success = False
        retries = 0
        
        while not success and retries < 2:
            try:
                # Standard Google Trends request
                pytrends.build_payload(batch, timeframe='today 3-m', geo='IN')
                df = pytrends.interest_over_time()
                
                if not df.empty:
                    df = df.drop(columns=['isPartial'])
                    averages = df.mean().to_dict()
                    for name, score in averages.items():
                        all_results[name] = round(score, 2)
                
                success = True
                # Use a longer delay to prevent 429 errors
                time.sleep(12) 
                
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    # Cool down period if rate-limited
                    time.sleep(60)
                    retries += 1
                else:
                    # Handle other errors gracefully for the web output
                    all_results[f"error_batch_{i+1}"] = error_msg
                    break

    return {
        "results": all_results
    }

@app.route('/get_trends', methods=['POST'])
def api_endpoint():
    """Web endpoint for your website to call."""
    data = request.json
    occasion = data.get('occasion', 'general')
    
    keywords = generate_inventory_trends(occasion)
    results = get_trends_data(keywords)
    
    return jsonify({
        "results": results
    })

if __name__ == "__main__":
    # Render uses the PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
