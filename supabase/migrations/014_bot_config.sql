-- Bot configuration table for dynamic settings (menu buttons, feature toggles).
-- Managed via the Sphere Admin Dashboard Settings tab.

CREATE TABLE IF NOT EXISTS bot_config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Default menu buttons configuration
INSERT INTO bot_config (key, value) VALUES ('menu_buttons', '{
    "buttons": [
        {"id": "my_profile",     "emoji": "👤", "label_en": "Profile",        "label_ru": "Профиль",              "enabled": true,  "locked": true,  "order": 0},
        {"id": "my_events",      "emoji": "🎉", "label_en": "Events",         "label_ru": "Ивенты",               "enabled": true,  "locked": false, "order": 1},
        {"id": "my_matches",     "emoji": "💫", "label_en": "Matches",        "label_ru": "Матчи",                "enabled": true,  "locked": true,  "order": 2},
        {"id": "my_activities",  "emoji": "🎯", "label_en": "My Activities",  "label_ru": "Мои активности",       "enabled": true,  "locked": false, "order": 3},
        {"id": "my_invitations", "emoji": "📩", "label_en": "Invitations",    "label_ru": "Приглашения",          "enabled": true,  "locked": false, "order": 4},
        {"id": "vibe_new",       "emoji": "🔮", "label_en": "Check Our Vibe", "label_ru": "Проверь совместимость", "enabled": true,  "locked": false, "order": 5},
        {"id": "giveaway_info",  "emoji": "🎁", "label_en": "Giveaway",       "label_ru": "Giveaway",             "enabled": true,  "locked": false, "order": 6}
    ]
}') ON CONFLICT (key) DO NOTHING;
