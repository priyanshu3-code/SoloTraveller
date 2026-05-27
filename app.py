import os
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

# LLM 1: Mistral-7B for main analysis work
HF_API_URL_MISTRAL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"

# LLM 2: Llama-2-70b for judging/validating results
HF_API_URL_LLAMA = "https://api-inference.huggingface.co/models/meta-llama/Llama-2-70b-chat-hf"

# Verify token is set
if HF_API_TOKEN == "YOUR_HUGGINGFACE_API_TOKEN_HERE":
    print("[WARNING] HF_API_TOKEN not set! Get one from: https://huggingface.co/settings/tokens")
else:
    print(f"[OK] HF_API_TOKEN loaded: {HF_API_TOKEN[:10]}...")
    print(f"[OK] Using 2 LLMs: Mistral-7B (analysis) + Llama-2-70b (judge)")

# --- SIMILAR CASES DATABASE ---
_DELHI_CASES = [
    {'type': 'water_overpriced', 'count': 30, 'scam_rate': 0.98, 'avg_loss': 450},
    {'type': 'stranger_approached', 'count': 25, 'scam_rate': 0.96, 'avg_loss': 800},
    {'type': 'gem_shop', 'count': 18, 'scam_rate': 0.99, 'avg_loss': 2500},
    {'type': 'taxi_overpriced', 'count': 22, 'scam_rate': 0.92, 'avg_loss': 350},
    {'type': 'tour_markup', 'count': 15, 'scam_rate': 0.88, 'avg_loss': 600},
]

_LONDON_CASES = [
    {'type': 'street_vendor', 'count': 16, 'scam_rate': 0.85, 'avg_loss': 45},
    {'type': 'tourist_trap_restaurant', 'count': 12, 'scam_rate': 0.82, 'avg_loss': 80},
]

SIMILAR_CASES_DATA = {
    'delhi': _DELHI_CASES,
    'new delhi': _DELHI_CASES,
    'mumbai': [
        {'type': 'water_overpriced', 'count': 28, 'scam_rate': 0.97, 'avg_loss': 500},
        {'type': 'stranger_approached', 'count': 22, 'scam_rate': 0.95, 'avg_loss': 900},
        {'type': 'tour_pressure', 'count': 20, 'scam_rate': 0.91, 'avg_loss': 700},
        {'type': 'counterfeit_goods', 'count': 16, 'scam_rate': 0.94, 'avg_loss': 1800},
    ],
    'goa': [
        {'type': 'beach_vendor', 'count': 32, 'scam_rate': 0.93, 'avg_loss': 550},
        {'type': 'water_overpriced', 'count': 26, 'scam_rate': 0.96, 'avg_loss': 480},
        {'type': 'stranger_approached', 'count': 24, 'scam_rate': 0.94, 'avg_loss': 750},
    ],
    'bangalore': [
        {'type': 'taxi_overpriced', 'count': 20, 'scam_rate': 0.90, 'avg_loss': 300},
        {'type': 'tourist_trap_shop', 'count': 15, 'scam_rate': 0.89, 'avg_loss': 650},
    ],
    'bangkok': [
        {'type': 'tuk_tuk_scam', 'count': 40, 'scam_rate': 0.96, 'avg_loss': 400},
        {'type': 'gem_shop', 'count': 22, 'scam_rate': 0.97, 'avg_loss': 3000},
        {'type': 'tour_pressure', 'count': 28, 'scam_rate': 0.93, 'avg_loss': 850},
        {'type': 'street_vendor', 'count': 18, 'scam_rate': 0.88, 'avg_loss': 250},
    ],
    'phuket': [
        {'type': 'beach_vendor', 'count': 35, 'scam_rate': 0.94, 'avg_loss': 600},
        {'type': 'tour_overpriced', 'count': 24, 'scam_rate': 0.91, 'avg_loss': 950},
        {'type': 'fake_goods', 'count': 20, 'scam_rate': 0.95, 'avg_loss': 2200},
    ],
    'london': _LONDON_CASES,
    'greater london': _LONDON_CASES,
    'paris': [
        {'type': 'street_vendor', 'count': 14, 'scam_rate': 0.83, 'avg_loss': 35},
        {'type': 'tour_pressure', 'count': 10, 'scam_rate': 0.80, 'avg_loss': 120},
    ],
    'tokyo': [
        {'type': 'fake_shop', 'count': 8, 'scam_rate': 0.75, 'avg_loss': 5000},
        {'type': 'overpriced_restaurant', 'count': 12, 'scam_rate': 0.70, 'avg_loss': 3500},
    ],
    'bali': [
        {'type': 'beach_vendor', 'count': 30, 'scam_rate': 0.92, 'avg_loss': 300},
        {'type': 'tour_overpriced', 'count': 26, 'scam_rate': 0.90, 'avg_loss': 800},
        {'type': 'fake_goods', 'count': 18, 'scam_rate': 0.93, 'avg_loss': 1500},
    ],
    'sydney': [
        {'type': 'overpriced_shop', 'count': 10, 'scam_rate': 0.80, 'avg_loss': 60},
        {'type': 'tour_pressure', 'count': 8, 'scam_rate': 0.78, 'avg_loss': 150},
    ],
}

# --- FLASK APP SETUP ---
app = Flask(__name__)

