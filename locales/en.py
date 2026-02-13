"""English strings for intent-based onboarding (V1.1)."""

EN_STRINGS = {
    # === WELCOME ===
    "welcome": "Hey {name}! Welcome to Sphere",
    "welcome_event": "Hey {name}! Welcome to {event_name}",

    # === INTENT SELECTION ===
    "intent_header": "What are you looking for? (pick up to 3)",
    "intent_networking": "Networking",
    "intent_networking_desc": "business contacts, co-founders, mentors",
    "intent_friends": "Friends",
    "intent_friends_desc": "like-minded people to hang out with",
    "intent_romance": "Romance",
    "intent_romance_desc": "meaningful romantic connections",
    "intent_hookup": "Hookup",
    "intent_hookup_desc": "casual dating, fun encounters",
    "intent_done": "Done ({count}) \u2192",
    "intent_max_warning": "You can pick up to 3",

    # === MODE CHOICE ===
    "mode_header": (
        "Great! Now let's build your profile:\n\n"
        "\U0001f916 Agent (Recommended) \u2014 Chat with me naturally, I'll build your profile from the conversation (3-5 min)\n"
        "\U0001f3a4 Voice \u2014 I'll ask a few questions, just talk naturally (3-4 min)\n"
        "\U0001f4cb Quick Choices \u2014 Pick from options with buttons (1-2 min)\n"
        "\U0001f4f1 Social Media \u2014 Share a link or screenshot, I'll do the rest"
    ),
    "mode_agent": "\U0001f916 Agent (Recommended)",
    "mode_voice": "\U0001f3a4 Voice",
    "mode_buttons": "\U0001f4cb Quick Choices",
    "mode_social": "\U0001f4f1 Social Media",

    # === AGENT MODE ===
    "agent_intro": (
        "Hey! I'm your personal onboarding agent \U0001f916\n\n"
        "Let's just chat \u2014 tell me about yourself, what you're into, what brings you here. "
        "I'll ask follow-ups and build your profile from our conversation.\n\n"
        "No forms, no buttons \u2014 just talk to me like you'd talk to a friend.\n\n"
        "So... who are you? What do you do? \U0001f60a"
    ),
    "agent_processing": "\U0001f914 Thinking...",
    "agent_profile_ready": (
        "\u2728 Based on our conversation, here's the profile I built for you:\n\n{profile}\n\n"
        "How does this look?"
    ),
    "agent_continue": "Tell me more! I'm listening \U0001f60a",
    "agent_almost_done": "Almost done! Just a couple more things I'd love to know...",
    "agent_great_profile": "You've got a great profile now! Let's finalize it.",

    # === VOICE MODE ===
    "voice_stage1": "Tell me about yourself \u2014 who are you and what do you do? Just 30-60 seconds, nice and easy.",
    "voice_stage2_networking": "What kind of connections would be most valuable for you right now?",
    "voice_stage2_friends": "What do you enjoy doing in your free time?",
    "voice_stage2_romance": "What matters most to you in a partner?",
    "voice_stage2_hookup": "What's your idea of a great first date?",
    "voice_stage3": "Describe the kind of person you'd love to meet. Be as specific as you want.",
    "voice_stage4_prompt": "One more quick question: {question}",
    "voice_processing": "\U0001f3a7 Got it! Processing your voice...",
    "voice_extracted": "Here's what I got:\n\n{summary}\n\nSounds good?",
    "voice_next": "Great! Next question:",
    "voice_skip_followup": "Your profile looks complete! Let's move on.",
    "voice_confirm_yes": "\u2713 Looks good!",
    "voice_confirm_edit": "\u270f\ufe0f Edit",

    # === QUICK CHOICES MODE ===
    "qc_about": "Tell me about yourself in a few words:",
    "qc_looking_for": "What kind of connections are you looking for?",
    "qc_profession": "What do you do? (profession / company)",
    "qc_skills": "Pick your main skills:",
    "qc_can_help": "How can you help others?",
    "qc_interests": "Pick your interests (up to 5):",
    "qc_vibe": "What's your vibe?",
    "qc_gender": "Your gender:",
    "qc_interested_in": "Interested in:",
    "qc_age_range": "Preferred age range:",
    "qc_values": "What matters most in a partner? (pick 2-3)",
    "qc_hookup_vibe": "Your ideal first date vibe:",
    "qc_skip": "Skip \u2192",
    "qc_done": "Done ({count}) \u2192",

    # Vibe options
    "vibe_active": "\U0001f3c3 Active",
    "vibe_creative": "\U0001f3a8 Creative",
    "vibe_intellectual": "\U0001f9e0 Intellectual",
    "vibe_social": "\U0001f389 Social",

    # Gender options
    "gender_male": "Male",
    "gender_female": "Female",
    "gender_nonbinary": "Non-binary",

    # Interested in options
    "interested_men": "Men",
    "interested_women": "Women",
    "interested_everyone": "Everyone",

    # Age range options
    "age_18_25": "18-25",
    "age_25_35": "25-35",
    "age_35_45": "35-45",
    "age_45_plus": "45+",

    # Partner values
    "value_humor": "Humor",
    "value_ambition": "Ambition",
    "value_kindness": "Kindness",
    "value_intelligence": "Intelligence",
    "value_adventurous": "Adventurous",
    "value_family": "Family-oriented",

    # Hookup vibe
    "hookup_chill": "\U0001f377 Chill date",
    "hookup_party": "\U0001f389 Party together",
    "hookup_active": "\U0001f3cb\ufe0f Active adventure",
    "hookup_talk": "\U0001f4ac Deep talk first",

    # Skills options
    "skill_tech": "Tech",
    "skill_business": "Business",
    "skill_marketing": "Marketing",
    "skill_design": "Design",
    "skill_finance": "Finance",
    "skill_creative": "Creative",
    "skill_operations": "Operations",

    # Interest options (quick choices)
    "interest_tech": "Tech",
    "interest_sports": "Sports",
    "interest_music": "Music",
    "interest_travel": "Travel",
    "interest_food": "Food & Cooking",
    "interest_art": "Art",
    "interest_gaming": "Gaming",
    "interest_books": "Books",
    "interest_outdoors": "Outdoors",
    "interest_fitness": "Fitness",

    # === SOCIAL MEDIA MODE ===
    "social_header": (
        "Send me a link to your profile or a screenshot from any app \u2014 "
        "Instagram, LinkedIn, Tinder, Bumble, anything works!"
    ),
    "social_link_btn": "\U0001f4ce I'll send a link",
    "social_screenshot_btn": "\U0001f4f8 I'll send a screenshot",
    "social_waiting_link": "Send me the link:",
    "social_waiting_screenshot": "Send me a screenshot:",
    "social_processing": "\U0001f50d Analyzing your profile...",
    "social_extracted": (
        "Here's what I found from your {platform}:\n\n"
        "\U0001f4dd {bio}\n"
        "\U0001f3af Interests: {interests}\n"
        "\U0001f4bc {profession}\n\n"
        "Pretty good start! Let me ask 1-2 quick questions to complete your profile."
    ),
    "social_followup": "Quick question: {question}",
    "social_error": "Couldn't extract much from that. Let's try voice instead!",

    # === CITY ===
    "city_header": "What city are you in?",
    "city_other": "\U0001f30d Other...",
    "city_type": "Type your city name:",

    # === PHOTO ===
    "photo_header": "\U0001f4f8 Add a photo (helps matches recognize you)",
    "photo_skip": "Skip for now \u2192",
    "photo_saved": "Photo saved!",

    # === CONFIRM ===
    "confirm_header": "Here's your profile:",
    "confirm_looks_good": "\u2713 Looks good!",
    "confirm_edit": "\u270f\ufe0f Edit",
    "confirm_saved": "\u2728 Profile saved! Finding your matches...",

    # === POST-ONBOARDING ===
    "tip_enrich": "\U0001f4a1 Tip: Send me a voice message, screenshot, or link anytime to enrich your profile!",

    # === DAILY QUESTION ===
    "daily_header": "\U0001f4ad Daily question:",
    "daily_skip": "Skip",
    "daily_voice": "\U0001f3a4 Voice",
    "daily_reaction": "Nice! {reaction}\nWant to chat more about this? Just keep talking, I'm here :)",
    "daily_end": "Updated your profile with new insights! \u2728",
    "daily_no_more": "No more questions for today. See you tomorrow!",

    # === ENRICHMENT ===
    "enrich_voice_done": "Got it! Added {summary} to your profile.",
    "enrich_screenshot_prompt": "What is this?",
    "enrich_screenshot_profile": "\U0001f4f8 Profile photo",
    "enrich_screenshot_analyze": "\U0001f4f1 Screenshot to analyze",
    "enrich_link_done": "Imported from {platform}! {summary}",

    # === GENERIC ===
    "error_generic": "Something went wrong. Try again or type /start",
    "processing": "\u2699\ufe0f Processing...",
}
