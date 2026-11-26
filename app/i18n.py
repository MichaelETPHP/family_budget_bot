"""All user-facing text, in English (default) and Amharic."""

LANGS = ("en", "am")
DEFAULT_LANG = "en"
DIVIDER = "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"

T: dict[str, tuple[str, str]] = {
    # ---- menu buttons ----
    "btn_expense": ("💸 Add Expense", "💸 ወጪ መዝግብ"),
    "btn_income": ("💰 Add Income", "💰 ገቢ መዝግብ"),
    "btn_transfer": ("🔄 Transfer", "🔄 ዝውውር"),
    "btn_accounts": ("🏦 Accounts", "🏦 ሂሳቦች"),
    "btn_today": ("📊 Today", "📊 የዛሬ"),
    "btn_month": ("📅 This Month", "📅 የወሩ"),
    "btn_history": ("🧾 History", "🧾 ታሪክ"),
    "btn_voice": ("🎙️ Voice Notes", "🎙️ የድምፅ ማስታወሻ"),
    "btn_undo": ("↩️ Undo", "↩️ አጥፋ"),
    "btn_help": ("ℹ️ Help", "ℹ️ እገዛ"),
    "btn_lang": ("🌐 Language", "🌐 ቋንቋ"),
    "menu_placeholder": ("Choose from the menu…", "ከምናሌው ይምረጡ…"),
    "cur": ("Birr", "ብር"),

    # ---- registration ----
    "intro": (
        "🏡 <b>Family Budget</b>\n" + DIVIDER + "\n"
        "💸 Track expenses and 💰 income together\n"
        "🔔 Get notified when your family records something\n"
        "🌙 Receive a daily summary every midnight\n\n"
        "To start, please <b>share your phone number</b> 👇",
        "🏡 <b>የቤተሰብ የገንዘብ መዝገብ</b>\n" + DIVIDER + "\n"
        "💸 ወጪ እና 💰 ገቢዎን በቀላሉ ይመዝግቡ\n"
        "🔔 የቤተሰብ አባል ሲመዘግብ ወዲያው ይነገርዎታል\n"
        "🌙 በየቀኑ እኩለ ሌሊት የቀኑ ማጠቃለያ ይደርስዎታል\n\n"
        "ለመጀመር <b>ስልክ ቁጥርዎን</b> ያጋሩ 👇",
    ),
    "btn_share_phone": ("📱 Share my phone number", "📱 ስልክ ቁጥሬን አጋራ"),
    "btn_switch_lang": ("🌐 አማርኛ", "🌐 English"),
    "own_number": ("⚠️ Please share <b>your own</b> number using the button.",
                   "⚠️ እባክዎ <b>የራስዎን</b> ቁጥር በቁልፉ ያጋሩ።"),
    "private": ("⛔ Sorry, this bot is for family members only.", "⛔ ይቅርታ፣ ይህ ቦት የቤተሰብ ብቻ ነው።"),
    "phone_needed": ("📱 Please tap the <b>Share my phone number</b> button below.",
                     "📱 እባክዎ ከታች ያለውን <b>ስልክ ቁጥሬን አጋራ</b> ቁልፍ ይጫኑ።"),
    "ask_name": ("✅ <b>Number verified</b>\n\n😊 What should I call you?",
                 "✅ <b>ቁጥርዎ ተረጋግጧል</b>\n\n😊 በምን ስም ልጥራዎት?"),
    "registered": ("🎉 <b>All set, {name}!</b>\n\nUse the menu below to get started 👇",
                   "🎉 <b>ተሳክቷል፣ {name}!</b>\n\nሁሉም ዝግጁ ነው። ከታች ካለው ምናሌ ይጀምሩ 👇"),
    "welcome_back": ("👋 <b>Welcome back, {name}!</b>\n\nWhat shall we record today? 👇",
                     "👋 <b>እንኳን ደህና መጡ፣ {name}!</b>\n\nዛሬ ምን እንመዝግብ? 👇"),
    "joined": ("👋 <b>{name}</b> joined the family budget!", "👋 <b>{name}</b> የቤተሰቡን መዝገብ ተቀላቅለዋል!"),
    "press_start": ("👋 Press /start to begin.", "👋 ለመጀመር /start ይጫኑ።"),
    "use_menu": ("🤔 Please use the menu below 👇", "🤔 እባክዎ ከታች ያለውን ምናሌ ይጠቀሙ 👇"),

    # ---- language ----
    "lang_title": ("🌐 <b>Choose your language</b>", "🌐 <b>ቋንቋ ይምረጡ</b>"),
    "lang_set": ("✅ <b>Language: English</b>\n\nThe menu below is updated 👇",
                 "✅ <b>ቋንቋ፦ አማርኛ</b>\n\nከታች ያለው ምናሌ ተቀይሯል 👇"),

    # ---- record kinds ----
    "k_expense": ("Expense", "ወጪ"),
    "k_income": ("Income", "ገቢ"),
    "k_transfer": ("Transfer", "ዝውውር"),
    "k_setbal": ("Balance", "ቀሪ ሂሳብ"),
    "kn_expense": ("New Expense", "አዲስ ወጪ"),
    "kn_income": ("New Income", "አዲስ ገቢ"),
    "kn_transfer": ("Transfer", "ዝውውር"),
    "kn_setbal": ("Fix Balance", "ቀሪ ሂሳብ አስተካክል"),

    # ---- form steps ----
    "step": ("Step {n}/{total}", "ደረጃ {n}/{total}"),
    "s_category": ("Choose a category", "ምድብ ይምረጡ"),
    "s_amount": ("Amount", "መጠን"),
    "s_confirm": ("Confirm", "ያረጋግጡ"),
    "s_from": ("From?", "ከየት?"),
    "s_to": ("To?", "ወዴት?"),
    "s_account": ("Account", "ሂሳብ"),
    "btn_cancel": ("✖️ Cancel", "✖️ አቋርጥ"),
    "btn_save": ("✅ Save", "✅ አስቀምጥ"),
    "btn_back": ("↩️ Back", "↩️ ተው"),
    "enter_amount": ("💵 <b>Type the amount</b>\ne.g. <code>250</code>",
                     "💵 <b>መጠኑን ይጻፉ</b>\nለምሳሌ፦ <code>250</code>"),
    "bad_amount": ("⚠️ <b>Please enter a valid number</b>", "⚠️ <b>ትክክለኛ ቁጥር ያስገቡ</b>"),
    "amount_label": ("💵 <b>Amount</b>", "💵 <b>መጠን</b>"),
    "pad_hint": ("Tap the numbers below (or type them)", "ከታች ያሉትን ቁጥሮች ይጫኑ (ወይም ይጻፉ)"),
    "pad_empty": ("Enter an amount first", "መጀመሪያ መጠን ያስገቡ"),
    "btn_ok": ("✅ OK", "✅ እሺ"),
    "dir_expense": ("From", "ከ"),
    "dir_income": ("To", "ወደ"),
    "balance_change": ("Balance: {a} ➜ {b}", "ቀሪ፦ {a} ➜ {b}"),
    "change_account": ("Tap below to change the account", "ሂሳቡን ለመቀየር ከታች ይምረጡ"),
    "red_not_enough": ("🚫 Red = not enough money", "🚫 ቀይ = በቂ ገንዘብ የለም"),
    "red_empty": ("🚫 Red = no money", "🚫 ቀይ = ገንዘብ የለም"),
    "no_account_money": ("⚠️ <b>No account has enough money</b>\n<i>Record income or fix a balance first</i>",
                         "⚠️ <b>በቂ ገንዘብ ያለው ሂሳብ የለም</b>\n<i>መጀመሪያ ገቢ ይመዝግቡ ወይም ቀሪ ሂሳብ ያስተካክሉ</i>"),
    "btn_fix_balance": ("✏️ Fix Balance", "✏️ ቀሪ አስተካክል"),
    "not_enough_alert": ("🚫 Not enough money in {name}\nAvailable: {amt}",
                         "🚫 {name} ላይ በቂ ገንዘብ የለም\nያለው፦ {amt}"),
    "not_enough": ("🚫 Not enough money", "🚫 በቂ ገንዘብ የለም"),
    "toast_saved": ("Saved ✅", "ተመዝግቧል ✅"),
    "toast_cancelled": ("Cancelled", "ተቋርጧል"),

    # ---- receipts ----
    "saved_title": ("✅ <b>{kind} saved</b>", "✅ <b>{kind} ተመዝግቧል</b>"),
    "voice_label": ("🎙️ Voice note", "🎙️ የድምፅ ማስታወሻ"),
    "balance_line": ("{acc} · balance <b>{amt}</b>", "{acc} · ቀሪ <b>{amt}</b>"),
    "balance_after": ("{acc} · balance after <b>{amt}</b>", "{acc} · ከዚህ በኋላ ቀሪ <b>{amt}</b>"),
    "day_total": ("Your {kind} on {date}: {amt}", "የ{date} ጠቅላላ {kind}ዎ፦ {amt}"),
    "btn_add_note": ("➕ Add note", "➕ ማስታወሻ ጨምር"),
    "note_prompt": ("📝 <b>Type a note</b>  or  🎙️ <b>record a voice message</b>",
                    "📝 <b>ማስታወሻ ይጻፉ</b>  ወይም  🎙️ <b>የድምፅ መልእክት ይቅዱ</b>"),
    "note_owner_only": ("Only the person who recorded it can add a note",
                        "ማስታወሻ መጨመር የሚችለው ያስመዘገበው ሰው ብቻ ነው"),
    "notify_new": ("🔔 <b>{new}</b> · {name}", "🔔 <b>{new}</b> · {name}"),
    "notify_note": ("📝 <b>Note added</b> · {name}", "📝 <b>ማስታወሻ ታክሏል</b> · {name}"),
    "today": ("Today", "ዛሬ"),
    "yesterday": ("Yesterday", "ትናንት"),

    # ---- transfers ----
    "tr_from_q": ("📤 <b>Which account did the money leave?</b>", "📤 <b>ገንዘቡ ከየትኛው ሂሳብ ወጣ?</b>"),
    "tr_to_q": ("📥 <b>Which account did it go to?</b>", "📥 <b>ወደየትኛው ሂሳብ ገባ?</b>"),
    "available": ("Available in {name}: {amt}", "በ{name} ያለው፦ {amt}"),
    "tr_too_much": ("🚫 <b>Not enough money</b>\n<i>You can send at most {amt} from {name}</i>",
                    "🚫 <b>በቂ ገንዘብ የለም</b>\n<i>ከ{name} መላክ የሚቻለው እስከ {amt} ብቻ ነው</i>"),
    "tr_saved": ("✅ <b>Transfer saved</b>", "✅ <b>ዝውውር ተመዝግቧል</b>"),
    "notify_transfer": ("🔔 <b>Transfer</b> · {name}", "🔔 <b>ዝውውር</b> · {name}"),
    "notify_sent_you": ("💝 <b>{name}</b> sent you <b>{amt}</b>\n📥 Into your {acc} · balance <b>{bal}</b>",
                        "💝 <b>{name}</b> <b>{amt}</b> ልከውልዎታል\n📥 ወደ {acc} · ቀሪ <b>{bal}</b>"),
    "tr_family": ("🤝 Family transfer", "🤝 የቤተሰብ ዝውውር"),
    "s_who": ("Where to?", "ወዴት?"),
    "tr_who_q": ("👥 <b>Where is the money going?</b>", "👥 <b>ገንዘቡ ወዴት ይሄዳል?</b>"),
    "btn_between_mine": ("🔄 Between my accounts", "🔄 በራሴ ሂሳቦች መካከል"),
    "btn_to_person": ("💝 Send to {name}", "💝 ለ{name} ላክ"),
    "btn_tr_note": ("📝 Add a reason", "📝 ምክንያት ጨምር"),
    "btn_change_note": ("✏️ Change the reason", "✏️ ምክንያቱን ቀይር"),
    "tr_note_prompt": ("📝 <b>What is it for?</b>\nType it, e.g. <i>Buy shoes for me</i>, or 🎙️ record a voice message",
                       "📝 <b>ለምንድነው?</b>\nይጻፉ፣ ለምሳሌ <i>ጫማ ግዛልኝ</i>፣ ወይም 🎙️ የድምፅ መልእክት ይቅዱ"),
    "my_accounts": ("Mine", "የእኔ"),
    "given": ("Given to family", "ለቤተሰብ የተሰጠ"),
    "received": ("Received from family", "ከቤተሰብ የተቀበለ"),
    "family_total": ("Family total", "የቤተሰብ ጠቅላላ"),
    "updated": ("🔄 Updated {time}", "🔄 የተዘመነ {time}"),

    # ---- accounts ----
    "acc_title": ("🏦 <b>Account Balances</b>", "🏦 <b>የሂሳብ ቀሪዎች</b>"),
    "total": ("Total", "ጠቅላላ"),
    "sb_which": ("🏦 <b>Which account should I fix?</b>", "🏦 <b>የትኛውን ሂሳብ ላስተካክል?</b>"),
    "sb_now": ("{acc} · now <b>{amt}</b>", "{acc} · አሁን <b>{amt}</b>"),
    "sb_enter": ("Enter the real amount in this account", "በሂሳቡ ውስጥ ያለውን ትክክለኛ ገንዘብ ያስገቡ"),
    "sb_done": ("✅ <b>Balance updated</b>", "✅ <b>ቀሪ ሂሳብ ተስተካክሏል</b>"),
    "before": ("Before", "ከዚህ በፊት"),
    "now": ("Now", "አሁን"),
    "notify_sb": ("✏️ <b>{name}</b> updated the {acc} balance · <b>{amt}</b>",
                  "✏️ <b>{name}</b> የ{acc} ቀሪ ሂሳብ አስተካክለዋል · <b>{amt}</b>"),

    # ---- reports ----
    "today_title": ("📊 <b>Today's Report</b>", "📊 <b>የዛሬ ሪፖርት</b>"),
    "month_title": ("📅 <b>Monthly Report</b>", "📅 <b>የወሩ ሪፖርት</b>"),
    "nothing_yet": ("😴 <i>Nothing recorded yet</i>", "😴 <i>እስካሁን ምንም አልተመዘገበም</i>"),
    "spent": ("Spent", "ወጪ"),
    "earned": ("Earned", "ገቢ"),
    "left": ("Balance", "ቀሪ"),
    "top_spending": ("📂 <b>Top spending</b>", "📂 <b>ዋና ዋና ወጪዎች</b>"),
    "history_title": ("🧾 <b>Recent records</b>", "🧾 <b>የቅርብ ጊዜ መዝገቦች</b>"),
    "no_records": ("🧾 <i>No records yet</i>", "🧾 <i>እስካሁን ምንም መዝገብ የለም</i>"),
    "play_hint": ("🎙️ <i>Tap below to listen to a voice note</i>", "🎙️ <i>የድምፅ ማስታወሻውን ለመስማት ከታች ይጫኑ</i>"),
    "undo_nothing": ("🤷 <i>You have nothing to undo</i>", "🤷 <i>የሚጠፋ መዝገብ የለዎትም</i>"),
    "undo_q": ("🗑️ <b>Delete this record?</b>", "🗑️ <b>ይህን መዝገብ ላጥፋው?</b>"),
    "btn_undo_yes": ("🗑️ Yes, delete", "🗑️ አዎ፣ አጥፋ"),
    "toast_deleted": ("Deleted 🗑️", "ጠፍቷል 🗑️"),
    "deleted": ("🗑️ <b>Record deleted</b>", "🗑️ <b>መዝገቡ ጠፍቷል</b>"),
    "already_deleted": ("Already deleted", "ቀድሞ ጠፍቷል"),

    # ---- voice ----
    "memo_saved": ("🎙️ <b>Voice note saved</b>", "🎙️ <b>የድምፅ ማስታወሻ ተቀምጧል</b>"),
    "memo_hint": ("<i>Tap</i> {btn} <i>to hear them all</i>", "<i>ሁሉንም ለመስማት</i> {btn} <i>ይጫኑ</i>"),
    "notify_memo": ("🎙️ <b>New voice note</b> · {name}", "🎙️ <b>አዲስ የድምፅ ማስታወሻ</b> · {name}"),
    "memos_title": ("🎙️ <b>Voice Notes</b>", "🎙️ <b>የድምፅ ማስታወሻዎች</b>"),
    "memos_empty": ("<i>Nothing yet.</i>\n\nTo record, press and hold the 🎤 <b>microphone</b> button, "
                    "then release when you're done.",
                    "<i>እስካሁን ምንም የለም።</i>\n\nለመቅዳት የ🎤 <b>ማይክሮፎን</b> ቁልፉን ተጭነው ይያዙ፣ ሲጨርሱ ይልቀቁ።"),
    "memos_sub": ("<i>Last {n} · tap to listen</i>", "<i>የመጨረሻዎቹ {n} · ለመስማት ይጫኑ</i>"),
    "memos_rec": ("🎤 <i>To record a new one, hold the microphone button</i>",
                  "🎤 <i>አዲስ ለመቅዳት የማይክሮፎን ቁልፉን ተጭነው ይያዙ</i>"),
    "not_found": ("Not found 🤷", "አልተገኘም 🤷"),

    # ---- help ----
    "help_title": ("ℹ️ <b>How to use</b>", "ℹ️ <b>አጠቃቀም</b>"),
    "h_expense": ("Record money you spent", "ያወጡትን ገንዘብ ይመዝግቡ"),
    "h_income": ("Record money you received", "ያገኙትን ገንዘብ ይመዝግቡ"),
    "h_transfer": ("Record money moved between accounts", "ከአንድ ሂሳብ ወደ ሌላ የላኩትን ይመዝግቡ"),
    "h_accounts": ("Balance of each account, and corrections", "የእያንዳንዱ ባንክ ቀሪ ሂሳብ፣ እና ማስተካከያ"),
    "h_today": ("Today's summary for the family", "የዛሬ ማጠቃለያ ለቤተሰቡ"),
    "h_month": ("This month's summary and top spending", "የወሩ ማጠቃለያ እና ዋና ወጪዎች"),
    "h_history": ("The last 15 records", "የመጨረሻዎቹ 15 መዝገቦች"),
    "h_voice": ("Listen to recorded voice notes", "የተቀዱ የድምፅ ማስታወሻዎችን ይስሙ"),
    "h_undo": ("Delete your own last record", "የራስዎን የመጨረሻ መዝገብ ያጥፉ"),
    "h_lang": ("Switch between English and Amharic", "በእንግሊዝኛ እና በአማርኛ መካከል ይቀይሩ"),
    "h_footer": ("🎙️ Send a <b>voice message</b> any time. It's saved and shared with your family.\n"
                 "🌙 A daily summary is sent at <b>midnight</b>.\n"
                 "📅 Dates use the <b>Ethiopian calendar</b>.",
                 "🎙️ ማንኛውንም ጊዜ <b>የድምፅ መልእክት</b> ይላኩ — ተቀምጦ ለቤተሰብዎ ይደርሳል።\n"
                 "🌙 በየቀኑ <b>እኩለ ሌሊት</b> የቀኑ ማጠቃለያ ይላካል።\n"
                 "📅 ቀኖች በ<b>ኢትዮጵያ አቆጣጠር</b> ናቸው።"),

    # ---- nightly ----
    "nightly_title": ("🌙 <b>Daily Summary</b>", "🌙 <b>የቀኑ ማጠቃለያ</b>"),
    "month_so_far": ("📅 {month} spending so far · <b>{amt}</b>", "📅 የ{month} ወጪ እስካሁን · <b>{amt}</b>"),
    "memos_yesterday": ("🎙️ {n} voice note(s) saved yesterday", "🎙️ ትናንት {n} የድምፅ ማስታወሻ ተቀምጧል"),
    "good_night": ("💤 <i>Good night!</i> 🌟", "💤 <i>መልካም ሌሊት!</i> 🌟"),
}

