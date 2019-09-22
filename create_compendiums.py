#!/usr/bin/env python
"""Create compendiums by combining the XML

Run this file from the root directory (the place where this file resides)

    $ python create_compendiums.py

This will update the XML files in the Compendiums directory.

You can review optional parameters (such separating subclasses into separate 'class' entries) by invoking help

    $ python create_compendiums.py -h

"""
import argparse
import copy
import fnmatch
import os
import re

from glob import glob
from xml.etree import ElementTree as et
from xml.etree.ElementTree import ParseError

COMPENDIUM = 'Compendiums/{category} Compendium.xml'


class XMLCombiner(object):

    """Combiner for xml files with multiple way to perform the combining"""

    def __init__(self, filenames):
        assert len(filenames) > 0, 'No filenames!'
        # TODO: clean up instance variables
        # sources was added to hold a reference to the filename for logging
        # files/roots are not strictly necessary but more descriptive than anonymous structure sources
        self.sources = [[data[0], data[1], data[1].getroot()] for data in
                        [[name, self.informed_parse(name)] for name in filenames]]
        self.files = [source[1] for source in self.sources]
        self.roots = [source[2] for source in self.sources]
        self.remove_excludes()

    def informed_parse(self, filename):
        """Parse source XML, logs filename on error"""
        try:
            return et.parse(filename)
        except ParseError as pe:
            print(filename)
            print(pe)
            raise

    def remove_excludes(self):
        """Removes xml with excluded attributes (default [M, HB])
           this handles attributes on root <compendium>"""
        for r in self.roots:
            if any(r.get(tag) for tag in args.excludes):
                r.clear()
            else:
                self.remove_excludes_recursive(r)

    def remove_excludes_recursive(self, root):
        """Removes xml with excluded attributes (default [M, HB])
           this handles attributes on descendent nodes"""
        if root.getchildren() is None:
            return

        for child in root.getchildren():
            if any(child.get(tag) for tag in args.excludes):
                root.remove(child)
            else:
                self.remove_excludes_recursive(child)

    def combine_templates(self, output_path):
        """ Finds Base/Sub class nodes and combines into a Class Compendium"""
        print("Compiling to {0}".format(output_path))

        items = self.remove_duplicates()
        self.compile_bases(items)
        self.compile_subs(items)

        # flatten out items for adding back into root
        elements = [element for categories in items.values() for element in categories.values()]
        # for element in elements:
        #     print(u"|{0}/{1}|".format(element.tag, element.findtext('name') or element.get('class')))
        elements.sort(key=lambda element: (element.tag, element.findtext('name') or element.get('class')))

        # drop <subclass> elements etc, FC5 doesn't recognize them and will treat <feature>s in them as <feat>s
        self.roots[0][:] = [element for element in elements
                            if element.tag not in ['baseclass', 'subclass']]
        return self.files[0].write(output_path, encoding='UTF-8')

    def remove_duplicates(self):
        """ Loads base elements into dictionaries, primarily so sub-classes can reference base-classes.
        Also removes and logs duplicates."""
        items = {'race': {}, 'class': {}, 'baseclass': {}, 'subclass': {},
                 'background': {}, 'feat': {}, 'item': {}, 'monster': {},
                 'spell': {}, 'spellList': {}, 'borrowSpells': {}, 'container': {}}
        attribution = copy.deepcopy(items)

        for filename, f, r in self.sources:
            for element in r:
                if element.tag == 'spellList':
                    name = element.get('class')
                    if name not in items[element.tag]:
                        items[element.tag][name] = element
                    else:
                        items[element.tag][name].extend(list(element))
                elif element.tag == 'borrowSpells':
                    name = element.get('fromClass')
                    item = items[element.tag]
                    if name not in item:
                        item[name] = element
                    else:
                        item[name].set('class', item[name].get('class')+","+element.get('class'))
                else:
                    name = element.findtext('name')
                    if name in attribution[element.tag]:
                        print('Duplicate {0} named {1} [{2} => {3}]'.format(element.tag, name,
                                                                            attribution[element.tag][name], filename))
                    attribution[element.tag][name] = filename
                    items[element.tag][name] = element

        # Try to include classes from <spellList>s into the <spell>s for FC5 compatibility
        for class_name, spells in items['spellList'].items():
            for name in [index.get('name') for index in spells]:
                if name in items['spell']:
                    class_element = items['spell'][name].find('classes')
                    class_list = [foo.strip() for foo in class_element.text.split(',')]
                    if class_name not in class_list:
                        class_list.append(class_name)
                        class_element.text = ', '.join(class_list)

        # resolve borrowed spells
        for ref_class, borrow_classes in items['borrowSpells'].items():
            for name in items['spell']:
                class_element = items['spell'][name].find('classes')
                class_list = [foo.strip() for foo in class_element.text.split(',')]
                if ref_class in class_list:
                    for borrow_class in [b.strip() for b in borrow_classes.get('class').split(',')]:
                        if borrow_class not in class_list:
                            class_list.append(borrow_class)
                            class_element.text = ', '.join(class_list)
        return items

    def compile_bases(self, items):
        # make <class> from <baseclass>
        for name, element in items['baseclass'].items():
            if args.basetype_format == 'complete':  # else 'none' to not include a full class
                if name in items['class']:
                    print('Duplicate')  # should be redundant
                complete_class = et.fromstring('<class name="{0}"></class>'.format(name))
                complete_class.extend(list(element))
                items['class'][name] = complete_class

            # reference, usable, or none. 'usable' doesn't need !Base and 'none' doesn't want it
            if args.subtype_format == 'reference':
                base_name = '{0} !Base'.format(name)
                reference_class = et.fromstring('<class name="{0}">\n\t\t<name>{0}</name>\n</class>'.format(base_name))
                reference_class.extend(list(element))
                reference_class.remove(reference_class.find('name[last()]'))
                items['class'][base_name] = reference_class

    def compile_subs(self, items):
        # combine subclasses with classes
        for name, element in sorted(items['subclass'].items()):
            if args.basetype_format == 'complete':  # else 'none' to not include a full class
                base_name = element.get('baseclass')

                # distribute archetypes over various "forms" of a class, e.g., ranger and ranger revised
                # this will cause a lot of missing base class items for the sub_type usable flag,
                # but everything seems to generate correctly anyway

                for c_name in items['class']:
                    if base_name not in c_name:
                        continue
                    if c_name not in items['baseclass']:
                        print('Missing baseclass {0} for {1}'.format(c_name, name))

                    complete_class = items['class'][c_name]
                    complete_class.extend(list(element))
                    complete_class.remove(complete_class.find('name[last()]'))
                    items['class'][c_name] = complete_class

            if args.subtype_format != 'none':  # useable or reference both want entries
                reference_class = et.fromstring('<class name="{0}">\n\t</class>'.format(name))
                if args.subtype_format == 'usable':  # skip baseclass info for 'reference'
                    base_class = copy.deepcopy(items['baseclass'][base_name])
                    base_class.remove(base_class.find('name'))
                    reference_class.extend(list(base_class))
                reference_class.extend(list(element))
                items['class'][name] = reference_class

    def combine_pruned(self, output_path):
        """Combine the xml files and sort the items alphabetically

        Items with the same name are removed.

        :param output_path: filepath in with the result will be stored.

        """
        print("Compiling to {0}".format(output_path))
        items = []
        for r in self.roots:
            for element in r:
                name = element.findtext('name')
                items.append((name, element))
        items.sort()

        # Include only one of each element with same name
        elements = [item[-1] for i, item in enumerate(items)
                    if not i or item[0] != items[i-1][0]]

        print('Removed {0} duplicate(s) from {1}'.format((len(items) - len(elements)), output_path))

        self.roots[0][:] = elements
        return self.files[0].write(output_path, encoding='UTF-8')


