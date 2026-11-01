/**
 * The words of the voice controls (reading aloud, speaking a question), in English, Bengali and Hindi.
 * The Bengali and Hindi are drafts by a non-native speaker and must be reviewed by a native
 * speaker before real use.
 */
import { createTranslator, type UiLanguage } from '@/i18n/translator'

const en = {
  listenAnswer: 'Listen to this answer',
  listenResult: 'Listen to this result',
  listenScheme: 'Listen to this scheme',
  stopReading: 'Stop reading',
  speed: 'Reading speed',
  speedSlow: 'Slower',
  speedNormal: 'Normal',
  speedFast: 'Faster',
  nameEnglish: 'English',
  nameBengali: 'Bengali',
  nameHindi: 'Hindi',
  noVoice:
    'This device has no {language} voice, so this cannot be read aloud. You can still read it on the screen.',
  noSynthesis: 'This browser cannot read text aloud. You can still read it on the screen.',
  mic: 'Speak your question',
  micStop: 'Stop and use what I said',
  micListening: 'Listening… speak your question now.',
  micHeard: 'Please check your question, then press Ask.',
  micUnsupported: 'This browser cannot turn speech into text. Please type your question.',
  micDenied: 'The microphone is blocked. Allow it in your browser, or type your question.',
  micNoSpeech: 'We did not hear anything. Press the microphone and try again.',
  micNetwork: 'Speaking a question needs an internet connection. Please type it instead.',
  micLanguage:
    'This browser cannot understand {language} speech. Please type your question instead.',
  micBusy: 'The microphone could not be used. Is another program using it?',
  micFailed: 'Speaking a question did not work this time. Please type it instead.',
  micPrivacy:
    'When you use the microphone, your browser may send the recording to its own speech service (for example Google for Chrome). CivicSaathi never receives or stores the recording.',
  talkTitle: 'Talk to the assistant',
  talkIntro:
    'Press Start talking and ask your question out loud. The answer is read to you, and then it listens again.',
  talkLanguage: 'I will speak in',
  talkStart: 'Start talking',
  talkStop: 'Stop talking',
  talkPrompt: 'Hello! What would you like to know about government schemes or your rights?',
  talkLeadDocs: 'Here is what the official documents say.',
  talkAnythingElse: 'Is there anything else you would like to ask?',
  talkListening: 'Listening… ask your question.',
  talkThinking: 'Looking in the official documents…',
  talkSpeaking: 'Reading the answer…',
  talkSilence: 'I did not hear anything, so I stopped. Press Start talking to try again.',
  talkErrorSpoken: 'Sorry, I could not get an answer. Please try again.',
  talkErrorShown: 'Stopped: the answer could not be found. Press Start talking to try again.',
  talkNoVoiceForAnswer:
    'Stopped: this device has no voice for the language of the answer, so it cannot be read aloud. The answer is on the screen.',
  talkUnsupported:
    'Talking to the assistant needs speech recognition, which this browser does not have. You can type your question instead.',
  talkStopped: 'Stopped.',
  talkQuestion: 'Your question',
  chipReady: 'Ready',
  chipListening: 'Listening',
  chipThinking: 'Thinking',
  chipSpeaking: 'Speaking',
  chipStopped: 'Stopped',
  stepListen: 'Listen',
  stepThink: 'Look up',
  stepSpeak: 'Answer',
  talkTryTitle: 'Or tap a question and hear its answer',
} as const

export type VoiceKey = keyof typeof en

