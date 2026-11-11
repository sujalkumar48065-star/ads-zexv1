#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ╔══════════════════════════════════════════════════════════════════╗
# ║  MEGA MARKETING BOT v5.0 - STRIPPED EDITION                      ║
# ║  Features: Accounts + Rejoin + Settings                           ║
# ╚══════════════════════════════════════════════════════════════════╝

import sys, subprocess, importlib
PACKAGE_MAP = {"python-telegram-bot": "telegram", "telethon": "telethon"}
PACKAGE_BINARY = ["groq"]
for pkg_name, import_name in PACKAGE_MAP.items():
    try: importlib.import_module(import_name)
    except ImportError:
        print(f"Installing {pkg_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_name, "-q"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

import asyncio, json, logging, re, random, os, html, time, io, zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Set
import traceback

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
    ChatMemberHandler, ChatJoinRequestHandler)
from telegram.constants import ParseMode

from telethon import TelegramClient
from telethon.errors import (SessionPasswordNeededError, FloodWaitError,
    ChannelPrivateError, ChannelInvalidError, InviteHashExpiredError,
    InviteHashInvalidError, UserAlreadyParticipantError, ChatWriteForbiddenError,
    UserPrivacyRestrictedError, UserNotMutualContactError, UserChannelsTooMuchError,
    UserKickedError, ChatAdminRequiredError, PeerFloodError,
    UsernameNotOccupiedError, UsernameInvalidError, ChatForbiddenError)
from telethon.tl.functions.channels import (JoinChannelRequest, LeaveChannelRequest,
    GetFullChannelRequest, GetParticipantsRequest, InviteToChannelRequest)
from telethon.tl.functions.messages import (ImportChatInviteRequest,
    CheckChatInviteRequest, AddChatUserRequest)
from telethon.tl.types import (ChatInviteAlready, InputPeerChannel, ChannelParticipantsSearch,
    InputPeerUser, Channel, Chat)
from telethon import functions
from telethon.sessions import StringSession

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m', 'INFO': '\033[32m', 'WARNING': '\033[33m',
        'ERROR': '\033[31m', 'CRITICAL': '\033[35m', 'RESET': '\033[0m'
    }
    def format(self, record):
        levelname = record.levelname
        color = self.COLORS.get(levelname, '')
        reset = self.COLORS['RESET']
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_message = f"{color}[{timestamp}] [{levelname:8}]{reset} {record.getMessage()}"
        if record.exc_info:
            log_message += f"\n{color}{traceback.format_exc()}{reset}"
        return log_message

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("MegaBot")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(ColoredFormatter())

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s:%(funcName)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except Exception:
        return int(default)

API_ID = _env_int("API_ID", 0)
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = _env_int("OWNER_ID", 0)
AUTHORIZED_USERS: set = set()
DATA_DIR = Path("user_data")
DATA_DIR.mkdir(exist_ok=True)

logger.info("BOT INITIALIZING - Mega Marketing Bot v5.0 (Stripped Edition)")
logger.info(f"Data Directory: {DATA_DIR.absolute()}")

def load_api_config():
    global API_ID, API_HASH, BOT_TOKEN, OWNER_ID
    config_file = Path("api_config.json")
    if config_file.exists():
        try:
            with open(config_file) as f:
                cfg = json.load(f)
                API_ID = cfg.get("api_id", API_ID)
                API_HASH = cfg.get("api_hash", API_HASH)
                BOT_TOKEN = cfg.get("bot_token", BOT_TOKEN)
                OWNER_ID = cfg.get("owner_id", OWNER_ID)
        except: pass

load_api_config()

# Conversation states
(PHONE, OTP, PASSWORD, CUSTOM_GAP, CUSTOM_CYCLES, SEND_LINKS,
 PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS, SET_API,
 WELCOME_TXT, INPUT_STATE, SET_API_ID, DISC_GAP_INPUT,
 SET_NAME, SET_BIO, SET_PFP, WAIT_FILE,
 SCRAP_TARGET, SCRAP_DELIVERY, SCRAP_GAP,
  GROUP_SET, GROUP_USER_INPUT, SCRAP_GIRLS_QTY, SCRAP_GIRLS_DELAY,
   GM_WELCOME, GM_RULES, GM_FILTER, GM_AF_MSGS, GM_AF_INT, GM_WARN_SET, BAN_GROQ, BAN_TARGET, BAN_SCAN_COUNT,
    BAN_REPORT_COUNT, BAN_REPORT_INTERVAL,
     SCRAP_USER_GAP, SCRAP_DAILY_LIMIT, AUTH_USER_ADD, SCRAP_GIRL_KW) = range(41)

active_tasks: Dict[int, Dict[str, asyncio.Task]] = {}
BOT_START_TIME = datetime.now()

def task_alive(user_id, key):
    t = active_tasks.get(user_id, {}).get(key)
    return t is not None and not t.done()

def any_task_alive(user_id, prefix):
    for k in list(active_tasks.get(user_id, {})):
        if k.startswith(prefix) and task_alive(user_id, k):
            return True
    return False

def rejoin_live(user_id, ud):
    r = ud.data.get("rej", {})
    if not r.get("running"):
        return False
    return task_alive(user_id, "rej") or any_task_alive(user_id, "rej_")

ABUSIVE_WORDS = {
    # ── Hindi (Devanagari) ──
    "मादरचोद","बहनचोद","लौडा","लोडा","भोसडी","भोसड़ी","चूत","लंड","लण्ड",
    "बकचोद","गांड","गाँड","हरामी","कमीने","हरामखोर","कुत्ता","सुअर","भेड़",
    "गधा","मूर्ख","बेवकूफ","साला","साली","बहन","माँ","मादर","चोद","चुदाई",
    "रंडी","वेश्या","भड़वा","भडवा","नंबरदार","नम्बरदार","चूतिया","चुतिया",
    "लवडा","लवड़ा","भोसदी","बोकाचोद","गांडू","गाँडू","मुर्गी","हिजड़ा",
    "छिनाल","कुतिया","नाजायज","हरामजादा","हरामजादी","बदमाश","बदजात",
    "गंडा","बेईमान","बेशर्म","बदतमीज","कमबख्त","बदबख्त","लौड़ा","लौड़े",
    "भोसड़ीके","भोसडिके","भोसडीके","भोसड़िके","माँचोद","बहनचोद","बहिनचोद",
    "बहनको","बहिनको","बहनके","बहिनके","मादरके","मादरको","चुदवाना","चुदाओ",
    "चोदो","चोदना","चुदकर","चुदने","चूची","चूचा","चूतड़","गांडू","गांड",
    "गांडफाड़","गांडमार","गांड में","गांडू","गांडिया","गांडी","गुदा","गुद",
    "भोसड़ी","भोसडी","भोसड़ी","भोसड़ा","भोसडा","भोसड़ा","लंड","लौड़ा","लौड़",
    "लौड","लोडा","लंडू","लंडिया","लोडू","बकचोदी","बकचोद","बकवास","बकवासी",
    "हरामखोर","हरामी","हरामजादा","हरामजादी","हरामि","हरामजात","बेवकूफी",
    "बेवकूफ","बेवकुफ","बेवकुफी","नालायक","नालायकी","बदमाशी","बदमाश",
    "बदतमीजी","बदतमीज","बदसलूकी","झाट","झाटू","झाटा","मादरजात","मादरजाद",
    "बहनजात","बहनजाद","चुदई","चुदाइ","चुदवाई","चुदक्कड़","चुदक्कड़",
    "गांडू","गांडू","गांडू","लवड़े","लवडे","लवडा","लवड़ा","भोसदीके",
    "पागल","पगली","पगलापन","कमीना","हरामी","भड़वा","भडवा","भडवी","भड़वी",
    # ── English ──
    "fuck","fucking","fucker","fucked","fucks","f*ck","fck","fuuck","fuk","f_u_c_k",
    "f00k","phuck","f@ck","f***","fk","f&ck","fuq","phuk","fukz","fukd","fok",
    "shit","sh*t","sht","shiit","shyt","sh!t","sh1t","shhit","$hit","s*it","shii",
    "shiitt","sht","sh!t","sh1t","sht","shet","shiete","shite","sheeit",
    "ass","arse","a$s","@ss","a55","*ss","asshole","a**hole","ashole","arsehole",
    "assholes","asshat","asswipe","assclown","assface","assfuck","assbag","asshead",
    "bitch","b*tch","bich","beetch","biatch","b1tch","b!tch","btch","biatc","beeatch",
    "bitches","bitching","bitchy","bithc","byatch","beyotch",
    "whore","hore","wh*re","whoor","whoar","whoor","hor","wh0re",
    "cunt","c*nt","k*nt","cnt","cun","cuntz","cunts","cun7",
    "dick","dik","d1ck","d*ck","di*k","d!ck","dicc","dic","dyck","diq",
    "dickhead","dickweed","dickface","dickhole","dickwad","dickbag",
    "cock","c0ck","c*ck","kock","cok","c@ck","coc","coq","cawk","cockface","cockhead",
    "pussy","p*ssy","pusy","pussi","pu55y","p@ssy","p*ssi","pusi","poosy","poossy",
    "pussies","puss","puzzy","pussay",
    "bastard","b*stard","basterd","b@stard","bastid","basturd","bastarrd","bastardz",
    "slut","sl*t","slvt","sl@t","s1ut","sloot","slutty","slutt","slutz","slt",
    "damn","d*mn","damm","dam","damnit","dammit","d@mn",
    "piss","p*ss","p$s","p1ss","pissed","pisser","pissing","piss off",
    "motherfucker","motherf*cker","mf","mofo","motherfukr","motherfuk","mothafucka",
    "mothafucker","muthafucker","muthafucka","mfer",
    "bullshit","bullsh*t","bs","b*llshit","bullshite","bulshit","bullsh!t",
    "douche","douchebag","douchecanoe","douchebaggery",
    "goddamn","goddam","goddammit","goddamnit","goddam",
    "jackass","jackassery",
    "bollocks","bollox",
    "wanker","wank","wanking","wanked","wanksta",
    "twat","twatt","twatface","twatwaffle",
    "dumbass","dumbfuck","dumbfucker",
    "shithead","shithead","shitface","shitbag","shitstain",
    "dickhead","dickface","dickwad",
    "cockhead",
    "retard","retarded","retardation","r3tard",
    "faggot","f*ggot","fag","f@g","f4g","phaggot","faggit",
    "nigger","n*gger","nigga","n1gga","niggah","niggar",
    "prick","prickface",
    "crap","crapper","crappy",
    "hell","hellhole",
    "damnation",
    "screw","screw you","screwed","screwing",
    "cripple",
    "spic","spic",
    "chink","ch*nk",
    "kike","k*ke",
    "gook","g00k",
    "wetback",
    "tard",
    "mongoloid",
    "imbecile",
    "moron","moronic",
    "idiot","idiotic",
    "stupid","stupidity","stoopid",
    "sucker","suck","sucks","sucked","sucking",
    "dipshit",
    "dumbshit",
    "pecker","peckerhead",
    "dildo","dildos",
    "vibrator",
    "bimbo",
    "prostitute","prosti",
    "pimp",
    "hussy",
    "tramp",
    "skank","skanky",
    "ho","hoe","ho3",
    "thot",
    "milf",
    "cougar",
    # ── Hinglish ──
    "madarchod","maderchod","madrchod","mdrchod","mc",
    "behnchod","bhenchod","bhenchood","bhenkchod","bhenkelode","bc","bkl",
    "bsdk","bsd","bhsdk","bhensdk","bklode","bklodi","bklod",
    "bhosdike","bhosdi","bhosdike","bhosdikeh","bhosdk","bhosdike","bhosdiwala",
    "chutiya","chutiye","chut","chutiyaa","chutmarani","chutad","chutad",
    "chutiyapa","chutiyagiri","chutiyo",
    "lund","lund","lun","lunnd","lundpila","lundbazzi","lundu","lundo",
    "lavde","lavda","lauda","laude","loda","lowda","lode","lodu","lodo",
    "gandu","gandu","gandoo","gandwe","gandvo","gandu",
    "randibaaz","randi","rande","rand","randipana","randibaazi",
    "bhadva","bhadwa","bhadva","bhadve","bhadwo","bhadwi",
    "chod","chuda","chudai","chudachudi","chodo","chode","choda",
    "terimaa","terimaaki","terimaakich","terimaa ki","behenkilodi","behen ki",
    "bhosad","bhosada","bhosad",
    "madarjaat","madarjaat",
    "sala","sali","salo","sale",
    "kamina","kaminey","kamine","kaminay",
    "harami","haramzada","haramkhor","harami",
    "kutti","kutta","kutte","kutto","kuttho",
    "suar","suwar","suar",
    "bhed","gadha","gadhe","murkh","bewakoof","bewakuf","bewakoof",
    "bakchod","bakchodi","bakchodo","bakchode",
    "fattu",
    "nalayak","nalaik",
    "nikamma","nikamm",
    "badtameez","badtameej","badmash","badtameezi",
    "jhatu","jhat","jhaant","jhaantu","jhaant",
    "lauda","laude","lode","lol",
    "chuchi","chuchu","chuchaa","chuchi",
    "bob","boob","boobs",
    "gaand","gaandu","gaand",
    "magga","magge","maggay",
    "fuddu","fuddu",
    "makkichod",
    "makkhi",
    "kotha","kothi",
    "ullu","ulla","ullukapaat",
    "bhenchod",
    "maachod","maachuda",
    "teri maa ki","teri maa","teri behen ki",
    "bhosdina",
    "chutad",
    "gandu",
    "lavdya",
    "chodina",
    "jhaant",
    "jhaant ke baal",
    "chhapri","chhapri",
    # ── Tamil ──
    "dei","dey","da","di","po","poda","podi","punda","pundai","kunna",
    "koothi","moothi","oombu","summa","suthi","sunda","kazhuda","kazhudha",
    "mairu","mair","olu","olunga","kasu",
    "thayoli","thayolai","thayolikk",
    "soothu","soothu mairu","soothu mair",
    "poda kazhuda","pode kazhuda",
    "dei maire",
    "mairu kazhudha",
    "thayoli koothi",
    "thayolikk",
    "ayyo","ambala",
    "pannu","pannunga",
    "thallu","thalli",
    "vetti",
    "koodhi","koodhi",
    "mounda","moundi",
    "oppari","oppari",
    "koothi","kuthi",
    # ── Telugu ──
    "pooku","puku","pukulu","gudda","guddalu","mooda","moodi",
    "lanja","lanjakoduku","lanjala",
    "pichodi","pichodi",
    "buddabukka","bukka",
    "donga","dongala","donga lanja",
    "munda","mundi",
    "talli","talli gudda",
    "nali","nali",
    "p*ck",
    "guddha","guddu",
    "linga","lingam",
    "pilli",
    "nayala","nayalakoduku","nayala",
    "guddhi",
    "pookulu", "pookuni",
    "buvva", "buvvagudda",
    # ── Kannada ──
    "shale","shale maga","shale magane",
    "sule","sule maga",
    "munde","munda",
    "hattari",
    "kuddi","kudri",
    "goobe","goobi","goobe magane",
    "kattale",
    "dodda",
    "thayi",
    "munde maga",
    "linga", "lingayya",
    "dodd",
    "kalla","kallu","kallanu",
    "chooru", "choor",
    "buddhi", "buddhi maga",
    # ── Malayalam ──
    "thayoli","thayolikk","thayolee",
    "myre","mairu","maire","thallu",
    "avalkk","avan","avante",
    "choodi","choodu",
    "kotham","koothara","kootham",
    "patti","pattikk",
    "mindan","minda","mindan",
    "nayinte","naye","nayikk",
    "thendi","thendikk","thendi",
    "kallan","kalla","kalli",
    "punda","pundakk",
    "kundi",
    "kantha",
    "kotham",
    "kanni",
    "chovva", "chov",
    # ── Marathi ──
    "bhosdya","bhosdyacha","bhosad","bhosdyavar",
    "gaand","gandu","gandya",
    "chod","chodicha","chodina",
    "aai","aaila","aai zhavala","aai jhavala",
    "lavdya","lavdicha",
    "kutha","kuthyavar","kuthya",
    "suvar","suvrya","suvar",
    "bakrichod","bakrichod",
    "chodu","choda","chode",
    "randicha","randi",
    "zhaval","jhaval",
    "maderchod",
    "behenchod",
    "sala","sali",
    "kamine",
    "harami",
    # ── Gujarati ──
    "bhosdo","bhosdiyo","bhonsdi",
    "chodo","choda","choda",
    "gaandu","gando",
    "lavdo","lavda",
    "randi","rande",
    "maderchod",
    "behenchod",
    "sala","sali","salu",
    "kamine","kaminu",
    "harami",
    "kutti","kutta",
    "suar","suar",
    "bakchod","bakchodi",
    "chhapri",
    "maggu",
    "ullu",
    # ── Punjabi ──
    "maderchod","maderchoda",
    "behenchod","behenchoda",
    "bhenji","bhen ji",
    "khotey","khoteya",
    "chodu","chodi","chode",
    "gaandu","gandu","gaand",
    "lann","lann de","lann da",
    "randi","randi da puttar",
    "kuttay","kutti","kutte","kutta",
    "sala","sali","sale",
    "harami","haramia",
    "bhadva","bhadva",
    "nikamma",
    "nalayak",
    "jhattu","jhattu",
    "lunn","lunn",
    "fuddu",
    # ── Bengali ──
    "magi","magir","magiya",
    "choda","chodon","chodar",
    "bhosdok","bhosdi","bhosdok",
    "gandu","gandu",
    "shala","shali","shalar",
    "boka","bokachoda","bokachoda",
    "randi","randir","randir",
    "kutta","kuttar","kuttir",
    "shuor","shuor",
    "gadha","gadhar",
    "murkho","murkher",
    "nalish","nalish",
    "badtameez","badtameezi",
    "choda","chodi",
    "magi randi",
    "shala kutta",
    "shali magi",
    "bapir pola",
    "maye r marod",
    "putkir",
    # ── Urdu / Farsi derived ──
    "laanat","laanati",
    "kameena","kameeni",
    "badmash","badmashi",
    "haram","harami",
    "zaalim",
    "jahil",
    "jaahil",
    "begairat","begairati",
    "najayaz",
    "badkar","badkari",
    "fahash","fahashi",
    "badtameez",
    "nalaik",
    # ── Numbers/symbols variations of common words ──
    "f*ck","f**k","f***","f****","f ck","f.u.c.k","fuc*","fu*k",
    "fukc","fukked","fukker","fukkin",
    "phuk","phukd","phukking","phucker",
    "sh!t","sh1t","sh!!!!t","shi*t","shhit","shiit",
    "b!tch","b1tch","b****","biiatch",
    "a55","@ss","a$$","a*s","as*",
    "d1ck","d*ck","d!ck","d1c",
    "c0ck","c*ck","c0k","cok",
    "p*ssy","p*ssi","pu55y","p@ssy",
    "b*stard","b@stard",
    "sl*t","sl@t","s1ut",
    "m0therfucker","m0thafucka",
    "n*gger","n1gga","n1gger","n*gga",
    "f4g","f@g","f4ggot",
    "b0llocks","b0llox",
    "tw4t",
    "cr4p",
    "sh1thead",
    "d1ckhead",
    "c0ckhead",
    "4ss","@rse",
    # ── Short forms / internet slang ──
    "wtf","stfu","lmfao","af","bf","gf",
    "milf","gilf","dm","pm",
    "nude","naked","sex","sexy","sexual",
    "porn","porno","pornhub","xnxx","xvideos",
    "penis","penile","vagina","boobs","boobies","boobie",
    "tits","titty","titties","titt",
    "dildo","dildos","vibrator","buttplug",
    "blowjob","bj","handjob","rimjob",
    "cum","cumshot","cumming","cummies","semen",
    "sperm","orgasm","masturbate","masturbation","masturbating",
    "anal","analsex",
    "bukkake",
    "gangbang",
    "facial",
    "creampie",
    "bareback",
    "incest",
    "rape","raping","rapist",
    "pedo","pedophile","paedophile",
    "bestiality",
    "bdsm",
    "domination",
    "submission",
    "slave","master",
    "kink","kinky",
    "fetish",
    "orgy",
    "threesome",
    "foursome",
    "squirt","squirting",
    "ebony",
    "teen",
    "mature",
    "amateur",
    "camgirl",
    "webcam",
    "sexting",
    "dirty talk",
    "nsfw",
    "horny",
    "horni",
    "aroused",
    "erotic",
    "erotica",
    "xxx",
    "adult content",
    "onlyfans",
    "fansly",
    "pattreon",
    # ── Additional English variations ──
    "ahole","azzhole","azz","assmonkey","asshat","assclown","asspimple","asspirate",
    "asshopper","assmunch","asswipe","asswad","assbandit","assranger","assface",
    "assbasket","assbite","asscock","assdick","assfuck","assgoblin","asshead",
    "assjacker","asskisser","asslicker","assmaster","assmonkey","assmuncher",
    "assneck","asspacker","asspain","asspuppet","assrat","asssniffer","asssucker",
    "asstard","asstool","assvampire","asswart","asswizard","assworm",
    "beastial","beastiality","bestial",
    "bloodclaat","bloodclat","bumbaclot","bumclat",
    "choad","chode","chodi","choty",
    "clit","clitoris","clitty",
    "cocksucker","cocksucking","cocksuc",
    "cunilingus","cunnilingus",
    "cumdumpster","dumass",
    "dumbfuck","dumfuck",
    "fagbag","fagfucker","faggot",
    "fanny","fannypack","fannyhole",
    "felch","felching",
    "fistfuck","fistfucking","fisting",
    "flamer","flamer",
    "frotting",
    "goatse",
    "egoblowjob",
    "gringo",
    "guido",
    "handjob",
    "hardon","hard on",
    "honkey","honky",
    "hooters",
    "humping",
    "incestuous",
    "jerk","jerk off","jerkoff","jerking",
    "jizz","jizm","jissom",
    "kaw","kawk",
    "knobjockey","knobjocky",
    "kunt","kunts",
    "labia",
    "lemonparty",
    "lesbo","lezbo","lezzie",
    "lube","lubricant",
    "lust","lusting",
    "meat","meatspin",
    "menage",
    "muff","muffdiver","muffdiving",
    "nob","nobjockey",
    "nutsack",
    "nutjob",
    "opiate",
    "orifice",
    "painfuck",
    "pecker","peckerwood",
    "pedophile","pedo","pederast","pederasty",
    "pegging",
    "phuck","phuk",
    "pi55","pish",
    "pissoff",
    "poop","poo","poophead",
    "porno","pornographic","pornography","porn",
    "priapus",
    "prolapse",
    "pube","pubes","pubic",
    "punani","punanny","poontang","poontang",
    "queaf","quim",
    "raghead",
    "rape","raping","rapist","raped",
    "rectum","rectal",
    "rim","rimjob","rimming",
    "sausage",
    "scat","scatology",
    "schlong",
    "scissoring",
    "semen",
    "shag","shagging",
    "shemale",
    "s hit","s hit",
    "shitter","shitting",
    "skank","skanky",
    "skeet",
    "slag",
    "slutbag","slutbucket","slutdumper",
    "smegma",
    "snatch",
    "sodomize","sodomy","sodom",
    "spank","spanking",
    "spermicide",
    "spic","spick",
    "spoo","spooge",
    "spunk",
    "stfu",
    "strap on","strapon","strap-on",
    "strip","stripper","stripclub",
    "swallow","swallowing","swallower",
    "swastika",
    "taint",
    "tantric",
    "tard","tardo",
    "teabag","teabagging",
    "testicle","testicles","testi",
    "titfuck","titfucking","tittyfuck",
    "towelhead",
    "trannie","tranny","transexual","transsexual",
    "turd",
    "tush","tushy","tushie",
    "twink","twinkie",
    "undressing",
    "urinal","urine","urinate",
    "uterine",
    "vajayjay",
    "vibrator",
    "vulva",
    "wad","wads",
    "wang",
    "wank","wanker","wanking","wanksta","wankjob",
    "wet dream",
    "whoralicious",
    "xrated",
    "zoophile","zoophilia",
    # ── Additional Hindi ──
    "अंड","अंडकोश","अंडे","अंडा",
    "अपवित्र","अश्लील","अश्लीलता",
    "औरतजादा","औरतजात",
    "कमीनी","करमीनी","कसाई",
    "कुतरा","कुतरी",
    "खड़ा","खड़ी","खड़े",
    "खोटा","खोटी","खोटे",
    "गंदगी","गंदा","गंदी","गंदे",
    "गलत","गलती",
    "गाली","गालियाँ",
    "गुदा","गुद",
    "घिनौना","घिनौनी",
    "चमचा","चमची",
    "चरित्रहीन",
    "चिड़िया","चिड़ी",
    "चुदक्कड़",
    "चूस","चूसो","चूसना",
    "छी","छी थू",
    "जड़","जड़ता",
    "जहर","जहरीला",
    "झगड़ालू",
    "टट्टी",
    "ठग","ठगी",
    "डमी",
    "तंग",
    "तमीज",
    "थर्क","थर्की","थर्कू",
    "थू","थू थू",
    "दलाल","दलाली",
    "दुष्ट","दुष्टता",
    "धत्","धत्त",
    "धोखा","धोखेबाज",
    "नकली",
    "नंगा","नंगी","नंगे",
    "नजायज",
    "नालायकी",
    "निचोड़","निचोड़ना",
    "नीच","नीचता",
    "बकचोद",
    "बदबू","बदबूदार",
    "बदसूरत",
    "बहिन","बहिनचोद",
    "बिगड़ा","बिगड़ी",
    "बेईमानी",
    "बेकार",
    "बेचैन",
    "बेटा","बेटी","बेटे",
    "बेवकूफी",
    "बेशर्मी",
    "बेहूदा","बेहूदगी",
    "भड़भड़िया",
    "भाड़","भाड़ में","भाड़में",
    "भाभी",
    "भेड़चोद",
    "भोंडा","भोंडी","भोंडे",
    "मक्खीचोद",
    "मटरगश्त",
    "मल",
    "माँचोद",
    "मांगे","मांगी",
    "मार","मारो","मारना",
    "मूत्र",
    "मैला","मैली",
    "लफड़ा","लफड़ेबाज",
    "लात","लातें",
    "लालची",
    "लोभी",
    "वाहियात",
    "शर्मनाक",
    "शैतान",
    "सड़ा","सड़ी","सड़े",
    "सड़ांध",
    "संभोग",
    "सालो","साले",
    "हग","हगना","हग्गी",
    "हजामत",
    "हरकत",
    "हिजड़ापन",
    "हीलाहवाला",
    # ── Additional Hinglish ──
    "aand","aandu","aandu",
    "bakwas","bawasir",
    "bhadva","bhadvi",
    "bhadwe",
    "bhadwo",
    "bhains","bhains ki aankh",
    "bhara hua",
    "bhootni",
    "bhosdiwala",
    "bsdk",
    "chachu",
    "chaman chutiya",
    "chandu",
    "charsi",
    "choti",
    "chudne",
    "chudwa",
    "chudwane",
    "chup",
    "chup be",
    "chup kar",
    "chutiya",
    "chutiyon",
    "dalali",
    "dalle",
    "dallu",
    "dhakkan",
    "dhokha",
    "dhokhebaaz",
    "doglapan",
    "fukra",
    "gadhe",
    "gadhi",
    "gaand",
    "gaandfat",
    "ghatiya",
    "ghoda","ghode",
    "goo",
    "goo kha",
    "hag",
    "hagdi",
    "haggu",
    "hijra",
    "hijron",
    "jhantu",
    "jhant",
    "jhuth","jhuta","jhuti",
    "kaleja",
    "kamini",
    "kanjar",
    "kathor",
    "kattar",
    "khar",
    "khotte",
    "khoti",
    "khotta",
    "kutti",
    "kuttiya",
    "laat",
    "laata",
    "lanat",
    "lanati",
    "launda",
    "laundi",
    "lund",
    "lundu",
    "lunj",
    "maggay",
    "makkhi",
    "makkhi ki",
    "mama",
    "mami",
    "mamta",
    "mara hua",
    "maar",
    "masi",
    "mausi",
    "mausa",
    "mitha",
    "mithi",
    "moh mata",
    "mooh",
    "moron",
    "motu",
    "muh",
    "muh me le",
    "muth",
    "muth marne wala",
    "naach",
    "naachne wali",
    "najariya",
    "nakli",
    "nalayak",
    "nalik",
    "nanga",
    "nangi",
    "nange",
    "nikamma",
    "nikali",
    "nunna",
    "nunnu",
    "padosi",
    "pagal",
    "pagli",
    "pagli",
    "pataka",
    "patli",
    "pichwada",
    "pichwade",
    "pila",
    "pili",
    "pille",
    "porkistan",
    "randi",
    "randi rona",
    "rasi",
    "rasse",
    "sadhu",
    "sadma",
    "sadme me",
    "sagai",
    "saale",
    "saali",
    "sadgi",
    "sala haraamkhor",
    "sali harami",
    "samjha",
    "samjhi",
    "samjho",
    "sanda",
    "sandali",
    "sasti",
    "sasta",
    "satega",
    "sategi",
    "satte",
    "sawari",
    "sawari kar",
    "sawari karne wala",
    "sawari karne wali",
    "sexy",
    "shaadi",
    "shadi",
    "shaitaan",
    "shakal",
    "shameless",
    "sharam",
    "sharminda",
    "sharmindagi",
    "sharif",
    "sharirik",
    "shehar",
    "shera",
    "shikaar",
    "shikaari",
    "shikayat",
    "shikayati",
    "shoch",
    "shoch kar",
    "shochne wala",
    "suit",
    "suit kar",
    "suiti",
    "suiti karo",
    "suiti karne wala",
    "suiti karne wali",
    "sulpha",
    "supha",
    "supari",
    "supari le",
    "suraj",
    "surma",
    "swarag",
    "takiya",
    "takleef",
    "tan",
    "tandoori",
    "tanga","tangi","tange",
    "tapu",
    "tarah",
    "tarka","tarki","tarkari",
    "tashan",
    "tatti",
    "tawar",
    "teer",
    "tharki","tharkipana","tharkapan",
    "tharrap",
    "thoka","thoki","thoke","thokar",
    "thullu",
    "tikat",
    "tikuli",
    "tinka",
    "tinku",
    "toda","todi","tode",
    "todu",
    "tokri",
    "tokro",
    "tola",
    "tolya",
    "toola",
    "topa",
    "topi",
    "tora",
    "tori",
    "torna",
    "tosak",
    "tota","toti","toto",
    "totta","totti","tottu",
}

def _a(uid):
    if isinstance(uid, int): return uid == OWNER_ID
    u = getattr(uid, 'effective_user', None) or getattr(uid, 'from_user', None)
    return u.id == OWNER_ID if u else False

def h_delay(base=None):
    if base is None or base == 0: return 0.5
    return max(0.5, base * (0.7 + random.random() * 0.6))

def log_activity(user_id, action):
    try:
        log_file = DATA_DIR / f"{user_id}_activity.log"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {action}\n")
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")

async def send_alert(bot, user_id, message):
    try:
        await bot.send_message(chat_id=user_id,
            text=f"SYSTEM ALERT\n\n{html.escape(message)}",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        logger.warning(f"Failed to send alert: {e}")

async def notify_progress(bot, user_id, text):
    """Send a live task log to the task owner and the bot owner (deduped)."""
    targets = []
    for t in (user_id, OWNER_ID):
        if t and t not in targets:
            targets.append(t)
    for t in targets:
        try:
            await bot.send_message(chat_id=t, text=text,
                parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        except Exception as e:
            logger.debug(f"notify_progress to {t} failed: {e}")

async def notify_owner(bot, text):
    """Send an event log to the bot owner only."""
    if not OWNER_ID:
        return
    try:
        await bot.send_message(chat_id=OWNER_ID, text=text,
            parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        logger.debug(f"notify_owner failed: {e}")

def esc(text):
    return html.escape(str(text))

def format_gap(seconds):
    if seconds is None: return "30s"
    if seconds >= 3600: return f"{seconds//3600}h{(seconds%3600)//60}m"
    if seconds >= 60: return f"{seconds//60}m{seconds%60}s"
    return f"{seconds}s"

# Human-like delay patterns for safe mode
_HUMAN_PATTERNS = [
    # Single wait
    lambda: random.uniform(5, 10),
    # Two-step: short pause then main wait
    lambda: random.uniform(1, 3) + random.uniform(4, 8),
    # Three-step: simulate hesitation
    lambda: random.uniform(0.5, 1.5) + random.uniform(1, 3) + random.uniform(3, 6),
    # Burst pattern: quick actions then pause
    lambda: random.uniform(0.3, 0.8) + random.uniform(5, 9),
    # Stutter pattern
    lambda: random.uniform(2, 4) + random.uniform(0.5, 1.5) + random.uniform(2, 5),
]

async def human_wait(extra_variance=0):
    """Simulate human-like delay with random patterns (5-10s range)."""
    pattern = random.choice(_HUMAN_PATTERNS)
    total = pattern()
    if extra_variance:
        total += random.uniform(-extra_variance, extra_variance)
    total = max(3, min(15, total))
    await asyncio.sleep(total)

def normalize_link(text):
    seen = set()
    def add(link):
        link = link.rstrip('/').rstrip('.')
        if link not in seen:
            seen.add(link)
            return link
        return None
    text = text.strip()
    if not text:
        return []
    # 1) Full URLs: https://t.me/... or http://t.me/...
    for m in re.finditer(r'https?://t\.me/([^\s<>"\'\]\)]+)', text):
        raw = m.group(0)
        link = add(raw)
    # 2) Bare t.me/... paths (no protocol) — min 5 chars, not pure number
    for m in re.finditer(r'(?<!https://)(?<!http://)t\.me/([a-zA-Z0-9_+\-]{5,})', text):
        path = m.group(1)
        if not path.lstrip('+').isdigit():
            link = add("https://" + m.group(0))
    # 3) @username patterns
    for m in re.finditer(r'(?<!\w)@([a-zA-Z0-9_]{5,32})(?!\w)', text):
        link = add("https://t.me/" + m.group(1))
    # 4) Numeric IDs (chat IDs) — fallback per-part
    parts = re.split(r'[\s,;]+', text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if re.match(r'^-?\d+$', part):
            if part.startswith("-100"):
                add("https://t.me/c/" + part[4:])
            elif part.startswith("-"):
                add(part)
            elif len(part) >= 9:
                add("https://t.me/c/" + part)
    return list(seen)

async def check_link_dead(client, link):
    try:
        if "t.me/+" in link or "joinchat" in link:
            from telethon.tl.functions.messages import CheckChatInviteRequest
            h = link.split("/")[-1].replace("+","")
            invite = await client(CheckChatInviteRequest(h))
            from telethon.tl.types import ChatInviteAlready
            if isinstance(invite, ChatInviteAlready):
                return False
            return False  # invite is valid (even if not joined)
        else:
            await client.get_entity(link)
            return False
    except (InviteHashExpiredError, InviteHashInvalidError, ValueError,
            ChannelPrivateError, ChannelInvalidError, UserAlreadyParticipantError):
        return True
    except Exception:
        return True

async def auto_show_next_link(uid, context, msg_or_query, ud):
    queue = context.user_data.get("approval_queue", [])
    idx = context.user_data.get("approval_index", 0)
    rej = ud.data["rej"]

    if not queue or idx >= len(queue):
        context.user_data["approval_queue"] = []
        if isinstance(msg_or_query, Update):
            await msg_or_query.message.reply_text(
                "✅  <b>All Links Processed!</b>", parse_mode=ParseMode.HTML,
                reply_markup=rejoin_menu(ud))
        else:
            await msg_or_query.edit_message_text(
                "✅  <b>All Links Processed!</b>", parse_mode=ParseMode.HTML,
                reply_markup=rejoin_menu(ud))
        return

    # Get a client to verify link
    phone = get_gm_client(ud)
    client = await get_client(phone, ud) if phone else None

    while idx < len(queue):
        link = queue[idx]
        dead = False
        if client:
            dead = await check_link_dead(client, link)
        if dead:
            if link not in rej.get("blacklist", []):
                rej.setdefault("blacklist", []).append(link)
            if link in rej.get("approved", []):
                rej["approved"].remove(link)
            ud.save()
            idx += 1
            context.user_data["approval_index"] = idx
        else:
            break

    if client:
        await client.disconnect()

    if idx >= len(queue):
        context.user_data["approval_queue"] = []
        text = "✅  <b>All Links Processed!</b>\n━━━━━━━━━━━━━━━━━━\nDead links auto-blacklisted."
        if isinstance(msg_or_query, Update):
            await msg_or_query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
        else:
            await msg_or_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
        return

    link = queue[idx]
    if isinstance(msg_or_query, Update):
        await msg_or_query.message.reply_text(
            f"📎  {link}\n📌  {idx+1} / {len(queue)}",
            parse_mode=ParseMode.HTML, reply_markup=approval_menu())
    else:
        await msg_or_query.edit_message_text(
            f"📎  {link}\n📌  {idx+1} / {len(queue)}",
            parse_mode=ParseMode.HTML, reply_markup=approval_menu())

def get_uptime():
    delta = datetime.now() - BOT_START_TIME
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"

def is_authorized(uid: int) -> bool:
    return uid == OWNER_ID or uid in AUTHORIZED_USERS

def load_authorized_users():
    global AUTHORIZED_USERS
    f = DATA_DIR / "authorized_users.json"
    if f.exists():
        try:
            with open(f) as fp:
                AUTHORIZED_USERS = set(json.load(fp))
        except Exception:
            pass

def save_authorized_users():
    f = DATA_DIR / "authorized_users.json"
    with open(f, "w") as fp:
        json.dump(list(AUTHORIZED_USERS), fp)

load_authorized_users()

class UserData:
    def __init__(self, user_id):
        self.user_id = user_id
        self.file_path = DATA_DIR / f"{user_id}_data.json"
        self.data = {
            "acc": {},
            "rej": {"approved":[],"denied":[],"blacklist":[],"gap":30,"cycles":0,
                "safe_mode":False,"running":False,"joined_count":0,"left_count":0,
                "include_discussions":True,"disc_gap":2,"auto_rejoin_on_kick":True,
                "use_all_acc":False,"priority":False,"member_counts":{},"auto_approve":False,
                "last_error":"","last_heartbeat":"","session_started":"","last_stop_at":""},
            "scraper": {"target":"","delivery":"","gap":3,"running":False,"scraped":0,
                        "user_gap":60,"daily_limit":0,"scraped_today":0,"last_scrape_date":"",
                        "mode":"send","add_gap":20,"add_running":False,"pending":[],
                        "add_added":0,"add_failed":0,"member_mode":"all","girl_keywords":"",
                        "added_uids":[],"source_used":"","found_total":0,"last_error":"",
                        "per_acc":{},"add_skipped":0},
            "gm": {"group_id":0,"group_title":"","notify":True,"join_reply":True,
                   "join_reply_text":"{username} Your request is received to join {grouptitle} received sweetie and it will accept soon.",
                   "welcome_enabled":False,"welcome_text":"Welcome {name} to {title}!",
                   "rules_enabled":False,"rules_text":"",
                   "filters":[],"antiflood":{},"antiflood_msgs":5,"antiflood_interval":3,"antiflood_action":"mute","warn_max":3,"media_filter":False,"link_filter":False,"bio_filter":False,"link_delete_msg":"⚠️  {first}, please remove links from your bio and don't share group/channel links here."},
            "scrap_girls": {"sources":[],"qty":50,"delay":3,"running":False,"scraped":0,"filename":"","name_filter":True},
            "banning": {"groq_api":"","target":"","target_type":"","running":False,"reports":[],"msg_limit":5000},
            "proxy": {"enabled":False,"host":"","port":0,"username":"","password":"","type":"socks5"},
            "welcome_msg": {"enabled":False,"text":"Welcome!"},
            "stats": {"total_joined":0,"total_left":0,
                      "uptime_start":None,"created_at":datetime.now().isoformat()},
        }
        self.load()

    def load(self):
        if self.file_path.exists():
            try:
                with open(self.file_path) as f:
                    loaded = json.load(f)
                    self._deep_merge(self.data, loaded)
            except Exception as e:
                logger.error(f"Failed to load user data {self.user_id}: {e}")

    def _deep_merge(self, base, override):
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._deep_merge(base[k], v)
            else:
                base[k] = v

    def save(self):
        tmp = self.file_path.with_suffix(".tmp")
        try:
            with open(tmp, "w") as f:
                json.dump(self.data, f, indent=2)
            tmp.rename(self.file_path)
        except Exception as e:
            logger.error(f"Failed to save data: {e}")
            if tmp.exists():
                tmp.unlink()

USER_DATA_CACHE: Dict[int, UserData] = {}

def get_user_data(user_id) -> UserData:
    if user_id not in USER_DATA_CACHE:
        ud = UserData(user_id)
        if user_id not in active_tasks:
            active_tasks[user_id] = {}
        USER_DATA_CACHE[user_id] = ud
    return USER_DATA_CACHE[user_id]

CLIENT_ERRORS: Dict[str, str] = {}

async def get_client(phone, user_data) -> Optional[TelegramClient]:
    accs = user_data.data.get("acc", {})
    if phone not in accs:
        CLIENT_ERRORS[phone] = "account not found in list"
        logger.warning(f"Phone {phone} not in accounts")
        return None
    session_str = accs[phone].get("ss","")
    if not session_str:
        CLIENT_ERRORS[phone] = "no session saved — re-login account"
        logger.error(f"Account {phone} has no session")
        return None
    px = user_data.data.get("proxy", {})
    proxy = None
    if px.get("enabled") and px.get("host"):
        from telethon import connection
        ptype = {"socks5": connection.Connection.Socks5Type,
                 "http": connection.Connection.HttpType}.get(
            px.get("type","socks5"), connection.Connection.Socks5Type)
        proxy = (ptype, px["host"], int(px.get("port", 0)), px.get("username",""), px.get("password",""))
    last_err = "unknown"
    for attempt in range(2):
        client = None
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH, proxy=proxy,
                connection_retries=1, request_retries=2, timeout=30)
            await asyncio.wait_for(client.connect(), timeout=60)
            if not await asyncio.wait_for(client.is_user_authorized(), timeout=10):
                last_err = "session expired / logged out — re-login account"
                logger.error(f"Account {phone} is not authorized")
                user_data.data["acc"][phone]["active"] = False
                user_data.save()
                await client.disconnect()
                CLIENT_ERRORS[phone] = last_err
                return None
            CLIENT_ERRORS.pop(phone, None)
            return client
        except asyncio.CancelledError:
            if client:
                try: await client.disconnect()
                except: pass
            raise
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:120]}"
            logger.error(f"Failed to get client for {phone} (try {attempt+1}/2): {last_err}")
            if client:
                try: await client.disconnect()
                except: pass
            if attempt == 0:
                await asyncio.sleep(2)
    CLIENT_ERRORS[phone] = last_err
    return None

RESOLVE_ERRORS: Dict[str, str] = {}

async def resolve_entity(client, link):
    """Resolve a public/invite link to an entity without failing on already-joined."""
    RESOLVE_ERRORS.pop(link, None)
    try:
        if "t.me/+" in link or "joinchat" in link:
            h = link.split("/")[-1].replace("+", "")
            try:
                up = await client(ImportChatInviteRequest(h))
                if getattr(up, "chats", None):
                    return up.chats[0]
            except UserAlreadyParticipantError:
                try:
                    inv = await client(CheckChatInviteRequest(h))
                    if isinstance(inv, ChatInviteAlready):
                        return inv.chat
                except Exception:
                    pass
                try:
                    return await client.get_entity(link)
                except Exception:
                    pass
            RESOLVE_ERRORS[link] = "invite link expire/invalid hai — naya link bhejo"
            return None
        return await client.get_entity(link)
    except Exception as e:
        logger.warning(f"resolve_entity({link}): {e}")
        RESOLVE_ERRORS[link] = _resolve_fail_reason(e)
        return None

def _resolve_fail_reason(e):
    if isinstance(e, (InviteHashExpiredError, InviteHashInvalidError, ValueError)):
        return "invite link expire ya invalid hai — naya link bhejo"
    if isinstance(e, ChannelPrivateError):
        return "group private hai ya account member nahi hai — pehle account se group join karo"
    if isinstance(e, ChatForbiddenError):
        return "account group me banned/blocked hai"
    if isinstance(e, ChatAdminRequiredError):
        return "member list dekhne ke liye admin permission chahiye"
    if isinstance(e, UsernameNotOccupiedError):
        return "username exist nahi karta — spelling check karo ya poora link do"
    if isinstance(e, UsernameInvalidError):
        return "username/link invalid hai — dobara check karo"
    if isinstance(e, FloodWaitError):
        return "Telegram flood wait %ds — thodi der baad try karo" % int(getattr(e, "seconds", 0))
    return "%s: %s" % (type(e).__name__, str(e)[:100])

async def get_discussion_group(client, channel_entity):
    try:
        full = await client(GetFullChannelRequest(channel_entity.id))
        if hasattr(full.full_chat, 'linked_chat_id') and full.full_chat.linked_chat_id:
            try:
                return await client.get_entity(full.full_chat.linked_chat_id)
            except:
                return await client.get_entity(InputPeerChannel(full.full_chat.linked_chat_id, 0))
    except:
        pass
    return None

# Feminine suffixes for girl name detection (case-insensitive)
# e.g. Ishika, Anamika, Nandita, Savita, Deepika, etc.
GIRL_NAME_SUFFIXES = {
    "a","aa","ai","ae","ah","ak","al","am","an","ar","as","at","av","ay",
    "ba","bi","bu","ca","ci","da","di","du","ea","ee","ei","el","em","en",
    "era","eri","ero","esa","esi","eta","eti","eva","evi","eya","eza",
    "fa","fi","ga","gi","ha","hi","ia","iba","ica","ida","ifa","iga","iha",
    "ika","ikha","iki","ila","ili","ima","imi","ina","ini","ira","iri",
    "isa","isi","ita","itha","iva","ivi","iya","iza","ja","ji","ka","ki",
    "kala","kani","kara","kari","kashi","kavi","kaya","keta","kiya","ksha",
    "kshi","la","li","lika","lina","lita","liza","mala","mani","mara",
    "mari","mati","maya","mina","mira","mita","miya","na","ni","nika",
    "nila","nima","nira","nita","niya","oli","oma","ona","ora","ori","osha",
    "pa","pi","pala","pari","pika","prabha","priya","ra","ri","rika","rina",
    "rita","riya","roopa","rupa","rushi","sa","sha","shi","shika","shita",
    "shiya","shma","shna","shree","shri","sia","sika","sima","sita","siya",
    "sna","sri","suha","ta","tha","ti","tia","tika","tina","tiya","tra",
    "ula","uma","una","ura","uri","usha","uti","uva","va","vati","vi",
    "vika","vina","vira","vita","viya","ya","yana","yani","yara","yari",
    "yasha","yati","yika","yina","yira","yita","yiya","za","zara","zari",
    "zaya","zika","zina","zira","zita","ziya","gni","tna","dha","ija",
    "ara","ari","ali","eli","devi","bala","mati","rani",
}


# ═══════════════════════════════════════════════════════════════════
# MENUS
# ═══════════════════════════════════════════════════════════════════

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊  Dashboard", callback_data="menu_dashboard"),
         InlineKeyboardButton("👤  Accounts", callback_data="menu_accounts")],
        [InlineKeyboardButton("🔄  Rejoin", callback_data="menu_rejoin"),
         InlineKeyboardButton("🚨  Banning", callback_data="menu_banning")],
        [InlineKeyboardButton("🧩  Features", callback_data="menu_features"),
         InlineKeyboardButton("📈  Live Logs", callback_data="menu_logs")],
        [InlineKeyboardButton("⚙️  Settings", callback_data="menu_settings"),
         InlineKeyboardButton("❓  Help", callback_data="menu_help")],
    ])

