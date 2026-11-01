/**
 * The words of the sector pages and of the scheme explorer, in English, Bengali and Hindi: the name
 * and description of each of the twelve sectors, and the search, filters and empty states.
 *
 * The Bengali and Hindi are drafts by a non-native speaker and must be reviewed by a native speaker
 * before real use. `i18n/strings.test.ts` checks that every language has every entry, with the same
 * placeholders.
 */
import { createTranslator, type TranslateWith } from '@/i18n/translator'

const en = {
  // The twelve sectors
  educationTitle: 'Education & Scholarships',
  educationText:
    'Scholarships, student loans, fee assistance, educational support and skill development.',
  healthTitle: 'Healthcare & Medical',
  healthText:
    'Government health insurance, free healthcare, medical assistance, maternity benefits and public health programmes.',
  agricultureTitle: 'Agriculture & Farmers',
  agricultureText:
    'Farmer financial assistance, crop insurance, agricultural subsidies, irrigation and farming support.',
  womenChildTitle: 'Women & Child Development',
  womenChildText:
    "Women's welfare, maternity assistance, child nutrition, girls' education and family support.",
  employmentTitle: 'Employment & Skill Development',
  employmentText:
    'Employment programmes, vocational training, skill development, apprenticeships and job assistance.',
  housingTitle: 'Housing & Basic Amenities',
  housingText:
    'Housing assistance, electricity subsidies, drinking water, sanitation and related government services.',
  socialWelfareTitle: 'Social Welfare & Pensions',
  socialWelfareText:
    'Senior citizen pensions, disability assistance, social security, financial aid and welfare programmes.',
  businessTitle: 'Business & MSME',
  businessText:
    'Business loans, entrepreneurship schemes, startup assistance, MSME support and subsidies.',
  transportTitle: 'Transport & Infrastructure',
  transportText:
    'Transport-related public services, infrastructure schemes and relevant citizen facilities.',
  budgetTitle: 'Budget & Economy',
  budgetText:
    'Union Budget, State Budget, financial allocations, taxation updates, economic policies and their impact on citizens.',
  environmentTitle: 'Environment & Energy',
  environmentText:
    'Solar energy, renewable energy, environmental programmes, clean energy and electricity-related assistance.',
  publicServicesTitle: 'Public Services & Citizen Rights',
  publicServicesText:
    'Public certificates, important citizen services, government regulations, legal rights and access to public institutions.',

  // Explore schemes
  exploreTitle: 'Explore schemes',
  exploreIntro:
    'Choose a sector, or search every scheme we have checked against its official documents.',
  sectorsHeading: 'Browse by sector',
  allSchemesHeading: 'All verified schemes',
  openSector: 'Open',
  schemeCountOne: '1 verified scheme',
  schemeCountMany: '{n} verified schemes',
  schemeCountNone: 'Being added',

  // A sector page
  allSectors: 'All sectors',
  sectorIntroNote:
    'Every scheme here was read from its official documents. Open one for who can get it, what to gather and how to apply.',
  schemesInSector: 'Schemes in this sector',
  checkerHint:
    'To find out whether you may qualify, open "Check if I am eligible" on a scheme. You can skip any question.',
  emptyTitle: 'Verified information is being added to this category.',
  emptyText:
    'We show a scheme only after it has been checked against an official document, so this page has none yet. Meanwhile you can ask AI Saathi, or explore the sectors that already have schemes.',
  budgetNote:
    'Budget figures are not schemes. A separate budget section, with allocations, revised estimates and actual spending kept apart, is being prepared.',
  askSectorTitle: 'Ask AI Saathi about {sector}',
  askSectorText:
    'Ask in your own words, by typing or speaking. Answers come only from the official documents we have, with the page they came from.',
  askSectorButton: 'Ask a question',
  questionsTitle: 'Questions you can ask',
  documentsTitle: 'Official documents for this sector',
  documentsEmpty: 'No official documents for this sector have been added yet.',

  // Search and filters
  searchLabel: 'Search schemes',
  searchPlaceholder: 'Scheme name, department or who it is for',
  levelLabel: 'Run by',
  levelAll: 'Central and State',
  levelCentral: 'Central government',
  levelState: 'State government',
  stateLabel: 'State',
  stateAll: 'All states',
  shownOne: 'Showing 1 scheme',
  shownMany: 'Showing {n} schemes',
  noMatch: 'No scheme matches these filters. Try fewer words, or clear the filters.',
  clearFilters: 'Clear filters',
  loading: 'Loading…',
  loadError: 'The schemes could not be loaded.',
  tryAgain: 'Try again',
  reference: 'Reference: {id}',
  notFoundTitle: 'Sector not found',
  notFoundText: 'There is no sector at this address.',
  scopeSector:
    'Looking first at the official documents about {sector}. Other topics are still answered.',
  scopeClear: 'Ask about everything',
  budgetHeading: 'What the budget documents say',
  budgetIntro:
    'These figures are copied from the official budget documents. A Budget Estimate is a plan. A Revised Estimate is the updated plan. Actual spending is money that was really spent. They are shown apart and never mixed.',
  basisBudget: 'Budget Estimate',
  basisRevised: 'Revised Estimate',
  basisActual: 'Actual spending',
  planNote:
    'These are plans or estimates. They are not money already spent, or money already received by citizens.',
  unitCrore: 'crore',
  unitLakhCrore: 'lakh crore',
  unitPercent: 'per cent',
  budgetOf: 'Budget {year}',
  figuresHeading: 'Figures',
  meaningHeading: 'What it means',
  announcementsHeading: 'What the document announces',
  budgetEmpty: 'No budget records have been added yet.',
  budgetError: 'The budget records could not be loaded.',
  budgetKindTax: 'Tax',
  budgetKindAnnouncement: 'Announcement',
  budgetKindAllocation: 'Allocation',
  budgetAskCitizens: 'What does this budget mean for ordinary citizens?',
  budgetShown: '{n} budget records',
  budgetOne: '1 budget record',
  openInSector: 'Budget records for {sector}',
  englishOnly:
    'The details are in English, as in the official documents. Ask AI Saathi in your own language.',
  centralBudget: 'Union (central) budget',
  stateBudget: 'State budget: {state}',
} as const

