#!/usr/bin/env python3
"""
Ghalla Mandi Backend Server - FINAL VERSION (GitHub Ready)
Developed by: Muhammad Umer Farooq

Features:
- USD/PKR: exchangerate-api.com (live, no key required)
- Pakistan prices: Scraped from tractors.com.pk, myagriculturalrates.pages.dev, kcapk.com
- City-wise price variation for major Pakistan cities
- International: TradingEconomics base prices
- Updates daily at midnight + live micro-fluctuation

Run: python ghalla_mandi_backend.py
Frontend: Open index.html in browser (or host on any static server)
"""

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import requests
import threading
import time
import random
import json
import os
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)  # Allow all origins so index.html works from file:// or any domain

DATA_FILE = 'daily_prices.json'

# ==================== REAL BASE PRICES (April 2026) ====================
REAL_BASE = {
    "wheat_usd_per_ton": 232.25,
    "cotton_usd_per_lb": 0.794,
    "cotton_usd_per_ton": 1750.00,
    "gandam": 3950,
    "bajra":  4200,
    "sarso":  6500,
    "kapas":  7200,
    "tili":   7800,
    "jo":     3600
}

# ==================== PAKISTAN CITIES ====================
# City-wise price multipliers relative to national average
# Based on: transport cost, local demand, mandis near production zones
CITIES = {
    "lahore":       {"name": "Lahore",       "province": "Punjab",   "multipliers": {"gandam": 1.00, "bajra": 1.02, "sarso": 1.01, "kapas": 0.98, "tili": 1.03, "jo": 1.00}},
    "karachi":      {"name": "Karachi",      "province": "Sindh",    "multipliers": {"gandam": 1.05, "bajra": 1.08, "sarso": 1.06, "kapas": 1.02, "tili": 1.07, "jo": 1.05}},
    "faisalabad":   {"name": "Faisalabad",   "province": "Punjab",   "multipliers": {"gandam": 0.97, "bajra": 0.99, "sarso": 0.98, "kapas": 0.97, "tili": 1.00, "jo": 0.97}},
    "multan":       {"name": "Multan",       "province": "Punjab",   "multipliers": {"gandam": 0.96, "bajra": 0.98, "sarso": 0.97, "kapas": 0.95, "tili": 0.99, "jo": 0.96}},
    "rawalpindi":   {"name": "Rawalpindi",   "province": "Punjab",   "multipliers": {"gandam": 1.02, "bajra": 1.03, "sarso": 1.02, "kapas": 1.01, "tili": 1.04, "jo": 1.02}},
    "peshawar":     {"name": "Peshawar",     "province": "KPK",      "multipliers": {"gandam": 1.03, "bajra": 1.05, "sarso": 1.04, "kapas": 1.03, "tili": 1.06, "jo": 1.04}},
    "quetta":       {"name": "Quetta",       "province": "Balochistan", "multipliers": {"gandam": 1.08, "bajra": 1.10, "sarso": 1.09, "kapas": 1.07, "tili": 1.11, "jo": 1.09}},
    "hyderabad":    {"name": "Hyderabad",    "province": "Sindh",    "multipliers": {"gandam": 1.02, "bajra": 1.04, "sarso": 1.03, "kapas": 0.99, "tili": 1.04, "jo": 1.02}},
    "gujranwala":   {"name": "Gujranwala",   "province": "Punjab",   "multipliers": {"gandam": 0.98, "bajra": 1.00, "sarso": 0.99, "kapas": 0.98, "tili": 1.01, "jo": 0.98}},
    "sialkot":      {"name": "Sialkot",      "province": "Punjab",   "multipliers": {"gandam": 0.99, "bajra": 1.01, "sarso": 1.00, "kapas": 0.99, "tili": 1.02, "jo": 0.99}},
    "sukkur":       {"name": "Sukkur",       "province": "Sindh",    "multipliers": {"gandam": 1.01, "bajra": 1.03, "sarso": 1.02, "kapas": 0.97, "tili": 1.03, "jo": 1.01}},
    "bahawalpur":   {"name": "Bahawalpur",   "province": "Punjab",   "multipliers": {"gandam": 0.95, "bajra": 0.97, "sarso": 0.96, "kapas": 0.94, "tili": 0.98, "jo": 0.95}},
    "sargodha":     {"name": "Sargodha",     "province": "Punjab",   "multipliers": {"gandam": 0.97, "bajra": 0.99, "sarso": 0.98, "kapas": 0.96, "tili": 1.00, "jo": 0.97}},
    "okara":        {"name": "Okara",        "province": "Punjab",   "multipliers": {"gandam": 0.96, "bajra": 0.98, "sarso": 0.97, "kapas": 0.95, "tili": 0.99, "jo": 0.96}},
    "islamabad":    {"name": "Islamabad",    "province": "ICT",      "multipliers": {"gandam": 1.04, "bajra": 1.05, "sarso": 1.04, "kapas": 1.03, "tili": 1.06, "jo": 1.04}},
    "dera_ghazi_khan": {"name": "D.G. Khan", "province": "Punjab",   "multipliers": {"gandam": 0.98, "bajra": 1.00, "sarso": 0.99, "kapas": 0.97, "tili": 1.01, "jo": 0.98}},
    "jhang":        {"name": "Jhang",        "province": "Punjab",   "multipliers": {"gandam": 0.97, "bajra": 0.99, "sarso": 0.98, "kapas": 0.96, "tili": 1.00, "jo": 0.97}},
    "sahiwal":      {"name": "Sahiwal",      "province": "Punjab",   "multipliers": {"gandam": 0.96, "bajra": 0.98, "sarso": 0.97, "kapas": 0.95, "tili": 0.99, "jo": 0.96}},
    "nawabshah":    {"name": "Nawabshah",    "province": "Sindh",    "multipliers": {"gandam": 1.03, "bajra": 1.05, "sarso": 1.04, "kapas": 0.98, "tili": 1.05, "jo": 1.03}},
    "larkana":      {"name": "Larkana",      "province": "Sindh",    "multipliers": {"gandam": 1.04, "bajra": 1.06, "sarso": 1.05, "kapas": 0.99, "tili": 1.06, "jo": 1.04}},
}


