#!/usr/bin/env python
from __future__ import with_statement
import os
import re
import sys
import time
import glob
import datetime

try:
    import json
except:
    import simplejson as json

from fiftystates import settings
from fiftystates.backend import db
from fiftystates.backend.utils import (insert_with_id, update, prepare_obj,
                                       base_arg_parser)

import pymongo
import argparse
import name_tools


def import_legislators(state, data_dir):
    data_dir = os.path.join(data_dir, state)
    pattern = os.path.join(data_dir, 'legislators', '*.json')
    for path in glob.iglob(pattern):
        with open(path) as f:
            data = prepare_obj(json.load(f))

        import_legislator(data)


def import_legislator(data):
    # Rename 'role' -> 'type'
    for role in data['roles']:
        if 'role' in role:
            role['type'] = role['role']
            del role['role']

    cur_role = data['roles'][0]

    leg = db.legislators.find_one(
        {'state': data['state'],
         'full_name': data['full_name'],
         'roles': {'$elemMatch': {
                    'term': cur_role['term'],
                    'chamber': cur_role['chamber'],
                    'type': cur_role['type'],
                    'district': cur_role['district']}}})

    if not leg:
        metadata = db.metadata.find_one({'_id': data['state']})

        term_names = [t['name'] for t in metadata['terms']]

        try:
            index = term_names.index(cur_role['term'])

            if index > 0:
                prev_term = term_names[index - 1]
                prev_leg = db.legislators.find_one(
                    {'full_name': data['full_name'],
                     'roles': {'$elemMatch': {
                                'state': data['state'],
                                'term': prev_term,
                                'chamber': cur_role['chamber'],
                                'type': cur_role['type'],
                                'district': cur_role['district']}}})

                if prev_leg:
                    update(prev_leg, data, db.legislators)
                    return
        except ValueError:
            print "Invalid term: %s" % cur_role['term']
            sys.exit(1)

        data['created_at'] = datetime.datetime.now()
        data['updated_at'] = datetime.datetime.now()

        insert_with_id(data)
    else:
        update(leg, data, db.legislators)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        parents=[base_arg_parser],
        description='Import scraped state legislators into a mongo databse.')

    parser.add_argument('--data_dir', '-d', type=str,
                        help='the base Fifty State data directory')

    args = parser.parse_args()

    if args.data_dir:
        data_dir = args.data_dir
    else:
        data_dir = settings.FIFTYSTATES_DATA_DIR

    import_legislators(args.state, data_dir)
