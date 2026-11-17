import re, unicodedata

ZERO_WIDTH=re.compile(r'[\u200b-\u200f\u2060\ufeff]')
LINKS=(
 re.compile(r'(?i)\b(?:https?|ftp)\s*:\s*/\s*/|\bwww\s*[.]|\b(?:discord[.]gg|t[.]me)\b'),
 re.compile(r'(?i)\[[^\]]+\]\s*\([^)]*\)|\b[\w.+-]+\s*@\s*[\w-]+\s*[.]\s*[a-z]{2,}\b'),
 re.compile(r'(?i)\b(?:\d{1,3}\s*[.]\s*){3}\d{1,3}\b'),
 re.compile(r'(?i)\b[a-z0-9äöüß-]{1,63}(?:\s*(?:[.]|\(dot\)|\[dot\]|punkt)\s*[a-z0-9äöüß-]{1,63})+\b'),
)
BLOCKED=(
 'arschloch','hurensohn','hure','wichser','wixer','fotze','bastard','missgeburt','spast','spasti',
 'behindert','schlampe','idiot','vollidiot','dummkopf','depp','opfer','kanake','nigger','neger',
 'schwuchtel','fag','faggot','kike','retard','nutte','verpiss','fick','fuck','bitch','cunt',
)
WORDS=re.compile(r'(?i)(?<!\w)('+('|'.join(re.escape(w) for w in sorted(BLOCKED,key=len,reverse=True)))+r')(?!\w)')
LEET=str.maketrans({'0':'o','1':'i','3':'e','4':'a','5':'s','7':'t','$':'s','!':'i'})

def clean(value,limit=300):
 text=ZERO_WIDTH.sub('',unicodedata.normalize('NFKC',str(value)))
 return ' '.join(text.split())[:limit]

def has_link(text):
 decoded=text.replace('%2e','.').replace('%2E','.').replace('%2f','/').replace('%2F','/')
 return any(pattern.search(decoded) for pattern in LINKS)

def moderate_message(value):
 text=clean(value)
 if not text: raise ValueError('Nachricht ist leer')
 if has_link(text): raise ValueError('Links sind im Chat nicht erlaubt')
 masked=WORDS.sub(lambda m:'•'*len(m.group(0)),text)
 compact=re.sub(r'[^a-zäöüß]','',text.lower().translate(LEET))
 if any(word in compact for word in BLOCKED) and masked==text:
  raise ValueError('Diese Formulierung wird vom Wortfilter blockiert')
 return masked

def moderate_name(value):
 text=clean(value,24)
 if not text: raise ValueError('Bitte einen Namen eingeben')
 if has_link(text): raise ValueError('Links sind auch als Name nicht erlaubt')
 if WORDS.search(text) or any(word in re.sub(r'[^a-zäöüß]','',text.lower().translate(LEET)) for word in BLOCKED):
  raise ValueError('Dieser Name wird vom Wortfilter blockiert')
 return text