export type SectorStringKey = keyof typeof en

const bn: Record<SectorStringKey, string> = {
  educationTitle: 'শিক্ষা ও বৃত্তি',
  educationText: 'বৃত্তি, ছাত্রঋণ, ফি সহায়তা, শিক্ষাগত সহায়তা ও দক্ষতা উন্নয়ন।',
  healthTitle: 'স্বাস্থ্য ও চিকিৎসা',
  healthText:
    'সরকারি স্বাস্থ্য বিমা, বিনামূল্যে স্বাস্থ্যসেবা, চিকিৎসা সহায়তা, মাতৃত্বকালীন সুবিধা ও জনস্বাস্থ্য কর্মসূচি।',
  agricultureTitle: 'কৃষি ও কৃষক',
  agricultureText: 'কৃষকদের আর্থিক সহায়তা, ফসল বিমা, কৃষি ভর্তুকি, সেচ ও চাষবাসে সহায়তা।',
  womenChildTitle: 'নারী ও শিশু উন্নয়ন',
  womenChildText: 'নারীকল্যাণ, মাতৃত্বকালীন সহায়তা, শিশুপুষ্টি, কন্যাশিক্ষা ও পরিবারের সহায়তা।',
  employmentTitle: 'কর্মসংস্থান ও দক্ষতা উন্নয়ন',
  employmentText:
    'কর্মসংস্থান কর্মসূচি, বৃত্তিমূলক প্রশিক্ষণ, দক্ষতা উন্নয়ন, শিক্ষানবিশি ও চাকরিতে সহায়তা।',
  housingTitle: 'আবাসন ও মৌলিক সুবিধা',
  housingText: 'আবাসন সহায়তা, বিদ্যুৎ ভর্তুকি, পানীয় জল, স্যানিটেশন ও সংশ্লিষ্ট সরকারি পরিষেবা।',
  socialWelfareTitle: 'সমাজকল্যাণ ও পেনশন',
  socialWelfareText:
    'প্রবীণ নাগরিকদের পেনশন, প্রতিবন্ধী সহায়তা, সামাজিক সুরক্ষা, আর্থিক সাহায্য ও কল্যাণ কর্মসূচি।',
  businessTitle: 'ব্যবসা ও এমএসএমই',
  businessText: 'ব্যবসায়িক ঋণ, উদ্যোক্তা প্রকল্প, স্টার্টআপ সহায়তা, এমএসএমই সহায়তা ও ভর্তুকি।',
  transportTitle: 'পরিবহন ও পরিকাঠামো',
  transportText: 'পরিবহন-সংক্রান্ত সরকারি পরিষেবা, পরিকাঠামো প্রকল্প ও নাগরিক সুবিধা।',
  budgetTitle: 'বাজেট ও অর্থনীতি',
  budgetText:
    'কেন্দ্রীয় বাজেট, রাজ্য বাজেট, আর্থিক বরাদ্দ, কর-সংক্রান্ত হালনাগাদ, অর্থনৈতিক নীতি ও নাগরিকদের উপর তার প্রভাব।',
  environmentTitle: 'পরিবেশ ও জ্বালানি',
  environmentText:
    'সৌরশক্তি, নবীকরণযোগ্য শক্তি, পরিবেশ কর্মসূচি, পরিচ্ছন্ন জ্বালানি ও বিদ্যুৎ-সংক্রান্ত সহায়তা।',
  publicServicesTitle: 'জনসেবা ও নাগরিক অধিকার',
  publicServicesText:
    'সরকারি শংসাপত্র, গুরুত্বপূর্ণ নাগরিক পরিষেবা, সরকারি বিধি, আইনি অধিকার ও সরকারি প্রতিষ্ঠানে প্রবেশাধিকার।',

  exploreTitle: 'প্রকল্প খুঁজুন',
  exploreIntro: 'একটি ক্ষেত্র বেছে নিন, অথবা সরকারি নথির সঙ্গে মিলিয়ে দেখা সব প্রকল্পে খুঁজুন।',
  sectorsHeading: 'ক্ষেত্র অনুযায়ী দেখুন',
  allSchemesHeading: 'যাচাই করা সব প্রকল্প',
  openSector: 'খুলুন',
  schemeCountOne: 'যাচাই করা 1টি প্রকল্প',
  schemeCountMany: 'যাচাই করা {n}টি প্রকল্প',
  schemeCountNone: 'যোগ করা হচ্ছে',

  allSectors: 'সব ক্ষেত্র',
  sectorIntroNote:
    'এখানকার প্রতিটি প্রকল্প সরকারি নথি থেকে পড়া। কে পাবেন, কী জোগাড় করবেন এবং কীভাবে আবেদন করবেন, জানতে একটি খুলুন।',
  schemesInSector: 'এই ক্ষেত্রের প্রকল্প',
  checkerHint:
    'আপনি যোগ্য কি না জানতে কোনো প্রকল্পে "আমি কি যোগ্য দেখুন" খুলুন। যে কোনো প্রশ্ন বাদ দিতে পারেন।',
  emptyTitle: 'এই বিভাগে যাচাই করা তথ্য যোগ করা হচ্ছে।',
  emptyText:
    'সরকারি নথির সঙ্গে মিলিয়ে দেখার পরেই আমরা প্রকল্প দেখাই, তাই এই পাতায় এখনও কিছু নেই। ততক্ষণ আপনি এআই সাথীকে প্রশ্ন করতে পারেন, অথবা যেসব ক্ষেত্রে প্রকল্প আছে সেগুলি দেখতে পারেন।',
  budgetNote:
    'বাজেটের অঙ্ক প্রকল্প নয়। বরাদ্দ, সংশোধিত অনুমান ও প্রকৃত ব্যয় আলাদা রেখে একটি পৃথক বাজেট বিভাগ তৈরি হচ্ছে।',
  askSectorTitle: '{sector} নিয়ে এআই সাথীকে প্রশ্ন করুন',
  askSectorText:
    'নিজের ভাষায় লিখে বা বলে প্রশ্ন করুন। উত্তর আসে শুধু আমাদের কাছে থাকা সরকারি নথি থেকে, কোন পাতা থেকে এসেছে তা-সহ।',
  askSectorButton: 'প্রশ্ন করুন',
  questionsTitle: 'যেসব প্রশ্ন করতে পারেন',
  documentsTitle: 'এই ক্ষেত্রের সরকারি নথি',
  documentsEmpty: 'এই ক্ষেত্রের কোনো সরকারি নথি এখনও যোগ করা হয়নি।',

  searchLabel: 'প্রকল্প খুঁজুন',
  searchPlaceholder: 'প্রকল্পের নাম, দপ্তর বা কাদের জন্য',
  levelLabel: 'পরিচালনায়',
  levelAll: 'কেন্দ্র ও রাজ্য',
  levelCentral: 'কেন্দ্রীয় সরকার',
  levelState: 'রাজ্য সরকার',
  stateLabel: 'রাজ্য',
  stateAll: 'সব রাজ্য',
  shownOne: '1টি প্রকল্প দেখানো হচ্ছে',
  shownMany: '{n}টি প্রকল্প দেখানো হচ্ছে',
  noMatch: 'এই ফিল্টারে কোনো প্রকল্প মেলেনি। কম শব্দ দিন, অথবা ফিল্টার মুছুন।',
  clearFilters: 'ফিল্টার মুছুন',
  loading: 'লোড হচ্ছে…',
  loadError: 'প্রকল্পগুলি লোড করা যায়নি।',
  tryAgain: 'আবার চেষ্টা করুন',
  reference: 'রেফারেন্স: {id}',
  notFoundTitle: 'ক্ষেত্রটি পাওয়া যায়নি',
  notFoundText: 'এই ঠিকানায় কোনো ক্ষেত্র নেই।',
  scopeSector: 'প্রথমে {sector} নিয়ে সরকারি নথি দেখা হচ্ছে। অন্য বিষয়েও উত্তর দেওয়া হবে।',
  scopeClear: 'সব বিষয়ে জিজ্ঞাসা করুন',
  budgetHeading: 'বাজেটের নথি কী বলছে',
  budgetIntro:
    'এই অঙ্কগুলি সরকারি বাজেট নথি থেকে নেওয়া। বাজেট অনুমান হলো পরিকল্পনা। সংশোধিত অনুমান হলো হালনাগাদ পরিকল্পনা। প্রকৃত ব্যয় হলো যে টাকা সত্যিই খরচ হয়েছে। এগুলি আলাদা করে দেখানো হয়, কখনও মেশানো হয় না।',
  basisBudget: 'বাজেট অনুমান',
  basisRevised: 'সংশোধিত অনুমান',
  basisActual: 'প্রকৃত ব্যয়',
  planNote:
    'এগুলি পরিকল্পনা বা অনুমান। এগুলি খরচ হয়ে যাওয়া টাকা নয়, বা নাগরিকদের হাতে পৌঁছে যাওয়া টাকাও নয়।',
  unitCrore: 'কোটি',
  unitLakhCrore: 'লক্ষ কোটি',
  unitPercent: 'শতাংশ',
  budgetOf: 'বাজেট {year}',
  figuresHeading: 'অঙ্ক',
  meaningHeading: 'এর অর্থ কী',
  announcementsHeading: 'নথি যা ঘোষণা করেছে',
  budgetEmpty: 'এখনও কোনো বাজেট রেকর্ড যোগ করা হয়নি।',
  budgetError: 'বাজেট রেকর্ড লোড করা যায়নি।',
  budgetKindTax: 'কর',
  budgetKindAnnouncement: 'ঘোষণা',
  budgetKindAllocation: 'বরাদ্দ',
  budgetAskCitizens: 'এই বাজেট সাধারণ নাগরিকদের কাছে কী অর্থ বহন করে?',
  budgetShown: '{n}টি বাজেট রেকর্ড',
  budgetOne: '1টি বাজেট রেকর্ড',
  openInSector: '{sector}-এর বাজেট রেকর্ড',
  englishOnly: 'বিবরণ ইংরেজিতে, সরকারি নথিতে যেমন আছে। নিজের ভাষায় এআই সাথীকে জিজ্ঞাসা করুন।',
  centralBudget: 'কেন্দ্রীয় বাজেট',
  stateBudget: 'রাজ্য বাজেট: {state}',
}

