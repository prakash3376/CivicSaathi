import type { SectorId } from '@/api/types'
import { examples } from '@/features/assistant/strings'
import type { UiLanguage } from '@/i18n/translator'

/**
 * Questions worth asking in each sector, offered as links to AI Saathi. A question is only a
 * suggestion: the assistant answers it from the official documents, or says that they do not say.
 * Education uses the assistant's own examples.
 */
const QUESTIONS: Record<Exclude<SectorId, 'education'>, Record<UiLanguage, readonly string[]>> = {
  health: {
    en: ['What government health insurance is available in West Bengal?'],
    bn: ['পশ্চিমবঙ্গে কোন সরকারি স্বাস্থ্য বিমা পাওয়া যায়?'],
    hi: ['पश्चिम बंगाल में कौन-सा सरकारी स्वास्थ्य बीमा उपलब्ध है?'],
  },
  agriculture: {
    en: ['How can a small farmer receive PM-KISAN assistance?'],
    bn: ['একজন ছোট কৃষক কীভাবে পিএম-কিষাণের সহায়তা পেতে পারেন?'],
    hi: ['एक छोटा किसान पीएम-किसान की सहायता कैसे पा सकता है?'],
  },
  'women-child': {
    en: ['What financial assistance is available for women in West Bengal?'],
    bn: ['পশ্চিমবঙ্গে মহিলাদের জন্য কোন আর্থিক সহায়তা পাওয়া যায়?'],
    hi: ['पश्चिम बंगाल में महिलाओं के लिए कौन-सी आर्थिक सहायता उपलब्ध है?'],
  },
  employment: {
    en: ['What government skill-development programmes are available?'],
    bn: ['কোন কোন সরকারি দক্ষতা উন্নয়ন কর্মসূচি পাওয়া যায়?'],
    hi: ['कौन-से सरकारी कौशल विकास कार्यक्रम उपलब्ध हैं?'],
  },
  housing: {
    en: ['Who can apply for PMAY?'],
    bn: ['পিএমএওয়াই-এর জন্য কারা আবেদন করতে পারেন?'],
    hi: ['पीएमएवाई के लिए कौन आवेदन कर सकता है?'],
  },
  'social-welfare': {
    en: ['What pension schemes are available for senior citizens?'],
    bn: ['প্রবীণ নাগরিকদের জন্য কোন কোন পেনশন প্রকল্প আছে?'],
    hi: ['वरिष्ठ नागरिकों के लिए कौन-सी पेंशन योजनाएँ उपलब्ध हैं?'],
  },
  business: {
    en: ['What government assistance is available for someone starting a small business?'],
    bn: ['ছোট ব্যবসা শুরু করতে চাইলে সরকারি কোন সহায়তা পাওয়া যায়?'],
    hi: ['छोटा व्यवसाय शुरू करने वाले के लिए कौन-सी सरकारी सहायता उपलब्ध है?'],
  },
  transport: {
    en: ['What is the Pradhan Mantri Gram Sadak Yojana for?'],
    bn: ['প্রধানমন্ত্রী গ্রাম সড়ক যোজনা কীসের জন্য?'],
    hi: ['प्रधानमंत्री ग्राम सड़क योजना किसलिए है?'],
  },
  budget: {
    en: [
      'What are the major education allocations in the latest West Bengal Budget?',
      'What does this budget mean for ordinary citizens?',
    ],
    bn: [
      'সর্বশেষ পশ্চিমবঙ্গ বাজেটে শিক্ষায় প্রধান বরাদ্দ কী কী?',
      'এই বাজেট সাধারণ নাগরিকদের কাছে কী অর্থ বহন করে?',
    ],
    hi: [
      'नवीनतम पश्चिम बंगाल बजट में शिक्षा के प्रमुख आवंटन क्या हैं?',
      'इस बजट का आम नागरिकों के लिए क्या मतलब है?',
    ],
  },
  environment: {
    en: ['How can a household get help to install rooftop solar?'],
    bn: ['ঘরের ছাদে সোলার বসাতে একটি পরিবার কীভাবে সহায়তা পেতে পারে?'],
    hi: ['घर की छत पर सोलर लगाने के लिए परिवार को सहायता कैसे मिल सकती है?'],
  },
  'public-services': {
    en: ['How can I obtain a caste certificate in West Bengal?'],
    bn: ['পশ্চিমবঙ্গে কীভাবে জাতিগত শংসাপত্র পাওয়া যায়?'],
    hi: ['पश्चिम बंगाल में जाति प्रमाणपत्र कैसे बनवाया जा सकता है?'],
  },
}

/** The questions to offer in a sector, in the language of the page. */
export function sectorQuestions(sector: SectorId, language: UiLanguage): readonly string[] {
  return sector === 'education' ? examples[language] : QUESTIONS[sector][language]
}
