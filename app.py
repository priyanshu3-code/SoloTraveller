import os
import sqlite3
import httpx
import json
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
import time

# Load environment variables from .env file
load_dotenv()

# Initialize geocoder (Nominatim - free, no API key required)
geocoder = Nominatim(user_agent="solotraveller_scam_radar")

# --- CONFIGURATION ---
# IMPORTANT: Add your Hugging Face API token here.
# You can get a token from https://huggingface.co/settings/tokens
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "YOUR_HUGGINGFACE_API_TOKEN_HERE")
HF_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"

# Verify token is set
if HF_API_TOKEN == "YOUR_HUGGINGFACE_API_TOKEN_HERE":
    print("[WARNING] HF_API_TOKEN not set! Get one from: https://huggingface.co/settings/tokens")
else:
    print(f"[OK] HF_API_TOKEN loaded: {HF_API_TOKEN[:10]}...")

DB_FILE = "traveler_log.db"

# --- FLASK APP SETUP ---
app = Flask(__name__)

# --- DATABASE INITIALIZATION ---
def init_db():
    """Initializes the SQLite database and creates the 'logs' table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_input TEXT NOT NULL,
            raw_llm_responses TEXT
        )
    """)
    conn.commit()
    conn.close()

def extract_location(text):
    """
    Extract location from text using Nominatim API (OpenStreetMap).
    Falls back to keyword matching if API call fails.
    """
    text_lower = text.lower()

    # List of common city/location keywords to search for
    common_locations = [
        'dehradun', 'delhi', 'new delhi', 'mumbai', 'bangalore',
        'jaipur', 'agra', 'goa', 'rajasthan',
        'bangkok', 'phuket', 'chiang mai', 'krabi',
        'bali', 'jakarta',
        'paris', 'london', 'barcelona', 'amsterdam', 'tokyo', 'sydney'
    ]

    # Find potential locations mentioned in text
    for location in common_locations:
        if location in text_lower:
            try:
                # Use Nominatim API to validate and get proper location name
                print(f"[DEBUG] Looking up location: {location}")
                result = geocoder.geocode(location, timeout=5)

                if result:
                    # Extract city/country from the result
                    address_parts = result.address.split(', ')

                    # Try to get city name (usually first or second part)
                    city_name = location.title()

                    # Better extraction: look for city in the address
                    if len(address_parts) > 0:
                        # For most cases, the city is in the first parts
                        # Try to find the most relevant part
                        for part in address_parts:
                            if part.lower() == location.lower():
                                city_name = part
                                break
                            elif location.lower() in part.lower():
                                city_name = part.split(',')[0].strip()
                                break

                    print(f"[DEBUG] Found location via API: {city_name}")
                    return city_name

                else:
                    print(f"[DEBUG] API returned no results for: {location}")

            except Exception as e:
                print(f"[DEBUG] API error for {location}: {e}")
                # Fall back to keyword matching if API fails
                continue

            # If API succeeded but let's also try the next location
            time.sleep(0.5)  # Rate limiting for API

    # Fallback: Simple keyword matching if no API results
    print("[DEBUG] Falling back to keyword matching")
    cities_db = {
        'dehradun': 'Dehradun', 'delhi': 'Delhi', 'new delhi': 'New Delhi',
        'mumbai': 'Mumbai', 'bangalore': 'Bangalore', 'jaipur': 'Jaipur',
        'agra': 'Agra', 'goa': 'Goa', 'rajasthan': 'Rajasthan',
        'bangkok': 'Bangkok', 'phuket': 'Phuket', 'chiang mai': 'Chiang Mai',
        'krabi': 'Krabi', 'bali': 'Bali', 'jakarta': 'Jakarta',
        'paris': 'Paris', 'london': 'London', 'barcelona': 'Barcelona',
        'amsterdam': 'Amsterdam', 'tokyo': 'Tokyo', 'sydney': 'Sydney',
    }

    for city, proper_name in sorted(cities_db.items(), key=lambda x: len(x[0]), reverse=True):
        if city in text_lower:
            return proper_name

    return 'Unknown'