def create_category_compendiums():
    """Create the category compendiums

    :return: list of output paths.

    """
    categories = ['Items', 'Character', 'Spells', 'Bestiary', 'Unearthed Arcana', 'Homebrew']
    output_paths = []
    for category in categories:
        if args.includes != ['*'] and (category not in args.includes):
            continue

        # filenames = glob('%s/*.xml' % category)
        filenames = []

        if category is 'Homebrew':  # populate base classes to allow for homebrew archetypes
            for root, dirnames, fnames in os.walk('Character/Classes'):
                for filename in [fname for fname in fnmatch.filter(fnames, '*.xml') if "(" not in fname]:
                    class_name = re.search('(.*)\.xml', filename).groups()[0]
                    if args.includes == ['*'] or args.includes == ['Homebrew'] or class_name in args.includes:
                        filenames.append(os.path.join(root, filename))
        for root, dirnames, fnames in os.walk(category):
            for filename in fnmatch.filter(fnames, '*.xml'):
                filenames.append(os.path.join(root, filename))
        output_path = COMPENDIUM.format(category=category)

        # Build UA compendium, but exclude from Full unless included
        if category != 'Unearthed Arcana' or 'Unearthed Arcana' in args.includes:
            output_paths.append(output_path)
        XMLCombiner(filenames).combine_templates(output_path)
    return output_paths


