import type {
  ChecklistDocument,
  CriterionResult,
  EligibilityResult,
  Evidence,
  Question,
  SchemeDetails,
  SchemeSummary,
  SchemesResponse,
} from '@/api/types'

/** The Hindi of the wordings the tests read in Hindi; any other gets its English after a marker. */
const HINDI: Record<string, string> = {
  'A yearly scholarship for students of West Bengal.':
    'पश्चिम बंगाल के विद्यार्थियों के लिए वार्षिक छात्रवृत्ति।',
  'Support for girls studying technical courses.':
    'तकनीकी कोर्स में पढ़ रही लड़कियों के लिए सहायता।',
  'Last date to apply': 'आवेदन की अंतिम तिथि',
  Undergraduate: 'स्नातक',
  Postgraduate: 'स्नातकोत्तर',
  'Rs 1,000 a month for 10 months.': '1,000 रुपये प्रति माह, 10 माह तक।',
  'Family income is at most Rs 2,50,000 a year': 'पारिवारिक आय प्रति वर्ष अधिकतम 2,50,000 रुपये है',
  'Rs 2,00,000 a year': 'प्रति वर्ष 2,00,000 रुपये',
  'Rs 9,00,000 a year': 'प्रति वर्ष 9,00,000 रुपये',
  'What is your family income in a year?': 'आपके परिवार की सालाना आय कितनी है?',
  'rupees a year': 'रुपये प्रति वर्ष',
  'Is your college or university in West Bengal?':
    'क्या आपका कॉलेज या विश्वविद्यालय पश्चिम बंगाल में है?',
  'Informational summary, not legal advice. Check the official document before acting.':
    'यह केवल जानकारी के लिए सारांश है, कानूनी सलाह नहीं। कोई भी कदम उठाने से पहले सरकारी दस्तावेज़ से मिलान कर लें।',
}

const text = (en: string, bn: string) => ({ en, bn, hi: HINDI[en] ?? `हिन्दी: ${en}` })

const quote = (words: string): Evidence[] => [{ source_id: 'wb-svmcm-guidelines', quote: words }]

const INCOME_QUOTE =
  'The total family income for the prospective scholars will be not more than Rs. 2,50,000/-per annum.'
const MARKS_QUOTE = 'Candidate must have secured at least 60% marks in the qualifying examination.'

const questions: Question[] = [
  {
    field: 'institution_in_west_bengal',
    type: 'yes_no',
    text: text(
      'Is your college or university in West Bengal?',
      'আপনার কলেজ বা বিশ্ববিদ্যালয় কি পশ্চিমবঙ্গে?',
    ),
    hint: null,
    unit: null,
    choices: [],
    minimum: null,
    maximum: null,
    integer: false,
  },
  {
    field: 'family_income',
    type: 'number',
    text: text('What is your family income in a year?', 'আপনার পরিবারের বার্ষিক আয় কত?'),
    hint: text('Add up the income of everyone in the family.', 'পরিবারের সবার আয় যোগ করুন।'),
    unit: text('rupees a year', 'টাকা প্রতি বছর'),
    choices: [],
    minimum: 0,
    maximum: 100000000,
    integer: true,
  },
  {
    field: 'board_topper',
    type: 'yes_no',
    text: text(
      'Did you rank among the toppers of your board?',
      'আপনি কি বোর্ডের শীর্ষস্থানীয়দের একজন?',
    ),
    hint: null,
    unit: null,
    choices: [],
    minimum: null,
    maximum: null,
    integer: false,
  },
  {
    field: 'admission_type',
    type: 'choice',
    text: text('How were you admitted?', 'আপনি কীভাবে ভর্তি হয়েছেন?'),
    hint: null,
    unit: null,
    choices: [
      { id: 'first_year', label: text('Into the first year', 'প্রথম বর্ষে') },
      { id: 'lateral_entry', label: text('By lateral entry', 'সরাসরি দ্বিতীয় বর্ষে') },
    ],
    minimum: null,
    maximum: null,
    integer: false,
  },
  {
    field: 'marks_percent',
    type: 'number',
    text: text('What percentage of marks did you get?', 'আপনি কত শতাংশ নম্বর পেয়েছেন?'),
    hint: null,
    unit: text('percent', 'শতাংশ'),
    choices: [],
    minimum: 0,
    maximum: 100,
    integer: false,
  },
]

