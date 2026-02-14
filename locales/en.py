"""English strings for intent-based onboarding (V1.1)."""

EN_STRINGS = {
    # === WELCOME ===
    "welcome": "Hey {name}! Welcome to Sphere \u2728\nLet's find your people.",
    "welcome_event": "Hey {name}! Welcome to {event_name} \u2728\nLet's find your people here.",

    # === INTENT SELECTION ===
    "intent_header": "What brings you here? Pick up to 3 \u2014 we'll tailor everything to you.",
    "intent_networking": "Networking",
    "intent_networking_desc": "co-founders, mentors, business contacts",
    "intent_friends": "Friends",
    "intent_friends_desc": "people to hang out with & vibe together",
    "intent_romance": "Romance",
    "intent_romance_desc": "meaningful romantic connections",
    "intent_hookup": "Hookup",
    "intent_hookup_desc": "casual dates, spontaneous fun",
    "intent_done": "Done ({count}) \u2192",
    "intent_max_warning": "You can pick up to 3",

    # === MODE CHOICE ===
    "mode_header": (
        "Now let's build your profile. Pick the way that feels right:\n\n"
        "\U0001f916 <b>Agent</b> (Recommended) \u2014 Just chat with me like a friend. I'll build your profile from our conversation. ~3 min\n\n"
        "\U0001f3a4 <b>Voice</b> \u2014 I'll ask a few questions, you answer with voice or text. ~3 min\n\n"
        "\U0001f4cb <b>Quick Choices</b> \u2014 Tap through buttons & type a few things. ~1 min\n\n"
        "\U0001f4f1 <b>Social Media</b> \u2014 Drop a link or screenshot, I'll import your profile"
    ),
    "mode_agent": "\U0001f916 Agent (Recommended)",
    "mode_voice": "\U0001f3a4 Voice",
    "mode_buttons": "\U0001f4cb Quick Choices",
    "mode_social": "\U0001f4f1 Social Media",

    # === AGENT MODE ===
    "agent_intro": (
        "Let's do this \U0001f60a\n\n"
        "Just talk to me naturally \u2014 who are you, what do you do, what gets you excited?\n\n"
        "I'll learn about you through our conversation and create your profile from it. No forms, no surveys.\n\n"
        "So tell me \u2014 what's your story?"
    ),
    "agent_processing": "\U0001f914 Thinking...",
    "agent_profile_ready": (
        "\u2728 Here's the profile I built from our conversation:\n\n{profile}\n\n"
        "How does that look?"
    ),
    "agent_continue": "Tell me more! I'm all ears \U0001f60a",
    "agent_max_reached": "I feel like I know you really well now! Let me save your profile and start finding your matches.",
    "agent_almost_done": "Almost there! Just one more thing I'm curious about...",
    "agent_great_profile": "Love it \u2014 your profile is looking really solid. Let's wrap up!",

    # === VOICE MODE ===
    "voice_stage1": "Tell me about yourself \u2014 who are you, what do you do? Just 30-60 seconds, keep it natural.",
    "voice_stage2_networking": "What kind of professional connections would be most valuable for you right now?",
    "voice_stage2_friends": "What do you enjoy doing when you're not working?",
    "voice_stage2_romance": "What matters most to you in a partner?",
    "voice_stage2_hookup": "What's your idea of a perfect first date?",
    "voice_stage3": "Describe the kind of person you'd love to meet. Be as specific as you want!",
    "voice_stage4_prompt": "One last thing: {question}",
    "voice_processing": "\U0001f3a7 Got it! Processing your voice...",
    "voice_extracted": "Here's what I picked up:\n\n{summary}\n\nLook right?",
    "voice_next": "Nice! Next one:",
    "voice_skip_followup": "Looking good! Let's keep going \u2192",
    "voice_confirm_yes": "\u2713 Looks good!",
    "voice_confirm_edit": "\u270f\ufe0f Edit",

    # === QUICK CHOICES MODE ===
    "qc_about": "Tell me about yourself in a few words \u2014 what's your thing?",
    "qc_looking_for": "What kind of people do you want to meet?",
    "qc_profession": "What do you do? (job title / company)",
    "qc_skills": "What are you good at? Pick a few:",
    "qc_can_help": "How could you help someone you meet here?",
    "qc_interests": "What are you into? Pick up to 5:",
    "qc_vibe": "What's your energy?",
    "qc_gender": "Your gender:",
    "qc_interested_in": "Who are you interested in?",
    "qc_age_range": "Preferred age range:",
    "qc_values": "What matters most in a partner? Pick 2-3:",
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
        "Drop me a link to your profile or a screenshot from any app \u2014 "
        "Instagram, LinkedIn, Tinder, Bumble, whatever you've got!"
    ),
    "social_link_btn": "\U0001f4ce I'll send a link",
    "social_screenshot_btn": "\U0001f4f8 I'll send a screenshot",
    "social_waiting_link": "Paste the link here:",
    "social_waiting_screenshot": "Send me the screenshot:",
    "social_processing": "\U0001f50d Analyzing your profile...",
    "social_extracted": (
        "Here's what I found from your {platform}:\n\n"
        "\U0001f4dd {bio}\n"
        "\U0001f3af Interests: {interests}\n"
        "\U0001f4bc {profession}\n\n"
        "Great start! Let me ask 1-2 quick things to round it out."
    ),
    "social_followup": "{question}",
    "social_error": "Hmm, couldn't get much from that. Want to try a different link, or switch to another mode? Just type /start",

    # === CITY ===
    "city_header": "\U0001f30d What city are you in right now?",
    "city_other": "\U0001f30d Other...",
    "city_type": "Type your city:",

    # === PHOTO ===
    "photo_header": "\U0001f4f8 Got a photo? It helps people recognize you and makes matches feel more real.",
    "photo_skip": "Skip for now \u2192",
    "photo_saved": "\U0001f4f8 Looking good! Photo saved.",

    # === CONFIRM ===
    "confirm_header": "\U0001f44b Here's your profile \u2014 take a look:",
    "confirm_looks_good": "\u2713 Looks good!",
    "confirm_edit": "\u270f\ufe0f Edit",
    "confirm_saved": "Profile saved! Now let's find your people \U0001f680",

    # === POST-ONBOARDING ===
    "tip_enrich": "\U0001f4a1 Pro tip: You can send me a voice message, screenshot, or link anytime to make your profile richer and get better matches!",

    # === DAILY QUESTION ===
    "daily_header": "\U0001f4ad Question of the day:",
    "daily_answer": "\u270d\ufe0f Text",
    "daily_skip": "Skip",
    "daily_voice": "\U0001f3a4 Voice",
    "daily_reaction": "Nice! {reaction}\nWant to go deeper? Just keep talking, I'm here :)",
    "daily_end": "Updated your profile with new insights! \u2728",
    "daily_no_more": "That's it for today! See you tomorrow \U0001f44b",

    # === ENRICHMENT ===
    "enrich_voice_done": "Got it! Added {summary} to your profile.",
    "enrich_screenshot_prompt": "What's this?",
    "enrich_screenshot_profile": "\U0001f4f8 Profile photo",
    "enrich_screenshot_analyze": "\U0001f4f1 Screenshot to analyze",
    "enrich_link_done": "Imported from {platform}! {summary}",

    # === GENERIC ===
    "error_generic": "Oops, something went wrong. Try again or type /start to restart.",
    "processing": "\u2699\ufe0f Processing...",
}