def menu_logs_text(ud, user_id):
    lines = []
    try:
        log_file = DATA_DIR / ("%s_activity.log" % user_id)
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                raw = f.readlines()[-12:]
            lines = [ln.strip() for ln in raw if ln.strip()]
    except Exception:
        lines = []
    r = ud.data.get("rej", {})
    live = rejoin_live(user_id, ud)
    diag = []
    diag.append("Rejoin: %s" % ("LIVE" if live else ("INTERRUPTED" if r.get("running") else "stopped")))
    if r.get("last_heartbeat"):
        diag.append("Heartbeat: %s" % r["last_heartbeat"])
    if r.get("last_error"):
        diag.append("Last error: %s" % str(r["last_error"])[:140])
    for ph, reason in list(CLIENT_ERRORS.items())[:3]:
        diag.append("acct …%s: %s" % (ph[-4:], str(reason)[:90]))
    body = "\n".join("<code>%s</code>" % html.escape(x) for x in lines) if lines else "<i>No activity yet.</i>"
    return ("📈  <b>LIVE LOGS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Recent activity</b>\n%s\n\n"
            "<b>Diagnostics</b>\n%s" % (body, "\n".join(html.escape(x) for x in diag)))

def features_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗂️  Scraper Hub", callback_data="scraper_hub")],
        [InlineKeyboardButton("⚙️  Group Manager", callback_data="menu_gm")],
        [InlineKeyboardButton("🔙  Back", callback_data="back_main")],
    ])

def accounts_menu(ud):
    btns = [[InlineKeyboardButton("➕  Add Account", callback_data="add_account")]]
    for ph in ud.data.get("acc", {}):
        active = ud.data["acc"][ph].get("active", True)
        status = "🟢" if active else "🔴"
        btns.append([
            InlineKeyboardButton("%s  %s" % (status, ph[:7]), callback_data="toggle_acc_%s" % ph),
            InlineKeyboardButton("🗑️", callback_data="rem_acc_%s" % ph)])
    btns.append([InlineKeyboardButton("✏️  Name", callback_data="set_name"),
                 InlineKeyboardButton("📝  Bio", callback_data="set_bio"),
                 InlineKeyboardButton("🖼️  Pfp", callback_data="set_pfp")])
    btns.append([InlineKeyboardButton("🔙  Back", callback_data="back_main")])
    return InlineKeyboardMarkup(btns)

def rejoin_menu(ud):
    r = ud.data.get("rej", {})
    live = rejoin_live(ud.user_id, ud)
    sts = "⏹️  STOP" if live else "▶️  START"
    safe = "🛡️  Safe: 5-10s" if r.get("safe_mode") else "🛡️  Safe: OFF"
    disc = "💬  Discussions: ON" if r.get("include_discussions", True) else "💬  Discussions: OFF"
    use_all = "👥  Multi-Acc: ON" if r.get("use_all_acc") else "👥  Multi-Acc: OFF"
    priority = "📊  Priority: ON" if r.get("priority") else "📊  Priority: OFF"
    auto_app = "✅  Auto-Approve: ON" if r.get("auto_approve") else "✅  Auto-Approve: OFF"
    bl_count = len(r.get("blacklist", []))
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(sts, callback_data="rejoin_toggle"),
         InlineKeyboardButton("🔗  Links", callback_data="rejoin_send_links")],
        [InlineKeyboardButton("📄  Export Links", callback_data="rejoin_export"),
         InlineKeyboardButton("📊  Stats", callback_data="rej_stats")],
        [InlineKeyboardButton("📂  Import File", callback_data="rejoin_import_file"),
         InlineKeyboardButton("🚫  Blacklist (%d)" % bl_count, callback_data="rejoin_blacklist")],
        [InlineKeyboardButton("🗑️  Clear", callback_data="rejoin_delete_links")],
        [InlineKeyboardButton(safe, callback_data="rejoin_safe_toggle")],
        [InlineKeyboardButton(use_all, callback_data="rejoin_use_all_toggle")],
        [InlineKeyboardButton(auto_app, callback_data="rejoin_autoapp_toggle")],
        [InlineKeyboardButton(disc, callback_data="rejoin_disc_toggle")],
        [InlineKeyboardButton(priority, callback_data="rejoin_priority_toggle")],
        [InlineKeyboardButton("⏱️  Gap: %s" % format_gap(r.get("gap", 30)), callback_data="rejoin_set_gap"),
         InlineKeyboardButton("🔄  Cycles: %s" % ("∞" if r.get("cycles", 0)==0 else r.get("cycles", 0)), callback_data="rejoin_set_cycles")],
        [InlineKeyboardButton("🔙  Back", callback_data="back_main")],
    ])

def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑  API Credentials", callback_data="set_api")],
        [InlineKeyboardButton("🌐  Proxy Config", callback_data="set_proxy")],
        [InlineKeyboardButton("👋  Welcome Message", callback_data="set_welcome")],
        [InlineKeyboardButton("👥  Authorized Users", callback_data="auth_users")],
        [InlineKeyboardButton("📊  Bot Stats", callback_data="download_stats")],
        [InlineKeyboardButton("🔄  Restart Bot", callback_data="restart_bot")],
        [InlineKeyboardButton("🔙  Back", callback_data="back_main")],
    ])

def approval_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅  APPROVE", callback_data="appr_yes"),
         InlineKeyboardButton("❌  DENY", callback_data="appr_no")],
        [InlineKeyboardButton("⏭️  Skip All", callback_data="appr_start")],
    ])

def render_blacklist_page(ud, page=0):
    bl = ud.data.get("rej", {}).get("blacklist", [])
    per_page = 8
    total = len(bl)
    pages = (total + per_page - 1) // per_page
    start = page * per_page
    end = min(start + per_page, total)
    lines = []
    for i in range(start, end):
        lines.append(f"<b>{i+1}.</b>  {bl[i][:50]}")
    txt = "🚫  <b>BLACKLIST</b>\n━━━━━━━━━━━━━━━━━━\n\n" + ("\n".join(lines) if lines else "Empty.")
    if pages > 1:
        txt += f"\n\n📄  Page {page+1}/{pages}  ({total} total)"
    btns = []
    for i in range(start, end):
        btns.append([InlineKeyboardButton(f"❌  {i+1}", callback_data=f"bl_remove_{i}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️  Prev", callback_data="bl_page_prev"))
    if page + 1 < pages:
        nav.append(InlineKeyboardButton("➡️  Next", callback_data="bl_page_next"))
    if nav:
        btns.append(nav)
    btns.append([InlineKeyboardButton("🔙  Back", callback_data="menu_rejoin")])
    return txt, InlineKeyboardMarkup(btns)

def render_filter_words(ud):
    fl = ud.data["gm"].get("filters", [])
    txt = "🚫  <b>FILTERED WORDS</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    if fl:
        for i, w in enumerate(fl):
            txt += f"{i+1}. <code>{html.escape(w[:20])}</code>\n"
    else:
        txt += "No filtered words."
    btns = [[InlineKeyboardButton("➕  Add Word", callback_data="gm_filter_add")]]
    if fl:
        row = []
        for i in range(min(len(fl), 8)):
            row.append(InlineKeyboardButton(str(i+1), callback_data=f"gm_filter_rm_{i}"))
        if row:
            btns.append(row)
    btns.append([InlineKeyboardButton("🔙  Back", callback_data="gm_protection")])
    return txt, InlineKeyboardMarkup(btns)

def scraper_hub_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥  Member Scraper", callback_data="menu_scraper"),
         InlineKeyboardButton("👩  Girls Scraper", callback_data="menu_scrap_girls")],
        [InlineKeyboardButton("📊  Scraper Dashboard", callback_data="scraper_dashboard"),
         InlineKeyboardButton("ℹ️  How It Works", callback_data="scraper_help")],
        [InlineKeyboardButton("🔙  Back", callback_data="menu_features")],
    ])

def scraper_menu(ud):
    s = ud.data.get("scraper", {})
    sts = "⏹️  STOP" if s.get("running") else "▶️  START"
    ug = s.get("user_gap", 60)
    ug_label = "%dm" % (ug // 60) if ug >= 60 else "%ds" % ug
    dl = s.get("daily_limit", 0)
    dl_label = "♾️" if dl == 0 else str(dl)
    mode = s.get("mode", "send")
    mode_label = "➕  Add to Group" if mode == "add" else "📨  Send as Msg"
    pend = len(s.get("pending", []))
    add_label = ("⏹️  Stop Adding" if s.get("add_running")
                 else "🚀  Add Pending (%d)" % pend)
    mm = s.get("member_mode", "all")
    def _mbtn(label, key):
        return InlineKeyboardButton(("✅ " if mm == key else "") + label,
                                    callback_data="scraper_mmode_" + key)
    kw = (s.get("girl_keywords") or "").strip()
    kw_label = (kw[:14] + "…") if len(kw) > 15 else (kw or "auto-detect")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(sts, callback_data="scraper_toggle"),
         InlineKeyboardButton("📊  Stats", callback_data="scraper_stats")],
        [InlineKeyboardButton("🎯  Target", callback_data="scraper_target"),
         InlineKeyboardButton("📤  Delivery", callback_data="scraper_delivery")],
        [_mbtn("👥 All", "all"), _mbtn("👩 Girls", "girls"), _mbtn("🔥 Active", "active")],
        [InlineKeyboardButton("🏷️  Girls Keywords: %s" % kw_label, callback_data="scraper_girl_kw")],
        [InlineKeyboardButton("🔀  Mode: %s" % mode_label, callback_data="scraper_mode_toggle")],
        [InlineKeyboardButton("⏱️  Batch Gap: %ds" % s.get("gap", 3), callback_data="scraper_set_gap")],
        [InlineKeyboardButton("👤  User Gap: %s" % ug_label, callback_data="scraper_user_gap"),
         InlineKeyboardButton("📅  Daily Limit: %s" % dl_label, callback_data="scraper_daily_limit")],
        [InlineKeyboardButton("➕  Add Gap: %ds" % s.get("add_gap", 20), callback_data="scraper_add_gap")],
        [InlineKeyboardButton(add_label, callback_data="scrap_add_yes")],
        [InlineKeyboardButton("🔙  Back", callback_data="scraper_hub")],
    ])


def gm_menu(ud):
    gm = ud.data.get("gm", {})
    gid = gm.get("group_id", 0)
    title = gm.get("group_title", "Not Set")[:15]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏷️  Group: %s" % title, callback_data="gm_set")],
        [InlineKeyboardButton("🛠️  Admin Actions", callback_data="gm_admin"),
         InlineKeyboardButton("🛡️  Protection", callback_data="gm_protection")],
        [InlineKeyboardButton("⚙️  Settings", callback_data="gm_settings")],
        [InlineKeyboardButton("🔄  Notify: %s" % ("ON" if gm.get("notify",True) else "OFF"), callback_data="gm_notify_toggle")],
        [InlineKeyboardButton("📩  JoinReply: %s" % ("ON" if gm.get("join_reply",True) else "OFF"), callback_data="gm_joinreply_toggle")],
        [InlineKeyboardButton("🔙  Back", callback_data="menu_features")],
    ])

def gm_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫  Ban", callback_data="gm_ban"), InlineKeyboardButton("✅  Unban", callback_data="gm_unban")],
        [InlineKeyboardButton("👢  Kick", callback_data="gm_kick"), InlineKeyboardButton("🔇  Mute", callback_data="gm_mute")],
        [InlineKeyboardButton("🔊  Unmute", callback_data="gm_unmute"), InlineKeyboardButton("⭐  Promote", callback_data="gm_promote")],
        [InlineKeyboardButton("⬇️  Demote", callback_data="gm_demote"), InlineKeyboardButton("📌  Pin", callback_data="gm_pin")],
        [InlineKeyboardButton("🚫  Ban List", callback_data="gm_banlist")],
        [InlineKeyboardButton("🔙  Back", callback_data="menu_gm")],
    ])

def gm_protection_menu(ud):
    gm = ud.data.get("gm", {})
    af_on = bool(gm.get("antiflood", {}))
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫  Filters: [%d blocked words]" % len(gm.get("filters",[])), callback_data="gm_filters")],
        [InlineKeyboardButton("🌊  Antiflood: %s" % ("ON" if af_on else "OFF"), callback_data="gm_af_toggle")],
        [InlineKeyboardButton("📊  AF msgs: [%d]" % gm.get("antiflood_msgs",5), callback_data="gm_af_msgs")],
        [InlineKeyboardButton("⏱️  AF interval: [%ds]" % gm.get("antiflood_interval",3), callback_data="gm_af_int")],
        [InlineKeyboardButton("⚠️  Warn max: [%d]" % gm.get("warn_max",3), callback_data="gm_warn_set")],
        [InlineKeyboardButton("🎬  MediaFilter: %s" % ("ON" if gm.get("media_filter") else "OFF"), callback_data="gm_media_toggle")],
        [InlineKeyboardButton("🔗  LinkFilter: %s" % ("ON" if gm.get("link_filter") else "OFF"), callback_data="gm_link_toggle")],
        [InlineKeyboardButton("📋  BioFilter: %s" % ("ON" if gm.get("bio_filter") else "OFF"), callback_data="gm_bio_toggle")],
        [InlineKeyboardButton("🔙  Back", callback_data="menu_gm")],
    ])

def gm_settings_menu(ud):
    gm = ud.data.get("gm", {})
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👋  Welcome: %s" % ("ON" if gm.get("welcome_enabled") else "OFF"), callback_data="gm_welcome_toggle")],
        [InlineKeyboardButton("✏️  Set Welcome", callback_data="gm_set_welcome")],
        [InlineKeyboardButton("📜  Rules: %s" % ("ON" if gm.get("rules_enabled") else "OFF"), callback_data="gm_rules_toggle")],
        [InlineKeyboardButton("✏️  Set Rules", callback_data="gm_set_rules")],
        [InlineKeyboardButton("ℹ️  Group Info", callback_data="gm_info")],
        [InlineKeyboardButton("🔗  Invite Link", callback_data="gm_invite")],
        [InlineKeyboardButton("🔙  Back", callback_data="menu_gm")],
    ])

def scrap_girls_menu(ud):
    sg = ud.data.get("scrap_girls", {})
    sts = "⏹️  STOP" if sg.get("running") else "▶️  START"
    nf = "ON" if sg.get("name_filter", True) else "OFF"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(sts, callback_data="sg_toggle"),
         InlineKeyboardButton("📊  Stats", callback_data="sg_stats")],
        [InlineKeyboardButton("👤  Qty: %d" % sg.get("qty", 50), callback_data="sg_set_qty"),
         InlineKeyboardButton("⏱️  Delay: %ds" % sg.get("delay", 3), callback_data="sg_set_delay")],
        [InlineKeyboardButton("📂  Sources (%d)" % len(sg.get("sources", [])), callback_data="sg_sources"),
         InlineKeyboardButton("👩  Filter: %s" % nf, callback_data="sg_filter_toggle")],
        [InlineKeyboardButton("🔙  Back", callback_data="scraper_hub")],
    ])


def banning_menu(ud):
    b = ud.data.get("banning", {})
    target = b.get("target", "")
    scan_label = f"📄  Scan: {b.get('msg_limit', 5000)}" if b.get('msg_limit') and b.get('msg_limit') != 'all' else "📄  Scan: ALL"
    buttons = [
        [InlineKeyboardButton("🎯  Target: %s" % (target[:25] if target else "Not Set"), callback_data="ban_set_target")],
        [InlineKeyboardButton("🔑  Groq API: %s" % ("✅ Set" if b.get("groq_api") else "❌ Not Set"), callback_data="ban_set_groq")],
        [InlineKeyboardButton(scan_label, callback_data="ban_scan_count")],
    ]
    if b.get("running"):
        buttons.append([InlineKeyboardButton("⏹️  Stop Review", callback_data="ban_stop")])
    else:
        buttons.append([InlineKeyboardButton("🚀  Start Review", callback_data="ban_start"),
                        InlineKeyboardButton("📊  Status", callback_data="ban_status")])
    buttons.append([InlineKeyboardButton("🔙  Back", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)

# ═══════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════

async def show_dashboard(update, context):
    query = update.callback_query
    if not query: return
    try:
        await query.answer()
    except:
        pass

    user_id = (update.effective_user or query.from_user).id
    ud = get_user_data(user_id)
    accs = ud.data.get("acc", {})
    r = ud.data.get("rej", {})
    s = ud.data.get("scraper", {})
    b = ud.data.get("banning", {})

    try:
        acc_count = len(accs)
        active_count = len([p for p in accs if accs[p].get("active", True)])
        r_live = rejoin_live(user_id, ud)
        s_live = task_alive(user_id, "scraper")
        add_pending = len(s.get("pending", []))
        acc_lines = []
        for ph in list(accs)[:4]:
            flag = "🟢" if accs[ph].get("active", True) else "🔴"
            acc_lines.append("     %s  …%s" % (flag, ph[-4:]))
        if acc_count > 4:
            acc_lines.append("     … +%d more" % (acc_count - 4))
        if not acc_lines:
            acc_lines.append("     <i>No accounts added</i>")
        rejoin_line = "🟢  RUNNING" if r_live else ("🟡  INTERRUPTED" if r.get("running") else "🔴  STOPPED")
        txt = (
            "📊  <b>CONTROL CENTER</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "👤  <b>ACCOUNTS</b>  —  %d active / %d total\n%s\n\n"
            "🔄  <b>REJOIN</b>  —  %s\n"
            "     ✅ %d joined   ↩️ %d left   ⚠️ %d failed\n"
            "     📋 %d groups   🚫 %d blocked   🔄 %s cycles\n"
            "     💓 %s%s\n\n"
            "👥  <b>SCRAPER</b>  —  %s%s\n"
            "     🔎 %s  •  source: %s\n"
            "     👤 %d scraped   📥 %d pending\n"
            "     ✅ %d added  ❌ %d failed  ⏭️ %d skipped\n"
            "     ♻️ %s\n\n"
            "🚨  <b>BANNING</b>  —  %s\n"
            "     📋 %d reports\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "⏱️  Uptime: %s"
            % (active_count, acc_count, "\n".join(acc_lines),
               rejoin_line,
               r.get("joined_count", 0), r.get("left_count", 0), r.get("failed_count", 0),
               len(r.get("approved", [])), len(r.get("blacklist", [])),
               ("∞" if r.get("cycles", 0) == 0 else r.get("cycles", 0)),
               (r.get("last_heartbeat") or "—"),
               ("   ⚠️ <code>%s</code>" % html.escape(str(r.get("last_error"))[:100]) if r.get("last_error") else ""),
               ("🟢 RUNNING" if s_live else "🔴 STOPPED"),
               ("  +  ➕ ADDING" if s.get("add_running") else ""),
               {"all": "👥 All members", "girls": "👩 Only girls", "active": "🔥 Active"}.get(s.get("member_mode", "all"), "👥 All members"),
               (s.get("source_used") or "—"),
               s.get("scraped", 0), add_pending,
               s.get("add_added", 0), s.get("add_failed", 0), s.get("add_skipped", 0),
               (", ".join("…%s=%d" % (k, v) for k, v in (s.get("per_acc") or {}).items()) or "—"),
               ("🟢 RUNNING" if b.get("running") else "🔴 STOPPED"),
               len(b.get("reports", [])),
               get_uptime())
        )
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄  Refresh", callback_data="menu_dashboard"),
                 InlineKeyboardButton("📈  Logs", callback_data="menu_logs")],
                [InlineKeyboardButton("🔄  Rejoin", callback_data="menu_rejoin"),
                 InlineKeyboardButton("👥  Scraper", callback_data="menu_scraper")],
                [InlineKeyboardButton("🔙  Back", callback_data="back_main")],
            ]))
        log_activity(user_id, "Viewed dashboard")
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        try:
            await query.edit_message_text(
                f"ERROR\n\n{str(e)[:100]}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back_main")]]))
        except:
            pass

