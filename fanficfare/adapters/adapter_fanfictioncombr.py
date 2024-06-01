from __future__ import absolute_import
import logging
logger = logging.getLogger(__name__)
import re
import requests

from bs4 import BeautifulSoup
from ..htmlcleanup import stripHTML
from ..base_helpers import get_mapping, normalize_character_name, normalize_tag
from .. import exceptions as exceptions

# py2 vs py3 transition
from ..six import text_type as unicode

from .base_adapter import BaseSiteAdapter,  makeDate

def getClass():
    return FanfictionComBrAdapter

class FanfictionComBrAdapter(BaseSiteAdapter):

    def __init__(self, config, url):
        BaseSiteAdapter.__init__(self, config, url)

        # get storyId from url--url validation guarantees query is only sid=1234
        self.storyId = unicode(self.getStoryId(url))
        self.story.setMetadata('storyId', self.storyId)

        # normalized story URL
        self._setURL('https://' + self.getSiteDomain() + '/historia/'+self.story.getMetadata('storyId'))

        # Each adapter needs to have a unique site abbreviation.
        self.story.setMetadata('siteabbrev',self.getSiteAbbrev())

        # The date format will vary from site to site.
        # http://docs.python.org/library/datetime.html#strftime-strptime-behavior
        self.dateformat = "%d/%m/%Y às %H:%M"

        self.chapter_photoUrl = {}

        
    @staticmethod
    def getSiteDomain():
        return 'fanfiction.com.br'


    @classmethod
    def getAcceptDomains(cls):
        return ['fanfiction.com.br']


    @classmethod
    def getSiteExampleURLs(cls):
        #Accepted formats
        #https://fanfiction.com.br/historia/1234
        #https://fanfiction.com.br/historia/782662/story-name
        return "https://"+cls.getSiteDomain()+"/historia/1234/story-name https://"+cls.getSiteDomain()+"/historia/1234" 


    # @classmethod
    def getSiteURLPattern(self):
        #Does it cover all addresses?
        #logger.debug(r"https?://(" + r"|".join([x.replace('.','\.') for x in self.getAcceptDomains()]) + r")/historia/(?P<storyId>\d+)(?:/[a-zA-Z0-9-]+-)?")
        return r"https?://(" + r"|".join([x.replace('.','\.') for x in self.getAcceptDomains()]) + r")/historia/(?P<storyId>\d+(?:/[a-zA-Z0-9-]+-)?)"


    @classmethod
    def getSiteAbbrev(cls):
        return 'nyah'
    

    def getStoryId(self, url):

        # get storyId from url--url validation guarantees query correct
        m = re.match(self.getSiteURLPattern(), url)
        if m:
            return m.group('storyId')
        else:
            raise exceptions.InvalidStoryURL(url, self.getSiteDomain(), self.getSiteExampleURLs())


    def extractChapterUrlsAndMetadata(self):

        data = self.get_request(self.url)
        # use BeautifulSoup HTML parser to make everything easier to find.
        soup = self.make_soup(data)
        # Now go hunting for all the meta data and the chapter list.

        # Title
        title = soup.find('h3')
        self.story.setMetadata('title', title.find('a').text.strip())
        logger.debug('title %s', self.story.getMetadata('title'))

        # Authors
        # Find authorid and URL
        authors = soup.findAll('a', {'class':'tooltip_userinfo'})
        for author in authors:
            self.story.addToList('authorId', author['href'].split('/')[-2])
            self.story.addToList('authorUrl', 'https://'+self.getSiteDomain()+author['href'])
            self.story.addToList('author', author.text.strip())
        logger.debug('author %s', self.story.getMetadata('author'))

        # Cover image
        cover_img = soup.find('img', class_='story_index_capa')
        if cover_img:
            self.setCoverImage(self.url, 'https:'+cover_img['src'])

        
        def parse_until_br(attribute, start_index, element_list, mapping=None):
            for element in element_list[start_index:]:
                if element.name == 'br':
                    break

                elif element.name == 'b' and attribute != 'category':
                    break

                else:
                    if attribute == 'rating' and element.name == 'span':
                        rating = element.next_sibling.strip()
                        if rating == '18+':
                            self.story.setMetadata(attribute, 'Explicit')
                        elif rating == '16+':
                            self.story.setMetadata(attribute, 'Mature')
                        elif rating == '13+':
                            self.story.setMetadata(attribute, 'Teen And Up Audiences')
                        elif rating == 'Livre':
                            self.story.setMetadata('rating', 'General Audiences')
                        else:
                            logger.debug('Rating not found: %s', rating)
                            self.story.setMetadata('rating', '?.'+rating)

                    elif attribute == 'numChapters':
                        matches = re.findall(r'\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?', element.next_sibling.strip())
                        numChapters = int(matches[0].replace(',', '').replace('.', '')) 
                        numWords = int(matches[1].replace(',', '').replace('.', ''))
                        self.story.setMetadata('numChapters', numChapters)
                        self.story.setMetadata('numWords', numWords)

                    elif attribute == 'status':
                        if element.next_sibling.strip() == 'Sim':
                            self.story.setMetadata(attribute, 'Completed')
                        elif element.next_sibling.strip() == 'Não':
                            self.story.setMetadata(attribute, 'In-Progress')

                    elif attribute == 'category':
                        if element.name == 'a':
                            self.story.addToList(attribute, element.text.strip())

                    elif attribute.startswith('date'):
                        self.story.setMetadata(attribute, makeDate(element.next_sibling.strip(' |'), self.dateformat))

                    else:
                        terms = element.next_sibling.strip().split(', ') if element.next_sibling else []
                        for term in terms or []:
                            self.story.addToList(attribute, term)
                            if attribute == 'characters':
                                character = normalize_character_name(term)[0]
                                if character != None:
                                    self.story.addToList('beta_'+attribute, character)
                            elif attribute == 'genre' or attribute == 'warnings':
                                tags = normalize_tag(term, mapping)[0]
                                for tag in tags or []:
                                    self.story.addToList('beta_tags', tag)

            return
        
        language_tags = self.getConfigList('language_tags')[0]
        mapping = get_mapping(language_tags)
        date_updated = None

        # Informações Gerais
        information = soup.find('div', id='left_part')
        #logger.debug('information: (%s)', information)
        info_contents = information.find_all(True)
        for i, content in enumerate(info_contents):

            if content.name == 'span':
                if content.b.get_text() == 'Classificação:':
                    parse_until_br('rating', i, info_contents)
                elif content.b.get_text() == 'Categorias:':
                    parse_until_br('category', i, info_contents)
                elif content.b.get_text() == 'Personagens:':
                    parse_until_br('characters', i, info_contents)
                elif content.b.get_text() == 'Capítulos:':
                    parse_until_br('numChapters', i, info_contents)
                elif content.b.get_text() == 'Terminada:':
                    parse_until_br('status', i, info_contents)
                elif content.b.get_text() == 'Publicada:':
                    parse_until_br('datePublished', i, info_contents)
                elif content.b.get_text() == 'Atualizada:':
                    parse_until_br('dateUpdated', i, info_contents)
            
            elif content.name == 'strong':
                if content.text.strip() == 'Gêneros:':
                    parse_until_br('genre', i, info_contents, mapping)
                elif content.text.strip() == 'Avisos:':
                    parse_until_br('warnings', i, info_contents, mapping)

        self.story.addToList('beta_tags', 'Fanfiction')

        newestChapter = None
        self.newestChapterNum = None # save for comparing during update.
        # Find the chapters:
        chapter_container = soup.find('div', class_='container_chapter_list')
        if chapter_container:
        # Find all the chapter elements within the container
            chapters = chapter_container.find_all('div', class_='chapter_list informacoes_adicionais')
            for chapter in chapters:

                # Extract the chapter number and title text
                chapter_number_text = chapter.text.split('.')[0].strip() # Gets the number before the dot and trims whitespace
                chapter_title_text = chapter.a.get_text().strip() # Gets the chapter title text
        
                # Combine the chapter number and title
                full_chapter_title = f"{chapter_number_text}. {chapter_title_text}"

                date = self.story.getMetadata('dateUpdated')
                #chapterDate = makeDate(date, self.dateformat).date()
                chapterDate = date

                self.add_chapter(full_chapter_title, 'https://'+self.getSiteDomain()+chapter.a['href'], {'date':chapterDate})

                if newestChapter == None or chapterDate > newestChapter:
                    newestChapter = chapterDate
                    self.newestChapterNum = self.story.getMetadata('numChapters')
            
        logger.debug('numChapters: (%s)', self.story.getMetadata('numChapters'))

        # Summary
        summary = information.find('p')
        self.story.setMetadata('description', summary)

    ## Normalize chapter URLs in case of title change
    def normalize_chapterurl(self,url):
        #https://fanfiction.com.br/historia/1234/story-name/capitulo/56/
        url = re.sub(r"https?://("+self.getSiteDomain()+r"/historia/\d+/capitulo/\d+)$",
                     r"https://\1",url)
        return url


    def getChapterText(self, url):
        logger.debug('Getting chapter text from: %s' % url)

        save_chapter_soup = self.make_soup(self.get_request(url))
        ## use the div because the full soup will also have <html><body>.
        ## need save_chapter_soup for .new_tag()
        save_chapter = BeautifulSoup("", "html.parser").new_tag("div")

        chapter_dl_soup = self.make_soup(self.get_request(url))
        if None == chapter_dl_soup:
            raise exceptions.FailedToDownload("Error downloading Chapter: %s!  Missing required element!" % url)
        chapter_text = chapter_dl_soup.find('div', class_='historia')

        exclude_notes=self.getConfigList('exclude_notes')

        def append_tag(elem, tag, string=None, classes=None):
            '''bs4 requires tags be added separately.'''
            new_tag = save_chapter_soup.new_tag(tag)
            if string:
                new_tag.string=string
            if classes:
                new_tag['class']=[classes]
            elem.append(new_tag)
            return new_tag
        

        def parse_text_block(text_block):
            next_element = text_block.find_next_sibling()
            full_string = ''
            while next_element:
                full_string += str(next_element)
                next_element = next_element.find_next_sibling()
                full_html = BeautifulSoup(full_string, 'html.parser')
            return full_html


        chaphead = chapfoot = None

        chaphead_block = save_chapter_soup.find('h4', text='Notas iniciais do capítulo')
        if chaphead_block:
            chaphead = parse_text_block(chaphead_block)

        chapfoot_block = save_chapter_soup.find('h4', text='Notas finais do capítulo')
        if chapfoot_block:
            chapfoot = parse_text_block(chapfoot_block)
    
        chaptext = chapter_text
    
        head_notes_div = append_tag(save_chapter,'div',classes="fff_chapter_notes fff_head_notes")
        if 'chapterheadnotes' not in exclude_notes:
            if chaphead != None:
                append_tag(head_notes_div,'b',"Notas iniciais do capítulo:")
                append_tag(head_notes_div,'br')
                head_notes_div.append(chaphead)
                append_tag(head_notes_div,'hr')

        save_chapter.append(chaptext)

        foot_notes_div = append_tag(save_chapter,'div',classes="fff_chapter_notes fff_foot_notes")
        ## Can appear on every chapter
        if 'chapterfootnotes' not in exclude_notes:
            if chapfoot != None:
                append_tag(foot_notes_div,'hr')
                append_tag(foot_notes_div,'b',"Notas finais do capítulo:")
                foot_notes_div.append(chapfoot)

        ## remove empty head/food notes div(s)
        if not head_notes_div.find(True):
            head_notes_div.extract()
        if not foot_notes_div.find(True):
            foot_notes_div.extract()

        return self.utf8FromSoup(url,save_chapter)