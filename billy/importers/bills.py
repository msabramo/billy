#!/usr/bin/env python
import os
import re
import glob
import json
import logging
from collections import defaultdict

from billy.conf import settings
from billy.utils import metadata, term_for_session
from billy import db
from billy.importers.names import get_legislator_id
from billy.importers.subjects import SubjectCategorizer
from billy.importers.utils import (insert_with_id, update, prepare_obj,
                                   next_big_id, oysterize, fix_bill_id)

import pymongo

logger = logging.getLogger('billy')


def ensure_indexes():
    # accomodates basic search / unique constraint
    db.bills.ensure_index([('state', pymongo.ASCENDING),
                           ('session', pymongo.ASCENDING),
                           ('chamber', pymongo.ASCENDING),
                           ('bill_id', pymongo.ASCENDING)],
                          unique=True)
    # used for search in conjunction with ElasticSearch
    db.bills.ensure_index([('versions.doc_id', pymongo.ASCENDING),
                           ('created_at', pymongo.DESCENDING)])
    # TODO: add a _current_term, _current_session index
    # TODO: re-evaluate if the below indices are needed
    db.bills.ensure_index([('state', pymongo.ASCENDING),
                           ('session', pymongo.ASCENDING),
                           ('chamber', pymongo.ASCENDING),
                           ('subjects', pymongo.ASCENDING)])
    db.bills.ensure_index([('state', pymongo.ASCENDING),
                           ('session', pymongo.ASCENDING),
                           ('chamber', pymongo.ASCENDING),
                           ('sponsors.leg_id', pymongo.ASCENDING)])


def import_votes(data_dir):
    pattern = os.path.join(data_dir, 'votes', '*.json')
    paths = glob.glob(pattern)

    votes = defaultdict(list)

    for path in paths:
        with open(path) as f:
            data = prepare_obj(json.load(f))

        # need to match bill_id already in the database
        bill_id = fix_bill_id(data.pop('bill_id'))

        votes[(data['bill_chamber'], data['session'], bill_id)].append(data)

    logger.info('imported %s vote files' % len(paths))
    return votes

def oysterize_version(bill, version):
    titles = [bill['title']] + bill.get('alternate_titles', [])
    logger.info('{0} tracked in oyster'.format(version['doc_id']))
    oysterize(version['url'], bill['state'] + ':billtext',
              id=version['doc_id'],
              # metadata
              mimetype=version.get('mimetype', None),
              titles=titles,
              state=bill['state'], session=bill['session'],
              chamber=bill['chamber'], bill_id=bill['bill_id'],
              subjects=bill.get('subjects', []),
              sponsors=[s['leg_id'] for s in bill['sponsors']],
             )


def import_bill(data, votes, categorizer):
    level = data['level']
    abbr = data[level]

    # clean up bill_ids
    data['bill_id'] = fix_bill_id(data['bill_id'])
    if 'alternate_bill_ids' in data:
        data['alternate_bill_ids'] = [fix_bill_id(bid) for bid in
                                      data['alternate_bill_ids']]

    # move subjects to scraped_subjects
    # NOTE: intentionally doesn't copy blank lists of subjects
    # this avoids the problem where a bill is re-run but we can't
    # get subjects anymore (quite common)
    subjects = data.pop('subjects', None)
    if subjects:
        data['scraped_subjects'] = subjects

    # update categorized subjects
    if categorizer:
        categorizer.categorize_bill(data)

    # this is a hack added for Rhode Island where we can't
    # determine the full bill_id, if this key is in the metadata
    # we just use the numeric portion, not ideal as it won't work
    # in states where HB/SBs overlap, but in RI they never do
    if metadata(abbr).get('_partial_vote_bill_id'):
        # pull off numeric portion of bill_id
        numeric_bill_id = data['bill_id'].split()[1]
        bill_votes = votes.pop((data['chamber'], data['session'],
                                numeric_bill_id), [])
    else:
        # add loaded votes to data
        bill_votes = votes.pop((data['chamber'], data['session'],
                                data['bill_id']), [])

    data['votes'].extend(bill_votes)

    bill = db.bills.find_one({'level': level, level: abbr,
                              'session': data['session'],
                              'chamber': data['chamber'],
                              'bill_id': data['bill_id']})

    # keep vote/doc ids consistent
    vote_matcher = VoteMatcher(abbr)
    doc_matcher = DocumentMatcher(abbr)
    if bill:
        vote_matcher.learn_ids(bill['votes'])
        doc_matcher.learn_ids(bill['versions'] + bill['documents'])
    vote_matcher.set_ids(data['votes'])
    doc_matcher.set_ids(data['versions'] + data['documents'])

    # match sponsor leg_ids
    for sponsor in data['sponsors']:
        id = get_legislator_id(abbr, data['session'], None,
                               sponsor['name'])
        sponsor['leg_id'] = id

    for vote in data['votes']:

        # committee_ids
        if 'committee' in vote:
            committee_id = get_committee_id(level, abbr, vote['chamber'],
                                            vote['committee'])
            vote['committee_id'] = committee_id

        # vote leg_ids
        for vtype in ('yes_votes', 'no_votes', 'other_votes'):
            svlist = []
            for svote in vote[vtype]:
                id = get_legislator_id(abbr, data['session'],
                                       vote['chamber'], svote)
                svlist.append({'name': svote, 'leg_id': id})

            vote[vtype] = svlist

    data['_term'] = term_for_session(abbr, data['session'])

    alt_titles = set(data.get('alternate_titles', []))

    for version in data['versions']:
        # push versions to oyster
        if settings.ENABLE_OYSTER and 'url' in version:
            oysterize_version(data, version)

        # Merge any version titles into the alternate_titles list
        if 'title' in version:
            alt_titles.add(version['title'])
        if '+short_title' in version:
            alt_titles.add(version['+short_title'])
    try:
        # Make sure the primary title isn't included in the
        # alternate title list
        alt_titles.remove(data['title'])
    except KeyError:
        pass
    data['alternate_titles'] = list(alt_titles)

    if not bill:
        insert_with_id(data)
        return "insert"
    else:
        update(bill, data, db.bills)
        return "update"


