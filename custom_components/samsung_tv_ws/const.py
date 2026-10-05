"""Constants for Samsung TV WebSocket."""

DOMAIN = "samsung_tv_ws"

CONF_TOKEN = "token"
CONF_MODEL = "model"
CONF_HDMI_COUNT = "hdmi_count"
CONF_ST_TOKEN = "smartthings_token"
CONF_ST_DEVICE_ID = "smartthings_device_id"

CLIENT_NAME = "HomeAssistant"
WS_PORT = 8002
REST_PORT = 8001

DEFAULT_HDMI_COUNT = 4

SOURCE_TV = "TV"
SOURCE_KEYS = {
    SOURCE_TV: "KEY_TV",
    "HDMI1": "KEY_HDMI1",
    "HDMI2": "KEY_HDMI2",
    "HDMI3": "KEY_HDMI3",
    "HDMI4": "KEY_HDMI4",
}
