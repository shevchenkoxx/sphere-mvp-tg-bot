-- Onboarding steps configuration — toggle individual steps on/off from the dashboard.
-- Each step has: id, label, enabled flag, and locked flag (locked = cannot be disabled).

INSERT INTO bot_config (key, value) VALUES ('onboarding_steps', '{
    "steps": [
        {"id": "photo_request",    "label_en": "Photo Request",      "label_ru": "Запрос фото",            "enabled": true, "locked": false},
        {"id": "activity_picker",  "label_en": "Activity Picker",    "label_ru": "Выбор активностей",      "enabled": true, "locked": false},
        {"id": "connection_mode",  "label_en": "Connection Mode",    "label_ru": "Режим связей",           "enabled": true, "locked": false},
        {"id": "adaptive_buttons", "label_en": "Adaptive Buttons",   "label_ru": "Адаптивные кнопки",      "enabled": true, "locked": false}
    ]
}') ON CONFLICT (key) DO NOTHING;