CATEGORIES: dict[str, dict[str, tuple[str, str]]] = {
    "expense": {
        "food": ("🍔 Food", "🍔 ምግብ"), "market": ("🛒 Groceries", "🛒 ገበያ"),
        "transport": ("🚕 Transport", "🚕 ትራንስፖርት"), "rent": ("🏠 Rent", "🏠 ኪራይ"),
        "bills": ("💡 Utilities", "💡 መብራት/ውሃ"), "phone": ("📱 Airtime/Data", "📱 ካርድ/ኢንተርኔት"),
        "health": ("🏥 Health", "🏥 ጤና"), "clothes": ("👕 Clothes", "👕 ልብስ"),
        "school": ("📚 Education", "📚 ትምህርት"), "fun": ("🎉 Fun", "🎉 መዝናኛ"),
        "gift": ("🎁 Gifts", "🎁 ስጦታ"), "other": ("📦 Other", "📦 ሌላ"),
    },
    "income": {
        "salary": ("💼 Salary", "💼 ደመወዝ"), "side": ("🧑‍💻 Side job", "🧑‍💻 የጎን ሥራ"),
        "business": ("🏪 Business", "🏪 ንግድ"), "gift": ("🎁 Gift", "🎁 ስጦታ"),
        "invest": ("📈 Profit", "📈 ትርፍ"), "other": ("📦 Other", "📦 ሌላ"),
    },
}

MENU_ACTIONS = ("expense", "income", "transfer", "accounts", "today", "month",
                "history", "voice", "undo", "help", "lang")


def t(lang: str, key: str, **kw) -> str:
    s = T[key][1 if lang == "am" else 0]
    return s.format(**kw) if kw else s


def all_labels(key: str) -> list[str]:
    return list(dict.fromkeys(T[key]))


# "💸 Add Expense" / "💸 ወጪ መዝግብ" -> "expense"
LABEL_TO_ACTION = {label: action for action in MENU_ACTIONS for label in all_labels(f"btn_{action}")}
