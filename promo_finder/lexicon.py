"""Editable signal lists. This is the 'taste' of the rules engine.

An editor can tune these without touching any logic. Patterns are regexes,
matched case-insensitively; weights are 0..1. First tier that matches wins.
"""

# ---- Delivery / emotion tags on dialogue, e.g. MIA (Furious, Shouting) ----
TAG_HEAT = [
    (1.0, r"scream|shout|roar|yell|bellow|bark|shriek|screech|wail|boom|thunder|blood-curdl|furi|fury|enrag|"
          r"\brage|livid|outrag|incensed|venom|poison|threat|menac|murder|lethal|deadly|dangerous|hyster|unhinged|"
          r"maniac|explo|savage|sadist|merciless|ruthless|hateful|vengeful|vow|damning|condemn|seeth|simmer|snarl|"
          r"spitting|wrath|sob|gasp|horrif|aghast|shock|astonish|astound|panic|frantic|terrif|fright|fear|"
          r"anguish|agoniz|devastat|heartbro|shatter|stricken|distraught|despair|grie|torment|betray|revelat|"
          r"proclaim|trap snap|corner|predator|relentless|unrelenting|intimidat|strangled|choking"),
    (0.8, r"cruel|gloat|taunt|mock|scorn|deri|spite|sinist|chill|accus|desperat|plead|beg|weep|cry|tear|"
          r"incredul|defian|fierc|command|arrogan|condescend|smug|triumph|victor|exult|revel|vicious|harsh|"
          r"broken|crush|unbeliev|malic|vindic|contempt|callous|sneer|scoff|disdain|scath|imperious|haughty|"
          r"cutting|sarcas|sardon|snide|insolent|patroniz|elitist|coerc|provok|provocat|goad|smirk|conceit|"
          r"boast|greedy|possess|warning|ominous|dark|grim|severe|unforgiv|uncomprom|implacab|inexorab|disgust|"
          r"indignant|pained|hurt|wound|humiliat|shaking|overwhelm|intense|powerful|forceful|vehement|emphatic|"
          r"adamant|aggress|brutal|heartless|resist|challeng|interrogat|deny|denial|lying|decept|seduct|carnal|"
          r"tempt|flirt|dramatic|startl|distress|choked"),
    (0.5, r"cold|stern|firm|urgent|demand|sharp|bitter|trembl|shaken|steel|resolut|unyield|alarm|authorit|"
          r"dismiss|proud|grave|breathless|protect|passion|schem|calculat|hard|icy|biting|raw|piercing|"
          r"anxious|nervous|tense|strain|suspic|wary|conspir|sly|devious|conniv|determin|dignif|unwaver|"
          r"unflinch|steadfast|fearless|unbow|indomit|unbreak|confident|decisive|emotion|falter|voice break|"
          r"hoarse|panting|weak|fragile|impatient|insist|blunt|gruff|stiff|alert|frustrat|annoy|offend|"
          r"disbeliev|disbelief|bewilder|confus|surpris|puzzl|perplex|baffl|realiz|recogniz|troubl|worr|uneasy|"
          r"haunt|brood|apprehens|severely|intent|absolute|final"),
]

# ---- Visual / sound hooks found in ACTION, CAMERA and SOUND FX text ----
VISUAL_HOOK = [
    (1.0, r"\bslap|branding|red-hot|explosion|explod|detonat|gallows|noose|whip crack|riding crop|\bstab"),
    (0.85, r"\bpunch|\bstrikes?\b|\bstruck\b|\bwhip|\bchok|throat|blade|dagger|sword|knife|blood|\bspits?\b|"
           r"shatter|inferno|\bblaze|flames|on fire|kicked open|burst[s]? (in|open|through)|fly open|slams? open|"
           r"collaps|thorn|briar|lacerat|scream|gasp|beam crashes|rafters"),
    (0.6, r"\bgrab|seiz|shove|\bdrags?\b|hurl|throws?\b|kneel|one knee|to (his|her) knees|\bkiss|\bchains?\b|"
          r"shackle|cell door|dungeon|faint|crash|wound|\bscar\b|regalia|crest|signet|unmask|reveal|stunned|"
          r"tears? (spill|stream|roll)|\bmud\b|recoil|lunge|raises? (his|her) hand|grips?\b|smoke"),
]

