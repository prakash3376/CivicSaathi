/**
 * The words of the home page, the universal search, the Policy & Rights page and My Profile, in
 * English, Bengali and Hindi.
 *
 * The Bengali and Hindi are drafts by a non-native speaker and must be reviewed by a native speaker
 * before real use. `i18n/strings.test.ts` checks that every language has every entry, with the same
 * placeholders.
 */
import { createTranslator, type TranslateWith } from '@/i18n/translator'

const en = {
  // Home: the hero
  tagline: 'Know Your Benefits. Understand Your Rights.',
  heroTitle: 'Government services, made understandable.',
  heroText:
    'Discover government benefits, understand policies and know your rights – all in your own language.',
  searchLabel: 'Search or ask a question',
  searchPlaceholder: 'Search schemes, government benefits, policies or ask a question...',
  searchButton: 'Search',
  askButton: 'Ask AI Saathi',
  searchOrAsk:
    'Search finds schemes and documents. Ask AI Saathi answers a question in plain words, from the official documents.',
  examplesLabel: 'Try one of these:',
  example1: 'Which scholarships can I apply for?',
  example2: 'What government schemes are available for farmers?',
  example3: 'What is the latest government budget?',
  example4: 'What benefits are available for women?',
  example5: 'Explain this government notification.',

  // Home: the rest
  sectorsHeading: 'Find help by sector',
  sectorsIntro: 'Twelve areas of government service. Pick the one that fits what you need.',
  featuredHeading: 'Explore important government schemes',
  featuredIntro: 'Each scheme was checked against its official documents.',
  seeAllSchemes: 'See all schemes',
  updatesHeading: 'Latest Government Updates',
  updatesIntro:
    'Official documents we have read, newest first. The dates are the ones printed in the documents.',
  updatesEmpty: 'No official updates have been added yet.',
  howHeading: 'How CivicSaathi works',
  step1Title: 'Explore',
  step1Text: 'Find government schemes or policies.',
  step2Title: 'Understand',
  step2Text: 'Get AI-powered explanations in your language.',
  step3Title: 'Take Action',
  step3Text: 'Check eligibility, collect documents and visit official portals.',
  trustNote:
    'No sign-in needed. A scheme appears here only after it has been checked against an official document.',

  // A document
  docTypeGuidelines: 'Guidelines',
  docTypeSchemePage: 'Scheme page',
  docTypeFaq: 'Frequently asked questions',
  docTypeNotification: 'Notification',
  docTypeCircular: 'Circular',
  docTypeOther: 'Official document',
  docPages: '{n} passages read',

  // Search results
  resultsTitle: 'Search results',
  resultsFor: 'Results for "{q}"',
  resultsSchemes: 'Schemes',
  resultsSectors: 'Sectors',
  resultsDocuments: 'Official documents',
  resultsNone: 'Nothing matched "{q}".',
  resultsNoneHelp:
    'Try other words, browse the sectors, or ask AI Saathi, which can understand a whole question.',
  resultsEmptyQuery: 'Type a word or a question above to search.',
  resultsAskTitle: 'Ask AI Saathi instead',
  resultsAskText: 'Get an answer in plain words, with the official page it comes from.',
  resultsLoading: 'Searching…',
  resultsError: 'The search could not be completed.',
  tryAgain: 'Try again',
  reference: 'Reference: {id}',
  browseSectors: 'Browse the sectors',

  // Policy & Rights
  policyTitle: 'Policy & Rights',
  policyIntro:
    'Read the official documents behind each scheme and ask questions about them. Every answer names the document and the page it came from.',
  policyAskTitle: 'Ask about these documents',
  policyAskText:
    'Type or speak a question. If the documents do not say, you will be told so rather than given a guess.',
  policyLibrary: 'Official documents we have read',
  policySearch: 'Search the documents',
  policySearchPlaceholder: 'Title, scheme or department',
  policyNoMatch: 'No document matches. Try other words.',
  policyLoading: 'Loading the documents…',
  policyError: 'The documents could not be loaded.',
  policyEmpty: 'No documents have been added yet.',
  policySoonTitle: 'Not available yet',
  policySoon1: 'Uploading your own notification or draft policy for a plain-language explanation.',
  policySoon2: 'Comparing an older and a newer version of a policy.',
  policySoonNote:
    'We would rather say so than show a button that does nothing. For now, the documents above can be read and questioned.',

  // My Profile
  profileTitle: 'My Profile',
  profileIntro: 'You do not need an account. Everything on CivicSaathi works without signing in.',
  profileSavedHeading: 'Saved in this browser',
  profileSavedText: 'These choices stay on this device only, so that the site remembers them.',
  profileInterface: 'Interface language',
  profileAnswer: 'Answer language',
  profileSpeed: 'Reading speed',
  profileDefault: 'Not set',
  profileAuto: 'Same as the question',
  profileSlow: 'Slow',
  profileNormal: 'Normal',
  profileFast: 'Fast',
  profileClear: 'Clear saved choices',
  profileCleared: 'Saved choices cleared.',
  profileNeverHeading: 'Never saved',
  profileNever1:
    'Your answers in an eligibility check and your questions stay in memory and are gone when you leave the page.',
  profileNever2:
    'Microphone audio is not stored by us. Your browser maker’s speech service may process it.',
  profileNever3: 'We do not ask for Aadhaar, PAN or bank details.',
  profileAccountHeading: 'Sign-in (optional)',
  profileAccountText:
    'Saving schemes, eligibility profiles and reminders would need an optional account. It is not available yet, and nothing here requires one.',
} as const