def import_bills(abbr, data_dir):
    data_dir = os.path.join(data_dir, abbr)
    pattern = os.path.join(data_dir, 'bills', '*.json')

    counts = {
        "update": 0,
        "insert": 0,
        "total": 0
    }

    votes = import_votes(data_dir)
    try:
        categorizer = SubjectCategorizer(abbr)
    except Exception as e:
        logger.debug('Proceeding without subject categorizer: %s' % e)
        categorizer = None

    paths = glob.glob(pattern)
    for path in paths:
        with open(path) as f:
            data = prepare_obj(json.load(f))

        counts["total"] += 1
        ret = import_bill(data, votes, categorizer)
        counts[ret] += 1

    logger.info('imported %s bill files' % len(paths))

    for remaining in votes.keys():
        logger.debug('Failed to match vote %s %s %s' % tuple([
            r.encode('ascii', 'replace') for r in remaining]))

    meta = db.metadata.find_one({'_id': abbr})
    level = meta['level']
    populate_current_fields(level, abbr)

    ensure_indexes()

    return counts

def populate_current_fields(level, abbr):
    """
    Set/update _current_term and _current_session fields on all bills
    for a given location.
    """
    meta = db.metadata.find_one({'_id': abbr})
    current_term = meta['terms'][-1]
    current_session = current_term['sessions'][-1]

    for bill in db.bills.find({'level': level, level: abbr}):
        if bill['session'] == current_session:
            bill['_current_session'] = True
        else:
            bill['_current_session'] = False

        if bill['session'] in current_term['sessions']:
            bill['_current_term'] = True
        else:
            bill['_current_term'] = False

        db.bills.save(bill, safe=True)


class GenericIDMatcher(object):

    def __init__(self, abbr):
        self.abbr = abbr
        self.ids = {}

    def _reset_sequence(self):
        self.seq_for_key = defaultdict(int)

    def _get_next_id(self):
        return next_big_id(self.abbr, self.id_letter, self.id_collection)

    def nondup_key_for_item(self, item):
        # call user's key_for_item
        key = self.key_for_item(item)
        # running count of how many of this key we've seen
        seq_num = self.seq_for_key[key]
        self.seq_for_key[key] += 1
        # append seq_num to key to avoid sharing key for multiple items
        return key + (seq_num,)

    def learn_ids(self, item_list):
        """ read in already set ids on objects """
        self._reset_sequence()
        for item in item_list:
            key = self.nondup_key_for_item(item)
            self.ids[key] = item[self.id_key]

    def set_ids(self, item_list):
        """ set ids on an object, using internal mapping then new ids """
        self._reset_sequence()
        for item in item_list:
            key = self.nondup_key_for_item(item)
            item[self.id_key] = self.ids.get(key) or self._get_next_id()


class VoteMatcher(GenericIDMatcher):
    id_letter = 'V'
    id_collection = 'vote_ids'
    id_key = 'vote_id'

    def key_for_item(self, vote):
        return (vote['motion'], vote['chamber'], vote['date'],
                vote['yes_count'], vote['no_count'], vote['other_count'])


class DocumentMatcher(GenericIDMatcher):
    id_letter = 'D'
    id_collection = 'document_ids'
    id_key = 'doc_id'

    def key_for_item(self, document):
        # URL is good enough as a key
        return (document['url'],)


__committee_ids = {}


def get_committee_id(level, abbr, chamber, committee):
    key = (level, abbr, chamber, committee)
    if key in __committee_ids:
        return __committee_ids[key]

    spec = {'level': level, level: abbr, 'chamber': chamber,
            'committee': committee, 'subcommittee': None}

    comms = db.committees.find(spec)

    if comms.count() != 1:
        spec['committee'] = 'Committee on ' + committee
        comms = db.committees.find(spec)

    if comms and comms.count() == 1:
        __committee_ids[key] = comms[0]['_id']
    else:
        __committee_ids[key] = None

    return __committee_ids[key]
