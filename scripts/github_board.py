"""REL-02: GitHub issues, ownership board and branch protection from the task board.

The task board (QUALITYRELAY_18_1_TEAM_TASKS_EN.md) stays the source of truth; this mirrors its
open `- [ ] **ID ...**` items into one issue each, labelled and assigned to the section owner,
and adds them to a GitHub Project ("ownership board"). Idempotent: an issue whose title starts
with `[ID]` is never created twice.

  python scripts/github_board.py plan                       # dry run, no network
  python scripts/github_board.py apply  --repo OWNER/REPO   # labels + issues + project (needs `gh auth login`, scope: project)
  python scripts/github_board.py protect --repo OWNER/REPO  # branch protection on main (repo admin only)
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK_BOARD = ROOT / 'QUALITYRELAY_18_1_TEAM_TASKS_EN.md'
OWNERS = {'Bakdaulet': 'Bakdaulet-omeraiuly', 'adilnurgg': 'adilnurgg', 'HyorinmaruK': 'HyorinmaruK'}
LABELS = {  # name: (color, description)
    'P0': ('b60205', 'Must ship for the demo'), 'P1': ('d93f0b', 'Should ship'), 'P2': ('fbca04', 'Nice to have'),
    'task': ('1d76db', 'Task-board item'), 'bug': ('d73a4a', 'Behaves differently from what is claimed'),
    'safety-critical': ('5319e7', 'Two-review rule (.github/safety-paths.txt)'),
    'owner:Bakdaulet-omeraiuly': ('0e8a16', 'Research / vision / simulation'),
    'owner:adilnurgg': ('0e8a16', 'Backend / agents / security / web / cloud / CI'),
    'owner:HyorinmaruK': ('0e8a16', 'Physical / firmware / presentation'),
}
# CI job names that must pass before merging to main (tests.yml + review-gate.yml).
REQUIRED_CHECKS = ['lint', 'types', 'schemas', 'security', 'dependencies', 'test (3.11)', 'test (3.13)', 'safety-review-gate']
SAFETY_PREFIXES = ('BACK-', 'LLM-04', 'LLM-09', 'PHY-04', 'REL-02')  # auth / actuation / CI-rule tasks

_TASK = re.compile(r'^- \[(?P<done>[ x])\] \*\*(?P<id>[A-Z]+-\d+)(?P<rest>.*)$')
_SECTION_OWNER = re.compile(r'^## \d+\. (Bakdaulet|adilnurgg|HyorinmaruK)\b')
_INLINE_OWNER = re.compile(r'^\s*—\s*(Bakdaulet|adilnurgg|HyorinmaruK)\s*:')
_PRIORITY = re.compile(r'^###\s+(P[012])\b')


def parse_tasks(text: str) -> list[dict]:
    owner, priority, tasks = None, 'P0', []
    for line in text.splitlines():
        if line.startswith('## '):
            m = _SECTION_OWNER.match(line)
            owner, priority = (OWNERS[m.group(1)] if m else None), 'P0'
            continue
        m = _PRIORITY.match(line)
        if m:
            priority = m.group(1); continue
        m = _TASK.match(line)
        if not m:
            continue
        rest = m.group('rest')
        inline = _INLINE_OWNER.match(rest)
        who = OWNERS[inline.group(1)] if inline else owner
        summary = re.sub(r'\*\(.*?\)\*', '', rest)  # drop "(done 31 Oct ...)" status notes
        summary = re.sub(r'^[\s—:*]+|\*\*', '', _INLINE_OWNER.sub('', summary)).strip(' :*').replace(' :', ':')
        tasks.append({'id': m.group('id'), 'done': m.group('done') == 'x', 'owner': who, 'priority': priority,
                      'title': f"[{m.group('id')}] {summary[:90].rstrip()}{'…' if len(summary) > 90 else ''}",
                      'line': line, 'safety': m.group('id').startswith(SAFETY_PREFIXES)})
    return tasks


def issue_body(t: dict) -> str:
    return (f"Mirrored from `QUALITYRELAY_18_1_TEAM_TASKS_EN.md` by `scripts/github_board.py`; the task board text is authoritative.\n\n"
            f"> {t['line'][6:]}\n\n**Owner:** {t['owner']}  \n**Priority:** {t['priority']}"
            + ('\n\n**Safety-critical:** PRs for this need two non-author approvals (`safety-review-gate`).' if t['safety'] else ''))


def _gh(*args: str, check=True) -> str:
    r = subprocess.run(['gh', *args], capture_output=True, text=True, check=False)  # nosec B603 B607
    if check and r.returncode != 0:
        raise SystemExit(f"gh {' '.join(args[:3])} failed: {r.stderr.strip()}")
    return r.stdout


def plan(tasks: list[dict]) -> None:
    open_ = [t for t in tasks if not t['done']]
    for t in open_:
        print(f"{t['priority']}  {(t['owner'] or 'UNOWNED'):22} {'SAFETY ' if t['safety'] else '       '}{t['title']}")
    print(f"\n{len(open_)} open tasks would become issues ({len(tasks) - len(open_)} done tasks skipped); "
          f"{sum(1 for t in open_ if not t['owner'])} without an owner.")


def apply(repo: str, tasks: list[dict], project_title: str) -> None:
    for name, (color, desc) in LABELS.items():
        _gh('label', 'create', name, '--repo', repo, '--color', color, '--description', desc, '--force')
    existing = {i['title'].split(']')[0] + ']' for i in json.loads(
        _gh('issue', 'list', '--repo', repo, '--state', 'all', '--limit', '500', '--json', 'title'))}
    owner_login = repo.split('/')[0]
    projects = json.loads(_gh('project', 'list', '--owner', owner_login, '--format', 'json'))['projects']
    proj = next((p for p in projects if p['title'] == project_title), None)
    if proj is None:
        proj = json.loads(_gh('project', 'create', '--owner', owner_login, '--title', project_title, '--format', 'json'))
        _gh('project', 'link', str(proj['number']), '--owner', owner_login, '--repo', repo, check=False)
    for t in tasks:
        if t['done'] or f"[{t['id']}]" in existing:
            continue
        labels = ['task', t['priority']] + ([f"owner:{t['owner']}"] if t['owner'] else []) + (['safety-critical'] if t['safety'] else [])
        args = ['issue', 'create', '--repo', repo, '--title', t['title'], '--body', issue_body(t), '--label', ','.join(labels)]
        url = _gh(*args, *(['--assignee', t['owner']] if t['owner'] else []), check=False).strip()
        if not url.startswith('https://'):  # owner not a collaborator yet: keep the owner label, skip assignment
            url = _gh(*args).strip()
        _gh('project', 'item-add', str(proj['number']), '--owner', owner_login, '--url', url)
        print(f'created {url}  {t["title"]}')
    print(f"Project: {proj.get('url', project_title)}. In the web UI add a Board view grouped by Assignee "
          "(views cannot be created through the API).")


def protect(repo: str) -> None:
    body = {'required_status_checks': {'strict': True, 'contexts': REQUIRED_CHECKS},
            'enforce_admins': True,
            'required_pull_request_reviews': {'required_approving_review_count': 1, 'require_code_owner_reviews': True,
                                              'dismiss_stale_reviews': True, 'require_last_push_approval': True},
            'restrictions': None, 'allow_force_pushes': False, 'allow_deletions': False,
            'required_conversation_resolution': True}
    r = subprocess.run(['gh', 'api', '-X', 'PUT', f'repos/{repo}/branches/main/protection', '--input', '-'],  # nosec B603 B607
                       input=json.dumps(body), capture_output=True, text=True, check=False)
    print(r.stdout or r.stderr)
    if r.returncode:
        raise SystemExit(1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', choices=['plan', 'apply', 'protect'])
    ap.add_argument('--repo', default='Bakdaulet-omeraiuly/qualityrelay')
    ap.add_argument('--project', default='QualityRelay 18.1 ownership board')
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[union-attr]  # task text has → ↔ –
    tasks = parse_tasks(TASK_BOARD.read_text(encoding='utf-8'))
    if a.step == 'plan':
        plan(tasks)
    elif a.step == 'apply':
        apply(a.repo, tasks, a.project)
    else:
        protect(a.repo)
    return 0


if __name__ == '__main__':
    sys.exit(main())