const documentItems: ChecklistDocument[] = [
  {
    id: 'bank_details',
    label: text('Bank account details', 'ব্যাংক অ্যাকাউন্টের বিবরণ'),
    detail: text('Account number and IFSC code.', 'অ্যাকাউন্ট নম্বর ও IFSC কোড।'),
    applicability: 'needed',
    evidence: quote('Bank account details of the applicant are required.'),
  },
  {
    id: 'income_documents',
    label: text('Proof of family income', 'পারিবারিক আয়ের প্রমাণ'),
    detail: null,
    applicability: 'maybe',
    evidence: quote('Income certificate if applicable.'),
  },
]

export const schemesBody: SchemesResponse = {
  schemes: [
    {
      id: 'svmcm',
      name: 'Swami Vivekananda Merit Cum Means Scholarship',
      authority: 'Government of West Bengal',
      level: 'state',
      state: 'West Bengal',
      sectors: ['education'],
      layout: 'check',
      kind: 'scheme',
      status: 'active',
      target: null,
      benefit: null,
      last_verified: null,
      summary: text(
        'A yearly scholarship for students of West Bengal.',
        'পশ্চিমবঙ্গের শিক্ষার্থীদের জন্য বার্ষিক বৃত্তি।',
      ),
      source_ids: ['wb-svmcm-guidelines', 'wb-svmcm-scheme-page'],
      tracks: [
        { id: 'ug', label: text('Undergraduate', 'স্নাতক') },
        { id: 'pg', label: text('Postgraduate', 'স্নাতকোত্তর') },
      ],
      deadline: null,
    },
    {
      id: 'aicte-pragati',
      name: 'AICTE Pragati Scholarship for Girls',
      authority: 'AICTE',
      level: 'central',
      state: null,
      sectors: ['education'],
      layout: 'check',
      kind: 'scheme',
      status: 'active',
      target: null,
      benefit: null,
      last_verified: null,
      summary: text(
        'Support for girls studying technical courses.',
        'কারিগরি কোর্সে পড়া মেয়েদের জন্য সহায়তা।',
      ),
      source_ids: ['aicte-pragati-faq'],
      tracks: [
        { id: 'degree', label: text('Degree', 'ডিগ্রি') },
        { id: 'diploma', label: text('Diploma', 'ডিপ্লোমা') },
      ],
      deadline: {
        id: 'close',
        label: text('Last date to apply', 'আবেদনের শেষ তারিখ'),
        on: '2026-10-31',
        status: 'open',
        days_left: 11,
        scanned: true,
        evidence: quote('last date for applications is 31 .10.2026'),
      },
    },
  ],
}

export const svmcm: SchemeSummary = schemesBody.schemes[0]!

