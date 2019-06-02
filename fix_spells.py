"""Fix spells in Bestiary based on spells in Spells

Run this file from the root directory (the place where this file resides)

    $ python fix_spells.py

This will update the XML files in the Bestiary directory.

You can review optional parameters by invoking help

    $ python fix_spells.py -h

"""
import argparse
import os
import re

from difflib import unified_diff
from glob import glob
from xml.etree import ElementTree as et


def find_spells(homebrew=False, verbose=False):
    spell_sources = glob('Spells/*.xml')
    if homebrew:
        spell_sources += glob('Homebrew/Spells/*.xml')

    if verbose:
        # List files which will be used as source
        print('Using these spell sources:\n  {}'.format('\n  '.join(spell_sources)))

    spell_names = []

    for spell_source in spell_sources:
        root = et.parse(spell_source)

        for spell_name in root.findall('./spell/name'):
            spell_names.append(spell_name.text)

    # Checks
    if len(spell_names) != len(set(spell_name.casefold() for spell_name in spell_names)):
        print('Duplicate spells were found!')

    return set(spell_names)


def fix_bestiary_spells(homebrew=False, verbose=False, dry_run=False):
    spell_names = find_spells(homebrew=homebrew, verbose=verbose)

    bestiary_sources = glob('Bestiary/*.xml')
    if homebrew:
        bestiary_sources += glob('Homebrew/Monsters/*.xml')

    if verbose:
        # List files which will be fixed
        print('Fixing these bestiary sources:\n  {}'.format('\n  '.join(bestiary_sources)))

    for bestiary_source in bestiary_sources:
        with open(bestiary_source, mode='r') as bestiary_file:
            bestiary_content = bestiary_file.read()
        original_content = bestiary_content
        for spell_name in spell_names:
            bestiary_content = re.sub(
                r'(<spells(>|.*, )){spell_name}((, .*|<)/spells>)'.format(spell_name=spell_name),
                r'\1{spell_name}\3'.format(spell_name=spell_name),
                bestiary_content,
                flags=re.IGNORECASE
            )

        if verbose:
            # Show diff for each fixed file
            diff = ''.join(unified_diff(
                original_content.splitlines(keepends=True),
                bestiary_content.splitlines(keepends=True),
                fromfile=bestiary_source,
                tofile='fixed',
                n=0
            ))
            if diff:
                print(diff)

        if not dry_run:
            with open(bestiary_source, mode='w') as bestiary_file:
                bestiary_file.write(bestiary_content)
    if dry_run:
        print('Dry run, did not write results back to files')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Fix spells in Bestiaries using the spell sources.',
    )
    parser.add_argument('--homebrew', action='store_true', help='Include homebrew spells and bestiary')
    parser.add_argument('--verbose', action='store_true', help='Be more verbose while processing')
    parser.add_argument('--dry-run', action='store_true', help='Do not write fixed content back to files')
    args = parser.parse_args()

    fix_bestiary_spells(homebrew=args.homebrew, verbose=args.verbose, dry_run=args.dry_run)