async def show_help(update, context):
    query = update.callback_query
    if not query: return
    try:
        await query.answer()
    except:
        pass

    try:
        txt = (
            "❓  <b>HELP & GUIDE</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "📌  <b>Commands</b>\n"
            "  /start   →  Open main menu\n"
            "  /stats   →  Quick stats\n"
            "  /cleanup →  Remove dead accounts\n"
            "  /backup  →  Data zip download (accounts + groups)\n"
            "  /restore →  Backup zip reply karke import\n\n"
            "📌  <b>Features</b>\n"
            "  👤  <b>Accounts</b>    —  Add & manage your Telegram accounts\n"
            "  🔄  <b>Rejoin</b>      —  Auto join/leave groups in cycles\n"
            "  👥  <b>Scraper</b>     —  Scrape all / only-girls / active members\n"
            "  👩  <b>Scrap Girls</b>  —  Filter & scrape Indian girl profiles\n"
            "  ⚙️  <b>Group Manager</b> —  Admin actions, filters, antiflood, welcome, rules, invites\n"
            "  🚨  <b>Banning</b>    —  AI-powered policy violation reviewer\n"
            "  ⚙️  <b>Settings</b>    —  API, proxy, welcome message\n\n"
            "📌  <b>Tips</b>\n"
            "  •  Safe mode = human-like delays (5-10s)\n"
            "  •  Set realistic gaps to avoid bans\n"
            "  •  Multi-Acc = every account covers every group (parallel, staggered)\n"
            "  •  Scraper add = round-robin accounts; gap sirf success ke baad\n"
            "  •  Scraper categories: All members, Only girls (keywords), Active members\n"
            "  •  Use proxy for better security\n"
            "━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="back_main")]]))
    except Exception as e:
        logger.error(f"Help error: {e}")

# ═══════════════════════════════════════════════════════════════════
# BACKGROUND TASK - REJOIN
# ═══════════════════════════════════════════════════════════════════

async def delayed_heart_reaction(phone, user_id, link):
    try:
        delay = random.randint(1800, 3000)
        await asyncio.sleep(delay)
        ud = get_user_data(user_id)
        client = await get_client(phone, ud)
        if not client: return
        try:
            entity = await client.get_entity(link)
            me = await client.get_me()
            async for msg in client.iter_messages(entity, limit=100):
                if getattr(msg, 'action', None) and hasattr(msg.action, 'users') and me.id in msg.action.users:
                    await client.send_reaction(entity, msg.id, '💖'); break
        except: pass
        finally:
            await client.disconnect()
    except asyncio.CancelledError: pass

async def rejoin_cycle_task(user_id, phone, bot, groups_override=None, slot=0, total=1):
    ud = get_user_data(user_id); rej = ud.data["rej"]
    acc = phone[-4:] if len(phone) >= 4 else phone
    client = await get_client(phone, ud)
    if not client:
        reason = CLIENT_ERRORS.get(phone, "connection failed")
        rej["running"] = False
        rej["last_error"] = "Connect failed: " + reason
        rej["last_stop_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ud.save()
        await notify_progress(bot, user_id,
            "❌ <b>REJOIN STOPPED — ACCOUNT CONNECT FAILED</b>\n"
            "👤 account: <code>…%s</code>\n"
            "⚠️ reason: <code>%s</code>\n\n"
            "<b>Fix karo:</b>\n"
            "• Accounts → account delete karke dobara login karo\n"
            "• Proxy ON hai to band karke try karo\n"
            "• Dusre device/bot pe same account chal raha ho to band karo"
            % (acc, html.escape(reason[:160])))
        if user_id in active_tasks:
            active_tasks[user_id].pop("rej_%s" % phone, None)
            active_tasks[user_id].pop("rej", None)
            remaining = [k for k in active_tasks.get(user_id, {}) if k.startswith("rej_")]
            if not remaining:
                if user_id in active_tasks:
                    active_tasks[user_id].pop("rej", None)
        return
    rej["last_error"] = ""
    rej["session_started"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rej["last_heartbeat"] = datetime.now().strftime("%H:%M:%S")
    ud.save()
    ecache = {}
    cancelled = False
    try:
        cycle = 0
        backoff = 5
        while rej["running"]:
            try:
                base = list(rej["approved"])
                if not base and groups_override:
                    base = list(groups_override)
                if not base:
                    rej["running"] = False; ud.save(); break
                if rej["cycles"] > 0 and cycle >= rej["cycles"]:
                    break
    
                groups = list(base)
                random.shuffle(groups)
    
                if rej.get("priority"):
                    mc = rej.get("member_counts", {})
                    missing = [g for g in groups if g not in mc]
                    if missing and cycle == 0:
                        for g in missing:
                            try:
                                e = await client.get_entity(g)
                                mc[g] = getattr(e, "participants_count", 0) or 0
                            except Exception:
                                mc[g] = 0
                        rej["member_counts"] = mc
                        ud.save()
                    groups.sort(key=lambda x: mc.get(x, 0), reverse=True)
    
                if groups:
                    off = (slot + cycle * max(total, 1)) % len(groups)
                    groups = groups[off:] + groups[:off]
    
                total_groups = len(groups)
                c_join = c_left = c_fail = 0
                drop = []
    
                for idx, link in enumerate(groups, 1):
                    if not rej["running"]:
                        break
                    rej["last_heartbeat"] = datetime.now().strftime("%H:%M:%S")

                    gap = int(rej["gap"] or 30)
                    if rej["safe_mode"]:
                        gap = random.randint(5, 10)
                    stay = gap
                    chat = ecache.get(link)
                    disc = None
                    already = False
                    joined = False
                    title = link
                    fail_reason = ""
    
                    for attempt in range(3):
                        try:
                            if "t.me/+" in link or "joinchat" in link:
                                h = link.split("/")[-1].replace("+", "")
                                try:
                                    up = await client(ImportChatInviteRequest(h))
                                    if getattr(up, "chats", None):
                                        chat = up.chats[0]; ecache[link] = chat
                                except UserAlreadyParticipantError:
                                    already = True
                                    if chat is None:
                                        try:
                                            inv = await client(CheckChatInviteRequest(h))
                                            if isinstance(inv, ChatInviteAlready):
                                                chat = inv.chat; ecache[link] = chat
                                        except Exception:
                                            pass
                                    if chat is None:
                                        try:
                                            chat = await client.get_entity(link); ecache[link] = chat
                                        except Exception:
                                            pass
                            else:
                                if chat is None:
                                    chat = await client.get_entity(link); ecache[link] = chat
                                try:
                                    await client(JoinChannelRequest(chat))
                                except UserAlreadyParticipantError:
                                    already = True
                            if chat is None:
                                fail_reason = "Cannot resolve group"
                                break
                            title = getattr(chat, "title", None) or link
                            joined = True
                            break
                        except FloodWaitError as e:
                            wait = int(e.seconds) + random.randint(1, 3)
                            await notify_progress(bot, user_id,
                                "⏳ <b>FLOOD</b>  •  acct …%s  •  %s\n"
                                "waiting <b>%ds</b> then retry %d/3"
                                % (acc, html.escape(str(title)[:40]), wait, attempt + 1))
                            await asyncio.sleep(wait)
                        except (InviteHashExpiredError, InviteHashInvalidError, ValueError,
                                ChannelPrivateError, ChannelInvalidError) as e:
                            fail_reason = "Dead / private / invalid link"
                            drop.append(link)
                            break
                        except Exception as e:
                            fail_reason = "%s: %s" % (type(e).__name__, str(e)[:60])
                            break
    
                    if any(d == link for d in drop) and not joined:
                        c_fail += 1
                        await notify_progress(bot, user_id,
                            "🚫 <b>BLACKLISTED</b>  •  acct …%s\n"
                            "<code>%s</code>\nreason: %s"
                            % (acc, html.escape(link[:60]), html.escape(fail_reason or "invalid")))
                        continue
    
                    if not joined:
                        c_fail += 1
                        await notify_progress(bot, user_id,
                            "❌ <b>JOIN FAILED</b>  •  acct …%s  %d/%d\n"
                            "group: <b>%s</b>\nreason: %s"
                            % (acc, idx, total_groups, html.escape(str(title)[:40]),
                               html.escape(fail_reason or "unknown")))
                        continue
    
                    if not already:
                        rej["joined_count"] += 1; ud.save(); c_join += 1
    
                    if rej.get("include_discussions", True):
                        try:
                            full = await client(GetFullChannelRequest(chat.id))
                            disc_id = getattr(full.full_chat, "linked_chat_id", None)
                            if disc_id:
                                try:
                                    disc = await client.get_entity(disc_id)
                                except Exception:
                                    disc = await client.get_entity(InputPeerChannel(disc_id, 0))
                                if disc:
                                    try:
                                        await client(JoinChannelRequest(disc))
                                        rej["joined_count"] += 1; ud.save(); c_join += 1
                                    except UserAlreadyParticipantError:
                                        pass
                                    await notify_progress(bot, user_id,
                                        "💬 <b>DISCUSSION JOINED</b>  •  acct …%s\n%s"
                                        % (acc, html.escape(str(getattr(disc, "title", "?") or "?"))))
                                    await asyncio.sleep(min(rej.get("disc_gap", 2), 5))
                        except Exception:
                            pass
    
                    if (rej.get("include_discussions", True) and not disc
                            and getattr(chat, "broadcast", False)):
                        drop.append(link)
                        await notify_progress(bot, user_id,
                            "🚫 <b>NO DISCUSSION</b>  •  acct …%s\n%s — blacklisted"
                            % (acc, html.escape(str(title)[:40])))
                        try:
                            await client(LeaveChannelRequest(chat))
                        except Exception:
                            pass
                        c_fail += 1
                        continue
    
                    await notify_progress(bot, user_id,
                        "✅ <b>JOINED</b>  •  acct …%s  %d/%d\n"
                        "group: <b>%s</b>\nmembers: %s  •  cycle %d%s"
                        % (acc, idx, total_groups, html.escape(str(title)[:40]),
                           getattr(chat, "participants_count", 0) or "?",
                           cycle + 1, "  •  rejoin" if already else ""))
    
                    try:
                        mc = getattr(chat, "participants_count", 999) or 999
                        if mc < 100:
                            stay = max(10, int(gap * 0.3))
                    except Exception:
                        pass
    
                    if not rej["running"]:
                        break
                    if rej["safe_mode"]:
                        await human_wait()
                    else:
                        await asyncio.sleep(stay)
    
                    try:
                        await client(LeaveChannelRequest(chat))
                        rej["left_count"] += 1; ud.save(); c_left += 1
                    except Exception:
                        pass
                    if disc:
                        try:
                            await client(LeaveChannelRequest(disc))
                            rej["left_count"] += 1; ud.save()
                        except Exception:
                            pass
                    await notify_progress(bot, user_id,
                        "↩️ <b>LEFT</b>  •  acct …%s\n%s"
                        % (acc, html.escape(str(title)[:40])))
                    await asyncio.sleep(random.uniform(0.5, 2.0))
    
                for link in drop:
                    if link in rej["approved"]:
                        rej["approved"].remove(link)
                    if link not in rej["blacklist"]:
                        rej["blacklist"].append(link)
                    if groups_override is not None and link in groups_override:
                        groups_override.remove(link)
                rej["failed_count"] = rej.get("failed_count", 0) + c_fail
                rej["last_cycle_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rej["last_heartbeat"] = datetime.now().strftime("%H:%M:%S")
                rej["last_error"] = ""
                ud.save()
    
                await notify_progress(bot, user_id,
                    "🔁 <b>CYCLE %d DONE</b>  •  acct …%s\n"
                    "joined %d  •  left %d  •  failed %d  •  groups %d\n"
                    "running totals — joined %d / left %d / failed %d"
                    % (cycle + 1, acc, c_join, c_left, c_fail, total_groups,
                       rej["joined_count"], rej["left_count"],
                       rej.get("failed_count", 0)))
                cycle += 1
            except asyncio.CancelledError:
                raise
            except Exception as e:
                reason = "%s: %s" % (type(e).__name__, str(e)[:140])
                rej["last_error"] = reason
                rej["last_heartbeat"] = datetime.now().strftime("%H:%M:%S")
                ud.save()
                await notify_progress(bot, user_id,
                    "⚠️ <b>REJOIN UNSTABLE</b>  •  acct …%s\n"
                    "reason: <code>%s</code>\nretrying in %ds..."
                    % (acc, html.escape(reason[:140]), backoff))
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            backoff = 5
    except asyncio.CancelledError:
        cancelled = True
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
        rej["last_stop_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if groups_override is None:
            if not cancelled:
                rej["running"] = False
            ud.save()
            if user_id in active_tasks:
                active_tasks[user_id].pop('rej', None)
        else:
            ud.save()
            task_key = "rej_%s" % phone
            if user_id in active_tasks:
                active_tasks[user_id].pop(task_key, None)
            remaining = [k for k in active_tasks.get(user_id, {}) if k.startswith("rej_")]
            if not remaining and not cancelled:
                rej["running"] = False
                ud.save()

# ═══════════════════════════════════════════════════════════════════
# BACKGROUND TASK - SCRAPER
# ═══════════════════════════════════════════════════════════════════

async def _scrape_participants(client, entity, s, seen_ids):
    users = []
    offset = 0
    limit = 200
    empty = 0
    while s.get("running"):
        try:
            parts = await client(GetParticipantsRequest(
                entity, ChannelParticipantsSearch(''), offset, limit))
        except Exception as e:
            logger.warning(f"participant fetch failed: {e}")
            break
        if not getattr(parts, "users", None):
            break
        page_new = 0
        for u in parts.users:
            if getattr(u, "bot", False) or getattr(u, "deleted", False):
                continue
            uid = getattr(u, "id", None)
            if not uid or uid in seen_ids:
                continue
            seen_ids.add(uid)
            users.append(u)
            page_new += 1
        offset += len(parts.users)
        if page_new == 0:
            empty += 1
            if empty >= 2:
                break
        else:
            empty = 0
        if len(parts.users) < limit:
            break
        await asyncio.sleep(max(1, int(s.get("gap", 3))))
    return users


async def _scrape_deep_scan(client, entity, s, seen_ids, bot, user_id, acc, cap=20000, rank=False):
    users = []
    counts = {}
    scanned = 0
    try:
        async for msg in client.iter_messages(entity, limit=cap):
            if not s.get("running"):
                break
            scanned += 1
            sender = getattr(msg, "sender", None)
            if sender is None:
                sid = getattr(msg, "sender_id", None)
                if sid:
                    try:
                        sender = await client.get_entity(sid)
                    except Exception:
                        sender = None
            if sender and not getattr(sender, "bot", False) and not getattr(sender, "deleted", False):
                uid = getattr(sender, "id", None)
                if uid and uid not in seen_ids:
                    seen_ids.add(uid)
                    users.append(sender)
                    counts[uid] = counts.get(uid, 0) + 1
                elif uid:
                    counts[uid] = counts.get(uid, 0) + 1
            act = getattr(msg, "action", None)
            if act is not None and hasattr(act, "users"):
                for au in getattr(act, "users", []) or []:
                    uid = getattr(au, "id", None)
                    if not uid or uid in seen_ids:
                        continue
                    try:
                        au2 = await client.get_entity(uid)
                    except Exception:
                        continue
                    if getattr(au2, "bot", False) or getattr(au2, "deleted", False):
                        continue
                    seen_ids.add(uid)
                    users.append(au2)
            if scanned % 500 == 0:
                await notify_progress(bot, user_id,
                    "🔎 <b>DEEP SCAN</b>  •  acct …%s\n"
                    "messages checked: <b>%d</b>  •  users found: <b>%d</b>"
                    % (acc, scanned, len(users)))
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.warning(f"deep scan error: {e}")
    if rank:
        users.sort(key=lambda u: counts.get(getattr(u, "id", None), 0), reverse=True)
    return users


def _girl_keywords(s):
    raw = (s.get("girl_keywords") or "").strip().lower()
    if not raw:
        return []
    return [k.strip() for k in re.split(r"[,;\s]+", raw) if k.strip()]


MALE_NAME_HINTS = {"krishna", "raja", "baba", "anna", "ravi", "hari", "shani",
                   "gopi", "munna", "chotu", "sonu", "monu", "raju", "vijay"}

def _is_girl(u, kws):
    name = ((getattr(u, "first_name", "") or "") + " " +
            (getattr(u, "last_name", "") or "")).strip().lower()
    uname = (getattr(u, "username", "") or "").lower()
    if kws:
        return any(k in name or k in uname for k in kws)
    if not name:
        return False
    if name in MALE_NAME_HINTS:
        return False
    strong = ("a", "ee", "iya", "ika", "ita", "ina", "isha", "esha",
              "ani", "ini", "ati", "devi", "rani", "kaur", "kumari", "bai")
    return any(name.endswith(suf) for suf in strong)


async def scraper_task(user_id, phone, bot):
    ud = get_user_data(user_id); s = ud.data["scraper"]
    for k, v in (("member_mode", "all"), ("girl_keywords", ""), ("added_uids", []),
                 ("source_used", ""), ("found_total", 0), ("last_error", ""),
                 ("per_acc", {}), ("add_skipped", 0)):
        s.setdefault(k, v)
    client = await get_client(phone, ud)
    if not client:
        reason = CLIENT_ERRORS.get(phone, "connection failed")
        s["running"] = False
        s["last_error"] = "Connect failed: " + reason
        ud.save()
        await notify_progress(bot, user_id,
            "❌ <b>SCRAPER STOPPED — ACCOUNT CONNECT FAILED</b>\n"
            "👤 account: <code>…%s</code>\n⚠️ reason: <code>%s</code>\n\n"
            "Account dobara login karo ya proxy band karke try karo."
            % (phone[-4:], html.escape(reason[:160])))
        if user_id in active_tasks:
            active_tasks[user_id].pop("scraper", None)
        return
    acc = phone[-4:] if len(phone) >= 4 else phone
    try:
        target_entity = await resolve_entity(client, s["target"])
        if target_entity is None:
            reason = RESOLVE_ERRORS.get(s["target"], "chat access nahi mila")
            s["running"] = False
            s["last_error"] = reason
            ud.save()
            await notify_progress(bot, user_id,
                "❌ <b>TARGET GROUP ACCESS FAILED</b>\n"
                "🔗 <code>%s</code>\n⚠️ reason: <code>%s</code>\n\n"
                "<b>Fix:</b> group exist karta hai? Account us group ka member hai? "
                "Private group hai to pehle account se join karo."
                % (html.escape(s["target"][:80]), html.escape(reason[:160])))
            return

        delivery_entity = await resolve_entity(client, s["delivery"])
        if delivery_entity is None:
            reason = RESOLVE_ERRORS.get(s["delivery"], "chat access nahi mila")
            s["running"] = False
            s["last_error"] = reason
            ud.save()
            await notify_progress(bot, user_id,
                "❌ <b>DELIVERY GROUP ACCESS FAILED</b>\n"
                "🔗 <code>%s</code>\n⚠️ reason: <code>%s</code>\n\n"
                "<b>Fix:</b> delivery group valid hai? Account member/admin hai? "
                "Private link expire ho gaya ho to naya link do."
                % (html.escape(s["delivery"][:80]), html.escape(reason[:160])))
            return

        today = datetime.now().strftime("%Y-%m-%d")
        if s.get("last_scrape_date") != today:
            s["scraped_today"] = 0
            s["last_scrape_date"] = today
            ud.save()

        mode = s.get("member_mode", "all")
        if mode not in ("all", "girls", "active"):
            mode = "all"
        mode_label = {"all": "ALL MEMBERS", "girls": "ONLY GIRLS", "active": "ACTIVE MEMBERS"}[mode]

        total_members = 0
        try:
            full = await client(GetFullChannelRequest(target_entity.id))
            total_members = getattr(full.full_chat, "participants_count", 0) or 0
        except Exception:
            total_members = 0

        title = getattr(target_entity, "title", None) or s["target"]
        await notify_progress(bot, user_id,
            "🚀 <b>SCRAPER STARTED</b>  •  acct …%s\n"
            "🎯 target: <b>%s</b>\n"
            "🔎 mode: <b>%s</b>\n"
            "👥 group members: <b>%s</b>\n"
            "⏳ fetching list..."
            % (acc, html.escape(str(title)[:45]), mode_label,
               (total_members if total_members else "hidden/unknown")))

        seen_ids = set()
        raw = []
        used_member_api = False
        if mode in ("all", "girls"):
            raw = await _scrape_participants(client, target_entity, s, seen_ids)
            used_member_api = len(raw) > 0

        need_scan = (mode == "active") or (not raw)
        if need_scan:
            if mode == "active":
                await notify_progress(bot, user_id,
                    "🔥 <b>ACTIVE MEMBER SCAN</b>  •  acct …%s\n"
                    "recent messages + joins se active users nikal rahe hain..." % acc)
            else:
                await notify_progress(bot, user_id,
                    "🔍 <b>MEMBER LIST HIDDEN / EMPTY</b>  •  acct …%s\n"
                    "deep message scan chalu — senders + join events se users nikal rahe hain..." % acc)
            scanned = await _scrape_deep_scan(client, target_entity, s, seen_ids, bot, user_id, acc,
                                              rank=(mode == "active"))
            known = set(getattr(u, "id", None) for u in raw)
            for u in scanned:
                if getattr(u, "id", None) not in known:
                    raw.append(u)
                    known.add(getattr(u, "id", None))
            if not used_member_api and raw:
                used_member_api = False

        if s.get("daily_limit", 0) > 0:
            remain = max(0, int(s["daily_limit"]) - int(s.get("scraped_today", 0)))
            if remain and len(raw) > remain:
                raw = raw[:remain]

        kws = _girl_keywords(s)
        if mode == "girls":
            filtered = [u for u in raw if _is_girl(u, kws)]
            raw = filtered

        added_set = set(str(x) for x in s.get("added_uids", []))
        final = []
        seen_out = set()
        for u in raw:
            uid = getattr(u, "id", None)
            if not uid:
                continue
            uname = getattr(u, "username", None)
            ident = uname if uname else str(uid)
            if str(uid) in added_set or ident in added_set or ident in seen_out:
                continue
            seen_out.add(ident)
            final.append(ident)

        source = "member list API" if used_member_api else "deep message scan"
        s["source_used"] = source
        s["found_total"] = len(raw)
        s["scraped"] = len(final)
        s["scraped_today"] = int(s.get("scraped_today", 0)) + len(final)
        s["last_error"] = ""
        ud.save()

        if not final:
            why = ("koi member match nahi hua (keywords ya filter check karo)"
                   if mode == "girls" else
                   "member list hidden hai aur message scan me koi user nahi mila")
            await notify_progress(bot, user_id,
                "❌ <b>NO USERS SCRAPED</b>\n"
                "🎯 target: <code>%s</code>\n"
                "🔎 mode: %s\n"
                "👥 raw found: %d\n"
                "⚠️ %s\n\n"
                "<b>Tip:</b> account ko group admin banao (member list ke liye), "
                "ya 'Active Members' mode try karo."
                % (html.escape(s["target"][:60]), mode_label, len(raw), why))
        elif s.get("mode", "send") == "add":
            s["pending"] = final
            s["add_added"] = 0
            s["add_failed"] = 0
            s["add_skipped"] = 0
            ud.save()
            await notify_progress(bot, user_id,
                "📦 <b>SCRAPE READY</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "🎯 target: <code>%s</code>\n"
                "📤 add to: <code>%s</code>\n"
                "🔎 mode: <b>%s</b>  •  source: %s\n"
                "👥 group total: %s  •  found: %d\n"
                "🚫 already added (skip): %d\n\n"
                "Multi-account round-robin add shuru karein?"
                % (html.escape(s["target"][:45]), html.escape(s["delivery"][:45]),
                   mode_label, source,
                   (total_members if total_members else "?"),
                   len(final), len(raw) - len(final)))
            try:
                await bot.send_message(chat_id=user_id,
                    text="👇 <b>CONFIRM ADD</b>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("✅  Add now", callback_data="scrap_add_yes"),
                        InlineKeyboardButton("❌  Cancel", callback_data="scrap_add_no")]]))
            except Exception:
                pass
        else:
            user_gap = max(s.get("user_gap", 60), 1)
            added = 0
            failed = 0
            for uid_val in final:
                if not s["running"]:
                    break
                try:
                    mention = ("@" + uid_val) if not str(uid_val).lstrip("-").isdigit() else str(uid_val)
                    await client.send_message(delivery_entity, mention)
                    added += 1
                except FloodWaitError as e:
                    await asyncio.sleep(int(getattr(e, "seconds", 5)) + 2)
                    try:
                        await client.send_message(delivery_entity, mention)
                        added += 1
                    except Exception as e2:
                        failed += 1
                        logger.warning(f"send user {uid_val} failed: {e2}")
                except Exception as e:
                    failed += 1
                    logger.warning(f"Failed to send user {uid_val}: {e}")
                if added < len(final):
                    await asyncio.sleep(int(user_gap))

            await notify_progress(bot, user_id,
                "✅ <b>SCRAPE COMPLETE</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "🔎 mode: %s  •  source: %s\n"
                "👤 found: %d\n✅ sent: %d\n❌ failed: %d\n"
                "📤 delivery: %s"
                % (mode_label, source, len(final), added, failed,
                   html.escape(s["delivery"][:45])))
    except asyncio.CancelledError:
        pass
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
        s["running"] = False
        ud.save()
        if user_id in active_tasks:
            active_tasks[user_id].pop("scraper", None)

def _add_fail_reason(e):
    if isinstance(e, UserPrivacyRestrictedError):
        return "user ne privacy me invite band kiya hai"
    if isinstance(e, UserNotMutualContactError):
        return "Telegram restriction — sirf mutual contact add ho sakta hai"
    if isinstance(e, UserChannelsTooMuchError):
        return "user bahut zyada groups/channels me hai"
    if isinstance(e, UserAlreadyParticipantError):
        return "already a member"
    if isinstance(e, UserKickedError):
        return "user group se kicked/banned hai"
    if isinstance(e, ChatAdminRequiredError):
        return "adder account admin nahi hai / invite permission nahi"
    if isinstance(e, PeerFloodError):
        return "peer flood — account pe add limit aa gayi"
    if isinstance(e, ChatWriteForbiddenError):
        return "group me add karne ki permission nahi"
    if isinstance(e, FloodWaitError):
        return "flood wait %ds" % int(getattr(e, "seconds", 0) or 0)
    if isinstance(e, (UsernameNotOccupiedError, UsernameInvalidError)):
        return "username invalid ya exist nahi karta"
    return "%s: %s" % (type(e).__name__, str(e)[:80])

async def scrap_add_task(user_id, phones, bot):
    ud = get_user_data(user_id); s = ud.data["scraper"]
    pending = [str(u).strip() for u in s.get("pending", []) if str(u).strip()]
    if not pending:
        s["add_running"] = False; ud.save(); return
    if isinstance(phones, str):
        phones = [phones]
    for k, v in (("added_uids", []), ("per_acc", {}), ("add_skipped", 0),
                 ("add_added", 0), ("add_failed", 0)):
        s.setdefault(k, v)

    pool = []
    seen_phones = set()
    completed = False
    try:
        for p in phones:
            if not s.get("add_running"):
                break
            if p in seen_phones:
                continue
            seen_phones.add(p)
            c = await get_client(p, ud)
            if not c:
                continue
            d = await resolve_entity(c, s["delivery"])
            if d is None:
                try:
                    await c.disconnect()
                except Exception:
                    pass
                continue
            admin = True
            try:
                perms = await c.get_permissions(d, await c.get_me())
                admin = bool(getattr(perms, "is_admin", False))
            except Exception:
                admin = True
            if not admin:
                try:
                    await c.disconnect()
                except Exception:
                    pass
                continue
            pool.append((p, c, d))

        if not pool:
            reason = RESOLVE_ERRORS.get(s.get("delivery", ""), "")
            await notify_progress(bot, user_id,
                "🛑 <b>ADD ABORTED</b> — koi usable admin account nahi mila\n"
                "📤 delivery: <code>%s</code>\n%s\n\n"
                "<b>Fix:</b> kisi active account ko delivery group me <b>admin</b> "
                "(invite users permission) banao, phir try karo."
                % (html.escape(str(s.get("delivery", ""))[:60]),
                   ("⚠️ " + html.escape(reason[:140])) if reason else ""))
            s["add_running"] = False
            ud.save()
            return

        try:
            s["destination_is_basic"] = all(isinstance(d, Chat) for _, _, d in pool)
        except Exception:
            s["destination_is_basic"] = False

        accs_label = ", ".join("…" + (p[-4:] if len(p) >= 4 else p) for p, _, _ in pool)
        dest_title = getattr(pool[0][2], "title", None) or s["delivery"]
        await notify_progress(bot, user_id,
            "🚀 <b>ADD STARTED — ROUND ROBIN</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🎯 target: <b>%s</b>\n"
            "👥 accounts: <b>%d</b>  (%s)\n"
            "📥 queue: %d\n"
            "⏱️ gap: %ds  (sirf success ke baad)\n"
            "♻️ fail hone par turant next user — time waste nahi"
            % (html.escape(str(dest_title)[:45]), len(pool), accs_label,
               len(pending), int(s.get("add_gap", 20))))

        added = failed = skipped = 0
        total = len(pending)
        processed = 0
        idx = 0
        added_ids = set(str(x) for x in s.get("added_uids", []))
        per_acc = dict(s.get("per_acc") or {})

        async def _do_add(c, d, u, ue):
            if isinstance(d, Chat):
                uid = getattr(ue, "user_id", None)
                if not uid:
                    uid = int(u) if str(u).lstrip("-").isdigit() else None
                if not uid:
                    ue2 = await c.get_entity(int(u) if str(u).lstrip("-").isdigit() else u)
                    uid = ue2.id
                await c(AddChatUserRequest(d.id, int(uid), 0))
            else:
                await c(InviteToChannelRequest(d, [ue]))

        for i, u in enumerate(pending, 1):
            if not s.get("add_running"):
                break
            if str(u) in added_ids:
                skipped += 1
                processed = i
                s["pending"] = pending[i:]
                s["add_skipped"] = skipped
                ud.save()
                continue

            ok = False
            skip_now = False
            last_reason = ""
            used_acc = None
            for attempt in range(len(pool)):
                phone, c, d = pool[(idx + attempt) % len(pool)]
                used_acc = phone[-4:] if len(phone) >= 4 else phone
                ue = None
                try:
                    try:
                        ue = await c.get_entity(int(u) if str(u).lstrip("-").isdigit() else u)
                    except Exception:
                        ue = await c.get_input_entity(int(u) if str(u).lstrip("-").isdigit() else u)
                    await _do_add(c, d, u, ue)
                    ok = True
                    idx = (idx + attempt + 1) % len(pool)
                    break
                except UserAlreadyParticipantError:
                    ok = True
                    skip_now = True
                    idx = (idx + attempt + 1) % len(pool)
                    break
                except FloodWaitError as e:
                    wait = int(getattr(e, "seconds", 0) or 0)
                    last_reason = "flood wait %ds" % wait
                    if wait <= 45:
                        await asyncio.sleep(wait + 2)
                        try:
                            if ue is None:
                                ue = await c.get_input_entity(int(u) if str(u).lstrip("-").isdigit() else u)
                            await _do_add(c, d, u, ue)
                            ok = True
                            idx = (idx + attempt + 1) % len(pool)
                            break
                        except UserAlreadyParticipantError:
                            ok = True
                            skip_now = True
                            idx = (idx + attempt + 1) % len(pool)
                            break
                        except Exception as e2:
                            last_reason = _add_fail_reason(e2)
                    continue
                except Exception as e:
                    last_reason = _add_fail_reason(e)
                    continue

            if ok and not skip_now:
                added += 1
                added_ids.add(str(u))
                per_acc[used_acc] = per_acc.get(used_acc, 0) + 1
                await notify_progress(bot, user_id,
                    "✅ <b>ADDED</b>  •  acct …%s  (%d/%d)\nuser: %s"
                    % (used_acc, i, total, html.escape(str(u))))
            elif skip_now:
                skipped += 1
                added_ids.add(str(u))
                await notify_progress(bot, user_id,
                    "⏭️ <b>SKIPPED</b> — user already group member  •  (%d/%d)\nuser: %s"
                    % (i, total, html.escape(str(u))))
            else:
                failed += 1
                hint = ""
                if "mutual" in last_reason.lower():
                    hint = ("\n💡 Telegram restriction: sirf mutual contact add ho sakta hai. "
                            "Dusre account se try hoga; phir bhi fail to us account ko 24h rest do.")
                elif "privacy" in last_reason.lower():
                    hint = "\n💡 User ne privacy me invite band kiya hai — skip karo."
                elif "flood" in last_reason.lower():
                    hint = "\n💡 Account add-limit pe hai — 24h rest ya dusra account."
                await notify_progress(bot, user_id,
                    "❌ <b>ADD FAILED</b>  •  (%d/%d)\nuser: %s\nreason: %s%s"
                    % (i, total, html.escape(str(u)),
                       html.escape(last_reason or "unknown"), hint))

            processed = i
            s["add_added"] = added
            s["add_failed"] = failed
            s["add_skipped"] = skipped
            s["pending"] = pending[i:]
            s["added_uids"] = list(added_ids)[-8000:]
            s["per_acc"] = per_acc
            ud.save()

            # Gap ONLY after a successful add. Failures move to the next user fast.
            if ok and not skip_now:
                await asyncio.sleep(max(1, int(s.get("add_gap", 20))))
            else:
                await asyncio.sleep(1)

        completed = (processed >= total and s.get("add_running"))
        await notify_progress(bot, user_id,
            "🏁 <b>ADD %s</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🎯 target: <b>%s</b>\n"
            "👥 queued: %d  •  processed: %d  •  left: %d\n"
            "✅ added: %d\n⏭️ skipped: %d\n❌ failed: %d\n"
            "♻️ per account: %s"
            % ("COMPLETE" if completed else "STOPPED",
               html.escape(str(dest_title)[:45]), total, processed,
               max(0, total - processed), added, skipped, failed,
               ", ".join("…%s=%d" % (k, v) for k, v in per_acc.items())))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"scrap_add_task error: {e}")
        await notify_progress(bot, user_id,
            "❌ <b>ADD ERROR</b>\n<code>%s</code>" % html.escape(str(e)[:120]))
    finally:
        for _, c, _ in pool:
            try:
                await c.disconnect()
            except Exception:
                pass
        s["add_running"] = False
        if completed:
            s["pending"] = []
        ud.save()
        if user_id in active_tasks:
            active_tasks[user_id].pop("scrap_add", None)

# ═══════════════════════════════════════════════════════════════════
# BACKGROUND TASK - SCRAP GIRLS
# ═══════════════════════════════════════════════════════════════════

async def scrap_girls_task(user_id, phone, bot):
    ud = get_user_data(user_id); sg = ud.data["scrap_girls"]
    client = await get_client(phone, ud)
    if not client: sg["running"] = False; ud.save(); return
    all_users = []
    try:
        for src in sg["sources"]:
            if not sg["running"]: break
            if len(all_users) >= sg["qty"]: break
            try:
                entity = None
                if "t.me/+" in src:
                    h = src.split("/")[-1].replace("+","")
                    updates = await client(ImportChatInviteRequest(h))
                    if hasattr(updates, 'chats') and updates.chats: entity = updates.chats[0]
                else:
                    entity = await client.get_entity(src)
                if not entity: continue
                offset = 0
                limit = 200
                while sg["running"] and len(all_users) < sg["qty"]:
                    parts = await client(GetParticipantsRequest(
                        entity, ChannelParticipantsSearch(''), offset, limit))
                    if not parts.users: break
                    for u in parts.users:
                        if len(all_users) >= sg["qty"]: break
                        if sg.get("name_filter", True):
                            fn = (u.first_name or "").strip().lower()
                            if not fn: continue
                            match = any(fn.endswith(suf) for suf in GIRL_NAME_SUFFIXES)
                            if not match:
                                continue
                        if u.username: all_users.append(u.username)
                        elif u.id: all_users.append(str(u.id))
                    offset += len(parts.users)
                    await asyncio.sleep(int(sg["delay"] * cpu_delay_factor()))
            except: continue
        sg["scraped"] = len(all_users)
        ud.save()
        if all_users:
            fn = f"girls_{int(time.time())}.txt"
            with open(fn, "w") as f: f.write("\n".join(all_users))
            try:
                await client.send_file("me", fn, caption=f"👩  Scraped <b>{len(all_users)}</b> girls",
                    parse_mode=ParseMode.HTML)
            except:
                with open(fn, "rb") as f:
                    await bot.send_document(chat_id=user_id, document=f, filename=fn,
                        caption=f"👩  Scraped <b>{len(all_users)}</b> girls",
                        parse_mode=ParseMode.HTML)
            os.remove(fn)
            await bot.send_message(chat_id=user_id,
                text=f"✅  <b>Girls Scrape Done!</b>\n━━━━━━━━━━━━━━━━━━\n👤  Members: {len(all_users)}",
                parse_mode=ParseMode.HTML)
        else:
            await bot.send_message(chat_id=user_id, text="❌  No users scraped.", parse_mode=ParseMode.HTML)
    except asyncio.CancelledError: pass
    finally:
        await client.disconnect()
        sg["running"] = False; ud.save()
        if user_id in active_tasks: active_tasks[user_id].pop("scrap_girls", None)

# ═══════════════════════════════════════════════════════════════════
# GROUP MANAGER HANDLERS
# ═══════════════════════════════════════════════════════════════════

def get_gm_client(ud):
    accs = [p for p in ud.data.get("acc", {}) if ud.data["acc"][p].get("active", True)]
    if not accs: return None
    return accs[0]

async def gm_action(user_id, ud, action, target_user):
    phone = get_gm_client(ud)
    if not phone: return "No active account."
    gm = ud.data.get("gm", {})
    gid = gm.get("group_id", 0)
    if not gid: return "Set group ID first."
    client = await get_client(phone, ud)
    if not client: return "Account unavailable."
    try:
        entity = await client.get_entity(int(gid))
        try:
            tu = int(target_user) if target_user.lstrip('-').isdigit() else target_user
            tu_entity = await client.get_entity(tu)
        except:
            if target_user.startswith('@'): target_user = target_user[1:]
            tu_entity = await client.get_entity(target_user)
        from telethon.tl.functions.channels import EditAdminRequest, EditBannedRequest
        from telethon.tl.types import ChatBannedRights, ChatAdminRights
        if action == "ban":
            rights = ChatBannedRights(until_date=None, send_messages=True, send_media=True, send_stickers=True, send_gifs=True, send_games=True, send_inline=True, embed_links=True)
            await client(EditBannedRequest(entity, tu_entity.id, rights))
            return f"✅  Banned {target_user}"
        elif action == "unban":
            rights = ChatBannedRights(until_date=None, send_messages=False, send_media=False, send_stickers=False, send_gifs=False, send_games=False, send_inline=False, embed_links=False)
            await client(EditBannedRequest(entity, tu_entity.id, rights))
            return f"✅  Unbanned {target_user}"
        elif action == "kick":
            await client(EditBannedRequest(entity, tu_entity.id, ChatBannedRights(until_date=None, view_messages=True)))
            rights = ChatBannedRights(until_date=None, send_messages=False, send_media=False, send_stickers=False, send_gifs=False, send_games=False, send_inline=False, embed_links=False)
            await client(EditBannedRequest(entity, tu_entity.id, rights))
            return f"✅  Kicked {target_user}"
        elif action == "mute":
            rights = ChatBannedRights(until_date=None, send_messages=True)
            await client(EditBannedRequest(entity, tu_entity.id, rights))
            return f"🔇  Muted {target_user}"
        elif action == "unmute":
            rights = ChatBannedRights(until_date=None, send_messages=False)
            await client(EditBannedRequest(entity, tu_entity.id, rights))
            return f"🔊  Unmuted {target_user}"
        elif action == "promote":
            rights = ChatAdminRights(change_info=True, post_messages=True, edit_messages=True, delete_messages=True, ban_users=True, invite_users=True, pin_messages=True, add_admins=False, anonymous=False, manage_call=True, other=True)
            await client(EditAdminRequest(entity, tu_entity.id, rights, rank="admin"))
            return f"⭐  Promoted {target_user}"
        elif action == "demote":
            rights = ChatAdminRights()
            await client(EditAdminRequest(entity, tu_entity.id, rights, rank=""))
            return f"⬇️  Demoted {target_user}"
        elif action == "pin":
            msg = await client.send_message(entity, "📌")
            from telethon.tl.functions.messages import UpdatePinnedMessageRequest
            await client(UpdatePinnedMessageRequest(entity, msg.id))
            return "📌  Pinned"
    except Exception as e:
        return f"❌  Error: {str(e)[:80]}"
    finally:
        await client.disconnect()

async def join_request_handler(update, context):
    cr = update.chat_join_request
    if not cr: return
    ud = get_user_data(OWNER_ID)
    gm = ud.data.get("gm", {})
    if not gm.get("join_reply", True): return
    if cr.chat.id != gm.get("group_id", 0): return
    txt = gm.get("join_reply_text", "{username} Your request is received to join {grouptitle} received sweetie and it will accept soon.")
    txt = txt.replace("{username}", f"@{cr.from_user.username}" if cr.from_user.username else cr.from_user.first_name or "User")
    txt = txt.replace("{grouptitle}", str(cr.chat.title or "Group"))
    try:
        await cr.approve()
        await context.bot.send_message(chat_id=cr.from_user.id, text=txt, parse_mode=ParseMode.HTML)
    except: pass

async def new_member_handler(update, context):
    cm = update.chat_member
    if not cm or not cm.new_chat_member or not cm.new_chat_member.status: return
    new = cm.new_chat_member
    # Auto-set managed group when owner adds the bot
    if new.user.id == context.bot.id and new.status in ("member", "administrator"):
        if cm.from_user and cm.from_user.id == OWNER_ID:
            ud = get_user_data(OWNER_ID)
            existing_id = ud.data.get("gm", {}).get("group_id", 0)
            if existing_id and existing_id != cm.chat.id:
                await context.bot.send_message(chat_id=OWNER_ID,
                    text=f"⚠️  <b>Group Manager already active</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                         f"Bot was added to <b>{html.escape(cm.chat.title or 'this group')}</b>.\n\n"
                         f"Already managing group ID <code>{existing_id}</code>.\n"
                         "To switch, use the Group Manager menu to change the group.",
                    parse_mode=ParseMode.HTML)
                return
            if existing_id == cm.chat.id:
                return
            ud.data.setdefault("gm", {})
            ud.data["gm"]["group_id"] = cm.chat.id
            ud.data["gm"]["group_title"] = cm.chat.title or "Group"
            ud.save()
            title = cm.chat.title or "this group"
            await context.bot.send_message(chat_id=OWNER_ID,
                text=f"✅  <b>Group Manager activated!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                     f"<b>{html.escape(title)}</b> is now your managed group.\n"
                     f"Use the Group Manager menu to configure settings.",
                parse_mode=ParseMode.HTML)
            log_activity(OWNER_ID, f"Auto-set managed group: {cm.chat.id} ({cm.chat.title})")
        return

    ud = get_user_data(OWNER_ID)
    gm = ud.data.get("gm", {})
    if not gm.get("notify", True): return
    if new.status in ("member", "administrator"):
        if cm.chat.id != gm.get("group_id", 0): return
        u = cm.new_chat_member.user
        if not u: return
        name = f"@{u.username}" if u.username else u.first_name or "User"
        await context.bot.send_message(chat_id=OWNER_ID,
            text=f"👤  <b>New Member</b>\n━━━━━━━━━━━━━━━━━━\n{name} joined <b>{cm.chat.title or 'Group'}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅  Approve", callback_data=f"gm_app_{u.id}"),
                 InlineKeyboardButton("❌  Deny", callback_data=f"gm_deny_{u.id}")]
            ]))
        # Send welcome message if enabled
        if gm.get("welcome_enabled") and gm.get("welcome_text"):
            wt = gm["welcome_text"]
            wt = wt.replace("{name}", u.first_name or "User")
            wt = wt.replace("{title}", cm.chat.title or "Group")
            try:
                await context.bot.send_message(chat_id=cm.chat.id,
                    text=wt, parse_mode=ParseMode.HTML)
            except: pass

