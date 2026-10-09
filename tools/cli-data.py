#!/usr/bin/env python3
"""tools/cli-data.py APP_CHECKOUT [DOZ] — regenerate cli-commands.json (the CLI section's terminal) from the app repo.

For every command in APP_CHECKOUT/Scripts/docs-known-commands.txt (the list the app's docs check against the real
CLI): its one-line description = the first sentence of `doz <command> --help`'s OVERVIEW (the command's own help),
and the manual page = the page of APP_CHECKOUT/docs/manual/ that shows `doz <command>` most. DOZ defaults to
APP_CHECKOUT/.build/debug/doz (make cli). Then run tools/stamp.sh."""
import glob, json, os, re, subprocess, sys

app = os.path.abspath(sys.argv[1])
doz = sys.argv[2] if len(sys.argv) > 2 else os.path.join(app, '.build/debug/doz')
MANUAL = 'https://dozersandbox.com/docs/'   # the manual's pages on the site (tools/docs-build.py): NN-slug.md -> slug.html
page_url = lambda md: MANUAL + re.sub(r'^\d+-', '', md)[:-3] + '.html'
names = [l.strip().replace('/', ' ') for l in open(os.path.join(app, 'Scripts/docs-known-commands.txt'))
         if l.strip() and not l.startswith('#')]
pages = sorted(glob.glob(os.path.join(app, 'docs/manual/[0-9]*.md')))
texts = {p: open(p, encoding='utf-8').read() for p in pages}

def describe(cmd):
    out = subprocess.run([doz, *cmd.split(), '--help'], capture_output=True, text=True,
                         env={**os.environ, 'NO_COLOR': '1'}).stdout
    m = re.search(r'OVERVIEW: (.*?)(?:\n\n|$)', out, re.S)
    text = ' '.join(m.group(1).split()) if m else ''
    s = re.match(r'(.+?[.!?])(\s|$)', text)
    return (s.group(1) if s else text).strip()

# The manual is organised by command group: a group's chapter is its home (counting is the fallback).
HOME = {
    'serve': '25-doz-serve.md', 'account': '09-agents-and-accounts.md', 'key': '09-agents-and-accounts.md',
    'access': '09-agents-and-accounts.md', 'point': '12-restore-points-duplicates-templates.md',
    'template': '12-restore-points-duplicates-templates.md', 'duplicate': '12-restore-points-duplicates-templates.md',
    'net': '10-permissions-and-network.md', 'config': '15-settings-reference.md', 'image': '08-images-and-bases.md',
    'base': '08-images-and-bases.md', 'builder': '08-images-and-bases.md', 'ui': '06-the-dashboard.md',
    'resources': '13-resources-and-disk-space.md', 'sessions': '07-terminals-and-sessions.md',
    'attach': '07-terminals-and-sessions.md', 'run': '07-terminals-and-sessions.md', 'exec': '07-terminals-and-sessions.md',
    'console': '07-terminals-and-sessions.md', 'ignore': '20-workspace-rules.md', 'tools': '19-the-tools-layer.md',
    'host': '05-sandboxes-and-lifecycle.md', 'onboard': '03-setting-up.md', 'init': '04-projects.md', 'up': '04-projects.md',
    'new': '05-sandboxes-and-lifecycle.md', 'create': '05-sandboxes-and-lifecycle.md', 'start': '05-sandboxes-and-lifecycle.md',
    'pause': '05-sandboxes-and-lifecycle.md', 'resume': '05-sandboxes-and-lifecycle.md', 'sleep': '05-sandboxes-and-lifecycle.md',
    'hibernate': '05-sandboxes-and-lifecycle.md', 'wake': '05-sandboxes-and-lifecycle.md', 'shutdown': '05-sandboxes-and-lifecycle.md',
    'reset': '05-sandboxes-and-lifecycle.md', 'rm': '05-sandboxes-and-lifecycle.md', 'ls': '05-sandboxes-and-lifecycle.md',
    'inspect': '05-sandboxes-and-lifecycle.md', 'upgrade': '02-install-upgrade-uninstall.md',
    'uninstall': '02-install-upgrade-uninstall.md', 'doctor': '17-troubleshooting-and-faq.md',
}

def manual(cmd):
    home = HOME.get(cmd.split()[0])
    if home and os.path.exists(os.path.join(app, 'docs/manual', home)):
        return page_url(home)
    """The page that shows the command MOST (its home page, not the getting-started tour); the earlier page on a tie."""
    pat = re.compile(r'doz %s(?![\w-])' % re.escape(cmd))
    # The two pages of example scripts for agents show many commands in passing — a command's home is elsewhere
    # whenever another page shows it at all.
    examples = ('14-letting-another-agent-drive.md', '22-prompts-for-your-agent.md')
    counts = [(os.path.basename(p) not in examples and len(pat.findall(texts[p])) > 0, len(pat.findall(texts[p])), -i, p)
              for i, p in enumerate(pages)]
    best = max(counts)
    return page_url(os.path.basename(best[3])) if best[1] else MANUAL


data = [{'cmd': 'doz ' + n, 'desc': describe(n), 'manual': manual(n)} for n in names]
missing = [d['cmd'] for d in data if not d['desc']]
json.dump(data, open('cli-commands.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print(f'cli-commands.json: {len(data)} commands, {len(missing)} without a description {missing[:5]}')