# ---- Dialogue hooks: lines that stop a scroll in the first 3 seconds ----
LINE_HOOK = [
    (1.0, r"\byou knew\b|how dare|changed my mind|marrying me|marry (me|her)\b|will hang|burn (her|the|you)|"
          r"\bwitch|poison|you('re| are) (no one|nothing|worthless)|\bkneel|i am the duke|rightful duke|"
          r"seize (her|him)|arrest (her|him|that|this)|take your hands off|she is my wife|you stole|stole my|"
          r"remove (her|him)|guards!|throw (her|him) out|imposter|told (me )?(he|she) was dead"),
    (0.75, r"\bthief|\bstole\b|theft|guilty|execut|\bhang(ed)?\b|disown|disinherit|betray|liar|you lied|"
           r"never (marry|forgive|loved)|traitor|treason|murder|\bkill|\bdie\b|\bdead\b|\balive\b|"
           r"get out|let (her|him|me) go|on your knees|\bbeg\b|\bduke\b|duchess|invalid|annul|you took|"
           r"took everything|ruined|destroyed|stop!|no!"),
    (0.45, r"\bsister\b|\bhusband\b|\bwife\b|\bfather\b|plain|low value|nothing to offer|tolerate|jewel|"
           r"embarrass|humiliat|shame|mistake|why are you|what have you done|who are you|how long|"
           r"\bwedding\b|family"),
]

# ---- Cliffhanger signals: good places to CUT ----
CLIFF_SFX = [
    (1.0, r"cliffhanger|sting\b|stinger"),
    (0.75, r"cut(s)? to black|into (sudden )?silence|abrupt|crescendo"),
    (0.5, r"ominous|swell|drone|tension|gasp|bang|pound|slam|footsteps (approach|echo)"),
]
CLIFF_ACTION = [
    (1.0, r"cliffhanger|freezes? on|holds? on (the|her|his)|cut to black|smash cut"),
    (0.9, r"burst[s]? (in|open|through)|doors? (fly|flies|bang|slam|swing)s? open|kicked open|appears in the doorway|"
          r"raises? (his|her|the) (hand|crop|iron|blade|sword)|lunges?|\baims?\b|pulls? out|draws? (a|his|her) "
          r"(blade|sword|knife|dagger)|one knee|offering (the|a) ring"),
    (0.7, r"freez|eyes widen|stops? dead|stunned|horror|gasp|turns? (slowly|sharply)|steps? forward|"
          r"approach|reaches? for|clench|hardening|resolve|defiance|stares? (down|coldly)|silence"),
]
CLIFF_LINE = [
    (0.95, r"who are you|what did you (say|do)|you will (hang|burn|die|pay|regret)|or (you|he|she) (will|hang|die)|"
           r"\buntil\b.*\b(dawn|tomorrow|sunset)|by (dawn|tomorrow|nightfall)|guards!|\bseize\b|\barrest|"
           r"is (alive|dead|my son|the duke)|i am (the|his|her)|you are (the|his|her)|invalid|not over|"
           r"accept my hand|marry me|be my wife|will you\b|remove her|take her"),
    (0.6, r"\?\s*$|\.\.\.\s*\"?$|—\s*\"?$|\bif you\b|\bunless\b|\bor else\b|we'll see|you'll see|"
          r"this isn't over|i will (make|destroy|ruin|find|end)|\bnever\b|promise|swear"),
]
# Lines/actions that feel RESOLVED (bad place to end a promo)
RESOLVED = (r"\bsmil(e|es|ing)\b.*(warm|soft|gentle)|\bembrac|laugh(s|ing)? (together|softly)|relief|\bpeace|"
            r"fades? out|warmly|tender(ly)?|holds? (her|him) close|sigh(s)? (of|in) relief|into his arms|"
            r"in his arms|buries her face|comfort|safe now|forehead|nestles|drifts? (off|to sleep)")