async def group_text_handler(update, context):
    ud = get_user_data(OWNER_ID)
    gm = ud.data.get("gm", {})
    gid = gm.get("group_id", 0)
    if not gid: return
    if not update.message: return
    if update.message.chat.id != gid: return

    user_obj = update.effective_user or update.message.from_user
    if not user_obj: return
    user_id = user_obj.id
    first_name = user_obj.first_name or "User"
    msg_text = (update.message.text or "").lower().strip()
    caption = (update.message.caption or "").lower().strip()

    # Media Filter - delete photos, stickers, animated stickers
    if gm.get("media_filter") and (update.message.photo or update.message.sticker):
        try:
            await update.message.delete()
            logger.info(f"MediaFilter: Deleted media from {user_id} in {gid}")
            log_activity(OWNER_ID, f"MediaFilter: deleted {user_id}'s media in {gid}")
        except Exception as e:
            logger.warning(f"MediaFilter delete error: {e}")
        return

    # Abusive words check (text + caption)
    full_text = (msg_text + " " + caption).strip()
    for word in ABUSIVE_WORDS:
        if word in full_text:
            try:
                await update.message.delete()
            except: pass
            warns = gm.setdefault("_warns", {})
            uw = warns.get(str(user_id), 0) + 1
            warns[str(user_id)] = uw
            ud.save()
            max_w = gm.get("warn_max", 3)
            if uw >= max_w:
                phone = get_gm_client(ud)
                if phone:
                    client = await get_client(phone, ud)
                    if client:
                        try:
                            from telethon.tl.functions.channels import EditBannedRequest
                            from telethon.tl.types import ChatBannedRights
                            entity = await client.get_entity(int(gid))
                            rights = ChatBannedRights(until_date=None, send_messages=True)
                            await client(EditBannedRequest(entity, user_id, rights))
                            warns[str(user_id)] = 0
                            ud.save()
                            await context.bot.send_message(chat_id=gid,
                                text=f"⚠️  User <b>{first_name}</b> muted after {uw} warns (abusive language).",
                                parse_mode=ParseMode.HTML)
                            log_activity(OWNER_ID, f"Auto-muted {user_id} after {uw} abusive warns")
                        except: pass
                        finally:
                            await client.disconnect()
            else:
                await context.bot.send_message(chat_id=gid,
                    text=f"⚠️  <b>{first_name}</b> warning {uw}/{max_w} — abusive language detected.",
                    parse_mode=ParseMode.HTML)
            return

    if not msg_text: return

    # Filters
    for word in gm.get("filters", []):
        if word.lower() in msg_text:
            try:
                await update.message.delete()
            except: pass
            # Track warnings
            warns = gm.setdefault("_warns", {})
            uw = warns.get(str(user_id), 0) + 1
            warns[str(user_id)] = uw
            ud.save()
            max_w = gm.get("warn_max", 3)
            if uw >= max_w:
                phone = get_gm_client(ud)
                if phone:
                    client = await get_client(phone, ud)
                    if client:
                        try:
                            from telethon.tl.functions.channels import EditBannedRequest
                            from telethon.tl.types import ChatBannedRights
                            entity = await client.get_entity(int(gid))
                            rights = ChatBannedRights(until_date=None, send_messages=True)
                            await client(EditBannedRequest(entity, user_id, rights))
                            warns[str(user_id)] = 0
                            ud.save()
                            await context.bot.send_message(chat_id=gid,
                                text=f"⚠️  User <b>{first_name}</b> muted after {uw} warns.",
                                parse_mode=ParseMode.HTML)
                            log_activity(OWNER_ID, f"Auto-muted {user_id} after {uw} filter warns")
                        except: pass
                        finally:
                            await client.disconnect()
            else:
                await context.bot.send_message(chat_id=gid,
                    text=f"⚠️  <b>{first_name}</b> warning {uw}/{max_w} — filtered word detected.",
                    parse_mode=ParseMode.HTML)
            return

    # Link filter
    if gm.get("link_filter"):
        text_to_check = (update.message.text or update.message.caption or "")
        if re.search(r'(t\.me/|https?://t\.me/|@[a-zA-Z0-9_]{5,})', text_to_check):
            try:
                await update.message.delete()
                first = first_name
                txt = gm.get("link_delete_msg", "⚠️  {first}, please remove links from your bio and don't share group/channel links here.").replace("{first}", first)
                await update.message.chat.send_message(txt)
            except:
                pass
            return

    # Bio filter
    if gm.get("bio_filter"):
        phone = get_gm_client(ud)
        if phone:
            client = await get_client(phone, ud)
            if client:
                try:
                    user_entity = await client.get_entity(user_id)
                    if hasattr(user_entity, 'about') and user_entity.about:
                        if re.search(r'(t\.me/|https?://|@[a-zA-Z0-9_]{5,})', user_entity.about):
                            try:
                                await update.message.delete()
                                first = first_name
                                txt = gm.get("link_delete_msg", "⚠️  {first}, please remove links from your bio and don't share group/channel links here.").replace("{first}", first)
                                await update.message.chat.send_message(txt)
                            except:
                                pass
                except:
                    pass
                finally:
                    try: await client.disconnect()
                    except: pass

    # Antiflood
    if gm.get("antiflood", {}):
        af_data = gm.setdefault("_af_data", {})
        now = time.time()
        interval = gm.get("antiflood_interval", 3)
        max_msgs = gm.get("antiflood_msgs", 5)
        uid_str = str(user_id)
        entry = af_data.get(uid_str, {"count": 0, "start": now})
        if now - entry["start"] > interval:
            entry["count"] = 1
            entry["start"] = now
        else:
            entry["count"] += 1
        af_data[uid_str] = entry
        ud.save()
        if entry["count"] > max_msgs:
            action = gm.get("antiflood_action", "mute")
            phone = get_gm_client(ud)
            if phone:
                client = await get_client(phone, ud)
                if client:
                    try:
                        from telethon.tl.functions.channels import EditBannedRequest
                        from telethon.tl.types import ChatBannedRights
                        entity = await client.get_entity(int(gid))
                        if action == "mute":
                            rights = ChatBannedRights(until_date=None, send_messages=True)
                            await client(EditBannedRequest(entity, user_id, rights))
                            await context.bot.send_message(chat_id=gid,
                                text=f"🔇  <b>{first_name}</b> muted for antiflood.",
                                parse_mode=ParseMode.HTML)
                        elif action == "ban":
                            rights = ChatBannedRights(until_date=None, view_messages=True, send_messages=True)
                            await client(EditBannedRequest(entity, user_id, rights))
                            await context.bot.send_message(chat_id=gid,
                                text=f"🚫  <b>{first_name}</b> banned for antiflood.",
                                parse_mode=ParseMode.HTML)
                        log_activity(OWNER_ID, f"Antiflood {action} for {user_id}")
                    except: pass
                    finally:
                        await client.disconnect()
            af_data[uid_str] = {"count": 0, "start": time.time()}
            ud.save()

# ═══════════════════════════════════════════════════════════════════
# BACKGROUND TASK - BANNING REVIEW
# ═══════════════════════════════════════════════════════════════════

