import re, subprocess
from pathlib import Path
from .ffmpeg import FFMPEG
from .ui import warn

# CAPTIONS — word alignment + rendered highlight cards

CAPTION_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/Library/Fonts/Arial Black.ttf",
    str(Path.home() / "Library/Fonts/Arial Black.ttf"),
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
CAPTION_STYLE     = "plate"     # "plate" = highlighted word on a coloured plate, "text" = coloured word
CAPTION_ACCENT    = "#FFD93B"
CAPTION_COLOR_MODE = "shuffle"  # "shuffle" = a different highlight colour on each caption card, "fixed" = CAPTION_ACCENT
CAPTION_PALETTE   = ["#FFD93B", "#5CF28E", "#4FD8FF", "#FF6FB5", "#FF9A3C", "#B69CFF"]  # yellow, green, cyan, pink, orange, lilac
CAPTION_LEAD_CARD = 0.10        # seconds a new caption card appears before its first word is spoken
CAPTION_LEAD_WORD = 0.04        # seconds the highlight moves onto a word before it is spoken
CAPTION_MAX_WORDS = 5
CAPTION_MAX_CHARS = 32
CAPTION_MAX_W     = 940         # px, inside the 1080 frame (Shorts side buttons live on the right)
CAPTION_CANVAS    = (1080, 400)
CAPTION_TOP       = 1230        # y of the card canvas on the 1920 frame → text sits ~y1430, above the Shorts UI

def _word_weight(w):
    letters = re.sub(r"[^A-Za-z0-9]", "", w)
    return max(1, len(re.findall(r"[aeiouy]+", letters.lower()))) + 0.25 * len(letters)

def _speech_profile(wav_path):
    """Return (speech_start, speech_end, gaps[(start, end)]) measured from the real audio."""
    import numpy as np
    r = subprocess.run([FFMPEG, "-v", "error", "-i", str(wav_path), "-f", "s16le", "-ac", "1",
                        "-ar", "16000", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    hop, win = 160, 320                       # 10 ms hop, 20 ms window
    frames = np.lib.stride_tricks.sliding_window_view(x, win)[::hop]
    rms    = np.sqrt((frames ** 2).mean(axis=1))
    thr    = max(0.004, 0.08 * float(np.percentile(rms, 90)))
    idx    = np.where(rms > thr)[0]
    if len(idx) == 0:
        raise ValueError("no speech detected")
    first, last = int(idx[0]), int(idx[-1])
    gaps, run = [], None
    for i in range(first, last + 1):
        if rms[i] <= thr:
            run = i if run is None else run
        elif run is not None:
            if i - run >= 9:                  # ≥ 90 ms of silence inside speech
                gaps.append((run * 0.01, i * 0.01))
            run = None
    return first * 0.01, (last + 1) * 0.01, gaps

def _align_heuristic(text, wav_path):
    """Estimate (word, start, end) for each word by pinning punctuation to the audio's real pauses.
    Independent of any transcription API (whisper-1 is being retired); words between two
    detected pauses are spread by syllable-ish weight."""
    words = text.split()
    n = len(words)
    try:
        t0, t1, gaps = _speech_profile(wav_path)
    except Exception:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                    "default=nw=1:nk=1", str(wav_path)], capture_output=True, text=True).stdout or 3)
        t0, t1, gaps = 0.0, max(0.5, dur - 0.12), []

    W      = [_word_weight(w) for w in words]
    pause  = [0.32 if w[-1] in ".?!।" else 0.16 if w[-1] in ",;:" else 0.0 for w in words]
    pause[-1] = 0.0
    speech_time = max(0.3, (t1 - t0) - sum(pause))
    rate   = sum(W) / speech_time             # weight units per second

    # Pure-estimate word starts (used to predict where each punctuation pause should fall).
    start, acc = [], t0
    for i in range(n):
        start.append(acc)
        acc += W[i] / rate + pause[i]
    bounds = [i for i in range(n - 1) if pause[i] > 0]
    pred   = [start[i + 1] - pause[i] / 2 for i in bounds]

    # Monotonic matching of punctuation boundaries → detected gaps (DP, small sizes).
    B, G, INF, SKIP = len(bounds), len(gaps), 1e9, 0.5
    dp = [[INF] * (G + 1) for _ in range(B + 1)]
    bk = [[None] * (G + 1) for _ in range(B + 1)]
    for j in range(G + 1):
        dp[0][j] = 0.0
    for b in range(1, B + 1):
        for j in range(G + 1):
            best, how = dp[b - 1][j] + SKIP, "skipb"
            if j > 0:
                if dp[b][j - 1] < best:
                    best, how = dp[b][j - 1], "skipg"
                d = abs(pred[b - 1] - (gaps[j - 1][0] + gaps[j - 1][1]) / 2)
                if d < 1.0 and dp[b - 1][j - 1] + d < best:
                    best, how = dp[b - 1][j - 1] + d, "match"
            dp[b][j], bk[b][j] = best, how
    matched, b, j = {}, B, G
    while b > 0:
        how = bk[b][j]
        if how == "match":
            matched[bounds[b - 1]] = gaps[j - 1]; b -= 1; j -= 1
        elif how == "skipg":
            j -= 1
        else:
            b -= 1

    # Walk the words in segments delimited by matched pauses; spread each segment by weight.
    out, seg_start, i = [], t0, 0
    while i < n:
        j = i
        while j < n - 1 and j not in matched:
            j += 1
        seg_end = matched[j][0] if j in matched else t1
        ws = [W[k] + (pause[k] * rate if (k != j and k in bounds) else 0.0) for k in range(i, j + 1)]
        total, t = sum(ws), seg_start
        for k, wk in zip(range(i, j + 1), ws):
            share = (seg_end - seg_start) * wk / total
            out.append([words[k], t, t + share]); t += share
        seg_start = matched[j][1] if j in matched else t1
        i = j + 1
    for k in range(n - 1):                    # a word stays "active" until the next one starts
        out[k][2] = out[k + 1][1]
    return [tuple(o) for o in out]