def find_similar_cases(location, situation_text):
    """
    Find similar scam cases from database based on location and situation type.
    Returns statistics about similar cases reported by other travelers.
    """
    location_lower = location.lower()
    situation_lower = situation_text.lower()

    # Get cases for this location
    location_cases = SIMILAR_CASES_DATA.get(location_lower, [])

    if not location_cases:
        return None

    # Detect scam type from situation
    scam_type_keywords = {
        'water_overpriced': ['water', 'bottle', 'drink', 'overpriced', 'expensive'],
        'stranger_approached': ['stranger', 'approached', 'man approached', 'woman approached'],
        'gem_shop': ['gem', 'diamond', 'jewelry', 'ruby', 'sapphire'],
        'taxi_overpriced': ['taxi', 'auto', 'ride', 'transport', 'overpriced'],
        'tuk_tuk_scam': ['tuk tuk', 'tuk-tuk', 'three wheeler'],
        'tour_pressure': ['tour', 'pressure', 'today only', 'last chance', 'urgent'],
        'tour_overpriced': ['tour', 'trip', 'expensive', 'overpriced'],
        'beach_vendor': ['beach', 'vendor', 'street vendor'],
        'street_vendor': ['street', 'vendor', 'street vendor'],
        'counterfeit_goods': ['fake', 'counterfeit', 'replica', 'copy'],
        'fake_goods': ['fake', 'counterfeit', 'replica'],
        'tourist_trap': ['tourist', 'trap', 'shop', 'overpriced'],
        'overpriced_shop': ['shop', 'overpriced', 'expensive'],
        'overpriced_restaurant': ['restaurant', 'meal', 'food', 'expensive'],
    }

    # Find matching case types
    matched_cases = []
    for situation_type, keywords in scam_type_keywords.items():
        if any(keyword in situation_lower for keyword in keywords):
            # Find exact or similar case in database
            for case in location_cases:
                if case['type'] == situation_type or situation_type.split('_')[0] in case['type']:
                    matched_cases.append(case)

    # If no exact match, return top cases for location
    if not matched_cases:
        matched_cases = location_cases[:3]

    # Calculate overall statistics
    total_cases = sum(case['count'] for case in matched_cases)

    if total_cases == 0:
        return None

    # Weighted average scam rate
    weighted_scam_rate = sum(case['count'] * case['scam_rate'] for case in matched_cases) / total_cases

    # Weighted average loss
    weighted_avg_loss = sum(case['count'] * case['avg_loss'] for case in matched_cases) / total_cases

    # Format case descriptions
    case_descriptions = []
    for case in matched_cases:
        case_type_name = case['type'].replace('_', ' ').title()
        case_descriptions.append(f"{case_type_name} ({case['count']} cases)")

    return {
        'location': location,
        'total_cases': total_cases,
        'scam_rate': weighted_scam_rate,
        'avg_loss': weighted_avg_loss,
        'case_types': case_descriptions,
        'matched_cases': matched_cases
    }

def get_currency_for_location(location):
    """Get currency code for a given location. Returns GBP for all London variants."""
    currency_map = {
        'delhi': 'INR', 'new delhi': 'INR', 'mumbai': 'INR', 'bangalore': 'INR', 'goa': 'INR', 'jaipur': 'INR', 'agra': 'INR', 'dehradun': 'INR', 'rajasthan': 'INR',
        'bangkok': 'THB', 'phuket': 'THB', 'chiang mai': 'THB', 'krabi': 'THB',
        'bali': 'IDR', 'jakarta': 'IDR',
        'london': 'GBP', 'greater london': 'GBP', 'barcelona': 'EUR', 'paris': 'EUR', 'amsterdam': 'EUR',
        'tokyo': 'JPY', 'sydney': 'AUD',
    }
    return currency_map.get(location.lower(), 'USD')

def format_similar_cases_response(similar_cases):
    """
    Format similar cases data for frontend display with proper currency mapping.
    """
    if not similar_cases or similar_cases['total_cases'] == 0:
        return None

    currency = get_currency_for_location(similar_cases['location'])

    # Format case types for display
    case_types_formatted = []
    for case in similar_cases['matched_cases']:
        case_type_name = case['type'].replace('_', ' ').title()
        case_types_formatted.append({
            'type': case_type_name,
            'count': case['count']
        })

    return {
        'location': similar_cases['location'],
        'total_cases': similar_cases['total_cases'],
        'scam_rate': similar_cases['scam_rate'],
        'avg_loss': similar_cases['avg_loss'],
        'currency': currency,
        'case_types': case_types_formatted
    }

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

                    return city_name

            except Exception:
                # Fall back to keyword matching if API fails
                continue

            # If API succeeded but let's also try the next location
            time.sleep(0.5)  # Rate limiting for API

    # Fallback: Simple keyword matching if no API results
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