# ==================== PRICE STORE ====================

class PriceStore:
    def __init__(self):
        self.daily = {}
        self.usd_pkr = 278.94
        self.last_update = None
        self.sources = []
        self.lock = threading.Lock()
        self.load()

    def load(self):
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE) as f:
                    data = json.load(f)
                    self.daily = data.get('daily', {})
                    self.usd_pkr = data.get('usd_pkr', 278.94)
                    self.last_update = data.get('last_update')
                    print(f"[STORE] Loaded from {self.last_update}")
        except Exception as e:
            print(f"[STORE] Load error: {e}")

    def save(self):
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump({
                    'daily': self.daily,
                    'usd_pkr': self.usd_pkr,
                    'last_update': self.last_update,
                    'saved': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            print(f"[STORE] Save error: {e}")

    def update(self, prices, source):
        with self.lock:
            for c, p in prices.items():
                self.daily[c] = {
                    'price': p,
                    'source': source,
                    'updated': datetime.now().isoformat()
                }
            self.last_update = datetime.now().isoformat()
            if source not in self.sources:
                self.sources.append(source)
            self.save()

store = PriceStore()


# ==================== SCRAPERS ====================

def scrape_tractors_pk():
    """Scrape cotton/kapas price from tractors.com.pk"""
    try:
        r = requests.get(
            "https://tractors.com.pk/cotton-price-phutti-rate-pakistan/",
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            timeout=15
        )
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, 'html.parser')
            text = soup.get_text()
            m = re.search(r'Rs\.?\s*([0-9,]+)\s*to\s*Rs\.?\s*([0-9,]+).*?40\s*kg', text, re.I)
            if m:
                avg = (int(m.group(1).replace(',', '')) + int(m.group(2).replace(',', ''))) // 2
                print(f"[SCRAPER] tractors.com.pk: Kapas PKR {avg}")
                return {'kapas': avg}
    except Exception as e:
        print(f"[SCRAPER] tractors.com.pk error: {e}")
    return None


def scrape_agricultural_rates():
    """Scrape grain prices from myagriculturalrates.pages.dev"""
    try:
        r = requests.get(
            "https://myagriculturalrates.pages.dev/",
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            timeout=15
        )
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, 'html.parser')
            text = soup.get_text()
            prices = {}
            for commodity, key in [('tili', r'til|sesame'), ('gandam', r'wheat|gandam')]:
                m = re.search(rf'({key}).*?Rs\.?\s*([0-9,]+)', text, re.I)
                if m:
                    prices[commodity] = int(m.group(2).replace(',', ''))
            if prices:
                print(f"[SCRAPER] myagriculturalrates: {prices}")
                return prices
    except Exception as e:
        print(f"[SCRAPER] myagriculturalrates error: {e}")
    return None


def scrape_kca():
    """Scrape cotton spot rate from kcapk.com"""
    try:
        r = requests.get(
            "http://www.kcapk.com/dailymarketrep.asp",
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            timeout=15
        )
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, 'html.parser')
            for table in soup.find_all('table'):
                text = table.get_text()
                if 'Spot Rate' in text or '40 kgs' in text:
                    for row in table.find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) >= 2 and ('40' in cells[0].get_text() or '37.32' in cells[0].get_text()):
                            m = re.search(r'([0-9,]+)', cells[1].get_text())
                            if m:
                                price = int(m.group(1).replace(',', ''))
                                print(f"[SCRAPER] kcapk.com: Cotton PKR {price}")
                                return {'kapas': price}
    except Exception as e:
        print(f"[SCRAPER] kcapk.com error: {e}")
    return None


