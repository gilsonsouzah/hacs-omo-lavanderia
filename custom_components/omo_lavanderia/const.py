"""Constants for the Omo Lavanderia integration."""

DOMAIN = "omo_lavanderia"
API_BASE_URL = "https://api.machine-guardian.com"
APP_VERSION = "1.7.0"
APP_PLATFORM = "web"
APP_OS_VERSION = "0.0.0"
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Config entry keys
CONF_LAUNDRY_ID = "laundry_id"
CONF_LAUNDRY_NAME = "laundry_name"
CONF_CARD_ID = "card_id"
CONF_CARD_DISPLAY = "card_display"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_TOKEN_EXPIRES_AT = "token_expires_at"

# Service names
SERVICE_START_CYCLE = "start_cycle"
