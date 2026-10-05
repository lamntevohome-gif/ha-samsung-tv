# Samsung TV WebSocket (HDMI) – Home Assistant

Điều khiển tivi Samsung Tizen (2016+) qua mạng LAN, **chọn ngõ HDMI**, bật/tắt, âm lượng, gửi phím bất kỳ.

## Cài đặt
1. HACS → Custom repositories → `https://github.com/lamntevohome-gif/ha-samsung-tv` (Integration).
   Hoặc copy `custom_components/samsung_tv_ws` vào `/config/custom_components/`.
2. Restart HA → Settings → Devices & services → Add → **Samsung TV WebSocket (HDMI)**.
3. Nhập IP tivi → bấm Gửi → chọn **Allow** trên tivi.

## Chuẩn bị trên tivi
- Settings → General → External Device Manager → Device Connection Manager → Access Notification: **First time only**.
- Settings → General → Network → Expert Settings → **Power On with Mobile** / IP Remote: **On** (để bật lại từ standby).
- Đặt IP tĩnh (DHCP reservation) cho tivi.

## Entity
| Entity | Chức năng |
|---|---|
| `media_player.<tv>` | Bật/tắt, volume, mute, **select_source: TV, HDMI1..HDMI4** |
| `remote.<tv>_remote` | `remote.send_command` với mã KEY_* bất kỳ |

```yaml
# Chọn HDMI2
action: media_player.select_source
target: { entity_id: media_player.samsung_tv }
data: { source: HDMI2 }

# Gửi chuỗi phím
action: remote.send_command
target: { entity_id: remote.samsung_tv_remote }
data: { command: [KEY_SOURCE, KEY_RIGHT, KEY_ENTER], delay_secs: 0.5 }
```

## Cách chọn HDMI
- **Mặc định**: gửi phím `KEY_HDMI1`…`KEY_HDMI4` qua WebSocket (wss://IP:8002).
- **Tuỳ chọn SmartThings** (Options): nhập token + device ID → dùng `setInputSource`, đọc được ngõ đang chọn. Nếu lỗi sẽ tự quay về gửi phím.

## Ghi chú
- Wake-on-LAN cần tivi cắm dây LAN; HA chạy Docker phải dùng `network_mode: host`.
- Mã phím phổ biến: KEY_POWER, KEY_HOME, KEY_RETURN, KEY_UP/DOWN/LEFT/RIGHT, KEY_ENTER, KEY_SOURCE, KEY_HDMI, KEY_HDMI1–4, KEY_VOLUP/DOWN, KEY_MUTE, KEY_CHUP/DOWN.
