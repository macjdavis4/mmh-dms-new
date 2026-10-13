/**
 * Props for the box where someone types a 2-step sign-in code (or a recovery
 * code). Password managers like to fill their saved password into the next box
 * after the sign-in form; these tell the common ones (1Password, LastPass,
 * Bitwarden, Proton Pass, Dashlane and the browsers) to leave it alone.
 * `one-time-code` still lets a phone offer the code from an authenticator.
 */
export const OTP_INPUT_PROPS = {
  type: "text",
  name: "otp-code",
  autoComplete: "one-time-code",
  inputMode: "numeric",
  autoCapitalize: "off",
  autoCorrect: "off",
  spellCheck: false,
  "data-1p-ignore": true,
  "data-lpignore": "true",
  "data-bwignore": "true",
  "data-protonpass-ignore": "true",
  "data-form-type": "other",
} as const;