async def banning_review_task(user_id, bot):
    ud = get_user_data(user_id); b = ud.data.get("banning", {})
    client = None
    try:
        accs = [p for p in ud.data.get("acc", {}) if ud.data["acc"][p].get("active", True)]
        if not accs:
            await bot.send_message(chat_id=user_id, text="❌  No active accounts.")
            b["running"] = False; ud.save(); return
        phone = accs[0]
        client = await get_client(phone, ud)
        if not client:
            await bot.send_message(chat_id=user_id, text="❌  Account unavailable.")
            b["running"] = False; ud.save(); return

        await bot.send_message(chat_id=user_id, text="🔍  Connecting to target...", parse_mode=ParseMode.HTML)

        target_str = b.get("target", "")
        entity = None
        target_id = None
        try:
            if "t.me/+" in target_str or "joinchat" in target_str:
                h = target_str.split("/")[-1].replace("+", "")
                try:
                    updates = await client(ImportChatInviteRequest(h))
                    if hasattr(updates, 'chats') and updates.chats:
                        entity = updates.chats[0]
                except UserAlreadyParticipantError:
                    invite = await client(CheckChatInviteRequest(h))
                    if hasattr(invite, 'channel'):
                        entity = invite.channel
                    elif hasattr(invite, 'chat'):
                        entity = invite.chat
                    else:
                        raise
                    entity = await client.get_entity(entity.id)
            else:
                entity = await client.get_entity(target_str)
        except Exception as e:
            await bot.send_message(chat_id=user_id,
                text=f"❌  Cannot access target: {str(e)[:100]}", parse_mode=ParseMode.HTML)
            b["running"] = False; ud.save(); return

        target_id = entity.id
        target_name = getattr(entity, 'title', None) or getattr(entity, 'first_name', None) or str(target_id)
        entity_type = type(entity).__name__
        await bot.send_message(chat_id=user_id,
            text=f"✅  Target found: <b>{target_name}</b> (Type: {entity_type}, ID: {target_id})",
            parse_mode=ParseMode.HTML)

        await bot.send_message(chat_id=user_id, text="📥  Scraping all messages...", parse_mode=ParseMode.HTML)
        all_texts = []
        msg_count = 0
        scan_limit = b.get("msg_limit", 5000)
        if scan_limit == "all":
            scan_limit = 5000
        else:
            scan_limit = int(scan_limit)
        human_delay = random.uniform(0.3, 0.8)
        try:
            msgs = await client.get_messages(entity, limit=scan_limit)
            for msg in msgs:
                msg_count += 1
                parts = [f"[MSG #{msg.id} | {msg.date}]"]
                if msg.text:
                    parts.append(f"Text: {msg.text[:400]}")
                if getattr(msg, 'media', None):
                    from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, MessageMediaPoll, MessageMediaContact, MessageMediaGeo, MessageMediaInvoice, MessageMediaWebPage, MessageMediaGame, MessageMediaDice, MessageMediaGiveaway
                    from telethon.tl.types import DocumentAttributeSticker, DocumentAttributeVideo, DocumentAttributeAudio
                    if msg.sticker:
                        sticker_info = f"[🎨 STICKER: {getattr(msg.sticker, 'emoji', '') or '?'}]"
                        parts.append(sticker_info)
                    elif isinstance(msg.media, MessageMediaPhoto):
                        parts.append("[📷 PHOTO]")
                    elif isinstance(msg.media, MessageMediaDocument):
                        has_video = any(isinstance(a, DocumentAttributeVideo) for a in getattr(msg.media.document, 'attributes', []))
                        has_audio = any(isinstance(a, DocumentAttributeAudio) for a in getattr(msg.media.document, 'attributes', []))
                        has_sticker = any(isinstance(a, DocumentAttributeSticker) for a in getattr(msg.media.document, 'attributes', []))
                        if has_sticker:
                            parts.append("[🎨 STICKER]")
                        elif has_video:
                            parts.append("[🎬 VIDEO]")
                        elif has_audio:
                            parts.append("[🎵 AUDIO]")
                        else:
                            parts.append("[📄 DOCUMENT]")
                    elif isinstance(msg.media, MessageMediaPoll):
                        parts.append("[📊 POLL]")
                    elif isinstance(msg.media, MessageMediaContact):
                        parts.append("[👤 CONTACT SHARED]")
                    elif isinstance(msg.media, MessageMediaGeo):
                        parts.append("[📍 LOCATION SHARED]")
                    elif isinstance(msg.media, MessageMediaInvoice):
                        parts.append("[💰 INVOICE/PAYMENT]")
                    elif isinstance(msg.media, MessageMediaGame):
                        parts.append("[🎮 GAME]")
                    elif isinstance(msg.media, MessageMediaDice):
                        parts.append("[🎲 DICE]")
                    elif isinstance(msg.media, MessageMediaGiveaway):
                        parts.append("[🎁 GIVEAWAY]")
                    elif isinstance(msg.media, MessageMediaWebPage):
                        pass
                    else:
                        parts.append("[📎 MEDIA]")
                if msg.forward:
                    parts.append(f"[FORWARDED from {getattr(msg.forward, 'chat_id', 'unknown')}]")
                text = " | ".join(parts)
                if len(text) > 600:
                    text = text[:600] + "..."
                all_texts.append(text)
                if msg_count % 5 == 0:
                    await asyncio.sleep(random.uniform(0.1, 0.3))
        except Exception as e:
            await bot.send_message(chat_id=user_id,
                text=f"⚠️  Message fetch error: {str(e)[:100]}", parse_mode=ParseMode.HTML)

        await asyncio.sleep(random.uniform(0.5, 1.5))

        # Get full channel info
        try:
            from telethon.tl.functions.channels import GetFullChannelRequest
            full = await client(GetFullChannelRequest(entity.id))
            if hasattr(full, 'full_chat') and hasattr(full.full_chat, 'about'):
                full_about = full.full_chat.about or ""
        except:
            full_about = ""

        await bot.send_message(chat_id=user_id,
            text=f"📊  Scraped {msg_count} messages. Analyzing with AI...",
            parse_mode=ParseMode.HTML)

        await asyncio.sleep(random.uniform(0.8, 2.0))

        # Fetch all participants
        all_members = []
        try:
            if hasattr(entity, 'megagroup') or hasattr(entity, 'gigagroup') or (hasattr(entity, 'broadcast') and not entity.broadcast):
                from telethon.tl.functions.channels import GetParticipantsRequest
                from telethon.tl.types import ChannelParticipantsSearch
                async for member in client.iter_participants(entity, limit=5000):
                    name = f"{getattr(member, 'first_name', '') or ''} {getattr(member, 'last_name', '') or ''}".strip()
                    uname = f"@{member.username}" if getattr(member, 'username', None) else ""
                    all_members.append(f"{name} {uname} (ID: {member.id})".strip())
                    if len(all_members) >= 5000:
                        break
        except:
            pass

        info_parts = [f"Target: {target_name}", f"ID: {target_id}", f"Type: {b['target_type']}", f"Total Messages Scraped: {msg_count}"]
        if all_members:
            info_parts.append(f"Total Members Fetched: {len(all_members)}")
        if hasattr(entity, 'participants_count'):
            info_parts.append(f"Members (shown): {entity.participants_count}")
        if hasattr(entity, 'username') and entity.username:
            info_parts.append(f"Username: @{entity.username}")
        if hasattr(entity, 'about') and entity.about:
            info_parts.append(f"About: {entity.about[:300]}")
        if full_about:
            info_parts.append(f"Full Description: {full_about[:500]}")
        if all_members:
            info_parts.append(f"\n📋 MEMBER LIST ({len(all_members)} members):")
            info_parts.extend(all_members[:50])

        if b["target_type"] == "user":
            try:
                full = await client(functions.users.GetFullUserRequest(entity.id))
                if hasattr(full, 'full_user') and hasattr(full.full_user, 'about'):
                    info_parts.append(f"Bio: {full.full_user.about[:300]}")
            except:
                pass

        entity_info = "\n".join(info_parts)

        await asyncio.sleep(random.uniform(0.5, 1.5))

        from groq import Groq
        groq_client = Groq(api_key=b["groq_api"])

        CATEGORIES = [
            "SPAM", "HATE_SPEECH", "HARASSMENT", "VIOLENCE", "TERRORISM",
            "CHILD_SAFETY", "NSFW_PORNOGRAPHY", "ILLEGAL_GOODS_DRUGS_WEAPONS",
            "SCAM_FRAUD_PHISHING", "COPYRIGHT", "IMPERSONATION",
            "PRIVACY_VIOLATION", "DEFAMATION", "CRIMINAL_INTIMIDATION",
            "PUBLIC_MISCHIEF", "BOT_VIOLATION", "MISINFORMATION",
            "PERSONAL_DATA_LEAK", "FINANCIAL_CRIME", "NONE"
        ]

        CATEGORY_LABELS = {
            "SPAM": "Spam / Unsolicited Messages",
            "HATE_SPEECH": "Hate Speech / Discrimination",
            "HARASSMENT": "Harassment / Bullying",
            "VIOLENCE": "Violence / Threats",
            "TERRORISM": "Terrorism / Extremism",
            "CHILD_SAFETY": "Child Safety Violation",
            "NSFW_PORNOGRAPHY": "NSFW / Pornography",
            "ILLEGAL_GOODS_DRUGS_WEAPONS": "Illegal Goods, Drugs & Weapons",
            "SCAM_FRAUD_PHISHING": "Scam / Fraud / Phishing",
            "COPYRIGHT": "Copyright Infringement",
            "IMPERSONATION": "Impersonation / Fake Identity",
            "PRIVACY_VIOLATION": "Privacy Violation (Doxing, etc.)",
            "DEFAMATION": "Defamation (IPC 499/500)",
            "CRIMINAL_INTIMIDATION": "Criminal Intimidation (IPC 503)",
            "PUBLIC_MISCHIEF": "Public Mischief (IPC 505)",
            "BOT_VIOLATION": "Bot / Automation Policy Violation",
            "MISINFORMATION": "Misinformation / Fake News",
            "PERSONAL_DATA_LEAK": "Personal Data Leak / GDPR Violation",
            "FINANCIAL_CRIME": "Financial Crime / Money Laundering",
            "NONE": "No Violation / Clean"
        }

        ANALYSIS_PROMPT = f"""You are a strict Telegram compliance & legal analyst. Review each message below and classify EVERY message into ONE of these categories:

{chr(10).join(f'- {cat} = {CATEGORY_LABELS[cat]}' for cat in CATEGORIES)}

For each message, output EXACTLY:
MSG#id | CATEGORY | SEVERITY(Low/Medium/High/Critical) | COMMENT(1 sentence explaining why)

Example:
MSG#5 | SCAM_FRAUD_PHISHING | High | Promises free money in exchange for sharing personal bank details, which is a clear phishing scam.
MSG#12 | NONE | None | Normal conversation about daily life.
MSG#20 | HATE_SPEECH | Critical | Contains racial slurs targeting a specific community, violating Indian IPC 505 and Telegram hate speech policy.

TARGET INFO:
{entity_info}

MESSAGES TO ANALYZE:
"""

        def chunk_messages(msgs, size):
            for i in range(0, len(msgs), size):
                yield msgs[i:i+size]

        all_classifications = []
        total_chunks = (len(all_texts) // 100) + 1
        status_msg = await bot.send_message(chat_id=user_id,
            text=f"🤖  Analyzing 0/{total_chunks} batches...",
            parse_mode=ParseMode.HTML)
        for ci, chunk in enumerate(chunk_messages(all_texts, 100)):
            start_idx = ci * 100 + 1
            end_idx = min((ci + 1) * 100, len(all_texts))
            pct = int((ci / total_chunks) * 100)
            bar = "▓" * (pct // 10) + "░" * (10 - pct // 10) if pct < 100 else "▓" * 10
            try:
                await status_msg.edit_text(
                    text=f"🤖  Analyzing batch {ci+1}/{total_chunks}\n"
                         f"📄  Messages {start_idx}-{end_idx} of {len(all_texts)}\n"
                         f"{bar} {pct}%\n"
                         f"⏳  Querying models...",
                    parse_mode=ParseMode.HTML)
            except:
                pass
            chunk_text = "\n".join(chunk)
            payload = ANALYSIS_PROMPT + chunk_text
            groq_models = [
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768"
            ]
            raw = None
            for model in groq_models:
                try:
                    try:
                        await status_msg.edit_text(
                            text=f"🤖  Batch {ci+1}/{total_chunks}\n"
                                 f"📄  Messages {start_idx}-{end_idx}\n"
                                 f"{bar} {pct}%\n"
                                 f"⏳  Model: {model}",
                            parse_mode=ParseMode.HTML)
                    except:
                        pass
                    c = groq_client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": payload}],
                        temperature=0.1,
                        max_tokens=4000
                    )
                    raw = c.choices[0].message.content
                    break
                except Exception as e:
                    try:
                        await status_msg.edit_text(
                            text=f"🤖  Batch {ci+1}/{total_chunks}\n"
                                 f"📄  Messages {start_idx}-{end_idx}\n"
                                 f"{bar} {pct}%\n"
                                 f"⚠️  {model} failed: {str(e)[:40]}",
                            parse_mode=ParseMode.HTML)
                    except:
                        pass
                    continue
            if raw is None:
                try:
                    await status_msg.edit_text(
                        text=f"🤖  Batch {ci+1}/{total_chunks}\n"
                             f"📄  Messages {start_idx}-{end_idx}\n"
                             f"{bar} {pct}%\n"
                             f"❌  All models failed",
                        parse_mode=ParseMode.HTML)
                except:
                    pass
                continue
            for line in raw.split("\n"):
                line = line.strip()
                if line.startswith("MSG#") and "|" in line:
                    all_classifications.append(line)
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 4:
                        cat = parts[1].strip().upper()
                        if cat != "NONE" and cat in CATEGORIES:
                            sev = parts[2].strip() if len(parts) >= 3 else "-"
                            comment = parts[3].strip() if len(parts) >= 4 else ""
                            pass  # violations collected; reported after full analysis
            await asyncio.sleep(1)

        try:
            unique_cats = len(set(line.split("|")[1].strip().upper() for line in all_classifications if "|" in line)) if all_classifications else 0
            await status_msg.edit_text(
                text=f"✅  AI Analysis complete!\n"
                     f"📊  {len(all_classifications)}/{len(all_texts)} messages classified\n"
                     f"📋  {unique_cats} categories affected",
                parse_mode=ParseMode.HTML)
        except:
            pass

        # Build categorized report
        by_category = {}
        for cl in all_classifications:
            parts = [p.strip() for p in cl.split("|")]
            if len(parts) >= 4:
                cat = parts[1].strip().upper()
                if cat not in CATEGORIES:
                    cat = "NONE"
                by_category.setdefault(cat, []).append(cl)

        # Full entity analysis pass
        await bot.send_message(chat_id=user_id,
            text="📝  Generating comprehensive report...", parse_mode=ParseMode.HTML)

        full_entity_prompt = f"""You are a senior legal & policy compliance analyst. Review the ENTIRE target entity below and provide:

1. OVERALL RISK ASSESSMENT (Low/Medium/High/Critical)
2. TOP VIOLATIONS FOUND (list each with category, severity, and detailed comment)
3. LAWS VIOLATED (specific sections)
4. RECOMMENDED ACTION (ban, restrict, report to authorities, etc.)
5. SUMMARY COMMENT for the entire target

TARGET INFO:
{entity_info}

Here is the complete message classification data:
{chr(10).join(all_classifications[-200:])}

OUTPUT FORMAT:
=== OVERALL RISK: [LEVEL] ===
=== TOP VIOLATIONS ===
1. Category: [CAT] | Severity: [SEV] | Comment: [detailed explanation of what was found and why it violates policy/law]
2. ...
=== LAWS VIOLATED ===
- [Law/Section]: [explanation]
=== RECOMMENDED ACTION ===
[detailed action plan]
=== SUMMARY COMMENT ===
[1-2 paragraph final assessment of this target]
"""
        entity_summary = "Summary generation failed."
        for smodel in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]:
            try:
                c2 = groq_client.chat.completions.create(
                    model=smodel,
                    messages=[{"role": "user", "content": full_entity_prompt}],
                    temperature=0.2,
                    max_tokens=6000
                )
                entity_summary = c2.choices[0].message.content
                break
            except:
                continue

        # Generate formal ban letter
        await bot.send_message(chat_id=user_id,
            text="📄  Drafting formal complaint letter...", parse_mode=ParseMode.HTML)

        violation_list = "\n".join(all_classifications[-100:]) if all_classifications else "No specific violations found."
        ban_letter_prompt = f"""You are a legal compliance officer. Write a FORMAL COMPLAINT LETTER to Telegram's abuse department requesting the immediate ban/suspension of the following target for policy violations.

TARGET:
- Name: {target_name}
- ID: {target_id}
- Type: {b['target_type']}

VIOLATIONS FOUND:
{violation_list}

Write a formal letter with:
1. Date and subject line
2. Target details (name, ID, type)
3. Detailed description of violations found (cite specific categories and examples)
4. Legal references (relevant Telegram ToS sections, applicable laws)
5. Requested action (ban/suspend the account/group/channel)
6. Sender's declaration (good faith report)

Format the letter professionally. Use formal legal language. Include a clear subject line.
"""

        ban_letter = "Could not generate formal letter."
        for lmodel in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]:
            try:
                c3 = groq_client.chat.completions.create(
                    model=lmodel,
                    messages=[{"role": "user", "content": ban_letter_prompt}],
                    temperature=0.3,
                    max_tokens=4000
                )
                ban_letter = c3.choices[0].message.content
                break
            except:
                continue

        await bot.send_message(chat_id=user_id,
            text=f"📄  <b>Formal Complaint Letter</b>\n━━━━━━━━━━━━━━━━━━\n<pre>{html.escape(ban_letter[:3000])}</pre>",
            parse_mode=ParseMode.HTML)

        # Store report data and ask user for bulk report params
        violations_found = sum(len(v) for c, v in by_category.items() if c != "NONE")
        report_submitted = False
        if violations_found > 0:
            violation_ids = []
            for c, entries in by_category.items():
                if c != "NONE":
                    for e in entries:
                        try:
                            mid = int(e.split("|")[0].replace("MSG#", "").strip())
                            violation_ids.append(mid)
                        except: pass
            if violation_ids:
                # Build violation context for AI
                violation_summary_lines = []
                for c, entries in by_category.items():
                    if c != "NONE":
                        for e in entries[:3]:
                            p = [x.strip() for x in e.split("|")]
                            if len(p) >= 4:
                                violation_summary_lines.append(f"- {CATEGORY_LABELS.get(p[1], p[1])}: {p[3][:150]}")
                violation_context = "\n".join(violation_summary_lines[:20]) if violation_summary_lines else "Various policy violations"

                # Store report context in user data for bulk submission
                ud.data["_ban_report"] = {
                    "entity_id": entity.id if hasattr(entity, 'id') else None,
                    "entity_username": getattr(entity, 'username', None),
                    "report_ids": violation_ids[:100],
                    "violation_ctx": violation_context,
                    "groq_api": b["groq_api"],
                    "phone": phone
                }
                ud.save()

                await bot.send_message(chat_id=user_id,
                    text="📮  <b>BULK REPORT SETUP</b>\n━━━━━━━━━━━━━━━━━━\n"
                         f"Found <b>{len(violation_ids[:100])}</b> violating messages.\n\n"
                         "Enter the <b>number of reports</b> to send (e.g. 5 or 10):",
                    parse_mode=ParseMode.HTML)
                # Store state for next handler
                ud.data["_ban_report"]["_state"] = BAN_REPORT_COUNT
                ud.save()
                b["running"] = False
                if user_id in active_tasks:
                    active_tasks[user_id].pop("banning", None)
                if client:
                    await client.disconnect()
                    client = None
                return  # exit task, user will respond via message handler

        total_violations = violations_found

        # Send comprehensive report as Telegram message
        report_msg = (
            f"🚨  <b>Full Violation Report</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎯  {target_name}\n"
            f"📊  {msg_count} msgs scanned, {total_violations} violations\n"
            f"📋  Categories: {len([c for c in by_category if c != 'NONE' and by_category[c]])} affected\n"
            f"{'✅ Report submitted to Telegram' if report_submitted else '❌ Could not submit'}\n\n"
            f"<b>Entity Summary:</b>\n<pre>{html.escape(entity_summary[:1500])}</pre>\n\n"
        )

        if total_violations == 0:
            report_msg += "✅  No violations found in any category."
            await bot.send_message(chat_id=user_id, text=report_msg, parse_mode=ParseMode.HTML)
        else:
            await bot.send_message(chat_id=user_id, text=report_msg, parse_mode=ParseMode.HTML)
            # Send per-category details
            for cat in CATEGORIES:
                entries = by_category.get(cat, [])
                if entries and cat != "NONE":
                    chunk = f"🚫  <b>{CATEGORY_LABELS[cat]}</b> ({len(entries)})\n"
                    for e in entries[:10]:
                        p = [x.strip() for x in e.split("|")]
                        sev = p[2] if len(p) >= 3 else "-"
                        cmt = html.escape(p[3][:200]) if len(p) >= 4 else ""
                        chunk += f"⚠️ {sev}: {cmt}\n"
                    if len(entries) > 10:
                        chunk += f"... and {len(entries)-10} more\n"
                    try:
                        await bot.send_message(chat_id=user_id, text=chunk, parse_mode=ParseMode.HTML)
                    except:
                        for sub in [chunk[i:i+4000] for i in range(0, len(chunk), 4000)]:
                            try: await bot.send_message(chat_id=user_id, text=sub, parse_mode=ParseMode.HTML)
                            except: pass

        # Per-category live summary
        cat_summary = ""
        for cat in CATEGORIES:
            entries = by_category.get(cat, [])
            if entries and cat != "NONE":
                sample = entries[0]
                sev = sample.split("|")[2].strip() if len(sample.split("|")) >= 3 else "-"
                cat_summary += f"  🚫  <b>{CATEGORY_LABELS[cat]}</b> ({len(entries)})\n"
                cat_summary += f"       Severity: {sev}\n"
                comment_parts = sample.split("|")
                if len(comment_parts) >= 4:
                    cat_summary += f"       💬  {comment_parts[3].strip()[:100]}\n"
                cat_summary += "\n"

        if not cat_summary:
            cat_summary = "  ✅  No violations found in any category.\n"

        await bot.send_message(chat_id=user_id,
            text=(
                f"📋  <b>VIOLATION SUMMARY</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"{cat_summary}"
                f"📌  Full report sent above."
            ),
            parse_mode=ParseMode.HTML)

        b.setdefault("reports", []).append({
            "target": target_name,
            "target_id": target_id,
            "date": datetime.now().isoformat(),
            "submitted": report_submitted,
            "messages_scanned": msg_count,
            "violations_found": total_violations,
            "categories_affected": len([c for c in by_category if c != "NONE" and by_category[c]])
        })

        if report_submitted:
            success_text = (
                "✅  <b>REVIEW COMPLETE!</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"🎯  Target:       <b>{target_name}</b>\n"
                f"🆔  ID:           <code>{target_id}</code>\n"
                f"📊  Messages:     {msg_count}\n"
                f"🚫  Violations:   {total_violations}\n"
                f"📂  Categories:   {len([c for c in by_category if c != 'NONE' and by_category[c]])}\n"
                f"📮  Telegram:     Report submitted successfully\n\n"
                "All violations have been documented, categorized, and reported."
            )
        else:
            success_text = (
                "⚠️  <b>REVIEW COMPLETE</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"🎯  Target:       <b>{target_name}</b>\n"
                f"🆔  ID:           <code>{target_id}</code>\n"
                f"📊  Messages:     {msg_count}\n"
                f"🚫  Violations:   {total_violations}\n"
                f"📂  Categories:   {len([c for c in by_category if c != 'NONE' and by_category[c]])}\n"
                f"📄  Report:      Sent as messages above\n"
                f"❌  Telegram:     Report submission failed\n\n"
                "Report saved locally. Submit manually if needed."
            )

        await bot.send_message(chat_id=user_id, text=success_text, parse_mode=ParseMode.HTML)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Banning review error: {e}")
        try:
            await bot.send_message(chat_id=user_id, text=f"❌  Error: {str(e)[:200]}", parse_mode=ParseMode.HTML)
        except:
            pass
    finally:
        if client:
            await client.disconnect()
        b["running"] = False
        ud.save()
        if user_id in active_tasks:
            active_tasks[user_id].pop("banning", None)

# ═══════════════════════════════════════════════════════════════════
# BULK REPORT TASK
# ═══════════════════════════════════════════════════════════════════

async def bulk_report_task(user_id, bot, ctx_data):
    ud = get_user_data(user_id)
    client = None
    try:
        entity = ctx_data.get("report_entity")
        report_ids = ctx_data.get("report_ids", [])
        violation_context = ctx_data.get("report_violation_ctx", "Various policy violations")
        groq_api_key = ctx_data.get("report_groq_api")
        count = ctx_data.get("report_count", 1)
        lo = ctx_data.get("report_interval_lo", 5)
        hi = ctx_data.get("report_interval_hi", 10)
        phone = ctx_data.get("report_phone")

        if not entity or not report_ids:
            await bot.send_message(chat_id=user_id, text="❌  Report data missing.", parse_mode=ParseMode.HTML)
            return

        from groq import Groq
        groq_client = Groq(api_key=groq_api_key)
        from telethon.tl.functions.messages import ReportRequest
        from telethon.tl.types import ReportResultChooseOption, ReportResultAddComment, ReportResultReported

        client = await get_client(phone, ud)
        if not client:
            await bot.send_message(chat_id=user_id, text="❌  Account unavailable.", parse_mode=ParseMode.HTML)
            return

        success_count = 0
        fail_count = 0
        for i in range(count):
            try:
                await bot.send_message(chat_id=user_id,
                    text=f"📮  <b>Report {i+1}/{count}</b>\n━━━━━━━━━━━━━━━━━━\nInitiating...",
                    parse_mode=ParseMode.HTML)

                result = await client(ReportRequest(peer=entity, id=report_ids, option=b'', message=''))
                step = 0
                while not isinstance(result, ReportResultReported):
                    step += 1
                    if isinstance(result, ReportResultChooseOption):
                        option_titles = [o.text for o in result.options]
                        option_text = "\n".join(f"{i}. {t}" for i, t in enumerate(option_titles))
                        select_prompt = f"""You are selecting a Telegram report category. Available options:
{option_text}

Violations found in the target:
{violation_context}

Respond ONLY with the EXACT NUMBER (e.g. "3") of the best-matching option. If unsure, pick "Other"."""
                        selected_idx = None
                        for smodel in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]:
                            try:
                                sel_resp = groq_client.chat.completions.create(
                                    model=smodel,
                                    messages=[{"role": "user", "content": select_prompt}],
                                    temperature=0.1,
                                    max_tokens=50
                                )
                                sel_text = sel_resp.choices[0].message.content.strip()
                                selected_idx = int(''.join(c for c in sel_text if c.isdigit()))
                                if selected_idx < 0 or selected_idx >= len(result.options):
                                    selected_idx = None
                                break
                            except:
                                continue
                        if selected_idx is None:
                            selected_idx = len(result.options) - 1
                        chosen_option = result.options[selected_idx].option
                        await bot.send_message(chat_id=user_id,
                            text=f"📮  Report {i+1}: Selected <b>{result.options[selected_idx].text}</b>",
                            parse_mode=ParseMode.HTML)
                        result = await client(ReportRequest(peer=entity, id=report_ids, option=chosen_option, message=''))
                    elif isinstance(result, ReportResultAddComment):
                        comment_prompt = f"""Write a concise, professional report comment for Telegram moderation regarding the following violations found in a user/group/channel:

{violation_context}

The comment should:
- Be 1-2 sentences (max 300 chars)
- Clearly state the policy violations found
- Be factual and formal
- Include relevant Telegram ToS references

Write ONLY the comment text, no prefix or labels."""
                        comment_text = "Automated report: See attached violation details."
                        for cmodel in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]:
                            try:
                                cresp = groq_client.chat.completions.create(
                                    model=cmodel,
                                    messages=[{"role": "user", "content": comment_prompt}],
                                    temperature=0.3,
                                    max_tokens=400
                                )
                                comment_text = cresp.choices[0].message.content.strip()[:300]
                                break
                            except:
                                continue
                        result = await client(ReportRequest(peer=entity, id=report_ids, option=result.option, message=comment_text))
                    else:
                        break

                if isinstance(result, ReportResultReported):
                    success_count += 1
                    await bot.send_message(chat_id=user_id,
                        text=f"✅  Report {i+1}/{count} submitted!",
                        parse_mode=ParseMode.HTML)
                else:
                    fail_count += 1
                    await bot.send_message(chat_id=user_id,
                        text=f"⚠️  Report {i+1}/{count} completed but may not have been submitted.",
                        parse_mode=ParseMode.HTML)

                if i < count - 1:
                    delay = random.randint(lo, hi)
                    delay = int(delay * cpu_delay_factor(1.0, 3.0))
                    await bot.send_message(chat_id=user_id,
                        text=f"⏳  Waiting {delay}s before next report...",
                        parse_mode=ParseMode.HTML)
                    await asyncio.sleep(delay)

            except Exception as e:
                fail_count += 1
                await bot.send_message(chat_id=user_id,
                    text=f"❌  Report {i+1}/{count} failed: {str(e)[:100]}",
                    parse_mode=ParseMode.HTML)

        await bot.send_message(chat_id=user_id,
            text=f"🏁  <b>Bulk Report Complete</b>\n━━━━━━━━━━━━━━━━━━\n✅  Submitted: {success_count}\n❌  Failed: {fail_count}",
            parse_mode=ParseMode.HTML)

        b = ud.data.get("banning", {})
        b.setdefault("reports", []).append({
            "target": str(getattr(entity, 'title', getattr(entity, 'username', str(entity.id)))),
            "target_id": entity.id,
            "date": datetime.now().isoformat(),
            "submitted": True,
            "bulk_count": success_count,
            "messages_scanned": 0,
            "violations_found": 0,
        })
        ud.save()

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Bulk report error: {e}")
        try:
            await bot.send_message(chat_id=user_id, text=f"❌  Bulk report error: {str(e)[:200]}", parse_mode=ParseMode.HTML)
        except:
            pass
    finally:
        if client:
            await client.disconnect()
        if user_id in active_tasks:
            active_tasks[user_id].pop("banning", None)

# ═══════════════════════════════════════════════════════════════════
# BUTTON HANDLER
# ═══════════════════════════════════════════════════════════════════

