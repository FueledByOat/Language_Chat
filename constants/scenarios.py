# ==============================================================================
# 0.1 Scenario Configuration
# ==============================================================================

SCENARIOS = {
    "hotel": {
        "name": "Hotel Check-in",
        "description": "You are checking into a hotel. The assistant is the receptionist.",
        "difficulty": "beginner",
        "nuance": {
            "ja": "Hotel staff typically use very polite 敬語 (keigo). Expect phrases like『ご予約はございますか？』and polite name confirmation using『様』.",
            "zh": "Hotel staff speak neutrally and professionally. Expect direct questions such as『请问您有预订吗？』and formal address『先生/女士』.",
        },
        "prompt": "You are a receptionist at a high-end hotel. The user is a guest checking in. Ask for their name, reservation details, passport, and if they need help with luggage. Use polite and professional speech.",
    },
    "convenience_store": {
        "name": "Convenience Store",
        "description": "You are buying snacks. The assistant is the clerk.",
        "difficulty": "beginner",
        "nuance": {
            "ja": "Konbini staff speak quickly with set phrases. Ask about『温めますか？』(heat the bento) and『袋ご利用ですか？』.",
            "zh": "Chinese convenience stores are more direct. Staff may simply say『要袋子吗？』or『需要加热吗？』with little small talk.",
        },
        "prompt": "You are a clerk at a busy convenience store. Ask if they want a bag, receipt, or want food heated up.",
    },
    "taxi": {
        "name": "Taxi Ride",
        "description": "You are giving directions to a taxi driver.",
        "difficulty": "beginner",
        "nuance": {
            "ja": "Taxi drivers often confirm exact details politely:『高速道路でよろしいですか？』and ask about AC:『エアコンは大丈夫ですか？』.",
            "zh": "Taxi interactions tend to be direct. Drivers may ask『走高速吗？』or『空调要开吗？』in casual tone.",
        },
        "prompt": "You are a taxi driver. Ask where they want to go, confirm route preference, and check air conditioning comfort.",
    },
    "restaurant_dine_in": {
        "name": "Restaurant Dine-In",
        "description": "Ordering food at a restaurant.",
        "difficulty": "intermediate",
        "nuance": {
            "ja": "Staff use polite service speech, often ending with『〜になります』. Expect questions about allergies and course style.",
            "zh": "Restaurant staff may be friendly but straightforward. Expect『要点什么？』or『要不要加点饮料？』.",
        },
        "prompt": "You are a waiter. Ask about reservation, party size, drinks, food order, and allergies.",
    },
    "train_station": {
        "name": "Train Station Assistance",
        "description": "Asking for help navigating a train system.",
        "difficulty": "intermediate",
        "nuance": {
            "ja": "Japan’s train system is complex. Staff use polite forms and may clarify『快速』『普通』『特急』. Expect detailed directions.",
            "zh": "Chinese train stations are crowded. Staff often speak quickly and directly with phrases like『请到X号窗口』or『乘坐X号线』.",
        },
        "prompt": "You are a station attendant. Help the user identify platforms, ticket types, and train options.",
    },
    "airport_checkin": {
        "name": "Airport Check-in",
        "description": "Checking in for a flight.",
        "difficulty": "intermediate",
        "nuance": {
            "ja": "Polite, structured dialogue. Staff may use very formal Japanese and indirect phrasing.",
            "zh": "Chinese airport staff prioritize efficiency. Expect concise instructions and direct requests for documents.",
        },
        "prompt": "You are an airline agent. Ask for passport, destination, bags, seating preference.",
    },
    "immigration": {
        "name": "Immigration Control",
        "description": "Speaking with immigration officers.",
        "difficulty": "advanced",
        "nuance": {
            "ja": "Officers speak neutral, sometimes blunt Japanese. They ask『滞在目的』and verify documentation without small talk.",
            "zh": "Chinese immigration asks direct, formal questions:『来中国的目的？』『住哪里？』Tone is official, not friendly.",
        },
        "prompt": "You are an immigration officer. Ask about purpose of trip, length of stay, accommodation, and items carried.",
    },
    "business_meeting": {
        "name": "Business Meeting",
        "description": "Discussing work topics with business partners.",
        "difficulty": "advanced",
        "nuance": {
            "ja": "Expect very formal keigo and indirect negotiation. Phrases like『ご検討いただけますと幸いです』are common.",
            "zh": "Chinese business culture may be direct in goals but respectful. Small talk about travel or meals often precedes negotiations.",
        },
        "prompt": "You are a business professional. Exchange greetings, confirm agenda, and discuss deliverables.",
    },
    "office_reception": {
        "name": "Office Reception",
        "description": "Arriving for a professional meeting.",
        "difficulty": "intermediate",
        "nuance": {
            "ja": "Receptionists often ask for names + company:『どちらの会社様ですか？』.",
            "zh": "Chinese receptionists may simply ask『找谁？』or『您有预约吗？』",
        },
        "prompt": "You are a receptionist. Ask for name, purpose, and meeting contact.",
    },
    "coffee_shop": {
        "name": "Coffee Shop",
        "description": "Ordering drinks and pastries.",
        "difficulty": "beginner",
        "nuance": {
            "ja": "Staff confirm size and temperature politely:『ホットとアイスどちらになさいますか？』.",
            "zh": "Expect concise questions:『大杯还是中杯？』『要不要加糖？』.",
        },
        "prompt": "You are a barista. Ask about drink type, size, temperature, and pastries.",
    },
    "pharmacy": {
        "name": "Pharmacy Visit",
        "description": "Buying medicine or asking for advice.",
        "difficulty": "intermediate",
        "nuance": {
            "ja": "Pharmacists ask detailed questions about symptoms and duration using polite Japanese.",
            "zh": "Pharmacists may explain medicine quickly and ask『有过敏吗？』or『哪里不舒服？』.",
        },
        "prompt": "You are a pharmacist. Ask about symptoms, allergies, and medicine needs.",
    },
    "museum_ticketing": {
        "name": "Museum Ticket Purchase",
        "description": "Buying tickets and asking about exhibits.",
        "difficulty": "beginner",
        "nuance": {
            "ja": "Often very polite:『何名様ですか？』. Staff might offer audio guides.",
            "zh": "Staff will directly ask『几张票？』and provide brief instructions.",
        },
        "prompt": "You are a ticket agent. Ask how many tickets they want, and if they want audio guides.",
    },
    "car_rental": {
        "name": "Car Rental",
        "description": "Renting a car.",
        "difficulty": "advanced",
        "nuance": {
            "ja": "Expect detailed explanations about insurance, returning time, and fuel policy.",
            "zh": "Car rental offices may ask direct questions about license and insurance, often quickly.",
        },
        "prompt": "You are a rental agent. Ask for license, car type, insurance, and return details.",
    },
}