_FA = {}

def _load_forced_aligner():
    """torchaudio's MMS_FA model (built for forced alignment; ~1.2 GB, downloaded once and cached)."""
    if "model" not in _FA:
        import torchaudio
        bundle = torchaudio.pipelines.MMS_FA
        _FA["model"] = bundle.get_model(with_star=False).eval()
        _FA["dict"]  = bundle.get_dict(star=None)
    return _FA["model"], _FA["dict"]

def _align_forced(text, wav_path):
    """Word timings by CTC forced alignment of the known script against the real audio (~30-50 ms accurate).
    Runs locally: no API call, nothing to be retired. Raises if torch/torchaudio are missing."""
    import numpy as np, torch, torchaudio
    model, dic = _load_forced_aligner()
    words = text.split()
    clean = [re.sub(r"[^a-z']", "", w.lower()) for w in words]
    idx   = [i for i, c in enumerate(clean) if c]
    if len(idx) < max(2, len(words) // 2):
        raise ValueError("too few alignable words")
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(wav_path), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True).stdout
    wav = torch.from_numpy(np.frombuffer(raw, dtype=np.float32).copy()).unsqueeze(0)
    with torch.inference_mode():
        emission, _ = model(wav)
    targets = torch.tensor([[dic[ch] for i in idx for ch in clean[i]]], dtype=torch.int32)
    aligned, scores = torchaudio.functional.forced_align(emission, targets, blank=0)
    spans  = torchaudio.functional.merge_tokens(aligned[0], scores[0].exp())
    stride = wav.shape[1] / emission.shape[1] / 16000
    got, k = {}, 0
    for i in idx:
        n = len(clean[i]); sp = spans[k:k + n]; k += n
        got[i] = (sp[0].start * stride, sp[-1].end * stride)

    total = wav.shape[1] / 16000
    out = [[w, *(got[i] if i in got else (None, None))] for i, w in enumerate(words)]
    for i, o in enumerate(out):                       # digits etc. with no letters: share the time between neighbours
        if o[1] is None:
            j = i
            while j < len(out) and out[j][1] is None:
                j += 1
            left  = out[i - 1][2] if i > 0 else 0.0
            right = out[j][1] if j < len(out) else total
            step  = (right - left) / (j - i + 1)
            for m in range(i, j):
                out[m][1], out[m][2] = left + step * (m - i), left + step * (m - i + 1)
    try:                                              # safety net: no word may start inside a real silence
        _, _, gaps = _speech_profile(wav_path)
        for g0, g1 in gaps:
            for o in out:
                if g0 + 0.05 < o[1] < g1 - 0.03:
                    o[1] = g1
    except Exception:
        pass
    for k in range(len(out) - 1):                     # a word stays "active" until the next one starts
        out[k][2] = max(out[k + 1][1], out[k][1] + 0.05)
    return [tuple(o) for o in out]

_ALIGN_WARNED = False

def align_words(text, wav_path, roman=None):
    """Forced alignment when torch/torchaudio are available, otherwise the pause-anchored estimate.
    `roman`: for non-Latin scripts, the same words in Latin letters (one per word), used only for timing."""
    global _ALIGN_WARNED
    try:
        if roman and len(roman.split()) == len(text.split()):
            timed = _align_forced(roman, wav_path)
            return [(w, a, b) for w, (_r, a, b) in zip(text.split(), timed)]
        return _align_forced(text, wav_path)
    except Exception as e:
        if not _ALIGN_WARNED:
            warn(f"Forced alignment unavailable ({type(e).__name__}: {str(e)[:80]}) — using estimated caption timing")
            _ALIGN_WARNED = True
        return _align_heuristic(text, wav_path)