def detect_price_anomaly(situation_text, detected_location='Unknown'):
    """
    Detect if prices in the situation are normal or inflated across multiple countries.
    Returns (has_price, is_inflated, price_details, currency)
    """
    import re
    situation_lower = situation_text.lower()

    # ============================================
    # GLOBAL PRICE BASELINES BY COUNTRY
    # ============================================
    price_baselines = {
        # INDIA
        'delhi': {'water': (10, 30), 'soft drink': (30, 60), 'chai': (20, 50), 'coffee': (40, 100),
                  'meal': (100, 400), 'tour': (500, 3000), 'cooking class': (1000, 5000),
                  'gem': (1000, 5000), 'jewelry': (500, 3000), 'transportation': (50, 500),
                  'currency': 'INR', 'threshold': 5000},
        'mumbai': {'water': (15, 40), 'soft drink': (30, 70), 'chai': (20, 50), 'coffee': (50, 120),
                   'meal': (150, 500), 'tour': (800, 4000), 'cooking class': (1500, 6000),
                   'gem': (1500, 6000), 'jewelry': (800, 4000), 'transportation': (100, 600),
                   'currency': 'INR', 'threshold': 6000},
        'bangalore': {'water': (10, 30), 'soft drink': (30, 60), 'chai': (25, 60), 'coffee': (50, 120),
                      'meal': (100, 400), 'tour': (500, 3000), 'cooking class': (1200, 5500),
                      'gem': (1000, 5000), 'jewelry': (500, 3000), 'transportation': (50, 500),
                      'currency': 'INR', 'threshold': 5000},
        'goa': {'water': (15, 40), 'soft drink': (40, 80), 'chai': (30, 60), 'coffee': (60, 150),
                'meal': (150, 500), 'tour': (800, 3500), 'cooking class': (1500, 6000),
                'gem': (1500, 6000), 'jewelry': (800, 4000), 'transportation': (100, 600),
                'currency': 'INR', 'threshold': 5000},
        'jaipur': {'water': (10, 25), 'soft drink': (25, 50), 'chai': (15, 40), 'coffee': (30, 80),
                   'meal': (80, 300), 'tour': (400, 2000), 'cooking class': (800, 4000),
                   'gem': (800, 3000), 'jewelry': (400, 2000), 'transportation': (30, 300),
                   'currency': 'INR', 'threshold': 4000},

        # THAILAND
        'bangkok': {'water': (10, 30), 'soft drink': (20, 50), 'chai': (30, 60), 'coffee': (50, 120),
                    'meal': (50, 300), 'street food': (30, 150), 'tour': (400, 2000), 'cooking class': (800, 3000),
                    'massage': (200, 600), 'jewelry': (300, 2000), 'transportation': (30, 200),
                    'currency': 'THB', 'threshold': 2000},
        'phuket': {'water': (15, 40), 'soft drink': (25, 60), 'chai': (40, 80), 'coffee': (70, 150),
                   'meal': (80, 400), 'tour': (600, 2500), 'cooking class': (1000, 4000),
                   'scuba': (1500, 5000), 'massage': (300, 800), 'transportation': (50, 300),
                   'currency': 'THB', 'threshold': 2500},
        'chiang mai': {'water': (10, 25), 'soft drink': (15, 40), 'chai': (20, 50), 'coffee': (40, 100),
                       'meal': (40, 200), 'tour': (300, 1500), 'cooking class': (600, 2000),
                       'massage': (150, 500), 'transportation': (20, 150), 'currency': 'THB', 'threshold': 1500},

        # INDONESIA
        'bali': {'water': (10000, 30000), 'soft drink': (15000, 40000), 'chai': (20000, 50000), 'coffee': (40000, 100000),
                 'meal': (30000, 200000), 'tour': (300000, 1500000), 'cooking class': (400000, 1500000),
                 'transportation': (15000, 100000), 'currency': 'IDR', 'threshold': 2000000},
        'jakarta': {'water': (15000, 35000), 'soft drink': (20000, 50000), 'chai': (25000, 60000), 'coffee': (50000, 120000),
                    'meal': (50000, 300000), 'tour': (400000, 2000000), 'cooking class': (800000, 3000000),
                    'transportation': (30000, 200000), 'currency': 'IDR', 'threshold': 400000},

        # EUROPE
        'paris': {'water': (1.5, 3), 'soft drink': (2, 4), 'chai': (3, 6), 'coffee': (2, 5),
                  'meal': (20, 50), 'tour': (50, 150), 'cooking class': (80, 200), 'museum': (12, 50),
                  'transportation': (2, 15), 'currency': 'EUR', 'threshold': 50},
        'london': {'water': (2, 4), 'soft drink': (2, 5), 'chai': (3, 6), 'coffee': (3, 6),
                   'meal': (15, 40), 'tour': (60, 150), 'cooking class': (80, 200), 'hotel': (50, 150),
                   'transportation': (2, 20), 'currency': 'GBP', 'threshold': 60},
        'barcelona': {'water': (1.5, 3), 'soft drink': (2, 4), 'chai': (3, 6), 'coffee': (2.5, 5),
                      'meal': (10, 25), 'tour': (40, 120), 'cooking class': (60, 150), 'museum': (12, 50),
                      'transportation': (2, 15), 'currency': 'EUR', 'threshold': 40},
        'amsterdam': {'water': (2, 4), 'soft drink': (2.5, 5), 'chai': (4, 7), 'coffee': (3, 6),
                      'meal': (12, 35), 'tour': (50, 150), 'cooking class': (80, 200),
                      'transportation': (3, 20), 'currency': 'EUR', 'threshold': 50},
        'tokyo': {'water': (100, 200), 'soft drink': (150, 250), 'chai': (250, 400), 'coffee': (300, 1000),
                  'meal': (1000, 5000), 'tour': (8000, 25000), 'cooking class': (10000, 25000),
                  'transportation': (200, 2000), 'currency': 'JPY', 'threshold': 5000},
        'sydney': {'water': (2, 4), 'soft drink': (3, 6), 'chai': (4, 7), 'coffee': (4, 7),
                   'meal': (15, 50), 'tour': (80, 200), 'cooking class': (100, 250), 'taxi': (30, 80),
                   'transportation': (3, 20), 'currency': 'AUD', 'threshold': 80},
    }

    # Get baseline for detected location
    location_lower = detected_location.lower()
    baseline = price_baselines.get(location_lower, price_baselines.get('delhi', {}))
    if not baseline:
        baseline = price_baselines['delhi']  # Default to India

    currency = baseline.get('currency', 'INR')
    threshold = baseline.get('threshold', 5000)

    # ============================================
    # ITEM DETECTION - Identify what's being sold
    # ============================================
    items = {
        'water': ['water', 'bottle of water', 'water bottle'],
        'soft drink': ['soft drink', 'coke', 'soda', 'cola', 'pepsi'],
        'chai': ['chai', 'chai tea', 'tea', 'cha yen'],
        'coffee': ['coffee', 'cappuccino', 'espresso', 'latte'],
        'meal': ['meal', 'food', 'rice', 'noodles', 'dish', 'restaurant'],
        'street food': ['street food', 'pad thai', 'street vendor'],
        'tour': ['tour', 'trip', 'excursion', 'guide'],
        'cooking class': ['cooking class', 'cooking lesson', 'chef'],
        'massage': ['massage', 'spa'],
        'gem': ['gem', 'gemstone', 'stone'],
        'jewelry': ['jewelry', 'bracelet', 'necklace', 'jewel'],
        'hotel': ['hotel', 'hostel', 'accommodation', 'room'],
        'museum': ['museum', 'gallery'],
        'scuba': ['scuba', 'diving lesson', 'dive'],
        'taxi': ['taxi', 'cab'],
        'transportation': ['taxi', 'ride', 'transport', 'auto', 'tuk-tuk'],
    }

    detected_items = []
    for item_name, keywords in items.items():
        for keyword in keywords:
            if keyword in situation_lower:
                detected_items.append(item_name)
                break

    # ============================================
    # MULTI-CURRENCY PRICE EXTRACTION
    # ============================================
    price_patterns = {
        'INR': [r'rs\.?\s*(\d+)', r'(\d+)\s*rs', r'rupees?\s*(\d+)', r'(\d+)\s*rupees?', r'inr\s*(\d+)', r'(\d+)\s*inr'],
        'THB': [r'thb\s*(\d+)', r'baht\s*(\d+)', r'(\d+)\s*thb', r'(\d+)\s*baht'],
        'IDR': [r'idr\s*(\d+)', r'rupiah\s*(\d+)', r'(\d+)\s*idr', r'(\d+)\s*k\s*idr', r'(\d+)k\s*idr'],
        'EUR': [r'eur\s*(\d+)', r'euros?\s*(\d+)', r'(\d+)\s*eur', r'(\d+)\s*euros?'],
        'GBP': [r'gbp\s*(\d+)', r'pounds?\s*(\d+)', r'(\d+)\s*gbp', r'(\d+)\s*pounds?', r'£\s*(\d+)'],
        'USD': [r'\$\s*(\d+)', r'(\d+)\s*\$', r'usd\s*(\d+)', r'dollars?\s*(\d+)', r'(\d+)\s*dollars?'],
        'JPY': [r'jpy\s*(\d+)', r'yen\s*(\d+)', r'(\d+)\s*yen'],
        'AUD': [r'aud\s*(\d+)', r'au\$\s*(\d+)', r'(\d+)\s*aud'],
    }

    # Try to extract prices for the detected currency first
    prices_found = []
    currency_detected = currency

    for curr, patterns in price_patterns.items():
        for pattern in patterns:
            matches = re.findall(pattern, situation_lower)
            if matches:
                prices_found.extend([int(m) for m in matches])
                currency_detected = curr
                break
        if prices_found:
            break

    if not prices_found:
        return False, False, None, currency

    # ============================================
    # ITEM-SPECIFIC PRICE CHECKING (IF/ELSE)
    # ============================================
    max_price = max(prices_found)

    # Check each detected item's price against fair range
    price_analysis = []
    is_price_inflated = False

    for item in detected_items:
        if item in baseline:
            fair_min, fair_max = baseline[item]

            if max_price < fair_min * 0.5:
                # Price significantly too low - suspicious/fake
                price_analysis.append(f"{item}: {currency_detected} {max_price} (SUSPICIOUS - too cheap, likely fake)")
                is_price_inflated = True
            elif fair_min <= max_price <= fair_max:
                # Price within fair range - NORMAL, NOT A SCAM
                price_analysis.append(f"{item}: {currency_detected} {max_price} (FAIR - normal market price)")
            elif fair_max < max_price <= fair_max * 1.5:
                # Price 0-50% higher - still acceptable
                price_analysis.append(f"{item}: {currency_detected} {max_price} (ACCEPTABLE - slightly above normal)")
            elif fair_max * 1.5 < max_price <= fair_max * 3:
                # Price 1.5-3x higher - likely scam
                markup = round(max_price / fair_max, 1)
                price_analysis.append(f"{item}: {currency_detected} {max_price} (SCAM - {markup}x normal price {fair_min}-{fair_max})")
                is_price_inflated = True
            elif fair_max * 3 < max_price <= fair_max * 5:
                # Price 3-5x higher - definite scam
                markup = round(max_price / fair_max, 1)
                price_analysis.append(f"{item}: {currency_detected} {max_price} (HIGH SCAM - {markup}x normal price!)")
                is_price_inflated = True
            else:
                # Price 5x+ higher - extreme scam
                markup = round(max_price / fair_max, 1)
                price_analysis.append(f"{item}: {currency_detected} {max_price} (EXTREME SCAM - {markup}x normal!)")
                is_price_inflated = True

    # Detect inflation indicators (keywords)
    inflation_keywords = [
        'expensive', 'overpriced', 'too much', 'double price', 'triple price',
        'x price', '3x', '5x', '10x', 'way too much', 'absurd price',
        'extremely expensive', 'shocking price', 'ridiculous', 'massively', 'grossly'
    ]

    has_inflation = any(keyword in situation_lower for keyword in inflation_keywords)

    # FINAL DECISION LOGIC
    if has_inflation:
        # Inflation keywords present → definite scam signal
        details = f"Price with inflation indicators detected. {'; '.join(price_analysis)}"
        return True, True, details, currency_detected

    if is_price_inflated:
        # Price exceeds fair range significantly
        details = '; '.join(price_analysis) if price_analysis else f"Price {currency_detected} {max_price} is inflated"
        return True, True, details, currency_detected

    if price_analysis:
        # Fair prices detected
        details = '; '.join(price_analysis)
        return True, False, details, currency_detected

    # Fallback: No item detected but price mentioned
    if max_price > threshold:
        return True, True, f"Extremely high price detected ({currency_detected} {max_price})", currency_detected

    return True, False, f"Prices detected: {currency_detected} {', '.join(map(str, prices_found))}", currency_detected

