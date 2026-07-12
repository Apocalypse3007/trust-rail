// Chrome-only copy (composer labels, empty states, toggle) — NOT verdict
// copy. Verdict headlines/body/reasons/advice/buttons always come from the
// API's localized render (spec §12.1) so they stay the single source of truth.
export const UI_COPY = {
  en: {
    verifyTitle: "Verify",
    verifySubtitle: "Forward it. We'll tell you if the market actually said it.",
    dropHint: "Drop a file",
    pasteText: "Paste text",
    pasteUrl: "Paste a URL",
    claimedSender: "Claimed sender (optional)",
    state: "State",
    send: "Send",
    emptyTitle: "Try it out",
    emptyHint:
      "Drop a file, paste a message, or paste a link to see how TrustRail checks it.",
    toggleLabel: "हिंदी",
    genericError: "Something went wrong.",
    networkError: "Could not reach the server.",
  },
  hi: {
    verifyTitle: "सत्यापित करें",
    verifySubtitle: "इसे भेजें। हम बताएंगे कि क्या बाज़ार ने वाकई यह कहा।",
    dropHint: "फ़ाइल छोड़ें",
    pasteText: "टेक्स्ट पेस्ट करें",
    pasteUrl: "URL पेस्ट करें",
    claimedSender: "दावा किया गया प्रेषक (वैकल्पिक)",
    state: "राज्य",
    send: "भेजें",
    emptyTitle: "इसे आज़माएं",
    emptyHint:
      "यह देखने के लिए फ़ाइल छोड़ें, संदेश पेस्ट करें, या लिंक पेस्ट करें कि TrustRail इसे कैसे जांचता है।",
    toggleLabel: "English",
    genericError: "कुछ गलत हो गया।",
    networkError: "सर्वर तक नहीं पहुंच सके।",
  },
} as const;

export type UiCopy = (typeof UI_COPY)["en"];