export type PortalKey = keyof typeof en

const bn: Record<PortalKey, string> = {
  tagline: 'আপনার সুবিধা জানুন। আপনার অধিকার বুঝুন।',
  heroTitle: 'সরকারি পরিষেবা, সহজ ভাষায়।',
  heroText: 'সরকারি সুবিধা খুঁজে নিন, নীতি বুঝুন এবং নিজের অধিকার জানুন – সবই আপনার নিজের ভাষায়।',
  searchLabel: 'খুঁজুন বা প্রশ্ন করুন',
  searchPlaceholder: 'প্রকল্প, সরকারি সুবিধা, নীতি খুঁজুন বা প্রশ্ন করুন...',
  searchButton: 'খুঁজুন',
  askButton: 'এআই সাথীকে জিজ্ঞাসা করুন',
  searchOrAsk:
    '"খুঁজুন" প্রকল্প ও নথি খুঁজে দেয়। "এআই সাথী" সরকারি নথি থেকে সহজ কথায় প্রশ্নের উত্তর দেয়।',
  examplesLabel: 'এগুলির একটি চেষ্টা করুন:',
  example1: 'আমি কোন কোন বৃত্তির জন্য আবেদন করতে পারি?',
  example2: 'কৃষকদের জন্য কোন কোন সরকারি প্রকল্প আছে?',
  example3: 'সরকারের সর্বশেষ বাজেট কী?',
  example4: 'মহিলাদের জন্য কী কী সুবিধা আছে?',
  example5: 'এই সরকারি বিজ্ঞপ্তিটি ব্যাখ্যা করুন।',

  sectorsHeading: 'ক্ষেত্র অনুযায়ী সাহায্য খুঁজুন',
  sectorsIntro: 'সরকারি পরিষেবার বারোটি ক্ষেত্র। আপনার প্রয়োজনের সঙ্গে যেটি মেলে সেটি বেছে নিন।',
  featuredHeading: 'গুরুত্বপূর্ণ সরকারি প্রকল্প দেখুন',
  featuredIntro: 'প্রতিটি প্রকল্প তার সরকারি নথির সঙ্গে মিলিয়ে দেখা হয়েছে।',
  seeAllSchemes: 'সব প্রকল্প দেখুন',
  updatesHeading: 'সরকারের সাম্প্রতিক হালনাগাদ',
  updatesIntro: 'আমাদের পড়া সরকারি নথি, নতুনটি আগে। তারিখগুলি নথিতে ছাপা তারিখ।',
  updatesEmpty: 'এখনও কোনো সরকারি হালনাগাদ যোগ করা হয়নি।',
  howHeading: 'সিভিকসাথী কীভাবে কাজ করে',
  step1Title: 'খুঁজুন',
  step1Text: 'সরকারি প্রকল্প বা নীতি খুঁজে নিন।',
  step2Title: 'বুঝুন',
  step2Text: 'নিজের ভাষায় এআই-চালিত ব্যাখ্যা পান।',
  step3Title: 'পদক্ষেপ নিন',
  step3Text: 'যোগ্যতা দেখুন, নথি জোগাড় করুন এবং সরকারি পোর্টালে যান।',
  trustNote: 'সাইন-ইন লাগে না। সরকারি নথির সঙ্গে মিলিয়ে দেখার পরেই কোনো প্রকল্প এখানে আসে।',

  docTypeGuidelines: 'নির্দেশিকা',
  docTypeSchemePage: 'প্রকল্পের পাতা',
  docTypeFaq: 'সাধারণ প্রশ্নোত্তর',
  docTypeNotification: 'বিজ্ঞপ্তি',
  docTypeCircular: 'সার্কুলার',
  docTypeOther: 'সরকারি নথি',
  docPages: '{n}টি অংশ পড়া হয়েছে',

  resultsTitle: 'খোঁজের ফল',
  resultsFor: '"{q}"-এর ফল',
  resultsSchemes: 'প্রকল্প',
  resultsSectors: 'ক্ষেত্র',
  resultsDocuments: 'সরকারি নথি',
  resultsNone: '"{q}"-এর সঙ্গে কিছু মেলেনি।',
  resultsNoneHelp:
    'অন্য শব্দ দিন, ক্ষেত্রগুলি দেখুন, অথবা এআই সাথীকে জিজ্ঞাসা করুন, সে পুরো প্রশ্ন বুঝতে পারে।',
  resultsEmptyQuery: 'খুঁজতে উপরে একটি শব্দ বা প্রশ্ন লিখুন।',
  resultsAskTitle: 'বরং এআই সাথীকে জিজ্ঞাসা করুন',
  resultsAskText: 'সহজ কথায় উত্তর পান, সঙ্গে কোন সরকারি পাতা থেকে এসেছে তাও।',
  resultsLoading: 'খোঁজা হচ্ছে…',
  resultsError: 'খোঁজা সম্পূর্ণ করা যায়নি।',
  tryAgain: 'আবার চেষ্টা করুন',
  reference: 'রেফারেন্স: {id}',
  browseSectors: 'ক্ষেত্রগুলি দেখুন',

  policyTitle: 'নীতি ও অধিকার',
  policyIntro:
    'প্রতিটি প্রকল্পের পেছনের সরকারি নথি পড়ুন এবং সে বিষয়ে প্রশ্ন করুন। প্রতিটি উত্তরে নথি ও পাতার নাম থাকে।',
  policyAskTitle: 'এই নথিগুলি নিয়ে প্রশ্ন করুন',
  policyAskText: 'লিখে বা বলে প্রশ্ন করুন। নথিতে না থাকলে আন্দাজ না করে সে কথাই জানানো হবে।',
  policyLibrary: 'আমাদের পড়া সরকারি নথি',
  policySearch: 'নথিতে খুঁজুন',
  policySearchPlaceholder: 'শিরোনাম, প্রকল্প বা দপ্তর',
  policyNoMatch: 'কোনো নথি মেলেনি। অন্য শব্দ দিন।',
  policyLoading: 'নথি লোড হচ্ছে…',
  policyError: 'নথিগুলি লোড করা যায়নি।',
  policyEmpty: 'এখনও কোনো নথি যোগ করা হয়নি।',
  policySoonTitle: 'এখনও পাওয়া যায় না',
  policySoon1: 'সহজ ভাষায় ব্যাখ্যার জন্য নিজের বিজ্ঞপ্তি বা খসড়া নীতি আপলোড করা।',
  policySoon2: 'কোনো নীতির পুরোনো ও নতুন সংস্করণের তুলনা।',
  policySoonNote:
    'কিছু না-করা বোতাম দেখানোর চেয়ে আমরা সে কথাই বলতে চাই। এখন ওপরের নথিগুলি পড়া ও সে নিয়ে প্রশ্ন করা যায়।',

  profileTitle: 'আমার প্রোফাইল',
  profileIntro: 'অ্যাকাউন্ট লাগে না। সিভিকসাথীর সবকিছু সাইন-ইন ছাড়াই কাজ করে।',
  profileSavedHeading: 'এই ব্রাউজারে সংরক্ষিত',
  profileSavedText: 'এই পছন্দগুলি শুধু এই ডিভাইসে থাকে, যাতে সাইটটি মনে রাখতে পারে।',
  profileInterface: 'ইন্টারফেসের ভাষা',
  profileAnswer: 'উত্তরের ভাষা',
  profileSpeed: 'পড়ে শোনানোর গতি',
  profileDefault: 'ঠিক করা নেই',
  profileAuto: 'প্রশ্নের ভাষার মতো',
  profileSlow: 'ধীর',
  profileNormal: 'স্বাভাবিক',
  profileFast: 'দ্রুত',
  profileClear: 'সংরক্ষিত পছন্দ মুছুন',
  profileCleared: 'সংরক্ষিত পছন্দ মোছা হয়েছে।',
  profileNeverHeading: 'কখনও সংরক্ষণ করা হয় না',
  profileNever1:
    'যোগ্যতা যাচাইয়ে আপনার উত্তর এবং আপনার প্রশ্ন শুধু মেমরিতে থাকে, পাতা ছাড়লেই চলে যায়।',
  profileNever2:
    'মাইক্রোফোনের অডিও আমরা সংরক্ষণ করি না। আপনার ব্রাউজারের নির্মাতার স্পিচ পরিষেবা তা প্রক্রিয়া করতে পারে।',
  profileNever3: 'আমরা আধার, প্যান বা ব্যাংকের তথ্য চাই না।',
  profileAccountHeading: 'সাইন-ইন (ঐচ্ছিক)',
  profileAccountText:
    'প্রকল্প সংরক্ষণ, যোগ্যতার প্রোফাইল ও অনুস্মারকের জন্য একটি ঐচ্ছিক অ্যাকাউন্ট লাগবে। এটি এখনও নেই, আর এখানে কিছুর জন্যই অ্যাকাউন্ট লাগে না।',
}