const bn: Record<VoiceKey, string> = {
  listenAnswer: 'এই উত্তরটি শুনুন',
  listenResult: 'এই ফলাফলটি শুনুন',
  listenScheme: 'এই প্রকল্পটি শুনুন',
  stopReading: 'পড়া থামান',
  speed: 'পড়ার গতি',
  speedSlow: 'ধীরে',
  speedNormal: 'স্বাভাবিক',
  speedFast: 'দ্রুত',
  nameEnglish: 'ইংরেজি',
  nameBengali: 'বাংলা',
  nameHindi: 'হিন্দি',
  noVoice:
    'এই ডিভাইসে {language} ভাষার কণ্ঠস্বর নেই, তাই এটি পড়ে শোনানো যাচ্ছে না। আপনি পর্দায় পড়ে নিতে পারেন।',
  noSynthesis: 'এই ব্রাউজার লেখা পড়ে শোনাতে পারে না। আপনি পর্দায় পড়ে নিতে পারেন।',
  mic: 'মুখে প্রশ্ন বলুন',
  micStop: 'থামুন এবং যা বলেছি তা ব্যবহার করুন',
  micListening: 'শুনছি… এখন আপনার প্রশ্ন বলুন।',
  micHeard: 'অনুগ্রহ করে প্রশ্নটি দেখে নিন, তারপর "জিজ্ঞাসা করুন" চাপুন।',
  micUnsupported: 'এই ব্রাউজার কথা লেখায় বদলাতে পারে না। অনুগ্রহ করে প্রশ্নটি টাইপ করুন।',
  micDenied: 'মাইক্রোফোন বন্ধ করা আছে। ব্রাউজারে অনুমতি দিন, অথবা প্রশ্নটি টাইপ করুন।',
  micNoSpeech: 'কিছু শুনতে পাইনি। মাইক্রোফোন চেপে আবার চেষ্টা করুন।',
  micNetwork: 'মুখে প্রশ্ন বলতে ইন্টারনেট লাগে। অনুগ্রহ করে টাইপ করুন।',
  micLanguage: 'এই ব্রাউজার {language} ভাষার কথা বুঝতে পারে না। অনুগ্রহ করে প্রশ্নটি টাইপ করুন।',
  micBusy: 'মাইক্রোফোন ব্যবহার করা যায়নি। অন্য কোনো প্রোগ্রাম কি সেটি ব্যবহার করছে?',
  micFailed: 'এবার মুখে প্রশ্ন বলা কাজ করেনি। অনুগ্রহ করে টাইপ করুন।',
  micPrivacy:
    'মাইক্রোফোন ব্যবহার করলে আপনার ব্রাউজার রেকর্ডিংটি তার নিজের কথা-বোঝার সেবায় (যেমন ক্রোমের জন্য গুগল) পাঠাতে পারে। CivicSaathi রেকর্ডিং পায় না এবং রাখে না।',
  talkTitle: 'সহায়কের সঙ্গে কথা বলুন',
  talkIntro:
    '"কথা শুরু করুন" চাপুন এবং মুখে আপনার প্রশ্ন বলুন। উত্তর পড়ে শোনানো হবে, তারপর আবার শোনার জন্য অপেক্ষা করবে।',
  talkLanguage: 'আমি যে ভাষায় বলব',
  talkStart: 'কথা শুরু করুন',
  talkStop: 'কথা থামান',
  talkPrompt: 'নমস্কার! সরকারি প্রকল্প বা আপনার অধিকার নিয়ে আপনি কী জানতে চান?',
  talkLeadDocs: 'সরকারি নথিতে যা লেখা আছে, তা বলছি।',
  talkAnythingElse: 'আর কিছু জানতে চান?',
  talkListening: 'শুনছি… আপনার প্রশ্ন বলুন।',
  talkThinking: 'সরকারি নথিতে খোঁজা হচ্ছে…',
  talkSpeaking: 'উত্তর পড়ে শোনানো হচ্ছে…',
  talkSilence: 'কিছু শুনতে পাইনি, তাই থেমে গেছি। আবার চেষ্টা করতে "কথা শুরু করুন" চাপুন।',
  talkErrorSpoken: 'দুঃখিত, উত্তর পাওয়া যায়নি। অনুগ্রহ করে আবার চেষ্টা করুন।',
  talkErrorShown: 'থেমে গেছে: উত্তর পাওয়া যায়নি। আবার চেষ্টা করতে "কথা শুরু করুন" চাপুন।',
  talkNoVoiceForAnswer:
    'থেমে গেছে: উত্তরের ভাষার কণ্ঠস্বর এই ডিভাইসে নেই, তাই পড়ে শোনানো যাচ্ছে না। উত্তরটি পর্দায় আছে।',
  talkUnsupported:
    'সহায়কের সঙ্গে কথা বলতে কথা-বোঝার সুবিধা লাগে, যা এই ব্রাউজারে নেই। আপনি প্রশ্নটি টাইপ করতে পারেন।',
  talkStopped: 'থেমে গেছে।',
  talkQuestion: 'আপনার প্রশ্ন',
  chipReady: 'প্রস্তুত',
  chipListening: 'শুনছি',
  chipThinking: 'খুঁজছি',
  chipSpeaking: 'বলছি',
  chipStopped: 'থেমে গেছে',
  stepListen: 'শোনা',
  stepThink: 'খোঁজা',
  stepSpeak: 'উত্তর',
  talkTryTitle: 'অথবা একটি প্রশ্নে চাপ দিন, উত্তর শুনুন',
}