def generate_fallback_response(prompt_type, situation, location, risk_level=None):
    """Generate smart responses based on keywords when network is unavailable."""

    if prompt_type == "analysis":
        situation_lower = situation.lower()

        # ============================================
        # PRICE DETECTION (MULTI-COUNTRY SUPPORT)
        # ============================================
        has_price, is_inflated, price_details, currency = detect_price_anomaly(situation.lower(), location)

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

        # CRITICAL Red flags - only DEFINITE scam indicators
        high_risk_keywords = [
            # Unsolicited high-pressure approaches
            'stranger approached me', 'man approached me', 'woman approached me',
            'random person approached', 'approached me urgently',

            # Extreme price anomalies (50x+ markup)
            '10x price', '5x price', '100x', '1000x',
            'grossly overpriced', 'massively overpriced',

            # Aggressive pressure + urgency combo
            'pay now or', 'pay today or', 'right now or never',
            'today only', 'only today', 'last chance',

            # Counterfeit goods
            'fake', 'counterfeit', 'replica watch', 'replica rolex',

            # Strong scam indicators
            'seems like scam', 'looks like scam', 'definitely scam',
            'unsolicited offer too good', 'promised delivery',
            'will send later', 'deliver tomorrow cash',
        ]

        # Count matches for better accuracy
        low_risk_count = sum(1 for keyword in low_risk_keywords if keyword in situation_lower)
        high_risk_count = sum(1 for keyword in high_risk_keywords if keyword in situation_lower)

        # ============================================
        # INDEPENDENT PRICE FILTER LOGIC
        # Price is the PRIMARY signal (no keywords needed)
        # ============================================
        if is_inflated:
            # INFLATED PRICES detected → HIGH risk (STANDALONE decision)
            print(f"[DEBUG] Price inflation detected (INDEPENDENT): {price_details}")
            scam_prob = 'High'
        elif has_price and not is_inflated:
            # FAIR/NORMAL prices detected → LOW risk (STANDALONE decision)
            # Price is fair = legitimate, regardless of keywords
            print(f"[DEBUG] Fair pricing detected (INDEPENDENT): {price_details}")
            scam_prob = 'Low'
        elif high_risk_count >= 1:
            # CRITICAL red flags detected (no price mentioned) → HIGH risk
            scam_prob = 'High'
        elif low_risk_count >= 3:
            # Multiple legitimacy signals (no price mentioned) → LOW risk
            scam_prob = 'Low'
        elif low_risk_count >= 2 and high_risk_count == 0:
            # Strong legitimacy signals (no price mentioned) → LOW risk
            scam_prob = 'Low'
        else:
            # Insufficient signals → Default to High (safety-first on uncertainty)
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
def call_llm(prompt, retries=2, model="mistral"):
    """
    Calls the Hugging Face Inference API with a given prompt.

    Args:
        prompt (str): The prompt to send to the model.
        retries (int): Number of times to retry on failure.
        model (str): Which model to use - "mistral" or "llama" (default: "mistral")

    Returns:
        str: The generated text from the model, or fallback response.
    """
    # Select the appropriate API URL based on model
    api_url = HF_API_URL_LLAMA if model.lower() == "llama" else HF_API_URL_MISTRAL

    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {"inputs": prompt, "options": {"wait_for_model": True}}

    for attempt in range(retries):
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(api_url, headers=headers, json=payload)
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

