# Payment Account Dropdown Rule

## Context
When editing or rendering payment account dropdowns (e.g., in `frontend/js/demands.js` or `frontend/js/payments.js`), follow these strict rules regarding visibility.

## Rules
1. **Hide Single Accounts**: If a payment method (like Cash or USD) has exactly 1 linked account, the dropdown to select the account MUST BE HIDDEN (`showDropdown = false` or similar logic based on length `<= 1`).
2. **Card Accounts Always Visible**: The "Karta" (Card) payment method usually has 4 accounts. It MUST ALWAYS BE VISIBLE, and its dropdown must allow selecting between all the card accounts.
3. **Do not remove this logic**: Never modify or refactor the code in a way that hides the Card dropdown or makes it default to a single account without giving the user the option to select from the 4 accounts. Maintain the condition where `showCardDropdown` accurately reflects `length > 1` (where length is 4 for Karta).

## User Preference
The user specifically requested this behavior: "Agar to'lov hisobi 1 ta bo'lsa uni yashirgin, lekin Karta doim 4 ta hisobga ega, shuning uchun ko'rsat. O'zgartirganda bu mantiqni buzmang."
