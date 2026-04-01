import requests
from datetime import datetime
import time

# ============================================
# NEWS SENTIMENT ANALYZER — FREE
# Uses NewsAPI (free tier: 100 calls/day)
# Reads headlines → scores sentiment
# Trading decision changes based on news!
# ============================================
# SETUP:
# 1. Go to newsapi.org
# 2. Sign up free → get API key
# 3. Paste below
# ============================================

NEWS_API_KEY = "e77d0af3a51c411f9d9f133ee8991ebb"   # Get free at newsapi.org

# Keywords that affect trading
BULLISH_WORDS = [
    "surge", "rally", "soar", "jump", "gain", "bull",
    "record high", "breakthrough", "growth", "profit",
    "beat expectations", "strong", "upgrade", "buy"
]

BEARISH_WORDS = [
    "crash", "plunge", "drop", "fall", "bear", "loss",
    "bankruptcy", "fraud", "scandal", "lawsuit", "fine",
    "miss expectations", "weak", "downgrade", "sell",
    "layoff", "recession", "inflation", "rate hike"
]


def get_news_sentiment(query, max_articles=5):
    """
    Get news for a stock/crypto and score sentiment.
    Returns: score between -1.0 (very bearish) to +1.0 (very bullish)
    """
    try:
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q":        query,
                "apiKey":   NEWS_API_KEY,
                "pageSize": max_articles,
                "sortBy":   "publishedAt",
                "language": "en"
            },
            timeout=10
        )

        if r.status_code != 200:
            return 0.0, []   # Neutral if API fails

        articles = r.json().get("articles", [])
        if not articles:
            return 0.0, []

        total_score = 0
        headlines   = []

        for article in articles:
            title = (article.get("title") or "").lower()
            desc  = (article.get("description") or "").lower()
            text  = title + " " + desc

            bull_count = sum(1 for w in BULLISH_WORDS if w in text)
            bear_count = sum(1 for w in BEARISH_WORDS if w in text)

            article_score = (bull_count - bear_count) / max(bull_count + bear_count, 1)
            total_score  += article_score
            headlines.append({
                "title": article.get("title", ""),
                "score": round(article_score, 2)
            })

        avg_score = total_score / len(articles)
        return round(avg_score, 2), headlines

    except Exception as e:
        print(f"  ⚠️ News API error: {e}")
        return 0.0, []


def get_market_sentiment():
    """Get overall market sentiment from financial news."""
    score, _ = get_news_sentiment("stock market today")
    if score > 0.3:
        return "BULLISH", score
    elif score < -0.3:
        return "BEARISH", score
    return "NEUTRAL", score


def should_trade_based_on_news(symbol, name, planned_action):
    """
    Check news before executing a trade.
    Returns: True if news supports the trade, False if against it
    """
    score, headlines = get_news_sentiment(f"{name} stock")

    print(f"  📰 News sentiment for {name}: {score:+.2f}")
    for h in headlines[:2]:
        print(f"     → {h['title'][:60]}... (score: {h['score']:+.2f})")

    # If planning to BUY but news very negative → skip
    if planned_action == "BUY" and score < -0.4:
        print(f"  🚫 Skipping BUY — bad news sentiment ({score:.2f})")
        return False

    # If planning to SELL but news very positive → skip (might recover)
    if planned_action == "SELL" and score > 0.4:
        print(f"  ⏸️ Holding SELL — positive news ({score:.2f})")
        return False

    return True


def get_sentiment_label(score):
    if score > 0.5:   return "🟢 VERY BULLISH"
    if score > 0.2:   return "🟡 BULLISH"
    if score < -0.5:  return "🔴 VERY BEARISH"
    if score < -0.2:  return "🟠 BEARISH"
    return "⚪ NEUTRAL"


def morning_market_briefing():
    """
    Send a morning Telegram briefing with market sentiment.
    Run this at 6:30 PM IST before US market opens.
    """
    try:
        from telegram_alerts_v2 import send_alert
    except:
        def send_alert(*a, **k): pass

    print("\n📰 MORNING MARKET BRIEFING")
    print("=" * 50)

    topics = [
        ("stock market today", "Overall Market"),
        ("Bitcoin today",      "Bitcoin"),
        ("gold price today",   "Gold"),
        ("oil price today",    "Oil"),
        ("US economy today",   "US Economy"),
    ]

    briefing = "📰 MARKET BRIEFING\n━━━━━━━━━━━━━━━━━━━━\n"

    for query, label in topics:
        score, _ = get_news_sentiment(query, max_articles=3)
        label_str = get_sentiment_label(score)
        briefing += f"{label}: {label_str}\n"
        print(f"  {label}: {label_str} ({score:+.2f})")
        time.sleep(0.5)

    briefing += f"━━━━━━━━━━━━━━━━━━━━\n🕐 {datetime.now().strftime('%d %b, %H:%M IST')}"

    send_alert(briefing, "info")
    print("\n✅ Briefing sent to Telegram!")
    return briefing


if __name__ == "__main__":
    print("Testing News Sentiment...")

    if NEWS_API_KEY == "YOUR_NEWSAPI_KEY":
        print("⚠️ Set your NewsAPI key first!")
        print("   Go to newsapi.org → sign up free → get key")
    else:
        score, headlines = get_news_sentiment("Apple stock")
        print(f"Apple sentiment: {score:+.2f} — {get_sentiment_label(score)}")
        for h in headlines[:3]:
            print(f"  → {h['title'][:70]}")
        morning_market_briefing()