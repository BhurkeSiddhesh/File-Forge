import subprocess
import os

branches_raw = subprocess.check_output(['git', 'branch', '-r'], text=True).strip().split('\n')
branches = [b.strip() for b in branches_raw if 'origin/HEAD' not in b and 'origin/main' not in b]

with open('all_diffs.txt', 'w', encoding='utf-8') as f:
    for b in branches:
        try:
            f.write(f"=== {b} ===\n")
            # We want to diff against the merge base, not the direct origin/main diff which includes all of main's changes if the branch is old.
            # Actually, `git diff origin/main...b` (three dots) does exactly this!
            stat = subprocess.check_output(['git', 'diff', f'origin/main...{b}', '--stat'], text=True)
            f.write(stat + '\n')
            
            # Also get the actual patch to look at what changed.
            patch = subprocess.check_output(['git', 'diff', f'origin/main...{b}'], text=True)
            # just save the files changed to not blow up the log
            # Let's write the names and insertion/deletion summary
            
        except subprocess.CalledProcessError as e:
            f.write(f"Error diffing {b}: {e}\n")