const hi: Record<VoiceKey, string> = {
  listenAnswer: 'यह उत्तर सुनें',
  listenResult: 'यह परिणाम सुनें',
  listenScheme: 'यह योजना सुनें',
  stopReading: 'पढ़ना रोकें',
  speed: 'पढ़ने की गति',
  speedSlow: 'धीमी',
  speedNormal: 'सामान्य',
  speedFast: 'तेज़',
  nameEnglish: 'अंग्रेज़ी',
  nameBengali: 'बंगाली',
  nameHindi: 'हिन्दी',
  noVoice:
    'इस डिवाइस में {language} भाषा की आवाज़ नहीं है, इसलिए इसे पढ़कर नहीं सुनाया जा सकता। आप इसे स्क्रीन पर पढ़ सकते हैं।',
  noSynthesis: 'यह ब्राउज़र लिखा हुआ पाठ पढ़कर नहीं सुना सकता। आप इसे स्क्रीन पर पढ़ सकते हैं।',
  mic: 'बोलकर प्रश्न पूछें',
  micStop: 'रुकें और जो बोला उसे इस्तेमाल करें',
  micListening: 'सुन रहे हैं… अब अपना प्रश्न बोलें।',
  micHeard: 'कृपया अपना प्रश्न जाँच लें, फिर "पूछें" दबाएँ।',
  micUnsupported: 'यह ब्राउज़र बोली को लिखित पाठ में नहीं बदल सकता। कृपया अपना प्रश्न टाइप करें।',
  micDenied: 'माइक्रोफ़ोन बंद है। अपने ब्राउज़र में अनुमति दें, या अपना प्रश्न टाइप करें।',
  micNoSpeech: 'कुछ सुनाई नहीं दिया। माइक्रोफ़ोन दबाकर फिर कोशिश करें।',
  micNetwork: 'बोलकर प्रश्न पूछने के लिए इंटरनेट चाहिए। कृपया इसे टाइप करें।',
  micLanguage: 'यह ब्राउज़र {language} भाषा की बोली नहीं समझ सकता। कृपया अपना प्रश्न टाइप करें।',
  micBusy: 'माइक्रोफ़ोन इस्तेमाल नहीं हो सका। क्या कोई दूसरा प्रोग्राम उसे इस्तेमाल कर रहा है?',
  micFailed: 'इस बार बोलकर प्रश्न पूछना काम नहीं किया। कृपया इसे टाइप करें।',
  micPrivacy:
    'माइक्रोफ़ोन इस्तेमाल करने पर आपका ब्राउज़र रिकॉर्डिंग को अपनी भाषण-सेवा (जैसे Chrome के लिए Google) को भेज सकता है। CivicSaathi रिकॉर्डिंग न पाता है, न रखता है।',
  talkTitle: 'सहायक से बात करें',
  talkIntro:
    '"बात शुरू करें" दबाएँ और अपना प्रश्न बोलकर पूछें। उत्तर आपको पढ़कर सुनाया जाएगा, फिर वह दोबारा सुनने लगेगा।',
  talkLanguage: 'बोलने की भाषा',
  talkStart: 'बात शुरू करें',
  talkStop: 'बात रोकें',
  talkPrompt: 'नमस्ते! सरकारी योजनाओं या आपके अधिकारों के बारे में आप क्या जानना चाहेंगे?',
  talkLeadDocs: 'सरकारी दस्तावेज़ों में यह लिखा है।',
  talkAnythingElse: 'क्या आप कुछ और पूछना चाहेंगे?',
  talkListening: 'सुन रहे हैं… अपना प्रश्न बोलिए।',
  talkThinking: 'सरकारी दस्तावेज़ों में देखा जा रहा है…',
  talkSpeaking: 'उत्तर पढ़कर सुनाया जा रहा है…',
  talkSilence:
    'कुछ सुनाई नहीं दिया, इसलिए बातचीत रुक गई। फिर कोशिश करने के लिए "बात शुरू करें" दबाएँ।',
  talkErrorSpoken: 'क्षमा करें, उत्तर नहीं मिल सका। कृपया फिर कोशिश करें।',
  talkErrorShown: 'बातचीत रुक गई: उत्तर नहीं मिल सका। फिर कोशिश करने के लिए "बात शुरू करें" दबाएँ।',
  talkNoVoiceForAnswer:
    'बातचीत रुक गई: उत्तर की भाषा की आवाज़ इस डिवाइस में नहीं है, इसलिए उसे पढ़कर नहीं सुनाया जा सकता। उत्तर स्क्रीन पर है।',
  talkUnsupported:
    'सहायक से बात करने के लिए बोली पहचानने की सुविधा चाहिए, जो इस ब्राउज़र में नहीं है। आप अपना प्रश्न टाइप कर सकते हैं।',
  talkStopped: 'बातचीत रुक गई।',
  talkQuestion: 'आपका प्रश्न',
  chipReady: 'तैयार',
  chipListening: 'सुन रहे हैं',
  chipThinking: 'खोज रहे हैं',
  chipSpeaking: 'बोल रहे हैं',
  chipStopped: 'रुक गई',
  stepListen: 'सुनना',
  stepThink: 'खोजना',
  stepSpeak: 'उत्तर',
  talkTryTitle: 'या किसी प्रश्न को दबाएँ और उसका उत्तर सुनें',
}

export const strings = { en, bn, hi }

export const translator = createTranslator<VoiceKey>(strings)

/** The key of the word for each language, for "no {language} voice" and the like. */
export const LANGUAGE_NAME: Record<UiLanguage, VoiceKey> = {
  en: 'nameEnglish',
  bn: 'nameBengali',
  hi: 'nameHindi',
}
