# Reddit API credentials
# Get these from: https://www.reddit.com/prefs/apps
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
USER_AGENT = "male_loneliness_research/1.0 by u/YOUR_REDDIT_USERNAME"

# Search settings
QUERIES = [
    "male loneliness",
    "men lonely",
    "loneliness men",
    "man alone",
    "male isolation",
]

SUBREDDITS = [
    "lonely",
    "MensLib",
    "AskMen",
    "dating_advice",
    "self",
    "relationship_advice",
    "ForeverAlone",
    "depression",
    "socialskills",
    "AskMenOver30",
    "mensrights",
    "offmychest",
]

MIN_UPVOTES = 200
MIN_COMMENTS = 10
TIME_FILTERS = ["year", "all"]
LIMIT_PER_SEARCH = 100
OUTPUT_FILE = "male_loneliness_threads.csv"
