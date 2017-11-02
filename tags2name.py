# -*- coding: utf-8 -*-
"""
Recursively changes file and directory names to a standard format based on ID3 tags
"""

import sys
import os
import re
import argparse
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen import MutagenError


def get_args():
    """
    Get the command line arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-r', help='set levels of recursion; default 0',
        type=int)
    return parser.parse_args()


class FileTags:
    """
    Holds relevant track data
    """

    TAG_TYPES = {
        'album': ['TALB', 'ALBUM', 'Album', '©alb'],
        'artist': ['TPE1', 'ARTIST', 'Artist', '©ART'],
        'album_artist': ['TPE2', 'ALBUMARTIST', 'Album Artist', 'aART'],
        'title': ['TIT2', 'TITLE', 'Title', '©nam'],
        'track_num': ['TRCK', 'TRACKNUMBER', 'Track', 'trkn'],
        'disc_num': ['TPOS', 'DISCNUMBER', 'Disc', 'disk'],
        'year': ['TYER', 'Year', 'DATE', 'TDRC', '©day'],
        'orig_year': ['TORY', 'ORIGINALYEAR', 'TDOR', 'ORIGINALDATE']
    }
    FORBIDDEN = '<>:"/\\|?*\0'

    def __init__(self):
        self._tags = {
            'album': '',
            'artist': '',
            'album_artist': '',
            'title': '',
            'track_num': '',
            'disc_num': '',
            'year': None,
            'orig_year': None
        }

    def __getitem__(self, key):
        return self._tags[key]

    def set_tags(self, tags):
        """
        Gets relevant tag names out of mutagen tag data
        """
        for tag_name in FileTags.TAG_TYPES:
            for desc in FileTags.TAG_TYPES[tag_name]:
                if desc in tags:
                    if type(tags[desc]) is list:
                        self._tags[tag_name] = tags[desc][0]
                    else:
                        self._tags[tag_name] = tags[desc].text[0]
                    break
        # track number formatting
        match = re.match(r'(\d+)/', self._tags['track_num'])
        if match is not None:
            self._tags['track_num'] = match.group(1)
        self._tags['track_num'] = self._tags['track_num'].zfill(2)
        # disc number formatting
        match = re.match(r'(\d+)/', self._tags['disc_num'])
        if match is not None:
            self._tags['disc_num'] = match.group(1)
        if self._tags['disc_num'] == '':
            self._tags['disc_num'] = '1'
        # date formatting
        if not isinstance(self._tags['year'], str):
            if self._tags['year'] is not None:
                self._tags['year'] = str(self._tags['year'].year)
        if not isinstance(self._tags['orig_year'], str):
            if self._tags['orig_year'] is not None:
                self._tags['orig_year'] = str(self._tags['orig_year'].year)

    def scrub(self):
        """
        Removes forbidden filename characters from tag data
        """
        for tag in self._tags:
            clean = self._tags[tag]
            if not isinstance(clean, str):
                continue
            for forbidden_char in FileTags.FORBIDDEN:
                clean = clean.replace(forbidden_char, '')
            self._tags[tag] = clean


YEAR_ENCLOSER = '[]'
SEPARATOR = ' - '
VALID_FILE_TYPES = ['.mp3', '.flac']


def rename_file(folder, file):
    """
    Renames a file based on its ID3 tags
    """
    full_path = folder + '/' + file
    ext = re.search(r'.\w+$', file)
    if ext is None:
        return
    ext = ext.group()
    folder_data = None
    if ext in VALID_FILE_TYPES:
        try:
            if ext == '.mp3':
                tags = ID3(full_path)
            elif ext == '.flac':
                tags = FLAC(full_path)
        except MutagenError:
            return (None, '', 'missing')
        file_tags = FileTags()
        file_tags.set_tags(tags)
        file_tags.scrub()
        artist = file_tags['album_artist'] or file_tags['artist']
        if artist == '' or file_tags['album'] == ''\
                or file_tags['disc_num'] == '' or file_tags['title'] == '':
            return (None, '', 'missing')
        new_name = (artist + SEPARATOR + file_tags['album']
                    + SEPARATOR + file_tags['disc_num'] + '-'
                    + file_tags['track_num'] + SEPARATOR + file_tags['title'] + ext)
        oldest_year = file_tags['orig_year']
        if not oldest_year:
            oldest_year = file_tags['year']
        if file != new_name:
            os.rename(full_path, folder + '/' + new_name)
            folder_data = (oldest_year, file_tags['album'], 'renamed')
        else:
            folder_data = (oldest_year, file_tags['album'], 'unchanged')
    return folder_data


def scan_album_folder(folder, file_list):
    """
    Renames all files in a folder. If all the files in the folder have the same Year and Album
    metadata, the folder itself will be renamed to the format "[YEAR] ALBUM"
    """
    folder_data = []
    folder_counts = {'found': 0, 'renamed': 0,
                     'unchanged': 0, 'missing': 0, 'folder_rename': ''}
    if folder_data\
            and len(folder_data[0]) == 3\
            and folder_data[0][0]\
            and folder_data[0][1]\
            and all((x[0] == folder_data[0][0] and x[1] == folder_data[0][1]) for x in folder_data):
        pass
    for file in file_list:
        folder_d = rename_file(folder, file)
        if folder_d is not None:
            folder_counts[folder_d[2]] += 1
            folder_counts['found'] += 1
            folder_data.append(folder_d)
    if folder_data\
            and len(folder_data[0]) == 3\
            and folder_data[0][0]\
            and folder_data[0][1]\
            and all((x[0] == folder_data[0][0] and x[1] == folder_data[0][1]) for x in folder_data):
        folder_name = YEAR_ENCLOSER[0] + \
            folder_data[0][0] + YEAR_ENCLOSER[1] + ' ' + folder_data[0][1]
        parent_path = folder.replace(
            re.search(r'[^\\/]+[\\/]?$', folder).group(), '')
        if folder != '.' and folder != parent_path + folder_name:
            counter = 2
            base_dir = parent_path + folder_name
            base_dir = re.search(r'(.*?)\.+$', base_dir)
            if base_dir is None:
                base_dir = parent_path + folder_name
            else:
                base_dir = base_dir.group(1)
            base_dir = base_dir.strip()
            try_dir = base_dir
            while os.path.isdir(try_dir) and counter < 100:
                if try_dir == folder:
                    break
                try_dir = base_dir + ' (' + str(counter) + ')'
                counter += 1
            if try_dir != folder:
                folder_counts['folder_rename'] = (folder, try_dir)
    return folder_counts


# how useful!
# http://stackoverflow.com/questions/229186/os-walk-without-digging-into-directories-below
def walklevel(some_dir, level=0):
    """
    Walk directory to arbitrary depth
    """
    some_dir = some_dir.rstrip(os.path.sep)
    assert os.path.isdir(some_dir)
    num_sep = some_dir.count(os.path.sep)
    for root_clip, dirs_clip, files_clip in os.walk(some_dir):
        yield root_clip, dirs_clip, files_clip
        num_sep_this = root_clip.count(os.path.sep)
        if num_sep + level <= num_sep_this:
            del dirs_clip[:]


def tags2name(recursion_level):
    """
    Perform the (possibly recursive) rename operation and output the results
    """
    result = {'found': 0, 'renamed': 0, 'unchanged': 0,
              'missing': 0, 'renamed_folders': []}
    total_dirs = 0
    # settings output
    print()
    print('-=Settings=-')
    print('Looking for file types: ' + ', '.join(VALID_FILE_TYPES))
    print()
    # directories output
    print()
    print('-=Directories=-')
    for root, _, files in walklevel('.', recursion_level):
        # give us something to look at while it's working
        print('.', end='')
        sys.stdout.flush()
        total_dirs += 1
        new_counts = scan_album_folder(root, files)
        if new_counts['folder_rename']:
            result['renamed_folders'].append(new_counts['folder_rename'])
        result['found'] += new_counts['found']
        result['renamed'] += new_counts['renamed']
        result['unchanged'] += new_counts['unchanged']
        result['missing'] += new_counts['missing']
    print('\nDirectories searched: ' + str(total_dirs))
    sys.stdout.flush()
    # iterate through the folders that need to be renamed, bottom-up
    for ren in reversed(result['renamed_folders']):
        try:
            os.rename(ren[0], ren[1])
            print('RENAMED FOLDER: ' + ren[0] + ' -> ' + ren[1])
        except OSError:
            print('ERROR: could not rename folder "' + ren[0] + '"')
    print()
    # files output
    print()
    print('-=Music files=-')
    print('Found:        ' + str(result['found']))
    print('---------------')
    print('Changed:      ' + str(result['renamed']))
    print('Unchanged:    ' + str(result['unchanged']))
    print('Missing Tags: ' + str(result['missing']))


if __name__ == '__main__':
    if sys.version_info[0] < 3:
        raise Exception("ERROR: this is a Python 3 script!")
    ARGS = get_args()
    tags2name((ARGS.r or 0))