def moderate_content(user_input):
    """
    Moderate user input for harmful, unsafe, and toxic content.
    Uses pattern-based detection (Tier 1) + Llama-2-70b (Tier 2) to detect:
    - Harmful/violent language
    - Toxicity and hate speech
    - Requests to help with scams or illegal activities
    - Threats, harassment, abuse
    - Unsafe prompts and toxic content
    - Sexual exploitation content

    Returns: {'is_safe': bool, 'reason': str, 'score': float, 'category': str}
    """
    text_lower = user_input.lower()

    # ============================================
    # TIER 1: PATTERN-BASED QUICK CHECK (< 1ms)
    # ============================================
    harmful_patterns = {
        'scam_help': [
            r'\b(help|teach|learn|tell|show|teach me).*\b(scam|fraud|cheat|swindle|con)',
            r'\b(how|ways?\s+to)\s*(scam|fraud|con|cheat)',
            r'(teach|help|guide).*\b(tourists|travelers|people)\b.*(scam|con)',
        ],
        'theft_help': [
            r'\b(help|teach|learn|tell|show|guide).*\b(steal|rob|rob|pickpocket|theft)',
            r'\b(how|ways?\s+to)\s*(steal|rob|pickpocket|shoplift|burgle|loot)',
            r'\b(best|easiest|fastest)\s+way\b.*\b(steal|rob|pickpocket)\b',
            r'\b(how|ways?)\b.*\b(steal|rob)\b.*\b(from|to)\b.*(tourists|travelers|people|backpackers)',
            r'\b(steal|rob|pickpocket|steal)\b.*\b(money|wallet|phone|passport|bag|camera)',
            r'\b(grab|snatch|take)\b.*\b(from|off|away)\b.*\b(tourists|travelers|person)',
            r'\b(theft|robbery|burglary|larceny|stealing)\b',
            r'\b(pick.*pocket|cut.*pocket|snatch.*bag|break.*into|burglar|shoplifter)\b',
        ],
        'credit_card_fraud': [
            r'\b(how|ways?)\b.*\b(clone|copy|steal|duplicate)\b.*\b(credit card|card number|cvv|pin)',
            r'\b(fake|forged|stolen)\b.*\b(credit card|debit card|identity)',
            r'\b(card.*skimming|skimmer|cloning)\b',
        ],
        'extortion_blackmail': [
            r'\b(extort|blackmail|coerce|force).*\b(payment|money|cash)\b',
            r'\b(unless.*pay|give.*money|or i will)\b.*\b(harm|hurt|tell|expose)\b',
            r'\b(ransom|extortion|blackmail)\b',
        ],
        'violence': [
            r'\b(want|will|can|should|would).*\b(harm|kill|hurt|attack|assault|beat|punch|stab)',
            r'\b(kill|murder|destroy|bomb|assault|attack|hurt)\b.*\b(tourists|travelers|people)',
            r'\b(how|ways?)\b.*\b(kill|hurt|harm|attack|violate|beat)\b',
            r'\b(mug|attack|rob)\b.*\b(tourist|traveler|person|backpacker)\b',
        ],
        'hate_speech': [
            r'\b(hate|despise|detest|dislike)\s+(all|every|people|tourists|travelers)',
            r'(all|people|tourists|travelers)\s+from\s+\w+\s+(are|is)\s+(scammers|criminals|bad|evil|thieves)',
            r'\b(racist|sexist|bigot|xenophobe)\b',
        ],
        'sexual_exploitation': [
            r'\b(sex|sexual|exploit).*\b(travelers|tourists|children|minors)',
            r'\b(rape|assault|abuse|grope)\b',
            r'\b(sex work|prostitution|trafficking|child.*abuse)\b',
        ],
        'illegal_activities': [
            r'\b(how|ways?)\b.*\b(drug|cocaine|heroin|meth|illegal)',
            r'\b(money|funds)\s+(launder|wash)',
            r'\b(counterfeit|forgery|trafficking|smuggle|contraband)\b',
            r'\b(make.*fake|create.*fake|forge)\b.*\b(passport|visa|id|document)\b',
        ],
        'harassment': [
            r'\b(abuse|exploit|harass|threaten|blackmail|intimidate)\b',
            r'\b(dox|doxxing|swat|leak)\b',
            r'\b(revenge|stalk|creep|cyberbully|troll)\b',
        ],
    }

    import re
    detected_category = None
    for category, patterns in harmful_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                reason = f"Pattern-based detection: {category.replace('_', ' ').title()} detected"
                return {'is_safe': False, 'reason': reason, 'score': 0.95, 'category': category}

    # ============================================
    # TIER 2: LLAMA-2-70B LLM CHECK (2-3 seconds)
    # ============================================
    moderation_prompt = f"""You are an expert content moderation system for travel safety. Analyze this input strictly for harmful, unsafe, or toxic content.

INPUT TEXT: "{user_input}"

EVALUATION CRITERIA:
1. **Scam Help**: Asking how to scam, defraud, or con travelers/people
2. **Theft/Robbery**: Asking how to steal, rob, pickpocket, burgle, or loot from others
3. **Credit Card Fraud**: Cloning cards, stealing payment info, fake identity theft
4. **Extortion/Blackmail**: Threatening harm unless payment, ransom demands
5. **Violence & Threats**: Harming, killing, attacking, mugging, beating people
6. **Hate Speech**: Derogatory language about groups, races, nationalities, religions
7. **Sexual Exploitation**: Sexual abuse, trafficking, or exploitation content
8. **Illegal Activities**: Drugs, counterfeiting, money laundering, passport forgery
9. **Harassment/Abuse**: Threats, blackmail, stalking, doxxing, bullying, cyberbullying

SAFETY RULES:
- ALLOW: Legitimate travel safety concerns ("Is X a scam?", "How to stay safe?")
- ALLOW: Reporting actual scams ("I was scammed by...")
- BLOCK: Everything asking HOW to commit harmful acts
- DEFAULT: When uncertain, block (prioritize safety)

RESPOND WITH ONLY THIS JSON (no markdown, no explanation):
{{"is_safe": true or false, "reason": "short reason if unsafe", "score": 0.0 to 1.0, "category": "violation_type or null"}}

Examples:
✗ {{"is_safe": false, "reason": "Asking how to steal from tourists", "score": 0.95, "category": "theft_help"}}
✗ {{"is_safe": false, "reason": "Asking how to pickpocket travelers", "score": 0.95, "category": "theft_help"}}
✗ {{"is_safe": false, "reason": "Asking how to clone credit cards", "score": 0.95, "category": "credit_card_fraud"}}
✗ {{"is_safe": false, "reason": "Threatening extortion for money", "score": 0.95, "category": "extortion_blackmail"}}
✓ {{"is_safe": true, "reason": "Legitimate travel safety question", "score": 0.0, "category": null}}"""

    try:
        moderation_response = call_llm(moderation_prompt, retries=1, model="llama")

        if moderation_response.startswith("Error:"):
            return {'is_safe': True, 'reason': 'Check failed', 'score': 0.0}

        json_start = moderation_response.find('{')
        json_end = moderation_response.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            return {'is_safe': True, 'reason': 'Parse error', 'score': 0.0}

        json_str = moderation_response[json_start:json_end]
        result = json.loads(json_str)

        is_safe = result.get('is_safe', True)
        reason = result.get('reason', '')
        score = float(result.get('score', 0.0))
        category = result.get('category', None)

        return {'is_safe': is_safe, 'reason': reason, 'score': score, 'category': category}

    except Exception:
        return {'is_safe': True, 'reason': 'Check error', 'score': 0.0}

