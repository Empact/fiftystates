import datetime

from fiftystates.scrape import NoDataForPeriod
from fiftystates.scrape.committees import CommitteeScraper, Committee
from fiftystates.scrape.nv.utils import clean_committee_name

import lxml.etree
from dbfpy import dbf
import scrapelib

class NJCommitteeScraper(CommitteeScraper):
    state = 'nj'

    def scrape(self, chamber, year):
        self.save_errors=False

        if year < 1996:
            raise NoDataForPeriod(year)
        elif year == 1996:
            year_abr = 9697
        elif year == 1998:
            year_abr = 9899
        else:
            year_abr = year

        session = (int(year) - 2010) + 214

        if chamber == 'upper':
            self.scrape_committees(year_abr, session)
        elif chamber == 'lower':
            self.scrape_committees(year_abr, session)

    def scrape_committees(self, year_abr, session):

        members_url = 'ftp://www.njleg.state.nj.us/ag/%sdata/COMEMB.DBF' % (year_abr)
        comm_info_url = 'ftp://www.njleg.state.nj.us/ag/%sdata/COMMITT.DBF' % (year_abr)
     
        COMEMB_dbf, resp = self.urlretrieve(members_url)
        COMMIT_dbf, resp2 = self.urlretrieve(comm_info_url)

        members_db = dbf.Dbf(COMEMB_dbf)
        info_db = dbf.Dbf(COMMIT_dbf)

        comm_dictionary = {}

        #Committe Info Database
        for name_rec in info_db:
            abrv = name_rec["code"]
            comm_name = name_rec["descriptio"]
            comm_type = name_rec["type"]
            aide = name_rec["aide"]
            contact_info = name_rec["phone"]

            if abrv[0] == "A":
                chamber = "General Assembly"
            elif abrv[0] == "S":
                chamber = "Senate"

            comm = Committee(chamber, comm_name, comm_type = comm_type, aide = aide, contact_info = contact_info)
            comm.add_source(members_url)
            comm.add_source(comm_info_url)
            comm_dictionary[abrv] = comm

        #Committee Member Database
        for member_rec in members_db:
            abr = member_rec["code"]
            comm_name = comm_dictionary[abr]
            
            leg = member_rec["member"]            
            comm_name.add_member(leg)
            
            self.save_committee(comm_name) 
