import re
import datetime as dt

from fiftystates.scrape import NoDataForPeriod
from fiftystates.scrape.bills import BillScraper, Bill
from fiftystates.scrape.votes import Vote
from fiftystates.scrape.pa import metadata
from fiftystates.scrape.pa.utils import (bill_abbr, start_year,
                                         parse_action_date,
                                         bill_list_url, history_url, info_url,
                                         vote_url)

from BeautifulSoup import BeautifulSoup


def action_type(action):
    return 'other'


class PABillScraper(BillScraper):
    state = 'pa'

    def scrape(self, chamber, year):
        session = "%s-%d" % (year, int(year) + 1)
        found = False
        for s in metadata['sessions']:
            if s['name'] == session:
                found = True
                specials = s['sub_sessions']
                break
        if not found:
            raise NoDataForPeriod(year)

        self.scrape_session(chamber, session)

        for special in specials:
            session_num = re.search('#(\d+)', special).group(1)
            self.scrape_session(chamber, session, int(session_num))

    def scrape_session(self, chamber, session, special=0):
        session_url = bill_list_url(chamber, session, special)
        
        with self.urlopen(session_url) as bill_list_page:
            bill_list_page = BeautifulSoup(bill_list_page)
            bill_link_re = "body=%s&type=(B|R)&bn=\d+" % bill_abbr(chamber)

            for link in bill_list_page.findAll(href=re.compile(bill_link_re)):
                self.parse_bill(chamber, session, special, link)

    def parse_bill(self, chamber, session, special, link):
        bill_number = link.contents[0]
        type = re.search('type=(B|R|)', link['href']).group(1)
        bill_id = "%s%s %s" % (bill_abbr(chamber), type, bill_number)

        bill_info_url = info_url(chamber, session, special, type, bill_number)

        with self.urlopen(bill_info_url) as info_page:
            info_page = BeautifulSoup(info_page)
            title_label = info_page.find(text='Short Title:')
            title = title_label.findNext().contents[0]

            bill = Bill(session, chamber, bill_id, title)
            bill.add_source(bill_info_url)

            self.parse_bill_versions(bill, info_page)

            self.parse_history(bill, history_url(chamber, session, special,
                                                 type, bill_number))

            self.parse_votes(bill, vote_url(chamber, session, special,
                                            type, bill_number))

            self.save_bill(bill)

    def parse_bill_versions(self, bill, info_page):
        """
        Grab links to all versions of a bill from its info page.
        """
        pn_table = info_page.find('div', {"class": 'pn_table'})
        text_rows = pn_table.findAll('tr')[1:]

        for row in text_rows:
            text_link = row.td.a
            text_url = 'http://www.legis.state.pa.us%s' % text_link['href']
            text_name = text_link.contents[0].strip()
            bill.add_version(text_name, text_url)

    def parse_history(self, bill, url):
        """
        Grab all history data (actions and votes) for a given bill provided
        the url to its history page.
        """
        bill.add_source(url)
        with self.urlopen(url) as history_page:
            history_page = BeautifulSoup(history_page)
            self.parse_sponsors(bill, history_page)
            self.parse_actions(bill, history_page)

    def parse_sponsors(self, bill, history_page):
        """
        Grab all of a bill's sponsors from its history page.
        """
        # Sponsor format changed in 2009
        if int(start_year(bill['session'])) < 2009:
            sponsors = history_page.find(
                text='Sponsors:').parent.findNext('td').find(
                'td').string.strip().replace(' and', ',').split(', ')

            bill.add_sponsor('primary', sponsors[0])

            for cosponsor in sponsors[1:]:
                bill.add_sponsor('cosponsor', cosponsor)
        else:
            sponsors = history_page.find(
                text='Sponsors:').parent.findNext().findAll('a')

            bill.add_sponsor('primary', sponsors[0].contents[0])

            for cosponsor in sponsors[1:]:
                bill.add_sponsor('cosponsor', cosponsor.contents[0])

    def parse_actions(self, bill, history_page):
        """
        Grab all of a bill's actions from its history page.
        """
        act_table = history_page.find(text="Actions:").parent.findNextSibling()
        act_chamber = bill['chamber']

        for row in act_table.findAll('tr'):
            act_raw = ""
            for node in row.td.div:
                if hasattr(node, 'contents'):
                    if len(node.contents) > 0:
                        act_raw += node.contents[0]
                else:
                    act_raw += node
            act_raw = act_raw.replace('&#160;', ' ')
            act_match = re.match('(.*),\s+((\w+\.?) (\d+), (\d{4}))', act_raw)

            if act_match:
                date = parse_action_date(act_match.group(2).strip())
                action = act_match.group(1).strip()
                type = action_type(action)
                bill.add_action(act_chamber, action, date,
                                type=type)
            else:
                # Handle actions from the other chamber
                # ("In the (House|Senate)" row followed by actions that
                # took place in that chamber)
                cham_match = re.match('In the (House|Senate)', act_raw)
                if not cham_match:
                    # Ignore?
                    continue

                if cham_match.group(1) == 'House':
                    act_chamber = 'lower'
                else:
                    act_chamber = 'upper'

    def parse_votes(self, bill, url):
        """
        Grab all of the votes for a bill given the url of its primary
        votes page.
        """
        bill.add_source(url)
        with self.urlopen(url) as votes_page:
            votes_page = BeautifulSoup(votes_page)
            for td in votes_page.findAll('td', {'class': 'vote'}):
                prev = td.findPrevious().contents[0].strip()
                if prev == 'Senate':
                    chamber = 'upper'
                    location = ''
                elif prev == 'House':
                    chamber = 'lower'
                    location = ''
                else:
                    # Committee votes come in a number of different formats
                    # that we don't handle yet
                    continue

                chamber_votes_url = td.a['href']
                self.parse_chamber_votes(chamber, bill, chamber_votes_url)

    def parse_chamber_votes(self, chamber, bill, url):
        """
        Grab all votes for a bill that occurred in a given chamber.
        """
        bill.add_source(url)
        with self.urlopen(url) as chamber_votes_page:
            chamber_votes_page = BeautifulSoup(chamber_votes_page)
            for link in chamber_votes_page.findAll(
                'a', href=re.compile('rc_view')):

                vote_details_url = "http://www.legis.state.pa.us/CFDOCS/"\
                    "Legis/RC/Public/%s" % link['href']
                vote = self.parse_vote_details(vote_details_url)
                bill.add_vote(vote)

    def parse_vote_details(self, url):
        """
        Grab the details of a specific vote, such as how each legislator
        voted.
        """

        def find_vote(letter):
            return vote_page.findAll('span', {'class': 'font8text'},
                                     text=letter)

        with self.urlopen(url) as vote_page:
            vote_page = BeautifulSoup(vote_page)
            header = vote_page.find('div', {'class': 'subHdrGraphic'})

            if 'Senate' in header.string:
                chamber = 'upper'
            else:
                chamber = 'lower'

            # we'll use the link back to the bill as a base to
            # get the motion/date
            linkback = vote_page.find(
                'a', href=re.compile('billinfo')).parent.parent
            date = linkback.find('div').string
            date = dt.datetime.strptime(date, "%A, %B %d, %Y")
            motion = linkback.findNextSibling('div')
            if motion.a:
                motion = "%s %s" % (motion.a.string,
                                    motion.contents[-1].string.strip())
            elif motion.span:
                motion = "%s %s" % (motion.span.string.strip(),
                                    motion.contents[-1].string.strip())
            else:
                motion = motion.string.strip().replace('&nbsp;', '')

            yes_count = int(vote_page.find('div', text='YEAS').next.string)
            no_count = int(vote_page.find('div', text='NAYS').next.string)
            lve_count = int(vote_page.find('div', text='LVE').next.string)
            nv_count = int(vote_page.find('div', text='N/V').next.string)
            other_count = lve_count + nv_count

            passed = yes_count > no_count
            vote = Vote(chamber, date, motion, passed, yes_count, no_count,
                        other_count)
            vote.add_source(url)

            # find the votes by the inner text. because background colors lie.
            yes_votes = [vote.yes, find_vote('Y')]
            no_votes = [vote.no, find_vote('N')]
            nv_votes = [vote.other, find_vote('E') + find_vote('X')]

            for (action, votes) in (yes_votes, no_votes, nv_votes):
                for a_vote in votes:
                    action(a_vote.parent.findNextSibling('span').string)

            if len(vote['yes_votes']) != yes_count:
                raise ScrapeError('wrong yes count %d/%d' %
                                  (len(vote['yes_votes']), yes_count))
            if len(vote['no_votes']) != no_count:
                raise ScrapeError('wrong no count %d/%d' %
                                  (len(vote['no_votes']), no_count))
            if len(vote['other_votes']) != other_count:
                raise ScrapeError('wrong other count %d/%d' %
                                  (len(vote['other_votes']), other_count))
        return vote