async def button_handler(update, context):
    query = update.callback_query
    if not query: return
    uid = query.from_user.id if query.from_user else 0
    if not is_authorized(uid):
        logger.warning(f"Unauthorized user {uid} tried to use buttons")
        return
    try:
        await query.answer()
    except Exception as e:
        logger.debug(f"Could not answer query: {e}")

    user_id = uid
    ud = get_user_data(user_id)
    data = query.data

    try:
        # Navigation
        if data == "back_main":
            await query.edit_message_text("🏠  <b>MAIN MENU</b>\n━━━━━━━━━━━━━━━━━━\nPick a module:",
                parse_mode=ParseMode.HTML, reply_markup=main_menu())
            log_activity(user_id, "Navigated to main menu")
        elif data == "resume_all":
            await query.edit_message_text(
                "✅  Tasks left marked as running.\nOpen each module in the menu to resume.",
                parse_mode=ParseMode.HTML, reply_markup=main_menu())
            log_activity(user_id, "Resumed all tasks after restart")
        elif data == "resume_stop":
            for key in ("rej","scraper","scrap_girls","banning"):
                if key in ud.data and isinstance(ud.data[key], dict):
                    ud.data[key]["running"] = False
            for key in list(ud.data):
                if key.startswith("rej_"):
                    ud.data[key]["running"] = False
            ud.save()
            await query.edit_message_text(
                "⏸️  All tasks stopped.\nUse the menu to restart them manually.",
                parse_mode=ParseMode.HTML, reply_markup=main_menu())
            log_activity(user_id, "Stopped all tasks after restart")
        elif data == "menu_dashboard":
            await show_dashboard(update, context)
        elif data == "menu_logs":
            ud2 = get_user_data(user_id)
            await query.edit_message_text(menu_logs_text(ud2, user_id),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄  Refresh", callback_data="menu_logs"),
                     InlineKeyboardButton("📊  Dashboard", callback_data="menu_dashboard")],
                    [InlineKeyboardButton("🔙  Back", callback_data="back_main")]]))
            log_activity(user_id, "Viewed live logs")
        elif data == "menu_help":
            await show_help(update, context)
        elif data == "menu_settings":
            await query.edit_message_text("⚙️  <b>SETTINGS</b>\n━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML, reply_markup=settings_menu())
            log_activity(user_id, "Opened settings")

        # Features
        elif data == "menu_features":
            await query.edit_message_text("🧩  <b>FEATURES</b>\n━━━━━━━━━━━━━━━━━━\nExtra tools & utilities:",
                parse_mode=ParseMode.HTML, reply_markup=features_menu())
            log_activity(user_id, "Opened features menu")
        elif data == "scraper_help":
            await query.edit_message_text(
                "🧭  <b>SCRAPER STRUCTURE & FLOW</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "1. <b>Target & Delivery</b>\n"
                "   Set target (source) and delivery (destination)\n"
                "   groups. Both support public @username or\n"
                "   private <code>t.me/+...</code> invite links.\n\n"
                "2. <b>Dual Scrape Mode</b>\n"
                "   <b>Mode A — Member List:</b> If group shows\n"
                "   members, uses <code>GetParticipantsRequest</code>\n"
                "   (200 per page) with Batch Gap delay.\n\n"
                "   <b>Mode B — Message Scan:</b> If member list\n"
                "   hidden, scans recent messages for unique senders.\n"
                "   1 message = 1 user; duplicate users ignored.\n"
                "   Fails for a user? Skipped, moves to next.\n\n"
                "3. <b>Delivery to Group</b>\n"
                "   Each user is sent to delivery group one by one\n"
                "   with <b>User Gap</b> delay (configurable in\n"
                "   seconds or minutes like <code>2m</code>).\n"
                "   Failed users are skipped automatically.\n\n"
                "4. <b>Daily Limit</b>\n"
                "   Set max users per day. Resets at midnight.\n"
                "   <code>0</code> = unlimited.\n\n"
                "5. <b>Girls Scraper</b>\n"
                "   Scrapes from <b>multiple source groups</b>,\n"
                "   collects specified quantity.\n"
                "   <b>Name Filter</b> (toggle ON/OFF in menu):\n"
                "   Matches if first name ends with a feminine\n"
                "   suffix like <code>ika</code>, <code>ita</code>,\n"
                "   <code>ina</code>, <code>devi</code>, etc.\n\n"
                "6. <b>CPU Throttling</b>\n"
                "   Bot monitors <code>/proc/stat</code> CPU load:\n"
                "   • &lt;30% → full speed (delay ×1.0)\n"
                "   • 30-60% → scaled delay\n"
                "   • &gt;60% → max delay (×2.5)\n"
                "   Stale cache files auto-cleared on startup.\n\n"
                "7. <b>Resume on Restart</b>\n"
                "   If bot restarts, checks saved <code>user_data/*.json</code>\n"
                "   for tasks marked <code>running: true</code>\n"
                "   and asks you to resume or stop them.",
                parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="scraper_hub")]]))
        elif data == "scraper_hub":
            await query.edit_message_text(
                "🗂️  <b>SCRAPER HUB</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "Choose a scraper module:",
                parse_mode=ParseMode.HTML, reply_markup=scraper_hub_menu())
            log_activity(user_id, "Opened scraper hub")
        elif data == "scraper_dashboard":
            s = ud.data["scraper"]
            sg = ud.data["scrap_girls"]
            txt = (
                "📊  <b>SCRAPER DASHBOARD</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "👥  <b>Member Scraper</b>\n"
                f"  Status:   {'🟢  RUNNING' if s['running'] else '🔴  STOPPED'}\n"
                f"  Target:   {s['target'][:25] or 'Not set'}\n"
                f"  Scrape:   { {'all':'👥 All members','girls':'👩 Only girls','active':'🔥 Active'}.get(s.get('member_mode','all'),'All') }\n"
                f"  Source:   {s.get('source_used') or '—'}  •  found {s.get('found_total', 0)}\n"
                f"  Mode:     {'ADD' if s.get('mode','send')=='add' else 'SEND'}\n"
                f"  Scraped:  {s['scraped']}  (pending {len(s.get('pending', []))})\n"
                f"  Add:      ✅ {s.get('add_added',0)}  ❌ {s.get('add_failed',0)}  ⏭️ {s.get('add_skipped',0)}\n"
                f"  Accounts: {', '.join('…%s=%d' % (k,v) for k,v in (s.get('per_acc') or {}).items()) or '—'}\n"
                f"  Gap:      {s['gap']}s\n\n"
                "👩  <b>Girls Scraper</b>\n"
                f"  Status:   {'🟢  RUNNING' if sg['running'] else '🔴  STOPPED'}\n"
                f"  Qty:      {sg['qty']}\n"
                f"  Scraped:  {sg['scraped']}\n"
                f"  Sources:  {len(sg['sources'])}\n\n"
                "⚡  <b>CPU Throttle:</b>  {:d}%\n"
                "🗑️  <b>Cache:</b>  auto-cleaned on startup"
            ).format(int(cpu_load()))
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="scraper_hub")]]))
            log_activity(user_id, "Viewed scraper dashboard")
        elif data == "sg_sources":
            sg = ud.data["scrap_girls"]
            if sg["sources"]:
                srcs = "\n".join(f"• {s}" for s in sg["sources"])
                txt = f"📂  <b>SCRAP GIRLS SOURCES</b>\n━━━━━━━━━━━━━━━━━━\n{srcs}"
            else:
                txt = "📂  <b>SCRAP GIRLS SOURCES</b>\n━━━━━━━━━━━━━━━━━━\nNo sources added.\n\nSend group links (one per line) to add:"
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕  Add Sources", callback_data="sg_add_sources"),
                     InlineKeyboardButton("🗑️  Clear All", callback_data="sg_clear_sources")],
                    [InlineKeyboardButton("🔙  Back", callback_data="scraper_hub")]]))
            log_activity(user_id, "Viewed scrap girls sources")
        elif data == "sg_add_sources":
            await query.edit_message_text("📂  <b>ADD SOURCES</b>\n━━━━━━━━━━━━━━━━━━\nSend group links (one per line):",
                parse_mode=ParseMode.HTML)
            context.user_data["sg_sources"] = []
            context.user_data["_state"] = "sg_sources"
            return
        elif data == "sg_clear_sources":
            ud.data["scrap_girls"]["sources"] = []
            ud.save()
            await query.edit_message_text("🗑️  Sources cleared.", parse_mode=ParseMode.HTML,
                reply_markup=scrap_girls_menu(ud))
            log_activity(user_id, "Cleared scrap girls sources")
        elif data == "menu_scraper":
            s = ud.data["scraper"]
            status = "🟢  RUNNING" if s["running"] else "🔴  STOPPED"
            await query.edit_message_text(
                "👥  <b>MEMBER SCRAPER</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"Status:  {status}\n"
                f"🎯  Target:   {s['target'][:30] if s['target'] else 'Not set'}\n"
                f"📤  Delivery: {s['delivery'][:30] if s['delivery'] else 'Not set'}\n"
                f"🔀  Mode:     {'ADD to group' if s.get('mode','send')=='add' else 'SEND as message'}\n"
                f"👤  Scraped:  {s['scraped']}   📦 Pending: {len(s.get('pending', []))}\n"
                f"➕  Add task: {'🟢 RUNNING' if s.get('add_running') else '🔴 STOPPED'}\n"
                f"⏱️  Gap:      {s['gap']}s",
                parse_mode=ParseMode.HTML, reply_markup=scraper_menu(ud))
            log_activity(user_id, "Opened scraper menu")

        # Group Manager
        elif data == "menu_gm":
            gm = ud.data["gm"]
            gid = gm.get("group_id", 0)
            await query.edit_message_text(
                "⚙️  <b>GROUP MANAGER</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"🏷️  Group: {gm.get('group_title','Not set')[:30]}\n"
                f"🆔  ID: {gid if gid else 'Not set'}\n"
                f"👤  Notify: {'ON' if gm.get('notify',True) else 'OFF'}\n"
                f"📩  JoinReply: {'ON' if gm.get('join_reply',True) else 'OFF'}",
                parse_mode=ParseMode.HTML, reply_markup=gm_menu(ud))
            log_activity(user_id, "Opened group manager")
        elif data == "gm_set":
            await query.edit_message_text("🏷️  <b>SET GROUP</b>\n━━━━━━━━━━━━━━━━━━\nSend group ID or link:",
                parse_mode=ParseMode.HTML)
            log_activity(user_id, "Setting group")
            return GROUP_SET
        elif data.startswith("gm_app_") or data.startswith("gm_deny_"):
            parts = data.split("_")
            target = parts[2]
            act = "approve" if parts[0] == "gm" and parts[1] == "app" else "deny"
            if act == "approve":
                await query.edit_message_text(f"✅  Approved member {target}")
            else:
                await query.edit_message_text(f"❌  Denied member {target}")
            log_activity(user_id, f"Member {act}: {target}")
        elif data in ("gm_ban","gm_unban","gm_kick","gm_mute","gm_unmute","gm_promote","gm_demote","gm_pin"):
            context.user_data["gm_action"] = data.split("_")[1]
            await query.edit_message_text("👤  <b>ENTER USER</b>\n━━━━━━━━━━━━━━━━━━\nSend username or user ID:",
                parse_mode=ParseMode.HTML)
            return GROUP_USER_INPUT
        elif data == "gm_notify_toggle":
            ud.data["gm"]["notify"] = not ud.data["gm"].get("notify", True)
            ud.save()
            await query.edit_message_reply_markup(reply_markup=gm_menu(ud))
        elif data == "gm_joinreply_toggle":
            ud.data["gm"]["join_reply"] = not ud.data["gm"].get("join_reply", True)
            ud.save()
            await query.edit_message_reply_markup(reply_markup=gm_menu(ud))

        # GM Sub-menus
        elif data == "gm_admin":
            gm = ud.data["gm"]
            txt = ("🛠️  <b>ADMIN ACTIONS</b>\n━━━━━━━━━━━━━━━━━━\n\n"
                   f"🏷️  {gm.get('group_title','N/A')}\n"
                   f"🆔  {gm.get('group_id',0) or 'Not set'}")
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=gm_admin_menu())
            log_activity(user_id, "Opened GM admin")
        elif data == "gm_protection":
            gm = ud.data["gm"]
            txt = ("🛡️  <b>PROTECTION</b>\n━━━━━━━━━━━━━━━━━━\n\n"
                   "Configure filters, antiflood & warns:")
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=gm_protection_menu(ud))
            log_activity(user_id, "Opened GM protection")
        elif data == "gm_settings":
            gm = ud.data["gm"]
            txt = ("⚙️  <b>GROUP SETTINGS</b>\n━━━━━━━━━━━━━━━━━━\n\n"
                   f"🏷️  {gm.get('group_title','N/A')}\n"
                   f"🆔  {gm.get('group_id',0) or 'Not set'}")
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=gm_settings_menu(ud))
            log_activity(user_id, "Opened GM settings")
        elif data == "gm_welcome_toggle":
            ud.data["gm"]["welcome_enabled"] = not ud.data["gm"].get("welcome_enabled", False)
            ud.save()
            await query.edit_message_reply_markup(reply_markup=gm_settings_menu(ud))
        elif data == "gm_set_welcome":
            await query.edit_message_text("👋  <b>SET WELCOME TEXT</b>\n━━━━━━━━━━━━━━━━━━\nSend welcome text.\nUse <code>{name}</code> for user name, <code>{title}</code> for group title:",
                parse_mode=ParseMode.HTML)
            return GM_WELCOME
        elif data == "gm_rules_toggle":
            ud.data["gm"]["rules_enabled"] = not ud.data["gm"].get("rules_enabled", False)
            ud.save()
            await query.edit_message_reply_markup(reply_markup=gm_settings_menu(ud))
        elif data == "gm_set_rules":
            await query.edit_message_text("📜  <b>SET RULES</b>\n━━━━━━━━━━━━━━━━━━\nSend the group rules text:",
                parse_mode=ParseMode.HTML)
            return GM_RULES
        elif data == "gm_filters":
            gm = ud.data["gm"]
            fl = gm.get("filters", [])
            if not fl:
                txt = "🚫  <b>FILTERS</b>\n━━━━━━━━━━━━━━━━━━\nNo blocked words yet."
            else:
                lines = [f"<b>{i+1}.</b> <code>{w}</code>" for i, w in enumerate(fl)]
                txt = "🚫  <b>FILTERS</b>\n━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(lines)
            btns = []
            for i, w in enumerate(fl):
                btns.append([InlineKeyboardButton(f"❌  {w}", callback_data=f"gm_filter_rm_{i}")])
            btns.append([InlineKeyboardButton("➕  Add Word", callback_data="gm_filter_add")])
            btns.append([InlineKeyboardButton("🔙  Back", callback_data="gm_protection")])
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns))
            log_activity(user_id, "Opened GM filters")
        elif data == "gm_filter_add":
            await query.edit_message_text("➕  <b>ADD FILTER WORD</b>\n━━━━━━━━━━━━━━━━━━\nSend the word to block:",
                parse_mode=ParseMode.HTML)
            return GM_FILTER
        elif data.startswith("gm_filter_rm_"):
            idx = int(data.split("_")[3])
            fl = ud.data.get("gm", {}).get("filters", [])
            if 0 <= idx < len(fl):
                removed = fl.pop(idx)
                ud.save()
                log_activity(user_id, f"Removed filter word: {removed}")
            txt, kb = render_filter_words(ud)
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        elif data == "gm_af_toggle":
            gm = ud.data["gm"]
            if gm.get("antiflood", {}):
                gm["antiflood"] = {}
            else:
                gm["antiflood"] = {"enabled": True}
            ud.save()
            await query.edit_message_reply_markup(reply_markup=gm_protection_menu(ud))
        elif data == "gm_af_msgs":
            await query.edit_message_text("📊  <b>SET ANTIFLOOD MSGS</b>\n━━━━━━━━━━━━━━━━━━\nEnter max messages allowed:",
                parse_mode=ParseMode.HTML)
            return GM_AF_MSGS
        elif data == "gm_af_int":
            await query.edit_message_text("⏱️  <b>SET ANTIFLOOD INTERVAL</b>\n━━━━━━━━━━━━━━━━━━\nEnter interval in seconds:",
                parse_mode=ParseMode.HTML)
            return GM_AF_INT
        elif data == "gm_warn_set":
            await query.edit_message_text("⚠️  <b>SET WARN MAX</b>\n━━━━━━━━━━━━━━━━━━\nEnter maximum warnings before action:",
                parse_mode=ParseMode.HTML)
            return GM_WARN_SET
        elif data == "gm_media_toggle":
            ud.data["gm"]["media_filter"] = not ud.data["gm"].get("media_filter", False)
            ud.save()
            await query.edit_message_reply_markup(reply_markup=gm_protection_menu(ud))
        elif data == "gm_link_toggle":
            ud.data["gm"]["link_filter"] = not ud.data["gm"].get("link_filter", False)
            ud.save()
            await query.edit_message_reply_markup(reply_markup=gm_protection_menu(ud))
        elif data == "gm_bio_toggle":
            ud.data["gm"]["bio_filter"] = not ud.data["gm"].get("bio_filter", False)
            ud.save()
            await query.edit_message_reply_markup(reply_markup=gm_protection_menu(ud))
        elif data == "gm_info":
            await query.edit_message_text("ℹ️  <b>FETCHING GROUP INFO...</b>\n━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML)
            gm = ud.data["gm"]
            gid = gm.get("group_id", 0)
            if not gid:
                await query.edit_message_text("❌  No group set.", parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="gm_settings")]]))
            else:
                phone = get_gm_client(ud)
                if not phone:
                    await query.edit_message_text("❌  No active account.", parse_mode=ParseMode.HTML)
                else:
                    client = await get_client(phone, ud)
                    if not client:
                        await query.edit_message_text("❌  Account unavailable.", parse_mode=ParseMode.HTML)
                    else:
                        try:
                            from telethon.tl.functions.channels import GetFullChannelRequest
                            entity = await client.get_entity(int(gid))
                            full = await client(GetFullChannelRequest(entity.id))
                            members = getattr(full.full_chat, 'participants_count', 'N/A')
                            txt = ("ℹ️  <b>GROUP INFO</b>\n━━━━━━━━━━━━━━━━━━\n\n"
                                   f"🏷️  Title: {getattr(entity, 'title', 'N/A')}\n"
                                   f"🆔  ID: {entity.id}\n"
                                   f"👥  Members: {members}\n"
                                   f"🔗  Link: {getattr(entity, 'username', 'Private') or 'Private'}")
                            await query.edit_message_text(txt, parse_mode=ParseMode.HTML,
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="gm_settings")]]))
                        except Exception as e:
                            await query.edit_message_text(f"❌  Error: {str(e)[:80]}", parse_mode=ParseMode.HTML)
                        finally:
                            await client.disconnect()
            log_activity(user_id, "Viewed GM group info")
        elif data == "gm_invite":
            await query.edit_message_text("🔗  <b>GENERATING INVITE LINK...</b>\n━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML)
            gm = ud.data["gm"]
            gid = gm.get("group_id", 0)
            if not gid:
                await query.edit_message_text("❌  No group set.", parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="gm_settings")]]))
            else:
                phone = get_gm_client(ud)
                if not phone:
                    await query.edit_message_text("❌  No active account.", parse_mode=ParseMode.HTML)
                else:
                    client = await get_client(phone, ud)
                    if not client:
                        await query.edit_message_text("❌  Account unavailable.", parse_mode=ParseMode.HTML)
                    else:
                        try:
                            from telethon.tl.functions.messages import ExportChatInviteRequest
                            entity = await client.get_entity(int(gid))
                            invite = await client(ExportChatInviteRequest(entity.id))
                            link = getattr(invite, 'link', 'N/A')
                            await query.edit_message_text(f"🔗  <b>INVITE LINK</b>\n━━━━━━━━━━━━━━━━━━\n\n{link}",
                                parse_mode=ParseMode.HTML,
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="gm_settings")]]))
                        except Exception as e:
                            await query.edit_message_text(f"❌  Error: {str(e)[:80]}", parse_mode=ParseMode.HTML)
                        finally:
                            await client.disconnect()
            log_activity(user_id, "Generated GM invite link")
        elif data == "gm_banlist":
            gm = ud.data["gm"]
            gid = gm.get("group_id", 0)
            if not gid:
                await query.edit_message_text("❌  No group set.", parse_mode=ParseMode.HTML)
            else:
                phone = get_gm_client(ud)
                if not phone:
                    await query.edit_message_text("❌  No active account.", parse_mode=ParseMode.HTML)
                else:
                    client = await get_client(phone, ud)
                    if not client:
                        await query.edit_message_text("❌  Account unavailable.", parse_mode=ParseMode.HTML)
                    else:
                        try:
                            from telethon.tl.functions.channels import GetParticipantsRequest
                            from telethon.tl.types import ChannelParticipantsBanned
                            entity = await client.get_entity(int(gid))
                            banned = await client(GetParticipantsRequest(entity, ChannelParticipantsBanned(''), 0, 200))
                            if not banned.users:
                                await query.edit_message_text("🚫  <b>No banned users.</b>", parse_mode=ParseMode.HTML,
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="gm_admin")]]))
                            else:
                                btns = []
                                for i, u in enumerate(banned.users[:20]):
                                    name = f"{u.first_name or ''} {u.last_name or ''}".strip() or str(u.id)
                                    btns.append([InlineKeyboardButton(f"✅  Unban {name[:20]}", callback_data=f"gm_unban_{u.id}")])
                                btns.append([InlineKeyboardButton("🔙  Back", callback_data="gm_admin")])
                                txt = f"🚫  <b>BANNED USERS</b>\n━━━━━━━━━━━━━━━━━━\n\nTotal: {len(banned.users)}"
                                await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns))
                        except Exception as e:
                            await query.edit_message_text(f"❌  Error: {str(e)[:80]}", parse_mode=ParseMode.HTML)
                        finally:
                            await client.disconnect()
            log_activity(user_id, "Viewed GM banlist")
        elif data.startswith("gm_unban_"):
            target_id = int(data.split("_")[2])
            gm = ud.data["gm"]
            gid = gm.get("group_id", 0)
            if not gid:
                await query.edit_message_text("❌  No group set.", parse_mode=ParseMode.HTML)
            else:
                phone = get_gm_client(ud)
                if not phone:
                    await query.edit_message_text("❌  No active account.", parse_mode=ParseMode.HTML)
                else:
                    client = await get_client(phone, ud)
                    if not client:
                        await query.edit_message_text("❌  Account unavailable.", parse_mode=ParseMode.HTML)
                    else:
                        try:
                            from telethon.tl.functions.channels import EditBannedRequest
                            from telethon.tl.types import ChatBannedRights
                            entity = await client.get_entity(int(gid))
                            rights = ChatBannedRights(until_date=None, view_messages=False, send_messages=False)
                            await client(EditBannedRequest(entity, target_id, rights))
                            await query.edit_message_text(f"✅  Unbanned user {target_id}", parse_mode=ParseMode.HTML,
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="gm_admin")]]))
                        except Exception as e:
                            await query.edit_message_text(f"❌  Error: {str(e)[:80]}", parse_mode=ParseMode.HTML)
                        finally:
                            await client.disconnect()
            log_activity(user_id, f"Unbanned user {target_id} from banlist")

        # Scrap Girls
        elif data == "menu_scrap_girls":
            sg = ud.data["scrap_girls"]
            status = "🟢  RUNNING" if sg["running"] else "🔴  STOPPED"
            await query.edit_message_text(
                "👩  <b>SCRAP GIRLS</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"Status:  {status}\n"
                f"👤  Qty:     {sg['qty']}\n"
                f"⏱️  Delay:   {sg['delay']}s\n"
                f"✅  Scraped: {sg['scraped']}\n"
                f"📂  Sources: {len(sg['sources'])}",
                parse_mode=ParseMode.HTML, reply_markup=scrap_girls_menu(ud))
            log_activity(user_id, "Opened scrap girls menu")
        elif data == "sg_toggle":
            sg = ud.data["scrap_girls"]
            if sg["running"]:
                sg["running"] = False; ud.save()
                for k in list(active_tasks.get(user_id, {})):
                    if k == "scrap_girls": active_tasks[user_id].pop(k).cancel()
                log_activity(user_id, "Scrap Girls STOPPED")
                await query.edit_message_text("⏹️  <b>SCRAP GIRLS STOPPED</b>",
                    parse_mode=ParseMode.HTML, reply_markup=scrap_girls_menu(ud))
            else:
                accs = [p for p in ud.data["acc"] if ud.data["acc"][p].get("active", True)]
                if not accs:
                    await query.edit_message_text("❌  No active accounts.", parse_mode=ParseMode.HTML)
                elif not sg["sources"]:
                    await query.edit_message_text("❌  Add source groups first.\nSend group links (one per line):",
                        parse_mode=ParseMode.HTML)
                    context.user_data["sg_sources"] = []
                    context.user_data["_state"] = "sg_sources"
                    return
                else:
                    sg["running"] = True; sg["scraped"] = 0; ud.save()
                    for k in list(active_tasks.get(user_id, {})):
                        if k == "scrap_girls": active_tasks[user_id].pop(k).cancel()
                    active_tasks.setdefault(user_id, {})
                    active_tasks[user_id]["scrap_girls"] = asyncio.create_task(
                        scrap_girls_task(user_id, accs[0], context.bot))
                    log_activity(user_id, "Scrap Girls STARTED")
                    await query.edit_message_text("✅  <b>SCRAP GIRLS STARTED</b>\n━━━━━━━━━━━━━━━━━━\nScraping in progress...",
                        parse_mode=ParseMode.HTML, reply_markup=scrap_girls_menu(ud))
        elif data == "sg_stats":
            sg = ud.data["scrap_girls"]
            nf = "ON" if sg.get("name_filter", True) else "OFF"
            txt = ("📊  <b>SCRAP GIRLS STATS</b>\n━━━━━━━━━━━━━━━━━━\n\n"
                   f"👤  Qty:     {sg['qty']}\n⏱️  Delay:   {sg['delay']}s\n"
                   f"✅  Scraped: {sg['scraped']}\n"
                   f"📂  Sources: {len(sg['sources'])}\n"
                   f"👩  Filter:  {nf}\n"
                   f"🔄  Status:  {'🟢  RUNNING' if sg['running'] else '🔴  STOPPED'}")
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="menu_scrap_girls")]]))
            log_activity(user_id, "Viewed scrap girls stats")
        elif data == "sg_set_qty":
            await query.edit_message_text("👤  <b>SET QUANTITY</b>\n━━━━━━━━━━━━━━━━━━\nEnter number of members to scrape:",
                parse_mode=ParseMode.HTML)
            return SCRAP_GIRLS_QTY
        elif data == "sg_set_delay":
            await query.edit_message_text("⏱️  <b>SET DELAY</b>\n━━━━━━━━━━━━━━━━━━\nEnter delay in seconds between scrapes:",
                parse_mode=ParseMode.HTML)
            return SCRAP_GIRLS_DELAY
        elif data == "sg_filter_toggle":
            ud.data["scrap_girls"]["name_filter"] = not ud.data["scrap_girls"].get("name_filter", True)
            ud.save()
            log_activity(user_id, f"NameFilter toggled: {ud.data['scrap_girls']['name_filter']}")
            await query.edit_message_reply_markup(reply_markup=scrap_girls_menu(ud))

        # Banning
        elif data == "menu_banning":
            await query.edit_message_text(
                "🚨  <b>AI BANNING SYSTEM</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "Analyze groups/users/channels for policy violations using AI.",
                parse_mode=ParseMode.HTML, reply_markup=banning_menu(ud))
            log_activity(user_id, "Opened banning menu")
        elif data == "ban_set_target":
            await query.edit_message_text("🎯  <b>SET TARGET</b>\n━━━━━━━━━━━━━━━━━━\nSend group link, username, or user ID:",
                parse_mode=ParseMode.HTML)
            return BAN_TARGET
        elif data == "ban_set_groq":
            await query.edit_message_text("🔑  <b>GROQ API KEY</b>\n━━━━━━━━━━━━━━━━━━\nEnter your Groq API key:\n\nGet one at: https://console.groq.com",
                parse_mode=ParseMode.HTML)
            return BAN_GROQ
        elif data == "ban_start":
            b = ud.data["banning"]
            if not b.get("groq_api"):
                await query.edit_message_text("❌  Set Groq API key first.", parse_mode=ParseMode.HTML)
            elif not b.get("target"):
                await query.edit_message_text("❌  Set a target first.", parse_mode=ParseMode.HTML)
            elif b.get("running"):
                await query.edit_message_text("⏳  Already running.", parse_mode=ParseMode.HTML)
            else:
                await query.edit_message_text(
                    "📄  <b>SCAN MESSAGES</b>\n━━━━━━━━━━━━━━━━━━\n"
                    "Enter number of messages to scan (e.g. 200) or type <b>all</b> for all messages:",
                    parse_mode=ParseMode.HTML)
                return BAN_SCAN_COUNT
        elif data == "ban_scan_count":
            await query.edit_message_text(
                "📄  <b>SET SCAN COUNT</b>\n━━━━━━━━━━━━━━━━━━\n"
                "Enter number of messages to scan (e.g. 200) or type <b>all</b> for all messages:",
                parse_mode=ParseMode.HTML)
            return BAN_SCAN_COUNT
        elif data == "ban_status":
            b = ud.data["banning"]
            txt = ("📊  <b>BANNING STATUS</b>\n━━━━━━━━━━━━━━━━━━\n\n"
                   f"🎯  Target:  {b['target'][:30] if b['target'] else 'Not set'}\n"
                   f"🔑  Groq:    {'✅ Set' if b.get('groq_api') else '❌ Not set'}\n"
                   f"📄  Msgs:    {b.get('msg_limit', 5000)}\n"
                   f"🔄  Status:  {'🟢 Running' if b.get('running') else '🔴 Idle'}\n"
                   f"📋  Reports: {len(b.get('reports',[]))}")
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="menu_banning")]]))
        elif data == "ban_stop":
            b = ud.data["banning"]
            b["running"] = False; ud.save()
            if user_id in active_tasks and "banning" in active_tasks[user_id]:
                active_tasks[user_id].pop("banning").cancel()
            await query.edit_message_text("⏹️  <b>Review Stopped</b>\n━━━━━━━━━━━━━━━━━━\nBanning review cancelled.",
                parse_mode=ParseMode.HTML, reply_markup=banning_menu(ud))
            log_activity(user_id, "Stopped banning review")

        # Accounts
        elif data == "add_account":
            await query.edit_message_text("📱  <b>ADD ACCOUNT</b>\n━━━━━━━━━━━━━━━━━━\nSend phone number in international format:\n\n<code>+1234567890</code>",
                parse_mode=ParseMode.HTML)
            log_activity(user_id, "Started add account flow")
            return PHONE
        elif data == "menu_accounts":
            await query.edit_message_text("👤  <b>ACCOUNTS</b>\n━━━━━━━━━━━━━━━━━━\nManage your Telegram accounts:",
                parse_mode=ParseMode.HTML, reply_markup=accounts_menu(ud))
            log_activity(user_id, "Opened accounts manager")
        elif data.startswith("rem_acc_"):
            phone = data[8:]
            if phone in ud.data["acc"]:
                del ud.data["acc"][phone]
                ud.save()
                logger.info(f"Removed account {phone} for user {user_id}")
                log_activity(user_id, f"Deleted account {phone}")
            await query.edit_message_text("👤  <b>ACCOUNTS</b>\n━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML, reply_markup=accounts_menu(ud))
        elif data.startswith("toggle_acc_"):
            phone = data[11:]
            if phone in ud.data["acc"]:
                cur = ud.data["acc"][phone].get("active", True)
                ud.data["acc"][phone]["active"] = not cur
                ud.save()
                status = "🟢 enabled" if not cur else "🔴 disabled"
                log_activity(user_id, f"Account {phone} toggled: {status}")
            await query.edit_message_text("👤  <b>ACCOUNTS</b>\n━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML, reply_markup=accounts_menu(ud))

        # Name/Bio/Pfp
        elif data == "set_name":
            await query.edit_message_text("✏️  <b>SET NAME</b>\n━━━━━━━━━━━━━━━━━━\nSend new display name:\n\n<code>FirstName LastName</code>",
                parse_mode=ParseMode.HTML)
            context.user_data["_auto_state"] = "name"
            return SET_NAME
        elif data == "set_bio":
            await query.edit_message_text("📝  <b>SET BIO</b>\n━━━━━━━━━━━━━━━━━━\nSend new bio text:",
                parse_mode=ParseMode.HTML)
            context.user_data["_auto_state"] = "bio"
            return SET_BIO
        elif data == "set_pfp":
            await query.edit_message_text("🖼️  <b>SET PROFILE PICTURE</b>\n━━━━━━━━━━━━━━━━━━\nSend a photo to apply across all accounts:",
                parse_mode=ParseMode.HTML)
            context.user_data["_auto_state"] = "pfp"
            return SET_PFP

        # Rejoin
        elif data == "menu_rejoin":
            r = ud.data["rej"]
            await query.edit_message_text(
                "🔄  <b>REJOIN ENGINE</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"Status:  {'🟢  RUNNING' if rejoin_live(user_id, ud) else ('🟡  INTERRUPTED' if r.get('running') else '🔴  STOPPED')}\n"
                f"✅  Joined: {r['joined_count']}          ↩️  Left: {r['left_count']}\n"
                f"⚠️  Failed: {r.get('failed_count', 0)}          🚫  Blocked: {len(r['blacklist'])}\n"
                f"📋  Groups: {len(r['approved'])}          🔄  Cycles: {'∞' if r['cycles']==0 else r['cycles']}\n"
                f"💓 Last activity: {r.get('last_heartbeat') or '—'}\n"
                + (f"⚠️  Error: <code>{html.escape(str(r['last_error'])[:120])}</code>" if r.get('last_error') else ""),
                parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
            log_activity(user_id, "Opened rejoin menu")
        elif data == "rejoin_toggle":
            rej = ud.data["rej"]
            live = rejoin_live(user_id, ud)
            if live:
                rej["running"] = False
                ud.save()
                for key in list(active_tasks.get(user_id, {})):
                    if key.startswith("rej"):
                        active_tasks[user_id].pop(key).cancel()
                log_activity(user_id, "Rejoin STOPPED")
                await notify_owner(context.bot,
                    "⏹️ <b>REJOIN STOPPED</b>\n👤 user: <code>%s</code>\n"
                    "📊 joined %d  •  left %d  •  failed %d"
                    % (user_id, rej.get("joined_count", 0), rej.get("left_count", 0),
                       rej.get("failed_count", 0)))
                await query.edit_message_text("⏹️  <b>REJOIN STOPPED</b>\n━━━━━━━━━━━━━━━━━━\nAll tasks cancelled.",
                    parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
            else:
                rej["running"] = False
                rej["last_error"] = ""
                accs = [p for p in ud.data["acc"] if ud.data["acc"][p].get("active", True)]
                if not accs:
                    await query.edit_message_text("❌  <b>No Active Accounts</b>\n━━━━━━━━━━━━━━━━━━\nAdd & activate an account first.",
                        parse_mode=ParseMode.HTML)
                elif not rej["approved"]:
                    await query.edit_message_text("❌  <b>No Group Links</b>\n━━━━━━━━━━━━━━━━━━\nAdd group links and approve them first.",
                        parse_mode=ParseMode.HTML)
                else:
                    rej["running"] = True
                    ud.save()
                    for key in list(active_tasks.get(user_id, {})):
                        if key.startswith("rej"):
                            active_tasks[user_id].pop(key).cancel()
                    if rej.get("use_all_acc") and len(accs) > 1:
                        groups = list(rej["approved"])
                        for i, acc in enumerate(accs):
                            tid = f"rej_{acc}"
                            active_tasks.setdefault(user_id, {})
                            active_tasks[user_id][tid] = asyncio.create_task(
                                rejoin_cycle_task(user_id, acc, context.bot,
                                                  groups_override=list(groups),
                                                  slot=i, total=len(accs)))
                        log_activity(user_id, f"Rejoin STARTED - {len(accs)} accounts, {len(groups)} groups, full coverage")
                        await notify_owner(context.bot,
                            "▶️ <b>REJOIN STARTED</b>\n👤 user: <code>%s</code>\n"
                            "👥 accounts: %d (parallel)\n📋 groups: %d (full coverage each)\n"
                            "🎲 shuffle: every cycle\n⏱️ gap: %s  •  cycles: %s"
                            % (user_id, len(accs), len(groups), format_gap(rej["gap"]),
                               "∞" if rej["cycles"] == 0 else rej["cycles"]))
                        await query.edit_message_text(
                            "✅  <b>REJOIN STARTED</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n\n"
                            f"👥  Accounts: {len(accs)}  (parallel, staggered)\n"
                            f"📋  Groups/account: all {len(groups)}  (full coverage)\n"
                            f"🎲  Order: shuffled every cycle\n"
                            f"⏱️  Gap: {format_gap(rej['gap'])}",
                            parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
                    else:
                        active_tasks.setdefault(user_id, {})
                        active_tasks[user_id]["rej"] = asyncio.create_task(
                            rejoin_cycle_task(user_id, accs[0], context.bot))
                        log_activity(user_id, f"Rejoin STARTED - Account: {accs[0][:7]}")
                        await notify_owner(context.bot,
                            "▶️ <b>REJOIN STARTED</b>\n👤 user: <code>%s</code>\n"
                            "👤 account: <code>…%s</code>\n📋 groups: %d\n"
                            "🎲 shuffle: every cycle\n⏱️ gap: %s  •  cycles: %s"
                            % (user_id, accs[0][-4:], len(rej["approved"]),
                               format_gap(rej["gap"]),
                               "∞" if rej["cycles"] == 0 else rej["cycles"]))
                        await query.edit_message_text(
                            "✅  <b>REJOIN STARTED</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n\n"
                            f"👤  Account: {accs[0][:7]}...\n"
                            f"📋  Groups: {len(rej['approved'])}\n"
                            f"⏱️  Gap: {format_gap(rej['gap'])}",
                            parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
        elif data == "rejoin_send_links":
            await query.edit_message_text("🔗  <b>ADD LINKS</b>\n━━━━━━━━━━━━━━━━━━\nSend Telegram links (one per line):\n\n<code>t.me/groupname</code>\n<code>https://t.me/+xyz</code>",
                parse_mode=ParseMode.HTML)
            log_activity(user_id, "Sending rejoin links")
            return SEND_LINKS
        elif data == "rejoin_delete_links":
            ud.data["rej"]["approved"] = []
            ud.data["rej"]["denied"] = []
            ud.data["rej"]["blacklist"] = []
            ud.save()
            log_activity(user_id, "Cleared all rejoin links")
            await query.edit_message_text("🗑️  <b>All Links Cleared</b>\n━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
        elif data == "rejoin_export":
            approved = ud.data["rej"]["approved"]
            if not approved:
                await query.edit_message_text("❌  No approved links to export.",
                    parse_mode=ParseMode.HTML)
            else:
                lines = [f"{i+1}. {link}" for i, link in enumerate(approved)]
                content = "\n".join(lines)
                with open("gclinks.txt", "w") as f:
                    f.write(content)
                with open("gclinks.txt", "rb") as f:
                    await context.bot.send_document(
                        chat_id=user_id,
                        document=f,
                        filename="gclinks.txt",
                        caption=f"📋  Approved Links  ({len(approved)} total)",
                        parse_mode=ParseMode.HTML)
                await query.edit_message_text("📄  <b>Exported!</b>\n━━━━━━━━━━━━━━━━━━\nCheck file above.",
                    parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
        elif data == "rejoin_import_file":
            await query.edit_message_text("📂  <b>IMPORT LINKS</b>\n━━━━━━━━━━━━━━━━━━\nUpload a <code>.txt</code> file with links (one per line).",
                parse_mode=ParseMode.HTML)
            context.user_data['_state'] = WAIT_FILE
            log_activity(user_id, "Waiting for import file")
            return WAIT_FILE
        elif data == "rejoin_blacklist":
            bl = ud.data["rej"]["blacklist"]
            if not bl:
                await query.edit_message_text("🚫  <b>Blacklist is empty.</b>",
                    parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
            else:
                page = context.user_data.get("bl_page", 0)
                txt, kb = render_blacklist_page(ud, page)
                await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        elif data == "bl_page_prev":
            context.user_data["bl_page"] = max(0, context.user_data.get("bl_page", 0) - 1)
            txt, kb = render_blacklist_page(ud, context.user_data["bl_page"])
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        elif data == "bl_page_next":
            context.user_data["bl_page"] = context.user_data.get("bl_page", 0) + 1
            txt, kb = render_blacklist_page(ud, context.user_data["bl_page"])
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        elif data.startswith("bl_remove_"):
            idx = int(data.split("_")[2])
            bl = ud.data["rej"]["blacklist"]
            if 0 <= idx < len(bl):
                removed = bl.pop(idx)
                ud.save()
                log_activity(user_id, f"Removed from blacklist: {removed[:50]}")
            context.user_data["bl_page"] = 0
            if not bl:
                await query.edit_message_text("🚫  <b>Blacklist is now empty.</b>",
                    parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
            else:
                txt, kb = render_blacklist_page(ud, 0)
                await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        elif data == "rejoin_priority_toggle":
            ud.data["rej"]["priority"] = not ud.data["rej"].get("priority", False)
            ud.save()
            log_activity(user_id, f"Priority toggled: {ud.data['rej']['priority']}")
            await query.edit_message_reply_markup(reply_markup=rejoin_menu(ud))
        elif data == "rej_stats":
            r = ud.data["rej"]
            txt = (
                "📊  <b>REJOIN STATS</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"✅  Joined:     {r['joined_count']}\n"
                f"↩️  Left:       {r['left_count']}\n"
                f"⚠️  Failed:     {r.get('failed_count', 0)}\n"
                f"📋  Approved:   {len(r['approved'])}\n"
                f"🚫  Blacklist:  {len(r['blacklist'])}\n"
                f"⏱️  Gap:        {format_gap(r['gap'])}\n"
                f"🔄  Cycles:     {'∞' if r['cycles']==0 else r['cycles']}\n"
                f"🕒  Last cycle: {r.get('last_cycle_at', '—')}"
            )
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="back_main")]]))
            log_activity(user_id, "Viewed rejoin stats")
        elif data == "rejoin_safe_toggle":
            ud.data["rej"]["safe_mode"] = not ud.data["rej"]["safe_mode"]
            ud.save()
            status = "ON" if ud.data["rej"]["safe_mode"] else "OFF"
            log_activity(user_id, f"Safe mode: {status}")
            await query.edit_message_reply_markup(reply_markup=rejoin_menu(ud))
        elif data == "rejoin_use_all_toggle":
            ud.data["rej"]["use_all_acc"] = not ud.data["rej"].get("use_all_acc", False)
            ud.save()
            log_activity(user_id, f"Use all acc toggled: {ud.data['rej']['use_all_acc']}")
            await query.edit_message_reply_markup(reply_markup=rejoin_menu(ud))
        elif data == "rejoin_autoapp_toggle":
            ud.data["rej"]["auto_approve"] = not ud.data["rej"].get("auto_approve", False)
            ud.save()
            status = "ON" if ud.data["rej"]["auto_approve"] else "OFF"
            log_activity(user_id, f"Auto-Approve: {status}")
            await query.edit_message_reply_markup(reply_markup=rejoin_menu(ud))
        elif data == "rejoin_disc_toggle":
            ud.data["rej"]["include_discussions"] = not ud.data["rej"].get("include_discussions", True)
            ud.save()
            status = "ON" if ud.data["rej"]["include_discussions"] else "OFF"
            log_activity(user_id, f"Discussions: {status}")
            await query.edit_message_reply_markup(reply_markup=rejoin_menu(ud))
        elif data == "rejoin_set_gap":
            await query.edit_message_text("⏱️  <b>SET GAP</b>\n━━━━━━━━━━━━━━━━━━\nEnter delay between actions:\n\n<code>30s</code>  <code>5m</code>  <code>1h</code>",
                parse_mode=ParseMode.HTML)
            log_activity(user_id, "Setting rejoin gap")
            return CUSTOM_GAP
        elif data == "rejoin_set_cycles":
            await query.edit_message_text("🔄  <b>SET CYCLES</b>\n━━━━━━━━━━━━━━━━━━\nEnter number of cycles (0 = infinite):",
                parse_mode=ParseMode.HTML)
            log_activity(user_id, "Setting rejoin cycles")
            return CUSTOM_CYCLES

        # Scraper
        elif data == "scraper_toggle":
            s = ud.data["scraper"]
            if s["running"]:
                s["running"] = False
                s["add_running"] = False
                ud.save()
                for key in list(active_tasks.get(user_id, {})):
                    if key in ("scraper", "scrap_add"):
                        active_tasks[user_id].pop(key).cancel()
                log_activity(user_id, "Scraper STOPPED")
                await notify_owner(context.bot,
                    "⏹️ <b>SCRAPER STOPPED</b>\n👤 user: <code>%s</code>\n"
                    "👥 scraped: %d  •  pending: %d"
                    % (user_id, s.get("scraped", 0), len(s.get("pending", []))))
                await query.edit_message_text("⏹️  <b>SCRAPER STOPPED</b>\n━━━━━━━━━━━━━━━━━━",
                    parse_mode=ParseMode.HTML, reply_markup=scraper_menu(ud))
            else:
                accs = [p for p in ud.data["acc"] if ud.data["acc"][p].get("active", True)]
                if not accs:
                    await query.edit_message_text("❌  <b>No Active Accounts</b>\n━━━━━━━━━━━━━━━━━━\nAdd & activate an account first.",
                        parse_mode=ParseMode.HTML)
                elif not s["target"] or not s["delivery"]:
                    await query.edit_message_text("❌  <b>Set Target & Delivery groups first.</b>",
                        parse_mode=ParseMode.HTML)
                else:
                    s["running"] = True
                    s["scraped"] = 0
                    ud.save()
                    for key in list(active_tasks.get(user_id, {})):
                        if key == "scraper":
                            active_tasks[user_id].pop(key).cancel()
                    active_tasks.setdefault(user_id, {})
                    active_tasks[user_id]["scraper"] = asyncio.create_task(
                        scraper_task(user_id, accs[0], context.bot))
                    log_activity(user_id, f"Scraper STARTED - {s['target'][:30]}")
                    await notify_owner(context.bot,
                        "▶️ <b>SCRAPER STARTED</b>\n👤 user: <code>%s</code>\n"
                        "🎯 target: <code>%s</code>\n📤 delivery: <code>%s</code>\n"
                        "🔀 mode: %s  •  ⏱️ gap: %ds"
                        % (user_id, html.escape(s["target"][:45]),
                           html.escape(s["delivery"][:45]),
                           "ADD" if s.get("mode", "send") == "add" else "SEND",
                           int(s["gap"])))
                    await query.edit_message_text(
                        "✅  <b>SCRAPER STARTED</b>\n"
                        "━━━━━━━━━━━━━━━━━━\n\n"
                        f"🎯  Target:   {s['target'][:30]}\n"
                        f"📤  Delivery: {s['delivery'][:30]}\n"
                        f"🔎  Scrape:   { {'all':'👥 All members','girls':'👩 Only girls','active':'🔥 Active'}.get(s.get('member_mode','all'),'All') }\n"
                        f"🔀  Mode:     {'ADD' if s.get('mode','send')=='add' else 'SEND'}\n"
                        f"⏱️  Gap:      {s['gap']}s",
                        parse_mode=ParseMode.HTML, reply_markup=scraper_menu(ud))
        elif data == "scraper_target":
            await query.edit_message_text("🎯  <b>SET TARGET GROUP</b>\n━━━━━━━━━━━━━━━━━━\nSend group link or username:",
                parse_mode=ParseMode.HTML)
            log_activity(user_id, "Setting scraper target")
            return SCRAP_TARGET
        elif data == "scraper_delivery":
            await query.edit_message_text("📤  <b>SET DELIVERY GROUP</b>\n━━━━━━━━━━━━━━━━━━\nSend group link where scraped data will be sent:",
                parse_mode=ParseMode.HTML)
            log_activity(user_id, "Setting scraper delivery")
            return SCRAP_DELIVERY
        elif data == "scraper_set_gap":
            await query.edit_message_text("⏱️  <b>SET SCRAPE GAP</b>\n━━━━━━━━━━━━━━━━━━\nEnter delay between scrapes in seconds:",
                parse_mode=ParseMode.HTML)
            log_activity(user_id, "Setting scraper gap")
            return SCRAP_GAP
        elif data.startswith("scraper_mmode_"):
            s = ud.data["scraper"]
            mm = data.rsplit("_", 1)[-1]
            if mm in ("all", "girls", "active"):
                s["member_mode"] = mm
                ud.save()
                log_activity(user_id, f"Scraper member mode -> {mm}")
            await query.edit_message_reply_markup(reply_markup=scraper_menu(ud))
        elif data == "scraper_girl_kw":
            s = ud.data["scraper"]
            await query.edit_message_text(
                "🏷️  <b>GIRLS KEYWORDS</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "Current: <code>%s</code>\n\n"
                "Comma/space se keywords bhejo. Match name + username me hoga.\n"
                "Example: <code>priya, sharma, kaur, neha, s</code>\n\n"
                "Blank bhejne par auto-detect (Indian feminine endings) use hoga.\n"
                "<code>clear</code> = auto-detect."
                % html.escape((s.get("girl_keywords") or "auto-detect")[:200]),
                parse_mode=ParseMode.HTML)
            log_activity(user_id, "Setting girls keywords")
            return SCRAP_GIRL_KW
        elif data == "scraper_mode_toggle":
            s = ud.data["scraper"]
            s["mode"] = "add" if s.get("mode", "send") == "send" else "send"
            ud.save()
            log_activity(user_id, f"Scraper mode -> {s['mode']}")
            await query.edit_message_text(
                "🔀  <b>SCRAPER MODE</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"Mode: <b>{'ADD members to Delivery group' if s['mode']=='add' else 'SEND users as messages'}</b>\n\n"
                "• <b>Send</b> — profile links as messages\n"
                "• <b>Add</b> — add scraped members into Delivery group\n"
                "  (the active account must be admin there)\n"
                "  fetches members → asks confirm → adds",
                parse_mode=ParseMode.HTML, reply_markup=scraper_menu(ud))
        elif data == "scraper_add_gap":
            s = ud.data["scraper"]
            choices = [10, 15, 20, 25, 30, 45, 60, 90, 120, 180]
            cur = int(s.get("add_gap", 20))
            nxt = choices[(choices.index(cur) + 1) % len(choices)] if cur in choices else 20
            s["add_gap"] = nxt
            ud.save()
            log_activity(user_id, f"Scraper add gap -> {nxt}s")
            await query.edit_message_reply_markup(reply_markup=scraper_menu(ud))
        elif data == "scrap_add_yes":
            s = ud.data["scraper"]
            if s.get("add_running"):
                s["add_running"] = False
                ud.save()
                for key in list(active_tasks.get(user_id, {})):
                    if key == "scrap_add":
                        active_tasks[user_id].pop(key).cancel()
                await query.edit_message_text("⏹️  <b>ADD STOPPED</b>", parse_mode=ParseMode.HTML,
                    reply_markup=scraper_menu(ud))
            elif s.get("pending"):
                accs = [p for p in ud.data["acc"] if ud.data["acc"][p].get("active", True)]
                if not accs:
                    await query.edit_message_text("❌ No active account.", parse_mode=ParseMode.HTML,
                        reply_markup=scraper_menu(ud))
                else:
                    s["add_running"] = True
                    s["add_added"] = 0
                    s["add_failed"] = 0
                    s["add_skipped"] = 0
                    s["per_acc"] = {}
                    ud.save()
                    active_tasks.setdefault(user_id, {})
                    active_tasks[user_id]["scrap_add"] = asyncio.create_task(
                        scrap_add_task(user_id, accs, context.bot))
                    await query.edit_message_text(
                        "🚀 <b>ADD STARTED — ROUND ROBIN</b>\n━━━━━━━━━━━━━━━━━━\n"
                        f"👥 queued: {len(s.get('pending', []))}\n"
                        f"👤 accounts: {len(accs)}\n"
                        f"⏱️ gap: {s.get('add_gap', 20)}s (sirf success ke baad)\n\n"
                        "Har user alag account se add hoga. Live log aa raha hai.",
                        parse_mode=ParseMode.HTML, reply_markup=scraper_menu(ud))
            else:
                await query.answer("No pending members — pehle scrape karo.", show_alert=True)
        elif data == "scrap_add_no":
            s = ud.data["scraper"]
            s["pending"] = []
            ud.save()
            await query.edit_message_text("❌ <b>ADD CANCELLED</b>\nPending list clear.",
                parse_mode=ParseMode.HTML, reply_markup=scraper_menu(ud))
        elif data == "scraper_user_gap":
            await query.edit_message_text("👤  <b>SET USER GAP</b>\n━━━━━━━━━━━━━━━━━━\nDelay between adding each user to delivery group.\nExamples: <code>30</code> (30s), <code>2m</code> (2min), <code>5m</code>:",
                parse_mode=ParseMode.HTML)
            log_activity(user_id, "Setting scraper user gap")
            return SCRAP_USER_GAP
        elif data == "scraper_daily_limit":
            await query.edit_message_text("📅  <b>SET DAILY LIMIT</b>\n━━━━━━━━━━━━━━━━━━\nMax users to scrape per day.\n<code>0</code> = unlimited.\nEnter a number:",
                parse_mode=ParseMode.HTML)
            log_activity(user_id, "Setting scraper daily limit")
            return SCRAP_DAILY_LIMIT
        elif data == "scraper_stats":
            s = ud.data["scraper"]
            txt = (
                "📊  <b>SCRAPER STATS</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"🎯  Target:     {s['target'][:30] if s['target'] else 'Not set'}\n"
                f"📤  Delivery:   {s['delivery'][:30] if s['delivery'] else 'Not set'}\n"
                f"👤  Scraped:    {s['scraped']}\n"
                f"👤  User Gap:   {s['user_gap']}s\n"
                f"📅  Daily Lmt:  {s['daily_limit'] or '♾️'}\n"
                f"📅  Today:      {s['scraped_today']}\n"
                f"⏱️  Batch Gap:  {s['gap']}s\n"
                f"🔎  Scrape Cat: { {'all':'All members','girls':'Only girls','active':'Active members'}.get(s.get('member_mode','all'),'All') }\n"
                f"🏷️  Keywords:   {(s.get('girl_keywords') or 'auto-detect')[:30]}\n"
                f"🛰️  Source:     {s.get('source_used') or '—'}   raw: {s.get('found_total', 0)}\n"
                f"🔀  Mode:       {'ADD to group' if s.get('mode','send')=='add' else 'SEND as message'}\n"
                f"📦  Pending:    {len(s.get('pending', []))}\n"
                f"➕  Add Gap:    {s.get('add_gap', 20)}s (success only)\n"
                f"✅  Add ok:     {s.get('add_added', 0)}   ❌ fail: {s.get('add_failed', 0)}   ⏭️ skip: {s.get('add_skipped', 0)}\n"
                f"♻️  Per acct:   {', '.join('…%s=%d' % (k,v) for k,v in (s.get('per_acc') or {}).items()) or '—'}\n"
                f"🔄  Status:     {'🟢  RUNNING' if s['running'] else '🔴  STOPPED'}"
            )
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="menu_scraper")]]))
            log_activity(user_id, "Viewed scraper stats")

        # Approval flow
        elif data == "appr_yes":
            queue = context.user_data.get("approval_queue", [])
            idx = context.user_data.get("approval_index", 0)
            if queue and idx < len(queue):
                link = queue[idx]
                if link not in ud.data["rej"]["approved"]:
                    ud.data["rej"]["approved"].append(link)
                ud.save()
                idx += 1
                context.user_data["approval_index"] = idx
                await auto_show_next_link(user_id, context, query, ud)
            log_activity(user_id, "Approved rejoin link")
        elif data == "appr_no":
            queue = context.user_data.get("approval_queue", [])
            idx = context.user_data.get("approval_index", 0)
            if queue and idx < len(queue):
                link = queue[idx]
                if link not in ud.data["rej"]["denied"]:
                    ud.data["rej"]["denied"].append(link)
                ud.save()
                idx += 1
                context.user_data["approval_index"] = idx
                await auto_show_next_link(user_id, context, query, ud)
            log_activity(user_id, "Denied rejoin link")
        elif data == "appr_start":
            queue = context.user_data.get("approval_queue", [])
            remaining = queue[context.user_data.get("approval_index", 0):] if queue else []
            for link in remaining:
                if link not in ud.data["rej"]["approved"] and link not in ud.data["rej"]["denied"]:
                    ud.data["rej"]["approved"].append(link)
            ud.save()
            context.user_data["approval_queue"] = []
            await query.edit_message_text("⏭️  <b>Skipped!</b>\n━━━━━━━━━━━━━━━━━━\nRemaining links auto-approved.",
                parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
            log_activity(user_id, "Skipped approval, auto-approved remaining")

        # Settings
        elif data == "set_api":
            await query.edit_message_text("🔑  <b>API CREDENTIALS</b>\n━━━━━━━━━━━━━━━━━━\nSend:\n\n<code>api_id api_hash bot_token owner_id</code>",
                parse_mode=ParseMode.HTML)
            context.user_data["_auto_state"] = "api"
            return SET_API
        elif data == "set_proxy":
            await query.edit_message_text("🌐  <b>PROXY CONFIG</b>\n━━━━━━━━━━━━━━━━━━\nSend:\n<code>host port</code>\nor <code>off</code> to disable",
                parse_mode=ParseMode.HTML)
            context.user_data["_auto_state"] = "proxy_host"
            return PROXY_HOST
        elif data == "set_welcome":
            await query.edit_message_text("👋  <b>WELCOME MESSAGE</b>\n━━━━━━━━━━━━━━━━━━\nSend welcome text (or <code>off</code> to disable):",
                parse_mode=ParseMode.HTML)
            context.user_data["_auto_state"] = "welcome"
            return WELCOME_TXT
        elif data == "auth_users":
            uid = update.effective_user.id
            if uid != OWNER_ID:
                await query.edit_message_text("❌ Only the owner can manage users.",
                    parse_mode=ParseMode.HTML, reply_markup=settings_menu())
                return
            if not AUTHORIZED_USERS:
                txt = "📋  <b>Authorized Users</b>\n━━━━━━━━━━━━━━━━━━\n\nNo authorized users."
            else:
                lines = [f"{i+1}.  <code>{u}</code>" for i, u in enumerate(sorted(AUTHORIZED_USERS))]
                txt = "📋  <b>Authorized Users</b>\n━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(lines)
            btns = [[InlineKeyboardButton("➕  Add User", callback_data="auth_user_add")]]
            for u in sorted(AUTHORIZED_USERS):
                btns.append([InlineKeyboardButton(f"❌  {u}", callback_data=f"auth_user_rm_{u}")])
            btns.append([InlineKeyboardButton("🔙  Back", callback_data="menu_settings")])
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(btns))
            log_activity(uid, "Opened authorized users")
        elif data == "auth_user_add":
            await query.edit_message_text("👤  <b>ADD AUTHORIZED USER</b>\n━━━━━━━━━━━━━━━━━━\nSend the user ID to authorize:",
                parse_mode=ParseMode.HTML)
            return AUTH_USER_ADD
        elif data.startswith("auth_user_rm_"):
            target = int(data.split("_", 2)[2])
            if target in AUTHORIZED_USERS:
                AUTHORIZED_USERS.discard(target)
                save_authorized_users()
                log_activity(OWNER_ID, f"Removed authorized user: {target}")
            # Re-render
            if not AUTHORIZED_USERS:
                txt = "📋  <b>Authorized Users</b>\n━━━━━━━━━━━━━━━━━━\n\nNo authorized users."
            else:
                lines = [f"{i+1}.  <code>{u}</code>" for i, u in enumerate(sorted(AUTHORIZED_USERS))]
                txt = "📋  <b>Authorized Users</b>\n━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(lines)
            btns = [[InlineKeyboardButton("➕  Add User", callback_data="auth_user_add")]]
            for u in sorted(AUTHORIZED_USERS):
                btns.append([InlineKeyboardButton(f"❌  {u}", callback_data=f"auth_user_rm_{u}")])
            btns.append([InlineKeyboardButton("🔙  Back", callback_data="menu_settings")])
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(btns))
        elif data == "download_stats":
            sts = ud.data.get("stats", {})
            txt = (
                "📊  <b>BOT STATISTICS</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"👤  Accounts:     {len(ud.data['acc'])}\n"
                f"✅  Total Joined: {sts.get('total_joined', 0)}\n"
                f"❌  Total Left:   {sts.get('total_left', 0)}\n"
                f"🗓️  Created:      {(sts.get('created_at', 'N/A')[:19])}\n"
                f"⏱️  Uptime:       {get_uptime()}"
            )
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙  Back", callback_data="back_main")]]))
        elif data == "restart_bot":
            await query.edit_message_text("🔄  <b>Restarting...</b>\n━━━━━━━━━━━━━━━━━━", parse_mode=ParseMode.HTML)
            log_activity(user_id, "Bot restart requested")
            python = sys.executable
            os.execl(python, python, *sys.argv)

        elif data == "cleanup":
            dead = []
            for phone in list(ud.data["acc"].keys()):
                session_str = ud.data["acc"][phone].get("ss","")
                if not session_str: dead.append(phone); continue
                client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
                try:
                    await client.connect()
                    if not await client.is_user_authorized(): dead.append(phone)
                except:
                    dead.append(phone)
                finally:
                    try: await client.disconnect()
                    except: pass
            for phone in dead: del ud.data["acc"][phone]
            ud.save()
            await query.edit_message_text("🧹  <b>Cleanup Done</b>\n━━━━━━━━━━━━━━━━━━\nRemoved %d dead accounts." % len(dead), parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Button handler error: {e}", exc_info=True)
        try:
            await query.edit_message_text(f"Error: {str(e)[:100]}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back_main")]]))
        except:
            pass

