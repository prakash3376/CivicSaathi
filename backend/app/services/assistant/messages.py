"""The fixed texts the user reads, in English, Bengali and Hindi.

These are never produced by the model. Whatever a question says, a refusal, the legal disclaimer
and a warning about a source read exactly as written here.

The Bengali and Hindi are drafts by a non-native speaker and must be reviewed by a native speaker
before real use. ``tests/test_messages.py`` only checks that every language says the same things
with the same placeholders.
"""

from app.domain.assistant import Language

MESSAGES: dict[Language, dict[str, str]] = {
    "en": {
        # SPEC rule R6, word for word.
        "disclaimer": (
            "Informational summary, not legal advice. Check the official document before acting."
        ),
        "not_covered": (
            "The official documents I have do not say this, so I cannot answer it. "
            "Please check the official website or helpline of the scheme."
        ),
        "refused_injection": (
            "I can only answer questions about government schemes, services and budgets, "
            "from the official documents. "
            "Ask about who can get something, documents, amounts or deadlines."
        ),
        "refused_forgery": (
            "I can't help with faking documents or getting around eligibility checks. "
            "I can explain what the official rules require."
        ),
        "blocked": (
            "The AI service declined to answer this question. Try asking it in a different way."
        ),
        "llm_fallback": (
            "The AI service is not answering right now, so no explanation can be written. "
            "Below are the parts of the official documents that best match your question, "
            "exactly as they are written. Read them with care, or try again in a minute."
        ),
        # General help is not an official statement: these words say so before it is read.
        "guidance_intro": (
            "I could not find this in the official documents I have, so here is some general "
            "help instead. It is not from an official document, so please confirm it with "
            "the local office or the helpline."
        ),
        "off_topic": (
            "I can help best with government schemes, services and your rights, such as "
            "scholarships, pensions, ration cards or support for farmers. Ask me about any of "
            "those and I will do my best."
        ),
        "smalltalk_greeting": (
            "Hello! I am CivicSaathi. I can help you understand government schemes, documents "
            "and your rights. What would you like to know?"
        ),
        "smalltalk_thanks": "You are welcome! Is there anything else I can help you with?",
        "smalltalk_bye": "Goodbye, and take care! Come back any time you have a question.",
        "smalltalk_about": (
            "I am CivicSaathi. I explain government schemes, services and your rights in "
            "simple words. You can ask me who can get a scheme, which papers to carry, or how "
            "to apply."
        ),
        "warn_stale": (
            "{title} is dated {date}, more than 12 months ago. "
            "It may have been replaced; check the official website."
        ),
        "warn_date_unknown": (
            "No date could be found on {title}. Check that it is the current version."
        ),
        "warn_verification_due": "We last checked {title} on {date}; it is due for a new check.",
        "warn_scanned": (
            "{title} was read from a scanned copy, so figures may be misread. "
            "Check the numbers in the original document."
        ),
        "warn_sanitized": (
            "Part of {title} was left out because it contained instructions aimed at an AI system."
        ),
        "warn_claims_removed": (
            "Some statements could not be matched to the official documents and were removed."
        ),
        "warn_language_fallback": (
            "Answers are available in English, Hindi and Bengali only, "
            "so this answer is in English."
        ),
        "warn_personal_data": (
            "Personal numbers were removed from your question. "
            "Please do not share ID, bank or phone numbers."
        ),
    },
    "bn": {
        "disclaimer": (
            "এটি শুধুমাত্র তথ্যমূলক সারসংক্ষেপ, আইনি পরামর্শ নয়। "
            "কোনো পদক্ষেপ নেওয়ার আগে সরকারি নথিটি মিলিয়ে দেখুন।"
        ),
        "not_covered": (
            "আমার কাছে থাকা সরকারি নথিগুলিতে এ বিষয়ে কিছু বলা নেই, তাই আমি উত্তর দিতে পারছি না। "
            "অনুগ্রহ করে প্রকল্পের সরকারি ওয়েবসাইট বা হেল্পলাইন দেখুন।"
        ),
        "refused_injection": (
            "আমি শুধু সরকারি প্রকল্প, পরিষেবা ও বাজেট সম্পর্কে সরকারি নথি থেকে প্রশ্নের উত্তর দিতে পারি। "
            "কারা পেতে পারেন, প্রয়োজনীয় নথি, টাকার পরিমাণ বা শেষ তারিখ সম্পর্কে জিজ্ঞাসা করুন।"
        ),
        "refused_forgery": (
            "নথি জাল করা বা যোগ্যতা যাচাই এড়ানোর ব্যাপারে আমি সাহায্য করতে পারি না। "
            "সরকারি নিয়মে কী প্রয়োজন, তা আমি বুঝিয়ে বলতে পারি।"
        ),
        "blocked": "এআই পরিষেবাটি এই প্রশ্নের উত্তর দিতে রাজি হয়নি। প্রশ্নটি অন্যভাবে করে দেখুন।",
        "llm_fallback": (
            "এআই পরিষেবা এখন উত্তর দিচ্ছে না, তাই ব্যাখ্যা লেখা যাচ্ছে না। "
            "নিচে সরকারি নথির যে অংশগুলি আপনার প্রশ্নের সবচেয়ে কাছাকাছি, "
            "সেগুলি নথিতে যেমন লেখা আছে তেমনই দেওয়া হলো। "
            "মন দিয়ে পড়ুন, অথবা এক মিনিট পরে আবার চেষ্টা করুন।"
        ),
        "guidance_intro": (
            "আমার কাছে থাকা সরকারি নথিতে এটি খুঁজে পাইনি, তাই তার বদলে সাধারণ কিছু সাহায্যের কথা বলছি। "
            "এটি কোনো সরকারি নথি থেকে নেওয়া নয়, তাই স্থানীয় অফিস বা হেল্পলাইনে মিলিয়ে নেবেন।"
        ),
        "off_topic": (
            "সরকারি প্রকল্প, পরিষেবা আর আপনার অধিকার নিয়ে আমি সবচেয়ে ভালো সাহায্য করতে পারি, "
            "যেমন বৃত্তি, পেনশন, রেশন কার্ড বা চাষিদের সহায়তা। এসব নিয়ে জিজ্ঞাসা করুন, আমি চেষ্টা করব।"
        ),
        "smalltalk_greeting": (
            "নমস্কার! আমি সিভিকসাথী। সরকারি প্রকল্প, নথি আর আপনার অধিকার বুঝতে আমি সাহায্য করতে পারি। "
            "আপনি কী জানতে চান?"
        ),
        "smalltalk_thanks": "আপনাকেও ধন্যবাদ! আর কিছু নিয়ে সাহায্য লাগলে বলুন।",
        "smalltalk_bye": "ঠিক আছে, ভালো থাকবেন! যখন ইচ্ছা আবার প্রশ্ন করবেন।",
        "smalltalk_about": (
            "আমি সিভিকসাথী। সহজ ভাষায় সরকারি প্রকল্প, পরিষেবা আর আপনার অধিকার বুঝিয়ে দিই। "
            "কারা কোন প্রকল্প পেতে পারেন, কোন কাগজ লাগে বা কীভাবে আবেদন করবেন, জিজ্ঞাসা করতে পারেন।"
        ),
        "warn_stale": (
            "{title} নথিটির তারিখ {date}, অর্থাৎ 12 মাসের বেশি পুরোনো। "
            "এটি বদলে গিয়ে থাকতে পারে; সরকারি ওয়েবসাইটে মিলিয়ে নিন।"
        ),
        "warn_date_unknown": (
            "{title} নথিতে কোনো তারিখ পাওয়া যায়নি। এটিই সর্বশেষ সংস্করণ কি না, মিলিয়ে নিন।"
        ),
        "warn_verification_due": (
            "{title} নথিটি আমরা শেষবার {date} তারিখে যাচাই করেছি; নতুন করে যাচাইয়ের সময় হয়েছে।"
        ),
        "warn_scanned": (
            "{title} নথিটি স্ক্যান করা কপি থেকে পড়া হয়েছে, তাই সংখ্যা ভুল পড়া হয়ে থাকতে পারে। "
            "মূল নথিতে সংখ্যাগুলি মিলিয়ে নিন।"
        ),
        "warn_sanitized": (
            "{title} নথির একটি অংশ বাদ দেওয়া হয়েছে, কারণ তাতে এআই-কে উদ্দেশ করে লেখা নির্দেশ ছিল।"
        ),
        "warn_claims_removed": ("কিছু বক্তব্য সরকারি নথির সঙ্গে মেলানো যায়নি, তাই সেগুলি বাদ দেওয়া হয়েছে।"),
        "warn_language_fallback": (
            "উত্তর শুধু ইংরেজি, হিন্দি ও বাংলায় পাওয়া যায়, তাই এই উত্তর ইংরেজিতে দেওয়া হয়েছে।"
        ),
        "warn_personal_data": (
            "আপনার প্রশ্ন থেকে পরিচয় বা যোগাযোগের নম্বর সরানো হয়েছে। অনুগ্রহ করে এসব নম্বর শেয়ার করবেন না।"
        ),
    },
    "hi": {
        "disclaimer": (
            "यह केवल जानकारी के लिए सारांश है, कानूनी सलाह नहीं। "
            "कोई भी कदम उठाने से पहले सरकारी दस्तावेज़ से मिलान कर लें।"
        ),
        "not_covered": (
            "मेरे पास मौजूद सरकारी दस्तावेज़ों में यह बात नहीं कही गई है, इसलिए इसका उत्तर नहीं दिया जा सकता। "
            "कृपया योजना की सरकारी वेबसाइट या हेल्पलाइन देखें।"
        ),
        "refused_injection": (
            "केवल सरकारी योजनाओं, सेवाओं और बजट के बारे में सरकारी दस्तावेज़ों से प्रश्नों के उत्तर दिए जा सकते हैं। "
            "कौन पा सकता है, ज़रूरी दस्तावेज़, राशि या अंतिम तिथि के बारे में पूछें।"
        ),
        "refused_forgery": (
            "दस्तावेज़ों में जालसाज़ी करने या पात्रता की जाँच से बचने में सहायता नहीं की जा सकती। "
            "सरकारी नियमों में क्या आवश्यक है, यह समझाया जा सकता है।"
        ),
        "blocked": ("एआई सेवा ने इस प्रश्न का उत्तर देने से मना कर दिया। कृपया प्रश्न को दूसरे ढंग से पूछकर देखें।"),
        "llm_fallback": (
            "एआई सेवा अभी उत्तर नहीं दे रही, इसलिए व्याख्या नहीं लिखी जा सकती। "
            "नीचे सरकारी दस्तावेज़ों के वे अंश दिए गए हैं जो आपके प्रश्न से सबसे अधिक मिलते हैं, "
            "जैसे वे दस्तावेज़ में लिखे हैं। "
            "ध्यान से पढ़ें, या एक मिनट बाद फिर कोशिश करें।"
        ),
        "guidance_intro": (
            "मेरे पास मौजूद सरकारी दस्तावेज़ों में यह बात नहीं मिली, "
            "इसलिए उसकी जगह कुछ सामान्य मदद दी जा रही है। "
            "यह किसी सरकारी दस्तावेज़ से नहीं ली गई है, इसलिए स्थानीय कार्यालय या हेल्पलाइन से इसकी पुष्टि कर लें।"
        ),
        "off_topic": (
            "सरकारी योजनाओं, सेवाओं और आपके अधिकारों, जैसे छात्रवृत्ति, पेंशन, राशन कार्ड या किसानों की सहायता, "
            "के बारे में पूछिए; इन्हीं विषयों पर सबसे अच्छी मदद मिल पाएगी।"
        ),
        "smalltalk_greeting": (
            "नमस्ते! मैं सिविकसाथी हूँ। सरकारी योजनाओं, दस्तावेज़ों और आपके अधिकारों को समझने में आपकी मदद होगी। "
            "आप क्या जानना चाहेंगे?"
        ),
        "smalltalk_thanks": "आपका भी धन्यवाद! और कुछ पूछना हो तो बताइए।",
        "smalltalk_bye": "ठीक है, अपना ध्यान रखिए! जब चाहें फिर पूछिए।",
        "smalltalk_about": (
            "मैं सिविकसाथी हूँ। यहाँ आसान भाषा में सरकारी योजनाओं, सेवाओं और आपके अधिकारों की जानकारी मिलती है। "
            "पूछिए कि कौन-सी योजना कौन पा सकता है, कौन-से कागज़ चाहिए या आवेदन कैसे करें।"
        ),
        "warn_stale": (
            "{title} पर {date} की तारीख है, यानी यह 12 महीने से अधिक पुराना है। "
            "हो सकता है इसकी जगह नया दस्तावेज़ आ गया हो; सरकारी वेबसाइट पर जाँच लें।"
        ),
        "warn_date_unknown": ("{title} पर कोई तारीख नहीं मिली। जाँच लें कि यही नवीनतम संस्करण है।"),
        "warn_verification_due": (
            "हमने {title} को आख़िरी बार {date} को जाँचा था; दोबारा जाँचने का समय हो गया है।"
        ),
        "warn_scanned": (
            "{title} स्कैन की गई प्रति से पढ़ा गया है, इसलिए अंक ग़लत पढ़े गए हो सकते हैं। "
            "मूल दस्तावेज़ में अंकों की जाँच कर लें।"
        ),
        "warn_sanitized": (
            "{title} का एक हिस्सा हटा दिया गया, क्योंकि उसमें एआई प्रणाली को संबोधित निर्देश थे।"
        ),
        "warn_claims_removed": ("कुछ कथन सरकारी दस्तावेज़ों से मेल नहीं खाए, इसलिए उन्हें हटा दिया गया।"),
        "warn_language_fallback": (
            "उत्तर केवल अंग्रेज़ी, हिन्दी और बंगाली में उपलब्ध हैं, इसलिए यह उत्तर अंग्रेज़ी में दिया गया है।"
        ),
        "warn_personal_data": (
            "आपके प्रश्न से व्यक्तिगत नंबर हटा दिए गए हैं। कृपया पहचान, बैंक या फ़ोन नंबर साझा न करें।"
        ),
    },
}


def say(language: Language, key: str, **fields: str) -> str:
    """The text for ``key`` in ``language``, with its placeholders filled in."""
    return MESSAGES[language][key].format(**fields)