def create_class_compendiums():
    classes = {}
    output_paths = []

    files = glob('Character/Classes/*/*.xml')

    if (args.includes == ['*'] and 'HB' not in args.excludes) or 'Homebrew' in args.includes:
        files += glob('Homebrew/Classes/*/*.xml')

    # Group source xml files into base class
    for file in files:
        class_name, subclass_name = re.search(r"/([^/]+)/([^/]+)\.xml$", file).groups()
        if args.includes == ['*'] or (class_name in args.includes):
            if class_name not in classes:
                classes[class_name] = []

            classes[class_name].append(file)

    # combine subclasses with baseclass to make <class> entries
    for name, filenames in classes.items():
        output_path = COMPENDIUM.format(category=name)
        output_paths.append(output_path)
        XMLCombiner(filenames).combine_templates(output_path)
    return output_paths


def create_full_compendium():
    """Create the category compendiums and combine them into full compendium"""

    # create the Compendiums directory if it doesn't already exist
    print("Making sure compendiums directory exists...")

    if not os.path.exists("Compendiums"):
        print("Making Compendiums directory")
        try:
            os.makedirs("Compendiums")
        except OSError:
            print("Error making Compendiums directory")
            return

    class_paths = create_class_compendiums()

    category_paths = create_category_compendiums()

    if args.name == 'Full' and args.includes != ['*']:
        category = 'Limited'
    else:
        category = args.name
    full_path = COMPENDIUM.format(category=category)
    XMLCombiner(category_paths + class_paths).combine_templates(full_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Compile Compendiums (including subclasses) into single file(s)',
        formatter_class=argparse.RawTextHelpFormatter
        )

    parser.add_argument('-b', '--basetype-format', dest='basetype_format', action='store',
                        choices=['complete', 'none'], default='complete',
                        help='''\
(default=%(default)s)
Whether to include a class including every subclass.
complete: include everything.
none: do not include a full Class
(see --subtype-format=usable)
                            ''')
    parser.add_argument('-s', '--subtype-format', dest='subtype_format', action='store',
                        choices=['usable', 'reference', 'none'], default='none',
                        help='''\
(default=%(default)s)
How to handle subclasses.
usable: combine Base and Subs into unique Classes (good for running a character).
reference: generate unique Classes for Base and Subs, but do not combine (each Class will be incomplete, but concise).
none: do not generate unique Classes for Base and Subs.
                            ''')

    parser.add_argument('-e', '--excludes', dest='excludes', action='store', nargs='*',
                        choices=['UA', 'MF', 'HB', 'PS', 'IL'], default=['MF', 'HB'],
                        help='''\
(default=%(default)s)
exclude certain content:
UA UnearthedArcana
MF renaissance Modern and Futuristic content
HB HomeBrew (and 3rd Party)
PS PseudoSpells (Class Features logged as Spells, eg Maneuvers)
IL InlinedLists (eg repeated Eldritch Invocations)
                            ''')

    parser.add_argument('-i', '--includes', dest='includes', action='store', nargs='+',
                        default=['*'],
                        help='''\
(default=%(default)s)
limit script to certain Compendiums, eg Fighter. primarily useful for testing.
If Homebrew is specified, this will override the HB parameter in excludes
                            ''')

    parser.add_argument('-n', '--name', dest='name', action='store',
                        default='Full',
                        help='''\
(default=%(default)s)
name for the final combined Compendium, defaults to Full or Limited if using --includes
                            ''')

    args = parser.parse_args()

    print("Arguments: {0}".format(vars(args)))

    # includes will override excludes if homebrew is in both
    if 'HB' in args.excludes and 'Homebrew' in args.includes:
        args.excludes.remove('HB')

    create_full_compendium()
