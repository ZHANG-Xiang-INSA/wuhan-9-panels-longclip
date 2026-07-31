# -*- coding: utf-8 -*-
"""One HTML file that anybody can open, with the heavy assets streamed from GitHub Pages.

    python data/standalone_html.py    ->  dist/wuhan-9-panels.html

The site itself is not touched.  This reads the same site/ sources and writes a separate file
that can be attached to an email or dropped in a chat.

WHAT IS IN THE FILE AND WHAT IS NOT.  All the CODE goes in - three.js, its loaders, app.js and
the stylesheet, about 2.3 MB - so the page draws its own shell the instant it opens, with no
network at all.  All the DATA stays out: boards.json, the nine models, the renders, the drawings
and the downloads are fetched from https://zhang-xiang-insa.github.io/wuhan-9-panels/ as the page
needs them.  Embedding those too would mean base64, which inflates binary by a third and would put
the file past 25 MB.

WHY IT IS ALLOWED TO DO THAT.  A page opened from a file:// URL has an opaque origin, so every
request it makes to the site is cross-origin.  GitHub Pages answers with
`Access-Control-Allow-Origin: *` on every response - verified against the html, the json, a glb,
a script and a webp - and that header is the whole reason this works.  Take it away and the
browser blocks the lot.

HOW THE URLS GET REDIRECTED.  One `<base href>` in the head, rather than rewriting paths through
the code: `fetch('data/boards.json')`, GLTFLoader's own request for a .glb, `<img src>` and every
download link all resolve against the document base, so they all follow it at once.  The one thing
`<base>` breaks is the in-page anchors - `href="#model"` would resolve to the ONLINE page and
navigate away - so those are intercepted and scrolled by hand.

BUNDLING.  The vendor files are ES modules that import each other, and a module cannot be inlined
with its imports intact.  They are concatenated in dependency order with the import and export
statements stripped: every module's top-level declarations then share one scope, which is what
those imports were fetching anyway.  app.js asks for `import * as THREE`, so the namespace is
rebuilt as a plain object from the names app.js actually uses.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
SITE = os.path.join(ROOT, 'site')
OUT = os.path.join(ROOT, 'dist')
BASE = 'https://zhang-xiang-insa.github.io/wuhan-9-panels/'
REPO = 'https://github.com/ZHANG-Xiang-INSA/wuhan-9-panels'

# dependency order.  three.core holds the classes; three.module imports from it and adds the
# renderer; GLTFLoader needs a helper out of BufferGeometryUtils.
VENDOR = ['three.core.js', 'three.module.js', 'BufferGeometryUtils.js',
          'OrbitControls.js', 'RoomEnvironment.js', 'GLTFLoader.js']

read = lambda *p: open(os.path.join(*p), encoding='utf-8').read()


def strip_module(src, name):
    """drop the import and export statements, keep every declaration

    Both appear only as `import ... from '...';` and `export { ... };` in these files, checked
    before writing this - there is no `export const` or `export default` anywhere in them.
    """
    n_i = len(re.findall(r'(?m)^import\b', src))
    n_e = len(re.findall(r'(?m)^export\b', src))
    src = re.sub(r"(?ms)^import\s+(?:[\w*\s{},]+\s+from\s+)?['\"][^'\"]+['\"]\s*;?", '', src)
    src = re.sub(r"(?ms)^export\s*\{[^}]*\}\s*(?:from\s*['\"][^'\"]+['\"])?\s*;?", '', src)
    left = re.findall(r'(?m)^(?:import|export)\b.*', src)
    if left:
        raise SystemExit('%s: %d import/export lines not handled, first: %.90s'
                         % (name, len(left), left[0]))
    return '/* ==== %s (%d imports, %d exports stripped) ==== */\n%s' % (name, n_i, n_e, src)


DECL = re.compile(r'(?m)^(?:const|let|var|function|class)\s+([A-Za-z_$][\w$]*)')


def deconflict(src, name, taken):
    """rename any top-level declaration this module shares with an earlier one

    Flattening modules into one scope means two files cannot both declare a name.  three.core and
    three.module both have `_m1`, `_m1$1`, `_v0` and `_id`; GLTFLoader has its own `_quaternion`
    and `_identityMatrix`, OrbitControls its own `_ray`.  Every one is an internal temporary - none
    appears in any export list - so the later module's copy is renamed and the earlier one wins.

    The lookbehind keeps property access out of it: `foo._m1` is a different thing from the
    binding `_m1` and must not be touched.
    """
    mine = set(DECL.findall(src))
    hit = sorted(mine & taken)
    for n in hit:
        tag = re.sub(r'\W', '_', name.rsplit('/', 1)[-1].rsplit('.', 1)[0])
        src = re.sub(r'(?<![.$\w])%s(?![\w$])' % re.escape(n), '%s__%s' % (n, tag), src)
    taken |= mine
    return src, hit


def build():
    html = read(SITE, 'index.html')
    css = read(SITE, 'style.css')
    app = read(SITE, 'app.js')

    parts, taken, renamed = [], set(), []
    for v in VENDOR:
        src = strip_module(read(SITE, 'vendor', v), 'vendor/'+v)
        src, hit = deconflict(src, v, taken)
        renamed += [(v, n) for n in hit]
        parts.append(src)
    for v, n in renamed:
        print('   renamed %-14s in %s' % (n, v))

    # app.js asks for the whole namespace; rebuild it from the names it actually uses
    names = sorted(set(re.findall(r'THREE\.([A-Za-z_$][\w$]*)', app)))
    parts.append('/* ==== the THREE namespace app.js imports ==== */\nconst THREE = {%s};'
                 % ', '.join(names))
    # app.js goes in a scope of its own rather than into the shared one.  It has its own `fill`,
    # and chasing collisions by renaming MY code to suit a vendored library is the wrong way round;
    # the vendor files have to share a scope because they were importing from each other, app.js
    # only reads from it.  An async wrapper because app.js opens with a top-level await.
    parts.append('/* ==== app.js, in its own scope ==== */\n(async () => {\n%s\n})();'
                 % strip_module(app, 'app.js'))
    js = '\n'.join(parts)

    # ---- the page ---------------------------------------------------------------------
    html = html.replace('<link rel="stylesheet" href="style.css">',
                        '<style>\n%s\n</style>' % css)
    html = re.sub(r'(?s)<script type="importmap">.*?</script>\s*', '', html)
    html = html.replace('<script type="module" src="app.js"></script>', '')
    assert 'importmap' not in html and 'src="app.js"' not in html

    head = ('<base href="%s">\n'
            '<meta name="robots" content="noindex">\n' % BASE)
    html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n'+head, 1)

    boot = '''
<script>
/* app.js keeps the chosen board in the address bar with history.replaceState('#b3').  Relative to
   the <base> that resolves to an https URL, and a document whose origin is null - which is what a
   file:// page is - is not allowed to push a history entry for another origin, so it throws a
   SecurityError.  Unhandled, that killed the rest of start-up: the board cards drew and nothing
   after them did.  Nothing here depends on the address bar, so the two calls are made harmless.
   localStorage, which app.js uses to remember the language, works fine on file:// in Chromium,
   but it is wrapped too - Firefox can refuse it for opaque origins and it is not worth a crash. */
(function () {
  ['replaceState', 'pushState'].forEach(function (k) {
    var f = history[k];
    history[k] = function () { try { return f.apply(history, arguments); } catch (e) {} };
  });
  var ls = window.localStorage;
  try { ls.setItem('__t', '1'); ls.removeItem('__t'); } catch (e) {
    var mem = {};
    Object.defineProperty(window, 'localStorage', {value: {
      getItem: function (k) { return k in mem ? mem[k] : null; },
      setItem: function (k, v) { mem[k] = String(v); },
      removeItem: function (k) { delete mem[k]; }}});
  }
})();

/* Every download link is cross-origin here, because <base> sends it to the site while the page
   itself is file://.  The HTML spec makes a browser IGNORE the download attribute across origins,
   so a tap did not save the file - it NAVIGATED to it, replacing the app with a .svg or a .json
   and losing the viewer.  WebKit says so out loud: "The download attribute on anchor was ignored
   because its href URL has a different security origin."  Opened in a new tab instead, which both
   saves the file and leaves the page where it was. */
document.addEventListener('click', function (e) {
  var a = e.target.closest && e.target.closest('a[href]');
  if (!a || !a.hasAttribute('download')) return;
  var u;
  try { u = new URL(a.href, location.href); } catch (err) { return; }
  if (u.origin === location.origin) return;
  e.preventDefault();
  window.open(a.href, '_blank', 'noopener');
}, true);

/* <base> sends every relative URL to the site, which is the point - but it sends the in-page
   anchors there too, so a click on "Model" would leave for the online page instead of scrolling.
   Catch those and scroll. */
document.addEventListener('click', function (e) {
  var a = e.target.closest && e.target.closest('a[href]');
  if (!a) return;
  var h = a.getAttribute('href') || '';
  if (h.charAt(0) !== '#') return;
  var el = document.querySelector(h);
  if (!el) return;
  e.preventDefault();
  el.scrollIntoView({behavior: 'smooth', block: 'start'});
});

/* If the assets cannot be reached - no connection, or GitHub blocked - the page would sit there
   half-drawn with no explanation.  Say so instead. */
(function () {
  var shown = false;
  function warn(msg) {
    if (shown) return;
    shown = true;
    var d = document.createElement('div');
    d.setAttribute('style', 'position:fixed;left:0;right:0;top:0;z-index:9999;padding:14px 18px;'
      + 'background:#8a2f1c;color:#fff;font:14px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif');
    d.innerHTML = msg;
    document.body.appendChild(d);
  }
  window.__wuhanWarn = warn;
  /* HEAD, not GET: app.js fetches this file for real a moment later, and a second GET was
     pulling the whole 250 KB again just to find out whether the network was there. */
  fetch('data/boards.json', {method: 'HEAD', cache: 'no-store'}).catch(function () {
    warn('\\u65e0\\u6cd5\\u8bfb\\u53d6\\u6570\\u636e\\u3002\\u8fd9\\u4e2a\\u6587\\u4ef6\\u9700\\u8981'
       + '\\u8054\\u7f51\\uff0c\\u4ece GitHub \\u53d6\\u6a21\\u578b\\u4e0e\\u56fe\\u7eb8\\uff1b'
       + '\\u8bf7\\u786e\\u8ba4\\u7f51\\u7edc\\u53ef\\u4ee5\\u8bbf\\u95ee '
       + '<a style="color:#ffd9cf" href="' + BASEURL + '">' + BASEURL + '</a>\\u3002'
       + '&nbsp;&nbsp;Could not load the data. This file needs a connection: the models and '
       + 'drawings come from GitHub. Check that the address above is reachable.');
  });
})();
</script>
'''.replace('BASEURL', "'%s'" % BASE)

    html = html.replace('</body>', boot + '<script type="module">\n' + js
                        + '\n</script>\n</body>')

    os.makedirs(OUT, exist_ok=True)
    q = os.path.join(OUT, 'wuhan-9-panels.html')
    open(q, 'w', encoding='utf-8').write(html)
    print('-> %s' % os.path.normpath(q))
    print('   %.2f MB   (css %.0f KB, app %.0f KB, vendor %.1f MB)'
          % (os.path.getsize(q)/1048576, len(css)/1024, len(app)/1024,
             sum(len(read(SITE, 'vendor', v)) for v in VENDOR)/1048576))
    print('   assets stream from %s' % BASE)
    return q


if __name__ == '__main__':
    build()