# ═══════════════════════════════════════════════════════════════════
# MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════════

async def message_handler(update, context):
    global API_ID, API_HASH, BOT_TOKEN, OWNER_ID
    user = update.effective_user
    if not user: return
    uid = user.id
    if not update.message:
        return
    msg = (update.message.text or update.message.caption or "").strip()
    if not msg and not update.message.photo and not update.message.document:
        return

    if not is_authorized(uid):
        return

    ud = get_user_data(uid)

    state = context.user_data.get('_state')
    auto_state = context.user_data.get('_auto_state')

    # Check if a background task left us a pending state
    if state is None:
        br = ud.data.get("_ban_report", {})
        pending = br.get("_state")
        if pending is not None:
            context.user_data['_state'] = pending
            state = pending

    logger.debug(f"Message from {user.id}: state={state}, auto_state={auto_state}, msg={msg[:50]}")

    # Debug: show current state
    if msg.lower() == "debug state":
        await update.message.reply_text(f"🧠  <b>State Debug</b>\n━━━━━━━━━━━━━━━━━━\n_state: <code>{state}</code>\n_auto_state: <code>{auto_state}</code>",
            parse_mode=ParseMode.HTML)
        return

    # TagAll command
    low = msg.lower()
    if low.startswith('/tagall') or low.startswith('/all') or low.startswith('@all'):
        custom_text = msg.split(maxsplit=1)[1] if len(msg.split(maxsplit=1)) > 1 else ''
        gm = ud.data.get("gm", {})
        gid = gm.get("group_id", 0)
        if not gid:
            await update.message.reply_text("❌  Set group ID in Group Manager first.", parse_mode=ParseMode.HTML)
            return
        phone = get_gm_client(ud)
        if not phone:
            await update.message.reply_text("❌  No active account.", parse_mode=ParseMode.HTML)
            return
        client = await get_client(phone, ud)
        if not client:
            await update.message.reply_text("❌  Account unavailable.", parse_mode=ParseMode.HTML)
            return
        try:
            await update.message.reply_text(f"📢  Tagging all members...", parse_mode=ParseMode.HTML)
            entity = await client.get_entity(int(gid))
            from telethon.tl.functions.channels import GetParticipantsRequest
            from telethon.tl.types import ChannelParticipantsSearch
            all_users = []
            offset = 0
            limit = 200
            while True:
                part = await client(GetParticipantsRequest(entity, ChannelParticipantsSearch(''), offset, limit))
                if not part.users:
                    break
                all_users.extend(part.users)
                offset += len(part.users)
                if len(part.users) < limit:
                    break
                await asyncio.sleep(0.5)
            if not all_users:
                await update.message.reply_text("❌  No members found.", parse_mode=ParseMode.HTML)
                return
            total = len(all_users)
            sent = 0
            groups = [all_users[i:i+5] for i in range(0, len(all_users), 5)]
            for group in groups:
                mentions = []
                for u in group:
                    name = (u.first_name or '').strip()
                    if u.last_name:
                        name += ' ' + u.last_name.strip()
                    if not name:
                        name = str(u.id)
                    name_md = name.replace('[','\\[').replace(']','\\]').replace('(','\\(').replace(')','\\)')
                    mentions.append(f"[{name_md}](tg://user?id={u.id})")
                line = ' '.join(mentions) + (f"  {custom_text}" if custom_text else '')
                try:
                    await client.send_message(entity, line, parse_mode='md')
                    sent += len(group)
                    await asyncio.sleep(2)
                except:
                    pass
            await update.message.reply_text(
                f"✅  <b>TagAll Complete</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"👥  Total: {total}\n"
                f"📨  Tagged: {sent}\n"
                f"📝  Text:  <code>{esc(custom_text) if custom_text else 'None'}</code>",
                parse_mode=ParseMode.HTML)
            log_activity(user.id, f"TagAll: {total} members tagged")
        except Exception as e:
            await update.message.reply_text(f"❌  Error: {str(e)[:100]}", parse_mode=ParseMode.HTML)
        finally:
            await client.disconnect()
        return

    # Scrap Girls custom source input (not a conv state)
    if state == "sg_sources":
        links = normalize_link(msg)
        if links:
            existing = ud.data["scrap_girls"]["sources"]
            for lnk in links:
                if lnk not in existing:
                    existing.append(lnk)
            ud.save()
            context.user_data['_state'] = None
            await update.message.reply_text(f"✅  Added <b>{len(links)}</b> source groups.",
                parse_mode=ParseMode.HTML, reply_markup=scrap_girls_menu(ud))
            log_activity(user.id, f"Set {len(links)} scrap girls sources")
        else:
            await update.message.reply_text("❌  No valid links. Try again:", parse_mode=ParseMode.HTML)
        return

    # Account adding
    if state == PHONE:
        context.user_data['_temp'] = {'phone': msg}
        context.user_data['_state'] = OTP
        # Only send code request when OTP state first entered
        key = f"session_{msg}"
        if key not in context.user_data:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            try:
                await client.send_code_request(msg)
            except Exception as e:
                context.user_data['_state'] = None
                await update.message.reply_text(f"❌  <b>Error:</b>  <code>{str(e)[:100]}</code>",
                    parse_mode=ParseMode.HTML)
                return
            context.user_data[key] = client
        await update.message.reply_text("📱  <b>OTP CODE</b>\n━━━━━━━━━━━━━━━━━━\nSend the OTP code with spaces:\n<code>1 2 3 4 5 6</code>\n(or 2FA password if asked):",
            parse_mode=ParseMode.HTML)
        return OTP

    elif state == OTP:
        temp = context.user_data.get('_temp', {})
        phone = temp.get('phone')
        if not phone:
            context.user_data['_state'] = None
            await update.message.reply_text("❌  <b>Session expired.</b>  Use /start",
                parse_mode=ParseMode.HTML)
            return

        key = f"session_{phone}"
        if key not in context.user_data:
            context.user_data['_state'] = None
            await update.message.reply_text("❌  Session expired. Use /start and add account again.",
                parse_mode=ParseMode.HTML)
            return

        client = context.user_data[key]
        try:
            code = msg.replace(" ", "")
            if len(code) > 10:
                await client.sign_in(phone=phone, password=code)
            else:
                await client.sign_in(phone=phone, code=code)
            me = await client.get_me()
            ss = StringSession.save(client.session)

            if phone not in ud.data["acc"]:
                ud.data["acc"][phone] = {}
            ud.data["acc"][phone]["ss"] = ss
            ud.data["acc"][phone]["active"] = True
            ud.data["acc"][phone]["added"] = datetime.now().isoformat()
            ud.data["acc"][phone]["name"] = f"{me.first_name or ''} {me.last_name or ''}".strip()
            ud.save()

            await client.disconnect()
            context.user_data['_state'] = None
            context.user_data.pop(key, None)
            context.user_data.pop('_temp', None)

            await update.message.reply_text(
                "✅  <b>Account Added!</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"📱  {phone}\n👤  {me.first_name}",
                parse_mode=ParseMode.HTML, reply_markup=accounts_menu(ud))
            log_activity(user.id, f"Added account {phone}")
            logger.info(f"Account {phone} added successfully")
        except SessionPasswordNeededError:
            await update.message.reply_text("🔐  <b>2FA PASSWORD</b>\n━━━━━━━━━━━━━━━━━━\nThis account has 2FA. Send your password:",
                parse_mode=ParseMode.HTML)
            context.user_data['_state'] = PASSWORD
            return PASSWORD
        except Exception as e:
            context.user_data['_state'] = None
            await update.message.reply_text(f"❌  <b>Error:</b>  <code>{str(e)[:100]}</code>",
                parse_mode=ParseMode.HTML)
            logger.error(f"OTP error for {phone}: {e}")
            return

    elif state == PASSWORD:
        temp = context.user_data.get('_temp', {})
        phone = temp.get('phone')
        key = f"session_{phone}"
        client = context.user_data.get(key)
        if not client:
            context.user_data['_state'] = None
            await update.message.reply_text("❌  <b>Session expired.</b>  Use /start",
                parse_mode=ParseMode.HTML)
            return

        try:
            await client.sign_in(phone=phone, password=msg)
            me = await client.get_me()
            ss = StringSession.save(client.session)

            if phone not in ud.data["acc"]:
                ud.data["acc"][phone] = {}
            ud.data["acc"][phone]["ss"] = ss
            ud.data["acc"][phone]["active"] = True
            ud.data["acc"][phone]["added"] = datetime.now().isoformat()
            ud.data["acc"][phone]["name"] = f"{me.first_name or ''} {me.last_name or ''}".strip()
            ud.save()

            await client.disconnect()
            context.user_data['_state'] = None
            context.user_data.pop(key, None)
            context.user_data.pop('_temp', None)

            await update.message.reply_text(
                "✅  <b>Account Added!</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"📱  {phone}\n👤  {me.first_name}",
                parse_mode=ParseMode.HTML, reply_markup=accounts_menu(ud))
            log_activity(user.id, f"Added account {phone}")
        except Exception as e:
            await update.message.reply_text(f"❌  <b>Error:</b>  <code>{str(e)[:100]}</code>",
                parse_mode=ParseMode.HTML)

    # Rejoin links
    elif state == SEND_LINKS:
        links = normalize_link(msg)
        if not links:
            await update.message.reply_text("❌  No valid links found. Try again or /cancel",
                parse_mode=ParseMode.HTML)
            return SEND_LINKS

        if ud.data["rej"].get("auto_approve"):
            added = 0
            for link in links:
                if link not in ud.data["rej"]["approved"]:
                    ud.data["rej"]["approved"].append(link)
                    added += 1
            ud.save()
            context.user_data['_state'] = None
            await update.message.reply_text(
                f"✅  <b>Auto-Approved!</b>  {added} links added to approved list.",
                parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
            return None

        context.user_data["approval_queue"] = links
        context.user_data["approval_index"] = 0
        context.user_data['_state'] = None

        await update.message.reply_text(
            f"🔍  Checking {len(links)} links for dead/invalid...",
            parse_mode=ParseMode.HTML)
        await auto_show_next_link(update.effective_user.id, context, update, ud)

    # Gap and cycles for rejoin
    elif state == CUSTOM_GAP:
        text = msg.lower()
        seconds = None
        if text.endswith('h'):
            try: seconds = int(text[:-1]) * 3600
            except: pass
        elif text.endswith('m'):
            try: seconds = int(text[:-1]) * 60
            except: pass
        elif text.endswith('s'):
            try: seconds = int(text[:-1])
            except: pass
        else:
            try: seconds = int(text)
            except: pass

        if seconds and seconds > 0:
            ud.data["rej"]["gap"] = seconds
            ud.save()
            context.user_data['_state'] = None
            await update.message.reply_text(f"✅  Gap set to {format_gap(seconds)}",
                parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
            log_activity(user.id, f"Rejoin gap set to {seconds}s")
        else:
            await update.message.reply_text("❌  Invalid gap. Use: <code>30s</code>  <code>5m</code>  <code>1h</code>",
                parse_mode=ParseMode.HTML)
            return CUSTOM_GAP

    elif state == CUSTOM_CYCLES:
        try:
            cycles = int(msg)
            if cycles >= 0:
                ud.data["rej"]["cycles"] = cycles
                ud.save()
                context.user_data['_state'] = None
                display = "∞" if cycles == 0 else str(cycles)
                await update.message.reply_text(f"✅  Cycles set to {display}",
                    parse_mode=ParseMode.HTML, reply_markup=rejoin_menu(ud))
                log_activity(user.id, f"Rejoin cycles set to {cycles}")
            else:
                await update.message.reply_text("❌  Cycles must be >= 0. Try again:",
                    parse_mode=ParseMode.HTML)
                return CUSTOM_CYCLES
        except ValueError:
            await update.message.reply_text("❌  Invalid number. Try again:",
                parse_mode=ParseMode.HTML)
            return CUSTOM_CYCLES

    # Settings
    elif state == SET_API:
        parts = msg.split()
        if len(parts) >= 4:
            try:
                api_id = int(parts[0])
                api_hash = parts[1]
                bot_token = parts[2]
                owner_id = int(parts[3])
                config = {"api_id": api_id, "api_hash": api_hash, "bot_token": bot_token, "owner_id": owner_id}
                with open("api_config.json", "w") as f:
                    json.dump(config, f)
                API_ID = api_id; API_HASH = api_hash; BOT_TOKEN = bot_token; OWNER_ID = owner_id
                context.user_data['_state'] = None
                await update.message.reply_text("✅  API credentials updated!  Restart recommended.",
                    parse_mode=ParseMode.HTML, reply_markup=settings_menu())
                log_activity(user.id, "Updated API credentials")
            except Exception as e:
                await update.message.reply_text(f"❌  <b>Error:</b>  <code>{str(e)[:50]}</code>\nFormat: <code>api_id api_hash bot_token owner_id</code>",
                    parse_mode=ParseMode.HTML)
                return SET_API
        else:
            await update.message.reply_text("📋  Format: <code>api_id api_hash bot_token owner_id</code>",
                parse_mode=ParseMode.HTML)
            return SET_API

    elif state == PROXY_HOST:
        if msg.lower() == 'off':
            ud.data["proxy"]["enabled"] = False
            ud.save()
            context.user_data['_state'] = None
            await update.message.reply_text("🌐  Proxy disabled.", parse_mode=ParseMode.HTML, reply_markup=settings_menu())
            return
        parts = msg.split()
        if len(parts) >= 2:
            try:
                ud.data["proxy"]["host"] = parts[0]
                ud.data["proxy"]["port"] = int(parts[1])
                ud.data["proxy"]["enabled"] = True
                if len(parts) >= 4:
                    ud.data["proxy"]["username"] = parts[2]
                    ud.data["proxy"]["password"] = parts[3]
                ud.save()
                context.user_data['_state'] = None
                await update.message.reply_text(f"🌐  Proxy set to <code>{parts[0]}:{parts[1]}</code>",
                    parse_mode=ParseMode.HTML, reply_markup=settings_menu())
                log_activity(user.id, f"Proxy set to {parts[0]}:{parts[1]}")
            except Exception as e:
                await update.message.reply_text(f"❌  <b>Error:</b>  <code>{str(e)[:50]}</code>",
                    parse_mode=ParseMode.HTML)
                return PROXY_HOST
        else:
            await update.message.reply_text("📋  Format: <code>host port</code>  (or <code>off</code> to disable)",
                parse_mode=ParseMode.HTML)
            return PROXY_HOST

    elif state == WELCOME_TXT:
        if msg.lower() == 'off':
            ud.data["welcome_msg"]["enabled"] = False
            ud.save()
            context.user_data['_state'] = None
            await update.message.reply_text("👋  Welcome message disabled.", parse_mode=ParseMode.HTML, reply_markup=settings_menu())
        else:
            ud.data["welcome_msg"]["text"] = msg
            ud.data["welcome_msg"]["enabled"] = True
            ud.save()
            context.user_data['_state'] = None
            await update.message.reply_text("✅  Welcome message updated!", parse_mode=ParseMode.HTML, reply_markup=settings_menu())

    elif state == WAIT_FILE:
        if update.message.document:
            file = await update.message.document.get_file()
            content = await file.download_as_bytearray()
            text = content.decode("utf-8", errors="ignore")
            links = normalize_link(text)
            if not links:
                await update.message.reply_text("❌  No valid links found in file.", parse_mode=ParseMode.HTML)
            else:
                context.user_data["approval_queue"] = links
                context.user_data["approval_index"] = 0
                context.user_data['_state'] = None
                await update.message.reply_text(
                    f"🔍  Checking {len(links)} links from file for dead/invalid...",
                    parse_mode=ParseMode.HTML)
                await auto_show_next_link(update.effective_user.id, context, update, ud)
                log_activity(user.id, f"Imported {len(links)} links from file")
                return
        else:
            await update.message.reply_text("📂  Please upload a <code>.txt</code> file.", parse_mode=ParseMode.HTML)
            return WAIT_FILE

    elif state == SCRAP_TARGET:
        links = normalize_link(msg)
        if links:
            ud.data["scraper"]["target"] = links[0]
            ud.save()
            context.user_data['_state'] = None
            await update.message.reply_text(f"✅  Target set to <code>{links[0][:40]}</code>",
                parse_mode=ParseMode.HTML, reply_markup=scraper_menu(ud))
            log_activity(user.id, f"Scraper target: {links[0][:30]}")
        else:
            await update.message.reply_text("❌  Invalid link. Try again:", parse_mode=ParseMode.HTML)
            return SCRAP_TARGET
    elif state == SCRAP_DELIVERY:
        links = normalize_link(msg)
        if links:
            ud.data["scraper"]["delivery"] = links[0]
            ud.save()
            context.user_data['_state'] = None
            await update.message.reply_text(f"✅  Delivery set to <code>{links[0][:40]}</code>",
                parse_mode=ParseMode.HTML, reply_markup=scraper_menu(ud))
            log_activity(user.id, f"Scraper delivery: {links[0][:30]}")
        else:
            await update.message.reply_text("❌  Invalid link. Try again:", parse_mode=ParseMode.HTML)
            return SCRAP_DELIVERY
    elif state == SCRAP_GAP:
        try:
            gap = int(msg)
            if gap > 0:
                ud.data["scraper"]["gap"] = gap
                ud.save()
                context.user_data['_state'] = None
                await update.message.reply_text(f"✅  Batch gap set to {gap}s", parse_mode=ParseMode.HTML,
                    reply_markup=scraper_menu(ud))
                log_activity(user.id, f"Scraper batch gap: {gap}s")
            else:
                await update.message.reply_text("❌  Gap must be > 0. Try again:", parse_mode=ParseMode.HTML)
                return SCRAP_GAP
        except ValueError:
            await update.message.reply_text("❌  Invalid number. Try again:", parse_mode=ParseMode.HTML)
            return SCRAP_GAP

    elif state == SCRAP_USER_GAP:
        try:
            t = msg.strip().lower()
            if t.endswith("m"):
                gap = int(t[:-1]) * 60
            elif t.endswith("h"):
                gap = int(t[:-1]) * 3600
            elif t.endswith("s"):
                gap = int(t[:-1])
            else:
                gap = int(t)
            if gap > 0:
                ud.data["scraper"]["user_gap"] = gap
                ud.save()
                context.user_data['_state'] = None
                label = "%dm" % (gap // 60) if gap >= 60 else "%ds" % gap
                await update.message.reply_text(f"✅  User gap set to {label}", parse_mode=ParseMode.HTML,
                    reply_markup=scraper_menu(ud))
                log_activity(user.id, f"Scraper user gap: {gap}s")
            else:
                await update.message.reply_text("❌  Gap must be > 0. Try again:", parse_mode=ParseMode.HTML)
                return SCRAP_USER_GAP
        except ValueError:
            await update.message.reply_text("❌  Invalid. Use seconds (<code>30</code>) or minutes (<code>2m</code>). Try again:", parse_mode=ParseMode.HTML)
            return SCRAP_USER_GAP

    elif state == SCRAP_GIRL_KW:
        txt = msg.strip()
        if txt.lower() in ("clear", "none", "off", "-"):
            txt = ""
        ud.data["scraper"]["girl_keywords"] = txt[:300]
        ud.save()
        context.user_data['_state'] = None
        await update.message.reply_text(
            "✅  Girls keywords set: <code>%s</code>"
            % html.escape(txt[:200] if txt else "auto-detect"),
            parse_mode=ParseMode.HTML, reply_markup=scraper_menu(ud))
        log_activity(user.id, f"Girls keywords: {txt[:60]}")

    elif state == SCRAP_DAILY_LIMIT:
        try:
            limit = int(msg)
            if limit >= 0:
                ud.data["scraper"]["daily_limit"] = limit
                ud.data["scraper"]["scraped_today"] = 0
                ud.data["scraper"]["last_scrape_date"] = ""
                ud.save()
                context.user_data['_state'] = None
                label = "♾️  Unlimited" if limit == 0 else str(limit)
                await update.message.reply_text(f"✅  Daily limit set to {label}", parse_mode=ParseMode.HTML,
                    reply_markup=scraper_menu(ud))
                log_activity(user.id, f"Scraper daily limit: {limit}")
            else:
                await update.message.reply_text("❌  Must be >= 0. Try again:", parse_mode=ParseMode.HTML)
                return SCRAP_DAILY_LIMIT
        except ValueError:
            await update.message.reply_text("❌  Invalid number. Try again:", parse_mode=ParseMode.HTML)
            return SCRAP_DAILY_LIMIT

    elif state == AUTH_USER_ADD:
        if uid != OWNER_ID:
            await update.message.reply_text("❌ Only the owner can add users.")
            context.user_data['_state'] = None
            return
        try:
            new_uid = int(msg.strip())
        except ValueError:
            await update.message.reply_text("❌  Invalid user ID. Try again:", parse_mode=ParseMode.HTML)
            return AUTH_USER_ADD
        if new_uid in AUTHORIZED_USERS:
            await update.message.reply_text(f"⚠️  User {new_uid} is already authorized.",
                parse_mode=ParseMode.HTML, reply_markup=settings_menu())
        else:
            AUTHORIZED_USERS.add(new_uid)
            save_authorized_users()
            await update.message.reply_text(f"✅  Authorized user {new_uid} added.",
                parse_mode=ParseMode.HTML, reply_markup=settings_menu())
            log_activity(OWNER_ID, f"Added authorized user: {new_uid}")
        context.user_data['_state'] = None

    elif state == GROUP_SET:
        links = normalize_link(msg)
        if links:
            gid_str = links[0].split("/")[-1]
            if "c/" in links[0] and gid_str.isdigit():
                try:
                    gid = int("-100" + gid_str)
                except ValueError:
                    gid = 0
            else:
                try:
                    gid = int(msg.strip()) if msg.strip().lstrip('-').isdigit() else 0
                except ValueError:
                    gid = 0
            ud.data["gm"]["group_id"] = gid
            ud.data["gm"]["group_title"] = links[0][:40]
            ud.save()
            context.user_data['_state'] = None
            await update.message.reply_text(f"✅  Group set to <code>{links[0][:40]}</code>",
                parse_mode=ParseMode.HTML, reply_markup=gm_menu(ud))
            log_activity(user.id, f"GM group: {gid}")
        else:
            await update.message.reply_text("❌  Invalid link. Try again:", parse_mode=ParseMode.HTML)
            return GROUP_SET
    elif state == GROUP_USER_INPUT:
        action = context.user_data.get("gm_action", "ban")
        result = await gm_action(user.id, ud, action, msg)
        context.user_data['_state'] = None
        await update.message.reply_text(result, parse_mode=ParseMode.HTML, reply_markup=gm_menu(ud))
        log_activity(user.id, f"GM {action}: {msg[:30]}")
    elif state == SCRAP_GIRLS_QTY:
        try:
            qty = int(msg)
            if qty > 0:
                ud.data["scrap_girls"]["qty"] = qty
                ud.save()
                context.user_data['_state'] = None
                await update.message.reply_text(f"✅  Quantity set to {qty}", parse_mode=ParseMode.HTML,
                    reply_markup=scrap_girls_menu(ud))
            else:
                await update.message.reply_text("❌  Must be > 0.", parse_mode=ParseMode.HTML)
                return SCRAP_GIRLS_QTY
        except ValueError:
            await update.message.reply_text("❌  Invalid number.", parse_mode=ParseMode.HTML)
            return SCRAP_GIRLS_QTY
    elif state == SCRAP_GIRLS_DELAY:
        try:
            d = int(msg)
            if d > 0:
                ud.data["scrap_girls"]["delay"] = d
                ud.save()
                context.user_data['_state'] = None
                await update.message.reply_text(f"✅  Delay set to {d}s", parse_mode=ParseMode.HTML,
                    reply_markup=scrap_girls_menu(ud))
            else:
                await update.message.reply_text("❌  Must be > 0.", parse_mode=ParseMode.HTML)
                return SCRAP_GIRLS_DELAY
        except ValueError:
            await update.message.reply_text("❌  Invalid number.", parse_mode=ParseMode.HTML)
            return SCRAP_GIRLS_DELAY

    elif state == GM_WELCOME:
        ud.data["gm"]["welcome_text"] = msg
        ud.data["gm"]["welcome_enabled"] = True
        ud.save()
        context.user_data['_state'] = None
        await update.message.reply_text("✅  Welcome text saved and enabled!",
            parse_mode=ParseMode.HTML, reply_markup=gm_settings_menu(ud))
        log_activity(user.id, "GM welcome text updated")
    elif state == GM_RULES:
        ud.data["gm"]["rules_text"] = msg
        ud.data["gm"]["rules_enabled"] = True
        ud.save()
        context.user_data['_state'] = None
        await update.message.reply_text("✅  Rules saved and enabled!",
            parse_mode=ParseMode.HTML, reply_markup=gm_settings_menu(ud))
        log_activity(user.id, "GM rules updated")
    elif state == GM_FILTER:
        word = msg.lower().strip()
        fl = ud.data["gm"].get("filters", [])
        if word and word not in fl:
            fl.append(word)
            ud.data["gm"]["filters"] = fl
            ud.save()
        context.user_data['_state'] = None
        await update.message.reply_text(f"✅  Added filter word: <code>{esc(word)}</code>",
            parse_mode=ParseMode.HTML, reply_markup=gm_protection_menu(ud))
        log_activity(user.id, f"GM filter added: {word}")
    elif state == GM_AF_MSGS:
        try:
            n = int(msg)
            if n > 0:
                ud.data["gm"]["antiflood_msgs"] = n
                if not ud.data["gm"].get("antiflood", {}):
                    ud.data["gm"]["antiflood"] = {"enabled": True}
                ud.save()
                context.user_data['_state'] = None
                await update.message.reply_text(f"✅  Antiflood max msgs set to {n}",
                    parse_mode=ParseMode.HTML, reply_markup=gm_protection_menu(ud))
                log_activity(user.id, f"GM antiflood msgs: {n}")
            else:
                await update.message.reply_text("❌  Must be > 0.", parse_mode=ParseMode.HTML)
                return GM_AF_MSGS
        except ValueError:
            await update.message.reply_text("❌  Invalid number.", parse_mode=ParseMode.HTML)
            return GM_AF_MSGS
    elif state == GM_AF_INT:
        try:
            n = int(msg)
            if n > 0:
                ud.data["gm"]["antiflood_interval"] = n
                if not ud.data["gm"].get("antiflood", {}):
                    ud.data["gm"]["antiflood"] = {"enabled": True}
                ud.save()
                context.user_data['_state'] = None
                await update.message.reply_text(f"✅  Antiflood interval set to {n}s",
                    parse_mode=ParseMode.HTML, reply_markup=gm_protection_menu(ud))
                log_activity(user.id, f"GM antiflood interval: {n}s")
            else:
                await update.message.reply_text("❌  Must be > 0.", parse_mode=ParseMode.HTML)
                return GM_AF_INT
        except ValueError:
            await update.message.reply_text("❌  Invalid number.", parse_mode=ParseMode.HTML)
            return GM_AF_INT
    elif state == GM_WARN_SET:
        try:
            n = int(msg)
            if n > 0:
                ud.data["gm"]["warn_max"] = n
                ud.save()
                context.user_data['_state'] = None
                await update.message.reply_text(f"✅  Max warns set to {n}",
                    parse_mode=ParseMode.HTML, reply_markup=gm_protection_menu(ud))
                log_activity(user.id, f"GM warn max: {n}")
            else:
                await update.message.reply_text("❌  Must be > 0.", parse_mode=ParseMode.HTML)
                return GM_WARN_SET
        except ValueError:
            await update.message.reply_text("❌  Invalid number.", parse_mode=ParseMode.HTML)
            return GM_WARN_SET

    # Banning - Groq API Key
    elif state == BAN_GROQ:
        key = msg.strip()
        if len(key) > 10 and key.startswith("gsk_"):
            ud.data["banning"]["groq_api"] = key
            ud.save()
            context.user_data['_state'] = None
            await update.message.reply_text("✅  Groq API key saved!", parse_mode=ParseMode.HTML,
                reply_markup=banning_menu(ud))
            log_activity(user.id, "Groq API key set")
        else:
            await update.message.reply_text("❌  Invalid key. Must start with 'gsk_'. Try again:", parse_mode=ParseMode.HTML)
            return BAN_GROQ
    elif state == BAN_TARGET:
        context.user_data['_state'] = None
        links = normalize_link(msg)
        if links:
            ud.data["banning"]["target"] = links[0]
            if "joinchat" in links[0] or "t.me/+" in links[0]:
                ud.data["banning"]["target_type"] = "group"
            elif any(c.isdigit() for c in links[0].split("/")[-1]) and len(links[0].split("/")[-1]) > 5:
                ud.data["banning"]["target_type"] = "channel"
            else:
                uname_part = links[0].split("/")[-1].lstrip("@")
                if uname_part and uname_part[0].isalpha():
                    ud.data["banning"]["target_type"] = "group"
                else:
                    ud.data["banning"]["target_type"] = "user"
        else:
            m = msg.strip().lstrip("@")
            if re.match(r'^-?\d+$', m):
                ud.data["banning"]["target"] = m
                ud.data["banning"]["target_type"] = "user"
            elif re.match(r'^[a-zA-Z][a-zA-Z0-9_]{4,}$', m):
                ud.data["banning"]["target"] = f"https://t.me/{m}"
                ud.data["banning"]["target_type"] = "group"
            else:
                await update.message.reply_text("❌  Invalid target. Try again:", parse_mode=ParseMode.HTML)
                return BAN_TARGET
        ud.save()
        await update.message.reply_text(f"✅  Target set: <code>{ud.data['banning']['target'][:40]}</code>",
            parse_mode=ParseMode.HTML, reply_markup=banning_menu(ud))
        log_activity(user.id, f"Ban target: {ud.data['banning']['target'][:30]}")
    elif state == BAN_SCAN_COUNT:
        inp = msg.strip().lower()
        valid = False
        if inp == "all":
            ud.data["banning"]["msg_limit"] = "all"
            valid = True
        elif inp.isdigit() and int(inp) > 0:
            ud.data["banning"]["msg_limit"] = int(inp)
            valid = True
        if valid:
            ud.save()
            context.user_data['_state'] = None
            b = ud.data["banning"]
            b["running"] = True; ud.save()
            if user.id not in active_tasks:
                active_tasks[user.id] = {}
            active_tasks[user.id]["banning"] = asyncio.create_task(
                banning_review_task(user.id, context.bot))
            await update.message.reply_text("🚀  <b>Review Started!</b>\n━━━━━━━━━━━━━━━━━━\nAnalyzing target...",
                parse_mode=ParseMode.HTML, reply_markup=banning_menu(ud))
            log_activity(user.id, "Started banning review")
        else:
            await update.message.reply_text("❌  Enter a number or 'all'. Try again:", parse_mode=ParseMode.HTML)
            return BAN_SCAN_COUNT
    elif state == BAN_REPORT_COUNT:
        # Load report context from user data
        br = ud.data.setdefault("_ban_report", {})
        ctx = context.user_data
        ctx["report_entity"] = br.get("entity_id")
        ctx["report_ids"] = br.get("report_ids", [])
        ctx["report_violation_ctx"] = br.get("violation_ctx", "Various policy violations")
        ctx["report_groq_api"] = br.get("groq_api")
        ctx["report_phone"] = br.get("phone")
        try:
            count = int(msg.strip())
            if count < 1 or count > 100:
                await update.message.reply_text("❌  Use 1-100. Try again:", parse_mode=ParseMode.HTML)
                return BAN_REPORT_COUNT
            context.user_data["report_count"] = count
            context.user_data['_state'] = BAN_REPORT_INTERVAL
            # Clear pending background state
            br["_state"] = None
            ud.save()
            await update.message.reply_text(
                "⏱  <b>REPORT INTERVAL</b>\n━━━━━━━━━━━━━━━━━━\n"
                "Enter interval between reports (e.g. <b>5-10sec</b> or <b>5-10m</b>):",
                parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌  Enter a valid number. Try again:", parse_mode=ParseMode.HTML)
            return BAN_REPORT_COUNT
    elif state == BAN_REPORT_INTERVAL:
        inp = msg.strip().lower()
        m = re.match(r'^(\d+)-(\d+)\s*(sec|s|m|min)?$', inp)
        if not m:
            await update.message.reply_text(
                "❌  Invalid format. Use <b>5-10sec</b> or <b>1-5m</b>:",
                parse_mode=ParseMode.HTML)
            return BAN_REPORT_INTERVAL
        lo, hi = int(m.group(1)), int(m.group(2))
        unit = m.group(3) or "sec"
        if lo < 1 or hi < lo:
            await update.message.reply_text("❌  Invalid range. Try again:", parse_mode=ParseMode.HTML)
            return BAN_REPORT_INTERVAL
        mult = 60 if unit in ("m", "min") else 1
        context.user_data["report_interval_lo"] = lo * mult
        context.user_data["report_interval_hi"] = hi * mult
        context.user_data['_state'] = None
        count = context.user_data.get("report_count", 1)
        await update.message.reply_text(
            f"🚀  <b>Sending {count} reports...</b>\n"
            f"⏱  Random delay: {lo}-{hi}{'m' if unit in ('m','min') else 'sec'}\n"
            "━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML)
        # Start bulk report task
        if user.id not in active_tasks:
            active_tasks[user.id] = {}
        active_tasks[user.id]["banning"] = asyncio.create_task(
            bulk_report_task(user.id, context.bot, context.user_data))
        log_activity(user.id, f"Started bulk report: {count}x, {lo}-{hi}{'m' if unit in ('m','min') else 'sec'} interval")

    # Name/Bio/Pfp across all accounts
    elif state == SET_NAME:
        parts = msg.split(None, 1)
        first = parts[0] if parts else msg
        last = parts[1] if len(parts) > 1 else ""
        accs = [p for p in ud.data["acc"] if ud.data["acc"][p].get("active", True)]
        if not accs:
            await update.message.reply_text("❌  No active accounts.", parse_mode=ParseMode.HTML)
        else:
            done = 0; failed = 0
            for phone in accs:
                client = await get_client(phone, ud)
                if not client:
                    failed += 1; continue
                try:
                    await client(functions.account.UpdateProfileRequest(first_name=first, last_name=last))
                    await client.disconnect()
                    done += 1
                except Exception as e:
                    await client.disconnect()
                    failed += 1
                    logger.error(f"Name update failed for {phone}: {e}")
            context.user_data['_state'] = None
            await update.message.reply_text(f"✏️  <b>Name Updated</b>\n━━━━━━━━━━━━━━━━━━\n✅  Done: {done}   ❌  Failed: {failed}",
                parse_mode=ParseMode.HTML, reply_markup=accounts_menu(ud))
            log_activity(user.id, f"Updated name across {done} accounts")
        return

    elif state == SET_BIO:
        accs = [p for p in ud.data["acc"] if ud.data["acc"][p].get("active", True)]
        if not accs:
            await update.message.reply_text("❌  No active accounts.", parse_mode=ParseMode.HTML)
        else:
            done = 0; failed = 0
            for phone in accs:
                client = await get_client(phone, ud)
                if not client:
                    failed += 1; continue
                try:
                    await client(functions.account.UpdateProfileRequest(about=msg))
                    await client.disconnect()
                    done += 1
                except Exception as e:
                    await client.disconnect()
                    failed += 1
                    logger.error(f"Bio update failed for {phone}: {e}")
            context.user_data['_state'] = None
            await update.message.reply_text(f"📝  <b>Bio Updated</b>\n━━━━━━━━━━━━━━━━━━\n✅  Done: {done}   ❌  Failed: {failed}",
                parse_mode=ParseMode.HTML, reply_markup=accounts_menu(ud))
            log_activity(user.id, f"Updated bio across {done} accounts")
        return

    elif state == SET_PFP:
        if not update.message.photo:
            await update.message.reply_text("🖼️  Please send a photo file.", parse_mode=ParseMode.HTML)
            return SET_PFP
        accs = [p for p in ud.data["acc"] if ud.data["acc"][p].get("active", True)]
        if not accs:
            await update.message.reply_text("❌  No active accounts.", parse_mode=ParseMode.HTML)
        else:
            photo = update.message.photo[-1]
            file = await photo.get_file()
            photo_bytes = await file.download_as_bytearray()
            done = 0; failed = 0
            for phone in accs:
                client = await get_client(phone, ud)
                if not client:
                    failed += 1; continue
                try:
                    uploaded = await client.upload_file(photo_bytes, file_name="pfp.jpg")
                    await client(functions.photos.UploadProfilePhotoRequest(file=uploaded))
                    await client.disconnect()
                    done += 1
                except Exception as e:
                    await client.disconnect()
                    failed += 1
                    logger.error(f"PFP update failed for {phone}: {e}")
            context.user_data['_state'] = None
            await update.message.reply_text(f"🖼️  <b>Profile Picture Updated</b>\n━━━━━━━━━━━━━━━━━━\n✅  Done: {done}   ❌  Failed: {failed}",
                parse_mode=ParseMode.HTML, reply_markup=accounts_menu(ud))
            log_activity(user.id, f"Updated pfp across {done} accounts")
        return

    else:
        await update.message.reply_text("❓  Use the menu buttons.", parse_mode=ParseMode.HTML)

    return

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

async def backup_cmd(update, context):
    if not is_authorized(update.effective_user.id):
        return
    uid = update.effective_user.id
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in DATA_DIR.glob("%s_*" % uid):
                if f.is_file():
                    z.write(f, arcname=f.name)
        buf.seek(0)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        await update.message.reply_document(document=buf,
            filename="ads_backup_%s_%s.zip" % (uid, stamp),
            caption="🗄️ Backup — Render restart ke baad /restore se wapas import karo.")
        log_activity(uid, "Created backup")
    except Exception as e:
        await update.message.reply_text("❌ Backup failed: %s" % html.escape(str(e)[:120]))

async def restore_cmd(update, context):
    if not is_authorized(update.effective_user.id):
        return
    uid = update.effective_user.id
    msg = update.message
    doc = msg.document if msg else None
    if not doc:
        await msg.reply_text("📦 Backup zip file ko reply karke /restore bhejo.")
        return
    try:
        tg = await doc.get_file()
        raw = bytes(await tg.download_as_bytearray())
        n = 0
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for name in z.namelist():
                if "/" in name or "\\" in name or not name.startswith("%s_" % uid):
                    continue
                if not name.endswith((".json", ".log")):
                    continue
                with z.open(name) as src, open(DATA_DIR / name, "wb") as dst:
                    dst.write(src.read())
                n += 1
        USER_DATA_CACHE.pop(uid, None)
        ud = get_user_data(uid)
        await msg.reply_text(
            "✅ Restore ho gaya — %d files.\n👤 accounts: %d  •  📋 rejoin groups: %d\n\nAb /start karo."
            % (n, len(ud.data.get("acc", {})), len(ud.data.get("rej", {}).get("approved", []))),
            parse_mode=ParseMode.HTML)
        log_activity(uid, "Restored backup")
    except Exception as e:
        await msg.reply_text("❌ Restore failed: %s" % html.escape(str(e)[:120]))

async def start(update, context):
    if not update.message:
        return
    uid = update.effective_user.id
    if not is_authorized(uid):
        await update.message.reply_text("⛔  Unauthorized. Contact the bot owner for access.", parse_mode=ParseMode.HTML)
        return

    context.user_data['_state'] = None
    context.user_data['_auto_state'] = None

    user_id = update.effective_user.id
    ud = get_user_data(user_id)
    acc_count = len(ud.data["acc"])

    await update.message.reply_text(
        "🎛️  <b>Mega Marketing Bot</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤  Accounts: {acc_count}\n"
        f"🔄  Rejoin:   {'🟢  Running' if rejoin_live(user_id, ud) else '🔴  Stopped'}",
        parse_mode=ParseMode.HTML, reply_markup=main_menu())
    log_activity(user_id, "Bot started")

async def stats_cmd(update, context):
    if not is_authorized(update.effective_user.id): return
    ud = get_user_data(update.effective_user.id)
    r = ud.data["rej"]
    txt = (
        "📊  <b>QUICK STATS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤  Accounts:    {len(ud.data['acc'])}\n"
        f"✅  Rejoin Join: {r['joined_count']}\n"
        f"❌  Rejoin Left: {r['left_count']}\n"
        f"📋  Approved:    {len(r['approved'])}\n"
        f"⏱️  Uptime:      {get_uptime()}"
    )
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

async def cleanup_cmd(update, context):
    if not is_authorized(update.effective_user.id): return
    ud = get_user_data(update.effective_user.id)
    dead = []
    for phone in list(ud.data.get("acc", {}).keys()):
        ss = ud.data["acc"][phone].get("ss","")
        if not ss: dead.append(phone); continue
        client = TelegramClient(StringSession(ss), API_ID, API_HASH)
        try:
            await client.connect()
            if not await client.is_user_authorized(): dead.append(phone)
        except:
            dead.append(phone)
        finally:
            try: await client.disconnect()
            except: pass
    for phone in dead: del ud.data["acc"][phone]
    ud.save()
    await update.message.reply_text(f"🧹  Removed {len(dead)} dead accounts.", parse_mode=ParseMode.HTML)

async def cancel(update, context):
    context.user_data['_state'] = None
    context.user_data['_auto_state'] = None
    await update.message.reply_text("❌  Cancelled.", parse_mode=ParseMode.HTML, reply_markup=main_menu())

def cpu_load():
    try:
        with open("/proc/stat") as f:
            line = f.readline().strip().split()
        if not line or line[0] != "cpu":
            return 0.0
        vals = [int(x) for x in line[1:]]
        total1 = sum(vals)
        idle1 = vals[3]
        time.sleep(0.5)
        with open("/proc/stat") as f:
            line = f.readline().strip().split()
        vals = [int(x) for x in line[1:]]
        total2 = sum(vals)
        idle2 = vals[3]
        total_delta = total2 - total1
        idle_delta = idle2 - idle1
        if total_delta == 0:
            return 0.0
        return round(100.0 * (1.0 - idle_delta / total_delta), 1)
    except Exception:
        try:
            with open("/proc/loadavg") as f:
                parts = f.read().strip().split()
            return float(parts[0]) * 10.0
        except Exception:
            return 0.0

def cpu_delay_factor(lo=1.0, hi=2.5):
    load = cpu_load()
    if load < 30:
        return lo
    elif load < 60:
        return lo + (hi - lo) * (load - 30) / 30
    else:
        return hi

def auto_clear_cache():
    cleared = 0
    for f in Path(".").iterdir():
        if f.suffix in (".session", ".journal", ".log") and f.stat().st_mtime < time.time() - 86400:
            try:
                f.unlink()
                cleared += 1
            except:
                pass
    tmp = Path("/tmp/opencode")
    if tmp.exists():
        for f in tmp.iterdir():
            if f.is_file() and f.stat().st_mtime < time.time() - 3600:
                try:
                    f.unlink()
                    cleared += 1
                except:
                    pass
    if cleared:
        logger.info(f"Auto-cleared {cleared} stale cache files")

async def check_resume_tasks(app: Application):
    await asyncio.sleep(3)
    data_dir = DATA_DIR
    if not data_dir.exists():
        return
    for f in sorted(data_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.suffix != ".json" or not f.stem.isdigit():
            continue
        try:
            uid = int(f.stem)
            with open(f) as fh:
                d = json.load(fh)
            tasks_to_resume = []
            if d.get("rej", {}).get("running"):
                tasks_to_resume.append("🔄 Rejoin Cycle")
            if d.get("scraper", {}).get("running"):
                tasks_to_resume.append("👥 Member Scraper")
            if d.get("scrap_girls", {}).get("running"):
                tasks_to_resume.append("👧 Girls Scraper")
            if d.get("banning", {}).get("running"):
                tasks_to_resume.append("🚫 Ban Review")
            for key in d:
                if key.startswith("rej_") and isinstance(d[key], dict) and d[key].get("running"):
                    tasks_to_resume.append(f"🔄 Rejoin ({key.split('_',1)[1]})")
            if tasks_to_resume:
                kb = [[InlineKeyboardButton("✅  Yes, Resume All", callback_data="resume_all")],
                      [InlineKeyboardButton("❌  No, Stop All", callback_data="resume_stop")]]
                await app.bot.send_message(
                    chat_id=uid,
                    text=(
                        "🤖  <b>Bot Restarted!</b>\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        "Detected these tasks were running before restart:\n\n"
                        + "\n".join(f"• {t}" for t in tasks_to_resume) +
                        "\n\nResume them?"
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(kb))
        except Exception as e:
            logger.error(f"Resume check for {f}: {e}")

async def scraper_help_cmd(update, context):
    if not is_authorized(update.effective_user.id): return
    await update.message.reply_text(
        "🧭  <b>SCRAPER STRUCTURE & FLOW</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "1. <b>Target & Delivery</b>\n"
        "   Set target (source) and delivery (destination)\n"
        "   groups. Both support public @username or\n"
        "   private <code>t.me/+...</code> invite links.\n\n"
        "2. <b>Dual Scrape Mode</b>\n"
        "   Mode A — Member List: If group shows members,\n"
        "   uses GetParticipantsRequest (200 per page).\n\n"
        "   Mode B — Message Scan: If member list hidden,\n"
        "   scans recent messages for unique senders.\n"
        "   1 msg = 1 user; duplicates ignored.\n"
        "   Fails? Skipped, moves to next.\n\n"
        "3. <b>Delivery to Group</b>\n"
        "   Each user sent one-by-one with User Gap delay\n"
        "   (e.g. 30s, 2m, 5m). Failed users auto-skipped.\n\n"
        "4. <b>Daily Limit</b>\n"
        "   Max users per day. Resets at midnight. 0 = unlimited.\n\n"
        "5. <b>Girls Scraper</b>\n"
        "   Multiple source groups, quantity setting.\n"
        "   Name Filter: matches if name ends with feminine\n"
        "   suffix (ika, ita, ina, devi, etc.).\n\n"
        "6. <b>CPU Throttling</b>\n"
        "   /proc/stat CPU load: <30% = 1.0x, 30-60% = scaled,\n"
        "   >60% = 2.5x delay. Auto-clear cache on startup.\n\n"
        "7. <b>Resume on Restart</b>\n"
        "   Checks user_data/*.json for running tasks\n"
        "   and asks to resume or stop them.",
        parse_mode=ParseMode.HTML)

async def adduser_cmd(update, context):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only the owner can add users."); return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /adduser <user_id>"); return
    try: new_uid = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID."); return
    if new_uid in AUTHORIZED_USERS:
        await update.message.reply_text(f"⚠️ User {new_uid} is already authorized."); return
    AUTHORIZED_USERS.add(new_uid); save_authorized_users()
    await update.message.reply_text(f"✅ Authorized user {new_uid} added.")
    log_activity(OWNER_ID, f"Added authorized user: {new_uid}")

async def removeuser_cmd(update, context):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only the owner can remove users."); return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /removeuser <user_id>"); return
    try: target = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID."); return
    if target not in AUTHORIZED_USERS:
        await update.message.reply_text(f"⚠️ User {target} is not authorized."); return
    AUTHORIZED_USERS.discard(target); save_authorized_users()
    await update.message.reply_text(f"✅ Removed user {target}.")
    log_activity(OWNER_ID, f"Removed authorized user: {target}")

async def listusers_cmd(update, context):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only the owner can list users."); return
    if not AUTHORIZED_USERS:
        txt = "📋  <b>Authorized Users</b>\n━━━━━━━━━━━━━━━━━━\n\nNo authorized users."
    else:
        lines = [f"•  <code>{u}</code>" for u in sorted(AUTHORIZED_USERS)]
        txt = "📋  <b>Authorized Users</b>\n━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(lines)
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

def _start_keep_alive():
    """Bind $PORT for Render health checks + self-ping public URL to avoid sleep."""
    port = os.environ.get("PORT")
    if not port:
        logger.info("PORT not set — keep-alive disabled (local mode)")
        return
    import threading
    import urllib.request
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class _Health(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/health", "/healthz"):
                body = b"ok"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    try:
        srv = ThreadingHTTPServer(("0.0.0.0", int(port)), _Health)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        logger.info(f"Keep-alive HTTP server on 0.0.0.0:{port}")
    except Exception as e:
        logger.error(f"Keep-alive server failed: {e}")

    ext = (os.environ.get("SELF_PING_URL")
           or os.environ.get("RENDER_EXTERNAL_URL")
           or os.environ.get("RENDER_WEB_URL") or "")
    if not ext and os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
        ext = "https://" + os.environ["RENDER_EXTERNAL_HOSTNAME"]
    url = (ext.rstrip("/") + "/health") if ext else f"http://127.0.0.1:{port}/health"
    interval = max(60, int(os.environ.get("SELF_PING_INTERVAL", "600")))

    def _pinger():
        while True:
            time.sleep(interval)
            try:
                with urllib.request.urlopen(url, timeout=15) as r:
                    r.read(1)
                logger.debug(f"self-ping ok {url}")
            except Exception as e:
                logger.warning(f"self-ping fail {url}: {e}")

    threading.Thread(target=_pinger, daemon=True).start()
    logger.info(f"Self-ping keep-alive started: {url} every {interval}s")


def main():
    _start_keep_alive()

    async def _post_init(application):
        application.create_task(check_resume_tasks(application))

    app = (Application.builder()
           .token(BOT_TOKEN)
           .post_init(_post_init)
           .build())

    auto_clear_cache()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("cleanup", cleanup_cmd))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("scraper_help", scraper_help_cmd))
    app.add_handler(CommandHandler("adduser", adduser_cmd))
    app.add_handler(CommandHandler("removeuser", removeuser_cmd))
    app.add_handler(CommandHandler("users", listusers_cmd))
    app.add_handler(CommandHandler("backup", backup_cmd))
    app.add_handler(CommandHandler("restore", restore_cmd))
    
    async def _bh(update, context):
        r = await button_handler(update, context)
        if r is not None:
            context.user_data['_state'] = r
            context.user_data['_auto_state'] = None
        return r

    app.add_handler(CallbackQueryHandler(_bh))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(MessageHandler(filters.PHOTO, message_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, message_handler))
    app.add_handler(ChatJoinRequestHandler(join_request_handler))
    app.add_handler(ChatMemberHandler(new_member_handler, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, group_text_handler))
    app.add_handler(MessageHandler(filters.PHOTO, group_text_handler))
    app.add_handler(MessageHandler(filters.Sticker.ALL, group_text_handler))

    logger.info("Bot started! Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
