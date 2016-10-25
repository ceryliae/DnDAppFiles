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
        self.files = [et.parse(f) for f in filenames]
        self.roots = [f.getroot() for f in self.files]

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

        # Include only of of each element with same name
        elements = [item[-1] for i, item in enumerate(items)
                    if not i or item[0] != items[i-1][0]]

        print 'Removed %d duplicate(s)' % (len(items) - len(elements))

        self.roots[0][:] = elements
        return self.files[0].write(output, encoding='UTF-8')


    def combine_concatenate(self, output):
        """Combine the xml files by concating the items

        :param output: filepath in with the result will be stored.

        """
        for r in self.roots[1:]:
            self.roots[0].extend(r.getchildren())

        return self.files[0].write(output, encoding='UTF-8')


def create_category_compendiums():
    """Create the category compendiums

    :return: list of output paths.

    """
    categories = ['Items', 'Character', 'Spells', 'Bestiary']
    output_paths = []
    for category in categories:
        filenames = glob('%s/*.xml' % category)
        output_path = COMPENDIUM.format(category=category)
        output_paths.append(output_path)
        XMLCombiner(filenames).combine_pruned(output_path)
    return output_paths


def create_full_compendium():
    """Create the category compendiums and combine them into full compendium"""

    category_paths = create_category_compendiums()

    full_path = COMPENDIUM.format(category='Full')
    XMLCombiner(category_paths).combine_concatenate(full_path)


if __name__ == '__main__':
    create_full_compendium()
