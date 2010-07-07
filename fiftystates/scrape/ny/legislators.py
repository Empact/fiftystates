#!/usr/bin/env python
from fiftystates.scrape.legislators import LegislatorScraper, Legislator
from votesmart import votesmart, VotesmartApiError
from fiftystates import settings

votesmart.apikey = settings.VOTESMART_API_KEY


class NYLegislatorScraper(LegislatorScraper):
    state = 'ny'

    def scrape(self, chamber, year):
        if chamber == 'upper':
            officeId = 9
        else:
            officeId = 7
        for official in votesmart.officials.getByOfficeState(officeId, 'NY'):
            full_name = official.firstName
            if official.middleName:
                full_name += " " + official.middleName
            full_name += " " + official.lastName
            leg = Legislator('2009-2010', chamber, official.officeDistrictName,
                             full_name, official.firstName, official.lastName,
                             official.middleName, official.officeParties)
            self.save_legislator(leg)
