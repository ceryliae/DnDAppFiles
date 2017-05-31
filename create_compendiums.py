"""Create compendiums by combining the XML

Run this file from the root directory (the place where this file resides)

    $ python create_compendiums.py

This will update the XML files in the Compendiums directory.

You can review optional parameters (such separating subclasses into separate 'class' entries) by invoking help

    $ python create_compendiums.py -h

"""
from xml.etree import ElementTree as et
from glob import glob
import re
import argparse

COMPENDIUM = 'Compendiums/{category} Compendium.xml'


class XMLCombiner(object):

    """Combiner for xml files with multiple way to perform the combining"""

    def __init__(self, filenames):
        assert len(filenames) > 0, 'No filenames!'
        self.files = [self.informed_parse(f) for f in filenames]
        self.roots = [f.getroot() for f in self.files]
        self.remove_excludes()

    def informed_parse(self, filename):
        """Parse source XML, logs filename on error"""
        try:
            return et.parse(filename)
        except:
            print filename
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
        if root.getchildren() is None: return
        for child in root.getchildren():
            if any(child.get(tag) for tag in args.excludes):
                root.remove(child)
            else:
                self.remove_excludes_recursive(child)

    def combine_templates(self, output_path):
        """ Finds Base/Sub class nodes and combines into a Class Compendium"""

        items = self.remove_duplicates()
        self.setup_class(items)
        self.flatten_classes(items)

        # flatten out items for adding back into root
        elements = [ element for categories in items.values() for element in categories.values()]

        # drop <subclass> elements etc, FC5 doesn't recognize them and will treat <feature>s in them as <feat>s
        self.roots[0][:] = [element for element in elements
                            if element.tag not in ['baseclass', 'subclass']]
        return self.files[0].write(output_path, encoding='UTF-8')     

    def remove_duplicates(self):
        """ Loads base elements into dictionaries, primarily so sub-classes can reference base-classes. Also removes and logs duplicates."""
        items = {'race':{},
        'class':{}, 'baseclass': {}, 'subclass':{},
        'background':{}, 'feat':{}, 'item':{}, 'monster':{}, 'spell':{}}
        
        for r in self.roots:
            for element in r:
                name = element.findtext('name')
                if name in items[element.tag]: print 'Duplicate {0} named {1}'.format(element.tag, name)
                items[element.tag][name] = element
        return items

    def setup_class(self, items):
        # make class elements for baseclasses
        for name, element in items['baseclass'].items():
            if args.basetype_format == 'complete': # else 'none' to not include a full class
                if name in items['class']: print 'Duplicate' # should be redundant
                deep_class = et.fromstring('<class name="{0}"></class>'.format(name))
                deep_class.extend(list(element))
                items['class'][name] = deep_class
            if args.subtype_format == 'reference': # else usable or none. 'usable' doesn't need !Base and 'none' doesn't want it
                base_name = '{0} !Base'.format(name)
                wide_class = et.fromstring('\<class name="{0}">\n\t\t</class>'.format(base_name))
                wide_class.extend(list(element))
                wide_class.append(et.fromstring('<name>{0}</name>'.format(base_name))) # a bit hacky but shadow other 'name's with base_name
                items['class'][base_name] = wide_class

    def flatten_classes(self, items):
        # combine subclasses with classes
        for name, element in items['subclass'].items():
            base_name = element.get('baseclass')
            if base_name not in items['baseclass']: print 'Missing baseclass {0} for {1}'.format(base_name, name)

            # build combined classes. wide, deep, or both
            if args.basetype_format == 'complete': # else 'none' to not include a full class
                deep_class = items['class'][base_name]
                deep_class.extend(list(element))
                deep_class.append(et.fromstring('<name>{0}</name>'.format(base_name))) # a bit hacky but shadow other 'name's with base_name
                items['class'][base_name] = deep_class

            if args.subtype_format != 'none': # useable or reference both want entries
                wide_class = et.fromstring('<class name="{0}">\n\t</class>'.format(name))
                if args.subtype_format == 'usable': # skip baseclass info for 'reference'
                    wide_class.extend(list(items['baseclass'][base_name]))
                wide_class.extend(list(element))
                items['class'][name] = wide_class

    def combine_pruned(self, output_path):
        """Combine the xml files and sort the items alphabetically

        Items with the same name are removed.

        :param output_path: filepath in with the result will be stored.

        """
        items = []
        for r in self.roots:
            for element in r:
                name = element.findtext('name')
                items.append((name, element))
        items.sort()

        # Include only one of each element with same name
        elements = [item[-1] for i, item in enumerate(items)
                    if not i or item[0] != items[i-1][0]]

        print 'Removed {0} duplicate(s) from {1}'.format((len(items) - len(elements)), output_path)

        self.roots[0][:] = elements
        return self.files[0].write(output_path, encoding='UTF-8')


    def combine_concatenate(self, output_path):
        """Combine the xml files by concating the items

        :param output_path: filepath in with the result will be stored.

        """
        for r in self.roots[1:]:
            self.roots[0].extend(r.getchildren())

        return self.files[0].write(output_path, encoding='UTF-8')