export const schemeDetailsBody: SchemeDetails = {
  id: 'svmcm',
  name: svmcm.name,
  authority: svmcm.authority,
  level: 'state',
  state: 'West Bengal',
  layout: 'check',
  sectors: ['education'],
  summary: svmcm.summary,
  source_ids: svmcm.source_ids,
  tracks: [
    {
      id: 'ug',
      label: text('Undergraduate', 'স্নাতক'),
      description: text('Bachelor degree courses.', 'ব্যাচেলর ডিগ্রি কোর্স।'),
      benefit: {
        text: text('Rs 1,000 a month for 10 months.', 'মাসে 1,000 টাকা, 10 মাস।'),
        evidence: quote('Rs. 1,000 per month for 10 months.'),
      },
      criteria: [
        {
          id: 'income',
          label: text(
            'Family income is at most Rs 2,50,000 a year',
            'পারিবারিক আয় বছরে সর্বোচ্চ 2,50,000 টাকা',
          ),
          note: text(
            'Not required of Board toppers.',
            'বোর্ডের শীর্ষস্থানীয়দের জন্য প্রযোজ্য নয়।',
          ),
          evidence: quote(INCOME_QUOTE),
        },
        {
          id: 'marks',
          label: text('At least 60% marks', 'অন্তত 60% নম্বর'),
          note: null,
          evidence: quote(MARKS_QUOTE),
        },
      ],
      questions: questions.filter((q) => q.field !== 'admission_type'),
      documents: documentItems,
      caveats: [
        {
          id: 'one_scholarship',
          text: text(
            'You may hold only one scholarship at a time.',
            'একসঙ্গে একটির বেশি বৃত্তি পাওয়া যায় না।',
          ),
          evidence: quote('Students getting any other scholarship are not eligible.'),
        },
      ],
    },
    {
      id: 'pg',
      label: text('Postgraduate', 'স্নাতকোত্তর'),
      description: null,
      benefit: {
        text: text('Rs 2,000 a month for 10 months.', 'মাসে 2,000 টাকা, 10 মাস।'),
        evidence: quote('Rs. 2,000 per month for 10 months.'),
      },
      criteria: [
        {
          id: 'marks',
          label: text('At least 53% marks', 'অন্তত 53% নম্বর'),
          note: null,
          evidence: quote('At least 53% marks.'),
        },
      ],
      questions: questions.filter((q) => q.field === 'marks_percent'),
      documents: [documentItems[0]!],
      caveats: [],
    },
  ],
  steps: [
    {
      id: 'apply_online',
      text: text('Apply online on the scholarship portal.', 'বৃত্তির পোর্টালে অনলাইনে আবেদন করুন।'),
      evidence: quote('Applications must be submitted online.'),
    },
  ],
  contacts: [
    {
      id: 'mail',
      label: text('Help desk e-mail', 'সহায়তা ইমেল'),
      value: 'help@example.gov.in',
      evidence: quote('Write to help@example.gov.in for any query.'),
    },
    {
      id: 'phone',
      label: text('Helpline', 'হেল্পলাইন'),
      value: '033-2345-6789',
      evidence: quote('Helpline: 033-2345-6789.'),
    },
  ],
  deadlines: [],
  apply: {
    text: text('Apply on the official portal.', 'সরকারি পোর্টালে আবেদন করুন।'),
    url: 'https://svmcm.wb.gov.in',
    evidence: quote('Applications must be submitted online at svmcm.wb.gov.in.'),
  },
  not_stated: [
    text('The last date to apply.', 'আবেদনের শেষ তারিখ।'),
    text('Any fee for applying.', 'আবেদনের জন্য কোনো ফি।'),
  ],
}

function criterion(
  id: string,
  status: CriterionResult['status'],
  overrides: Partial<CriterionResult> = {},
): CriterionResult {
  const source = schemeDetailsBody.tracks[0]!.criteria.find((c) => c.id === id)!
  return {
    id,
    label: source.label,
    status,
    waived: false,
    field: id === 'income' ? 'family_income' : 'marks_percent',
    answer_text: null,
    note: source.note,
    evidence: source.evidence,
    ...overrides,
  }
}

const checklist = (documents: ChecklistDocument[] = documentItems) => ({
  documents,
  steps: schemeDetailsBody.steps,
  contacts: schemeDetailsBody.contacts,
  deadlines: [],
  apply: schemeDetailsBody.apply,
  not_stated: schemeDetailsBody.not_stated,
})

const DISCLAIMER = text(
  'Informational summary, not legal advice. Check the official document before acting.',
  'তথ্যমূলক সারাংশ, আইনি পরামর্শ নয়। কাজ করার আগে সরকারি নথি দেখে নিন।',
)

export const eligibleBody: EligibilityResult = {
  scheme_id: 'svmcm',
  track_id: 'ug',
  outcome: 'eligible',
  criteria: [
    criterion('income', 'met', { answer_text: text('Rs 2,00,000 a year', 'বছরে 2,00,000 টাকা') }),
    criterion('marks', 'met', { answer_text: text('72 percent', '72 শতাংশ') }),
  ],
  unanswered: [],
  caveats: schemeDetailsBody.tracks[0]!.caveats,
  checklist: checklist(),
  disclaimer: DISCLAIMER,
}

export const notEligibleBody: EligibilityResult = {
  ...eligibleBody,
  outcome: 'not_eligible',
  criteria: [
    criterion('income', 'not_met', {
      answer_text: text('Rs 9,00,000 a year', 'বছরে 9,00,000 টাকা'),
    }),
    criterion('marks', 'unknown'),
  ],
  unanswered: ['marks_percent'],
}

export const needMoreInfoBody: EligibilityResult = {
  ...eligibleBody,
  outcome: 'need_more_info',
  criteria: [criterion('income', 'unknown'), criterion('marks', 'met')],
  unanswered: ['family_income'],
}

export const waivedBody: EligibilityResult = {
  ...eligibleBody,
  criteria: [
    criterion('income', 'met', {
      waived: true,
      answer_text: text('Rs 9,00,000 a year', 'বছরে 9,00,000 টাকা'),
    }),
    criterion('marks', 'met'),
  ],
}