def fetch_usd_pkr():
    """Fetch live USD/PKR rate"""
    try:
        r = requests.get('https://api.exchangerate-api.com/v4/latest/USD', timeout=10)
        if r.status_code == 200:
            rate = r.json()['rates']['PKR']
            store.usd_pkr = rate
            print(f"[RATE] USD/PKR updated: {rate}")
            return rate
    except Exception as e:
        print(f"[RATE] USD/PKR error: {e}")
    return store.usd_pkr


def estimate_missing(wheat_price):
    """Estimate commodities from wheat base using historical market ratios"""
    return {
        'bajra': round(wheat_price * 1.06),
        'sarso': round(wheat_price * 1.65),
        'jo':    round(wheat_price * 0.92),
        'tili':  round(wheat_price * 1.95)
    }


def daily_update():
    """Run full daily price scrape"""
    print("\n" + "="*60)
    print(f"DAILY UPDATE - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)

    fetch_usd_pkr()
    scraped = 0

    result = scrape_tractors_pk()
    if result:
        store.update(result, 'tractors.com.pk')
        scraped += len(result)

    result = scrape_agricultural_rates()
    if result:
        store.update(result, 'myagriculturalrates.pages.dev')
        scraped += len(result)

    result = scrape_kca()
    if result:
        store.update(result, 'kcapk.com')
        scraped += len(result)

    # Fill in any missing commodities from wheat ratio
    wheat = store.daily.get('gandam', {}).get('price', REAL_BASE['gandam'])
    store.update(estimate_missing(wheat), 'market_ratio_estimate')

    print(f"[DAILY] Scraped {scraped} real prices, estimated rest")
    print(f"[DAILY] USD/PKR: {store.usd_pkr}")
    print("="*60 + "\n")

    engine.reset()


# ==================== LIVE ENGINE ====================

class LiveEngine:
    """Provides micro-fluctuation around scraped daily base prices"""

    def __init__(self):
        self.local = {}
        self.intl = {}
        self.reset()

    def reset(self):
        for c in ['gandam', 'bajra', 'sarso', 'kapas', 'tili', 'jo']:
            base = store.daily.get(c, {}).get('price', REAL_BASE.get(c, 3000))
            self.local[c] = {
                'current': base, 'previous': base,
                'change': 0, 'change_percent': 0,
                'history': [base] * 20,
                'high': base, 'low': base
            }

        w_base = REAL_BASE['wheat_usd_per_ton']
        c_base = REAL_BASE['cotton_usd_per_ton']
        self.intl = {
            'wheat_futures': {
                'current': w_base, 'previous': w_base,
                'change': 0, 'change_percent': 0,
                'history': [w_base] * 20, 'high': w_base, 'low': w_base
            },
            'cotton_futures': {
                'current': c_base, 'previous': c_base,
                'change': 0, 'change_percent': 0,
                'history': [c_base] * 20, 'high': c_base, 'low': c_base
            }
        }

    def update_local(self):
        vols = {
            'gandam': 0.008, 'bajra': 0.012, 'sarso': 0.015,
            'kapas': 0.018, 'tili': 0.020, 'jo': 0.010
        }
        for c, d in self.local.items():
            base = store.daily.get(c, {}).get('price', d['current'])
            vol = vols.get(c, 0.01)
            delta = base * vol * (random.random() - 0.5) * 2
            new_price = round(max(base * 0.97, min(base * 1.03, base + delta)))
            d['previous'] = d['current']
            d['current'] = new_price
            d['change'] = new_price - d['previous']
            d['change_percent'] = (d['change'] / d['previous'] * 100) if d['previous'] else 0
            d['history'].pop(0)
            d['history'].append(new_price)
            d['high'] = max(d['history'])
            d['low'] = min(d['history'])

    def update_intl(self):
        for key, d in self.intl.items():
            vol = 0.006 if 'wheat' in key else 0.012
            delta = d['current'] * vol * (random.random() - 0.5) * 2
            new_price = round((d['current'] + delta) * 100) / 100
            d['previous'] = d['current']
            d['current'] = new_price
            d['change'] = round(new_price - d['previous'], 4)
            d['change_percent'] = (d['change'] / d['previous'] * 100) if d['previous'] else 0
            d['history'].pop(0)
            d['history'].append(new_price)
            d['high'] = max(d['history'])
            d['low'] = min(d['history'])

    def get_city_prices(self, city_id):
        """Return local prices adjusted for a specific city"""
        if city_id not in CITIES:
            return None
        city = CITIES[city_id]
        result = {}
        for c, d in self.local.items():
            mult = city['multipliers'].get(c, 1.0)
            # Add city-specific micro noise
            noise = 1 + (random.random() - 0.5) * 0.004
            adjusted = round(d['current'] * mult * noise)
            result[c] = {
                'current': adjusted,
                'previous': round(d['previous'] * mult),
                'change': adjusted - round(d['previous'] * mult),
                'change_percent': d['change_percent'],
                'history': [round(h * mult) for h in d['history']],
                'high': round(d['high'] * mult),
                'low': round(d['low'] * mult),
                'multiplier': mult
            }
        return result


engine = LiveEngine()


# ==================== BACKGROUND THREADS ====================

def daily_loop():
    """Runs daily_update every midnight"""
    daily_update()
    while True:
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        midnight = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        sleep_sec = (midnight - now).total_seconds()
        print(f"[SCHEDULER] Next daily update in {sleep_sec/3600:.1f} hours")
        time.sleep(sleep_sec)
        daily_update()


def local_loop():
    """Update local prices every 10 seconds"""
    while True:
        engine.update_local()
        time.sleep(10)


def intl_loop():
    """Update international prices every 60 seconds"""
    while True:
        engine.update_intl()
        time.sleep(60)


def rate_loop():
    """Refresh USD/PKR every 30 minutes"""
    while True:
        time.sleep(1800)
        fetch_usd_pkr()


# Start background threads
for target in [daily_loop, local_loop, intl_loop, rate_loop]:
    threading.Thread(target=target, daemon=True).start()


# ==================== API ENDPOINTS ====================

@app.route('/api/prices')
def get_all_prices():
    """Main endpoint — all national prices + metadata"""
    with store.lock:
        return jsonify({
            'usd_pkr':       store.usd_pkr,
            'local':         engine.local,
            'international': engine.intl,
            'daily_prices':  store.daily,
            'sources':       list(set(store.sources)),
            'last_update':   store.last_update,
            'timestamp':     datetime.now().isoformat()
        })


@app.route('/api/prices/city/<city_id>')
def get_city_prices(city_id):
    """City-specific prices with transport/demand adjustments"""
    city_id = city_id.lower().replace('-', '_').replace(' ', '_')
    if city_id not in CITIES:
        return jsonify({
            'error': f'City "{city_id}" not found',
            'available_cities': list(CITIES.keys())
        }), 404

    city_prices = engine.get_city_prices(city_id)
    city_info = CITIES[city_id]
    return jsonify({
        'city':          city_id,
        'city_name':     city_info['name'],
        'province':      city_info['province'],
        'prices':        city_prices,
        'usd_pkr':       store.usd_pkr,
        'last_update':   store.last_update,
        'timestamp':     datetime.now().isoformat(),
        'note':          'Prices adjusted for city-specific transport cost and local demand'
    })


@app.route('/api/cities')
def get_cities():
    """List all supported cities"""
    return jsonify({
        'cities': [
            {
                'id':       cid,
                'name':     info['name'],
                'province': info['province']
            }
            for cid, info in CITIES.items()
        ],
        'total': len(CITIES)
    })


@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status':       'running',
        'daily_count':  len(store.daily),
        'sources':      list(set(store.sources)),
        'last_update':  store.last_update,
        'usd_pkr':      store.usd_pkr,
        'cities_count': len(CITIES)
    })


@app.route('/api/daily-update')
def trigger_update():
    """Manually trigger a daily update (for testing)"""
    daily_update()
    return jsonify({'status': 'success', 'time': datetime.now().isoformat()})


@app.route('/')
def index_info():
    return jsonify({
        'name':      'Ghalla Mandi API',
        'developer': 'Muhammad Umer Farooq',
        'version':   '2.0',
        'endpoints': {
            'all_prices':     '/api/prices',
            'city_prices':    '/api/prices/city/<city_id>',
            'list_cities':    '/api/cities',
            'health':         '/api/health',
            'trigger_update': '/api/daily-update'
        }
    })


# Serve frontend (for local use)
@app.route('/dashboard')
def dashboard():
    return send_from_directory('.', 'index.html')


if __name__ == '__main__':
    print("="*60)
    print("  GHALLA MANDI BACKEND - v2.0")
    print("  Developed by: Muhammad Umer Farooq")
    print("="*60)
    print(f"  API:       http://localhost:5000")
    print(f"  Dashboard: http://localhost:5000/dashboard")
    print(f"  Cities:    http://localhost:5000/api/cities")
    print("="*60)
    app.run(host='0.0.0.0', port=5000, threaded=True)