def group_cards(words):
    """Caption cards of up to CAPTION_MAX_WORDS words / CAPTION_MAX_CHARS characters.
    A card never spans a sentence end (so cards line up with the picture changes), and a long sentence is
    cut into even pieces, preferably right after a comma, instead of leaving a 1-word straggler."""
    sentences, cur = [], []
    for w in words:
        cur.append(w)
        if w[0][-1] in ".?!।":
            sentences.append(cur); cur = []
    if cur:
        sentences.append(cur)

    def chars(ws):
        return sum(len(x[0]) + 1 for x in ws) - 1

    cards = []
    for s in sentences:
        n = len(s)
        for k in range(1, n + 1):                                    # fewest pieces that all fit
            base, extra = divmod(n, k)
            sizes = [base + (1 if i < extra else 0) for i in range(k)]
            cuts, acc = [], 0
            for sz in sizes[:-1]:
                acc += sz
                cuts.append(acc)
            for ci, cut in enumerate(cuts):                          # nudge a cut to sit right after a comma if one is adjacent
                lo = (cuts[ci - 1] if ci else 0) + 1
                hi = (cuts[ci + 1] if ci + 1 < len(cuts) else n) - 1
                for cand in (cut, cut - 1, cut + 1):
                    if lo <= cand <= hi and s[cand - 1][0][-1] in ",;:":
                        cuts[ci] = cand
                        break
            pieces = [s[a:b] for a, b in zip([0] + cuts, cuts + [n])]
            if all(len(p) <= CAPTION_MAX_WORDS and chars(p) <= CAPTION_MAX_CHARS for p in pieces) or k == n:
                cards += pieces
                break
    return cards

def find_caption_font():
    return next((f for f in CAPTION_FONTS if Path(f).exists()), None)

def _font(size):
    from PIL import ImageFont
    path = find_caption_font()
    try:
        return ImageFont.truetype(path, size) if path else ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default(size)


# ── Text that Pillow cannot shape (Hindi etc.): drawn with macOS CoreText instead ──────────────────
_CT_FONT = "KohinoorDevanagari-Bold"
_ct_cache = {}
_ct_lock  = __import__("threading").Lock()     # pyobjc's lazy symbol loading is not thread-safe; clips render in threads

def _shaped(label):
    return any(ord(ch) > 0x7F for ch in label)

def _ct_mask(label, size):
    """(mask 'L' image, advance, baseline_y_in_mask, pad) for `label` shaped by CoreText."""
    key = (label, size)
    with _ct_lock:
        if key not in _ct_cache:
            _ct_cache[key] = _ct_render(label, size)
        return _ct_cache[key]

def _ct_render(label, size):
    import CoreText as CT, Quartz as Q
    from Foundation import NSAttributedString
    from PIL import Image
    font = CT.CTFontCreateWithName(_CT_FONT, size * 0.95, None)
    astr = NSAttributedString.alloc().initWithString_attributes_(
        label, {CT.kCTFontAttributeName: font, CT.kCTForegroundColorFromContextAttributeName: True})
    line = CT.CTLineCreateWithAttributedString(astr)
    adv, asc, desc, _ = CT.CTLineGetTypographicBounds(line, None, None, None)
    pad = 4
    w, h = int(adv) + 2 * pad + 2, int(asc + desc) + 2 * pad + 2
    buf = bytearray(w * h)
    ctx = Q.CGBitmapContextCreate(buf, w, h, 8, w, Q.CGColorSpaceCreateDeviceGray(), Q.kCGImageAlphaNone)
    Q.CGContextSetGrayFillColor(ctx, 1.0, 1.0)
    Q.CGContextSetTextPosition(ctx, pad, pad + desc)
    CT.CTLineDraw(line, ctx)
    img = Image.frombuffer("L", (w, h), bytes(buf), "raw", "L", 0, 1)      # the buffer is already top row first
    return (img, adv, pad + asc, pad)

def _tw(d, label, f, size):
    """Width of a label in px, shaped or not."""
    return _ct_mask(label, size)[1] if _shaped(label) else d.textlength(label, font=f)