def judge_analysis(analysis_result, advice_text, summary_text, location):
    """
    Use Llama-2-70b as a judge to validate Mistral's analysis.
    Checks if the risk assessment, advice, and summary are appropriate and consistent.
    Returns confidence scores and validation results.
    """
    judge_prompt = f"""You are an expert judge evaluating a travel scam analysis.

SITUATION ANALYSIS FROM AI:
Risk Level: {analysis_result.get('scam_probability', 'Unknown')}
Location: {location}
Advice: {advice_text[:200]}...
Summary: {summary_text[:200]}...

JUDGE THIS ANALYSIS:
1. Is the risk level assessment reasonable? (yes/no)
2. Is the advice appropriate for the risk level? (yes/no)
3. Is the summary clear and actionable? (yes/no)
4. Overall confidence in this analysis (0-100%)?

Respond with ONLY valid JSON:
{{"risk_valid": true/false, "advice_valid": true/false, "summary_valid": true/false, "confidence": 0-100, "feedback": "brief comment"}}"""

    try:
        judge_response = call_llm(judge_prompt, retries=1, model="llama")

        if judge_response.startswith("Error:"):
            return {'confidence': 0.0, 'risk_valid': True, 'advice_valid': True, 'summary_valid': True, 'feedback': 'Judge unavailable'}

        json_start = judge_response.find('{')
        json_end = judge_response.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            return {'confidence': 0.0, 'risk_valid': True, 'advice_valid': True, 'summary_valid': True, 'feedback': 'Parse error'}

        json_str = judge_response[json_start:json_end]
        result = json.loads(json_str)

        confidence = float(result.get('confidence', 0)) / 100.0
        feedback = result.get('feedback', '')


        return {
            'confidence': confidence,
            'risk_valid': result.get('risk_valid', True),
            'advice_valid': result.get('advice_valid', True),
            'summary_valid': result.get('summary_valid', True),
            'feedback': feedback
        }

    except Exception:
        return {'confidence': 0.0, 'risk_valid': True, 'advice_valid': True, 'summary_valid': True, 'feedback': 'Error'}