def create_category_compendiums():
    """Create the category compendiums

    :return: list of output paths.

    """
    categories = ['Items', 'Character', 'Spells', 'Bestiary', 'Unearthed Arcana']
    output_paths = []
    for category in categories:
        if (args.includes != ['*'] and (category not in args.includes)): continue
        filenames = glob('%s/*.xml' % category)
        output_path = COMPENDIUM.format(category=category)

        """build UA compendium, but exclude from Full"""
        if category != 'Unearthed Arcana':
            output_paths.append(output_path)
        XMLCombiner(filenames).combine_pruned(output_path)
    return output_paths


def create_class_compendiums():
    classes = {}
    output_paths = []

    # Group source xml files into base class
    for file in glob('Character/Classes/*/*.xml'):
        class_name, subclass_name = re.search(r"/([^/]+)/([^/]+)\.xml$", file).groups()
        if args.includes == ['*'] or (class_name in args.includes):
            if class_name not in classes: classes[class_name] = []
            classes[class_name].append(file)

    # combine subclasses with baseclass to make <class> entries
    for name, filenames in classes.items():
        output_path = COMPENDIUM.format(category=name)
        output_paths.append(output_path)
        XMLCombiner(filenames).combine_templates(output_path)
    return output_paths

def create_full_compendium():
    """Create the category compendiums and combine them into full compendium"""

    class_paths = create_class_compendiums()

    category_paths = create_category_compendiums()

    if args.includes != ['*']: return
    full_path = COMPENDIUM.format(category='Full')
    XMLCombiner(category_paths + class_paths).combine_concatenate(full_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Compile Compendiums (including subclasses) into single file(s)')
    parser.add_argument('-b', '--basetype-format', dest='basetype_format', action='store',
                        choices=['complete', 'none'], default='complete',
                        help='Whether to include a class including every subclass. complete: include everything. none: do not include a full Class (see --subtype-format=usable)')
    parser.add_argument('-s', '--subtype-format', dest='subtype_format', action='store',
                        choices=['usable', 'reference', 'none'], default='none',
                        help='How to handle subclasses. usable: combine Base and Subs into unique Classes (good for running a character). reference: generate unique Classes for Base and Subs, but do not combine (each Class will be incomplete, but consise). none: do not generate unique Classes for Base and Subs.')

    parser.add_argument('-i', '--includes', dest='includes', action='store', nargs='+',
                        default=['*'],
                        help='limit script to certain Compendiums, eg Fighter. primarily useful for testing.')
    parser.add_argument('-e', '--excludes', dest='excludes', action='store', nargs='+',
                        choices=['UA', 'M', 'HB', 'PS', 'IL'], default=['M', 'HB'],
                        help='exclude certain content: UnearthedArcana, Modern (and Futuristic content), HomeBrew (and 3rd Party), PseudoSpells (Class Features logged as Spells, eg Maneuvers), InlinedLists (additional Eldritch Invocations). Default=[M, HB]')
    args = parser.parse_args()

    print "Arguments: {0}".format(vars(args))
    create_full_compendium()