def _draw(layer, d, x, base, label, f, size, fill, stroke_w=0, stroke_fill=None):
    """Draw a label with its baseline at `base` on `layer` (d is ImageDraw of layer)."""
    if not _shaped(label):
        kw = {"stroke_width": stroke_w, "stroke_fill": stroke_fill} if stroke_w else {}
        d.text((x, base), label, font=f, fill=fill, anchor="ls", **kw)
        return
    from PIL import Image, ImageFilter
    mask, _adv, base_in, pad = _ct_mask(label, size)
    ox, oy = int(round(x)) - pad, int(round(base - base_in))
    if stroke_w:
        grown = mask.filter(ImageFilter.MaxFilter(2 * max(1, stroke_w // 3) + 1))   # thinner outline: Indic strokes are fine
        layer.paste(Image.new("RGBA", mask.size, stroke_fill), (ox, oy), grown)
    layer.paste(Image.new("RGBA", mask.size, fill), (ox, oy), mask)

def _layout(labels):
    """Pick the largest font size where the card fits in ≤2 balanced lines. Returns (size, [[idx..], ..])."""
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    for size in (84, 78, 72, 66, 60, 54):
        f     = _font(size)
        space = d.textlength(" ", font=f)
        wid   = [_tw(d, t, f, size) for t in labels]
        def width(ix): return sum(wid[k] for k in ix) + space * (len(ix) - 1)
        allw = list(range(len(labels)))
        if width(allw) <= CAPTION_MAX_W and len(labels) <= 3:
            return size, [allw]
        best = None
        for cut in range(1, len(labels)):
            a, b = allw[:cut], allw[cut:]
            m = max(width(a), width(b))
            if best is None or m < best[0]:
                best = (m, [a, b])
        if best and best[0] <= CAPTION_MAX_W:
            return size, best[1]
    return 54, [allw[:len(allw) // 2 or 1], allw[len(allw) // 2 or 1:]] if len(allw) > 1 else [allw]

def render_card(card, active, path, color=CAPTION_ACCENT):
    """Render one caption state (all words visible, word #active highlighted) to a transparent PNG."""
    from PIL import Image, ImageDraw, ImageFilter
    labels = [w[0].upper().rstrip(",.;:") for w in card]
    size, lines = _layout(labels)
    f      = _font(size)
    W, H   = CAPTION_CANVAS
    d0     = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    space  = d0.textlength(" ", font=f)
    lh     = int(size * 1.22)
    top    = (H - lh * len(lines)) // 2
    plates, texts = [], []
    for li, ix in enumerate(lines):
        widths = [_tw(d0, labels[k], f, size) for k in ix]
        x      = (W - (sum(widths) + space * (len(ix) - 1))) / 2
        base   = top + li * lh + int(size * 0.9)
        for k, wd in zip(ix, widths):
            texts.append((k, x, base, wd))
            x += wd + space
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    plate  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    main   = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds, dp_, dm = ImageDraw.Draw(shadow), ImageDraw.Draw(plate), ImageDraw.Draw(main)
    for k, x, base, wd in texts:
        is_act = (k == active)
        _draw(shadow, ds, x, base + 7, labels[k], f, size, (0, 0, 0, 200), 9, (0, 0, 0, 200))
        if is_act and CAPTION_STYLE == "plate":
            pad = int(size * 0.16)
            dp_.rounded_rectangle((x - pad, base - size * 0.86 - pad * 0.3, x + wd + pad, base + size * 0.22 + pad * 0.3),
                                  radius=int(size * 0.24), fill=color)
            _draw(main, dm, x, base, labels[k], f, size, "#14141c")
        elif is_act:
            _draw(main, dm, x, base, labels[k], f, size, color, 8, "black")
        else:
            _draw(main, dm, x, base, labels[k], f, size, "white", 8, "black")
    shadow = shadow.filter(ImageFilter.GaussianBlur(4))
    out = Image.alpha_composite(Image.alpha_composite(shadow, plate), main)
    if path is not None:
        out.save(path)
    return out

def caption_events(words, speech_end):
    """Return (card_index, card, active_word_index, t_start, t_end) for every highlight state."""
    # Captions lead the voice slightly: a caption that appears a beat early is invisible to the viewer,
    # one that appears late reads as lag. Each state runs until the next state starts (no gaps, no overlaps).
    events = []
    cards  = group_cards(words)
    starts = [[max(0.0, w[1] - (CAPTION_LEAD_CARD if wi == 0 else CAPTION_LEAD_WORD)) for wi, w in enumerate(card)]
              for card in cards]
    for ci, card in enumerate(cards):
        card_end = starts[ci + 1][0] if ci + 1 < len(cards) else speech_end + 0.1
        for wi, w in enumerate(card):
            a = starts[ci][wi]
            b = starts[ci][wi + 1] if wi + 1 < len(card) else card_end
            events.append((ci, card, wi, a, max(b, a + 0.05)))
    return events
