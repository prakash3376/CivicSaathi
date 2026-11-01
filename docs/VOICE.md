# Voice and languages

How CivicSaathi reads answers aloud and takes a spoken question, in English, Hindi and Bengali, what it does with the audio, and where it stops working. The code is in `frontend/src/features/voice/`; the language plumbing in `frontend/src/i18n/` and, for answers, `backend/app/services/assistant/`.

## What you can do

- **Talk with the assistant.** On the ask page, "Start talking" begins a spoken conversation: it says (in the language you speak) "Ask your question about scholarships", listens, asks your question, reads the answer aloud, and then listens again, until you press "Stop talking", say nothing twice in a row, or something goes wrong. You choose the language you speak (English, বাংলা, हिन्दी); the answer comes in the language of the answer box, or in the language you spoke when that is on automatic. Every step is also written in one live region, and a failure is spoken as well as shown. The conversation appears on the page like any other, so it can be read, and the answers carry their sources.
- **What the panel shows.** One large microphone button whose picture follows the conversation (rings spreading while it listens, a spinner while it looks up, rising bars while it speaks), a word for the state (Ready, Listening, Thinking, Speaking, Stopped), the three steps (listen, look up, answer) with the current one marked, and your question as it is heard. Under it, example questions in the language you speak: tap one to hear its answer without speaking. Colour is never the only signal, the pictures and steps are hidden from screen readers (the live region says each step, and does not repeat the words heard), and the motion stops for people whose device asks for less of it.
- **Listen.** Every answer, every eligibility result and every scheme page has a "Listen" button with a speed choice (slower, normal, faster). The text is read in the language it is written in, with a voice made for that language.
- **Speak a question.** On the ask page the microphone turns speech into text in the question box. You read and edit it, then press Ask: nothing is sent on its own.
- **Three languages across the product.** The English / বাংলা / हिन्दी switch in the header changes the whole interface; the answer language of the chat (automatic, English, Bengali, Hindi) is chosen separately. A question written in Devanagari is answered in Hindi when the language is automatic. A question in any other language (Tamil, Gujarati, ...) is answered in English, and the answer says so (SPEC rule R8).

## How it works, and what is sent where

| Part | Done by | What leaves the device |
| --- | --- | --- |
| Reading aloud | The browser's speech synthesis (`speechSynthesis`) | Nothing of ours. Some browsers use their maker's online voices (Chrome offers Google voices), which receive the text being read. |
| Speaking a question | The browser's speech recognition (`SpeechRecognition`) | The **recording goes to the browser maker's speech service** (Google for Chrome, Microsoft for Edge). CivicSaathi never receives, stores or logs it, and the page says so beside the microphone. |
| The words recognised | Land in the question box | Sent to CivicSaathi only when the person presses Ask, like any typed question. |

There is no speech code on the server and no new dependency. The only thing stored on the device is the reading speed (`civicsaathi.speech-rate`) next to the two language choices.

## How the conversation works

`VoiceConversation` is a small state machine (idle, prompting, listening, thinking, speaking, stopped). Each step continues from the end of the one before: the speaker tells how a reading ended (`speak(..., onEnd)`), the chat tells how a question ended (`ask()` returns the outcome), and the recogniser tells that listening ended. Stopping, or leaving the page, starts a new session number, so anything still on its way from the old session is ignored (a late answer is never read to someone who stopped). It never listens while it is speaking, so it does not hear itself. It ends on: the person stopping it, two silences in a row, a microphone problem (blocked, no network, language not supported), a failed question, or an answer in a language the device has no voice for (the answer stays on the screen). A typed question waiting for its answer disables "Start talking".

## Rules the code keeps

- **A text is read only with a voice for its language** (`pickVoice`). An English voice reading Bengali is noise, so when the device has no Bengali or Hindi voice the page says so, in the language of the page, and leaves the text on the screen (SPEC rule R8). It never fails silently.
- **Long texts are cut into sentences** and spoken one after another, because Chrome stops a long utterance after about fifteen seconds. Only one thing is read at a time; starting another, leaving the page or listening to a question stops the first.
- **What is read is what the screen shows,** in reading order, and ends with the disclaimer (rule R6): `speechText.ts`. Each text is in one language so that one voice can read it. The **Listen** buttons always read the disclaimer. In a **spoken conversation** the same words are put the way a person would say them (`conversationSpeech`): a lead-in, the answer, then a closing question. The disclaimer is read in full at the first answer of each conversation and left to the screen afterwards, so it is not repeated after every turn; a greeting or thanks has none. General help (see [ASSISTANT.md](ASSISTANT.md), "General guidance") is always read after the fixed words that say it is not from an official document.
- **Spoken questions stay questions.** The microphone adds words after what is already in the box, within the 500-character limit, and moves focus to the box so the words can be checked. Personal numbers are still removed from the question by the backend before the model sees it.
- **Hindi and Bengali digits.** Figures are written with 0-9 everywhere. Someone typing an amount in Devanagari or Bengali digits (२,००,००० or ২,০০,০০০) is understood.

## Hindi across the product

Hindi is a full third language, not a translation layer:

- **Answers** (`Language = en | bn | hi`): the model is told to write in Hindi; a statement that is not mostly Devanagari is rejected like a statement in the wrong language; refusals, the disclaimer and the warnings are fixed Hindi texts in `services/assistant/messages.py`, never model output. The check that every figure, month and address of a statement is in its quote works the same for Hindi.
- **Schemes:** every statement of a scheme file has `en`, `bn` and `hi` wording, all checked against the same quote. A scheme file without Hindi does not load.
- **Screens:** one table of words per area, tested for equal entries, equal placeholders and the right script (`i18n/strings.test.ts`).

## Limits, plainly

- **The Hindi and the Bengali are drafts by a non-native speaker** and need a native speaker's review before real use: the interface, the fixed assistant texts and the scheme wording.
- **Voices depend on the device.** On Windows the installed voices may be English only (this machine has David, Hazel and Zira): add Hindi and Bengali under Settings, Time & language, Speech, or use Chrome or Edge, which usually offer online voices. The code was tested against a fake speech engine and against Chrome without voices; **audible Hindi and Bengali speech has not been heard**. The whole conversation (prompt, listening, a real Hindi question to the real backend and Gemini, the Hindi answer read, listening again, ending after two silences) was run in real Chrome with scripted stand-ins for the microphone and the speaker, which proves the flow and the wiring but not the sound or the recognition quality.
- **The language spoken is chosen, not detected.** The browser's recogniser needs to be told the language before it listens. To switch language, stop and choose another (the choice is locked during a conversation).
- **Speech recognition needs the internet** and is only as good as the browser maker's service for each language. Firefox has no speech recognition: the page says so and offers typing.
- **Numbers are read as the voice reads them.** "Rs 2,50,000" may be spoken as a string of digits by some Bengali and Hindi voices.
- **No offline audio files and no chapters yet** (SPEC feature 5): the audio is live speech, not a downloadable MP3. A server-side voice (for example Bhashini or a cloud TTS) would give the same voice everywhere and downloadable audio, at the cost of a key, a bill and sending text to another service.
