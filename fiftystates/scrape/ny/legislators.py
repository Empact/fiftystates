#!/usr/bin/env python
from fiftystates.scrape.legislators import LegislatorScraper, Legislator
from votesmart import votesmart, VotesmartApiError
from fiftystates import settings

votesmart.apikey = settings.VOTESMART_API_KEY


class NYLegislatorScraper(LegislatorScraper):
    state = 'ny'

    class UpperChamber:
        def __init__(self):
            self.name = 'upper'
            self.vote_smart_office_id = 9

        def home_page_for(self, official):
            return ""

        def scrape_home_page_for(self, official):
            return {}

    class LowerChamber:
        def __init__(self):
            self.name = 'lower'
            self.vote_smart_office_id = 7
            self.home_page_root = "http://assembly.state.ny.us/mem/"

        def home_page_for(self, official):
            return self.home_page_root + "?ad=" + official.officeDistrictName

        def scrape_home_page_for(self, official):
            return {"headshot_url": self.home_page_root + 'hdgimages/' + official.officeDistrictName.rjust(3, '0') + '_hdrhs.png'}

    def scrape(self, chamber, year):
        if chamber == 'upper':
            chamber = self.UpperChamber()
        else:
            chamber = self.LowerChamber()
        for official in votesmart.officials.getByOfficeState(chamber.vote_smart_office_id, 'NY'):
            full_name = official.firstName
            if official.middleName:
                full_name += " " + official.middleName
            full_name += " " + official.lastName

            leg = Legislator('2009-2010', chamber.name, official.officeDistrictName,
                             full_name, official.firstName, official.lastName,
                             official.middleName, official.officeParties,
                             **chamber.scrape_home_page_for(official))
            leg.add_source(chamber.home_page_for(official))

            self.save_legislator(leg)
