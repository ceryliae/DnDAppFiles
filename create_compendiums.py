"""Create compendiums by combining the XML

Run this file from the root directory (the place where this file resides)

    $ python create_compendiums.py

This will update the XML files in the Compendiums directory.

"""
from xml.etree import ElementTree as et
from glob import glob


COMPENDIUM = 'Compendiums/{category} Compendium.xml'


class XMLCombiner(object):

    """Combiner for xml files with multiple way to perform the combining"""

    def __init__(self, filenames):
        assert len(filenames) > 0, 'No filenames!'
        self.files = [self.informed_parse(f) for f in filenames]
        self.roots = [f.getroot() for f in self.files]

    def informed_parse(self, filename):
        try:
            return et.parse(filename)
        except:
            print filename
            raise

    def combine_pruned(self, output):
        """Combine the xml files and sort the items alphabetically

        Items with the same name are removed.

        :param output: filepath in with the result will be stored.

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

        print 'Removed %d duplicate(s)' % (len(items) - len(elements))

        self.roots[0][:] = elements
        return self.files[0].write(output, encoding='UTF-8')

    def combine_templates(self, output, format):
        items = {'race':{}, 'class':{}, 'subclass':{}, 'background':{}, 'feat':{}, 'item':{}, 'monster':{}, 'spell':{}}
        for r in self.roots:
            for element in r:
                name = element.findtext('name')
                if name in items[element.tag]: print 'Duplicate {0} named {1}'.format(element.tag, name)
                items[element.tag][name] = element

        # combine subclasses with classes
        for name, element in items['subclass'].items():
            base_name = element.get('baseclass')
            if base_name not in items['class']: print 'Missing baseclass {0} for {1}'.format(base_name, name)
            baseclass = items['class'][base_name]

            # build combined classes. wide, deep, or both
            if format != 'wide': # deep or both
                deep_name = '{0}_full'.format(base_name)
                deep_class = items['class'][deep_name] if deep_name in items['class'] else baseclass.copy()
                deep_class.extend(list(element))
                deep_class.append(et.fromstring('<name>{0}</name>'.format(deep_name))) # a bit hacky but shadow other 'name's with deep_name
                items['class'][deep_name] = deep_class
            elif format != 'deep': # wide or both
                wide_class = baseclass.copy()
                wide_class.extend(list(element))
                items['class'][name] = wide_class



        # flatten out myitems for adding back into root
        elements = [ element for categories in items.values() for element in categories.values()]

        # for element in elements:
        #     if element.tag == 'subclass':
        #         print element.findtext('name')
        #         print element.get('baseclass')

        # drop <subclass> elements, FC5 doesn't recognize them
        self.roots[0][:] = [element for element in elements
                            if not element.tag == 'subclass']
        return self.files[0].write(output, encoding='UTF-8')     

    def combine_concatenate(self, output_path):
        """Combine the xml files by concating the items

        :param output: filepath in with the result will be stored.

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
        filenames = glob('%s/*.xml' % category)
        output_path = COMPENDIUM.format(category=category)

        """build UA compendium, but exclude from Full"""
        if output_path != 'Unearthed Arcana':
            output_paths.append(output_path)
        XMLCombiner(filenames).combine_pruned(output_path)
    return output_paths


def create_class_compendiums():
    filenames = glob('Character/Classes/*.xml') # ['Items', 'Character', 'Spells', 'Bestiary', 'Unearthed Arcana']
    output_paths = []
    output_path = COMPENDIUM.format(category='Fighter')
    output_paths.append(output_path)
    XMLCombiner(filenames).combine_templates(output_path, 'deep')
    return output_paths
def create_class_compendiums():
    # Automate classes by directory names. (is there a better way to exclude files?)
    class_names = [ path.split('/')[-1] for path in glob('Character/Classes/*')
                if not re.search('\.', path)]

    output_paths = []
    for class_name in class_names:
        filenames = glob('Character/Classes/{class_name}/*.xml'.format(class_name=class_name))
        output_path = 'Character/Classes/{class_name}.xml'.format(class_name=class_name)
        output_paths.append(output_path)
        XMLCombiner(filenames).combine_templates(output_path, 'deep')
    return output_paths

def create_full_compendium():
    """Create the category compendiums and combine them into full compendium"""

    category_paths = create_category_compendiums()

    full_path = COMPENDIUM.format(category='Full')
    XMLCombiner(category_paths).combine_concatenate(full_path)

import sys
import re
import os
if __name__ == '__main__':
    print sys.argv[1:]
    create_class_compendiums()
    # create_full_compendium()
    # print os.listdir('Character/Classes')