# ---- Things a brand-new viewer won't understand without setup ----
# Generic plot-object words; character names are detected automatically per show (see scoring.py).
CONTEXT_NOUNS = (r"\bledger|herbarium|grimoire|\bjournal\b|signet|antidote|council|licen[sc]e|ecclesiastic|"
                 r"testimony|reprieve|informant|the plan\b|the deal\b|the letter\b|the documents?\b|"
                 r"as we agreed|like i said|remember when|ten[- ]day|west wing")
# Lines that only make sense as a reply. "No." / "Yes," are replies; "No! Stop!" is an outburst, not a reply.
CONTINUATION_START = (r"^\s*\"?(and|but|so|then|because|or|still|which|that's|it's|he's|she's)\b|"
                      r"^\s*\"?(yes|no)\s*[,.]|^\s*\"?\.\.\.")

# ---- Universal microdrama tropes: make a clip self-explanatory + feed 'why it works' ----
# (pattern, pitch line, specificity weight)
TROPES = {
    "altar_betrayal": (r"\baltar\b|changed my mind|marrying me|\bjilt|my (own )?wedding|my fianc|"
                       r"(going|want) to marry (you|her)|call(ed|ing) off the wedding",
                       "She is left at the altar", 1.0),
    "secret_identity": (r"\bthe duke\b|rightful (duke|heir)|true heir|\bmy son\b|ducal|regalia|\bcrest\b|"
                        r"(he|she) was dead|imposter|is alive|who (are|is) (you|he) really|duke of",
                        "Hints that the man nobody rates is secretly powerful, which is what the title promises", 1.0),
    "proposal": (r"marry me|one knee|proposal|be my wife|accept my hand|will you marry",
                 "A stranger proposes out of nowhere: the show's premise in one scene", 1.0),
    "protector": (r"take your hands off|let her go|steps? between|shields? her|\bpunch|guard collaps|"
                  r"don't touch her|touch my wife|stands? in front of her",
                  "Someone steps in to protect her", 0.9),
    "cruelty": (r"\bthorns?\b|briar|branding|red-hot|\bwhip|riding crop|dungeon|\bchains\b|starv|iron door|"
                r"\bcell\b|bare hands",
                "The villain hurts her, so the stakes are clear", 0.8),
    "false_accusation": (r"\bthief|theft|\bstole\b|\bwitch|framed|\barrest|constable|guilty|\btrial\b|"
                         r"testimony|\bexecut|\bhang(ed|s)?\b|admits? (she|he)",
                         "She is blamed for something she didn't do", 0.8),
    "danger": (r"\bfire\b|\bblaze|flames|inferno|explosion|detonat|beam crashes|burning|rafters",
               "Someone's life is in danger", 0.8),
    "humiliation": (r"\bmud\b|\bscrub|scullery|\bplain\b|worthless|low value|tolerate|embarrass|humiliat|"
                    r"laugh(s|ing)? at|nothing to offer|on your knees|discarded",
                    "She is humiliated in front of others", 0.7),
    "family_betrayal": (r"stepmother|my own (family|sister|father)|\bsister\b|\bdisown|disinherit|"
                        r"(your|my) (father|mother) (has|said|chose)|(the )?daughter (they|you) (choose|chose)",
                        "Her own family turns on her", 0.7),
    "comeuppance": (r"salute|treason|exposed|apprehend|by order of the crown|under arrest|bows? to|"
                    r"you have lost|it's over|no longer",
                    "The people who wronged her get caught out", 0.8),
    "romance": (r"\bkiss|love you|my wife|my husband|forehead|tender",
                "A romantic moment between the leads", 0.5),
}
# Which tropes are the show's *premise* is worked out per show from its title + first loglines
# (scoring.premise_tropes), so a new show needs no edits here.
