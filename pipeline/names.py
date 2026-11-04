"""Name helpers for matching the same person across FEC, Wikipedia, CAWP, Pettigrew and congress-legislators."""
import difflib
import re
import unicodedata

SUFFIX = {"jr", "sr", "ii", "iii", "iv", "v", "md", "phd", "esq", "dr"}


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return s.lower()


def tokens(s):
    s = fold(s)
    s = re.sub(r"\([^)]*\)", " ", s)          # (nicknames) and notes
    s = re.sub(r"\"[^\"]*\"", " ", s)
    s = re.sub(r"[^a-z' \-.,]", " ", s)
    return [t for t in re.split(r"[\s.]+", s) if t and t.strip(",") not in SUFFIX]


def split_name(s):
    """-> (first, last, all tokens). Handles 'Last, First Middle' and 'First Middle Last'."""
    s = str(s or "").strip()
    s = re.sub(r"\s*\((?:i|incumbent)\)\s*", " ", s, flags=re.I)
    if "," in s:
        last, rest = s.split(",", 1)
        lt = [t for t in tokens(last) if t.strip(",")]
        rt = [t.strip(",") for t in tokens(rest) if t.strip(",") and t.strip(",") not in SUFFIX]
        first = rt[0] if rt else ""
        return first, " ".join(t.strip(",") for t in lt), lt + rt
    t = [x.strip(",") for x in tokens(s)]
    t = [x for x in t if x]
    if not t:
        return "", "", []
    return t[0], t[-1], t


def nick(n):
    groups = [{"william", "bill", "billy", "will"}, {"robert", "bob", "rob", "bobby"}, {"james", "jim", "jimmy"},
              {"richard", "rick", "dick", "rich"}, {"elizabeth", "liz", "lizzie", "lizzy", "beth", "betsy", "betty", "eliza", "lisa", "libby"},
              {"katherine", "kathryn", "catherine", "kathy", "kate", "katie", "cathy"}, {"margaret", "maggie", "peggy", "marge"},
              {"patricia", "pat", "patty", "trish"}, {"jennifer", "jen", "jenny"}, {"deborah", "debra", "debbie", "deb"},
              {"susan", "sue", "suzanne", "suzan"}, {"christopher", "chris"}, {"christine", "christina", "chris", "tina"},
              {"thomas", "tom", "tommy"}, {"michael", "mike"}, {"joseph", "joe"}, {"anthony", "tony"}, {"daniel", "dan", "danny"},
              {"david", "dave"}, {"steven", "stephen", "steve"}, {"edward", "ed", "eddie", "ted"}, {"charles", "chuck", "charlie"},
              {"kimberly", "kim"}, {"constance", "connie"}, {"dorothy", "dottie", "dot"}, {"frances", "fran"}, {"judith", "judy"}, {"carolyn", "carol"}, {"jo ann", "joann", "jo"}, {"virginia", "ginny"}, {"suzanne", "suzy"}, {"sandra", "sandy"}, {"pamela", "pam"}, {"madeleine", "madeline", "maddie"}, {"marjorie", "margie"}, {"rebecca", "becky", "becca"}, {"barbara", "barb"}, {"nancy", "nan"}, {"cynthia", "cindy"},
              {"theresa", "teresa", "terri", "terry"}, {"victoria", "vicki", "vicky"}, {"jacqueline", "jackie"}, {"alexandria", "alex", "alexandra"},
              {"samantha", "sam"}, {"gregory", "greg"}, {"donald", "don"}, {"ronald", "ron"}, {"kenneth", "ken"}, {"lawrence", "larry"},
              {"gerald", "jerry"}, {"timothy", "tim"}, {"matthew", "matt"}, {"andrew", "andy", "drew"}, {"nicholas", "nick"},
              {"benjamin", "ben"}, {"frederick", "fred"}, {"leonard", "len"}, {"raymond", "ray"}, {"douglas", "doug"}, {"jeffrey", "jeff"}]
    out = {n}
    for g in groups:
        if n in g:
            out |= g
    return out


def first_ok(fa, fb, strict):
    if not fa or not fb:
        return False
    if nick(fa) & nick(fb):
        return True
    if len(fa) == 1 or len(fb) == 1:
        return fa[0] == fb[0]
    if strict:
        return len(fa) >= 3 and len(fb) >= 3 and (fa.startswith(fb) or fb.startswith(fa))
    return fa[0] == fb[0]


def score(a, b, strict=False):
    """0 (different) .. 3 (same last name and first name/nickname). strict: first names must agree beyond the initial
    (Jane/John Smith do not match), or another given name must appear in both."""
    fa, la, ta = split_name(a)
    fb, lb, tb = split_name(b)
    if not la or not lb:
        return 0
    ja, jb = re.sub(r"[^a-z]", "", la), re.sub(r"[^a-z]", "", lb)
    sa, sb = set(re.sub(r"[^a-z ]", " ", " ".join(ta)).split()), set(re.sub(r"[^a-z ]", " ", " ".join(tb)).split())
    s = 0.0
    if ja == jb:
        s = 2
    elif ja and jb and (ja in re.sub(r"[^a-z]", "", " ".join(tb)) or jb in re.sub(r"[^a-z]", "", " ".join(ta))):
        s = 1.5
    elif set(re.split(r"[-' ]", la)) & set(re.split(r"[-' ]", lb)) - {""}:
        s = 1.2
    elif ja and jb and len(ja) >= 4 and difflib.SequenceMatcher(None, ja, jb).ratio() >= 0.8:
        s = 1.0  # spelling slip (e.g. Norcoss / Norcross); needs a first-name match to count
    else:
        return 0
    if first_ok(fa, fb, strict) or (fa and fa in sb and len(fa) > 1) or (fb and fb in sa and len(fb) > 1):
        s += 1
    return s


def best(name, candidates, min_score=2, strict=False):
    """index of the best-matching name in candidates (list of strings) or None"""
    sc = [(score(name, c, strict), i) for i, c in enumerate(candidates)]
    sc = [x for x in sc if x[0] >= min_score]
    if not sc:
        return None
    sc.sort(reverse=True)
    if len(sc) > 1 and sc[0][0] == sc[1][0]:
        return None  # ambiguous
    return sc[0][1]


def same_person(a, b):
    """stricter test used before labelling someone a woman: last names agree (allowing a one-letter slip) and
    first names agree (nickname, prefix, or initial when one side only has an initial)"""
    fa, la, ta = split_name(a)
    fb, lb, tb = split_name(b)
    if not la or not lb:
        return False
    ja, jb = re.sub(r"[^a-z]", "", la), re.sub(r"[^a-z]", "", lb)
    whole_a, whole_b = re.sub(r"[^a-z]", "", " ".join(ta)), re.sub(r"[^a-z]", "", " ".join(tb))
    last_ok = ja == jb or (len(ja) >= 4 and ja in whole_b) or (len(jb) >= 4 and jb in whole_a) or \
        bool(set(re.split(r"[-' ]", la)) & set(re.split(r"[-' ]", lb)) - {""})
    fuzzy = not last_ok and len(ja) >= 4 and difflib.SequenceMatcher(None, ja, jb).ratio() >= 0.75
    if not (last_ok or fuzzy):
        return False
    given_a = {t for t in ta if t not in (la,) and len(t) > 1}
    given_b = {t for t in tb if t not in (lb,) and len(t) > 1}
    if fuzzy:
        return bool(fa and fb and (nick(fa) & nick(fb)))
    return first_ok(fa, fb, strict=True) or bool(given_a & given_b - {ja, jb})