# --- FLASK ROUTES ---
@app.route('/')
def index():
    """Renders the main HTML page."""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_input():
    """
    3-LLM AI Workflow:
    LLM Call 1 → Analyze scam probability & location
    if/else condition → Route to different workflows
    LLM Call 2 → Generate risk-specific advice (high risk emergency, low risk tips)
    LLM Call 3 → Generate final summary/checklist
    """
    try:
        # INPUT VALIDATION
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON payload."}), 400

        user_input = data.get('user_input', '').strip()
        if not user_input:
            return jsonify({"error": "No user input provided."}), 400

        if len(user_input) < 10:
            return jsonify({"error": "Input too short. Please provide more details."}), 400

        if len(user_input) > 5000:
            return jsonify({"error": "Input too long. Maximum 5000 characters."}), 400

    except Exception as e:
        return jsonify({"error": f"Invalid request format: {str(e)}"}), 400

    moderation_result = moderate_content(user_input)
    if not moderation_result['is_safe']:
        return jsonify({
            "error": "Content Policy Violation",
            "details": f"Your input was flagged for safety reasons: {moderation_result['reason']}",
            "safety_score": moderation_result['score'],
            "workflow_status": "blocked_by_moderation"
        }), 400

    all_raw_responses = {}
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
    detected_location = extract_location(user_input)
    all_raw_responses['analysis'] = raw_response1

    # PARSE & VALIDATE LLM Call 1 Response
    try:
        if raw_response1.startswith("Error:"):
            network_error_detected[0] = True
            raise ValueError("Network error in LLM call")

        json_start = raw_response1.find('{')
        json_end = raw_response1.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in response")

        json_str = raw_response1[json_start:json_end]
        analysis_result = json.loads(json_str)

        # Validate scam_probability field
        scam_prob = str(analysis_result.get('scam_probability', 'Low')).strip().lower()
        if 'high' in scam_prob or 'yes' in scam_prob or 'probable' in scam_prob:
            scam_prob = 'High'
        elif 'low' in scam_prob or 'no' in scam_prob or 'safe' in scam_prob:
            scam_prob = 'Low'
        else:
            scam_prob = 'High'  # Safety-first default

        analysis_result['scam_probability'] = scam_prob

        # Validate location field
        location_from_api = analysis_result.get('location', 'Unknown').strip()
        if location_from_api.lower() == 'unknown':
            analysis_result['location'] = detected_location
        else:
            analysis_result['location'] = location_from_api

    except (json.JSONDecodeError, ValueError, KeyError):
        analysis_result_json = generate_fallback_response("analysis", user_input, detected_location)
        analysis_result = json.loads(analysis_result_json)

    scam_probability = analysis_result.get('scam_probability', 'Low')
    location = analysis_result.get('location', 'an unknown location')
    if scam_probability == 'High':
        prompt2 = f"""⚠️ DANGER ALERT - Potential scam detected in {location}!

SITUATION: '{user_input}'

Provide 5 CRITICAL action steps (SHORT, direct sentences only):

1. STOP NOW: Do not pay any money. Do not agree to anything. Leave immediately.
2. EXTRACT: Remove yourself from the situation. Walk away or run if necessary. Get to safety.
3. SECURE: Go directly to your hotel, hostel, or official place. Tell staff what happened.
4. EVIDENCE: Take notes of details (time, place, person's appearance, what they said). Take photos if safe.
5. REPORT: Contact local tourist police or your country's embassy/consulate. File an official report.

Be direct and actionable. Maximum 1 sentence per step."""
    else:
        print("[ELSE Branch] Generating encouragement tips for LOW RISK situation")
        prompt2 = f"""Great news! {location} opportunity appears LEGITIMATE.

SITUATION: '{user_input}'

Provide 5 practical action steps (SHORT, encouraging sentences only):

1. VERIFY: Check recent reviews online. Ask other travelers there. Confirm on booking platform if booked.
2. CONFIRM: Ask about pricing, timing, and what's included. Get it in writing or take a photo of details.
3. COMPARE: See if other vendors offer similar prices. Negotiate if you think price is high.
4. COMMUNICATE: Ask questions about the experience. Build rapport with the person/organizer.
5. ENJOY: Go ahead with booking. Document your experience with photos. Leave a positive review if happy.

Be practical and encouraging. Maximum 1 sentence per step."""

    advice_result = call_llm(prompt2)
    all_raw_responses['advice'] = advice_result

    try:
        if advice_result.startswith("Error:"):
            network_error_detected[0] = True
            raise ValueError("Network error in LLM call")

        advice_text = advice_result.split(prompt2)[-1].strip() if prompt2 in advice_result else advice_result
        advice_text = advice_text.replace("```", "").replace("json", "").replace("\\n", "\n").strip()
        advice_text = advice_text.replace("python", "").replace("bash", "").replace("markdown", "")

        if advice_text.startswith('"') and advice_text.endswith('"'):
            advice_text = advice_text[1:-1]

        if not advice_text or len(advice_text) < 20:
            raise ValueError("Response too short or empty")

    except (ValueError, AttributeError):
        advice_text = generate_fallback_response("advice", user_input, location, scam_probability)
    if scam_probability == 'High':
        prompt3 = f"""Create a 3-point DANGER CHECKLIST for this SCAM situation in {location}.

SITUATION: '{user_input}'

Format (SHORT, direct language only):
⚠️ THREAT: [Identify what's dangerous about this]
⚠️ ESCAPE: [Immediate action to get to safety]
⚠️ REPORT: [How to report it to authorities]

Make it clear and urgent. 1-2 words per point max.
Examples:
⚠️ THREAT: Stranger + extreme markup = classic scam
⚠️ ESCAPE: Leave now. Go to nearest police station.
⚠️ REPORT: Tell police + contact your embassy/consulate"""
    else:
        prompt3 = f"""Create a 3-point GO-AHEAD CHECKLIST for this LEGITIMATE opportunity in {location}.

SITUATION: '{user_input}'

Format (SHORT, encouraging language only):
✓ CONFIRM: [What to verify before booking]
✓ BOOK: [How to secure the experience safely]
✓ ENJOY: [What to do and how to maximize the experience]

Make it practical and encouraging. 1-2 words per point max.
Examples:
✓ CONFIRM: Check reviews + ask locals + compare prices
✓ BOOK: Use official platform or get written confirmation
✓ ENJOY: Go ahead + take photos + leave positive review"""
    summary_result = call_llm(prompt3)
    all_raw_responses['summary'] = summary_result

    try:
        if summary_result.startswith("Error:"):
            network_error_detected[0] = True
            raise ValueError("Network error in LLM call")

        summary_text = summary_result.split(prompt3)[-1].strip() if prompt3 in summary_result else summary_result
        summary_text = summary_text.replace("```", "").replace("json", "").replace("\\n", "\n").strip()
        summary_text = summary_text.replace("python", "").replace("bash", "").replace("markdown", "")

        if summary_text.startswith('"') and summary_text.endswith('"'):
            summary_text = summary_text[1:-1]

        if not summary_text or '✓' not in summary_text:
            raise ValueError("Invalid summary format")

    except (ValueError, AttributeError):
        summary_text = generate_fallback_response("summary", user_input, location, scam_probability)

    similar_cases = find_similar_cases(location, user_input)
    similar_cases_response = None
    if similar_cases and similar_cases['total_cases'] > 0:
        similar_cases_response = format_similar_cases_response(similar_cases)

    judge_result = judge_analysis(analysis_result, advice_text, summary_text, location)

    # FINAL RESPONSE with validation
    try:
        response = {
            "analysis": analysis_result,
            "advice": advice_text,
            "summary": summary_text,
            "workflow_status": "success",
            "judge_validation": {
                "confidence": judge_result['confidence'],
                "risk_valid": judge_result['risk_valid'],
                "advice_valid": judge_result['advice_valid'],
                "summary_valid": judge_result['summary_valid'],
                "feedback": judge_result['feedback']
            }
        }

        # Add similar cases if found
        if similar_cases_response:
            response["similar_cases"] = similar_cases_response
            print(f"[Response] Added similar cases data")

        print(f"\n[Workflow Complete] 3 LLM calls (Mistral) + Judge validation (Llama) + Similar Cases matching processed successfully\n")
        return jsonify(response), 200

    except Exception as e:
        print(f"[ERROR] Final response generation failed: {e}")
        return jsonify({"error": "Failed to generate response", "details": str(e)}), 500

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # Note: In a real production environment, use a proper WSGI server like Gunicorn or Waitress
    # instead of app.run(). The host '0.0.0.0' makes it accessible on your local network.
    app.run(host='0.0.0.0', port=5000, debug=True)