const hi: Record<SectorStringKey, string> = {
  educationTitle: 'शिक्षा और छात्रवृत्ति',
  educationText: 'छात्रवृत्ति, छात्र ऋण, शुल्क सहायता, शैक्षिक सहायता और कौशल विकास।',
  healthTitle: 'स्वास्थ्य और चिकित्सा',
  healthText:
    'सरकारी स्वास्थ्य बीमा, मुफ़्त स्वास्थ्य सेवा, चिकित्सा सहायता, मातृत्व लाभ और सार्वजनिक स्वास्थ्य कार्यक्रम।',
  agricultureTitle: 'कृषि और किसान',
  agricultureText: 'किसानों को आर्थिक सहायता, फसल बीमा, कृषि सब्सिडी, सिंचाई और खेती में सहयोग।',
  womenChildTitle: 'महिला और बाल विकास',
  womenChildText: 'महिला कल्याण, मातृत्व सहायता, बाल पोषण, बालिका शिक्षा और परिवार सहयोग।',
  employmentTitle: 'रोज़गार और कौशल विकास',
  employmentText:
    'रोज़गार कार्यक्रम, व्यावसायिक प्रशिक्षण, कौशल विकास, अप्रेंटिसशिप और नौकरी में सहायता।',
  housingTitle: 'आवास और बुनियादी सुविधाएँ',
  housingText: 'आवास सहायता, बिजली सब्सिडी, पेयजल, स्वच्छता और संबंधित सरकारी सेवाएँ।',
  socialWelfareTitle: 'समाज कल्याण और पेंशन',
  socialWelfareText:
    'वरिष्ठ नागरिक पेंशन, दिव्यांग सहायता, सामाजिक सुरक्षा, आर्थिक सहायता और कल्याण कार्यक्रम।',
  businessTitle: 'व्यापार और एमएसएमई',
  businessText: 'व्यावसायिक ऋण, उद्यमिता योजनाएँ, स्टार्टअप सहायता, एमएसएमई सहयोग और सब्सिडी।',
  transportTitle: 'परिवहन और बुनियादी ढाँचा',
  transportText: 'परिवहन से जुड़ी सार्वजनिक सेवाएँ, बुनियादी ढाँचा योजनाएँ और नागरिक सुविधाएँ।',
  budgetTitle: 'बजट और अर्थव्यवस्था',
  budgetText:
    'केंद्रीय बजट, राज्य बजट, वित्तीय आवंटन, कर संबंधी अपडेट, आर्थिक नीतियाँ और नागरिकों पर उनका प्रभाव।',
  environmentTitle: 'पर्यावरण और ऊर्जा',
  environmentText:
    'सौर ऊर्जा, नवीकरणीय ऊर्जा, पर्यावरण कार्यक्रम, स्वच्छ ऊर्जा और बिजली से जुड़ी सहायता।',
  publicServicesTitle: 'जन सेवाएँ और नागरिक अधिकार',
  publicServicesText:
    'सरकारी प्रमाणपत्र, महत्वपूर्ण नागरिक सेवाएँ, सरकारी नियम, कानूनी अधिकार और सार्वजनिक संस्थानों तक पहुँच।',

  exploreTitle: 'योजनाएँ खोजें',
  exploreIntro: 'कोई क्षेत्र चुनें, या सरकारी दस्तावेज़ों से मिलान की गई सभी योजनाओं में खोजें।',
  sectorsHeading: 'क्षेत्र के अनुसार देखें',
  allSchemesHeading: 'जाँची गई सभी योजनाएँ',
  openSector: 'खोलें',
  schemeCountOne: 'जाँची गई 1 योजना',
  schemeCountMany: 'जाँची गई {n} योजनाएँ',
  schemeCountNone: 'जोड़ी जा रही हैं',

  allSectors: 'सभी क्षेत्र',
  sectorIntroNote:
    'यहाँ की हर योजना उसके सरकारी दस्तावेज़ों से पढ़ी गई है। कौन पा सकता है, क्या जुटाना है और कैसे आवेदन करना है, यह जानने के लिए कोई एक खोलें।',
  schemesInSector: 'इस क्षेत्र की योजनाएँ',
  checkerHint:
    'आप पात्र हो सकते हैं या नहीं, यह जानने के लिए किसी योजना में "जाँचें कि मैं पात्र हूँ या नहीं" खोलें। आप कोई भी प्रश्न छोड़ सकते हैं।',
  emptyTitle: 'इस श्रेणी में जाँची हुई जानकारी जोड़ी जा रही है।',
  emptyText:
    'हम योजना तभी दिखाते हैं जब उसे सरकारी दस्तावेज़ से मिला लिया गया हो, इसलिए इस पन्ने पर अभी कोई नहीं है। तब तक आप एआई साथी से पूछ सकते हैं, या जिन क्षेत्रों में योजनाएँ हैं उन्हें देख सकते हैं।',
  budgetNote:
    'बजट के आँकड़े योजनाएँ नहीं हैं। आवंटन, संशोधित अनुमान और वास्तविक खर्च को अलग रखकर एक अलग बजट खंड तैयार किया जा रहा है।',
  askSectorTitle: '{sector} के बारे में एआई साथी से पूछें',
  askSectorText:
    'अपनी भाषा में लिखकर या बोलकर पूछें। उत्तर केवल हमारे पास मौजूद सरकारी दस्तावेज़ों से आते हैं, उस पन्ने के साथ जहाँ से वे लिए गए हैं।',
  askSectorButton: 'प्रश्न पूछें',
  questionsTitle: 'आप ये प्रश्न पूछ सकते हैं',
  documentsTitle: 'इस क्षेत्र के सरकारी दस्तावेज़',
  documentsEmpty: 'इस क्षेत्र का कोई सरकारी दस्तावेज़ अभी जोड़ा नहीं गया है।',

  searchLabel: 'योजनाएँ खोजें',
  searchPlaceholder: 'योजना का नाम, विभाग या किनके लिए',
  levelLabel: 'किसके द्वारा चलाई जाती है',
  levelAll: 'केंद्र और राज्य',
  levelCentral: 'केंद्र सरकार',
  levelState: 'राज्य सरकार',
  stateLabel: 'राज्य',
  stateAll: 'सभी राज्य',
  shownOne: '1 योजना दिखाई जा रही है',
  shownMany: '{n} योजनाएँ दिखाई जा रही हैं',
  noMatch: 'इन फ़िल्टर से कोई योजना नहीं मिली। कम शब्द आज़माएँ, या फ़िल्टर हटाएँ।',
  clearFilters: 'फ़िल्टर हटाएँ',
  loading: 'लोड हो रहा है…',
  loadError: 'योजनाएँ लोड नहीं हो सकीं।',
  tryAgain: 'फिर से कोशिश करें',
  reference: 'संदर्भ: {id}',
  notFoundTitle: 'क्षेत्र नहीं मिला',
  notFoundText: 'इस पते पर कोई क्षेत्र नहीं है।',
  scopeSector:
    'पहले {sector} के सरकारी दस्तावेज़ देखे जा रहे हैं। दूसरे विषयों के उत्तर भी दिए जाएँगे।',
  scopeClear: 'सब कुछ के बारे में पूछें',
  budgetHeading: 'बजट के दस्तावेज़ क्या कहते हैं',
  budgetIntro:
    'ये आँकड़े सरकारी बजट दस्तावेज़ों से लिए गए हैं। बजट अनुमान एक योजना है। संशोधित अनुमान अद्यतन योजना है। वास्तविक खर्च वह पैसा है जो सचमुच खर्च हुआ। इन्हें अलग-अलग दिखाया जाता है, कभी मिलाया नहीं जाता।',
  basisBudget: 'बजट अनुमान',
  basisRevised: 'संशोधित अनुमान',
  basisActual: 'वास्तविक खर्च',
  planNote:
    'ये योजनाएँ या अनुमान हैं। ये खर्च हो चुका पैसा नहीं हैं, और न ही नागरिकों को मिल चुका पैसा।',
  unitCrore: 'करोड़',
  unitLakhCrore: 'लाख करोड़',
  unitPercent: 'प्रतिशत',
  budgetOf: 'बजट {year}',
  figuresHeading: 'आँकड़े',
  meaningHeading: 'इसका मतलब',
  announcementsHeading: 'दस्तावेज़ क्या घोषणा करता है',
  budgetEmpty: 'अभी कोई बजट रिकॉर्ड जोड़ा नहीं गया है।',
  budgetError: 'बजट रिकॉर्ड लोड नहीं हो सके।',
  budgetKindTax: 'कर',
  budgetKindAnnouncement: 'घोषणा',
  budgetKindAllocation: 'आवंटन',
  budgetAskCitizens: 'इस बजट का आम नागरिकों के लिए क्या मतलब है?',
  budgetShown: '{n} बजट रिकॉर्ड',
  budgetOne: '1 बजट रिकॉर्ड',
  openInSector: '{sector} के बजट रिकॉर्ड',
  englishOnly:
    'विवरण अंग्रेज़ी में है, जैसा सरकारी दस्तावेज़ों में है। अपनी भाषा में एआई साथी से पूछें।',
  centralBudget: 'केंद्रीय बजट',
  stateBudget: 'राज्य बजट: {state}',
}

export const strings = { en, bn, hi } as const

export const translator = createTranslator<SectorStringKey>(strings)
export type Translate = TranslateWith<SectorStringKey>