def generate_fallback_response(prompt_type, situation, location, risk_level=None):
    """Generate smart responses based on keywords when network is unavailable."""

    if prompt_type == "analysis":
        situation_lower = situation.lower()

        # VERY STRICT Low risk indicators - require MULTIPLE legitimacy signals
        low_risk_keywords = [
            'booked', 'booking', 'reservation',  # Booked through platform
            'official', 'licensed', 'registered', 'verified',  # Official
            'tripadvisor', 'airbnb', 'booking.com', 'getyourguide',  # Trusted platforms
            '4.8', '4.9', '5.0', 'reviews', '50 reviews', '100 reviews', '200 reviews',  # Good reviews
            'hostel organized', 'hotel arranged', 'concierge',  # Official venue
            'organized by', 'arranged by', 'booking through',  # Proper organization
            'other guests', 'other travelers', 'group tour', 'fellow travelers',  # Others present
        ]

        # AGGRESSIVE High risk indicators - catch scams early
        high_risk_keywords = [
            # Unsolicited approaches (auto-flag as HIGH)
            'stranger', 'approached me', 'man approached', 'woman approached',
            'random person', 'randomly', 'offered me', 'approached',

            # Price anomalies
            '1000rs', '500rs', 'cash only', 'cash payment', 'cash deal',
            'pay cash', 'cash today', '10x price', '5x price', '100x',
            'too good to be true', 'unbelievable price', 'suspiciously cheap',

            # Pressure tactics
            'pushy', 'pressure', 'urgent', 'today only', 'today', 'limited',
            'must buy', 'must pay', 'no choice', 'hurry', 'rush', 'now',
            'only today', 'last chance', 'only few left',

            # Fake/counterfeit goods
            'fake', 'copy', 'counterfeit', 'replica',
            'rolex', 'watch', '$20', 'gem', 'diamond', 'jewelry',

            # Questionable person/behavior
            'unsolicited', 'suspicious', 'scam', 'sketchy', 'fishy',
            'seemed off', 'didnt feel right', 'uncomfortable',

            # Future promises (classic scam)
            'deliver tomorrow', 'deliver later', 'will deliver', 'next day delivery',
            'future delivery', 'will send',
        ]

        # Count matches for better accuracy
        low_risk_count = sum(1 for keyword in low_risk_keywords if keyword in situation_lower)
        high_risk_count = sum(1 for keyword in high_risk_keywords if keyword in situation_lower)

        # SAFETY-FIRST DECISION LOGIC (Default to HIGH risk)
        # Only mark as LOW if we see MULTIPLE strong legitimacy signals
        if low_risk_count >= 3 and high_risk_count == 0:
            # Only LOW if strong legitimacy AND no red flags at all
            scam_prob = 'Low'
        elif high_risk_count >= 1:
            # HIGH risk for ANY red flag (conservative, safety-first)
            scam_prob = 'High'
        elif low_risk_count >= 2:
            # Multiple legitimacy signals but no high-risk keywords
            scam_prob = 'Low'
        else:
            # Default to HIGH risk when uncertain
            scam_prob = 'High'

        return json.dumps({"scam_probability": scam_prob, "location": location})

    elif prompt_type == "advice":
        if risk_level == 'High':
            return """1. Stop and do not hand over any money immediately.
2. Walk away from the situation and go to your hotel.
3. Go to the nearest tourist police station and report.
4. Document what happened and keep evidence.
5. Contact your embassy if threatened."""
        else:
            return """1. Verify the offer through official channels or reviews.
2. Check if the price is fair for the location and service.
3. Support the local business if it seems legitimate.
4. Enjoy the experience and be respectful.
5. Connect authentically with locals."""

    elif prompt_type == "summary":
        if risk_level == 'High':
            return """✓ Recognize: This is a high-risk situation with multiple scam indicators.
✓ Decide: Do not pay and walk away immediately.
✓ Act: Go to your hotel or tourist police and report the incident."""
        else:
            return """✓ Recognize: This appears to be a legitimate opportunity.
✓ Decide: Proceed with caution after verification.
✓ Act: Enjoy the experience and support the local community."""

