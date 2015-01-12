import re
import csv
import unicodecsv

from openelex.base.load import BaseLoader
from openelex.models import RawResult
from openelex.lib.text import ocd_type_id, slugify
from .datasource import Datasource

"""
Nevada elections have pre-processed CSV results files for county results from 2000-2012, and
XML files for 2012 and 2014. Pre-processed precinct-level CSV files are available for elections
from 2004-2012. All CSV versions are contained in the https://github.com/openelections/openelections-data-nv
repository.
"""

class LoadResults(object):
    """Entry point for data loading.

    Determines appropriate loader for file and triggers load process.

    """

    def run(self, mapping):
        election_id = mapping['pre_processed_url']
        if mapping['raw_url'] != '':
            loader = NVXmlLoader()
        elif 'precinct' in election_id:
            loader = NVPrecinctLoader()
        else:
            loader = NVCountyLoader()
        loader.run(mapping)


class NVBaseLoader(BaseLoader):
    datasource = Datasource()

    target_offices = set([
        'PRESIDENT AND VICE PRESIDENT OF THE UNITED STATES',
        'PRESIDENT',
        'UNITED STATES SENATOR',
        'U.S. REPRESENTATIVE IN CONGRESS',
        'GOVERNOR',
        'LIEUTENANT GOVERNOR',
        'SECRETARY OF STATE',
        'STATE TREASURER',
        'STATE CONTROLLER',
        'ATTORNEY GENERAL',
        'STATE SENATE',
        'STATE ASSEMBLY',
    ])

    district_offices = set([
        'U.S. REPRESENTATIVE IN CONGRESS',
        'STATE SENATE',
        'STATE ASSEMBLY',
    ])

    def _skip_row(self, row):
        """
        Should this row be skipped?

        This should be implemented in subclasses.
        """
        return False

    def _build_contest_kwargs(self, row):
        if 'primary' in self.mapping['election']:
            office = row['office'].split('(')[0].split(', ')[0].strip()
            primary_party = row['office'].strip().split('(')[1].split(')')[0]
            if 'DISTRICT' in row['office'].upper():
                # 2004 primary district has no comma
                district = row['office'].split(', ')[1].split(' (')[0].strip()
            else:
                district = None
        else:
            primary_party = None
            if 'DISTRICT' in row['office'].upper():
                district = row['office'].split(', ')[1].strip()
                office = row['office'].split(', ')[0].strip()
            else:
                district = None
                office = row['office'].strip()
        return {
            'office': office,
            'district': district,
            'primary_party': primary_party,
            'party': primary_party
        }

    def _build_candidate_kwargs(self, row):
        return {
            'full_name': row['candidate'].strip()
        }

class NVPrecinctLoader(NVBaseLoader):
    """
    Loads Nevada results for 2004-2012.

    Format:

    Nevada has HTML files that have been converted to CSV files for elections after 2004 primary.
    Header rows are identical but not always in the same order, so we just use the first row.
    """

    def load(self):
        # use first row as headers, not pre-canned list
        # need to use OCD_ID from jurisdiction in mapping
        self._common_kwargs = self._build_common_election_kwargs()
        self._common_kwargs['reporting_level'] = 'precinct'
        # Store result instances for bulk loading
        results = []

        with self._file_handle as csvfile:
            reader = unicodecsv.DictReader(csvfile, encoding='latin-1')
            for row in reader:
                if self._skip_row(row):
                    continue
                rr_kwargs = self._common_kwargs.copy()
                rr_kwargs.update(self._build_contest_kwargs(row))
                rr_kwargs.update(self._build_candidate_kwargs(row))
                jurisdiction = row['precinct'].strip()
                if row['votes'].strip() == '':
                    votes = 'N/A'
                else:
                    votes = int(row['votes'].replace(',','').strip())
                rr_kwargs.update({
                    'jurisdiction': jurisdiction,
                    'ocd_id': "{}/precinct:{}".format(self.mapping['ocd_id'], ocd_type_id(jurisdiction)),
                    'votes': votes
                })
                results.append(RawResult(**rr_kwargs))
        RawResult.objects.insert(results)

    def _skip_row(self, row):
        return row['office'].split(',')[0].strip().upper() not in self.target_offices

class NVCountyLoader(NVBaseLoader):
    """
    Loads Nevada county-level results for 2000-2014 elections.
    """

    def load(self):
        # use first row as headers, not pre-canned list
        # need to use OCD_ID from jurisdiction in mapping
        self._common_kwargs = self._build_common_election_kwargs()
        self._common_kwargs['reporting_level'] = 'county'
        # Store result instances for bulk loading
        results = []

        with self._file_handle as csvfile:
            reader = unicodecsv.DictReader(csvfile, encoding='latin-1')
            for row in reader:
                if self._skip_row(row):
                    continue
                rr_kwargs = self._common_kwargs.copy()
                rr_kwargs.update(self._build_contest_kwargs(row))
                rr_kwargs.update(self._build_candidate_kwargs(row))
                jurisdiction = self.mapping['name']
                if row['party'] and row['party'] != '&nbsp;':
                    party = row['party'].strip()
                else:
                    party = None
                rr_kwargs.update({
                    'party': party,
                    'jurisdiction': jurisdiction,
                    'ocd_id': self.mapping['ocd_id'],
                    'votes': int(row['votes'].replace(',','').strip())
                })
                results.append(RawResult(**rr_kwargs))
        RawResult.objects.insert(results)

    def _skip_row(self, row):
        return row['office'].split(',')[0].strip().upper() not in self.target_offices

class NVXmlLoader(NVBaseLoader):
    pass
