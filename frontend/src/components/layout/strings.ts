/**
 * The words of the page frame (skip link, menu, language switch, footer) and of the not-found
 * page, in English, Bengali and Hindi. The Bengali and Hindi are drafts by a non-native speaker
 * and must be reviewed by a native speaker before real use.
 */
import { createTranslator } from '@/i18n/translator'

const en = {
  skip: 'Skip to main content',
  loading: 'Loading…',
  mainNav: 'Main',
  navHome: 'Home',
  navExplore: 'Explore Schemes',
  navPolicy: 'Policy & Rights',
  navAsk: 'Ask AI Saathi',
  navProfile: 'My Profile',
  menu: 'Menu',
  closeMenu: 'Close menu',
  languageGroup: 'Language',
  english: 'English',
  bengali: 'বাংলা',
  hindi: 'हिन्दी',
  footer: 'Informational summaries, not legal advice. Check the official document before acting.',
  status: 'System status',
  notFoundTitle: 'Page not found',
  notFoundText: 'The page you are looking for does not exist or has moved.',
  backHome: 'Back to home',
  errorPageTitle: 'This page could not be shown',
  errorPageText:
    'Something went wrong while showing this page. You can try again, or go to the home page.',
  errorChunkText:
    'This page could not be loaded. Your connection may have dropped, or the site may have been updated. Check your connection and try again.',
  errorSectionTitle: 'This part of the page could not be shown',
  errorSectionText: 'The rest of the page still works. You can try this part again.',
  errorTryAgain: 'Try again',
  errorHome: 'Go to the home page',
  errorReference: 'Reference: {id}',
  offlineTitle: 'You are offline.',
  offlineText:
    'What is on the screen may be out of date. Searching, checking and asking will not work until your connection returns.',
} as const

export type LayoutKey = keyof typeof en

const bn: Record<LayoutKey, string> = {
  skip: 'মূল অংশে যান',
  loading: 'লোড হচ্ছে…',
  mainNav: 'প্রধান মেনু',
  navHome: 'হোম',
  navExplore: 'প্রকল্প খুঁজুন',
  navPolicy: 'নীতি ও অধিকার',
  navAsk: 'এআই সাথী',
  navProfile: 'আমার প্রোফাইল',
  menu: 'মেনু',
  closeMenu: 'মেনু বন্ধ করুন',
  languageGroup: 'ভাষা',
  english: 'English',
  bengali: 'বাংলা',
  hindi: 'हिन्दी',
  footer: 'তথ্যমূলক সারাংশ, আইনি পরামর্শ নয়। কাজ করার আগে সরকারি নথি দেখে নিন।',
  status: 'সিস্টেমের অবস্থা',
  notFoundTitle: 'পৃষ্ঠা পাওয়া যায়নি',
  notFoundText: 'আপনি যে পৃষ্ঠাটি খুঁজছেন তা নেই বা সরে গেছে।',
  backHome: 'প্রথম পাতায় ফিরুন',
  errorPageTitle: 'এই পৃষ্ঠাটি দেখানো যায়নি',
  errorPageText: 'পৃষ্ঠাটি দেখাতে গিয়ে কিছু ভুল হয়েছে। আবার চেষ্টা করুন, অথবা প্রথম পাতায় যান।',
  errorChunkText:
    'এই পৃষ্ঠাটি লোড করা যায়নি। আপনার ইন্টারনেট সংযোগ কেটে যেতে পারে, অথবা সাইটটি হালনাগাদ হয়ে থাকতে পারে। সংযোগ দেখে আবার চেষ্টা করুন।',
  errorSectionTitle: 'পৃষ্ঠার এই অংশটি দেখানো যায়নি',
  errorSectionText: 'পৃষ্ঠার বাকি অংশ ঠিকই কাজ করছে। এই অংশটি আবার চেষ্টা করতে পারেন।',
  errorTryAgain: 'আবার চেষ্টা করুন',
  errorHome: 'প্রথম পাতায় যান',
  errorReference: 'সূত্র: {id}',
  offlineTitle: 'আপনি অফলাইনে আছেন।',
  offlineText:
    'পর্দায় যা দেখছেন তা পুরনো হতে পারে। সংযোগ ফিরে না আসা পর্যন্ত খোঁজা, যাচাই করা ও প্রশ্ন করা কাজ করবে না।',
}

const hi: Record<LayoutKey, string> = {
  skip: 'मुख्य भाग पर जाएँ',
  loading: 'लोड हो रहा है…',
  mainNav: 'मुख्य मेनू',
  navHome: 'मुखपृष्ठ',
  navExplore: 'योजनाएँ खोजें',
  navPolicy: 'नीति और अधिकार',
  navAsk: 'एआई साथी',
  navProfile: 'मेरी प्रोफ़ाइल',
  menu: 'मेनू',
  closeMenu: 'मेनू बंद करें',
  languageGroup: 'भाषा',
  english: 'English',
  bengali: 'বাংলা',
  hindi: 'हिन्दी',
  footer: 'जानकारी के लिए सारांश, कानूनी सलाह नहीं। कदम उठाने से पहले सरकारी दस्तावेज़ देख लें।',
  status: 'सिस्टम की स्थिति',
  notFoundTitle: 'पेज नहीं मिला',
  notFoundText: 'आप जो पेज खोज रहे हैं वह मौजूद नहीं है या हट गया है।',
  backHome: 'मुखपृष्ठ पर लौटें',
  errorPageTitle: 'यह पेज दिखाया नहीं जा सका',
  errorPageText: 'पेज दिखाते समय कुछ गड़बड़ हो गई। फिर कोशिश करें, या मुखपृष्ठ पर जाएँ।',
  errorChunkText:
    'यह पेज लोड नहीं हो सका। हो सकता है आपका कनेक्शन टूट गया हो, या साइट अपडेट हो गई हो। कनेक्शन जाँचकर फिर कोशिश करें।',
  errorSectionTitle: 'पेज का यह हिस्सा दिखाया नहीं जा सका',
  errorSectionText: 'पेज का बाकी हिस्सा ठीक से काम कर रहा है। आप इस हिस्से को फिर आज़मा सकते हैं।',
  errorTryAgain: 'फिर कोशिश करें',
  errorHome: 'मुखपृष्ठ पर जाएँ',
  errorReference: 'संदर्भ: {id}',
  offlineTitle: 'आप ऑफ़लाइन हैं।',
  offlineText:
    'स्क्रीन पर जो दिख रहा है वह पुराना हो सकता है। कनेक्शन वापस आने तक खोजना, जाँचना और सवाल पूछना काम नहीं करेगा।',
}

export const strings = { en, bn, hi }

export const translator = createTranslator<LayoutKey>(strings)