const hi: Record<PortalKey, string> = {
  tagline: 'अपने लाभ जानें। अपने अधिकार समझें।',
  heroTitle: 'सरकारी सेवाएँ, आसान भाषा में।',
  heroText: 'सरकारी लाभ खोजें, नीतियाँ समझें और अपने अधिकार जानें – सब कुछ अपनी भाषा में।',
  searchLabel: 'खोजें या प्रश्न पूछें',
  searchPlaceholder: 'योजनाएँ, सरकारी लाभ, नीतियाँ खोजें या प्रश्न पूछें...',
  searchButton: 'खोजें',
  askButton: 'एआई साथी से पूछें',
  searchOrAsk:
    '"खोजें" योजनाएँ और दस्तावेज़ ढूँढता है। "एआई साथी" सरकारी दस्तावेज़ों से सरल शब्दों में प्रश्न का उत्तर देता है।',
  examplesLabel: 'इनमें से कोई एक आज़माएँ:',
  example1: 'किन छात्रवृत्तियों के लिए आवेदन किया जा सकता है?',
  example2: 'किसानों के लिए कौन-सी सरकारी योजनाएँ उपलब्ध हैं?',
  example3: 'सरकार का नवीनतम बजट क्या है?',
  example4: 'महिलाओं के लिए कौन-से लाभ उपलब्ध हैं?',
  example5: 'इस सरकारी अधिसूचना को समझाइए।',

  sectorsHeading: 'क्षेत्र के अनुसार सहायता खोजें',
  sectorsIntro: 'सरकारी सेवाओं के बारह क्षेत्र। अपनी ज़रूरत से जो मेल खाए, उसे चुनें।',
  featuredHeading: 'महत्वपूर्ण सरकारी योजनाएँ देखें',
  featuredIntro: 'हर योजना को उसके सरकारी दस्तावेज़ों से मिलाकर जाँचा गया है।',
  seeAllSchemes: 'सभी योजनाएँ देखें',
  updatesHeading: 'सरकार के ताज़ा अपडेट',
  updatesIntro:
    'हमारे पढ़े हुए सरकारी दस्तावेज़, नए पहले। तारीख़ें वही हैं जो दस्तावेज़ों में छपी हैं।',
  updatesEmpty: 'अभी कोई सरकारी अपडेट जोड़ा नहीं गया है।',
  howHeading: 'सिविकसाथी कैसे काम करता है',
  step1Title: 'खोजें',
  step1Text: 'सरकारी योजनाएँ या नीतियाँ खोजें।',
  step2Title: 'समझें',
  step2Text: 'अपनी भाषा में एआई से मिली व्याख्या पाएँ।',
  step3Title: 'कदम उठाएँ',
  step3Text: 'पात्रता जाँचें, दस्तावेज़ जुटाएँ और सरकारी पोर्टल पर जाएँ।',
  trustNote:
    'साइन-इन की ज़रूरत नहीं। कोई योजना यहाँ तभी आती है जब उसे सरकारी दस्तावेज़ से मिला लिया गया हो।',

  docTypeGuidelines: 'दिशानिर्देश',
  docTypeSchemePage: 'योजना का पन्ना',
  docTypeFaq: 'अक्सर पूछे जाने वाले प्रश्न',
  docTypeNotification: 'अधिसूचना',
  docTypeCircular: 'परिपत्र',
  docTypeOther: 'सरकारी दस्तावेज़',
  docPages: '{n} अंश पढ़े गए',

  resultsTitle: 'खोज के परिणाम',
  resultsFor: '"{q}" के परिणाम',
  resultsSchemes: 'योजनाएँ',
  resultsSectors: 'क्षेत्र',
  resultsDocuments: 'सरकारी दस्तावेज़',
  resultsNone: '"{q}" से कुछ नहीं मिला।',
  resultsNoneHelp:
    'दूसरे शब्द आज़माएँ, क्षेत्र देखें, या एआई साथी से पूछें, जो पूरा प्रश्न समझ सकता है।',
  resultsEmptyQuery: 'खोजने के लिए ऊपर कोई शब्द या प्रश्न लिखें।',
  resultsAskTitle: 'इसके बजाय एआई साथी से पूछें',
  resultsAskText: 'सरल शब्दों में उत्तर पाएँ, उस सरकारी पन्ने के साथ जहाँ से वह आया है।',
  resultsLoading: 'खोज रहे हैं…',
  resultsError: 'खोज पूरी नहीं हो सकी।',
  tryAgain: 'फिर से कोशिश करें',
  reference: 'संदर्भ: {id}',
  browseSectors: 'क्षेत्र देखें',

  policyTitle: 'नीति और अधिकार',
  policyIntro:
    'हर योजना के पीछे के सरकारी दस्तावेज़ पढ़ें और उनके बारे में प्रश्न पूछें। हर उत्तर में दस्तावेज़ और पन्ने का नाम होता है।',
  policyAskTitle: 'इन दस्तावेज़ों के बारे में पूछें',
  policyAskText:
    'लिखकर या बोलकर प्रश्न पूछें। अगर दस्तावेज़ों में नहीं है, तो अंदाज़ा लगाने के बजाय यही बताया जाएगा।',
  policyLibrary: 'हमारे पढ़े हुए सरकारी दस्तावेज़',
  policySearch: 'दस्तावेज़ों में खोजें',
  policySearchPlaceholder: 'शीर्षक, योजना या विभाग',
  policyNoMatch: 'कोई दस्तावेज़ नहीं मिला। दूसरे शब्द आज़माएँ।',
  policyLoading: 'दस्तावेज़ लोड हो रहे हैं…',
  policyError: 'दस्तावेज़ लोड नहीं हो सके।',
  policyEmpty: 'अभी कोई दस्तावेज़ जोड़ा नहीं गया है।',
  policySoonTitle: 'अभी उपलब्ध नहीं',
  policySoon1: 'सरल भाषा में व्याख्या के लिए अपनी अधिसूचना या मसौदा नीति अपलोड करना।',
  policySoon2: 'किसी नीति के पुराने और नए संस्करण की तुलना।',
  policySoonNote:
    'हम कुछ न करने वाला बटन दिखाने के बजाय यही बताना चाहते हैं। अभी ऊपर के दस्तावेज़ पढ़े और उनके बारे में पूछे जा सकते हैं।',

  profileTitle: 'मेरी प्रोफ़ाइल',
  profileIntro: 'खाते की ज़रूरत नहीं। सिविकसाथी पर सब कुछ साइन-इन के बिना काम करता है।',
  profileSavedHeading: 'इस ब्राउज़र में सहेजा गया',
  profileSavedText: 'ये चुनाव सिर्फ़ इसी डिवाइस पर रहते हैं, ताकि साइट इन्हें याद रख सके।',
  profileInterface: 'इंटरफ़ेस की भाषा',
  profileAnswer: 'उत्तर की भाषा',
  profileSpeed: 'पढ़कर सुनाने की गति',
  profileDefault: 'तय नहीं',
  profileAuto: 'प्रश्न की भाषा जैसी',
  profileSlow: 'धीमी',
  profileNormal: 'सामान्य',
  profileFast: 'तेज़',
  profileClear: 'सहेजे गए चुनाव हटाएँ',
  profileCleared: 'सहेजे गए चुनाव हटा दिए गए।',
  profileNeverHeading: 'कभी नहीं सहेजा जाता',
  profileNever1:
    'पात्रता जाँच में आपके उत्तर और आपके प्रश्न सिर्फ़ मेमोरी में रहते हैं, पन्ना छोड़ते ही चले जाते हैं।',
  profileNever2:
    'माइक्रोफ़ोन का ऑडियो हम सहेजते नहीं हैं। आपके ब्राउज़र बनाने वाले की स्पीच सेवा उसे प्रोसेस कर सकती है।',
  profileNever3: 'हम आधार, पैन या बैंक की जानकारी नहीं माँगते।',
  profileAccountHeading: 'साइन-इन (वैकल्पिक)',
  profileAccountText:
    'योजनाएँ सहेजने, पात्रता प्रोफ़ाइल और अनुस्मारक के लिए एक वैकल्पिक खाता चाहिए होगा। यह अभी उपलब्ध नहीं है, और यहाँ किसी चीज़ के लिए खाता ज़रूरी नहीं है।',
}

export const strings = { en, bn, hi } as const

export const translator = createTranslator<PortalKey>(strings)
export type Translate = TranslateWith<PortalKey>