# Track network errors globally
network_error_detected = [False]

# --- HUGGING FACE API HELPER ---
def call_llm(prompt, retries=2):
    """
    Calls the Hugging Face Inference API with a given prompt.

    Args:
        prompt (str): The prompt to send to the model.
        retries (int): Number of times to retry on failure.

    Returns:
        str: The generated text from the model, or fallback response.
    """
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {"inputs": prompt, "options": {"wait_for_model": True}}

    for attempt in range(retries):
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(HF_API_URL, headers=headers, json=payload)
                response.raise_for_status()
                network_error_detected[0] = False
                return response.json()[0]['generated_text']
        except Exception as e:
            error_str = str(e).lower()
            is_network_error = any(x in error_str for x in ['errno 11001', 'getaddrinfo', 'host is unknown',
                                                             'connection refused', 'network unreachable'])

            print(f"[Attempt {attempt + 1}] Error: {type(e).__name__}: {e}")

            if is_network_error:
                network_error_detected[0] = True

            if attempt + 1 == retries:
                if network_error_detected[0]:
                    print("[INFO] Network error detected - using fallback responses")
                return f"Error: LLM call failed after {retries} attempts. Details: {e}"

# --- FLASK ROUTES ---
@app.route('/')
def index():
    """Renders the main HTML page."""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_input():
    """
    Processes user input through a 3-step LLM chain.
    1. Analyzes for scam probability and location.
    2. Provides advice based on the probability (escape vs. cultural tips).
    3. Creates a final summary checklist.
    """
    data = request.get_json()
    user_input = data.get('user_input')
    if not user_input:
        return jsonify({"error": "No user input provided."}), 400
    
    all_raw_responses = {}

    # 1. First LLM Call: Analyze scam probability and location with detailed analysis
    prompt1 = f"""You are a HIGHLY CAUTIOUS expert in detecting travel scams targeting solo travelers. Your job is to protect travelers from financial loss.

CRITICAL RED FLAGS - BE VERY STRICT:
1. Unsolicited approach by stranger (HIGH RISK by default)
2. Price is 50%+ higher than normal market rate in that region (SCAM indicator)
3. Price is extremely low (too good to be true) - SCAM indicator
4. Pressure to pay immediately/urgently (SCAM tactic)
5. Cash-only payment demanded (SCAM indicator)
6. Promises of future delivery (SCAM indicator)
7. Operating outside official channels (tourist trap indicator)
8. Excessive friendliness with strangers (SCAM manipulation)
9. Vague promises or guaranteed returns (SCAM language)
10. Demanding upfront payment (SCAM tactic)
11. Limited time offers "today only" (SCAM pressure tactic)
12. Unsolicited "special deals" or "exclusive access" (SCAM language)

TOURIST TRAP LOCATIONS & PRICES:
- Street vendors at tourist hotspots: Often 5-10x normal prices
- Hilltop/rooftop vendors: Often 5-20x normal prices
- Unsolicited shop owners: Often overpriced 50-300%
- Gem shops approached by strangers: Classic scam (80%+ scam rate)
- Taxi/transport offered by strangers: Often overpriced or scams

NORMAL MARKET PRICES (INDIA):
- Bottle of water: 10-30 Rs
- Regular soft drink: 30-60 Rs
- Coffee/chai: 20-50 Rs
- Restaurant meal: 100-300 Rs

SITUATION TO ANALYZE: '{user_input}'

DECISION LOGIC:
1. If price is abnormally high (3x+ normal) → HIGH RISK
2. If stranger approached you unsolicited → HIGH RISK by default (unless obviously legitimate)
3. If multiple red flags present (2+) → HIGH RISK
4. If legitimate business/official setup → LOW RISK

Respond with ONLY a JSON object (no markdown, no explanation):
{{"scam_probability": "High", "location": "detected city or Unknown"}}
OR
{{"scam_probability": "Low", "location": "detected city or Unknown"}}

WARNING: Err on the side of caution. Tourist areas have 60-80% scam probability for unsolicited offers."""
    raw_response1 = call_llm(prompt1)

    # Extract location from user input FIRST (works for both API and fallback)
    detected_location = extract_location(user_input)

    # Check if API call failed (error message returned)
    if raw_response1.startswith("Error:"):
        print(f"[Network Error] {raw_response1}")
        network_error_detected[0] = True
        # Use fallback for analysis with detected location
        analysis_result_json = generate_fallback_response("analysis", user_input, detected_location)
        analysis_result = json.loads(analysis_result_json)
    else:
        # Extract the JSON part from the response
        try:
            # The model often returns the prompt plus the JSON. We find the JSON.
            json_start = raw_response1.find('{')
            json_end = raw_response1.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")

            json_str = raw_response1[json_start:json_end]
            analysis_result = json.loads(json_str)

            # Validate and clean the response - be strict about high/low
            scam_prob = str(analysis_result.get('scam_probability', 'Low')).strip().lower()

            if 'high' in scam_prob or 'yes' in scam_prob or 'probable' in scam_prob:
                scam_prob = 'High'
            elif 'low' in scam_prob or 'no' in scam_prob or 'safe' in scam_prob:
                scam_prob = 'Low'
            else:
                # Default to High if unclear (err on side of caution)
                scam_prob = 'High'

            analysis_result['scam_probability'] = scam_prob

            # Extract location from both API response and user input
            location_from_api = analysis_result.get('location', 'Unknown').strip()

            # If API returned 'Unknown', use our extraction
            if location_from_api.lower() == 'unknown':
                analysis_result['location'] = detected_location
            else:
                analysis_result['location'] = location_from_api

        except (json.JSONDecodeError, IndexError, ValueError) as e:
            print(f"[ERROR] Parse error on analysis: {e}")
            print(f"[DEBUG] Raw response: {raw_response1[:500]}")
            # Use fallback with detected location
            analysis_result_json = generate_fallback_response("analysis", user_input, detected_location)
            analysis_result = json.loads(analysis_result_json)
    
    all_raw_responses['analysis'] = raw_response1
    scam_probability = analysis_result.get('scam_probability', 'Low')
    location = analysis_result.get('location', 'an unknown location')

    # 2. Second LLM Call: Conditional advice with practical guidance
    if scam_probability == 'High':
        prompt2 = f"""⚠️ EMERGENCY SCAM SITUATION - Solo traveler in {location} needs IMMEDIATE action!

SITUATION: '{user_input}'

This appears to be a scam. Provide 5 URGENT action steps to:
1. IMMEDIATELY STOP and DO NOT pay
2. Remove yourself from the situation RIGHT NOW
3. Go to a safe location (hotel, police, official shop)
4. Document what happened (screenshots, details)
5. Report to authorities if threatened

Use SHORT, URGENT sentences. Each step is 1-2 sentences max. This is an EMERGENCY.

Example format:
1. Stop right now. Do not hand over any money.
2. Walk away immediately. Go to your hotel/police station.
3. Take photos/notes of the person/offer for evidence.
4. Contact local tourist police with details.
5. Tell your hotel staff what happened."""
    else:
        prompt2 = f"""A solo traveler in {location} has found a LEGITIMATE opportunity.

SITUATION: '{user_input}'

Provide 5 practical tips to enhance the experience:
1. Verify it's legitimate (check reviews, official channels, other travelers)
2. Negotiate fairly if price seems high
3. Support the local business/person ethically
4. Enjoy and document the authentic experience
5. Connect genuinely with the person/community

Use respectful, encouraging tone. Each tip is 1-2 sentences."""

    advice_result = call_llm(prompt2)

    # Use fallback if network error detected
    if network_error_detected[0] and "Error:" in advice_result:
        print(f"[Fallback] Using smart fallback for advice")
        advice_text = generate_fallback_response("advice", user_input, location, scam_probability)
    else:
        # Clean up the response by removing the echoed prompt part
        advice_text = advice_result.split(prompt2)[-1].strip() if prompt2 in advice_result else advice_result

        # Further cleanup - remove common LLM artifacts
        advice_text = advice_text.replace("```", "").replace("json", "").replace("\\n", "\n").strip()
        advice_text = advice_text.replace("python", "").replace("bash", "").replace("markdown", "")
        # Remove leading/trailing quotes if present
        if advice_text.startswith('"') and advice_text.endswith('"'):
            advice_text = advice_text[1:-1]

    if not advice_text:
        advice_text = "Unable to generate advice at this time. Trust your instincts - if something feels wrong, it probably is."

    all_raw_responses['advice'] = advice_result
    
    # 3. Third LLM Call: Final summary checklist
    if scam_probability == 'High':
        prompt3 = f"""Create a CRITICAL 3-point action checklist for this SCAM situation.

CONTEXT:
- Risk Level: {scam_probability} (DANGEROUS)
- Location: {location}
- Situation: '{user_input}'

Create exactly 3 action points using this format:
✓ RECOGNIZE: [One sentence identifying the scam pattern]
✓ DECIDE: [One sentence decision - must include "walk away" or "do not pay"]
✓ ACT: [One sentence specific action - where to go, who to tell]

Make it SHORT, CLEAR, URGENT. Each line = 1 sentence max.
Example:
✓ Recognize: This is a classic tourist overpricing scam.
✓ Decide: Refuse to pay and walk away immediately.
✓ Act: Go to your hotel and report to staff."""
    else:
        prompt3 = f"""Create a clear 3-point action checklist for this LEGITIMATE opportunity.

CONTEXT:
- Risk Level: {scam_probability} (SAFE)
- Location: {location}
- Situation: '{user_input}'

Create exactly 3 action points using this format:
✓ RECOGNIZE: [One sentence identifying the legitimate aspect]
✓ DECIDE: [One sentence decision - what you'll do]
✓ ACT: [One sentence specific action - what to do next]

Make it SHORT, CLEAR, ENCOURAGING. Each line = 1 sentence max.
Example:
✓ Recognize: This is a genuine local experience with good reviews.
✓ Decide: Book it and enjoy the authentic experience.
✓ Act: Confirm details with the venue and enjoy your visit."""
    summary_result = call_llm(prompt3)

    # Use fallback if network error detected
    if network_error_detected[0] and "Error:" in summary_result:
        print(f"[Fallback] Using smart fallback for summary")
        summary_text = generate_fallback_response("summary", user_input, location, scam_probability)
    else:
        # Clean up the response
        summary_text = summary_result.split(prompt3)[-1].strip() if prompt3 in summary_result else summary_result

        # Further cleanup
        summary_text = summary_text.replace("```", "").replace("json", "").replace("\\n", "\n").strip()
        summary_text = summary_text.replace("python", "").replace("bash", "").replace("markdown", "")
        # Remove leading/trailing quotes if present
        if summary_text.startswith('"') and summary_text.endswith('"'):
            summary_text = summary_text[1:-1]

    if not summary_text:
        summary_text = "✓ Recognize: Something didn't feel right about this offer.\n✓ Decide: Trust your gut feeling.\n✓ Act: When in doubt, walk away and consult locals or your hotel staff."

    all_raw_responses['summary'] = summary_result

    # Log to database
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO logs (user_input, raw_llm_responses) VALUES (?, ?)",
                       (user_input, json.dumps(all_raw_responses)))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

    # Return final JSON to frontend
    return jsonify({
        "analysis": analysis_result,
        "advice": advice_text,
        "summary": summary_text
    })

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    init_db()
    # Note: In a real production environment, use a proper WSGI server like Gunicorn or Waitress
    # instead of app.run(). The host '0.0.0.0' makes it accessible on your local network.
    app.run(host='0.0.0.0', port=5000, debug=True)
